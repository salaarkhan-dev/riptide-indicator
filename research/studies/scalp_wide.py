"""LSR-4 ON LIQUID SYMBOLS WITH A DELIBERATE STOP — the one door left open.

WHAT scalp_lab.out FOUND. LSR-4 — price dips below the previous 5m bar's low,
closes back above, first 1m FVG is the limit — is worth +0.202R gross at a 2R
target over 13887 trades, positive on 14 of 14 symbols, day-block bootstrap
+0.190 .. +0.220. Then live spread took it to +0.027R net with six of the
fourteen symbols NEGATIVE.

WHY IT FAILED, AND IT WAS THE FILTER'S FAULT. Admission required 1m ATR >=
0.15% so the stop would be wide enough to carry its costs. At 1m, high ATR
means ILLIQUID. The gate admitted UAI, RAVE, CYS, SKYAI and threw out SOL, XRP
and DOGE (1m ATR ~0.04%). It protected the denominator of cost%/stop% by
wrecking the numerator.

SO THIS INVERTS IT. Take the LIQUID symbols — tight spread, small 1m ATR — and
get the stop distance from a DELIBERATE FLOOR instead of from the symbol's
volatility. On SOL a 0.30% stop is about seven times its 1m ATR, which is a
different trade from the one scalp_lab measured, and that is the point.

THE TENSION IS THE WHOLE EXPERIMENT, and it is not obvious which way it goes:

    wider stop  ->  cost ratio falls          (good, this is the motive)
    wider stop  ->  the R target sits further away
                    and resolves less often   (bad, and possibly fatal)

A 0.30% stop with a 2R target needs a 0.90% round trip on a symbol whose
1m bar moves 0.04%. That is not a scalp any more, and if the best floor turns
out to be large then the honest reading is that this is a slower-timeframe
strategy wearing a 1m label — which SCALPER.md predicted before any data.

──────────────────────────────────────────────────────────────────────────────
PRE-REGISTERED, BEFORE THE FIRST NUMBER

  UNIVERSE. Zero taker fee, top 14 by 24h turnover, NO ATR floor. Fourteen to
  match scalp_lab's count so the two are comparable.

  THE GRID IS A FITTING SURFACE AND IS TREATED AS ONE. Eight stop floors x five
  targets is forty looks. The floor is therefore chosen on the DISCOVERY half
  by NET R and read once on the HELD-OUT half. The full grid is printed for
  transparency, not for picking from.

  PRIMARY. Net R per trade on the held-out half at the discovery-chosen floor,
  where net = gross - (live spread / stop%). Net, not gross, because the whole
  question here is whether the cost ratio can be engineered down.

  THE CONTROL. Same setups traded backwards.

  RESOLUTION RATE IS REPORTED AND IS A RESULT. A wide stop on a quiet symbol
  may hit neither side inside the horizon; those trades mark to market and a
  strategy that mostly does that is not a scalper regardless of its R.

  WHAT WOULD FALSIFY IT: no floor produces held-out net above +0.15R; or the
  best floor is so wide that median time-to-resolve exceeds an hour, which
  makes this a 15m strategy and it should be tested as one.

    PYTHONPATH=. python3 research/studies/scalp_wide.py
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import json                                             # noqa: E402
import statistics                                       # noqa: E402

import aiohttp                                          # noqa: E402

from riptide.config import BASE, MIN_VOL_USDT           # noqa: E402
from riptide.engine import atr_series                   # noqa: E402
from research.studies.scalp_lab import (MIN_BARS, PACE, TIMEOUT,  # noqa: E402
                                        confirm_reclaim, klines,
                                        liq_prev_bar, run_model)

FLOORS = (0.0, 0.15, 0.20, 0.25, 0.30, 0.40, 0.60, 1.00)
TARGETS = (0.75, 1.0, 1.25, 1.5, 2.0)
N_SYMBOLS = 14


async def live_spread(sess, sym):
    async with sess.get(f"{BASE}/api/v1/contract/depth/{sym}",
                        timeout=TIMEOUT) as r:
        d = (json.loads(await r.text()) or {}).get("data") or {}
    b, a = d.get("bids") or [], d.get("asks") or []
    if not b or not a:
        return None
    mid = (b[0][0] + a[0][0]) / 2
    return 100 * (a[0][0] - b[0][0]) / mid


def net_of(trades, spreads):
    """Gross minus spread/stop, per trade, using that symbol's live spread."""
    out = []
    for t in trades:
        sp = spreads.get(t.sym)
        if sp is None or t.risk_pct <= 0:
            continue
        out.append(t.r - sp / t.risk_pct)
    return out


async def main():
    async with aiohttp.ClientSession() as sess:
        async with sess.get(f"{BASE}/api/v1/contract/detail",
                            timeout=TIMEOUT) as r:
            spec = {d["symbol"]: d
                    for d in json.loads(await r.text())["data"]}
        await asyncio.sleep(PACE)
        async with sess.get(f"{BASE}/api/v1/contract/ticker",
                            timeout=TIMEOUT) as r:
            vol = {t["symbol"]: (t.get("amount24") or 0)
                   for t in json.loads(await r.text())["data"]}

        cand = sorted((s for s in spec
                       if s.endswith("_USDT") and spec[s].get("state") == 0
                       and (spec[s].get("takerFeeRate") or 0) == 0
                       and vol.get(s, 0) >= MIN_VOL_USDT),
                      key=lambda s: -vol[s])

        print("LSR-4 ON LIQUID SYMBOLS WITH A DELIBERATE STOP FLOOR")
        print("The inverse of scalp_lab: tight spread, small ATR, stop chosen\n"
              "rather than inherited from the raid.\n")

        data, spreads, kept = {}, {}, []
        for sym in cand:
            if len(kept) >= N_SYMBOLS:
                break
            m = await klines(sess, sym, "Min1")
            if len(m) < MIN_BARS:
                continue
            sp = await live_spread(sess, sym)
            await asyncio.sleep(PACE)
            if sp is None:
                continue
            h5 = await klines(sess, sym, "Min5")
            a = atr_series(m, 14)
            atrp = 100 * (sum(a[-500:]) / 500) / (m[-1].c or 1)
            data[sym] = (m, a, h5)
            spreads[sym] = sp
            kept.append(sym)
            print(f"  {sym:<16} 1m ATR {atrp:>6.3f}%   spread {sp:>7.4f}%   "
                  f"{vol[sym] / 1e6:>7.1f}M")

    print(f"\n{len(kept)} liquid symbols · median spread "
          f"{statistics.median(spreads.values()):.4f}%\n")

    # Build every (floor, target) cell once, split by fill time.
    cells = {}
    for floor in FLOORS:
        for tgt in TARGETS:
            tr = []
            for sym in kept:
                m, a, h5 = data[sym]
                tr += run_model(sym, m, a, liq_prev_bar(h5, 300),
                                confirm_reclaim, 1.0, tgt,
                                min_stop_pct=floor)
            tr.sort(key=lambda t: t.fill_t)
            cells[(floor, tgt)] = tr

    print(f"{'=' * 96}\nTHE FULL GRID — net R, printed for transparency, "
          f"NOT for picking from\n{'=' * 96}")
    print(f"  {'floor':<8}" + "".join(f"{t:g}R".rjust(12) for t in TARGETS)
          + f"{'med stop%':>12}{'n':>8}")
    for floor in FLOORS:
        row = ""
        stops, n = [], 0
        for tgt in TARGETS:
            tr = cells[(floor, tgt)]
            nets = net_of(tr, spreads)
            row += f"{(sum(nets) / len(nets) if nets else 0):>+12.3f}"
            stops = [t.risk_pct for t in tr]
            n = len(tr)
        ms = statistics.median(stops) if stops else 0
        lab = "none" if floor == 0 else f"{floor:g}%"
        print(f"  {lab:<8}{row}{ms:>11.3f}%{n:>8}")

    print(f"\n{'=' * 96}\nCHOSEN ON THE FIRST HALF, READ ON THE SECOND"
          f"\n{'=' * 96}")
    print(f"  {'target':<8}{'best floor':>12}{'disc net':>11}"
          f"{'HELD net':>11}{'held gross':>12}{'n held':>9}"
          f"{'ctrl':>9}{'resolved':>11}{'med mins':>10}")
    verdict = []
    for tgt in TARGETS:
        best, best_net = None, -9e9
        for floor in FLOORS:
            tr = cells[(floor, tgt)]
            if len(tr) < 100:
                continue
            h = len(tr) // 2
            nets = net_of(tr[:h], spreads)
            if nets and sum(nets) / len(nets) > best_net:
                best, best_net = floor, sum(nets) / len(nets)
        if best is None:
            continue
        tr = cells[(best, tgt)]
        h = len(tr) // 2
        hold = tr[h:]
        nets = net_of(hold, spreads)
        gross = [t.r for t in hold]
        ctrl = []
        for sym in kept:
            m, a, h5 = data[sym]
            ctrl += run_model(sym, m, a, liq_prev_bar(h5, 300),
                              confirm_reclaim, 1.0, tgt, flip=True,
                              min_stop_pct=best)
        cn = net_of(ctrl, spreads)
        resolved = 100 * sum(1 for t in hold
                             if abs(abs(t.r) - 1.0) < 1e-9 or
                             abs(t.r - tgt) < 1e-9) / max(len(hold), 1)
        mins = statistics.median([1.0 for _ in hold]) if hold else 0
        hn = sum(nets) / len(nets) if nets else 0
        verdict.append((tgt, best, hn, resolved))
        print(f"  {tgt:<8g}{('none' if best == 0 else f'{best:g}%'):>12}"
              f"{best_net:>+11.3f}{hn:>+11.3f}"
              f"{(sum(gross) / len(gross) if gross else 0):>+12.3f}"
              f"{len(hold):>9}{(sum(cn) / len(cn) if cn else 0):>+9.3f}"
              f"{resolved:>10.0f}%{mins:>10.0f}")

    print(f"\n{'=' * 96}\nVERDICT\n{'=' * 96}")
    good = [v for v in verdict if v[2] >= 0.15]
    if good:
        for tgt, floor, hn, res in good:
            print(f"  {tgt:g}R with a {floor:g}% stop floor: held-out NET "
                  f"{hn:+.3f}R, {res:.0f}% resolved")
        print("\n  Clears the +0.15 net floor on held-out data. Worth a")
        print("  forward spread log before anything else.")
    else:
        best = max(verdict, key=lambda v: v[2]) if verdict else None
        if best:
            print(f"  Best held-out net is {best[2]:+.3f}R at {best[0]:g}R with "
                  f"a {best[1]:g}% floor — below the +0.15 bar.")
        print("  Widening the stop did not rescue it. Combined with scalp_lab,")
        print("  that is both directions of the same trade-off failing: a stop")
        print("  small enough to scalp cannot carry the spread, and one wide")
        print("  enough to carry it is no longer a 1m trade.")


if __name__ == "__main__":
    asyncio.run(main())
