"""Is the EXIT the bug? Runs exactly what prereg/PREREG_undertow_exits.md says.

    PYTHONPATH=. python3 indicators/undertow/studies/undertow_exits.py
    PYTHONPATH=. python3 indicators/undertow/studies/undertow_exits.py Min30

THE QUESTION. Every number measured for Undertow so far closes at a fixed 2R or
3R. The person trading it lets winners run to opposite-side liquidity and
reports 1:3 to 1:7. At a 30% win rate that is the difference between +0.20 R and
+0.65 R per trade -- same entries, same stops, decided entirely by where the
trade is closed. If that is the gap, every verdict so far is about a strategy
nobody trades.

HOW IT WORKS. The entries are produced ONCE, by the same configuration the
ablation used, and then every exit model is scored on THE IDENTICAL FILLS. The
stop never changes: it is the R denominator, and a study that varied it would
not be comparing exits. Two arms move the stop after entry (break-even, trail)
and that is the arm's definition, not a change to the risk.

    E0-E3   fixed 2R / 3R / 5R / 7R
    E4      +1R then break-even, run to the horizon
    E5      LIQUIDITY -- the opposing structural extreme at entry. The manual
            rule, as described.
    E6      ATR trail, 2.0x, armed at +1R
    E7      MFE ORACLE -- the best price the trade ever saw. NOT TRADEABLE and
            excluded from every verdict; it is the ceiling, so every other arm
            can be read as a fraction of what was actually available.

HORIZON 200 BARS, and a trade that has neither stopped nor exited by then is
MARKED TO MARKET rather than discarded. Discarding would quietly delete the
trades that run longest, which is exactly the population the runner arms exist
to capture -- it would flatter them by throwing away their failures.

THE MFE DISTRIBUTION is printed alongside and carries no hypothesis. It is the
fact that decides whether the manual account's tail is in this data at all: if
the 90th percentile is under 3R, the 1:7 trades are not here and the
disagreement is about which setups get taken, not about where they close.
"""
from __future__ import annotations

import dataclasses
import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))

from indicators.undertow.port import undertow as U               # noqa: E402
from indicators.undertow.studies.undertow_sweep import (         # noqa: E402
    FEE, LOADED, SEED, TFS, clustered, load, quadrant)
from research.data import SYMBOLS                                # noqa: E402

HORIZON = 200
# AS PUBLISHED, PINNED. Every setting this study's page was run under is
# named here even where it matched P's default at the time, because a default
# that later moves silently re-points a published study: `swingSrc` went from
# the bar pivot to "price move" after this ran, so without these lines the
# script would print different numbers under the same page's name. A study that
# cannot reproduce its own measurement is not a record of anything.
BASE = U.P(biasGate=U.BG_TRADEABLE, famStrict=False, armWins=False, stopSrc=U.S_PULL, useBackup=False, pinNewest=False, famPriority=False, failTest=U.T_CLOSE, biasSrc=U.BS_STRUCT, confirmOrder=U.C_EITHER, rr=3.0, feeFrac=FEE, maxLive=64,
           swingSrc=U.SW_BAR, msLen=15, msShortLen=3,
           endSweep=True, endStale=True)

EXITS = ["E0 fixed 2R", "E1 fixed 3R", "E2 fixed 5R", "E3 fixed 7R",
         "E4 BE then run", "E5 liquidity", "E6 ATR trail 2.0",
         "E7 MFE oracle"]
TRADEABLE = EXITS[:-1]          # E7 is a ceiling, never a verdict


def score(cs, t, atr, liq, horizon=HORIZON):
    """One filled trade, scored under every exit model at once.

    Walked bar by bar from the fill. Within a bar the STOP IS CHECKED FIRST:
    when one bar spans both the stop and the target the order is unknowable
    intrabar, so the conservative reading is taken. That rule is the same one
    the port applies and it is what keeps these numbers comparable to it.

    `liq` is the opposing structural extreme captured at the fill bar -- the
    engine's running msMax for a long, msMin for a short. It is read at entry
    and never updated, because a target that moves with price is a trail, and
    a trail is E6.
    """
    risk = abs(t.stop - t.entry)
    if risk <= 0:
        return None
    sgn = -1.0 if t.short else 1.0
    fee = FEE * t.entry / risk

    def rOf(px):
        return sgn * (px - t.entry) / risk

    targets = {"E0 fixed 2R": 2.0, "E1 fixed 3R": 3.0,
               "E2 fixed 5R": 5.0, "E3 fixed 7R": 7.0}
    out = {}
    mfe = 0.0
    # per-arm live state
    beStop = None                       # E4
    trStop = None                       # E6
    peak = t.entry
    end = min(t.fillBar + horizon, len(cs) - 1)

    for j in range(t.fillBar, end + 1):
        b = cs[j]
        hiR, loR = rOf(b.h if not t.short else b.l), rOf(b.l if not t.short else b.h)
        mfe = max(mfe, hiR)
        stopR = rOf(t.stop)

        # --- the fixed-target arms, and the original stop -------------------
        hitStop = (b.h >= t.stop) if t.short else (b.l <= t.stop)
        for name, k in targets.items():
            if name in out:
                continue
            if hitStop:
                out[name] = stopR
            elif hiR >= k:
                out[name] = k
        # --- E5 liquidity ---------------------------------------------------
        if "E5 liquidity" not in out:
            if hitStop:
                out["E5 liquidity"] = stopR
            elif liq is not None and rOf(liq) > 0 and hiR >= rOf(liq):
                out["E5 liquidity"] = rOf(liq)
        # --- E4 break-even then run -----------------------------------------
        if "E4 BE then run" not in out:
            active = beStop if beStop is not None else t.stop
            if (b.h >= active) if t.short else (b.l <= active):
                out["E4 BE then run"] = rOf(active)
            elif beStop is None and hiR >= 1.0:
                beStop = t.entry
        # --- E6 ATR trail ----------------------------------------------------
        if "E6 ATR trail 2.0" not in out:
            active = trStop if trStop is not None else t.stop
            if (b.h >= active) if t.short else (b.l <= active):
                out["E6 ATR trail 2.0"] = rOf(active)
            else:
                peak = (min(peak, b.l) if t.short else max(peak, b.h))
                if hiR >= 1.0:
                    cand = peak + 2.0 * atr[j] if t.short else peak - 2.0 * atr[j]
                    # a trail only ever tightens
                    trStop = cand if trStop is None else (
                        min(trStop, cand) if t.short else max(trStop, cand))
        if len(out) == 7:
            break

    # Anything unresolved at the horizon is MARKED TO MARKET. Not discarded --
    # see the module docstring; discarding deletes the runner arms' failures.
    mark = rOf(cs[end].c)
    for name in EXITS[:-1]:
        out.setdefault(name, mark)
    out["E7 MFE oracle"] = mfe
    return {k: v - fee for k, v in out.items()}, mfe


def entries(tf, pairs):
    """The frozen entry set, plus what each exit model needs to score it."""
    data = LOADED[tf]
    rows = []
    for sym, older in pairs:
        cs = data.get(sym)
        if not cs or len(cs) < 1200:
            continue
        seg, skip = quadrant(cs, older)
        r = U.run(seg, BASE, sym)
        st, atr = U.structure(seg, BASE)
        for t in r.real:
            if t.fillBar < skip:
                continue
            liq = st["msMax"][t.fillBar] if not t.short else st["msMin"][t.fillBar]
            got = score(seg, t, atr, liq)
            if got:
                rows.append((sym, got[0], got[1]))
    return rows


def pct(vals, q):
    if not vals:
        return 0.0
    s = sorted(vals)
    return s[min(len(s) - 1, int(q * len(s)))]


def as_trades(rows, name):
    return [U.Trade(symbol=s, r=d[name]) for s, d, _ in rows]


def panel(tf, pairs, title):
    rows = entries(tf, pairs)
    print(f"\n{'-' * 78}\n{tf} · {title}   {len(rows)} filled trades\n{'-' * 78}")
    if not rows:
        return {}
    mfes = [m for _, _, m in rows]
    print("  MFE — how far these actually ran, in R. Descriptive, no claim.")
    print(f"    median {pct(mfes, .5):.2f}   p75 {pct(mfes, .75):.2f}   "
          f"p90 {pct(mfes, .90):.2f}   p95 {pct(mfes, .95):.2f}   "
          f"max {max(mfes):.1f}")
    # THE TABLE THAT DECIDES THIS. A fixed-R exit breaks even at a hit rate of
    # 1/(1+R) -- which is also exactly what a driftless random walk delivers.
    # So "reached kR" against 1/(1+k) is the strategy against a coin, with no
    # control run needed: it is arithmetic.
    print(f"\n  {'target':>7} {'reached':>9} {'break-even':>11} {'edge':>8}")
    for k in (1, 2, 3, 5, 7):
        share = sum(1 for m in mfes if m >= k) / len(mfes)
        need = 1.0 / (1.0 + k)
        print(f"  {k:6}R {share * 100:8.1f}% {need * 100:10.1f}% "
              f"{(share - need) * 100:+7.1f}pp")
    # How many trades the 200-bar horizon TRUNCATED. If this is large the
    # runner arms are being cut off rather than measured, and every number
    # above understates them.
    trunc = sum(1 for _, d, _ in rows
                if abs(d["E3 fixed 7R"] - d["E4 BE then run"]) < 1e-9
                and abs(d["E3 fixed 7R"]) < 0.999)
    print(f"  horizon {HORIZON} bars truncated ~{100 * trunc / len(rows):.0f}% "
          f"of trades (marked to market, not discarded)")
    print(f"\n  {'exit':20} {'mean R':>8} {'+/-':>6} {'z':>6}   vs E1")
    out = {}
    e1 = None
    for name in EXITS:
        ts = as_trades(rows, name)
        m, se, n = clustered(ts)
        z = m / se if se and not math.isinf(se) else 0.0
        if name == "E1 fixed 3R":
            e1 = (m, se, ts)
        d = ""
        if e1 and name != "E1 fixed 3R":
            dm = m - e1[0]
            dse = math.sqrt(se ** 2 + e1[1] ** 2) if se and e1[1] else float("inf")
            d = f"{dm:+.3f} +/- {dse:.3f} (z {dm / dse:+.2f})" if dse else ""
        tail = "  CEILING, not tradeable" if name == "E7 MFE oracle" else d
        print(f"  {name:20} {m:+8.3f} {se:6.3f} {z:+6.2f}   {tail}")
        out[name] = dict(m=m, se=se, n=n, ts=ts)
    return out


def main():
    argv = [a for a in sys.argv[1:] if a in TFS]
    tfs = argv or list(TFS)
    for tf in tfs:
        LOADED[tf] = load(tf)
        if not LOADED[tf]:
            print(f"{tf}: no cached candles. Run undertow_sweep.py --fetch.")
            return 2

    evens = [s for i, s in enumerate(SYMBOLS) if i % 2 == 0]
    odds = [s for i, s in enumerate(SYMBOLS) if i % 2 == 1]

    print("UNDERTOW EXIT MODELS — is the exit the bug?")
    print("prereg: indicators/undertow/prereg/PREREG_undertow_exits.md")
    print(f"entries FROZEN: {BASE.tag()} maxLive {BASE.maxLive}")
    print(f"horizon {HORIZON} bars, marked to market if unresolved; "
          f"fees {FEE * 1e4:.0f}bp; stop identical in every arm")

    picks = []
    for tf in tfs:
        tr = panel(tf, [(s, True) for s in evens], "TRAIN — even symbols, older half")
        if not tr:
            continue
        best = max((n for n in TRADEABLE if n != "E1 fixed 3R"),
                   key=lambda n: tr[n]["m"])
        print(f"\n  CARRIED OVER: {best}   (train {tr[best]['m']:+.3f})")
        ho = panel(tf, [(s, False) for s in odds],
                   "HOLDOUT — odd symbols, newer half — scored once")
        if not ho:
            continue
        a, b = ho[best], ho["E1 fixed 3R"]
        dm = a["m"] - b["m"]
        dse = math.sqrt(a["se"] ** 2 + b["se"] ** 2)
        z = dm / dse if dse else 0.0
        bars = [a["n"] >= 300, dm >= 0.15 and abs(z) >= 2.0, a["m"] > 0]
        print(f"\n  HOLDOUT VERDICT for {best}")
        print(f"    1 coverage        {a['n']} trades        "
              f"{'PASS' if bars[0] else 'FAIL — a bound, not a verdict'}")
        print(f"    2 beats fixed 3R  {dm:+.3f} +/- {dse:.3f} (z {z:+.2f})  "
              f"{'PASS' if bars[1] else 'FAIL'}")
        print(f"    3 positive        {a['m']:+.3f} R            "
              f"{'PASS' if bars[2] else 'FAIL'}")
        print(f"    ceiling (E7)      {ho['E7 MFE oracle']['m']:+.3f} R — "
              f"{best} captures "
              f"{100 * a['m'] / ho['E7 MFE oracle']['m']:.0f}% of it"
              if ho["E7 MFE oracle"]["m"] > 0 else "")
        picks.append(dict(tf=tf, best=best, m=a["m"], se=a["se"], n=a["n"],
                          d=dm, z=z, bars=bars,
                          e1=b["m"], ceil=ho["E7 MFE oracle"]["m"]))

    print(f"\n{'=' * 78}\nVERDICT\n{'=' * 78}\n")
    print(f"  {'tf':8} {'exit':20} {'holdout':>8} {'fixed 3R':>9} "
          f"{'delta':>8} {'z':>6} {'ceiling':>8}")
    for p in picks:
        print(f"  {p['tf']:8} {p['best']:20} {p['m']:+8.3f} {p['e1']:+9.3f} "
              f"{p['d']:+8.3f} {p['z']:+6.2f} {p['ceil']:+8.3f}")
    pos = [p for p in picks if p["m"] > 0]
    print(f"\n  5 NOT ONE TIMEFRAME  {len(pos)} of {len(picks)} positive   "
          f"{'PASS' if len(pos) >= 2 else 'FAIL'}")
    win = [p for p in picks if all(p["bars"])]
    print()
    if len(pos) >= 2 and win:
        print("  A RUNNER EXIT BEATS THE FIXED ONE on: "
              + ", ".join(p["tf"] for p in win))
        print("  Bar 4 -- beating the same exit applied to a RANDOM entry -- is")
        print("  not scored here and is what decides whether this is Undertow")
        print("  or just the market. It needs its own run.")
    else:
        print("  NO RUNNER EXIT CLEARS THE BARS.")
        print("  Then the exit is not the explanation, and the next thing to")
        print("  test is the BACKUP FILL -- `gone` and `back` are the two")
        print("  largest no-entry buckets and the spec has always said so.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
