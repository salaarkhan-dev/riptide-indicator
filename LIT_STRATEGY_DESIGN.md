# Riptide LIT — Strategy Design (enhanced §72)

Design document. **No strategy code yet.**

Master prompt §72 is a six-line skeleton written before any of the reference
author's trading material was available. `LIT_SOURCE.md` Part Two (Ch.14–22) now
describes a complete pipeline. This document is §72 rewritten against it, and
says plainly which parts are source-confirmed, which are ours, and which are
still open.

**Constraints that do not move.** §75 and the standing project rule: research
only, alerts only, **no exchange API, no order placement, no execution
automation**. `riptide_bot.py` is a separate phase-1 product and nothing here
touches it. Standardised R for research; no leverage logic in the engine.

---

## 1. What §72 got right, and what it missed

§72 said:

```
Main bullish → valid Demand Pullback → bullish IDM → IDM swept/broken
→ bullish BOS locked above → price reclaims/holds structure → long toward BOS
```

Right: the structural precondition, and that the trade is a continuation after
inducement is taken. Everything up to "BOS locked above" survives intact.

Missing, and each is a whole subsystem:

| §72 says | The source actually requires |
|---|---|
| "price reclaims/holds structure" | price returns to a **classified POI zone** (Decisional / Extreme / Breaker / Flip) or a **Liquidity Grab Level**, and then produces **SCOB confirmation**. Reaching the zone is explicitly *not* enough |
| — | an **FVG filter** on zone validity, where FVG is the gap between two consecutive *pullbacks*, not three candles |
| — | the POI range **tightened by internal pullbacks** when the external pullback contains valid internal structure |
| — | **mitigation**: when a zone is consumed rather than merely touched, with the arbitrary 50% rejected by name |
| "stop below IDM raid extreme" (§73) | **two** placements — SL on Order Block (high risk) or SL on Pullback / OrderFlow (low risk) |
| "long toward BOS" (§74) | **no fixed target.** Active Price arms a **trailing stop**. §74 is overridden |
| — | an **obstacle check** that rejects a confirmed setup when the Entry → Active Price corridor is blocked |
| — | **Hidden Shadow on the stop**, so a body break of SL is not automatically an exit |

§74 is the notable correction. It named BOS as "the natural structural target"
because LIT's thesis is that inducement resolves toward BOS. The thesis is
right — our own statistic measures it — but the reference does **not** target
BOS. It uses the BOS direction to justify the trade and then trails.

---

## 2. The premise is already measured, and it holds

Everything below rests on one claim:

> "in most cases, when the IDM level is broken, a trend reversal does not occur,
> and price ultimately reaches the BOS level."

That is the `IDM → BOS touch` row, and it is the only row in the whole table
with no "near" definition in it:

| | Total | Count | Rate |
|---|---|---|---|
| reference, ZEC 30m | 20 | 13 | **65.0%** |
| Riptide V2, ZEC 30m | 32 | 21 | **65.6%** |
| Riptide V2, ZEC 15m | 38 | 24 | **63.2%** |

The premise survives on our own engine, on two timeframes, at a rate matching
the reference. **That is the green light for this work, and it is the only
thing so far that has earned one.**

What it does *not* establish: that 65% first-passage is profitable. First
passage to BOS says nothing about where you entered, how far the stop was, or
what happened in between. Which is the whole of Stage A.

---

## 3. Build order — premise first, machinery second

The lesson this project has paid for repeatedly: a mechanism reasoned about
rather than measured is a mechanism that will be wrong. So the staging is
deliberately backwards from the obvious order — the crudest version first,
because it is the one that tests the thesis without a single new subsystem.

### Stage A — the naked continuation. Nothing new to build.

Every level already exists in `riptide-lit-v2.pine`. In `research/`, on real
candles, measure the simplest possible expression of §72:

```
long  when a bullish IDM is taken and a BOS is locked above
entry at the IDM break bar's close
stop  below the IDM raid extreme                       (§73)
exit  at BOS touch, or at CHoCH touch, whichever first
```

Record per setup: **R at exit, MFE, MAE, bars held, BOS-before-CHoCH, and the
distance to BOS in R at entry.**

The decisive number is not the win rate. It is **the R distribution of the 65%
that reach BOS against the 35% that don't**, because the stop distance is set by
the raid extreme and has no reason to be proportionate to the BOS distance. If
the winners average less than ~0.54R per unit of loser, 65% is not enough.

**Stage A can kill the whole strategy, and that is what it is for.** If the
naked version has no edge, adding POI, SCOB and an obstacle filter is
decorating a losing distribution — and every one of those subsystems is weeks
of work with its own inference risk.

### Stage B — FVG, defined properly

Gate: Stage A shows positive expectancy, or shows a clearly identifiable subset
that does.

An FVG here is a gap between two **consecutive confirmed pullbacks** with
displacement between them, not a three-candle wick gap. We already emit
pullbacks with their full ranges, so this is a comparison between consecutive
`PB` records rather than a candle pattern. Measure: does requiring an FVG on the
appropriate side improve Stage A's distribution, and by how much per setup lost?

### Stage C — POI zones

Decisional first (it is the one tied to IDM, which Stage A already uses).
Extreme, Breaker and Flip after, each measured separately — they are different
objects with different preconditions, and "Jump" (displacement) gates the last
two.

POI range uses internal pullbacks when the external pullback contains valid
internal structure. **This is where P7b stops being cosmetic**: if Internal is
not producing real structure, the zone cannot be tightened, and Ch.15 says
tightening is automatic in the reference.

### Stage D — SCOB

Cheap, now that Ch.21 closed its geometry: the last opposite-direction candle
before the reaction, its facing boundary as the level, broken under the existing
three-mode engine. Mode 3 is `brkStep` in `BRK_SWEEP` unchanged.

Measure it as a **filter on Stage C**: how many entries does it remove, and is
the removed set worse than the kept set? A filter that removes setups without
improving the remainder is a cost, not a feature — the same test that sank the
structure-trend gate earlier in this project.

### Stage E — Active Price, RR gate, obstacle check

Active Price from entry, stop, minimum RR and commission. Then the obstacle
check: reject when a BOS level, an opposing pullback or a Breakout Zone sits
inside the Entry → Active Price corridor.

This is the filter with no §72 counterpart and the one most likely to matter,
because it removes setups that are structurally fine but have no room to pay.
Measure it last and on its own, so its effect is attributable.

### Stage F — sizing and trailing stop

Position size from evolving balance, stop distance, max risk % and commission.
Trailing stop armed at Active Price.

**[GAP] What the trailing stop trails is not stated anywhere in the source.**
It is the last large hole and it must not be filled by inference. Candidates to
measure against a fixed-R control: trail behind each new confirmed pullback
pivot; trail behind the most recent structural level; trail a fraction of MFE.
The fixed-R control is the honest baseline — if none of the trailing variants
beat it, say so.

---

## 4. The conflict that has to be resolved before Stage C

Ch.15: *"We only enter trades in the direction of the prevailing trend."*

Ch.21's BOS-grab slide: bullish structure, price sweeps above the BOS, red arrow
**down**.

Both are source. Two readings:

1. **Liquidity Grab Levels are a separate entry family** from POI zones, and the
   with-trend rule was stated inside the POI section only.
2. **A failed BOS sweep is itself the signal the leg is finished.**

Reading 2 is already instrumented — `BOS near → Opp PB reach` is precisely this
event, at 69% in the reference and 55% in ours. So it is measurable rather than
arguable, and the measurement belongs in Stage A' (a small extension of Stage A)
rather than waiting for Stage C.

Until it is settled, **Stage A trades with-trend only.** A counter-trend arm is
a separate arm with its own evidence, exactly as §73 insists risk parameters
must be.

---

## 5. What we are NOT importing

- **No 2R target.** §74 is explicit that Riptide's 2R is a different hypothesis,
  and the source uses no fixed target at all.
- **No 1.2–2.6% risk band.** §73 forbids importing it. This family earns its own.
- **No 50% mitigation threshold.** Rejected by name in Ch.15.
- **No ATR, no pivot length, no percentage band anywhere.** Ch.2's determinism
  requirement, which has held through every round of this project.
- **No order placement, no exchange keys, no execution.** §75 and the standing
  project rule.

---

## 6. Next action

Write `research/lit_entry.py`: Stage A on ZEC and the wider universe, reporting
the R distribution, MFE/MAE, and the BOS-before-CHoCH split, plus the Stage A'
counter-trend arm for the §4 conflict.

No Pine strategy code until Stage A returns a number worth building on.
