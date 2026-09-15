# PRE-REGISTRATION — P9, the bootstrap CHoCH: which arm, if either

Committed before the first number. Run by
`research/studies/lit_seek_escape.py`.

## The defect being fixed

Established in `research/studies/lit_main_latch.py`, not assumed here:

> The CHoCH level is created when a BOS *breaks*, at step 7. The first cycle
> after bootstrap therefore reaches `PH_SEEK` with no opposing boundary, and
> `PH_SEEK` is a one-way door — step 8 needs `ch.ready()`, step 5 will not
> publish an IDM outside DISCOVER/TRACK, and there is no timeout. If that
> first BOS is never broken, the context emits nothing for the rest of the
> chart.

4/28 symbols on Min30 (BNB, ONDO, TIA, BTC) and 1/28 on Min15, over 333 days.

## The arms

`POL.seekCh`, default `"none"`, verified byte-identical to the frozen engine
on the latch study and on both frozen test scripts.

| arm | the first cycle's CHoCH |
|---|---|
| `none` | none — the frozen behaviour, and the incumbent |
| `leg` | the leg extreme **against** the trend: the exact mirror of the BOS, which is the leg extreme with it |
| `raid` | the IDM raid extreme — the level Stage A already takes as its stop. Tighter, so it flips sooner |

An **expiry** arm — abandon an unbroken BOS after N bars — was considered and
**rejected before measurement**, because `Pol`'s own contract is *"No policy
may introduce a number"* and a bar count is a number. Recorded so it is not
mistaken for an option that lost on the evidence.

## This is a liveness bug, and it is judged on liveness

The primary criterion is **not** which arm makes more money.

A structure engine that stops emitting is broken whether or not the silence
happened to be profitable, and choosing the repair by its P&L is the same
curve-fit that the 162-combination grid already showed decaying ~0.95 R/bet out
of sample. The economics are measured and printed, and are explicitly barred
from the selection.

## GATES — an arm that fails any of these is rejected outright

* **G1 LIVENESS.** Zero latched panels. A panel is latched when Main's last
  event lands before the halfway point of the window while Internal's does not.
  Evaluated on every symbol-timeframe where Internal is healthy.
* **G2 INVARIANTS.** `ctx.bad` stays empty on every symbol and both
  timeframes. The engine self-checks I1, I2, I3, I5 and I11; an arm that trips
  one has produced an inconsistent structure and is rejected however well it
  scores on anything else. Non-negotiable.
* **G3 NO NEW LATCHES.** No panel healthy under `none` may become latched.

## SELECTION — among arms that clear every gate

* **S1 RETENTION, the deciding number.** On panels that were **already
  healthy** under `none`, the share of `none`'s `idm_break` events that survive
  at an identical bar under the arm. The defect is confined to the bootstrap
  cycle, so a correct repair should be nearly invisible where nothing was
  broken. The arm with higher retention wins; `leg` takes a tie, because it is
  the exact mirror of the BOS and so is the smaller assumption.
* **S1b INFLATION**, reported alongside: the share of the arm's `idm_break`
  events that are new. Retention can be bought by emitting everything, and this
  is what stops that reading.

**No absolute retention threshold is set.** I do not know in advance how far a
bootstrap change cascades, and inventing a bar I cannot justify is how this
project ended up retracting a `t ≥ 3.0` in stage A. The comparison between two
arms is what the sample can actually support.

* **S2 ECONOMICS — reported, explicitly NOT used to select.** Stage-C-style
  setup R per bet under each arm, so that nothing is hidden. If an arm wins on
  retention and loses on R, it still wins.

## Confirmation on untouched symbols

The latch prevalence was measured on `DISCOVERY[:30]`. Whichever arm is
selected is then re-run on symbols that were not in that set, and **G1 must
hold there too**. Liveness is not a quantity that can be overfitted the way a
return can, so this is a check rather than a second experiment — but a repair
that only works on the symbols that motivated it is not a repair.

## What a pass does NOT authorise

* **The default stays `none`.** An arm winning here earns the right to be
  *proposed*, not switched on. Turning it on is the user's call.
* **Enabling it in production means LIT_FORWARD_V2, not a patch to V1.**
  `PREREG_lit_forward_v1.md` freezes V1's rules; this changes the structure
  those setups come from. V1 and V2 records must never be pooled.
* **It does not revisit the three INCONCLUSIVE stage verdicts.** Re-running A,
  B or C under a repaired engine would be a new experiment needing its own
  pre-registration, not a re-read of the old ones.
* **No production change in this step.** Nothing under `riptide/` is modified,
  `rules_hash` is untouched, and both frozen test scripts must still pass.

## If neither arm clears the gates

Reported as: the defect is real and neither parameter-free repair is sound.
`none` stands, the latched symbol-timeframes stay absent from every Main-based
sample, and that limitation gets stated wherever Main is used rather than
quietly carried.
