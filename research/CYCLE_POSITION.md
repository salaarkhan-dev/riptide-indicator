# Early vs late in a structure cycle

Pre-registered in `PREREG_cycle_position.md`, committed before the run.
Study: `research/studies/cycle_position.py`, output alongside it.
20,353 trades, 28 symbols, Min30 and Min15, 333 days.

## Verdict

**DEFINITIONAL.** The effect is real, it replicates in every panel, and it is
an artefact of how a cycle is defined. The pre-registered reading said exactly
this outcome would be called that way, and it was written before the numbers.

The usable version of the effect does not exist: it fails sign stability, and
what signal there is points the *opposite* way.

## A. It replicates — strongly

Mean R by decile of cycle position, all four panels, and the effect is not
subtle:

| panel | first 30% | last 30% | gap | z |
|---|---|---|---|---|
| Min30 older | −0.282 | −0.719 | +0.437 | 5.29 |
| Min30 newer | −0.262 | −0.741 | +0.479 | 5.87 |
| Min15 older | −0.317 | −0.849 | +0.532 | 8.69 |
| Min15 newer | −0.377 | −0.997 | +0.620 | 11.89 |

Four panels, same sign, z from 5.3 to 11.9. On any normal reading this is a
finding. It is not.

## B. The tautology test — the decider

Restrict to **CONFINED** entries: trades where the structure did not flip at
any point during the whole horizon, so no entry sits just before a confirmed
reversal.

| sample | n | first 30% | last 30% | gap | z |
|---|---|---|---|---|---|
| all entries | 15,200 | −0.321 | −0.861 | **+0.540** | **16.36** |
| **CONFINED only** | 5,427 | −0.049 | −0.031 | **−0.017** | **−0.14** |
| flipped during trade | 9,773 | −0.705 | −0.911 | +0.205 | 5.46 |

**Confine the trades inside their own cycle and the effect is exactly zero.**
Not reduced — gone, and marginally the other way.

The whole +0.54 R was one sentence restated: *a long entered just before price
breaks the structural low does badly.* A bull cycle **ends** when price breaks
that low, so its last bars **are** the bars before that break, by construction.
Nothing was learned about structure.

This is why the tautology route was named in the prereg rather than discovered
here. A z of 16 is what a definition looks like when you measure it.

## C. The usable version — fails, and points the other way

`ELAPSED` — bars since the CHoCH — is the only version a rule could use, since
a bar's fraction of its cycle is unknowable until the cycle ends. Quartile cuts
at 34 / 90 / 194 bars:

| panel | below median − above median | z |
|---|---|---|
| Min30 older | **+0.076** | 0.26 |
| Min30 newer | −0.181 | −2.63 |
| Min15 older | −0.167 | −3.38 |
| Min15 newer | −0.029 | −0.67 |

Sign stability **fails**. And the direction that dominates is *negative* —
entering soon after a flip is **worse**, not better. That is the opposite of
the story the FRACTION profile tells, and it is what the prereg anticipated:
ELAPSED's survivorship bias runs the other way, because a bar at a high elapsed
count only exists in cycles that lasted, and those are the persistent ones.

Pooled newer-half z is −2.14, which clears bar 3 — and bar 3 alone was never
enough. Bar 2 fails, so the verdict is INCONCLUSIVE.

## The one number worth keeping, with its own caveat

Confined trades average about **−0.04 R**. Trades during which the structure
flipped average **−0.7 to −0.9 R**. Essentially the entire negative expectancy
of this engine lives in trades that were still open when the structure turned.

Read carefully, that is *also* close to circular — a trade during which the
structure flipped is by definition a trade that went far enough against you to
break a structural level. It is not a filter, because you cannot know at entry
whether the structure will flip before you are out.

It does say something about *exits* rather than entries, and that is a
different question from any asked so far. It has not been tested and is not
being proposed here.

## Standing

Per the prereg: **one study**, and B declaring the effect definitional means
there is no reformulation that rescues it. Nothing changes in `riptide/`, in
either Pine file, or in any default. The frozen control test passes.

This closes the largest loose end from `research/MS_ENTRY_MODELS.md`, and it
closes it negatively.
