# P9 — the bootstrap CHoCH: result

Pre-registered in `PREREG_lit_seek_escape.md`, committed before the run.
Study: `research/studies/lit_seek_escape.py`, output alongside it.

## Verdict, stated first

**`leg` is REJECTED under the pre-registered gate, and the gate was
mis-specified by me.** Both halves of that sentence matter and neither cancels
the other.

## What the arms did

| arm | G1 latched | G2 invariants | G3 new latches | verdict |
|---|---|---|---|---|
| `none` (frozen) | **5** | 0 | 0 | fails — it *is* the defect |
| `leg` | **0** | 0 | 0 | passes every gate |
| `raid` | 1 | 0 | 0 | fails — BNB Min15 stays latched |

All five in-sample latched panels are repaired by `leg`:

| panel | main coverage, `none` → `leg` | main IDM breaks |
|---|---|---|
| BNB Min15 | 0.00 → 0.98 | 1 → 20 |
| BNB Min30 | 0.00 → 0.99 | 1 → 10 |
| BTC Min30 | 0.05 → 0.98 | 1 → 28 |
| ONDO Min30 | 0.00 → 0.77 | 1 → 27 |
| TIA Min30 | 0.01 → 0.99 | 1 → 51 |

And it is close to invisible where nothing was broken — the prediction the
prereg made in advance, since the defect is confined to the bootstrap cycle:

| arm | retention | inflation |
|---|---|---|
| `leg` | **99.8%** (2467 of 2473) | 1.6% (41 new) |
| `raid` | 99.8% | 1.7% |

Economics, reported and **barred from the selection** by the prereg:

| arm | bets | mean R | SE | total R |
|---|---|---|---|---|
| `none` | 1903 | 0.192 | 0.110 | 365.5 |
| `leg` | 2090 | 0.150 | 0.100 | 313.3 |
| `raid` | 2077 | 0.152 | 0.101 | 316.4 |

`none` looks better per bet and worse in count; the gap is well inside one SE
either way. It did not enter the decision and it should not enter yours.

## Why it was rejected

On 24 untouched symbols, 6 Min30 panels were latched under `none`. `leg`
repaired five. **XMR Min30 stayed latched**, so G1 — *zero latched panels* —
failed out of sample, and the prereg says that rejects the arm.

## But XMR is a different defect

Diagnosed after the verdict, and it does not change it:

```
XMR_USDT Min30   phase = LOCK   dir = bear   stuck 10,385 bars
    ch.on  = True   px = 800.72
    bos.on = True   px = 276.66
    price after the stuck bar:  max high 569.27,  min low 291.83
```

Both boundaries lie **outside the range price traded for the next 10,385
bars** — the BOS 5% below the lowest low, the CHoCH 41% above the highest
high. This context is not stuck in `PH_SEEK` with a missing CHoCH. It is in
`PH_LOCK` with two boundaries it can never reach.

That is a **second trap state**, unrelated to the one P9 repairs, and `leg`
was never designed to touch it. Prevalence across the 104 panels measured
here: `PH_SEEK` ≈ 10.6% (11 panels), `PH_LOCK` ≈ 1% (1 panel).

## My error, named

G1 was written as *"zero latched panels"* — the symptom. It should have been
*"zero panels latched by the mechanism under repair"* — the cause. As written
it cannot distinguish "the fix failed" from "a different thing is broken", and
those need opposite responses.

**I am not reinterpreting it now.** A rule rewritten after seeing which way it
cut is worth nothing, and the whole value of writing these down in advance is
that they bind when the result is inconvenient. So the recorded verdict is
REJECTED, and what would license `leg` is a fresh pre-registration whose
confirmation test names the mechanism, run again.

What I can say without any rule-bending, because it is just description:

* `leg` repairs 10 of the 11 `PH_SEEK` latches across both samples, and the
  eleventh is not a `PH_SEEK` latch.
* It introduces no invariant violations and no new latches anywhere.
* It changes 0.2% of existing events on healthy panels.

## Open, and not fixed here

* **The `PH_LOCK` stall.** Both boundaries unreachable, no timeout, no
  invalidation — the same shape of flaw as `PH_SEEK`, one level up. Needs its
  own diagnosis and its own policy.
* **FARTCOIN Min30** reaches only 0.71 coverage under `leg`, passing the
  threshold but not comfortably.

## Standing constraints, unchanged

`POL.seekCh` defaults to `"none"`. The frozen engine is byte-identical under
that default — verified against the latch study's output — `rules_hash` is
untouched, and both frozen test scripts pass. Nothing under `riptide/` was
modified.

Enabling any arm in production would be **LIT_FORWARD_V2**, never a patch to
V1, and the two records must never be pooled. It would not revisit stages A, B
or C: re-running those under a repaired engine is a new experiment needing its
own pre-registration.
