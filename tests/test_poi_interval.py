"""The POI names the timeframe it actually reads.

THIS TEST EXISTS BECAUSE THE BOT LIED TO ITS USER FOR TWO DAYS AND NOTHING
CAUGHT IT. trend.poi_at read TREND_INTERVAL, and on 9 Sep that moved Day1 ->
Hour8 for a measurement about the SuperTrend and the DI. The point of interest
went with it. Every description stayed put: poi_at's own first line, the
daily_zones name, six comment blocks in config.py, /help, /stats, and
engine._POI — the string printed on the grade line of every single alert. The
filter behaved correctly throughout and was described wrongly everywhere,
which is the failure mode with no symptom.

The engine already had the right pattern for this. _TL, the trend half of the
grade, was made dynamic the first time TREND_INTERVAL moved, with a comment
saying the literal word "daily" was "correct only for as long as the default
never moved". The POI half was left literal and then that prediction came true
about it.

WHAT IS ASSERTED, and deliberately not more: that the label tracks the key, and
that the key defaults to TREND_INTERVAL so the behaviour before it existed is
the behaviour with it unset. Whether Hour8 or Day1 is the better POI is a
research question (research/studies/poi_tf.py says |z| 0.1, i.e. neither), not
something a test should pin.

    PYTHONPATH=. python3 tests/test_poi_interval.py
"""
import importlib
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def load(**env):
    """Re-import config, engine and trend under a fresh environment.

    All three read their intervals at IMPORT time, which is the whole reason a
    stale module constant could go wrong silently in the first place, so a test
    that only sets os.environ would assert nothing.
    """
    keep = {k: os.environ.get(k) for k in
            ("RIPTIDE_POI_INTERVAL", "RIPTIDE_TREND_INTERVAL")}
    try:
        for k, v in env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        for m in ("riptide.trend", "riptide.engine", "riptide.config"):
            sys.modules.pop(m, None)
        cfg = importlib.import_module("riptide.config")
        eng = importlib.import_module("riptide.engine")
        trd = importlib.import_module("riptide.trend")
        return cfg, eng, trd
    finally:
        for k, v in keep.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def test_defaults_to_the_trend_interval():
    cfg, eng, _ = load(RIPTIDE_POI_INTERVAL=None,
                       RIPTIDE_TREND_INTERVAL="Hour8")
    assert cfg.POI_INTERVAL == cfg.TREND_INTERVAL == "Hour8"
    assert eng._POI == "8h POI", eng._POI


def test_the_label_follows_the_key():
    for interval, word in (("Day1", "daily POI"), ("Hour8", "8h POI"),
                           ("Hour4", "4h POI"), ("Min60", "1h POI")):
        _, eng, _ = load(RIPTIDE_POI_INTERVAL=interval)
        assert eng._POI == word, (interval, eng._POI)
        # And it reaches the alert: the grade's reason string is what the
        # message prints, so an unlabelled constant here would show up there.
        assert word in eng.GRADES[(False, True, True)][1]


def test_it_moves_independently_of_the_trend():
    """The point of having a second key at all.

    Before this, asking for a daily POI meant moving the SuperTrend and the DI
    to daily too — three findings entangled in one setting.
    """
    cfg, eng, _ = load(RIPTIDE_POI_INTERVAL="Day1",
                       RIPTIDE_TREND_INTERVAL="Hour8")
    assert cfg.POI_INTERVAL == "Day1"
    assert cfg.TREND_INTERVAL == "Hour8"
    assert eng.GRADES[(False, True, True)][1] == "daily POI · 8h trend agrees"


def test_a_bad_value_falls_back_rather_than_crashing():
    cfg, _, _ = load(RIPTIDE_POI_INTERVAL="Nonsense",
                     RIPTIDE_TREND_INTERVAL="Hour8")
    assert cfg.POI_INTERVAL == "Hour8"


def test_poi_at_reads_the_poi_interval_not_the_trend_one():
    """The behavioural half. A label that tracks a key nothing reads is worse
    than no label, so this asserts the fetch itself."""
    import asyncio

    for want in ("Day1", "Hour8"):
        cfg, eng, trd = load(RIPTIDE_POI_INTERVAL=want,
                             RIPTIDE_TREND_INTERVAL="Min30")
        asked = []

        async def fetch(sess, symbol, interval=""):
            asked.append(interval)
            # One bar is enough: _series only needs a non-empty series, and
            # what is under test is which interval was requested.
            return [eng.Candle(0, 1.0, 1.0, 1.0, 1.0, 0.0)]

        asyncio.run(trd.poi_at(None, "X_USDT", 10_000, 1.0, True, fetch))
        assert asked == [want], (want, asked)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
