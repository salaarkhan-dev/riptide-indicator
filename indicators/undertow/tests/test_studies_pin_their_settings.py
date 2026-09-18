"""A published study must still reproduce its published page.

    PYTHONPATH=. python3 indicators/undertow/tests/test_studies_pin_their_settings.py

THIS EXISTS BECAUSE IT HAPPENED, TWICE, IN ONE AFTERNOON.

`swingSrc` moved from the bar pivot to "price move", and `slopeUnit` from
"bars" to "hours". Neither commit touched a study script, and both silently
re-pointed arms that had been leaning on P's defaults:

  * undertow_bias's S0 and S1 became the range arm, making them duplicates of
    S6 -- the page reports 2.2 flips a day for S0/S1 and 0.7 for S6
  * undertow_bias's S4 became the hours variant of Slope
  * undertow_ablation, _exits, _backup and _late_backup all inherited a swing
    definition their measurements were never run under

Nothing failed. Every script still ran, still printed a table, and every number
in it would have been wrong under the name of a page that says otherwise. That
is the worst failure mode a measurement repository has, because the output
looks exactly like the output.

THE RULE: a study that constructs a baseline `U.P(...)` names the settings
below explicitly, even when they match the current default. A study that is
SUPPOSED to track whatever ships says so with the marker comment and is exempt
-- undertow_rate.py is the real case, because its tables describe the live
watcher.

The check is on the SOURCE TEXT, not on an import, because importing a study
runs it and several of them fetch candles.
"""
import os
import pathlib
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))))

STUDIES = pathlib.Path(__file__).resolve().parents[1] / "studies"

# The fields whose defaults have actually moved under a published study. Add to
# this list when you move another one -- that is cheaper than the alternative,
# which is finding out from a table that silently disagrees with its page.
PINNED = ("swingSrc", "msLen", "msShortLen", "rr", "endSweep",
          "endStale", "confirmOrder", "biasSrc", "pinNewest", "famPriority",
          "failTest")
# A SETTING THAT ONLY ONE SOURCE READS DOES NOT BELONG IN PINNED, because
# PINNED makes EVERY study name it. `emaFast`/`emaSlow` moved 50/200 -> 9/21
# when the EMA cross went on the chart, and putting them above made twelve
# studies that cannot reach the EMA source declare a length for it -- which
# reads as a dependency that is not there.
#
# The real risk is narrower and so is the guard: a study that names BS_EMA and
# forgets the lengths. `biasSrc` IS in PINNED, so such a study has to name the
# source out loud, and the test below then requires the lengths beside it.
SOURCE_BOUND = {"BS_EMA": ("emaFast", "emaSlow"), "BS_DI": ("diLen",),
                "BS_RSI": ("rsiLen", "rsiTop", "rsiBot")}
# A study whose whole job is to describe what currently ships puts this on the
# line that reads the default. It is a deliberate, visible opt-out.
EXEMPT = "TRACKS THE CURRENT DEFAULT"
# sha256 of P's field defaults, first 16 hex. See the third test for what to do
# when this fails -- the answer is not to paste the new value.
#
# 2026-09-17: bumped once, for `htfUnit`/`htfHours`. The procedure was followed:
# both are additive, the default keeps the HTF gate off and htf_mult() under
# "bars" is exactly the old expression (asserted by
# test_htf_hours_is_the_same_gate_in_a_consistent_unit), and undertow_bias
# Min15 and undertow_slope Min60 were re-run and reproduced their pages to the
# digit before this line changed.
#
# 2026-09-17: bumped again, for `mtfFast`/`mtfSlow`/`mtfMult`. That change also
# touched SHARED code -- bias() gained a stand-aside channel for BS_MTF -- so
# the re-run mattered more than the field count did. undertow_bias Min15 (all
# seven arms) and undertow_htf Min15 (all five arms plus its random gate) both
# reproduced to the digit first.
#
# 2026-09-17: bumped a third time, for `pbMinAge`/`pbMinDepth` — the two
# minimums SPEC.md 2.3b added after reading the pullback rule against the code.
# Both ship at the value that reproduces current behaviour. undertow_bias Min15
# and undertow_htf Min15 were re-run and reproduced before this moved.
#
# 2026-09-17: bumped a fourth time, for `confirmOrder`/`needBos`/`pinNewest` —
# the v2 rule corrections in SPEC.md 8. All three default to v1 so the twelve
# measurement pages keep reproducing; undertow_bias Min15 and undertow_pullback
# Min15 were re-run and reproduced to the digit before this moved. When v2 is
# measured and promoted, every page produced under v1 is superseded and this
# comment is where that starts.
#
# 2026-09-17: bumped a fifth time, for `smcSwingLen`/`smcInternalLen` — the
# LuxAlgo structure source. Additive, read only when biasSrc is BS_SMC, and
# undertow_bias Min15 reproduced before this moved.
#
# 2026-09-17: `confirmOrder` DEFAULT flipped to the corrected rule, so the port
# and the chart ship the same strategy. Every study now PINS C_EITHER because
# every measurement page was produced under it -- that is why confirmOrder is
# in PINNED above. undertow_bias Min15 and undertow_pullback Min15 reproduced
# to the digit before this moved.
#
# 2026-09-17: bumped for `pinAt`/`famPriority` — the corrected ANCHOR. Both
# default to v1 so the thirteen pages keep reproducing; undertow_bias Min15 and
# undertow_pullback Min15 reproduced before this moved.
#
# 2026-09-17: bumped for `feeFrac`, 0.0 → 0.0007, and this one is a REPORTING
# fix rather than a strategy change. The procedure was followed and it is short
# here for a reason worth writing down: every study in this directory passes
# feeFrac=FEE explicitly, so NO measurement page moves by a digit. The one
# study that reads the default is undertow_rate.py, which is the file's own
# exemption case, and it reports alert RATE and never scores R — checked, not
# assumed. What did read the zero were the CHART and the WATCH, which is the
# whole point: both reported gross R and a gross break-even line, and
# UNDERTOW_V3.md showed that the gap between 22.2% and 23.5% is exactly the
# difference between "this rule makes money" and "this rule is the fee".
#
# 2026-09-18: `biasSrc` 'structure' → 'SMC structure', by decision rather than
# by measurement, because the chart's structure engine is now a transcription
# of LuxAlgo's Smart Money Concepts and the port has to run what the chart
# runs. THE PROCEDURE WAS FOLLOWED IN THE ONLY ORDER THAT WORKS:
#
#   1. `biasSrc` went into PINNED above. It was NOT there, and TEN studies read
#      it from the default — undertow_ablation, _backup, _exits, _htf,
#      _late_backup, _overlap, _pin, _pullback, _sweep and _v3. Moving the
#      default first would have silently re-pointed all ten, which is the exact
#      failure this file exists to catch and has already caught twice.
#   2. All ten now pass biasSrc=U.BS_STRUCT explicitly, so every published page
#      keeps describing the engine it was produced on.
#   3. Only then did the default move.
#
# WHAT IT COSTS, STATED PLAINLY: every measurement page in ../measurements
# describes riptide's engine at 6/2, and the shipped bias is now LuxAlgo's at
# 50/5. UNDERTOW_V2.md scored the ENGINE swap at +0.002 / +0.065 / +0.006 R per
# trade — ../port/smc.py shows the two detectors are the same expression — but
# nothing has scored the LENGTH, and 50 against 6 is the larger change of the
# two by a distance.
#
# 2026-09-18: `smcSwingLen` 50 → 14. A PREFERENCE, and the measurement is what
# made it a free one: UNDERTOW_SCALE.md found R identical from 6/2 to 50/5, so
# the only thing a length buys is how often the bias speaks. 50 spoke rarely —
# tradeable 16% of the time, dead stretches with a median of 109 bars.
#
# NO STUDY MOVES. Every study that runs BS_SMC sets both lengths explicitly
# (undertow_v2's SMC dict, undertow_scale's arms), checked rather than assumed,
# and no study reads these from the default. The pinning test's own rule is
# what made that cheap to verify.
#
# 2026-09-18: `pinNewest` and `famPriority` ON, `failTest` → "close at or
# beyond". All three are the strategy author's stated rule, shipped as a
# CORRECTION on the footing W→F went out on: the author's rule goes on the
# chart, and measurement decides defaults it has an opinion about.
# UNDERTOW_V3.md measured the pair at nothing, so it has none.
#
# THE PROCEDURE, AND THE TRAP IT ALMOST WALKED INTO. Every study was pinned
# first — and the textual check that drives PINNED reads the WHOLE FILE, so
# undertow_pin, undertow_v2 and undertow_v3 all looked pinned because they name
# `pinNewest` or `famPriority` in an ARM dict while their BASE read the
# default. Caught by constructing each BASE and printing the three fields
# rather than trusting the grep. That is a real weakness in this test: it
# proves a name appears, not that the baseline names it.
#
# 2026-09-18: `armWins` added, OFF. Purely additive — no existing default
# moves and no study's arms change, so nothing needed re-running. It is off
# because it changes which trades exist (about 10% of armed setups) and
# UNDERTOW_ANCHOR.md is what set the standard that those get a prereg rather
# than shipping on the strength of being clearly stated.
#
# 2026-09-18: `famStrict` added, OFF. The priority RANKING becomes a GATE --
# only the shooting star in a bull trend, only the hammer in a bear trend, and
# the hanging man and the inverted hammer stop being setups at all. Purely
# additive: no existing default moves and no study's arms change, so nothing
# needed re-running. It is off because it cuts 42-46% of the armed setups
# (measured on the spent 23-symbol set, where the two surviving codes are
# untouched -- 474 shooting stars become 475), and that is the second-largest
# single cut in P after the anchor. UNDERTOW_ANCHOR.md is also the specific
# warning here: it took the author's stated anchor, confirmed the mechanism
# fired 86-88% of the time, and the trades were worse. A shape filter is the
# same kind of claim and gets the same treatment.
#
# 2026-09-18: `famInvert` added, OFF, and PORT-ONLY -- no chart input, which is
# the first field in a while to have none. It inverts `famStrict` so the gate
# admits the SECOND-choice shape instead of the first. Nobody asked for the
# rule; UNDERTOW_STRICT.md found that on 1h those shapes scored +0.197 against
# the priority half's -0.062, the only |z| >= 2 in eighteen studies, and
# PREREG_undertow_complement.md is the replication. Purely additive: no
# existing default moves, and with famStrict off the new branch cannot be
# reached at all, so no study's arms change and nothing needed re-running.
#
# 2026-09-18: `biasTier`, for the "why are there so few setups" question.
# Additive -- it defaults to "swing", which IS the old behaviour. The shipped
# configuration was counted on the spent 23 immediately before and after:
# 1101 / 1104 / 1104 armed trades on 15m / 30m / 1h, identical both times.
#
# 2026-09-18: ChartArt's EMA slope + cross came and WENT IN THE SAME DAY.
# `scFast`/`scMid`/`scSlow` and `BS_XCROSS` are gone: measured at a FIFTH of
# the setups on the spent 23, which is the opposite of the reason it was
# added, and its author asked for it removed. It is not in the history as a
# default that moved, because it never was one.
#
# 2026-09-18: `diLen` added and `emaFast`/`emaSlow` MOVED, 50/200 -> 9/21, for
# the two bias sources that replaced it. THE DEFAULT MOVE IS THE PART THAT
# NEEDED CARE and the procedure was followed in the only order that works:
#
#   1. emaFast and emaSlow went into PINNED above. Three studies read the EMA
#      source -- undertow_bias (S2), undertow_mtf (M2) and
#      undertow_mtf_default -- and all three already named their own lengths,
#      checked rather than assumed.
#   2. S2 was reproduced at its pinned 50/200 AFTER the default moved: 791
#      trades at -0.032 R on Min30, which is the study's own configuration and
#      not the chart's.
#   3. Only then did the default move.
#
# `diLen` is purely additive: nothing reads it unless biasSrc is BS_DI.
#
# 2026-09-18: `rsiLen`/`rsiTop`/`rsiBot`/`rsiHA`, for Duyck's RSI bias -- the
# third alternative source and the only LATCHED one. Purely additive: nothing
# reads any of them unless biasSrc is BS_RSI, which is not the default, and
# BS_RSI is bound to its own fields by test_a_source_arm_names_its_own_lengths
# so a future study cannot name the source and inherit the chart's levels.
DEFAULTS_FINGERPRINT = "ce5519e17914999b"
DEFAULTS_COUNT = 74

good = []


def ok(cond, msg):
    good.append(bool(cond))
    print(("  ok   " if cond else "  FAIL ") + msg)


def test_every_study_pins_or_opts_out():
    files = sorted(p for p in STUDIES.glob("*.py")
                   if not p.name.startswith("_"))
    ok(len(files) >= 6, f"found the studies: {len(files)}")
    for p in files:
        src = p.read_text()
        if EXEMPT in src:
            print(f"       {p.name}: exempt — {EXEMPT}")
            good.append(True)
            continue
        # The baseline is whatever this file passes to P(...) -- under any
        # alias, because the first version of this check looked for `U.P(`
        # only and waved undertow_rate.py through for the wrong reason: it
        # reads `_P().swingSrc` and is exactly the case the exemption is for.
        if not re.search(r"\b_?P\(\)?", src):
            print(f"       {p.name}: reads no P at all")
            good.append(True)
            continue
        missing = [f for f in PINNED if not re.search(rf"\b{f}\s*=", src)]
        ok(not missing,
           f"{p.name} pins its settings"
           + ("" if not missing else f" — MISSING {', '.join(missing)}"))


def test_a_source_arm_names_its_own_lengths():
    """Naming an alternative bias source without its lengths reads the chart's.

    `emaFast`/`emaSlow` went 50/200 -> 9/21 the day the EMA cross went on the
    chart. UNDERTOW_BIAS_SOURCE.md's S2 is "EMA cross 50/200" and it names both
    -- had it not, the page's title would now describe an arm that ran 9/21.
    """
    for p in sorted(STUDIES.glob("*.py")):
        src = p.read_text()
        if EXEMPT in src:
            continue
        for const, needed in sorted(SOURCE_BOUND.items()):
            if not re.search(rf"\b{const}\b", src):
                continue
            # BOTH SPELLINGS. An arm is written either as a keyword,
            # `emaFast=50`, or inside a dict literal, `"emaFast": 50`.
            # undertow_bias.py uses the second and the first version of this
            # test only matched the first, which failed a study that was
            # already doing the right thing.
            missing = [f for f in needed
                       if not re.search(rf'\b{f}\s*=|"{f}"\s*:', src)]
            ok(not missing,
               f"{p.name} names {const} and its lengths"
               + ("" if not missing else f" — MISSING {', '.join(missing)}"))


def test_the_marker_is_not_a_blank_cheque():
    """An exempt study still has to say WHY on the line that reads the default,
    not once at the top of the file as a way of skipping the check."""
    for p in sorted(STUDIES.glob("*.py")):
        src = p.read_text()
        if EXEMPT not in src:
            continue
        lines = [ln for ln in src.splitlines() if EXEMPT in ln]
        ok(all(ln.lstrip().startswith("#") for ln in lines),
           f"{p.name}: the exemption is a comment, not a string in output")
        near = src.split(EXEMPT, 1)[1][:400]
        ok("_P()" in near or "U.P(" in near or "swingSrc" in near,
           f"{p.name}: the exemption sits next to the default it reads")


def test_the_defaults_have_not_moved_unnoticed():
    """THE GUARD THAT DOES NOT NEED A LIST, and the reason it exists is that
    the list above was WRONG on its first outing.

    PINNED named swingSrc, msLen, msShortLen and rr. It missed `endSweep` and
    `endStale`, which had also flipped, so undertow_exits still failed to
    reproduce -- it chose a different exit arm on two of three timeframes --
    and only a full re-run found it. Enumerating consequences does not work,
    because the enumerator is the thing that is out of date.

    So this fails on ANY default moving, which is the CAUSE. It is meant to be
    updated deliberately: change a default, re-run the studies, confirm they
    still reproduce their pages or pin what they need, then paste the new
    fingerprint. The failure message is the procedure.
    """
    import dataclasses
    import hashlib
    import json

    from indicators.undertow.port import undertow as U

    fields = {f.name: f.default for f in dataclasses.fields(U.P)}
    got = hashlib.sha256(
        json.dumps(fields, sort_keys=True, default=str).encode()).hexdigest()
    ok(got.startswith(DEFAULTS_FINGERPRINT),
       "P's defaults are the ones the studies were audited against"
       if got.startswith(DEFAULTS_FINGERPRINT) else
       f"P's DEFAULTS MOVED — fingerprint {got[:16]}, expected "
       f"{DEFAULTS_FINGERPRINT}.\n"
       "         Every study that does not pin the field you changed is now\n"
       "         measuring something its page does not describe. Re-run them,\n"
       "         confirm each reproduces its measurement, pin what it needs,\n"
       "         then paste the new fingerprint here. Do not just paste it.")
    ok(len(fields) == DEFAULTS_COUNT,
       f"P has {len(fields)} fields (audited against {DEFAULTS_COUNT})")


def main():
    for fn in (test_every_study_pins_or_opts_out,
               test_a_source_arm_names_its_own_lengths,
               test_the_marker_is_not_a_blank_cheque,
               test_the_defaults_have_not_moved_unnoticed):
        print(f"\n{fn.__name__}")
        fn()
    print(f"\n{'ALL PASS' if all(good) else 'FAILURES'}  "
          f"{sum(good)}/{len(good)}")
    return 0 if all(good) else 1


if __name__ == "__main__":
    sys.exit(main())
