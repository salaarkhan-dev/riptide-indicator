# Why section 12 draws fewer BOS and CHoCH than the reference

    python3 research/studies/ms_bos_gate.py

A diagnostic, not a study. It counts events and scores nothing. **No claim
that more marks are better marks is made here**, and none should be read into
it — it answers "why are there fewer", not "which is right".

**Three** independent causes. None is a port bug: `deploy/ms-port-check.py`
and `deploy/ms-py-parity.py` both still pass.

Read cause 3 first. It was found last, it is almost certainly the largest, and
it means most of what looked like missed detection was detection followed by
deletion.

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

## Cause 3 — and it is probably the biggest: the drawings were being evicted

Added after a second comparison against the reference, and it **corrects the
emphasis of everything above.**

    python3 research/studies/ms_period_grid.py

A CHoCH that the reference labelled and this layer appeared to miss was
checked directly against the engine, on the same bars:

```
msLen=15 short=3   whole file {'sweep': 45, 'choch': 26, 'idm': 38, 'bos': 14}
  15 Sep 04:00-10:00 UTC:  CHOCH 05:00 @ 77441.6     IDM 09:45 @ 76973.1
msLen=10 short=3   identical in that window
msLen=8  short=2   identical in that window
```

**It fired.** At every period setting tried. It was not a detection miss at
all — so `msLen` was not the reason that one was absent from the chart.

The reason is `msKeepN`. Every event costs one line and one label, and the old
cap of **40** against **123 events** on that file meant roughly **two thirds
of everything this layer detected was drawn and then deleted** to make room
for something newer. An event vanishing after it printed looks exactly like an
event that never printed.

`msKeepN` default raised **40 → 100**, maxval 200 → 400.

**The cheaper lever is not raising it.** Sweeps were 45 of those 123 events —
37% of the budget spent on the small `x` marks. Unticking *Sweeps* frees a
third of the budget for CHoCH, BOS and IDM and costs Riptide's own drawings
nothing.

---

## The period grid — CHoCH and IDM/BOS are steerable separately

`research/studies/ms_period_grid.py`, same data, cells are
**CHoCH / IDM / BOS / IDM-blocked**:

```
 msLen        short=1              short=2              short=3              short=5
    20   56/122/ 63/  0      56/110/ 51/  0      56/105/ 46/  0      56/ 92/ 38/  5
    15   70/144/ 72/  0      70/126/ 57/  0      70/116/ 50/  0      70/ 98/ 40/  5
    12   82/156/ 72/  0      82/134/ 55/  1      82/122/ 46/  3      82/103/ 36/  8
    10   94/167/ 74/  1      94/135/ 51/  8      94/120/ 41/ 12      94/ 96/ 32/ 19
     8  122/197/ 76/  1     122/158/ 50/ 12     122/137/ 39/ 21     122/ 93/ 28/ 48
     6  160/227/ 77/  3     160/164/ 45/ 33     160/121/ 28/ 71     160/ 45/ 11/143
     5  178/231/ 80/ 10     178/155/ 44/ 46     178/ 99/ 25/107
```

Two clean facts:

* **CHoCH depends on `msLen` only.** Every column is identical down a row. So
  if you want the reference's CHoCH density, `msLen` is the single knob, and
  nothing else moves with it.
* **The collision is avoidable.** `msShortLen = 1` keeps IDM-blocked at ~0 all
  the way down to `msLen = 5`, and BOS stays flat at 72–80 instead of
  collapsing.

The second is a trap, not a recommendation, and it is worth being blunt about.
At `msShortLen = 1` an "inducement" is *price dipped below the previous bar's
low*. The count goes up because the test became trivial, not because more
inducements exist. Satisfying the BOS prerequisite with a meaningless
inducement is a worse answer than the honest one, which is to turn the
prerequisite off with `msBosNeedsIdm` and say so.

If the goal is to match the reference's read: **`msLen` 8, `msShortLen` 2**
gives 122 CHoCH / 158 IDM / 50 BOS with 12 blocked — more CHoCH and more IDM
than the shipped 15/3, same BOS. The default was left at 15/3 rather than
moved twice in two commits; those are two numbers to type, and this table is
here so the choice is yours rather than mine.

Nothing in this file measures whether any of it is *better*. It measures how
many marks appear and why.

---

## What changed, exactly

| | |
|---|---|
| `msBosNeedsIdm` | **new input**, default `true` = the original's behaviour. OFF labels every break of the running extreme. |
| `msLen` default | **50 → 15**. Context-only, not parity-locked. |
| `msLen` minval | 2 → 5, so the IDM/BOS-dead regime is unreachable. |
| `msKeepN` default | **40 → 100**, maxval 200 → 400. See cause 3 — this is the one most likely to have been hiding structure. |
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
