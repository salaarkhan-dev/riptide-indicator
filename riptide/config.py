"""Configuration: environment settings and the engine's calibrated defaults.

Cfg mirrors the Pine inputs in riptide-indicator.pine. Change values here,
never in the engine body — the two are calibrated against each other and the
bot's alerts are verified against that indicator's chart output.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, fields

log = logging.getLogger("riptide")

# Futures API moved from contract.mexc.com to api.mexc.com in Jan 2026.
BASE = os.getenv("MEXC_BASE", "https://api.mexc.com")

TG_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TG_CHAT = os.getenv("TELEGRAM_CHAT_ID", "")

INTERVAL = os.getenv("RIPTIDE_INTERVAL", "Min30")     # Min15 Min30 Min60 Hour4

# Structure timeframes actually scanned. Every one of them is scanned in full
# — its own pools, its own sweeps, its own shifts — which is NOT what
# RIPTIDE_ENTRY_INTERVAL does (that moves the entry of a signal found on the
# main timeframe, and it is off and staying off; see riptide/mtf.py).
#
# Measured: Min15 alone is NEGATIVE (-0.095 confirmed, -0.039 early) and only
# turns positive inside a daily POI (+0.417 and +0.159). So a second timeframe
# is worth having ONLY with POI_REQUIRED on, and turning one on without the
# other makes the bot worse. See MEASUREMENTS.md, "The cell table".
INTERVALS = tuple(dict.fromkeys(
    i.strip() for i in os.getenv("RIPTIDE_INTERVALS", "Min30,Min15").split(",")
    if i.strip()) ) or (INTERVAL,)

# Send only signals whose raid landed inside a daily order block or fair value
# gap. The single largest separation measured here and the only filter to pass
# a pre-registered held-out test on symbols it was not found on. Policy G in
# research/studies/hybrid.py: return per unit of drawdown 6.94 -> 21.53 on a
# 300 USDT account.
#
# It suppresses roughly two thirds of alerts, and TOTAL R falls while R PER
# SIGNAL roughly doubles. That trade is only right while a position slot is
# the scarce thing. On a large enough account to take every signal, turn this
# off.
POI_REQUIRED = os.getenv("RIPTIDE_POI_REQUIRED", "1") == "1"

# Lowest grade worth a message. "C" sends everything the POI filter lets
# through; "B" mutes grade C; "A" leaves only confirmed setups that are both
# in a daily POI and with the daily trend.
#
# Measured over 2704 alerts in 42 days (research/studies/grades.py):
#
#     grade   n     /day   fill   win    RR    R/signal
#       A     188    4.5    72%   47%   1.82    +0.251
#       B    1043   25.1    81%   44%   1.72    +0.173
#       C    1473   35.4    78%   38%   1.70    +0.026
#
# C is 54% of the traffic for 4% of the return, and its largest single cell —
# 15m early C, about 15 alerts a day on its own — measures NEGATIVE at -0.007.
# Muting it takes 65 alerts a day down to 30 and keeps 86% of the total R.
#
# Grade D cannot be reached while POI_REQUIRED is on: D is early, no POI,
# against the trend, and the no-POI half is exactly what the filter removes.
MIN_GRADE = os.getenv("RIPTIDE_MIN_GRADE", "C").strip().upper()[:1] or "C"
if MIN_GRADE not in "ABCD":
    log.warning("RIPTIDE_MIN_GRADE=%r is not one of A B C D, using C",
                MIN_GRADE)
    MIN_GRADE = "C"
BAR_SECONDS = {"Min1": 60, "Min5": 300, "Min15": 900, "Min30": 1800,
               "Min60": 3600, "Hour4": 14400, "Hour8": 28800, "Day1": 86400}
LOOKBACK = int(os.getenv("RIPTIDE_LOOKBACK", "600"))   # bars fetched per symbol
# Only alert if the setup became detectable this recently — measured from
# Setup.detected_time, not from the shift. A shift-based window binned every
# setup whose gap was slow to arrive, which Cfg.max_bars_after_mss explicitly
# allows for up to 10 bars.
#
# Minimum 2; see _min_fresh below. 2 means "only the scan that fires right
# after the setup appears", which is the tightest setting that sends anything.
FRESH_BARS = int(os.getenv("RIPTIDE_FRESH_BARS", "2"))
DB_PATH = os.getenv("RIPTIDE_DB", "riptide.db")
CONCURRENCY = int(os.getenv("RIPTIDE_CONCURRENCY", "8"))

# Minimum gap between MEXC requests, in seconds, across the whole process.
#
# CONCURRENCY caps how many requests are in flight; it does not cap the RATE.
# Eight slots against a fast endpoint emptied 120 kline requests in about two
# seconds — roughly 60 a second — and the exchange answered most of them with
# a body carrying no candles at all. From one IP that burst is fine; from
# another it is not, and the difference is invisible from the code.
#
# 0.07s is about 14 requests a second, so a 120-request cycle spreads over
# ~9 seconds. That is nothing against a 15-minute scan and it removes the
# burst entirely. 0 disables the pacing.
MIN_REQUEST_GAP = float(os.getenv("RIPTIDE_MIN_REQUEST_GAP", "0.07"))
QUOTE = os.getenv("RIPTIDE_QUOTE", "USDT")
SYMBOLS_ENV = os.getenv("RIPTIDE_SYMBOLS", "")          # comma list, or blank
MIN_VOL_USDT = float(os.getenv("RIPTIDE_MIN_VOL", "3000000"))  # 24h turnover

# Cap the universe at the N most liquid symbols rather than everything above a
# turnover floor. A floor drifts with the market — 3M matched 91 symbols on one
# day and would match a different number on any other — while a top-N is a
# scan cost you can actually plan around: N x len(INTERVALS) kline requests per
# cycle. 0 disables the cap and keeps the floor alone.
TOP_N = int(os.getenv("RIPTIDE_TOP_N", "60"))

# Skip MEXC's tokenised stocks, indices and commodities — XAU, USOIL, SPX500,
# MUSTOCK and the rest. They are 428 of the 1024 USDT perps and 13 of the 60
# most active, so at any useful universe size they are most of what expanding
# would ADD.
#
# They must not be in it. Every measurement in this project was made on 24/7
# crypto perpetuals, and several depend on that directly: the Piercing Line
# and Dark Cloud Cover result rests on there being NO GAPS (0 of 1999 bars),
# because bar i opens exactly where bar i-1 closed. A tokenised stock follows
# an equity session — it gaps over the close, it gaps over the weekend, and a
# liquidity sweep across a session gap is a different event from the one
# measured here.
#
# The exchange's own conceptPlate tagging is the discriminator, so this
# follows MEXC's classification rather than guessing from ticker names.
EXCLUDE_TRADFI = os.getenv("RIPTIDE_EXCLUDE_TRADFI", "1") == "1"
ALERT_ON_FIRST_RUN = os.getenv("RIPTIDE_ALERT_FIRST_RUN", "0") == "1"
# Scan immediately on startup instead of waiting for the next bar close.
SCAN_ON_START = os.getenv("RIPTIDE_SCAN_ON_START", "1") == "1"
TG_RETRIES = int(os.getenv("RIPTIDE_TG_RETRIES", "4"))


# Listen for commands from TELEGRAM_CHAT_ID. Read-only status plus service
# control; there is still no exchange key and no order path anywhere.
TG_COMMANDS = os.getenv("RIPTIDE_TG_COMMANDS", "1") == "1"
# IANA name, e.g. Asia/Karachi. Display only — every internal calculation
# stays on UTC epoch seconds.
DISPLAY_TZ = os.getenv("RIPTIDE_TZ", "")
# Lower timeframe to place entries on. Structure is always found on
# RIPTIDE_INTERVAL; when this is set the entry and stop move to the first gap
# on this timeframe after the shift. Unset keeps the single-timeframe
# behaviour. Measured: Min15 entries fill 85% of the time against 45% for
# Min30, at the same hit rate.
ENTRY_INTERVAL = os.getenv("RIPTIDE_ENTRY_INTERVAL", "").strip()
# The cadence the scanner wakes on. With an entry timeframe set it follows the
# faster one, otherwise a gap could form and be up to a full HTF bar stale
# before anything looked for it.
# The loop has to wake at least once per bar of the FASTEST thing it scans,
# or 15m signals would be looked at on a 30m cadence and half of them would
# already be past the freshness window by the time they were seen.
SCAN_INTERVAL = ENTRY_INTERVAL or min(INTERVALS, key=lambda i: BAR_SECONDS.get(i, 1 << 30))
# How long to hold a setup back waiting for a lower-timeframe gap before
# falling back to the higher-timeframe entry, in HTF bars. The gap cannot
# exist at the first scan after the shift, so 0 would defeat the feature.
MTF_GRACE_BARS = int(os.getenv("RIPTIDE_MTF_GRACE_BARS", "2"))

# Suppress setups and sweeps that face against the higher-timeframe trend.
# The one filter measured to separate winners from losers — see trend.py.
TREND_FILTER = os.getenv("RIPTIDE_TREND_FILTER", "0") == "1"
# The SuperTrend filter's timeframe. Back to daily after re-measuring.
#
# It was moved to 4h on numbers from a backtest scorer that turned out to be
# broken — see the correction at the top of MEASUREMENTS.md. On the corrected
# scorer, separation between with-trend and against-trend on Min30 confirmed
# setups, net of fees:
#
#   daily SuperTrend  +0.250  +2.4 SE      (read +0.150 / +2.2 before)
#   4h SuperTrend     +0.214  +2.0 SE      (read +0.255 / +3.7 before)
#
# Daily is now ahead on both signal types, which is what it was before the
# switch. Neither clears 3 SE, so this is the better of two weak readings
# rather than a finding — /stats settles it.
# Hour8, not Day1, since 9 Sep. See MEASUREMENTS.md, "HELD-OUT: does Hour8
# replicate?". Discovered across eight arms on the recent 83 days and confirmed
# on days 83-166 back, which nothing had looked at: agree-minus-against positive
# in 8 of 8 cells across discovery and hold-out, under both conventions,
# beating Day1 in 4/4 out of sample. On that held-out window the DAILY reading
# went NEGATIVE on Min30 (-0.117) -- setups agreeing with the daily trend scored
# worse than those against it -- while Hour8 stayed positive on the same setups.
#
# THIS AND DI_INTERVAL MOVE TOGETHER. grade_of ANDs the SuperTrend with the DI,
# so changing one alone produces a mixed 8h/daily combination that no study
# measured. Set both or neither.
TREND_INTERVAL = os.getenv("RIPTIDE_TREND_INTERVAL", "Hour8")

# DI's timeframe, and it must stay DAILY. DI is the axis the grade letter is
# built on, and it is the one thing here that does not survive being moved:
#
#   daily DI  +0.266  +2.5 SE
#   4h DI     +0.011  +0.1 SE
#
# A flat null on 4h, and this is the one reading the correction did not move:
# it was +0.250 against +0.001 on the broken scorer and is +0.266 against
# +0.011 on the fixed one. They are two settings rather than one because the
# question is separable, which the 4h experiment proved even though the 4h
# answer was wrong; both now sit on Day1.
# Moved from Day1 to Hour8 with TREND_INTERVAL above, and for the same
# measurement — the tested arm was the SuperTrend AND the DI both on 8h.
DI_INTERVAL = os.getenv("RIPTIDE_DI_INTERVAL", "Hour8")

# The timeframe BTC's own trend is read on, for the market-context line on each
# alert. 30m — the effect is in the SHORT timeframes and vanishes by 4h. Early
# signals, held-out window: 30m +0.123 (1.8 SE), 1h +0.182 (2.7), 4h -0.051,
# daily +0.051. Never filters anything; see trend.btc_at.
BTC_REGIME_INTERVAL = os.getenv("RIPTIDE_BTC_REGIME_INTERVAL", "Min30")
TREND_LEN = int(os.getenv("RIPTIDE_TREND_LEN", "14"))
TREND_FACTOR = float(os.getenv("RIPTIDE_TREND_FACTOR", "5.0"))

# Outcome tracking. Scores every fresh setup forward against candles the
# scanner already fetches — no extra requests, no effect on what is alerted,
# and still no exchange key or order path. See tracker.py; read it with /stats.
TRACK = os.getenv("RIPTIDE_TRACK", "1") == "1"
# Bars after the gap forms in which a limit at the entry may fill. Past this
# the setup is recorded as never filled, which is a result, not a discard.
TRACK_FILL_BARS = int(os.getenv("RIPTIDE_TRACK_FILL_BARS", "10"))
# Bars a filled setup is followed before being marked to market. 60 Min30 bars
# is 30 hours — long enough that the target is reached or the trade is dead.
TRACK_HORIZON_BARS = int(os.getenv("RIPTIDE_TRACK_HORIZON_BARS", "60"))
# Target in R for the simulated rule. 1.0 is what measured best; MFE and MAE
# are stored per setup so another fixed target can be scored from the same
# rows afterwards.
# 2R, the minimum ratio actually traded. It was 1.0, so /stats was scoring a
# trade nobody takes. Measured on the corrected scorer, confirmed setups,
# total R across the whole window: 1R +20.4, 1.5R +39.5, 2R +52.8, 3R +61.9 —
# monotone, though each step is only about 1.5 SE, so this follows the trade
# rather than claiming the ladder is proven.
#
# Rows settled before this change were scored at 1R and are not comparable
# with rows settled after it.
TRACK_TARGET_R = float(os.getenv("RIPTIDE_TRACK_TARGET_R", "2.0"))

# Log open interest and funding per bar, so they can be tested LATER.
#
# MEXC serves holdVol (open interest) and fundingRate only as a snapshot from
# contract/ticker — there is no history endpoint for either, so unlike volume
# they cannot be backtested at all. The only way they ever become testable is
# to start recording them now and wait.
#
# Worth doing because open interest is the one genuine supply/demand reading a
# futures venue offers: OI FALLING through a raid means positions are being
# closed out, which is what a stop run is; OI RISING means new money is
# positioning, which is continuation and the reversal is wrong. Nothing in the
# OHLC can distinguish those two.
#
# Costs one request per scan — contract/ticker returns every symbol at once —
# and touches nothing that decides an alert. See market.py.
LOG_MARKET = os.getenv("RIPTIDE_LOG_MARKET", "1") == "1"
# Days of snapshots to keep. At one row per symbol per bar this is roughly
# 20 symbols x 48 bars x 180 days = 173k rows, a few MB.
MARKET_KEEP_DAYS = int(os.getenv("RIPTIDE_MARKET_KEEP_DAYS", "180"))
# Minimum 24h turnover for a symbol to be SNAPSHOTTED. Deliberately a third of
# MIN_VOL_USDT rather than equal to it: the scanned set is the top TOP_N by
# turnover and symbols near that line rotate in and out every few hours, so
# logging only the scanned ones produced short broken series — 94 symbols in
# 2.8 days but only 20 covering more than 95% of the bars. A broken series is
# nearly worthless here, because the quantity being tested is the CHANGE in
# open interest across the raid, which needs the previous bar too.
#
# The ticker response already carries every contract (1196 of them), so a
# lower floor costs no extra request and no extra latency — only rows. At this
# default that is roughly 180 symbols and about 1.5M rows over the full
# retention, tens of megabytes. Raise it if disk ever matters; MARKET_KEEP_DAYS
# is the other lever. Scanned symbols are always logged regardless of this.
MARKET_MIN_VOL = float(os.getenv("RIPTIDE_MARKET_MIN_VOL", "1000000"))

# The no-shift entry: sweep -> first imbalance, no structure shift required.
# A second strategy running beside the confirmed one, not a replacement — both
# fire independently on the same sweep and each alert says which it is.
# Whether early signals are SENT. They are always detected, recorded and
# armed for /stats regardless — muting a strategy must not stop measuring it,
# and the moment one looks bad is the moment its forward sample matters most.
EARLY_ALERTS = os.getenv("RIPTIDE_EARLY_ALERTS", "1") == "1"

# Heads-up alerts on the liquidity grab itself, ahead of the structure shift.
SWEEP_ALERTS = os.getenv("RIPTIDE_SWEEP_ALERTS", "1") == "1"
# Must be at least 2. Candle.t is the bar's OPEN time, so a bar that has just
# closed is already one full step old, and the scan wakes another 10s after
# that. A window of 1 * step can never contain the sweep that just confirmed,
# so 1 silently suppresses every alert.
SWEEP_FRESH_BARS = int(os.getenv("RIPTIDE_SWEEP_FRESH_BARS", "2"))

# Which timeframes send sweep heads-ups, and whether the POI filter applies to
# them. Sweeps are NOT trades — no entry, no stop, nothing to score — so no
# cell in the measured table covers them and neither of these is an edge
# decision. They are purely about how many messages a phone gets, and the
# rates are measured (research/studies/missed.py, 60 symbols, 42 days):
#
#     every sweep, both timeframes      393/day
#     every sweep, 30m only             216/day
#     in a daily POI, both timeframes   123/day
#     in a daily POI, 30m only           65/day   <- the default
#
# 30m only, POI required, is fewer messages than the 23-symbol single-timeframe
# setup used to send (~83/day) despite scanning nearly three times the market.
#
# The POI default is not arbitrary either: a sweep's POI is evaluated at the
# same raid the setup's would be, so a sweep outside a zone can only lead to
# signals that POI_REQUIRED then suppresses. Sending it would be advertising a
# setup the bot has already decided not to alert on.
SWEEP_INTERVALS = tuple(dict.fromkeys(
    i.strip() for i in os.getenv("RIPTIDE_SWEEP_INTERVALS", "Min30").split(",")
    if i.strip())) or (INTERVAL,)
POI_SWEEPS = os.getenv("RIPTIDE_POI_SWEEPS", "1") == "1"

# Send only the sweeps the alert would label WATCH — in a daily POI AND with
# the shift level closer than WATCH_MAX_DIST. The gate calls the same
# sweep_worth() that writes the label, so what the message says and what the
# filter does cannot drift apart.
#
# Measured over 5098 raids inside a daily POI, by how far the shift still was:
#
#     under 2%   30% of raids   65% of the R that followed
#     under 3%   48% of raids   87%          <- the threshold
#     under 4%   61% of raids   88%
#
# The band past 3% adds 13% more raids for 1% more value. Muting SKIP takes
# sweeps from about 65 a day to about 31.
SWEEP_WATCH_ONLY = os.getenv("RIPTIDE_SWEEP_WATCH_ONLY", "1") == "1"

# The distance threshold behind that verdict, in percent. One number, read by
# both the label and the filter — see engine.sweep_worth. This replaced a
# separate RIPTIDE_SWEEP_MAX_DIST, which was a second knob for the same
# decision and could have been set to disagree with the label the reader saw.
WATCH_MAX_DIST = float(os.getenv("RIPTIDE_WATCH_MAX_DIST", "3.0"))
# Which pool types raise a heads-up. Unset means all of them — the right
# default while the output is being checked against the chart, since
# filtering would hide part of what is being verified.
#
# For reference when tuning later: over 12.5 days on 20 symbols the share of
# sweeps that went on to produce a setup was Pivot 28%, Day 9%, Week 2%. The
# intuition that daily and weekly levels are the significant ones is not what
# the numbers show.
_sweep_src = os.getenv("RIPTIDE_SWEEP_SRC", "").strip()
SWEEP_SRC = ({s.strip() for s in _sweep_src.split(",") if s.strip()}
             if _sweep_src else None)


# ---------------------------------------------------------------- trendline
# The Liquidity Trendline watch: a heads-up when price closes clear of a
# descending resistance or an ascending support built from confirmed pivots.
# riptide/trendline.py is an exact port of the published indicator.
#
# THIS IS NOT A TRADE AND MUST NOT BE READ AS ONE. The same breakout went
# through the same scorer as everything else in this project
# (research/studies/trendline_measure.py): net R per signal is NEGATIVE on both
# halves of the window and indistinguishable from a random entry of the same
# shape. It carries no entry, no stop and no grade, and it never arms outcome
# tracking — there is no trade to track. What it is for is the thing
# TradingView cannot do: watch sixty charts at once and say which one just
# did something.
#
# THE TIMEFRAME IS THE WHOLE DESIGN, because a heads-up fails by arriving too
# often to read rather than by losing money. Measured over 60 symbols
# (research/studies/trendline_rate.py):
#
#     timeframe   per symbol/day   ACROSS THE UNIVERSE   worst single close
#     15m               1.82              109 a day            29 at once
#     30m               0.87               52                  21
#     1h                0.42               25                  16
#     4h                0.11                7  <- the default  20
#
# 109 a day is not an alert service, it is a feed, and the 15m chart is the
# one it is most tempting to set this to. 4h is roughly seven a day.
#
# Those bursts are why the watch sends ONE DIGEST per bar close rather than one
# message per break: twenty separate messages arriving in the same second is
# both unreadable and past Telegram's per-chat rate limit, and a market-wide
# move is exactly when it would happen.
TRENDLINE_ALERTS = os.getenv("RIPTIDE_TRENDLINE_ALERTS", "1") == "1"
# More than one is allowed and 15m+30m is the default, because a 30m close is
# also a 15m close: both land in the SAME digest rather than in two messages,
# and a symbol that breaks on both at once is shown once, on the slower one.
# The raw rate at 15m+30m is 161 a day, which is not readable — the slope gate
# below is what makes this pair viable, and it is not optional at these speeds.
TRENDLINE_INTERVALS = tuple(dict.fromkeys(
    i.strip() for i in
    os.getenv("RIPTIDE_TRENDLINE_INTERVALS", "Min15,Min30").split(",")
    if i.strip())) or ("Hour4",)
# Pivot length and channel padding, matching the indicator's own defaults. Left
# configurable because they are the indicator's inputs and someone comparing
# against a chart set differently needs to be able to match it — not because
# any value here has been measured as better. None has.
TRENDLINE_PIVOT = int(os.getenv("RIPTIDE_TRENDLINE_PIVOT", "5"))
TRENDLINE_SPACE = float(os.getenv("RIPTIDE_TRENDLINE_SPACE", "2.0"))
# THE STEEPNESS GATE, in |slope| / ATR(200) at the break. A flat line is a
# horizontal level, and price crossing a horizontal level is the most ordinary
# thing a chart does; a steeply descending resistance broken upward is at least
# a picture worth looking at. This drops the flat ones.
#
# IT IS A VOLUME CONTROL AND NOT A QUALITY FILTER, and that distinction was
# measured rather than assumed — research/studies/trendline_slope.py, 9082
# breaks at Min15 and 4327 at Min30, asking whether steep breaks follow through
# more often than flat ones over the next 8 bars:
#
#     Min15 discovery   flat 43.4%   steep 52.4%   +9.0pp   +4.4 SE
#     Min15 HELD OUT    flat 46.0%   steep 43.0%   -3.1pp   -1.4 SE
#     Min30 HELD OUT    flat 43.8%   steep 44.0%   +0.2pp   +0.1 SE
#
# The discovery half said steep breaks continue nine points more often at 4.4
# SE. The held-out half REVERSED it. That is what a fitted result looks like,
# and the only reason it was caught is that the threshold was chosen on one
# half and read on the other. If anything the lean is the other way: steep
# breaks' adverse excursion grows faster than their favourable one, on both
# timeframes held out. So this filter buys READABILITY, nothing more, and
# nothing in the alert claims otherwise.
#
# What it does buy, on the same measurement:
#
#     >= 0.00   100% kept   161 a day at 15m+30m   unreadable
#     >= 0.05    68%        110
#     >= 0.10    39%         63
#     >= 0.15    20%         32   <- the default
#     >= 0.20    10%         16
#
# Continuation sits at 44-48% at every threshold on both halves, against a 50%
# coin flip. These breaks very slightly MEAN REVERT. That is the fourth
# independent measurement in this project pointing the same way and it is the
# reason the digest says "not a trade" in the message itself.
TRENDLINE_MIN_SLOPE = float(os.getenv("RIPTIDE_TRENDLINE_MIN_SLOPE", "0.15"))


# Same rule as every other freshness window here: minimum 2, because a bar
# that has just closed is already one full step old. See _min_fresh.
TRENDLINE_FRESH_BARS = int(os.getenv("RIPTIDE_TRENDLINE_FRESH_BARS", "2"))
# Lines in one digest before it says "+N more". 20 is the worst single 4h
# close in the measured window, so in practice this trims nothing — it is there
# so a market-wide move on a faster timeframe cannot turn the digest into a
# wall. Telegram's own 4096-character cap is enforced separately and is the
# guarantee that the message sends at all; see watch.MAX_CHARS.
TRENDLINE_MAX_LINES = int(os.getenv("RIPTIDE_TRENDLINE_MAX_LINES", "20"))


def _min_fresh(name: str, value: int) -> int:
    """
    Freshness windows below 2 bars send nothing at all, ever.

    Candle.t is the bar's OPEN time, so a bar that has just closed is already
    one full step old, and the scan wakes another 10s after that: the age of
    the freshest possible signal is step + 10s. A window of 1 * step is
    smaller than that, so every signal fails the gate and the bot goes
    silent while looking perfectly healthy — no error, full logs, no alerts.

    Clamping loudly is better than honouring a value whose only effect is to
    mute the thing. 2 is the tightest window that sends anything, and it means
    "only the scan that fires immediately after the signal appears".
    """
    if value >= 2:
        return value
    log.warning("%s=%d would suppress every alert — a just-closed bar is "
                "already step+10s old, which no 1-bar window can contain. "
                "Using 2, the tightest window that sends anything.", name, value)
    return 2


FRESH_BARS = _min_fresh("RIPTIDE_FRESH_BARS", FRESH_BARS)
SWEEP_FRESH_BARS = _min_fresh("RIPTIDE_SWEEP_FRESH_BARS", SWEEP_FRESH_BARS)
TRENDLINE_FRESH_BARS = _min_fresh("RIPTIDE_TRENDLINE_FRESH_BARS",
                                  TRENDLINE_FRESH_BARS)


@dataclass
class Cfg:
    """Defaults mirror the Pine inputs. Change here, not in the engine."""
    pivot_left: int = 1
    pivot_right: int = 2
    atr_len: int = 28
    tol_atr: float = 0.25
    max_pool_span_bars: int = 60
    max_cluster_span_atr: float = 0.80
    min_pivots: int = 2
    max_overshoot_atr: float = 0.25
    allow_join_after_sweep: bool = True
    pending_expiry_bars: int = 500
    pending_invalidate_atr: float = 0.50
    grab_buffer_atr: float = 0.0
    trail_grab_extreme: bool = True
    max_bars_after_grab: int = 50
    mss_close: bool = True
    mss_cooldown_bars: int = 5
    min_fvg_atr: float = 0.05
    max_fvg_atr: float = 2.0
    # CONFIRMED setups only. 2.5, not 4.0, and the two signal types no longer
    # share one cap. Swept by re-running the engine at each value — a rejected
    # gap does not end the search, so a tighter cap yields a later, tighter gap
    # off the same raid rather than simply fewer signals:
    #
    #   confirmed  2.5 ATR  242 signals  +0.260 R  total +63.0
    #              4.0 ATR  544 signals  +0.110 R  total +59.7
    #
    # +0.151 at 2.5 SE, same sign on all four splits. Read it for what it is:
    # total R is inside noise, so this is the SAME money from 44% of the
    # trades, not more money. What improves is exposure and R per trade.
    max_risk_atr: float = 2.5
    # EARLY signals, which want the opposite and are why this is two settings.
    # Tightening them costs total R the whole way down — 4.0 ATR +153.4,
    # 3.0 +151.3, 2.5 +143.2, 1.5 +105.0 — while R per signal rises, which is
    # the shape of a filter deleting winners. Against 4.0 the 2.5 difference is
    # +0.007 at 0.035 SE: nothing.
    early_max_risk_atr: float = 4.0
    # There is deliberately no minimum on either. A stop inside one ordinary
    # candle looks like it should be filtered out, but three pre-registered
    # floors (0.50, 0.75, 1.00 ATR) found no effect, and the two with enough
    # samples to read ran the other way. See "A minimum risk floor" in
    # MEASUREMENTS.md.
    max_bars_after_mss: int = 10
    # Where the entry-gap search starts. Mirrors the Pine input "Look for
    # entry zones from":
    #   "grab"  every imbalance across the whole move from the raid to the
    #           break, including gaps that formed BEFORE the break
    #   "mss"   the break bar onwards only
    # "grab" was the original default, matching the reference indicator, and it
    # has a failure mode: the stop is pinned at the raid extreme, so as price
    # runs, newer gaps fail max_risk_atr and the search walks back until one
    # fits — handing back an entry from many bars ago, far below market. The
    # two score the same per setup (+0.045 against +0.042 R), but "mss" fills
    # 64-75% of the time against 40-60%. Both defaults now say "mss".
    fvg_scan_from: str = "mss"            # grab | mss
    # No-shift entry: how many bars after the raid to keep watching for the
    # first imbalance. Has no counterpart in the Pine — this pattern is not in
    # the reference indicator. See Early in engine.py.
    early_max_bars: int = 10
    sl_buffer_atr: float = 0.0
    entry_mode: str = "proximal"          # proximal | mid | distal
    use_pivot: bool = True
    use_daily: bool = True
    # Off by default: 295 weekly raids produced zero setups in 41.6 days. See
    # "Pool source" in MEASUREMENTS.md — it is a switch, not a deletion.
    use_weekly: bool = False
    # OFF. It shipped at 1.5R for months and was never measured; when it
    # finally was, it lost money at every setting on both signal types.
    # Against no break-even, target 2R, confirmed setups:
    #
    #   arm 1.0R  -0.074  -2.5 SE       arm 1.5R  -0.019  -1.3 SE
    #   arm 1.75R -0.008  -1.0 SE
    #
    # Early signals the same, -0.001 to -0.009. The mechanism is not subtle:
    # it converts trades that would have reached the target into +0.1R
    # scratches, and 26% of confirmed setups reach 3R. 0 leaves the stop alone.
    be_arm_r: float = 0.0
    be_lock_r: float = 0.1     # break-even stop locks in this much,
                               # so a 'scratch' still covers fees.
                               # Mirrors beLockR in the Pine.


def _cfg_from_env(base: Cfg) -> tuple[Cfg, dict]:
    """
    Every Cfg field can be overridden as RIPTIDE_<FIELD_NAME>, e.g.
    RIPTIDE_PIVOT_RIGHT=1. Defaults are untouched — this only adds the ability
    to change one from riptide.conf, so the reference indicator's settings can
    be tried live and reverted without a code change.
    """
    changed = {}
    for f in fields(base):
        raw = os.getenv("RIPTIDE_" + f.name.upper())
        if raw is None:
            continue
        current = getattr(base, f.name)
        try:
            # bool before int: bool is a subclass of int, so the int branch
            # would swallow it and turn "false" into a ValueError.
            if isinstance(current, bool):
                value = raw.strip().lower() in ("1", "true", "yes", "on")
            elif isinstance(current, int):
                value = int(raw)
            elif isinstance(current, float):
                value = float(raw)
            else:
                value = raw.strip()
        except ValueError:
            log.warning("RIPTIDE_%s=%r is not a valid %s, keeping %r",
                        f.name.upper(), raw, type(current).__name__, current)
            continue
        if value != current:
            changed[f.name] = (current, value)
            setattr(base, f.name, value)
    return base, changed


CFG, CFG_OVERRIDES = _cfg_from_env(Cfg())

# The engine reads fvg_scan_from as `== "grab"`, so ANY other string — a typo,
# or the Pine's own wording — silently selects a mode instead of failing.
# Normalise and validate here, where it can say so.
_FVG_SCAN_FROM = {"grab": "grab", "grab candle": "grab",
                  "mss": "mss", "mss candle only": "mss", "mss only": "mss"}
_raw_scan = str(CFG.fvg_scan_from).strip().lower()
if _raw_scan in _FVG_SCAN_FROM:
    CFG.fvg_scan_from = _FVG_SCAN_FROM[_raw_scan]
else:
    # Fall back to the DEFAULT, not to a hardcoded mode. This used to say
    # "grab", which was the default at the time; once the default moved to
    # "mss" that turned a typo into a silent downgrade to the old behaviour —
    # the exact failure this block exists to prevent.
    fallback = Cfg().fvg_scan_from
    log.warning("RIPTIDE_FVG_SCAN_FROM=%r is not 'grab' or 'mss'; using %r, "
                "the default. Anything unrecognised would otherwise have "
                "selected 'mss' by accident, since the engine tests for "
                "'grab' by name.", CFG.fvg_scan_from, fallback)
    CFG.fvg_scan_from = fallback
    CFG_OVERRIDES.pop("fvg_scan_from", None)


def build_id() -> str:
    """
    Short commit the running code came from, written by deploy/update.sh.

    update.sh writes BUILD into the application directory, beside
    riptide_bot.py — one level above this package. The candidates cover that,
    a copy inside the package, and the working directory systemd starts us in,
    so the lookup survives being moved or run from a checkout.
    """
    pkg = os.path.dirname(os.path.abspath(__file__))
    for path in (os.path.join(os.path.dirname(pkg), "BUILD"),
                 os.path.join(pkg, "BUILD"),
                 "BUILD"):
        try:
            with open(path) as f:
                value = f.read().strip()[:12]
        except OSError:
            continue
        if value:
            return value
    return "unknown"

# How recent a same-direction trendline breakout has to be to count as
# CONFLUENCE on a trade alert, in bars of that signal's own timeframe.
#
# NOT COSMETIC, AND THE FIRST LIVE CHECK PROVED IT. The tag stores the raw
# bars-since-break, and without this window 667 of 1662 signals — 40% — carried
# a "confluence" whose most recent break was 38, 69 or 108 bars old. The
# measured effect does not survive anywhere near that far:
#
#     window   kept   difference vs no break
#        3      1%          +0.126
#        5      2%          +0.178
#       10      3%          +0.206   <- this
#       20     10%          +0.052
#       40     26%          -0.002
#
# 10 is CFG.early_max_bars, which is the engine's own notion of "recent enough
# to be the same event", and it was fixed in advance rather than read off that
# table. A marker on 40% of alerts would mean nothing and would still look like
# it meant something, which is worse than not having one.
#
# The raw distance is stored regardless, so a different window can be measured
# later from rows already on disk without re-recording anything.
TRENDLINE_CONFLUENCE_BARS = int(
    os.getenv("RIPTIDE_TRENDLINE_CONFLUENCE_BARS", "0")) or CFG.early_max_bars
