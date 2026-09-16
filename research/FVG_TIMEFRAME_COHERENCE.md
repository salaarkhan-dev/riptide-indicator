# Is the FVG result coherent across timeframes?

Pre-registered in `PREREG_fvg_timeframe_coherence.md`. Study:
`research/studies/fvg_timeframe_coherence.py`.

## The pre-registered verdict: OUTCOME C

The prereg fixed three readings before any number existed. By its rule this is
**C — mixed signs across adjacent timeframes, unstable, not established, no
forward run.** That stands as recorded.

```
Min15   n  2,534   R -0.044 ± 0.030   Δ +0.108 ± 0.033   z +3.28   control Δ +0.096
Min30   n 28,910   R +0.005 ± 0.009   Δ +0.087 ± 0.010   z +8.82   control Δ +0.014
Min60   n 15,639   R +0.045 ± 0.011   Δ +0.117 ± 0.013   z +9.33   control Δ +0.045

anchor: Min60 reproduces +0.045 against the expected +0.046 — pipeline sound
```

## Two things wrong with the test, and I designed both

**1. The Min15 panel covers 25 days.** Min30 and Min60 each got 862 days. The
exchange would not page Min15 back further at that resolution, so the panel
that produced the "mixed sign" — the whole basis of outcome C — has **3% of the
others' time span** and sits entirely inside one month of market.

| | window | grabs |
|---|---|---|
| Min15 | **25 days** | 12,933 |
| Min30 | 862 days | 149,093 |
| Min60 | 862 days | 83,222 |

The prereg set a floor on the number of grabs and none on the span of time.
12,933 grabs in one month looks like coverage and is not.

**2. The rule classified on the sign of standalone R, which mixes up the effect
with its cost.** Look at Δ — the thing the filter actually does:

    Min15  +0.108   z +3.28
    Min30  +0.087   z +8.82
    Min60  +0.117   z +9.33

**Positive and strongly significant on all three.** As a statement about
whether the FVG filter sorts grabs, this is as coherent as it gets. What varies
across timeframes is not the sorting, it is whether what is sorted survives
fees — and I wrote a rule that could not tell those apart.

## A post-hoc observation, labelled as one

This was noticed after seeing the numbers and is therefore **not evidence**. It
is written down because it is checkable and because it predicts something.

`research/studies/ccp_entry_models.out` measured the mean fee drag per bet:
0.136 R at Min15, 0.088 at Min30, 0.058 at Min60 — cost goes as 1/risk, and
risk as a fraction of price grows with timeframe. Adding it back:

| | net R | fee drag | implied gross |
|---|---|---|---|
| Min15 | −0.044 | 0.136 | **+0.092** |
| Min30 | +0.005 | 0.088 | **+0.093** |
| Min60 | +0.045 | 0.058 | **+0.103** |

**The gross edge is flat across timeframes; only the cost changes.** On that
reading the effect was never about 1h at all — 1h is simply the first timeframe
where the same edge clears its own fees. The drags are borrowed from a study
with a different stop rule, so the arithmetic is indicative and not exact.

## What this does and does not change

**It does not rescue the result.** Reinterpreting a failed pre-registered test
after seeing which rule failed is the exact move the preregs exist to stop, and
CCP_FILTER_OVERFIT measured what that move is worth. Outcome C stands.

**It changes what to test next.** The hypothesis is now sharper and falsifiable
in a way the original was not:

> The FVG filter's GROSS edge at grabs is constant across timeframes at about
> +0.09 R, and net profitability is fee drag alone.

That predicts three things a new prereg can check in advance: gross R within a
narrow band on all three timeframes, net R tracking `gross − 0.044/risk%`, and
Min15 turning net-positive on a fee tier low enough. If gross is not flat, this
explanation is wrong and the Min60 result goes back to being a one-timeframe
oddity.

**And Min15 needs redoing properly.** Its control Δ of +0.096 against a filter
Δ of +0.108 says the FVG barely beat a random entry there — but on 25 days of
one regime that is not a finding either.

## Status of the FVG line

| run | result |
|---|---|
| discovery, Min60 | positive both halves |
| 84 unseen symbols | CONFIRMED, z +4.12 |
| 862 days before | CONFIRMED, z +9.19 |
| **timeframe coherence** | **OUTCOME C — not established** |

No forward run, no signal, no alert, no production code. Three passes and one
failure is not a green light; it is a reason to ask a better question.
