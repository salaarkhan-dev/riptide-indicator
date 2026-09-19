# The route, the wide stop, the pullback age — two nulls and a footnote

From [`undertow_edges.py`](../studies/undertow_edges.py). **DESCRIPTIVE** —
561 cached symbols, the shipped configuration. Written so
[`PREREG_undertow_exit_and_zone.md`](../prereg/PREREG_undertow_exit_and_zone.md)
could name a threshold instead of searching over one.

## 1. W→F vs F→W→F — NULL, closed

| | W→F | F→W→F |
|---|---|---|
| Min15 | −0.026 | −0.020 |
| Min30 | +0.036 | +0.035 |
| Min60 | +0.008 | −0.015 |

The messier route is not worse. No filter, and the `· F→W→F` tag on an alert
is information rather than a warning.

## 2. Stop width — real, consistent, and a smaller prize than it looks

R by stop width, clustered by symbol:

| risk | Min15 | Min30 | Min60 |
|---|---|---|---|
| <1% | −0.015 | +0.052 | **+0.257** |
| 1–2% | −0.028 | +0.038 | +0.040 |
| 2–3% | +0.009 | +0.037 | −0.020 |
| 3–5% | −0.039 | +0.020 | −0.011 |
| 5–8% | **−0.219** | −0.037 | −0.035 |
| >8% | **−0.283** | **−0.157** | −0.013 |

Tighter is better everywhere, and those trades resolve 3–6× faster. **But the
bad buckets are rare**, so a cap moves the aggregate very little:

| cap | Min15 | Min30 | Min60 |
|---|---|---|---|
| 3% | −0.000 (keeps 89%) | **+0.008** (77%) | +0.015 (55%) |
| 2% | −0.003 (75%) | +0.004 (55%) | +0.051 (29%) |

Min60's +0.051 keeps 29% of trades — that is a different strategy, not a
filter.

**A WEIGHTING TRAP, and it nearly became a prereg hypothesis.** The first
version of this page printed clustered bucket rows above a TRADE-WEIGHTED cap
table, so a bucket reading −0.219 sat directly over a table claiming the cap
changed nothing. Two statistics presented as one. Both are clustered now, and
the corrected cap table is what shrank this from a headline to a footnote.

## 3. Minimum pullback age — NULL, and inverted from the expectation

| age at the pin | Min15 | Min30 | Min60 |
|---|---|---|---|
| 0–1 bars | −0.021 | **+0.050** | +0.014 |
| 2–3 bars | −0.014 | **+0.052** | −0.033 |
| 4–6 bars | −0.039 | +0.032 | +0.010 |
| 7–10 bars | −0.028 | +0.014 | +0.016 |

On Min30 the **youngest** pullbacks are the best. A minimum-age filter would
cut the strongest bucket. **Closed.**

There is a weaker signal in the CANDLE COUNT instead — the 4th-or-later
qualifying candle is worst on all three timeframes — but it is not
pre-registered here.

## And the control is inert

`pbMinAge` and `pbMinDepth` are applied inside `if p.pinAt == PIN_PULL`, and
the shipped anchor is `PIN_LOCAL`. Both read sensibly in the Pine and **do
nothing on the chart anybody loads.** Testing a minimum pullback without
widening that condition would have measured a field that never fires.

---

```
Three edge cases the chart owner named: the route, the wide stop, the age.
DESCRIPTIVE — 561 cached symbols, shipped configuration.
`pbMinAge` and `pbMinDepth` are INERT under PIN_LOCAL — see the module docstring.

==============================================================================
Min15  ·  205268 trades joined to their arm
==============================================================================

   1. BY CONFIRMATION ROUTE
     bucket                   trades        R     +/-      z   win%   bars
     W-F                      165461   -0.026   0.006  -4.14   23.1     20
     F-W-F                     39807   -0.020   0.010  -1.98   23.4     18

   median risk 1.25% of entry   p90 3.15%   p99 8.60%

   2. BY STOP WIDTH  (risk as % of entry)
     bucket                   trades        R     +/-      z   win%   bars
     a <1%                     75498   -0.015   0.011  -1.41   24.1     11
     b 1-2%                    79326   -0.028   0.010  -2.88   22.7     21
     c 2-3%                    27701   +0.009   0.014  +0.60   22.6     36
     d 3-5%                    15468   -0.039   0.021  -1.82   22.1     50
     e 5-8%                     4849   -0.219   0.043  -5.13   21.9     57
     f >8%                      2426   -0.283   0.060  -4.71   22.6     75

   3. BY PULLBACK AGE AT THE PIN  (bars since it began)
     bucket                   trades        R     +/-      z   win%   bars
     a 0-1 bars                55757   -0.021   0.010  -2.18   23.3     19
     b 2-3 bars                45254   -0.014   0.010  -1.42   23.4     19
     c 4-6 bars                43494   -0.039   0.010  -3.91   22.9     19
     d 7-10 bars               60763   -0.028   0.008  -3.46   23.1     20

   4. BY QUALIFYING CANDLES BEFORE THE PIN
     bucket                   trades        R     +/-      z   win%   bars
     a 1st candle             126099   -0.025   0.007  -3.58   23.2     19
     b 2nd                     48823   -0.019   0.010  -2.03   23.3     19
     c 3rd                     19963   -0.039   0.014  -2.72   22.9     19
     d 4th or later            10383   -0.025   0.020  -1.26   23.2     19

   5. WHAT A MAX-RISK CAP WOULD KEEP  (descriptive, not a choice)
          cap     kept   share        R    vs all
           2%   154824   75.4%   -0.028   -0.003
           3%   182525   88.9%   -0.025   -0.000
           4%   193130   94.1%   -0.025   +0.000
           5%   197993   96.5%   -0.025   +0.000
           8%   202842   98.8%   -0.025   -0.000
     FIVE CAPS ARE A SEARCH. None of these is a result; the prereg
     names ONE on a stated reason and scores that one.

==============================================================================
Min30  ·  192678 trades joined to their arm
==============================================================================

   1. BY CONFIRMATION ROUTE
     bucket                   trades        R     +/-      z   win%   bars
     W-F                      157474   +0.036   0.006  +5.67   24.0     20
     F-W-F                     35204   +0.035   0.011  +3.11   24.1     19

   median risk 1.86% of entry   p90 4.48%   p99 11.49%

   2. BY STOP WIDTH  (risk as % of entry)
     bucket                   trades        R     +/-      z   win%   bars
     a <1%                     29276   +0.052   0.020  +2.57   25.5      9
     b 1-2%                    76049   +0.038   0.010  +3.91   24.2     16
     c 2-3%                    42492   +0.037   0.011  +3.34   23.7     27
     d 3-5%                    29935   +0.020   0.015  +1.34   23.2     38
     e 5-8%                    10074   -0.037   0.027  -1.35   23.2     52
     f >8%                      4852   -0.157   0.046  -3.43   22.2     66

   3. BY PULLBACK AGE AT THE PIN  (bars since it began)
     bucket                   trades        R     +/-      z   win%   bars
     a 0-1 bars                53166   +0.050   0.010  +5.16   24.4     19
     b 2-3 bars                42088   +0.052   0.011  +4.84   24.4     20
     c 4-6 bars                41395   +0.032   0.010  +3.24   23.9     20
     d 7-10 bars               56029   +0.014   0.009  +1.50   23.5     20

   4. BY QUALIFYING CANDLES BEFORE THE PIN
     bucket                   trades        R     +/-      z   win%   bars
     a 1st candle             118087   +0.038   0.007  +5.39   24.1     20
     b 2nd                     46040   +0.049   0.010  +5.00   24.3     20
     c 3rd                     18970   +0.015   0.015  +1.02   23.5     20
     d 4th or later             9581   -0.014   0.021  -0.68   23.0     19

   5. WHAT A MAX-RISK CAP WOULD KEEP  (descriptive, not a choice)
          cap     kept   share        R    vs all
           2%   105325   54.7%   +0.040   +0.004
           3%   147817   76.7%   +0.044   +0.008
           4%   167810   87.1%   +0.044   +0.007
           5%   177752   92.3%   +0.039   +0.003
           8%   187826   97.5%   +0.038   +0.002
     FIVE CAPS ARE A SEARCH. None of these is a result; the prereg
     names ONE on a stated reason and scores that one.

==============================================================================
Min60  ·  168611 trades joined to their arm
==============================================================================

   1. BY CONFIRMATION ROUTE
     bucket                   trades        R     +/-      z   win%   bars
     W-F                      138687   +0.008   0.007  +1.07   22.9     19
     F-W-F                     29924   -0.015   0.012  -1.25   22.5     18

   median risk 2.79% of entry   p90 6.42%   p99 15.34%

   2. BY STOP WIDTH  (risk as % of entry)
     bucket                   trades        R     +/-      z   win%   bars
     a <1%                      6701   +0.257   0.049  +5.26   26.8      7
     b 1-2%                    41836   +0.040   0.013  +2.94   24.0     11
     c 2-3%                    43782   -0.020   0.011  -1.81   22.1     17
     d 3-5%                    45853   -0.011   0.011  -1.02   22.4     26
     e 5-8%                    20717   -0.035   0.017  -2.06   22.0     44
     f >8%                      9722   -0.013   0.033  -0.41   22.5     66

   3. BY PULLBACK AGE AT THE PIN  (bars since it began)
     bucket                   trades        R     +/-      z   win%   bars
     a 0-1 bars                46579   +0.014   0.010  +1.37   23.0     19
     b 2-3 bars                36792   -0.033   0.011  -2.91   22.0     19
     c 4-6 bars                35427   +0.010   0.011  +0.93   23.0     19
     d 7-10 bars               49813   +0.016   0.010  +1.63   23.2     20

   4. BY QUALIFYING CANDLES BEFORE THE PIN
     bucket                   trades        R     +/-      z   win%   bars
     a 1st candle             102949   +0.012   0.007  +1.60   23.1     19
     b 2nd                     40622   -0.001   0.011  -0.13   22.6     19
     c 3rd                     16409   -0.009   0.015  -0.57   22.5     19
     d 4th or later             8631   -0.026   0.022  -1.18   21.8     18

   5. WHAT A MAX-RISK CAP WOULD KEEP  (descriptive, not a choice)
          cap     kept   share        R    vs all
           2%    48537   28.8%   +0.054   +0.051
           3%    92319   54.8%   +0.019   +0.015
           4%   120857   71.7%   +0.015   +0.012
           5%   138172   81.9%   +0.013   +0.009
           8%   158889   94.2%   +0.006   +0.003
     FIVE CAPS ARE A SEARCH. None of these is a result; the prereg
     names ONE on a stated reason and scores that one.
```
