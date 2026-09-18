"""Does the LIVE WATCHER still trade the strategy the CHART draws?

    python3 deploy/undertow-three-way-check.py

WHY A THIRD CHECK. Two already existed and between them they left a hole big
enough to ship through:

    undertow-port-check.py     Pine inputs  ==  P's defaults
    test_watch_undertow.py     watcher output == port output, on fixtures
    test_studies_pin_...py     P's defaults have not moved unnoticed

The gap is that the watcher test compares OUTPUT on candles, running both sides
at whatever settings the test chooses -- so a setting the watcher holds at a
different value from the chart is invisible to it, as long as the port can be
asked to use that value too. And the port check never looks at the watcher.

THAT IS NOT HYPOTHETICAL. `max_live` was a FUNCTION DEFAULT in the watcher, 64,
while the chart shipped 4. The frozen-constants test could not see it because
it only inspects module-level constants; the parity test could not see it
because it passes max_live explicitly. Three files, three values, no check with
standing to complain.

THE DANGEROUS BUCKET IS NOT THE MISMATCHED CONSTANT, IT IS THE HARDCODE.

The watcher does not implement the whole of P. It runs ONE anchor, ONE bias
engine, ONE stop source, with the family and the colour rule always on. Each of
those is a P field the watcher never reads -- and each is fine ONLY while P
still defaults to the value the watcher assumes. The day `pinAt` defaults to
`leg extreme` on the chart, the watcher keeps pinning the pullback extreme, the
parity test keeps passing because it sets pinAt itself, and the bot alerts
setups that are not on the chart. That is the failure this file exists for, and
it is why every one of P's fields is listed below rather than the handful that
happened to have a matching constant.

WHAT THIS CHECKS

  MIRRORED   the watcher holds this setting somewhere -- a module constant, a
             riptide.config constant, or a function default -- and the value
             must equal P's default
  HARDCODED  the watcher implements exactly one value of this setting and does
             not read it. P must still default to that value
  ABSENT     the watcher does not implement this part of the strategy at all.
             Where the field has an off value, P must still be at it
  every field of P is in exactly one bucket, or this fails

  and, separately: no watcher function may take a parameter it never reads. A
  dead knob is worse than a missing one, because the chat command that sets it
  still answers as though it worked.

It does NOT check logic. Nothing short of running both can, and
test_watch_undertow.py is that. This checks the thing that silently differs.
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PORT = ROOT / "indicators/undertow/port/undertow.py"
WATCH = ROOT / "riptide/watchers/undertow.py"
CONFIG = ROOT / "riptide/config.py"

# ── bucket 1: MIRRORED ── P field -> where the watcher keeps it.
#   ("const", NAME)    module-level constant in the watcher
#   ("config", NAME)   constant in riptide/config.py, imported by the watcher
#   ("param", "fn/arg") a function default -- the one the other checks miss
MIRRORED = {
    "biasSrc": ("const", "BIAS_SRC"),
    "smcSwingLen": ("const", "SMC_SWING_LEN"),
    "smcInternalLen": ("const", "SMC_INTERNAL_LEN"),
    "confirmOrder": ("const", "CONFIRM_ORDER"),
    "failTest": ("const", "FAIL_TEST"),
    "pinNewest": ("const", "PIN_NEWEST"),
    "famPriority": ("const", "FAM_PRIORITY"),
    "famStrict": ("const", "FAM_STRICT"),
    # BOTH WERE HARDCODED AND BOTH BECAME REAL. This check is what said so, the
    # moment the chart's defaults moved: it had `armWins` pinned at False and
    # `stopSrc` at the pullback extreme with the watcher's code as the reason,
    # and the chart went to True and the minor swing on the same day. The
    # watcher implements both now and mirrors them.
    "armWins": ("const", "ARM_WINS"),
    "stopSrc": ("const", "STOP_SRC"),
    "endMinor": ("const", "END_MINOR"),
    "endSweep": ("const", "END_SWEEP"),
    "endStale": ("const", "END_STALE"),
    "staleBars": ("const", "STALE_BARS"),
    "retraceMax": ("const", "RETRACE_MAX"),
    "wickEdge": ("const", "WICK_EDGE"),
    "locTol": ("const", "LOC_TOL"),
    "stopBuf": ("const", "STOP_BUF"),
    "stopTrack": ("const", "STOP_TRACK"),
    "rr": ("const", "RR"),
    "confirmBars": ("config", "UNDERTOW_CONFIRM_BARS"),
    "fillBars": ("config", "UNDERTOW_FILL_BARS"),
    "maxLive": ("param", "run_setups/max_live"),
}

# ── bucket 2: HARDCODED ── the watcher implements ONE value and never reads
# the setting. The required default is what the watcher's code assumes; if P
# moves off it the chart and the bot part company in silence.
HARDCODED = {
    "pinAt": ("pullback extreme",
              "run_setups pins at pbExtX and has no anchor branch"),
    "workTest": ("close beyond",
                 "wHit is a strict close past the Working line"),
    "needBos": (False,
                "arming does not gate on bosN; bosN only labels the state"),
    "useHammer": (True, "the hammer family always arms"),
    "useStar": (True, "the star family always arms"),
    "useFamily": (True, "famHam/famStar is the only shape gate"),
    "useColour": (True, "colourOk is unconditional"),
    "pbMinAge": (0, "no age test on the pullback extreme"),
    "pbMinDepth": (0.0, "no depth test on the pullback extreme"),
}

# ── bucket 3: ABSENT ── the watcher does not implement this at all. Where the
# field has an OFF value, it must still be there; where it has none, the entry
# is None and the reason carries the justification.
ABSENT = {
    # RESEARCH-ONLY PIN SELECTION. The watcher takes the newest qualifying
    # candle and both directions, which is `pinLag` 0 and `shortsOnly` False --
    # so the OFF value IS asserted here rather than left as None. A default
    # moving would put the live alerts on a different candle from the chart
    # without a line of code changing anywhere.
    "pinLag": (0, "the watcher trades the newest qualifying candle"),
    "retraceLatch": (True, "the watcher latches Ending like the chart"),
    "biasGate": ("tradeable", "the watcher refuses a setup while Ending"),
    "locAtr": (0.0, "the watcher's location test counts bars"),
    "pbLook": (10, "PIN_LOCAL only; the watcher has no local anchor"),
    "shortsOnly": (False, "the watcher alerts both directions"),
    # the nine bias sources the watcher does not run. Guarded by biasSrc,
    # which is MIRRORED, so a switch away from SMC is caught there.
    # THESE TWO WERE IN THE HARDCODED BUCKET AND THE REASONS WERE WRONG.
    # `matureBars` was justified as "the watcher labels immature as bosN == 0,
    # which is the port's rule at this default" -- but the port's rule is
    # bosN == 0 at EVERY value, because matureBars is read only by
    # alt_structure and structure() returns the SMC state before reaching it.
    # `msBosNeedsIdm` was justified as "dead in the SMC path on both sides",
    # which is true and is a reason for ABSENT, not for asserting a value.
    # Neither is a setting the watcher implements one value of; both are
    # parameters of machinery it does not contain, guarded by biasSrc.
    "matureBars": (None, "alt_structure only, unreachable at BS_SMC"),
    "msBosNeedsIdm": (None, "the BS_STRUCT branch only, unreachable at "
                            "BS_SMC; LuxAlgo's BOS has no inducement"),
    "msLen": (None, "bar-pivot bias only"),
    "msShortLen": (None, "bar-pivot bias only"),
    "emaFast": (None, "EMA bias only"), "emaSlow": (None, "EMA bias only"),
    "stAtrLen": (None, "supertrend bias only"),
    "stMult": (None, "supertrend bias only"),
    "slopeUnit": (None, "slope bias only"),
    "slopeLen": (None, "slope bias only"),
    "slopeMin": (None, "slope bias only"),
    "slopeHours": (None, "slope bias only"),
    "slopeMinPerHr": (None, "slope bias only"),
    "donLen": (None, "donchian bias only"),
    "mtfFast": (None, "MTF bias only"), "mtfSlow": (None, "MTF bias only"),
    "mtfMult": (None, "MTF bias only"),
    # Wilder's DI length. The watcher does not run that source -- biasSrc is
    # MIRRORED above, so a default switch to it fails there rather than here,
    # which is the right place for it to fail.
    "rsiLen": (None, "RSI bias"), "rsiTop": (None, "RSI bias"),
    "rsiBot": (None, "RSI bias"), "rsiHA": (False, "RSI bias"),
    "swingSrc": (None, "price-move swings feed the bar-pivot bias only"),
    "swingK": (None, "price-move swings only"),
    "swingKMinor": (None, "price-move swings only"),
    "swingHours": (None, "price-move swings only"),
    "htfUnit": (None, "HTF filter, off"), "htfMult": (0, "HTF filter, off"),
    "htfHours": (0.0, "HTF filter, off"),
    "adxMin": (0, "no ADX gate in the watcher; must stay off"),
    # the backup fill. Off by default, unmeasured, and the watcher stops at
    # the arming bar -- see the module docstring.
    # NO REQUIRED VALUE, and the reason is an invariant rather than an
    # opinion: the backup is entirely POST-ARMING. It re-prices where an
    # already-armed setup fills and cannot create, remove or move an arm, so
    # the watcher -- which stops at the arming bar and alerts nothing else --
    # sends exactly what the chart draws whether it is on or off.
    #
    # THAT CLAIM IS CHECKED, not asserted here. test_watch_undertow.py runs
    # the port with useBackup on and off and requires the ARMED lists to be
    # identical bar for bar and level for level. If the backup ever grows a
    # path that touches arming, that test fails and this waiver is void.
    "useBackup": (None, "post-arming only; the watcher stops at the arm, and "
                        "test_watch_undertow asserts arming is unaffected"),
    "bkTrigger": (None, "backup fill"), "bkMaxRisk": (None, "backup fill"),
    "useOB": (None, "backup fill"), "useFVG": (None, "backup fill"),
    "bkLook": (None, "backup fill"), "bkWhen": (None, "backup fill"),
    "bkLateBars": (None, "backup fill"), "bkMode": (None, "backup fill"),
    # scoring, which the watcher never does: it alerts, it does not grade.
    "feeFrac": (None, "the watcher scores nothing"),
    # A RULE UNDER TEST, not one on the chart. Port-only, off, and reachable
    # only when famStrict is on -- which the watcher mirrors at off. If
    # PREREG_undertow_complement.md replicates the 1h finding this becomes a
    # chart input and moves to MIRRORED with a watcher constant beside it.
    "famInvert": (False, "port-only, a rule under test; must stay off"),
}

# A parameter the watcher accepts and deliberately ignores needs a reason.
DEAD_OK = {
    "rate/db": "the Indicator registry calls every rate(db, tfs, **over); "
               "undertow's answer is a measured table and needs no database",
}


def _consts(tree) -> dict:
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    out[t.id] = node.value.value
    return out


def port_defaults() -> dict:
    tree = ast.parse(PORT.read_text())
    consts, fields = _consts(tree), {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "P":
            for st in node.body:
                if isinstance(st, ast.AnnAssign) and isinstance(st.target, ast.Name):
                    v = st.value
                    if isinstance(v, ast.Constant):
                        fields[st.target.id] = v.value
                    elif isinstance(v, ast.Name):
                        fields[st.target.id] = consts.get(v.id)
    return fields


def config_defaults() -> dict:
    """int(os.getenv("X", "6")) -- the literal, which is what ships unset."""
    out = {}
    for node in ast.parse(CONFIG.read_text()).body:
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1):
            continue
        t = node.targets[0]
        if not isinstance(t, ast.Name):
            continue
        lits = [n.value for n in ast.walk(node.value)
                if isinstance(n, ast.Constant)]
        v = node.value
        if isinstance(v, ast.Constant):
            out[t.id] = v.value
        elif isinstance(v, ast.Call) and isinstance(v.func, ast.Name) and lits:
            cast = {"int": int, "float": float, "bool": bool}.get(v.func.id)
            out[t.id] = cast(lits[-1]) if cast else lits[-1]
    return out


def watch_funcs(tree):
    """(name, {param: default}, {params never read in the body})."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        a = node.args
        defaults = dict(zip([x.arg for x in a.args][-len(a.defaults):],
                            [getattr(d, "value", None) for d in a.defaults])
                        ) if a.defaults else {}
        names = {x.arg for x in a.args} - {"self"}
        read = {n.id for n in ast.walk(node)
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
        yield node.name, defaults, names - read


def main() -> int:
    fields = port_defaults()
    wtree = ast.parse(WATCH.read_text())
    wconst = {k: v for k, v in _consts(wtree).items() if k.isupper()}
    cfg = config_defaults()
    params = {f"{fn}/{p}": d for fn, defs, _ in watch_funcs(wtree)
              for p, d in defs.items()}
    bad = []

    # EVERY field of P is in exactly one bucket. A new setting added to the
    # chart with no decision recorded here is itself the finding.
    buckets = [set(MIRRORED), set(HARDCODED), set(ABSENT)]
    placed = buckets[0] | buckets[1] | buckets[2]
    for f in sorted(set(fields) - placed):
        bad.append((f"P.{f}", "a setting on the chart with no entry in this "
                              "file. Say whether the watcher mirrors it, "
                              "hardcodes it, or does not implement it"))
    for f in sorted(placed - set(fields)):
        bad.append((f"P.{f}", "listed here and no longer a field of P"))
    for f in sorted(b1 & b2 for i, b1 in enumerate(buckets)
                    for b2 in buckets[i + 1:]):
        for name in sorted(f):
            bad.append((f"P.{name}", "in two buckets at once"))

    for f, (kind, where) in sorted(MIRRORED.items()):
        if f not in fields:
            continue
        have = {"const": wconst, "config": cfg, "param": params}[kind]
        if where not in have:
            bad.append((where, f"MIRRORED P.{f} and the watcher has no such "
                               f"{kind}"))
        elif have[where] != fields[f]:
            bad.append((where, f"watcher {have[where]!r} != chart "
                               f"P.{f} {fields[f]!r}"))

    for f, (want, why) in sorted(HARDCODED.items()):
        if f in fields and fields[f] != want:
            bad.append((f"P.{f}", f"the chart now defaults to {fields[f]!r} "
                                  f"and the watcher can only do {want!r} — "
                                  f"{why}. The bot would alert setups that "
                                  f"are not on the chart"))

    for f, (want, why) in sorted(ABSENT.items()):
        if want is not None and f in fields and fields[f] != want:
            bad.append((f"P.{f}", f"the chart now defaults to {fields[f]!r}; "
                                  f"the watcher does not implement it at all "
                                  f"({why})"))

    for fn, _, dead in watch_funcs(wtree):
        for d in sorted(dead):
            if f"{fn}/{d}" not in DEAD_OK:
                bad.append((f"{fn}({d})",
                            "accepted and never read. A dead knob is worse "
                            "than a missing one: the chat command that sets "
                            "it still answers as though it worked"))

    n = len(MIRRORED) + len(HARDCODED) + len(ABSENT)
    print(f"{n} of the chart's {len(fields)} settings accounted for — "
          f"{len(MIRRORED)} mirrored, {len(HARDCODED)} hardcoded in the "
          f"watcher, {len(ABSENT)} not implemented")
    if not bad:
        print("\nTHE CHART AND THE LIVE WATCHER AGREE ON EVERY SETTING.")
        print("Values only — the LOGIC is held by")
        print("indicators/undertow/tests/test_watch_undertow.py, and the")
        print("Pine's inputs by deploy/undertow-port-check.py.")
        return 0
    print(f"\n{len(bad)} DISAGREEMENT(S):")
    for name, why in bad:
        print(f"    {name}\n        {why}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
