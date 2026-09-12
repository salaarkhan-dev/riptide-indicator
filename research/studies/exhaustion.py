"""DOES A 🎯 PICK LANDING NEAR AN EXHAUSTION COUNT SCORE ANY BETTER?

THE QUESTION. riptide-reversal.pine draws TD Sequential counts — a 9-bar
Momentum Setup and a 13-bar Terminal Countdown — and says in three places that
nothing about it is measured. This is where that changes or does not.

The claim being tested is confluence: Riptide finds a liquidity sweep into an
imbalance; the exhaustion count finds a stretched directional run. The two know
nothing about each other, so if a pick that arrives near a completed count
scores better than one that does not, that is two independent methods agreeing.
If it does not, the indicator stays a chart aid and this file says so.

"NEAR", NOT "ON". Exact coincidence is far too rare to measure — a count
completes on one specific bar and a sweep fires on another. So the test is a
WINDOW, in bars of the signal's own timeframe, and several widths are tried:
0 (same bar), 3, 5, 10. A wider window catches more but means less.

CAUSAL, WHICH IS THE WHOLE RISK IN A JOIN LIKE THIS. research/td.bars_since
only ever looks backwards, so a count completing AFTER a signal can never mark
it. A lookahead here would make every number below meaningless and would look
completely normal.

──────────────────────────────────────────────────────────────────────────────
PRE-REGISTERED, BEFORE THE FIRST NUMBER

  PRIMARY. R per trade on the PICKED stream, split by whether a same-direction
  count completed within the window, with the difference and its standard
  error. Picks are what the reader takes, so picks are what the claim is about.

  SECONDARY. The same on the full SENT stream (9118 trades), which has three
  times the power and can see an effect the picked stream is too thin for.

  THE CONTROL, AND IT IS THE PART THAT MATTERS. The same test against the
  OPPOSITE direction. A buy-side count is supposed to help LONGS. If it helps
  shorts equally, the mechanism is not exhaustion — it is something both share,
  most likely a volatility or trend regime, and the confluence story is wrong
  even if the same-direction number looks good. Reported side by side.

  Also reported: both halves of the window, because an effect living in one
  half is a non-result here as everywhere else in this project.

  DECISION RULE, fixed now so it cannot be chosen afterwards. The confluence is
  worth acting on only if ALL of:
    (a) the same-direction difference clears 2 SE on the picked stream,
    (b) it is materially larger than the opposite-direction control,
    (c) it holds in both halves.
  Anything else is reported as null and NOTHING in riptide/ changes. Four
  windows x two counts x two streams is sixteen looks; at 2 SE roughly one will
  clear by chance, so a single clearing cell means nothing on its own and the
  control and the halves are what separate a finding from a coincidence.

  EXPECTATION, on record so it can be wrong. Null. TD Sequential has a long
  public record of not surviving honest testing, and this project's own history
  is the same story twice: trendline breaks looked obviously useful and scored
  zero out of sample, the BTC-trend filter cleared five panels and reversed. I
  expect the Terminal count to look slightly better than the Momentum count
  simply because it is rarer, and I expect that to evaporate against the
  control.

  WHAT WOULD CHANGE MY MIND: a same-direction effect of +0.05 R or more that
  clears 2 SE, is at least twice the opposite-direction effect, and is positive
  in both halves. That would be worth a pre-registered forward test — not a
  code change.

    PYTHONPATH=. python3 research/studies/exhaustion.py
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import math                                             # noqa: E402

import aiohttp                                          # noqa: E402

from riptide.config import BAR_SECONDS                  # noqa: E402
from research.deep import load_universe                 # noqa: E402
from research.td import bars_since, counts              # noqa: E402
from research.studies.poi_tf import DAY, DAYS, H8       # noqa: E402
from research.studies.poi_tf import collect, context, universe  # noqa: E402
from research.studies.report import drawdown            # noqa: E402
from research.studies.band_key import (COOLDOWN, KEYS,  # noqa: E402
                                       pick_rolling)
from research.studies.pick_rule import TFS              # noqa: E402

WINDOWS = (0, 3, 5, 10)

# poi_tf.T declares __slots__, so a trade cannot carry new attributes. The
# marks live in a side table keyed by identity instead of by (symbol, time,
# tf) — the rows are held for the whole run, and an identity key cannot
# silently collide two trades that share a bar the way a value key could.
MARKS: dict = {}


def mark(t, key):
    return MARKS.get(id(t), {}).get(key)


def tag(rows, by_tf_cs):
    """Stamp every trade with how many bars since each kind of completion.

    Four attributes, all None when nothing completed inside the widest window:
      me_same / te_same   a count in the SAME direction as the trade
      me_opp  / te_opp    a count in the OPPOSITE direction — the control
    """
    widest = max(WINDOWS)
    cache = {}
    for tf, cs_by_sym in by_tf_cs.items():
        for sym, cs in cs_by_sym.items():
            k = counts(cs)
            cache[(tf, sym)] = dict(
                idx={c.t: i for i, c in enumerate(cs)},
                me_buy=bars_since([v == 9 for v in k.buy_setup], widest),
                me_sell=bars_since([v == 9 for v in k.sell_setup], widest),
                te_buy=bars_since([v == 13 for v in k.buy_cd], widest),
                te_sell=bars_since([v == 13 for v in k.sell_cd], widest))
    missed = 0
    for t in rows:
        c = cache.get((t.tf, t.sym))
        i = c["idx"].get(t.t) if c else None
        if i is None:
            missed += 1
            MARKS[id(t)] = dict(me_same=None, me_opp=None,
                                te_same=None, te_opp=None)
            continue
        # A BUY count is a stretched DECLINE looking for a bullish turn, so it
        # pairs with a LONG. Getting this inverted would quietly turn the test
        # into its own control.
        MARKS[id(t)] = dict(
            me_same=(c["me_buy"] if t.is_long else c["me_sell"])[i],
            me_opp=(c["me_sell"] if t.is_long else c["me_buy"])[i],
            te_same=(c["te_buy"] if t.is_long else c["te_sell"])[i],
            te_opp=(c["te_sell"] if t.is_long else c["te_buy"])[i])
    return missed


def mean_se(rows):
    if len(rows) < 2:
        return None
    rs = [t.r for t in rows]
    m = sum(rs) / len(rs)
    sd = math.sqrt(sum((r - m) ** 2 for r in rs) / (len(rs) - 1))
    return m, sd / math.sqrt(len(rs))


def halves(rows):
    order = sorted(rows, key=lambda x: x.exit_t)
    out = []
    for part in (order[:len(order) // 2], order[len(order) // 2:]):
        s = mean_se(part)
        out.append(s[0] if s else float("nan"))
    return out


def compare(pop, attr, window):
    """(near, far) stats plus the difference and its SE, or None if too thin."""
    near = [t for t in pop
            if mark(t, attr) is not None and mark(t, attr) <= window]
    nearset = set(id(t) for t in near)
    far = [t for t in pop if id(t) not in nearset]
    if len(near) < 30 or len(far) < 30:
        return None
    a, b = mean_se(near), mean_se(far)
    diff = a[0] - b[0]
    se = math.sqrt(a[1] ** 2 + b[1] ** 2)
    return dict(n_near=len(near), m_near=a[0], se_near=a[1],
                n_far=len(far), m_far=b[0], diff=diff, se=se,
                z=abs(diff) / se if se else 0.0, h=halves(near))


HEAD = (f"  {'window':<10}{'n near':>8}{'R near':>9}{'R far':>9}"
        f"{'diff':>9}{'se':>8}{'|z|':>6}{'1st':>8}{'2nd':>8}")


def block(title, pop, same_attr, opp_attr):
    print(f"\n  {title}  ({len(pop)} trades)")
    print(HEAD)
    for w in WINDOWS:
        s = compare(pop, same_attr, w)
        o = compare(pop, opp_attr, w)
        if s is None:
            print(f"  {'<= ' + str(w) + ' bars':<10}   too thin")
            continue
        flag = ' *' if s["z"] >= 2 else ''
        print(f"  {'<= ' + str(w) + ' bars':<10}{s['n_near']:>8}"
              f"{s['m_near']:>+9.3f}{s['m_far']:>+9.3f}{s['diff']:>+9.3f}"
              f"{s['se']:>8.3f}{s['z']:>6.1f}{s['h'][0]:>+8.3f}"
              f"{s['h'][1]:>+8.3f}{flag}")
        if o is not None:
            print(f"  {'  control':<10}{o['n_near']:>8}"
                  f"{o['m_near']:>+9.3f}{o['m_far']:>+9.3f}{o['diff']:>+9.3f}"
                  f"{o['se']:>8.3f}{o['z']:>6.1f}{o['h'][0]:>+8.3f}"
                  f"{o['h'][1]:>+8.3f}")


async def main():
    by_tf, by_tf_cs = {}, {}
    async with aiohttp.ClientSession() as sess:
        syms = await universe(sess)
        zday = await context(sess, syms, DAY)
        z8h = await context(sess, syms, H8)
        for tf in TFS:
            cs = await load_universe(
                sess, syms, tf, DAYS,
                min_bars=int(0.8 * DAYS * 86400 // BAR_SECONDS[tf]))
            by_tf_cs[tf] = cs
            r = await collect(sess, cs, zday, z8h, interval=tf)
            by_tf[tf] = [t for t in r if t.filled and t.exit_t is not None]

    sent = [t for tf in TFS for t in by_tf[tf] if t.day]
    missed = tag(sent, by_tf_cs)
    pick = pick_rolling(sent, KEYS["A  tf > band > confd  (shipped)"], COOLDOWN)

    print("EXHAUSTION CONFLUENCE — does a count near a signal change anything?")
    print(f"{len(syms)} symbols · {DAYS} days · 15m+30m+1h")
    print(f"{len(sent)} sent, {len(pick)} picked"
          + (f" · {missed} trades could not be matched to a bar" if missed else ""))
    print("\nMOMENTUM = the 9-bar setup.  TERMINAL = the 13-bar countdown.")
    print("'control' is the SAME test against the OPPOSITE direction. If the")
    print("control moves as much as the signal, the mechanism is not")
    print("exhaustion — it is whatever both directions share.")
    print("* marks |z| >= 2. Sixteen looks are taken, so roughly one will")
    print("clear by chance; the control and the two halves are what separate a")
    print("finding from a coincidence.")

    print(f"\n{'=' * 88}\nPRIMARY — THE 🎯 PICKS\n{'=' * 88}")
    block("MOMENTUM 9", pick, "me_same", "me_opp")
    block("TERMINAL 13", pick, "te_same", "te_opp")

    print(f"\n{'=' * 88}\nSECONDARY — EVERY ALERT SENT (more power, not the "
          f"claim)\n{'=' * 88}")
    block("MOMENTUM 9", sent, "me_same", "me_opp")
    block("TERMINAL 13", sent, "te_same", "te_opp")

    # How often this even arises. A confluence that fires on 1% of picks is a
    # curiosity whatever its number; one that fires on 40% is a filter.
    print(f"\n{'=' * 88}\nHOW OFTEN IT ARISES\n{'=' * 88}")
    print(f"  {'window':<10}{'ME same':>10}{'ME opp':>10}"
          f"{'TE same':>10}{'TE opp':>10}")
    for w in WINDOWS:
        row = []
        for a in ("me_same", "me_opp", "te_same", "te_opp"):
            k = sum(1 for t in pick
                    if mark(t, a) is not None and mark(t, a) <= w)
            row.append(f"{100 * k / len(pick):>9.1f}%")
        print(f"  {'<= ' + str(w) + ' bars':<10}" + "".join(row))

    # And what the picked stream looks like split by timeframe, since a count
    # on 15m and a count on 1h are different objects with the same name.
    print(f"\n{'=' * 88}\nBY TIMEFRAME, TERMINAL WITHIN 5 BARS\n{'=' * 88}")
    print(HEAD)
    for tf in TFS:
        sub = [t for t in pick if t.tf == tf]
        s = compare(sub, "te_same", 5)
        if s is None:
            print(f"  {tf:<10}   too thin ({len(sub)} trades)")
            continue
        print(f"  {tf:<10}{s['n_near']:>8}{s['m_near']:>+9.3f}"
              f"{s['m_far']:>+9.3f}{s['diff']:>+9.3f}{s['se']:>8.3f}"
              f"{s['z']:>6.1f}{s['h'][0]:>+8.3f}{s['h'][1]:>+8.3f}")

    # Drawdown, because R per trade alone has never been this project's
    # primary. If the confluence subset is a better STREAM, it shows here.
    print(f"\n{'=' * 88}\nAS A STREAM — picks with a Terminal within 5 bars\n"
          f"{'=' * 88}")
    for label, sub in (("all picks", pick),
                       ("with TE <= 5",
                        [t for t in pick if mark(t, "te_same") is not None
                         and mark(t, "te_same") <= 5]),
                       ("without",
                        [t for t in pick if mark(t, "te_same") is None
                         or mark(t, "te_same") > 5])):
        if len(sub) < 30:
            print(f"  {label:<16}{len(sub):>6}  too thin")
            continue
        order = sorted(sub, key=lambda x: x.exit_t)
        rs = [t.r for t in order]
        dd, _ = drawdown(rs)
        print(f"  {label:<16}{len(sub):>6}  total {sum(rs):>+8.1f} R   "
              f"maxDD {dd:>6.1f}   recovery {sum(rs) / dd if dd else 0:>6.2f}")


if __name__ == "__main__":
    asyncio.run(main())
