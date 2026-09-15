"""EARLY VS LATE IN A STRUCTURE CYCLE.

Pre-registered in PREREG_cycle_position.md, committed before this ran.

Three tests, and the second decides the outcome:

  A  REPLICATION   does the decile profile reproduce in all four panels?
  B  TAUTOLOGY     re-run on entries whose cycle did NOT flip during the whole
                   trade, so none is "entered just before the reversal". The
                   reading was fixed in advance: significant unrestricted and
                   not significant restricted means the effect is definitional.
  C  USABLE        R against ELAPSED bars since the CHoCH — the only version of
                   this a rule could ever use, because a fraction of a cycle is
                   not knowable until the cycle ends.

    PYTHONPATH=. RIPTIDE_DEEP_CACHE=/tmp/deep \\
        python3 research/studies/cycle_position.py
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import random                                           # noqa: E402
import statistics                                       # noqa: E402
import time                                             # noqa: E402
from collections import defaultdict                     # noqa: E402

import aiohttp                                          # noqa: E402

from research.deep import load_deep                     # noqa: E402
from research.harness import simulate_market            # noqa: E402
import research.ms_struct as MS                         # noqa: E402
import research.lit_repl as RP                          # noqa: E402
from riptide.config import BAR_SECONDS                  # noqa: E402
from research.studies.ms_entry_models import (          # noqa: E402
    DAYS, FEE, HORIZON_HOURS, MS_LEN, MS_SHORT, SYMS, TARGET_R, TFS, stop_for)

PER_CYCLE = 4        # uniform draws per cycle, so long cycles do not dominate
MIN_CYC = 12
MIN_Q = 200          # the coverage bar from the prereg


def agg(v):
    n = len(v)
    if n < 2:
        return None
    m = statistics.fmean(v)
    se = statistics.stdev(v) / (n ** 0.5)
    return dict(n=n, m=m, se=se, z=(m / se) if se else 0.0)


def contrast(a, b):
    """Difference of two independent means, with its z."""
    A, B = agg(a), agg(b)
    if not A or not B:
        return None
    d = A["m"] - B["m"]
    se = (A["se"] ** 2 + B["se"] ** 2) ** 0.5
    return dict(d=d, se=se, z=(d / se) if se else 0.0, na=A["n"], nb=B["n"])


async def main():
    print("=" * 96)
    print("  EARLY VS LATE IN A STRUCTURE CYCLE")
    print("=" * 96)
    print(f"  engine     research.ms_struct (msLen={MS_LEN}, "
          f"msShortLen={MS_SHORT}) — unchanged, not swept")
    print(f"  entry      a bar's close, cycle's own direction; stop = live "
          f"short opposing swing")
    print(f"  exit       {TARGET_R}R or stop, {HORIZON_HOURS}h horizon, "
          f"Riptide fees")
    print(f"  sampling   {PER_CYCLE} uniform draws per cycle, seeded")
    print("=" * 96)

    # rows: (tf, half, fraction, elapsed, r, confined)
    rows = []
    t0 = time.time()
    async with aiohttp.ClientSession() as sess:
        for tf in TFS:
            horizon = max(1, HORIZON_HOURS * 3600 // BAR_SECONDS[tf])
            done = 0
            for sym in SYMS:
                try:
                    cs = await load_deep(sess, sym, tf, days=DAYS)
                except Exception:
                    continue
                if len(cs) < 3000:
                    continue
                n = len(cs)
                cut = n // 2
                _ev, st = MS.engine(cs, MS_LEN, MS_SHORT)
                bars = defaultdict(list)
                for i in range(n):
                    bars[st["cyc"][i]].append(i)
                for cyc, idx in bars.items():
                    if len(idx) < MIN_CYC:
                        continue
                    rng = random.Random(f"cyc|{sym}|{tf}|{cyc}")
                    for _ in range(PER_CYCLE):
                        i = rng.choice(idx[:-1])
                        if i + 1 + horizon > n:
                            continue
                        d = st["os"][i]
                        e = cs[i].c
                        s = stop_for(d, st["sBtmY"][i], st["sTopY"][i], e)
                        if s is None:
                            continue
                        o = simulate_market(cs, i, e, s, d > 0,
                                            target_r=TARGET_R,
                                            horizon_bars=horizon, **FEE)
                        if o is None or not o.filled:
                            continue
                        frac = idx.index(i) / (len(idx) - 1)
                        elapsed = i - idx[0]
                        # CONFINED: the structure did not flip at any point
                        # during the trade's whole horizon, so this entry
                        # cannot be "just before the reversal".
                        conf = st["cyc"][min(n - 1, i + horizon)] == cyc
                        rows.append((tf, "older" if i < cut else "newer",
                                     frac, elapsed, o.r, conf))
                done += 1
            print(f"  {tf}: {done} symbols, {len(rows)} trades "
                  f"({time.time()-t0:.0f}s)")

    def sel(tf=None, half=None, conf=None):
        return [r for r in rows
                if (tf is None or r[0] == tf)
                and (half is None or r[1] == half)
                and (conf is None or r[5] == conf)]

    panels = [(tf, h) for tf in TFS for h in ("older", "newer")]

    # ── A. replication ──────────────────────────────────────────────────────
    print("\n" + "=" * 96)
    print("  A. REPLICATION — mean R by decile of cycle position (FRACTION)")
    print("=" * 96)
    print(f"  {'panel':<16}" + "".join(f"{k/10:>7.1f}" for k in range(10)))
    for tf, h in panels:
        v = sel(tf, h)
        cells = ""
        for k in range(10):
            g = [r[4] for r in v if min(9, int(r[2] * 10)) == k]
            cells += f"{statistics.fmean(g):>7.2f}" if len(g) >= 20 else f"{'—':>7}"
        print(f"  {tf + ' ' + h:<16}{cells}")
    print()
    print(f"  {'panel':<16}{'first 30%':>11}{'last 30%':>11}{'gap':>9}"
          f"{'SE':>8}{'z':>7}")
    for tf, h in panels:
        v = sel(tf, h)
        e = [r[4] for r in v if r[2] < 0.3]
        l_ = [r[4] for r in v if r[2] > 0.7]
        c = contrast(e, l_)
        if c:
            print(f"  {tf + ' ' + h:<16}{statistics.fmean(e):>11.3f}"
                  f"{statistics.fmean(l_):>11.3f}{c['d']:>9.3f}"
                  f"{c['se']:>8.3f}{c['z']:>7.2f}")

    # ── B. the tautology test ───────────────────────────────────────────────
    print("\n" + "=" * 96)
    print("  B. THE TAUTOLOGY TEST — the pre-specified decider")
    print("=" * 96)
    print("  CONFINED = the structure did not flip at any point during the")
    print("  trade, so no entry here sits just before a confirmed reversal.")
    print()
    print(f"  {'sample':<24}{'n':>8}{'first 30%':>11}{'last 30%':>11}"
          f"{'gap':>9}{'SE':>8}{'z':>7}")
    verdict = {}
    for lab, conf in (("all entries", None), ("CONFINED only", True),
                      ("flipped during trade", False)):
        v = sel(conf=conf)
        e = [r[4] for r in v if r[2] < 0.3]
        l_ = [r[4] for r in v if r[2] > 0.7]
        c = contrast(e, l_)
        if not c:
            continue
        verdict[lab] = c
        print(f"  {lab:<24}{len(v):>8}{statistics.fmean(e):>11.3f}"
              f"{statistics.fmean(l_):>11.3f}{c['d']:>9.3f}{c['se']:>8.3f}"
              f"{c['z']:>7.2f}")
    print()
    a_ = verdict.get("all entries")
    b_ = verdict.get("CONFINED only")
    if a_ and b_:
        sig_a = abs(a_["z"]) >= 2.0
        sig_b = abs(b_["z"]) >= 2.0
        print(f"  unrestricted significant: {sig_a}   "
              f"confined significant: {sig_b}")
        if sig_a and not sig_b:
            print("  -> DEFINITIONAL. The pre-specified reading: the effect is")
            print("     an artefact of the cycle definition, not a property of")
            print("     structure. There is no reformulation that rescues it.")
        elif sig_a and sig_b:
            print("  -> SURVIVES confinement. Not merely proximity to the flip.")
        else:
            print("  -> the unrestricted effect is not significant here, so")
            print("     there is nothing for this test to strip away.")

    # ── C. the usable version ───────────────────────────────────────────────
    print("\n" + "=" * 96)
    print("  C. THE USABLE VERSION — R against ELAPSED bars since the CHoCH")
    print("=" * 96)
    allel = sorted(r[3] for r in rows)
    qs = [allel[int(p * (len(allel) - 1))] for p in (0.25, 0.5, 0.75)]
    print(f"  elapsed quartile cuts: {qs[0]}, {qs[1]}, {qs[2]} bars")
    print()
    print(f"  {'panel':<16}{'Q1':>9}{'Q2':>9}{'Q3':>9}{'Q4':>9}"
          f"{'below-above':>13}{'SE':>8}{'z':>7}{'  cov':>7}")
    cres = {}
    for tf, h in panels:
        v = sel(tf, h)
        cells = ""
        ok = True
        for k in range(4):
            lo = qs[k - 1] if k else -1
            hi = qs[k] if k < 3 else 10 ** 9
            g = [r[4] for r in v if lo < r[3] <= hi]
            if len(g) < MIN_Q:
                ok = False
            cells += f"{statistics.fmean(g):>9.3f}" if len(g) >= 20 else f"{'—':>9}"
        below = [r[4] for r in v if r[3] <= qs[1]]
        above = [r[4] for r in v if r[3] > qs[1]]
        c = contrast(below, above)
        cres[(tf, h)] = c
        if c:
            print(f"  {tf + ' ' + h:<16}{cells}{c['d']:>13.3f}{c['se']:>8.3f}"
                  f"{c['z']:>7.2f}{('yes' if ok else 'NO'):>7}")

    pooled = contrast([r[4] for r in sel(half="newer") if r[3] <= qs[1]],
                      [r[4] for r in sel(half="newer") if r[3] > qs[1]])
    ds = [c["d"] for c in cres.values() if c]
    b2 = bool(ds) and (all(x > 0 for x in ds) or all(x < 0 for x in ds))
    b3 = bool(pooled and abs(pooled["z"]) >= 2.0)
    print()
    print(f"  sign stable across four panels: {b2}")
    print(f"  pooled newer half: d={pooled['d']:.3f} z={pooled['z']:.2f} "
          f"-> bar 3 {'met' if b3 else 'NOT met'}" if pooled else "  pooled: —")

    print("\n" + "=" * 96)
    print("  READ")
    print("=" * 96)
    print("  B decides. A large FRACTION effect that vanishes once trades are")
    print("  confined inside their cycle is the cycle definition talking: the")
    print("  last bars of a bull cycle ARE the bars before a break of its low.")
    print()
    print("  C is the only version a rule could use, because the fraction of a")
    print("  cycle a bar sits at is not knowable until the cycle has ended.")
    print("  Note its bias runs the other way: a bar at a high ELAPSED exists")
    print("  only in cycles that lasted, and those are the persistent ones.")


if __name__ == "__main__":
    asyncio.run(main())
