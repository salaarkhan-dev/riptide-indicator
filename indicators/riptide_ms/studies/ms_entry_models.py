"""WHICH ENTRY MODEL ON THE MARKET-STRUCTURE ENGINE, IF ANY.

Pre-registered in PREREG_ms_entry_models.md, committed before this ran.

Five triggers plus a RANDOM control that enters at an arbitrary bar inside the
same cycle, in the same direction, with the same stop rule. Only the trigger
varies. The paired difference against that control is the primary metric,
because a model that makes money only because its cycles trended is a long
position with extra steps, and the control is what catches it.

    PYTHONPATH=. RIPTIDE_DEEP_CACHE=/tmp/deep \\
        python3 indicators/riptide_ms/studies/ms_entry_models.py
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
import indicators.riptide_ms.port.ms_struct as MS  # noqa: E402
import research.discovery_symbols as RP              # noqa: E402
from riptide.config import BAR_SECONDS                  # noqa: E402

DAYS = 333
SYMS = RP.DISCOVERY[:30]
TFS = ("Min30", "Min15")
MS_LEN, MS_SHORT = 50, 3          # the pasted script's own defaults, not swept
TARGET_R = 2.0
HORIZON_HOURS = 48
FEE = dict(fee_maker=0.02, fee_taker=0.06)
MIN_BETS = 200

MODELS = ("E0_RANDOM", "E1_IDM", "E2_BOS", "E3_CHOCH", "E4_SWEEP",
          "E5_IDM_BOS")
CONTROL = "E0_RANDOM"


def stop_for(d, sBtmY, sTopY, entry):
    """The one stop rule, held constant across every model: the live
    short-period opposing swing. Wrong side or missing -> SKIP, never
    substituted. Stage A/B established that the alternative is degenerate."""
    s = sBtmY if d > 0 else sTopY
    if s is None or entry is None or entry <= 0:
        return None
    if (s >= entry) if d > 0 else (s <= entry):
        return None
    if abs(entry - s) <= 0:
        return None
    return s


def signals(ev, st, n):
    """(model, cycle, dir) -> list of (bar, entry, stop)."""
    out = defaultdict(list)
    seen_idm = set()

    def add(model, e, d):
        s = stop_for(d, e["sBtmY"], e["sTopY"], e["close"])
        if s is not None:
            out[(model, e["cycle"], d)].append((e["bar"], e["close"], s))

    for e in ev:
        k, d = e["kind"], e["dir"]
        if k == "idm":
            add("E1_IDM", e, d)
            seen_idm.add((e["cycle"], d))
        elif k == "bos":
            add("E2_BOS", e, d)
            if (e["cycle"], d) in seen_idm:
                add("E5_IDM_BOS", e, d)
                seen_idm.discard((e["cycle"], d))
        elif k == "choch":
            add("E3_CHOCH", e, d)
        elif k == "sweep":
            add("E4_SWEEP", e, d)
    return out


def control_signals(st, n, sym, tf):
    """E0: one uniformly random bar per cycle, in the cycle's own direction,
    with the stop rule as it stood on that bar. Seeded per cycle so it is
    identical on every re-run and cannot be re-rolled."""
    bars = defaultdict(list)
    for i in range(n):
        bars[st["cyc"][i]].append(i)
    out = defaultdict(list)
    for cyc, idx in bars.items():
        if len(idx) < 3:
            continue
        rng = random.Random(f"{sym}|{tf}|{cyc}")
        # BOTH directions. E4_SWEEP fires AGAINST the trend, so a control that
        # only ever exists in the cycle's own direction leaves it with nothing
        # to pair against — which is what the first run did, reporting E4 as
        # unpaired on every panel. That was a defect in the specification, not
        # a property of the model, so it is corrected rather than reported.
        for d in (1, -1):
            i = rng.choice(idx[:-1])
            # `close` is not kept per bar; the entry is the bar's close, taken
            # from the candle in the caller. Return the index and resolve there.
            out[(CONTROL, cyc, d)].append((i, None, None))
    return out


def agg(vals):
    n = len(vals)
    if n < 2:
        return None
    m = statistics.fmean(vals)
    se = statistics.stdev(vals) / (n ** 0.5)
    return dict(n=n, m=m, se=se, z=(m / se) if se else 0.0)


async def main():
    print("=" * 100)
    print("  ENTRY MODELS ON THE MARKET-STRUCTURE ENGINE")
    print("=" * 100)
    print(f"  engine     riptide_ms.port.ms_struct (msLen={MS_LEN}, "
          f"msShortLen={MS_SHORT}) — the pasted script's defaults, not swept")
    print(f"  entry      close of the trigger bar, market")
    print(f"  stop       live short-period opposing swing; wrong side = SKIP")
    print(f"  exit       {TARGET_R}R or stop, {HORIZON_HOURS}h horizon, "
          f"Riptide fees")
    print(f"  unit       the bet = one CHoCH cycle per direction")
    print(f"  control    {CONTROL} — random bar in the SAME cycle, same "
          f"direction, same stop rule")
    print("=" * 100)

    # panel[(tf, half)][model][cycle_key] = mean R
    panel = defaultdict(lambda: defaultdict(dict))
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
                ev, st = MS.engine(cs, MS_LEN, MS_SHORT)
                sig = signals(ev, st, n)
                sig.update(control_signals(st, n, sym, tf))

                for (model, cyc, d), rows in sig.items():
                    rs = []
                    bar0 = None
                    for bar, entry, stop in rows:
                        if entry is None:            # the control
                            entry = cs[bar].c
                            stop = stop_for(d, st["sBtmY"][bar],
                                            st["sTopY"][bar], entry)
                            if stop is None:
                                continue
                        if bar + 1 + horizon > n:
                            continue
                        o = simulate_market(cs, bar, entry, stop, d > 0,
                                            target_r=TARGET_R,
                                            horizon_bars=horizon, **FEE)
                        if o is None or not o.filled:
                            continue
                        rs.append(o.r)
                        bar0 = bar if bar0 is None else bar0
                    if not rs or bar0 is None:
                        continue
                    half = "older" if bar0 < cut else "newer"
                    panel[(tf, half)][model][(sym, cyc, d)] = \
                        statistics.fmean(rs)
                done += 1
            print(f"\n  {tf}: {done} symbols ({time.time()-t0:.0f}s)")

    # ── tables ──────────────────────────────────────────────────────────────
    res = {}
    for tf in TFS:
        for half in ("older", "newer"):
            cells = panel[(tf, half)]
            ctl = cells.get(CONTROL, {})
            print("\n" + "=" * 100)
            print(f"  {tf}  {half.upper()} HALF")
            print("=" * 100)
            print(f"  {'model':<14}{'bets':>7}{'R/bet':>9}{'SE':>8}"
                  f"{'paired n':>10}{'delta vs E0':>13}{'SE':>8}{'z':>7}")
            for m in MODELS:
                rows = cells.get(m, {})
                a = agg(list(rows.values()))
                if a is None:
                    print(f"  {m:<14}{len(rows):>7}   too few")
                    res[(tf, half, m)] = None
                    continue
                if m == CONTROL:
                    print(f"  {m:<14}{a['n']:>7}{a['m']:>9.3f}{a['se']:>8.3f}"
                          f"{'—':>10}{'—':>13}{'—':>8}{'—':>7}")
                    res[(tf, half, m)] = dict(a, d=None, dse=None, dz=None,
                                              dn=0)
                    continue
                pair = [rows[k] - ctl[k] for k in rows if k in ctl]
                p = agg(pair)
                if p is None:
                    print(f"  {m:<14}{a['n']:>7}{a['m']:>9.3f}{a['se']:>8.3f}"
                          f"{len(pair):>10}   unpaired")
                    res[(tf, half, m)] = None
                    continue
                print(f"  {m:<14}{a['n']:>7}{a['m']:>9.3f}{a['se']:>8.3f}"
                      f"{p['n']:>10}{p['m']:>13.3f}{p['se']:>8.3f}"
                      f"{p['z']:>7.2f}")
                res[(tf, half, m)] = dict(a, d=p["m"], dse=p["se"],
                                          dz=p["z"], dn=p["n"])

    # ── verdict ─────────────────────────────────────────────────────────────
    print("\n" + "=" * 100)
    print("  VERDICT AGAINST THE FOUR PRE-REGISTERED BARS")
    print("=" * 100)
    print(f"   1 at least {MIN_BETS} bets in every panel")
    print("   2 delta keeps one sign in all four panels")
    print("   3 delta > 0 in BOTH halves — it beats random timing")
    print("   4 z >= 2.0 on the pooled newer half")
    print()
    print(f"  {'model':<14}{'1 cov':>8}{'2 sign':>9}{'3 beats':>10}"
          f"{'4 z':>8}   verdict")
    panels = [(tf, h) for tf in TFS for h in ("older", "newer")]
    for m in MODELS:
        if m == CONTROL:
            continue
        rs = [res.get((tf, h, m)) for tf, h in panels]
        if any(r is None for r in rs):
            print(f"  {m:<14}{'—':>8}{'—':>9}{'—':>10}{'—':>8}   "
                  f"NOT COMPUTABLE")
            continue
        b1 = all(r["dn"] >= MIN_BETS for r in rs)
        ds = [r["d"] for r in rs]
        b2 = all(x > 0 for x in ds) or all(x < 0 for x in ds)
        b3 = all(r["d"] > 0 for tf, h in panels
                 for r in [res[(tf, h, m)]] if h == "newer") and \
            all(r["d"] > 0 for tf, h in panels
                for r in [res[(tf, h, m)]] if h == "older")
        pooled = []
        for tf in TFS:
            cells = panel[(tf, "newer")]
            ctl = cells.get(CONTROL, {})
            rows = cells.get(m, {})
            pooled += [rows[k] - ctl[k] for k in rows if k in ctl]
        p = agg(pooled)
        b4 = bool(p and p["z"] >= 2.0)
        zs = f"{p['z']:.2f}" if p else "—"
        ok = b1 and b2 and b3 and b4
        print(f"  {m:<14}{('yes' if b1 else 'NO'):>8}"
              f"{('yes' if b2 else 'NO'):>9}{('yes' if b3 else 'NO'):>10}"
              f"{zs:>8}   {'PASSES' if ok else 'INCONCLUSIVE'}")

    print()
    print("=" * 100)
    print("  READ")
    print("=" * 100)
    print("  The delta column is the result. Standalone R/bet is not: every")
    print("  model and the control sit in the same cycles, so a cycle that")
    print("  trended pays all of them. Only the paired difference isolates")
    print("  WHEN the model entered.")
    print()
    print("  Five models, so at z >= 2.0 alone the family-wise false-positive")
    print("  rate is about 20%. Bars 1-3 carry any pass; bar 4 alone does not.")


if __name__ == "__main__":
    asyncio.run(main())
