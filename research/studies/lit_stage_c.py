"""LIT STAGE C — the trailing exit, on symbols that took no part in A or B.

Runs the experiment frozen in PREREG_lit_stage_c.md. Read that first. This is
a REPLICATION of one number — Stage B's T6_PIVOT at +0.145 R/bet against a
BOS_TARGET control — on an untouched population. It gets one test.

The stop is fixed at PRIOR_PB and is not varied. The population is the 55
symbols in the ranked turnover universe that appear in neither the discovery
set nor the rank-31+ set used by Stages A and B; the previous "held-out" tier
is NOT out of sample and is not treated as one.

    PYTHONPATH=. RIPTIDE_DEEP_CACHE=/tmp/deep \\
        python3 research/studies/lit_stage_c.py > lit_stage_c_out.txt
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import statistics                                       # noqa: E402
import subprocess                                       # noqa: E402
import time                                             # noqa: E402
from collections import defaultdict, Counter            # noqa: E402

import aiohttp                                          # noqa: E402

from research.deep import load_deep                     # noqa: E402
from research.harness import simulate_market, FEE_MAKER, FEE_TAKER  # noqa: E402,E501
import research.lit_v3 as L                             # noqa: E402
import research.lit_repl as RP                          # noqa: E402
from research.studies.lit_stage_a import (               # noqa: E402
    trails, bets, drawdown, q, HORIZON, MIN_RR)

ARMS = ("T6_PIVOT", "BOS_TARGET", "T6_STRUCTURE", "FIXED_1R", "FIXED_2R")
PRIMARY = "T6_PIVOT"
CONTROL = "BOS_TARGET"
FEE_RT = (FEE_MAKER + FEE_TAKER) / 100.0

# PREREG §4 and §5, frozen.
MIN_BETS = 2000          # below this the run is declared UNDERPOWERED
MAX_TIMEOUT_PCT = 20.0   # above this the primary arm is CONFOUNDED
MAX_LOSS_TAIL = 10.0     # P(realized loss > 1.5R) ceiling
T_BAR = 2.0
Z_BAR = 2.0
STAGE_B_EFFECT = 0.145   # the number being replicated


class T:
    __slots__ = ("sid", "t", "r", "arm", "why", "mfe", "held", "sym")

    def __init__(self, sid, ts, r, arm, why, mfe, held, sym):
        self.sid, self.t, self.r, self.arm = sid, ts, r, arm
        self.why, self.mfe, self.held, self.sym = why, mfe, held, sym


def run_symbol(cs, sym, tf, out, evcount):
    m, _i, _d, _g = L.engine(cs)
    piv, stc = trails(cs, m.events)
    pbs = {1: [], -1: []}
    n = 0
    for e in m.events:
        d = 1 if e["dir"] > 0 else -1
        if e["kind"] == "pb":
            pbs[d].append(e["px"])
            continue
        if e["kind"] != "idm_break":
            continue
        n += 1
        i, up, entry, bos = e["bar"], d > 0, e["entry"], e["bos"]
        prior = pbs[d][-2] if len(pbs[d]) > 1 else None
        pbs[d] = []
        if i < RP.WARMUP or bos is None or entry <= 0:
            continue
        if (bos <= entry) if up else (bos >= entry):
            continue                      # with-trend only
        if prior is None or ((prior >= entry) if up else (prior <= entry)):
            continue                      # PREREG §3: stop is PRIOR_PB or skip
        risk = abs(entry - prior)
        if risk <= 0:
            continue
        sid = f"{sym}:{tf}:{i}"
        for arm in ARMS:
            kw = dict(horizon_bars=HORIZON)
            if arm == "FIXED_1R":
                kw["target_r"] = 1.0
            elif arm == "FIXED_2R":
                kw["target_r"] = 2.0
            elif arm == "BOS_TARGET":
                kw["target_px"] = bos
                kw["target_r"] = abs(bos - entry) / risk
            else:
                kw["target_r"] = 1e9
                kw["trail"] = piv[d] if arm == "T6_PIVOT" else stc[d]
                kw["trail_arm_r"] = MIN_RR
            o = simulate_market(cs, i, entry, prior, up, **kw)
            if o is None or not o.filled:
                continue
            out[arm].append(T(sid, cs[i].t, o.r, arm, o.exit, o.mfe,
                              (o.exit_bar - i) if o.exit_bar else 0, sym))
    evcount[sym] = n


def stat(rows):
    b = bets_of(rows)
    if len(b) < 20:
        return None
    m = statistics.fmean(b)
    se = statistics.stdev(b) / (len(b) ** 0.5) if len(b) > 1 else 0.0
    tot, mdd = drawdown(b)
    w = [r.r for r in rows if r.r > 0]
    lo = [r.r for r in rows if r.r <= 0]
    return dict(n=len(rows), nb=len(b), m=m, se=se,
                t=(m / se if se else 0.0),
                win=100 * sum(1 for x in b if x > 0) / len(b),
                pf=(sum(w) / abs(sum(lo))) if lo and sum(lo) else float("inf"),
                tot=tot, mdd=mdd)


def bets_of(rows):
    by = defaultdict(list)
    for r in rows:
        by[r.t].append(r.r)
    return [statistics.fmean(v) for v in by.values()]


def paired_delta(a, b):
    ka = {r.sid: r.r for r in a}
    kb = {r.sid: r.r for r in b}
    ta = {r.sid: r.t for r in a}
    by = defaultdict(list)
    for k in ka.keys() & kb.keys():
        by[ta[k]].append(ka[k] - kb[k])
    d = [statistics.fmean(v) for v in by.values()]
    if len(d) < 20:
        return None
    m = statistics.fmean(d)
    se = statistics.stdev(d) / (len(d) ** 0.5) if len(d) > 1 else 0.0
    imp = sum(1 for k in ka.keys() & kb.keys() if ka[k] > kb[k])
    return dict(n=len(d), m=m, se=se, z=(m / se if se else 0.0),
                pct=100.0 * imp / max(1, len(ka.keys() & kb.keys())))


def show(label, s):
    if s is None:
        print(f"  {label:<16}   too few bets to read")
        return
    print(f"  {label:<16}{s['n']:>8}{s['nb']:>7}{s['m']:>9.3f}{s['se']:>7.3f}"
          f"{s['t']:>7.1f}{s['win']:>7.1f}%{s['pf']:>7.2f}{s['tot']:>9.1f}"
          f"{s['mdd']:>8.1f}")


HDR = (f"\n  {'arm':<16}{'trades':>8}{'bets':>7}{'R/bet':>9}{'SE':>7}"
       f"{'t':>7}{'win':>8}{'PF':>7}{'totR':>9}{'maxDD':>8}")


async def main():
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                            capture_output=True, text=True).stdout.strip()
    print("=" * 100)
    print("LIT STAGE C — THE TRAILING EXIT, ON UNTOUCHED SYMBOLS")
    print("=" * 100)
    print("TYPE        REPLICATION of Stage B's T6_PIVOT (+0.145 R/bet vs a")
    print("            BOS_TARGET control). Not a discovery test.")
    print("POPULATION  the symbols in the ranked turnover universe that took")
    print("            NO part in Stage A or B. The old 'held-out' tier was")
    print("            inside those stages and is NOT used as out-of-sample.")
    print("STOP        fixed at PRIOR_PB (Stage B primary). Not varied.")
    print("PRIMARY     T6_PIVOT — the T6 DEFAULT in LIT_STRATEGY_DESIGN.md,")
    print("            which also happened to score best in Stage B; the")
    print("            prereg discloses the coincidence rather than hiding it.")
    print(f"CRITERION   BOTH: R/bet>0 with t>={T_BAR}, AND paired delta vs")
    print(f"            {CONTROL} > 0 with z>={Z_BAR}.")
    print(f"GUARDS      >{MAX_TIMEOUT_PCT:.0f}% horizon exits => CONFOUNDED;"
          f" P(loss>1.5R)>{MAX_LOSS_TAIL:.0f}% => CONFOUNDED;")
    print(f"            <{MIN_BETS} bets => UNDERPOWERED, a null is"
          f" uninformative.")
    print(f"DATE        {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}")
    print(f"COMMIT      {commit}")
    print("PREREG      PREREG_lit_stage_c.md (committed at 639d287, before)")
    print("=" * 100)

    fresh_rows = defaultdict(list)
    repro_rows = defaultdict(list)
    evc_fresh, evc_old = {}, {}

    async with aiohttp.ClientSession() as sess:
        used = set(RP.DISCOVERY) | set(
            (await RP.heldout(sess, skip=len(RP.DISCOVERY), want=70))[:30])
        ranked = await RP.heldout(sess, skip=0, want=400)
        fresh = [s for s in ranked if s not in used]
        print(f"\n  untouched symbols: {len(fresh)}")
        print(f"  Stage A/B symbols (reproduction check only): {len(used)}")

        for tf in RP.TFS:
            for syms, out, evc in ((fresh, fresh_rows, evc_fresh),
                                   (sorted(used), repro_rows, evc_old)):
                for sym in syms:
                    try:
                        cs = await load_deep(sess, sym, tf, days=RP.DAYS)
                    except Exception:
                        continue
                    if len(cs) < 2000:
                        continue
                    run_symbol(cs, sym, tf, out, evc)

    # --- PREREG §7: the engine defect may be worse on a lower-liquidity tier
    def dead(evc):
        v = [n for n in evc.values() if n is not None]
        return (sum(1 for n in v if n < 5), len(v),
                statistics.median(v) if v else 0)
    df, nf, mf = dead(evc_fresh)
    do, no, mo = dead(evc_old)
    print(f"\n{'=' * 100}\n  ENGINE HEALTH ON THE UNTOUCHED TIER  [PREREG §7]"
          f"\n{'=' * 100}")
    print(f"  untouched : {df}/{nf} symbol-runs with <5 IDM breaks, "
          f"median {mf}")
    print(f"  Stage A/B : {do}/{no} symbol-runs with <5 IDM breaks, "
          f"median {mo}")

    print(f"\n{'=' * 100}\n  PRIMARY ENDPOINT — untouched symbols, in BETS"
          f"\n{'=' * 100}{HDR}")
    S = {}
    for arm in ARMS:
        S[arm] = stat(fresh_rows[arm])
        show(arm + ("  <-- PRIMARY" if arm == PRIMARY else ""), S[arm])

    print(f"\n{'=' * 100}\n  REPRODUCTION CHECK — Stage A/B symbols, same "
          f"pipeline\n  Confirms the code still returns Stage B's numbers. "
          f"NO part in the verdict.\n{'=' * 100}{HDR}")
    for arm in ARMS:
        show(arm, stat(repro_rows[arm]))

    pd = paired_delta(fresh_rows[PRIMARY], fresh_rows[CONTROL])
    print(f"\n{'=' * 100}\n  PAIRED: {PRIMARY} vs {CONTROL}, untouched symbols"
          f"\n{'=' * 100}")
    if pd:
        print(f"  bets {pd['n']}   mean delta {pd['m']:+.3f}   "
              f"SE {pd['se']:.3f}   z {pd['z']:.1f}   "
              f"improved {pd['pct']:.1f}%")

    print(f"\n{'=' * 100}\n  GUARDS  [PREREG §5]\n{'=' * 100}")
    why = Counter(r.why for r in fresh_rows[PRIMARY])
    ntot = max(1, sum(why.values()))
    tmo = 100.0 * why.get("timeout", 0) / ntot
    for k, v in why.most_common():
        sel = [r.r for r in fresh_rows[PRIMARY] if r.why == k]
        print(f"    exit={k:<9}{v:>6} ({100 * v / ntot:>5.1f}%)  "
              f"mean R {statistics.fmean(sel):>7.3f}  "
              f"contributes {sum(sel) / ntot:>7.3f}R/trade")
    ls = [-r.r for r in fresh_rows[PRIMARY] if r.r < 0]
    tail = 100 * sum(1 for x in ls if x > 1.5) / len(ls) if ls else 0.0
    print(f"  mark-to-market : {tmo:.1f}% horizon exits  "
          f"({'PASS' if tmo <= MAX_TIMEOUT_PCT else 'TRIPPED'})")
    print(f"  risk unit      : P(loss>1.5R) = {tail:.1f}%  "
          f"({'PASS' if tail <= MAX_LOSS_TAIL else 'TRIPPED'})")
    if ls:
        print(f"                   median loss {q(ls, .5):.2f}R  "
              f"p95 {q(ls, .95):.2f}R  worst {max(ls):.2f}R")

    print(f"\n{'=' * 100}\n  POWER ACHIEVED  [PREREG §4]\n{'=' * 100}")
    p = S[PRIMARY]
    if p:
        print(f"  bets {p['nb']}  SE {p['se']:.4f}  "
              f"MDE at t=2.0: {2 * p['se']:.3f}R")
        print(f"  Stage B effect being replicated: {STAGE_B_EFFECT:+.3f}R  ->"
              f" detectable here at t={STAGE_B_EFFECT / p['se']:.1f}"
              if p['se'] else "")
        print(f"  underpowered (<{MIN_BETS} bets): "
              f"{'YES' if p['nb'] < MIN_BETS else 'no'}")

    print(f"\n{'=' * 100}\n  RESULT AGAINST THE FROZEN CRITERION  [PREREG §6]"
          f"\n{'=' * 100}")
    c1 = bool(p and p["m"] > 0 and p["t"] >= T_BAR)
    c2 = bool(pd and pd["m"] > 0 and pd["z"] >= Z_BAR)
    conf = tmo > MAX_TIMEOUT_PCT or tail > MAX_LOSS_TAIL
    under = bool(p and p["nb"] < MIN_BETS)
    print(f"  criterion 1  R/bet>0 and t>={T_BAR}     : "
          f"{'MET' if c1 else 'not met'}"
          f"   ({p['m']:+.3f} at t={p['t']:.1f})" if p else "  no data")
    print(f"  criterion 2  paired delta>0, z>={Z_BAR} : "
          f"{'MET' if c2 else 'not met'}"
          f"   ({pd['m']:+.3f} at z={pd['z']:.1f})" if pd else "  no data")
    print(f"  disqualifiers                         : "
          f"{'TRIPPED' if conf else 'clear'}")

    if conf:
        verdict = "CONFOUNDED"
    elif c1 and c2:
        verdict = "PASS"
    elif (p and p["m"] <= 0) or (pd and pd["m"] <= 0):
        verdict = "FAIL"
    elif under:
        verdict = "INCONCLUSIVE (UNDERPOWERED)"
    else:
        verdict = "INCONCLUSIVE"
    print(f"\n  VERDICT: {verdict}")
    if verdict == "PASS":
        print("  Per PREREG §6 the claim stays NARROW: a pivot-trailing exit")
        print("  on the naked LIT continuation replicated on untouched")
        print("  symbols. NOT 'LIT is profitable'. It justifies one")
        print("  engineering cycle - Pine plus forward-recorded alerts - and")
        print("  nothing is traded on it.")
    else:
        print("  Per PREREG §6 the LIT trading family is closed PERMANENTLY.")
        print("  No Stage D, no further variants, no re-registration.")


if __name__ == "__main__":
    asyncio.run(main())
