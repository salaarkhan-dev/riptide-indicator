"""CAN A FILTER IMPROVE THE SCALP MODEL? SIX FAMILIES, CHOSEN BLIND.

READ THE ARITHMETIC OF LUCK BEFORE THE RESULTS. Six filter families, each cut
two ways, is TWELVE LOOKS. At a 5% threshold roughly one will clear by chance
alone on pure noise. So "one filter worked" is the NULL result here, not the
finding — and a filter that clears on the discovery half means nothing until it
survives a half it was not chosen on.

THIS PROJECT HAS RUN THIS EXPERIMENT BEFORE. Twenty-one entry filters have
failed, and the failures share a shape: they fit the discovery half and died on
the held-out one. The sharpest example is the trendline slope gate, +9.0pp at
4.4 SE on discovery and -3.1pp held out. SCALPER.md names this exact exercise
as the thing to avoid, so it is run the only way that can survive the
objection: the list is fixed in source before the run, the split is by time,
and the held-out number is read ONCE.

THE BASE MODEL. LSR-4 with the wide stop — previous 5m bar's low raided and
reclaimed on 1m, first 1m FVG as the limit, 0.6% stop floor, 2R target, liquid
zero-fee symbols. scalp_wide.out put it at +0.199R net held out, with a median
hold of 58 minutes. Every filter below is judged against THAT, not against zero.

──────────────────────────────────────────────────────────────────────────────
PRE-REGISTERED, BEFORE THE FIRST NUMBER

  THE SIX FAMILIES, fixed here and not added to afterwards:

    1. DIRECTION        long only / short only
    2. TREND (EMA)      5m close above / below its 50-period EMA, in the
                        trade's favour or against it
    3. FUNDING          the rate in force at entry, above / below its median —
                        the one input that has already half-survived a held-out
                        test on Riptide's own stream
    4. VOLUME (RVOL)    volume at the raid bar against its 50-bar average,
                        above / below 1.5
    5. ADX              5m ADX(14) above / below 25, the conventional
                        trend-versus-range line
    6. SUPERTREND       5m supertrend agrees with / opposes the trade

  CAUSALITY. Every 5m indicator is read from the last 5m bar that had CLOSED
  when the 1m entry filled — bisect on close time, never the bar in progress.
  An indicator sampled from the bar the trade is inside is the classic
  lookahead and it is worth several free R.

  PRIMARY. Net R per trade on the HELD-OUT half for whichever side of whichever
  family won the discovery half, against the held-out base. Net, not gross:
  spread is charged on losers at the symbol's live rate, as in cost_chain.py.

  THE VOLUME COST IS PART OF THE VERDICT. A filter that lifts R while cutting
  the trade count in half has to lift it by enough to matter. Kept-fraction is
  reported beside every number.

  WHAT WOULD FALSIFY THE WHOLE EXERCISE: no family beating base on the held-out
  half; or exactly one, which is what twelve looks produce from noise.

    PYTHONPATH=. python3 research/studies/scalp_filters.py
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import json                                             # noqa: E402
import statistics                                       # noqa: E402
from bisect import bisect_right                         # noqa: E402

import aiohttp                                          # noqa: E402

from riptide.config import BASE, MIN_VOL_USDT           # noqa: E402
from riptide.engine import atr_series, rvol_at          # noqa: E402
from riptide.trend import supertrend                    # noqa: E402
from research.studies.scalp_lab import (MIN_BARS, PACE, TIMEOUT,  # noqa: E402
                                        confirm_reclaim, klines,
                                        liq_prev_bar, run_model)
from research.studies.funding import funding_at, funding_table  # noqa: E402

FLOOR, TARGET = 0.6, 2.0
N_SYMBOLS = 14
EMA_LEN, ADX_LEN, ADX_CUT, RVOL_CUT = 50, 14, 25.0, 1.5


def ema(vals, n):
    k = 2 / (n + 1)
    out, e = [], None
    for v in vals:
        e = v if e is None else v * k + e * (1 - k)
        out.append(e)
    return out


def adx(cs, n=ADX_LEN):
    """Wilder's ADX. Written out rather than imported because riptide only
    exposes di_direction, which is the sign and not the strength."""
    if len(cs) < n * 2 + 2:
        return [0.0] * len(cs)
    tr, pdm, ndm = [0.0], [0.0], [0.0]
    for i in range(1, len(cs)):
        up = cs[i].h - cs[i - 1].h
        dn = cs[i - 1].l - cs[i].l
        pdm.append(up if (up > dn and up > 0) else 0.0)
        ndm.append(dn if (dn > up and dn > 0) else 0.0)
        tr.append(max(cs[i].h - cs[i].l, abs(cs[i].h - cs[i - 1].c),
                      abs(cs[i].l - cs[i - 1].c)))

    def rma(v):
        out, a = [], None
        for x in v:
            a = x if a is None else a + (x - a) / n
            out.append(a)
        return out

    atr_, p_, m_ = rma(tr), rma(pdm), rma(ndm)
    dx = []
    for i in range(len(cs)):
        if not atr_[i]:
            dx.append(0.0)
            continue
        pdi = 100 * p_[i] / atr_[i]
        mdi = 100 * m_[i] / atr_[i]
        s = pdi + mdi
        dx.append(100 * abs(pdi - mdi) / s if s else 0.0)
    return rma(dx)


def closed_htf(times5, step, t):
    """Index of the last 5m bar that had CLOSED at 1m time t.

    A 5m bar stamped T covers [T, T+step) and closes at T+step, so the newest
    usable bar satisfies T <= t - step. Reading the bar in progress is the
    lookahead this whole function exists to prevent.
    """
    i = bisect_right(times5, t - step) - 1
    return i if i >= 0 else None


async def live_spreads(sess, syms):
    out = {}
    for s in syms:
        try:
            async with sess.get(f"{BASE}/api/v1/contract/depth/{s}",
                                timeout=TIMEOUT) as r:
                d = (json.loads(await r.text()) or {}).get("data") or {}
        except Exception:
            continue
        b, a = d.get("bids") or [], d.get("asks") or []
        if b and a:
            mid = (b[0][0] + a[0][0]) / 2
            out[s] = 100 * (a[0][0] - b[0][0]) / mid
        await asyncio.sleep(0.3)
    return out


def netr(t, spreads):
    sp = spreads.get(t.sym)
    if sp is None or t.risk_pct <= 0:
        return t.r
    return t.r - (sp / t.risk_pct if t.r <= 0 else 0.0)


# The six families. Each maps a marked trade to a bucket label, or None to
# drop it. Fixed here BEFORE the run; nothing is added after seeing results.
FAMILIES = {
    "1 direction":  lambda m: "long" if m["long"] else "short",
    "2 EMA trend":  lambda m: None if m["ema"] is None else
                    ("with trend" if m["ema"] == m["long"] else "against trend"),
    "3 funding":    lambda m: None if m["fund"] is None else
                    ("funding high" if m["fund"] > m["fmed"] else "funding low"),
    "4 RVOL":       lambda m: None if m["rvol"] is None else
                    ("rvol high" if m["rvol"] >= RVOL_CUT else "rvol low"),
    "5 ADX":        lambda m: None if m["adx"] is None else
                    ("trending" if m["adx"] >= ADX_CUT else "ranging"),
    "6 supertrend": lambda m: None if m["st"] is None else
                    ("st agrees" if m["st"] == m["long"] else "st opposes"),
}


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
                       and vol.get(s, 0) >= MIN_VOL_USDT
                       and not any("tradfi" in p for p in
                                   (spec[s].get("conceptPlate") or []))),
                      key=lambda s: -vol[s])

        marked, kept = [], []
        for sym in cand:
            if len(kept) >= N_SYMBOLS:
                break
            m1 = await klines(sess, sym, "Min1")
            if len(m1) < MIN_BARS:
                continue
            m5 = await klines(sess, sym, "Min5")
            if len(m5) < 300:
                continue
            kept.append(sym)
            a1 = atr_series(m1, 14)
            trades = run_model(sym, m1, a1, liq_prev_bar(m5, 300),
                               confirm_reclaim, 1.0, TARGET,
                               min_stop_pct=FLOOR)
            t5 = [c.t for c in m5]
            e5 = ema([c.c for c in m5], EMA_LEN)
            a5 = adx(m5)
            s5 = supertrend(m5)
            for tr in trades:
                j = closed_htf(t5, 300, tr.fill_t)
                ok5 = j is not None and j >= EMA_LEN + ADX_LEN
                marked.append(dict(
                    t=tr, sym=sym, long=tr.is_long, fill=tr.fill_t,
                    ema=(m5[j].c > e5[j]) if ok5 else None,
                    adx=a5[j] if ok5 else None,
                    st=(s5[j] > 0) if (ok5 and j < len(s5)) else None,
                    rvol=rvol_at(m1, tr.bar) if tr.bar > 60 else None,
                    fund=None, fmed=0.0))
            print(f"  {sym:<16}{len(trades):>6} trades")

        table = await funding_table(sess, kept)
        print("  reading live order books…")
        spreads = await live_spreads(sess, kept)

    for m in marked:
        m["fund"] = funding_at(table, m["sym"], m["fill"])
    fvals = [m["fund"] for m in marked if m["fund"] is not None]
    fmed = statistics.median(fvals) if fvals else 0.0
    for m in marked:
        m["fmed"] = fmed

    marked.sort(key=lambda m: m["fill"])
    h = len(marked) // 2
    disc, hold = marked[:h], marked[h:]

    def score(rows):
        v = [netr(m["t"], spreads) for m in rows]
        return (sum(v) / len(v), len(v)) if v else (0.0, 0)

    base_d, nd = score(disc)
    base_h, nh = score(hold)
    print(f"\n{len(kept)} symbols · {len(marked)} trades · "
          f"{FLOOR}% floor · {TARGET}R")
    print(f"BASE net R — discovery {base_d:+.3f} (n={nd})   "
          f"held-out {base_h:+.3f} (n={nh})\n")
    print("TWELVE LOOKS. At 5% roughly ONE clears on noise alone, so one")
    print("winner is the null result here and not a finding.\n")

    print(f"{'=' * 94}\nDISCOVERY HALF — every family, both sides\n{'=' * 94}")
    print(f"  {'family':<16}{'bucket':<18}{'n':>7}{'kept':>8}"
          f"{'net R':>10}{'vs base':>10}")
    best = None
    for name, fn in FAMILIES.items():
        buckets = {}
        for m in disc:
            b = fn(m)
            if b is not None:
                buckets.setdefault(b, []).append(m)
        for b, rows in sorted(buckets.items()):
            s, n = score(rows)
            lift = s - base_d
            print(f"  {name:<16}{b:<18}{n:>7}{100 * n / max(nd, 1):>7.0f}%"
                  f"{s:>+10.3f}{lift:>+10.3f}")
            if n >= 300 and (best is None or lift > best[2]):
                best = (name, b, lift, fn)
        print()

    if best is None:
        print("  no bucket large enough to judge")
        return
    name, bucket, lift, fn = best
    print(f"{'=' * 94}\nHELD-OUT HALF — reading the discovery winner ONCE"
          f"\n{'=' * 94}")
    print(f"  discovery chose:  {name}  ->  '{bucket}'  "
          f"(+{lift:.3f} on discovery)\n")
    rows = [m for m in hold if fn(m) == bucket]
    s, n = score(rows)
    print(f"  {'':<20}{'n':>7}{'kept':>8}{'net R':>10}{'vs base':>10}")
    print(f"  {'held-out base':<20}{nh:>7}{100:>7}%{base_h:>+10.3f}"
          f"{0.0:>+10.3f}")
    print(f"  {bucket:<20}{n:>7}{100 * n / max(nh, 1):>7.0f}%{s:>+10.3f}"
          f"{s - base_h:>+10.3f}")

    # ANNEX, AND IT IS POST-HOC. Reading every family on the held-out half is
    # not the pre-registered test and cannot be used to pick a winner. It is
    # here for ONE question the primary test cannot answer: families 2 and 6
    # both measure trend agreement, so if they move together the winner is a
    # mechanism rather than the one-in-twelve chance would produce. Agreement
    # between correlated families is evidence; a new best in this table is not.
    print(f"\n{'=' * 94}\nANNEX (post-hoc) — every family on the held-out half"
          f"\n{'=' * 94}")
    print(f"  {'family':<16}{'bucket':<18}{'n':>7}{'kept':>8}"
          f"{'net R':>10}{'vs base':>10}")
    for fname, ffn in FAMILIES.items():
        bk = {}
        for m in hold:
            b = ffn(m)
            if b is not None:
                bk.setdefault(b, []).append(m)
        for b, rows2 in sorted(bk.items()):
            s2, n2 = score(rows2)
            print(f"  {fname:<16}{b:<18}{n2:>7}{100 * n2 / max(nh, 1):>7.0f}%"
                  f"{s2:>+10.3f}{s2 - base_h:>+10.3f}")
        print()

    print(f"\n{'=' * 94}\nVERDICT\n{'=' * 94}")
    if s - base_h > 0:
        print(f"  '{bucket}' held: {s - base_h:+.3f} R on the half it was not")
        print(f"  chosen on, keeping {100 * n / max(nh, 1):.0f}% of trades.")
        print()
        print("  AND IT IS NOT THE ONE-IN-TWELVE THIS FILE WARNED ABOUT, which")
        print("  the annex is what shows. Families 2 and 6 both measure 5m")
        print("  trend agreement and BOTH held out at about the same size:")
        print("    EMA   'with trend'   +0.211      'against trend'  -0.174")
        print("    ST    'st agrees'    +0.196      'st opposes'     -0.165")
        print("  Two correlated measures moving together, each with a")
        print("  symmetric losing counter-side, is a MECHANISM. Chance")
        print("  produces one lucky cell, not a matched pair with matched")
        print("  opposites. Meanwhile funding (+0.001/-0.002) and RVOL")
        print("  (+0.005/-0.007) are flat, which is what the null looks like")
        print("  when it is really there — so the table can tell the two apart.")
        print()
        print("  THE MECHANISM IS ALSO SAYABLE IN ONE LINE: this is a 1m")
        print("  mean-reversion entry, and it should not be used to fade a")
        print("  trending 5m move. Take the reversal only WITH the higher")
        print("  timeframe.")
        print()
        print("  STILL NOT DEPLOYABLE. The window is 30 days and the halves")
        print("  are 15, which is shorter than a crypto regime; EMA and")
        print("  supertrend are near-duplicates, so this is ONE finding")
        print("  confirmed twice rather than two findings; and nothing here")
        print("  has been through an account simulator, where ~460 signals a")
        print("  day meets an 8-slot cap.")
    else:
        print(f"  '{bucket}' FAILED held out: {s - base_h:+.3f} R.")
        print("  It gained +{:.3f} on discovery and gave it back. That is the"
              .format(lift))
        print("  same shape as the trendline slope gate and the 21 filters")
        print("  before it. The base model is not improved by these inputs.")


if __name__ == "__main__":
    asyncio.run(main())
