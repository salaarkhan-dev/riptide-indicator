# Pre-registration — BTC regime as a filter on EARLY signals
Written before the held-out window was fetched.

## The claim being tested
On the discovery window (the most recent ~41.6 days, already mined for this
and much else), early signals split by whether the BTC 30m SuperTrend agrees
with the trade direction:

    disagrees  -0.129  (n=626)
    agrees     +0.045  (n=758)
    +0.174, 3.6 SE, monotone, same sign on all four splits, survives the
    stop-size control in all three terciles.

## Stated direction, in advance
BTC 30m AGREEING predicts a HIGHER R per signal. A result the other way
refutes it; a result near zero refutes it.

## The contradiction that has to be resolved
The BTC DAILY trend points the opposite way on the same signals, -0.122 at
-2.6 SE. Both cannot be a description of the same mechanism. Three timeframes
(30m, 1h, 4h, daily) are therefore reported together. A coherent story looks
like a monotone drift across timeframes; an incoherent one looks like 30m
alone, with the rest noise around zero — and that would mean the 30m result
was one of fourteen comparisons landing at 3.6 SE by chance.

## Held-out data
A window of 2000 Min30 bars ending where the discovery window BEGINS. It has
never been looked at, by me or by any earlier script in this project. No
parameter was chosen on it.

## Metric
research/harness.py, unchanged. R per signal, unfilled 0.0, net of fees, live
windows, target 2.0R (the shipped setting).

## Bar for calling it real
On the HELD-OUT window alone: the stated direction, >= 3 SE, and the same sign
on all four splits. The discovery window does not count towards it — it is
where the hypothesis came from.
