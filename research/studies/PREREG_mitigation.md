# Pre-registration — daily zone mitigation

Written **before** the held-out window was fetched. Same procedure as
`PREREG_btc.md`, and with its lesson applied: that pre-registration ran
correctly and still certified a backwards claim, because nothing in it ever
checked the code computing the variable. So this document names the sanity
check as part of the test, not as an afterthought.

## What was found on the discovery window

`research/studies/mitigation.py`, 2655 POI signals, the current ~42 days.

A daily zone is **unmitigated** when price did not visit it on any daily bar
strictly between the bar that formed it and the raid. Both endpoints are
excluded: a zone always touches its own formation bar, and the raid is the
return being scored.

| definition | population | unmitigated | mitigated | difference |
|---|---|---|---|---|
| close | all POI | +0.448 (58% win) | −0.091 (33%) | **+0.539, +10.3 SE** |
| close | confirmed | +0.406 (58%) | +0.022 (37%) | +0.384, +3.0 SE |
| close | grade A | +0.510 (62%) | +0.130 (41%) | +0.380, +2.0 SE |
| wick | confirmed | +0.517 (67%) | +0.045 (38%) | +0.472, +3.4 SE |
| wick | grade A | +0.657 (70%) | +0.173 (43%) | +0.484, +2.3 SE |

Both definitions, every population, same direction. It survives inside grade
A, where the POI, the daily trend and DI are all already held fixed.

## The prediction, stated in advance

**An UNMITIGATED daily zone scores a higher R per signal than a mitigated one,
on held-out data, on both the wick and the close definition.**

## The bar

**3 SE on the held-out window alone, on the `close` definition, all POI
signals** — the largest cell, named in advance so the bar cannot be moved to
whichever cell happens to clear it.

Secondary, reported but not decisive: confirmed-only and grade-A-only, and the
wick definition. The effect must keep its SIGN in all of them. A sign flip in
any panel means it does not ship regardless of the primary.

Shrinkage is expected and is not failure. The BTC effect returned at ~70% of
its discovered size and that was the shape of a real effect overestimated
where it was found. An effect this large returning at half strength would
still be the biggest thing in the project.

## What would make me reject it

1. **Under 3 SE on the primary.** Not shipped. Recorded as a candidate.
2. **A sign flip in any secondary panel.** The BTC × own-trend interaction was
   rejected for exactly this and it was right to be.
3. **Degeneracy.** If the held-out split is near 0% or 100% unmitigated the
   definition has broken on that data and the numbers mean nothing. Discovery
   split was 15% (wick) and 33% (close); anything outside 5–60% is a fail.
4. **The mechanism check below.**

## The mechanism check, which is the part I most expect to fail

The ICT story is that an unmitigated zone still holds unfilled orders. There
is a duller explanation that fits the same data: a zone price has never
returned to means price left and stayed away, which is a **trending** market,
while a zone visited repeatedly is a **ranging** one. If "unmitigated" is
mostly a proxy for "not chopping", the effect is real but the story is wrong,
and it would likely be unstable across regimes the way the BTC split was.

Two things are therefore also measured and stated here in advance:

- **Within-regime.** Split by whether the daily trend agrees, which is the
  closest available proxy for a directional regime. The effect must survive
  inside both halves. It already survives inside grade A, which requires the
  trend, so the with-trend half is expected to hold; the against-trend half is
  the real test.
- **The visit gradient is NOT monotone on discovery and I am saying so now.**
  On the close definition: 0 visits +0.448, 1 visit −0.206, 2–3 −0.040, 4+
  −0.063. Four or more visits scores BETTER than one, in four of six panels.
  Doctrine predicts a dose-response and this is a cliff with a recovery. I am
  not going to explain that away after the fact: if the held-out data shows
  the same U-shape it is evidence the variable is not measuring what the story
  says, and the finding ships as "fresh vs not" with the mechanism marked
  unknown rather than as ICT confirmation.

## THE CONTROL — added before the held-out fetch, and I expect it to bite

Recorded honestly: this was **not** in the first draft of this document. It
was added after reading the discovery numbers and before any held-out data
was requested.

A zone formed one daily bar before the raid has **no intervening daily bars at
all** and is therefore "unmitigated" by construction. A thirty-day-old zone has
thirty chances to be visited. So "unmitigated" is mechanically entangled with
**zone age**, and the +11.9 SE may be measuring youth rather than unfilled
orders.

This is the same failure mode that killed premium/discount: it pointed the
right way, and the control showed it was a restatement of stop size.

**The effect must survive inside age terciles.** If it vanishes there, the
finding is zone AGE, the correct shipped change is a tighter
`ZONE_MAX_AGE_BARS` rather than a mitigation test, and the ICT story is wrong.
Both the tercile split and the median age of each group are printed.

## The sanity check that `PREREG_btc.md` lacked

Before the held-out numbers are read, `poi_state` is verified on synthetic
data: a zone with a known visit placed between formation and raid must count
exactly one visit, a zone with a visit only on the formation bar or only on
the raid bar must count zero, and a zone price never approaches must count
zero. The BTC bug survived a correct pre-registration because no one checked
that `supertrend()` meant what the comment said. This is that check.

## Window

Held-out window ends where the discovery window begins — 2000 Min30 bars
before now, the same construction `btc_regime.py` used. Nothing in this
project has looked at it since the BTC work, and the mitigation variable has
never been computed on it at all.


---

## OUTCOME — 9 Sep 2026, before any held-out data was fetched

The discovery numbers this document was written around were **entirely a
look-ahead**. `poi_state` carried its own copy of `t <= when`, so the fix to
`in_poi` never reached this study; the giveaway was that a re-run moved
nothing at all.

Corrected, the wick arm collapses from 408 unmitigated zones to **3**, failing
the degeneracy rule stated above (5-60%). The close arm survives at **+0.269,
+4.1 SE**, clearing the pre-registered primary — but the "must hold on both
definitions" clause cannot be satisfied, the fixed-age control is inconsistent
(positive at ages 1, 2, 4, 5; flat or negative at 3, 6, 8), and the
non-monotone visit gradient predicted here as a warning sign is still present.

**Held-out test not run.** There is no point spending a held-out window on a
variable whose discovery-window evidence is this mixed; the window is a
one-shot resource and burning it here would leave nothing for a cleaner
candidate. Recorded as a candidate.

The mechanism check in this document was the right instinct and the control
that mattered was the one added late — "is unmitigated just young?" It was
not young. It was the leak.
