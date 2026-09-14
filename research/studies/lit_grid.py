"""EVERY SETTING COMBINATION — and then the only question that matters.

The claim under test is one a lot of people arrive at honestly: "different
settings work on each timeframe, and on each pair." This runs the grid rather
than arguing about it.

But a grid ALWAYS produces a winner. With 162 combinations, the best cell is
the best of 162 draws, and most of what makes it best is luck. So picking the
winner is not the experiment — the experiment is whether that winner still
works on data it was not picked on.

    IN-SAMPLE   everything before the last 120 days. The grid searches here
                and picks a champion per timeframe, and per (symbol,timeframe).
    OUT-OF-SAMPLE  the last 120 days. The champions are then scored here,
                against the frozen default config scored on the same bars.

If per-pair tuning is real, the champions beat the default out of sample. If
it is curve-fitting, they do not, and the gap between their in-sample and
out-of-sample numbers is the size of the self-deception.

This is a MEASUREMENT, not a proposal. Nothing here can change LIT_FORWARD_V1,
which is frozen by PREREG_lit_forward_v1.md; a settings change would be V2 and
would need its own pre-registration.

    PYTHONPATH=. RIPTIDE_DEEP_CACHE=/tmp/deep \\
        python3 research/studies/lit_grid.py > lit_grid_out.txt
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import itertools                                        # noqa: E402
import statistics                                       # noqa: E402
import sys                                              # noqa: E402
import time                                             # noqa: E402
from collections import defaultdict                     # noqa: E402

import aiohttp                                          # noqa: E402

from research.deep import load_deep                     # noqa: E402
from research.harness import simulate_market            # noqa: E402
import research.lit_v3 as L                             # noqa: E402
import research.lit_repl as RP                          # noqa: E402
from research.studies.lit_stage_a import trails         # noqa: E402

DAYS = 333
OOS_DAYS = 120
WARMUP = 500
HORIZON = 500
MIN_RR = 0.5
SYMS = RP.DISCOVERY[:10]
TFS = ("Min15", "Min30")

MODES = {"Shadow": L.BRK_SHADOW, "Body": L.BRK_BODY, "Sweep": L.BRK_SWEEP}
RESEED = ("resolver", "pivot")

# The frozen configuration, for reference on every table.
DEFAULT = ("Body", "Shadow", "Sweep", "Sweep", "resolver")


def combos():
    for pb, idm, bos, ch in itertools.product(MODES, repeat=4):
        for rs in RESEED:
            yield (pb, idm, bos, ch, rs)


def apply(c):
    L.M_PB, L.M_IDM, L.M_BOS, L.M_CH = (MODES[c[0]], MODES[c[1]],
                                        MODES[c[2]], MODES[c[3]])
    L.POL.reseed = c[4]


def setups(cs, cut):
    """Frozen V1 setup rule, unchanged, split by window."""
    main, _i, _d, _g = L.engine(cs)
    ev = main.events
    piv, _s = trails(cs, ev)
    pbs = {1: [], -1: []}
    out = {"is": [], "oos": []}
    for e in ev:
        d = 1 if e["dir"] > 0 else -1
        if e["kind"] == "pb":
            pbs[d].append(e["px"])
            continue
        if e["kind"] != "idm_break":
            continue
        i, up, en, bos = e["bar"], d > 0, e["entry"], e["bos"]
        prior = pbs[d][-2] if len(pbs[d]) > 1 else None
        pbs[d] = []
        if i < WARMUP or bos is None or en is None or en <= 0:
            continue
        if (bos <= en) if up else (bos >= en):
            continue
        if prior is None or ((prior >= en) if up else (prior <= en)):
            continue
        if abs(en - prior) <= 0:
            continue
        key = "oos" if cs[i].t >= cut else "is"
        out[key].append((i, up, en, prior, bos, piv[d], cs[i].t))
    return out


def score(cs, rows):
    """T6_PIVOT and the frozen control, on the same setups. Returns bets."""
    by = defaultdict(list)
    for i, up, en, stop, bos, trail, ts in rows:
        risk = abs(en - stop)
        t6 = simulate_market(cs, i, en, stop, up, target_r=1e9, trail=trail,
                             trail_arm_r=MIN_RR, horizon_bars=HORIZON)
        ct = simulate_market(cs, i, en, stop, up, target_px=bos,
                             target_r=abs(bos - en) / risk,
                             horizon_bars=HORIZON)
        if t6 is None or ct is None or not t6.filled or not ct.filled:
            continue
        by[ts].append((t6.r, ct.r, t6.r - ct.r))
    return [tuple(statistics.fmean(x[k] for x in v) for k in (0, 1, 2))
            for v in by.values()]


def agg(bets):
    if not bets:
        return None
    t6 = [b[0] for b in bets]
    dl = [b[2] for b in bets]
    n = len(bets)
    se = statistics.stdev(dl) / (n ** 0.5) if n > 1 else 0.0
    return dict(n=n, t6=statistics.fmean(t6), d=statistics.fmean(dl), se=se,
                z=(statistics.fmean(dl) / se) if se else 0.0)


async def main():
    cut = time.time() - OOS_DAYS * 86400
    print("=" * 96)
    print("LIT — EVERY SETTING COMBINATION, AND WHETHER THE WINNER SURVIVES")
    print("=" * 96)
    print(f"grid      pullback x IDM x BOS x CHoCH modes (3^4) x reseed (2)"
          f" = {len(list(combos()))} combinations")
    print(f"symbols   {len(SYMS)}   timeframes {', '.join(TFS)}")
    print(f"split     IN-SAMPLE = everything before the last {OOS_DAYS} days;"
          f" OUT-OF-SAMPLE = the last {OOS_DAYS}")
    print("entry     the frozen V1 rule, UNCHANGED. Only structure settings")
    print("          vary - entry, stop, Active Price and exits are fixed.")
    print(f"default   {DEFAULT}  (what LIT_FORWARD_V1 records)")
    print("=" * 96)

    data = {}
    async with aiohttp.ClientSession() as sess:
        for tf in TFS:
            for sym in SYMS:
                try:
                    cs = await load_deep(sess, sym, tf, days=DAYS)
                except Exception:
                    continue
                if len(cs) >= 2000:
                    data[(tf, sym)] = cs
    print(f"\nloaded {len(data)} symbol-timeframes\n")

    # results[(combo, tf, sym)] = {"is": agg, "oos": agg}
    res = {}
    allc = list(combos())
    t0 = time.time()
    for k, c in enumerate(allc):
        apply(c)
        for (tf, sym), cs in data.items():
            sp = setups(cs, cut)
            res[(c, tf, sym)] = {w: agg(score(cs, sp[w])) for w in
                                 ("is", "oos")}
        if (k + 1) % 20 == 0:
            el = time.time() - t0
            print(f"  {k+1}/{len(allc)} combos  {el:.0f}s elapsed, "
                  f"~{el/(k+1)*(len(allc)-k-1):.0f}s left", flush=True)
    apply(DEFAULT)

    def pool(c, tf, w, syms=None):
        rows = [res[(c, tf, s)][w] for s in (syms or SYMS)
                if (c, tf, s) in res and res[(c, tf, s)][w]]
        if not rows:
            return None
        n = sum(r["n"] for r in rows)
        d = sum(r["d"] * r["n"] for r in rows) / n
        t6 = sum(r["t6"] * r["n"] for r in rows) / n
        return dict(n=n, d=d, t6=t6)

    print("\n" + "=" * 96)
    print("  1. BEST COMBINATION PER TIMEFRAME, chosen IN-SAMPLE")
    print("=" * 96)
    print(f"  {'tf':<7}{'combination':<40}{'IS n':>7}{'IS Δ':>8}"
          f"{'OOS n':>7}{'OOS Δ':>8}{'decay':>8}")
    for tf in TFS:
        scored = [(pool(c, tf, "is"), c) for c in allc]
        scored = [(a, c) for a, c in scored if a and a["n"] >= 30]
        if not scored:
            continue
        best = max(scored, key=lambda x: x[0]["d"])
        for lab, c in (("best", best[1]), ("default", DEFAULT)):
            i_, o_ = pool(c, tf, "is"), pool(c, tf, "oos")
            if not i_ or not o_:
                continue
            print(f"  {tf if lab=='best' else '':<7}"
                  f"{lab + ': ' + '/'.join(c):<40}{i_['n']:>7}{i_['d']:>8.3f}"
                  f"{o_['n']:>7}{o_['d']:>8.3f}{o_['d']-i_['d']:>8.3f}")

    print("\n" + "=" * 96)
    print("  2. BEST COMBINATION PER (SYMBOL, TIMEFRAME) — the actual claim")
    print("  Each pair gets its own winner, chosen in-sample. Then all of them")
    print("  are scored out-of-sample and compared with the single frozen")
    print("  default applied to every pair.")
    print("=" * 96)
    for tf in TFS:
        tunedI = tunedO = defI = defO = 0.0
        nI = nO = ndI = ndO = 0
        picks = 0
        for sym in SYMS:
            cand = [(res[(c, tf, sym)]["is"], c) for c in allc
                    if (c, tf, sym) in res and res[(c, tf, sym)]["is"]]
            cand = [(a, c) for a, c in cand if a["n"] >= 8]
            if not cand:
                continue
            a, c = max(cand, key=lambda x: x[0]["d"])
            picks += 1
            tunedI += a["d"] * a["n"]
            nI += a["n"]
            o = res[(c, tf, sym)]["oos"]
            if o:
                tunedO += o["d"] * o["n"]
                nO += o["n"]
            di = res[(DEFAULT, tf, sym)]["is"]
            do = res[(DEFAULT, tf, sym)]["oos"]
            if di:
                defI += di["d"] * di["n"]
                ndI += di["n"]
            if do:
                defO += do["d"] * do["n"]
                ndO += do["n"]
        if not nO or not ndO:
            continue
        print(f"\n  {tf}  ({picks} pairs each given their own best settings)")
        print(f"    {'':<22}{'IS Δ/bet':>10}{'OOS Δ/bet':>12}{'decay':>10}")
        print(f"    {'per-pair tuned':<22}{tunedI/max(1,nI):>10.3f}"
              f"{tunedO/nO:>12.3f}{tunedO/nO - tunedI/max(1,nI):>10.3f}")
        print(f"    {'one frozen default':<22}{defI/max(1,ndI):>10.3f}"
              f"{defO/ndO:>12.3f}{defO/ndO - defI/max(1,ndI):>10.3f}")
        print(f"    {'tuning advantage OOS':<22}{'':>10}"
              f"{tunedO/nO - defO/ndO:>12.3f}")

    print("\n" + "=" * 96)
    print("  READ")
    print("=" * 96)
    print("  DECAY is the number to look at. A large positive in-sample delta")
    print("  that collapses out-of-sample is the signature of picking the best")
    print("  of many draws, and it is what a grid produces from pure noise.")
    print()
    print("  'tuning advantage OOS' is the whole claim in one number: how much")
    print("  better per-pair tuning did on data it was NOT picked on. If it is")
    print("  at or below zero, the settings that looked better were fitted to")
    print("  the window they were chosen from.")
    print()
    print("  Nothing here can change LIT_FORWARD_V1. It is frozen by")
    print("  PREREG_lit_forward_v1.md; a settings change would be V2 and would")
    print("  need its own pre-registration and its own out-of-sample test.")


if __name__ == "__main__":
    asyncio.run(main())
