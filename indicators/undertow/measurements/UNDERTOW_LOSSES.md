# Why the losers lose: the entry works, the exit gives it back

From [`undertow_losses.py`](../studies/undertow_losses.py). **DESCRIPTIVE** —
561 cached symbols, ~566,000 resolved trades, the shipped configuration.
Nothing compared, nothing promoted.

## The finding, and it is the same on all three timeframes

| | Min15 | Min30 | Min60 |
|---|---|---|---|
| losers that **never moved** | 10.0% | 9.5% | 9.1% |
| losers that gave back **+1R or more** | **38.8%** | **39.3%** | **38.6%** |
| losers that gave back **+2R or more** | 15.5% | 15.4% | 14.9% |
| losers that gave back **+3R or more** | 4.0% | 4.0% | 3.7% |

One loser in ten never moved. **Four in ten were a full R in profit and handed
it back.** The pin, the direction and the moment are finding something; the
fixed 3.5R exit is where it is lost.

Winners agree from the other side: median max-adverse **0.42 R**, p95 **0.93
R**, on every timeframe. Winners and losers separate early.

## And the backup zones beat the primary entry, everywhere

| fill | Min15 | Min30 | Min60 |
|---|---|---|---|
| **FVG** | **+0.120** | **+0.208** | **+0.127** |
| **OB** | +0.018 | +0.079 | +0.036 |
| at the Focus line | **−0.063** | −0.006 | −0.038 |

The Focus line is ~64% of trades and it is the losing part of the strategy.
**This is the largest effect anywhere in this repository** and it was not the
question the page was written to ask.

**IT IS ALSO A SELF-SELECTED POPULATION and that must not be forgotten.** A
backup fill only exists because price ran 1R away and never came back to the
limit — those trades are a different population, not merely a different price
for the same one. The prereg has to test "place at the zone from the start",
which is not what this table measures.

## Two exits, walked bar by bar

| | ships | + break-even stop after +1R | gain |
|---|---|---|---|
| Min15 | −0.0256 | −0.0046 | **+0.0210** |
| Min30 | +0.0362 | **+0.0498** | **+0.0136** |
| Min60 | −0.0021 | **+0.0185** | **+0.0205** |

Positive on all three **after** charging it the 36–37% of winners it scratches.
Walked from the fill rather than inferred from MFE, because the inferred
version counts a winner that dipped back through its entry as a win and can
only overstate the prize.

---

```
Why do the losers lose? Anatomy of every losing trade, whole venue.
DESCRIPTIVE — 561 cached symbols, shipped configuration.

==============================================================================
Min15  ·  205268 resolved trades
==============================================================================

   losers 157725   winners 47543   ( 76.8% of trades lose)

   HOW FAR THE LOSERS GOT BEFORE THEY DIED
     never moved          15758   10.0%
     under +0.5R          34477   21.9%
     +0.5R to +1R         46370   29.4%
     +1R to +2R           36635   23.2%
     +2R to +3R           18199   11.5%
     +3R or better         6286    4.0%

     GAVE IT BACK from +1R or more: 61120 ( 38.8% of losers)
     GAVE IT BACK from +2R or more: 24485 ( 15.5% of losers)

   HOW MUCH HEAT THE WINNERS TOOK  (max adverse, in R)
     median  0.42   p75  0.70   p90  0.87   p95  0.93
     never went past -0.25R:  31.3%  <- a stop there keeps  31.3% of winners
     never went past -0.50R:  57.3%  <- a stop there keeps  57.3% of winners
     never went past -0.75R:  79.5%  <- a stop there keeps  79.5% of winners

   WHICH BUCKET LOSES WORST
     by bias state at the pin
       ending                  130732 trades  R -0.039
       immature                 28080 trades  R -0.013
       running                  46456 trades  R +0.004
     by candle code
       HAM                     111020 trades  R -0.017
       SS                       94248 trades  R -0.036
     by fill
       FVG                      17210 trades  R +0.120
       OB                       56055 trades  R +0.018
       at the focus line       132003 trades  R -0.063
     by risk size
       normal 1-3%             107027 trades  R -0.024
       tight  <1%               75498 trades  R -0.029
       wide   >3%               22743 trades  R -0.019

   WHAT TWO EXITS WOULD HAVE DONE — descriptive, not a choice
     as it ships (target 3.5R)      -0.0256 R per trade
     + break-even stop after +1R    -0.0046   (+0.0210)
     + half off at +1R              +0.0009   (+0.0265)
     winners the break-even stop would have SCRATCHED: 17675  ( 37.2% of winners)
     WALKED BAR BY BAR, not inferred from MFE: a winner that went
     +1R, came back through its entry and then ran to target is
     counted as a SCRATCH here, which is what would really happen.

==============================================================================
Min30  ·  192678 resolved trades
==============================================================================

   losers 146395   winners 46283   ( 76.0% of trades lose)

   HOW FAR THE LOSERS GOT BEFORE THEY DIED
     never moved          13835    9.5%
     under +0.5R          31645   21.6%
     +0.5R to +1R         43417   29.7%
     +1R to +2R           34892   23.8%
     +2R to +3R           16797   11.5%
     +3R or better         5809    4.0%

     GAVE IT BACK from +1R or more: 57498 ( 39.3% of losers)
     GAVE IT BACK from +2R or more: 22606 ( 15.4% of losers)

   HOW MUCH HEAT THE WINNERS TOOK  (max adverse, in R)
     median  0.42   p75  0.69   p90  0.87   p95  0.93
     never went past -0.25R:  31.8%  <- a stop there keeps  31.8% of winners
     never went past -0.50R:  58.2%  <- a stop there keeps  58.2% of winners
     never went past -0.75R:  80.2%  <- a stop there keeps  80.2% of winners

   WHICH BUCKET LOSES WORST
     by bias state at the pin
       ending                  121663 trades  R +0.039
       immature                 27598 trades  R +0.082
       running                  43417 trades  R +0.000
     by candle code
       HAM                     104679 trades  R +0.042
       SS                       87999 trades  R +0.030
     by fill
       FVG                      15488 trades  R +0.208
       OB                       57006 trades  R +0.079
       at the focus line       120184 trades  R -0.006
     by risk size
       normal 1-3%             118541 trades  R +0.038
       tight  <1%               29276 trades  R +0.047
       wide   >3%               44861 trades  R +0.024

   WHAT TWO EXITS WOULD HAVE DONE — descriptive, not a choice
     as it ships (target 3.5R)      +0.0362 R per trade
     + break-even stop after +1R    +0.0498   (+0.0136)
     + half off at +1R              +0.0466   (+0.0104)
     winners the break-even stop would have SCRATCHED: 16554  ( 35.8% of winners)
     WALKED BAR BY BAR, not inferred from MFE: a winner that went
     +1R, came back through its entry and then ran to target is
     counted as a SCRATCH here, which is what would really happen.

==============================================================================
Min60  ·  168611 resolved trades
==============================================================================

   losers 130107   winners 38504   ( 77.2% of trades lose)

   HOW FAR THE LOSERS GOT BEFORE THEY DIED
     never moved          11782    9.1%
     under +0.5R          28526   21.9%
     +0.5R to +1R         39576   30.4%
     +1R to +2R           30879   23.7%
     +2R to +3R           14569   11.2%
     +3R or better         4775    3.7%

     GAVE IT BACK from +1R or more: 50223 ( 38.6% of losers)
     GAVE IT BACK from +2R or more: 19344 ( 14.9% of losers)

   HOW MUCH HEAT THE WINNERS TOOK  (max adverse, in R)
     median  0.42   p75  0.69   p90  0.87   p95  0.93
     never went past -0.25R:  31.4%  <- a stop there keeps  31.4% of winners
     never went past -0.50R:  57.8%  <- a stop there keeps  57.8% of winners
     never went past -0.75R:  79.8%  <- a stop there keeps  79.8% of winners

   WHICH BUCKET LOSES WORST
     by bias state at the pin
       ending                  105848 trades  R +0.009
       immature                 25070 trades  R +0.002
       running                  37693 trades  R -0.037
     by candle code
       HAM                      95260 trades  R +0.006
       SS                       73351 trades  R -0.012
     by fill
       FVG                      13036 trades  R +0.127
       OB                       52487 trades  R +0.036
       at the focus line       103088 trades  R -0.038
     by risk size
       normal 1-3%              85618 trades  R -0.001
       tight  <1%                6701 trades  R +0.111
       wide   >3%               76292 trades  R -0.013

   WHAT TWO EXITS WOULD HAVE DONE — descriptive, not a choice
     as it ships (target 3.5R)      -0.0021 R per trade
     + break-even stop after +1R    +0.0185   (+0.0205)
     + half off at +1R              +0.0184   (+0.0204)
     winners the break-even stop would have SCRATCHED: 13824  ( 35.9% of winners)
     WALKED BAR BY BAR, not inferred from MFE: a winner that went
     +1R, came back through its entry and then ran to target is
     counted as a SCRATCH here, which is what would really happen.

==============================================================================
READ THE FIRST BLOCK. If most losers never moved, the ENTRY is the
problem and no exit will fix it. If a large share gave back a gain,
the entry is finding something the exit is handing back — and those
are different weeks of work.
```
