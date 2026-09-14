# Riptide LIT — Trading System Design (enhanced §72)

Design document. **No strategy code yet.** Same discipline as
`LIT_V2_DESIGN.md`: every rule traced to source, every undefined case named as a
policy with a default and a switch, every stage gated on a measurement that can
fail.

Sources: `LIT_SOURCE.md` Part Two (Ch.14–24 — the author's own trading material),
master prompt §72–§75, and the measurements in `LIT_CHANGELOG.md`.

**Constraints that do not move.** §75 and the standing project rule: research
only, alerts only, **no exchange API, no order placement, no execution
automation**. `riptide_bot.py` is a separate phase-1 product and nothing here
touches it. Standardised R for research; no leverage logic in the engine.

---

## 1. What §72 got right, and what it missed

```
§72:  Main bullish → valid Demand Pullback → bullish IDM → IDM swept/broken
      → bullish BOS locked above → price reclaims/holds structure → long toward BOS
```

Everything up to "BOS locked above" survives intact. After that it is a
placeholder, and each missing piece is a subsystem:

| §72 says | The source requires |
|---|---|
| "price reclaims/holds structure" | return to a **classified POI zone** or a **Liquidity Grab Level**, then **SCOB confirmation**. Reaching the zone is explicitly not enough |
| — | an **FVG filter**, where FVG is the gap between two consecutive *pullbacks* |
| — | POI range **tightened by internal pullbacks** where they exist |
| — | **mitigation** — consumed vs merely touched, with 50% rejected by name |
| "stop below IDM raid extreme" (§73) | **two** placements: SL on Order Block (high risk) / SL on Pullback (low risk) |
| "long toward BOS" (§74) | **no target.** Active Price arms a **trailing stop**. §74 overridden |
| — | an **obstacle check** that rejects confirmed setups |
| — | **Hidden Shadow on the stop** |

§74 is the notable correction: the BOS thesis is right and our own statistic
measures it, but the reference uses BOS *direction* to justify the trade and
then trails. It never exits at BOS.

---

## 2. The premise is measured and it holds

> "in most cases, when the IDM level is broken, a trend reversal does not occur,
> and price ultimately reaches the BOS level."

| `IDM → BOS touch` | Total | Count | Rate |
|---|---|---|---|
| reference, ZEC 30m | 20 | 13 | **65.0%** |
| Riptide V2, ZEC 30m | 32 | 21 | **65.6%** |
| Riptide V2, ZEC 15m | 38 | 24 | **63.2%** |

The only row in the table with no "near" definition in it, and our engine
reproduces the reference's rate on two timeframes. **This is the only green
light this project has issued.** It does not establish profitability — first
passage says nothing about entry, stop distance, or the path.

---

## 3. Object specifications

### 3.1 FVG — between PULLBACKS, never three candles

> "FVG is the Distance between two consecutive pullbacks" … "an FVG is not
> merely the distance between the wicks of three consecutive candles."

```
given consecutive confirmed pullbacks P(n-1), P(n) in the same direction
gap exists  ⟺  their [edge, pivot] ranges DO NOT OVERLAP          [T1]
fvg         =  the open interval between them
side        =  the impulse side of the leg
```

A new pullback that penetrates the previous one **consumes** it; the earlier
node loses validity. A gap means the orders there may be unconsumed.

Every generic SMC library computes the three-candle object. It is the wrong one.

### 3.2 POI zones

```
DECISIONAL   on IDM break, each still-valid pullback carrying an FVG on the
             appropriate side becomes a POI.
             bullish structure → Demand.  bearish → Supply.

EXTREME      after BOS breaks and CHoCH forms, the final valid high/low of the
             PRIOR structure. Valid only if its candle range is unpenetrated.

BREAKER      an Extreme that has been broken WITH A JUMP.                [T2]

FLIP         same Jump precondition. The substitute zone, used when price fails
             to react at the Breaker after a CHoCH break.
```

**Direction rule.** Demand → uptrend → long only. Supply → downtrend → short
only. **A zone dies structurally**: once the BOS breaks, a CHoCH forms above the
Demand zones, so price must cross it before reaching them — the market has
already turned and the zones stop being extended.

### 3.3 POI range — this is what Internal structure is FOR

> "If an External Pullback contains a valid Internal Pullback, the POI range is
> defined using the Internal Pullbacks. If the External Pullback is not extensive
> and does not contain a valid internal structure, the POI range is derived from
> the External Pullback itself."

```
OrderFlow range  = the external pullback's full [edge, pivot]
OrderBlock range = the internal pullback(s) inside it — tighter, and the SL anchor
selection        = automatic: OrderBlock when valid internal structure exists
```

P7b stops being a display question here. No Internal structure, no tightened
zone, no low-risk stop distinction.

### 3.4 Mitigation — the 50% shortcut is forbidden

> "It is incorrect to assume or set an arbitrary and subjective level such as
> 50%." … "it uses the selected structural logic."

A zone is consumed, not merely touched, when price penetrates the structural
sub-object. **[T3]** decides which.

### 3.5 Liquidity Grab Levels

IDM, BOS, CHoCH as *levels*, not boxes. Price grabs the level (touches through
without a valid break), then **SCOB is checked**. The grab alone never enters.

### 3.6 SCOB — Single Candle Order Block

> Ch.21 closed the geometry.

```
candle  the last opposite-direction candle before the reaction        [T5]
level   its boundary facing the intended move                         [T4]
break   the SAME three-mode engine the structure uses:
          Shadow          wick through
          Body            close beyond
          Body & Sweep    level ratchets to each deeper candle, ✗ on each
                          abandoned one, until a close beyond the latest
behavior  Move With Deeper Candle  |  Keep First Penetration Candle
```

**No new break engine.** Mode 3 is `brkStep` in `BRK_SWEEP`, unchanged.
Without SCOB there is no entry, however valid the zone.

### 3.7 Stop loss

```
HIGH RISK  SL on the Order Block  — beyond the tightened zone, closer to entry
LOW RISK   SL on the Pullback     — beyond the OrderFlow, farther   (ref default)
break      BODY basis, plus Hidden Shadow                             [T10]
buffer     none. The body rule and HS replace it.
```

### 3.8 Active Price and the RR gate

```
ActivePrice = f(entry, stop, minRR, commission)      minRR default 0.5
```

**Active Price is where the trailing stop ARMS, not a target.** A 0.5 threshold
is not a 0.5R exit — it is the point at which the setup has enough room to be
worth taking net of costs, after which the trade stops being fixed-risk.

### 3.9 The obstacle check — rejects CONFIRMED setups

> "If Active Price is invalid or a structural obstacle blocks the path toward it,
> the setup is rejected even if SCOB has been confirmed."

Obstacles, named on the slide and in the text:

```
BOS level   |   valid opposite pullback   |   Breakout Zone            [T7]
            |   other broken structural levels
corridor    entry → Active Price
```

No §72 counterpart. The filter most likely to change a distribution rather than
shave it, because it removes setups that are structurally fine but have no room
to pay.

### 3.10 Sizing and exit

```
size    from evolving balance, stop distance, max-loss %, commission
exit    TRAILING STOP armed at Active Price                            [T6]
        initial stop before that
cap     optional Second Max Loss Cap (ships OFF)                       [T10]
```

**The realised loss can exceed the planned one.** The author's own worked
example: planned 1% ≈ $30, realised at exit 2.5% ≈ $75, because the stop is
judged on a body break and HS defers the exit another candle. That is the price
of Hidden Shadow on the stop and it must be measured, not assumed beneficial.

---

## 4. Policy register — the undefined cases

Same contract as the engine's P1–P8: an explicit default, a switch, and a
measurement. **No policy may introduce a number** — Ch.2's determinism
requirement has held through every round of this project and applies here.

### T1 — what makes a gap between two pullbacks
- **`no-overlap` (DEFAULT)** — the two pullback ranges do not intersect
- `edge-gap` — a strict gap between edge(n-1) and pivot(n)

Non-numeric by construction. "Sharp displacement" is never quantified in the
source, and a percentage would violate §2.

### T2 — what makes a "Jump" (gates Breaker and Flip)
- **`fvg-present` (DEFAULT)** — the break carries an FVG by T1
- `range-exceeds` — the breaking group's range exceeds the broken zone's

Reusing T1 keeps one displacement definition in the system rather than two.

### T3 — mitigation depth
- **`ob-touch` (DEFAULT)** — price touches the OrderBlock (the tight range)
- `ob-consume` — price crosses the OrderBlock entirely
- `of-touch` — price touches the OrderFlow (the wide range)

The reference distinguishes "a simple touch" from "actual consumption" but never
says which applies to which zone type. All three are structural; none is 50%.

### T4 — the SCOB level
- **`body` (DEFAULT)** — the candle's body boundary facing the move
- `wick` — its high/low

The slide draws the level at the body top of the red candle, but at slide
resolution body and wick are one or two pixels apart. Low confidence — measure.

### T5 — which candle is the SCOB
- **`last-opposite` (DEFAULT)** — the last opposite-direction candle before the
  first candle that closes back in the trend direction
- `deepest` — the candle that reached deepest into the zone

### T6 — what the trailing stop trails  ← **the largest hole**
- **`pivot` (DEFAULT)** — behind each newly confirmed pullback pivot
- `structure` — behind the most recent structural level (IDM/BOS)
- `mfe-fraction` — a fraction of MFE

**Completely unstated in the source.** Measured against a **fixed-R control**,
which is the honest baseline: if no trailing variant beats a fixed exit, that is
the result and it gets recorded as one.

### T7 — what a "Breakout Zone" is
- **`break-candle` (DEFAULT)** — the range of the candle that broke the level
- `level-line` — the bare price, no zone

The slide shows "Breakout Zone" twice at two different prices, so a broken level
leaves a zone rather than a line. Its extent is not stated.

### T8 — the with-trend conflict  ← **must be settled before Stage C**
- **`with-trend-only` (DEFAULT)** — Ch.15, literally
- `grabs-may-counter` — Liquidity Grab Levels are a separate family

Ch.15: *"We only enter trades in the direction of the prevailing trend."*
Ch.21's BOS-grab slide: bullish structure, sweep above BOS, arrow **down**.

Both are source. Reading 2 is already instrumented — `BOS near → Opp PB reach`
is exactly this event, 69% in the reference and 55% in ours — so it is
measurable rather than arguable. Until settled, with-trend only; a counter-trend
arm earns its own evidence, as §73 insists.

### T9 — entry price
- **`confirm-close` (DEFAULT)** — the close of the SCOB confirmation bar
- `zone-edge` — a limit at the zone boundary

`confirm-close` is the only one that is executable without assuming a fill.

### T10 — Hidden Shadow on the stop, and the cap
- **`hs-on` (DEFAULT, = reference)** — body break + HS, matching the shipped default
- `hs-off` — plain body break
- Second Max Loss Cap: **OFF by default**, matching the reference

The 1%-planned / 2.5%-realised example is the reason both arms must be measured
on the **realised-loss distribution**, not on win rate.

---

## 5. Build order and acceptance

Nothing merges on argument. Every stage has a test that can fail, and each is
gated on the one before.

### Stage A — the naked continuation. **No new subsystem.**

Every level exists in `riptide-lit-v2.pine` today. In `research/`, on real
candles, Pullback = **Body** (Ch.24: the strategy build's default, not the
structure build's Shadow):

```
long   bullish IDM taken, BOS locked above, with-trend only            [T8]
entry  IDM-break bar close
stop   below the IDM raid extreme                                      (§73)
arm    trailing stop at Active Price = +0.5R net of commission
exit   stop, initial or trailed                                        [T6]
```

Record per setup: **R at exit, MFE, MAE, bars held, Active Price reached?,
BOS-before-CHoCH, distance to BOS in R at entry, realised loss vs planned.**

The decisive number is neither win rate nor BOS hit rate. It is **MFE beyond
Active Price on the winners** — the entire source of edge in a trail-based
system, and what decides whether a 0.5R arming threshold with a raid-extreme
stop pays for the losers.

**Stage A can kill the strategy, and that is what it is for.** If the naked
version has no edge, POI + SCOB + obstacle filtering is decorating a losing
distribution — and each is weeks of work carrying its own inference risk.

Run the T6 sweep here too: three trailing variants against the fixed-R control.

### Stage A′ — settle T8
Same harness, counter-trend arm on BOS grabs. Cheap, and it unblocks Stage C.

### Stage B — FVG (T1), as a filter on Stage A
Does requiring an FVG improve the distribution, and by how much per setup lost?

### Stage C — POI zones
Decisional first (it is the one Stage A already touches via IDM). Extreme,
Breaker, Flip after, each measured **separately** — different objects, different
preconditions, and T2 gates the last two. Zone range per §3.3, which requires
Internal structure to be genuinely working.

### Stage D — SCOB (T4, T5), as a filter on Stage C
How many entries removed, and is the removed set worse than the kept set? A
filter that removes setups without improving the remainder is a cost, not a
feature — the same test that sank the structure-trend gate earlier in this log.

### Stage E — obstacle check (T7), on its own so its effect is attributable

### Stage F — sizing, HS-on-stop (T10), Second Loss Cap
Report the **realised-loss distribution**, not just the win rate.

### Then, and only then: Pine
`riptide-lit-v2-strategy.pine`, built on the frozen V2 engine, implementing only
what survived. Same acceptance discipline as the engine port: the Pine must
reproduce the research harness's trade list before any new behaviour is added.

---

## 6. Not importing

- **No 2R target.** §74 is explicit it is a different hypothesis, and the source
  uses no fixed target at all.
- **No 1.2–2.6% risk band.** §73 forbids it. This family earns its own.
- **No 50% mitigation.** Rejected by name.
- **No ATR, pivot length, or percentage band anywhere.** §2 determinism.
- **No order placement, exchange keys, or execution.** §75 and the project rule.

---

## 7. Next action

`research/lit_entry.py` — Stage A and Stage A′ on ZEC and the wider universe,
reporting the R distribution, MFE/MAE, Active-Price reach rate, realised vs
planned loss, and the T6 trailing sweep against a fixed-R control.

No strategy Pine until Stage A returns a number worth building on.
