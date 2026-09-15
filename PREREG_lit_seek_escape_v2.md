# PRE-REGISTRATION v2 — P9, judged against the mechanism it repairs

Supersedes the gates in `PREREG_lit_seek_escape.md`. The arms, the population,
the selector and every standing constraint carry over unchanged. Run by
`research/studies/lit_seek_escape2.py`.

## This is a second look at the same data, and that is a cost

v1 rejected `leg`. I am running it again with a changed rule. That is exactly
the move this project exists to be suspicious of, so the reasons and the price
are both stated before anything runs.

### What was wrong with v1's gate

G1 read *"zero latched panels"*. It should have read *"zero panels latched by
the mechanism under repair"*.

As written it cannot distinguish two situations that call for opposite
responses: **the fix did not work**, and **something else is broken**. `leg`
repaired 10 of the 11 `PH_SEEK` latches across both samples. The eleventh,
XMR Min30, is not a `PH_SEEK` latch at all:

```
XMR_USDT Min30   phase = LOCK   dir = bear   stuck 10,385 bars
    ch.on  = True   px = 800.72     (41% above the highest high that followed)
    bos.on = True   px = 276.66     (5% below the lowest low that followed)
```

That is a **second trap state**: `PH_LOCK` with both boundaries outside the
range price went on to trade. It has nothing to do with a missing bootstrap
CHoCH, and `leg` was never designed to touch it.

The correction is verifiable from the code and from the data, and it points the
same way regardless of which arm it happens to favour. That is the test for
whether a rule change is legitimate, and this one passes it.

### The price, paid up front

A corrected rule on the same symbols would be a free second attempt. So the
held-out universe is **enlarged from 30 to 80 requested symbols**, none in
`DISCOVERY`, giving the confirmation genuinely new panels rather than a
re-score of the 24 already seen.

### And there is no v3

If `leg` fails here it is rejected for good and `none` stands permanently. A
third specification would be fitting the rule to the answer, and at that point
the honest report is that the repair could not be validated.

## The latch taxonomy — named before it is counted

A panel is **unhealthy** when Main's last event lands before the halfway point
of the window while Internal's does not. Unhealthy panels are then classified
by the engine's final state:

| type | final state | meaning |
|---|---|---|
| `SEEK_LATCH` | `phase == PH_SEEK` and `not ch.on` | **the defect P9 repairs** |
| `LOCK_STALL` | `phase == PH_LOCK` | both boundaries unreachable — a different defect |
| `OTHER` | anything else | unclassified; reported, not excused |

## GATES

* **G1 LIVENESS — against the mechanism.** Zero `SEEK_LATCH` panels, in
  sample **and** on the enlarged held-out set. A surviving `LOCK_STALL` does
  not fail this gate; it is counted, reported, and left open.
* **G2 INVARIANTS.** `ctx.bad` empty on every symbol and both timeframes.
  Non-negotiable, unchanged.
* **G3 NO NEW LATCHES — against ANY mechanism.** No panel healthy under
  `none` may become unhealthy under the arm, of any type, in either sample.

**The asymmetry between G1 and G3 is deliberate and is the whole correction.**
An arm may only be judged on the defect it set out to repair, so G1 names the
mechanism. An arm may never make anything worse by any route, so G3 names none.
Failing to fix an unrelated bug is not a failure; creating one is.

## SELECTION — unchanged from v1

* **S1 RETENTION**, the deciding number: the share of `none`'s `idm_break`
  events surviving at identical bars on panels that were already healthy.
  Higher wins; `leg` takes a tie as the smaller assumption.
* **S1b INFLATION** reported alongside, so retention cannot be bought by
  emitting more.
* **S2 ECONOMICS reported and barred from the selection.** A structure repair
  chosen on its returns is the curve-fit the settings grid already priced at
  ~0.95 R/bet out of sample. If an arm wins on retention and loses on R, it
  still wins.

No absolute retention threshold, for the reason v1 gave: I cannot justify one
in advance, and this project has already retracted one unreachable bar.

## The `PH_LOCK` stall is characterised, not fixed

Its prevalence and shape are reported. **No policy for it is proposed in this
run**, and none may be added mid-run. Fixing a second defect discovered while
validating the first, inside the same experiment, is how a clean measurement
turns into a rolling redesign. It gets its own diagnosis and its own
pre-registration or it does not get fixed.

## What a pass does NOT authorise — unchanged

* **The default stays `none`.** A pass earns the right to be *proposed*.
  Switching it on is the user's call.
* **Enabling it in production is LIT_FORWARD_V2**, never a patch to V1, and
  the two records are never pooled.
* **It does not revisit stages A, B or C.** Re-running them under a repaired
  engine is a new experiment needing its own pre-registration.
* **No production change.** Nothing under `riptide/` is modified,
  `rules_hash` is untouched, and both frozen test scripts must still pass.
