"""One raid printing on two timeframes is one idea, and the alert says so.

WHY THIS EXISTS. Min60 was added to RIPTIDE_INTERVALS on 11 Sep, so the bot now
scans 15m, 30m and 1h in full. A single raid on a single symbol routinely
prints on two or three of them inside the same hour. tag_event_pick cannot see
that: it groups on (tf, bar, direction), so its "size once" chip and its pick
are computed strictly INSIDE one timeframe. Without a cross-timeframe mark the
reader gets three messages for one idea, with a 🎯 on each, and the obvious
reading is three trades.

That is the exact failure the 🔗 chip was built to prevent, arriving through a
door 🔗 does not watch.

WHAT IS ASSERTED, and deliberately not more. That duplicates within one bar of
the slowest scanned timeframe are marked, that non-duplicates are not, and that
the mark never becomes a filter — the tagger only ever writes `also_tf`. Which
timeframe to prefer is NOT asserted, because research/studies/timeframes.py
found no pair of timeframes separating at even 1 SE, so there is nothing to
rank on and the code must not pretend otherwise.

    PYTHONPATH=. python3 tests/test_cross_tf.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from riptide.config import BAR_SECONDS, INTERVALS         # noqa: E402
from riptide.scanner import tag_cross_tf                  # noqa: E402
from riptide.telegram import marks                        # noqa: E402


class Sig:
    """The handful of attributes the tagger reads. Not a Setup, on purpose:
    the tagger uses getattr throughout so it survives both Setup and Early,
    and a stub proves it does not secretly depend on one of them."""

    def __init__(self, symbol, is_long, tf, fvg_time):
        self.symbol = symbol
        self.is_long = is_long
        self.tf = tf
        self.fvg_time = fvg_time
        self.mss_time = 0
        self.sweep_time = 0


def wrap(sigs):
    """The shape cycle() hands the taggers: (setups, _, early, _) per symbol."""
    return [(sigs, None, [], None)]


def test_the_same_raid_on_two_timeframes_is_marked_on_both():
    a = Sig("BTC_USDT", True, "Min15", 10_000)
    b = Sig("BTC_USDT", True, "Min60", 10_000)
    tag_cross_tf(wrap([a, b]))
    assert a.also_tf == ("Min60",), a.also_tf
    assert b.also_tf == ("Min15",), b.also_tf


def test_three_timeframes_all_see_the_other_two_slowest_last():
    a = Sig("SOL_USDT", False, "Min15", 50_000)
    b = Sig("SOL_USDT", False, "Min30", 50_000)
    c = Sig("SOL_USDT", False, "Min60", 50_000)
    tag_cross_tf(wrap([a, b, c]))
    assert a.also_tf == ("Min30", "Min60"), a.also_tf
    assert c.also_tf == ("Min15", "Min30"), c.also_tf


def test_a_different_symbol_or_direction_is_a_different_idea():
    a = Sig("BTC_USDT", True, "Min15", 10_000)
    other_sym = Sig("ETH_USDT", True, "Min60", 10_000)
    other_dir = Sig("BTC_USDT", False, "Min60", 10_000)
    tag_cross_tf(wrap([a, other_sym, other_dir]))
    assert a.also_tf == ()
    assert other_sym.also_tf == ()
    assert other_dir.also_tf == ()


def test_the_same_timeframe_twice_is_left_to_tag_event_pick():
    """Two Min15 signals on one symbol are breadth's business, not this one's,
    and double-marking them would put two chips on one fact."""
    a = Sig("BTC_USDT", True, "Min15", 10_000)
    b = Sig("BTC_USDT", True, "Min15", 10_000)
    tag_cross_tf(wrap([a, b]))
    assert a.also_tf == () and b.also_tf == ()


def test_far_apart_in_time_is_not_the_same_raid():
    """The window is one bar of the SLOWEST scanned timeframe, each way."""
    span = max(BAR_SECONDS[i] for i in INTERVALS)
    a = Sig("BTC_USDT", True, "Min15", 100_000)
    near = Sig("BTC_USDT", True, "Min60", 100_000 + span)
    far = Sig("BTC_USDT", True, "Min30", 100_000 + span * 3)
    tag_cross_tf(wrap([a, near, far]))
    assert a.also_tf == ("Min60",), a.also_tf
    assert far.also_tf == ()


def test_no_edge_effect_where_a_bucket_would_have_one():
    """A floored bucket would split 09:59 from 10:00 and pair 10:00 with
    10:59. A window does neither, which is the whole reason it is a window."""
    hour = max(BAR_SECONDS[i] for i in INTERVALS)
    straddling = Sig("BTC_USDT", True, "Min15", 6 * hour - 60)
    on_the_hour = Sig("BTC_USDT", True, "Min60", 6 * hour)
    tag_cross_tf(wrap([straddling, on_the_hour]))
    assert straddling.also_tf == ("Min60",)
    assert on_the_hour.also_tf == ("Min15",)


def test_it_reaches_the_alert():
    a = Sig("BTC_USDT", True, "Min15", 10_000)
    b = Sig("BTC_USDT", True, "Min60", 10_000)
    tag_cross_tf(wrap([a, b]))
    a.tl_break = -1
    out = marks(a) or ""
    assert "🔁 same raid on 1h" in out, out


def test_it_suppresses_nothing():
    """The tagger writes one attribute and nothing else. If it ever gains the
    power to drop a signal, this fails."""
    a = Sig("BTC_USDT", True, "Min15", 10_000)
    b = Sig("BTC_USDT", True, "Min60", 10_000)
    before = dict(vars(a))
    tag_cross_tf(wrap([a, b]))
    after = dict(vars(a))
    changed = {k for k in after if before.get(k, object()) != after[k]}
    assert changed == {"also_tf"}, changed


def test_a_single_timeframe_scan_marks_nothing():
    a = Sig("BTC_USDT", True, "Min30", 10_000)
    b = Sig("BTC_USDT", True, "Min30", 10_000)
    tag_cross_tf(wrap([a, b]))
    assert a.also_tf == () and b.also_tf == ()


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
