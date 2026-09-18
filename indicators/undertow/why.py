"""Why did the chart not take the setup I took?

    PYTHONPATH=. python3 indicators/undertow/why.py BTC_USDT Min30 "2026-09-09 18:00"
    PYTHONPATH=. python3 indicators/undertow/why.py BTC_USDT Min30 "2026-09-09 18:00" --bars 40

Nothing in the machine could answer this. The funnel counters say how many
candidates died at each stage and never WHICH BAR or WHICH GATE, so
"I took this and the chart did not" had no reply but a guess. `run(trace=True)`
records the gate state of every bar and this reads it back.

HOW TO USE THE ANSWER, and this matters more than the tool:

    A MECHANISM DEFECT is worth fixing whatever that trade did. "The whole
    pullback was discarded because its highest bar was a doji and locTol is 0"
    is a defect -- the rule threw away a pullback it had no opinion about.

    A THRESHOLD IS NOT A DEFECT. "The lower wick was 0.04 and the cut is 0.05"
    is the gate working. Moving a cut to admit one remembered trade is fitting
    to an outcome, and ../measurements/UNDERTOW_PARAMS.md priced that kind of
    selection at -0.31 R per trade of illusion.

The difference is whether the reason would still be a reason if the trade had
lost. Remembered setups are a biased sample -- they are the ones that worked --
so the only safe thing to take from them is MECHANISM.
"""
from __future__ import annotations

import datetime as dt
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from indicators.undertow.port import undertow as U               # noqa: E402
from indicators.undertow.studies.undertow_sweep import load      # noqa: E402

# The gates in the order run() applies them. The FIRST false is the reason.
GATES = [
    ("tradeable", "the bias is not tradeable — none or ending"),
    ("famOk", "shape: neither wick dominates by wickEdge, or the strict "
              "gate refused the non-priority shape"),
    ("colourOk", "wrong colour for the bias"),
    ("locOk", "not at the pullback extreme — locTol is 0, so the bar must BE "
              "the extreme bar"),
    ("htfOk", "the higher timeframe disagrees"),
    ("bosOk", "no break of structure behind the pullback yet"),
]


def parse_when(s):
    for f in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(s, f).replace(
                tzinfo=dt.timezone.utc).timestamp()
        except ValueError:
            pass
    raise SystemExit(f"cannot read a time from {s!r} — use 'YYYY-MM-DD HH:MM' UTC")


def main(sym, tf, when, span=30, **over):
    cs = load(tf, [sym]).get(sym)
    if not cs:
        raise SystemExit(f"no cached candles for {sym} {tf}")
    p = U.P(**over)
    r = U.run(cs, p, sym, trace=True)
    ts = parse_when(when)
    mid = min(range(len(cs)), key=lambda k: abs(cs[k].t - ts))
    lo, hi = max(0, mid - span), min(len(cs), mid + span)

    print(f"\n  {sym} {tf} around "
          f"{dt.datetime.fromtimestamp(cs[mid].t, dt.timezone.utc):%Y-%m-%d %H:%M} UTC")
    print(f"  bar {mid}, window {lo}..{hi}\n")
    print(f"  {'time':16} {'bar':>6} {'close':>11} {'dir':>4} {'state':>9} "
          f"{'upW':>6} {'dnW':>6} {'  '}why not")
    tr = {t["i"]: t for t in r.trace}
    admitted = []
    for i in range(lo, hi):
        t = tr.get(i)
        if t is None:
            continue
        when_s = f"{dt.datetime.fromtimestamp(t['t'], dt.timezone.utc):%m-%d %H:%M}"
        if t["admitted"]:
            reason = "** ADMITTED — became a candidate **"
            admitted.append(i)
        else:
            reason = next((why for k, why in GATES if not t[k]), "?")
            if not t["locOk"]:
                reason += f"  ({t['barsFromAnchor']} bars past the extreme)"
        print(f"  {when_s:16} {i:6} {t['c']:11.2f} {t['dir']:+4} "
              f"{t['state']:>9} {t['upW']:6.3f} {t['dnW']:6.3f}   {reason}")

    print(f"\n  ADMITTED IN THIS WINDOW: {len(admitted)}")
    if not admitted:
        stuck = {}
        for i in range(lo, hi):
            t = tr.get(i)
            if t and not t["admitted"]:
                k = next((kk for kk, _ in GATES if not t[kk]), "?")
                stuck[k] = stuck.get(k, 0) + 1
        print("  every bar was refused, and by which gate:")
        for k, n in sorted(stuck.items(), key=lambda kv: -kv[1]):
            print(f"      {k:12} {n:4} bars")

    # WHAT HAPPENED NEXT to anything that was admitted. Admission is not
    # arming: on BTC Min30 the shipped configuration admits 138 bars and arms
    # SIX, so "the chart did not take it" is usually a confirmation failure
    # rather than a detection one, and blaming the gates would be wrong.
    arm = {a["pin"]: a for a in r.armed}
    fill = {f["pin"]: f for f in r.fills}
    for i in admitted:
        a = arm.get(i)
        if a is None:
            print(f"    bar {i}: admitted, NEVER ARMED — the Working/Failure "
                  f"pair did not complete inside confirmBars={p.confirmBars}")
            continue
        f = fill.get(i)
        got = next((t for t in r.real if t.bar == i), None)
        print(f"    bar {i}: ARMED at {a['bar']}  entry {a['entry']:.2f} "
              f"stop {a['stop']:.2f} target {a['target']:.2f} code {a['code']}"
              + ("" if f else "  — never filled")
              + (f"  → R {got.r:+.2f}" if got else ""))


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    span = 30
    if "--bars" in sys.argv:
        span = int(sys.argv[sys.argv.index("--bars") + 1])
    if len(args) < 3:
        raise SystemExit(__doc__.split("\n\n")[1].strip())
    main(args[0], args[1], args[2], span=span)
