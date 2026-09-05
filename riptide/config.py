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
QUOTE = os.getenv("RIPTIDE_QUOTE", "USDT")
SYMBOLS_ENV = os.getenv("RIPTIDE_SYMBOLS", "")          # comma list, or blank
MIN_VOL_USDT = float(os.getenv("RIPTIDE_MIN_VOL", "3000000"))  # 24h turnover
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
SCAN_INTERVAL = ENTRY_INTERVAL or INTERVAL
# How long to hold a setup back waiting for a lower-timeframe gap before
# falling back to the higher-timeframe entry, in HTF bars. The gap cannot
# exist at the first scan after the shift, so 0 would defeat the feature.
MTF_GRACE_BARS = int(os.getenv("RIPTIDE_MTF_GRACE_BARS", "2"))

# Suppress setups and sweeps that face against the higher-timeframe trend.
# The one filter measured to separate winners from losers — see trend.py.
TREND_FILTER = os.getenv("RIPTIDE_TREND_FILTER", "0") == "1"
TREND_INTERVAL = os.getenv("RIPTIDE_TREND_INTERVAL", "Day1")
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
TRACK_TARGET_R = float(os.getenv("RIPTIDE_TRACK_TARGET_R", "1.0"))

# Heads-up alerts on the liquidity grab itself, ahead of the structure shift.
SWEEP_ALERTS = os.getenv("RIPTIDE_SWEEP_ALERTS", "1") == "1"
# Must be at least 2. Candle.t is the bar's OPEN time, so a bar that has just
# closed is already one full step old, and the scan wakes another 10s after
# that. A window of 1 * step can never contain the sweep that just confirmed,
# so 1 silently suppresses every alert.
SWEEP_FRESH_BARS = int(os.getenv("RIPTIDE_SWEEP_FRESH_BARS", "2"))
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
    max_risk_atr: float = 4.0
    max_bars_after_mss: int = 10
    # Where the entry-gap search starts. Mirrors the Pine input "Look for
    # entry zones from":
    #   "grab"  every imbalance across the whole move from the raid to the
    #           break, including gaps that formed BEFORE the break
    #   "mss"   the break bar onwards only
    # The Pine ships "Grab candle", so that is the default here too. Note what
    # it costs: the stop is pinned at the raid extreme, so as price runs the
    # newer gaps fail max_risk_atr and the search keeps walking back until one
    # fits — which can hand back an entry from many bars ago, far below market.
    fvg_scan_from: str = "grab"           # grab | mss
    sl_buffer_atr: float = 0.0
    entry_mode: str = "proximal"          # proximal | mid | distal
    use_pivot: bool = True
    use_daily: bool = True
    use_weekly: bool = True
    be_arm_r: float = 1.5
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
# or the Pine's own wording — silently selects the other mode instead of
# failing. Normalise and validate here, where it can say so.
_FVG_SCAN_FROM = {"grab": "grab", "grab candle": "grab",
                  "mss": "mss", "mss candle only": "mss", "mss only": "mss"}
_raw_scan = str(CFG.fvg_scan_from).strip().lower()
if _raw_scan in _FVG_SCAN_FROM:
    CFG.fvg_scan_from = _FVG_SCAN_FROM[_raw_scan]
else:
    log.warning("RIPTIDE_FVG_SCAN_FROM=%r is not 'grab' or 'mss'; using 'grab'. "
                "Anything unrecognised would otherwise have selected 'mss' by "
                "accident, since the engine tests for 'grab' by name.",
                CFG.fvg_scan_from)
    CFG.fvg_scan_from = "grab"
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
