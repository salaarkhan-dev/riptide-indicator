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
                     TG_CHAT, TG_RETRIES, TG_TOKEN, TRACK_TARGET_R,
                     TREND_INTERVAL, TRENDLINE_CONFLUENCE_BARS, log)
from .engine import (Early, Setup, Sweep, grade_of, shift_odds,
                     sweep_worth)

def keyboard(*rows) -> dict:
    """An inline keyboard from rows of (label, callback_data) or (label, url).

    Telegram caps callback_data at 64 BYTES, which is why every button here
    carries a database row id rather than the trade it refers to.
    """
    out = []
    for row in rows:
        line = []
        for label, data in row:
            key = "url" if str(data).startswith("http") else "callback_data"
            line.append({"text": label, key: str(data)})
        if line:
            out.append(line)
    return {"inline_keyboard": out}


async def _api(sess, method: str, payload: dict) -> dict | None:
    """One non-critical Telegram call. Never retried and never raised: these
    are button housekeeping, and a failed edit must not disturb a scan."""
    if not TG_TOKEN:
        return None
    try:
        async with sess.post(
                f"https://api.telegram.org/bot{TG_TOKEN}/{method}",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=15, sock_connect=8)) as r:
            body = await r.json()
            if not body.get("ok"):
                log.warning("telegram %s: %s", method, str(body)[:200])
            return body
    except Exception as e:
        log.warning("telegram %s failed: %s", method, e)
        return None


async def answer_callback(sess, cb_id: str, text: str = "",
                          alert: bool = False) -> None:
    """Clear the spinner on a tapped button. Telegram shows the loading state
    for a few seconds if this never arrives, so it is sent even when empty."""
    await _api(sess, "answerCallbackQuery",
               {"callback_query_id": cb_id, "text": text[:200],
                "show_alert": alert})


async def edit_markup(sess, chat_id, message_id, markup: dict | None) -> None:
    await _api(sess, "editMessageReplyMarkup",
               {"chat_id": chat_id, "message_id": message_id,
                "reply_markup": markup or {"inline_keyboard": []}})


async def tg_send(sess, text: str, buttons: dict | None = None) -> bool:
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
    if buttons:
        payload["reply_markup"] = buttons

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
    """A price, printed at enough precision to place the order with.

    THIS WAS 4 SIGNIFICANT FIGURES AND THAT WAS TOO FEW. A LINK alert showed
    "Entry 12.71 · Stop 12.57 · 1.15% risk", but 12.71 − 12.57 is 1.10% — the
    percentage was computed from the real values and the prices were rounded
    to two decimals under them. Reading the entry off the message put the
    limit order about 0.005 from where the engine meant it, which is 3% of the
    risk on that trade, and the same rounding on a 127-dollar symbol costs
    0.049 — nearly 4%.

    Six significant figures covers every tick size in the 1–1000 range where
    the loss occurred, and changes nothing below 1, which was always printed
    at eight. Above 1000 a tenth of a unit is already far finer than any
    plausible stop, so that branch stays as it was.
    """
    if v >= 1000:
        return f"{v:,.1f}"
    if v >= 1:
        return f"{v:.6g}"
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


# THE BTC LINE IS GONE, AND THE FINDING BEHIND IT IS RETIRED.
#
# Every alert used to carry "BTC trending with/against you". It was there
# because context.py measured BTC's 30m trend AGAINST the trade at +0.174,
# 3.6 SE, monotone, surviving all four splits — flagged CANDIDATE and never
# acted on.
#
# Re-measured in research/studies/three_ideas.py on the full 60-symbol corpus:
# +0.202 at +5.1 SE on the pooled data, and -0.036 at -0.6 SE on the held-out
# half. The sign REVERSES. The pooled number was carried entirely by the
# discovery half, which is the same failure the trendline slope study showed at
# a smaller magnitude.
#
# A line reading "BTC trending against you" is a warning, and a warning whose
# basis has been withdrawn is worse than no line: it costs a second of reading
# on every alert and pushes the eye toward a factor now measured at nothing.
# Removed rather than reworded, because a neutral "BTC 30m: down" would still
# be occupying a line in a message that has to be read in two seconds.
#
# `btc_dir` is still computed, still stored on every outcome row, and still
# available to /stats. Retiring a display is not the same as stopping the
# measurement — the day there is a fresh window to test it on, the data is
# there.


def bar_label(t: int) -> str:
    """UTC bar-open time, matching how TradingView labels the bar."""
    return datetime.fromtimestamp(t, timezone.utc).strftime("%H:%M")


def _headline(tag: str, is_long: bool, symbol: str, tf: str,
              suffix: str = "", grade: str = "") -> str:
    """
    First line of every alert, and the only line Telegram shows in the
    notification preview — so it carries everything needed to triage without
    opening the chat: which strategy, how good, which way, which symbol.

    The GRADE goes here, in the preview, because it is the one thing that
    decides whether to open the message at all. It used to sit seven lines
    down, below the entry and stop — which meant reading the numbers of a
    trade before finding out it was a D.

    suffix qualifies the direction ("bias" on a sweep, where nothing is
    tradeable yet) and belongs beside it, not after the timeframe.
    """
    side = "LONG" if is_long else "SHORT"
    # The grade is a bare bold letter, not a coloured dot. The direction
    # already owns the green/red dot on this line and a second coloured circle
    # beside it reads as noise rather than as a second signal.
    return (f"{tag}{f' <b>{grade}</b>' if grade else ''}"
            f"  {'🟢' if is_long else '🔴'} <b>{side}</b>"
            f"{f' <i>{suffix}</i>' if suffix else ''}  <b>{symbol}</b>  {tf}")


# MEXC's interval names to TradingView's, for the chart link.
TV_INTERVAL = {"Min1": "1", "Min5": "5", "Min15": "15", "Min30": "30",
               "Min60": "60", "Hour4": "240", "Hour8": "480", "Day1": "D"}


def tv_link(tv_symbol: str, interval: str = "") -> str:
    """A TradingView URL for this symbol ON THIS TIMEFRAME.

    The interval is not decoration. Without it TradingView opens on whatever
    the chart was last left on, and an alert compared against the wrong
    timeframe looks like a bug in the bot: the same ENA raid was a 30m SHORT
    and a 15m LONG on the same afternoon, both correct, and the chart opened
    on 15m.

    Shared with the trendline watch digest, which is a list of links and
    nothing else — the whole message is "go look at these charts", so the
    charts had better open where the break was.
    """
    tf = TV_INTERVAL.get(interval or INTERVAL)
    return (f"https://www.tradingview.com/chart/?symbol=MEXC%3A"
            f"{tv_symbol.replace('_', '')}.P" + (f"&interval={tf}" if tf else ""))


def _footer(when: int, price: float, tv_symbol: str,
            interval: str = "") -> str:
    """Time, age and the price as of the scan, so a stale alert is obvious."""
    px = f" · {fmt(price)}" if price else ""
    return (f"<i>{signal_age(when)}{px}</i>\n"
            f"<a href='{tv_link(tv_symbol, interval)}'>chart</a>")


def _grade(x, early: bool = False) -> str:
    """The one-line reason for the letter in the headline.

    THE BAND'S HISTORICAL RATE USED TO BE PRINTED HERE AND IS NOT ANY MORE.
    "76% of fills reached 2R, 67% filled, 43 backtest" was the least
    actionable line in the message and the most likely to be misread: a base
    rate from a single 42-day window, on 43 signals for band A, reads as a
    probability for the trade in front of you. It is not one. The letter
    already carries everything that replicated — the ORDERING of the bands —
    and the levels are the least stable thing measured here.

    The numbers still exist and still matter; they live in /stats, where they
    are forward, out of sample, and can be looked at deliberately rather than
    glanced at while deciding.
    """
    return f"<i>{grade_of(early, x.poi, x.trend_dir, x.is_long, x.di_dir)[1]}</i>"


def _pool(src: str, level: float, pivots: int, pools: int = 0) -> str:
    """`pools` > 1 means several separate pools were raided into the same gap
    — worth saying, since it is why one alert stands for what the engine saw
    as several clusters."""
    extra = f" · {pivots} swings" if src == "Pivot" else ""
    if pools > 1:
        extra += f" · {pools} pools taken"
    return f"{src} pool @ {fmt(level)}{extra}"


# THREE ZONES, THREE DIFFERENT STRENGTHS OF EVIDENCE, SO THREE DIFFERENT WORDS.
#
# For months only "skip" printed and everything at or under 2.6% said nothing.
# That was right at the time: risk_band.py had tested the two edges separately
# against a circular-shift null and only the upper one cleared, so asserting a
# "take" would have asserted something that failed. The cost was that the most
# common alert carried no verdict at all and read as though the band had not
# been measured.
#
# Re-measured 10-11 Sep on the 333-day window with the SYMBOL BOOTSTRAP from
# research/studies/survivor.py, which is the stricter instrument: it resamples
# the sixty perpetuals with replacement, so a number carried by a handful of
# coins falls apart and one spread across the universe does not. 595 confirmed
# Min30 setups:
#
#   over 2.6%   -0.192 R/bet, 30% win, bootstrap [-0.338, -0.032] ENTIRELY
#               BELOW ZERO, negative in 4 quarters of 4, and the sign holds in
#               both halves of the window (-0.273 then -0.536 against the
#               band). This was always the strong one and it got stronger.
#
#   1.2-2.6%    +0.214 R/bet, 42% win, bootstrap [+0.082, +0.329] ENTIRELY
#               ABOVE ZERO, positive in 4 quarters of 4 (+0.209 +0.260 +0.132
#               +0.207) and in both halves. That is a claim about the BAND
#               standing on its own, which is what "take" now says. It is not
#               a claim that a narrow stop is bad.
#
#   under 1.2%  -0.051 R/bet, bootstrap [-0.193, +0.075] STRADDLING ZERO, and
#               Q3 flips positive (+0.13) after three negative quarters. Still
#               not supported, exactly as risk_band.py found. It gets "flat",
#               which says measured and indistinguishable from zero — NOT
#               "unmeasured" and NOT "bad".
#
# TWO THINGS THIS LABEL DOES NOT SAY. It is not a filter: nothing is suppressed
# by it and a "skip" alert is still sent, because the decision is the reader's.
# And the 1.2 and the 2.6 were chosen by looking at data — risk_band.py
# pre-registered the test, not the boundaries — so some of the separation is
# selection and no amount of re-slicing the same 333 days removes it.
RISK_TIGHT = 1.2
RISK_WIDE = 2.6

# THE BAND WAS MEASURED ON Min30 AND THE BOT ALSO ALERTS ON Min15, so Min15 was
# measured too rather than assumed. 791 confirmed Min15 setups over the same 333
# days. It replicates, but NOT EVENLY, and the uneven part is worth stating:
#
#   1.2-2.6%    +0.129 R/bet, 41% win, resampling [+0.028, +0.238], entirely
#               above zero, positive in 3 quarters of 4 and flat in the fourth.
#               An independent timeframe agreeing is the strongest thing said
#               about this band anywhere in the project.
#
#   under 1.2%  -0.021 R/bet, resampling [-0.111, +0.051], straddling zero,
#               quarters alternating. Same answer as Min30: "flat".
#
#   over 2.6%   -0.154 R/bet, resampling [-0.462, +0.058] — STRADDLES ZERO.
#
# THE WIDE ARM ON Min15 IS UNDERPOWERED, NOT CONTRADICTORY, and the difference
# matters. 63 bets at a standard error of 0.162: if Min30's -0.192 were exactly
# true here it would score |z| 1.2 and still fail to clear. The point estimate
# agrees in sign and is within a quarter of an R of Min30's. So "skip" on Min15
# is CARRIED OVER from Min30 on the strength of the mechanism and the matching
# sign — it is not independently evidenced on this timeframe, and that judgment
# is recorded here rather than buried. A gap of 15m alerts with a 3% stop and no
# warning at all looked like the worse failure, since the label suppresses
# nothing and the reader decides.
#
# Everything else stays silent until it has its own measurement.
RISK_MEASURED_ON = {"Min30", "Min15"}


def risk_verdict(riskpct: float, interval: str | None = None) -> str:
    """"skip" over 2.6%, "take" in 1.2-2.6%, "flat" under 1.2%.

    Blank on any timeframe the band has not been measured on, and blank when
    the caller passes no timeframe at all, so a new call site cannot acquire a
    verdict by accident.

    CONFIRMED SETUPS ONLY, enforced by the caller. The same split on early
    signals is non-monotone with no block, so there is no verdict to give.
    """
    if interval not in RISK_MEASURED_ON:
        return ""
    if riskpct > RISK_WIDE:
        return "skip"
    return "take" if riskpct >= RISK_TIGHT else "flat"


def _levels(entry: float, stop: float, risk: float, is_long: bool,
            confirmed: bool = False, interval: str | None = None) -> str:
    """
    The trade. Four plain lines, no code block.

    A <pre> block buys column alignment and costs a heavy grey panel with a
    copy button, which on a phone dominates the message. Without it the
    columns cannot align anyway — Telegram's body font is proportional — so
    the layout leans on line breaks and weight instead: entry and stop get a
    line each because they are what you act on, the targets share one, and
    break-even reads as an instruction rather than a column.
    """
    sign = 1 if is_long else -1
    riskpct = risk / entry * 100 if entry else 0
    verdict = risk_verdict(riskpct, interval) if confirmed else ""
    out = (f"Entry  <b>{fmt(entry)}</b>\n"
           f"Stop   <b>{fmt(stop)}</b>  <i>{riskpct:.2f}% risk"
           f"{' · ' + verdict if verdict else ''}</i>\n"
           f"2R {fmt(entry + sign * risk * 2)}  ·  "
           f"3R {fmt(entry + sign * risk * 3)}")
    # The break-even line is gone unless it is switched back on. It advised a
    # stop move for months without ever having been measured, and it loses
    # money at every arm level on both signal types — see be_arm_r in
    # config.py. Advice on an alert should have cleared a bar.
    if CFG.be_arm_r > 0:
        out += (f"\n<i>BE at {fmt(entry + sign * risk * CFG.be_arm_r)} → stop "
                f"{fmt(entry + sign * risk * CFG.be_lock_r)}</i>")
    return out


def grade_chip(x, early: bool = False) -> str:
    """The grade as it appears in the headline."""
    return grade_letter(x, early)


def grade_letter(x, early: bool = False) -> str:
    """Just the letter, for looking up a band's live rate before rendering."""
    return grade_of(early, x.poi, x.trend_dir, x.is_long, x.di_dir)[0]


def _short(symbol: str) -> str:
    """APT_USDT -> APT. The quote is the same on all sixty and costs five
    characters on a line that has to fit a phone."""
    return symbol.split("_")[0] if symbol else "?"


def marks(x) -> str | None:
    """The one meta line under the grade: compact chips, no prose.

    THIS REPLACED THREE SENTENCES AND THAT WAS THE POINT. Each mark had its own
    line explaining what it meant and how well it was evidenced — honest, and
    unreadable at thirty alerts a day. An alert is glanced at on a phone while
    something is moving; the reader needs the direction, the levels and the
    handful of facts that change the size, and prose crowds all three off the
    screen.

    So the CLAIM stays on the alert as a glyph and the EVIDENCE moves to
    /legend, where it can be as long as it needs to be and is read once. That
    keeps this project's rule that no mark is a bare assertion — the assertion
    is still backed, just not re-typed into every message.

    🔗 SAYS "SIZE ONCE" AT EVERY COUNT. Eight was where the return measurably
    stepped up; the correlation of outcomes does not wait for eight. The
    deployed stream's worst losing run is forty trades inside twelve hours —
    one market move taking out everything open, which happens at two symbols
    as readily as at eight.
    """
    bits = []
    if tl_agrees(x):
        b = x.tl_break
        bits.append(f"📐 {'up' if _tl_up(x) else 'down'} "
                    f"{'this bar' if b == 0 else f'{b}b ago'}")
    n = getattr(x, "breadth", 0)
    if isinstance(n, int) and n >= 2:
        bits.append(f"🔗 {n} on this close, size once")
        # WHICH ONE OF THE CLUSTER. "Size once" told the reader a bundle is one
        # bet and then left them to guess which expression of it to take.
        # Scored over 2445 events, taking one rather than all of them lifts the
        # recovery factor from 1.33 to 1.84 and halves time under water; see
        # scanner.tag_event_pick. Only ever a label — the alert still sends.
        size = getattr(x, "event_size", 0)
        if isinstance(size, int) and size >= 2:
            bits.append("🎯 the pick" if getattr(x, "event_pick", False)
                        else f"pick is {_short(getattr(x, 'event_of', '') or '?')}")
    # The reader's OWN book, not the market's. 🔗 counts what is printing this
    # bar; ⚖ counts what they are still holding on this side from every bar
    # before it. A cluster that hurts usually spans several closes, so the two
    # are different facts and only one of them was ever on the alert.
    k = getattr(x, "open_same", 0)
    if isinstance(k, int) and k >= 2:
        side = "longs" if x.is_long else "shorts"
        bits.append(f"⚖ {k} {side} already open")
    return f"<i>{' · '.join(bits)}</i>" if bits else None


def tl_agrees(x) -> bool:
    """Whether the stored distance counts as confluence at all.

    THE WINDOW IS THE WHOLE THING. The raw bars-since-break is stored, and on
    the first live scan 40% of signals had SOME earlier break behind them — 38
    bars, 69, 108. The measured effect is gone by 20. A mark on 40% of alerts
    would mean nothing while still looking like it meant something.
    """
    b = getattr(x, "tl_break", -1)
    return isinstance(b, int) and 0 <= b <= TRENDLINE_CONFLUENCE_BARS


def _tl_up(x) -> bool:
    """Which way the agreeing break went. A swept HIGH implies a short, so the
    sweep's mapping is inverted exactly as it is everywhere else."""
    return (not x.is_high) if isinstance(x, Sweep) else x.is_long


def setup_message(s: Setup) -> str:
    tf = (f"{tf_label(s.tf or INTERVAL)}→{tf_label(ENTRY_INTERVAL)}"
          if s.entry_tf == "LTF" else tf_label(s.tf or INTERVAL))
    # The gap sits on whichever timeframe produced the entry.
    gap_step = BAR_SECONDS[ENTRY_INTERVAL] if s.entry_tf == "LTF" \
        else BAR_SECONDS[s.tf or INTERVAL]
    # When the same gap also produced an early signal, this one message stands
    # for both — the scanner suppressed the duplicate rather than sending the
    # identical entry and stop twice. Saying so keeps the early strategy
    # visible instead of silently swallowing it.
    also = (f" · ⚡ also early, gap {s.also_early} "
            f"bar{'' if s.also_early == 1 else 's'} after the raid"
            if s.also_early else "")
    why = _grade(s)
    return "\n".join(x for x in (
        _headline(f"★ 🎯 CONFIRMED", s.is_long, s.symbol, tf,
                  grade=grade_chip(s)),
        why,
        marks(s),
        "",
        _levels(s.entry, s.stop, s.risk, s.is_long, confirmed=True,
                interval=s.tf or INTERVAL),
        "",
        f"<i>sweep → shift → FVG{also} · "
        f"{_pool(s.src, s.level, s.pivots)}</i>",
        _footer(s.detected_time + gap_step, s.last_price, s.symbol, s.tf),
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
    why = _grade(s, early=True)
    return "\n".join(x for x in (
        _headline(f"⚡ EARLY", s.is_long, s.symbol,
                  tf_label(s.tf or INTERVAL), grade=grade_chip(s, True)),
        why,
        marks(s),
        "",
        _levels(s.entry, s.stop, s.risk, s.is_long),
        "",
        f"<i>sweep → FVG · no shift · gap {bars} bar"
        f"{'' if bars == 1 else 's'} after the raid · "
        f"{_pool(s.src, s.level, s.pivots, s.pools)}</i>",
        _footer(s.fvg_time + BAR_SECONDS[s.tf or INTERVAL], s.last_price,
                s.symbol, s.tf),
    ) if x is not None)


def _shift_distance(extreme: float, struct_level: float) -> str:
    """
    " · 5.9% away" appended to the line that already names the shift level.

    A first version of this was a whole extra LINE carrying the historical
    conversion rate. It was reverted: a sweep alert is read in two seconds to
    decide whether to open the chart, and a sentence of statistics is not what
    that decision needs.

    The rate is back, but as two words on the line that already exists. The
    distance and the conversion rate are the same fact stated twice — 3.9%
    away IS about 6% — so putting the rate anywhere other than beside the
    distance would be padding. Together they cost no line and answer the only
    question the level alone left open: is this worth watching at all.
    """
    odds = shift_odds(extreme, struct_level)
    if not odds:
        return ""
    return f" · {odds[0]:.1f}% away · ~{odds[1]}% convert"


def sweep_message(s: Sweep) -> str:
    """Heads-up on the grab. Deliberately carries no entry or stop: there is
    no setup yet, and the shift may never come."""
    is_long = not s.is_high
    took = "high" if s.is_high else "low"
    direction = "below" if s.is_high else "above"
    # The POI goes on the line that already exists rather than getting one of
    # its own. On a sweep it is not a verdict — there is nothing to grade yet
    # — it is the reason THIS raid was sent when dozens of others were not,
    # and it is the same test any setup born from this raid will face.
    #
    # With POI_SWEEPS on it is true of every sweep that arrives, so it reads
    # as a label rather than as news. That is the point: it says what the
    # filter let through. When the filter is off it varies, and then it is the
    # single most useful word in the message.
    where = (" in a daily POI" if s.poi
             else "" if s.poi_known else " · POI unknown")
    # No "WATCH" on a watchable sweep. With SWEEP_WATCH_ONLY on, every sweep
    # that arrives is one, so the word said nothing — the same reason the
    # band's historical rate came off the trade alerts. What stays is the
    # marking for the case where the filter is OFF: a skipped raid gets a
    # different icon and a lowercase tag, because eyes on a raid the bot is
    # telling you to ignore is a contradiction the reader has to look past.
    watch = sweep_worth(s.sweep_extreme, s.struct_level, s.poi, s.rvol)
    return "\n".join(x for x in (
        _headline("👀 <b>SWEEP</b>" if watch else "💤 <b>sweep</b>",
                  is_long, s.symbol, tf_label(s.tf or INTERVAL),
                  suffix="bias", grade="" if watch else "skip"),
        f"<i>liquidity taken{where} · no entry yet</i>",
        "",
        f"Sweep {took}   <code>{fmt(s.sweep_extreme)}</code>"
        + (f"   <i>{s.rvol:.1f}x volume</i>" if s.rvol > 0 else ""),
        f"Shift confirms {direction} <code>{fmt(s.struct_level)}</code>"
        f"{_shift_distance(s.sweep_extreme, s.struct_level)}",
        _pool(s.src, s.level, s.pivots, s.pools),
        _footer(s.sweep_time + BAR_SECONDS[s.tf or INTERVAL], s.last_price,
                s.symbol, s.tf),
    ) if x is not None)
