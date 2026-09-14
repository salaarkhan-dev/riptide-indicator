"""THE 2x2 FACTORIAL ON THE TWO UNDOCUMENTED RULES, PLUS A COUNTERFACTUAL REPLAY.

The documented state machine has been implemented closely enough that the
remaining pathology - boundary locks lasting thousands of bars, with a
correction frozen open inside them - is an UNDOCUMENTED INTERACTION rather
than a coding defect. Three proposed root causes were falsified by measurement
first; this is what the decision gate opens onto.

  ARM A  control     documented ratchet   documented full-leg BOS
  ARM B  sweep only  EXPERIMENTAL reset   documented full-leg BOS
  ARM C  bos only    documented ratchet   EXPERIMENTAL segment BOS
  ARM D  both        EXPERIMENTAL reset   EXPERIMENTAL segment BOS

Nothing else differs between arms. Arm A is the untouched engine and stays
bit-identical to everything already measured.

THE TWO EXPERIMENTAL RULES, STATED BEFORE ANY NUMBER WAS SEEN

  SWEEP RESET. baseLevel remains the structural level and activeLevel migrates
  on wick-only sweeps as today. If price then CLOSES back on the original,
  non-breakout side of baseLevel, activeLevel returns to baseLevel and the
  sweep chain is cleared. The owning BOS/CHoCH is not retired - only its
  sweep-confirmation threshold resets. Hypothesis: repeated failed liquidity
  probes should not make a structural level indefinitely harder to break once
  price has clearly returned through it.

  SEGMENT BOS. Instead of the extreme from the structural leg start through
  the IDM break, the extreme of the impulse segment that CARRIES the active
  IDM - anchored at the tracker reset that followed the correction which
  became that IDM. No bar count, no ATR window, no percentage.

HOW A WINNER IS CHOSEN, in this order and not by duration:

  1. no invariant violations
  2. coherent LIT semantics
  3. materially better match to reference event geometry
  4. removes pathological terminal locks
  5. does not explode event count
  6. only then, duration distribution

A rule is not better merely because it shortens a 7403-bar correction. If an
arm halves the durations while manufacturing twice the reference's pullbacks
and inducements, it is rejected.

REGRESSION CASE. PB#64 on ZEC 15m, bars 1870..9273, ended by REORIENTATION on
a trend flip rather than by confirmation. Any proposed rule has to explain why
it resolves that differently, not merely make the box disappear.

    PYTHONPATH=. RIPTIDE_DEEP_CACHE=/tmp/deep python3 research/lit_exp.py
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
from collections import Counter                         # noqa: E402

import aiohttp                                          # noqa: E402

from research.deep import load_universe                 # noqa: E402
import research.lit_v02 as L                            # noqa: E402

SYMS = ["ZEC_USDT", "BTC_USDT", "ETH_USDT", "SOL_USDT", "ONDO_USDT",
        "LINK_USDT", "AVAX_USDT", "DOGE_USDT"]
ARMS = [("A control", False, False), ("B sweep only", True, False),
        ("C bos only", False, True), ("D both", True, True)]
REF_IDM_PER_2K = 23.0
REF_BOS_SHARE = 0.565


def pct(v, p):
    if not v:
        return 0
    w = sorted(v)
    return w[int(p * (len(w) - 1))]


def line(name, v):
    return (f"  {name:<22}median {pct(v, .5):>6}  p90 {pct(v, .9):>6}  "
            f"p95 {pct(v, .95):>6}  p99 {pct(v, .99):>6}  "
            f"max {max(v) if v else 0:>7}   n {len(v)}")


def run_arm(cs, sweep, seg):
    """One arm over the whole universe. Returns per-symbol state and spans."""
    L.CFG.sweep_reset = sweep
    L.CFG.segment_bos = seg
    out = {}
    for s, k in cs.items():
        m, it, dp, groups = L.engine(k)
        out[s] = (m, it, dp, groups)
    return out


def spans(ctx, groups):
    """Pullback cycles and boundary locks, as (start, end) bar pairs."""
    # rebuilt from the context's own event stream is not possible after the
    # fact, so this re-walks nothing - the engine records what is needed.
    return ctx


def replay_lock(groups, lo, hi, bosCtrl, bosSeg, chPx, direction):
    """Counterfactual: on which bar would each arm FIRST have resolved this
    lock? Nothing here mutates engine state - it is four shadow pairs of break
    trackers fed the same candles.

    Returns {arm: (bar, which level)} with None where the lock survives.
    """
    res = {}
    for nm, sweep, useSeg in ARMS:
        bp = bosSeg if (useSeg and bosSeg is not None) else bosCtrl
        if bp is None or chPx is None:
            res[nm] = None
            continue
        bb = L.Brk()
        cb = L.Brk()
        L.arm(bb, bp, 1 if direction > 0 else -1, L.M_BOS, L.HS_BOS)
        L.arm(cb, chPx, -1 if direction > 0 else 1, L.M_CH, L.HS_CH)
        prev = L.CFG.sweep_reset
        L.CFG.sweep_reset = sweep
        hit = None
        for (i, o, h, l, c) in groups:
            if i <= lo:
                continue
            if i > hi + 4000:
                break
            if L.brk_step(bb, o, h, l, c):
                hit = (i, "BOS")
                break
            if L.brk_step(cb, o, h, l, c):
                hit = (i, "CHoCH")
                break
        L.CFG.sweep_reset = prev
        res[nm] = hit
    return res


async def main():
    async with aiohttp.ClientSession() as sess:
        cs = await load_universe(sess, SYMS, "Min15", 120, min_bars=2000)

    print("RIPTIDE LIT - 2x2 FACTORIAL ON THE TWO UNDOCUMENTED RULES")
    print(f"{len(cs)} symbols, Min15, 120 days. Arm A is the untouched "
          f"documented engine.\n")

    arms = {}
    for nm, sweep, seg in ARMS:
        arms[nm] = run_arm(cs, sweep, seg)
    L.CFG.sweep_reset = L.CFG.segment_bos = False

    print(f"{'=' * 100}\nSTRUCTURAL POPULATION - Main depth, all symbols\n"
          f"{'=' * 100}")
    print(f"  {'arm':<14}{'PB':>7}{'IDM':>7}{'taken':>7}{'BOS':>6}{'CHoCH':>7}"
          f"{'flips':>7}{'locks':>7}{'latent used':>13}")
    for nm, _sw, _sg in ARMS:
        t = Counter()
        for s in cs:
            t.update(arms[nm][s][0].ev)
        print(f"  {nm:<14}{t['pivot']:>7}"
              f"{t['idm_create'] + t['idm_move']:>7}{t['idm_break']:>7}"
              f"{t['bos_break']:>6}{t['choch_create'] + t['choch_move']:>7}"
              f"{t['trend_flip']:>7}{t['enter_lock']:>7}"
              f"{t['latent_activated']:>13}")

    print(f"\n{'=' * 100}\nINVARIANTS AND AMBIGUITY - gate 1, any non-zero is "
          f"disqualifying\n{'=' * 100}")
    for nm, _sw, _sg in ARMS:
        bad = Counter()
        amb = 0
        for s in cs:
            for d in range(3):
                bad.update(arms[nm][s][d].bad)
            amb += arms[nm][s][0].ev["race_ambiguous"]
        tag = "all clean" if not bad else str(dict(bad))
        print(f"  {nm:<14}{tag:<52} ambiguous bars excluded {amb}")

    print(f"\n{'=' * 100}\nREFERENCE FIXTURE - ZEC 15m, deepest degree\n"
          f"{'=' * 100}")
    print("  the reference shows 23 taken inducements per ~2000 bars splitting")
    print("  56.5/43.5. gate 5 rejects an arm that explodes the population.")
    zn = len(cs["ZEC_USDT"])
    print(f"  {'arm':<14}{'deep taken':>12}{'per 2000':>10}{'vs ref':>9}"
          f"{'BOS-first':>11}{'main PB':>9}{'main IDM':>10}")
    for nm, _sw, _sg in ARMS:
        d = arms[nm]["ZEC_USDT"][2]
        m = arms[nm]["ZEC_USDT"][0]
        p2k = d.ev["idm_break"] * 2000 / zn
        b, c2 = d.ev["race_bos"], d.ev["race_choch"]
        sh = f"{b / (b + c2):.1%}" if b + c2 else "-"
        print(f"  {nm:<14}{d.ev['idm_break']:>12}{p2k:>10.1f}"
              f"{p2k / REF_IDM_PER_2K:>8.2f}x{sh:>11}{m.ev['pivot']:>9}"
              f"{m.ev['idm_create'] + m.ev['idm_move']:>10}")

    print(f"\n{'=' * 100}\nBOS LOCK OUTCOMES - Main\n{'=' * 100}")
    for nm, _sw, _sg in ARMS:
        logs = [e for s in cs for e in arms[nm][s][0].bosLog]
        k = Counter(e[2] if not isinstance(e[2], int) else "broke"
                    for e in logs)
        n = max(len(logs), 1)
        dur = [e[2] for e in logs if isinstance(e[2], int)]
        far0 = sum(1 for e in logs if e[2] is None)
        print(f"  {nm:<14}n {len(logs):>4}   broke {k['broke'] / n:>4.0%}   "
              f"abandoned {k['abandoned'] / n:>4.0%}   "
              f"open at end {far0 / n:>4.0%}   "
              f"bars-to-break median {pct(dur, .5):>4} p99 {pct(dur, .99):>5}")

    print(f"\n{'=' * 100}\nCOUNTERFACTUAL REPLAY ON THE CONTROL'S WORST LOCKS\n"
          f"{'=' * 100}")
    print("  for each pathological lock found by Arm A, when would each rule")
    print("  FIRST have resolved it? nothing is acted on - shadow trackers only.")
    ctrl = arms["A control"]
    shown = 0
    for s in cs:
        m, _it, _dp, groups = ctrl[s]
        for e in m.bosLog:
            dur = e[2] if isinstance(e[2], int) else 99999
            if dur < 600:
                continue
            lo = e[1]
            bosCtrl, bosSeg, chPx, dr = e[3], e[4], e[5], e[6]
            hi = lo + (dur if dur < 99999 else 0)
            r = replay_lock(groups, lo, hi, bosCtrl, bosSeg, chPx, dr)
            shown += 1
            print(f"\n  {s}  lock from bar {lo}   dir "
                  f"{'bull' if dr > 0 else 'bear'}   "
                  f"BOS ctrl {bosCtrl:.2f}" +
                  (f"   BOS seg {bosSeg:.2f}" if bosSeg else "   BOS seg n/a") +
                  (f"   CHoCH {chPx:.2f}" if chPx else "   CHoCH n/a"))
            for nm, _a, _b in ARMS:
                v = r[nm]
                if v is None:
                    print(f"      {nm:<14} survives the window")
                else:
                    print(f"      {nm:<14} resolves bar {v[0]:>6} "
                          f"(+{v[0] - lo:>5} bars) via {v[1]}")
            if shown >= 6:
                break
        if shown >= 6:
            break

    print(f"\n{'=' * 100}\nSWEEP BEHAVIOUR - how far the threshold walks\n"
          f"{'=' * 100}")
    print("  drift is the active level's distance from its base when the level")
    print("  was retired. a ratchet that never resets is what walks it away.")
    for nm, sweep, seg in ARMS:
        L.CFG.sweep_reset, L.CFG.segment_bos = sweep, seg
        drift = []
        sw = []
        for s in cs:
            m = arms[nm][s][0]
            for b in (m.bos.b, m.ch.b):
                if b.base and b.act:
                    drift.append(round(100 * abs(b.act - b.base) / b.base, 2))
                    sw.append(b.sweeps)
        print(f"  {nm:<14}final-state drift% "
              f"median {pct(drift, .5):>5}  max {max(drift) if drift else 0:>6}"
              f"   sweep chain max {max(sw) if sw else 0}")
    L.CFG.sweep_reset = L.CFG.segment_bos = False


if __name__ == "__main__":
    asyncio.run(main())
