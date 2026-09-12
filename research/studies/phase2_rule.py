"""WHICH SELECTION RULE SHOULD AN AUTOMATED BOT TRADE?

THE PROBLEM, AND IT IS A REAL ONE. This project has TWO selection rules, both
measured, both shipped, and they have never been run against each other:

  THE SLOT RULE (research/studies/portfolio.py, TRADING.md). Take everything
  the scanner sends, cap concurrent positions at 8, reserve 3 slots for
  confirmed setups. Judged on a 300 USDT account: return per unit of drawdown.

  THE PICK RULE (riptide/decide.py, research/studies/band_key.py). Name ONE 🎯
  per 120 minutes per direction, ranked slowest-timeframe > stop band >
  confirmed-before-early. Judged on R per trade and recovery factor.

A HUMAN CAN HOLD BOTH — read the 🎯, respect the slots. A BOT CANNOT. It needs
one rule that decides, per arriving signal, whether to place an order.

WHY THEY WERE NEVER COMPARED, which took a failed run to discover.
research.data.load() — the pipeline portfolio.py uses — fetches ONE interval
per symbol. It is single-timeframe by construction. The pick rule's FIRST
ranking key is "slowest timeframe first", so it cannot even be expressed
there: the dimension it sorts on does not exist in that harness. The two
headline numbers of this project therefore describe different universes:

    portfolio.py    ~42 days, ONE timeframe, account simulation
    band_key.py     333 days, THREE timeframes, R per trade

So this rebuilds the comparison on the DEEP pipeline — 333 days, 15m+30m+1h,
the same rows band_key and exhaustion already use — and runs the account
simulator over those. portfolio.simulate() is imported rather than copied, so
the judge is literally the same code; only the rows reaching it change.

A SECOND REASON NOT TO TRUST THE OLD NUMBER. Rerunning portfolio.py unchanged
today gives 5.47 ret/DD for "max 8, 3 slots for confirmed" where TRADING.md
records 3.67, and "everything, no rules" moved 1.30 -> 0.54. Same code, same
rules, a window that has slid forward. At ~42 days the LEVEL of this metric is
noise; only the ordering survived. That alone is a reason to re-measure on 333
days before wiring an account to it.

──────────────────────────────────────────────────────────────────────────────
PRE-REGISTERED, BEFORE THE FIRST NUMBER

  PRIMARY. Return per unit of maximum drawdown, at risk 0.5% (what phase 2
  will run) and 1.0% (what the existing numbers used). The comparison that
  decides phase 2 is arms 2-3 (slots) against arms 4-6 (pick, pick+slots).

  SECONDARY. Trade count. The pick rule takes far fewer trades, and fewer
  trades means longer before live data can confirm anything. A rule that wins
  on ret/DD while taking a third as many trades is worse for a bot that has to
  prove itself before being funded.

  THE 15m QUESTION, decisive for a bot and for nothing else. On the sent
  stream (fee_key.out) 15m is gross +0.0064 and NET -0.0268 over 4625 trades.
  A human quietly skips a bad-looking 15m alert; a bot takes every one. Arms
  7-8 drop 15m.

  BOTH HALVES for every arm. An edge living in one half is a non-result.

  WHAT WOULD FALSIFY THE PICK RULE FOR PHASE 2: ret/DD no better than the slot
  rule, or better on the whole window but reversing across the halves. That
  would mean decide.py is a reading aid for a human and the bot should trade
  slots — a surprising and useful answer.

    PYTHONPATH=. RIPTIDE_DEEP_CACHE=/tmp/deep \
        python3 research/studies/phase2_rule.py
"""
import research.env                                     # noqa: F401  MUST be first

import asyncio                                          # noqa: E402

import aiohttp                                          # noqa: E402

from riptide.config import BAR_SECONDS                  # noqa: E402
from research.deep import load_universe                 # noqa: E402
from research.studies.poi_tf import DAY, DAYS, H8       # noqa: E402
from research.studies.poi_tf import collect, context, universe  # noqa: E402
from research.studies.pick_rule import TFS, pick_rolling  # noqa: E402
from research.studies.band_key import COOLDOWN, KEYS    # noqa: E402
from research.studies.portfolio import Rules, simulate  # noqa: E402

SHIPPED = KEYS["A  tf > band > confd  (shipped)"]


class Sig:
    """The one field simulate() reads off .signal."""
    __slots__ = ("is_long",)

    def __init__(self, is_long):
        self.is_long = is_long


class Adapt:
    """A deep-pipeline T wearing the field names simulate() expects.

    An adapter rather than an edit to either side: portfolio.simulate stays the
    exact code that produced TRADING.md's table, and poi_tf's T stays the exact
    row band_key scored. If they are made to agree by changing one of them, the
    comparison stops being between the two shipped rules.
    """
    __slots__ = ("filled", "fill_time", "exit_time", "r", "risk_pct",
                 "kind", "signal", "tf", "src")

    def __init__(self, t):
        self.src = t
        self.filled = t.filled
        self.fill_time = t.fill_t or 0
        self.exit_time = t.exit_t or 0
        self.r = t.r
        self.risk_pct = t.risk_pct
        self.kind = t.kind
        self.tf = t.tf
        self.signal = Sig(t.is_long)


def no_15m(rows):
    return [r for r in rows if r.tf != "Min15"]


def halves(rows):
    """Split on fill time so both halves carry roughly equal ACTIVITY."""
    ok = sorted((r for r in rows if r.filled and r.exit_time),
                key=lambda r: r.fill_time)
    if not ok:
        return [], []
    mid = ok[len(ok) // 2].fill_time
    return ([r for r in rows if r.fill_time <= mid],
            [r for r in rows if r.fill_time > mid])


def build_arms(pick_set):
    """pick_set: the ids of rows decide.py would have tagged 🎯."""
    def only_picks(rows):
        return [r for r in rows if id(r.src) in pick_set]

    return [
        ("1  everything, no rules", lambda r: r, dict()),
        ("2  slots: max 8", lambda r: r, dict(max_open=8)),
        ("3  slots: max 8 + 3 confd", lambda r: r,
         dict(max_open=8, reserve_confirmed=3)),
        ("4  PICK only, no cap", only_picks, dict()),
        ("5  PICK + max 8", only_picks, dict(max_open=8)),
        ("6  PICK + max 8 + 3 confd", only_picks,
         dict(max_open=8, reserve_confirmed=3)),
        ("7  PICK + max 8, no 15m", lambda r: only_picks(no_15m(r)),
         dict(max_open=8)),
        ("8  slots max 8 + 3 confd, no 15m", no_15m,
         dict(max_open=8, reserve_confirmed=3)),
    ]


def header():
    print(f"  {'arm':<34}{'fed':>7}{'taken':>8}{'win':>6}{'ret':>8}"
          f"{'maxDD':>7}{'ret/DD':>8}{'blocked':>9}")


def run(rows, arms, risk):
    out = []
    for name, filt, rules in arms:
        sub = filt(rows)
        res = simulate(sub, Rules(name=name, risk_pct=risk, **rules))
        if res is None:
            print(f"  {name:<34}  BLEW UP")
            continue
        res["fed"] = len(sub)
        out.append(res)
        print(f"  {res['name']:<34}{res['fed']:>7}{res['n']:>8}"
              f"{res['win']:>5.0f}%{res['ret']:>+8.0f}%{res['dd']:>6.0f}%"
              f"{res['score']:>8.2f}{res['blocked']:>9}")
    return out


async def main():
    by_tf = {}
    async with aiohttp.ClientSession() as sess:
        syms = await universe(sess)
        zday = await context(sess, syms, DAY)
        z8h = await context(sess, syms, H8)
        for tf in TFS:
            cs = await load_universe(
                sess, syms, tf, DAYS,
                min_bars=int(0.8 * DAYS * 86400 // BAR_SECONDS[tf]))
            r = await collect(sess, cs, zday, z8h, interval=tf)
            by_tf[tf] = [t for t in r if t.filled and t.exit_t is not None]

    # The SENT stream: what the bot actually messages, POI required.
    sent = [t for tf in TFS for t in by_tf[tf] if t.day]
    pick_set = {id(t) for t in pick_rolling(sent, SHIPPED, COOLDOWN)}
    rows = [Adapt(t) for t in sent]
    arms = build_arms(pick_set)

    print("PHASE 2 — WHICH RULE SHOULD THE BOT TRADE?")
    print(f"{len(syms)} symbols · {DAYS} days · {'+'.join(TFS)} · 300 USDT · "
          f"10x · maker/taker fees")
    print(f"{len(sent)} signals sent · {len(pick_set)} would carry a 🎯 "
          f"({100 * len(pick_set) / max(len(sent), 1):.0f}%)\n")
    print("'fed' is how many rows the rule handed the account; 'taken' how")
    print("many it had room for. 'blocked' is the gap — the cost of the cap.\n")

    for risk in (0.5, 1.0):
        tag = "   <- what phase 2 will run" if risk == 0.5 else ""
        print(f"{'=' * 96}\nRISK {risk:g}% PER TRADE{tag}\n{'=' * 96}")
        header()
        out = run(rows, arms, risk)
        print("\n  best by return per unit of drawdown:")
        for b in sorted(out, key=lambda x: -x["score"])[:3]:
            print(f"    {b['name']:<34}{b['ret']:>+6.0f}% / {b['dd']:.0f}% DD"
                  f"  = {b['score']:.2f}  on {b['n']} trades")
        print()

    print(f"{'=' * 96}\nBOTH HALVES — an edge living in one half is a "
          f"non-result\n{'=' * 96}")
    first, second = halves(rows)
    for label, part in (("FIRST half", first), ("SECOND half", second)):
        print(f"\n  -- {label}, risk 0.5% --")
        header()
        run(part, arms, 0.5)

    print(f"\n{'=' * 96}\nTHE 15m QUESTION — a bot cannot quietly skip one"
          f"\n{'=' * 96}")
    print(f"  {'stream':<22}{'n':>7}{'net R/trade':>14}")
    for tf in TFS:
        allt = [r for r in rows if r.tf == tf]
        pck = [r for r in allt if id(r.src) in pick_set]
        for lab, grp in ((f"{tf} sent", allt), (f"{tf} PICKED", pck)):
            if grp:
                print(f"  {lab:<22}{len(grp):>7}"
                      f"{sum(g.r for g in grp) / len(grp):>+14.3f}")
    print("\n  fee_key.out, sent stream: 15m gross +0.0064 net -0.0268;")
    print("  30m +0.0486/+0.0255; 1h +0.0594/+0.0435. If 15m picks are")
    print("  negative too, the bot must not be given that timeframe at all.")


if __name__ == "__main__":
    asyncio.run(main())
