"""Portfolio rules: concurrency, correlation, daily loss limits, priority.

The signal work is done — twenty-one entry ideas flat, stop placement already
optimal, exits already near-optimal. What is left is the layer above: how many
positions at once, which ones when there is not room for all, and when to stop
for the day. The loser diagnosis pointed here (27% of confirmed losers fall on
five days out of forty-two) and so did the 300 USDT simulation (450-950
signals skipped because margin was committed).

Judged on return per unit of drawdown, not return. A strategy that doubles
with a 50% drawdown is worse than one that gains 60% with 8%, because the
first one is untradeable by a human and unfundable by anyone else.

    PYTHONPATH=. python3 research/studies/portfolio.py
"""
import research.env                                     # noqa: F401  MUST be first
import asyncio, time                                    # noqa: E402
from bisect import bisect_right                         # noqa: E402
from dataclasses import dataclass                       # noqa: E402

import aiohttp                                          # noqa: E402
from riptide.config import BAR_SECONDS, BTC_REGIME_INTERVAL, TRACK_TARGET_R  # noqa: E402
from riptide.exchange import fetch_candles              # noqa: E402
from riptide.trend import supertrend                    # noqa: E402
from research.data import load                          # noqa: E402

START, LEVERAGE = 300.0, 10.0
BTC = {}


def btc_ok(r):
    got = BTC.get("x")
    if not got:
        return True
    t, st = got
    j = bisect_right(t, r.candles[r.bar].t - BAR_SECONDS[BTC_REGIME_INTERVAL]) - 1
    return True if not (0 <= j < len(st) and st[j]) else (st[j] > 0) == r.signal.is_long


@dataclass
class Rules:
    name: str
    max_open: int = 99
    max_same_dir: int = 99          # correlation cap: N longs OR N shorts
    reserve_confirmed: int = 0      # slots only a confirmed setup may use
    daily_loss_stop: float = 0.0    # halt new entries after losing this % of
                                    # the day's opening balance
    risk_pct: float = 1.0
    compound: bool = True
    early_needs_btc: bool = False


def simulate(rows, rk: Rules):
    # Sort on (time, kind, seq) — a Row is not orderable, and letting the
    # tuple fall through to it would compare objects and raise. seq keeps the
    # order stable so a rerun cannot silently reshuffle a tie.
    events = []
    for n, r in enumerate(rows):
        if r.filled and r.exit_time:
            events.append((r.fill_time, 1, n, r))   # 1 sorts after 0: close first
            events.append((r.exit_time, 0, n, r))
    events.sort(key=lambda e: e[:3])

    bal = peak = START
    dd = 0.0
    open_pos, stake = {}, {}
    taken = wins = blocked = 0
    day = None
    day_open = START
    halted = False
    streak = worst_streak = 0

    for t, kind, _seq, r in events:
        d = time.gmtime(t).tm_yday
        if d != day:
            day, day_open, halted = d, bal, False

        if kind == 0:                              # close
            if id(r) not in open_pos:
                continue
            notional = stake.pop(id(r))
            open_pos.pop(id(r))
            bal += r.r * notional * (r.risk_pct / 100)
            if r.r > 0:
                wins += 1
                streak = 0
            else:
                streak += 1
                worst_streak = max(worst_streak, streak)
            peak = max(peak, bal)
            dd = max(dd, (peak - bal) / peak)
            if rk.daily_loss_stop and bal <= day_open * (1 - rk.daily_loss_stop / 100):
                halted = True
            if bal <= 0:
                return None
            continue

        if halted:
            blocked += 1
            continue
        if rk.early_needs_btc and r.kind == "early" and not btc_ok(r):
            blocked += 1
            continue
        limit = rk.max_open - (rk.reserve_confirmed if r.kind == "early" else 0)
        if len(open_pos) >= limit:
            blocked += 1
            continue
        same = sum(1 for p in open_pos.values() if p.signal.is_long == r.signal.is_long)
        if same >= rk.max_same_dir:
            blocked += 1
            continue
        base = bal if rk.compound else START
        notional = (base * rk.risk_pct / 100) / (r.risk_pct / 100)
        if (sum(stake.values()) + notional) / LEVERAGE > bal:
            blocked += 1
            continue
        open_pos[id(r)] = r
        stake[id(r)] = notional
        taken += 1

    return dict(name=rk.name, n=taken, win=100 * wins / max(taken, 1), bal=bal,
                ret=100 * (bal / START - 1), dd=100 * dd, blocked=blocked,
                streak=worst_streak,
                score=(100 * (bal / START - 1)) / max(100 * dd, 1))


async def main():
    rows = await load(target_r=TRACK_TARGET_R, fee_maker=0.02, fee_taker=0.06)
    async with aiohttp.ClientSession() as s:
        cs = await fetch_candles(s, "BTC_USDT", BTC_REGIME_INTERVAL)
        if len(cs) > 40:
            BTC["x"] = ([c.t for c in cs], supertrend(cs))
    span = (rows[0].candles[-1].t - rows[0].candles[0].t) / 86400
    print(f"{START:.0f} USDT · {LEVERAGE:g}x · target {TRACK_TARGET_R:g}R · "
          f"{span:.1f} days · maker/taker fees\n"
          f"'ret/DD' is return divided by max drawdown — the column that matters.\n")

    tests = [
        Rules("everything, no rules"),
        Rules("max 12 open", max_open=12),
        Rules("max 8 open", max_open=8),
        Rules("max 5 open", max_open=5),
        Rules("max 3 open", max_open=3),
        Rules("max 8, max 5 same direction", max_open=8, max_same_dir=5),
        Rules("max 8, max 3 same direction", max_open=8, max_same_dir=3),
        Rules("max 8, 3 slots for confirmed", max_open=8, reserve_confirmed=3),
        Rules("max 8, early needs BTC", max_open=8, early_needs_btc=True),
        Rules("max 8, stop day at -4%", max_open=8, daily_loss_stop=4),
        Rules("max 8, stop day at -6%", max_open=8, daily_loss_stop=6),
        Rules("max 8, stop day at -10%", max_open=8, daily_loss_stop=10),
        Rules("ALL RULES", max_open=8, max_same_dir=3, reserve_confirmed=2,
              daily_loss_stop=6, early_needs_btc=True),
        Rules("ALL RULES, flat sizing", max_open=8, max_same_dir=3,
              reserve_confirmed=2, daily_loss_stop=6, early_needs_btc=True,
              compound=False),
        Rules("ALL RULES, risk 2%", max_open=8, max_same_dir=3,
              reserve_confirmed=2, daily_loss_stop=6, early_needs_btc=True,
              risk_pct=2.0),
        Rules("ALL RULES, risk 0.5%", max_open=8, max_same_dir=3,
              reserve_confirmed=2, daily_loss_stop=6, early_needs_btc=True,
              risk_pct=0.5),
    ]
    print(f"  {'rules':<34}{'trades':>7}{'win':>6}{'end':>9}{'ret':>8}"
          f"{'maxDD':>7}{'ret/DD':>8}{'lose run':>9}{'blocked':>9}")
    out = []
    for rk in tests:
        res = simulate(rows, rk)
        if res is None:
            print(f"  {rk.name:<34}  BLEW UP")
            continue
        out.append(res)
        print(f"  {res['name']:<34}{res['n']:>7}{res['win']:>5.0f}%"
              f"{res['bal']:>9.0f}{res['ret']:>+7.0f}%{res['dd']:>6.0f}%"
              f"{res['score']:>8.2f}{res['streak']:>9}{res['blocked']:>9}")
    best = sorted(out, key=lambda x: -x["score"])[:3]
    print("\n  best by return per unit of drawdown:")
    for b in best:
        print(f"    {b['name']:<34}{b['ret']:>+6.0f}% / {b['dd']:.0f}% DD"
              f"  = {b['score']:.2f}")

# Guarded so another study can import simulate() without running this whole
# report as a side effect. research/studies/phase2_rule.py reuses the
# simulator and got portfolio.py's entire output prepended to its own.
if __name__ == "__main__":
    asyncio.run(main())
