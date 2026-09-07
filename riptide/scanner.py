"""The scan cycle and the loop that drives it.

Imports telegram as a module rather than pulling tg_send into this namespace,
so a test or the flood harness can substitute it in one place.
"""

from __future__ import annotations

import asyncio
import time

from . import market
from . import mtf
from . import telegram as tg
from . import tracker
from . import trend
from .config import (ALERT_ON_FIRST_RUN, BAR_SECONDS, CFG, CONCURRENCY,
                     EARLY_ALERTS, ENTRY_INTERVAL, FRESH_BARS, INTERVAL,
                     INTERVALS, LOG_MARKET, MTF_GRACE_BARS, POI_REQUIRED,
                     POI_SWEEPS, SCAN_INTERVAL, SWEEP_ALERTS,
                     SWEEP_FRESH_BARS, SWEEP_INTERVALS, SWEEP_SRC,
                     TREND_FILTER, TREND_INTERVAL, log)
from .engine import Early, Sweep, atr_series, run_engine
from .exchange import fetch_candles, list_symbols
from .storage import (already_sent, early_already_sent, early_sig, first_run,
                      meta_get, meta_set, record, record_early,
                      record_sweep, sweep_already_sent, sweep_sig, sig_id)

async def scan_symbol(sess, sem, symbol, trend_on=None, interval=""):
    """
    Returns (setups, sweeps, early, candles). sweeps and early are empty
    unless their alerts are enabled; the candles are handed back so outcome
    tracking can score open signals against the same fetch rather than
    repeating it.

    trend_on defaults to the configured setting; cycle() passes the live
    value so /trend takes effect on the next scan without a restart.
    """
    if trend_on is None:
        trend_on = TREND_FILTER
    interval = interval or INTERVAL
    async with sem:
        cs = await fetch_candles(sess, symbol, interval)
        if len(cs) < 100:
            return [], [], [], cs
        # Structure always comes from the higher timeframe; only the entry can
        # move. Fetched inside the semaphore so the pair counts as one slot.
        ltf = await fetch_candles(sess, symbol, ENTRY_INTERVAL) \
            if ENTRY_INTERVAL else []

        sweeps: list[Sweep] = [] if SWEEP_ALERTS else None
        # Always collected, even when the alert is switched off. Muting a
        # strategy must not also stop measuring it: /stats is the only
        # forward, out-of-sample evidence this project has, and the moment a
        # strategy looks bad is the moment its live sample matters most.
        early: list[Early] = []
        try:
            setups = run_engine(symbol, cs, sweeps_out=sweeps,
                                early_out=early)
            for x in list(setups) + list(early) + list(sweeps or []):
                x.tf = interval
        except Exception as e:
            log.warning("engine failed on %s: %s", symbol, e)
            return [], [], [], cs

        # Gate on the setting, not on the data arriving. A failed lower-
        # timeframe fetch — one rate-limited request among the two per symbol
        # — must not silently downgrade to higher-timeframe entries: refine
        # returns None for an empty list, so the hold below treats it as "no
        # gap yet" and the next scan tries again.
        if ENTRY_INTERVAL:
            if not ltf:
                log.warning("%s: no %s candles this cycle; setups held for a "
                            "retry rather than sent with %s entries",
                            symbol, ENTRY_INTERVAL, INTERVAL)
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

        # Trend alignment is recorded on every signal, whether or not the
        # filter is suppressing anything, so the alert can say which side of
        # the trend it is on. Measured: with the trend +0.119 R per setup,
        # against it -0.016, a 2.8 SE difference over 1188 setups — worth
        # knowing even when taking both. Daily bars are cached for an hour,
        # so this costs one fetch per symbol per hour.
        keep_s, keep_w, keep_e = [], [], []
        for x in setups:
            # detected_time, not mss_time: the gap can arrive up to
            # max_bars_after_mss bars after the shift, and the trend that
            # matters is the one in force when the signal became actionable.
            # Early already used its detection bar; this makes them agree.
            d = await trend.direction_at(sess, symbol, x.detected_time,
                                         fetch_candles)
            x.trend_dir = d or 0
            # DI sets the grade letter; the SuperTrend above still prints
            # beside it so both can be watched live. Same cached daily bars,
            # so this costs no extra request. The filter below deliberately
            # still keys on the SuperTrend: DI has replicated on splits of one
            # window, which earns it the letter, not the power to suppress an
            # alert before /stats has seen it forward.
            x.btc_dir = await trend.btc_at(sess, x.detected_time,
                                          fetch_candles) or 0
            x.di_dir = await trend.di_at(sess, symbol, x.detected_time,
                                         fetch_candles) or 0
            # The stop sits just beyond the raid extreme, and it is the raid
            # that has to land in the daily zone — not the entry, which is a
            # retracement away from it.
            _poi = await trend.poi_at(sess, symbol, x.detected_time, x.stop,
                                       x.is_long, fetch_candles)
            x.poi, x.poi_known = bool(_poi), _poi is not None
            with_trend = d is None or (d > 0) == x.is_long
            if with_trend or not trend_on:
                keep_s.append(x)
        for w in (sweeps or []):
            d = await trend.direction_at(sess, symbol, w.sweep_time, fetch_candles)
            w.trend_dir = d or 0
            w.btc_dir = await trend.btc_at(sess, w.sweep_time,
                                          fetch_candles) or 0
            w.di_dir = await trend.di_at(sess, symbol, w.sweep_time,
                                         fetch_candles) or 0
            # A Sweep has no entry and no stop — it fires before either
            # exists — so the raid price is sweep_extreme itself, and the
            # direction is implied: a swept HIGH is a short bias.
            _poi = await trend.poi_at(sess, symbol, w.sweep_time,
                                      w.sweep_extreme, not w.is_high,
                                      fetch_candles)
            w.poi, w.poi_known = bool(_poi), _poi is not None
            # A swept high implies a short, so it wants a downtrend.
            with_trend = d is None or (d < 0) == w.is_high
            if with_trend or not trend_on:
                keep_w.append(w)
        for e in (early or []):
            d = await trend.direction_at(sess, symbol, e.fvg_time, fetch_candles)
            e.trend_dir = d or 0
            e.btc_dir = await trend.btc_at(sess, e.fvg_time,
                                          fetch_candles) or 0
            e.di_dir = await trend.di_at(sess, symbol, e.fvg_time,
                                         fetch_candles) or 0
            _poi = await trend.poi_at(sess, symbol, e.fvg_time, e.stop,
                                       e.is_long, fetch_candles)
            e.poi, e.poi_known = bool(_poi), _poi is not None
            with_trend = d is None or (d > 0) == e.is_long
            if with_trend or not trend_on:
                keep_e.append(e)

        # Latest close, for the alert footer. Display only — nothing decides
        # anything on it, and the engine has already finished by this point.
        px = cs[-1].c
        for x in (*keep_s, *keep_w, *keep_e):
            x.last_price = px

        dropped = len(setups) - len(keep_s)
        if dropped:
            log.debug("%s: %d setup(s) dropped against the %s trend",
                      symbol, dropped, TREND_INTERVAL)
        return keep_s, keep_w, keep_e, cs


def _same_trade(e: Early, s) -> bool:
    """Whether an Early and a Setup are the identical trade, not merely the
    same idea. Both are computed by the same formulas from the same candles,
    so equal entry and stop means equal to the last bit; the tolerance is
    only there so a float representation change cannot silently unpair them."""
    scale = max(abs(s.entry), 1e-12)
    return (abs(e.entry - s.entry) / scale < 1e-9
            and abs(e.stop - s.stop) / scale < 1e-9)


def poi_ok(x) -> bool:
    """Should this signal be SENT under the POI policy?

    Gates sending only. The signal is still recorded and still armed, because
    muting a strategy must not also stop measuring it — /stats is the only
    forward, out-of-sample evidence this project has, and a suppressed band is
    exactly the one whose live numbers decide whether the policy was right.

    Policy G, research/studies/hybrid.py: requiring a daily POI on every
    timeframe took return per unit of drawdown from 6.94 to 21.53 on a 300
    USDT account. It suppresses roughly two thirds of alerts.
    """
    if not POI_REQUIRED:
        return True
    # Sweeps opt out separately. They are heads-ups rather than trades, no
    # measurement covers them, and gating them was a code decision rather than
    # a finding — so it gets its own switch instead of riding on one made for
    # something else.
    if isinstance(x, Sweep) and not POI_SWEEPS:
        return True
    # Unknown sends. A transient daily-bar failure must not read as "not in a
    # zone" — that would mute a symbol for as long as the failure lasted, and
    # silently, which is the worst possible failure mode for an alerting
    # service. The grade still shows the conservative letter.
    if not getattr(x, "poi_known", True):
        return True
    return bool(getattr(x, "poi", False))


def pair_early(results) -> dict:
    """
    Find early signals that describe the same trade as a confirmed setup.

    The early block fires on the gap bar; with fvg_scan_from="mss" the setup
    search looks at that same gap on that same bar, with the same entry formula
    and the same stop. Whenever the shift lands within early_max_bars of the
    raid, both produce a signal — same entry, same stop, same detected bar, so
    both pass the freshness gate in the same cycle and two messages go out for
    one trade. Measured: 457 of 2966 early signals, 15.4%.

    They are paired rather than one being dropped: the confirmed alert carries
    strictly more (the shift, the breaker in its confluence) and gains a line
    saying it also qualified early, so nothing is lost by sending it alone.

    Returns the set of early keys to suppress, and stamps `also_early` on the
    setup that will carry the message.
    """
    suppress = set()
    for setups, _, early, _ in results:
        # The timeframe is part of the key. A 30m bar open is also a 15m bar
        # open, so without it a 30m confirmed setup would suppress an
        # unrelated 15m early that merely shares a timestamp.
        keyed = {(s.symbol, s.tf, s.fvg_time, s.is_long): s for s in setups}
        for e in early:
            s = keyed.get((e.symbol, e.tf, e.fvg_time, e.is_long))
            if s is not None and _same_trade(e, s):
                s.also_early = e.bars_from_sweep or 0
                suppress.add((e.symbol, e.tf, e.fvg_time, e.is_long))
    return suppress


def trend_on(db) -> bool:
    """Live trend-filter state: the /trend override if set, else the config."""
    v = meta_get(db, "trend_filter", "")
    return v == "1" if v in ("0", "1") else TREND_FILTER


async def cycle(sess, db, symbols):
    sem = asyncio.Semaphore(CONCURRENCY)
    # Read once per cycle so every symbol in it sees the same setting.
    tf_on = trend_on(db)
    # One task per (symbol, timeframe). Both timeframes go through the same
    # semaphore, so CONCURRENCY still bounds requests in flight rather than
    # being quietly multiplied by the number of intervals.
    jobs = [(s, tf) for tf in INTERVALS for s in symbols]
    results = await asyncio.gather(
        *(scan_symbol(sess, sem, s, tf_on, tf) for s, tf in jobs))

    bootstrap = first_run(db) and not ALERT_ON_FIRST_RUN
    # /pause records everything as usual but sends nothing, so resuming does
    # not replay the backlog.
    paused = meta_get(db, "alerts_paused", "0") == "1"
    mute = bootstrap or paused
    # Freshness is counted in BARS, and a bar is a different length on each
    # timeframe, so it is read off the signal rather than off a single global.
    step_of = lambda x: BAR_SECONDS[getattr(x, "tf", "") or INTERVAL]
    now = int(time.time())
    sent = 0

    # Score already-open setups before arming new ones, against the candles
    # this cycle just fetched. Ordering matters only in that a setup armed
    # below cannot resolve on the bar that created it — its fill window starts
    # after the gap bar, and update() walks each bar once per row.
    for (symbol, tf), (_, _, _, cs) in zip(jobs, results):
        try:
            tracker.update(db, symbol, cs, tf)
        except Exception as e:
            log.warning("outcome tracking failed on %s %s: %s", symbol, tf, e)
    try:
        tracker.expire_stale(db)
    except Exception as e:
        log.warning("stale outcome sweep failed: %s", e)

    # Open interest and funding for this bar. Neither has a history endpoint,
    # so recording forward is the only way they ever become testable — see
    # market.py. Wrapped because a logger must never be able to cost an alert.
    if LOG_MARKET:
        try:
            n = await market.snapshot(sess, db, symbols)
            log.debug("market: logged %d snapshots", n)
            if now % 86400 < BAR_SECONDS[INTERVAL]:      # about once a day
                market.prune(db)
        except Exception as e:
            log.warning("market snapshot failed: %s", e)

    # Sweeps first: the grab precedes the shift, so the heads-up should land
    # before the setup message when both fall in the same cycle.
    swept = 0
    for _, sweeps, _, _ in results:
        for w in sweeps:
            if w.tf not in SWEEP_INTERVALS:
                continue
            if SWEEP_SRC is not None and w.src not in SWEEP_SRC:
                continue
            fresh = (now - w.sweep_time) <= SWEEP_FRESH_BARS * step_of(w)
            sid = sweep_sig(w)
            if sweep_already_sent(db, sid):
                continue
            record_sweep(db, sid, w)
            if fresh and not mute and poi_ok(w):
                if await tg.tg_send(sess, tg.sweep_message(w)):
                    swept += 1

    # The no-shift strategy. Fires on the gap bar with no confirmation, so it
    # lands before the confirmed setup on the same sweep — often bars before,
    # sometimes instead of, since most sweeps never produce a shift at all.
    quick = 0
    paired = pair_early(results)
    for _, _, early, _ in results:
        for e in early:
            fresh = (now - e.detected_time) <= FRESH_BARS * step_of(e)
            sid = early_sig(e)
            if early_already_sent(db, sid):
                continue
            record_early(db, sid, e)
            # Same trade as a confirmed setup in this cycle. Record it so it
            # can never be sent later, then stand aside: the confirmed alert
            # below carries it. Deliberately NOT armed either — two outcome
            # rows for one trade would double-count it in /stats and correlate
            # the sample, which is worse than the duplicate message.
            if (e.symbol, e.tf, e.fvg_time, e.is_long) in paired:
                continue
            if fresh:
                tracker.arm(db, sid, e, kind=tracker.EARLY)
            if fresh and not mute and EARLY_ALERTS and poi_ok(e):
                if await tg.tg_send(sess, tg.early_message(e)):
                    quick += 1

    for setups, _, _, _ in results:
        for s in setups:
            # Only setups from the last few bars are actionable. Older ones
            # are recorded so a restart cannot re-alert the whole history.
            #
            # Measured from detected_time, not the shift. Cfg.max_bars_after_mss
            # lets the gap arrive up to 10 bars after the shift, and a shift-
            # based window silently binned every setup slower than FRESH_BARS
            # — 3% of them — while still recording each one, so dedupe made the
            # loss permanent. The setup is not late; it did not exist yet.
            fresh = (now - s.detected_time) <= FRESH_BARS * step_of(s)
            sid = sig_id(s)
            if already_sent(db, sid):
                continue
            record(db, sid, s)
            # Track what was actionable, sent or not: a pause or a delivery
            # failure must not put a hole in the sample. The freshness gate
            # is also what keeps this forward-only — on a first run the 600
            # bars of recorded history are all stale, so none of them arm.
            if fresh:
                tracker.arm(db, sid, s, kind=tracker.CONFIRMED)
            if fresh and not mute and poi_ok(s):
                if await tg.tg_send(sess, tg.setup_message(s)):
                    sent += 1
    if bootstrap:
        log.info("first run: history recorded, nothing sent")
    elif paused:
        log.info("alerts paused; recorded but not sent")
    log.info("scanned %d symbols, sent %d confirmed, %d early, "
             "%d sweep heads-ups", len(symbols), sent, quick, swept)
    return sent + quick + swept


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
