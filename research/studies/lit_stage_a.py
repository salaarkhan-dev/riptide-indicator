"""LIT STAGE A — the naked IDM continuation event.

Runs the experiment frozen in PREREG_lit_stage_a.md. Read that first; nothing
here may be changed to improve a result, and no threshold in it moves.

THE QUESTION. Does the naked continuation event — enter at the IDM-break
close, stop at the raid extreme, nothing else — carry enough economic edge to
justify building POI, pullback-gap, SCOB, mitigation and obstacle filtering on
top of it? Stage A is allowed to kill the family.

WHAT IS DIFFERENT FROM EVERY EARLIER LIT MEASUREMENT.

  1. The REPOSITORY's fee model (harness.py maker 0.010% / taker 0.022%), not
     the reference document's 0.05% per side. Earlier work charged ~3x.
  2. The BET as the unit of evidence, per studies/fvg_continuation.py.
  3. The SHARED scorer, harness.simulate_market. No private scorer, no
     duplicate fee logic.

    PYTHONPATH=. RIPTIDE_DEEP_CACHE=/tmp/deep \\
        python3 research/studies/lit_stage_a.py > lit_stage_a_out.txt
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import statistics                                       # noqa: E402
import subprocess                                       # noqa: E402
import time                                             # noqa: E402
from collections import defaultdict                     # noqa: E402
from dataclasses import dataclass                       # noqa: E402

import aiohttp                                          # noqa: E402

from research.deep import load_deep                     # noqa: E402
from research.harness import simulate_market            # noqa: E402
import research.lit_v3 as L                             # noqa: E402
import research.lit_repl as RP                          # noqa: E402

DAYS = RP.DAYS
RECENT_DAYS = RP.RECENT_DAYS
WARMUP = RP.WARMUP
TFS = RP.TFS
HORIZON = 500
MIN_RR = 0.5

# PREREG §6. MFE-fraction trailing is deliberately absent.
POLICIES = ("FIXED_1R", "FIXED_2R", "BOS_TARGET", "T6_PIVOT", "T6_STRUCTURE")
CONTROLS = ("FIXED_1R", "FIXED_2R", "BOS_TARGET")
PAIRED_BASE = "BOS_TARGET"


@dataclass
class Row:
    """PREREG §12 outcome record."""
    setup_id: str
    symbol: str
    timeframe: str
    direction: int
    signal_time: int
    entry: float
    initial_stop: float
    raid_extreme: float
    stop_distance_price: float
    stop_distance_pct: float
    bos_price: float
    choch_price: float | None
    bos_distance_r: float
    active_price: float
    active_reached: bool
    bos_before_choch: bool | None
    mfe_r: float
    mae_r: float
    exit_policy: str
    exit_price: float
    exit_reason: str
    bars_held: int
    realized_r: float
    planned_loss_r: float
    realized_loss_r: float
    window: str
    symset: str


def trails(cs, events):
    """Per-bar trailing levels, indexed like `cs`, one array per direction.

    PIVOT     the most recent confirmed pullback pivot in the trade direction.
    STRUCTURE the most recent structural level — the IDM raid extreme.

    Both are forward-filled: once a level exists it stands until replaced.
    harness.simulate_market reads trail[k-1], so a level is never used on the
    bar that produced it.
    """
    n = len(cs)
    piv = {1: [None] * n, -1: [None] * n}
    stc = {1: [None] * n, -1: [None] * n}
    curP = {1: None, -1: None}
    curS = {1: None, -1: None}
    byBar = defaultdict(list)
    for e in events:
        byBar[e["bar"]].append(e)
    for i in range(n):
        for e in byBar.get(i, ()):
            d = 1 if e["dir"] > 0 else -1
            if e["kind"] == "pb":
                curP[d] = e["px"]
            elif e["kind"] == "idm_break":
                curS[d] = e["stop"]
        for d in (1, -1):
            piv[d][i], stc[d][i] = curP[d], curS[d]
    return piv, stc


def first_touch(cs, start, px, up):
    """Bar index where price first reaches `px`, or None inside the horizon."""
    if px is None:
        return None
    for k in range(start + 1, min(start + 1 + HORIZON, len(cs))):
        if (cs[k].h >= px) if up else (cs[k].l <= px):
            return k
    return None


def score(cs, piv, stc, ev, sym, tf, window, symset, idx):
    """One IDM-break signal under all five exit policies. PREREG §4, §6, §7."""
    i = ev["bar"]
    up = ev["dir"] > 0
    entry, stop, bos = ev["entry"], ev["stop"], ev["bos"]
    if bos is None or entry <= 0:
        return []
    risk = abs(entry - stop)
    if risk <= 0:
        return []
    # With-trend only: the BOS the thesis targets must lie beyond the entry.
    if (bos <= entry) if up else (bos >= entry):
        return []

    d = 1 if up else -1
    # PREREG §4. Active Price is where a trail ARMS; it is not a target.
    from research.harness import FEE_MAKER, FEE_TAKER
    feePx = entry * (FEE_MAKER + FEE_TAKER) / 100.0
    active = entry + d * (MIN_RR * risk + feePx)

    bosBar = first_touch(cs, i, bos, up)
    chBar = first_touch(cs, i, ev.get("choch"), not up)
    if bosBar is None and chBar is None:
        bbc = None
    else:
        bbc = bosBar is not None and (chBar is None or bosBar <= chBar)

    out = []
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
            # A trail with no fixed target, armed at Active Price. The target
            # is set unreachably far so only the stop or the horizon can end
            # the trade — the reference does not take fixed profits.
            kw["target_r"] = 1e9
            kw["trail"] = (piv[d] if pol == "T6_PIVOT" else stc[d])
            kw["trail_arm_r"] = MIN_RR
        o = simulate_market(cs, i, entry, stop, up, **kw)
        if o is None or not o.filled:
            continue
        exPx = entry + d * o.r * risk        # approximate realised exit price
        out.append(Row(
            setup_id=f"{sym}:{tf}:{i}", symbol=sym, timeframe=tf,
            direction=d, signal_time=cs[i].t, entry=entry,
            initial_stop=stop, raid_extreme=stop,
            stop_distance_price=risk, stop_distance_pct=100.0 * risk / entry,
            bos_price=bos, choch_price=ev.get("choch"),
            bos_distance_r=abs(bos - entry) / risk,
            active_price=active, active_reached=o.mfe >= MIN_RR,
            bos_before_choch=bbc, mfe_r=o.mfe, mae_r=o.mae,
            exit_policy=pol, exit_price=exPx, exit_reason=o.exit,
            bars_held=(o.exit_bar - i) if o.exit_bar else 0,
            realized_r=o.r, planned_loss_r=-1.0,
            realized_loss_r=(o.r if o.r < 0 else 0.0),
            window=window, symset=symset))
    return out


def bets(rows):
    """PREREG §8. Trades sharing a bar open time are ONE observation."""
    by = defaultdict(list)
    for r in rows:
        by[r.signal_time].append(r.realized_r)
    return [statistics.fmean(v) for v in by.values()]


def paired(a, b):
    """Same setups, so compare per setup. PREREG §10."""
    ka = {r.setup_id: r.realized_r for r in a}
    kb = {r.setup_id: r.realized_r for r in b}
    tb = {r.setup_id: r.signal_time for r in a}
    by = defaultdict(list)
    for k in ka.keys() & kb.keys():
        by[tb[k]].append(ka[k] - kb[k])
    d = [statistics.fmean(v) for v in by.values()]
    if len(d) < 20:
        return None
    m = statistics.fmean(d)
    se = statistics.stdev(d) / (len(d) ** 0.5) if len(d) > 1 else 0.0
    imp = sum(1 for k in ka.keys() & kb.keys() if ka[k] > kb[k])
    return dict(n=len(d), m=m, se=se, z=(m / se if se else 0.0),
                pct=100.0 * imp / max(1, len(ka.keys() & kb.keys())))


def drawdown(series):
    peak = cum = mdd = 0.0
    for r in series:
        cum += r
        peak = max(peak, cum)
        mdd = min(mdd, cum - peak)
    return cum, -mdd


def q(v, p):
    if not v:
        return 0.0
    s = sorted(v)
    return s[min(len(s) - 1, int(p * (len(s) - 1)))]


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


async def main():
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                                capture_output=True, text=True).stdout.strip()
    except Exception:
        commit = "unknown"
    cut = time.time() - RECENT_DAYS * 86400

    print("=" * 100)
    print("LIT STAGE A — NAKED IDM CONTINUATION")
    print("=" * 100)
    print("HYPOTHESIS  H0: the naked LIT continuation event has no economic")
    print("            edge net of costs. H1: it does, enough to justify")
    print("            building POI / pullback-gap / SCOB / obstacle on top.")
    print("POPULATION  60 symbols (30 discovery + 30 held-out at turnover")
    print("            ranks 31+), Min15/Min30/Min60, 333 days, 500-bar")
    print("            warm-up, split at 120 days into recent/older.")
    print("RULES       Entry: close of the IDM-break bar, MARKET, with-trend")
    print("            only, MAIN depth. Stop: the IDM raid extreme, no")
    print("            buffer. Active Price: entry +/- (0.5R + fee) — it ARMS")
    print("            a trail, it is NOT a target.")
    print("CONTROLS    FIXED_1R, FIXED_2R, BOS_TARGET (fully specified)")
    print("POLICIES    T6_PIVOT, T6_STRUCTURE (armed at Active Price).")
    print("            MFE-fraction deliberately NOT run.")
    print("SCORING     harness.simulate_market — shared scorer, repo fees")
    print("            (maker 0.010% / taker 0.022%), entry bar resolves")
    print("            nothing, stop before target, horizon 500 bars.")
    print("UNIT        the BET: trades sharing a bar open time are averaged.")
    print(f"DATE        {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}")
    print(f"COMMIT      {commit}")
    print(f"PREREG      PREREG_lit_stage_a.md (committed before this run)")
    print("=" * 100)

    rows = []
    async with aiohttp.ClientSession() as sess:
        held = (await RP.heldout(sess, skip=len(RP.DISCOVERY), want=70))[:30]
        for tf in TFS:
            for symset, syms in (("discovery", RP.DISCOVERY),
                                 ("held-out", held)):
                for sym in syms:
                    try:
                        cs = await load_deep(sess, sym, tf, days=DAYS)
                    except Exception:
                        continue
                    if len(cs) < 2000:
                        continue
                    m, _i, _d, _g = L.engine(cs)
                    piv, stc = trails(cs, m.events)
                    for e in m.events:
                        if e["kind"] != "idm_break" or e["bar"] < WARMUP:
                            continue
                        w = "recent" if cs[e["bar"]].t >= cut else "older"
                        rows += score(cs, piv, stc, e, sym, tf, w, symset,
                                      len(rows))

    byPol = defaultdict(list)
    for r in rows:
        byPol[r.exit_policy].append(r)
    setups = len({r.setup_id for r in rows})

    hdr = (f"\n  {'policy':<14}{'trades':>7}{'bets':>7}{'R/bet':>9}{'SE':>7}"
           f"{'t':>7}{'win':>8}{'PF':>7}{'totR':>9}{'maxDD':>8}{'recov':>8}")
    print(f"\n{'=' * 100}\n  PRIMARY ENDPOINT — all 60 symbols, all "
          f"timeframes, both windows, in BETS\n{'=' * 100}")
    print(f"  setups: {setups}")
    print(hdr)
    stats = {}
    for pol in POLICIES:
        stats[pol] = block(pol, byPol[pol])

    print(f"\n{'=' * 100}\n  PAIRED COMPARISON vs {PAIRED_BASE} — same "
          f"setups, per-bet deltas\n{'=' * 100}")
    print(f"  {'policy':<14}{'bets':>7}{'mean d':>9}{'SE':>7}{'z':>7}"
          f"{'improved':>10}")
    for pol in POLICIES:
        if pol == PAIRED_BASE:
            continue
        p = paired(byPol[pol], byPol[PAIRED_BASE])
        if p:
            print(f"  {pol:<14}{p['n']:>7}{p['m']:>9.3f}{p['se']:>7.3f}"
                  f"{p['z']:>7.1f}{p['pct']:>9.1f}%")

    base = byPol[CONTROLS[0]]
    print(f"\n{'=' * 100}\n  DECISIVE DIAGNOSTIC — MFE beyond Active Price"
          f"  [PREREG §11]\n{'=' * 100}")
    reach = [r for r in base if r.active_reached]
    print(f"  Active Price reached: {len(reach)}/{len(base)} = "
          f"{100 * len(reach) / max(1, len(base)):.1f}%")
    mf = [r.mfe_r for r in reach]
    if mf:
        print(f"  among those: median {q(mf, .5):.2f}R  mean "
              f"{statistics.fmean(mf):.2f}R")
        print(f"    p25 {q(mf, .25):.2f}  p50 {q(mf, .50):.2f}  "
              f"p75 {q(mf, .75):.2f}  p90 {q(mf, .90):.2f}")
        for thr in (1.0, 1.5, 2.0, 3.0):
            print(f"    exceeding {thr:>3}R: "
                  f"{100 * sum(1 for x in mf if x >= thr) / len(mf):>5.1f}%")

    print(f"\n{'=' * 100}\n  REALIZED LOSS  [PREREG §12]\n{'=' * 100}")
    for pol in CONTROLS:
        ls = [-r.realized_r for r in byPol[pol] if r.realized_r < 0]
        if not ls:
            continue
        print(f"  {pol}: planned loss 1.00R, n={len(ls)}")
        for thr in (1.0, 1.25, 1.5, 2.0):
            print(f"    P(loss > {thr:>4}R) = "
                  f"{100 * sum(1 for x in ls if x > thr) / len(ls):>5.1f}%")
        print(f"    median {q(ls, .5):.2f}R  p90 {q(ls, .90):.2f}R  "
              f"p95 {q(ls, .95):.2f}R  worst {max(ls):.2f}R")

    print(f"\n{'=' * 100}\n  PRE-SPECIFIED SECONDARY BREAKDOWNS  [PREREG §9]"
          f"\n  Descriptive only. A positive cell here does NOT overturn the"
          f" primary endpoint.\n{'=' * 100}")
    for pol in CONTROLS:
        print(f"\n  {pol}{hdr}")
        for key, sel in (("recent", lambda r: r.window == "recent"),
                         ("older", lambda r: r.window == "older"),
                         ("discovery", lambda r: r.symset == "discovery"),
                         ("held-out", lambda r: r.symset == "held-out"),
                         ("Min15", lambda r: r.timeframe == "Min15"),
                         ("Min30", lambda r: r.timeframe == "Min30"),
                         ("Min60", lambda r: r.timeframe == "Min60")):
            block(key, [r for r in byPol[pol] if sel(r)])

    print(f"\n{'=' * 100}\n  OTHER FROZEN METRICS\n{'=' * 100}")
    sd = [r.stop_distance_pct for r in base]
    print(f"  STOP DISTANCE, % of entry: median {q(sd, .5):.3f}%  "
          f"p10 {q(sd, .10):.3f}%  p25 {q(sd, .25):.3f}%  "
          f"p75 {q(sd, .75):.3f}%")
    print(f"  fee as a fraction of R (repo 0.032% round trip): "
          f"median {0.032 / max(1e-9, q(sd, .5)):.3f}R  "
          f"p10-stop {0.032 / max(1e-9, q(sd, .10)):.3f}R")
    bd = [r.bos_distance_r for r in base]
    print(f"  distance to BOS at entry, in R: median {q(bd, .5):.2f}  "
          f"p25 {q(bd, .25):.2f}  p75 {q(bd, .75):.2f}  p90 {q(bd, .90):.2f}")
    known = [r for r in base if r.bos_before_choch is not None]
    if known:
        print(f"  BOS before CHoCH: "
              f"{100 * sum(1 for r in known if r.bos_before_choch) / len(known):.1f}%"
              f"  (n={len(known)}, undetermined {len(base) - len(known)})")
    print(f"  hold time, bars: median {q([r.bars_held for r in base], .5)}  "
          f"mean {statistics.fmean([r.bars_held for r in base]):.0f}")
    print(f"  MAE, in R: median {q([r.mae_r for r in base], .5):.2f}  "
          f"p10 {q([r.mae_r for r in base], .10):.2f}")

    print(f"\n{'=' * 100}\n  RESULT AGAINST THE FROZEN CRITERION  "
          f"[PREREG §10]\n{'=' * 100}")
    print("  PASS requires a control with R/bet > 0 AND t >= 2.0,")
    print("  AND P(realized loss > 1.5R) <= 10%.")
    ok = [c for c in CONTROLS
          if stats.get(c) and stats[c]["m"] > 0 and stats[c]["t"] >= 2.0]
    ls = [-r.realized_r for r in byPol[CONTROLS[0]] if r.realized_r < 0]
    tail = 100 * sum(1 for x in ls if x > 1.5) / len(ls) if ls else 0.0
    print(f"  controls meeting criterion 1: {ok if ok else 'NONE'}")
    print(f"  P(realized loss > 1.5R) = {tail:.1f}%  "
          f"({'<= 10%, passes' if tail <= 10 else '> 10%, fails'})")
    neg = all(stats.get(c) and stats[c]["m"] <= 0 for c in CONTROLS)
    verdict = ("PASS" if (ok and tail <= 10)
               else "FAIL" if neg else "INCONCLUSIVE")
    print(f"\n  VERDICT: {verdict}")
    if verdict != "PASS":
        print("  Per PREREG §10, work STOPS. No progression to pullback-gap,")
        print("  POI, Breaker/Flip, mitigation, SCOB, obstacle checking or")
        print("  position sizing. Those are not rescue tools for a weak base.")


if __name__ == "__main__":
    asyncio.run(main())
