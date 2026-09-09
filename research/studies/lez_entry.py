"""Two changes to what happens AFTER a Liquidity Entry Zones signal.

    1  A HIGHER-TIMEFRAME BIAS as its own arm — 4h and daily, separately.
    2  WAIT FOR A FAIR VALUE GAP, and either take it at market or rest a limit
       in it and require the RETEST.

WHY EACH, AND WHAT THE PRIOR IS

**The HTF bias.** `ema_len.py` just confirmed that the chart's own EMA is a
knob on a null: seven lengths, best arm a different length in every panel,
whole ladder inside 1.5 SE. `which_trend.py` says the thing that DOES sort is
the higher timeframe, at +4.5 SE. LEZ has no notion of one. So this is the only
direction filter in the project with evidence behind it, tested here for the
first time on this trigger.

The prior is not clean, though, and saying so matters: `location.py` found the
daily trend's ABSOLUTE lift did not survive its held-out half — worth +0.19 R
on the newer 42 days and 0.00 on the older ones. So 4h and daily are both run,
separately, and a result that appears on one half only is not a result.

**The FVG.** LEZ enters at the confirmation bar's CLOSE — a market order, which
pays taker on the way in and buys at whatever price the candle happened to end
on. Riptide does not do that: it waits for a fair value gap and rests a LIMIT
inside it, which pays maker and buys a retracement. `mss_entry.py` measured
that difference on Riptide's own signals and the market entry lost on all six
arms. This asks whether LEZ's trigger improves under Riptide's entry.

Two versions, because they are different trades:

    FVG market   a gap forms within 10 bars -> enter at THAT bar's close.
                 Still a market order; the gap is only being used as a filter
                 saying "the move has displacement behind it".
    FVG retest   a gap forms -> rest a limit at its proximal edge and fill
                 ONLY if price comes back. Pays maker, buys a retracement, and
                 frequently never fills at all.

An unfilled retest scores 0.0 R, not a loss — the project's convention, and the
only honest one: it is a trade that did not happen. Fill rate is printed beside
every arm so the trade-off is visible rather than buried in the mean.

FAIRNESS, WHICH IS MOST OF THE WORK

Every arm is scored on the IDENTICAL signal set: a signal is kept only if the
whole worst-case window (10 bars of gap-waiting plus the fill window plus the
horizon) exists in the data. Otherwise the base arm would be scored on signals
the FVG arms had to drop, and the comparison would be between two populations.

The stop is 1.5 x ATR from whatever the entry turns out to be, on every arm, so
`risk_pct` stays comparable and the fee cannot masquerade as an edge — the trap
`momentum.py` fell into at 4.8 SE. The risk column is printed to prove it.

PRE-REGISTERED, BEFORE THE FIRST NUMBER

    PRIMARY   Does any arm beat `base` on net R PER SIGNAL in all four panels
              (2 timeframes x 2 window halves)? Four for four or it is nothing.

    Seven arms, fixed in advance, no sweep. R per filled trade and fill rate
    are reported but are NOT the bar: a filter that fills 20% of the time and
    scores well on those is not obviously better than one that always fills,
    and R per opportunity is the only number that compares them.

    PYTHONPATH=. python3 research/studies/lez_entry.py
"""
from __future__ import annotations

import research.env  # noqa: F401  (must precede riptide.config)

import asyncio
import statistics

import aiohttp

from riptide.config import BAR_SECONDS
from riptide.engine import atr_series, entry_of
from riptide.exchange import list_symbols
from riptide.trend import di_direction, supertrend
from research.harness import mean_se, simulate, simulate_market
from research.studies.lez import FEE, lez_signals
from research.studies.mtf_grid import fetch_paged, htf_dir_at

TFS = (("Min30", 2), ("Min15", 4))
SYMBOLS = 30
HORIZON_HOURS, FILL_HOURS = 48, 5
STOP_ATR, TARGET_R, ATR_LEN = 1.5, 2.0, 14
FVG_WAIT = 10                 # Riptide's own max_bars_after_mss
ENTRY_MODE = "proximal"       # Riptide's default: the gap's near edge

ARMS = ("base", "+ 4h bias", "+ daily bias", "FVG market", "FVG retest",
        "FVG retest + 4h", "FVG retest + daily")


def first_fvg(cs, after: int, is_long: bool, limit: int):
    """The first fair value gap in the signal's direction, formed strictly
    after bar `after` and within `limit` bars.

    A three-bar gap at bar j needs bars j-2, j-1 and j, and is only KNOWN once
    j closes — which is why the scan returns j and every entry derived from it
    is priced at or after j. Nothing here can see a bar that has not closed.

    Returns (bar, entry_price) or None.
    """
    for j in range(after + 1, min(after + 1 + limit, len(cs))):
        if j < 2:
            continue
        if is_long and cs[j].l > cs[j - 2].h:
            return j, entry_of(True, cs[j].l, cs[j - 2].h, ENTRY_MODE)
        if not is_long and cs[j].h < cs[j - 2].l:
            return j, entry_of(False, cs[j - 2].l, cs[j].h, ENTRY_MODE)
    return None


async def collect(sess, syms, tf, pages, cache):
    """One record per signal, carrying every arm's outcome for THAT signal.

    Per-signal rather than per-arm because the question that decides this study
    is paired: on the signals where the retest actually filled, how did the
    plain market entry do? A per-arm list cannot answer that, and without it
    "the retest is better" is indistinguishable from "the retest trades less,
    and less of a losing thing loses less".
    """
    horizon = max(1, HORIZON_HOURS * 3600 // BAR_SECONDS[tf])
    fill_bars = max(1, FILL_HOURS * 3600 // BAR_SECONDS[tf])
    need = FVG_WAIT + fill_bars + horizon + 2
    recs, days = [], []

    for sym in syms:
        try:
            cs = await fetch_paged(sess, sym, tf, pages)
            for htf in ("Day1", "Hour4"):
                if (sym, htf) not in cache:
                    cache[(sym, htf)] = await fetch_paged(sess, sym, htf, 1)
        except Exception:
            continue
        hd, h4 = cache[(sym, "Day1")], cache[(sym, "Hour4")]
        if len(cs) < 800 or len(hd) < 60 or len(h4) < 60:
            continue
        days.append((cs[-1].t - cs[0].t) / 86400)
        atr = atr_series(cs, ATR_LEN)
        cut = len(cs) // 2
        sd, dd = supertrend(hd), di_direction(hd)
        s4, d4 = supertrend(h4), di_direction(h4)

        for x in lez_signals(cs):
            if atr[x.bar] <= 0 or x.bar + need > len(cs) or x.entry <= 0:
                continue
            want = 1 if x.is_long else -1

            def market(bar, entry):
                d = atr[bar] * STOP_ATR
                stop = entry - d if x.is_long else entry + d
                if entry <= 0 or stop <= 0:
                    return None, 0.0
                return simulate_market(cs, bar, entry, stop, x.is_long,
                                       target_r=TARGET_R,
                                       horizon_bars=horizon,
                                       **FEE), 100 * d / entry

            def limit(bar, entry):
                d = atr[bar] * STOP_ATR
                stop = entry - d if x.is_long else entry + d
                if entry <= 0 or stop <= 0:
                    return None, 0.0
                return simulate(cs, bar, entry, stop, x.is_long,
                                target_r=TARGET_R, fill_bars=fill_bars,
                                horizon_bars=horizon, fee_pct=0.0,
                                **FEE), 100 * d / entry

            base_o, base_risk = market(x.bar, x.entry)
            if base_o is None:
                continue
            g = first_fvg(cs, x.bar, x.is_long, FVG_WAIT)
            mo = lo = None
            mrisk = lrisk = 0.0
            if g is not None and atr[g[0]] > 0:
                mo, mrisk = market(g[0], cs[g[0]].c)
                lo, lrisk = limit(g[0], g[1])
            recs.append(dict(
                half="held" if x.bar < cut else "disc",
                agree_4=htf_dir_at(h4, s4, d4, cs[x.bar].t) == want,
                agree_d=htf_dir_at(hd, sd, dd, cs[x.bar].t) == want,
                base=base_o, base_risk=base_risk,
                fvg_m=mo, fvg_m_risk=mrisk, fvg_l=lo, fvg_l_risk=lrisk,
                had_gap=g is not None))
    return recs, days


def arm_rows(recs, arm):
    """(r, risk, filled) per SIGNAL for one arm. A signal the arm declined —
    no gap came, or the limit never filled — is 0.0 R and unfilled, never
    dropped: it is an opportunity that produced nothing, which is the honest
    treatment and the only one that lets arms with different fill rates be
    compared on the same denominator."""
    out = []
    for r in recs:
        if arm == "+ 4h bias" and not r["agree_4"]:
            continue
        if arm == "+ daily bias" and not r["agree_d"]:
            continue
        if arm == "FVG retest + 4h" and not r["agree_4"]:
            continue
        if arm == "FVG retest + daily" and not r["agree_d"]:
            continue
        o = (r["fvg_m"] if arm == "FVG market"
             else r["fvg_l"] if arm.startswith("FVG retest")
             else r["base"])
        risk = (r["fvg_m_risk"] if arm == "FVG market"
                else r["fvg_l_risk"] if arm.startswith("FVG retest")
                else r["base_risk"])
        if o is None:
            out.append((0.0, 0.0, False))
        else:
            out.append((o.r, risk, o.filled))
    return out


HEAD = (f"  {'arm':<21}{'n':>6}{'fill':>7}{'win':>6}{'risk':>7}"
        f"{'R/signal':>10}{'SE':>7}{'R/filled':>10}{'vs base':>9}")


def report(tf, recs, days):
    print(f"\n{'=' * 100}\n{tf}   {statistics.median(days):.0f} days across "
          f"{len(days)} symbols, split in half\n{'=' * 100}")
    means = {}
    for half, title in (("disc", "DISCOVERY (newer half)"),
                        ("held", "HELD OUT (older half)")):
        sub = [r for r in recs if r["half"] == half]
        print(f"\n  {title}")
        print(HEAD)
        base = None
        for a in ARMS:
            rows = arm_rows(sub, a)
            if len(rows) < 25:
                print(f"  {a:<21}{len(rows):>6}   too few")
                means.setdefault(a, {})[half] = None
                continue
            rs = [r for r, _, _ in rows]
            fl = [r for r, _, f in rows if f]
            risk = statistics.fmean([k for _, k, f in rows if f] or [0.0])
            m, se = mean_se(rs)
            means.setdefault(a, {})[half] = m
            if base is None:
                base = m
            print(f"  {a:<21}{len(rows):>6}{len(fl) / len(rows):>7.0%}"
                  f"{sum(r > 0 for r in rs) / len(rs):>6.0%}{risk:>6.2f}%"
                  f"{m:>+10.3f}{se:>7.3f}"
                  f"{statistics.fmean(fl) if fl else 0.0:>+10.3f}"
                  + (f"{m - base:>+9.3f}" if a != "base" else f"{'—':>9}"))
        decompose(sub, half)
        bias_split(sub, half)
    return means


def bias_split(recs, half):
    """THE PROPER TEST FOR A BIAS FILTER, which is not what the table above is.

    "+ 4h bias" is compared against `base` — the filter's own subset against
    the whole. That is guaranteed to look better whenever the filter removes
    anything worse than average, and it cannot distinguish a real sort from
    picking a lucky third. The test that can is AGREE against AGAINST, which
    is how which_trend.py measured the daily trend at +4.5 SE.

    Base's outcome is used on both sides so the entry is held constant and only
    the direction filter moves.
    """
    for lab, key in (("4h", "agree_4"), ("daily", "agree_d")):
        a = [r["base"].r for r in recs if r[key]]
        b = [r["base"].r for r in recs if not r[key]]
        if len(a) < 25 or len(b) < 25:
            continue
        ma, sa = mean_se(a)
        mb, sb = mean_se(b)
        d, se = ma - mb, (sa ** 2 + sb ** 2) ** 0.5
        print(f"    {lab + ' bias, agree vs AGAINST (' + half + ')':<48}"
              f"agree {ma:+.3f} (n={len(a)})  against {mb:+.3f} (n={len(b)})"
              f"  diff {d:+.3f} ± {se:.3f} ({d / se if se else 0:+.1f} SE)")


def decompose(recs, half):
    """THE CONTROL THAT DECIDES THE RETEST ARM.

    A limit that fills 55% of the time turns 45% of a losing strategy into
    zeros, and multiplying a negative mean by 0.55 makes it less negative
    without anything having improved. So the gain has to be split:

      SELECTION   base scored ONLY on the signals where the retest filled,
                  against base on all signals. Does waiting for a gap and a
                  retest pick better signals, or just fewer?
      ENTRY       retest against base on those SAME signals, paired. Is the
                  limit at the gap a better price than the close?

    The paired difference also gets an honest standard error — the naive
    sqrt(se_a^2 + se_b^2) is wrong when the two arms share signals, and it is
    wrong in the direction that overstates significance.
    """
    got = [r for r in recs if r["fvg_l"] is not None and r["fvg_l"].filled]
    if len(got) < 50:
        return
    all_base = [r["base"].r for r in recs]
    sub_base = [r["base"].r for r in got]
    sub_rt = [r["fvg_l"].r for r in got]
    d = [b - a for a, b in zip(sub_base, sub_rt)]
    md, sd_ = mean_se(d)
    print(f"    -- what the retest arm's gain actually is ({half}) --")
    print(f"       base, all {len(all_base)} signals            "
          f"{mean_se(all_base)[0]:+.3f}")
    print(f"       base, only the {len(got)} the retest filled  "
          f"{mean_se(sub_base)[0]:+.3f}"
          f"   <- SELECTION: {mean_se(sub_base)[0] - mean_se(all_base)[0]:+.3f}")
    print(f"       retest, those same {len(got)} signals        "
          f"{mean_se(sub_rt)[0]:+.3f}"
          f"   <- ENTRY: {md:+.3f} ± {sd_:.3f} paired"
          f" ({md / sd_ if sd_ else 0:+.1f} SE)")


def verdict(all_means):
    print(f"\n{'=' * 100}\n  THE PRE-REGISTERED BAR: an arm must beat `base` "
          f"on R per signal in ALL FOUR panels\n{'=' * 100}")
    for a in ARMS[1:]:
        cells, wins = 0, 0
        detail = []
        for tf, means in all_means.items():
            for half in ("disc", "held"):
                v, b = means.get(a, {}).get(half), means.get("base", {}).get(half)
                if v is None or b is None:
                    detail.append("  n/a ")
                    continue
                cells += 1
                wins += v > b
                detail.append(f"{v - b:+.3f}")
        ok = cells == 4 and wins == 4
        print(f"  {a:<21}{'  '.join(detail)}   {wins}/{cells}   "
              f"{'PASSES' if ok else 'fails'}")


async def main():
    async with aiohttp.ClientSession() as sess:
        syms = (await list_symbols(sess))[:SYMBOLS]
        print(f"After the signal: HTF bias, and waiting for an FVG\n"
              f"{len(syms)} symbols · stop {STOP_ATR:g} x ATR({ATR_LEN}) from "
              f"whatever the entry is · target {TARGET_R:g}R · gap window "
              f"{FVG_WAIT} bars · {ENTRY_MODE} edge")
        cache: dict = {}
        all_means = {}
        for tf, pages in TFS:
            recs, days = await collect(sess, syms, tf, pages, cache)
            if days:
                all_means[tf] = report(tf, recs, days)
        if all_means:
            verdict(all_means)


if __name__ == "__main__":
    asyncio.run(main())
