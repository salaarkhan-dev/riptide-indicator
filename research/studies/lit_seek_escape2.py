"""P9 v2 — judged against the mechanism it repairs.

Pre-registered in PREREG_lit_seek_escape_v2.md, committed before this ran.
`research/studies/lit_seek_escape.py` is left untouched so v1's rejection stays
reproducible.

One change from v1, and it is the whole point. Unhealthy panels are classified
by the engine's FINAL STATE before being counted:

    SEEK_LATCH   phase == PH_SEEK and not ch.on   the defect P9 repairs
    LOCK_STALL   phase == PH_LOCK                 both boundaries unreachable
    OTHER        anything else                    unclassified, still reported

G1 is then scored against SEEK_LATCH alone — an arm may only be judged on the
defect it set out to repair. G3 stays scored against ANY unhealthy panel — an
arm may never make anything worse by any route. That asymmetry is deliberate.

The held-out universe grows from 30 to 80 requested symbols to pay for taking
a second look at the same data.

    PYTHONPATH=. RIPTIDE_DEEP_CACHE=/tmp/deep \\
        python3 research/studies/lit_seek_escape2.py
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import statistics                                       # noqa: E402
import time                                             # noqa: E402
from collections import Counter                         # noqa: E402

import aiohttp                                          # noqa: E402

from research.deep import load_deep                     # noqa: E402
import research.lit_v3 as L                             # noqa: E402
import research.lit_repl as RP                          # noqa: E402
from research.studies.lit_seek_escape import (          # noqa: E402
    ARMS, DAYS, SYMS, TFS, cover, econ)

HELD_WANT = 80          # v1 asked for 30; the enlargement is the price of a
                        # second look, and it is fixed by the prereg


def classify(rec):
    """The taxonomy, named in the prereg before anything was counted."""
    if not (rec["mcov"] < 0.5 <= rec["icov"]):
        return "healthy"
    if rec["phase"] == L.PH_SEEK and not rec["ch_on"]:
        return "SEEK_LATCH"
    if rec["phase"] == L.PH_LOCK:
        return "LOCK_STALL"
    return "OTHER"


async def run_arm(sess, arm, syms, econ_too=True):
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
            rec = dict(
                n=n, mcov=cover(m, n), icov=cover(it, n),
                phase=m.phase, ch_on=m.ch.on, dir=m.dir,
                ch_px=m.ch.px, bos_px=m.bos.px, phaseBar=m.phaseBar,
                idm={e["bar"] for e in m.events if e["kind"] == "idm_break"},
                bad={k: dict(x.bad) for k, x in
                     (("main", m), ("int", it), ("deep", dp)) if x.bad},
                r=(econ(cs, m) if econ_too else []),
            )
            rec["type"] = classify(rec)
            out[(tf, sym)] = rec
    L.POL.seekCh = "none"
    return out


def tally(res):
    return Counter(v["type"] for v in res.values())


async def main():
    print("=" * 98)
    print("  P9 v2 — THE BOOTSTRAP CHoCH, JUDGED AGAINST ITS OWN MECHANISM")
    print("=" * 98)
    print(f"  arms       {', '.join(ARMS)}   ('none' is frozen and the "
          f"incumbent)")
    print(f"  in-sample  {len(SYMS)} symbols x {len(TFS)} timeframes, "
          f"{DAYS} days")
    print(f"  held out   up to {HELD_WANT} symbols, none in DISCOVERY "
          f"(v1 used 30)")
    print("  G1 scores SEEK_LATCH only; G3 scores any unhealthy panel.")
    print("  Setup R is printed and barred from the selection by the prereg.")
    print("=" * 98)

    t0 = time.time()
    res = {}
    async with aiohttp.ClientSession() as sess:
        for arm in ARMS:
            res[arm] = await run_arm(sess, arm, SYMS)
            t = tally(res[arm])
            print(f"  {arm:<6} {len(res[arm])} panels   "
                  f"SEEK_LATCH {t['SEEK_LATCH']}  LOCK_STALL "
                  f"{t['LOCK_STALL']}  OTHER {t['OTHER']}   "
                  f"({time.time()-t0:.0f}s)")

        base = res["none"]
        sick = {k for k, v in base.items() if v["type"] != "healthy"}
        well = {k for k, v in base.items() if v["type"] == "healthy"
                and v["icov"] >= 0.5}

        print("\n" + "=" * 98)
        print(f"  EVERY UNHEALTHY PANEL UNDER 'none' ({len(sick)}), "
              f"BY MECHANISM")
        print("=" * 98)
        print(f"  {'panel':<22}{'type':<12}{'arm':<7}{'main cov':>10}"
              f"{'idm':>6}{'int cov':>9}  type under arm")
        for k in sorted(sick, key=lambda x: (base[x]['type'], x[1])):
            for arm in ARMS:
                v = res[arm].get(k)
                if not v:
                    continue
                print(f"  {(k[1]+' '+k[0]):<22}"
                      f"{(base[k]['type'] if arm == 'none' else ''):<12}"
                      f"{arm:<7}{v['mcov']:>10.2f}{len(v['idm']):>6}"
                      f"{v['icov']:>9.2f}  {v['type']}")
            print()

        print("=" * 98)
        print("  GATES — IN SAMPLE")
        print("=" * 98)
        print(f"  {'arm':<8}{'G1 SEEK_LATCH':>15}{'G2 invariants':>15}"
              f"{'G3 new unhealthy':>19}   verdict")
        gate = {}
        for arm in ARMS:
            t = tally(res[arm])
            bad = sum(1 for v in res[arm].values() if v["bad"])
            new = sum(1 for k in well if k in res[arm]
                      and res[arm][k]["type"] != "healthy")
            ok = (t["SEEK_LATCH"] == 0 and bad == 0 and new == 0)
            gate[arm] = ok
            note = "  (incumbent — it IS the defect)" if arm == "none" else ""
            print(f"  {arm:<8}{t['SEEK_LATCH']:>15}{bad:>15}{new:>19}   "
                  f"{'PASSES' if ok else 'FAILS'}{note}")

        print("\n" + "=" * 98)
        print(f"  S1  RETENTION on the {len(well)} panels already healthy")
        print("=" * 98)
        print(f"  {'arm':<8}{'base idm':>10}{'kept':>8}{'retention':>11}"
              f"{'arm idm':>10}{'new':>7}{'inflation':>11}")
        ret = {}
        for arm in ARMS:
            b = k_ = a_ = 0
            for k in well:
                if k not in res[arm]:
                    continue
                bi, ai = base[k]["idm"], res[arm][k]["idm"]
                b += len(bi)
                a_ += len(ai)
                k_ += len(bi & ai)
            ret[arm] = k_ / max(1, b)
            print(f"  {arm:<8}{b:>10}{k_:>8}{ret[arm]:>11.1%}"
                  f"{a_:>10}{a_-k_:>7}{(a_-k_)/max(1,a_):>11.1%}")

        print("\n" + "=" * 98)
        print("  S2  ECONOMICS — REPORTED, BARRED FROM THE SELECTION")
        print("=" * 98)
        print(f"  {'arm':<8}{'bets':>8}{'mean R':>10}{'SE':>8}{'total R':>10}")
        for arm in ARMS:
            rs = [r for v in res[arm].values() for r in v["r"]]
            if len(rs) < 2:
                continue
            se = statistics.stdev(rs) / (len(rs) ** 0.5)
            print(f"  {arm:<8}{len(rs):>8}{statistics.fmean(rs):>10.3f}"
                  f"{se:>8.3f}{sum(rs):>10.1f}")

        cands = [a for a in ARMS if a != "none" and gate[a]]
        print("\n" + "=" * 98)
        print("  SELECTION")
        print("=" * 98)
        if not cands:
            print("  No arm cleared the in-sample gates. 'none' stands.")
            return
        win = max(cands, key=lambda a: (ret[a], a == "leg"))
        for a in cands:
            print(f"    {a:<6} retention {ret[a]:.1%}")
        print(f"\n  SELECTED for confirmation: {win}")

        # ── confirmation on a LARGER untouched universe ─────────────────────
        print("\n" + "=" * 98)
        print("  CONFIRMATION — the enlarged held-out universe")
        print("=" * 98)
        try:
            held = await RP.heldout(sess, skip=len(RP.DISCOVERY),
                                    want=HELD_WANT)
        except Exception as e:                       # noqa: BLE001
            print(f"  could not build a held-out universe: {e}")
            return
        held = [s for s in held if s not in SYMS][:HELD_WANT]
        print(f"  {len(held)} symbols requested, none in DISCOVERY\n")
        hb = await run_arm(sess, "none", held, econ_too=False)
        hw = await run_arm(sess, win, held, econ_too=False)
        tb, tw = tally(hb), tally(hw)
        print(f"  panels                     {len(hb)}")
        print(f"  {'':<27}{'none':>10}{win:>10}")
        for ty in ("SEEK_LATCH", "LOCK_STALL", "OTHER", "healthy"):
            print(f"  {ty:<27}{tb[ty]:>10}{tw[ty]:>10}")
        print()
        seek_left = [k for k, v in hw.items() if v["type"] == "SEEK_LATCH"]
        newly = [k for k, v in hb.items() if v["type"] == "healthy"
                 and v["icov"] >= 0.5 and k in hw
                 and hw[k]["type"] != "healthy"]
        bad_h = sum(1 for v in hw.values() if v["bad"])
        print(f"  G1  SEEK_LATCH remaining under '{win}'   "
              f"{len(seek_left)}   "
              f"{sorted(s + ' ' + t for t, s in seek_left)}")
        print(f"  G2  invariant violations                {bad_h}")
        print(f"  G3  panels made unhealthy by '{win}'     {len(newly)}   "
              f"{sorted(s + ' ' + t for t, s in newly)}")
        ok = (not seek_left) and bad_h == 0 and not newly
        print()
        print(f"  CONFIRMATION: {'HOLDS' if ok else 'FAILS'}")

        print("\n" + "=" * 98)
        print("  THE PH_LOCK STALL — characterised, NOT fixed")
        print("=" * 98)
        stalls = [(k, v) for k, v in list(hb.items()) + list(base.items())
                  if v["type"] == "LOCK_STALL"]
        tot = len(hb) + len(base)
        print(f"  {len(stalls)} of {tot} panels across both samples "
              f"({100*len(stalls)/max(1,tot):.1f}%)")
        for k, v in stalls:
            print(f"    {k[1]} {k[0]}: dir={v['dir']} stuck "
                  f"{v['n']-v['phaseBar']} bars, bos={v['bos_px']} "
                  f"ch={v['ch_px']}")
        print()
        print("  No policy is proposed for it here, by the prereg. Fixing a")
        print("  second defect found while validating the first, inside the")
        print("  same experiment, is how a measurement becomes a redesign.")

        print("\n" + "=" * 98)
        print(f"  VERDICT: '{win}' "
              f"{'PASSES' if ok else 'is REJECTED, and there is no v3'}")
        print("=" * 98)
        if ok:
            print("  It earns the right to be PROPOSED. The default stays")
            print("  'none'; switching it on is the user's call, and doing so")
            print("  in production means LIT_FORWARD_V2 — never a patch to V1,")
            print("  and the two records are never pooled.")
        else:
            print("  'none' stands permanently. The latched panels remain")
            print("  absent from every Main-based sample, and that limitation")
            print("  is stated wherever Main is used.")


if __name__ == "__main__":
    asyncio.run(main())
