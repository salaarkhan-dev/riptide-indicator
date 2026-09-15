# Why section 12 draws fewer BOS and CHoCH than the reference

    python3 research/studies/ms_bos_gate.py

A diagnostic, not a study. It counts events and scores nothing. **No claim
that more marks are better marks is made here**, and none should be read into
it — it answers "why are there fewer", not "which is right".

Two independent causes. Neither is a port bug: `deploy/ms-port-check.py` and
`deploy/ms-py-parity.py` both still pass.

---

## Cause 1 — a BOS here requires an inducement first

This is the big one, and it is a *definitional* difference from most SMC
indicators.

Section 12 does not label a BOS when price breaks the running extreme. It
labels one when price breaks the running extreme **and an inducement was taken
first**:

```pine
if close > msMax and msSBtmCrossed and msOs == 1          // before
```

`msSBtmCrossed` is set in exactly one place — the IDM block — so the real
sequence is **CHoCH → IDM → BOS**. A break with no inducement before it is
silently not labelled.

How often that happens, over 20.8 days of 15m data on BTC, ETH and SOL:

```
 msLen   CHoCH    IDM    BOS  BOS suppressed  IDM blocked
------------------------------------------------------------
    50      29     62     30              83            0     <- old default
    30      38     82     41             120            0
    20      56    105     46             145            0
    15      70    116     50             167            0     <- new default
    10      94    120     41             208           12
     8     122    137     39             242           21
     6     160    121     28             321           71
     5     178     99     25             371          107
     4     206     72     18             404          152
     3     238      0      0             472          235     <- engine dead
```

**At the old default, 30 breaks were labelled and 83 were not.** The engine
drew a BOS on 27% of the occasions price actually broke its running extreme in
the trend direction. An indicator that marks every swing break will always
show roughly four times as many.

Whether the prerequisite is *right* is a genuine editorial question and nothing
here answers it. It is the ported author's position that a break which did not
first take an inducement is a weaker break. That is arguable, and it is now
arguable on the chart: **`msBosNeedsIdm`**, ON by default (the original
exactly), OFF to label every break.

Note what this does NOT let you conclude. `research/INDUCEMENT_ON_RIPTIDE.md`
found that seven definitions of inducement failed to sort Riptide's own bets,
but that tested IDM as a covariate on setups, not as a gate on BOS labelling.
Those are different questions and the first does not settle the second.

---

## Cause 2 — `msLen` was 50, and the reference uses 5

The ported script shipped `len = 50` and this file kept it. On a 15m chart
that is 12.5 hours: a swing only confirms when its high is the highest of the
last 50 bars. The mickes reference sets its market-structure pivot to **5/5**.
An order of magnitude coarser structure produces an order of magnitude fewer
CHoCH, which is exactly what you see.

From the same table: 50 gives 29 CHoCH / 62 IDM / 30 BOS; **15 gives 70 / 116
/ 50 — more of all three, and 15 is where BOS peaks.**

So the default moved **50 → 15**. It is context-only, it is not parity-locked,
and no alert, entry, stop or target changes. Put it back if you prefer the
coarser read.

---

## The trap in that table, which is worth more than the defaults

Follow the last two columns down. Below about `msLen` 10, **"IDM blocked" goes
from 0 to 235 and BOS collapses to zero.**

The cause is one condition: an inducement must differ from the structural
level, `msSBtmY != msBtmY`. `msLen` and `msShortLen` drive two swing detectors,
and as the two periods converge they start finding the *same swing*. The IDM
rule then rejects it, `msSBtmCrossed` never gets set, and since BOS requires
it — cause 1 — **BOS and IDM both go to zero while CHoCH keeps climbing.**

At `msLen = 3` the layer draws 238 CHoCH, no IDM and no BOS. It looks busier
than ever and has stopped detecting two of its four event types.

Nothing warned about this. Now three things do: `minval` is raised from 2 to
**5** so the dead regime cannot be reached by accident, the tooltip names 10 as
the honest floor, and this file exists.

---

## What changed, exactly

| | |
|---|---|
| `msBosNeedsIdm` | **new input**, default `true` = the original's behaviour. OFF labels every break of the running extreme. |
| `msLen` default | **50 → 15**. Context-only, not parity-locked. |
| `msLen` minval | 2 → 5, so the IDM/BOS-dead regime is unreachable. |
| tooltips | carry the numbers above, including the floor warning. |

`deploy/pine-input-audit.py --diff` reports both behavioural changes by name
and nothing else. `deploy/ms-port-check.py` now prints the BOS toggle under a
**DECLARED DEVIATIONS** heading of its own — it is a change of meaning, so it
was deliberately *not* filed under the equivalences table, which is for
renames and restructurings only. Both checkers were re-verified against the
tampered fixtures and still fail on a real break.

## What is still true of this layer

It remains **context**. It reads nothing from Riptide and feeds nothing to it,
so every alert, entry, stop and target is identical whichever way these
switches are set — including `msShow` off entirely.
