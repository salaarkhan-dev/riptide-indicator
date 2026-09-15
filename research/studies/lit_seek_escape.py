"""P9 — does a bootstrap CHoCH repair the PH_SEEK latch, and at what cost?

Pre-registered in PREREG_lit_seek_escape.md, committed before this ran.

Three arms of `POL.seekCh` over the same candles:

    none    the frozen behaviour — the CHoCH exists only after a BOS breaks
    leg     the first cycle's CHoCH is the leg extreme AGAINST the trend
    raid    ...is the IDM raid extreme, the level Stage A takes as its stop

Judged on LIVENESS, not on returns. The gates are zero latched panels, no
engine self-check violations and no new latches; the selector is how much of
the existing event stream survives on panels that were never broken. Setup R
is printed and is barred from the decision — that bar is in the prereg and it
is the whole reason this is trustworthy.

    PYTHONPATH=. RIPTIDE_DEEP_CACHE=/tmp/deep \\
        python3 research/studies/lit_seek_escape.py
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import statistics                                       # noqa: E402
import time                                             # noqa: E402
from collections import defaultdict                     # noqa: E402

import aiohttp                                          # noqa: E402

from research.deep import load_deep                     # noqa: E402
from research.harness import simulate_market            # noqa: E402
import research.lit_v3 as L                             # noqa: E402
import research.lit_repl as RP                          # noqa: E402
from research.studies.lit_stage_a import trails         # noqa: E402

DAYS = 333
SYMS = RP.DISCOVERY[:30]
TFS = ("Min30", "Min15")
ARMS = ("none", "leg", "raid")
HELD_WANT = 30

WARMUP, HORIZON, MIN_RR = 500, 500, 0.5     # the frozen Stage C scoring shape


def cover(ctx, n):
    return (ctx.events[-1]["bar"] / n) if ctx.events else 0.0


def econ(cs, ctx):
    """Stage-C-style setup R per bet: the frozen V1 rule, T6_PIVOT trail.

    REPORTED ONLY. The prereg bars this from the selection.
    """
    ev = ctx.events
    piv, _s = trails(cs, ev)
    pbs = {1: [], -1: []}
    rs = []
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
        o = simulate_market(cs, i, en, prior, up, target_r=1e9, trail=piv[d],
                            trail_arm_r=MIN_RR, horizon_bars=HORIZON)
        if o is not None and o.filled:
            rs.append(o.r)
    return rs


async def run_arm(sess, arm, syms, econ_too=True):
    """One pass over every symbol-timeframe under one arm."""
    L.POL.seekCh = arm
    out = {}
    for tf in TFS:
        for sym in syms:
            try:
                cs = await load_deep(sess, sym, tf, days=DAYS)
            except Exception:
                continue
            if len(cs) < 2000:
                continue
            m, it, dp, _g = L.engine(cs)
            n = len(cs)
            out[(tf, sym)] = dict(
                n=n,
                mcov=cover(m, n), icov=cover(it, n),
                idm={e["bar"] for e in m.events if e["kind"] == "idm_break"},
                bad={k: dict(x.bad) for k, x in
                     (("main", m), ("int", it), ("deep", dp)) if x.bad},
                r=(econ(cs, m) if econ_too else []),
            )
    L.POL.seekCh = "none"
    return out


def latched(rec):
    return rec["mcov"] < 0.5 <= rec["icov"]


async def main():
    print("=" * 96)
    print("  P9 — THE BOOTSTRAP CHoCH. Does it repair the PH_SEEK latch?")
    print("=" * 96)
    print(f"  arms         {', '.join(ARMS)}   ('none' is frozen and the "
          f"incumbent)")
    print(f"  symbols      {len(SYMS)}   timeframes {', '.join(TFS)}   "
          f"days {DAYS}")
    print("  judged on    liveness. Setup R is printed and is barred from")
    print("               the selection by the pre-registration.")
    print("=" * 96)

    t0 = time.time()
    res = {}
    async with aiohttp.ClientSession() as sess:
        for arm in ARMS:
            res[arm] = await run_arm(sess, arm, SYMS)
            print(f"  {arm:<6} {len(res[arm])} panels "
                  f"({time.time()-t0:.0f}s)")

        base = res["none"]
        sick = {k for k, v in base.items() if latched(v)}
        well = {k for k, v in base.items() if not latched(v)
                and v["icov"] >= 0.5}

        print("\n" + "=" * 96)
        print(f"  G1  LIVENESS — {len(sick)} panels latched under 'none'")
        print("=" * 96)
        print(f"  {'panel':<22}{'arm':<8}{'main cov':>10}{'main idm':>10}"
              f"{'int cov':>9}   still latched?")
        for k in sorted(sick):
            for arm in ARMS:
                v = res[arm].get(k)
                if not v:
                    continue
                print(f"  {(k[1]+' '+k[0]):<22}{arm:<8}{v['mcov']:>10.2f}"
                      f"{len(v['idm']):>10}{v['icov']:>9.2f}   "
                      f"{'YES' if latched(v) else 'no'}")
            print()

        print("=" * 96)
        print("  GATES")
        print("=" * 96)
        print(f"  {'arm':<8}{'G1 latched':>12}{'G2 invariants':>16}"
              f"{'G3 new latches':>17}   verdict")
        gate = {}
        for arm in ARMS:
            nl = sum(1 for k, v in res[arm].items() if latched(v))
            bad = sum(1 for v in res[arm].values() if v["bad"])
            new = sum(1 for k in well if k in res[arm]
                      and latched(res[arm][k]))
            ok = (nl == 0 and bad == 0 and new == 0)
            gate[arm] = ok
            print(f"  {arm:<8}{nl:>12}{bad:>16}{new:>17}   "
                  f"{'PASSES' if ok else 'FAILS'}"
                  f"{'  (incumbent — it IS the defect)' if arm == 'none' else ''}")
        for arm in ARMS:
            for k, v in res[arm].items():
                if v["bad"]:
                    print(f"    {arm} {k}: {v['bad']}")

        print("\n" + "=" * 96)
        print(f"  S1  RETENTION on the {len(well)} panels that were ALREADY "
              f"HEALTHY")
        print("=" * 96)
        print("  A repair confined to the bootstrap cycle should be nearly")
        print("  invisible where nothing was broken.")
        print()
        print(f"  {'arm':<8}{'base idm':>10}{'kept':>8}{'retention':>11}"
              f"{'arm idm':>10}{'new':>7}{'inflation':>11}")
        for arm in ARMS:
            b = k_ = a_ = 0
            for k in well:
                if k not in res[arm]:
                    continue
                bi, ai = base[k]["idm"], res[arm][k]["idm"]
                b += len(bi)
                a_ += len(ai)
                k_ += len(bi & ai)
            print(f"  {arm:<8}{b:>10}{k_:>8}{k_/max(1,b):>11.1%}"
                  f"{a_:>10}{a_-k_:>7}{(a_-k_)/max(1,a_):>11.1%}")

        print("\n" + "=" * 96)
        print("  S2  ECONOMICS — REPORTED, AND BARRED FROM THE SELECTION")
        print("=" * 96)
        print(f"  {'arm':<8}{'bets':>8}{'mean R':>10}{'SE':>8}{'total R':>10}")
        for arm in ARMS:
            rs = [r for v in res[arm].values() for r in v["r"]]
            if len(rs) < 2:
                print(f"  {arm:<8}{len(rs):>8}   too few")
                continue
            se = statistics.stdev(rs) / (len(rs) ** 0.5)
            print(f"  {arm:<8}{len(rs):>8}{statistics.fmean(rs):>10.3f}"
                  f"{se:>8.3f}{sum(rs):>10.1f}")
        print()
        print("  If an arm wins on retention and loses here, it still wins.")

        # ── selection ───────────────────────────────────────────────────────
        cands = [a for a in ARMS if a != "none" and gate[a]]
        ret = {}
        for arm in cands:
            b = k_ = 0
            for k in well:
                if k in res[arm]:
                    b += len(base[k]["idm"])
                    k_ += len(base[k]["idm"] & res[arm][k]["idm"])
            ret[arm] = k_ / max(1, b)
        print("=" * 96)
        print("  SELECTION")
        print("=" * 96)
        if not cands:
            print("  Neither arm cleared the gates. 'none' stands, and the")
            print("  latched panels stay absent from every Main-based sample.")
            return
        win = max(cands, key=lambda a: (ret[a], a == "leg"))
        print(f"  arms clearing every gate: {', '.join(cands)}")
        for a in cands:
            print(f"    {a:<6} retention {ret[a]:.1%}")
        print(f"\n  SELECTED: {win}")

        # ── confirmation on untouched symbols ───────────────────────────────
        print("\n" + "=" * 96)
        print("  CONFIRMATION — G1 on symbols that were never in the sample")
        print("=" * 96)
        try:
            held = await RP.heldout(sess, skip=len(RP.DISCOVERY),
                                    want=HELD_WANT)
        except Exception as e:                       # noqa: BLE001
            print(f"  could not build a held-out universe: {e}")
            return
        held = [s for s in held if s not in SYMS][:HELD_WANT]
        print(f"  {len(held)} symbols, none of them in DISCOVERY\n")
        hb = await run_arm(sess, "none", held, econ_too=False)
        hw = await run_arm(sess, win, held, econ_too=False)
        sick_h = {k for k, v in hb.items() if latched(v)}
        still = {k for k in sick_h if k in hw and latched(hw[k])}
        newl = {k for k, v in hb.items()
                if not latched(v) and v["icov"] >= 0.5
                and k in hw and latched(hw[k])}
        print(f"  panels                       {len(hb)}")
        print(f"  latched under 'none'         {len(sick_h)}"
              f"  {sorted(s + ' ' + t for t, s in sick_h)}")
        print(f"  still latched under '{win}'   {len(still)}")
        print(f"  NEW latches under '{win}'     {len(newl)}")
        print()
        if not still and not newl:
            print(f"  G1 holds on untouched symbols. '{win}' is a repair, not")
            print("  a patch fitted to the four symbols that motivated it.")
        else:
            print("  G1 does NOT hold out of sample. The arm is rejected and")
            print("  'none' stands.")

        print("\n" + "=" * 96)
        print("  WHAT THIS DOES NOT AUTHORISE")
        print("=" * 96)
        print("  The default stays 'none'. Turning this on is the user's call,")
        print("  and doing it in production means LIT_FORWARD_V2 — never a")
        print("  patch to V1, and the two records are never pooled.")
        print("  It does not revisit stages A, B or C: re-running them under a")
        print("  repaired engine is a new experiment needing its own prereg.")


if __name__ == "__main__":
    asyncio.run(main())
