# Which of these pages still reproduce, and which describe a dead engine

Produced by `deploy/measurement-provenance.py`, 2026-09-18, after `stopSrc`
moved and every study was re-run. **Nothing here says a page is wrong.** Two
of the three findings below are what a repository that fixes its own bugs is
supposed to look like; the third is the one worth acting on.

Re-run the sweep after any change to `port/`, and update this file. It takes
most of an hour and it is not in preflight for that reason.

## THREE FAILURES, AND THEY WEAR ONE FACE

The first reading of this sweep was "eleven pages don't reproduce", which
conflated three completely different things and made ordinary correctness work
read as a scandal. They want opposite responses:

| | what happened | is it a bug? | the response |
|---|---|---|---|
| **PIN DRIFT** | a default moved under a study that read it from `P`, so the script measures something its page never described — **and still prints a table** | **yes** | pin it, and `tests/test_studies_pin_their_settings.py` guards it |
| **SUPERSESSION** | the engine was deliberately corrected, so a page produced before the fix cannot reproduce after it | **no** | stamp the page with the commit it reproduces at |
| **PROVENANCE GAP** | the page's numbers cannot be reproduced from **any** committed state | **yes, and unguarded** | the page cannot be trusted to the digit |

## The state of every page

| page | at HEAD | at its own commit | |
|---|---|---|---|
| `UNDERTOW_ANCHOR.md` | reproduces | — | |
| `UNDERTOW_COMPLEMENT.md` | reproduces | — | |
| `UNDERTOW_DEFAULT.md` | reproduces | — | |
| `UNDERTOW_HTF.md` | reproduces | — | |
| `UNDERTOW_MTF_EMA.md` | reproduces | — | |
| `UNDERTOW_SCALE.md` | reproduces | — | |
| `UNDERTOW_SLOPE_DEFAULT.md` | reproduces | — | |
| `UNDERTOW_STRICT.md` | reproduces | — | |
| `UNDERTOW_BIAS_SOURCE.md` | 25/28 | **28/28** at `c8bbb81` | superseded |
| `UNDERTOW_EXITS.md` | **0/9** | **9/9** at `fcbcf5a` | superseded |
| `UNDERTOW_LATE_BACKUP.md` | 4/8 | **8/8** at `def1059` | superseded |
| `UNDERTOW_OVERLAP.md` | **0/9** | **9/9** at `365d6ab` | superseded |
| `UNDERTOW_V2.md` | 17/23 | **23/23** at `279b2c8` | superseded |
| `UNDERTOW_MTF_DEFAULT.md` | 6/20 | 14/20 at `312ce3a` | superseded; the 6 are a row quoting another page and two derived deltas |
| `UNDERTOW_PULLBACK.md` | 9/23 | 21/23 at `bd4da15` | superseded; the 2 are computed "difference" rows |
| `UNDERTOW_V3.md` | 7/29 | 20/29 at `6f4b8d2` **and** at `1d06b39` | **PROVENANCE GAP** |
| `UNDERTOW_BACKUP_FILL.md` | 12/22 | 12/22 at `4b90043`, 14/22 at `def1059` | **PROVENANCE GAP** |

`UNDERTOW_EXITS.md` is the clean demonstration: **9/9 at the commit that
published it, 0/9 at HEAD**, across forty `port/` commits. The page was exactly
right when written. No amount of pinning would have changed that, and nothing
should try to.

## THE TWO PAGES THAT NEVER REPRODUCED

`UNDERTOW_BACKUP_FILL.md` reports `armed` of 4442 / 4474 / 4538. The study at
the commit that added the page produces **3737 / 3701 / 3783** — the same
shape, 18% fewer setups, and the page's own sample sizes appear nowhere in the
output at any commit in its history. `UNDERTOW_V3.md` is the same: its
n-values of 1,953 / 812 / 1,822 / 674 / 1,089 appear in no committed state.

The likeliest explanation is the dullest one: **the study was run, the numbers
were pasted into the page, and the code moved before the commit landed.** The
run happened against a working tree that was never committed.

That is not supersession and pinning cannot catch it, because nothing was
mis-set — the page is simply a record of a run nobody can re-do. Both pages'
conclusions are nulls and neither is load-bearing, so the cost here is
credibility rather than a wrong decision. The fix is procedural: **run the
study from a clean tree, and commit the output alongside the page.**

## What this does NOT mean

* **No conclusion changes.** Every superseded page reported a null and still
  does. The engine corrections moved magnitudes, not signs or verdicts.
* **The pages are not retracted.** A page that reproduces at its own commit is
  a correct record of the engine it names.
* **Re-running them is optional.** Re-running on the same frozen universe is
  legitimate — same data, better code, same prereg — but it is only *worth* it
  where a conclusion might flip, and none of these would.

## The one that WAS a bug

`UNDERTOW_BACKUP_FILL.md`'s re-run, not the page. `undertow_backup.py`'s
baseline arm was `("B0", "backup off", {})`, leaning on `useBackup` still
defaulting to `False`. It defaults `True` now, so **B0 became a second copy of
B3** and the study printed `B3 − B0 = +0.000` on all three timeframes, zero
trades added, every pre-empted fill worth `+0.000`, and a verdict reading *"the
backup fill does not clear its bars ... every component of Undertow has now
been ablated and none carries an effect."* Every number in it was an arm
subtracted from itself.

Repaired, the same study gives **+0.011 / +0.030 / +0.035**, positive on all
three timeframes, with 541–646 ADDED trades at **+0.65 to +0.96 R each** against
968–1135 PRE-EMPTED at −0.26 to −0.28. Still short of bar 3, still not
established — but it is not nothing, and the published page said nothing.

That is what pin drift costs, and it is the failure this directory can actually
prevent.
