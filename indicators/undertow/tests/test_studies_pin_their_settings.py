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
          "failTest",
          # FIVE DEFAULTS MOVED IN ONE DAY AND FOUR OF THEM WERE NOT IN HERE.
          # `stopSrc` went pullback -> minor swing at the chart owner's
          # request and silently re-pointed NINETEEN studies: undertow_strict's
          # S0 read -0.124 against the -0.026 on its own page until it was
          # pinned back, which is this file's entire subject happening again.
          # famStrict and armWins were the same exposure and had not yet
          # bitten. `useBackup` was recorded here as "caught before it moved",
          # AND THAT WAS WRONG -- it had already moved to True, and
          # undertow_backup's B0 arm was `("B0", "backup off", {})`, so the
          # baseline of the page became a copy of the primary. The study
          # printed +0.000 on all three timeframes and a verdict to match.
          # It passed THIS TEST the whole time, for the reason the next
          # function exists.
          #
          # `biasTier` was in here and is gone with the field: it could only
          # ever be read on the BS_SMC path and the shipped source bypasses it.
          "useBackup", "famStrict", "armWins", "stopSrc",
          # `biasGate` went "tradeable" -> "direction only" and EVERY page was
          # produced under the veto. It goes in here, and into all twenty
          # baselines, BEFORE the default moves -- which is the order this file
          # has had to state three times in one day.
          "biasGate")
# A SETTING THAT ONLY ONE SOURCE READS DOES NOT BELONG IN PINNED, because
# PINNED makes EVERY study name it. `emaFast`/`emaSlow` moved 50/200 -> 9/21
# when the EMA cross went on the chart, and putting them above made twelve
# studies that cannot reach the EMA source declare a length for it -- which
# reads as a dependency that is not there.
#
# The real risk is narrower and so is the guard: a study that names BS_EMA and
# forgets the lengths. `biasSrc` IS in PINNED, so such a study has to name the
# source out loud, and the test below then requires the lengths beside it.
SOURCE_BOUND = {"BS_EMA": ("emaFast", "emaSlow"),
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
#
# 2026-09-18: `diLen` GONE with the DI+/DI- source, `emaFast`/`emaSlow` BACK to
# 50/200 as the EMA cross came off the chart again, and THREE DEFAULTS MOVED
# BY REQUEST with the numbers in front of the person moving them:
#
#   famStrict  False -> True   the priority shape becomes a GATE. It removes
#                              roughly the smaller half of the setups and
#                              UNDERTOW_STRICT.md scored it negative on 3 of 3
#                              and below its control on 2 of 3. Its own page
#                              says the decision belongs to the chart's owner
#                              with the number in front of them; this is that.
#   armWins    False -> True   first to complete W->F drops its unarmed
#                              rivals. Unmeasured, about 10% of armed setups.
#   stopSrc    pullback -> minor swing extreme. 1,054 setups against 1,104 on
#                              the spent 23 at 30m, and it makes `stopTrack`
#                              inert -- a stop pinned to a confirmed swing has
#                              nothing to follow.
#
# NO STUDY MOVES. All three are in no study's BASE by way of PINNED, but that
# is not the reason: the reason is that every study in the directory was
# checked for whether it reads them from the default, and the two fixtures
# that did -- test_undertow_port's ghost-accounting walk and
# test_watch_undertow's stop-tracking walk -- now pin them, because both are
# fixtures for something else and both went vacuous rather than wrong.
#
# 2026-09-18: THE v2 ENGINE IS BACK ON THE CHART as a bias source, because it
# is the only one here with an INDUCEMENT -- LuxAlgo's SMC has none, so its BOS
# is a close beyond the last pivot with no liquidity precondition. Three
# defaults moved with it, and all three are already in PINNED, which is exactly
# the situation PINNED exists for:
#
#   msLen       6 -> 50    the CHoCH pivot, at the value the script this
#   msShortLen  2 -> 3     reproduces ships. A slow reversal level and a fast
#                          inducement; the gap between them is the design.
#   swingSrc    price move -> bar pivot. The chart draws the bar-pivot version,
#                          so the port has to default to the same detector or
#                          the two describe different engines.
#
# NO STUDY MOVES, checked rather than assumed: a pinned BS_STRUCT arm at
# 6/2 price-move scored 3,717 trades at -0.0820 R on Min30 after the move,
# because it names all three. The bar count is not scale invariant and the
# price-move swings were adopted to fix that -- that flaw comes back with this
# engine and is stated in the input's tooltip rather than quietly inherited.
#
# 2026-09-18: `biasSrc` BS_SMC -> BS_STRUCT, and the literal renamed again to
# "market structure + inducement". THE CHART'S DIRECTION NOW COMES FROM A
# DIFFERENT ENGINE, which is the largest default move in this file's history
# and is a chart-owner decision taken with the numbers in front of them:
#
#   tf     SMC 14/5 (was)        MS+IDM 50/3 (now)
#   15m    666 at -0.011         395 at +0.117
#   30m    682 at -0.008         374 at -0.058
#   1h     702 at -0.152         402 at -0.072
#
# Spent 23, counts and not a study. It is 40% FEWER setups again and the R
# column disagrees with itself across timeframes, which is what three numbers
# on a read universe look like.
#
# EVERY MEASUREMENT PAGE NOW DESCRIBES A DIFFERENT ENGINE FROM THE CHART, and
# that is not new but it is worse: the pages were produced on this engine at
# 6/2 PRICE-MOVE swings, and the chart now runs it at 50/3 BAR pivots with the
# minor tier coming from LuxAlgo's internal pass. `biasSrc` has been in PINNED
# since the last engine swap, so all ten studies that read it name it and none
# moves -- checked, not assumed.
#
# AND THE WATCHER HAD TO LEARN THE ENGINE. The parity test failed the instant
# the default moved, because the bot could not run what the chart draws; that
# is the whole point of it. riptide/watchers/undertow.py::_ms_structure is the
# third copy and two bugs were caught getting it there: a bar pivot whose
# probe sat inside its own window (zero swings, zero setups), and the port
# building the internal pass WITHOUT the swing pass as its reference, which
# moved sOs on 351 bars of a 4,000-bar walk.
#
# 2026-09-18: `useBackup` False -> True, the backup fill on the chart. And the
# procedure caught something much worse than the change it was run for.
#
# EIGHTEEN STUDIES READ useBackup FROM THE DEFAULT, so it went into PINNED and
# every one of them now names it -- step 1 and 2 before step 3, as this file
# says. Then the reproduction in step 4 FAILED: undertow_strict's S0 came back
# -0.124 against the -0.026 on its own published page.
#
# THE CAUSE WAS NOT THIS CHANGE. It was `stopSrc`, moved pullback -> minor
# swing EARLIER THE SAME DAY at the chart owner's request, with no check of
# which studies read it. Nineteen did. Pinning it back reproduced the page bit
# for bit, both arms. famStrict, armWins and biasTier all moved the same day
# with the same exposure and had not yet been noticed.
#
# ALL FIVE ARE IN PINNED NOW and all twenty studies name them at the values
# their pages were produced under -- famStrict False, armWins False, stopSrc
# the pullback extreme, biasTier the swing tier, useBackup off. The one
# exemption is undertow_rate.py, which is supposed to track whatever ships.
#
# The lesson is not new, which is the uncomfortable part: this file's own
# docstring describes exactly this happening twice before. What was missing is
# that a default moved BY REQUEST gets the same procedure as one moved on a
# whim, and four went through in a day without it.
# 2026-09-18: `biasTier` REMOVED — the field, its two constants, the Pine
# input, the watcher constant and the pin in twenty studies.
#
# IT COULD NOT AFFECT THE SHIPPED CHART. It chose which of the SMC engine's
# two passes was the direction, so `smc.state()` was the only reader — and the
# shipped `biasSrc` is BS_STRUCT, whose direction is the v2 engine's `os` and
# never goes through `state()` at all. The port produced BIT-IDENTICAL output
# on "swing" and "internal", 23 symbols, three timeframes. The watcher said the
# quiet part in code: `_ms_structure(cs) if BIAS_SRC == ... else mnr if
# BIAS_TIER == "internal" else maj` — the v2 branch came first.
#
# Its Pine tooltip meanwhile still advertised "internal" as 1.6x the setups at
# better R on all three timeframes. True when it was written, unreachable
# after the engine swap, and left on the chart promising an effect the switch
# could no longer produce.
#
# THE PROCEDURE, and this is the cheapest case it will ever see: every study
# pinned TIER_SWING, which is now the only behaviour, so removal is a no-op by
# construction. Asserted anyway — undertow_anchor, _htf and _slope re-run
# bit-identical against their pre-removal output before this line moved.
#
# 73 -> 72 fields.
# 2026-09-18: `pinLag` and `shortsOnly` added, for the chart owner's own
# description of what his eye does -- "let's say three qualified (n, n-1,
# n-2), in this case choose n-1".
#
# PURELY ADDITIVE. pinLag 0 is the newest candle, which is what `pinNewest`
# already produced and what every page was measured under; shortsOnly False
# keeps both directions. No existing default moves and no study's arms change.
# undertow_anchor re-ran BIT-IDENTICAL before this line moved.
#
# NEITHER GOES IN PINNED. `shortsOnly` is read by one study and `pinLag` by
# one, so putting them above would make twenty studies declare a setting they
# do not use -- the `emaFast` argument, a few entries up.
#
# 72 -> 74 fields.
# 2026-09-18: `stopSrc` REVERTED, minor swing -> pullback extreme.
#
# It moved TO the minor swing this morning on my reading of the chart owner's
# rule. His own worked example then showed the stop sitting just above the
# PULLBACK'S HIGHEST HIGH: 0.447% on BTC, against 0.53% for the pullback
# extreme and 0.24% for the pin high. The code was running a rule he does not
# trade.
#
# THAT ONE MOVE COST THREE DEFECTS IN A DAY -- nineteen silently re-pointed
# studies, a bias source that armed ZERO setups for want of a minor swing to
# read, and a stop 1.7x wider than the one being traded, which is most of why
# the code books 3.5R where he books 8R on the same move to the same target.
#
# The paired comparison leans the same way on all three timeframes, +0.049 /
# +0.092 / +0.073 R per armed setup with the worst leave-one-out still
# positive, and clears nothing -- no z past 1.2, symbols agreeing about half
# the time. It is a lean, not a result, and it is not the reason for the
# revert. The reason is that every page in ../measurements was produced under
# the pullback extreme and it is what the strategy's author actually does.
#
# NO STUDY MOVES: `stopSrc` is in PINNED and all twenty name it. undertow_
# anchor re-ran BIT-IDENTICAL before this line changed.
# 2026-09-18: `retraceLatch` added, True -- which is what has always happened.
#
# FOUND BY DIAGNOSING A TRADE THE CHART OWNER TOOK AND THE CHART DID NOT. At
# his bar the bias read `ending` with endWhy `retrace`, while the impulse was
# 46% given back against a threshold of 70. The condition that killed the bias
# was NO LONGER TRUE and the state had not noticed: `ending` latches and clears
# only on a CHoCH or a with-trend BOS, which at msLen 50 are rare. It had been
# untradeable for 66 bars -- 33 hours.
#
# Retrace is a CONTINUOUS, RECOVERABLE condition and bias() already argues, for
# `mixed`, that latching such a thing "would turn one bar of disagreement into
# a permanent cancellation". The flag makes that choice available to endD and
# touches nothing else; the other Ending rules are events and latching an event
# is defensible.
#
# ADDITIVE -- True reproduces current behaviour exactly, undertow_anchor re-ran
# BIT-IDENTICAL, and it is declared to the port check and the three-way check
# on that value. Not in PINNED: one study will read it and putting it above
# would make twenty declare a setting they never touch.
#
# 74 -> 75 fields.
# 2026-09-18: `biasGate` and `locAtr` added, both at the value that reproduces
# current behaviour. THE CAPABILITY ONLY -- no default moves here.
#
# `locAtr` IS THE KNIFE EDGE FIXED. `locTol` counts BARS since the pullback
# extreme and ships at 0, so the pin must BE the extreme bar: a doji there
# discards the whole pullback, and a pin seven bars later at nearly the same
# price is refused for being LATE rather than for being FAR. At > 0 the test
# becomes a price distance in ATR, which is the question the rule was always
# trying to ask.
#
# `biasGate` at "direction only" keeps the bias's DIRECTION and drops its
# veto -- the chart owner's "we don't reject based on the bias, we just trade
# the bias direction".
#
# AND THE MEASUREMENT SAYS SOMETHING NEITHER OF US EXPECTED. On the spent 23,
# shorts, R per armed setup:
#
#   direction only   271 -> 271 armed on Min15, 255 -> 257 on Min30. The bias
#                    veto admits far more PINS when dropped (138 -> 273 located
#                    on BTC alone) and almost no extra ARMS. Confirmation is
#                    the binding constraint, not the bias.
#   locAtr 0.5/1/2   armed 271 -> 317 -> 353 -> 416 on Min15, and R goes
#                    -0.057 -> -0.204 -> -0.192 -> -0.242. Mixed on Min30 and
#                    Min60. No value is clearly better and 15m is clearly
#                    worse.
#
# So the knife edge is now fixable and the data does not ask for it to be
# widened. Both stay off until that is decided deliberately.
#
# 75 -> 77 fields. undertow_anchor re-ran BIT-IDENTICAL.
# 2026-09-18: `PIN_LOCAL` and `pbLook` -- a FOURTH anchor, off by default.
#
# FOUND BY DIAGNOSING TWO OF THE CHART OWNER'S OWN SETUPS. All three existing
# anchors are tied to STRUCTURE -- a 50-bar pivot, the major CHoCH, the last
# internal break -- and in a grinding trend they sit nowhere near the pullback
# he is actually trading. On his two worked shorts the SHIPPED anchor was 7 and
# 41 bars back, 1.17 and 4.86 ATR away; PIN_LEG and PIN_TREND were worse still
# at 45 and 79 bars.
#
# PIN_LOCAL has no structure in it: the pullback is the rally since the LOWEST
# LOW OF THE LAST `pbLook` BARS. Under it both his pins land on the extreme --
# 0.00 and 0.13 ATR -- and his stop on the second matches the level to 14
# points in 78,500. The answer was stable from pbLook 6 to 12, a plateau rather
# than a fitted point, and breaks at 16 where it collapses back onto the
# structural high.
#
# WHAT IT REFRAMES. `locAtr` measured WORSE when widened, and this is why:
# widening a tolerance around the WRONG anchor admits noise rather than finding
# the right candles. With the anchor corrected, his first pin passes locTol = 0
# outright and the second needs 0.13 ATR.
#
# NOT MEASURED AND NOT DEFAULT. It reproduces two remembered setups, which is a
# reason to measure it and not a result -- remembered setups are the ones that
# worked. Additive; undertow_anchor re-ran BIT-IDENTICAL.
#
# 77 -> 78 fields.
# 2026-09-18: `msLen` 50 -> 14 and `biasGate` -> "direction only". SHIPPED, in
# all three copies, at the strategy author's instruction.
#
# msLen, because at 50 a bar pivot needs fifty bars either side -- twelve and a
# half hours on 15m -- and the bias cannot know about a trend that started this
# morning. It read LONG on his Min15 chart in the middle of a multi-day
# decline. Six alternative definitions were tested and EVERY ONE read SHORT
# there: 14/3, 6/2, SMC, an EMA cross, a regression slope, a Donchian midpoint.
# The genuinely fast ones are WORSE on the population -- Donchian is negative
# on Min15 -- so the answer was the same engine at a shorter length, not a
# different engine. Min30 spread +0.200 against +0.140; Min15 t 3.26 against
# 2.86; 12 turns per thousand bars against 3.6; tradeable 41% against 24%.
#
# biasGate, because "keep bias as the direction, nothing will stop the trade".
# Immature, Running and Ending all trade now. `Result.armed` carries the state
# on every setup, and the alert and panel report it, so the three can be scored
# apart later -- which is the stated reason for taking them all.
#
# THE PROCEDURE, IN THE ONLY ORDER THAT WORKS, and this file has had to say so
# three times today:
#   1. `biasGate` went into PINNED above. It was NOT there and every one of the
#      twenty studies read it from the default.
#   2. All twenty now pass biasGate=U.BG_TRADEABLE, which is what every
#      published page was produced under.
#   3. Only then did the default move.
# undertow_anchor, _htf and _slope all re-ran BIT-IDENTICAL before this line.
#
# AND THE THREE-WAY CHECK WAS NOT WATCHING msLen. It sat in the ABSENT bucket
# as "bar-pivot bias only" while the watcher had MS_LEN and fed it straight to
# _bar_pivots -- so the check that exists to stop the chart and the bot
# drifting apart was blind to the single largest lever on either. Moved to
# MIRRORED with msShortLen and biasGate.
DEFAULTS_FINGERPRINT = "be2ecc06ce36fb9a"
DEFAULTS_COUNT = 78

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


def _spread(node, dicts):
    """Keys reachable through a ** argument.

    A bare Name is the easy case. `{**BASE, "famStrict": strict}` is the one
    that bit: a study varying ONE setting across arms writes exactly that, and
    reading only the Name form made undertow_pinlag look like a baseline with a
    single setting and fifteen missing.
    """
    import ast as _ast
    if isinstance(node, _ast.Name):
        return set(dicts.get(node.id, set()))
    if isinstance(node, _ast.Dict):
        out = set()
        for k, v in zip(node.keys, node.values):
            if k is None:                       # nested ** inside the literal
                out |= _spread(v, dicts)
            elif isinstance(k, _ast.Constant):
                out.add(k.value)
        return out
    if isinstance(node, _ast.Call) and getattr(node.func, "id", None) == "dict":
        out = {kw.arg for kw in node.keywords if kw.arg}
        for a in node.args:
            out |= _spread(a, dicts)
        return out
    return set()


def test_the_baseline_pins_them_not_merely_the_file():
    """THE TEST ABOVE PROVES A NAME APPEARS. That is not the same thing.

    This weakness was written down in the header of this file on 2026-09-18 --
    "it proves a name appears, not that the baseline names it" -- and left
    unfixed. It then cost a whole page. `undertow_backup`'s BASE pinned
    everything and carried a docstring explaining why; its ARMS list right
    underneath had `("B0", "backup off", {})`, leaning on `useBackup` still
    defaulting to False. The grep above was satisfied by the five arms that DO
    say `useBackup=True`, so a baseline that had silently become a copy of the
    primary sailed through, and UNDERTOW_BACKUP_FILL.md's entire verdict was an
    arm subtracted from itself.

    So: parse the file, find the P(...) call that builds the BASELINE, and
    require the pinned names INSIDE THOSE PARENTHESES. A `**SPREAD` of a
    module-level dict counts -- undertow_default.py builds its baseline that
    way and it is the pattern the rest should move to -- so the dict's own keys
    are resolved and folded in.
    """
    import ast

    for p in sorted(STUDIES.glob("*.py")):
        src = p.read_text()
        if EXEMPT in src:
            continue
        tree = ast.parse(src)
        # Module-level dicts, so `U.P(**NEW)` can be resolved to NEW's keys.
        # BOTH SPELLINGS, because the first version of this only understood the
        # `{...}` literal and undertow_default.py -- the one study already
        # doing this the right way -- writes `NEW = dict(...)`. It came back as
        # a baseline with ONE setting and fourteen names missing, which is a
        # test calling its own best example the worst offender.
        dicts: dict = {}
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            keys, v = set(), node.value
            if isinstance(v, ast.Dict):
                keys = {k.value for k in v.keys if isinstance(k, ast.Constant)}
            elif isinstance(v, ast.Call) and getattr(v.func, "id", None) == "dict":
                keys = {k.arg for k in v.keywords if k.arg}
                # `OLD = dict(NEW, stopSrc=...)` inherits NEW's keys.
                for a in v.args:
                    if isinstance(a, ast.Name):
                        keys |= dicts.get(a.id, set())
            else:
                continue
            for t in node.targets:
                if isinstance(t, ast.Name):
                    dicts[t.id] = keys
        # A COLLECTION OF CONFIGS, and `for sw in SWINGS: P(**sw)`. undertow_
        # sweep.py is the real case and it is not an oversight: it SWEEPS
        # swingSrc/msLen/msShortLen, so those fields are the study's subject
        # rather than something it forgot. The union across the collection is
        # what is credited -- entries 3 and 4 of SWINGS set `swingK` instead of
        # `msLen`, correctly, because a price-move swing has no bar count, and
        # an intersection would fail a study for being right.
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            v = node.value
            if not isinstance(v, (ast.Tuple, ast.List)):
                continue
            keys = set()
            for e in v.elts:
                if isinstance(e, ast.Dict):
                    keys |= {k.value for k in e.keys if isinstance(k, ast.Constant)}
                elif isinstance(e, ast.Call) and getattr(e.func, "id", None) == "dict":
                    keys |= {k.arg for k in e.keywords if k.arg}
            if keys:
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        dicts[t.id] = keys
        # `for sw in SWINGS` -- bind the loop target to the collection's keys.
        for node in ast.walk(tree):
            if (isinstance(node, ast.For) and isinstance(node.target, ast.Name)
                    and isinstance(node.iter, ast.Name)
                    and node.iter.id in dicts):
                dicts[node.target.id] = dicts[node.iter.id]
        calls = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            f = node.func
            nm = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None)
            if nm not in ("P", "_P"):
                continue
            names = {k.arg for k in node.keywords if k.arg}
            for k in node.keywords:                      # **SPREAD
                if k.arg is None:
                    names |= _spread(k.value, dicts)
            calls.append(names)
        if not calls:
            continue
        # THE BASELINE IS THE RICHEST P(...) IN THE FILE. Every study here
        # builds one and derives its arms from it with dataclasses.replace, so
        # the call carrying the most settings is it. A study that grew a second,
        # equally specified baseline would need this rule revisited -- which is
        # why the count is printed rather than hidden.
        base = max(calls, key=len)
        missing = [f for f in PINNED if f not in base]
        ok(not missing,
           f"{p.name} pins its settings ON THE BASELINE "
           f"({len(base)} settings, {len(calls)} P() calls)"
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
               test_the_baseline_pins_them_not_merely_the_file,
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
