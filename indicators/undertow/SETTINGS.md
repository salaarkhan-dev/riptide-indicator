# Every setting, and where its value came from

You asked me to revisit the parameters. This is the audit, not a retune — the
last section says why those are different things.

> **WHAT THIS AUDIT CHANGED.** The chart went from **56 inputs to 40**, and of
> those 40 only 23 decide anything — the rest are display and debug. The rule
> applied, and it is the only rule this file argues for:
>
> **an input earns its place only if the strategy's definition needs it, a
> study showed the choice matters, or it is display.**
>
> Sixteen failed all three. They are listed in §6 and every one of them is
> still in the port, because that is where an unmeasured option belongs: the
> port can express it, the chart does not offer it, and the studies that name
> it keep reproducing unchanged. No strategy default was touched.

**65 settings. 17 have a pre-registered study behind them. 15 are values that
came off your chart or out of the Pine's first draft and have never been
measured at the value they ship at. 28 are inert. 4 are definitions, not
numbers. 1 was wrong and is fixed in this commit.**

---

## 1 · INERT — 28 settings that do nothing as shipped

These are read only when a feature that is OFF gets switched on. Changing them
today changes nothing on your chart.

| group | settings | why inert |
|---|---|---|
| retired bias sources | `emaFast` `emaSlow` `stAtrLen` `stMult` `slopeUnit` `slopeLen` `slopeMin` `slopeHours` `slopeMinPerHr` `donLen` `mtfFast` `mtfSlow` `mtfMult` `smcSwingLen` `smcInternalLen` `matureBars` | `biasSrc` is `structure`. Five alternatives were measured; [none beat it](measurements/UNDERTOW_BIAS_SOURCE.md) |
| the backup fill | `bkTrigger` `bkMaxRisk` `useOB` `useFVG` `bkLook` `bkWhen` `bkLateBars` `bkMode` | `useBackup` is off — [+0.03 R per armed setup, significant on none](measurements/UNDERTOW_BACKUP_FILL.md) |
| off-switch operands | `staleBars` (needs `endStale`) · `htfUnit` `htfHours` (need `htfMult`) · `adxMin` at 0 is its own off switch | the gates they belong to are off |

**Nothing here needs your attention, and most of it is no longer on the chart
at all** — see §6. They exist so a study can switch a feature on without a code
change.

---

## 2 · MEASURED — 17 settings a study actually tested

A pre-registered study compared the shipped value against alternatives, on
symbols it had never seen, against a control.

| setting | ships | what the study found |
|---|---|---|
| `biasSrc` | structure | five sources measured, [none beat it](measurements/UNDERTOW_BIAS_SOURCE.md); SMC structure [scored the same](measurements/UNDERTOW_V2.md) |
| `endMinor` | on the flip | swept in [PARAMS](measurements/UNDERTOW_PARAMS.md); [discards 64% of trades](measurements/UNDERTOW_MTF_DEFAULT.md) and that cost is uncontrolled |
| `swingSrc` | price move | the [holdout's chosen source](measurements/UNDERTOW_PARAMS.md) — see §4, this is a weaker claim than it sounds |
| `useHammer` `useStar` `useFamily` `useColour` | on | [the taxonomy adds nothing](measurements/UNDERTOW_PIN_VALUE.md) — removing it scored **higher** on 2 of 3. Kept on because it is the strategy's definition, not because it earned it |
| `confirmOrder` | working then failure | your correction; [measured in v2](measurements/UNDERTOW_V2.md) and it did not pay. Ships anyway as a correction, not a promotion |
| `needBos` | off | [removing it improved v2](measurements/UNDERTOW_V2.md) on 3 of 3 |
| `pinNewest` `famPriority` | off | [v2](measurements/UNDERTOW_V2.md) scored the wrong form, [v3](measurements/UNDERTOW_V3.md) found it; **the pairing is under test now** |
| `pinAt` | pullback extreme | [the corrected anchor is not harmful and did not clear](measurements/UNDERTOW_V3.md); selectable, off |
| `locTol` | 0 | [2 scores within ±0.025 R and nearly doubles the setups](measurements/UNDERTOW_PULLBACK.md) — 0 is the status quo, not the winner |
| `pbMinAge` `pbMinDepth` | 0 | [the setups they would remove are not worse](measurements/UNDERTOW_PULLBACK.md) |
| `htfMult` | 0 (off) | [worth +0.032 / +0.010 / −0.029 R over a matched control](measurements/UNDERTOW_HTF.md) |
| `useBackup` | off | [two significant halves that nearly cancel](measurements/UNDERTOW_BACKUP_FILL.md) |

**Read that column again.** Not one of these says "this value is better". They
say "the alternatives were not better either". Fourteen studies, no edge found
in any direction — which is why nothing has been promoted and why the
parameters have not moved.

---

## 3 · DEFINITIONS — 4 settings that are the strategy, not knobs

| setting | ships | |
|---|---|---|
| `workTest` `failTest` | close beyond | a CLOSE past the line, not a wick through it. Your rule |
| `stopSrc` | pullback extreme | the new lower high. Your whiteboard, and [453 of 453 bearish stops sit above the entry](measurements/UNDERTOW_V3.md) |
| `stopTrack` | on | the stop follows the pullback as it extends |

Changing these makes it a different strategy. They are not candidates for
tuning.

---

## 4 · THE 15 THAT NOTHING SUPPORTS

**This is the part worth your attention.** Each of these is a specific number
that shapes what the indicator does, and none has ever been measured at the
value it ships at.

| setting | ships | where the value came from |
|---|---|---|
| `rr` | 3.5 | **your chart.** [The sweep used 3.0](measurements/UNDERTOW_PARAMS.md); 3.5 is what your TradingView layout had |
| `msLen` `msShortLen` | 6 / 2 | your chart |
| `endSweep` `endStale` | off / off | your chart |
| `retraceMax` | 70 | the Pine's first draft |
| `stopBuf` | 0.25 ATR | the Pine's first draft. [The median gap is exactly the buffer](measurements/UNDERTOW_V3.md), so it is load-bearing |
| `swingK` `swingKMinor` | 0.40 / 0.12 | **worse than unmeasured — see below** |
| `swingHours` | 24.0 | the window the swing threshold is a fraction OF. Never varied |
| `maxLive` | 4 | **see below** |
| `wickEdge` | 0.05 | the doji exclusion. The margin that decides hammer vs. nothing. Never varied |
| `confirmBars` | 20 | how long a pin waits for its two confirmations |
| `fillBars` | 20 | how long the limit rests. [What happens AFTER it expires was measured](measurements/UNDERTOW_LATE_BACKUP.md); the 20 was not |
| `msBosNeedsIdm` | on | inherited from the v2 structure indicator |

### Two of these are worse than merely unmeasured

**`swingK` 0.40 / `swingKMinor` 0.12 were chosen by a sweep that failed its own
holdout.** They are the Min30 training winner in
[`UNDERTOW_PARAMS.md`](measurements/UNDERTOW_PARAMS.md) — the study whose
headline result is that picking the best of 48 configurations bought **+0.31 R
per trade of pure illusion**, three times over. The values then became the
defaults. That is the one place in this project where a number that failed a
holdout is still shipping, and it is shipping because it was already on the
chart when the sweep agreed with it.

**`maxLive` 4 means your chart is not running the strategy that was measured.**
Every study sets 64 and reports `nCap = 0` — no setup was ever turned away. At
4, setups past the cap are refused, and
[74% of 15m trades run alongside another in the same direction](measurements/UNDERTOW_OVERLAP.md).
The panel counts the refusals on its "at the live cap" row. If that number is
large on your chart, the chart is a stricter rule than any page here describes.

---

## 5 · THE ONE THAT WAS WRONG, and is fixed

**`feeFrac` shipped at 0.** Every study passed 7bp explicitly, so no
measurement moves — but the **chart and the watcher read the default**, so both
reported **gross** R and a **gross** break-even line.

[`UNDERTOW_V3.md`](measurements/UNDERTOW_V3.md) is what made that
indefensible. The fee is charged in price and the trade is scored in R, so the
drag is `fee ÷ risk`, and risk runs 1.3% of entry on 15m against 2.4% on 1h:

| tf | median risk | drag | break-even | v1's actual win rate |
|---|---|---|---|---|
| Min15 | 1.26% | 0.055 R | **23.5%** | 23.6% |
| Min30 | 1.62% | 0.043 R | **23.2%** | 23.6% |
| Min60 | 2.38% | 0.029 R | **22.9%** | 22.9% |

The panel drew its line at 22.2% and coloured anything above it **green**. So a
chart showing 23.0% — a rule losing money — showed green. Both the line and
`net R` now include the fee, with a `Round-trip fee` input defaulting to the
same 7bp every study used. Set it to 0 to read the panel gross.

---

## 6 · THE SIXTEEN THAT CAME OFF THE CHART

Removed from the Pine, kept in the port. None was a default change — every one
of them was already at the value it is now fixed at.

| what went | why |
|---|---|
| **the backup fill** — `useBackup` `bkTrigger` `bkMaxRisk` `useOB` `useFVG` `bkLook` `bkWhen` `bkLateBars` | measured **twice** and worthless: [+0.03 R per armed setup, significant on none](measurements/UNDERTOW_BACKUP_FILL.md), and [waiting for the limit to expire removes the tax and all the opportunity](measurements/UNDERTOW_LATE_BACKUP.md) |
| **three Ending rules** — `endSweep` `endStale` `staleBars` `adxMin` | all shipped **off**, none ever measured **on**. ADX had already failed as a filter [elsewhere in this project](../ccp/measurements/CCP_CONTEXT_FILTERS.md) |
| **two pullback minimums** — `pbMinAge` `pbMinDepth` | [measured: the setups they remove are not systematically worse](measurements/UNDERTOW_PULLBACK.md) |
| **two confirmation tests** — `workTest` `failTest` | three unmeasured variants each of something the strategy defines as *a close beyond* |

**Two of the backup fill's eight inputs were never wired up at all.** `bkWhen`
and `bkLateBars` were declared, given tooltips, and never read by a single line
of the indicator — the "after the limit expires" mode exists in the port and
was measured there, and the chart silently never had it. That is what an input
panel nobody prunes looks like from the inside.

The Ending panel row was five counters wide, `minor·swp·stale·rt·adx`, three of
which could never be anything but zero. It is now `minor · retrace`.



**I am not going to pick better values for the 15.** Not because it would be
hard — it would be easy, and that is the problem.

This project has measured the cost of doing exactly that:
**−0.31 R per trade**, on all three timeframes, in
[`UNDERTOW_PARAMS.md`](measurements/UNDERTOW_PARAMS.md). Picking the best of 48
configurations produced +0.28 to +0.35 R on the data it was picked on and
−0.09 to +0.07 R on data it had not seen. The gap is not bad luck. It is what
choosing from a finite sample buys you, every time, and it is why every number
in `measurements/` was produced under a pre-registration committed before the
run.

If I sweep `wickEdge`, `confirmBars`, `stopBuf`, `rr` and the rest, I will find
a combination that looks good. It will look good by construction. On your money
it will be worth about −0.31 R per trade.

**So the honest answer to "are the parameters right" is: nobody knows, for 15
of them, and finding out costs one fresh universe per question.** The venue has
255 unused contracts left and each study spends 45 of them. That is roughly
five more questions at full strength, which is why the queue matters more than
the answers:

1. **`maxLive`** — the only one where the chart and the measurements
   demonstrably disagree. Not a tuning question: a "which rule am I running"
   question, answerable by re-running an existing study at 4 and comparing.
2. **`rr`** — the largest single lever, shipping at a value no study used, and
   [the exits page](measurements/UNDERTOW_EXITS.md) already has the raw
   material for it.
3. **`swingK` / `swingKMinor`** — the ones carrying a failed holdout.
4. **`locTol`** — already measured as equal-scoring at 2 with nearly double the
   setups; it needs a decision, not a study.

**None of that is urgent, and here is the reason.** Fourteen studies say the
entry is break-even after costs. A parameter that moves a break-even rule by
0.05 R is not the difference between this working and not working. The thing
that has never been tested is whether *you*, choosing which of these setups to
take, beat the machine taking all of them — and no amount of parameter work
answers that. It needs alerts fired forward and outcomes written down.
