"""What a 300 USDT account would have done on these signals.

An EQUITY simulation, not a trading system. There is no exchange key and no
order path anywhere in this project, and this changes nothing about that — it
replays recorded candles and arithmetic.

    PYTHONPATH=. python3 research/studies/equity.py
"""
import research.env                                     # noqa: F401  MUST be first
import asyncio                                          # noqa: E402
from bisect import bisect_right                         # noqa: E402

import aiohttp                                          # noqa: E402
from riptide.config import BAR_SECONDS, BTC_REGIME_INTERVAL, TRACK_TARGET_R  # noqa: E402
from riptide.exchange import fetch_candles              # noqa: E402
from riptide.trend import supertrend                    # noqa: E402
from research.data import load                          # noqa: E402

START = 300.0
RISK_PCT = 1.0            # of CURRENT balance, so it compounds
LEVERAGE = 10.0
BTC = {}


def btc_agrees(r):
    got = BTC.get("x")
    if not got:
        return None
    t, st = got
    j = bisect_right(t, r.candles[r.bar].t - BAR_SECONDS[BTC_REGIME_INTERVAL]) - 1
    return None if not (0 <= j < len(st) and st[j]) else (st[j] < 0) == r.signal.is_long


def run(rows, label, max_open=99, risk_pct=RISK_PCT):
    """Chronological replay. Risk is a share of the balance AT ENTRY, so it
    compounds; a trade that never fills costs nothing and blocks nothing.

    max_open is the real constraint a 300 USDT account hits. Notional is
    risk / stop%, so a 1% risk on a 1.24% stop is 242 USDT of position — at
    10x that is 24 USDT of margin, and twenty of those do not fit.
    """
    events = []
    for r in rows:
        if not r.filled or not r.exit_time:
            continue
        events.append((r.fill_time, "open", r))
        events.append((r.exit_time, "close", r))
    events.sort(key=lambda e: (e[0], e[1] == "open"))

    bal, peak, dd = START, START, 0.0
    open_now, staked, taken, skipped = {}, {}, 0, 0
    wins = 0
    margin_blocked = 0
    for t, kind, r in events:
        if kind == "open":
            if len(open_now) >= max_open:
                skipped += 1
                continue
            stake = bal * risk_pct / 100
            notional = stake / (r.risk_pct / 100)
            used = sum(staked.values())
            # margin actually available, at LEVERAGE
            if (used + notional) / LEVERAGE > bal:
                margin_blocked += 1
                continue
            open_now[id(r)] = r
            staked[id(r)] = notional
            taken += 1
        else:
            if id(r) not in open_now:
                continue
            stake = staked.pop(id(r)) * (r.risk_pct / 100)
            open_now.pop(id(r))
            bal += r.r * stake
            if r.r > 0:
                wins += 1
            peak = max(peak, bal)
            dd = max(dd, (peak - bal) / peak)
            if bal <= 0:
                print(f"  {label:<34}  BLEW UP after {taken} trades")
                return
    print(f"  {label:<34}{taken:>7}{100*wins/max(taken,1):>7.0f}%"
          f"{bal:>11.2f}{100*(bal/START-1):>+9.0f}%{100*dd:>8.0f}%"
          f"{skipped + margin_blocked:>9}")


async def main():
    rows = await load(target_r=TRACK_TARGET_R, fee_maker=0.02, fee_taker=0.06)
    async with aiohttp.ClientSession() as s:
        cs = await fetch_candles(s, "BTC_USDT", BTC_REGIME_INTERVAL)
        if len(cs) > 40:
            BTC["x"] = ([c.t for c in cs], supertrend(cs))
    span = (rows[0].candles[-1].t - rows[0].candles[0].t) / 86400

    print(f"{START:.0f} USDT · risk {RISK_PCT:g}% of balance per trade · "
          f"{LEVERAGE:g}x · target {TRACK_TARGET_R:g}R · {span:.1f} days\n"
          f"maker 0.02% / taker 0.06%. No slippage, no funding, no liquidation.\n")
    print(f"  {'strategy':<34}{'trades':>7}{'win':>7}{'end USDT':>11}"
          f"{'return':>9}{'maxDD':>8}{'skipped':>9}")

    conf = [r for r in rows if r.kind == "confirmed"]
    early = [r for r in rows if r.kind == "early"]
    ebtc = [r for r in early if btc_agrees(r) is True]

    run(conf, "confirmed only")
    run(early, "early only")
    run(ebtc, "early, BTC agrees only")
    run(conf + ebtc, "confirmed + early(BTC agrees)")
    run(rows, "everything")
    print()
    for cap in (3, 5, 10):
        run(conf + ebtc, f"confirmed + early(BTC), max {cap} open", max_open=cap)
    print()
    for rp in (0.5, 2.0, 3.0):
        run(conf + ebtc, f"confirmed + early(BTC), risk {rp:g}%", risk_pct=rp)

asyncio.run(main())
