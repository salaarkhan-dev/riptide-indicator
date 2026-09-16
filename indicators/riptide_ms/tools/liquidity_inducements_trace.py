"""Reproducer for two claims in audit/LIQUIDITY_INDUCEMENTS_AUDIT.md.

No Pine compiler exists in this environment, so these are traces of the
script's own arithmetic against Pine's documented semantics, not a run of the
indicator. Both claims are deterministic — they do not depend on market data.

    python3 indicators/riptide_ms/tools/liquidity_inducements_trace.py

Pine semantics modelled:
  * `time[i]` for i > bar_index returns `na`.
  * any comparison with `na` yields `na`, and `if na` does not branch.
  * `max_bars_back` defaults to ~300 when the script does not declare it, and
    a historical reference beyond it is a runtime error, not a na.
"""
NA = None


def lt(a, b):
    """Pine `a < b` with na propagation."""
    if a is NA or b is NA:
        return NA
    return a < b


def set_bar_index(times, bar_index, bar_time, max_bars_back=300, cap=1000):
    """Line 102-110 of the source, transcribed.

        barIndex = 0
        i = 0
        while true
            if time[i] < barTime
                barIndex := bar_index - (i - 1)
                break
            i += 1

    `times` is indexed as Pine does it: times[0] is the current bar.
    """
    i = 0
    while True:
        if i > max_bars_back:
            return ("RUNTIME ERROR: historical offset beyond max_bars_back", i)
        t = times[i] if i < len(times) else NA
        if lt(t, bar_time) is True:
            return ("ok", bar_index - (i - 1))
        i += 1
        if i > cap:
            return ("INFINITE LOOP: na never satisfies the break", i)


def claim_1():
    print("=" * 74)
    print("CLAIM 1  SetBarIndex has no termination condition when it runs off")
    print("         the loaded history")
    print("=" * 74)
    # 400 bars of 30m history, newest first, as Pine indexes them.
    step = 1800
    now = 1_700_000_000
    times = [now - k * step for k in range(400)]
    bar_index = 399

    cases = [
        ("pivot 5 bars back, plenty of history", times[5], 300),
        ("pivot on the OLDEST loaded bar", times[-1], 300),
        ("pivot older than ALL loaded history", times[-1] - 10 * step, 300),
        ("...same, with max_bars_back raised", times[-1] - 10 * step, 5000),
    ]
    for label, bt, mbb in cases:
        print(f"  {label:<38} {set_bar_index(times, bar_index, bt, mbb)}")
    print()
    print("  The last two rows are the same input. Which failure you see")
    print("  depends only on a limit the script never declares.")
    print()
    print("  A pivot fetched from a higher timeframe carries that timeframe's")
    print("  open time. When the chart's loaded window does not reach back to")
    print("  it, `time[i]` is na, `na < barTime` is na, the `if` never taken,")
    print("  and `i` increments without bound. The script does not declare")
    print("  max_bars_back, so which limit fires first is not under its")
    print("  control -- either way the outcome is an error, not a drawing.")
    print()


def claim_2():
    print("=" * 74)
    print("CLAIM 2  The equal-pivot gate is only satisfied when the right")
    print("         pivot length is exactly 1")
    print("=" * 74)
    step = 1800
    now = 1_700_000_000
    times = [now - k * step for k in range(400)]
    bar_index = 399

    print(f"  {'right len':>10}{'Time = time[R]':>18}{'BarIndex':>12}"
          f"{'gate wants':>12}{'fires?':>9}")
    for R in (1, 2, 3, 5, 10):
        # GetEqualPivotsPivots: Time = time[settings.PivotRightLength]
        bt = times[R]
        status, bi = set_bar_index(times, bar_index, bt)
        assert status == "ok"
        # EqualPivotsInducementAndLiquidity: if latestPivot.BarIndex ==
        #                                    bar_index - 1
        want = bar_index - 1
        print(f"  {R:>10}{'time[%d]' % R:>18}{bi:>12}{want:>12}"
              f"{str(bi == want):>9}")
    print()
    print("  CreateRetracementInducement writes the same test as")
    print("  `bar_index - settings.PivotRightLength`, which holds for every R.")
    print("  The equal-pivot copy hard-codes 1. That is the inconsistency.")
    print()
    print("  On a HIGHER timeframe the pivot's Time is an HTF bar's open, so")
    print("  BarIndex lands on whatever chart bar opened it -- neither")
    print("  `bar_index - 1` nor `bar_index - R`. Both gates then fail on")
    print("  essentially every bar:")
    htf = 48  # 1D pivot on a 30m chart, right length 1 -> ~48 chart bars
    bt = times[htf]
    status, bi = set_bar_index(times, bar_index, bt)
    print(f"    1D pivot on a 30m chart: BarIndex={bi}, gate wants "
          f"{bar_index - 1} -> {bi == bar_index - 1}")
    print()


if __name__ == "__main__":
    claim_1()
    claim_2()
