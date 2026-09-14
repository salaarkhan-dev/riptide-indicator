# Riptide LIT Structure — v0.1 → v0.2

Pine only. The production Riptide strategy and bot are untouched.

Files: `riptide-lit.pine` (the indicator), `research/lit_v02.py` (the engine
transcribed so it can be run over real candles), `research/lit_v02.out` (the
measurements quoted below).

---

## 1. The headline: the deviation is gone, and it was covering a different bug

v0.1 contained a comment saying *"CORRECTION to the reference text"* and moved
a correction's confirmation level down every time the correction made a deeper
low. The brief is right to strike it, and it is gone.

But it was a patch over a real defect, and the defect was not in the
confirmation rule. **v0.1 ran a demand tracker and a supply tracker
permanently and in parallel, feeding one shared pivot stream.** The documented
algorithm is trend-relative — *assume the parent structure is bullish*, ride
the impulse, detect the correction against it. Running a demand tracker
through a sustained downtrend opens a correction that can never confirm,
because price never returns to the level. Measured: one correction stayed open
for **9,200 bars**, and Main produced 25 pivots where it should produce
hundreds.

v0.2 orients each detector to its own context's direction and re-initialises
it on a trend flip. With that fixed, the confirmation level stays **fixed at
the correction-start candle exactly as documented** and nothing starves.

This is the diagnosis §0 asked for: the fault was *impulse tracker lifecycle
and scope initialisation*, not the pullback rule.

---

## 2. v0.1 bugs found

| # | Bug | Evidence |
|---|---|---|
| 1 | Detectors ran unoriented and in parallel, so corrections opened against the trend never confirmed | one correction open 9,200 bars; 25 pivots vs ~1,600 |
| 2 | The confirmation level chased price down to compensate | removed |
| 3 | A new IDM could be published while a BOS was still unresolved | phase gate now permits IDM only in DISCOVER and TRACK; invariant I6 |
| 4 | A level could be broken on the bar that created it | every level carries `createdBar`; invariants I8, I9 |
| 5 | Main / Internal / Deep consumed one shared pivot stream | each depth now owns an oriented detector, direction, phase and history |
| 6 | Retired inducements were drawn as fully labelled lines | a taken IDM now leaves a small `x` |
| 7 | Every active label was moved to `bar_index` each bar, piling up on the current candle | labels anchor at 70% along their own segment |
| 8 | Internal levels were faint cyan, invisible on a light chart | depth graded by width and transparency on a solid palette |
| 9 | Statistics were computed from an uncalibrated event population | off by default, reduced to counts, rates withheld |

---

## 3. Something I tried that does not work, and it closes a route

The brief requires three genuinely independent depths, forbids pivot lengths
(§15) and forbids "fake hierarchy using the same events with different resets".
The obvious remaining mechanism is granularity, so I tried chaining the
inside-bar normalizer — Deep on raw candles, Internal on Deep's output, Main on
Internal's.

**It cannot work. The normalizer is idempotent.** A group closes on the bar
that *breaks* its range, and that bar opens the next group — so group N+1
always breaks group N by construction. Two different emit rules were tried
(the mother's own OHLC, then the merged group) and both filtered **0.0%** above
the first pass.

With granularity closed and length parameters forbidden, **scope is the only
mechanism left**, and scope necessarily means resets. What makes it real
rather than decorative is that each depth runs its *own oriented detector*: a
bull-oriented and a bear-oriented detector on the same candles find different
corrections, and a child re-bootstrapped inside its parent's range runs shorter
legs with its own direction.

Measured mirroring — a child level at the same price and same anchor bar as one
its parent published:

```
main -> int     2538 child levels    442 identical    17.4%
int  -> deep    4175 child levels   1218 identical    29.2%
```

Real hierarchy, not duplication. **The 29.2% is higher than I would like and is
the top calibration item.**

---

## 4. Architecture

```
Norm  (one, shared)     mother range -> merged group candle
  |
  +-- Ctx MAIN     own PBDet (oriented) -> IDM / BOS / CHoCH -> phase
  +-- Ctx INTERNAL own PBDet, resets when MAIN resolves a boundary
  +-- Ctx DEEP     own PBDet, resets when INTERNAL resolves a boundary

Brk      one break engine: Shadow / Body / Body & Sweep + Hidden Shadow
PBDet    two-phase correction tracker, oriented, fixed confirmation level
Lvl      price + anchor bar + createdBar + its own Brk
Renderer presentation only — infers nothing
```

Per-bar order, per context: reset → normalizer → detector → running extremes →
publish or cache the correction → IDM → BOS → CHoCH → invariants. **At most one
major transition per bar**, enforced by a `moved` flag.

---

## 5. Behaviours removed

- The migrating pullback confirmation level.
- The shared `pivLo`/`pivHi` stream feeding all three depths.
- IDM publication during `PH_SEEK` / `PH_LOCK`.
- Same-bar evaluation of a newly created level.
- The single flat pullback-zone family (now one per depth, nesting).
- First-passage percentages on the chart.

---

## 6. Measurements — 8 symbols, 120 days, Min15

```
invariant violations          0   at every depth, every symbol
same-bar ambiguity            0
Main BOS locks: broke 71%, abandoned 27%, still open 2%
median lock distance       1.43%

depth    pivots    IDM   taken   BOS   flips   resets
main       1574    567     278   198      95        0
int        3052   1513     703   322     114      571
deep       4383   2567    1210   398     100     1139
```

Against the only quantitative fixture available — the reference showed **23
taken inducements per ~2000 bars on ZEC 15m at its deepest degree**, splitting
56.5/43.5 (recorded in `research/lit.py` before the premium subscription
lapsed):

```
depth   taken   per 2000 bars   vs ref   BOS-first   n
main       19             3.3    0.14x       70.6%  17
int        84            14.6    0.63x       63.8%  47
deep      170            29.5    1.28x       62.9%  35
```

Deep sits at **1.28x** the reference count against v0.1's ~4x, and its
first-passage split is 62.9/37.1 against the reference's 56.5/43.5. §37
predicted materially fewer pullbacks and IDMs after the fix; that is what
happened, at every depth.

---

## 7. Unresolved assumptions

1. **Child scope reset** — the mechanism is scope because granularity is
   provably unavailable, but the exact reset condition (parent boundary
   resolution) is inferred. Deep's 29.2% mirroring says this is not finished.
2. **Leg restart** — survives IDM migration as documented (invariant I7);
   restarts at the CHoCH point on a BOS break and a flip, because a leg that
   never restarts makes BOS the all-time extreme and it can never break.
3. **Bootstrap** — both orientations run until one confirms.
4. **Equality is not a break**; both-sides candles close the group without
   guessing an order; Body & Sweep keeps its migrated level after a Hidden
   Shadow rejection.

---

## 8. Calibration — ZEC 15m

**The screenshots were not attached to this round**, so items 1–20 of the §27
checklist cannot be ticked off visually here. What has been checked is the
numeric fixture above and the invariant set. The checklist, in the order to
work it:

1–3 Main / Internal / Deep trend · 4–7 Main pullback count, start and end
bars, pivot · 8–10 IDM creation, migration, break · 11–14 BOS and CHoCH price
and break · 15 Strong/Weak · 16–19 Internal zones, iIDM count, iBOS, iCHoCH ·
20 Deep last.

Start in **MAIN ONLY** mode (Engine → Development mode). Do not look at
Internal until Main's pullback count and IDM geometry match.

---

## 9. UI changes

- Depth graded by **width and transparency on a solid palette** — Main width 2
  at 0% fade, Internal width 1 at 25%, Deep width 1 at 50%. Legible on
  TradingView Light, which v0.1's faint cyan was not.
- Labels anchored at **70% along their own segment**, not at `bar_index`.
- A taken inducement leaves a small **`x`**, not a labelled line.
- Pullback zones nest: Main 88% fill, Internal 92%, Deep 95% and off by
  default.
- History defaults cut to 12 / 8 / 4 per depth and 6 zones — the object budget
  is what keeps the chart readable, not just what keeps it under 500 lines.
- Deep off by default while calibration is ongoing.

---

## 10. Debug

`Panels and debug → Debug panel`, then pick the depth. It shows direction,
phase, mother range, inside-bar rate and both-sides count, tracker high/low,
pullback state with its start bar and fixed confirmation level, leg start,
active IDM, latent pullback, Hidden Shadow state, last event, and counters for
pullbacks / IDMs / taken / BOS / CHoCH / flips / latent activations.

**The row that matters is INVARIANTS.** It reads `all clean` or a count and the
name of the last violated rule. A non-zero count is a defect in the engine, not
a display problem. Twelve invariants are checked continuously; the Python
harness reports the same set across all symbols at once.

---

## 11. Still open

- Not compiled. There is no Pine compiler in this environment; the logic is
  validated in `research/lit_v02.py`, the syntax is not.
- The §27 visual checklist needs the ZEC screenshots.
- Deep's 29.2% mirroring.
- No Python bot port — that is explicitly a later phase.

---

# v0.3 diagnosis — why the giant pullback box exists

Measured, not inferred. `research/lit_v02.py` over ZEC 15m, 120 days.

## The box is not a drawing bug

`zone()` already draws `left = pb.startBar, right = pb.confirmBar` and freezes
at creation, which is what §16 asks for. §12's hypothesis — that a structural
range is being used to draw the box — is wrong; I checked before changing
anything.

The correction genuinely ran that long:

```
main  demand (bull ctx)   n  72   median  6   p90  71   p99 604   MAX  666
main  supply (bear ctx)   n  39   median  1   p90  21   p99 167   MAX 7403
```

Median **1 bar**, p90 21 — and one at **7,403**.

## The correction is frozen because the CONTEXT is frozen

```
longest Main phase run:   4917 bars in PH_BOUNDARY_LOCK, ending bar 9273
longest open correction:  7402 bars, bars 1870..9272
```

The same event. §1 is right that pullback lifetime must be separate from
structural lifetime, but the coupling is not in the detector — the detector is
stuck oriented the wrong way because the context cannot leave the lock.

This also explains §13-E and §14: across those 4,917 bars nothing confirmed, so
**no latent pullbacks accumulated**, so there was nothing to reuse when the lock
resolved. The missed IDMs and the giant box are one defect, not two.

## Two compounding causes, both real

Dumping both long locks:

```
LOCK bars 1934..9273  (4917 bars)
  BOS   base 250.00   touched  0 times   sweeps 0   drift 0.0%
  CHoCH base 644.48   touched  5 times   sweeps 2   drift 0.6%
  close ranged 342.53 .. 648.99

LOCK bars 9411..10541  (704 bars)
  BOS   base 859.43   touched 72 times   sweeps 4   drift 3.4%
  CHoCH base 730.61   touched  0 times   sweeps 0   drift 4.8%
  close ranged 760.24 .. 914.20
```

**A. The Body & Sweep ratchet is unbounded.** Each failed wick migrates the
active level further away and nothing ever resets it. Lock 2 is the signature:
the BOS was touched **72 times**, swept 4 times, and its active level had
walked **3.4%** beyond its base — 859 base, 889 active. A level price keeps
testing becomes progressively harder to break, which inverts the intent. §6 of
the brief states the migration rule and says nothing about when it ends.

**B. A BOS locked at the full leg extreme can be unreachable, and in
PH_BOUNDARY_LOCK nothing may supersede it.** Lock 1: BOS at 250 while price
ranged 342–649 — 28% away, **touched zero times in 4,917 bars**. In PH_SEEK a
later IDM break re-locks a nearer BOS (measured in v0.2: 31% of locks were
superseded that way). §8 correctly forbids that in PH_LOCK, so a far BOS there
is terminal until the CHoCH breaks — and the CHoCH is being walked away by (A).

Invariant 11 was verified independently and is clean: BOS and CHoCH are always
on the correct sides. Lock 1 was a bearish context, so BOS below and CHoCH
above is correct geometry — the level is unreachable, not mis-sided.

## What this means for the fix

The repair belongs in boundary-lock resolution and in the sweep engine, not in
the pullback detector. Neither rule is stated by the reference, so both are
[INF] and both need deciding before v0.3 is written:

1. When does a migrated sweep level reset? Candidates: on a close back beyond
   the base level, or when the structural phase changes.
2. What resolves a lock whose BOS was locked unreachably far? Candidates: the
   BOS is not the full leg extreme but the extreme of the segment the IDM
   belonged to; or price leaving the BOS↔CHoCH range entirely re-scopes the
   context.

**Regression fixture:** the correction-lifetime distribution above. `MAX` should
fall to the p99 range (~170 bars) without any size, ATR or bar-count filter.

---

# v0.3.1 diagnostics — the decision gate is open

Both briefs name a root cause and ask for verification first. All three are
falsified. Measured on ZEC 15m, 120 days, Main depth.

## Q2/Q3 — the pullback tracker DOES reset after confirmation

```
cycles 111   median 3   p90 71   p95 154   p99 604   MAX 7403 bars
cycles longer than 300 bars: 4
```

111 distinct cycles with a median of **3 bars**. The v0.3.1 §5 hypothesis —
tracker not restarted, subsequent corrections swallowed by the old pullback —
does not hold: `detStep` already sets `state := PB_IMPULSE` and reseeds
`trkHi/trkLo` from the confirmation bar, and the cycle count proves it works.
**4 of 111 cycles are pathological, not most of them.**

## Q1 — the PullbackObserver is NOT frozen by the lock

It runs on every analytical bar regardless of phase, and a confirmed
correction is cached as latent whenever the phase forbids publishing it. The
third long lock proves the path works end to end:

```
lock  569..986   (417 bars)   latent PB confirmed inside: 0
lock 1934..9273  (7339 bars)  latent PB confirmed inside: 0
lock 9411..10541 (1130 bars)  latent PB confirmed inside: 5
```

Locks 1 and 2 cached nothing not because the observer was gated, but because
the detector was sitting inside one unconfirmed correction for the whole span.

## Q4 — the leg anchor was NOT stale

```
lock 1934..9273   legStart 644.48 at bar 1649   BOS 250.00   CHoCH 644.48
                  leg anchor age at lock start: 285 bars
```

285 bars old, and `legStart == CHoCH` exactly — which is correct by
construction, since a BOS continuation sets the new leg anchor to the newly
validated opposite extreme. The anchor history confirms it moves on every BOS
break (breaks 7→13, a new anchor each time). **The 250 BOS did not come from a
stale anchor.** It is the genuine lowest low from bar 1649 through the IDM
break, which is the documented rule applied correctly.

## What is actually happening

All four pathological cycles occur inside a boundary lock:

```
PB#64   bars  1870..9273   len 7403   phase lock
PB#79   bars  9497..10163  len  666   phase lock
PB#25   bars   382..986    len  604   phase lock
PB#81   bars 10187..10538  len  351   phase lock
```

A bearish context in a long range: BOS sits at the leg's true low (250, reached
early and then left far below), CHoCH sits at the leg's high (644.48) where it
is repeatedly swept but never body-broken. Price oscillates between them. A
supply correction opens inside that range and its frozen level — the start
candle's low — is never revisited, so it waits for the flip rather than
confirming. PB#64 ended by reorientation on the flip, not by confirmation.

**The documented rules produce this lock.** It is not a lifecycle defect.

## The decision gate (lock brief §10) is open

The gate says: only if pathological locks remain after (a) continuous latent PB
detection, (b) correct BOS-cycle legStart reset, (c) correct BreakTracker
ownership. All three are verified present:

- (a) verified above — the observer is unfrozen and latent caching works.
- (b) verified above — the anchor is re-established from the new valid opposite
  extreme at every BOS break.
- (c) verified by inspection — `setLvl` calls `arm`, which sets
  `base = act = px` and clears the pending and sweep state, so a replaced level
  never inherits a migrated threshold.

The pathological locks remain. Per §10 the next step is an EXPERIMENTAL
comparison of the two undocumented alternatives — Body & Sweep reset semantics,
and BOS range semantics — measured against the fixture and not silently
adopted.

Distributions to report before and after, per §9, with no target value:
pullback duration and lock duration, median / p90 / p95 / p99 / max.

---

# v0.3.2 — the 2x2 factorial. Verdict: keep Arm A.

`research/lit_exp.py`, `research/lit_exp.out`. 8 symbols, Min15, 120 days.
Arm A is the untouched engine and is bit-identical to everything measured
before. Nothing else differs between arms.

## Gate 1 — invariants

All four arms: **all clean**, zero ambiguous bars. Nothing disqualified here.

## Gate 5 — event population, against the reference fixture

```
arm             deep taken  per 2000   vs ref  BOS-first  main PB  main IDM
A control              170      29.5    1.28x      62.9%      106        54
B sweep only           205      35.6    1.55x      55.1%      114        60
C bos only             196      34.0    1.48x      64.3%      108        54
D both                 229      39.8    1.73x      58.8%      116        60
```

**Every experimental arm moves further from the reference count.** A is closest
at 1.28x; D is 1.73x with 58% more taken inducements than A.

One point for B: its first-passage split, **55.1%**, is the closest any arm gets
to the reference's 56.5% — A is 62.9%. That is a real mark in B's favour and it
is the only one.

## Gate 4 — the counterfactual replay, and it is decisive

```
ZEC lock from bar 1934   dir bear   BOS ctrl 250.00   BOS seg 250.00   CHoCH 644.48
    A control      survives the window
    B sweep only   survives the window
    C bos only     survives the window
    D both         survives the window
```

**No arm resolves the lock that motivated the whole experiment.** Both rules
fail gate 4 on the case they were designed for.

B does help elsewhere, materially:

```
ZEC lock from bar 9411   A resolves +1130 bars via BOS
                         B resolves   +85 bars via BOS
ZEC lock from bar   27   A resolves   +71 bars      B  +19 bars
```

and it eliminates threshold drift outright (max drift 2.23% -> 0.0%, sweep
chain max 6 -> 0). C is close to inert: the segment extreme equals the leg
extreme in almost every lock observed (250/250, 497.30/497.30, 690/690,
859.43/856.13), so the rule rarely changes the level it was meant to change.

## Why the sweep-reset rule cannot fire where it is needed

Isolating the 644.48 CHoCH from bar 1934 onward:

```
after bar 1934: 6306 analytical bars, max HIGH 1296.37, max CLOSE 1285.56
closes above the 644.48 base: 1390

ratchet + HS   (Arm A)        breaks at 9273 (+7339)   sweeps 2   HS rejections 1
reset   + HS   (Arm B)        breaks at 9273 (+7339)   sweeps 2   HS rejections 1
ratchet, no HS  EXPERIMENTAL  breaks at 9269 (+7335)   sweeps 1   HS rejections 0
reset,   no HS  EXPERIMENTAL  breaks at 9269 (+7335)   sweeps 1   HS rejections 0
```

Price closed above the base **1,390 times** and the level still did not break
for 7,339 bars. The cause is a **single unbounded ratchet jump**: one sweep on a
bar with a very large high walks the threshold from 644 to near the top of the
subsequent rally, and nothing brings it back.

The proposed reset is specified to fire when price closes back on the ORIGINAL
side of baseLevel. In a sustained move past the level price never returns
there, **so the reset cannot fire in exactly the situation that motivated it**.
That is a property of the rule as specified, not of this implementation.

Hidden Shadow is not the blocker either: disabling it moves the break four
bars, from 9273 to 9269.

## Verdict

Keep **Arm A**, the documented control. Neither experimental rule passes the
decision hierarchy: both fail gate 4 on the motivating lock and all four
experimental configurations fail gate 5. Arm B is not adopted, but it is worth
keeping on the shelf - it is the only arm that improves the first-passage match
and it demonstrably fixes the milder locks.

The switches stay in the engine, default OFF, so any arm is one flag away.

## The sharper hypothesis this produced

The ratchet's defect is not that it lacks a reset - it is that **one sweep can
move the threshold an unbounded distance**. `activeLevel = high` accepts any
excursion, however large, as "the level that must now be body-broken". A
bounded formulation - the furthest failed wick within the retest that produced
it, rather than any subsequent high - would be a different rule and is NOT
implemented or tested here. It is recorded as the next candidate, and it needs
reference examples before it is worth building.

## Regression case, kept

PB#64, ZEC 15m bars 1870..9273, ends by REORIENTATION on a trend flip rather
than by confirmation. Still true in all four arms. Any future rule must explain
why it resolves differently, not merely shorten the box.

---

# v0.3.3 — Body & Sweep forensics. No implementation bug, and a correction.

Diagnostics only. Arm A is bit-identical; the only file change is debug-mode
drawing and one debug table row.

## First: I have to correct my own last report

Last turn I reported the pathological CHoCH as "a single unbounded ratchet
jump" that walked the threshold from 644 to roughly 1296. **That was an
artifact of my own diagnostic, not the engine.** The shadow tracker in that
script was re-armed at bar 1934 and then scanned to the end of the data — which
is mostly *after* the level had already broken at 9273. The window was wrong,
so the figures drawn from it ("max HIGH 1296.37", "1,390 closes above the
base") described a period the real tracker never saw.

The engine never did that. The real migration sequence is small.

## 1. The actual sweep sequence

```
   bar  raw candle class  group H  group L   close   act before  act after  event      n
  1796  outside-up         527.36   510.58  517.62       527.00     644.48  (level created)
  9268  outside-up         647.29   621.58  639.09       644.48     647.29  SWEEP      1
  9269  outside-up         659.15   636.99  648.32       647.29     647.29  HS-PENDING 1
  9270  outside-down       659.24   645.15  646.70       647.29     647.29  HS-REJECT  1
  9271  outside-up         648.13   634.73  645.48       647.29     648.13  SWEEP      2
  9272  outside-down       650.52   644.11  648.99       648.13     648.13  HS-PENDING 2
  9273  break confirmed
```

Two sweeps. **644.48 → 647.29 (+0.4%) → 648.13 (+0.1%)**, total drift 0.6%.
The bar-1796 row is the level being created by `arm()`, not a sweep — the
sweep counter is 0 there.

## 2. Sweep-candle eligibility — clean

Every candle that moved the threshold is classified `outside-up` against the
owning normalizer's mother range at the moment it was consumed: an analytical
bar at that depth. **No candle suppressed as internal ratcheted the level.**

## 3. Temporal eligibility — clean

The CHoCH was created on bar 1796 and `ready()` gates evaluation on
`i > createdBar`. On the creation bar the CHoCH block is additionally unreachable
because `moved` is already true from the BOS break that created it — doubly
protected. My first pass reported VIOLATED twice; both were the diagnostic
recording the creation event itself as an interaction, not the engine
evaluating early.

## 4. Why the level held for 7,472 bars

```
between bar 1796 and 9268:
  highest group HIGH reached: 625.25   vs base 644.48
  group closes above the base: 0
```

**The level was never touched.** No sweep could occur because price did not
reach it. Price sat between BOS 250 below and CHoCH 644.48 above and came
within 19 points of the upper boundary without tagging it, for 7,472 bars.

## 5. Is there an implementation bug?

**No.** Sweep eligibility is clean, temporal eligibility is clean, migration is
0.6% across two sweeps, and Hidden Shadow cost four bars. The long lock is a
genuine 7,000-bar range between two correctly-placed structural boundaries.

Which also falsifies the hypothesis I proposed last turn — a bounded ratchet
would change nothing here, because the ratchet never moved.

## 6. Debug visualisation added (§4, §5)

Debug mode now draws the Body & Sweep threshold: a faint dashed BASE, a
stronger dotted ACTIVE, and an `S1/S2/...` mark at each wick that moved it, plus
a table row carrying base, active, drift %, sweep count and age for both BOS
and CHoCH.

Setting expectation honestly: on measured data the two lines will sit almost on
top of each other, because the drift is 0.6%. The visual was requested to make a
large migration obvious — there is no large migration to see. A visible gap on
some other chart is the interesting case, and now it is visible when it happens.

## 7. The calibration question has changed

It is no longer "does Index Algo ratchet its threshold far after a big failed
wick?" — ours does not ratchet far. The open question is now:

> When price ranges for thousands of bars between a BOS and a CHoCH, touching
> neither, does Index Algo hold both boundaries for the whole range as we do,
> or does it re-scope the structure at some point?

That is a question a screenshot of the 1796–9273 region answers immediately,
and no amount of further instrumentation on our side can.

---

# v0.3.4 — structural re-scope forensics. Diagnostics only.

Arm A bit-identical. No behavioural change.

## 1. Are structural range and external-pullback scope the same lifetime?

Three concepts, and the code has **two of the three**:

| | concept | object in the code | own lifetime? |
|---|---|---|---|
| A | structural range, BOS ↔ CHoCH | `x.bos`, `x.ch` — each a `Lvl` with its own `createdBar` and `Brk` | yes |
| B | order-flow / external-pullback scope | **does not exist** | — |
| C | pullback event range, PB_START → PB_CONFIRM | `x.det` — `startBar`, frozen `conf`, reset every cycle | yes |

**A and C are correctly separate. B is absent, and is implicitly identified
with A.** The conflation is one line of consequence: `x.det` is re-oriented
only when `x.dir` changes — that is, only on a CHoCH break — so order-flow
direction is *slaved to structural trend*. There is exactly one correction in
flight per depth and its orientation is the structure's orientation.

That is precisely what §4 warns against, and it is the whole finding.

## 2. Main corrections inside lock 1934..9273

```
start 1870  end 9273  len 7403  conf level 291.89  dir -1  status REORIENTED
-> 1 Main correction across 7339 bars
```

One. It never confirmed — it ended when the trend flip re-oriented the
detector out from under it.

## 3. Diagnostic order-flow segmentation of the same window

A parameter-free swing walker, run diagnostically and never fed to the engine
(a swing extreme is confirmed when price takes the opposite extreme of the
candle that made it):

```
2051 segments inside the lock.  median length 2 bars, max 85.
seg 1  1935..1937  up    hi 399.62  lo 384.17
seg 2  1937..1941  down  hi 398.28  lo 377.84
seg 3  1941..1942  up    hi 397.05  lo 384.00
...
```

**1 versus 2,051.** Stated honestly: 2,051 at a median of 2 bars is raw swing
flow, far finer than the handful of External Pullbacks the reference draws. It
is not a candidate segmentation — it is the opposite extreme, and it brackets
the answer. Main sits at one end, raw swings at the other, and the reference
sits between them.

## 4. Reference geometry comparison

**Not possible this round — the ZEC screenshot was not attached.** Items 7.1–7.n
cannot be filled in. This is now the fourth brief in a row whose visual
comparison step is blocked on the same missing image; the numeric fixture
(23 taken inducements per 2000 bars, 56.5/43.5) is all that has been available.

## 5. Internal activity during the Main lock

```
int PB       179
iIDM          24
iBOS          24
iCHoCH         1     (counting artifact: only the FIRST is a "create",
                      the rest register as "move")
int flip      17
```

**Yes — Internal completes full LIT cycles repeatedly while Main never moves.**
24 inducements taken and 24 BOS breaks, and the internal trend changed
direction 17 times, all inside one frozen Main boundary lock.

## 6. Is there any parent/child promotion mechanism?

**No.** The coupling is strictly one-directional:

```python
resetInt, resetDeep = rMain, rInt     # parent resolution resets the child
rMain = ctx_step(main, False, ...)    # Main is ALWAYS called resetMe=False
```

Nothing a child does can reach its parent. There is no promotion, no
re-scope, and no order-flow scope object to promote into.

## 7. Do the geometries support H1 or H2?

**H1 — parent BOS/CHoCH stays valid while the external pullback / order-flow
scope is replaced: SUPPORTED.** The structural boundaries were correct
throughout (never touched, verified last round), yet the flow inside them
reversed 17 times at Internal degree and produced 179 confirmed corrections,
while Main held one correction open for 7,403 bars. Structural-range lifetime
and order-flow lifetime are demonstrably different quantities on this data.

**H2 — a completed child cycle may define the next parent external-PB scope
without a parent CHoCH reversal: CONSISTENT, NOT DISTINGUISHED.** 24 complete
Internal cycles with Main unchanged is exactly what H2 predicts. But it is also
exactly what H1 predicts, because the same 24 cycles are the order flow. **This
data cannot separate the two hypotheses**, and choosing between them decides
whether the re-scope trigger is order flow itself (H1) or a completed child
structural cycle (H2).

What would separate them: a reference window where order flow changes direction
*without* Internal completing a full cycle. If the reference draws a new
External Pullback there, H1; if not, H2.

## 8. No behaviour changed

Neither hypothesis is implemented. Arm A is untouched and remains canonical.

---

# v0.3.5 — H1 vs H2 discrimination against the ZEC 15m reference

Visual forensics. **No behaviour changed.** Arm A bit-identical.

## 0. A correction to my own framing first

The pathological lock I have been dissecting for three rounds — bars 1934–9273
— maps to **06 Jun → 21 Aug**. The screenshot is **08 Sep → 14 Sep**, which is
bars 10958–11518. Same phenomenon, different instance. Everything measured
about bar 1934 stands, but it was never the box on your chart.

Here is what our engine does in the window you are actually looking at:

```
09 Sep 05:30  MAIN PB 221 bars · IDM published
09 Sep 07:45  MAIN PB   8 bars · IDM published
09 Sep 08:30  MAIN PB   1 bar  · IDM published
09 Sep 11:15  MAIN PB   7 bars · IDM published
09 Sep 15:15  MAIN PB   1 bar  · IDM published
09 Sep 15:30  IDM taken
09 Sep 15:45  MAIN PB   1 bar
10 Sep 23:15  MAIN PB 118 bars · TREND FLIP
11 Sep 02:30  MAIN PB  10 bars · IDM published
11 Sep 04:00  MAIN PB   4 bars · IDM published
11 Sep 04:15  IDM taken
      ... then nothing for ~250 bars, to the end of data
final Main state: bear, phase LOCK
```

Main cycles perfectly well on 9 Sep — six corrections, five inducements. It
then **goes silent from 11 Sep 04:15 onward** and holds one open correction to
the right edge. That silence is the giant box.

## A. Structural-boundary lifetime vs external-PB lifetime

**CONFIRMED, high confidence.** The reference's Main `Choch` at ≈1295 is drawn
as one unbroken line from the HH on 9 Sep all the way to the right edge on
14 Sep — five days — while beneath it I count **eight to ten separate
pullback boxes**. The boundary outlives the corrections by an order of
magnitude.

## B. Visible reference external PB cycles under live old boundaries

Ordered ledger, approximate, from the image:

| # | when | dir | approx band | ownership | conf |
|---|---|---|---|---|---|
| REF-1 | 8 Sep 06:00 → 9 Sep 11:00 | bull | 1110–1260 | MAIN_EXTERNAL | HIGH |
| REF-2 | 8 Sep 18:00 → 9 Sep 06:00 | bull | 1140–1185 | INTERNAL (nested in REF-1) | MEDIUM |
| REF-3 | 9 Sep 18:00 → 20:00 | bear | 1255–1295 | MAIN_EXTERNAL | HIGH |
| REF-4 | 10 Sep 00:00 → 04:00 | bear | 1230–1265 | MAIN_EXTERNAL | MEDIUM |
| REF-5 | 10 Sep 06:00 → 12:00 | bear | 1225–1260 | MAIN_EXTERNAL | MEDIUM |
| REF-6 | 10 Sep 12:00 → 18:00 | bear | 1225–1250 | INTERNAL (nested, darker) | MEDIUM |
| REF-7 | 11 Sep 00:00 → 06:00 | bear | 1115–1160 | MAIN_EXTERNAL | MEDIUM |
| REF-8 | 12 Sep 12:00 → 18:00 | bear | 1150–1175 | MAIN_EXTERNAL | MEDIUM |
| REF-9 | 13 Sep 06:00 → 12:00 | bear | 1140–1165 | MAIN_EXTERNAL | MEDIUM |
| REF-10 | 13 Sep 12:00 → 14 Sep | bear | 1100–1130 | MAIN_EXTERNAL | MEDIUM |

**Roughly 8 external cycles under one unchanged Main CHoCH.** Our engine
produces **one** open box over REF-7 through REF-10.

## C / E. H2 — FALSIFIED

The discriminator is REF-3 → REF-6, the run from 9 Sep 18:00 to 10 Sep 18:00.
Four successive external bearish corrections form there, and **no internal
structural label appears anywhere in that region**. Every `iIDM`, `iBOS`,
`iChoch`, `iiDM`, `iiChoch` in the image sits from ≈11 Sep 18:00 rightward.

If a completed Internal cycle were required to promote each new external
pullback, those four boxes could not exist. They do.

Confidence MEDIUM-HIGH rather than certain: absence of a drawn label is weaker
evidence than presence of one, and Internal drawing could in principle be
suppressed in that region. But combined with D below it is decisive enough.

## D. H1 — SUPPORTED

The reference shows **three separate unprefixed `IDM` levels** — ≈1205 on
9 Sep, ≈1070 on 11 Sep, ≈1105 on 14 Sep — while exactly one Main `Choch` at
1295 persists across all of them. Main's inducement cycles at least three
times under one unchanged Main structural boundary, with Main external
pullbacks cycling alongside.

That is H1 stated exactly: order flow has its own lifecycle underneath a
persistent structure.

## F. Promotion trigger

**None is needed, and none is supported.** Order flow cycles on its own
pullback confirmations. Of the §13 candidates, **OF-1** (a confirmed
opposite-direction pullback re-orients the flow) is the only one required to
explain the geometry; OF-3/4/5/6 all presuppose the child dependency that
REF-3→REF-6 falsifies. I cannot cleanly separate OF-1 from **OF-2** (the flow
tracker's opposite side being taken) from one screenshot — they coincide on
every transition visible here.

## G. Depth shift — SUPPORTED

```
reference        Main structure  →  Main ORDER FLOW  →  Internal  →  Deep
riptide today    Main structure  →  (missing)        →  Internal  →  Deep
```

With the order-flow layer absent, Internal is doing the job the reference's
Main order flow does, and Deep is doing Internal's. That is exactly the
`iBOS` ↔ `iiBOS` mismatch, and it is one level in size. Our Internal has taken
84 inducements over this data while our Main took 2 in the screenshot window —
the work is being done, just one degree too deep.

## H. Where IDM belongs

**OrderFlowState, not StructureState.** Evidence in D: three Main IDM levels
under one Main CHoCH. BOS and CHoCH belong to structure; IDM and the external
pullback belong to flow.

## I. Minimal architecture — DESIGN ONLY, not implemented

```
MainStructureState      trend, valid high/low, BOS, CHoCH     (unchanged)
MainOrderFlowState      flow direction, external PB, pivot, IDM
InternalStructureState  iBOS, iCHoCH
InternalOrderFlowState  internal PB, iIDM
DeepStructureState      iiBOS, iiCHoCH
```

Minimum state for OrderFlowState, per §11 — it is NOT another BOS/CHoCH
machine: a direction, an impulse tracker pair, one correction in flight, the
last confirmed pivot. It re-orients on OF-1/OF-2 and never consults the
structural phase. `PH_BOUNDARY_LOCK` continues to gate IDM *publication* only.

## J. Open questions before any of this is built

1. **OF-1 vs OF-2** need a window where they disagree.
2. **The calibration fixture may be wrong by ~4x.** The reference stat table
   reads `IDM → BOS touch  Total 24`. If that total is window-scoped it means
   ≈24 taken inducements in ≈600 bars — about 80 per 2000 — where I have been
   calibrating Main against 23 per 2000 from `research/lit.py`. Worth
   confirming whether that table counts the visible window or all loaded bars
   before any target is set against it.
3. Box ownership above is MEDIUM confidence; several boxes could be Internal.

---

# v0.3.6 — MainOrderFlowState experiment. Both minimum models REJECT.

`research/lit_of.py`, `research/lit_of.out`. **No Pine written, no canonical
change.** The reason for that is below and it is deliberate.

## What was built

`OrderFlow` — owns flow direction, the impulse tracker, the live external
pullback, its pivot and the IDM. It holds no reference to a `Ctx`, so
**OF-INV-1 and OF-INV-2 hold by construction**: it cannot mutate structural
direction, BOS or CHoCH even by accident. OF-INV-3 (every IDM originates from a
confirmed external PB pivot), OF-INV-4 (confirmed PBs are appended and never
touched) and OF-INV-5 (boundary lock gates publication, never the flow) are
enforced in the code path. The canonical engine is read, never written.

The brief settles the architecture but not **what orients the flow**, and §8
permits exactly two readings. Both were built and measured:

- **OF-A** — the flow carries the structural direction; only the *cycle* is
  decoupled.
- **OF-B** — OF-1 taken literally: a completed opposite-direction pullback
  re-orients the flow.

## Result — ZEC 15m, fixture window 08 Sep → 13 Sep

```
CONTROL          9 external PB in window   open PB at right edge   255 bars

OF-A             8 external PB in window   18.2 per 2000 bars
                 IDM create 19  migrate 34  taken 19   flow changes 6
                 PB duration median 3  p90 21  p99 221  max 666
                 longest silent interval 7422 bars   SILENT TAIL 256 bars
                 §20: REJECT - leaves the problem region silent

OF-B             6 external PB in window   64.9 per 2000 bars
                 IDM create 24  migrate 41  taken 24   flow changes 99
                 PB duration median 2  p90 25  p99 962  max 2224
                 longest silent interval 1104 bars   SILENT TAIL 401 bars
                 §20: REJECT - raw swing noise, not a structural scale
```

**Neither fixes the defect.** Every external pullback either model produces in
the window lands on 9 Sep or early 11 Sep — the same events the control already
had. Across **11 Sep 04:00 → 13 Sep 20:00**, the exact stretch where the giant
box sits and where the reference draws roughly three boxes, both models produce
**nothing**.

## The result that matters most

**OF-B's silent tail is 401 bars — longer than the control's 255.** Taking
OF-1 literally makes the problem region *worse* while simultaneously producing
raw-swing noise elsewhere at 64.9 events per 2000 bars.

The mechanism is visible in the numbers: 99 flow direction changes. In a chop
the flow flips constantly, and every flip abandons the correction in flight
and reseeds, so nothing ever reaches confirmation. **OF-1 as the flow
orientation rule is falsified**, not merely unsupported.

## Why no Pine was written

§1 asks for the feature flag with a bit-identity proof, and §21 asks for the
Pine build. I have not written it. The variant failed the acceptance gate
before it was worth 400 lines of Pine I cannot compile here, and §20 explicitly
authorises rejection. Writing the flag would have produced a switch whose ON
state is measurably worse than OFF in the region under investigation.

The architecture itself is not what failed — the reference evidence for
splitting structure from flow is unchanged and still strong. What failed is
both permitted readings of the orientation rule.

## Recommendation: NEED MORE REFERENCE

Specifically, on one question: **what re-orients Main order flow?** It is
neither "follow the structure" (OF-A, too sticky — it never turns in the chop)
nor "turn on any opposite confirmation" (OF-B, far too eager — it turns 99
times and completes nothing). The reference sits between them and this fixture
cannot locate it.

**The screenshot region that would settle it is 11 Sep 04:00 → 13 Sep 20:00.**
The reference draws roughly three external boxes there (REF-8/9/10). For each,
what immediately precedes it — a new low, a failed rally, an internal event, a
particular candle relation? That is a zoom on one region of a chart you already
have, and it is worth more than any further instrumentation on our side.

Until then nothing is adopted, Arm A is canonical and untouched, and the two
rejected models stay in `research/lit_of.py` so the next candidate can be
measured against them rather than argued about.

---

# v0.3.7 — the zoomed reference plus our own chart. The premise was wrong.

No behaviour change. Arm A untouched.

## The finding that reframes everything

**Every structural label in the reference between 11 Sep 15:00 and 14 Sep is
PREFIXED.** `iiIDM`, `iBOS`, `iIDM`, `iiDM`, `iiChoch`, `iiBOS`, `iChoch`.
There is **no unprefixed Main IDM, BOS or Choch anywhere in that window.**

So the answer to the focus question — are the successive pink pullbacks from
12 Sep ~11:00 through 13 Sep ~15:00 order-flow reversals, same-direction IDM
migration, or nested Internal/Deep events? — is **nested Internal/Deep**, on
label evidence, high confidence.

**The reference's Main is quiet through that stretch. So is ours:**

```
zoom window bars 11306..11518   (11 Sep 15:00 .. 13 Sep 20:00)
  MAIN      events:  0
  INTERNAL  events: 18   PB 11  IDM 2  taken 2  BOS 1  CHoCH 1  flip 1
  DEEP      events: 39   PB 17  IDM 10 taken 6  BOS 3  CHoCH 3
reference labels in the same window: iiIDM iBOS iIDM iiDM iiChoch iiBOS iChoch
reference unprefixed Main labels:    NONE
```

**Main being silent there is a MATCH, not a defect.** The last two rounds —
OF-A and OF-B, and the whole hunt for a flow-orientation rule — were aimed at
making Main produce events in a region where the reference produces none
either. That work stands as a correct rejection of two rules, but it was
solving a problem that does not exist in this region.

This also corrects my own v0.3.5 ledger, where I classified the 12–13 Sep
boxes as `MAIN_EXTERNAL` at MEDIUM confidence. The zoom shows that was wrong.

## Our Main population is roughly right

From the debug panel on our chart against the reference's stat table:

```
              ours (Main)      reference
PB                    155              —
IDM                    76              —
IDM taken              35              24
BOS                    24              37
CHoCH                  24              39
flips                  13              —
```

Same order of magnitude on every comparable row. **Population was never the
problem.**

## What IS wrong, and it is narrow

Our chart draws **one enormous pink box from ~11 Sep 09:00 to ~14 Sep 03:00**,
roughly 1070–1220, covering the whole quiet stretch. The reference draws no
Main box there at all.

The debug panel says why:

```
pullback   active from 7208, confirms at 1062.72
leg from   1295.43  bar 6778
BOS base 1054.38 act 1041.86 drift 1.19% n1 age 291
CHoCH base 1295.43 act 1295.43 drift 0% n0 age 311
last event latent cached
```

Main holds **one correction open across the entire boundary lock**, and when
such a correction eventually confirms it is drawn as a single box spanning
everything it covered. The reference has no equivalent object on the chart.

So the discrepancy is not flow orientation. It is that **a correction which
spans a boundary lock is a different animal from an external pullback, and
should not be rendered as one.**

## A–I

**A.** Visible Main external PBs in the target region: **0**.
**B.** Inferred Main OF direction changes there: **0**.
**C.** Multiple PBs inside one persistent direction: yes — but at Internal and
Deep degree, not Main.
**D.** Preceding event for each Main OF transition: **not applicable, none
exist in this region.**
**E.** OF-1 … OF-7 score table: **not scoreable.** There are zero Main
order-flow transitions in the chosen window to score against. A candidate
cannot be ranked on a region containing none of the events it governs.
**F.** OF-3 (IDM-qualified) and OF-4 (PB+IDM handshake): **undecidable from
this fixture** for the same reason. Both remain plausible and neither is
tested.
**G.** Are Internal events necessary to trigger Main OF? **Undecidable here** —
Main does not transition in this window at all.
**H.** Minimal orientation rule supported by every visible transition:
**NEED_MORE_REFERENCE**, and the region to look at is *not* this one. It has to
be a stretch containing unprefixed Main IDM activity — on this chart that is
**9 Sep** and **11 Sep 06:00–09:00**, where the reference does show `IDM` and
`Choch` without a prefix.
**I.** No behaviour changed.

## The question worth asking before more work

On your Riptide chart, the giant box is Main. On the reference, the same
stretch has Internal and Deep boxes and nothing from Main. Both engines agree
Main is quiet. Before any orientation rule is chased further, the cheaper
question is whether a Main correction that opens and then spans a boundary lock
should be drawn at all — or whether the reference simply does not carry such an
object.

---

# v0.3.8 — rendering-lifetime arms. Box identified; no arm adopted.

Diagnostics only. **No Pine changed.**

## Coupling check — clean

`zone()` only READS `x.det.*`. Every write to detector state is inside
`ctxStep`. `box.delete` touches box handles and the `x.zones` array and nothing
else. **Drawing IDs are already presentation-only; no accidental coupling
exists.**

## The arms as briefed do not describe the mechanism

A box is created **only on `x.det.hit` — the confirmation bar** — with
`left = correction start`, `right = confirmation`, and is never touched again.
There is no continuously-extending box and no box at all while a correction is
unresolved. So "hide the unresolved Main PB" and "freeze its right edge" are
both no-ops against the current renderer.

## Why the first run showed nothing, and the fix

My data ends **13 Sep 20:00**; the chart runs to **14 Sep ~10:00**. The giant
box *confirms* in those missing hours, so it never appeared in my window. Main
still holds the same correction open at my right edge, so its confirmation was
simulated at the last bar to make the arms comparable.

## Results — 11–14 Sep

```
WIDEST BOX EACH DEPTH WOULD DRAW
  MAIN        3 boxes   widest  255 bars   11 Sep 04:15 -> 13 Sep 20:00
  INTERNAL   19 boxes   widest   52 bars
  DEEP       22 boxes   widest   33 bars

arm                                  boxes   widest
1 control - draw every confirmed         3      255
2 suppress if span crossed a lock        2       10     <- removes it
3 truncate right edge at lock entry      3      255     <- no-op
```

**The giant box is identified: a Main correction running 11 Sep 04:15 →
13 Sep 20:00, 255 bars — starting exactly at lock entry.** That is why arm 3
does nothing: there is no pre-lock portion to truncate back to.

Internal and Deep are **bit-identical** across all three arms (19 and 22 boxes,
widest 52 and 33) — no Main rendering arm touches them. Engine state is
identical by construction, since the arms are downstream and read-only:
invariants 0/0/0, final Main bearish/lock, latent cache 1073.93, Main 106
pivots / 54 IDM / 19 taken / 13 BOS / 13 CHoCH / 6 flips over all data.

## Why I am not recommending arm 2

It works on this box, but it is blunt:

```
across all data: 54 of 112 Main boxes (48%) cross a lock
  suppressed widths: median 8 bars, max 7403
  kept widths:       median 2 bars, max 221
```

**It removes nearly half of all Main pullback boxes, most of them small and
perfectly legitimate**, to delete one. The reference draws no Main box during
*this* lock, but I have no evidence about what it draws during the many short
locks arm 2 would also blank.

I tried a narrower class — suppress only a correction that opened inside a lock
and outlived it — and **mis-specified it**: my condition suppressed 95% of Main
boxes. Not usable as written, and recorded as a failure rather than presented
as an option.

## Where this leaves it

The object is now identified precisely and the coupling question is closed.
What is not settled is the rule: "crosses a lock" is too broad, and the exact
narrower class needs stating properly before it is worth coding. Nothing
adopted; Arm A canonical and untouched.


────────────────────────────────────────────────────────────────────────────
v0.7.16 — FULL AUDIT: riptide-lit.pine against the master prompt (82 §)
────────────────────────────────────────────────────────────────────────────

Line-by-line audit of every numbered section. Diagnostic only. Nothing in
this pass changes engine behaviour or rendering.

THE TWO THINGS SUSPECTED MISSING ARE PRESENT AND CORRECT
--------------------------------------------------------

§24-§30 HIDDEN SHADOW — implemented, matches the MD.
  §25 candidate: armed on the candle that pushes past the level without
      resolving it.
  §26 skip-inside: `h < b.hsMomHi and l > b.hsMomLo` — strict, as §26 asks.
  §27 synthetic candle: open = candidate.open, high/low = span extremes,
      close = resolver.close.
  §28/§29 resolution: only the resolver CLOSE is tested against hsLvl.
      hsHi/hsLo are tracked but deliberately unread — correct, the MD says
      only syntheticClose decides.
  §30 B&S after rejection: present.
  §60 inputs present with the documented defaults
      PB false / IDM false / BOS true / CHoCH true.
  §31 break-mode defaults correct: Shadow / Shadow / B&S / B&S.

§8-§12 INSIDE BARS — implemented, persistent mother range, not prev-bar.
  §8  inside = not (rh > n.hi) and not (rl < n.lo)  — strict both sides.
  §10 exit is geometric (range), never Body or B&S.
  §11 equality: exact touch is NOT a break, so it falls through to inside.
      The MD is internally ambiguous at exact equality (§8 and §10 both want
      strict, which leaves equality unclassified); resolving it as inside is
      the only reading consistent with §11. Code comment should say so.
  §12 OUTSIDE_BOTH counted in n.bothCount; the group emits and the offending
      candle seeds the next mother range, so no two structural events come
      off one bar. See DEFECT 2 for the missing debug output.

ALSO VERIFIED CONFORMING
------------------------
  §3   forbidden constructs: zero uses of ta.pivothigh / ta.pivotlow.
  §4   non-repainting: cfgConfirm default true.
  §23  pullback-zone boundary input present (pbEdge), visual only.
  §33  IDM migration: one active IDM per depth, retire-and-replace.
  §34  structural leg anchor: legHi/legLo/legHiBar/legLoBar maintained
       independently of IDM migration; BOS reads the LEG extreme, not the
       latest IDM. This is the one the MD calls out as important, and it
       is right.
  §42  latent pullbacks during boundary lock: cached, not dropped.
  §45  child context starts UNDEFINED (DIR_NONE).
  §46  Deep only runs with Internal (runDeep = runInt and showDeep).
  §47  strong/weak are derived display labels; nothing in the engine reads
       them.
  §57  bounded history: 8 / 6 / 3 levels, 10 zones per depth.
  §59  break-mode inputs all four exposed with the documented defaults.

DEFECTS — ordered by how much they cost
---------------------------------------

DEFECT 1  §58/§81 default view is not clean. Five defaults are wrong.
    showDeep      true   → MD says false
    pbDeepOn      true   → MD says false
    showStats     true   → MD says false
    showNearScan  true   → a research table on by default; §81 says
                           "no giant table"
    showInside    false  → MD §58/§61 say Color Inside Bars = true
  The first four make the default chart noisier than the MD asks for; the
  fifth makes it quieter. §81 is explicit about what a first load should
  look like and this is not it.

DEFECT 2  §63 Debug Mode is unreachable. `bool showDbg = false` on line 239
  is a hardcoded constant, not an input. Everything gated on it is dead:
  the §63 debug surface, the §12 outside-both debug output the MD calls
  mandatory ("must not silently corrupt structure"), and markHiddenPb —
  whose own tooltip says "When Debug is on", which can never happen.
  markHiddenPb is therefore a live input wired to nothing.

DEFECT 3  §51/§52 depth is not graded by line width. paint() takes an `int w`
  parameter and then every drawLvl call passes a hardcoded 1. Main,
  Internal and Deep all render at width 1. The MD wants Main "slightly
  thicker" and Internal "thinner". Depth is currently carried only by line
  style and fade. The parameter is accepted and ignored — dead argument.

DEFECT 4  §55/§51 label placement. tagLvl puts every label at 50% along the
  live segment (`x1t + int((time - x1t) * 0.50)`). The MD says BOS and
  CHoCH labels sit near the line's RIGHT EDGE, and §51 repeats it: "not
  floating in middle of candles". The reference screenshots agree. As
  written, on a long-lived Main level the label sits in open chart space
  far from the current bar.

NOT DEFECTS — optional, recorded so they are not re-raised
----------------------------------------------------------
  §76A event journal: 6 `lastEvent :=` assignments, not the 14-event
       journal. §76 is headed "Improvement Suggestions".
  §76B structure IDs: sc.id exists; no per-cycle structure ID. Same.
  §57  the MD's suggested caps are 20/30/30/30 but it permits "sensible
       fixed limits"; 8/6/3/10 is inside that.

ONE HOUSEKEEPING ITEM
---------------------
  The indicator() title still reads "Riptide LIT Structure — v0.7.9 CAL"
  while the file header says v0.7.15.

NOTHING CHANGED IN THIS PASS. Defects 1 and 2 are one-line each and carry no
engine risk. Defects 3 and 4 are rendering and should be settled against the
reference screenshots, not against the MD text alone.


v0.7.16 — the four defects fixed
--------------------------------

DEFECT 1 — §58/§81 defaults. showDeep, pbDeepOn, showStats and showNearScan
  now default false; showInside now defaults true. Tooltips rewritten so they
  no longer argue the opposite of the value they carry.
  CONSEQUENCE WORTH KNOWING: runDeep = runInt and showDeep, so showDeep off
  stops the Deep ENGINE, not just Deep drawing. Deep statistics read empty
  until it is switched on. This is what §46 and §58 ask for, but it is a
  behaviour change at default settings, not only a cosmetic one.

DEFECT 2 — §63 Debug Mode. showDbg is an input again. It was not enough to
  un-hardcode it: §63 lists what debug must expose and almost none of it was
  exposed, so a compact bottom-left table was added printing the mother range,
  inside-bar state and count, the §12 OUTSIDE_BOTH count with a this-bar flag,
  the pullback tracker and its frozen confirmation level, the Body & Sweep
  base→act migration and sweep chain length, Hidden Shadow pending state and
  which level owns it, the §34 leg anchor, IDM/BOS/CHoCH, and phase/direction.
  It follows the existing depth selector, now relabelled "Statistics / debug
  depth". markHiddenPb is reachable for the first time.

DEFECT 3 — §51/§52 width. paint()'s `w` parameter is wired through instead of
  every draw passing a hardcoded 1. Main BOS/CHoCH read a new "Main line width"
  input; Main IDM sits one step below it, floored at 1 (§51 wants Main IDM
  thinner than Main BOS/CHoCH); Internal and Deep are always 1.
  FIRST ATTEMPT WAS WRONG AND WAS CORRECTED ON SIGHT. Main went out at width 2
  and on a real chart that reads as heavy, not as hierarchy - Main is already
  separated from the children by solid style and zero fade. Pine has no width
  below 1, so "thinner" has exactly one value and the default is now 1. The
  input exists so calibration can raise it rather than re-edit the file.

DEFECT 4 — §55 label placement, SPLIT BY LIFETIME.
  LIVE level   → tags near the segment's right endpoint, which is the current
                 bar, so the text sits next to price. Inset two bars so a
                 centred style_none label does not overhang the price scale,
                 clamped to the segment start for a level created on this bar.
  RETIRED level → tag recentres on its own frozen span. A closed historical
                 segment has no live edge; tagging its right end puts the text
                 on top of whatever structure replaced it. This is why the
                 first pass, which moved retire() to the right edge too, was
                 wrong: "right edge" is only meaningful while the edge tracks
                 the current bar.
  The bar width is computed once at global scope (barMs) rather than opening a
  `time[1]` history buffer at each call site.

Housekeeping: indicator() title bumped to v0.7.16 (it still read v0.7.9 CAL).

NOT COMPILED. There is no Pine compiler in this environment and there has not
been one for any version in this log. Everything here was checked by reading:
no function assigns a global scalar (CE10088), every drawing stays anchored in
xloc.bar_time (RE10026), continuation indents follow the file's 9-space
convention, and no `[]` history is taken on an object field. Compile errors on
first paste are still possible and are the expected next round.


────────────────────────────────────────────────────────────────────────────
v0.7.17 — NEAR CALIBRATION: the scan was scoring against the wrong target
────────────────────────────────────────────────────────────────────────────

Measured on ZEC 30m, viewport ≈ 11 Sep 06:00 → 14 Sep, Main depth.

                          reference        ours
  IDM → BOS touch         20  13  65.0%    31  19  61.3%
  IDM → Choch touch       20   7  35.0%    31  12  38.7%
  BOS near → Opp PB       29  20  69.0%    34  17  50.0%
  BOS near → BOS break    29   9  31.0%    34  17  50.0%
  Choch near → Opp PB     14   7  50.0%    18   6  33.3%
  Choch near → Choch brk  14   7  50.0%    18  12  66.7%

THE FINDING
-----------
Row 1 is not a "near" statistic at all - it uses no near rule - and it says
the reference resolves 20 lock episodes in this window where we resolve 31.
Our Main structure runs about 1.55x hotter than the reference's on the same
bars. That single number reframes everything below it.

Near events per lock episode:
    reference   29/20 = 1.45 BOS      14/20 = 0.70 CHoCH
    ours        34/31 = 1.10 BOS      18/31 = 0.58 CHoCH

So our near rule fires LESS often per opportunity than the reference's, not
more. The raw totals (34 vs 29, 18 vs 14) looked close and pointed the other
way, which is exactly the trap.

The calibration scan has been scored against the reference's raw 29 / 14 since
it was built. Against a raw target, a candidate is rewarded for firing LESS -
so the scan has been steering every prior round toward a stricter rule when
the evidence says the rule is already too strict. Rescored on the normalized
target (1.45 and 0.70 applied to OUR race count, so 45 / 22 at 31 races):

    candidate              BOS  Choch    old error    new error
    Raw level touch         48     19       24            6
    ≤10% range              82     35       74           50
    ≤20% range              83     45       85           61
    IN USE: armed touch     34     18        9           15

Raw level touch, the simplest reading of the source word, goes from worst-but-
one to best once the comparison is like-for-like. The armed rule currently
driving the live table goes the other way.

WHY THIS ALSO EXPLAINS THE SPLITS
---------------------------------
Both near rows are biased the same way - we break where the reference reaches
the opposite pullback. The arm rule allows one race in flight per boundary, so
a second or third approach to a still-live boundary is not counted. Those
repeat approaches are by construction ones that already failed once, and a
failed approach is far more likely to retreat to the opposite pullback than to
break. Excluding them removes mostly-reach events from the denominator, which
drives the split toward break. One cause, both symptoms, and it is falsifiable:
loosening the arm should raise the totals AND the reach share together.

CHANGED IN THIS PASS — instrumentation only, no rule adopted
------------------------------------------------------------
  - The scan's Error column is now scored against the density-normalized
    target, and the target row prints it alongside our race count. If our race
    count ever reaches 20, the target collapses back to 29 / 14 by itself.
  - The rule actually driving the live table ("armed touch") is now a row in
    the scan, scored on the same target. It was never in the scan, so it was
    never comparable to the rows it was being selected against.
  - Removed statBosNearSeenLevel / statChNearSeenLevel: declared, never
    written, never read.

CHECKED AND CLEAN, recorded so it is not re-investigated
--------------------------------------------------------
  - The `if not moved` gate on the Opp-PB reach branch looked like an
    asymmetry that would bias toward break. It is not: `moved` is set only by
    the IDM, BOS and CHoCH break branches, both break branches disarm BOTH
    races before the gate is reached, and a race cannot be armed on an IDM
    break bar (the arm site runs after it, and bosArmedThisBar excludes it).
    The gate is redundant, not harmful. Left alone.
  - The cross-invalidation IS symmetric: BOS break clears the CHoCH race and
    CHoCH break clears the BOS race.

NOT ADOPTED. No near rule changed. The next round needs one reload to read the
rescored table, and one A/B on statsWindow ("Visible chart" vs "All loaded
bars") to settle whether the reference table is window-cohorted at all - if it
is not, our windowed totals are not comparable to its totals in the first
place and the ratios above are the only sound comparison.


v0.7.18 — label gap, and the BOS/CHoCH swap theory tested and rejected
----------------------------------------------------------------------

LABEL GAP. A live level's tag now sits PAST its right endpoint by a
"Label gap (bars)" input (default 3), in the empty margin, instead of on the
last bars of its own line. Retired tags still centre on their frozen span.

THE SWAP THEORY. Observation raised: our BOS near row (50.0/50.0) looks like
the reference's CHoCH row (50.0/50.0), and our CHoCH row (33.3/66.7) looks
like the reference's BOS row (69.0/31.0) with the two rows exchanged. Two
places a swap could live were audited, and then the theory was tested against
the numbers themselves.

  CODE AUDIT — no swap found.
    Render: each of the six cells reads the counter its label names.
    Counters: statBosNearOppPb increments only in the Opp-PB reach branch,
      statBosNearBreak only inside the confirmed BOS break branch, and the
      CHoCH pair mirrors it exactly.
    Orientation: which level is BOS and which is CHoCH is guarded every bar by
      invariant I11 (bullish bos > ch, bearish bos < ch). It has not flagged.

  THE DATA RULES IT OUT ON ITS OWN, which is stronger than the audit.
    A BOS/CHoCH swap would cross the TOTALS too. Ours are BOS 34, CHoCH 18 -
    BOS is 1.9x CHoCH. The reference is BOS 29, CHoCH 14 - BOS is 2.1x CHoCH.
    Same ordering, same ratio. Under a swap our BOS total would be the SMALL
    one. It is not.

    A row swap within a pair cannot explain it either. The two rows of a pair
    share a Total and sum to it, so swapping them just exchanges the two
    percentages. For BOS ours is 50/50 and swapping leaves 50/50 - it changes
    nothing against the reference's 69/31. For CHoCH ours is 33.3/66.7 and
    swapping gives 66.7/33.3, which is not the reference's 50/50 either. A row
    swap makes both rows no closer.

  WHAT THE RESEMBLANCE ACTUALLY IS. 50/50 is the degenerate value any
  near-even race lands on, so it turning up in both tables on different rows
  carries no information. 33.3/66.7 against 69/31 is a mirrored pair at n=18
  and n=29 - one event either way moves our CHoCH row by 5.6 points. The gap
  is real; a crossed wire is not the cause of it.

The density finding from v0.7.17 still stands as the live explanation and is
untested until the rescored scan is read back.


────────────────────────────────────────────────────────────────────────────
VARIANT 2 — riptide-lit-v2.pine, first build
────────────────────────────────────────────────────────────────────────────

New file. riptide-lit.pine (v1) is untouched and stays the working build.
Built against LIT_V2_DESIGN.md; every rule traces to LIT_SOURCE.md.

WHAT IS STRUCTURALLY DIFFERENT FROM v1
--------------------------------------

1. THE UNDEFINED CASES ARE NAMED. v1's rules were all source-correct; what was
   wrong was that wherever the source is silent, v1 answered by statement order
   - an `if` arm that happened to be written first. Those answers moved the
   output and were invisible. V2 exposes them as policies P1, P3, P4, P8 with
   explicit defaults, and the debug panel counts how often each actually fires.

2. DUAL-ORIENTATION DETECTORS [P8]. A pullback detector runs in EACH direction
   at every depth. Only the one matching the structural direction may publish
   an IDM or open a child scope; the other is observed. This is the single
   confirmed divergence from the reference and it has two witnesses - Ch.3's
   post-flip lookback and Ch.12's "Show Latest Bullish & Bearish" display
   option. It makes the Ch.3 lookback implementable for the first time:
   on a CHoCH flip, if an opposite-direction pullback already exists it becomes
   the IDM immediately instead of waiting for a fresh one.

3. NO FLOATING IDM, AND NO INPUT FOR IT. The line begins on the candle that
   MADE the level - the pivot - and runs to the current bar. v1 carried an
   idmAnchor input offering the wrong answer as an option; the reference does
   it one way and that is the only correct way, so the input is gone.

4. MIGRATED IDMs ARE DELETED. User decision, overriding the reference's own
   faded-trail rendering: "we move the idm up and after moving we will delete
   the previous IDM ... so that our chart will be cleaned". One live IDM per
   depth, nothing behind it. BOS/CHoCH still fade into capped history.

5. RETYPE IN PLACE. On a CHoCH flip the old BOS line OBJECT is transferred to
   the CHoCH and relabelled, with a small ✗ at the retype bar - one continuous
   level, which is what Ch.8's diagram shows. v1 deleted and recreated.

6. TWELVE-ROW STATISTICS, all-loaded-bars cohort by default, including the six
   Hidden Shadow break/cancel rows. Near arms on a TOUCH and targets the LAST
   opposite pullback, which under P8 is literal rather than approximated.

7. NEAR HAS NO DISTANCE BAND ANYWHERE. Ch.2's determinism requirement forbids
   one and the rescored scan already showed every proximity band an order of
   magnitude worse than raw touch.

NO COMPLEX-PULLBACK RULE, DELIBERATELY. A complex pullback is the emergent
shape of the frozen-confirmation-level machine: oscillations that fail to break
`conf` leave the correction running, the range ratchets, one pivot comes out at
the true extreme. Writing a rule for it would be inventing exactly what Ch.2
spends its length warning against.

THREE BUGS FOUND IN SELF-REVIEW AND FIXED BEFORE COMMIT
--------------------------------------------------------
  - The I5 invariant read `not x.idm.on == false`, which does not parse as
    intended and would have silently never fired.
  - A bar that bootstraps the direction fell through and advanced its detectors
    a SECOND time, stepping one group twice. Guarded with `justSeeded`. This is
    precisely the class of bug that surfaces as an unexplained density
    discrepancy several rounds later.
  - Pullback zones were drawn in the render section, which runs on every bar,
    while `det.hit` persists between analytical groups - so one confirmation
    would redraw its box on every intervening inside bar. Zones are now drawn
    where they are decided.

NOT COMPILED. There is no Pine compiler in this environment. Checked by reading
and by script: no function assigns a global scalar (CE10088), every drawing is
anchored in xloc.bar_time (RE10026), no return-type annotations, no `[]`
history on object fields, no continuation line on a multiple-of-4 indent, zero
ta.pivot* uses. Compile errors on first paste are still possible.

NOT YET MEASURED. The acceptance test in LIT_V2_DESIGN.md §8 step 1 is a parity
run against v1 with P8 set to Single - identical pullback count, pivots and
IDM/BOS/CHoCH sequence. Any difference there is a porting bug, not an
improvement. Nothing about V2 should be believed until that passes.


────────────────────────────────────────────────────────────────────────────
V2 — FIRST REAL MEASUREMENT, ZEC 30m, all loaded bars, Main depth
────────────────────────────────────────────────────────────────────────────

                          reference (30m)      V2
  IDM → BOS touch          20  13  65.0%    32  21  65.6%
  IDM → Choch touch        20   7  35.0%    32  11  34.4%
  HS BOS break             19  16  84.2%    23  21  91.3%
  HS BOS cancel            19   3  15.8%    23   2   8.7%
  HS Choch break            5   5 100.0%    16  14  87.5%
  HS Choch cancel           5   0   0.0%    16   2  12.5%
  BOS near → Opp PB        29  20  69.0%    20   0   0.0%
  BOS near → BOS break     29   9  31.0%    20  20 100.0%
  Choch near → Opp PB      14   7  50.0%    12   1   8.3%
  Choch near → Choch brk   14   7  50.0%    12  11  91.7%

(HS reference figures are from the author's annotated table, a different
chart and date, so they are shape comparisons and not same-window.)

WHAT IS GOOD
------------
The IDM race now matches the reference's RATE almost exactly - 65.6/34.4
against 65.0/35.0. That is the one row with no "near" definition in it, so it
is the cleanest read we have of whether the structural engine agrees with the
reference, and it does. The Hidden Shadow rows are in the right region too.

Totals still run high (32 against 20), but the viewport-cohorting artefact is
only now removed, so this is the first genuinely comparable reading of it.

WHAT WAS BROKEN, AND IT WAS MINE
--------------------------------
BOS near → Opp PB reach read 0 of 20. Not low - ZERO. A statistic that never
fires is not a calibration problem, it is a bug, and the debug panel found it
in one screenshot:

    bull trk hi/lo   1295.43 / 1271.43   correcting
    bear trk hi/lo    316.73 /  292.87   correcting
    conf bull / bear 1295.43 /  298.47

Price was trading at 1130. The bear detector was holding trackers at 316/292
with a frozen confirmation level of 298.47 - stale by thousands of bars and by
a factor of four in price.

CAUSE. P8 runs a detector in each direction. The idle one opens a correction
like any other, and a bear correction confirms only on a break BELOW its
frozen low. In a market that has quadrupled since, that never happens, so it
sat in one correction indefinitely. Its ancient `last` record was then handed
to the near statistic as "the last opposite pullback", at a price the market
left long ago - so the race could only ever resolve as a break. Hence 100%.

This is the same failure mode as the v0.1 "unoriented parallel trackers"
defect, reintroduced by P8 and not caught because P8 was reasoned about rather
than measured.

FIX, and it is structural rather than a threshold:
  - The idle opposite detector RESTARTS at every major structural event. It is
    an observer of the current leg, and a structural event is what ends a leg,
    so an in-flight opposite correction costs nothing there.
  - The near target must be a pullback confirmed within the CURRENT leg.
    Leg-relative, not a distance band - §2's determinism requirement rules out
    a number, and the rescored scan already showed every proximity band far
    worse than raw touch.

STILL OPEN
----------
Main 139/96/33/32/31/14/67/0 against Internal 139/94/32/32/18/14/65/0
(pv/idm/take/bos/ch/flip/latent/inv). Under P7b Continuous, Internal reads raw
candles and Main reads normalized groups - roughly 5000 steps against 850 - yet
they produce nearly the same structure. Either the finer feed is not actually
producing finer structure, or Internal is stuck the same way the bear detector
was. Not diagnosed. Next measurement, not the next theory.

Zero invariant violations at both depths, which is the one unambiguously good
line in the whole panel.


V2 — NEAR TARGET CORRECTED BY MEASUREMENT (the asymmetry was the tell)
---------------------------------------------------------------------

After the stale-detector fix, ZEC all loaded bars, Main:

                      reference 30m      V2 30m        V2 15m   (ref 15m)
  BOS near → Opp PB    29 20 69.0%    42 23 54.8%   31  8 25.8%  (68.4%)
  Choch near → Opp PB  14  7 50.0%    28 14 50.0%   48 36 75.0%  (79.5%)

CHoCH-near landed on the reference almost exactly on BOTH timeframes - 50.0%
against 50.0%, and 75.0% against 79.5%. BOS-near sat far too low on both. One
row right and its mirror wrong is not sampling noise, it is a sign error.

CAUSE. V2 read "the last OPPOSITE pullback" as the opposite-DIRECTION
detector's last record. That is a different quantity from what the reference
means, and the geometry exposes it:

  bearish structure, CHoCH is the UPPER boundary
    the opposite-direction detector's pivots lie BELOW it → correct, by accident
  bearish structure, BOS is the LOWER boundary
    those same pivots lie below it too → WRONG SIDE. Price that fails at the
    BOS retraces UP, so the target has to be above it.

"Opposite" is geometric - the side AWAY from the boundary approached - which is
what v1 had and what v2 replaced with a worse reading. Restored, with two
things v1 lacked: among eligible zones take the most RECENTLY confirmed (Ch.10
says "the last"), and only from the CURRENT leg.

Also: the two Hidden Shadow rows for a level on Shadow mode are now omitted
rather than printed as "HS not active". They carry no information.

STILL OPEN. BOS-near totals run about 1.45x the reference (42 against 29) while
CHoCH-near runs 2x (28 against 14). The 15m and 30m readings disagree sharply
on BOS-near (25.8% against 54.8%), which nothing in the model predicts. Not
theorised about - next measurement.


────────────────────────────────────────────────────────────────────────────
STAGE A — §72's naked continuation is REFUTED, and usefully
────────────────────────────────────────────────────────────────────────────

research/lit_entry.py on research/lit_v3.py (a separate copy; lit_v02.py stays
the frozen control). 8 symbols, 30m, commission 0.05%/side, minRR 0.5,
Pullback = Body per Ch.24. 51 setups.

    long   bullish IDM taken, BOS locked above, with-trend only
    entry  the IDM-break bar's close
    stop   that bar's extreme - the IDM raid extreme (§73)

THE PREMISE IS REAL
    BOS reached before CHoCH   34/41 = 82.9%   (reference 65.0%)
    distance entry → BOS       11.85R median   [1.65 .. 30.67]

EVERY EXIT ARM LOSES
    trail        n   win%     expR    avgW    avgL  armed%
    fixed       51  39.2%   -0.709    0.50   -1.49   39.2%
    bos         51   9.8%   -0.657    3.44   -1.10   33.3%
    breakeven   51   0.0%   -1.002    0.00   -1.00   39.2%
    pivot       51   3.9%   -0.983    0.48   -1.04   39.2%
    mfe         51  39.2%   -0.421    1.23   -1.49   39.2%

83% of paths reach BOS, yet the BOS arm wins 9.8%. The contradiction is the
finding, and one measurement resolves it - on the 34 paths that DO reach BOS,
how far does price go against the entry first:

    median   6.27R of the raid-extreme stop distance
    75th    13.63R
    90th    22.79R

A stop wide enough to survive 80% of the WINNING paths is ~20x wider, and BOS
then sits at ~0.6R of that risk.

    tight stop → noise stops you out long before the structural move
    wide stop  → the reward no longer covers the risk

THERE IS NO STOP DISTANCE AT WHICH THIS ENTRY PAYS. §72's naked continuation is
refuted on its own terms.

WHY THIS IS A GOOD RESULT, NOT A DEAD END
The premise survived and the ENTRY LOCATION is what failed. Price travels a
median 6.3x the raid-bar distance against you before going to BOS - which is
precisely the excursion POI zones exist to capture. The reference does not
chase the IDM break; it waits for the retrace into a Decisional/Extreme zone,
takes SCOB confirmation, and puts its stop behind structure rather than behind
a single bar. Stage A has just measured why that architecture exists.

So the design's gate is met in substance: it existed to stop us decorating a
distribution with no edge, and the edge is demonstrably there (83% to a 12R
target). What is missing is a place to stand.

TWO HARNESS BUGS FOUND AND FIXED MID-RUN, both mine:
  - the "fixed" control moved the stop to entry and then held with no target,
    so it could only ever return 0R or -1R. It duly returned a 0.0% win rate
    across every trade. That is not a control, it is a broken arm. A real
    fixed-R control takes profit AT Active Price.
  - the premise check measured "BOS before MY EXIT", which measures the exit
    rule rather than the premise, and produced a nonsense 9.8%. Corrected to
    BOS-before-CHoCH on the price path, independent of any exit, with same-bar
    ties excluded rather than guessed.

NEXT: not Stage B. The entry model is what needs replacing, so the next
measurement is the reference's own - retrace to a zone, stop behind the zone -
even in a crude form, before any filter is built on top of it.
