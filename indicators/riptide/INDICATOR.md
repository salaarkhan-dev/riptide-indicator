# Riptide — the production sweep-and-reversal engine

**Status: LIVE.** This is the strategy the bot runs. It is not a watch and it
is not a bench.

```
pine/riptide-indicator.pine     the chart source, byte-for-byte the control
```

## The rule this repository keeps

**This file is the CONTROL and does not change during research.** Its Pine
inputs and `riptide/config.py`'s `Cfg` are calibrated against each other, and
the bot's alerts are verified against this indicator's chart output. Two checks
enforce that rather than leaving it to memory:

* `tests/test_control_frozen.py` — the engine's behaviour is hashed. A change
  to the signal path fails the test rather than silently redefining every
  measurement that came before it.
* `deploy/check-parity.py` — every setting shared between the Pine and the
  bot's config is compared. 24 of them agree today.

Both run under `python3 deploy/preflight.py`.

## Where its evidence lives

Not here. This engine predates the per-indicator layout and its measurements
are the project's own: `docs/MEASUREMENTS.md`, `docs/STRATEGIES.md`,
`research/studies/` and `research/README.md`. The live scoring is in the bot's
`/stats`, which reads forward outcomes rather than a backtest.

## Known, unfixed

Lines 721 and 744 hold `size() == 0 or get(...)` array guards — the RE10045
pattern, where Pine evaluates both sides. It has been offered and never
authorised, and it is a production risk independent of anything in research.
