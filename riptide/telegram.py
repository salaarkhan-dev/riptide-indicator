"""Telegram delivery and message formatting.

tg_send is the only place that talks to the Telegram API. Its retry policy is
deliberately narrow — see the docstring; sendMessage is not idempotent, so a
careless retry duplicates an alert.
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import aiohttp

from .config import (BAR_SECONDS, CFG, DISPLAY_TZ, ENTRY_INTERVAL, INTERVAL,
                     TG_CHAT, TG_RETRIES, TG_TOKEN, log)
from .engine import Setup, Sweep

async def tg_send(sess, text: str) -> bool:
    """
    Send one alert. Returns True only if Telegram acknowledged it.

    sendMessage is not idempotent — there is no request id to deduplicate on —
    so a blind retry can deliver the same alert twice. Retries are therefore
    limited to failures where the message provably did not arrive:

      429  Telegram states it did not deliver and says how long to wait.
      5xx  the request was not processed; Telegram's own docs say to retry.
      connect errors  the request never reached Telegram at all.

    Everything else stops. A read timeout or a reset mid-request is ambiguous:
    Telegram may have sent the message and lost the reply, so retrying risks a
    duplicate. Those are logged as possibly-delivered and dropped, which is the
    quieter failure of the two.
    """
    if not TG_TOKEN or not TG_CHAT:
        log.info("[no telegram configured]\n%s", text)
        return False

    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {"chat_id": TG_CHAT, "text": text, "parse_mode": "HTML",
               "disable_web_page_preview": True}

    for attempt in range(1, TG_RETRIES + 1):
        try:
            async with sess.post(
                    url, json=payload,
                    timeout=aiohttp.ClientTimeout(total=20, sock_connect=10)) as r:
                if r.status == 200:
                    if attempt > 1:
                        log.info("telegram delivered on attempt %d", attempt)
                    return True

                body = await r.text()

                if r.status == 429:
                    wait = 1.0
                    try:
                        wait = float(json.loads(body)
                                     .get("parameters", {}).get("retry_after", 1))
                    except (ValueError, AttributeError, TypeError):
                        pass
                    wait = min(max(wait, 1.0), 60.0)
                    log.warning("telegram rate limited, waiting %.0fs "
                                "(attempt %d/%d)", wait, attempt, TG_RETRIES)
                    await asyncio.sleep(wait)
                    continue

                if 500 <= r.status < 600:
                    back = min(2 ** attempt, 30)
                    log.warning("telegram %s, retrying in %ds (attempt %d/%d)",
                                r.status, back, attempt, TG_RETRIES)
                    await asyncio.sleep(back)
                    continue

                # 400 bad request, 403 blocked by the user, and friends. These
                # do not improve on a retry.
                log.error("telegram %s, not retried: %s", r.status, body[:300])
                return False

        except aiohttp.ClientConnectorError as e:
            back = min(2 ** attempt, 30)
            log.warning("telegram unreachable, retrying in %ds (attempt %d/%d): %s",
                        back, attempt, TG_RETRIES, e)
            await asyncio.sleep(back)
            continue

        except (asyncio.TimeoutError, aiohttp.ClientError) as e:
            log.error("telegram send outcome unknown (%s) — not retried, since "
                      "Telegram may already have delivered it. This alert may "
                      "or may not have arrived.", e)
            return False

    log.error("telegram gave up after %d attempts; alert NOT delivered", TG_RETRIES)
    return False


def fmt(v: float) -> str:
    if v >= 1000:
        return f"{v:,.1f}"
    if v >= 1:
        return f"{v:.4g}"
    return f"{v:.8g}"


def local_clock() -> str:
    """Current time in RIPTIDE_TZ, e.g. '08:30 PKT'. Empty if unset or bad."""
    if not DISPLAY_TZ:
        return ""
    try:
        now = datetime.now(ZoneInfo(DISPLAY_TZ))
    except Exception:
        log.warning("RIPTIDE_TZ=%r is not a valid IANA zone, ignoring", DISPLAY_TZ)
        return ""
    return now.strftime("%H:%M %Z")


def signal_age(closed_at: int) -> str:
    """
    'HH:MM PKT · 2m ago' for the moment a signal became actionable.

    Answers one question — is this fresh, or did it sit somewhere. The
    freshness gates should already prevent a stale send, so a large age here
    means something is wrong upstream rather than merely late.
    """
    delta = max(0, int(time.time()) - closed_at)
    if delta < 60:
        ago = f"{delta}s ago"
    elif delta < 3600:
        ago = f"{delta // 60}m ago"
    else:
        ago = f"{delta // 3600}h {(delta % 3600) // 60}m ago"

    tz = timezone.utc
    if DISPLAY_TZ:
        try:
            tz = ZoneInfo(DISPLAY_TZ)
        except Exception:
            pass                      # local_clock already logs a bad zone
    return f"{datetime.fromtimestamp(closed_at, tz).strftime('%H:%M %Z')} · {ago}"


def bar_label(t: int) -> str:
    """UTC bar-open time, matching how TradingView labels the bar."""
    return datetime.fromtimestamp(t, timezone.utc).strftime("%H:%M")


def setup_message(s: Setup) -> str:
    side = "LONG" if s.is_long else "SHORT"
    sign = 1 if s.is_long else -1
    t1 = s.entry + sign * s.risk
    t15 = s.entry + sign * s.risk * CFG.be_arm_r
    # A stop moved exactly to entry still loses the round-trip fee,
    # so break-even locks a little in. Mirrors beLockR in the Pine.
    be_stop = s.entry + sign * s.risk * CFG.be_lock_r
    t3 = s.entry + sign * s.risk * 3
    riskpct = s.risk / s.entry * 100 if s.entry else 0
    tv = f"https://www.tradingview.com/chart/?symbol=MEXC%3A{s.symbol.replace('_', '')}.P"
    tf = f"{INTERVAL} → {ENTRY_INTERVAL}" if s.entry_tf == "LTF" else INTERVAL
    # The gap sits on whichever timeframe produced the entry.
    gap_step = BAR_SECONDS[ENTRY_INTERVAL] if s.entry_tf == "LTF" \
        else BAR_SECONDS[INTERVAL]
    return (
        f"<b>{side}  {s.symbol}</b>  ({tf})\n"
        f"{s.src} liquidity @ {fmt(s.level)}"
        f"{f' · {s.pivots} swings' if s.src == 'Pivot' else ''}\n\n"
        f"Entry  <code>{fmt(s.entry)}</code>\n"
        f"Stop   <code>{fmt(s.stop)}</code>   ({riskpct:.2f}% risk)\n"
        f"1R     {fmt(t1)}\n"
        f"BE at  {fmt(t15)}  \u2192 stop {fmt(be_stop)}\n"
        f"3R     {fmt(t3)}\n\n"
        f"<i>{signal_age(s.fvg_time + gap_step)}</i>\n"
        f"<a href='{tv}'>chart</a>"
    )


def sweep_message(s: Sweep) -> str:
    """Heads-up on the grab. Deliberately carries no entry or stop: there is
    no setup yet, and the shift may never come."""
    bias = "SHORT" if s.is_high else "LONG"
    took = "high" if s.is_high else "low"
    direction = "below" if s.is_high else "above"
    tv = f"https://www.tradingview.com/chart/?symbol=MEXC%3A{s.symbol.replace('_', '')}.P"
    return (
        f"⚠️ <b>SWEEP  {s.symbol}</b>  ({INTERVAL})\n"
        f"{s.src} {took} @ {fmt(s.level)} taken"
        f"{f' · {s.pivots} swings' if s.src == 'Pivot' else ''}\n\n"
        f"Watching for  <b>{bias}</b>\n"
        f"Shift confirms {direction} <code>{fmt(s.struct_level)}</code>\n"
        f"Sweep {took}   {fmt(s.sweep_extreme)}\n\n"
        f"No entry yet — the FVG forms after the shift.\n"
        f"<i>{signal_age(s.sweep_time + BAR_SECONDS[INTERVAL])}</i>\n"
        f"<a href='{tv}'>chart</a>"
    )
