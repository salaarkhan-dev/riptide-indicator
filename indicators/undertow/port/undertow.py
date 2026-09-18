"""Riptide Undertow in Python — the transcription of riptide-undertow.pine.

WHY A PORT EXISTS. The Pine answers one chart at a time and scores it in
sample, which is how every bad result in this repository was produced. The port
answers the questions the chart cannot: the same rules over many symbols, three
timeframes, a held-out half and a random control, in seconds instead of an
afternoon of clicking.

TRANSCRIBED, NOT REIMPLEMENTED. Every identifier carries the Pine's name and
every condition is written in the Pine's order, so the two can be compared
mechanically rather than by eye:

    python3 deploy/undertow-port-check.py     the inputs: same names, same
                                              defaults, same dropdown strings
    indicators/undertow/tests/test_undertow_port.py    the logic

That is why this file reads oddly for Python. `msSBtmCrossed`, `pbExtX` and
`workHi` are not names anyone would choose here; they are the names in the
Pine, so they are the names here. The first of those two checks found a real
drift on its first run -- `rr` had defaulted to 2.0 here and 3.0 in the Pine --
which is exactly the silent kind: a study reporting a number for settings the
chart is not running.

THREE THINGS THE PORT HAS THAT THE PINE DOES NOT, each because Pine cannot:

  1. PRICE SWINGS (swings.py). A swing as a k x price move instead of n bars,
     so one setting can mean the same thing on 15m and on 1h. Off by default,
     and swings.py records the measurement that says WHICH price unit works --
     the obvious one, ATR, is worse than the bar pivot it replaces.
  2. HTF BIAS. Doing this correctly in Pine needs the whole structure engine
     inside a function so request.security can evaluate it on higher-timeframe
     bars, which would break the parity check against v2. In Python it is
     resampling and a forward-fill, with the HTF state made visible only on the
     base bar where the HTF bar CLOSES — no look-ahead.
  3. COSTS. A round-trip fee in R, subtracted per trade. The Pine's net R is
     gross and says so; at 1m gross is a fantasy and even at 30m it is not
     exactly right.

WHAT IT DELIBERATELY KEEPS. The ghost column: a setup the bias gate cancels is
walked forward anyway, into separate counters, so the gate can be measured
instead of trusted. See SPEC.md.

NOTHING HERE PLACES AN ORDER, and nothing here reads an API key.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from indicators.undertow.port import smc
from indicators.undertow.port.swings import (bar_swings, bars_per,
                                             price_swings, range_basis)

# The Pine's three comparison modes, by their exact input strings.
T_CLOSE = "close beyond"
T_TOUCH = "close at or beyond"
T_BODY = "whole body beyond"
# `stopSrc`
S_PIN = "Pin high / low"
# `biasGate` -- WHAT THE BIAS IS FOR. Module level, not class level, because
# deploy/undertow-port-check.py and the three-way check resolve a field default
# only through a module-level CONSTANT and silently skip anything else.
BG_TRADEABLE = "tradeable"
BG_DIRECTION = "direction only"
S_PULL = "Pullback extreme"
S_SWING = "Minor swing extreme"
# `bkWhen` — the two strings the Pine's dropdown offers, compared by value on
# both sides, so a reworded option silently breaks the branch. See
# deploy/undertow-port-check.py, which is the guard against exactly that.
B_LIVE = "live"
B_LATE = "after the limit expires"
# `biasSrc` — WHERE THE DIRECTION COMES FROM. Compared by value on both sides.
#
# The structure engine is the original and stays the default. The other four
# exist because "swing can be messy" is a real complaint with a real number
# behind it: a 6-bar pivot flips the bias 2.3 times a day on 15m and 1.1 on
# 30m -- the SAME setting behaving differently per timeframe, because six bars
# is ninety minutes on one chart and three hours on the other.
#
# NONE OF THEM IS ENDORSED. An earlier note in this project dismissed EMA,
# ADX and Supertrend on the strength of CCP_CONTEXT_FILTERS.md -- that study
# measured them as ENTRY FILTERS at liquidity grabs, which is a mean-reversion
# event on a different population doing a different job. Carrying its verdict
# to "direction source for a pullback-continuation strategy" was wrong, and
# these are here to be measured rather than assumed either way.
# THE EXTERNAL CHARACTER, AND THE DEFAULT. LuxAlgo's "Market Structure with
# Inducements & Sweeps", which riptide-indicator-v2.pine section 12 is a
# transcription of -- same bar-pivot detector, same crossed-flag CHoCH, same
# `sbtmy != btmy` inducement guard, same sweep. It is the only engine here
# with an INDUCEMENT.
#
# IT IS HALF OF A PAIR AND THE NAME SHOULD NOT HIDE THAT. Under this source
# the MAJOR tier is this engine and the MINOR tier is LuxAlgo's Smart Money
# Concepts internal pass at `smcInternalLen` -- external character from one,
# internal from the other, which is the arrangement that was asked for. See
# `structure()` and the Pine's `bSOs` line.
#
# The literal has been "structure" and "v2 structure (inducement)" and is now
# this. Both sides compare biasSrc BY VALUE so the Pine's option must match it
# exactly; renaming is safe because every reader in the tree uses the CONSTANT
# (checked -- no bare literal anywhere).
BS_STRUCT = "market structure + inducement"
BS_EMA = "EMA cross"
BS_ST = "Supertrend"
BS_SLOPE = "Slope"
BS_DON = "Range midpoint"
# TWO TIMEFRAMES, EMA 20/50 ON EACH, AND TRADE ONLY WHEN THEY AGREE. Supplied
# as a Pine script ("MTF Market Structure Bias"): bias from the slower
# timeframe, structure from the faster, FULL BULLISH / FULL BEARISH / MIXED,
# and MIXED means stand aside. It is NOT any of the four above:
#   * S2 in UNDERTOW_BIAS_SOURCE.md was EMA 50/200 on ONE timeframe, and that
#     prereg said in as many words that "EMA 20/50 might do better" is a
#     different prereg. This is it.
#   * the HTF gate in UNDERTOW_HTF.md ran the STRUCTURE engine one timeframe
#     up. That page's own closing line says an HTF direction "from something
#     else entirely" is a different question. This is that too.
# It is the first source here with a THIRD state. The others are always long or
# short; this one abstains, which is why `mixed` needed a channel of its own.
BS_MTF = "MTF EMA align"
# LuxAlgo's Smart Money Concepts structure, asked for as the major character.
# smc.py has the two measurements that say what is and is not different from
# the original engine: the swing detector and the CHoCH are IDENTICAL, and the
# pivot length and the BOS rule are not.
BS_SMC = "SMC structure"
BS_RSI = "RSI bias"
# `biasTier`, `TIER_SWING` and `TIER_INTERNAL` WERE HERE. The field chose which
# of the SMC engine's two passes was the direction, so it was read only on the
# BS_SMC path -- and the shipped `biasSrc` is BS_STRUCT, whose direction is the
# v2 engine's `os` and never goes through smc.state() at all. Both settings
# produced bit-identical output on 23 symbols at all three timeframes.
#
# It was removed rather than documented, for the reason UNDERTOW_DEFAULT.md
# gives about `armWins`: a switch that cannot change an outcome is one fewer
# thing to reason about. Nineteen studies pinned it and every one pinned the
# swing tier, so removing it moves no published number -- asserted by
# re-running them, not by this comment.
# `swingSrc` — how a swing is DEFINED. Compared by value on both sides.
SW_BAR = "bar pivot"
SW_RANGE = "price move"
# Port-only, and kept only because a test pins the measurement that rejected
# it. Not an option on the chart and it must not become one.
SW_ATR = "atr"
# `pinAt` — WHICH END OF THE LEG THE COUNTER-TREND CANDLE SITS AT, and this is
# the rule v1 and v2 both got wrong.
#
#   "pullback extreme"  the top of the rally in a downtrend. What every
#                       measurement before UNDERTOW_V2.md used.
#   "trend extreme"     the LEG LOW in a downtrend -- the bounce attempt. The
#                       corrected reading, confirmed by the strategy's author.
#
# The geometry is what gives it away. The stated priority shape in a bearish
# trend is the HAMMER, which has a long LOWER wick. A long lower wick at the
# TOP of a rally is a candle that dipped and recovered; the rejection shape
# there is the long UPPER wick. A hammer belongs at a LOW. Measured, the code
# was picking hammer and inverted hammer 49/51 -- a coin flip -- because it was
# looking somewhere neither shape means anything in particular.
#
# And it fits W->F exactly: a green hammer at the leg low is a bounce attempt,
# W is the bounce WORKING (close above its high), F is it FAILING (close below
# its low), and the limit sells the retrace back to its open.
PIN_PULL = "pullback extreme"
PIN_TREND = "trend extreme"
# THE THIRD ANCHOR, and it is the one the strategy's author drew. PIN_TREND
# anchors on the running extreme since the MAJOR CHoCH -- one point per trend.
# At the 6/2 scale that updated every few bars and looked right; at 50/5 it is
# a single stale point and the priority-shape pin sits a MEDIAN OF 47 BARS
# past it, so `locTol 0` keeps 3.9% of them and the option is unusable.
#
# The author's diagram shows one anchor PER MINOR LEG -- four circles in one
# trend, each at a local turn. That is this: the running extreme since the last
# INTERNAL structure break. Median distance 8 bars, and `locTol 2` keeps 26.7%
# against PIN_TREND's 9.2%.
#
# IT IS ALSO THE ONLY ONE OF THE THREE THAT IS BOTH PER-LEG AND LAG-FREE.
# Anchoring on the confirmed internal SWING would also be per-leg, but a pivot
# of length N is confirmed N bars late, so nothing can ever sit within N bars
# of it -- measured, 0% at any tolerance below 5. SPEC 2.3 avoided swings for
# exactly this reason and the same reason applies here.
PIN_LEG = "leg extreme"
# THE FOURTH ANCHOR, and the one two of the chart owner's own trades point at.
# The other three are all tied to STRUCTURE -- a 50-bar pivot, the major CHoCH,
# the last internal break -- and in a grinding trend they sit a long way from
# where the trader's pullback is. On his two worked setups the shipped anchor
# was 7 and 41 bars back, 1.17 and 4.86 ATR away; PIN_LEG and PIN_TREND were
# worse still at 45 and 79 bars.
#
# This one has no structure in it at all: THE PULLBACK IS THE RALLY SINCE THE
# LOWEST LOW OF THE LAST `pbLook` BARS (mirrored for an uptrend). Under it both
# his pins land ON the extreme -- 0.00 and 0.13 ATR -- and his stop on the
# second matches the level to 14 points in 78,500.
#
# NOT MEASURED. It reproduces two remembered setups, which is a reason to
# measure it and not a result.
PIN_LOCAL = "local pullback"
# `slopeUnit` — whether the Slope source measures its window and its threshold
# in bars (so it means a different thing on every chart) or in time.
SL_BARS = "bars"
SL_HOURS = "hours"
# `htfUnit` — the same question for the higher-timeframe gate. A MULTIPLE of
# the base bar is a different span of time on every chart; a span of hours is
# not. The two share SL_BARS/SL_HOURS' spelling on purpose.
HTF_BARS = "bars"
HTF_HOURS = "hours"
# `endMinor`
# `confirmOrder` — THE ORDER THE TWO CONFIRMATIONS MUST ARRIVE IN.
#
# v1 required both "in either order", and that was a misreading of the
# strategy, corrected by its author after twelve studies had been run on it.
# The real rule is that a WORKING break must come FIRST and a FAILURE break
# after it. W->F arms. F->W->F arms, on that second F. F->W does not arm until
# another F arrives. An F with no W before it is not the setup at all.
#
# The mechanism is what makes it a rule rather than a detail: the pin is a
# counter-trend candle, W is it appearing to WORK as a reversal, F is that
# reversal failing. "Either order" admits bars where the reversal never worked,
# which is a different event with the same two lines touched.
C_EITHER = "either order"
C_WF = "working then failure"
E_OFF = "off"
E_FLIP = "on the flip"
E_OPPOSED = "while opposed"


@dataclass(frozen=True)
class P:
    """Every input in the Pine, same names, same defaults, plus the three the
    Pine cannot have. Frozen so a sweep cannot mutate a shared config."""
    # 1 · Bias
    msLen: int = 50
    msShortLen: int = 3
    msBosNeedsIdm: bool = True
    endMinor: str = E_FLIP
    endSweep: bool = False
    endStale: bool = False
    staleBars: int = 30
    retraceMax: int = 70
    adxMin: int = 0
    # THE CHART'S ENGINE IS LuxAlgo's NOW, so the port's default follows it —
    # a port default that differs from the chart's is the one failure
    # deploy/undertow-port-check.py exists to catch, and `biasSrc` is port-only
    # there, so nothing would have caught this one.
    #
    # BS_STRUCT is still here and still runs riptide's engine: every page in
    # ../measurements was produced on it, and all ten studies that used to read
    # this default now pin BS_STRUCT explicitly so they keep reproducing. See
    # test_studies_pin_their_settings.py, where the order of operations is
    # written out.
    biasSrc: str = BS_STRUCT
    # DUYCK'S RSI BIAS, the one alternative source on the chart. The two
    # levels are a HYSTERESIS BAND, not a threshold: crossing above the top
    # turns the bias up, crossing below the bottom turns it down, and between
    # them it holds whatever it last was. 55 and 34 by request, against the
    # reference's 60 and 40.
    #
    # `rsiHA` picks the reference's "future smoothed" variant, which runs the
    # RSI over the projected next Heikin-Ashi open instead of ohlc4 -- and
    # hard-codes length 14 while doing it, which is the original's quirk and is
    # reproduced rather than tidied. See dir_rsi.
    rsiLen: int = 14
    rsiTop: float = 55.0
    rsiBot: float = 34.0
    rsiHA: bool = False
    # PORT-ONLY AGAIN, and back at the lengths its page was produced under.
    # The EMA cross was on the chart for part of one day at 9/21; the chart now
    # offers the structure engine and Duyck's RSI bias and nothing else, so the
    # only readers left are UNDERTOW_BIAS_SOURCE.md's S2 at 50/200 and
    # undertow_mtf at 20/50 -- both of which name their own lengths, which is
    # what test_a_source_arm_names_its_own_lengths requires of any study that
    # touches an alternative source.
    emaFast: int = 50
    emaSlow: int = 200
    stAtrLen: int = 10
    stMult: float = 3.0
    # SLOPE, AND THE SAME TRAP THE SWINGS FELL INTO. `slopeLen` is a number of
    # BARS and `slopeMin` is quoted in ATR per BAR, so BOTH halves of the rule
    # move when the chart does: the shipped 50/0.05 flips the direction 1.2
    # times a day on 15m and 0.5 on 30m. That is the exact defect `price move`
    # swings were adopted to fix, and Slope as shipped does not fix it.
    #
    # `slopeUnit = "hours"` restates the same rule in time:
    #   window     `slopeHours` of trading, however many bars that takes
    #   threshold  `slopeMinPerHr` DAY-RANGES PER HOUR -- the fit's rise per
    #              hour over the last 24h high-to-low, the same unit the swing
    #              detector uses, and the only one here that is not per-bar.
    # 12.5 hours is 50 bars on 15m: the shipped setting, restated, not retuned.
    #
    # "hours" IS THE DEFAULT, on the consistency ground alone and by an explicit
    # decision recorded in UNDERTOW_SLOPE_DEFAULT.md. It is NOT a promotion:
    # Slope is not the default bias and did not clear the promotion rule. This
    # only decides which Slope you get if you pick Slope. Measured flips per
    # day across 15m / 30m / 1h: bars 1.21 / 0.63 / 0.28, hours 1.21 / 1.16 /
    # 1.55. A rule whose activity quarters between two charts is two rules.
    #
    # 0.02, not 0.05, and the difference matters. 0.02 is the rung the
    # pre-registered ladder picked by matching flip rate to the bars setting on
    # 15m -- 1.120 a day against a target of 1.066. 0.05 was a placeholder
    # written before that ran and gives 0.412 a day with a 45-hour hold, which
    # is a different rule wearing the same name.
    slopeUnit: str = SL_HOURS
    slopeLen: int = 50
    slopeMin: float = 0.05
    slopeHours: float = 12.5
    slopeMinPerHr: float = 0.02
    donLen: int = 50
    # `BS_MTF`. The EMA pair is run on the BASE bars and again on bars
    # aggregated `mtfMult` times, and a direction is only taken when the two
    # agree. mtfMult 2 on a 15m chart is exactly the 15m / 30m pairing the
    # script was written with; expressing it as a ratio rather than two fixed
    # timeframe strings is what lets the same rule be run on 30m and 1h at all,
    # since a 15m series cannot be built from 1h bars.
    mtfFast: int = 20
    mtfSlow: int = 50
    mtfMult: int = 2
    # For every source EXCEPT the structure engine there is no BOS to count, so
    # "running" cannot mean "has broken structure once". It means the direction
    # has held this many bars since it last flipped. Structure ignores it.
    # `BS_SMC`. LuxAlgo's own defaults, 50 and 5, because the pivot LENGTH is
    # the real difference between that engine and this one and running it at
    # Undertow's 6/2 would test the wrong thing.
    # 14, NOT LuxAlgo's 50, and the reason is coverage rather than accuracy.
    # UNDERTOW_SCALE.md measured 50/5 against 6/2 and found R identical across
    # the whole range -- the scale buys a quieter chart, not better trades. So
    # the choice is purely how often the thing speaks, and 50 speaks rarely:
    # the bias flips 0.34 times a day on 15m and is tradeable 16% of the time,
    # in dead stretches with a median of 109 bars.
    #
    # THE INTERNAL LENGTH MATTERS MORE THAN THE SWING LENGTH FOR COVERAGE, and
    # that was the surprise. Measured on FRESH6 Min15, at the SAME 1.10 flips a
    # day:
    #
    #     14/2   0.36 trades a day   29.6% tradeable
    #     14/5   0.75 trades a day   41.1% tradeable
    #
    # Double the trades from the internal length alone. At 2 the minor tier is
    # twitchy, `endMinor` fires on noise and latches `ending`; at 5 the same
    # major bias comes with far fewer spurious Endings. 14/5 is the best
    # coverage-per-flip on the table.
    #
    # THIS IS A PREFERENCE, NOT A PROMOTION, on the same footing 50/5 had. R is
    # flat across 6/2 to 50/5, so nothing here was earned by measurement --
    # what the measurement did was establish that the choice is free.
    smcSwingLen: int = 14
    smcInternalLen: int = 5
    matureBars: int = 20
    # 2 · Candle
    wickEdge: float = 0.05
    useHammer: bool = True
    useStar: bool = True
    # 3 · Setup
    workTest: str = T_CLOSE
    # "AFTER EXACT CLOSE AT THE FAILURE WE WILL CONSIDER AS FAILED, at that
    # failure or beyond." The strategy's author, and it is a definition rather
    # than a setting: a close that lands exactly ON the Failure line IS the
    # failure. WORKING stays strict -- the counter-trend attempt has to
    # genuinely clear its line for it to count as having worked, which is the
    # asymmetry the rule describes.
    #
    # It bites less often than it sounds and more often than never: an exact
    # equality needs a close on the tick, which happens on coarse ticks and
    # round numbers. Every measurement page was produced under the strict test
    # and each study now pins it.
    failTest: str = T_TOUCH
    # THE DEFAULT IS THE CORRECTED RULE, and it matches the chart's. v1's
    # "either order" was a misreading of the strategy, so shipping it as the
    # default would mean the port and the Pine agree on a rule that is not the
    # one being traded -- and a Pine default that differs from the port's is
    # precisely the failure undertow-port-check.py exists to catch.
    #
    # EVERY MEASUREMENT PAGE WAS PRODUCED UNDER "either order", so every study
    # now PINS it. That is the arrangement test_studies_pin_their_settings.py
    # enforces, and confirmOrder is in its PINNED list for exactly this reason.
    confirmOrder: str = C_WF
    # Require a BOS in the trend direction before a pullback is tradeable --
    # "look for the pullback AFTER the BOS". At False a fresh CHoCH with no
    # break of structure behind it is tradeable, which is what v1 did.
    needBos: bool = False
    # The NEWEST counter-trend candle in a pullback supersedes the ones before
    # it, across families: a hammer then an inverted hammer uses the inverted
    # hammer, and an inverted hammer then a hammer uses the hammer. At False
    # every pin runs as its own candidate, which is what v1 did.
    pinNewest: bool = True
    # WHICH of the pullback's qualifying candles to trade, counting back from
    # the newest. 0 = the newest, which is what `pinNewest` already produces
    # and what ships. 1 = THE SECOND NEWEST -- "if three qualified, n, n-1 and
    # n-2, take n-1" -- which is the chart owner's own description of what his
    # eye does and has never been coded.
    #
    # HOW OFTEN IT BITES, counted from `Result.pins` per pullback: 36% of
    # pullbacks offer two or more qualifying candles under the strict shape
    # gate, and 62% under the whole hammer family. So lag 1 is a minority rule
    # under strict and a MAJORITY rule under the family.
    #
    # THE FIRST VERSION OF THIS COMMENT SAID 18% AND 22%, and it was wrong.
    # Those came from grouping ARMED setups that fell within twelve bars of
    # each other, which both merges separate pullbacks and counts only the
    # candidates that happened to confirm. The qualifying candles are scattered
    # through the pullback, not adjacent -- which is exactly what the chart
    # owner said when correcting it -- and `pins` was added so the question is
    # answered from the pullback identity instead of from a proximity guess.
    #
    # The comparison is still PAIRED, on the pullbacks where the two rules pick
    # different candles: most qualifying candles never confirm, so the number
    # of pullbacks where BOTH rules produce a trade is far smaller than the
    # number that offer a choice.
    #
    # A pullback with fewer qualifying candles than the lag needs produces NO
    # setup. That is a real cost of the rule rather than an implementation
    # detail, and `nLagShort` counts it so no page can quietly omit it.
    # DOES THE RETRACE RULE LATCH? It always has, and that is the defect the
    # chart owner's own 1:8 short exposed: at his bar the bias read `ending`
    # with endWhy `retrace`, while the impulse was 46% retraced against a
    # threshold of 70. The condition that killed the bias was no longer true
    # and the state had not noticed -- it had been untradeable for 66 bars.
    #
    # Retrace is a CONTINUOUS, RECOVERABLE condition: price gives back 75% of
    # the leg and then takes it back to 40%. `mixed` is the same kind of
    # condition and bias() already refuses to latch it, in as many words --
    # "latching it would turn one bar of disagreement into a permanent
    # cancellation". This makes that choice available to the retrace rule.
    #
    # The other Ending rules are EVENTS -- a minor CHoCH against the trend, a
    # sweep -- and latching an event is defensible. This flag is deliberately
    # narrow and touches endD only.
    # WHAT THE BIAS IS FOR. "tradeable" is what has always happened: a setup is
    # refused unless the bias is Immature or Running, so Ending and None kill
    # it outright. "direction" uses the bias for its DIRECTION ONLY -- trade
    # with it, never reject on its state.
    #
    # THE COST IS NOT SMALL AND IS NOT HIDDEN. The bias is tradeable 24% of the
    # time at the shipped lengths, so "direction" admits roughly four times the
    # population. It also removes the guard that the retrace rule exists to be:
    # setups will be taken into a leg that has already given itself back.
    # `biasSeen` is still required -- before the first CHoCH there is no
    # direction to trade, only the initial value of `os`.
    biasGate: str = BG_TRADEABLE
    # LOCATION IN ATR RATHER THAN IN BARS, and this is the knife edge fixed.
    # `locTol` counts BARS since the pullback extreme and ships at 0, so the
    # pin must BE the extreme bar -- a doji or a wrong-coloured bar there
    # discards the whole pullback, and a pin seven bars later at nearly the
    # same price is refused for being late rather than for being far.
    #
    # At > 0 the test becomes a PRICE distance: the candle's own extreme must
    # sit within `locAtr` x ATR of the pullback's extreme, and `locTol` is not
    # consulted. Continuous, scale-free, and it asks the question the rule was
    # always trying to ask.
    # How far back PIN_LOCAL looks for the low that starts the pullback. The
    # answer was stable from 6 to 12 on both worked setups -- a plateau rather
    # than a fitted point -- and breaks at 16, where the anchor jumps back to
    # the structural high the shipped rule already uses.
    pbLook: int = 10
    locAtr: float = 0.0
    retraceLatch: bool = True
    pinLag: int = 0
    # Take only shorts. The chart owner asked for the bearish leg on its own
    # first -- "just measure the shorts and bearish whether this work or not"
    # -- and filtering AFTER the run is not the same thing, because the longs
    # would still have consumed `maxLive` slots and changed which shorts exist.
    shortsOnly: bool = False
    confirmBars: int = 20
    fillBars: int = 20
    maxLive: int = 4
    # LOCATION, AND THE THREE DEFECTS SPEC.md 2.3b RECORDS. All three ship at
    # the value that reproduces current behaviour; none is endorsed and none is
    # measured yet.
    #
    #   locTol      bars AFTER the pullback extreme a pin may still sit. At 0
    #               the pin must BE the extreme bar, so a doji or a wrong-
    #               coloured bar there discards the whole pullback and a
    #               textbook pin one bar later cannot qualify.
    #   pbMinAge    bars the pullback must have RUN before a pin counts. At 0
    #               the bar that makes a new trend extreme is immediately its
    #               own "pullback extreme" -- 25% to 34% of setups are that.
    #   pbMinDepth  fraction of the impulse leg the pullback must have given
    #               back. At 0.0 there is no minimum pullback in price at all.
    #
    # `locTol` has only ever been measured at 0 and at 50, and 50 is the
    # ablation's destroy-it arm, not a 1-to-3-bar tolerance.
    # DEFAULTS TO v1's so every measurement page keeps reproducing. The
    # corrected reading is PIN_TREND and it is measured before it moves.
    pinAt: str = PIN_PULL
    # The stated priority: HAMMER in a bearish trend, SHOOTING STAR in a
    # bullish one, with the other shape acceptable when the priority one is
    # absent. v1 had no ordering at all and took whichever sat at the extreme.
    famPriority: bool = True
    # THE PRIORITY SHAPE AND NOTHING ELSE. `famPriority` above is a RANKING:
    # the second-choice shape still trades when the priority one is absent.
    # This makes it a GATE -- in a bullish trend only the red shooting star
    # arms, in a bearish trend only the green hammer, and the hanging man and
    # the inverted hammer stop being setups at all.
    #
    # Note what the pair of gates leaves. `colourOk` already fixes the colour,
    # so strict + colour is exactly ONE code per direction: SS in a bull trend,
    # HAM in a bear trend. The four-code taxonomy collapses to two.
    #
    # OFF, AND MEASURED -- ../measurements/UNDERTOW_STRICT.md. The gate is
    # EXACT: 3,157 armed trades on a universe never looked at, not one of them
    # anything but a hammer short or a shooting star long. The pre-registered
    # impossibility was zero off-shape rather than a threshold, and it held.
    # And the trades are not better: -0.067 / -0.040 / -0.062 R against what
    # ships at -0.090 / -0.026 / +0.038, beaten by a matched random discard on
    # two of three.
    #
    # THE ONE CELL WORTH KNOWING ABOUT, because somebody will find it later
    # and think it was buried: on 1h the half this gate THROWS AWAY scored
    # +0.197 at a 27.3% win rate against the priority half's -0.062, z -2.46.
    # It is the only |z| >= 2 in eighteen studies and it points AGAINST the
    # stated rule. One cell of three with the other two at nothing is a ~14%
    # coincidence, so it is not a result -- it is the best-supported candidate
    # this project has produced for its own prereg, and it needs a fresh
    # universe rather than a promotion out of the study that found it.
    famStrict: bool = True
    # WHICH HALF THE STRICT GATE ADMITS, and it is PORT-ONLY on purpose.
    #
    # With `famStrict` on and this on, the gate inverts: only the hanging man
    # in a bullish trend and only the inverted hammer in a bearish one -- the
    # shapes the strategy calls second-best. Nobody asked for this rule. It
    # exists because ../measurements/UNDERTOW_STRICT.md found that on 1h those
    # shapes scored +0.197 R per trade against the priority half's -0.062, the
    # only |z| >= 2 in eighteen studies, and the only way to find out whether
    # that was the ~14% coincidence its own page predicted is to run it on a
    # universe nobody has seen.
    #
    # IT DID NOT REPLICATE -- ../measurements/UNDERTOW_COMPLEMENT.md, on a
    # universe frozen for it with the primary timeframe named in advance. The
    # sign held and the size halved: +0.258 became +0.117 +/- 0.114, z 1.03,
    # which is what the winner's curse does to a cell selected as the largest
    # of three. And the close is sharper than "no effect": detecting +0.117 at
    # |z| >= 2 needs about 110 symbols carrying 500 days of 1h, and 75 unused
    # contracts remain on the venue. No further study can settle it.
    #
    # NO CHART INPUT. An input is for a rule somebody wants to trade; this is a
    # rule that was tested and did not clear its bars. See
    # ../prereg/PREREG_undertow_complement.md, which also says why the study's
    # PRIMARY arm is a slice of the baseline rather than this flag: with the
    # gate inverted the priority shapes never enter the pool, so famPriority's
    # rivalry has nothing to act on and the surviving set can differ. This flag
    # is the tradeable version; the slice is the measured one.
    famInvert: bool = False
    # FIRST TO ARM WINS, and the rest of the pullback's candidates are dropped.
    #
    # "Which one wins first we should remove the other -- by win I mean W→F."
    # A pullback offers several counter-trend candles and `pinNewest` already
    # thins them as new ones appear, but once one COMPLETES ITS W→F the others
    # are still sitting there waiting to arm on their own levels. That is how
    # four limit orders end up resting inside one pullback, which
    # UNDERTOW_OVERLAP.md measured as one idea at four times the size: 74% of
    # 15m trades run alongside another in the same direction and they resolve
    # the same way 78% of the time.
    #
    # It is a better selector than `maxLive` because it selects on an EVENT
    # rather than on age. The cap keeps the oldest four and turns away the
    # rest; this keeps the one that actually completed the pattern.
    #
    # OFF BY DEFAULT AND UNMEASURED, and the size of it is smaller than it
    # sounds: armed setups fall 10% on a spent universe, not the large share I
    # assumed before measuring. `pinNewest` already thins the rivals, so by the
    # time one arms there are often few left to drop. At the CHART's own
    # maxLive of 4 it also cuts cap-refusals from 511 to 364, which is the
    # visible half of the complaint -- fewer setups turned away by AGE because
    # fewer are loitering.
    #
    # 10% is small enough to argue it is a correction and large enough that it
    # is still a trade-population change with no evidence behind it, so it
    # waits for a prereg rather than shipping on the strength of being clearly
    # stated.
    armWins: bool = True
    locTol: int = 0
    pbMinAge: int = 0
    pbMinDepth: float = 0.0
    # 4 · Levels
    # REVERTED to the pullback extreme. It went to the minor swing this
    # morning on a reading of the chart owner's rule, and his own worked
    # example shows the stop sitting just above the PULLBACK'S HIGHEST HIGH
    # -- 0.447% on BTC against 0.53% for this source and 0.24% for the pin.
    #
    # It is also what every page in ../measurements was produced under, and
    # the paired comparison leans the same way on all three timeframes
    # (+0.049 / +0.092 / +0.073 R per armed setup, worst leave-one-out still
    # positive, no z past 1.2 -- a lean, not a result).
    #
    # THE MOVE AWAY COST THREE DEFECTS IN A DAY: nineteen silently
    # re-pointed studies, a bias source that armed zero setups because it has
    # no minor swing to read, and a stop 1.7x wider than the one being traded.
    stopSrc: str = S_PULL
    stopTrack: bool = True
    stopBuf: float = 0.25
    rr: float = 3.5
    # 5 · Backup fill. "if we miss we can fill the order as a backup on any OB
    # or FVG." OFF by default and unmeasured. It is NOT a better price: for a
    # short the zone sits BELOW the Focus, so it is further from the stop --
    # bigger risk, further target, worse R on the same move. What it buys is a
    # trade instead of no trade.
    useBackup: bool = True
    bkTrigger: float = 1.0
    bkMaxRisk: float = 2.0
    useOB: bool = True
    useFVG: bool = True
    bkLook: int = 30
    # WHEN the backup is placed, and it is the whole question.
    #   "live"  alongside the Focus limit, once the move has run bkTrigger x
    #           risk. The zone is NEARER than the Focus, so price touches it
    #           first -- which converts some misses into trades and takes a
    #           worse price on others that were going to fill anyway. Measured:
    #           +0.6R on the first group, -0.27R on the second, net nothing.
    #   "late"  only once the Focus window has EXPIRED unfilled. There is then
    #           no order left to pre-empt, so every backup is an added trade by
    #           construction -- at the cost of every zone touch that happened
    #           inside the window.
    bkWhen: str = "live"   # or "after the limit expires"
    bkLateBars: int = 20
    # ── port only ───────────────────────────────────────────────────────────
    # WHERE THE SWINGS COME FROM. See swings.py -- the choice is the answer to
    # "each works different on different TF", and the three options are not
    # equally good at it. Measured on a 4:1 aggregation, swings per unit time:
    #   "bar pivot"   the v2 pivot, msLen / msShortLen in BARS     x0.30
    #   "atr"         k x ATR(14). A per-bar unit, so it is WORSE  x0.22
    #   "price move"  k x the range of `swingHours` of trading     x0.89
    # "price move" is the only one that means the same thing on 15m and on 1h.
    # IT IS NOW THE DEFAULT, and not because it makes money -- it does
    # not. UNDERTOW_BIAS_SOURCE.md measured it against four alternatives and it
    # beat none of them. It is the default because it is the only setting in
    # that study that behaves the SAME on 15m as on 30m: 0.6 flips a day on
    # both, against the bar pivot's 2.3 and 1.1. One setting that means one
    # thing on every chart is worth having on its own terms, and it makes every
    # future measurement comparable across timeframes.
    swingSrc: str = SW_BAR
    swingK: float = 0.40
    swingKMinor: float = 0.12
    swingHours: float = 24.0
    # HTF BIAS. The base bars are aggregated, the SAME structure engine is run
    # on the aggregate, and a setup may only be taken when the higher
    # timeframe's direction agrees with the base direction and is itself
    # tradeable. `htf_dir` writes an HTF bar's verdict onto base bars only from
    # the bar AFTER the one that closed it, so there is no look-ahead.
    #
    # AND IT HAS THE SAME UNIT PROBLEM AS EVERYTHING ELSE HERE. `htfMult` is a
    # multiple of the BASE bar, so htfMult 4 is 1h on a 15m chart and 4h on a
    # 1h chart -- one setting, two rules, which is the defect the swings and
    # then Slope were both rewritten to remove.
    #
    #   htfUnit "bars"   htfMult BASE bars per HTF bar. 0 or 1 = the gate is
    #                    off. This is what the parameter study ran.
    #   htfUnit "hours"  htfHours of trading per HTF bar, however many base
    #                    bars that takes. 4.0 is a 4h bias on every chart.
    #
    # DEFAULT IS OFF, under either unit, and was never measured on its own --
    # the parameter study carried htf as one binary dimension of a 48-cell
    # grid and only ever scored the selected cell.
    htfUnit: str = HTF_BARS
    htfMult: int = 0
    htfHours: float = 0.0
    # ABLATION SWITCHES. Not inputs on the chart, because they are not settings
    # anyone should trade -- they exist so a study can remove one gate at a
    # time and attribute the difference. The Pine has no equivalent and must
    # not grow one; deploy/undertow-port-check.py lists them as port-only.
    #   useFamily  False -> every bar passes the wick taxonomy. The 1CP layer
    #                       is gone and only location and colour remain.
    #   useColour  False -> the counter-trend colour test is gone.
    # With both off and locTol at 0, the "pin" is just "the pullback extreme".
    useFamily: bool = True
    useColour: bool = True
    # THE BACKUP'S CONTROL, and it is the bar that decides whether the zones
    # mean anything. "zone" is the real thing: the nearest order block or
    # fair-value gap. "mid" keeps the trigger, the cap and the direction and
    # throws the zone detection away, entering at the MIDPOINT between the
    # trigger bar's extreme and the Focus line. If the two score the same, what
    # is being measured is "enter later into a running move" and the OB/FVG
    # machinery is decoration.
    bkMode: str = "zone"
    # Round-trip cost as a fraction of NOTIONAL, subtracted per trade after
    # conversion to R. 0.0007 is a maker-in / taker-out round trip on a major
    # perp. Not a guess at slippage, which is separate and worse.
    #
    # IT DEFAULTED TO ZERO AND THAT WAS A REPORTING BUG, not a neutral choice.
    # Every study passes 0.0007 explicitly, so no measurement moves -- but the
    # CHART and the WATCH read the default, so both reported gross R and a
    # gross break-even line. UNDERTOW_V3.md is what made that indefensible: the
    # fee is charged in price and the trade is scored in R, so the drag is
    # fee/risk, and with risk at 1.3% of entry on 15m the break-even win rate
    # is 23.5% rather than 22.2%. A panel colouring 23.0% green was calling a
    # losing strategy a winning one. The default is now the same 7bp every
    # study has used since the first one.
    feeFrac: float = 0.0007

    def tag(self) -> str:
        """The settings that a sweep varies, in one short line."""
        sw = (f"bar {self.msLen}/{self.msShortLen}"
              if self.swingSrc == SW_BAR
              else f"{self.swingSrc} {self.swingK}/{self.swingKMinor}")
        return (f"{sw} idm{int(self.msBosNeedsIdm)} "
                f"end[{self.endMinor[:4]}|{int(self.endSweep)}"
                f"{int(self.endStale)}|rt{self.retraceMax}|adx{self.adxMin}] "
                f"w{self.wickEdge} loc{self.locTol} rr{self.rr} "
                + (f"htf{self.htfHours}h" if self.htfUnit == HTF_HOURS
                   else f"htf{self.htfMult}"))


@dataclass(eq=False)
class Trade:
    """One filled setup, walked to its target or its stop."""
    symbol: str = ""
    bar: int = 0                 # the pin
    armBar: int = 0
    fillBar: int = 0
    exitBar: int = 0
    short: bool = False
    entry: float = 0.0
    stop: float = 0.0
    target: float = 0.0
    won: bool = False
    r: float = 0.0               # net of feeFrac
    ghost: bool = False          # the bias gate cancelled it; scored apart
    state: str = ""              # the bias AT THE PIN
    code: str = ""               # HAM / HGM / IH / SS
    backup: str = ""             # "OB" / "FVG" if this was a backup fill


@dataclass
class Result:
    symbol: str = ""
    bars: int = 0
    # the funnel, exactly the Pine's panel
    nRaw: int = 0
    nPins: int = 0
    nColour: int = 0
    nLoc: int = 0
    nCap: int = 0
    nArmed: int = 0
    nFilled: int = 0
    nMissBack: int = 0
    nMissStop: int = 0
    nMissGone: int = 0
    nMissBias: int = 0
    # Candidates that expired inside the confirm window, split by what was
    # missing. nLoc - nCap - nArmed == nNoWork + nNoFail + whatever is still
    # live at the end of the series.
    nNoWork: int = 0
    nNoFail: int = 0
    # Superseded by a later pin in the same pullback -- `pinNewest`. This is
    # the one that turned out to dominate the funnel.
    nSuper: int = 0
    # Pullbacks that never offered enough qualifying candles for `pinLag` to
    # have one to pick. At lag 0 this is always 0; at lag 1 it is most of them,
    # and it is the honest cost of the rule.
    nLagShort: int = 0
    # The bias stopped being tradeable while the candidate was still unarmed.
    nBiasDrop: int = 0
    # Fills that came from a backup zone rather than the Focus line. Counted
    # apart so no number can imply the limit worked when it did not.
    nBackup: int = 0
    # THE SWING STOP HAD NO SWING TO READ, so the pullback extreme was used
    # instead. Only a source with no minor tier can do this -- `alt_structure`
    # publishes sTopY/sBtmY as None on every bar, deliberately, because faking
    # a minor tier would make the sources look comparable when they are not.
    #
    # IT IS COUNTED BECAUSE IT USED TO BE SILENT AND FATAL. With `stopSrc` at
    # the minor swing, every RSI-bias candidate hit `base is None` and was
    # discarded at arming: 0 setups on every symbol, no counter, no panel row,
    # and a chart option that selected to nothing.
    nStopFallback: int = 0
    # which Ending rule cancelled an armed setup
    nEndMinor: int = 0
    nEndSweep: int = 0
    nEndStale: int = 0
    nEndRetr: int = 0
    nEndAdx: int = 0
    nEndMixed: int = 0
    # HTF disagreement, when htfMult is on
    nHtf: int = 0
    # Still running when the data ended, split by kind. THE SPLIT IS THE POINT:
    # the Pine panel counted ghosts as live trades and read "28 / 58 · 1 open"
    # against 86 entered, which is 87. Keeping the two apart here makes the
    # identity nFilled == won + lost + nOpenReal testable, which is what would
    # have caught it.
    nOpenReal: int = 0
    nOpenGhost: int = 0
    trades: list = field(default_factory=list)
    # THE MOMENT A LIMIT ORDER WOULD GO ON. One entry per setup that armed:
    # (bar, symbol, short, entry, stop, target, code, state). This is the only
    # thing the live watcher alerts on, and indicators/undertow/tests/
    # test_watch_undertow.py asserts the bot's own copy of the machine
    # reproduces this list exactly.
    # EVERY QUALIFYING CANDLE, armed or not, as (bar, short, pbStart). The
    # armed list cannot answer "how many candidates did this pullback offer?"
    # because most never confirm -- and that question is what decides whether a
    # rule like `pinLag` bites on a majority or a rump. Counting it from armed
    # setups grouped by proximity got it wrong once already.
    # PER-BAR GATE STATE, only when run(trace=True). Nothing in the machine
    # could say WHY a bar was refused -- the funnel counters say how many died
    # at each stage and never which bar or which gate. Diagnosing "I took this
    # setup and the chart did not" needed that, and reconstructing it by
    # re-deriving the gates outside run() would be a second implementation to
    # keep in step.
    trace: list = field(default_factory=list)
    pins: list = field(default_factory=list)
    armed: list = field(default_factory=list)
    # THE MOMENT THE LIMIT ACTUALLY FILLED — you are in the trade. Separate
    # from `armed` because roughly half of armed setups never reach it, and
    # because the STOP CAN HAVE MOVED in between: it tracks the pullback while
    # the order rests, so the level alerted at arming is not necessarily the
    # level the trade is taken with.
    fills: list = field(default_factory=list)

    @property
    def real(self):
        return [t for t in self.trades if not t.ghost]

    @property
    def ghosts(self):
        return [t for t in self.trades if t.ghost]

    @property
    def netR(self) -> float:
        return sum(t.r for t in self.real)

    @property
    def gateCost(self) -> float:
        """What the cancelled setups would have made. Positive = the gate is
        throwing trades away; negative = it cancelled losers."""
        return sum(t.r for t in self.ghosts)

    def add(self, o: "Result") -> "Result":
        for k, v in vars(o).items():
            if isinstance(v, int) and k != "bars":
                setattr(self, k, getattr(self, k) + v)
        self.bars += o.bars
        self.trades += o.trades
        self.pins += o.pins
        self.armed += o.armed
        self.fills += o.fills
        return self


# ───────────────────────────────────────────────────────────── indicators ──


def _rma(values, length):
    """Wilder's smoothing, as ta.rma does it. Same code as riptide.engine.rma;
    duplicated rather than imported so the research tree cannot break the bot
    tree, which is the rule in indicators/README.md."""
    out = []
    acc = 0.0
    for i, v in enumerate(values):
        if i < length:
            acc += v
            out.append(acc / (i + 1))
        else:
            out.append((out[-1] * (length - 1) + v) / length)
    return out


def _tr(cs):
    out = []
    for i, c in enumerate(cs):
        if i == 0:
            out.append(c.h - c.l)
        else:
            pc = cs[i - 1].c
            out.append(max(c.h - c.l, abs(c.h - pc), abs(c.l - pc)))
    return out


def atr_series(cs, length=14):
    return _rma(_tr(cs), length)


def di_series(cs, diLen=14):
    """ta.dmi(diLen, _)[0] and [1] -- DI+ and DI-, the two halves of Wilder's
    directional movement, as a pair of per-bar lists.

    FACTORED OUT OF adx_series RATHER THAN COPIED. ADX is built from exactly
    these two. The bias source that read them directly is gone -- DI+/DI- was
    on the chart for part of one day -- but ADX still needs them and writing
    Wilder's smoothing twice would be two things to keep in step for no reason.
    """
    n = len(cs)
    plusDM, minusDM = [0.0] * n, [0.0] * n
    for i in range(1, n):
        up = cs[i].h - cs[i - 1].h
        dn = cs[i - 1].l - cs[i].l
        plusDM[i] = up if (up > dn and up > 0) else 0.0
        minusDM[i] = dn if (dn > up and dn > 0) else 0.0
    trur = _rma(_tr(cs), diLen)
    rp, rm = _rma(plusDM, diLen), _rma(minusDM, diLen)
    # `fixnan`, WHICH IS THE PART A FUDGE GETS WRONG. The reference divides by
    # `trur` and wraps it in fixnan, so a bar where the smoothed true range is
    # ZERO carries the PREVIOUS DI forward rather than producing a number. The
    # first version of this used `trur[i] or 1e-12`, which on such a bar gives
    # either an enormous DI or a 0/0 tie -- and a tie flips this bias short.
    #
    # It only bites when every true range in the window is zero, which is a
    # halted or completely untraded stretch. Carrying forward is also the right
    # answer for a BIAS on such a bar: nothing happened, so the direction
    # should not change.
    plus, minus = [], []
    for i in range(n):
        if trur[i]:
            plus.append(100.0 * rp[i] / trur[i])
            minus.append(100.0 * rm[i] / trur[i])
        else:
            plus.append(plus[-1] if plus else 0.0)
            minus.append(minus[-1] if minus else 0.0)
    return plus, minus


def adx_series(cs, diLen=14, adxLen=14):
    """ta.dmi(14, 14)[2]. Transcribed from the Pine reference implementation,
    including the `sum == 0 ? 1 : sum` guard, because that guard is the
    difference between ADX and a divide by zero on a flat bar."""
    plus, minus = di_series(cs, diLen)
    dx = []
    for pl, mi in zip(plus, minus):
        s = pl + mi
        dx.append(abs(pl - mi) / (s if s != 0 else 1))
    return [100.0 * v for v in _rma(dx, adxLen)]


# ─────────────────────────────────────────────────────── the bias sources ──
#
# FOUR ALTERNATIVES TO THE STRUCTURE ENGINE, each answering only one question:
# which way is the trend, on this bar. Everything downstream -- the pullback,
# the pin, the confirmations, the levels -- is untouched, so a study of these
# is a study of the DIRECTION and nothing else.
#
# Each returns a per-bar +1 / -1. None may look forward.


def _ema(vals, length):
    out, k = [], 2.0 / (length + 1.0)
    for i, v in enumerate(vals):
        out.append(v if i == 0 else out[-1] + k * (v - out[-1]))
    return out


def dir_ema(cs, p):
    """Fast EMA above slow EMA. The oldest trend rule there is."""
    cl = [c.c for c in cs]
    f, sl = _ema(cl, p.emaFast), _ema(cl, p.emaSlow)
    return [1 if a > b else -1 for a, b in zip(f, sl)]


def dir_supertrend(cs, p):
    """ta.supertrend(), transcribed including its band-carry rules.

    The carry is the whole algorithm: a band only moves in the direction that
    tightens it, unless the previous close broke through, which is what stops
    it flapping on every bar. Pine returns -1 for an uptrend; this returns +1,
    because every other source here does.
    """
    atr = atr_series(cs, p.stAtrLen)
    n = len(cs)
    out = [1] * n
    lo_b = hi_b = None
    st = None
    d = 1
    for i, c in enumerate(cs):
        hl2 = (c.h + c.l) / 2.0
        up = hl2 + p.stMult * atr[i]
        dn = hl2 - p.stMult * atr[i]
        pl, pu = (lo_b, hi_b) if lo_b is not None else (dn, up)
        pc = cs[i - 1].c if i else c.c
        dn = dn if (dn > pl or pc < pl) else pl
        up = up if (up < pu or pc > pu) else pu
        if i == 0:
            d = 1
        elif st is not None and st == pu:
            d = -1 if c.c > up else 1
        else:
            d = 1 if c.c < dn else -1
        st = dn if d == -1 else up
        lo_b, hi_b = dn, up
        out[i] = 1 if d == -1 else -1      # Pine's -1 is an uptrend
    return out


def dir_slope(cs, p):
    """The slope of a least-squares fit, in units per unit, direction held
    below a threshold so a flat patch does not manufacture a trend in whichever
    way the noise happened to lean.

    TWO UNITS, and the difference is the whole reason this has a switch.

      "bars"   window `slopeLen` BARS, threshold in ATR per BAR. ATR per bar
               rather than price per bar is what makes one number mean the
               same thing on BTC at 90,000 and on a token at 0.02 -- but it
               does NOT make it mean the same thing on 15m as on 1h, because
               both the window and the unit are per-bar. This is the shipped
               setting and the one measured in UNDERTOW_BIAS_SOURCE.md.
      "hours"  window `slopeHours` of trading, threshold in DAY-RANGES PER
               HOUR. Nothing per-bar survives, so the rule is the same rule on
               every chart.
    """
    n = len(cs)
    hours = p.slopeUnit == SL_HOURS
    if hours:
        # Both halves of the rule restated in time. `unit` is the last 24
        # hours' high-to-low, a price that does not care how the day is
        # sliced, and the fit's rise is converted to per HOUR before the
        # comparison -- so 15m and 1h ask the same question.
        L = max(2, bars_per(cs, p.slopeHours))
        unit = range_basis(cs, bars_per(cs, 24.0))
        per = float(bars_per(cs, 1.0))
        thr = p.slopeMinPerHr
    else:
        L = max(2, p.slopeLen)
        unit = atr_series(cs, 14)
        per = 1.0
        thr = p.slopeMin
    cl = [c.c for c in cs]
    # sum of (x - xbar)^2 for x = 0..L-1, constant, so only the cross term moves
    xb = (L - 1) / 2.0
    sxx = sum((x - xb) ** 2 for x in range(L))
    out, d = [1] * n, 1
    run = 0.0
    for i in range(n):
        if i + 1 >= L:
            w = cl[i + 1 - L:i + 1]
            yb = sum(w) / L
            sxy = sum((x - xb) * (y - yb) for x, y in enumerate(w))
            run = (sxy / sxx) * per / (unit[i] or 1e-12)
        if abs(run) >= thr:
            d = 1 if run > 0 else -1
        out[i] = d
    return out


def dir_mtf_ema(cs, p):
    """Two timeframes, EMA `mtfFast`/`mtfSlow` on each, aligned or stand aside.

    Returns (dirs, mixed): the direction to take, and a per-bar flag saying the
    two timeframes disagree and NOTHING should be taken. Every other source
    here is always long or short; this is the first that abstains.

    NO LOOK-AHEAD, and it is the one place this differs from the Pine it came
    from. `request.security(sym, "30", ta.ema(close, 20))` returns the value of
    the FORMING higher-timeframe bar on the live bar, so the table flips
    intrabar and the historical chart is cleaner than live trading would be.
    Here the slower EMA is read from `aggregate`, whose verdict is written onto
    base bars only from the bar AFTER the one that closed it -- the same rule
    `htf_dir` follows. A study of the repainting version would measure the
    repaint.
    """
    n = len(cs)
    fast = _ema([c.c for c in cs], p.mtfFast)
    slow = _ema([c.c for c in cs], p.mtfSlow)
    base = [1 if fast[i] > slow[i] else -1 for i in range(n)]

    mult = max(1, p.mtfMult)
    hb, closeX = aggregate(cs, mult) if mult > 1 else ([], [])
    if not hb:
        # Nothing to aggregate: the pair degenerates to one timeframe, which is
        # a real answer and not an error. Nothing is mixed, so nothing abstains.
        return base, [False] * n
    hf = _ema([c.c for c in hb], p.mtfFast)
    hs = _ema([c.c for c in hb], p.mtfSlow)
    hi = [1 if hf[j] > hs[j] else -1 for j in range(len(hb))]

    slow_d = [0] * n
    for j, ci in enumerate(closeX):
        lo = ci + 1
        end = closeX[j + 1] if j + 1 < len(closeX) else n - 1
        for i in range(lo, min(end, n - 1) + 1):
            slow_d[i] = hi[j]
    dirs, mixed = [], []
    for i in range(n):
        agree = slow_d[i] != 0 and slow_d[i] == base[i]
        dirs.append(base[i])
        mixed.append(not agree)
    return dirs, mixed


def dir_donchian(cs, p):
    """Where price sits in the last `donLen` bars' range: above the midpoint is
    an uptrend. No pivots, no state, nothing to flap."""
    hh = _roll_max([c.h for c in cs], max(2, p.donLen))
    ll = _roll_min([c.l for c in cs], max(2, p.donLen))
    return [1 if c.c >= (a + b) / 2.0 else -1 for c, a, b in zip(cs, hh, ll)]


def _roll_max(v, L):
    from collections import deque
    out, dq = [0.0] * len(v), deque()
    for i, x in enumerate(v):
        while dq and v[dq[-1]] <= x:
            dq.pop()
        dq.append(i)
        while dq[0] <= i - L:
            dq.popleft()
        out[i] = v[dq[0]]
    return out


def _roll_min(v, L):
    from collections import deque
    out, dq = [0.0] * len(v), deque()
    for i, x in enumerate(v):
        while dq and v[dq[-1]] >= x:
            dq.pop()
        dq.append(i)
        while dq[0] <= i - L:
            dq.popleft()
        out[i] = v[dq[0]]
    return out


def _rsi(vals, length):
    """Wilder's RSI over an arbitrary series, not just closes.

    riptide.engine.rsi_series is close-only and this needs ohlc4 and a
    Heikin-Ashi projection, so the arithmetic is here. Same duplication rule
    and same reason as `_rma` above.
    """
    up, dn = [0.0], [0.0]
    for i in range(1, len(vals)):
        d = vals[i] - vals[i - 1]
        up.append(max(d, 0.0))
        dn.append(max(-d, 0.0))
    au, ad = _rma(up, length), _rma(dn, length)
    return [100.0 if d == 0 and u > 0 else 50.0 if d == 0
            else 100.0 - 100.0 / (1.0 + u / d) for u, d in zip(au, ad)]


def dir_rsi(cs, p):
    """Duyck's "RSI direction bias - JD", v5, transcribed.

        if ta.crossover(rsi_val, top_level)    bias := 1
        if ta.crossunder(rsi_val, bottom_level) bias := -1

    LATCHED, WITH A DEAD BAND, and that is what makes it different from every
    other source in this file. Between 40 and 60 it holds; nothing else here
    abstains from having a new opinion on every bar. Seeded +1, as the original
    does with `var int bias = 1`.

    THE SOURCE IS ohlc4 AND IS NOT AN INPUT. The reference offers a source
    selector; SETTINGS.md's rule is that an input earns its place only if the
    definition needs it, a study showed the choice matters, or it is display,
    and a price-source dropdown on an unmeasured bias fails all three.

    THE FUTURE-SMOOTHED VARIANT hard-codes 14 in the original -- `ta.rsi(
    next_ha_open, 14)`, not `len` -- and that is reproduced rather than tidied,
    because tidying it would make this a different indicator from the one that
    was handed over. `request.security(heikinashi, timeframe.period, ...)` is
    just Heikin-Ashi on the chart's own timeframe, so it is computed inline
    here with no lookahead.
    """
    if p.rsiHA:
        hc = [(c.o + c.h + c.l + c.c) / 4.0 for c in cs]
        ho = []
        for i, c in enumerate(cs):
            ho.append((c.o + c.c) / 2.0 if i == 0
                      else (ho[i - 1] + hc[i - 1]) / 2.0)
            
        vals = [(a + b) / 2.0 for a, b in zip(ho, hc)]
        r = _rsi(vals, 14)
    else:
        r = _rsi([(c.o + c.h + c.l + c.c) / 4.0 for c in cs], p.rsiLen)
    out, d = [], 1
    for i in range(len(cs)):
        if i:
            if r[i - 1] <= p.rsiTop < r[i]:
                d = 1
            elif r[i - 1] >= p.rsiBot > r[i]:
                d = -1
        out.append(d)
    return out


DIRS = {BS_EMA: dir_ema, BS_RSI: dir_rsi, BS_ST: dir_supertrend, BS_SLOPE: dir_slope,
        BS_DON: dir_donchian, BS_MTF: dir_mtf_ema}


def alt_structure(cs, p):
    """A non-structure direction, dressed as the state dict everything else
    reads. The DOWNSTREAM IS UNCHANGED, which is the point: a study of the
    sources is then a study of direction and nothing else.

    What each key becomes, and why:

      choch      the bar the direction flipped. There is no CHoCH here, but a
                 flip is the same event for every purpose downstream.
      bosUp/Dn   fired ONCE, `matureBars` after a flip. Without a break of
                 structure to count, "running" has to mean "the direction has
                 held a while" or every setup would read immature forever.
      msMax/Min  the running extremes SINCE THE FLIP, which is exactly what the
                 structure engine's are since its CHoCH. The pullback and the
                 retrace rule both read these, so they must mean the same
                 thing or the arms are not comparable.
      sweeps, minor structure   absent. They are structure concepts and the
                 Ending rules that use them are simply off for these sources --
                 stated rather than faked, because a fabricated minor CHoCH
                 would make the comparison look fair while not being.
    """
    d = DIRS[p.biasSrc](cs, p)
    # A source may return a bare direction list, or (dirs, mixed) when it has a
    # stand-aside state. Only BS_MTF has one so far.
    d, mixed = d if isinstance(d, tuple) else (d, [False] * len(cs))
    n = len(cs)
    out = dict(os=[], choch=[], bosUp=[], bosDn=[], sweepUp=[], sweepDn=[],
               msMax=[], msMin=[], msMaxX=[], msMinX=[], sOs=[],
               minorChoch=[], sTopY=[], sBtmY=[])
    mx = mn = None
    mxX = mnX = 0
    since = 0
    for i in range(n):
        c = cs[i]
        flip = i > 0 and d[i] != d[i - 1]
        if flip or mx is None:
            mx, mn, mxX, mnX, since = c.h, c.l, i, i, 0
        else:
            since += 1
            if c.h > mx:
                mx, mxX = c.h, i
            if c.l < mn:
                mn, mnX = c.l, i
        mature = since == p.matureBars
        out["os"].append(1 if d[i] > 0 else 0)
        out["choch"].append(flip)
        out["bosUp"].append(mature and d[i] > 0)
        out["bosDn"].append(mature and d[i] < 0)
        out["sweepUp"].append(False)
        out["sweepDn"].append(False)
        out["sOs"].append(1 if d[i] > 0 else 0)
        out["minorChoch"].append(False)
        out["sTopY"].append(None)
        out["sBtmY"].append(None)
        out["msMax"].append(mx)
        out["msMin"].append(mn)
        out["msMaxX"].append(mxX)
        out["msMinX"].append(mnX)
    out["mixed"] = mixed
    return out, atr_series(cs, 14)


# ──────────────────────────────────────────────────── the structure engine ──


def _swings(cs, p: P, major: bool, atr):
    # STRICT, and deliberately so. This used to fall through to the price-move
    # branch for anything it did not recognise, which meant a typo -- or an old
    # study still passing the pre-rename "bar" -- ran a DIFFERENT swing
    # definition than it asked for and printed a number that looked fine.
    if p.swingSrc == SW_BAR:
        return bar_swings(cs, p.msLen if major else p.msShortLen)
    if p.swingSrc not in (SW_RANGE, SW_ATR):
        raise ValueError(f"unknown swingSrc {p.swingSrc!r}; expected one of "
                         f"{SW_BAR!r}, {SW_RANGE!r}, {SW_ATR!r}")
    k = p.swingK if major else p.swingKMinor
    scale = (atr if p.swingSrc == SW_ATR
             else range_basis(cs, bars_per(cs, p.swingHours)))
    return price_swings(cs, k, scale)


def structure(cs, p: P):
    """Sections 3 and 4 of the Pine, one pass, per-bar state out.

    When `biasSrc` is not the structure engine this hands straight over to
    `alt_structure`, which produces the same keys from a different direction.
    Everything downstream reads this dict and nothing downstream knows or
    cares which source filled it.

    Section 3 is the copied v2 engine and the statements are unchanged from
    riptide_ms/port/ms_struct.py. Section 4 is the same crossing machine run on
    the SHORT swings and is Undertow's own.
    """
    # SMC has REAL breaks of structure, so it does not go through
    # alt_structure -- that helper fabricates a BOS `matureBars` after a flip
    # for sources that have none, and faking one here would throw away the
    # thing that was asked for.
    if p.biasSrc == BS_SMC:
        return smc.state(cs, p), atr_series(cs, 14)
    if p.biasSrc != BS_STRUCT:
        return alt_structure(cs, p)
    n = len(cs)
    # THE HYBRID. This engine supplies the EXTERNAL character -- direction,
    # CHoCH, BOS and the inducement that gates the BOS -- and LuxAlgo's
    # internal pass supplies the minor tier that `endMinor` and the
    # minor-swing stop read. Computed here so the loop below can take it
    # per bar; see the comment where sOs is filled.
    # WITH THE SWING PASS AS ITS REFERENCE, exactly as smc.state builds it.
    # `ref` is what stops an internal break that sits on a swing level being
    # counted as a second event, and dropping it changed `sOs` on 351 bars of
    # a 4,000-bar walk -- enough to arm a setup the other copy did not. The
    # reference is LuxAlgo's own swing pass, not this engine's major tier:
    # the internal pass is half of THAT pair and has to be built the way that
    # pair builds it.
    inner = smc.structure(cs, p.smcInternalLen,
                          ref=smc.structure(cs, p.smcSwingLen))
    atr = atr_series(cs, 14)
    msTop, msTopX, msBtm, msBtmX = _swings(cs, p, True, atr)
    msSTop, msSTopX, msSBtm, msSBtmX = _swings(cs, p, False, atr)

    msOs = 0
    msTopCrossed = False
    msBtmCrossed = False
    msMax = msMin = msMaxX = msMinX = None
    msTopY = msBtmY = None
    msSTopCrossed = False
    msSBtmCrossed = False
    msSTopY = msSBtmY = None
    # section 4
    msSOs = 0
    msSTopXd = False
    msSBtmXd = False
    msSTopLvl = msSBtmLvl = None

    out = dict(os=[], choch=[], bosUp=[], bosDn=[], sweepUp=[], sweepDn=[],
               msMax=[], msMin=[], msMaxX=[], msMinX=[], sOs=[],
               minorChoch=[], sTopY=[], sBtmY=[])

    def gt(a, b):
        return a is not None and b is not None and a > b

    def lt(a, b):
        return a is not None and b is not None and a < b

    for i in range(n):
        c = cs[i]
        msOsPrev = msOs
        msMaxPrev, msMinPrev = msMax, msMin

        if msTop[i] is not None:
            msTopY = msTop[i]
            msTopCrossed = False
        if msBtm[i] is not None:
            msBtmY = msBtm[i]
            msBtmCrossed = False

        if gt(c.c, msTopY) and not msTopCrossed:
            msOs = 1
            msTopCrossed = True
        if lt(c.c, msBtmY) and not msBtmCrossed:
            msOs = 0
            msBtmCrossed = True

        msChoch = msOs != msOsPrev
        if msChoch:
            msMax, msMin = c.h, c.l
            msMaxX = msMinX = i
            msSTopCrossed = False
            msSBtmCrossed = False

        if msSTop[i] is not None:
            msSTopY = msSTop[i]
        if msSBtm[i] is not None:
            msSBtmY = msSBtm[i]

        msIdmUp = (lt(c.l, msSBtmY) and not msSBtmCrossed and msOs == 1
                   and msSBtmY != msBtmY)
        if msIdmUp:
            msSBtmCrossed = True
        msBosUp = (gt(c.c, msMax) and (not p.msBosNeedsIdm or msSBtmCrossed)
                   and msOs == 1)
        if msBosUp:
            msSBtmCrossed = False

        msIdmDn = (gt(c.h, msSTopY) and not msSTopCrossed and msOs == 0
                   and msSTopY != msTopY)
        if msIdmDn:
            msSTopCrossed = True
        msBosDn = (lt(c.c, msMin) and (not p.msBosNeedsIdm or msSTopCrossed)
                   and msOs == 0)
        if msBosDn:
            msSTopCrossed = False

        msSweepUp = (gt(c.h, msMax) and lt(c.c, msMax) and msOs == 1
                     and msMaxX is not None and i - msMaxX > 1)
        msSweepDn = (lt(c.l, msMin) and gt(c.c, msMin) and msOs == 0
                     and msMinX is not None and i - msMinX > 1)

        # ── section 4, the minor crossing machine ───────────────────────────
        msSOsPrev = msSOs
        if msSTop[i] is not None:
            msSTopLvl = msSTop[i]
            msSTopXd = False
        if msSBtm[i] is not None:
            msSBtmLvl = msSBtm[i]
            msSBtmXd = False
        if gt(c.c, msSTopLvl) and not msSTopXd:
            msSOs = 1
            msSTopXd = True
        if lt(c.c, msSBtmLvl) and not msSBtmXd:
            msSOs = 0
            msSBtmXd = True
        msMinorChoch = msSOs != msSOsPrev

        out["os"].append(msOs)
        out["choch"].append(msChoch)
        out["bosUp"].append(msBosUp)
        out["bosDn"].append(msBosDn)
        out["sweepUp"].append(msSweepUp)
        out["sweepDn"].append(msSweepDn)
        # THE MINOR TIER COMES FROM LuxAlgo'S INTERNAL PASS, NOT FROM THIS
        # ENGINE'S OWN, and that hybrid is deliberate. This engine's short
        # swings exist to supply the INDUCEMENT -- `msSBtmY` above, which is
        # the only thing v2 ever used them for. What `endMinor` and the
        # minor-swing stop read is LuxAlgo's internal structure at
        # `smcInternalLen`, which is the better of the two at saying where a
        # pullback is turning.
        #
        # External character from one engine, internal from the other. The
        # Pine's mux does exactly the same thing -- see the comment on `bSOs`.
        out["sOs"].append(1 if (inner["dir"][i] or 1) > 0 else 0)
        out["minorChoch"].append(inner["choch"][i])
        out["sTopY"].append(inner["hiLvl"][i])
        out["sBtmY"].append(inner["loLvl"][i])

        # Trailing extremes, AFTER the tests above read them.
        msMax = c.h if msMax is None else max(c.h, msMax)
        msMin = c.l if msMin is None else min(c.l, msMin)
        if msMaxPrev is None or msMax > msMaxPrev:
            msMaxX = i
        if msMinPrev is None or msMin < msMinPrev:
            msMinX = i
        out["msMax"].append(msMax)
        out["msMin"].append(msMin)
        out["msMaxX"].append(msMaxX)
        out["msMinX"].append(msMinX)

    return out, atr


# ────────────────────────────────────────────────────────────── HTF bias ──


@dataclass
class _Bar:
    t: int
    o: float
    h: float
    l: float
    c: float
    v: float = 0.0


def aggregate(cs, mult: int):
    """`mult` base bars into one, and the BASE index at which each HTF bar is
    finished. Returns (htf_bars, close_index) with close_index[j] the base bar
    whose close completes htf bar j.

    ALIGNED ON THE TIMESTAMP, not on a running count, so the buckets do not
    shift when the feed has a gap — which every broker feed with a session
    break has, and which is a large part of why XAUUSD and XAUUSDT.P disagreed.
    """
    if mult <= 1 or not cs:
        return [], []
    gaps = [b.t - a.t for a, b in zip(cs, cs[1:]) if b.t > a.t]
    step = min(gaps) if gaps else 0
    if step <= 0:
        return [], []
    span = step * mult
    out, closeX = [], []
    cur = None
    for i, c in enumerate(cs):
        b = (c.t // span) * span
        if cur is None or b != cur.t:
            if cur is not None:
                out.append(cur)
                closeX.append(i - 1)
            cur = _Bar(b, c.o, c.h, c.l, c.c, c.v)
        else:
            cur.h = max(cur.h, c.h)
            cur.l = min(cur.l, c.l)
            cur.c = c.c
            cur.v += c.v
    if cur is not None:
        out.append(cur)
        closeX.append(len(cs) - 1)
    return out, closeX


def htf_mult(cs, p: P) -> int:
    """BASE bars per HTF bar, or 0 when the gate is off.

    The single place that turns `htfUnit`/`htfMult`/`htfHours` into one number,
    so the three call sites cannot drift apart. Under "bars" it is exactly the
    old `p.htfMult if p.htfMult > 1 else 0`, which is what keeps every study
    that predates `htfUnit` running unchanged.
    """
    if p.htfUnit == HTF_HOURS:
        if p.htfHours <= 0:
            return 0
        m = bars_per(cs, p.htfHours)
        return m if m > 1 else 0
    return p.htfMult if p.htfMult > 1 else 0


def htf_dir(cs, p: P, mult: int = 0):
    """Per BASE bar, the HTF bias direction (+1/-1) and whether it is tradeable.

    NO LOOK-AHEAD, and this is the only thing that makes the feature honest: an
    HTF bar's verdict is written onto base bars only from the bar AFTER the one
    that closed it. On the base bars inside a forming HTF bar, the answer is the
    previous HTF bar's -- exactly what a live scanner would have.
    """
    n = len(cs)
    hb, closeX = aggregate(cs, mult or htf_mult(cs, p))
    if not hb:
        return [0] * n, [False] * n
    # Same rules, one timeframe up. msLen stays in BARS on the aggregate, which
    # is the point of running it there at all.
    st, _ = structure(hb, p)
    dirs, ok = bias(hb, st, p)
    outD, outK = [0] * n, [False] * n
    for j, ci in enumerate(closeX):
        lo = ci + 1
        hi = closeX[j + 1] if j + 1 < len(closeX) else n - 1
        for i in range(lo, min(hi, n - 1) + 1):
            outD[i] = dirs[j]
            outK[i] = ok[j]
    return outD, outK


# ───────────────────────────────────────────────────────────────── bias ──


def bias(cs, st, p: P):
    """Section 5. Returns (biasDir, tradeable) per bar, plus latches the reason
    in `st["endWhy"]` so a study can attribute a cancellation."""
    n = len(cs)
    adx = adx_series(cs) if p.adxMin > 0 else [0.0] * n
    mixedSeries = st.get("mixed") or [False] * n
    biasSeen = False
    bosN = 0
    ending = False
    endWhy = "-"
    dirs, ok, whys, states = [], [], [], []
    for i in range(n):
        if st["choch"][i]:
            biasSeen = True
            bosN = 0
            ending = False
        biasDir = 1 if st["os"][i] == 1 else -1
        bosNow = st["bosUp"][i] if biasDir > 0 else st["bosDn"][i]
        if bosNow:
            bosN += 1
            ending = False

        minorAgainst = (st["sOs"][i] == 0) if biasDir > 0 else (st["sOs"][i] == 1)
        endA = (False if p.endMinor == E_OFF else
                minorAgainst if p.endMinor == E_OPPOSED else
                (st["minorChoch"][i] and minorAgainst))
        endB = p.endSweep and (st["sweepUp"][i] if biasDir > 0
                               else st["sweepDn"][i])
        lastExtX = st["msMaxX"][i] if biasDir > 0 else st["msMinX"][i]
        endC = (p.endStale and lastExtX is not None
                and i - lastExtX >= p.staleBars)
        msMax, msMin = st["msMax"][i], st["msMin"][i]
        msLeg = (msMax - msMin) if (msMax is not None and msMin is not None) else 0.0
        retraced = 0.0
        if msLeg > 0:
            retraced = ((msMax - cs[i].c) / msLeg if biasDir > 0
                        else (cs[i].c - msMin) / msLeg)
        endD = p.retraceMax > 0 and retraced >= p.retraceMax / 100.0
        endE = p.adxMin > 0 and adx[i] < p.adxMin
        # THE STAND-ASIDE STATE. Only BS_MTF sets it: the two timeframes
        # disagree, so there is no direction to trade. Unlike the five rules
        # above it is not latched -- it goes away the moment they agree again,
        # which is what "MIXED" means on the chart it came from. Latching it
        # would turn one bar of disagreement into a permanent cancellation.
        endF = mixedSeries[i]

        # THE LATCHING SET, and endD leaves it when `retraceLatch` is off.
        latching = endA or endB or endC or endE
        if biasSeen and (latching or (endD and p.retraceLatch)):
            if not ending:
                endWhy = ("minor" if endA else "sweep" if endB else
                          "stale" if endC else "retrace" if endD else "adx")
            ending = True
        # NON-LATCHING RETRACE. The bias is untradeable WHILE the leg is given
        # back past the threshold and recovers the moment it is not, exactly
        # as `mixed` does below. It cannot clear a latch set by one of the
        # event rules, which is why `ending` itself is untouched here.
        softEnd = endD and not p.retraceLatch

        dirs.append(biasDir)
        ok.append(biasSeen and not ending and not endF and not softEnd)
        whys.append("retrace" if (softEnd and not ending)
                    else "mixed" if (endF and not ending) else endWhy)
        states.append("none" if not biasSeen else "ending" if ending
                      else "ending" if softEnd
                      else "mixed" if endF
                      else "immature" if bosN == 0 else "running")
    st["endWhy"] = whys
    st["biasState"] = states
    return dirs, ok


# ───────────────────────────────────────────────────── the setup machine ──


def _beyond_up(c, lvl, mode):
    if mode == T_TOUCH:
        return c.c >= lvl
    if mode == T_BODY:
        return min(c.o, c.c) > lvl
    return c.c > lvl


def _beyond_dn(c, lvl, mode):
    if mode == T_TOUCH:
        return c.c <= lvl
    if mode == T_BODY:
        return max(c.o, c.c) < lvl
    return c.c < lvl


def bk_zone(cs, i, short, focus, lo, look, want_ob, want_fvg):
    """The Pine's `bkZone()`. The nearest order block or fair-value gap edge
    between `lo` and `focus`, or None.

    THE NEAR EDGE, ON FIRST TOUCH. A short retracing upward touches the bottom
    of a zone above it, so that is the fill -- and it is the worse of the two
    edges for a short, which makes it the conservative reading. The better
    price needs a deeper retrace that may never come, and assuming it would be
    assuming a fill that did not happen.

    AN ORDER BLOCK NEEDS A CLOSE BEYOND IT, not a wick through. That is the fix
    for the loose OB detection this project already has: a wick through an
    up-candle is noise, a close beyond it is a decision.
    """
    best, why = None, ""
    first = max(1, i - look)

    def better(e):
        return best is None or (e < best if short else e > best)

    def in_range(e):
        return (lo < e < focus) if short else (focus < e < lo)

    for b in range(i - 1, first - 1, -1):
        c = cs[b]
        if want_ob:
            is_opp = c.c > c.o if short else c.c < c.o
            if is_opp:
                disp = any((cs[j].c < c.l) if short else (cs[j].c > c.h)
                           for j in range(b + 1, i + 1))
                if disp:
                    edge = c.l if short else c.h
                    if in_range(edge) and better(edge):
                        best, why = edge, "OB"
        if want_fvg and 1 <= b < i:
            # PINE INDICES RUN BACKWARDS AND THIS IS WHERE THAT BITES. In the
            # Pine `high[b - 1]` is the bar AFTER b; here `cs[b - 1]` is the
            # bar BEFORE it. Getting that the wrong way round produced a
            # detector that found zero fair-value gaps while reporting the
            # feature as on, which is the quietest possible failure -- the
            # backup still worked, on order blocks alone, and nothing said so.
            #   bearish gap (a short):  high[newer] < low[older]
            #   bullish gap (a long):   low[newer]  > high[older]
            newer, older = cs[b + 1], cs[b - 1]
            edge = newer.h if short else newer.l
            far = older.l if short else older.h
            if (edge < far) if short else (edge > far):
                if in_range(edge) and better(edge):
                    best, why = edge, "FVG"
    return best, why


@dataclass(eq=False)
class _Cand:
    bar: int
    hi: float
    lo: float
    focus: float
    workHi: bool
    short: bool
    pbExt: float
    state: str
    code: str
    workOk: bool = False
    failOk: bool = False
    workBar: int = -1
    # WHICH CONFIRMATION LANDED FIRST. 1 = Working then Failure, 2 = the other
    # way. The Pine has carried this since v1 (`Cand.order`) and the port did
    # not, which made it the one field on the chart with no counterpart here.
    # It gates nothing; it is what the alert says happened.
    order: int = 0
    armed: bool = False
    armBar: int = -1
    stop: float = 0.0
    target: float = 0.0
    ghost: bool = False
    bkPx: float = 0.0
    bkWhy: str = ""
    ran: bool = False
    late: bool = False
    # HOW MANY QUALIFYING CANDLES CAME BEFORE THIS ONE in the same pullback,
    # same direction. `pinLag` reads it: a candidate may arm only once exactly
    # `pinLag` newer candles exist, so lag 0 is "nothing came after me" (what
    # pinNewest already enforces by deletion) and lag 1 is "exactly one did".
    pinIdx: int = 0
    # Counted ONCE into nLagShort. A candidate can survive past the reset that
    # ends its own pullback, and counting it at every later reset turned an
    # honest diagnostic into a number four times too big.
    lagCounted: bool = False
    # WHICH PULLBACK THIS CANDLE BELONGS TO, stamped at creation. Recorded so
    # two pin rules can be compared PAIRED on the same pullback: comparing
    # whole populations that share 82% of their trades measures noise. It is
    # taken at creation and not at the arm because a candidate can outlive the
    # pullback that produced it.
    pbStart: int = -1


def run(cs, p: P = P(), symbol: str = "", trace: bool = False) -> Result:
    """Sections 6 and 7, and the scoring the Pine's panel does.

    One pass over the bars. The loop below is the Pine's loop in the Pine's
    order, including the two orderings that were found the hard way on real
    charts and are load-bearing:

      * `target reached before the fill` is tested BEFORE the fill, because the
        bar that comes back to the entry is often the same bar returning FROM
        the target, and scoring that as a win is how the chart printed a clean
        2R over a trade that collapsed.
      * the stop is tested BEFORE the touch, so a bar spanning both counts as
        the loss.
    """
    res = Result(symbol=symbol, bars=len(cs))
    if len(cs) < 60:
        return res
    st, atr = structure(cs, p)
    dirs, tradeable = bias(cs, st, p)
    hM = htf_mult(cs, p)
    hD, hK = (htf_dir(cs, p, hM) if hM
              else ([0] * len(cs), [True] * len(cs)))

    cands: list[_Cand] = []
    live: list[Trade] = []
    pbExt = None
    pbExtX = None
    # Qualifying candles so far in the CURRENT pullback, per direction.
    pinSeen: dict = {}
    pbStartX = None
    # The per-leg running extreme, for PIN_LEG. See the constant's note.
    legMax = legMin = None
    legMaxX = legMinX = 0

    for i, c in enumerate(cs):
        biasDir = dirs[i]
        atrBuf = p.stopBuf * atr[i]

        # ── the pullback, section 6 ─────────────────────────────────────────
        prevDir = dirs[i - 1] if i else biasDir
        prevMaxX = st["msMaxX"][i - 1] if i else st["msMaxX"][i]
        prevMinX = st["msMinX"][i - 1] if i else st["msMinX"][i]
        pbReset = (biasDir != prevDir
                   or (biasDir < 0 and st["msMinX"][i] != prevMinX)
                   or (biasDir > 0 and st["msMaxX"][i] != prevMaxX))
        if pbReset or pbExt is None:
            pbExt = c.h if biasDir < 0 else c.l
            pbExtX = i
            pbStartX = i
            # A NEW PULLBACK, so the qualifying candles start counting again.
            # Anything still waiting on a newer candle that will now never
            # come is the cost of `pinLag`, counted rather than dropped in
            # silence.
            if p.pinLag:
                for x in cands:
                    if (not x.armed and not x.ghost and not x.lagCounted
                            and pinSeen.get(x.short, 0) - x.pinIdx - 1
                            < p.pinLag):
                        x.lagCounted = True
                        res.nLagShort += 1
            pinSeen = {}
        elif biasDir < 0 and c.h >= pbExt:
            pbExt, pbExtX = c.h, i
        elif biasDir > 0 and c.l <= pbExt:
            pbExt, pbExtX = c.l, i

        # ── every candidate, oldest last so removal is safe ─────────────────
        armWon: set = set()
        for cd in list(cands):
            gone = False
            filled = False
            if not tradeable[i] and not cd.ghost:
                if not cd.armed:
                    # THE BIAS TURNED UNDER AN UNARMED CANDIDATE. Counted
                    # separately from nMissBias, which is the same event to an
                    # ARMED setup and already has a panel row -- this one had
                    # none, and between it and nSuper they are three quarters
                    # of the drop from "setups found" to "triggered".
                    res.nBiasDrop += 1
                if cd.armed:
                    res.nMissBias += 1
                    w = st["endWhy"][i]
                    if w == "minor":
                        res.nEndMinor += 1
                    elif w == "sweep":
                        res.nEndSweep += 1
                    elif w == "stale":
                        res.nEndStale += 1
                    elif w == "retrace":
                        res.nEndRetr += 1
                    elif w == "adx":
                        res.nEndAdx += 1
                    elif w == "mixed":
                        res.nEndMixed += 1
                    cd.ghost = True
                else:
                    gone = True

            if not gone and not cd.armed:
                if cd.short and c.h > cd.pbExt:
                    cd.pbExt = c.h
                if not cd.short and c.l < cd.pbExt:
                    cd.pbExt = c.l
                wHit = (_beyond_up(c, cd.hi, p.workTest) if cd.workHi
                        else _beyond_dn(c, cd.lo, p.workTest))
                fHit = (_beyond_dn(c, cd.lo, p.failTest) if cd.workHi
                        else _beyond_up(c, cd.hi, p.failTest))
                if wHit and not cd.workOk:
                    cd.workOk = True
                    cd.workBar = i
                    cd.order = cd.order or 1
                if fHit and not cd.failOk:
                    cd.failOk = True
                    cd.order = cd.order or 2
                # UNDER C_WF the arming event is the FAILURE break, and only
                # one that lands STRICTLY AFTER a working break. Strictly,
                # because a bar that spans both lines gives no intrabar order
                # -- the same reason a bar spanning entry and stop counts as
                # the loss. That bar does not arm; a later F does, which is
                # what makes F->W->F work.
                ready = (cd.workOk and cd.failOk if p.confirmOrder == C_EITHER
                         else fHit and cd.workBar >= 0 and i > cd.workBar)
                # THE LAG GATE. A candidate may arm only once EXACTLY `pinLag`
                # newer qualifying candles exist in its pullback. At 0 that is
                # "nothing came after me", which is what pinNewest already
                # enforces by deleting the losers; at 1 it is "exactly one
                # did", which is the chart owner's n-1.
                #
                # It is checked HERE, at the arm, rather than at the pin,
                # because how many candles came after is not knowable when the
                # candle forms. Deciding it at arm time is the only causal
                # reading and is what a person watching the chart is doing.
                if ready and p.pinLag:
                    newer = pinSeen.get(cd.short, 0) - cd.pinIdx - 1
                    ready = newer == p.pinLag
                if ready:
                    sw = st["sTopY"][i] if cd.short else st["sBtmY"][i]
                    base = ((cd.hi if cd.short else cd.lo) if p.stopSrc == S_PIN
                            else cd.pbExt if p.stopSrc == S_PULL
                            else sw)
                    # NO MINOR TIER, SO NO MINOR SWING. Fall back to the
                    # pullback extreme rather than discard the setup. The
                    # alternative is what shipped: `base is None` on every bar
                    # under the RSI source, every candidate dropped as `gone`,
                    # and the whole source producing 0 setups in silence.
                    #
                    # Only the SWING source can land here -- S_PIN and S_PULL
                    # read the candidate, not the structure -- so this cannot
                    # change a configuration that currently works.
                    if base is None and p.stopSrc == S_SWING:
                        base = cd.pbExt
                        if base is not None:
                            res.nStopFallback += 1
                    if base is None:
                        gone = True
                    else:
                        stp = base + atrBuf if cd.short else base - atrBuf
                        risk = abs(stp - cd.focus)
                        sane = risk > 0 and (stp > cd.focus if cd.short
                                             else stp < cd.focus)
                        if sane:
                            cd.armed = True
                            cd.armBar = i
                            cd.stop = stp
                            cd.target = (cd.focus - p.rr * risk if cd.short
                                         else cd.focus + p.rr * risk)
                            res.nArmed += 1
                            res.armed.append(dict(
                                bar=i, symbol=symbol, short=cd.short,
                                entry=cd.focus, stop=cd.stop,
                                target=cd.target, code=cd.code,
                                state=cd.state, pin=cd.bar, order=cd.order,
                                pbStart=cd.pbStart, pinIdx=cd.pinIdx))
                            # FIRST TO ARM WINS. Every other candidate in the
                            # same direction that has NOT armed is dropped --
                            # the pattern completed somewhere, and the rest of
                            # this pullback's candles are no longer separate
                            # ideas. Armed ones are untouched: they have
                            # levels and an order behind them.
                            # RECORDED HERE, SWEPT AFTER THE LOOP, and it
                            # used to remove them right here. That was two
                            # bugs. This loop walks a SNAPSHOT, list(cands),
                            # so a victim removed mid-loop was still visited
                            # afterwards -- it could arm and append a setup
                            # the rule had just deleted -- and then
                            # `cands.remove(cd)` at the bottom raised
                            # ValueError because it was already gone. That
                            # crash is what the last universe's fetch run
                            # hit, the first time armWins was ever a default.
                            #
                            # Sweeping after the bar also makes the rule
                            # ORDER-INDEPENDENT. Removing mid-loop meant
                            # whichever candidate the iteration reached first
                            # won, and the Pine walks this array in the
                            # OPPOSITE order -- so the two copies could pick
                            # different winners with nothing to say they had.
                            # Two candidates completing on the same bar have
                            # equal claim: both arm, and the unarmed rest go
                            # at the end of the bar.
                            if p.armWins:
                                armWon.add(cd.short)
                        else:
                            gone = True
                elif i - cd.bar >= p.confirmBars:
                    # WHY THE FUNNEL NARROWS, and nothing counted it until
                    # somebody looked at a panel reading "setups found 139,
                    # triggered 13" and had nowhere to go. The panel has a
                    # whole section for why an ARMED setup did not enter and
                    # had none for the far bigger drop before it.
                    #
                    # Two different failures and they mean different things: a
                    # pin whose Working line never broke was never a reversal
                    # attempt at all, and one that worked and never failed is
                    # a reversal that is still going. The second is the
                    # strategy being right about the candle and wrong about
                    # what came next; the first is just a shape that did
                    # nothing.
                    if not cd.workOk:
                        res.nNoWork += 1
                    else:
                        res.nNoFail += 1
                    gone = True

            if not gone and cd.armed and p.stopTrack and p.stopSrc == S_PULL:
                deeper = c.h > cd.pbExt if cd.short else c.l < cd.pbExt
                if deeper:
                    cd.pbExt = c.h if cd.short else c.l
                    cd.stop = (cd.pbExt + atrBuf if cd.short
                               else cd.pbExt - atrBuf)
                    rk2 = abs(cd.stop - cd.focus)
                    cd.target = (cd.focus - p.rr * rk2 if cd.short
                                 else cd.focus + p.rr * rk2)

            # ── the LIVE backup arms, ONCE ──────────────────────────────
            # Re-scanning every bar would keep finding a nearer zone and would
            # converge on "enter at the current price", which is not a backup.
            # In "late" mode nothing happens here: the backup is placed at the
            # Focus window's expiry, below.
            if (p.useBackup and p.bkWhen == B_LIVE
                    and not gone and cd.armed and not cd.ran):
                risk0 = abs(cd.stop - cd.focus)
                ranR = 0.0
                if risk0 > 0:
                    ranR = ((cd.focus - c.l) / risk0 if cd.short
                            else (c.h - cd.focus) / risk0)
                if ranR >= p.bkTrigger:
                    cd.ran = True
                    ext = c.l if cd.short else c.h
                    if p.bkMode == "mid":
                        px, why = (ext + cd.focus) / 2.0, "MID"
                    else:
                        px, why = bk_zone(cs, i, cd.short, cd.focus, ext,
                                          p.bkLook, p.useOB, p.useFVG)
                    if px is not None:
                        rk = abs(cd.stop - px)
                        if 0 < rk <= p.bkMaxRisk * risk0:
                            cd.bkPx, cd.bkWhy = px, why

            if not gone and cd.armed and i > cd.armBar:
                tgtGone = c.l <= cd.target if cd.short else c.h >= cd.target
                stopHit = c.h >= cd.stop if cd.short else c.l <= cd.stop
                # The nearer level, so price reaches it first, and for a short
                # the worse price. Checked before the Focus for both reasons.
                bkHit = bool(cd.bkWhy) and c.h >= cd.bkPx >= c.l
                # Once the Focus window has expired its limit is CANCELLED, so
                # a later touch of that price is not a fill. Without this the
                # "late" arm would still pre-empt, just later.
                touched = (c.h >= cd.focus >= c.l) and not cd.late
                if tgtGone:
                    if not cd.ghost:
                        res.nMissGone += 1
                    gone = True
                elif stopHit:
                    if not cd.ghost:
                        res.nMissStop += 1
                    gone = True
                elif bkHit or touched:
                    if bkHit:
                        # Re-based onto the zone: same stop, bigger risk, and a
                        # target recomputed from it -- or `rr` would quietly
                        # stop meaning rr.
                        cd.focus = cd.bkPx
                        rk3 = abs(cd.stop - cd.focus)
                        cd.target = (cd.focus - p.rr * rk3 if cd.short
                                     else cd.focus + p.rr * rk3)
                        if not cd.ghost:
                            res.nBackup += 1
                    if not cd.ghost:
                        res.nFilled += 1
                    filled = True
                    live.append(Trade(
                        symbol=symbol, bar=cd.bar, armBar=cd.armBar, fillBar=i,
                        short=cd.short, entry=cd.focus, stop=cd.stop,
                        target=cd.target, ghost=cd.ghost, state=cd.state,
                        code=cd.code, backup=cd.bkWhy))
                    if not cd.ghost:
                        res.fills.append(dict(
                            bar=i, symbol=symbol, short=cd.short,
                            entry=cd.focus, stop=cd.stop, target=cd.target,
                            code=cd.code, state=cd.state, pin=cd.bar,
                            armBar=cd.armBar, backup=cd.bkWhy))
                    gone = True
                elif not cd.late and i - cd.armBar >= p.fillBars:
                    # THE FOCUS WINDOW IS OVER. In "late" mode this is where
                    # the backup is placed, not where the setup dies: the zone
                    # is scanned NOW rather than at the earlier trigger,
                    # because a zone found twenty bars ago may be behind price
                    # by the time the window closes, and "the level I would
                    # take now" is the rule being described.
                    kept = False
                    if p.useBackup and p.bkWhen == B_LATE:
                        risk0 = abs(cd.stop - cd.focus)
                        ext = c.l if cd.short else c.h
                        if p.bkMode == "mid":
                            px, why = (ext + cd.focus) / 2.0, "MID"
                        else:
                            px, why = bk_zone(cs, i, cd.short, cd.focus, ext,
                                              p.bkLook, p.useOB, p.useFVG)
                        if px is not None:
                            rk = abs(cd.stop - px)
                            if 0 < rk <= p.bkMaxRisk * risk0:
                                cd.bkPx, cd.bkWhy, cd.late = px, why, True
                                kept = True
                    if not kept:
                        if not cd.ghost:
                            res.nMissBack += 1
                        gone = True
                elif cd.late and i - cd.armBar >= p.fillBars + p.bkLateBars:
                    if not cd.ghost:
                        res.nMissBack += 1
                    gone = True
            if gone or filled:
                cands.remove(cd)

        # THE ARM-WINS SWEEP, after every candidate has had its bar.
        for x in [y for y in cands
                  if not y.armed and not y.ghost and y.short in armWon]:
            res.nSuper += 1
            cands.remove(x)

        # ── filled trades, walked to their target or their stop ─────────────
        # AFTER the candidate loop, as in the Pine, so a setup filled on this
        # bar is checked for its outcome on this bar too. A limit filled
        # intrabar really was exposed to the rest of that bar. Stop first: when
        # one bar spans both levels the order is unknowable, so it is the loss.
        for t in list(live):
            lost = c.h >= t.stop if t.short else c.l <= t.stop
            won = c.l <= t.target if t.short else c.h >= t.target
            if lost or won:
                t.won = bool(won and not lost)
                t.exitBar = i
                risk = abs(t.stop - t.entry)
                gross = p.rr if t.won else -1.0
                # The round trip in R. A wider stop is a smaller cost in R,
                # which is the whole reason this is not a flat number.
                cost = (p.feeFrac * t.entry / risk) if risk > 0 else 0.0
                t.r = gross - cost
                res.trades.append(t)
                live.remove(t)

        # ── a new pin, section 6 tests ──────────────────────────────────────
        rng = c.h - c.l
        # THE PER-LEG RUNNING EXTREME, reset whenever the INTERNAL direction
        # turns. Read off `sOs`, which both engines supply, so this is one
        # expression rather than a branch per bias source.
        if legMax is None or (i > 0 and st["sOs"][i] != st["sOs"][i - 1]):
            legMax, legMin, legMaxX, legMinX = c.h, c.l, i, i
        else:
            if c.h > legMax:
                legMax, legMaxX = c.h, i
            if c.l < legMin:
                legMin, legMinX = c.l, i
        upW = (c.h - max(c.o, c.c)) / rng if rng > 0 else 0.0
        dnW = (min(c.o, c.c) - c.l) / rng if rng > 0 else 0.0
        isGreen = c.c >= c.o
        famHam = dnW - upW >= p.wickEdge
        famStar = upW - dnW >= p.wickEdge
        # THE THREE GATES, each independently removable. See `useFamily` and
        # `useColour` in P: turning one off does not change what the machine
        # then does with the bar, only whether the bar is admitted -- which is
        # what makes the difference between two arms attributable to the gate.
        #
        # `famHam` still decides which line is Working even when the family
        # test is OFF, because the machine needs the answer either way. With
        # the test off it degenerates to "whichever wick is longer", ties going
        # to the hammer reading. That is a fallback, not a finding.
        famOk = True if not p.useFamily else (
            (famHam and p.useHammer) or (famStar and p.useStar))
        # STRICT: only the priority shape is admitted at all. Folded in here
        # rather than added as a sixth gate because it IS a family test --
        # `useHammer` and `useStar` are the same question asked without
        # reference to the bias. Doing it here also keeps the funnel honest:
        # a bar the strict rule refuses never counted as a pin, which is what
        # `nRaw` is supposed to mean.
        if p.famStrict:
            prio = famHam if biasDir < 0 else famStar
            if prio == p.famInvert:
                famOk = False
        colourOk = True if not p.useColour else (
            isGreen if biasDir < 0 else not isGreen)
        # LOCATION, plus the two minimums. `pbAge` is measured from where the
        # pullback STARTED, not from the extreme, so extending the pullback
        # does not reset the clock -- which is the point: a pullback that has
        # run ten bars and just made a new high is still ten bars old.
        # THE ANCHOR, one of three. PIN_TREND uses the running extreme since
        # the major CHoCH; PIN_LEG uses the running extreme since the last
        # INTERNAL break, which is the per-leg object the author's diagram
        # shows. See the constants at the top for why the third exists.
        anchorX = pbExtX
        if p.pinAt == PIN_LOCAL:
            # Recomputed per bar rather than tracked, because the window slides
            # and a running extreme cannot un-see a low that has aged out.
            j0 = max(0, i - p.pbLook)
            loX = min(range(j0, i + 1), key=lambda k: cs[k].l) if biasDir < 0 \
                else max(range(j0, i + 1), key=lambda k: cs[k].h)
            span = range(loX, i + 1)
            exX = (max(span, key=lambda k: cs[k].h) if biasDir < 0
                   else min(span, key=lambda k: cs[k].l))
            pbExt = cs[exX].h if biasDir < 0 else cs[exX].l
            pbExtX, pbStartX, anchorX = exX, loX, exX
        elif p.pinAt == PIN_TREND:
            anchorX = (st["msMinX"][i] if biasDir < 0 else st["msMaxX"][i])
            if anchorX is None:
                anchorX = i
        elif p.pinAt == PIN_LEG:
            anchorX = legMinX if biasDir < 0 else legMaxX
        pbAge = i - pbStartX if pbStartX is not None else 0
        pbDepth = 0.0
        if p.pbMinDepth > 0.0:
            mx, mn = st["msMax"][i], st["msMin"][i]
            leg = (mx - mn) if (mx is not None and mn is not None) else 0.0
            if leg > 0:
                pbDepth = ((pbExt - mn) / leg if biasDir < 0
                           else (mx - pbExt) / leg)
        # pbMinAge / pbMinDepth measure how far a PULLBACK has run, which is
        # meaningless at the trend extreme -- there the pullback has not
        # started. They apply to PIN_PULL only, rather than silently refusing
        # every setup.
        # LOCATION. In BARS by default, in ATR when `locAtr` is set -- the
        # knife edge and its fix. The ATR form asks how FAR the candle's own
        # extreme is from the pullback's, which is the question; the bar form
        # asks how LATE it is, which is a proxy that throws away a pullback
        # whose highest bar happened to be a doji.
        if p.locAtr > 0.0:
            a14 = atr[i] if atr[i] else 0.0
            here = c.h if biasDir < 0 else c.l
            gap = (pbExt - here) if biasDir < 0 else (here - pbExt)
            locOk = a14 > 0 and gap <= p.locAtr * a14
        else:
            locOk = (i - anchorX) <= p.locTol
        if p.pinAt == PIN_PULL:
            locOk = (locOk and pbAge >= p.pbMinAge
                     and (p.pbMinDepth <= 0.0 or pbDepth >= p.pbMinDepth))
        # The HTF gate. A base-timeframe setup may only be taken when the
        # higher timeframe agrees on direction AND is itself tradeable. Off
        # when the gate is off, and then it is not counted either.
        htfOk = True
        if hM:
            htfOk = hK[i] and hD[i] == biasDir
        # "Look for the pullback AFTER the BOS." An Immature bias is a CHoCH
        # with no break of structure behind it yet; requiring `running` is what
        # makes the pullback a pullback FROM something.
        bosOk = (not p.needBos) or st["biasState"][i] == "running"

        # THE BIAS GATE. `tradeable` refuses a setup while the bias is Ending
        # or None; `direction only` keeps the direction and drops the refusal,
        # which is what the strategy's author asked for -- "we don't reject
        # based on the bias, we just trade the bias direction". `biasSeen` is
        # still required either way, and that is what `st["biasState"] != none`
        # tests: before the first CHoCH there is no direction, only the initial
        # value of `os`.
        biasOk = (tradeable[i] if p.biasGate == BG_TRADEABLE
                  else st["biasState"][i] != "none")
        if trace:
            res.trace.append(dict(
                i=i, t=getattr(c, "t", None), o=c.o, h=c.h, l=c.l, c=c.c,
                dir=biasDir, state=st["biasState"][i],
                tradeable=bool(biasOk),
                upW=round(upW, 3), dnW=round(dnW, 3), green=isGreen,
                famHam=famHam, famStar=famStar,
                famOk=famOk, colourOk=colourOk, locOk=locOk,
                htfOk=htfOk, bosOk=bosOk,
                pbExt=pbExt, pbExtX=pbExtX, pbStartX=pbStartX,
                anchorX=anchorX, barsFromAnchor=i - anchorX,
                pbAge=pbAge,
                admitted=bool(famOk and biasOk and colourOk and locOk
                              and htfOk and bosOk)))
        if famOk:
            res.nRaw += 1
        if famOk and biasOk:
            res.nPins += 1
            if colourOk:
                res.nColour += 1
                if locOk:
                    res.nLoc += 1
                    if not htfOk:
                        res.nHtf += 1
        # THE BEARISH LEG ON ITS OWN. Filtered here rather than on the trade
        # list afterwards, because a long that never existed also never took a
        # `maxLive` slot -- filtering after the run would leave the shorts
        # changed by longs that were never traded.
        if p.shortsOnly and biasDir > 0:
            famOk = False
        if famOk and biasOk and colourOk and locOk and htfOk and bosOk:
            # THE NEWEST COUNTER-TREND CANDLE SUPERSEDES THE ONES BEFORE IT,
            # across families. A hammer then an inverted hammer uses the
            # inverted hammer; an inverted hammer then a hammer uses the
            # hammer. Only UNARMED candidates in the same direction are
            # dropped -- one that has already confirmed is a live setup with an
            # order behind it and is not somebody's second opinion any more.
            # THIS CANDLE'S PLACE IN THE PULLBACK, before anything is dropped.
            side = biasDir < 0
            idx = pinSeen.get(side, 0)
            pinSeen[side] = idx + 1
            # `pinNewest` DELETES the older rivals, which is exactly right at
            # lag 0 and destroys the rule at lag 1 -- the candle to be traded
            # is one of the ones it would remove. So the deletion is skipped
            # while lagging and the arm gate below does the selecting instead.
            if p.pinNewest and not p.pinLag:
                # THE PRIORITY SHAPE WINS, and the newest of that shape. A
                # hammer (lower wick) in a bearish trend, a shooting star
                # (upper wick) in a bullish one; the other shape is used only
                # while the priority one is absent. With famPriority off this
                # is plain newest-wins, which is what v2 measured.
                isPriority = famHam if biasDir < 0 else famStar
                rivals = [x for x in cands
                          if not x.armed and not x.ghost
                          and x.short == (biasDir < 0)]
                if p.famPriority and not isPriority:
                    # A non-priority candle does not displace a priority one.
                    held = any(x.workHi == (biasDir < 0) for x in rivals)
                    rivals = [] if held else rivals
                for x in rivals:
                    res.nSuper += 1
                    cands.remove(x)
            if len([x for x in cands if not x.ghost]) >= p.maxLive:
                res.nCap += 1
            else:
                res.pins.append((i, biasDir < 0,
                                 pbStartX if pbStartX is not None else i))
                cands.append(_Cand(
                    bar=i, hi=c.h, lo=c.l, focus=c.o, workHi=famHam,
                    short=biasDir < 0, pbExt=pbExt, pinIdx=idx,
                    pbStart=pbStartX if pbStartX is not None else i,
                    state=st["biasState"][i],
                    code=("HAM" if isGreen else "HGM") if famHam
                    else ("IH" if isGreen else "SS")))

    res.nOpenReal = sum(1 for t in live if not t.ghost)
    res.nOpenGhost = sum(1 for t in live if t.ghost)
    # Trades still open at the end of the data have not had their window.
    # Counting them as anything would score an unfinished trade at whatever
    # price the fetch happened to stop on, which is noise dressed as an
    # outcome -- the same rule research/data.py applies.
    return res
