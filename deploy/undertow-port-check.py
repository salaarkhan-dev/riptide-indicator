"""Do the Pine and the Python port agree on their INPUTS?

    python3 deploy/undertow-port-check.py

WHAT THIS IS, AND WHAT IT IS NOT. It is not a logic parity check. Sections 5, 6
and 7 of riptide-undertow.pine have no v2 counterpart, so there is no second
copy to diff them against, and a statement-level comparison between Pine and
Python across a state machine that size would need an exception table longer
than the check. That guard is behavioural instead and lives in
indicators/undertow/tests/test_undertow_port.py.

What this IS: every `input.*` in the Pine must have a field of the same name in
the port's `P`, with the SAME DEFAULT, and every `options = [...]` list must
match the string constants the port compares against.

AND THE OTHER DIRECTION, which is the half that used to be weak. Every field of
`P` with NO Pine input is placed in one of two buckets, by name, with a reason:

    PINE_HARDCODED   the Pine implements this, at exactly one value, with no
                     input to change it. P must still default to that value.
    PINE_ABSENT      the Pine does not implement it at all. Where the field
                     has an OFF value, P must still be sitting on it.

That used to be one flat "retired" set, waved through on the strength of "the
chart no longer offers this", with no VALUE compared. But `pinNewest` and
`famPriority` are not absent from the chart — the Pine supersedes and it ranks,
unconditionally, on every bar. The day either default flipped in P, the chart
would keep ranking and the port would stop, and nothing here would say a word.
Same for the two confirmation tests, which the Pine holds as the literals
`kWork` and `kFail`, and for `biasSrc`, which the Pine simply IS.

A new field of P in neither bucket fails the check, which is how the decision
gets made in a diff rather than by default.

That sounds small. It is the drift that actually happens. The port and the Pine
are edited on different days for different reasons, and the failure is silent
in the worst possible way: a study reports a number for `retraceMax = 70` while
the chart the number is supposed to describe is running 50. Nothing crashes,
nothing looks wrong, and the conclusion is about a strategy nobody is trading.

The string options matter for the same reason and worse. Both sides compare
these by VALUE -- Pine does `stopSrc == "Pullback extreme"` and the port does
`p.stopSrc == S_PULL`. Change the wording of a dropdown in the Pine and the
port's comparison silently stops matching, every branch falls through to its
else, and the machine still runs.

DELIBERATELY NOT COMPARED: the display group (showZones, showUnfilled,
showStruct, keepN, the zone counts and mitigation choice, the colours, the two
debug toggles). Those drive drawing, and the port draws nothing. They are
listed in DISPLAY_ONLY below by name, so adding to that list shows up in a diff
rather than quietly widening the hole.

THE THIRD COPY IS NOT THIS FILE'S JOB. deploy/undertow-three-way-check.py does
the same accounting for riptide/watchers/undertow.py, which is the copy that
sends the alerts, and it uses the same three buckets for the same reason.
"""
from __future__ import annotations

import ast
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PINE = ROOT / "indicators/undertow/pine/riptide-undertow.pine"
PORT = ROOT / "indicators/undertow/port/undertow.py"

# Pine inputs that only ever reach a drawing call. The port has no analogue and
# must not grow one.
DISPLAY_ONLY = {"showZones", "showUnfilled", "showStruct", "keepN",
                "overlapMode", "showStats", "showBias", "showOB", "colOBBull",
                "colOBBear", "showFVG", "fvgExtend", "zoneAuto",
                # The minor tier's breaks, drawn or not. Pure drawing: the
                # tier itself always runs, because endMinor and the
                # minor-swing stop read it whether or not it is on screen.
                "showInternal",
                # HOW MANY ZONES SURVIVE, AND WHAT KILLS THEM. All three
                # reach only box.new and box.delete.
                #
                # `zoneMitig` looks like a rule and is not, but the reason is
                # worth writing down. The port DOES find order blocks and fair
                # value gaps -- bk_zone() -- and it finds them by a completely
                # different algorithm: a demand scan over the last `bkLook`
                # bars for the last opposite-coloured candle that got
                # displaced, with no persistent zone list and so no mitigation
                # state to mitigate. The chart's zones are LuxAlgo's, anchored
                # to a structure break, kept in an array and deleted when price
                # goes through. Two different objects that share a name.
                #
                # They are allowed to differ because bk_zone is reached ONLY by
                # the backup fill, which is off by default, is not on the chart
                # at all, and was measured twice -- UNDERTOW_BACKUP_FILL.md and
                # UNDERTOW_LATE_BACKUP.md. If the backup fill ever comes back,
                # that divergence is the first thing to settle and these three
                # stop being display-only.
                "obCount", "fvgCount", "zoneMitig",
                "colLong", "colShort", "colLine", "dbgOn", "dbgRejects"}

# input.color / input.string defaults that are Pine expressions rather than
# literals are not comparable as values; none of the non-display inputs are.
INPUT = re.compile(
    r"^\s*(\w+)\s*=\s*input\.(int|float|bool|string|color)\s*\(\s*(.+)$")


def pine_inputs():
    """(name, kind, default, options) for every input in the Pine.

    Reads the FIRST argument by scanning to the first top-level comma, because
    a default can be a string containing a comma and a naive split eats it.
    """
    out = {}
    src = PINE.read_text().splitlines()
    for n, line in enumerate(src):
        m = INPUT.match(line)
        if not m:
            continue
        name, kind, rest = m.group(1), m.group(2), m.group(3)
        # the call can wrap; join until the parens balance
        buf, depth, k = rest, 0, n
        while True:
            depth = buf.count("(") - buf.count(")")
            if depth < 0 or k >= len(src) - 1:
                break
            k += 1
            buf += " " + src[k].strip()
        default = _first_arg(buf)
        opts = None
        mo = re.search(r"options\s*=\s*\[([^\]]*)\]", buf)
        if mo:
            opts = [s.strip().strip('"') for s in mo.group(1).split(",")]
        out[name] = (kind, default, opts)
    return out


def _first_arg(buf: str) -> str:
    depth = 0
    quote = False
    for i, ch in enumerate(buf):
        if ch == '"':
            quote = not quote
        elif not quote:
            if ch in "([":
                depth += 1
            elif ch in ")]":
                if depth == 0:
                    return buf[:i].strip()
                depth -= 1
            elif ch == "," and depth == 0:
                return buf[:i].strip()
    return buf.strip()


def port_defaults():
    """P's field defaults, plus the module-level string constants, by AST so a
    comment or a reordering cannot fool it."""
    tree = ast.parse(PORT.read_text())
    consts, fields = {}, {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    consts[t.id] = node.value.value
        if isinstance(node, ast.ClassDef) and node.name == "P":
            for st in node.body:
                if isinstance(st, ast.AnnAssign) and isinstance(st.target, ast.Name):
                    v = st.value
                    if isinstance(v, ast.Constant):
                        fields[st.target.id] = v.value
                    elif isinstance(v, ast.Name):
                        fields[st.target.id] = consts.get(v.id, f"<{v.id}>")
    return fields, consts


def as_py(kind: str, default: str):
    """The Pine literal as the Python value it should equal."""
    if kind == "bool":
        return default == "true"
    if kind == "int":
        return int(default)
    if kind == "float":
        return float(default)
    if kind == "string":
        return default.strip('"')
    return None


def main() -> int:
    pin = pine_inputs()
    fields, consts = port_defaults()
    bad, checked = [], 0

    for name, (kind, default, opts) in sorted(pin.items()):
        if name in DISPLAY_ONLY or kind == "color":
            continue
        checked += 1
        if name not in fields:
            bad.append((name, f"the Pine has this input; P has no field. "
                              f"Pine default {default}"))
            continue
        want = as_py(kind, default)
        got = fields[name]
        if want is None:
            continue
        if isinstance(want, float) or isinstance(got, float):
            same = abs(float(want) - float(got)) < 1e-9
        else:
            same = want == got
        if not same:
            bad.append((name, f"DEFAULT DIFFERS — pine {want!r}, port {got!r}"))
        if opts:
            missing = [o for o in opts if o not in consts.values()]
            if missing:
                bad.append((name, "OPTION STRING NOT IN THE PORT: "
                            + ", ".join(repr(m) for m in missing)
                            + " — both sides compare these by value, so a "
                              "reworded dropdown makes every branch fall "
                              "through in silence"))

    # ── THE OTHER DIRECTION, and it is the half that used to be weak ──
    #
    # A field of P with no Pine input is not automatically fine. There are two
    # very different reasons for one, and only the first is safe to wave
    # through:
    #
    #   PINE_ABSENT     the Pine does not implement this part of the strategy
    #                   at all. Where the field has an OFF value, P must still
    #                   be sitting on it, or the port is running a gate the
    #                   chart has no way to show.
    #   PINE_HARDCODED  the Pine DOES implement it, at exactly one value, with
    #                   no input to change it. P must still default to that
    #                   value.
    #
    # THE SECOND BUCKET IS WHY THIS WAS REWRITTEN. It used to be one flat
    # RETIRED set: every field in it was waved through on the strength of
    # "the chart no longer offers this", and nothing compared a VALUE. But
    # `pinNewest` and `famPriority` are not absent from the Pine — it
    # supersedes and it ranks, unconditionally, on every bar. The day either
    # default flips to False in P, the chart keeps ranking, the port stops,
    # and no check in this repository says a word. Same for the two
    # confirmation tests, which the Pine holds as the literals `kWork` and
    # `kFail`, and for `biasSrc`, which the Pine simply IS.
    #
    # Each entry below was checked against the Pine rather than assumed, and
    # two beliefs did not survive that:
    #
    #   * `swingK`, `swingKMinor` and `swingHours` were documented here as
    #     "FIXED IN THE PINE at the values every measurement page was produced
    #     under". They do not appear in the Pine at all. The chart runs SMC
    #     structure and has no price-move swings to scale, so they are ABSENT.
    #   * `matureBars` and `msBosNeedsIdm` are not hardcoded either. Both are
    #     read only by `alt_structure` and the BS_STRUCT branch, and
    #     `structure()` returns before either when biasSrc is BS_SMC. They are
    #     unreachable at the shipped configuration, and biasSrc is checked
    #     below, which is what guards them.

    # value, why. The value is what the PINE does; P must agree with it.
    PINE_HARDCODED = {
        # `biasSrc` IS AN INPUT NOW — the chart offers SMC structure, a plain
        # EMA cross and DI+/DI- — so it is compared above like any other
        # dropdown rather than asserted here, and so are emaFast, emaSlow and
        # diLen.
        #
        # `matureBars` came the other way. The Pine's second source has no
        # structure to break, so it fabricates a BOS a fixed number of bars
        # after a direction flip exactly as alt_structure does, and that
        # number is the literal `xcMature`. It is not an input: a dial for
        # "how long until a fabricated break counts" is the kind of setting
        # SETTINGS.md exists to keep off the panel.
        "matureBars": (20, "the literal altMature in the two alt sources"),
        # `pinOk` has no bosOk term, so a pin arms in `immature` as readily as
        # in `running`.
        "needBos": (False, "pinOk does not gate on the bias state"),
        # The supersede block runs unconditionally on every accepted pin, and
        # the priority ranking runs unconditionally inside it. NEITHER IS
        # ABSENT FROM THE CHART, which is the whole reason this bucket exists.
        "pinNewest": (True, "a new pin always clears its unarmed rivals"),
        "famPriority": (True,
                        "and a non-priority pin never displaces a waiting "
                        "priority one"),
        # `famOk` is the wick test with no "gate off" branch, and `colourOk`
        # is unconditional in `pinOk`.
        "useFamily": (True, "famOk has no bypass"),
        "useColour": (True, "colourOk is a term of pinOk, not a switch"),
        # `locOk` is the tolerance and nothing else; the port adds the two
        # minimums to it only when they are above zero.
        "pbMinAge": (0, "locOk carries no age test"),
        "pbMinDepth": (0.0, "locOk carries no depth test"),
        # Held as literals near the top of the Pine: `string kWork` and
        # `string kFail`. Compared BY VALUE on both sides, so a reworded
        # constant is the silent-fallthrough failure this file's docstring
        # warns about, one step removed.
        "workTest": ("close beyond", "the literal kWork"),
        # The backup's seven fixed settings, each a literal in the trigger or
        # in bkZone. A dial for "how far price must run before the backup
        # arms" is the kind of thing SETTINGS.md exists to keep off the panel.
        "bkTrigger": (1.0, "the literal 1.0 in the ranR test"),
        "bkMaxRisk": (2.0, "the literal 2.0 in the risk cap"),
        "useOB": (True, "bkZone always scans order blocks"),
        "useFVG": (True, "and always scans fair value gaps"),
        "bkLook": (30, "the literal in bkZone's lookback"),
        "bkWhen": ("live", "the chart places it while the setup is LIVE, and "
                           "only that -- the late variant is not offered"),
        "bkMode": ("zone", "bkZone returns an edge, never a midpoint"),
        # THE FOUR SWING DIALS MOVED BUCKETS WHEN THE v2 ENGINE WENT BACK ON
        # THE CHART, and the old entry for them was wrong in a way worth
        # recording: it claimed they were "FIXED IN THE PINE at the values
        # every measurement page was produced under" while the Pine had no
        # swing detector in it at all. Now it does -- v2PriceSwings in section
        # 4b -- and they really are fixed, as literals in the two calls to it
        # and in the 24-hour reference window. So the claim is finally true and
        # is finally checked.
        # THE DETECTOR IS THE BAR PIVOT on the chart -- v2Swings, section 4b --
        # because the script being reproduced uses one. The price-move swings
        # this engine also supports have no detector in the Pine at all, so
        # their three dials are ABSENT below rather than hardcoded. An earlier
        # version of this file claimed they were "FIXED IN THE PINE at the
        # values every measurement page was produced under" while the Pine had
        # no swing detector whatsoever; the bucket split is what caught that.
        "swingSrc": ("bar pivot", "v2Swings is the only detector"),
        "failTest": ("close at or beyond", "the literal kFail, via tTouch"),
    }

    # value or None, why. None means the field has no "off" setting worth
    # asserting — it parameterises machinery the Pine does not contain.
    PINE_ABSENT = {
        # RESEARCH-ONLY PIN SELECTION, and both sit on the value the chart
        # behaves as. `pinLag` 0 is "trade the newest qualifying candle", which
        # is what the Pine's supersede already produces; `shortsOnly` False is
        # both directions, which is the only thing the Pine does. If either
        # default moved, the chart and the port would part company in silence,
        # which is what the OFF-value assertion below is for.
        #
        # They exist for undertow_pinlag.py, measuring the chart owner's own
        # account of his eye -- "if three qualified, n, n-1 and n-2, take n-1".
        # Nothing is on the chart until that measures something.
        "pinLag": (0, "pin selection, research only"),
        # The Pine latches Ending unconditionally, which is this field's True.
        "retraceLatch": (True, "the Pine's Ending latch is unconditional"),
        "shortsOnly": (False, "pin selection, research only"),
        # THE RETIRED BIAS SOURCES. EMA cross, Slope, Donchian midpoint,
        # Supertrend and MTF EMA align were all on the chart to be measured;
        # UNDERTOW_BIAS_SOURCE.md and undertow_slope.py measured them, none
        # beat the baseline, and they cost fifteen inputs in group 1 to offer
        # settings their own pages warn against. They stay in the port because
        # undertow_bias (S2, S4, S5) and undertow_slope (A1, A2) must keep
        # reproducing. `biasSrc` above is what stops the port drifting onto
        # one of them unnoticed.
        # BACK OFF THE CHART. The EMA cross was an input for part of one day
        # at 9/21; it is port-only again at the 50/200 its page was produced
        # under, and DI+/DI- went the same way and left no field behind.
        "emaFast": (None, "EMA bias"), "emaSlow": (None, "EMA bias"),
        "donLen": (None, "Donchian bias"),
        "slopeUnit": (None, "slope bias"), "slopeLen": (None, "slope bias"),
        "slopeMin": (None, "slope bias"), "slopeHours": (None, "slope bias"),
        "slopeMinPerHr": (None, "slope bias"),
        "stAtrLen": (None, "supertrend bias"), "stMult": (None, "supertrend"),
        "mtfFast": (None, "MTF bias"), "mtfSlow": (None, "MTF bias"),
        "mtfMult": (None, "MTF bias"),
        # THE OLD BAR-PIVOT ENGINE and the price-move swings that fed it.
        # Section 3 is a transcription of LuxAlgo's SMC now, so the chart has
        # one detector at two lengths and no swing source to choose, no pivot
        # lengths to set and no inducement rule to gate a BOS on.
        "swingK": (None, "price-move swings, which the chart does not have"),
        "swingKMinor": (None, "price-move swings"),
        "swingHours": (None, "price-move swings"),
        # THE BACKUP FILL, eight inputs, measured twice and worthless: +0.03 R
        # per armed setup significant on none (UNDERTOW_BACKUP_FILL.md), and
        # waiting for the limit to expire removes the tax and all the
        # opportunity (UNDERTOW_LATE_BACKUP.md). Two of the eight — bkWhen and
        # bkLateBars — were never even WIRED UP in the Pine: declared, never
        # read. That is what an input panel nobody prunes looks like.
        #
        # `useBackup` CARRIES A REQUIRED VALUE and the rest do not. The chart
        # cannot fill on a zone, so a port that could would be scoring trades
        # the chart never shows.
        # THE BACKUP FILL IS BACK, as ONE input rather than the eight it used
        # to cost, so `useBackup` is compared above and its seven sub-settings
        # are HARDCODED below at P's values. The chart offers the rule; it does
        # not offer a search over the rule, which is ../SETTINGS.md's line and
        # the reason the eight came off in the first place.
        "bkLateBars": (None, "the late variant, which the chart does not "
                             "offer: UNDERTOW_LATE_BACKUP.md found 100% of "
                             "this rule's added fills land INSIDE the window"),
        # THREE ENDING RULES AND THE ADX GATE, all shipped off, none ever
        # measured switched on, and ADX failed as a filter elsewhere in this
        # project (CCP_CONTEXT_FILTERS.md). Each carries its off value: an
        # ending rule live in the port and absent from the chart would cancel
        # setups the chart still draws.
        "endSweep": (False, "no sweep rule on the chart; must stay off"),
        "endStale": (False, "no stale rule on the chart; must stay off"),
        "staleBars": (None, "parameter of the stale rule"),
        "adxMin": (0, "no ADX gate on the chart; must stay off"),
        # THE HTF BIAS. An honest one in Pine needs the whole structure slab
        # inside a function so request.security can evaluate it on
        # higher-timeframe bars. If the gate ever clears a prereg, that
        # refactor is the price of putting it on the chart.
        "htfMult": (0, "HTF gate; must stay off"),
        "htfUnit": (None, "HTF gate"), "htfHours": (0.0, "HTF gate"),
        # A RULE UNDER TEST, not one on the chart. It inverts famStrict so the
        # gate admits the second-choice shape. UNDERTOW_COMPLEMENT.md ran it
        # and it did not replicate, so it has no claim on an input.
        "famInvert": (False, "port-only, did not replicate; must stay off"),
    }

    # A BUCKET ENTRY THAT IS ALSO A PINE INPUT IS STALE, and stale is not
    # harmless: the loop below skips it, so it looks accounted for while the
    # input is actually being compared by the loop above -- or, worse, the
    # entry outlives the input and claims a value nothing checks. `feeFrac`
    # sat in the old port-only set for exactly this reason after it became an
    # input, and the count is what caught the next one.
    for name in sorted((set(PINE_HARDCODED) | set(PINE_ABSENT)) & set(pin)):
        bad.append((name, "listed as hardcoded-or-absent AND present as a "
                          "Pine input. One of the two is stale"))
    # AND A FIELD IN BOTH BUCKETS IS A CONTRADICTION. The Pine either
    # implements a setting at a fixed value or it does not implement it; both
    # entries cannot be true, the loop below silently takes the first, and the
    # count is what shows it. `matureBars` was in both the moment the Pine
    # grew a second bias source: absent from the old chart, and hardcoded as
    # `altMature` on the new one.
    for name in sorted(set(PINE_HARDCODED) & set(PINE_ABSENT)):
        bad.append((name, "in PINE_HARDCODED and PINE_ABSENT at once — the "
                          "Pine either implements it at a value or does not "
                          "implement it"))

    for name in sorted(fields):
        if name in pin:
            continue
        if name in PINE_HARDCODED:
            want, why = PINE_HARDCODED[name]
            if fields[name] != want:
                bad.append((name, f"THE PINE HARDCODES {want!r} ({why}) and "
                                  f"P now defaults to {fields[name]!r}. The "
                                  f"chart cannot follow — there is no input "
                                  f"to change"))
            continue
        if name in PINE_ABSENT:
            want, why = PINE_ABSENT[name]
            if want is not None and fields[name] != want:
                bad.append((name, f"the Pine does not implement this ({why}) "
                                  f"and P now defaults to {fields[name]!r} "
                                  f"rather than {want!r} — the port would be "
                                  f"running a rule the chart cannot show"))
            continue
        bad.append((name, "P has this field and the Pine has no input for it. "
                          "Say which: PINE_HARDCODED if the Pine implements "
                          "one value of it, PINE_ABSENT if the Pine does not "
                          "implement it at all"))

    hard = len(set(PINE_HARDCODED) & set(fields))
    absent = len(set(PINE_ABSENT) & set(fields))
    print(f"{checked} shared inputs compared, {hard} values the Pine "
          f"hardcodes, {absent} the Pine does not implement — "
          f"{checked + hard + absent} of P's {len(fields)} fields, with "
          f"{len(DISPLAY_ONLY)} display-only inputs skipped by name")
    if not bad:
        print("\nTHE PINE AND THE PORT AGREE ON EVERY SETTING.")
        print("Defaults, dropdown strings and the values the Pine holds")
        print("as literals — the LOGIC is held by")
        print("indicators/undertow/tests/test_undertow_port.py.")
        return 0
    print(f"\n{len(bad)} DISAGREEMENT(S):")
    for name, why in bad:
        print(f"    {name}\n        {why}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
