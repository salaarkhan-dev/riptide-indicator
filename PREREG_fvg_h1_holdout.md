# PRE-REGISTRATION — confirmatory test of the FVG/1h result on 90 unseen symbols

Committed before the first number. Run by
`research/studies/fvg_h1_holdout.py`.

## The single hypothesis

`research/CCP_CONTEXT_FILTERS.md` found one cell that was not noise-shaped:
**on Min60, grabs with an unfilled FVG in the trade's direction were positive
in both halves of the discovery window.**

```
discovery, 23 symbols, 333 days, Min60
  OLD   n 891   R +0.090   Δ +0.108  z +2.07   control Δ +0.020
  NEW   n 926   R +0.034   Δ +0.127  z +2.53   control Δ −0.045
```

That cell failed its own study's bars — the same filter loses on Min15 and
Min30, the panel was flagged UNDERPOWERED, and it is one sub-panel of six arms
across three timeframes. It earned exactly one thing: **a test on data that did
not generate it.**

**This prereg tests one hypothesis, once.** There is no exploration here, no
second arm, and no other timeframe. That is the whole point: the discovery ran
36 panel-level cells, this runs one.

    H: on Min60, grabs with an unfilled directional FVG have positive
       net R after fees, and beat grabs without one.

## Population — the holdout

The exchange lists **113 symbols**. The discovery used the **23** in
`research.data.SYMBOLS`. This uses **the other 90**, over the same 333-day
window, at Min60.

Symbols are kept if `load_universe` returns at least its default 2,000 bars.
The count that survives is reported; no symbol is dropped for any other reason,
and none is dropped after its result is seen.

**This is a cross-sectional holdout, not a clean replica, and the difference
matters.** The 90 are smaller, newer and less liquid than the 23. A real effect
should still appear; an artefact of the discovery universe should not. But a
*positive* result here is weaker evidence than a forward run would be, and this
file will not claim otherwise.

## Held constant — everything

Identical to `PREREG_ccp_context_filters.md`, and the code imports the FVG
definition from that study rather than restating it, so the two cannot drift:

* entry: close of `grabBar + ccpFwd`, market
* stop: extreme of the grab window minus 0.25 × ATR
* target 2R, horizon 48 hours, `research.harness` fees, `simulate_market`
* grabs from the 3/3 narrow instance
* **F2 unchanged**: a three-bar gap in the trade's direction formed at bar *i*
  in `[grabBar − 1, signalBar − 1]`, still unfilled at the signal bar

**No parameter is tuned. Not one.** If the effect needs a different FVG
window, a different target or a different stop to appear, it is not this
hypothesis and this run does not look for it.

## Metric and bars

Bet = one grab. SEs clustered by (symbol, calendar day).

1. **COVERAGE.** At least **300 FVG grabs** in the holdout. Below that the run
   is declared not measurable rather than read — the discovery cell had ~900
   per half and was already underpowered.
2. **MAKES MONEY.** Standalone net R **> 0** after fees.
3. **BEATS UNFILTERED.** Δ = R(FVG) − R(no FVG) **> 0**.
4. **IT IS ABOUT GRABS.** Δ exceeds the same filter's Δ on seeded random-bar
   entries with matched direction and risk fraction.
5. **SIGNIFICANCE.** Clustered |z| ≥ 2.0 on Δ.

**Family size is ONE.** One hypothesis, one timeframe, one arm, one
population. There is no multiple-comparison correction to argue about, which is
the entire advantage of a confirmatory run and the reason nothing else is
bolted on.

### Power

The discovery got ~1,800 FVG grabs from 23 symbols over 333 days at Min60.
Ninety symbols should give more, but they are newer, so the bar-1 floor of 300
is the guard. SE(Δ) near 0.05 R is expected; if the realised MDE exceeds
**0.15 R** the run is declared **UNDERPOWERED** and reported as a bound.

### A robustness report that can only falsify

The holdout is split at the median by available history into more- and
less-established halves, and R is reported for each. This is **descriptive, not
a test**: it cannot rescue a failing result, and it exists because an effect
concentrated in the thinnest symbols is an artefact of a fixed fee assumption
rather than a tradeable edge. If bars 1–5 pass but the effect lives only in the
thin half, the verdict is **not confirmed**.

## My prediction, recorded before the run

**I expect this to fail bar 2.** The discovery cell is one of 36, it was
underpowered on its own terms, and three prior studies put gross expectancy at
a grab at about zero with an available edge budget of roughly +0.03 R against a
0.05–0.14 R fee drag. The both-halves replication is the one thing arguing the
other way, and it is why the test is worth running rather than dismissing.

If it passes, I am wrong, and it earns a forward-tracking run before anything
is built on it — not a signal, not an alert, and not a line of production code.

## What cannot happen

* **No tuning, no second arm, no second timeframe.** If it fails, Min240 does
  not get a turn and neither does a 1.5R target.
* **No production change.** Nothing under `riptide/`;
  `tests/test_control_frozen.py` must still pass.
* **No exchange API key, no order placement.**
* **One run.** There is no v2 of this prereg.

## If it fails

Then the FVG/1h cell was the 26% the family-wise warning described, four
studies agree, and the grab layer stays what it has been: context, with no
entry, no alert and no claim.
