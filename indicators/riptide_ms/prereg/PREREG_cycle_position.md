# PRE-REGISTRATION — the early-vs-late-in-cycle effect

Committed before the first number. Run by
`indicators/riptide_ms/studies/cycle_position.py`.

## What was seen, and why it needs its own study

While diagnosing the entry models, the random control's R was found to decline
with position inside a structure cycle:

| decile | 0.0 | 0.2 | 0.4 | 0.6 | 0.8 | 0.9 |
|---|---|---|---|---|---|---|
| mean R | −0.250 | −0.503 | −0.543 | −0.467 | −0.893 | −1.204 |

    first 30% of a cycle   −0.340 R
    last  30% of a cycle   −0.975 R
    gap                    +0.636 R

That was a by-product of checking whether E3_CHOCH's win was an artefact. It
was not the thing being measured, it is the largest effect anywhere in that
work, and nothing here has measured it directly. Hence this.

## Two ways it is probably an artefact, named before measuring

**1. It may be unusable even if real.** Position-as-a-fraction needs the
cycle's total length, which is not known until the cycle ENDS. "This bar is at
90% of its cycle" is not a fact available at that bar. Any rule phrased on it
is unimplementable, however large the effect.

**2. It may be a tautology of the cycle definition.** A bull cycle ends when
price breaks the structural low. So the last bars of a bull cycle are, *by
construction*, the bars immediately preceding a decline large enough to flip
the structure. "A long entered late in a bull cycle does badly" may be another
way of saying "a long entered just before a confirmed reversal does badly",
which is true by definition and worth nothing.

Both are stated here so that neither can be discovered later and presented as a
nuance.

## The two covariates

| name | definition | knowable in real time? |
|---|---|---|
| **FRACTION** | position as a share of the completed cycle | **NO** — needs the end |
| **ELAPSED** | bars since the CHoCH that opened the cycle | **YES** |

FRACTION replicates the observation. **ELAPSED is the primary**, because it is
the only one a rule could use.

Note ELAPSED carries an opposite bias, which helps: a bar at elapsed = 200
exists only in cycles that lasted at least 200 bars, and those are the
persistent ones. So survivorship pushes late-ELAPSED R *up*. If R still
declines with ELAPSED, that is against the bias rather than with it.

## Population and scoring

Unchanged from the entry-model study, so the two are comparable:
`research.ms_struct` at its shipped defaults, 30 discovery symbols, Min30 and
Min15, 333 days, split older/newer → four panels. Entry at a bar's close in the
cycle's own direction, stop = the live short-period opposing swing (wrong side
→ SKIP), 2R target, 48-hour horizon, Riptide fees, `simulate_market`.

Entries are sampled uniformly within each cycle, seeded per cycle, so long
cycles do not dominate and the sample cannot be re-rolled.

## The tests

**A. REPLICATION.** The FRACTION decile profile, in all four panels. Does the
by-product reproduce, or was it one panel?

**B. THE TAUTOLOGY TEST — the one that decides this.** Re-run A on entries
whose cycle did **not** flip during the trade's whole horizon, so every trade
lives entirely inside one cycle and none is "entered just before the
reversal".

> **Pre-specified reading:** if the first-30% vs last-30% gap is significant
> (|z| ≥ 2) unrestricted but NOT significant (|z| < 2) restricted, the effect
> is declared **definitional** and the finding is that it is an artefact of the
> cycle definition. That verdict is fixed now, before the numbers.

**C. THE USABLE VERSION.** R against ELAPSED, bucketed by quartile of elapsed
bars. Primary contrast: mean R below the median elapsed minus mean R above it.

## Pre-registered bars for C — all three

1. **COVERAGE.** Each elapsed quartile holds ≥ 200 trades in every panel.
2. **SIGN STABILITY.** The below-minus-above contrast keeps one sign in all
   four panels.
3. **SIGNIFICANCE.** |z| ≥ 2.0 pooled on the newer half.

Two covariates and one contrast, so family-wise inflation is small here — but
bar 3 still does not stand alone, and B can invalidate a pass on C.

## What a pass would and would not license

A pass on C means *trades opened soon after a structure flip score better than
trades opened long after one*, on this engine, over this window. It would be a
**filter on timing, not an entry signal** — nothing here proposes a trigger,
and the entry-model study already found none that beat random timing.

It would **not** license a Pine change on its own. It would earn its own
forward test, exactly as the LIT work did.

## What cannot happen

* No production change; the frozen control test must still pass.
* No exchange API key, no order placement, no execution code.
* No parameter tuning. `msLen = 50`, `msShortLen = 3`, the stop rule, the
  target, the horizon and the fees are all carried over unchanged from
  `PREREG_ms_entry_models.md` and are not swept.
* No retrospective symbol or timeframe filtering.
* **One study.** If B declares the effect definitional, there is no
  reformulation that rescues it.
