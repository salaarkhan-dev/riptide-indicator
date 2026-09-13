"""THE FULL TABLE BEHIND THE STRUCTURE-TREND GATE — early, confirmed, pooled.

lit_trend.py and lit_trend_conf.py settled the statistics. This prints what a
person deciding whether to SHIP it needs to see instead: win rate, average win,
average loss, profit factor and total R for every arm, split by whether the
structure indicator's trend agreed with the signal.

No new measurement and no new claim. It reads the row cache the other two
studies built, so the numbers here are the same numbers, presented for a
decision rather than for a significance test.

THE COLUMN THAT DECIDES IS `cut R/sig`, NOT `|SE|`. A gate pays only when the
group it removes LOSES money. A group that is merely less positive costs
alerts and returns nothing, which is what sank the pooled arm even though the
pooled arm was the one that was pre-registered and the one that separated.

    PYTHONPATH=. RIPTIDE_DEEP_CACHE=/tmp/deep \\
        python3 research/studies/lit_trend_detail.py
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import statistics                                       # noqa: E402

from research.harness import mean_se                    # noqa: E402
from research.studies.poi_tf import DAYS                # noqa: E402
from research.studies.lit_trend import INTERVAL         # noqa: E402
from research.studies.lit_trend_conf import build       # noqa: E402

SYMS_LIVE = 120


def stats(rows):
    """(n, win%, avg win, avg loss, R/sig, SE, profit factor, total R)."""
    rs = [r for _, r in rows]
    w = [r for r in rs if r > 0]
    lo = [r for r in rs if r <= 0]
    m, se = mean_se(rs)
    gl = -sum(lo)
    return (len(rs), len(w) / len(rs) if rs else 0.0,
            statistics.fmean(w) if w else 0.0,
            statistics.fmean(lo) if lo else 0.0,
            m, se, sum(w) / gl if gl else 0.0, sum(rs))


def header():
    print(f"  {'arm':<26}{'n':>6}{'win':>6}{'avg win':>9}{'avg loss':>10}"
          f"{'R/sig':>9}{'':>7}{'PF':>6}{'total R':>10}")


def line(label, rows):
    n, win, aw, al, m, se, pf, tot = stats(rows)
    print(f"  {label:<26}{n:>6}{win:>6.0%}{aw:>+9.3f}{al:>+10.3f}"
          f"{m:>+9.3f}±{se:.3f}{pf:>6.2f}{tot:>+10.1f}")


def arm(name, rows):
    a = [(s, r) for s, ok, r in rows if ok]
    b = [(s, r) for s, ok, r in rows if not ok]
    if len(a) < 25 or len(b) < 25:
        print(f"\n{name} — too few to read")
        return
    print(f"\n{name}")
    header()
    line("everything (no gate)", [(s, r) for s, _, r in rows])
    line("KEPT  structure agrees", a)
    line("CUT   structure disagrees", b)
    ma, sa = mean_se([r for _, r in a])
    mb, sb = mean_se([r for _, r in b])
    se = (sa ** 2 + sb ** 2) ** 0.5
    z = abs((ma - mb) / se) if se else 0.0
    tot = sum(r for _, r in rows_r(rows))
    gain = len(a) * ma - tot
    per_day = len(b) / DAYS * SYMS_LIVE / 59
    print(f"  {'':<26}separation |SE| {z:>4.1f}"
          f"   gate delta {gain:>+7.1f}R"
          f"   alerts {-len(b) / len(rows):>4.0%}  ({per_day:.1f}/day at 120)")
    if mb >= 0:
        print("  the cut group does NOT lose money — this gate costs alerts "
              "and returns nothing")


def rows_r(rows):
    return [(s, r) for s, _, r in rows]


def main():
    blob = asyncio.run(build())
    data = [tuple(d) for d in blob["data"]]

    print("THE STRUCTURE-TREND GATE, IN FULL — what shipping it would change")
    print(f"{len(data)} filled signals, 59 symbols, {DAYS} days, {INTERVAL}. "
          f"'/day at 120' scales to the deployed universe.")
    print("n counts FILLED signals only; unfilled limits never became trades.")

    ab = [(d[0], d[1], d[2]) for d in data if d[5]]
    early = [(d[0], d[1], d[2]) for d in data if d[5] and d[3] == "early"]
    conf = [(d[0], d[1], d[2]) for d in data if d[5] and d[3] == "confirmed"]
    cd = [(d[0], d[1], d[2]) for d in data if not d[5]]

    arm("A/B POOLED — the pre-registered primary", ab)
    arm("A/B EARLY", early)
    arm("A/B CONFIRMED — the only arm whose cut group loses money", conf)
    arm("C/D — what the existing grade already throws away", cd)

    print(f"\n{'=' * 92}\nLONG AND SHORT, ON THE CONFIRMED ARM\n{'=' * 92}")
    for nm, want in (("longs", True), ("shorts", False)):
        sub = [(d[0], d[1], d[2]) for d in data
               if d[5] and d[3] == "confirmed" and d[7] == want]
        a = [(s, r) for s, ok, r in sub if ok]
        b = [(s, r) for s, ok, r in sub if not ok]
        if len(a) < 25 or len(b) < 25:
            print(f"  {nm:<10} too few ({len(a)} / {len(b)})")
            continue
        print(f"\n  {nm}")
        header()
        line("    KEPT  agrees", a)
        line("    CUT   disagrees", b)

    print(f"\n{'=' * 92}\nWHAT IT COSTS TO BE WRONG\n{'=' * 92}")
    a = [r for _, ok, r in conf if ok]
    b = [r for _, ok, r in conf if not ok]
    pooled = statistics.fmean(a + b)
    print(f"  if the effect is REAL      the gate adds "
          f"{len(a) * statistics.fmean(a) - sum(a + b):>+7.1f}R over {DAYS} days")
    print(f"  if the effect is NOISE     the cut group would have averaged the "
          f"pool's {pooled:+.3f},")
    print(f"                             so cutting {len(b)} of them costs "
          f"{-len(b) * pooled:>+7.1f}R")
    print("  the bet is roughly symmetric in R and it is ALERTS ONLY — no")
    print("  capital moves on a label being wrong. that is the whole argument")
    print("  for shipping it before the forward sample exists.")


if __name__ == "__main__":
    main()
