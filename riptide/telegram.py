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
                     TG_CHAT, TG_RETRIES, TG_TOKEN, TREND_INTERVAL, log)
from .engine import Early, Setup, Sweep

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


TF_LABEL = {"Min1": "1m", "Min5": "5m", "Min15": "15m", "Min30": "30m",
            "Min60": "1h", "Hour4": "4h", "Hour8": "8h", "Day1": "1D"}


def tf_label(interval: str) -> str:
    return TF_LABEL.get(interval, interval)


def trend_note(trend_dir: int, is_long: bool) -> str:
    """
    Which side of the higher-timeframe trend the signal sits on.

    Shown on every alert whether or not the filter is suppressing anything —
    the point is to judge a counter-trend setup, not to be spared it.
    Measured: with the trend +0.103 R per setup, against it -0.008.
    Empty when the trend is unknown, which is honest about not knowing.
    """
    if not trend_dir:
        return ""
    name = {"Day1": "daily", "Hour4": "4h", "Hour8": "8h",
            "Min60": "hourly"}.get(TREND_INTERVAL, tf_label(TREND_INTERVAL))
    aligned = (trend_dir > 0) == is_long
    return (f"✅ with the {name} trend" if aligned
            else f"⚠️ AGAINST the {name} trend")


def bar_label(t: int) -> str:
    """UTC bar-open time, matching how TradingView labels the bar."""
    return datetime.fromtimestamp(t, timezone.utc).strftime("%H:%M")


def _headline(tag: str, is_long: bool, symbol: str, tf: str,
              suffix: str = "") -> str:
    """
    First line of every alert, and the only line Telegram shows in the
    notification preview — so it carries all three things needed to triage
    without opening the chat: which strategy, which way, which symbol.

    suffix qualifies the direction ("bias" on a sweep, where nothing is
    tradeable yet) and belongs beside it, not after the timeframe.
    """
    side = "LONG" if is_long else "SHORT"
    return (f"{tag}  {'🟢' if is_long else '🔴'} <b>{side}</b>"
            f"{f' <i>{suffix}</i>' if suffix else ''}  <b>{symbol}</b>  {tf}")


def _footer(when: int, price: float, tv_symbol: str) -> str:
    """Time, age and the price as of the scan, so a stale alert is obvious."""
    tv = f"https://www.tradingview.com/chart/?symbol=MEXC%3A{tv_symbol.replace('_', '')}.P"
    px = f" · {fmt(price)}" if price else ""
    return f"<i>{signal_age(when)}{px}</i>\n<a href='{tv}'>chart</a>"


def _pool(src: str, level: float, pivots: int) -> str:
    return (f"{src} pool @ {fmt(level)}"
            f"{f' · {pivots} swings' if src == 'Pivot' else ''}")


def _levels(entry: float, stop: float, risk: float, is_long: bool) -> str:
    """
    The trade, as an aligned monospace block. Kept to five short lines: the
    numbers are what gets acted on and everything else is context around them.
    """
    sign = 1 if is_long else -1
    riskpct = risk / entry * 100 if entry else 0
    return ("<pre>"
            f"entry {fmt(entry)}\n"
            f"stop  {fmt(stop)}  {riskpct:.2f}%\n"
            f"1R    {fmt(entry + sign * risk)}\n"
            f"BE    {fmt(entry + sign * risk * CFG.be_arm_r)} → "
            f"{fmt(entry + sign * risk * CFG.be_lock_r)}\n"
            f"3R    {fmt(entry + sign * risk * 3)}"
            "</pre>")


def setup_message(s: Setup) -> str:
    tf = (f"{tf_label(INTERVAL)}→{tf_label(ENTRY_INTERVAL)}"
          if s.entry_tf == "LTF" else tf_label(INTERVAL))
    # The gap sits on whichever timeframe produced the entry.
    gap_step = BAR_SECONDS[ENTRY_INTERVAL] if s.entry_tf == "LTF" \
        else BAR_SECONDS[INTERVAL]
    note = trend_note(s.trend_dir, s.is_long)
    return "\n".join(x for x in (
        _headline("🎯 <b>CONFIRMED</b>", s.is_long, s.symbol, tf),
        "<i>sweep → shift → FVG</i>",
        "",
        _levels(s.entry, s.stop, s.risk, s.is_long),
        note or None,
        _pool(s.src, s.level, s.pivots),
        _footer(s.detected_time + gap_step, s.last_price, s.symbol),
    ) if x is not None)


def early_message(s: Early) -> str:
    """
    The no-shift entry. Labelled distinctly from the confirmed setup because
    it is a different bet, not an earlier version of the same one: nothing has
    confirmed the reversal, so the sweep may simply be a trend continuing.
    What it buys is the stop sitting a few candles away at the raid extreme
    rather than a whole leg back.
    """
    bars = s.bars_from_sweep
    note = trend_note(s.trend_dir, s.is_long)
    return "\n".join(x for x in (
        _headline("⚡ <b>EARLY</b>", s.is_long, s.symbol, tf_label(INTERVAL)),
        f"<i>sweep → FVG · no shift · gap {bars} "
        f"bar{'' if bars == 1 else 's'} after the raid</i>",
        "",
        _levels(s.entry, s.stop, s.risk, s.is_long),
        note or None,
        _pool(s.src, s.level, s.pivots),
        _footer(s.fvg_time + BAR_SECONDS[INTERVAL], s.last_price, s.symbol),
    ) if x is not None)


def sweep_message(s: Sweep) -> str:
    """Heads-up on the grab. Deliberately carries no entry or stop: there is
    no setup yet, and the shift may never come."""
    is_long = not s.is_high
    took = "high" if s.is_high else "low"
    direction = "below" if s.is_high else "above"
    note = trend_note(s.trend_dir, is_long)
    return "\n".join(x for x in (
        _headline("👀 <b>SWEEP</b>", is_long, s.symbol, tf_label(INTERVAL),
                  suffix="bias"),
        "<i>liquidity taken · no entry yet</i>",
        "",
        f"Sweep {took}   <code>{fmt(s.sweep_extreme)}</code>",
        f"Shift confirms {direction} <code>{fmt(s.struct_level)}</code>",
        note or None,
        _pool(s.src, s.level, s.pivots),
        _footer(s.sweep_time + BAR_SECONDS[INTERVAL], s.last_price, s.symbol),
    ) if x is not None)
