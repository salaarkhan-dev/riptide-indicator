#!/usr/bin/env python3
"""
One-shot flood test: run a single scan cycle immediately and exit.

The bot's own loop sleeps until the next bar close before its first cycle, so
running riptide_bot.py directly makes this test wait up to 30 minutes before
anything is sent. This calls cycle() once, now.

A test harness only. It imports the package and calls its functions; it does
not modify them. Normal alerting behaviour is untouched — the two env
overrides are set for this process alone, and the shell wrapper resets the
database.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time

# The package reads its configuration at import time, so these must be set
# first. setdefault means an explicit value from the shell still wins.
os.environ.setdefault("RIPTIDE_ALERT_FIRST_RUN", "1")
os.environ.setdefault("RIPTIDE_FRESH_BARS", "100000")
os.environ.setdefault("RIPTIDE_SWEEP_FRESH_BARS", "100000")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import aiohttp  # noqa: E402

from riptide import telegram as tg  # noqa: E402
from riptide import config, scanner, storage  # noqa: E402

# Telegram allows approximately one message per second to a single chat.
# cycle() sends in a tight loop, which is fine for the one or two alerts a
# real cycle produces but trips the limit on a deliberate flood — and tg_send
# only retries failures it knows did not deliver, so a 429 storm still costs
# messages. Space them out here rather than in the bot, where the rate limit
# is not a real concern.
SEND_GAP = 1.2

_send = tg.tg_send
_last = 0.0


async def throttled_send(sess, text):
    """Wraps the real sender. scanner calls tg.tg_send, so this is seen."""
    global _last
    wait = SEND_GAP - (time.monotonic() - _last)
    if wait > 0:
        await asyncio.sleep(wait)
    _last = time.monotonic()
    return await _send(sess, text)


tg.tg_send = throttled_send


async def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=sys.stdout)

    symbols = [s.strip() for s in os.getenv("RIPTIDE_SYMBOLS", "BTC_USDT").split(",")
               if s.strip()]
    if not symbols:
        print("no symbols configured")
        return 1

    db = storage.db_init()
    async with aiohttp.ClientSession() as sess:
        print(f"flood test: {len(symbols)} symbol(s), {config.INTERVAL} bars")
        print(f"sending every historic setup and sweep in the "
              f"{config.LOOKBACK}-bar window, ~{SEND_GAP:.1f}s apart to stay "
              f"under Telegram's rate limit")
        print()

        t0 = time.monotonic()
        sent = await scanner.cycle(sess, db, symbols)
        elapsed = time.monotonic() - t0

    print()
    if sent:
        print(f"done: {sent} messages sent in {elapsed:.0f}s — check Telegram")
    else:
        print("done: 0 messages sent.")
        print("  Either these symbols produced nothing in the lookback window,")
        print("  or riptide.db was not empty. The wrapper deletes it; if you")
        print("  ran this by hand, delete riptide.db and retry.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("\ninterrupted")
