"""Does our structure mark anything, and at which detection period?

Runs research/studies/PREREG_structure_value.md exactly as written. The arms,
the events, the 20-bar primary horizon, the two controls, the seed, the
even/odd held-out split, the 3.0 SE bar and the 0.60 ATR power escape hatch
are all fixed there.

It does NOT compare against the reference indicator. That engine lives in
mickes/PriceAction/4, which is not fetchable here, so the comparison would be
against a reconstruction rather than against their code. The prereg says so.

    python3 research/studies/structure_value.py
"""
from __future__ import annotations

import asyncio
import os
import random
import statistics
import sys

import aiohttp

sys.path.insert(0, ".")
os.environ.setdefault("RIPTIDE_LOOKBACK", "2000")

from riptide.exchange import fetch_candles        # noqa: E402
from research.data import SYMBOLS                 # noqa: E402
from research.ms_struct import engine             # noqa: E402

ARMS = (20, 15, 12, 10, 8, 6, 5)
SHORT = 3
KINDS = ("choch", "bos", "idm")
H_PRIMARY = 20
HORIZONS = (10, 20, 40)
SEED = 20260915
SE_BAR = 3.0
POWER_LIMIT = 0.60          # ATR at the 20-bar horizon


def atr14(cs, n=14):
    tr, out, prev = [], [], None
    for i, c in enumerate(cs):
        t = c.h - c.l if i == 0 else max(c.h - c.l, abs(c.h - cs[i - 1].c),
                                         abs(c.l - cs[i - 1].c))
        tr.append(t)
        if i + 1 < n:
            out.append(None)
            continue
        prev = sum(tr[:n]) / n if prev is None else (prev * (n - 1) + t) / n
        out.append(prev)
    return out


def mean_se(v):
    if len(v) < 2:
        return (statistics.fmean(v) if v else 0.0), 0.0
    return statistics.fmean(v), statistics.stdev(v) / len(v) ** 0.5


def fwd(cs, a, i, d, h):
    """Signed forward move in ATR units. None if the window runs off the end
    or the ATR is not yet defined — never scored as zero."""
    if i + h >= len(cs) or a[i] is None or a[i] <= 0:
        return None
    return d * (cs[i + h].c - cs[i].c) / a[i]


async def main():
    rng = random.Random(SEED)
    # rows[arm][kind] = list of (even_split, {h: real}, {h: c1}, {h: c2})
    rows: dict = {L: {k: [] for k in KINDS} for L in ARMS}
    bars = {L: 0 for L in ARMS}
    got = 0

    async with aiohttp.ClientSession() as sess:
        for n, sym in enumerate(SYMBOLS):
            try:
                cs = await fetch_candles(sess, sym, "Min15")
            except Exception:                                  # noqa: BLE001
                continue
            if len(cs) < 300:
                continue
            got += 1
            a = atr14(cs)
            even = n % 2 == 0
            for L in ARMS:
                bars[L] += len(cs)
                ev, _ = engine(cs, msLen=L, msShortLen=SHORT)
                for k in KINDS:
                    es = [e for e in ev if e["kind"] == k]
                    if not es:
                        continue
                    dirs = [e["dir"] for e in es]
                    for e in es:
                        i, d = e["bar"], e["dir"]
                        real = {h: fwd(cs, a, i, d, h) for h in HORIZONS}
                        if real[H_PRIMARY] is None:
                            continue
                        # C1 sign-randomised: same bar, coin-flip direction
                        fd = rng.choice((1, -1))
                        c1 = {h: fwd(cs, a, i, fd, h) for h in HORIZONS}
                        # C2 random bar, direction from the same marginal mix
                        j = rng.randrange(20, len(cs) - max(HORIZONS) - 1)
                        rd = rng.choice(dirs)
                        c2 = {h: fwd(cs, a, j, rd, h) for h in HORIZONS}
                        rows[L][k].append((even, real, c1, c2))

    print(f"symbols: {got}/{len(SYMBOLS)}   Min15   lookback "
          f"{os.environ['RIPTIDE_LOOKBACK']}   seed {SEED}")
    print(f"primary horizon {H_PRIMARY} bars; 10 and 40 are context and are "
          f"BARRED from the verdict by the prereg.\n")

    def col(v, key, h):
        return [x[key][h] for x in v if x[key][h] is not None]

    worst_se = 0.0
    verdicts = []
    for k in KINDS:
        print(f"══ {k.upper()} "
              f"{'═' * (66 - len(k))}")
        print(f"  {'msLen':>6}{'n':>6}{'per 1k bars':>13}"
              f"{'fwd@20':>10}{'SE':>7}{'SE units':>10}"
              f"{'C1':>8}{'C2':>8}{'held-out':>11}{'':>9}")
        for L in ARMS:
            v = rows[L][k]
            if len(v) < 10:
                print(f"  {L:>6}{len(v):>6}   too few events")
                continue
            r = col(v, 1, H_PRIMARY)
            m, se = mean_se(r)
            units = m / se if se else 0.0
            worst_se = max(worst_se, SE_BAR * se)
            m1, _ = mean_se(col(v, 2, H_PRIMARY))
            m2, _ = mean_se(col(v, 3, H_PRIMARY))
            dec = [x[1][H_PRIMARY] for x in v if x[0]]
            hld = [x[1][H_PRIMARY] for x in v if not x[0]]
            md = statistics.fmean(dec) if len(dec) > 5 else 0.0
            mh = statistics.fmean(hld) if len(hld) > 5 else 0.0
            held = len(hld) > 5 and (mh > 0) == (md > 0) and md != 0
            beats = m > m1 and m > m2
            ok = units >= SE_BAR and beats and held and md > 0
            # The prereg asks for power PER ARM, not once for the run.
            powered = SE_BAR * se <= POWER_LIMIT
            verdicts.append((k, L, ok, powered))
            print(f"  {L:>6}{len(v):>6}{1000*len(v)/bars[L]:>13.1f}"
                  f"{m:>+10.3f}{se:>7.3f}{units:>+10.1f}"
                  f"{m1:>+8.3f}{m2:>+8.3f}"
                  f"{('held' if held else 'flipped'):>11}"
                  f"{('PASSES' if ok else 'fails'):>9}"
                  f"{('' if powered else '  UNDERPOWERED'):>15}")
        # context horizons, explicitly not part of the verdict
        ctx = []
        for L in ARMS:
            v = rows[L][k]
            if len(v) < 10:
                continue
            ctx.append(f"msLen {L}: " + " ".join(
                f"@{h}={mean_se(col(v, 1, h))[0]:+.2f}" for h in HORIZONS))
        if ctx:
            print("  context horizons (NOT part of any verdict):")
            for c in ctx:
                print(f"    {c}")
        print()

    npass = sum(1 for _, _, ok, _ in verdicts if ok)
    weak = [(k, L) for k, L, _, pw in verdicts if not pw]
    print(f"{npass} of {len(verdicts)} cells pass the preregistered bar.\n")
    print(f"POWER, per arm as the prereg specifies. A cell is UNDERPOWERED "
          f"when 3.0 SE")
    print(f"exceeds a mean forward move of {POWER_LIMIT:.2f} ATR — its null "
          f"is a bound, not a verdict.")
    if weak:
        by: dict = {}
        for k, L in weak:
            by.setdefault(k, []).append(L)
        for k, ls in by.items():
            print(f"  {k.upper():<6} underpowered at msLen "
                  f"{', '.join(str(x) for x in ls)}")
    else:
        print("  none — every cell is powered as preregistered.")
    ok_cells = len(verdicts) - len(weak)
    print(f"  {ok_cells} of {len(verdicts)} cells are powered; their nulls "
          f"are verdicts.")
    del worst_se


asyncio.run(main())
