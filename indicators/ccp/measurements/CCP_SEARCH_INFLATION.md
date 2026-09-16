# The CCP window search manufactures its own matches

    python3 indicators/ccp/tools/ccp_merge_check.py      # the ungated version, below
    python3 indicators/ccp/tools/ccp_at_grabs_check.py   # after the fix, §"What fixed it"

A diagnostic, not a study. It counts matches and scores nothing. What it says
is a fact about the *search*, not about the market — which is the point.

## The first run marked 88.4% of all bars

`riptide-ccp.pine` section 5 searches every window containing an anchor:
`ccpBack` candles before by `ccpFwd` after. With the CCP sheet's own pin shape
— body ≤ 0.35 of the range, longer wick ≥ 0.50 — and a 3/3 window:

```
45,379 anchors, 23 symbols, Min15, min range 0.5 ATR

  mode              matches    rate   by name
  Smallest run        40122   88.4%   Inv 11093  Hang 9980  Ham 9869  Shoot 9180
  Strongest wick      40122   88.4%   Inv 11343  Hang 10202  Ham 9780  Shoot 8797
  Most centred        40122   88.4%   Inv 10976  Hang 10275  Ham 9785  Shoot 9086
```

**A mark that appears on nine bars in ten is not a detector.** Every anchor
gets 16 chances to be called a pin, and on real price data something nearly
always is.

## It is the search, not the thresholds

Both were swept. They are not comparable in effect.

**Thresholds**, at a fixed 3/3 window:

```
   body ≤    wick≥0.5   wick≥0.6   wick≥0.7   wick≥0.8
     0.35       89.0%      80.8%      61.4%      32.4%
     0.25       84.9%      76.8%      59.5%      32.4%
     0.15       77.8%      67.5%      51.2%      30.2%
     0.10       69.6%      58.0%      42.7%      25.4%
```

**Window**, at a fixed body ≤ 0.15 / wick ≥ 0.70:

```
   back/fwd     rate   windows tried
        0/0     5.1%          1
        1/1    19.7%          4
        2/2    35.5%          9
        3/3    51.3%         16
        5/5    70.5%         36
```

Squeezing the shape from its loosest to its tightest takes the rate 89% → 25%.
Narrowing the window alone takes it 51% → 5%. **The rate tracks the number of
windows tried, not how selective the shape is.** Nineteen windows in twenty
are finding a shape by accident.

This is a multiple-comparisons problem wearing a costume. It is the same
mistake the prereg discipline exists to catch, arriving through geometry
instead of statistics: try enough definitions of an event and one of them
fires.

## What changed

| | originally | after this file | **shipped today** |
|---|---|---|---|
| `ccpBack` / `ccpFwd` | 3 / 3 | 1 / 1 | **2 / 2** |
| `ccpBodyMax` | 0.35 | 0.15 | **0.25** |
| `ccpWickMin` | 0.50 | 0.70 | **0.70** |

> **The body cap moved back to 0.25 after this file was written**, because
> 0.15 was rejecting shapes that the CCP sheet, and any reasonable eye, call
> pins: a hanging man at a sell-side grab with upper wick .00, lower wick .79
> and the right direction was thrown out on its body alone at .21.
>
> **Every rate quoted in this file and in `research/CCP_ENTRY_MODELS.md` was
> measured at 0.15.** At 0.25 the comparable both-ends figure is about **24.9%**
> rather than 16.8%. The entry study's null carries over rather than being
> voided: loosening accepts more grabs, which moves the filter toward taking
> every grab, and every grab is the most solidly measured zero in that study.
> A *tighter* setting would be the one needing its own run.

That lands near 20% — still high, and deliberately not hidden. The debug table
now prints the **no-merge baseline** beside the live count: the `b = 0, f = 0`
window is the anchor candle alone, so that row is how often the shape was
simply *there*. Every match above it was produced by widening the search.

At the shipped defaults the baseline is roughly 5% against a live rate near
20% — so **three marks in four exist because the search looked harder**, and
the table says so on the chart while you tune.

## Two things that survive, and they matter

**The merge is not decoration.** Under "Smallest run" the winning window needs
two or more candles **72%** of the time:

```
  mode                  1      2      3      4      5      6      7  candles
  Smallest run        28%    39%    22%    10%     1%     0%     0%
  Strongest wick      10%    18%    22%    28%    13%     7%     3%
  Most centred        18%     9%    23%     7%    20%     3%    20%
```

If it were 90% single candles the search would be pure overhead. It is not —
the idea of merging neighbours is doing real work, which is exactly what was
worth finding out.

**The tie-break is a real choice.** "Smallest run" and "Strongest wick" pick
the *same* window only **45%** of the time (17,940 / 40,122). Which rule is
right is an open question, and it is a switch on the panel rather than a
decision buried in the code.

## What fixed it: a prior, not a threshold

Scanning stopped being "every bar" and became **the two ends of a grab, in the
direction that grab implies** — the swing that built the level and the candles
that ran it, accepting only a bearish shape at a buy-side grab and only a
bullish one at a sell-side grab. Same thresholds, same merge, same four names.

`indicators/ccp/tools/ccp_at_grabs_check.py`, 2,729 grabs, 23 symbols, Min15:

```
   back/fwd   grabs   left   right   BOTH   both %   aa / am / ma / mm
        0/0    2729    192     104      7     0.3%   7 /  0 /  0 /   0
        1/1    2729    734     623    159     5.8%   7 / 32 / 23 /  97
        2/2    2729   1157    1080    448    16.4%   7 / 61 / 38 / 342
        3/3    2729   1441    1365    716    26.2%   7 / 84 / 43 / 582
```

**88.4% of all bars became 16.4% of grabs** at the shipped 2/2 default, with
the thresholds untouched. The prior did what no threshold could.

The four combination columns are `alone+alone / alone+merged / merged+alone /
merged+merged`, and the first one **never moves**. Exactly 7 grabs in 2,729 —
0.3% — have both ends pinned without merging anything. That number is fixed
because the `b = 0, f = 0` window exists at every setting, so it is the honest
floor: everything above it was found by widening.

Which means the same warning survives in a smaller form. At 2/2, **441 of 448
matches (98%) needed a merge somewhere**, and the rate still climbs roughly
with the number of windows tried. Whether that is discovery or arithmetic is
not settled by any count, and this file does not claim it is.

## Was the tightening still needed once the grab gate existed? Yes.

    python3 indicators/ccp/tools/ccp_threshold_sweep.py

The thresholds went from the CCP sheet's own 0.35 body / 0.50 wick to
0.15 / 0.70 while the classifier still scanned every bar. The grab gate came
later and did far more. That raised a fair question — **is the tightening now
redundant?** — and I assumed for a while that it might be. It is not.

Both ends matching, with the grab gate in place, sweeping the shape:

```
   body<=  wick>=   Min15   Min30   Min60
     0.35    0.50   68.4%   69.4%   67.2%    the CCP sheet's own shape
     0.35    0.60   50.9%   51.3%   48.9%
     0.25    0.60   43.4%   44.0%   41.7%
     1.00    0.65   39.6%   39.0%   36.2%    WICK ONLY — no body cap at all
     0.35    0.65   39.6%   39.0%   36.2%    identical, and that is the point
     0.30    0.65   37.8%   37.5%   34.9%    the cap binds again, barely
     0.20    0.65   29.6%   29.5%   27.6%
     0.25    0.70   24.9%   24.3%   21.7%
     0.15    0.70   16.8%   16.9%   15.1%    SHIPPED
     0.10    0.75    6.9%    6.7%    6.0%
```

### The body cap and the wick floor are not independent

Those two middle rows are identical to the digit — 17,213 / 8,666 / 3,859
both-ends matches — because the three fractions sum to exactly one:

```
hi - lo  =  (hi - max(o,c))  +  |c - o|  +  (min(o,c) - lo)
              upper wick         body         lower wick
```

The range IS those three pieces stacked, so **a longer wick of at least w
already forces a body of at most 1 - w**, with no help from the body cap. The
cap only rejects anything when `bodyMax < 1 - wickMin`; at or above that it is
a dead input.

| wick floor | implied body cap | a body cap of 0.35 is |
|---|---|---|
| 0.50 | 0.50 | binding |
| 0.60 | 0.40 | binding |
| **0.65** | **0.35** | **dead** |
| 0.70 (shipped) | 0.30 | dead |

At the shipped 0.70 floor the implied cap is 0.30, so the shipped **0.15 is
doing real work** — it is half of what the wick floor already guarantees.

This is worth knowing before tuning, because "loosen the body to 0.35" is a
natural thing to try and above a 0.65 wick floor it changes nothing at all.
The row above is the check: if those two ever stop matching, the identity is
wrong about the code.

**At the sheet's own shape, two grabs in three carry the mark at both ends.**
The gate took the ungated 88% of all bars down to 68% of grabs at those
thresholds — a real improvement, and still not a detector. The prior and the
shape test are doing separate jobs and neither replaces the other.

So the shipped 0.15 / 0.70 is not an arbitrary tightening left over from an
earlier problem. It is what keeps the mark rare, and dropping it to match what
the eye calls a pin costs a factor of four in rate.

**None of these rows is better than another.** `research/CCP_ENTRY_MODELS.md`
measured the shipped setting and found gross expectancy at a grab is about
zero, so a looser shape marks more grabs without making the marks mean more.
The row to pick is the one that matches what you call a pin, and that is a
readability choice, not a performance one.

## The anchor is always in the window — and that is weaker than it sounds

    python3 indicators/ccp/tools/ccp_anchor_check.py

A merge is the anchor candle plus some of its immediate neighbours. It is never
a run of neighbours that leaves the anchor out. That holds at every setting —
all 441 windows from 0/0 to 5/5 — and it is proved by enumeration rather than
by reading the code, because the Pine writes it in backwards offsets where
`anchorOff + b` is an *older* bar and a sign flip reads as plausible either way.
The same run checks the incremental run high/low against a from-scratch
max/min on 5,454 real anchors, and the four window-bound lines against the Pine
itself so the transcription cannot silently go stale.

**But positional inclusion is not contribution.** The merged open comes from
the oldest bar of the run, the close from the newest, and the high and the low
can both belong to neighbours. So the anchor can be inside a five-candle run
and have put nothing into the shape:

```
  2,236 matched anchors at 2/2

    the defining extreme is the anchor's own      1430   64%
    the defining extreme is a neighbour's          806   36%
```

On the right-hand end that second row means **the rejection the arrow is drawn
for happened on a bar that is not the one that ran the level.** Whether that
should count is a judgement, not an error.

`ccpAnchorExtreme` makes it switchable, applied inside the search so rejecting
a wide window still lets a narrower one win. It costs a lot:

```
  gate off    448 both-ends matches   16.4% of grabs
  gate on     106 both-ends matches    3.9% of grabs
```

It is **off by default**. Neither rate has been scored against anything, so
turning it on would trade a number that has been measured for a number that has
not, and tightening a detector is not the same as improving it.

## What this does not say

Nothing here measures whether a CCP mark predicts anything. It measures how
often the classifier fires and why. A forward-return study on these marks
needs its own prereg, and on this evidence its first job would be to beat a
control that searches the same number of windows on shuffled candles — because
the number above that a real effect has to clear is not zero, it is the search
rate.
