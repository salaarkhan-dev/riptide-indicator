"""The scan cycle and the loop that drives it.

Imports telegram as a module rather than pulling tg_send into this namespace,
so a test or the flood harness can substitute it in one place.
"""

from __future__ import annotations

import asyncio
import time

from . import mtf
from . import telegram as tg
from .config import (ALERT_ON_FIRST_RUN, BAR_SECONDS, CFG, CONCURRENCY,
                     ENTRY_INTERVAL, FRESH_BARS, INTERVAL, MTF_GRACE_BARS,
                     SCAN_INTERVAL,
                     SWEEP_ALERTS, SWEEP_FRESH_BARS, SWEEP_SRC, log)
from .engine import Sweep, atr_series, run_engine
from .exchange import fetch_candles, list_symbols
from .storage import (already_sent, first_run, meta_get, meta_set, record,
                      record_sweep, sweep_already_sent, sweep_sig, sig_id)

async def scan_symbol(sess, sem, symbol):
    """Returns (setups, sweeps). sweeps is empty unless RIPTIDE_SWEEP_ALERTS."""
    async with sem:
        cs = await fetch_candles(sess, symbol)
        if len(cs) < 100:
            return [], []
        # Structure always comes from the higher timeframe; only the entry can
        # move. Fetched inside the semaphore so the pair counts as one slot.
        ltf = await fetch_candles(sess, symbol, ENTRY_INTERVAL) \
            if ENTRY_INTERVAL else []

        sweeps: list[Sweep] = [] if SWEEP_ALERTS else None
        try:
            setups = run_engine(symbol, cs, sweeps_out=sweeps)
        except Exception as e:
            log.warning("engine failed on %s: %s", symbol, e)
            return [], []

        if ltf:
            atr = atr_series(cs, CFG.atr_len)
            now = int(time.time())
            # A gap needs three lower-timeframe candles measured from the
            # shift bar's OPEN. At the scan that fires when the shift bar
            # closes, only two of them have closed — so the lower timeframe
            # can never have an answer yet on the first look.
            #
            # Sending the higher-timeframe entry then would record the
            # signature and let dedupe suppress the refined entry that
            # arrives a scan later, which is the entry the feature exists to
            # produce. So hold the setup back instead and reconsider next
            # scan; fall back only once the lower timeframe has had a fair
            # chance and the setup would otherwise be lost.
            grace = MTF_GRACE_BARS * BAR_SECONDS[INTERVAL]
            refined = []
            for s in setups:
                r = None
                if 0 <= s.mss_bar < len(atr):
                    r = mtf.refine(s, ltf, atr[s.mss_bar])
                if r is not None:
                    refined.append(r)
                elif now - s.mss_time > grace:
                    refined.append(s)          # no gap came; take the HTF entry
                else:
                    log.debug("%s: holding setup for a %s gap", symbol,
                              ENTRY_INTERVAL)
            setups = refined

        return setups, (sweeps or [])


async def cycle(sess, db, symbols):
    sem = asyncio.Semaphore(CONCURRENCY)
    results = await asyncio.gather(*(scan_symbol(sess, sem, s) for s in symbols))

    bootstrap = first_run(db) and not ALERT_ON_FIRST_RUN
    # /pause records everything as usual but sends nothing, so resuming does
    # not replay the backlog.
    paused = meta_get(db, "alerts_paused", "0") == "1"
    mute = bootstrap or paused
    step = BAR_SECONDS[INTERVAL]
    now = int(time.time())
    sent = 0

    # Sweeps first: the grab precedes the shift, so the heads-up should land
    # before the setup message when both fall in the same cycle.
    swept = 0
    for _, sweeps in results:
        for w in sweeps:
            if SWEEP_SRC is not None and w.src not in SWEEP_SRC:
                continue
            fresh = (now - w.sweep_time) <= SWEEP_FRESH_BARS * step
            sid = sweep_sig(w)
            if sweep_already_sent(db, sid):
                continue
            record_sweep(db, sid, w)
            if fresh and not mute:
                if await tg.tg_send(sess, tg.sweep_message(w)):
                    swept += 1

    for setups, _ in results:
        for s in setups:
            # Only shifts from the last few bars are actionable. Older ones are
            # recorded so a restart cannot re-alert the whole history.
            fresh = (now - s.mss_time) <= FRESH_BARS * step
            sid = sig_id(s)
            if already_sent(db, sid):
                continue
            record(db, sid, s)
            if fresh and not mute:
                if await tg.tg_send(sess, tg.setup_message(s)):
                    sent += 1
    if bootstrap:
        log.info("first run: history recorded, nothing sent")
    elif paused:
        log.info("alerts paused; recorded but not sent")
    if SWEEP_ALERTS:
        log.info("scanned %d symbols, sent %d alerts, %d sweep heads-ups",
                 len(symbols), sent, swept)
    else:
        log.info("scanned %d symbols, sent %d alerts", len(symbols), sent)
    return sent + swept


def seconds_to_next_close(step: int, pad: int = 10) -> float:
    now = time.time()
    return (step - (now % step)) + pad


async def scan_loop(sess, db, state) -> None:
    step = BAR_SECONDS[SCAN_INTERVAL]
    last_symbol_refresh = time.time()
    # Persisted, so "alive" means a day has genuinely passed rather than
    # "the process restarted". Survives updates; a deleted riptide.db
    # resets it, which only costs one extra heartbeat.
    try:
        last_heartbeat = float(meta_get(db, "last_heartbeat", "0") or 0)
    except ValueError:
        last_heartbeat = 0.0

    while True:
        try:
            await asyncio.sleep(seconds_to_next_close(step))
            n = await cycle(sess, db, state["symbols"])
            state["last_cycle"], state["last_sent"] = time.time(), n

            if time.time() - last_symbol_refresh > 21600:      # 6h
                fresh = await list_symbols(sess)
                if fresh:
                    state["symbols"] = fresh
                last_symbol_refresh = time.time()

            # Daily heartbeat, so silence means something is broken rather
            # than that nothing set up.
            if time.time() - last_heartbeat > 86400:
                when = tg.local_clock()
                await tg.tg_send(sess, f"Riptide alive · {len(state['symbols'])} symbols"
                                    + (f" · {when}" if when else ""))
                last_heartbeat = time.time()
                meta_set(db, "last_heartbeat", last_heartbeat)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.exception("cycle error: %s", e)
            await asyncio.sleep(30)
