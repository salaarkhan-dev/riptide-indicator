"""US macro release timestamps, taken from the issuing agencies. Nothing here
is inferred from a rule of thumb.

WHY THIS FILE IS HAND-ENTERED RATHER THAN FETCHED. Four keyless calendar feeds
were tried first and all four are unusable from this box: TradingView and
Investing return 403, the TradingEconomics guest account is discontinued (410),
and FMP wants a key. Nasdaq's `api/calendar/economicevents` IS reachable and
carries consensus and actual — but a 248-weekday harvest of it returned 12,059
rows containing ZERO Consumer Price Index or Producer Price Index events for
any country, and only 5 Nonfarm Payrolls prints in twelve months against the 12
that exist. It is silently incomplete on exactly the releases that matter, and
a study built on it would have measured "days Nasdaq happened to list" instead
of "days the number came out". So the dates below come from the schedules BLS
and the Federal Reserve publish themselves.

  CPI / PPI / Employment Situation
      https://www.bls.gov/schedule/news_release/cpi.htm
      https://www.bls.gov/schedule/news_release/ppi.htm
      https://www.bls.gov/schedule/news_release/empsit.htm
      https://www.bls.gov/schedule/2025/home.htm
      All BLS principal releases are 08:30 America/New_York.

  FOMC
      https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
      The statement lands 14:00 America/New_York on the SECOND day of the
      meeting, which is the date recorded here.

THE 2025 SHUTDOWN IS VISIBLE IN THIS DATA AND IS NOT A TYPO. There is no
November 2025 CPI release, no October 2025 PPI release, and the September 2025
jobs report came out on 20 Nov. The schedule stayed off its normal cadence into
2026, which is why a jobs report appears on a Wednesday (11 Feb 2026) and a CPI
on a Friday (13 Feb 2026). Those are the real dates; a study that "corrected"
them to the usual first-Friday pattern would be testing a calendar that never
happened.

TIMES ARE LOCAL TO NEW YORK, DELIBERATELY. 08:30 ET is 12:30 UTC under EDT and
13:30 UTC under EST, so a UTC constant would silently drift by an hour across
the two DST changes inside the window and misalign a third of the sample by two
Min30 bars.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")

# (date, local time, kind) — kind is what an alert would name.
SCHEDULE = [
    # ---- CPI, 08:30 ET
    ("2025-10-24", "08:30", "CPI"),
    ("2025-12-18", "08:30", "CPI"),
    ("2026-01-13", "08:30", "CPI"),
    ("2026-02-13", "08:30", "CPI"),
    ("2026-03-11", "08:30", "CPI"),
    ("2026-04-10", "08:30", "CPI"),
    ("2026-05-12", "08:30", "CPI"),
    ("2026-06-10", "08:30", "CPI"),
    ("2026-07-14", "08:30", "CPI"),
    ("2026-08-12", "08:30", "CPI"),
    ("2026-09-11", "08:30", "CPI"),
    # ---- PPI, 08:30 ET
    ("2025-11-25", "08:30", "PPI"),
    ("2026-01-14", "08:30", "PPI"),
    ("2026-01-30", "08:30", "PPI"),
    ("2026-02-27", "08:30", "PPI"),
    ("2026-03-18", "08:30", "PPI"),
    ("2026-04-14", "08:30", "PPI"),
    ("2026-05-13", "08:30", "PPI"),
    ("2026-06-11", "08:30", "PPI"),
    ("2026-07-15", "08:30", "PPI"),
    ("2026-08-13", "08:30", "PPI"),
    ("2026-09-10", "08:30", "PPI"),
    # ---- Employment Situation (nonfarm payrolls), 08:30 ET
    ("2025-11-20", "08:30", "NFP"),
    ("2025-12-16", "08:30", "NFP"),
    ("2026-01-09", "08:30", "NFP"),
    ("2026-02-11", "08:30", "NFP"),
    ("2026-03-06", "08:30", "NFP"),
    ("2026-04-03", "08:30", "NFP"),
    ("2026-05-08", "08:30", "NFP"),
    ("2026-06-05", "08:30", "NFP"),
    ("2026-07-02", "08:30", "NFP"),
    ("2026-08-07", "08:30", "NFP"),
    ("2026-09-04", "08:30", "NFP"),
    # ---- FOMC statement, 14:00 ET, second day of the meeting
    ("2025-10-29", "14:00", "FOMC"),
    ("2025-12-10", "14:00", "FOMC"),
    ("2026-01-28", "14:00", "FOMC"),
    ("2026-03-18", "14:00", "FOMC"),
    ("2026-04-29", "14:00", "FOMC"),
    ("2026-06-17", "14:00", "FOMC"),
    ("2026-07-29", "14:00", "FOMC"),
]


def releases(kinds=None):
    """[(unix_seconds, kind)] sorted, DST resolved against New York."""
    out = []
    for day, hm, kind in SCHEDULE:
        if kinds and kind not in kinds:
            continue
        h, m = (int(x) for x in hm.split(":"))
        y, mo, d = (int(x) for x in day.split("-"))
        out.append((datetime(y, mo, d, h, m, tzinfo=NY).timestamp(), kind))
    return sorted(out)
