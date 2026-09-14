"""LIT STAGE B — the stop definition.

Runs the experiment frozen in PREREG_lit_stage_b.md. Read that first. Nothing
here may be changed to improve a result and no threshold in it moves.

Stage A failed on criterion 2: the raid-extreme stop is the break bar's own
wick, median 0.42% of price, and 99% of losses exceeded the planned 1R. The
failure was located in the stop, not demonstrated in the entry event — among
setups reaching Active Price, median MFE was 1.91R.

Stage B therefore holds the entry, the exits, the scorer, the fees and the
unit of evidence fixed, and varies ONE thing: where the stop goes.

PRIMARY  PRIOR_PB — the second-most-recent confirmed pullback pivot in the
         trade direction within the current cycle. Selected on GEOMETRY before
         any return was computed; see PREREG §2.
CONTROL  RAID — Stage A's stop, reproduced for a direct comparison.
ALSO     IDM_PIVOT (requested, and shown in PREREG §2 to be NARROWER than RAID
         and so unable to fix anything), LEG, CHOCH.

    PYTHONPATH=. RIPTIDE_DEEP_CACHE=/tmp/deep \\
        python3 research/studies/lit_stage_b.py > lit_stage_b_out.txt
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import statistics                                       # noqa: E402
import subprocess                                       # noqa: E402
import time                                             # noqa: E402
from collections import defaultdict                     # noqa: E402

import aiohttp                                          # noqa: E402

from research.deep import load_deep                     # noqa: E402
from research.harness import simulate_market, FEE_MAKER, FEE_TAKER  # noqa: E402,E501
import research.lit_v3 as L                             # noqa: E402
import research.lit_repl as RP                          # noqa: E402
from research.studies.lit_stage_a import (               # noqa: E402
    Row, trails, first_touch, bets, paired, drawdown, q,
    POLICIES, CONTROLS, PAIRED_BASE, HORIZON, MIN_RR)

STOPS = ("PRIOR_PB", "RAID", "IDM_PIVOT", "LEG", "CHOCH")
PRIMARY = "PRIOR_PB"
FEE_RT = (FEE_MAKER + FEE_TAKER) / 100.0      # round trip, as a fraction


def candidates(ev, idm, pbs, d):
    """The five registered stop levels for one IDM break. PREREG §3.

    `idm` is the live IDM level, `pbs` the confirmed pullback pivots of the
    trade direction inside the current cycle — the last of which IS the IDM,
    so PRIOR_PB is the one behind it.
    """
    prior = pbs[-2] if len(pbs) > 1 else None
    leg = (min(pbs) if d > 0 else max(pbs)) if pbs else None
    return {"RAID": ev["stop"], "IDM_PIVOT": idm, "PRIOR_PB": prior,
            "LEG": leg, "CHOCH": ev.get("choch")}


def score(cs, piv, stc, ev, idm, pbs, sym, tf, window, symset, skips):
    """One IDM break, under every (stop policy x exit policy) pair."""
    i, up = ev["bar"], ev["dir"] > 0
    entry, bos = ev["entry"], ev["bos"]
    if bos is None or entry <= 0:
        return []
    if (bos <= entry) if up else (bos >= entry):
        return []                 # with-trend only
    d = 1 if up else -1

    bosBar = first_touch(cs, i, bos, up)
    chBar = first_touch(cs, i, ev.get("choch"), not up)
    bbc = (None if (bosBar is None and chBar is None)
           else bosBar is not None and (chBar is None or bosBar <= chBar))

    out = []
    for sp, lvl in candidates(ev, idm, pbs, d).items():
        # PREREG §3: a missing level, or one on the wrong side of the entry,
        # is a SKIP for that policy — never silently replaced by another.
        if lvl is None or ((lvl >= entry) if up else (lvl <= entry)):
            skips[sp] += 1
            continue
        risk = abs(entry - lvl)
        if risk <= 0:
            skips[sp] += 1
            continue
        active = entry + d * (MIN_RR * risk + entry * FEE_RT)
        for pol in POLICIES:
            kw = dict(horizon_bars=HORIZON)
            if pol == "FIXED_1R":
                kw["target_r"] = 1.0
            elif pol == "FIXED_2R":
                kw["target_r"] = 2.0
            elif pol == "BOS_TARGET":
                kw["target_px"] = bos
                kw["target_r"] = abs(bos - entry) / risk
            else:
                kw["target_r"] = 1e9
                kw["trail"] = piv[d] if pol == "T6_PIVOT" else stc[d]
                kw["trail_arm_r"] = MIN_RR
            o = simulate_market(cs, i, entry, lvl, up, **kw)
            if o is None or not o.filled:
                continue
            r = Row(
                setup_id=f"{sym}:{tf}:{i}", symbol=sym, timeframe=tf,
                direction=d, signal_time=cs[i].t, entry=entry,
                initial_stop=lvl, raid_extreme=ev["stop"],
                stop_distance_price=risk,
                stop_distance_pct=100.0 * risk / entry,
                bos_price=bos, choch_price=ev.get("choch"),
                bos_distance_r=abs(bos - entry) / risk,
                active_price=active, active_reached=o.mfe >= MIN_RR,
                bos_before_choch=bbc, mfe_r=o.mfe, mae_r=o.mae,
                exit_policy=pol, exit_price=entry + d * o.r * risk,
                exit_reason=o.exit,
                bars_held=(o.exit_bar - i) if o.exit_bar else 0,
                realized_r=o.r, planned_loss_r=-1.0,
                realized_loss_r=(o.r if o.r < 0 else 0.0),
                window=window, symset=symset)
            r.stop_policy = sp
            out.append(r)
    return out


def block(name, rows):
    b = bets(rows)
    if len(b) < 20:
        print(f"  {name:<14}{len(rows):>7}{len(b):>7}   too few bets to read")
        return None
    m = statistics.fmean(b)
    se = statistics.stdev(b) / (len(b) ** 0.5) if len(b) > 1 else 0.0
    wins = [r.realized_r for r in rows if r.realized_r > 0]
    loss = [r.realized_r for r in rows if r.realized_r <= 0]
    pf = (sum(wins) / abs(sum(loss))) if loss and sum(loss) else float("inf")
    tot, mdd = drawdown(b)
    print(f"  {name:<14}{len(rows):>7}{len(b):>7}{m:>9.3f}{se:>7.3f}"
          f"{(m / se if se else 0):>7.1f}"
          f"{100 * sum(1 for x in b if x > 0) / len(b):>7.1f}%"
          f"{pf:>7.2f}{tot:>9.1f}{mdd:>8.1f}"
          f"{(tot / mdd if mdd else float('inf')):>8.2f}")
    return dict(m=m, se=se, t=(m / se if se else 0.0), n=len(b))


HDR = (f"\n  {'cell':<14}{'trades':>7}{'bets':>7}{'R/bet':>9}{'SE':>7}"
       f"{'t':>7}{'win':>8}{'PF':>7}{'totR':>9}{'maxDD':>8}{'recov':>8}")


async def main():
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                            capture_output=True, text=True).stdout.strip()
    cut = time.time() - RP.RECENT_DAYS * 86400

    print("=" * 104)
    print("LIT STAGE B — THE STOP DEFINITION")
    print("=" * 104)
    print("HYPOTHESIS  H0: with a structurally-defined stop the naked LIT")
    print("            continuation event still has no edge net of costs.")
    print("            H1: it does, and Stage A's failure was the stop.")
    print("PRIMARY     PRIOR_PB — 2nd-most-recent confirmed pullback pivot of")
    print("            the trade direction in the current cycle. Selected on")
    print("            GEOMETRY before any return existed (PREREG §2).")
    print("CONTROL     RAID — Stage A's stop, for direct comparison.")
    print("SECONDARY   IDM_PIVOT (requested; PREREG §2 shows it is NARROWER")
    print("            than RAID), LEG, CHOCH. Descriptive only.")
    print("INHERITED   population, entry, exits, scorer, fees, BET unit — all")
    print("            unchanged from PREREG_lit_stage_a.md.")
    print("CRITERION   PASS needs a control exit with R/bet>0 AND t>=2.5,")
    print("            AND P(realized loss > 1.5R) <= 10%.")
    print(f"DATE        {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}")
    print(f"COMMIT      {commit}")
    print("PREREG      PREREG_lit_stage_b.md (committed at becc0bf, before)")
    print("=" * 104)

    rows, skips = [], defaultdict(int)
    async with aiohttp.ClientSession() as sess:
        held = (await RP.heldout(sess, skip=len(RP.DISCOVERY), want=70))[:30]
        for tf in RP.TFS:
            for symset, syms in (("discovery", RP.DISCOVERY),
                                 ("held-out", held)):
                for sym in syms:
                    try:
                        cs = await load_deep(sess, sym, tf, days=RP.DAYS)
                    except Exception:
                        continue
                    if len(cs) < 2000:
                        continue
                    m, _i, _d, _g = L.engine(cs)
                    piv, stc = trails(cs, m.events)
                    idm = {1: None, -1: None}
                    pbs = {1: [], -1: []}
                    for e in m.events:
                        dd = 1 if e["dir"] > 0 else -1
                        if e["kind"] == "pb":
                            pbs[dd].append(e["px"])
                        elif e["kind"] == "idm":
                            idm[dd] = e["px"]
                        elif e["kind"] == "idm_break":
                            if e["bar"] >= RP.WARMUP:
                                w = ("recent" if cs[e["bar"]].t >= cut
                                     else "older")
                                rows += score(cs, piv, stc, e, idm[dd],
                                              pbs[dd], sym, tf, w, symset,
                                              skips)
                            idm[dd] = None
                            pbs[dd] = []

    by = defaultdict(list)
    for r in rows:
        by[(r.stop_policy, r.exit_policy)].append(r)

    print(f"\n{'=' * 104}\n  STOP GEOMETRY ON THE FULL POPULATION  "
          f"[PREREG §6]\n{'=' * 104}")
    print(f"  {'stop':<12}{'setups':>8}{'skipped':>9}{'med width':>11}"
          f"{'p25':>9}{'fee/R':>9}{'med BOS dist':>14}")
    for sp in STOPS:
        s = by[(sp, CONTROLS[0])]
        if not s:
            continue
        w = [r.stop_distance_pct for r in s]
        bd = [r.bos_distance_r for r in s]
        md = q(w, .5)
        print(f"  {sp:<12}{len(s):>8}{skips[sp]:>9}{md:>10.3f}%"
              f"{q(w, .25):>8.3f}%{0.032 / max(1e-9, md):>8.3f}R"
              f"{q(bd, .5):>13.2f}R")

    print(f"\n{'=' * 104}\n  PRIMARY ENDPOINT — stop = {PRIMARY}, in BETS"
          f"\n{'=' * 104}{HDR}")
    stats = {}
    for pol in POLICIES:
        stats[pol] = block(pol, by[(PRIMARY, pol)])

    print(f"\n{'=' * 104}\n  CONTROL — stop = RAID (Stage A's), same run"
          f"\n{'=' * 104}{HDR}")
    for pol in POLICIES:
        block(pol, by[("RAID", pol)])

    print(f"\n{'=' * 104}\n  REALIZED LOSS — the criterion Stage A failed"
          f"\n{'=' * 104}")
    for sp in STOPS:
        ls = [-r.realized_r for r in by[(sp, CONTROLS[0])]
              if r.realized_r < 0]
        if len(ls) < 20:
            continue
        tag = "  <-- PRIMARY" if sp == PRIMARY else ""
        print(f"  {sp} (planned loss 1.00R, n={len(ls)}){tag}")
        print("    " + "  ".join(
            f"P(>{t}R)={100 * sum(1 for x in ls if x > t) / len(ls):.1f}%"
            for t in (1.0, 1.25, 1.5, 2.0)))
        print(f"    median {q(ls, .5):.2f}R  p90 {q(ls, .90):.2f}R  "
              f"p95 {q(ls, .95):.2f}R  worst {max(ls):.2f}R")

    print(f"\n{'=' * 104}\n  PAIRED vs {PAIRED_BASE} on the primary stop"
          f"\n{'=' * 104}")
    print(f"  {'exit':<14}{'bets':>7}{'mean d':>9}{'SE':>7}{'z':>7}"
          f"{'improved':>10}")
    for pol in POLICIES:
        if pol == PAIRED_BASE:
            continue
        p = paired(by[(PRIMARY, pol)], by[(PRIMARY, PAIRED_BASE)])
        if p:
            print(f"  {pol:<14}{p['n']:>7}{p['m']:>9.3f}{p['se']:>7.3f}"
                  f"{p['z']:>7.1f}{p['pct']:>9.1f}%")

    base = by[(PRIMARY, CONTROLS[0])]
    reach = [r for r in base if r.active_reached]
    print(f"\n{'=' * 104}\n  MFE BEYOND ACTIVE PRICE — primary stop"
          f"\n{'=' * 104}")
    print(f"  Active Price reached: {len(reach)}/{len(base)} = "
          f"{100 * len(reach) / max(1, len(base)):.1f}%")
    mf = [r.mfe_r for r in reach]
    if mf:
        print(f"  median {q(mf, .5):.2f}R  mean {statistics.fmean(mf):.2f}R  "
              f"p75 {q(mf, .75):.2f}R  p90 {q(mf, .90):.2f}R")
        print("  " + "  ".join(
            f">{t}R: {100 * sum(1 for x in mf if x >= t) / len(mf):.1f}%"
            for t in (1.0, 1.5, 2.0, 3.0)))
    print(f"  hold time bars: median {q([r.bars_held for r in base], .5)}  "
          f"MAE median {q([r.mae_r for r in base], .5):.2f}R")

    print(f"\n{'=' * 104}\n  SECONDARY STOP POLICIES — DESCRIPTIVE ONLY"
          f"\n  PREREG §5: these cannot convert a FAIL or INCONCLUSIVE into a"
          f" PASS.\n{'=' * 104}")
    for sp in STOPS:
        if sp in (PRIMARY, "RAID"):
            continue
        print(f"\n  stop = {sp}{HDR}")
        for pol in CONTROLS:
            block(pol, by[(sp, pol)])

    print(f"\n{'=' * 104}\n  RESULT AGAINST THE FROZEN CRITERION  [PREREG §5]"
          f"\n{'=' * 104}")
    ok = [c for c in CONTROLS
          if stats.get(c) and stats[c]["m"] > 0 and stats[c]["t"] >= 2.5]
    ls = [-r.realized_r for r in base if r.realized_r < 0]
    tail = 100 * sum(1 for x in ls if x > 1.5) / len(ls) if ls else 0.0
    neg = all(stats.get(c) and stats[c]["m"] <= 0 for c in CONTROLS)
    print(f"  primary stop policy: {PRIMARY}")
    print(f"  criterion 1 (R/bet>0 and t>=2.5): "
          f"{ok if ok else 'NO control exit qualifies'}")
    print(f"  criterion 2 (P(loss>1.5R) <= 10%): {tail:.1f}%  "
          f"{'PASSES' if tail <= 10 else 'FAILS'}")
    verdict = ("PASS" if (ok and tail <= 10)
               else "FAIL" if neg else "INCONCLUSIVE")
    print(f"\n  VERDICT: {verdict}")
    if verdict != "PASS":
        print("  Per PREREG §5 the LIT trading family is CLOSED. No")
        print("  progression to pullback-gap, POI, Breaker/Flip, mitigation,")
        print("  SCOB, obstacle checking or sizing, and NO third stop")
        print("  pre-registration: fitting by iteration is what this process")
        print("  exists to prevent.")


if __name__ == "__main__":
    asyncio.run(main())
