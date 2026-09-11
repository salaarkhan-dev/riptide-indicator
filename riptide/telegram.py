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
                     POI_INTERVAL, TREND_INTERVAL,
                     TRENDLINE_CONFLUENCE_BARS, log)
from .engine import (Early, Setup, Sweep, grade_of, shift_odds,
                     sweep_worth, tf_word)

def keyboard(*rows) -> dict:
    """An inline keyboard from rows of (label, callback_data) or (label, url).

    Telegram caps callback_data at 64 BYTES, which is why every button here
    carries a database row id rather than the trade it refers to.
    """
    out = []
    for r in rows:
        line = []
        for label, data in r:
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
              kind: str = "", suffix: str = "", grade: str = "",
              note: str = "") -> str:
    """
    First line of every alert, and the only line Telegram shows in the
    notification preview — so it carries everything needed to triage without
    opening the chat: what to do about it, which strategy, how good, which way,
    which symbol.

    THE TAG IS NOW THE INSTRUCTION, AND THERE IS EXACTLY ONE PER MESSAGE.
    It used to name the strategy (★ CONFIRMED / ⚡ EARLY) and leave the
    instruction to a 🎯 chip three lines down, next to a risk label that said
    "take" or "skip" — so a single alert could carry a 🎯 and the word "skip"
    and contradict itself on the reader's behalf. There is one decision in this
    bot and it is the pick; everything else describes. So the pick owns the
    first two words and the strategy moved to the middle of the line, where it
    is a fact like the timeframe rather than a call to action.

    The GRADE stays here, in the preview, because it is the one thing that
    decides whether to open the message at all.

    suffix qualifies the direction ("bias" on a sweep, where nothing is
    tradeable yet) and belongs beside it, not after the timeframe.
    """
    side = "long" if is_long else "short"
    # The grade is a bare bold letter, not a coloured dot. The direction
    # already owns the green/red dot on this line and a second coloured circle
    # beside it reads as noise rather than as a second signal.
    return (f"{tag} — {f'{kind} ' if kind else ''}"
            f"{'🟢' if is_long else '🔴'} {side}"
            f"{f' <i>{suffix}</i>' if suffix else ''} · "
            f"<b>{_short(symbol)}</b> · {tf}"
            f"{f' · grade <b>{grade}</b>' if grade else ''}"
            f"{f' · <i>{note}</i>' if note else ''}")


def _tag(x, kind: str) -> tuple[str, str]:
    """(tag, strategy word) for the headline.

    Three outcomes, and the third is not a fallback nobody sees: with
    RIPTIDE_EVENT_PICK=0, or on a signal the grouper could not place (no
    usable signal time), there is no pick to report and the alert names its
    strategy instead. Inventing a 🎯 there would be a claim nothing measured.
    """
    if getattr(x, "event_pick", False):
        return "🎯 <b>THE PICK</b>", kind
    if getattr(x, "event_of", ""):
        return "👀 <b>WATCH</b>", kind
    return (("★ <b>CONFIRMED</b>" if kind == "confirmed"
             else "⚡ <b>EARLY</b>"), "")


def _lead(x) -> str | None:
    """The optional second line. Present only when the header alone would
    mislead, which is two cases and no others.

    A plain 🎯 THE PICK gets NOTHING here. A restating line ("this is the one")
    is the kind of filler that teaches a reader to skip the line, and then the
    two lines that matter get skipped with it.
    """
    if getattr(x, "event_pick", False):
        # Best of a bad lot is still named — withholding the pick in an
        # all-wide cluster measured 4.08 recovery against 4.85 — but it is not
        # named in the same words as a pick that had a good candidate.
        return ("<i>best of a wide cluster</i>"
                if getattr(x, "event_weak", False) else None)
    of = getattr(x, "event_of", "")
    if not of:
        return None
    # "pick is SOL" reads as a live instruction. If SOL went out forty minutes
    # ago the reader is being pointed BACKWARDS, at a message they have already
    # seen and either took or did not, so past tense from five minutes.
    age = getattr(x, "event_age", 0)
    if isinstance(age, int) and age >= 300:
        return f"<i>{_short(of)} took this move {age // 60}m ago</i>"
    return f"<i>pick is {_short(of)}</i>"


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


# EVERY ALERT IS THE SAME SHAPE, AND THE SHAPE IS A LABELLED TABLE.
#
# What it replaced: a headline, a grade sentence, a line of chips, a block of
# levels, a line of provenance, and a footer — six different layouts across
# three alert types, with the same fact appearing in two of them depending on
# which type it was. A reader had to learn where each message put things.
#
# Now there are exactly three rows under the numbers and they never move:
#
#   move     what else is firing, and whether someone already took this
#   context  why it graded the way it did, and where the pool was
#   when     the clock, the last price, the chart
#
# The labels are wrapped in <code> and padded to a fixed width. That is not
# decoration — Telegram's body font is proportional, so plain-text padding does
# not align, and <code> is the only inline monospace it offers. <pre> would
# align the whole block but draws a heavy grey panel with a copy button, which
# on a phone dominates the message; that was tried and reverted once already
# (see _levels' old docstring, now gone with it).
LABEL_W = 8

# The price column, padded so the annotation beside it starts in the same place
# on every row. <code> rather than <b> and the two are not combined: Telegram
# does not allow other entities inside a code span, and monospace already
# stands out from the proportional body font as strongly as bold does. 13 fits
# the widest thing fmt() produces — "1.224958e-05".
PRICE_W = 13


def row(label: str, rest: str) -> str:
    return f"<code>{label:<{LABEL_W}}</code>{rest}"


def price_cell(v: float, note: str = "") -> str:
    return (f"<code>{fmt(v):<{PRICE_W}}</code><i>{note}</i>" if note
            else f"<code>{fmt(v)}</code>")


def _when(when: int, price: float, tv_symbol: str, interval: str = "") -> str:
    """The `when` row: clock, last price, chart. Age ONLY when it is news.

    signal_age always appended "· 0s ago", which on a fresh alert is a
    duplicate of the clock two characters to its left and cost a glance on
    every message. The age exists to catch a STALE send, so it prints from five
    minutes — the same threshold the deferral chip uses to decide whether it is
    pointing forwards or backwards.
    """
    clock, _, ago = signal_age(when).partition(" · ")
    bits = [clock]
    if int(time.time()) - when >= 300:
        bits.append(ago)
    if price:
        bits.append(f"last {fmt(price)}")
    bits.append(f"<a href='{tv_link(tv_symbol, interval)}'>chart</a>")
    return " · ".join(bits)


def _why(x, early: bool = False) -> str:
    """The reason for the letter in the headline, as the head of `context`.

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
    return grade_of(early, x.poi, x.trend_dir, x.is_long, x.di_dir)[1]


def _pool(src: str, pivots: int, pools: int = 0, level: float = 0.0) -> str:
    """`pools` > 1 means several separate pools were raided into the same gap
    — worth saying, since it is why one alert stands for what the engine saw
    as several clusters.

    THE POOL'S PRICE IS GONE FROM TRADE ALERTS and stays on sweeps. On a setup
    the message already carries an entry, a stop and a target; a fourth price
    that is not an order level is three characters of provenance competing with
    the three the reader acts on. On a sweep there are no order levels at all
    and the pool is the whole subject, so it is passed explicitly there.
    """
    out = f"{src} pool"
    if level:
        out += f" @ {fmt(level)}"
    if src == "Pivot" and pivots:
        out += f", {pivots} swings"
    if pools > 1:
        out += f", {pools} pools taken"
    return out


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
# Min60 ADDED 11 SEP, AND IT IS THE BEST-EVIDENCED OF THE THREE AFTER Min30.
# research/studies/poi_risk.py, 4723 filled Min60 trades over the same 333
# days, asked band-against-outside separately inside six POI arms and two
# streams -- eighteen tests, EIGHTEEN positive differences, +0.068 to +0.313,
# three clearing 2 SE. The arms overlap heavily so that is nearer five
# independent looks than eighteen, but not one points the wrong way.
#
# What makes it worth more than a fourth replication is that nothing was
# refitted. The 1.2 and 2.6 boundaries come from Min30 CONFIRMED and were
# applied unchanged to Min60 EARLY, a different stream on a different
# timeframe, and still separated. That is out-of-sample in the sense this
# project almost never gets.
#
# THE WIDE ARM IS WHERE THE DRAWDOWN LIVES, WHICH IS THE REAL ARGUMENT. On the
# Min60 R curve in exit order: tight +143.2 R at maxDD 41.9, band +280.1 at
# 55.3, wide -50.7 at 141.9. Of the 150.0 R maximum drawdown of the entire 1h
# stream, 141.9 sits in a bucket that makes no money. "skip" is not a marginal
# expectancy claim there; it is most of the pain.
#
# ONE HONEST DISCOUNT. The band's LOWER boundary does not obviously transfer.
# Min60's tight bucket runs +0.153 +/- 0.056 on 619 bets where the same bucket
# is flat on Min30, so on 1h only the upper cut may be doing work. That
# reading was taken AFTER seeing the grid and is not acted on: "flat" stays
# "flat" on Min60 until forward data says otherwise. It is recorded here so
# the next person does not rediscover it and think it is new.
#
# Still CONFIRMED ONLY, enforced by the caller, on every timeframe. The band
# holds on Min60 early too (+0.105, |z| 1.4) but that is not established, and
# widening the label and adding a timeframe in the same change would leave
# nothing to read forward.
#
# THE THREE WORDS CHANGED ON 11 SEP FROM take/flat/skip TO tight/normal/wide,
# AND THE GATING CAME OFF WITH THEM. Everything measured above is unchanged;
# what changed is that the label stopped pretending to be a decision.
#
# Two facts forced it. First, the bot now names ONE pick per rolling 120
# minutes (riptide/decide.py), and 61% of the picks it actually makes are not
# in the middle band — 39% normal, 47% tight, 13% wide. A message headed
# "🎯 THE PICK" three lines above a word reading "skip" is a contradiction the
# reader has to resolve, on every sixth alert. Second, 86% of the picks are
# EARLY signals, and on early the band measures +0.002: the word "take" was
# never available there anyway, which is why early alerts printed no label at
# all and looked like the measurement had been forgotten.
#
# tight / normal / wide is a description of the stop and it is TRUE ON EVERY
# TIMEFRAME AND ON BOTH STREAMS, because it is arithmetic on the stop distance
# rather than a claim about returns. So RISK_MEASURED_ON is gone: the gate
# existed to stop a VERDICT travelling to a timeframe it was not measured on,
# and there is no verdict to travel any more. A 15m early signal with a 4% stop
# now says "wide", which is a fact, where before it said nothing.
#
# What was lost: the alert no longer states the direction of the evidence. That
# moved to /legend and to the reference card, where it can carry the bootstrap
# intervals instead of compressing them into one word. The ordering the numbers
# above establish — wide is where the drawdown lives — is exactly why "wide" is
# still worth a word beside the percentage.
RISK_TIGHT_LABEL, RISK_NORMAL_LABEL, RISK_WIDE_LABEL = "tight", "normal", "wide"


def stop_width(riskpct: float) -> str:
    """"wide" over 2.6%, "normal" in 1.2-2.6%, "tight" under 1.2%.

    A description of the stop, not a verdict on the trade, so it is never
    blank: there is no timeframe and no stream on which a stop fails to have a
    width. See the block above for what the three zones measured, and for why
    that measurement is no longer stated in the word itself.
    """
    if riskpct > RISK_WIDE:
        return RISK_WIDE_LABEL
    return RISK_NORMAL_LABEL if riskpct >= RISK_TIGHT else RISK_TIGHT_LABEL


def _numbers(entry: float, stop: float, risk: float, is_long: bool) -> list:
    """The three rows you act on: entry, stop, target.

    3R IS GONE. It was printed beside 2R for months and was never measured:
    every study in research/ targets 2R and every band figure quoted anywhere
    in this codebase is a 2R figure. A second target with no evidence behind it
    sitting next to one with all of it is the kind of line a reader splits the
    difference on.

    THE ONE TARGET LEFT IS THE ONE THE TRACKER SCORES, read from the same
    TRACK_TARGET_R the tracker uses rather than from a literal 2. They were two
    independent constants that happened to agree; moving the key would have
    left /stats grading against a level no alert ever named.
    """
    sign = 1 if is_long else -1
    riskpct = risk / entry * 100 if entry else 0
    rows = [row("Entry", price_cell(entry)),
            row("Stop", price_cell(stop,
                                   f"{riskpct:.2f}%  ·  {stop_width(riskpct)}")),
            row("Target", price_cell(entry + sign * risk * TRACK_TARGET_R,
                                     f"{TRACK_TARGET_R:g}R"))]
    # The break-even row is gone unless it is switched back on. It advised a
    # stop move for months without ever having been measured, and it loses
    # money at every arm level on both signal types — see be_arm_r in
    # config.py. Advice on an alert should have cleared a bar.
    if CFG.be_arm_r > 0:
        rows.append(row("BE", price_cell(
            entry + sign * risk * CFG.be_arm_r,
            f"arm → stop {fmt(entry + sign * risk * CFG.be_lock_r)}")))
    return rows


def grade_letter(x, early: bool = False) -> str:
    """Just the letter, for looking up a band's live rate before rendering."""
    return grade_of(early, x.poi, x.trend_dir, x.is_long, x.di_dir)[0]


def _short(symbol: str) -> str:
    """APT_USDT -> APT. The quote is the same on all sixty and costs five
    characters on a line that has to fit a phone."""
    return symbol.split("_")[0] if symbol else "?"


def move_row(x) -> str:
    """The `move` row: everything about the CLUSTER this signal belongs to.

    ONE ROW, NOT FOUR CHIPS. The facts here used to be four separate glyphs —
    🔗 for other symbols on this close, 🎯 for the pick, 🔁 for the same raid
    on another timeframe, ⚖ for the reader's open book — and every one of them
    answers the same question: how many different ways is this one market move
    reaching me right now. Four glyphs made it look like four questions.

    "SIZE ONCE" IS NO LONGER WRITTEN, AND THE ADVICE DID NOT GO ANYWHERE. It
    was there because the deployed stream's worst losing run is forty trades
    inside twelve hours — one move taking out everything open. The pick rule
    now enforces exactly that: one 🎯 per rolling 120 minutes, so a reader
    following the header sizes once by construction. Repeating it as text on a
    message that already says WATCH is the contradiction the rename was for.

    Never empty: a lone signal says so, because "nothing else is firing" is
    itself a fact about the move and a blank row would read as a missing one.
    """
    bits = []
    # How wide the move is. event_size counts the whole rolling group across
    # every scanned timeframe; breadth counts one close on one timeframe, and
    # is the fallback for a signal the grouper could not place.
    size = getattr(x, "event_size", 0) or getattr(x, "breadth", 0)
    if isinstance(size, int) and size >= 2:
        bits.append(f"{size} symbols")
    # A DEFERRAL IS NOT GATED ON CLUSTER SIZE, and it used to be. The pick
    # holds for a cooldown that outlives the scan cycle, so a signal can be the
    # ONLY one in its cycle and still be deferring to a pick sent an hour ago.
    # Under the old size >= 2 gate that alert said nothing at all, which is the
    # one case where the reader most needs telling: it looks like a fresh
    # opportunity and it is not.
    of = getattr(x, "event_of", "")
    if of and not getattr(x, "event_pick", False):
        age = getattr(x, "event_age", 0)
        bits.append(f"{_short(of)} took it {age // 60}m ago"
                    if isinstance(age, int) and age >= 300
                    else f"{_short(of)} is the pick")
    # THE SAME RAID ON ANOTHER TIMEFRAME. The count above is other SYMBOLS;
    # this is the same symbol and the same direction printing again on a
    # different resolution, which is one idea arriving as two or three
    # messages. No preference between them — timeframes.py finds no timeframe
    # measurably better than another, so there is nothing to rank on and this
    # only says the duplication is there.
    also = getattr(x, "also_tf", ())
    if also:
        bits.append("also " + "+".join(tf_label(i) for i in also))
    # The reader's OWN book, not the market's. The count above is what is
    # printing now; this is what they are still holding on this side from every
    # bar before it. A cluster that hurts usually spans several closes, so the
    # two are different facts and only one of them was ever on the alert.
    k = getattr(x, "open_same", 0)
    if isinstance(k, int) and k >= 2:
        bits.append(f"you hold {k} {'longs' if x.is_long else 'shorts'}")
    return " · ".join(bits) or "alone this close"


def context_row(x, early: bool, pool: str) -> str:
    """The `context` row: why it graded the way it did, and where the pool was.

    Everything here is provenance. Nothing on this row changes what to do —
    the header does that — so it is the row to skim past when the chart is
    already open, and the row to read when deciding whether to open it.
    """
    bits = [_why(x, early), pool]
    if tl_agrees(x):
        b = x.tl_break
        bits.append(f"📐 {'up' if _tl_up(x) else 'down'} "
                    f"{'this bar' if b == 0 else f'{b}b ago'}")
    return " · ".join(b for b in bits if b)


def _card(head: str, lead: str | None, numbers: list, move: str,
          context: str, when: str) -> str:
    """Assemble the fixed layout. The three labelled rows are ALWAYS all three
    and always in this order, so the eye can go straight to one of them."""
    parts = [head] + ([lead] if lead else []) + [""] + numbers + [
        "",
        row("move", move),
        row("context", context),
        row("when", when)]
    return "\n".join(parts)


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
    """The confirmed setup: sweep, structure shift, entry gap.

    "sweep → shift → FVG" USED TO BE PRINTED HERE AND IS NOT ANY MORE. It was
    a restatement of the word CONFIRMED on the first line — that sequence is
    exactly what confirmed MEANS in this bot, and the early alert's own line
    said "no shift" to distinguish itself. One of the two had to go, and the
    header is the one that is read.
    """
    tf = (f"{tf_label(s.tf or INTERVAL)}→{tf_label(ENTRY_INTERVAL)}"
          if s.entry_tf == "LTF" else tf_label(s.tf or INTERVAL))
    # The gap sits on whichever timeframe produced the entry.
    gap_step = BAR_SECONDS[ENTRY_INTERVAL] if s.entry_tf == "LTF" \
        else BAR_SECONDS[s.tf or INTERVAL]
    context = context_row(s, False, _pool(s.src, s.pivots))
    # When the same gap also produced an early signal, this one message stands
    # for both — the scanner suppressed the duplicate rather than sending the
    # identical entry and stop twice. Saying so keeps the early strategy
    # visible instead of silently swallowing it.
    if s.also_early:
        context += f" · also early, gap {s.also_early}b"
    tag, kind = _tag(s, "confirmed")
    return _card(
        _headline(tag, s.is_long, s.symbol, tf, kind=kind,
                  grade=grade_letter(s)),
        _lead(s),
        _numbers(s.entry, s.stop, s.risk, s.is_long),
        move_row(s), context,
        _when(s.detected_time + gap_step, s.last_price, s.symbol, s.tf))


def early_message(s: Early) -> str:
    """
    The no-shift entry. Labelled distinctly from the confirmed setup because
    it is a different bet, not an earlier version of the same one: nothing has
    confirmed the reversal, so the sweep may simply be a trend continuing.
    What it buys is the stop sitting a few candles away at the raid extreme
    rather than a whole leg back.
    """
    bars = s.bars_from_sweep
    context = context_row(s, True, _pool(s.src, s.pivots, s.pools))
    context += f" · gap {bars}b after the raid"
    tag, kind = _tag(s, "early")
    return _card(
        _headline(tag, s.is_long, s.symbol, tf_label(s.tf or INTERVAL),
                  kind=kind, grade=grade_letter(s, True)),
        _lead(s),
        _numbers(s.entry, s.stop, s.risk, s.is_long),
        move_row(s), context,
        _when(s.fvg_time + BAR_SECONDS[s.tf or INTERVAL], s.last_price,
              s.symbol, s.tf))


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
    # "the {word} POI", never "a daily POI". The literal word was correct
    # only while POI_INTERVAL never moved, and on 9 Sep it moved to Hour8 and
    # this line spent two days naming a timeframe the bot was not reading.
    poi_word = (f"{tf_word(POI_INTERVAL)} POI" if s.poi
                else "POI unknown" if not s.poi_known
                else f"no {tf_word(POI_INTERVAL)} POI")
    # THE SAME VOCABULARY AS A SETUP'S GRADE, built by hand because a sweep has
    # no grade to take it from: nothing has confirmed, so engine.grade_of would
    # be scoring a trade that does not exist yet. The words match on purpose —
    # this is the same test any setup born from this raid will face, and a
    # reader should recognise it when it arrives on the setup an hour later.
    trend_ok = bool(s.trend_dir) and (s.trend_dir > 0) == is_long
    trend_word = (f"{tf_word(TREND_INTERVAL)} trend agrees" if trend_ok
                  else f"against the {tf_word(TREND_INTERVAL)} trend")
    # No "WATCH" on a watchable sweep. With SWEEP_WATCH_ONLY on, every sweep
    # that arrives is one, so the word said nothing — the same reason the
    # band's historical rate came off the trade alerts. What stays is the
    # marking for the case where the filter is OFF: a skipped raid gets a
    # different icon and a lowercase tag, because eyes on a raid the bot is
    # telling you to ignore is a contradiction the reader has to look past.
    watch = sweep_worth(s.sweep_extreme, s.struct_level, s.poi, s.rvol)
    # Level / Needs, not Entry / Stop / Target, and the labels are deliberately
    # not tradeable words: there is no order to place here. What replaces the
    # number block keeps the same two-column shape so the eye lands in the same
    # place, and says what has happened and what would have to happen next.
    numbers = [
        row("Level", price_cell(
            s.sweep_extreme,
            f"took the {_pool(s.src, s.pivots, s.pools, s.level)}")),
        row("Needs", price_cell(
            s.struct_level, f"shift {direction}"
            f"{_shift_distance(s.sweep_extreme, s.struct_level)}"))]
    move = (f"{s.rvol:.1f}x volume on the raid" if s.rvol > 0
            else "volume not measurable")
    return _card(
        _headline("👀 <b>SWEEP</b>" if watch else "💤 <b>sweep</b>",
                  is_long, s.symbol, tf_label(s.tf or INTERVAL),
                  kind=f"{took} taken", suffix="bias",
                  note="" if watch else "below the watch filter"),
        "<i>no entry yet — the shift may never come</i>",
        numbers, move, f"{poi_word} · {trend_word}",
        _when(s.sweep_time + BAR_SECONDS[s.tf or INTERVAL], s.last_price,
              s.symbol, s.tf))
