# Detection, engineered — the pullback and the candle

**Status: SPEC ONLY. Nothing here is implemented and nothing is measured.**
Written after twenty null measurements, on the chart owner's instruction to
*"use some mathematical methods and formulas ... first understand, then design
the specs, then improve."* So: part 1 is what the code does today, stated
exactly; part 2 is which of it is arbitrary; part 3 is the design; part 4 is
how to test it without manufacturing a result, which given this project's
history is the part that matters most.

---

## 1. WHAT THE CODE DOES TODAY

Read off [`port/undertow.py`](port/undertow.py) rather than remembered.

### 1.1 The pullback

There is no pullback *object*. There is a running extreme and a reset:

```
pbReset  ⟺  biasDir flipped
         ∨  the trend-side structural extreme moved
            (msMinX changed in a downtrend, msMaxX in an uptrend)

on reset   pbExt ← h (downtrend) | l (uptrend),  pbStartX ← i
otherwise  pbExt ← max(pbExt, h) (downtrend) | min(pbExt, l) (uptrend)

pbAge   = i − pbStartX
pbDepth = (pbExt − msMin) / (msMax − msMin)      [downtrend]
```

`pbDepth` **is only computed when `pbMinDepth > 0`**, and `pbMinDepth` is 0.
So it is normally not computed at all.

**A pullback has no minimum, no maximum, and no end.** It runs until the trend
makes a new extreme. `pbMinAge = 0` and `pbMinDepth = 0`, so a one-bar 0.2% dip
is a pullback on equal terms with a twenty-bar 60% retracement. `retraceMax =
70` exists but ends the **bias**, which is a different object with a different
denominator.

### 1.2 The candle — five independent binary gates

```
r    = h − l
upW  = (h − max(o,c)) / r          dnW = (min(o,c) − l) / r

famHam   ⟺ dnW − upW ≥ wickEdge            wickEdge = 0.05
famStar  ⟺ upW − dnW ≥ wickEdge
famOk    ⟺ (famHam ∧ useHammer) ∨ (famStar ∧ useStar)
famStrict⟹ in a downtrend only famHam survives
colourOk ⟺ green in a downtrend, red in an uptrend
locOk    ⟺ i − anchorX ≤ locTol            locTol = 0
htfOk, bosOk
```

`locTol = 0` means **the candle must BE the bar that made the pullback's
extreme.**

### 1.3 Choosing between qualifying candles

`pinNewest` (the newest supersedes), `famPriority` (a non-priority shape does
not displace a waiting priority one), `pinLag` (0 newest, 1 second-newest),
`armWins`, `maxLive`.

**Every one of these is a rule about ORDER.** None is a rule about which candle
is *better*.

---

## 2. WHAT IS ARBITRARY, AND WHY IT MATTERS

### 2.1 There is no notion of candle quality — this is the root defect

A candle with `dnW − upW = 0.051` and one with `0.85` are **the same object** to
this code. Both pass; neither is preferred. So when the question "which candle
in the pullback?" arose, the only answers available were positional —
*newest*, *second newest* — because **no quality criterion existed to rank them
by.**

That is why `pinLag` had to be invented and why it measured nothing:
`undertow_pinlag.py` returned −0.468 / −0.056 / +0.870 across gates and
timeframes, signs disagreeing. A positional rule is a proxy for the thing the
eye is actually doing, and proxies are what this project keeps measuring.

### 2.2 `locTol = 0` is a knife edge, not a filter

The candle must be exactly the extreme bar. If that bar is a doji, or the wrong
colour, **the entire pullback is discarded** — not deferred, discarded.

Measured today from `Result.pins`, Min30 shorts on the spent 23: **64% of
pullbacks yield exactly one qualifying candle** under the strict gate, 38%
under the family. That is not the market offering one good candle. That is a
binary location test admitting one bar per pullback by construction.

### 2.3 A pullback has no bounds

`pbMinAge` and `pbMinDepth` exist, both 0, **never measured at any other
value**. There is no maximum depth at all. A 95% retracement is not a pullback
in any useful sense, and nothing here says so.

### 2.4 The frame is a 50-bar pivot

`msLen = 50` turns over once per ~286 bars — median 172 bars between bias
flips, tradeable 24% of the time. The pullback is defined against a structure
that barely moves.

### 2.5 `wickEdge = 0.05` has never been measured

Not at 0.02, not at 0.20. It is a number that was chosen.

---

## 3. THE DESIGN

Three objects, each defined rather than emergent.

### 3.1 The pullback as a bounded object

Given trend direction σ ∈ {−1,+1} and the impulse leg it retraces, with range
`L = msMax − msMin`:

```
depth   δ = (pbExt − msMin) / L        [σ = −1]      δ ∈ [0, 1]
age     α = i − pbStartX                              bars
```

**Admission bounds, all currently unbounded:**

```
δ ∈ [δmin, δmax]        proposed start 0.15 … 0.85
α ∈ [αmin, αmax]        proposed start 2 … 40
```

`δmax` is the one with no counterpart today and the one most likely to matter:
past it, the move is a reversal wearing a pullback's name, which is exactly the
failure [`UNDERTOW_ANCHOR.md`](measurements/UNDERTOW_ANCHOR.md)'s retrace rule
was added for at the bias level and never added at the pullback level.

**An explicit end.** A pullback terminates on the first of: a new trend
extreme, δ > δmax, or α > αmax. Today only the first exists.

### 3.2 The candle as a score, not a gate

Replace the cascade with `s ∈ [0,1]`. For a short (hammer family), `r = h − l`,
`A` = ATR(14):

| | component | formula | what it captures |
|---|---|---|---|
| w₁ | wick dominance | `clip(dnW − upW, 0, 1)` | which side rejected |
| w₂ | wick magnitude | `dnW` | how hard |
| w₃ | body tightness | `1 − |c−o|/r` | indecision at the extreme |
| w₄ | close position | `(c − l)/r` | closed back near the high |
| w₅ | relative size | `clip(r/A, 0, 2)/2` | a hammer on a tiny bar is noise |
| w₆ | sweep depth | `clip((minₖ(l) − l)/A, 0, 1)` | probed liquidity below the prior k-bar low and closed back |

```
s = Σᵢ βᵢ wᵢ   /   Σᵢ βᵢ              additive, β ≥ 0
```

Additive rather than multiplicative so a single weak component cannot zero an
otherwise excellent candle — and so the fitted βs are directly readable as
*"this is what the eye weighs"*.

**w₆ is the one nothing in the code has today** and it is the component the
chart owner's own drawings keep pointing at: the arrow marked *Liquidity* in
his screenshot is a sweep, and the current detector has no term for it.

### 3.3 Location as a continuous penalty

Replace `i − anchorX ≤ locTol` with a distance in ATR:

```
λ = (pbExt − h) / A          ≥ 0, zero at the extreme bar
loc = 1 / (1 + λ/τ)          τ proposed 0.5 ATR
```

`locTol = 0` is the limit τ → 0. This is what stops a whole pullback being
thrown away because its highest bar happened to be a doji.

### 3.4 Selection by score

```
admit   s · loc ≥ θ
choose  argmax over the pullback of (s · loc)
```

`pinNewest` is the special case where `s` is binary and ties break by recency.
`pinLag` has no counterpart and needs none — it was a positional stand-in for
the ranking this provides.

**Free parameters: 6 weights + θ + τ + 4 pullback bounds = 12.**
Stated here, before any fitting, because
[`UNDERTOW_PARAMS.md`](measurements/UNDERTOW_PARAMS.md) priced best-of-48
selection at **−0.31 R per trade of pure illusion**, and twelve continuous
parameters is far more freedom than 48 discrete configurations.

---

## 4. HOW THIS GETS TESTED WITHOUT MANUFACTURING A RESULT

**This is the part that decides whether any of the above is worth building.**

### 4.1 Two signals, kept apart

| signal | source | used for |
|---|---|---|
| **labels** | the chart owner's blind take/skip on `label_setups.py` | **fitting β, θ, τ** |
| **R** | the outcome of the trades | **testing, and nothing else** |

**β is never fitted on R.** Fitting on the labels and testing on R keeps the
fit independent of the outcome, which is the only reason twelve parameters is
defensible at all. If β were fitted on R, the result would be a curve fit with
a story attached, and this repository has a page pricing exactly that.

### 4.2 What each stage may conclude

1. **Fit.** Split the labels in half by symbol. Fit on one half, report
   **agreement** on the other — not R. A score that cannot predict his own
   choices on held-out pullbacks is not a model of his eye, and the work stops
   here.
2. **Baseline it.** Agreement must beat (a) always-take, (b) always-skip, and
   (c) `pinNewest`. A score that merely reproduces "newest wins" has added
   twelve parameters for nothing.
3. **Only then, R.** Pre-register the fitted rule — weights frozen, written
   down, committed — and measure once.

### 4.3 The data budget, stated before anything is spent

**21 usable contracts remain** (see `research/symbols_fresh.py`). At the
coverage the last three sets achieved they field roughly 20 / 19 / 14 symbols
on Min15 / Min30 / Min60, so a fresh test can report **Min15 only**, and
marginally. The alternatives are walk-forward on spent sets, or the prospective
forward record.

**The fitting stage costs no fresh data at all** — labels are not R. That is
the design's main practical virtue: stages 1 and 2 can be done entirely on
spent symbols, and the last fresh contracts are spent only if the score clears
stage 2.

### 4.4 What would make this fail honestly

* held-out label agreement no better than `pinNewest` → the eye is doing
  something these six components do not capture, and the components are wrong
* agreement good, R null → the eye is reproducible and has no edge, which is a
  real and publishable finding and the single most likely outcome given twenty
  prior nulls
* agreement good, R positive → the first promoted component in the project,
  and it will have been fitted on one signal and tested on another

---

## 5. ORDER OF WORK

1. **Labels.** ≥ 200 blind take/skip on `label_setups.py`. Nothing below can
   start without them.
2. **Fit and report held-out agreement** against the three baselines. No R.
3. **Prereg**, if and only if stage 2 clears.
4. **Implement** — port first, then Pine, then watcher, with the three-way
   check holding them together.
5. **Measure once.**

Steps 1–2 spend no fresh data. Step 5 spends what is left.

---

## 6. WHAT THIS SPEC DOES NOT DO

* It does not change the exit. The measured gap between the chart owner's 1:8
  and the code's 1:3.5 was **the stop width**, not the target, and `stopSrc`
  has been reverted to the pullback extreme to match what he trades.
* It does not touch the bias. `msLen = 50` is named in 2.4 as a defect of the
  frame; it is a separate question with a separate answer and mixing them would
  make both unmeasurable.
* It does not add an input to the chart. Nothing reaches the Pine until stage 3
  is written and stage 5 is run.
