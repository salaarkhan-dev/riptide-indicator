"""Startup and task supervision."""

from __future__ import annotations

import asyncio
import logging
import sys
import time

import aiohttp

from . import telegram as tg
from .config import (BAR_SECONDS, INTERVAL, SCAN_ON_START, TG_COMMANDS,
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
    if INTERVAL not in BAR_SECONDS:
        log.error("bad interval %s", INTERVAL)
        return
    db = db_init()

    async with aiohttp.ClientSession() as sess:
        symbols = await list_symbols(sess)
        if not symbols:
            log.error("no symbols; check MEXC_BASE or RIPTIDE_SYMBOLS")
            return
        log.info("riptide up: %d symbols, %s bars, build %s",
                 len(symbols), INTERVAL, build_id())
        await tg.tg_send(sess, f"Riptide scanner started\n"
                               f"{len(symbols)} symbols · {INTERVAL} bars")

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
        if SCAN_ON_START:
            n = await cycle(sess, db, symbols)
            state["last_cycle"], state["last_sent"] = time.time(), n

        tasks = [asyncio.create_task(scan_loop(sess, db, state), name="scan")]
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
