"""Exhaustion counts — the 9-count and the 13-count, as a watch indicator.

WHAT THIS IS FOR. riptide-reversal.pine draws a 9-bar Momentum count and a
13-bar Terminal count on whatever chart you have open. Nobody can keep a
hundred charts open. This is that indicator across the whole universe: one
message per bar close saying which symbols just completed a count, with a link
straight to each chart at the right timeframe. "Which chart should I open" —
nothing more.

IT IS NOT A TRADE, AND THE MEASUREMENT IS NOT MERELY ABSENT — IT CAME BACK
NEGATIVE. indicators/exhaustion/studies/exhaustion.py joined these counts to
Riptide's own signals over 333 days and 9118 trades. A 🎯 landing near a
completed count scored no better, and the control settles it: the OPPOSITE
direction benefited MORE (+0.273 against +0.093 on the picks, +0.281 against
+0.096 on the full stream), and the only cells clearing 2 SE anywhere in the
table were control cells. Whatever these counts mark, it is not exhaustion —
it is a regime both sides ride.

So there is no entry, no stop, no target, no grade, and no outcome tracking.
`riptide/watch.py` enforces that for every indicator; this file could not arm a
row if it wanted to.

──────────────────────────────────────────────────────────────────────────────
THE VOLUME PROBLEM, WHICH DECIDED EVERY DEFAULT IN THIS FILE

Rows a day across the real universe, 59 symbols over 333 days, from
indicators/exhaustion/studies/exhaust_rate.py — rerun it rather than trusting
this comment, which is what the first version of this table needed and did not
get:

    tf     M9/day   M9★/day   T13/day    both   both★
    15m      128        96        40      167     136
    30m       66        49        19       85      68
    1h        34        24         9       43      34
    ALL      227       169        68      295     237

These are ROWS, not messages — the watch sends one digest per bar close
carrying every symbol that completed on it, so 1h is at most 24 messages. Rows
are still the unit that decides anything, because a forty-row digest is the one
that does not get read.

Everything on is 295 rows a day: three and a half times Riptide's entire alert
volume and sixteen times the number of 🎯 picks. Shipping that would drown the
one thing in this chat with a measured effect, to add a stream that has none.

SO IT SHIPS OFF. RIPTIDE_EXHAUST_ALERTS defaults to 0 and its loop starts but
never sends until /exhaust on. When it is switched on it begins in the quiet
corner of the table — 1h only, and a plain M9 must be PERFECTED to count: 24 +
9 = 33 a day. Everything else is one config key or one /exhaust away; see
riptide.conf.
"""

from __future__ import annotations

from ..config import (BAR_SECONDS, EXHAUST_ALERTS, EXHAUST_FRESH_BARS,
                      EXHAUST_INTERVALS, EXHAUST_KINDS, EXHAUST_MAX_LINES,
                      EXHAUST_PERFECT_ONLY)
from .registry import Hit, Indicator, Option, register

# How far back to look for a completed count. Anything older cannot pass the
# freshness gate, so walking further would only fill the dedupe table.
RECENT_BARS = 6


def sig_of(symbol: str, tf: str, bar_time: int, kind: str,
           is_long: bool) -> str:
    """The dedupe signature. UNCHANGED from before the watch was generalised —
    the rows already on disk carry these strings, and a new shape would replay
    the most recent bar of every watched timeframe on the first close after an
    update."""
    return f"EX|{symbol}|{tf}|{bar_time}|{kind}|{'U' if is_long else 'D'}"


def _counts(cs):
    """The 9-count and the 13-count over a candle list.

    A PORT OF A PORT, AND DELIBERATELY SO.
    indicators/exhaustion/port/td.py already holds this logic, checked line
    by line against the Pine and covered by invariants — but that tree is not
    importable from the live bot and must not become so:
    it pulls in the whole study stack, and a research refactor must never be
    able to break a running scanner. The two are kept in step by hand, and the
    shared test (indicators/exhaustion/tests/test_exhaust.py) runs BOTH and
    asserts they agree bar for bar, so a drift fails rather than hides.
    """
    n = len(cs)
    out = [(0, 0, 0, 0, False, False, 0.0, 0.0)] * n
    if n < 6:
        return out
    buy = sell = buy_cd = sell_cd = 0
    buy_res = sell_sup = 0.0
    start_buy = start_sell = False
    buy_ref8 = sell_ref8 = 0.0
    res = []
    for i in range(n):
        c, h, lo = cs[i].c, cs[i].h, cs[i].l
        falling = i >= 4 and c < cs[i - 4].c
        rising = i >= 4 and c > cs[i - 4].c
        buy_flip = i >= 5 and falling and cs[i - 1].c > cs[i - 5].c
        sell_flip = i >= 5 and rising and cs[i - 1].c < cs[i - 5].c

        if falling:
            buy = (1 if buy_flip else 0) if buy in (0, 9) else buy + 1
            sell = 0
        elif rising:
            sell = (1 if sell_flip else 0) if sell in (0, 9) else sell + 1
            buy = 0
        else:
            buy = sell = 0

        if i >= 3:
            bperf = ((lo <= cs[i - 3].l and lo <= cs[i - 2].l)
                     or (cs[i - 1].l <= cs[i - 3].l
                         and cs[i - 1].l <= cs[i - 2].l))
            sperf = ((h >= cs[i - 3].h and h >= cs[i - 2].h)
                     or (cs[i - 1].h >= cs[i - 3].h
                         and cs[i - 1].h >= cs[i - 2].h))
        else:
            bperf = sperf = False

        if buy == 9:
            buy_res = max(x.h for x in cs[max(0, i - 8): i + 1])
        elif c > buy_res:
            buy_res = 0.0
        if sell == 9:
            sell_sup = min(x.l for x in cs[max(0, i - 8): i + 1])
        elif c < sell_sup:
            sell_sup = 0.0

        cd_buy = i >= 2 and c <= cs[i - 2].l
        cd_sell = i >= 2 and c >= cs[i - 2].h

        if buy == 9 and buy_cd == 0:
            start_buy = True
        elif sell == 9 or buy_cd == 13 or c > buy_res:
            start_buy = False
        if sell == 9 and sell_cd == 0:
            start_sell = True
        elif buy == 9 or sell_cd == 13 or c < sell_sup:
            start_sell = False

        if start_buy:
            if buy == 9:
                buy_cd = 1 if cd_buy else 0
            elif cd_buy:
                buy_cd += 1
        else:
            buy_cd = 0
        if start_sell:
            if sell == 9:
                sell_cd = 1 if cd_sell else 0
            elif cd_sell:
                sell_cd += 1
        else:
            sell_cd = 0

        if buy_cd == 13 and cd_buy and lo >= buy_ref8:
            buy_cd = 12
        if sell_cd == 13 and cd_sell and h <= sell_ref8:
            sell_cd = 12
        if buy_cd == 8 and (not res or res[-1][2] != 8):
            buy_ref8 = c
        if sell_cd == 8 and (not res or res[-1][3] != 8):
            sell_ref8 = c

        res.append((buy, sell, buy_cd, sell_cd,
                    bperf and buy == 9, sperf and sell == 9,
                    buy_res, sell_sup))
    return res


def detect(cs, symbol: str, tf: str, opts: dict) -> tuple:
    """Completed counts in the last RECENT_BARS bars, and how many this
    indicator's own gates threw away.

    The drop count is what lets /status tell "34 counts, all unperfected" from
    "the loop never woke". Both look like silence from the chat.
    """
    want = opts.get("kinds", EXHAUST_KINDS)
    perfect = opts.get("perfect", EXHAUST_PERFECT_ONLY)
    k = _counts(cs)
    step = BAR_SECONDS[tf]
    out, dropped = [], 0
    for i in range(max(0, len(cs) - RECENT_BARS), len(cs)):
        buy, sell, bcd, scd, bperf, sperf, buy_res, sell_sup = k[i]
        for kind, is_long, done, perf in (
                ("momentum", True, buy == 9, bperf),
                ("momentum", False, sell == 9, sperf),
                ("terminal", True, bcd == 13, False),
                ("terminal", False, scd == 13, False)):
            if not done:
                continue
            if want != "both" and want != kind:
                dropped += 1
                continue
            if kind == "momentum" and perfect and not perf:
                dropped += 1
                continue
            out.append(Hit(
                key=sig_of(symbol, tf, cs[i].t, kind, is_long),
                symbol=symbol, tf=tf, is_long=is_long,
                # Candle.t is the bar's OPEN and a count is only true once the
                # bar has CLOSED, so the moment it became real is t + step.
                # That is what the freshness gate and the "Nm ago" measure
                # from.
                bar_time=cs[i].t + step, price=cs[i].c,
                detail=_name(kind, perf),
                kind=kind, perfect=perf,
                level=buy_res if is_long else sell_sup))
    return out, dropped


def _name(kind: str, perfect: bool) -> str:
    return "T13" if kind == "terminal" else ("M9★" if perfect else "M9")


def _label(h) -> str:
    return _name(h.extra["kind"], h.extra["perfect"])


# Four groups in strength order, strongest first — a 13-count is the rarest
# thing here and a plain 9 the most common, so a reader who only reads the top
# of the message reads the rarest rows. The four words are the ones a reader
# actually asked for: the arrow says which way without needing "buy-side"
# explained again.
_GROUPS = {("terminal", True): (0, "STRONG LONG"),
           ("terminal", False): (1, "STRONG SHORT"),
           ("momentum", True): (2, "possible long"),
           ("momentum", False): (3, "possible short")}


def classify(h) -> tuple:
    rank, name = _GROUPS[(h.extra["kind"], h.is_long)]
    return (rank, -BAR_SECONDS[h.tf], h.symbol), name


# The alerts' own label column is 8, which these overrun — the first render
# read "strong longSOL 1h", and 14 still butted "possible short" against the
# symbol because the word is exactly that long. This digest gets its own width
# rather than shortening a label that has to be unambiguous at a glance.
GROUP_W = 16


def row(h, group: str) -> str:
    """One symbol in the digest. The label column carries the group only on its
    first row, so the rows under it read as a list."""
    from .. import watch                      # at call time: watch imports us
    return (watch.label(SPEC, group) + watch.chart(h)
            + f"  <i>{_label(h)}</i>")


# Completed counts a day per timeframe, as (M9, M9 perfected, T13), measured
# over 59 symbols and 333 days in
# indicators/exhaustion/studies/exhaust_rate.py.
# It is the number that set every default: all three timeframes unfiltered is
# 295 rows a day, three and a half times the bot's entire alert volume. Printed
# by /exhaust because the rate is the product decision, not a footnote to it.
RATE = {"Min15": (128, 96, 40),
        "Min30": (66, 49, 19),
        "Min60": (34, 24, 9)}


def rate(db, tfs=None, **over) -> int:
    """Alerts a day at a given setting. Defaults to the live one, and takes
    overrides so a message can quote the rate a change WOULD produce."""
    from .. import watch                      # at call time: watch imports us
    opts = watch.settings(db, SPEC)
    opts.update(over)
    tfs = tuple(tfs) if tfs is not None else watch.intervals(db, SPEC)
    total = 0
    for t in tfs:
        nine, nine_perf, thirteen = RATE.get(t, (0, 0, 0))
        if opts["kinds"] in ("both", "momentum"):
            total += nine_perf if opts["perfect"] else nine
        if opts["kinds"] in ("both", "terminal"):
            total += thirteen
    return total


SPEC = register(Indicator(
    name="exhaust",
    title="EXHAUSTION",
    glyph="⚖",
    unit="count",
    caveat=("a heads-up, not a trade — measured at no edge, and the opposite "
            "direction scored better. Go look."),
    detect=detect,
    row=row,
    classify=classify,
    # The counts need history to be meaningful at all. Under this a symbol is
    # not quiet, it has no answer, and returning nothing silently would look
    # identical.
    min_bars=60,
    recent_bars=RECENT_BARS,
    fresh_bars=EXHAUST_FRESH_BARS,
    max_lines=EXHAUST_MAX_LINES,
    label_w=GROUP_W,
    default_enabled=EXHAUST_ALERTS,
    default_intervals=tuple(EXHAUST_INTERVALS),
    fallback_interval="Min60",
    options=(
        Option("kinds", "choice", EXHAUST_KINDS,
               "the single biggest volume control after the timeframe — "
               "terminal alone is about a quarter of the traffic",
               choices=("both", "momentum", "terminal")),
        # On by default, and the cheapest useful filter here: a perfected count
        # is 74% of all M9s, so this is not the volume lever the timeframe is —
        # but an unperfected 9 is the weakest thing the indicator prints and it
        # is the one most likely to be read as a signal.
        Option("perfect", "bool", EXHAUST_PERFECT_ONLY,
               "whether a plain M9 counts, or only a perfected one"),
    ),
    tf_counted=tuple(RATE),
    rate=rate,
    blurb=("<i>The 9-count and 13-count off the Riptide reversal indicator, "
           "on every symbol at once, in one digest per bar close. A count "
           "measures how long a move has been going against itself — a "
           "completed one says the move is old, not that it is over.</i>\n\n"
           "<b>STRONG LONG</b> / <b>STRONG SHORT</b> <i>are completed "
           "13-counts (T13). </i><b>possible long</b> / <b>possible short</b>"
           "<i> are completed 9-counts (M9★).</i>"),
    evidence=("Scored through the same harness as everything else here, a 🎯 "
              "landing near a completed count did no better than one landing "
              "anywhere else — and the OPPOSITE direction scored three times "
              "as well (+0.273 against +0.093, and +0.296 against +0.057 on "
              "the sent stream at 2.3 SE). A signal whose control beats it is "
              "a shared regime read backwards. There is no entry, no stop and "
              "no grade on it, and it is not in /stats."),
    examples=("<i>All three, unfiltered, is 295 rows a day — three and a half "
              "times every alert this bot sends, and sixteen times the "
              "picks.</i>\n\n"
              "<code>/exhaust 30m,1h</code> — watch both\n"
              "<code>/exhaust terminal</code> — 13-counts only, far fewer\n"
              "<code>/exhaust perfect off</code> — plain 9s too, many more\n"
              "<code>/exhaust off</code> — stop them"),
))
