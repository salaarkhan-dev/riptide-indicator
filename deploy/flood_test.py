#!/usr/bin/env python3
"""
One-shot flood test: run a single scan cycle immediately and exit.

The bot's own main loop sleeps until the next bar close before its first
cycle, so running riptide_bot.py directly makes this test wait up to 30
minutes before anything is sent. This calls cycle() once, now.

A test harness only. It imports the bot and calls its functions; it does not
modify them. Normal alerting behaviour is untouched — the two env overrides
are set for this process alone, and the shell wrapper resets the database.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time

# riptide_bot reads its configuration at import time, so these must be set
# first. setdefault means an explicit value from the shell still wins.
os.environ.setdefault("RIPTIDE_ALERT_FIRST_RUN", "1")
os.environ.setdefault("RIPTIDE_FRESH_BARS", "100000")

import aiohttp  # noqa: E402

import riptide_bot as rb  # noqa: E402

# Telegram allows approximately one message per second to a single chat.
# cycle() sends in a tight loop, which is fine for the one or two alerts a
# real cycle produces but trips the limit on a deliberate flood — and
# tg_send logs a 429 without retrying, so those messages are simply lost.
# Space them out here rather than in the bot, where the rate limit is not a
# real concern.
SEND_GAP = 1.2

_send = rb.tg_send
_last = 0.0


async def throttled_send(sess, text):
    global _last
    wait = SEND_GAP - (time.monotonic() - _last)
    if wait > 0:
        await asyncio.sleep(wait)
    _last = time.monotonic()
    await _send(sess, text)


rb.tg_send = throttled_send


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

    db = rb.db_init()
    async with aiohttp.ClientSession() as sess:
        print(f"flood test: {len(symbols)} symbol(s), {rb.INTERVAL} bars")
        print(f"sending every historic setup in the {rb.LOOKBACK}-bar window, "
              f"~{SEND_GAP:.1f}s apart to stay under Telegram's rate limit")
        print()

        t0 = time.monotonic()
        sent = await rb.cycle(sess, db, symbols)
        elapsed = time.monotonic() - t0

    print()
    if sent:
        print(f"done: {sent} messages sent in {elapsed:.0f}s — check Telegram")
    else:
        print("done: 0 messages sent.")
        print("  Either these symbols produced no setups in the lookback")
        print("  window, or riptide.db was not empty. The wrapper deletes it;")
        print("  if you ran this by hand, delete riptide.db and retry.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("\ninterrupted")
