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
