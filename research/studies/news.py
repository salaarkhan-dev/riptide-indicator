"""Does a signal fired near a US macro release cost anything?

THE QUESTION, ASKED THE USEFUL WAY ROUND. The obvious wish is an alert that
front-runs CPI with the consensus attached. But the bot does not trade the
number, it trades a raid-and-retrace, and its whole edge is +0.063 R per bet at
a 38% win rate. A release does not have to be tradeable to be expensive: if an
08:30 print routinely runs the stop on a setup that was working, then the
profitable use of the calendar is a MUTE, not a trade. A mute is also the only
version that needs no paid consensus feed, because the schedule is free and
deterministic and the numbers are not. So that is what gets measured first.

PRE-REGISTERED, BEFORE THE FIRST NUMBER

  PRIMARY. Confirmed A/B Min30 signals whose bar opens within 120 minutes
  either side of a CPI, PPI, Employment Situation or FOMC release, against
  every other signal. One arm, one window, decided in advance. The grid of
  other windows below it is descriptive and is not a second test.

  THE NULL IS A SHIFTED CALENDAR, NOT A SHUFFLED FEATURE. Every other study
  here rotates a per-symbol series, because its feature was a property of the
  symbol. "Near a release" is not: it is a property of the clock, true for all
  sixty symbols in the same half hour. Shuffling it per symbol would destroy
  exactly the cross-sectional clustering that makes the arm small, and would
  hand back a null far too lenient. So the placebo moves the WHOLE CALENDAR by
  a whole number of WEEKS, ±1 to ±16, which preserves the day of week, the time
  of day, the count of events and their spacing, and destroys only the fact
  that the number came out. 32 placebo calendars.

  AND THE HOUR IS CONFOUNDED WITH THE NEWS. 08:30 New York is the pre-open
  run-up whether or not anything is released; three of the four event types sit
  exactly there. If signals are simply bad at that hour, a careless reading
  credits it to CPI. The week-shift placebo already controls for this, and it
  is reported directly as well: the same clock window on NON-release weekdays
  against everything else.

  SURVIVES ONLY IF: the primary contrast beats at least 95% of the 32 placebo
  calendars AND holds its sign in 3 of 4 quarters AND is not explained by the
  same-clock control.

  EXPECTATION. Recorded before running. I expect the near-release arm to be
  worse, but by less than its own standard error — 40 events over 333 days is
  perhaps 30 to 80 independent bets, and at a per-bet sd near 1.4 R that arm
  cannot resolve anything smaller than about 0.3 R. The likely honest answer is
  "cannot tell", and a big clean number would make me suspect the calendar
  before believing the effect.

    PYTHONPATH=. RIPTIDE_MIN_GRADE=B RIPTIDE_DEEP_CACHE=/tmp/deep \\
        python3 research/studies/news.py

RESULT, 10 Sep 2026 — NOTHING HERE, AND THE CEILING IS THE REASON

  608 signals / 501 bets over 333 days, 39 releases in window.

    near release   13 bets  31% win  -0.092 R      other  488 bets  38% win
                                                          +0.065 R
    difference     -0.158 R at |z| 0.44

  THE PLACEBO CALENDARS SETTLE IT, AND NOT BY A NEAR MISS. 16 of the 20 usable
  week-shifted calendars produced a LARGER |z| than the real one, and their
  median difference was -0.273 R against the real -0.158. A calendar of dates
  on which nothing was published looks MORE like a news effect than the dates
  on which CPI actually came out. There is no signal to argue about.

  AND EVEN A REAL EFFECT WOULD NOT BE WORTH WIRING UP. The ±120 minute window
  is 2.20% of all bars and caught 13 of 501 bets. Muting it, at the measured
  and unsupported -0.158, saves 13 x 0.158 = 2.1 R a year against the stream's
  total of about 32 R. Six percent of annual return, estimated at 0.44 SE. The
  arm is too small to matter even if the number were true, which is the more
  durable finding: the sample cannot be fixed by waiting, because the shortage
  is releases per year, not days of history.

  WHAT DID SHOW UP IS THE HOUR, NOT THE NEWS. The pre-registered control — the
  same 08:30 New York window on weekdays with NO release — ran 72 bets at 31%
  and -0.107 R against +0.090 R elsewhere, |z| 1.14. Five times the arm of the
  news test, the same sign, the same win rate, and no release anywhere near it.
  Still short of significance, and it is a control rather than a hypothesis, so
  it is recorded here and NOT claimed. It is the better-powered question and
  would need its own pre-registration.

  Filed: hypothesis 13, not supported.
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import statistics                                       # noqa: E402
from collections import defaultdict                     # noqa: E402
from datetime import datetime, timezone                 # noqa: E402

import aiohttp                                          # noqa: E402

from riptide.config import CFG, TRACK_TARGET_R          # noqa: E402
from riptide.engine import grade_of, run_engine         # noqa: E402
from riptide.exchange import fetch_candles, list_symbols  # noqa: E402
from riptide.trend import di_at, direction_at, poi_at   # noqa: E402
from research.deep import load_universe                 # noqa: E402
from research.harness import mean_se, simulate          # noqa: E402
from research.releases import NY, releases              # noqa: E402

DAYS = 333
BEFORE, AFTER = 120, 120          # the pre-registered window, minutes
WEEK = 7 * 86400
PLACEBOS = [w for w in range(-16, 17) if w]     # ±1..±16 weeks, 32 calendars


class Sig:
    __slots__ = ("sym", "t", "r")


async def collect(sess, candles):
    """The deployed stream: confirmed A/B setups, filled, scored with fees."""
    out = []
    for sym, cs in candles.items():
        try:
            setups = run_engine(sym, cs, CFG)
        except Exception:
            continue
        idx = {c.t: i for i, c in enumerate(cs)}
        for x in setups:
            i = idx.get(x.detected_time)
            if i is None or x.entry <= 0 or abs(x.entry - x.stop) <= 0:
                continue
            o = simulate(cs, i, x.entry, x.stop, x.is_long,
                         target_r=TRACK_TARGET_R)
            if not o.filled or o.exit_bar is None:
                continue
            w = x.detected_time
            poi = await poi_at(sess, sym, w, x.stop, x.is_long, fetch_candles)
            if not (True if poi is None else bool(poi)):
                continue
            d = await direction_at(sess, sym, w, fetch_candles)
            di = await di_at(sess, sym, w, fetch_candles)
            if grade_of(False, True, d or 0, x.is_long, di or 0)[0] not in "AB":
                continue
            s = Sig()
            s.sym, s.t, s.r = sym, w, o.r
            out.append(s)
    return out


def near(t, stamps, before=BEFORE, after=AFTER):
    """Is bar-open t inside [-before, +after] minutes of any release in stamps?

    Linear over 40 stamps is nothing next to the engine, and a bisect here
    would only be a place to put an off-by-one.
    """
    for s in stamps:
        if -before * 60 <= t - s <= after * 60:
            return True
    return False


def bets(sigs):
    """One bet per signal BAR, averaging the symbols that fired on it.

    This matters more here than anywhere else in the project. Near-release
    signals arrive in cross-sectional bursts — one macro print moves all sixty
    perpetuals together — so counting each symbol as its own bet would inflate
    that arm's n by an order of magnitude against a standard error that assumes
    independence.
    """
    g = defaultdict(list)
    for s in sigs:
        g[s.t].append(s.r)
    return [statistics.fmean(v) for v in g.values()]


def contrast(sigs, flag):
    a = bets([s for s in sigs if flag(s)])
    b = bets([s for s in sigs if not flag(s)])
    if len(a) < 8 or len(b) < 20:
        return None
    ma, sa = mean_se(a)
    mb, sb = mean_se(b)
    se = (sa ** 2 + sb ** 2) ** 0.5
    return dict(na=len(a), nb=len(b), ma=ma, mb=mb, d=ma - mb, se=se,
                wa=sum(1 for r in a if r > 0) / len(a),
                wb=sum(1 for r in b if r > 0) / len(b),
                z=(ma - mb) / se if se else 0.0)


def line(tag, g):
    print(f"  {tag:<26} {g['na']:>4} bets {g['wa']:>3.0%} win {g['ma']:>+7.3f} R"
          f"   vs {g['nb']:>4} bets {g['wb']:>3.0%} win {g['mb']:>+7.3f} R"
          f"   diff {g['d']:>+7.3f}  |z| {abs(g['z']):>4.2f}")


async def main():
    async with aiohttp.ClientSession() as sess:
        syms = await list_symbols(sess)
        candles = await load_universe(sess, syms, "Min30", DAYS)
        sigs = await collect(sess, candles)

    lo = min(s.t for s in sigs)
    hi = max(s.t for s in sigs)
    rel = [(t, k) for t, k in releases() if lo - 86400 <= t <= hi + 86400]
    stamps = [t for t, _ in rel]
    kinds = defaultdict(int)
    for _, k in rel:
        kinds[k] += 1

    print(f"NEAR A US MACRO RELEASE\n{len(sigs)} confirmed A/B Min30 signals "
          f"over {DAYS} days · {len(bets(sigs))} bets\n"
          f"{len(rel)} releases in window: "
          + "  ".join(f"{k} {v}" for k, v in sorted(kinds.items()))
          + f"\nwindow {datetime.fromtimestamp(lo, timezone.utc):%Y-%m-%d} to "
          f"{datetime.fromtimestamp(hi, timezone.utc):%Y-%m-%d}")

    print(f"\nPRIMARY  -{BEFORE}min .. +{AFTER}min around any release")
    real = contrast(sigs, lambda s: near(s.t, stamps))
    if not real:
        print("  too few signals in the near arm to say anything. stopping.")
        return
    line("near release", real)

    # ---- the shifted-calendar placebo
    null = []
    for w in PLACEBOS:
        sh = [t + w * WEEK for t in stamps]
        g = contrast(sigs, lambda s, sh=sh: near(s.t, sh))
        if g:
            null.append((abs(g["z"]), g["d"], w))
    null.sort()
    zs = [z for z, _, _ in null]
    p95 = zs[int(0.95 * (len(zs) - 1))] if zs else float("nan")
    beat = sum(1 for z in zs if z >= abs(real["z"]))
    print(f"\n  placebo calendars ({len(zs)} of {len(PLACEBOS)} usable, whole-week "
          f"shifts, weekday and hour preserved)")
    print(f"    real |z| {abs(real['z']):.2f}   placebo p95 {p95:.2f}   "
          f"placebo max {zs[-1]:.2f}   {beat} of {len(zs)} placebos beat the real"
          f"   ->  {'CLEARS' if abs(real['z']) >= p95 else 'does not clear'}")
    worse = sum(1 for _, d, _ in null if d < 0)
    print(f"    placebo diffs: {worse} of {len(null)} negative, "
          f"median {statistics.median(d for _, d, _ in null):+.3f}")

    # ---- is it the news, or is it the hour?
    print("\n  same-clock control (is it the release or 08:30 New York?)")
    days = {datetime.fromtimestamp(t, NY).date() for t in stamps}

    def clockwin(s, h, m):
        d = datetime.fromtimestamp(s.t, NY)
        if d.date() in days or d.weekday() >= 5:
            return False
        mins = d.hour * 60 + d.minute - (h * 60 + m)
        return -BEFORE <= mins <= AFTER

    for label, h, m in (("08:30 ET, no release", 8, 30),
                        ("14:00 ET, no release", 14, 0)):
        g = contrast(sigs, lambda s, h=h, m=m: clockwin(s, h, m))
        if g:
            line(label, g)
        else:
            print(f"  {label:<26} too few")

    # ---- descriptive: other windows, and each release type alone
    print("\n  DESCRIPTIVE ONLY (not tested; each is a different question)")
    for b, a in ((30, 30), (60, 60), (120, 120), (60, 240), (0, 120), (120, 0)):
        g = contrast(sigs, lambda s, b=b, a=a: near(s.t, stamps, b, a))
        if g:
            line(f"-{b}min .. +{a}min", g)
    for k in ("CPI", "PPI", "NFP", "FOMC"):
        ks = [t for t, kk in rel if kk == k]
        g = contrast(sigs, lambda s, ks=ks: near(s.t, ks))
        if g:
            line(k + " only", g)
        else:
            print(f"  {k + ' only':<26} too few ({len(ks)} releases)")

    # ---- quarters
    byq = defaultdict(list)
    for s in sigs:
        d = datetime.fromtimestamp(s.t, timezone.utc)
        byq[f"{d.year}Q{(d.month - 1) // 3 + 1}"].append(s)
    cells, signs = [], []
    for q in sorted(byq):
        g = contrast(byq[q], lambda s: near(s.t, stamps))
        cells.append(f"{q} {g['d']:>+6.3f}" if g else f"{q}  thin ")
        if g:
            signs.append(g["d"] > 0)
    agree = max(sum(signs), len(signs) - sum(signs)) if signs else 0
    print("\n  by quarter  " + "   ".join(cells)
          + f"   -> sign holds {agree} of {len(signs)}")


if __name__ == "__main__":
    asyncio.run(main())
