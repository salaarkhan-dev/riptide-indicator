# The `PH_LOCK` stall — diagnosis

Found while validating P9 and deliberately left unfixed there. This is its own
diagnosis. **No fix is proposed and no arm is selected.**

Study: `research/studies/lit_lock_stall.py`, output alongside it. Run against
the engine as it now ships (`POL.seekCh = "leg"`).

## The short version

It is real, it is **1.1% of panels**, and — unlike the `PH_SEEK` latch — **it
cannot be repaired the way P9 was.** A stall is not distinguishable from a long
lock that happened to resolve, so every rule that would catch it reduces to a
bar count, and `Pol`'s contract forbids numbers.

My recommendation is at the bottom, and it is not "fix it next".

---

## 1. Prevalence

189 panels, 30 discovery symbols plus a held-out universe, Min30 and Min15,
333 days:

| | count |
|---|---|
| panels | 189 |
| unhealthy (Main dead while Internal lives) | 2 |
| …of those, `PH_LOCK` stalls | **2 (1.1%)** |
| …of those, anything else | 0 |

Down from 3 before P9 was turned on. `leg` incidentally cleared CATE Min30 —
noted, not claimed, since it was not designed to do that and one panel is not
evidence.

For scale: the `PH_SEEK` latch P9 repaired was **7.3%**.

## 2. Mechanism

Identical in shape to `PH_SEEK`, one level up. `PH_LOCK` is entered at an IDM
break when a CHoCH already exists. Its only exits are step 7 (BOS breaks) and
step 8 (CHoCH breaks). Step 5 will not publish a new IDM in LOCK — it caches
the correction as `latent_cached`. There is no timeout and no invalidation.

Where the boundaries come from, and how they go stale:

* **BOS** — set at the IDM break to the leg extreme in the trend direction.
  Fresh, but anchored to the whole structural leg, so after a large impulse it
  can sit far beyond anything that follows.
* **CHoCH** — *inherited*. Set at the previous BOS break from `phLo`/`phHi`,
  the extreme reached while that cycle sat in SEEK or LOCK. One spike during
  that window and the CHoCH keeps it forever.

Neither is re-derived while the lock holds.

## 3. Two triggers, and the second one changes the diagnosis

Counted from the candles rather than described, because the obvious story is
only half right:

| panel | level | price | wick reached | closed beyond | extreme | trigger |
|---|---|---|---|---|---|---|
| XMR Min30 | BOS | 276.66 | 0 | 0 | 291.83 | never reached |
| XMR Min30 | CHoCH | 800.72 | 0 | 0 | 569.27 | never reached |
| KAS Min30 | BOS | 0.04145 | **2** | 0 | 0.0419 | **reached, break declined** |
| KAS Min30 | CHoCH | 0.02475 | 0 | 0 | 0.025 | never reached |

XMR is the story you would guess: two boundaries outside everything price
traded for 10,384 bars, 5% below the lowest low and 29% above the highest high.

**KAS is not.** Its BOS was wicked twice, reaching 0.0419 against a level of
0.04145 — and no bar closed beyond it. `M_BOS` is Body & Sweep, which wants a
sweep and *then* a body close, so a lone wick is not a break. The level was
reached and the break mode refused it.

That is the same trigger that produced two of the four `PH_SEEK` latches (ONDO
and BTC). So the two defects share both a shape and a doorway:

> **The defect is a phase with no escape hatch. The trigger is either a level
> price never reaches, or a level price touches while the break mode declines
> it.** A diagnosis phrased purely as "the boundaries drifted too far apart"
> would be wrong for half the observed cases, and a repair aimed only at
> distance would miss them.

I wrote that wrong first — the P9 findings describe this as "both boundaries
unreachable", which is true of XMR and false of KAS. Corrected here.

## 4. Why this cannot be fixed the way P9 was

P9 was repairable because `PH_SEEK with ch.on == False` is a **structural**
description. It names a state, not a magnitude, so a parameter-free rule could
address it.

A `PH_LOCK` stall has no such description. Both boundaries exist and both are
well-formed. The only thing separating a stall from a working lock is that the
data ran out first — and duration does not separate them:

```
longest lock ever held, across 189 panels:
  p50    3,845 bars      p95   10,509 bars
  p75    5,606 bars      p99   11,492 bars
  p90    8,534 bars      p100  14,283 bars
```

| | range |
|---|---|
| stalled, still stuck at the end of data | 8,452 – 10,385 bars |
| recovered, longest lock held | 388 – **14,283** bars (median 3,837) |

**PI Min15 recovered from a 14,283-bar lock and ended in TRACK** — a longer
lock than either stall, resolved. Both stalls sit *below* the 95th percentile
of lock durations on panels that were fine.

So the overlap is total. No rule phrased on how long a lock has lasted can
separate a stall from a healthy lock, because the healthy ones last longer. And
a rule phrased on duration is a bar count, which `Pol`'s contract — *"No policy
may introduce a number"* — forbids regardless.

## 5. Candidate escapes — named, none chosen

| name | rule | honest assessment |
|---|---|---|
| `latent_out` | let the correction LOCK already caches as latent publish an IDM, returning the context to TRACK | parameter-free; uses state the engine keeps and throws away; **does not depend on distance, so it addresses both triggers** |
| `re_leg` | re-derive the CHoCH from the current leg at *every* IDM break, not only when none exists | parameter-free — it is P9 with its `if not ch.on` guard removed — but it changes every healthy cycle, so retention will be far below P9's 99.8%. That is a different engine, not a repair |
| `stale_lvl` | invalidate a boundary once the leg that produced it has been superseded | parameter-free in principle, but "superseded" needs a definition that does not smuggle in a distance or a bar count. I do not currently have one |

**Rejected before measuring**, for the same reason P9's expiry arm was: anything
of the form *"abandon the lock after N bars"* or *"once the boundaries are more
than X% apart"* introduces a number.

If one is ever pursued, `latent_out` is the one to pre-register first — it is
the only candidate that addresses both triggers and the only one that adds no
new concept to the engine. That is a recommendation about ordering, not a
selection: choosing needs its own pre-registration with liveness gates and a
retention selector, exactly as P9 had.

## 6. What I would actually do

**Leave it.** Documented, not fixed.

* 1.1% of panels against P9's 7.3%.
* The two candidates that could work are either unproven (`stale_lvl` has no
  definition yet) or amount to replacing the engine (`re_leg`).
* `latent_out` is plausible but would change how every lock behaves, and the
  thing it buys is two panels out of 189.

The cost of leaving it is bounded and knowable: on about one chart in ninety,
Main structure will go quiet and stay quiet. That is now a documented failure
mode with a named cause, which is a different situation from the one this
started in — where the same thing was happening on BTC 30m and being read as a
quiet market.

`riptide-lit-v3.pine`'s header already tells a reader to suspect this first if
Main goes silent on a v3 chart.
