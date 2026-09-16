"""Can an exit rule rescue an entry with no edge?

Pre-registered in PREREG_ccp_exit_models.md, committed before this ran.

    python3 indicators/ccp/studies/ccp_exit_models.py

THE DESIGN: entry, stop and horizon are identical for every arm, so the arms
differ by their EXIT and nothing else. X1 and X3 are literally the same trade
scored two ways, which makes the comparison paired on the same grab and far
more powerful than the entry study's unpaired selection test.

    X1  2R target, no partial            the bridge to CCP_ENTRY_MODELS
    X2  1.5R target, no partial
    X3  50% off at 1.5R, stop to BE, rest to 2R     the model asked for

    C1/C2/C3  the same three exits on a seeded random bar

The C arms are the bar that matters. If X3 beats X1 by the same margin that C3
beats C1, the partial is a property of the exit on any path and says nothing
about grabs.
"""
from __future__ import annotations

import asyncio
import collections
import math
import os
import random
import sys

import aiohttp

sys.path.insert(0, ".")

os.environ.setdefault("RIPTIDE_DEEP_CACHE", ".cache/deep")
os.makedirs(os.environ["RIPTIDE_DEEP_CACHE"], exist_ok=True)

from research.data import SYMBOLS                        # noqa: E402
from research.deep import load_universe                  # noqa: E402
from research.harness import simulate_market, FEE_MAKER  # noqa: E402
from indicators.ccp.tools.ccp_merge_check import atr14  # noqa: E402
from indicators.ccp.tools.ccp_at_grabs_check import grabs  # noqa: E402

PIVOT = 3
CCP_BACK = CCP_FWD = 2
ATR_BUF = 0.25                 # the stop sits PAST the wick by this much ATR
MIN_BETS = 200                 # bar 1
MDE_CEILING = 0.10             # bar: tighter than the entry study, pairing helps
RANDOM_SPAN = 20
DAYS = 333
TFS = (("Min15", 192), ("Min30", 96), ("Min60", 48))

# (id, kwargs for simulate_market). Fixed by the prereg; no arm gets a fourth.
EXITS = (
    ("X1", dict(target_r=2.0)),
    ("X2", dict(target_r=1.5)),
    ("X3", dict(target_r=2.0, part_at_r=1.5, part_to_r=2.0, be_lock_r=0.0)),
)
PARTIAL_ARMS = {"X3"}


def clustered(vals, keys) -> tuple[float, float, int]:
    """Mean and a cluster-robust SE, clustering by key. Prereg's primary SE."""
    n = len(vals)
    if n < 2:
        return (vals[0] if vals else 0.0), float("inf"), n
    m = sum(vals) / n
    by = collections.defaultdict(list)
    for v, k in zip(vals, keys):
        by[k].append(v - m)
    g = len(by)
    if g < 2:
        return m, float("inf"), n
    meat = sum(sum(d) ** 2 for d in by.values())
    return m, math.sqrt(meat * g / max(g - 1, 1)) / n, n


def build(cs, a, tf: str, sym: str, horizon: int) -> list[dict]:
    """One row per grab, carrying every arm's R for the SAME trade."""
    out = []
    for pv, gb, is_high in grabs(cs, PIVOT, PIVOT):
        sig = gb + CCP_FWD
        lo_i, hi_i = gb - CCP_BACK, gb + CCP_FWD
        if lo_i < 0 or sig >= len(cs) - 1:
            continue
        if a[sig] is None:
            continue
        is_long = not is_high
        entry = cs[sig].c
        # PAST the wick by ATR_BUF, not floored at it. The prereg records this
        # as the one difference from the entry study, and X1 is the bridge.
        buf = a[sig] * ATR_BUF
        stop = (min(cs[k].l for k in range(lo_i, hi_i + 1)) - buf if is_long
                else max(cs[k].h for k in range(lo_i, hi_i + 1)) + buf)
        if (stop >= entry) if is_long else (stop <= entry):
            continue

        row = {"sym": sym, "t": cs[sig].t,
               "risk_pct": 100.0 * abs(entry - stop) / entry}
        ok = True
        for name, kw in EXITS:
            o = simulate_market(cs, sig, entry, stop, is_long,
                                horizon_bars=horizon, **kw)
            if o is None:
                ok = False
                break
            row[name] = o.r
            row[name + "_exit"] = o.exit
        if not ok:
            continue

        # The control: same direction, same risk FRACTION, a random bar.
        rnd = random.Random(f"{sym}|{tf}|{gb}")
        row["ctl"] = False
        frac = abs(entry - stop) / entry
        for _ in range(4):
            j = rnd.randrange(CCP_BACK + 20, len(cs) - horizon - 1)
            if a[j] is None:
                continue
            e2 = cs[j].c
            s2 = e2 - e2 * frac if is_long else e2 + e2 * frac
            good = True
            for name, kw in EXITS:
                o = simulate_market(cs, j, e2, s2, is_long,
                                    horizon_bars=horizon, **kw)
                if o is None:
                    good = False
                    break
                row["C" + name[1:]] = o.r
            if good:
                row["ctl"] = True
            break
        out.append(row)
    return out


def corrected(rows, arm: str) -> list[float]:
    """Arm R with the prereg's fee correction applied to partial arms.

    simulate_market charges ONE fee per trade even when a partial is taken. A
    real partial exits twice, so half a maker leg is missing. Charging it in R
    means dividing by risk%, the same way the harness does.
    """
    if arm not in PARTIAL_ARMS:
        return [r[arm] for r in rows]
    return [r[arm] - 0.5 * FEE_MAKER / r["risk_pct"] for r in rows]


def panel(rows, label: str) -> dict:
    keys = [(r["sym"], r["t"] // 86400) for r in rows]
    print(f"  {label}   {len(rows)} bets")
    risk = sorted(r["risk_pct"] for r in rows)
    print(f"    median risk {risk[len(risk) // 2]:.2f}% of price")
    out = {}
    base = [r["X1"] for r in rows]
    for name, _ in EXITS:
        raw = [r[name] for r in rows]
        cor = corrected(rows, name)
        m, se, n = clustered(cor, keys)
        wins = sum(1 for v in raw if v > 0) / max(len(raw), 1)
        line = f"    {name}  R {m:+.3f} ± {se:.3f}   win {100*wins:4.1f}%"
        if name in PARTIAL_ARMS:
            mr = sum(raw) / len(raw)
            line += f"   (harness {mr:+.3f}, fee-corrected above)"
        if name != "X1":
            d = [c - b for c, b in zip(cor, base)]
            dm, dse, _ = clustered(d, keys)
            z = dm / dse if dse > 0 and not math.isinf(dse) else float("nan")
            line += f"\n         Δ vs X1 {dm:+.3f} ± {dse:.3f}  z {z:+.2f}"
            out[name] = (dm, dse, z, m, n)
        print(line)

    ctl = [r for r in rows if r["ctl"] and "C1" in r]
    if ctl:
        ck = [(r["sym"], r["t"] // 86400) for r in ctl]
        cb = [r["C1"] for r in ctl]
        print(f"    control, {len(ctl)} random bars")
        for name, _ in EXITS:
            cn = "C" + name[1:]
            cor = ([r[cn] - 0.5 * FEE_MAKER / r["risk_pct"] for r in ctl]
                   if name in PARTIAL_ARMS else [r[cn] for r in ctl])
            m, se, _ = clustered(cor, ck)
            extra = ""
            if name != "X1":
                d = [c - b for c, b in zip(cor, cb)]
                dm, dse, _ = clustered(d, ck)
                extra = f"   Δ vs C1 {dm:+.3f} ± {dse:.3f}"
                out[name + "_ctl"] = dm
            print(f"      {cn}  R {m:+.3f} ± {se:.3f}{extra}")
    print()
    return out


def stats_table(rows, keys, label: str) -> None:
    """The per-arm summary. R/bet is the only column that decides anything.

    Win rate and profit factor are here because they are what a partial
    changes: it buys a higher win rate with smaller wins, which looks like an
    improvement on every column except the one that matters.
    """
    print(f"  {label}   {len(rows)} bets")
    print(f"    {'arm':<5}{'bets':>7}{'win%':>7}{'R/bet':>9}{'SE':>7}"
          f"{'totR':>9}{'PF':>7}{'targ%':>7}{'stop%':>7}{'time%':>7}")
    print("    " + "-" * 72)
    for name, _ in EXITS:
        cor = corrected(rows, name)
        m, se, n = clustered(cor, keys)
        wins = [v for v in cor if v > 0]
        loss = [v for v in cor if v < 0]
        pf = (sum(wins) / abs(sum(loss))) if loss and sum(loss) else float("nan")
        ex = collections.Counter(r[name + "_exit"] for r in rows)
        d = max(len(rows), 1)
        print(f"    {name:<5}{n:>7}{100*len(wins)/d:>7.1f}{m:>9.3f}{se:>7.3f}"
              f"{sum(cor):>9.1f}{pf:>7.2f}"
              f"{100*ex['target']/d:>7.1f}{100*ex['stop']/d:>7.1f}"
              f"{100*ex['timeout']/d:>7.1f}")
    print()


async def main() -> None:
    print(__doc__.split("\n\n")[0])
    print(f"\n{len(SYMBOLS)} symbols, {DAYS} days, stop {ATR_BUF} ATR past the "
          f"grab wick, SE clustered by (symbol, day)\n")

    store: dict[str, list[dict]] = {}
    async with aiohttp.ClientSession() as sess:
        for tf, horizon in TFS:
            uni = await load_universe(sess, SYMBOLS, tf, DAYS)
            rows: list[dict] = []
            for sym, cs in uni.items():
                rows += build(cs, atr14(cs), tf, sym, horizon)
            rows.sort(key=lambda r: r["t"])
            store[tf] = rows
            print(f"{tf}: {len(uni)} symbols, {len(rows)} scored grabs")
    print()

    print("═══ STATS TABLE ═══")
    print("R/bet is the only column that decides anything. Win rate and profit")
    print("factor are here because a partial buys a higher win rate with")
    print("smaller wins — it improves every column except that one.\n")
    for tf, _ in TFS:
        rows = store[tf]
        if not rows:
            continue
        cut = len(rows) // 2
        for half, sl in (("OLDER", rows[:cut]), ("NEWER", rows[cut:])):
            k = [(r["sym"], r["t"] // 86400) for r in sl]
            stats_table(sl, k, f"{tf} {half}")

    res: dict[tuple[str, str], dict] = {}
    for tf, _ in TFS:
        rows = store[tf]
        if not rows:
            continue
        cut = len(rows) // 2
        print(f"═══ {tf} ═══")
        res[(tf, "old")] = panel(rows[:cut], "OLDER half")
        res[(tf, "new")] = panel(rows[cut:], "NEWER half")

    print("═══ VERDICT AGAINST THE PRE-REGISTERED BARS ═══")
    print("12 tests plus controls. At z >= 2.0 each the chance of at least one")
    print("false positive is about 45%, so bar 6 alone carries nothing.\n")
    for arm in ("X2", "X3"):
        signs, newer, cov, beats_ctl, mdes = set(), [], [], [], []
        for tf, _ in TFS:
            for half in ("old", "new"):
                p = res.get((tf, half), {})
                if arm not in p:
                    continue
                dm, dse, z, m, n = p[arm]
                cov.append(n >= MIN_BETS)
                signs.add(dm > 0)
                mdes.append(2 * dse)
                cd = p.get(arm + "_ctl")
                if cd is not None:
                    beats_ctl.append(dm > cd)
                print(f"      {tf} {half}: Δ {dm:+.3f}  z {z:+.2f}  "
                      f"R {m:+.3f}  n {n}"
                      + (f"  control Δ {cd:+.3f}" if cd is not None else ""))
                if half == "new":
                    newer.append((dm > 0, m > 0))
        b1 = bool(cov) and all(cov)
        b2 = len(signs) == 1
        b3 = bool(newer) and all(d for d, _ in newer)
        b4 = bool(newer) and all(r for _, r in newer)
        b5 = bool(beats_ctl) and all(beats_ctl)
        worst = max(mdes) if mdes else float("inf")
        print(f"  {arm}")
        for n_, ok, what in ((1, b1, f"{MIN_BETS}+ bets in every panel"),
                             (2, b2, "one sign across six panels"),
                             (3, b3, "beats the plain exit, newer half"),
                             (4, b4, "positive standalone R after the fee "
                                     "correction, newer half"),
                             (5, b5, "beats the plain exit by MORE than the "
                                     "random control does")):
            print(f"      bar {n_}  {'PASS' if ok else 'FAIL'}  {what}")
        print(f"      power   worst MDE {worst:.3f} R"
              + ("  UNDERPOWERED" if worst > MDE_CEILING else "  (adequate)"))
        print(f"      → {'PASSES' if all((b1,b2,b3,b4,b5)) else 'FAILS'}\n")


asyncio.run(main())
