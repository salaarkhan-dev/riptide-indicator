"""Which of the sixty should the bot scan — and can that question be answered
from performance at all?

THE REQUEST WAS REASONABLE AND THE OBVIOUS WAY TO ANSWER IT IS A TRAP. "Some of
these are memes that move on news and manipulation, keep the good ones" is a
sound instinct. But the tempting implementation — rank the sixty by R over
these 333 days, keep the top twenty — is the single most reliable way to
manufacture a beautiful backtest and a dead live account. The survivor cell
holds 312 trades across 57 symbols. Five trades each. At five trades the gap
between the best and worst symbol is very nearly all noise, and selecting on it
is selecting noise, which by construction does not repeat.

SO THE FIRST TEST IS WHETHER RANKING WORKS AT ALL, AND IT COMES BEFORE ANY
LIST. Split the window in half. Rank the symbols on the first half. Ask what
the top half then did in the SECOND half, which the ranking could not see. If
a symbol that traded well in H1 is no better than a coin flip in H2, then
per-symbol skill does not persist, no ranked list is worth shipping, and the
honest answer to the request is "not this way". That result would be a finding,
not a failure — it is exactly the number that stops a bad change.

THE SECOND TEST IS THE ONE THE REQUEST ACTUALLY POINTED AT. "Meme", "moves on
news", "manipulated" are not statements about past R. They are statements about
what a symbol IS, knowable before the year starts. Selection on a property
known in advance generalises; selection on realised performance does not. Three
such axes are measured here, all computed from bars STRICTLY BEFORE each
signal so nothing leaks:

    realised volatility   median true range / close over the trailing 240 bars
    turnover              median close x volume x CONTRACT SIZE, same window
    meme                  a hand-written list, spelled out below so it can be
                          argued with rather than trusted

THE CONTRACT SIZE IN THAT SECOND LINE IS NOT DECORATION AND LEAVING IT OUT
INVERTED THE ANSWER. The first run of this study computed turnover as
`close * v` and reported, with a bootstrap interval clear of zero, that THIN
turnover was the profitable tercile. It is not a liquidity result. `v` is
CONTRACT count and a contract is 0.0001 BTC but 10,000,000 PEPE, so `close * v`
came out at 894 billion for BTC and 0 for PEPE — it correlated +0.902 with log
PRICE and was measuring nothing but the size of the number the coin trades at.
`riptide/exchange.py` already says this in as many words: "volume24 is contract
count, which is not comparable across symbols". Multiplying by contractSize
reproduces the exchange's own amount24 to within a few percent on BTC, PEPE,
SHIB and SOL, so that is what is used here.

Every cell is read through the SYMBOL BOOTSTRAP from `survivor.py`, not the
per-bet standard error, because the whole question here is how much a number
depends on which coins happened to be in the universe.

    PYTHONPATH=. RIPTIDE_MIN_GRADE=B RIPTIDE_DEEP_CACHE=/tmp/deep \\
        python3 research/studies/symbols.py

RESULT, 10 Sep 2026 — DO NOT SHIP A SYMBOL LIST

  RANKING DOES NOT PERSIST, ON ANY OF THE THREE STREAMS.

      all tradeable   H1-best half -> H2 +0.038   H1-worst half -> H2 +0.042
      confirmed       +0.059 vs -0.000      survivor cell  +0.535 vs +0.021
      shuffled-ranking null clears every one of them; Spearman between the
      two halves is +0.13, +0.15, +0.18.

  On the only sample large enough to mean anything — 4230 trades, 59 symbols —
  last year's leaderboard is worth MINUS 0.004 R a trade in the half it could
  not see. The two filtered streams look better but both sit far inside a
  shuffled ranking, which is what five trades a symbol buys.

  THE MEME LABEL FAILS THE SAME WAY IT WAS MEANT TO SUCCEED. Whole-window it
  looked like a finding, and in the direction OPPOSITE to the hypothesis: memes
  were the BEST bucket on confirmed (+0.149, bootstrap clear of zero) and on
  the survivor cell (+0.531). Split in half it flips — memes are -0.208 worse
  in H1 and +0.080 better in H2 across all tradeable signals, -0.162 then
  +0.247 on confirmed. The survivor cell holds its sign, but on 20 trades in H1
  against 2115 that flip. When a label fails on four thousand trades and passes
  on fifty-five, believe the four thousand. There is no meme effect here in
  either direction.

  TURNOVER FLIPS TOO on both streams worth trading. It holds only on the full
  stream, which is 86% early signals — and there it is thin-is-better, which is
  the opposite of a liquidity story and more likely a small-cap beta.

  ONE THING HELD, AND IT IS NOT ABOUT WHICH SYMBOL. Inside the survivor cell,
  the WILD volatility tercile beat the calm one by +0.300 in H1 and +0.298 in
  H2 — the same number twice, out of sample. It is not the meme label in
  disguise: strip the nine meme symbols out and the wild tercile is still
  +0.291 over 83 trades.

  The mechanism is coherent, which is why it is worth a real test rather than a
  shrug. `risk_pct` is how far the stop sits for THIS setup; `atr_pct` is how
  far the coin moves on an ordinary bar. Holding the first inside 1.2-2.6% and
  raising the second means the stop is tight RELATIVE TO THE COIN'S OWN NOISE,
  which is a statement that the raid was unusually well defined. The natural
  variable is therefore the RATIO risk_pct / atr_pct, not the tercile, and it
  has not been measured yet.

  NOT SHIPPED. 103 trades a half, found after roughly twenty-one cells were
  read on the same rows. It needs its own pre-registration on the ratio, with
  the circular-shift null, before it goes anywhere near riptide.conf.
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import random                                           # noqa: E402
import statistics                                       # noqa: E402
from collections import defaultdict                     # noqa: E402

import aiohttp                                          # noqa: E402

from riptide.exchange import BASE, get_json, list_symbols  # noqa: E402
from research.deep import load_universe                 # noqa: E402
from research.harness import mean_se                    # noqa: E402
from research.studies.report import (DAYS, INTERVAL, bets_of,
                                     collect)           # noqa: E402
from research.studies.survivor import LO, HI, symbol_bootstrap  # noqa: E402

LOOKBACK = 240          # 5 days of Min30 bars, the trailing feature window
MIN_TRADES = 6          # per symbol per half, to be ranked at all
DRAWS = 4000

# A HAND LABEL, WRITTEN DOWN SO IT CAN BE DISAGREED WITH. This is the user's
# own hypothesis made explicit: coins whose price is driven by attention rather
# than by flow. DOGE and SHIB are the awkward ones — large and liquid enough to
# look like majors, and they trade on attention anyway. They are labelled meme
# because that is what the hypothesis says, not because of how they scored.
MEME = {
    "1000BONK_USDT", "DOGE_USDT", "FARTCOIN_USDT", "PENGU_USDT", "PEPE_USDT",
    "SHIB_USDT", "TRUMPOFFICIAL_USDT", "USELESS_USDT", "PUMPFUN_USDT",
}


async def contract_sizes(sess):
    """symbol -> contractSize. Without it `v` is not comparable across coins."""
    d = await get_json(sess, f"{BASE}/api/v1/contract/detail")
    out = {}
    for r in (d or {}).get("data") or []:
        try:
            out[r["symbol"]] = float(r["contractSize"])
        except (KeyError, TypeError, ValueError):
            continue
    return out


def features(candles, csize):
    """{(symbol, bar time): (atr_pct, turnover)} from the TRAILING window only.

    The window ends at the bar BEFORE the signal. A feature that peeks at the
    signal bar would carry the raid itself, and the raid is the thing being
    predicted.
    """
    out = {}
    for sym, cs in candles.items():
        mult = csize.get(sym)
        if not mult:
            continue                 # no size, no comparable turnover, no row
        tr, to = [], []
        for i, c in enumerate(cs):
            if i:
                p = cs[i - 1].c
                tr.append(max(c.h - c.l, abs(c.h - p), abs(c.l - p)) / c.c
                          if c.c else 0.0)
            else:
                tr.append(0.0)
            to.append(c.c * c.v * mult)
            if i >= LOOKBACK:
                out[(sym, c.t)] = (
                    100 * statistics.median(tr[i - LOOKBACK:i]),
                    statistics.median(to[i - LOOKBACK:i]),
                )
    return out


def boot_line(name, trades, draws=DRAWS):
    if len(trades) < 25:
        return f"  {name:<26} {len(trades):>4} trades — too few"
    rs = [t.r for t in trades]
    b = bets_of(trades)
    m, se = mean_se(b)
    bo = symbol_bootstrap(trades, draws)
    if not bo:
        return f"  {name:<26} {len(trades):>4} trades — bootstrap failed"
    p5 = bo[int(0.05 * (len(bo) - 1))]
    p95 = bo[int(0.95 * (len(bo) - 1))]
    nsym = len({t.sym for t in trades})
    return (f"  {name:<26} {len(trades):>4} tr {len(b):>4} bets {nsym:>3} sym  "
            f"{sum(1 for r in rs if r > 0) / len(rs):>3.0%} win  "
            f"{m:>+6.3f}±{se:.3f}  boot [{p5:>+6.3f}, {p95:>+6.3f}]  "
            f"{'OK ' if p5 > 0 else '   '}{sum(rs):>+7.1f} R")


# ------------------------------------------------------- does ranking persist?

def persistence(trades, label, min_trades=MIN_TRADES):
    """Rank symbols on the first half; score that ranking on the second.

    THE NULL IS A SHUFFLED RANKING, not a shuffled outcome. The question is not
    "is H2 performance random" — it plainly is not, some symbols really did do
    better. It is "does knowing H1 help pick them", so the thing to destroy is
    the LINK between the two halves. Reassigning H1 ranks at random over the
    same symbols does exactly that and leaves everything else alone.
    """
    ts = sorted(t.t for t in trades)
    mid = ts[len(ts) // 2]
    h1, h2 = defaultdict(list), defaultdict(list)
    for t in trades:
        (h1 if t.t < mid else h2)[t.sym].append(t)

    both = [s for s in h1
            if len(h1[s]) >= min_trades and len(h2.get(s, [])) >= min_trades]
    if len(both) < 12:
        print(f"\n{label}: only {len(both)} symbols have {min_trades}+ trades "
              "in both halves — cannot test persistence.")
        return

    score = {s: statistics.fmean(t.r for t in h1[s]) for s in both}
    order = sorted(both, key=lambda s: -score[s])
    half = len(order) // 2

    def h2_mean(syms):
        v = [t.r for s in syms for t in h2[s]]
        return statistics.fmean(v), len(v)

    top, ntop = h2_mean(order[:half])
    bot, nbot = h2_mean(order[half:])
    real = top - bot

    rnd = random.Random(7717)
    null = []
    for _ in range(2000):
        sh = both[:]
        rnd.shuffle(sh)
        a, _ = h2_mean(sh[:half])
        b, _ = h2_mean(sh[half:])
        null.append(abs(a - b))
    null.sort()
    p95 = null[int(0.95 * (len(null) - 1))]

    # rank agreement, computed without scipy
    r2 = {s: statistics.fmean(t.r for t in h2[s]) for s in both}
    o1 = {s: i for i, s in enumerate(sorted(both, key=lambda s: score[s]))}
    o2 = {s: i for i, s in enumerate(sorted(both, key=lambda s: r2[s]))}
    n = len(both)
    d2 = sum((o1[s] - o2[s]) ** 2 for s in both)
    rho = 1 - 6 * d2 / (n * (n * n - 1))

    print(f"\n{label}")
    print(f"  {n} symbols with {min_trades}+ trades in each half, split at the "
          f"median signal time")
    print(f"  H1-best half   -> H2 {top:>+7.3f} R/trade over {ntop} trades")
    print(f"  H1-worst half  -> H2 {bot:>+7.3f} R/trade over {nbot} trades")
    print(f"  the ranking is worth {real:>+7.3f} R/trade in the half it could "
          f"not see")
    print(f"  shuffled-ranking null: |diff| p95 {p95:.3f}, max {null[-1]:.3f}"
          f"   ->  {'RANKING WORKS' if abs(real) >= p95 else 'RANKING IS NOISE'}")
    print(f"  Spearman rank correlation H1 vs H2  {rho:>+.3f}"
          "   (0 means last year's leaderboard tells you nothing)")


def split_half(rows, name, key, lab_lo, lab_hi):
    """The same contrast in each half of the window, cut inside each half.

    THIS IS THE TEST THAT DECIDES, NOT THE BOOTSTRAP. A bootstrap asks how much
    a number depends on which coins were drawn; it cannot tell you whether the
    effect was there all year or only after March. Twenty-one cells were read
    on the whole window above and several came back with intervals clear of
    zero — which is roughly what twenty-one cells produce by chance. An effect
    that is real shows up in BOTH halves with the same sign. One that flips is
    a period, not a property, and shipping it buys the last six months.

    Terciles are recomputed inside each half so the cut itself cannot leak.
    """
    ts = sorted(t.t for t in rows)
    mid = ts[len(ts) // 2]
    out = []
    for pick, half in ((lambda t: t.t < mid, "H1"), (lambda t: t.t >= mid, "H2")):
        h = [t for t in rows if pick(t)]
        lo_, hi_ = key(h)
        if len(lo_) < 15 or len(hi_) < 15:
            out.append((half, None, None, None))
            continue
        a = statistics.fmean(bets_of(lo_))
        b = statistics.fmean(bets_of(hi_))
        out.append((half, a, b, len(lo_) + len(hi_)))
    print(f"  {name:<30}", end="")
    diffs = []
    for half, a, b, n in out:
        if a is None:
            print(f"  {half} thin        ", end="")
        else:
            print(f"  {half} {lab_hi[:4]}-{lab_lo[:4]} {b - a:>+7.3f} ({n:>3})",
                  end="")
            diffs.append(b - a)
    ok = len(diffs) == 2 and (diffs[0] > 0) == (diffs[1] > 0)
    print("   " + ("HOLDS" if ok else "FLIPS" if len(diffs) == 2 else ""))


def tercile_key(feat, ix):
    def k(h):
        v = sorted(feat[(t.sym, t.t)][ix] for t in h)
        q1, q3 = v[len(v) // 3], v[2 * len(v) // 3]
        return ([t for t in h if feat[(t.sym, t.t)][ix] <= q1],
                [t for t in h if feat[(t.sym, t.t)][ix] > q3])
    return k


def meme_key(h):
    return ([t for t in h if t.sym not in MEME],
            [t for t in h if t.sym in MEME])


async def main():
    async with aiohttp.ClientSession() as sess:
        syms = await list_symbols(sess)
        candles = await load_universe(sess, syms, INTERVAL, DAYS)
        trades = await collect(sess, candles)
        csize = await contract_sizes(sess)
    feat = features(candles, csize)

    live = [t for t in trades if t.filled and t.exit_t is not None]
    conf = [t for t in live if t.kind == "confirmed"]
    cell = [t for t in conf if LO <= t.risk_pct <= HI]

    print("CHOOSING SYMBOLS\n"
          f"{DAYS} days · {len(candles)} symbols · features from the trailing "
          f"{LOOKBACK} bars, strictly before each signal\n"
          "boot [ , ] is the 5th-95th percentile over 4000 resamples OF THE "
          "UNIVERSE.\nOK marks a cell whose 5th percentile is above zero.")

    print("\n" + "=" * 78)
    print("1. DOES A SYMBOL RANKING PERSIST? — the test that decides whether a")
    print("   'best symbols' list can be shipped at all")
    print("=" * 78)
    persistence(live, "ALL tradeable signals  (the biggest sample there is)")
    persistence(conf, "CONFIRMED only", min_trades=4)
    persistence(cell, f"CONFIRMED, stop {LO}-{HI}%  (the survivor)",
                min_trades=3)

    print("\n" + "=" * 78)
    print("2. EX-ANTE PROPERTIES — knowable before the year starts, so a filter")
    print("   built on one of these can generalise")
    print("=" * 78)

    for name, rows in (("ALL tradeable", live), ("CONFIRMED", conf),
                       (f"SURVIVOR cell", cell)):
        rows = [t for t in rows if (t.sym, t.t) in feat]
        if len(rows) < 60:
            continue
        print(f"\n-- {name}  ({len(rows)} trades with features)")

        vols = sorted(feat[(t.sym, t.t)][0] for t in rows)
        q1, q3 = vols[len(vols) // 3], vols[2 * len(vols) // 3]
        print(f"  realised volatility, terciles at {q1:.2f}% and {q3:.2f}% "
              "median true range per bar")
        for lab, f in (("  calm", lambda v: v <= q1),
                       ("  middle", lambda v: q1 < v <= q3),
                       ("  wild", lambda v: v > q3)):
            print(boot_line(lab, [t for t in rows
                                  if f(feat[(t.sym, t.t)][0])]))

        tos = sorted(feat[(t.sym, t.t)][1] for t in rows)
        t1, t3 = tos[len(tos) // 3], tos[2 * len(tos) // 3]
        print(f"  turnover, terciles at {t1:,.0f} and {t3:,.0f} USDT per bar"
              f"  ({t1 * 48 / 1e6:,.0f}M and {t3 * 48 / 1e6:,.0f}M a day)")
        for lab, f in (("  thin", lambda v: v <= t1),
                       ("  middle", lambda v: t1 < v <= t3),
                       ("  deep", lambda v: v > t3)):
            print(boot_line(lab, [t for t in rows
                                  if f(feat[(t.sym, t.t)][1])]))

        print(f"  meme label ({len(MEME)} symbols, listed in the docstring)")
        print(boot_line("  meme", [t for t in rows if t.sym in MEME]))
        print(boot_line("  not meme", [t for t in rows if t.sym not in MEME]))

    print("\n" + "=" * 78)
    print("3. THE SAME AXES, ONE HALF AT A TIME — an effect that is a property")
    print("   of the symbol holds its sign in both halves. One that flips is a")
    print("   period, and shipping it buys the last six months.")
    print("=" * 78 + "\n")
    for name, rows in (("ALL tradeable", live), ("CONFIRMED", conf),
                       ("SURVIVOR cell", cell)):
        rows = [t for t in rows if (t.sym, t.t) in feat]
        if len(rows) < 60:
            continue
        split_half(rows, f"{name}: volatility", tercile_key(feat, 0),
                   "calm", "wild")
        split_half(rows, f"{name}: turnover", tercile_key(feat, 1),
                   "thin", "deep")
        split_half(rows, f"{name}: meme", meme_key, "other", "meme")
        print()


if __name__ == "__main__":
    asyncio.run(main())
