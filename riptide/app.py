"""Startup and task supervision."""

from __future__ import annotations

import asyncio
import logging
import sys
import time

import aiohttp

from . import telegram as tg
from . import watch
from .config import (BAR_SECONDS, CFG_OVERRIDES, ENTRY_INTERVAL, INTERVAL,
                     INTERVALS, POI_REQUIRED, SCAN_ON_START, TG_COMMANDS,
                     build_id, log)
from .commands import command_loop
from .exchange import list_symbols
from .scanner import cycle, scan_loop
from .storage import db_init


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=sys.stdout)
    bad = [i for i in INTERVALS if i not in BAR_SECONDS]
    if bad:
        log.error("bad interval(s) %s; valid: %s",
                  ", ".join(bad), ", ".join(BAR_SECONDS))
        return
    if len(INTERVALS) > 1 and not POI_REQUIRED:
        # Measured: Min15 alone is -0.095 R per confirmed setup and -0.039 per
        # early. It only turns positive inside a daily POI. Scanning a second
        # timeframe without the filter that makes it work is strictly worse
        # than not scanning it, so this is loud rather than silent.
        log.warning("scanning %s with POI_REQUIRED off — the faster "
                    "timeframes measured NEGATIVE without the POI filter; "
                    "see MEASUREMENTS.md", ", ".join(INTERVALS))
    if ENTRY_INTERVAL and ENTRY_INTERVAL not in BAR_SECONDS:
        log.error("bad entry interval %s", ENTRY_INTERVAL)
        return
    if ENTRY_INTERVAL and BAR_SECONDS[ENTRY_INTERVAL] >= BAR_SECONDS[INTERVAL]:
        log.error("entry interval %s is not faster than %s; the point is to "
                  "place entries on a lower timeframe", ENTRY_INTERVAL, INTERVAL)
        return
    db = db_init()

    async with aiohttp.ClientSession() as sess:
        symbols = await list_symbols(sess)
        if not symbols:
            log.error("no symbols; check MEXC_BASE or RIPTIDE_SYMBOLS")
            return
        if CFG_OVERRIDES:
            log.warning("engine defaults overridden: %s",
                        ", ".join(f"{k} {a}->{b}"
                                  for k, (a, b) in sorted(CFG_OVERRIDES.items())))
        log.info("riptide up: %d symbols, %s bars%s, build %s",
                 len(symbols), "+".join(INTERVALS),
                 f" + {ENTRY_INTERVAL} entries" if ENTRY_INTERVAL else "",
                 build_id())
        await tg.tg_send(sess, f"Riptide scanner started\n"
                               f"{len(symbols)} symbols · "
                               f"{'+'.join(INTERVALS)} bars"
                               + (" · POI filter on" if POI_REQUIRED else ""))

        # Shared with the command listener so /status reports live values.
        state = {"symbols": symbols, "started": time.time(),
                 "last_cycle": 0.0, "last_sent": 0}

        # Scan once before entering the loop. The loop sleeps first, so without
        # this a restart is blind until the next close — up to a full bar. That
        # is not just a delay: a sweep on the bar that closed just before the
        # restart is 2*step + pad old by the first scheduled cycle, past the
        # 2-bar window, so it would never be sent at all.
        #
        # Safe to repeat work: dedupe skips anything the previous process
        # already recorded, the freshness gate still applies, and an empty
        # database still bootstraps silently.
        #
        # Wrapped, and this is not defensive padding. main() runs this BEFORE
        # the command listener starts, so an exception here kills the process
        # before Telegram can answer anything — systemd restarts it, the
        # startup scan throws again, and the result is a crash loop whose only
        # symptom is that /status has gone quiet. The one moment you most need
        # to ask the bot what is wrong is the one moment it cannot reply.
        #
        # A failed startup scan costs one cycle. The scheduled loop retries in
        # minutes, and the freshness gate means nothing is lost that would not
        # have been lost anyway.
        if SCAN_ON_START:
            try:
                n = await cycle(sess, db, symbols)
                state["last_cycle"], state["last_sent"] = time.time(), n
            except Exception as e:
                log.exception("startup scan failed (%s) — continuing so the "
                              "command listener comes up; the scheduled loop "
                              "will retry", e)

        tasks = [asyncio.create_task(scan_loop(sess, db, state), name="scan")]
        # The trendline watch, on its own timer. Always started, because it
        # reads its on/off switch every wake — so /trendline on works without a
        # restart, and an idle loop costs one sleep per bar close.
        tasks.append(asyncio.create_task(
            watch.watch_loop(sess, db, state), name="trendline"))
        if watch.enabled(db):
            log.info("trendline watch on, %s bars", watch.interval(db))
        if TG_COMMANDS:
            tasks.append(asyncio.create_task(
                command_loop(sess, db, state), name="commands"))
            log.info("telegram commands enabled")

        # If either loop dies the process should exit and let systemd restart
        # it, rather than limp along with half its behaviour missing.
        done, pending = await asyncio.wait(
            tasks, return_when=asyncio.FIRST_COMPLETED)
        for t in pending:
            t.cancel()
        for t in done:
            t.result()          # re-raise whatever stopped it
