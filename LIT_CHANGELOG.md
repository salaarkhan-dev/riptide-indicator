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
