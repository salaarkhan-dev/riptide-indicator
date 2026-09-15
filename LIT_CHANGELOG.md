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


────────────────────────────────────────────────────────────────────────────
ENTRY VARIANT 2 — the retrace entry also has no edge, and a subset that
looked real turned out to be noise
────────────────────────────────────────────────────────────────────────────

research/lit_entry2.py. Zones born at IDM break from the leg's unmitigated
pullbacks, entry on the retrace touch, stop beyond the zone's far edge (the
reference's LowRisk "SL on Pullback"), zones killed by a BOS break per Ch.15.
30 symbols, 30m AND 15m, 1214 trades.

THE GEOMETRY IS FIXED - this is a real improvement over Stage A
    stop distance        1.251% of price   (Stage A 0.330%)
    commission in R          0.08R         (Stage A 0.30R - was eating half of R)
    entry -> BOS             1.52R         (Stage A 11.85R)
    zone fill rate           58.6%

SO THE SETUP IS NOW COHERENT. AND IT STILL LOSES
    arm        n     win%     expR
    fixed   1212    37.2%   -0.517
    bos     1214    19.9%   -0.459
    mfe     1158    36.8%   -0.456

THE PART WORTH RECORDING: A FALSE POSITIVE, CAUGHT
On the first 102-trade run the zone-stack rank split looked monotone and
rank 2+ came out POSITIVE:

    rank 2   n=11   36.4%   +0.172R
    rank 3+  n=10   20.0%   +0.205R

It had everything a real finding is supposed to have - a monotone trend, the
same direction on two independent exit arms, and a source-recognised story
(Ch.15's Decisional-nearer / Extreme-deepest distinction). At 1214 trades:

    rank 0   n=821   -0.502      rank 2   n=111   -0.446
    rank 1   n=192   -0.404      rank 3+  n= 90   -0.190

Every rank negative, ordering gone. Split by timeframe, 30m rank 3+ is -0.379
and 15m rank 3+ is -0.024 - not consistent and neither positive.

That subset was noise found by slicing, and it would have been the worst kind
of false positive: it came with a ready-made source-flavoured justification.
The only reason it did not get reported as a finding is that the sample was
widened BEFORE writing it up, not after.

VERDICT: Stage B/C/D stay locked.

WHAT THIS DOES NOT PROVE. The source's real entry takes only zones carrying an
FVG, classifies them into Decisional/Extreme/Breaker/Flip, and requires SCOB
confirmation - every one of those is a filter on WHICH zone to take.
"Unfiltered zones lose" does not establish "filtered zones lose". What it does
establish is the rule for what happens next: no filter gets built on a hunch,
and the next thing to move is whichever filter can be MEASURED on this existing
trade list without being built first.


────────────────────────────────────────────────────────────────────────────
FVG — the source's own filter, tested retrospectively. A LARGE, REAL effect.
────────────────────────────────────────────────────────────────────────────

Tested as a TAG on the 1214 trades that already existed, not as a new system.
[SRC Ch.14] FVG is the gap between two CONSECUTIVE PULLBACKS - "if a new
Pullback penetrates into the previous Pullback, the orders ... are considered
to have been consumed" and "if there is a price gap between two Pullbacks ...
the orders from the previous Pullback may not have been fully consumed". Those
two statements are one test: do the consecutive ranges overlap?

    arm      group      n     win%     expR     armed%
    fixed    FVG      234    55.6%   -0.220     55.6%
             no FVG   978    32.8%   -0.589     32.8%
    bos      FVG      236    19.5%   -0.135     55.5%
             no FVG   978    20.0%   -0.537     33.5%
    mfe      FVG      228    54.4%   -0.105     54.8%
             no FVG   930    32.5%   -0.542     32.7%

IT ROUGHLY QUARTERS THE LOSS, and the mechanism is visible rather than
inferred: armed% goes from ~33% to ~55%. Zones the next pullback did NOT
consume actually hold when price returns to them. That is what the source says
an unconsumed transactional node is, and it behaves like one.

STILL NOT ENOUGH. Best arm ≈ -0.105R. Per timeframe on the bos arm, 30m is
-0.020 (effectively breakeven) and 15m is -0.211.

WHY THIS IS BELIEVED WHERE THE RANK SPLIT WAS NOT
The rank split looked equally good at n=10 and evaporated at n=1200. FVG:
  - was predicted BY THE SOURCE before being measured, not found by slicing
  - holds at n=234 against n=978
  - moves the INTERMEDIATE quantity it ought to move (armed%), not just the
    outcome
Three independent reasons the rank split never had.

NEXT: SCOB, and it is the obvious one. Our entry is a bare TOUCH of the zone,
and Ch.16 exists to forbid exactly that - "Reaching a valid zone or level is
not enough on its own to justify an entry ... it also evaluates how the market
behaves after reaching that zone." SCOB is testable on this same trade list by
changing WHEN the entry fires (wait inside the zone for the confirmation break)
rather than building anything new.


────────────────────────────────────────────────────────────────────────────
SCOB + the cost/timeframe test — the edge is real but too small to survive
────────────────────────────────────────────────────────────────────────────

research/lit_entry3.py. SCOB confirmation replacing the bare touch, on FVG
zones only, 30 symbols. NET is after a 0.05%/side round trip; GROSS is before.

    entry (arm 'bos')          n    win%     NET   GROSS
    touch  (Variant 2)       258   20.5%  -0.124  -0.016
    SCOB shadow, zone SL     221   29.0%  -0.085  +0.100
    SCOB body,   zone SL     210   29.5%  -0.180  +0.008
    SCOB shadow, SCOB SL     246   10.6%  -0.421  -0.058
    SCOB body,   SCOB SL     227   12.8%  -0.201  -0.043

1. SCOB ADDS REAL EDGE. Gross -0.016 -> +0.100. Ch.16 is right that reaching a
   zone is not an entry.
2. AND IT PAYS FOR IT. SCOB enters DEEPER in the zone, so R shrinks and the
   same fee takes a larger share. Net barely moves, -0.124 -> -0.085.
3. SCOB BARELY FILTERS. Only 2 of 265 touched zones timed out in shadow mode.
   Ch.16 presents SCOB as a gate that refuses entries; as implemented it
   refuses ~1% and mostly just re-prices. Either the implementation is too
   permissive or the gating language oversells it - not resolved.

THE COST/TIMEFRAME TEST, predicted from the gross/net gap before running

    tf       n     NET   GROSS  fee/R  stop%   win%
    Min15  133  -0.189  +0.069  0.257   1.87   26.3
    Min30   88  +0.071  +0.147  0.076   3.19   33.0
    Min60   51  -0.015  +0.049  0.064   4.13   25.5

The fee mechanism is confirmed and is pure arithmetic: fee-in-R falls
0.257 -> 0.076 -> 0.064 as the stop widens 1.87% -> 3.19% -> 4.13%.

BUT GROSS EDGE DOES NOT HOLD UP: 0.069 / 0.147 / 0.049. Small everywhere and
not monotone. The single NET-positive cell is Min30 at +0.071R on n=88, with
unremarkable neighbours on both sides.

THAT IS THE RANK-SPLIT SHAPE AND IT IS NOT CLAIMED AS A FINDING. One positive
cell at n=88 bracketed by two negative ones is what noise looks like. The rank
split had a trend, two agreeing arms and a source story, and still died at
scale; this has less.

HONEST STATUS
The setup is roughly breakeven before costs and negative after. At 60m, where
fees are nearly irrelevant (0.064R), gross is still only +0.049R. So the
binding constraint is no longer transaction cost - it is that the edge is too
small to survive anything.

CUMULATIVE PROGRESSION, all measured, none positive:
    Stage A   chase the IDM break              no stop distance works at all
    Variant 2 retrace to zone                  -0.46R
    + FVG     [SRC Ch.14]                      -0.11R   (armed% 33% -> 55%)
    + SCOB    [SRC Ch.16]                      -0.085R  (gross -0.016 -> +0.10)

Each source filter helped and each helped less. Remaining untested from the
source: zone CLASSIFICATION (Decisional/Extreme/Breaker/Flip) and the OBSTACLE
CHECK, which is the one flagged in the design as most likely to change a
distribution rather than shave it.

---

## VARIANT 4 — the obstacle check and zone classification (research/lit_entry4.py)

The last two untested source filters. Baseline is Variant 3's best arm: FVG
zones, SCOB shadow confirmation, stop at the zone's far edge, exit at BOS.
30 symbols across Min15/Min30/Min60.

    arm                       n    win%    NET R  GROSS R   avgW   avgL
    baseline (V3 best)      271   37.3%    0.008    0.170   2.05  -1.20
    + obstacle check        246   32.5%   -0.027    0.157   2.44  -1.21
    + Extreme zones         349   37.8%   -0.047    0.112   1.85  -1.20
    + both                  309   32.4%   -0.084    0.096   2.29  -1.22

### THE OBSTACLE CHECK IS CONFOUNDED, NOT REFUTED

A first pass rejected only 3 of 273 setups, which would have read as "the
filter does nothing". That was a harness fault, not a result: the obstacle set
held only the CHoCH level and other zones' near edges. Ch.22's slide names the
types explicitly — BOS Level, Valid opposite pullback, Breakout Zone (a level
that CHANGED NATURE after being broken) — so broken BOS/CHoCH levels and
opposite-direction pending pullbacks were added. Rejections went 3 -> 27.

The filter then makes things worse, and the direct test says why. Taking the
rejects anyway and tagging them, so kept and rejected come from ONE run and
cannot differ through trade-slot competition:

    kept (path clear)       244   32.8%   -0.011    0.166   2.44  -1.21
    REJECTED (blocked)       27   77.8%    0.183    0.208   0.53  -1.04

    kept      target distance: median 2.51R   mean 6.22R
    rejected  target distance: median 0.35R   mean 0.51R

The rejected set is the BEST set in the sample. The mechanism is arithmetic,
not luck: Active Price is entry + 0.5R, BOS is an obstacle, and BOS is also our
EXIT. So "blocked" is very nearly a restatement of "the target is nearer than
0.5R" — median 0.35R against 2.51R kept. The filter removes short-path trades,
which under a BOS exit are the quick reliable winners (77.8% at avgW 0.53).

Dropping BOS from the obstacle set isolates the non-circular part:

    kept                    268   36.6%   -0.016    0.148   2.04  -1.20
    REJECTED                  3   too few to read

Three rejections in 271. The other named obstacles essentially never sit in the
entry -> Active corridor, because that corridor is 0.5R wide and sits at the
zone, where there is little structure by construction.

CONCLUSION: the obstacle check cannot be evaluated under a BOS exit. It is
entirely BOS-driven, and BOS is the exit, so the filter and the exit are the
same variable. It becomes testable only once T6 — what the trailing stop
actually trails — is defined. T6 was already the design's largest hole; this is
the second thing now blocked behind it. NOT a verdict on the source.

### ZONE CLASSIFICATION IS A REAL NEGATIVE

Extreme zones per Ch.15: created BY the CHoCH flip, from the prior structure's
final pullback, facing the NEW direction. 384 born, 79 traded.

    decisional              270   37.4%    0.012    0.175   2.05  -1.20
    extreme                  79   39.2%   -0.250   -0.103   1.21  -1.19

Classification does separate the population, but with the opposite sign to the
hope. Extreme is the only arm measured in this whole programme that is negative
GROSS. Win rate is comparable (39.2% vs 37.4%); the damage is in avgW, 1.21
against 2.05. Extreme zones get hit about as often and pay far less.

n=79 is small and this is one negative reading, so it is not proof the source
is wrong. It is enough to stop Breaker and Flip, which chain off an Extreme
being broken: building them now would stack on a base that does not hold.

CUMULATIVE PROGRESSION, all measured, none positive:
    Stage A   chase the IDM break        no stop distance works at all
    Variant 2 retrace to zone            -0.46R
    + FVG     [SRC Ch.14]                -0.11R   (armed% 33% -> 55%)
    + SCOB    [SRC Ch.16]                -0.085R  (gross -0.016 -> +0.10)
    + obstacle[SRC Ch.18]                confounded by the BOS exit, blocked on T6
    + Extreme [SRC Ch.15]                gross -0.103, worse than decisional

Every source filter is now measured except the two that need T6 first. T6 is no
longer one hole among several — it is the only road left open.

---

## T6 — WHAT THE TRAILING STOP TRAILS (research/lit_exit.py)

The source is explicit that everything measured before this used an exit it
rules out:

    [SRC Ch.20] "Index Algo relies on a Trailing Stop logic rather than fixed
    take-profit targets." — "This CONTRADICTS master prompt §74, which names
    BOS as 'the natural structural target'. The reference does not target BOS."

So this is not a refinement of Variants 2-4, it is a different question.

TWO HARNESS CHANGES, both of which change how earlier work should be read.

1. SETUPS ARE COLLECTED ONCE AND SHARED. Every prior variant allowed one live
   trade, so a longer-held exit blocks later entries and n differs per arm —
   the same slot-competition confound that muddied the obstacle check. Here all
   ten arms run over an identical 277-setup set.

2. A STANDARD-ERROR COLUMN. This should have been there from the start.

    exit rule                      n    win%    NET R      se   avgW   avgL
    CONTROL initial stop only    277    17.3%    0.360   0.346   7.58  -1.15
    CONTROL exit at BOS          277    36.1%   -0.020   0.138   2.06  -1.20
    CONTROL fixed 1R             277    47.7%   -0.198   0.069   0.89  -1.19
    CONTROL fixed 2R             277    34.7%   -0.126   0.092   1.83  -1.16
    CONTROL fixed 3R             277    28.5%   -0.049   0.111   2.71  -1.15
    T6 break-even only           277    28.9%   -0.005   0.143   1.78  -0.73
    T6 pivot trail               277    32.9%   -0.011   0.128   1.55  -0.77
    T6 structure trail           277    31.4%    0.026   0.137   1.73  -0.76
    T6 mfe - 0.5R                277    58.5%   -0.129   0.080   0.67  -1.25
    T6 mfe - 1.0R                277    39.7%   -0.057   0.091   1.16  -0.86
    T6 mfe - 1.5R                277    36.8%    0.017   0.106   1.46  -0.82

### T6 IS ANSWERED, IN THE NEGATIVE

The design said: "Measured against a fixed-R control, which is the honest
baseline: if no trailing variant beats a fixed exit, that is the result and it
gets recorded as one." That is the result. The best trailing arm is +0.026 with
se 0.137 — a fifth of one standard error from zero, and indistinguishable from
the BOS control at -0.020. Nothing in this table separates.

What trailing DOES do is real but not an edge: it cuts avgL from -1.20 to about
-0.76 and pays for it in win rate (36.1% -> 31.4%) and avgW (2.06 -> 1.73). It
reshapes the distribution and nets zero. The worst trade is -5.82 in every
single arm, because it gapped through the INITIAL stop before the trail could
ever arm. No exit rule reaches that trade.

### THE BEST-LOOKING ARM IS AN ARTEFACT, NOT A FINDING

"Initial stop only" (hold, no target, no trail) posts the highest NET at +0.360
— on se 0.346, 17.3% win rate, avgW 7.58. That shape is a warning, so:

    exit=stop   219 trades   79.1% of set   NET  -1.194
    exit=cap     58 trades   20.9% of set   NET  +6.226
    LONG  125 trades NET -0.124 se 0.484   SHORT 152 trades NET +0.758 se 0.488
    median hold 39 bars, mean 146 bars (cap 500)

The entire result is 58 positions that never closed, marked to market at an
arbitrary 500-bar cutoff. Those are not exits. NOT A FINDING.

### THE ARMED SUBSET LOOKS GREAT AND IS NOT TRADEABLE

Restricted to the 182 setups whose MFE reached Active Price, every arm is
strongly positive (BOS control +0.503, structure trail +0.579). That is
selection on the outcome — you cannot know at entry which trades will reach
0.5R. Recorded only because it shows that even there, trailing does not beat
the control: +0.579 against +0.503 on se ~0.20.

### THE ROOT CAUSE, AND IT IS NOT THE EXIT

MFE measured with no target and no trail, so the exit rule cannot truncate it:

    reached Active Price (0.5R)  65.7%      reached 2R  35.4%
    reached 1R                   50.5%      reached 3R  27.8%
    median MFE 1.01R   p75 3.35R   p90 9.55R

A setup whose median best-case excursion is 1.01R against a 1R stop has no room
for any exit rule to work in. A third never reach 0.5R at all, so on those the
trail never arms and every trailing arm IS the control. The exit was never the
binding constraint — the entry does not generate enough favourable excursion
relative to its own stop.

### THE OBSTACLE CHECK, RE-TESTED UNCONFOUNDED

Variant 4 could not read this filter because BOS was both the obstacle and the
exit. Under a trailing exit that circularity is gone:

    structure trail   path clear    250   0.012  se 0.149
                      path blocked   27   0.156  se 0.272
    mfe - 1.5R        path clear    250  -0.024  se 0.113
                      path blocked   27   0.395  se 0.311

The blocked set still reads no worse than the kept set, so there is still no
evidence the filter helps. But at n=27 and se ~0.3 this cannot be read either
way. Correct status: NO EVIDENCE OF BENEFIT, SAMPLE TOO SMALL TO REFUTE.

### WHAT THE se COLUMN DOES TO THE EARLIER WRITE-UPS

The cumulative progression was recorded as "each source filter helped and each
helped less": -0.46 -> -0.11 (FVG) -> -0.085 (SCOB). At n~270 the se on these
is roughly 0.10-0.14. The first step, 0.35R, is around 3 se and is probably
real. The FVG -> SCOB step of 0.025R is a fifth of one se and is NOT
distinguishable from nothing. Variant 4's obstacle arm, "0.008 -> -0.027", was
read as a degradation; it is noise. Those small deltas were over-read, and this
correction applies to every table in this file before this section.

### STATUS

T6 was the last large hole and the only road left open. It is now measured and
it does not open. Across ten exit rules on a shared setup set, nothing is
distinguishable from zero. The MFE ceiling says why, and it is an entry problem,
not an exit problem.

---

## THE Min30 CELL DOES NOT REPLICATE (research/lit_repl.py)

Min30 had come up best twice — Variant 3 (+0.071, n=88) and T6 (+0.245, se
0.240, n=91). Neither was claimed, because both readings came from the SAME 30
symbols over the SAME 120 days: one observation seen twice, not two
confirmations. The rank split is the precedent — positive at n=102 on two
agreeing arms, every rank negative at n=1214.

So: a 2x2 of {discovery, held-out} symbols x {recent 120d, older window}.
Held-out symbols are turnover ranks 31+, built the way
research/studies/trend_holdout.py builds its hold-out — the ones the bot does
not scan. The older window is the part of 333 days of deep history ending
before the recent 120 begin, so the windows share no bars. One engine pass per
symbol over the full history, setups split by timestamp, first 500 bars dropped
for warm-up.

### Min30, the cell under test

    exit at BOS            n    NET R      se       t
    discovery / recent    70    0.298   0.300     1.0    <- the original claim
    discovery / older    131   -0.162   0.138    -1.2    <- SAME syms, sign flip
    held-out  / recent    62    0.340   0.217     1.6
    held-out  / older    119   -0.082   0.167    -0.5    <- the real OOS cell

    structure trail
    discovery / recent    70    0.112   0.279     0.4
    discovery / older    131   -0.130   0.120    -1.1
    held-out  / recent    62    0.564   0.422     1.3
    held-out  / older    119   -0.240   0.091    -2.6   >2se NEGATIVE

Same symbols on a different window flips the sign. New symbols on a new window
are negative, significantly so under the structure trail. The Min30 reading
does not survive either change.

### IT WAS NEVER A TIMEFRAME EFFECT — IT WAS THE WINDOW

Every recent cell was positive and every older cell negative, in both symbol
sets and all three exit rules. Pooling on window alone, all timeframes and both
symbol sets together:

                          n    win%    NET R      se       t
    exit at BOS
      recent 120d       457    39.2%    0.033   0.101     0.3
      older window      860    35.9%   -0.137   0.057    -2.4   >2se
    structure trail
      recent 120d       457    38.1%    0.073   0.106     0.7
      older window      860    37.6%   -0.192   0.042    -4.5   >2se
    mfe - 1.5R
      recent 120d       457    44.0%    0.139   0.083     1.7
      older window      860    41.3%   -0.117   0.041    -2.9   >2se

Two things follow, and the second is the important one.

1. THE RECENT WINDOW IS NOT POSITIVE EITHER. +0.033, +0.073, +0.139 at t of
   0.3, 0.7, 1.7. All inside noise. "Min30 is good" was a slice of a window
   that is not itself distinguishable from zero.

2. THE OLDER WINDOW IS SIGNIFICANTLY NEGATIVE, on nearly twice the sample and
   on every exit rule. This is the best-powered measurement in the whole
   programme — 860 setups, 333 days, discovery and held-out symbols pooled —
   and it says the setup loses.

The long/short split in the recent window rules out a simple drift story:
LONG +0.009/+0.109/+0.183 and SHORT +0.052/+0.045/+0.104 across the three exit
rules, neither direction significant.

### THE SURVIVORSHIP DIRECTION MAKES THIS STRONGER, NOT WEAKER

research/deep.py: "The universe is the sixty most liquid perpetuals TODAY.
Walking those same sixty back a year over-samples coins that went up... A
replication that comes back BETTER than the 42-day result is evidence of that
bias, not of a stronger edge."

The older window sits further back, so it carries MORE of that bias and should
if anything look better. It looks worse. The negative is not a survivorship
artefact; survivorship was pushing the other way.

### THE ONE POSITIVE CELL, AND WHY IT IS NOT CLAIMED

held-out / recent, Min30, mfe-1.5R: +0.442 on se 0.193, t=2.3. It is one cell
out of 36 tested, where roughly two beyond 2se are expected by chance alone,
and its own held-out/older counterpart is -0.141. Not claimed.

### STATUS

The entry model as implemented has negative expectancy on the best-powered
sample available. The earlier near-zero readings were an underpowered recent
window, not a breakeven system. Combined with the T6 finding — median MFE 1.01R
against a 1R stop — the conclusion is consistent: this is an entry problem, and
no exit rule, filter or timeframe selection measured so far changes it.

---

## STAGE A, PRE-REGISTERED — AND TWO ERRORS IN ALL EARLIER LIT WORK

Checking the LIT research against the repository's own conventions rather than
against itself found two errors in it. They push in opposite directions.

### ERROR 1 — the fee model was the reference's, not the repository's

Every LIT measurement charged COMMISSION = 0.0005 per side, 0.10% round trip,
from `LIT_SOURCE.md` Ch.24. `research/harness.py` defines the repo's model:
maker 0.010%, taker 0.022%, charged in R as fee_pct / risk_pct. The
conservative round trip is 0.032% — roughly a third of what was charged.

### ERROR 2 — the unit of evidence was the trade, not the bet

`research/studies/fvg_continuation.py` and six other studies average trades
sharing a bar open time into one observation. LIT counted each trade
separately, understating standard error and overstating significance.

`research/lit_recheck.py` isolates both. The fee correction did most of the
work; bet-grouping only reduced 860 trades to 683 bets.

    pooled, older window       NET R      se       t
    source fee, trades        -0.192   0.042    -4.5
    source fee, BETS          -0.181   0.044    -4.1
    repo fee,   trades        -0.131   0.042    -3.1
    repo fee,   BETS          -0.115   0.044    -2.6   (structure trail)

    exit at BOS,  repo + BETS -0.056   0.061    -0.9
    mfe - 1.5R,   repo + BETS -0.033   0.044    -0.7

**This retracts the previous section's headline.** "Significantly negative on
the best-powered sample" does not survive the corrections: two of three exit
rules on the out-of-sample window are indistinguishable from zero once the
repo's own fee and unit of evidence are used. Only the structure trail stays
significantly negative. The correct statement is weaker and duller — the
zone-entry strategy is not demonstrably profitable AND not demonstrably dead.

### STAGE A — frozen in PREREG_lit_stage_a.md, committed at 50801c7 before the run

Naked continuation: enter at the IDM-break close, stop at the raid extreme, no
buffer, with-trend only, MAIN depth. 60 symbols, three timeframes, 333 days,
5112 setups / 3632 bets, scored through `harness.simulate_market`.

    policy          bets    R/bet     SE      t     win     PF
    FIXED_1R        3632   -0.478  0.021  -22.3   36.0%   0.39
    FIXED_2R        3632   -0.296  0.027  -11.1   33.4%   0.63
    BOS_TARGET      3632    0.806  0.256    3.1   20.0%   1.82
    T6_PIVOT        3632    0.564  0.149    3.8   21.0%   1.59
    T6_STRUCTURE    3632    0.772  0.311    2.5   11.5%   1.61

**VERDICT: INCONCLUSIVE.** Criterion 1 met by BOS_TARGET; criterion 2 failed,
P(realized loss > 1.5R) = 14.3% against a 10% ceiling. Work stops.

### THE STOP IS DEGENERATE, AND CRITERION 2 CAUGHT IT

    stop distance, % of entry: median 0.422%  p25 0.179%  p10 0.076%
    distance to BOS at entry:  median 8.67R   p90 49.43R
    hold time: median 1 bar    MAE: median -1.35R
    P(realized loss > 1.0R): 98.6-99.9%       worst 22.45R

The specified stop is the break bar's own wick measured from that bar's close.
A quarter of setups risk under 0.18% of price — inside crypto noise. So the
risk unit is fictional: 99% of losses exceed it, and BOS sitting a median
8.67R away is a tiny denominator rather than a rich target. BOS_TARGET's
+0.806R is 20% of trades paying ~8R. A lottery ticket, not an edge.

This also explains the old "no stop distance works at all": at the p10 stop the
0.10% fee cost 1.31R per trade, more than the whole risk unit. The fee error
was catastrophic *because* the stop is degenerate.

The failure is located in the STOP DEFINITION, not demonstrated in the entry
event. Among the 60.0% of setups reaching Active Price, median MFE is 1.91R and
48.3% exceed 2R — there is real favourable excursion; the risk unit under it is
broken. Testing a wider stop now, after seeing this, is the post-hoc fitting
PREREG §10 forbids. It needs its own pre-registration.

### STAGE A-PRIME (T8) — NOT RESOLVED, AND THE REASON IS SPECIFIC

Two definitions of "the opposite pullback" bracket the source's object without
hitting it. Carried across cycles it sits a median 7.76% of price away and
loses every race by construction (6.2% reach). Scoped to the live BOS cycle
there are no qualifying grabs at all — at the moment of a grab the opposite
pullback has not formed yet; it forms during the reaction the grab causes.

The Pine engine keeps both directions live through the P8 idle observer, which
is where its "BOS near → Opp PB reach" figure comes from. `lit_v3` does not
expose that. **T8 stays unresolved and no rate is claimed.**

### AND A LIMIT THAT IS NOT WORKED AROUND

The specified Pine→Python parity gate CANNOT be executed here: there is no Pine
compiler in this environment and `riptide-lit-v2.pine` has never been compiled.
Agreement between it and `lit_v3` is unverified and no parity claim is made
anywhere. The external validation that does exist is against the reference
indicator's own published statistics (ZEC 30m IDM→BOS 65.6% vs 65.0%).

---

## STAGE B — THE STOP DEFINITION. FAMILY CLOSED.

Pre-registered in `PREREG_lit_stage_b.md`, committed at `becc0bf` before the
run. Stage A failed on its risk unit rather than visibly on its entry, so
Stage B holds entry, exits, scorer, fees and unit of evidence fixed and varies
only where the stop goes.

### THE STOP THAT WAS REQUESTED DOES NOT WORK, AND GEOMETRY SAID SO FIRST

Stop widths were measured before any P&L existed — width and fee-in-R are
properties of the setup and carry no return information:

    stop        setups  skipped  med width     fee/R   med BOS dist
    PRIOR_PB      4440      929     2.917%    0.011R          1.25R
    RAID          5112      257     0.422%    0.076R          8.67R
    IDM_PIVOT     2530     2839     0.347%    0.092R          8.71R
    LEG           4994      375     8.407%    0.004R          0.42R
    CHOCH         5330       39    12.213%    0.003R          0.28R

The IDM pivot stop is NARROWER than the raid stop it was meant to replace: for
a long the IDM pivot sits ABOVE the raid low, because the raid is the sweep
through that pivot. It was registered and run anyway, and it reproduces Stage
A's failure exactly — worst realized-loss tail of all five at P(>1.5R)=19.9%.

### THE FIX WORKED, AND THEN THE EDGE VANISHED

    realized loss      median  P(>1.25R)  P(>1.5R)   worst
    RAID (Stage A)      1.13R     28.5%     14.3%   22.45R
    PRIOR_PB (primary)  1.02R      4.3%      1.9%    9.45R

Criterion 2 passes at 1.9% against a 10% ceiling. The risk unit is real.

    control exit     RAID stop   PRIOR_PB stop
    FIXED_1R            -0.478          -0.028
    FIXED_2R            -0.296          +0.021
    BOS_TARGET          +0.806          +0.024

**VERDICT: INCONCLUSIVE.** No control exit reaches t >= 2.5. Family closed.

BOS_TARGET's collapse from +0.806 to +0.024 is the artefact being removed, not
a degradation: median distance to BOS falls from 8.67R to 1.25R over the same
setups once the denominator stops being one candle's wick.

### A RETRACTION OF STAGE A'S ONE OPTIMISTIC LINE

Stage A reported median MFE 1.91R with 48.3% exceeding 2R among Active-Price
reached, and called it real favourable excursion. On the primary stop it is
1.09R and 8.1%. It was measured in the same fake units. **Withdrawn.**

### THE STRONGEST PART OF THE RESULT

Three stop widths spanning 2.9% to 12.2% of price — PRIOR_PB, LEG, CHOCH —
all put every fully-specified control within 0.03R of zero. The finding is not
sensitive to the stop choice once the stop is sane.

### RECORDED, NOT CLAIMED

The trailing arms are the best cells on the primary stop: T6_PIVOT +0.145
(t=2.5) and T6_STRUCTURE +0.138 (t=2.2), beating BOS_TARGET on paired deltas
(z=2.5, 2.4). PREREG §5 restricted criterion 1 to fully-specified controls
because T6 is an open [GAP]; across 25 cells a |t| of 2.5 is near what chance
produces, and the two arms are not independent. Pursuing them needs a new
pre-registration with a trail as primary, which is the fitting-by-iteration
§5 forbids. That is a human's call, not this process's momentum.

### CONCLUSION

The LIT structure engine is sound and externally validated (ZEC 30m IDM→BOS
65.6% vs the reference's 65.0%). The LIT trading family, across two
pre-registered experiments and five stop definitions, shows no economic edge
net of costs. Stage A failed on a broken risk unit; Stage B fixed it and found
roughly zero.

---

## STAGE C — THE TRAILING EXIT ON UNTOUCHED SYMBOLS. FAMILY CLOSED PERMANENTLY.

Pre-registered in `PREREG_lit_stage_c.md` at `639d287` before the run. A third
prereg, which Stage B §5 had called fitting by iteration; it exists because a
human authorised one clean test of the trail lead, and it committed against a
fourth before any number existed.

Two design corrections made before running:

- **The previous "held-out" tier is not out of sample** and was not used as
  one. Ranks 31-60 were inside Stages A and B. Stage C used the 55 symbols in
  the ranked universe that took no part in either.
- **The t ≥ 3.0 bar I proposed was refuted by a power calculation** and
  dropped. It needs ~4770 bets, more than Stages A/B produced on the full
  population, so it would have returned FAIL even if the effect were exactly
  real. Replaced by two conditions required together, which is jointly
  stricter while staying inside available power.

### RESULT

                             Stage A/B      untouched tier
    T6_PIVOT, standalone        +0.145           +0.114   (t 2.5 -> 2.4)
    paired delta vs control     +0.120           +0.068   (z 2.5 -> 1.5)

    criterion 1  R/bet>0, t>=2.0      MET      (+0.114 at t=2.4)
    criterion 2  paired delta, z>=2.0 NOT MET  (+0.068 at z=1.5)

**VERDICT: INCONCLUSIVE.** Family closed permanently.

The reproduction check on Stage A/B symbols returned +0.145 at t=2.5 on 3195
bets — Stage B to three decimals — so the pipeline is confirmed.

### THE THINGS THAT MAKE THIS A CLEAN NULL RATHER THAN A WEAK ONE

**Adequately powered.** 3027 bets, SE 0.0468, MDE 0.094R. Stage B's paired
delta would have registered at z=2.6 here. The test could see what it was
looking for and found about half. The underpower declaration did not fire.

**Both guards clean.** 3.0% horizon exits contributing +0.010R/trade, so this
is not the mark-to-market artefact that produced the earlier "+0.360" false
positive. P(loss>1.5R) = 1.3%, median loss 1.01R, worst 4.03R — Stage A's
broken risk unit is fully absent.

Neither of the two ways this measurement could have lied is what happened.

### THE READING

Shrinkage of about half on an untouched tier is the winner's-curse signature:
T6_PIVOT was the best of 25 cells in Stage B, and the best of 25 regresses. A
real-but-smaller effect looks identical and one test cannot separate them. The
honest pooled estimate of the trail's advantage is around +0.09, which is not
distinguishable from zero on any sample this project can assemble.

Not pooled to manufacture significance, not re-sliced, not re-registered.

### THE SEQUENCE

    Stage A   naked continuation, raid stop     INCONCLUSIVE  risk unit broken
    Stage B   five stop definitions             INCONCLUSIVE  stop fixed, edge gone
    Stage C   pivot trail, untouched symbols    INCONCLUSIVE  effect halved, bar missed

The LIT **structure engine** is sound and externally validated (ZEC 30m
IDM→BOS 65.6% vs the reference's 65.0%). The LIT **trading family** does not
show an economic edge that survives out-of-sample testing at a pre-specified
bar. Closed.


---

## riptide-lit.pine (v1) REMOVED

Deleted at the user's request. It was the original LIT structure indicator,
v0.7.18, frozen since `riptide-lit-v2.pine` was built and untouched by every
change after that.

Nothing depended on it. `deploy/check-parity.py` targets
`riptide-indicator.pine`, not this file; no production module imported or read
it; the only mention inside `riptide/` is a note about **v2**. Removing it
breaks nothing.

Documents earlier in this changelog, and in `LIT_V2_DESIGN.md`,
`LIT_SOURCE.md` and `research/lit_v01.py`, still refer to it. Those references
are left as they are: they are a record of what was done at the time, and
rewriting history to hide a deleted file would be worse than a dangling name.

**Recovery**, if it is ever wanted:

    git show bebcbbe:riptide-lit.pine > riptide-lit.pine

`riptide-lit-v2.pine` is now the only LIT indicator. It carries the same
structure engine with every undefined case turned into a named policy, and its
defaults match the Python forward record.


---

## riptide-structure.pine REMOVED

Deleted at the user's request. A standalone 460-line v5 indicator, "Market
Structure Inducements ICT CHoch BOS Sweeps", carrying a period-based pivot
engine alongside a Pullback (LIT) mode.

Nothing loaded it. `deploy/check-parity.py` targets `riptide-indicator.pine`;
no production module read it. `research/studies/lit_trend.py` and
`research/lit.py` name it in their docstrings, but they PORTED its ChoCh block
into Python rather than importing the file, so those studies still run exactly
as before.

**Recovery**, if it is ever wanted:

    git show fc04f65:riptide-structure.pine > riptide-structure.pine

Pine files remaining: `riptide-indicator.pine` (production, untouched),
`riptide-lit-v2.pine`, `riptide-reversal.pine`, `liquidity-trendline.pine`.


---

## DEFECT: Main structure latches in PH_SEEK

Found while designing the inducement measurement, not looked for.
`research/studies/lit_main_latch.py` reproduces every number below.

**`PH_SEEK` with no CHoCH is a one-way door.** The CHoCH level is created at
step 7, *when a BOS breaks*. So the first BOS after bootstrap has no opposing
boundary: step 8 needs `x.ch.ready(i)`, step 5 will not publish an IDM outside
DISCOVER/TRACK, and there is no timeout and no invalidation. If that first BOS
is never broken, Main emits nothing for the rest of the chart.

Every later cycle owns both boundaries and can race between them. The bootstrap
cycle is the only one that can trap — which is why every latched symbol latches
between bar 20 and bar 164 and never recovers.

Measured on 28 symbols, 333 days:

| | latched | symbols |
|---|---|---|
| Min30 | 4/28 (14%) | BNB, ONDO, TIA, **BTC** |
| Min15 | 1/28 (4%) | BNB |

Two triggers, one dead end:

| symbol | BOS | max high after | closes beyond | trigger |
|---|---|---|---|---|
| BNB Min30 | 1374.64 | 1316.98 (−4.2%) | 0 | never reached |
| TIA Min30 | 1.2140 | 1.1810 (−2.7%) | 0 | never reached |
| ONDO Min30 | 0.8354 | 0.8425 (+0.8%) | 3 | poked, no body close |
| BTC Min30 | 115908.9 | 116398.8 (+0.4%) | 1 | poked, no body close |

`M_BOS` is Body & Sweep, which wants a sweep and then a body close, so a lone
poke does not count. Internal structure on the same candles stays healthy
throughout on every latched symbol — this is the engine's silence, not the
market's.

**This is why Main looked dead on BTC 30m.** The user reported that different
settings worked per timeframe and moved the signal depth to Internal. On BTC
Min30 the Main tracker stops at bar 25 of 15,983 and never emits again, so
there was nothing to see. That observation was correct and this is the cause.

**What it affects.** `riptide-lit-v2.pine` renders Main and a faithful port has
the same trap. LIT_FORWARD_V1 collects Main setups. Stages A, B and C all
measured Main.

**What it does not do** is overturn the three INCONCLUSIVE verdicts. A smaller
sample is less power, and those stages failed to find evidence rather than
finding a negative. It does mean their effective sample was smaller than
reported, and selected toward symbols whose first BOS happened to break.

No fix is applied here. An escape is a new rule and needs a name, a default and
its own measurement; two candidates are named in the study and neither is
picked. The frozen engine stands, `rules_hash` is unchanged, and both frozen
test scripts still pass.

### Resolution: P9, the bootstrap CHoCH — PROPOSED, default still off

`POL.seekCh = "leg"` gives the first cycle after bootstrap the CHoCH every
later cycle already has: the leg extreme against the trend, the exact mirror of
the BOS. Parameter-free, so it respects `Pol`'s contract that no policy may
introduce a number.

Measured over two pre-registered rounds — see `research/LIT_SEEK_ESCAPE.md`:

* repairs **14 of 14** `PH_SEEK` latches (5 in sample, 9 on 71 untouched
  symbols); BTC Min30 goes from 1 IDM break in 333 days to 28
* zero invariant violations, zero panels made unhealthy
* **99.8%** of existing `idm_break` events preserved on panels that were
  already healthy, 1.6% inflation

Round 1 rejected it on a gate I had written against the symptom rather than
the cause; that verdict is kept in the record rather than edited away. Round 2
re-ran it with the gate naming the mechanism and the held-out universe enlarged
from 30 to 80 requested symbols to pay for the second look.

Two things are stated in the findings rather than smoothed over: retention did
not separate `leg` from `raid` — a pre-registered tiebreak did — and the v2
gates would have let `raid` pass while it converted one panel's `SEEK_LATCH`
into a `LOCK_STALL`.

A second defect was found and **not** fixed: `PH_LOCK` with both boundaries
outside the range price goes on to trade, 3 of 191 panels (1.6%).

**The default remains `"none"` and the frozen engine is byte-identical under
it.** Switching it on is a user decision, and in production it would be
LIT_FORWARD_V2 — never a patch to V1, and the two records never pooled.

---

## P9 TURNED ON — the forward record is now LIT_FORWARD_V2

`POL.seekCh` defaults to `"leg"`. `FWD_VERSION` is `LIT_FORWARD_V2` and
`rules_hash()` is `ec15663860a09853` (V1 was `4b105c593bc48469`).

Confirmed end to end rather than assumed: with the new default, the latch study
reports **0/28 latched on Min30 and 0/28 on Min15**, against 4 and 1 before.
BTC Min30 goes from 10 Main events at 0.05 coverage to **229 at 0.98**.

### `RULES["policies"]` — a hole in the hash, closed

`RULES` named the engine module but not how it was configured, so a policy flip
inside `research.lit_v3` left `rules_hash()` **unmoved** — the exact silent
change that file's docstring promises to make impossible. The policies are now
part of `RULES`, and `tests/test_lit_forward.py` asserts each one against the
live `POL` and checks that flipping one moves the hash.

### V1 rows, and the part that costs something

Every query in `forward.py` filters on `strategy_version`, and
`signals.setup_id` mixes the version into the key, so V1 and V2 cannot collide
even on the same bar of the same symbol. V1 rows are not touched.

**Any V1 setup still PENDING at the switch will never resolve** — the resolver
only reads the current version. Those are *censored* observations and must be
reported as censored, not as timeouts. `DEPLOY.md` and
`research/LIT_FORWARD_STATUS.md` carry the SQL to count them. Nothing rewrites
them, because a rewrite would be worse than the censoring.

### riptide-lit-v3.pine

A new file. **`riptide-lit-v2.pine` is untouched** so anything recorded under
V1 stays reproducible.

Built from v2 by five asserted anchor replacements, each required to match
exactly once, so a silent mis-patch of a 2,000-line file was not possible.
Changes: the header note, the `Bootstrap CHoCH [P9]` input (two options — "Leg
extreme (V2)" default, "Off (V1)" for v2.3's exact behaviour), the engine block
at the IDM break, and a setup tooltip that names whichever version the switch
selects.

`nCh` is deliberately NOT incremented by the P9 block. It mirrors the engine's
`choch_create + choch_move`, and the engine books a bootstrap CHoCH under its
own separate key; counting it in Pine would make the debug panel disagree with
the record.

The third arm, `raid`, is **not offered in Pine**. It was measured and rejected
— it converted one latched chart into a different kind of stall — and shipping
a rejected arm as a setting invites misuse.

### deploy/pine-static-check.py

No Pine compiler exists in this environment, so v3 was checked statically
against v2 as a control: v2 compiles, so any finding present in both is a
checker false positive and only a finding unique to v3 is real. **11 findings,
all 11 present in v2, none unique to v3.**

The checker was itself verified against a file with five planted errors — a
reserved word as an identifier, a comma-separated declaration, a comma-joined
assignment, a function used before declaration, and a continuation line on a
multiple-of-4 indent — and catches all five without flagging a normal
`input.int(..., group = g, tooltip = t)` line. A clean result from a checker
that cannot fail would mean nothing.

**This is still not a compile.** Pine↔Python parity remains open, and
`research/LIT_FORWARD_STATUS.md` still lists it as the blocking precondition.

### What this does NOT do

It does not revisit stages A, B or C. They were measured under the latching
engine, so their samples were smaller than recorded and selected toward symbols
whose first BOS broke — but a smaller sample is less evidence, not contrary
evidence, and all three stay INCONCLUSIVE. Re-running them is a new experiment
needing its own pre-registration.

A second trap state remains **open and unfixed**: `PH_LOCK` with both
boundaries outside the range price goes on to trade, 1.6% of panels.

---

## PH_LOCK STALL — DIAGNOSED, NOT FIXED

`research/LIT_LOCK_STALL.md`, from `research/studies/lit_lock_stall.py`.

**1.1% of panels** (2 of 189) against the `PH_SEEK` latch's 7.3%. Down from 3
before P9; `leg` incidentally cleared CATE Min30, which is noted rather than
claimed.

Same shape as `PH_SEEK` one level up: `PH_LOCK` exits only on a BOS break or a
CHoCH break, step 5 caches corrections as latent without publishing an IDM, and
there is no timeout or invalidation.

**Two triggers, and the second one corrected an earlier claim.** XMR's
boundaries were never reached — 5% below the lowest low, 29% above the highest
high, over 10,384 bars. **KAS's BOS was wicked twice** (reaching 0.0419 against
0.04145) with no bar closing beyond, so Body & Sweep declined the break. That
is the same doorway that produced two of the four `PH_SEEK` latches. The
earlier write-up in `research/LIT_SEEK_ESCAPE.md` said "two boundaries, neither
reachable"; that is true of XMR and false of KAS, and it has been corrected
where it was written.

**It cannot be repaired the way P9 was.** `PH_SEEK with ch.on == False` names a
state; a stalled lock does not — both boundaries exist and are well-formed, and
the only thing separating a stall from a working lock is that the data ran out.
Duration does not separate them:

    stalled, stuck at the end     8,452 – 10,385 bars
    recovered, longest lock       388 – 14,283 bars (median 3,837)

PI Min15 recovered from a **14,283-bar** lock — longer than either stall. Both
stalls sit below the 95th percentile of lock durations on healthy panels. Any
rule that catches them is phrased on duration, and a duration rule is a number,
which `Pol`'s contract forbids.

Three candidates are named and **none is chosen**: `latent_out` (publish the
correction LOCK already caches — the only one addressing both triggers),
`re_leg` (P9 without its guard — a different engine, not a repair), and
`stale_lvl` (needs a definition of "superseded" that does not smuggle in a
number; I do not have one). An expiry arm was rejected before measuring, as
P9's was.

**Recommendation: leave it.** 1.1% against 7.3%, and the fix costs more than it
buys. The cost of leaving it is bounded and now documented — about one chart in
ninety goes quiet with a named cause, which is a different situation from BTC
30m going quiet and being read as a quiet market.

---

## riptide-indicator-v2.pine — a market structure layer beside Riptide

**`riptide-indicator.pine` is untouched** and stays the parity target
`deploy/check-parity.py` reads against `riptide.conf` (still passing: all 24
shared settings agree). v2 is that file plus one new section, 12, at the end.

Section 12 draws CHoCH, BOS, inducements and sweeps from the "Market Structure
with Inducements & Sweeps" script the user supplied, ported v5 → v6. It reads
no Riptide state, writes none and feeds no signal, so every alert, entry, stop
and target is identical with it on or off.

**No claim is attached to it, and that is measured rather than modest.** Seven
definitions of inducement — this engine's among them — were tested as a
covariate on Riptide's own 6,663 bets and none sorted good setups from bad;
every one changed sign across the four panels
(`research/INDUCEMENT_ON_RIPTIDE.md`). Nothing in section 12 prints a win rate
or calls anything high-probability, and the master tooltip says so outright.

**Attribution.** The copy supplied carried no author or licence header.
TradingView scripts are normally MPL-2.0 with a `// ©` line, and the header
belongs at the top of this file before it is redistributed. Section 12 is not
original work of this project and says so.

### Port changes, all named in the file

* v5 → v6, splitting the original's comma-joined statements
  (`a.set_xy1(...), a.set_xy2(...)`), which v6 rejects
* every identifier prefixed `ms` — `n`, `top` and `swings` all already exist in
  this file and would have collided silently
* `os[1]` read as `nz(os[1], 0)`: a `var`'s history is na on bar 0 and
  `os := na` would poison every bar after it
* `if top` → `if not na(msTop)`, and the per-direction draw guards restructured
* **drawings recycled on their own budget.** The original creates two objects
  per event and deletes none; dropped in as-is it would evict Riptide's own
  entry and stop lines out of the shared 500-drawing allowance. Same rule the
  "All imbalances" layer already follows.

### Two checkers, both verified able to fail

`deploy/pine-static-check.py` compares a Pine file against a known-good control
— the original compiles, so a finding in both is a false positive and only one
unique to v2 is real. **11 findings, all 11 in the control, none unique.** The
checker itself catches five planted errors (reserved word as identifier,
comma-separated declaration, comma-joined assignment, use-before-declaration,
continuation line on a multiple-of-4 indent) without flagging a normal
`input.int(..., group = g)` line.

`deploy/ms-port-check.py` answers what the static checker cannot: is the port
faithful? It extracts every condition and assignment from both sources, renames
the original's identifiers, and pairs them. **EVERY CONDITION AND ASSIGNMENT
MATCHES**, with 8 differences accounted for explicitly as renames or
restructuring rather than normalised away silently. Planting a flipped `>` and
a dropped `not` is caught with exact was/now pairs.

Neither is a compile. Nothing here has been run through TradingView.

### One property worth recording

This engine's boundaries **migrate** — `msTopY` and `msBtmY` are re-seeded by
every new swing — so a level cannot go stale and the state machine cannot
deadlock. The LIT engine fixes its boundaries at creation, which is exactly
what produced the `PH_SEEK` latch and the `PH_LOCK` stall. Migration is not
free: structure re-reads itself as swings form. But it cannot hang.
