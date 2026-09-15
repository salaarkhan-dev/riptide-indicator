# The CCP window search manufactures its own matches

    python3 audit/ccp_merge_check.py

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

| | was | now |
|---|---|---|
| `ccpBack` / `ccpFwd` | 3 / 3 | **1 / 1** |
| `ccpBodyMax` | 0.35 | **0.15** |
| `ccpWickMin` | 0.50 | **0.70** |

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

## What this does not say

Nothing here measures whether a CCP mark predicts anything. It measures how
often the classifier fires and why. A forward-return study on these marks
needs its own prereg, and on this evidence its first job would be to beat a
control that searches the same number of windows on shuffled candles — because
the number above that a real effect has to clear is not zero, it is the search
rate.
