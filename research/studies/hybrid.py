"""Hybrid alert policies on a 300 USDT account, and the evidence for regrading.

Two jobs, one data load, because they need exactly the same rows.

  1  THE CELL TABLE. Every signal falls into (timeframe, kind, daily POI,
     daily trend) — four binary-ish axes, all known at signal time, all
     individually measured. The table of R per cell is what a grade should be
     built from. The current GRADES table is built on daily DI plus an RSI
     tiebreak, which was the best available when it was written and is now
     two findings out of date.

  2  THE POLICY SIMULATION. A grade is only worth having if acting on it beats
     not acting on it, and at 300 USDT with 10x the binding constraint is
     margin, not signal quality — the portfolio study had to skip 450-950
     signals for want of a slot. So each policy is run through the same
     account simulation, judged on return per unit of drawdown.

WHAT A POLICY IS
----------------
A predicate over rows. "Send everything" is a policy. "30m confirmed always,
plus early only inside a daily POI" is a policy. The point is to find the
combination that uses the scarce slots on the best available signals, which is
NOT the same as the combination with the highest R per signal — a filter that
doubles quality and quarters volume can leave slots empty.

Fees are maker in / maker out on a win, maker in / taker out on a loss, as
everywhere else. Sizing is 1% of the compounding balance divided by the stop
distance; margin is checked against 10x.
"""
from __future__ import annotations

import research.env  # noqa: F401  (must precede riptide.config)

import asyncio
import statistics
import time
from dataclasses import dataclass

import aiohttp

from riptide.config import CFG, BAR_SECONDS
from riptide.engine import atr_series, run_engine
from riptide.trend import supertrend, di_direction
from research.data import SYMBOLS
from research.harness import mean_se, simulate as sim_trade
from research.studies.mtf_grid import (FEE, FILL_HOURS, HORIZON_HOURS,
                                       fetch_paged, zones_of, in_poi,
                                       htf_dir_at)

START, LEVERAGE, RISK_PCT = 300.0, 10.0, 1.0
HTF = "Day1"
TFS = ("Min30", "Min15")


@dataclass
class Row:
    symbol: str
    tf: str
    kind: str
    poi: bool
    trend: bool
    r: float
    filled: bool
    risk_pct: float
    fill_time: int
    exit_time: int
    is_long: bool


async def gather():
    rows: list[Row] = []
    async with aiohttp.ClientSession() as sess:
        for sym in SYMBOLS:
            try:
                hcs = await fetch_paged(sess, sym, HTF, 1)
            except Exception:
                continue
            if len(hcs) < 60:
                continue
            zones = zones_of(hcs, atr_series(hcs, CFG.atr_len))
            hst, hdi = supertrend(hcs), di_direction(hcs)
            for tf in TFS:
                try:
                    cs = await fetch_paged(sess, sym, tf, 1)
                except Exception:
                    continue
                if len(cs) < 300:
                    continue
                step = BAR_SECONDS[tf]
                fill = FILL_HOURS * 3600 // step
                hor = HORIZON_HOURS * 3600 // step
                idx = {c.t: i for i, c in enumerate(cs)}
                early: list = []
                setups = run_engine(sym, cs, CFG, early_out=early)
                for kind, sigs in (("confirmed", setups), ("early", early)):
                    for x in sigs:
                        i = idx.get(x.detected_time)
                        if i is None:
                            continue
                        o = sim_trade(cs, i, x.entry, x.stop, x.is_long,
                                      fill_bars=fill, horizon_bars=hor, **FEE)
                        # An unfinished trade at the end of the data would be
                        # scored as a timeout at whatever price the fetch
                        # happened to stop on.
                        if o.filled and o.exit_bar is None:
                            continue
                        rows.append(Row(
                            symbol=sym, tf=tf, kind=kind,
                            poi=in_poi(zones, cs[i].t, x.stop, x.is_long,
                                       BAR_SECONDS[HTF]),
                            trend=htf_dir_at(hcs, hst, hdi, cs[i].t)
                            == (1 if x.is_long else -1),
                            r=o.r, filled=o.filled,
                            risk_pct=100 * abs(x.entry - x.stop) / x.entry,
                            fill_time=cs[o.fill_bar].t if o.fill_bar else 0,
                            exit_time=cs[o.exit_bar].t if o.exit_bar else 0,
                            is_long=x.is_long))
    return rows


# ------------------------------------------------------------- the cell table

def cells(rows):
    print("\n" + "=" * 78)
    print("CELL TABLE — what a grade should actually be built from")
    print("=" * 78)
    print(f"  {'tf':<7}{'kind':<11}{'POI':<5}{'trend':<7}{'n':>6}"
          f"{'fill':>7}{'win':>7}{'R/signal':>18}")
    out = {}
    for tf in TFS:
        for kind in ("confirmed", "early"):
            for poi in (False, True):
                for tr in (False, True):
                    sub = [r for r in rows if r.tf == tf and r.kind == kind
                           and r.poi == poi and r.trend == tr]
                    if len(sub) < 25:
                        continue
                    rs = [r.r for r in sub]
                    m, se = mean_se(rs)
                    won = [r for r in sub if r.filled]
                    win = sum(r.r > 0 for r in won) / len(won) if won else 0
                    fillr = sum(r.filled for r in sub) / len(sub)
                    out[(tf, kind, poi, tr)] = (m, se, len(sub))
                    print(f"  {tf:<7}{kind:<11}{'yes' if poi else 'no':<5}"
                          f"{'yes' if tr else 'no':<7}{len(sub):>6}"
                          f"{fillr:>6.0%}{win:>7.0%}{m:>+11.3f} ± {se:.3f}")
    return out


# ------------------------------------------------------------ account sim

@dataclass
class Policy:
    name: str
    pick: object                    # row -> bool
    max_open: int = 8
    reserve_confirmed: int = 2
    one_per_symbol: bool = True     # see account()


def account(rows, pol: Policy):
    sel = [r for r in rows if pol.pick(r)]
    events = []
    for n, r in enumerate(sel):
        if r.filled and r.exit_time:
            events.append((r.fill_time, 1, n, r))
            events.append((r.exit_time, 0, n, r))
    events.sort(key=lambda e: e[:3])

    bal = peak = START
    dd = 0.0
    open_pos, stake = {}, {}
    taken = wins = blocked = 0
    for t, ev, _n, r in events:
        if ev == 0:
            if id(r) not in open_pos:
                continue
            notional = stake.pop(id(r))
            open_pos.pop(id(r))
            bal += r.r * notional * (r.risk_pct / 100)
            wins += r.r > 0
            peak = max(peak, bal)
            dd = max(dd, (peak - bal) / peak)
            if bal <= 0:
                return None
            continue
        # A 30m early and a 15m early on the same symbol at the same time are
        # the same idea twice, not two positions. Without this the multi-
        # timeframe policies get a free doubling of size on exactly the moves
        # both charts agree about, which flatters them precisely where they
        # are meant to be compared against the single-timeframe ones.
        if pol.one_per_symbol and any(p.symbol == r.symbol
                                      for p in open_pos.values()):
            blocked += 1
            continue
        limit = pol.max_open - (pol.reserve_confirmed
                                if r.kind == "early" else 0)
        if len(open_pos) >= limit:
            blocked += 1
            continue
        notional = (bal * RISK_PCT / 100) / (r.risk_pct / 100)
        if (sum(stake.values()) + notional) / LEVERAGE > bal:
            blocked += 1
            continue
        open_pos[id(r)] = r
        stake[id(r)] = notional
        taken += 1
    return dict(name=pol.name, alerts=len(sel), n=taken,
                win=100 * wins / max(taken, 1), bal=bal,
                ret=100 * (bal / START - 1), dd=100 * dd, blocked=blocked,
                score=(100 * (bal / START - 1)) / max(100 * dd, 1))


def main():
    rows = asyncio.run(gather())
    span = 41.0
    n30 = sum(r.tf == "Min30" for r in rows)
    print(f"\nloaded {len(rows)} signals ({n30} on Min30, {len(rows) - n30} "
          f"on Min15) across {len(SYMBOLS)} symbols")
    cells(rows)

    m30 = lambda r: r.tf == "Min30"
    pol = [
        Policy("A  everything, 30m only (shipped)",
               lambda r: m30(r)),
        Policy("B  30m confirmed only",
               lambda r: m30(r) and r.kind == "confirmed"),
        Policy("C  30m, POI required on both",
               lambda r: m30(r) and r.poi),
        Policy("D  30m confirmed all + 30m early in POI",
               lambda r: m30(r) and (r.kind == "confirmed" or r.poi)),
        Policy("E  D + 15m early in POI",
               lambda r: (m30(r) and (r.kind == "confirmed" or r.poi))
               or (r.tf == "Min15" and r.kind == "early" and r.poi)),
        Policy("F  E + 15m confirmed in POI",
               lambda r: (m30(r) and (r.kind == "confirmed" or r.poi))
               or (r.tf == "Min15" and r.poi)),
        Policy("G  both tf, POI required on everything",
               lambda r: r.poi),
        Policy("H  POI and trend on everything",
               lambda r: r.poi and r.trend),
        Policy("I  30m confirmed all + anything with POI+trend",
               lambda r: (m30(r) and r.kind == "confirmed")
               or (r.poi and r.trend)),
    ]
    print("\n" + "=" * 78)
    print(f"ACCOUNT SIMULATION — {START:.0f} USDT, {LEVERAGE:g}x, "
          f"{RISK_PCT:g}% risk, {span:.0f} days, max 8 open (2 reserved)")
    print("'ret/DD' is the column that matters, not 'ret'.")
    print("=" * 78)
    print(f"  {'policy':<38}{'alerts':>7}{'taken':>7}{'win':>6}{'end':>8}"
          f"{'ret':>8}{'maxDD':>7}{'ret/DD':>8}{'skipped':>9}")
    out = []
    for p in pol:
        res = account(rows, p)
        if res is None:
            print(f"  {p.name:<38}  BLEW UP")
            continue
        out.append(res)
        print(f"  {res['name']:<38}{res['alerts']:>7}{res['n']:>7}"
              f"{res['win']:>5.0f}%{res['bal']:>8.0f}{res['ret']:>+7.0f}%"
              f"{res['dd']:>6.0f}%{res['score']:>8.2f}{res['blocked']:>9}")
    print("\n  the same policies WITHOUT the one-position-per-symbol rule,")
    print("  to show what double-counting the same move is worth:")
    for p in pol:
        p2 = Policy(p.name, p.pick, p.max_open, p.reserve_confirmed, False)
        res = account(rows, p2)
        if res:
            print(f"  {res['name']:<38}{res['alerts']:>7}{res['n']:>7}"
                  f"{res['win']:>5.0f}%{res['bal']:>8.0f}{res['ret']:>+7.0f}%"
                  f"{res['dd']:>6.0f}%{res['score']:>8.2f}{res['blocked']:>9}")

    best = sorted(out, key=lambda x: -x["score"])[:3]
    print("\n  best by return/drawdown: "
          + ", ".join(f"{b['name'].split()[0]} ({b['score']:.2f})"
                      for b in best))


if __name__ == "__main__":
    main()
