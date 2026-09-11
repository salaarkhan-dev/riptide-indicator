# Pre-registration — stop distance measured in the coin's own ATR

**Written and committed 11 Sep 2026, before the variable was computed on any
row.** Nothing below was chosen after seeing a number. If the result section of
`research/studies/stop_atr.py` disagrees with anything here, this file is the
record and the study is the outcome.

---

## Where the hypothesis came from

`research/studies/symbols.py` tested three ex-ante symbol properties against
outcome. Two of them (a hand-written meme label, and turnover) flipped sign
between the two halves of the window and are dead. One did not:

> Inside the surviving stop-distance cell (confirmed setups whose stop sits
> 1.2%–2.6% from entry), the **wild** realised-volatility tercile beat the
> **calm** one by **+0.300 R/bet in the first half and +0.298 in the second** —
> the same number twice, out of sample. It is not the meme symbols in disguise:
> strip all nine out and the wild tercile is still +0.291 over 83 trades.

That result was found on a tercile of *ambient volatility* while *stop distance
as a percent of price* was held inside a fixed band. Holding a numerator fixed
and varying a denominator is a clumsy way to express a ratio, so the variable
this file pre-registers is the ratio itself.

## The variable

```
R_ATR  =  |entry − stop|  /  ATR(28) at the signal bar
```

Dimensionless. How far the stop sits from the entry, **in units of how far this
coin ordinarily moves**, rather than in percent of price.

ATR is the engine's own `atr_series(cs, CFG.atr_len)` read at the signal bar —
causal by construction, already on the production path, and the same series the
stop's buffer is built from. No trailing window is invented for this.

**It is not mechanically determined by the stop rule.** The stop is
`raid_extreme ∓ sl_buffer_atr × ATR`, so ATR enters the stop only through a
small buffer; the distance is dominated by how far the entry gap sits from the
raid extreme. `R_ATR` therefore measures something real: how tightly the
structure pinned the turn, relative to the coin's own noise.

## Direction, stated before the test

**LOW `R_ATR` performs better than HIGH.**

This follows arithmetically from the finding above — with stop-percent held
inside 1.2–2.6%, a *wild* coin (large ATR) produces a *low* ratio, and wild won
both halves.

It is also the direction a naive reading would get **backwards**: a stop that is
close in ATR terms is more exposed to ordinary noise and "should" be hit more
often. The proposed mechanism is that a tight stop relative to a coin's own
movement means the raid was unusually well defined — precision of the setup, not
safety of the stop. **That mechanism is post-hoc and is not evidence.** It is
written down so it cannot be rewritten after the fact to fit whatever comes out.

## Design

**Discovery set:** the original 60-symbol universe, 333 days, Min30.
**Held-out set:** symbols on which no hypothesis in this project has ever been
fitted — a genuinely fresh cross-section rather than a later slice of the same
one.

> ### Amendment, 11 Sep 2026 — before any row was scored
>
> This section originally said the held-out set would be "the ~44 symbols added
> by raising `RIPTIDE_TOP_N` from 60 to 104". **That was based on a miscount and
> is corrected here, before the variable was computed on anything.**
>
> The 104 figure counted every USDT perpetual above the 3M turnover floor. The
> scanner deliberately excludes MEXC's tokenised stocks and commodities — XAU,
> USOIL, SPX500 and the rest — which are most of what expanding would add.
> Crypto-only, the real counts are: **69** above 3M, 79 above 2M, 120 above 1M,
> 161 above 0.5M, 220 above 0.3M, out of 595 live crypto USDT perps.
>
> So raising `TOP_N` to 104 adds **nine** symbols, not forty-four: the floor
> binds, not the cap. Nine symbols is far too thin to hold out.
>
> **The fix keeps the design and leaves production alone.** The research
> universe does not have to equal the scanned universe. The held-out set is now
> every crypto symbol between the 60th and roughly the 120th by turnover — the
> band from the current floor down to 1M/day — loaded for measurement only.
> `RIPTIDE_MIN_VOL` is NOT changed, so the bot scans exactly what it scanned
> before plus the nine, and no thinner coin reaches an alert.
>
> This amendment changes the SAMPLING FRAME, forced by a fact about the
> exchange's listing mix, and changes nothing about the variable, the direction,
> the bucketing, or the pass criteria. Those remain exactly as committed in
> e2f16b0.
>
> **One consequence to hold against the result:** the held-out symbols are by
> construction thinner than the discovery ones. If the held-out arm disagrees,
> liquidity is a live alternative explanation and not merely a caveat. Median
> turnover of both sets is reported alongside the result.

**Primary population:** all confirmed grade A/B setups. This is where the
statistical power is — 504 bets, MDE 0.346.

**Secondary, reported but NOT decisive:** the 1.2–2.6% stop band alone, which
is where the lead was found. At 252 bets its MDE is 0.497, which is **larger
than the +0.30 effect that prompted this test.** The cell cannot resolve its own
hypothesis and saying so in advance is the point of writing this down.

**Buckets:** terciles of `R_ATR`, with boundaries computed **on the discovery
set only**, then **frozen** and applied unchanged to the held-out set. The
boundaries are not tuned, not re-cut, and not revisited.

**One test. One direction. No second bite.**

## What counts as a pass

All three, or it has failed:

1. **Discovery direction and size.** The low tercile beats the high tercile,
   and the spread is at least the discovery MDE (0.346 R/bet).
2. **Not a handful of coins.** The winning tercile's symbol bootstrap (4000
   resamples, `research/studies/survivor.py`) has a 5th percentile above zero.
3. **Held-out sign.** On the 44 unseen symbols, with the frozen boundaries, low
   still beats high, with a spread of at least half the discovery spread.

Criterion 3 is deliberately a **sign-and-magnitude** test, not a significance
test. At roughly 440 bets the held-out set has an MDE near 0.37 and could not
reach significance even if the effect were entirely real. Demanding significance
there would be demanding something the sample cannot supply, which is how a
genuine effect gets discarded.

## What would make the result uninterpretable

Recorded now so it cannot be argued about later:

- If the 44 new symbols turn out to be materially thinner than the original 60
  such that their fill assumptions differ, the held-out arm measures liquidity
  rather than the hypothesis. Median turnover of both sets is reported.
- If `R_ATR` turns out to correlate above about 0.8 with stop-percent, the two
  are the same variable and this adds nothing. The correlation is reported.

## Expectation, recorded before the first number

I expect the **discovery arm to show the right direction and fail criterion 1
on magnitude** — the prompting effect was +0.30 against an MDE of 0.346, so it
is sitting right on the threshold and the coin lands either way. I expect the
held-out arm to be the informative one, and I give it slightly better than even
odds of reproducing the sign.

If this fails, it is the last lead on the list and the honest next move is the
question in `HANDOFF.md` section 9 — whether there is an edge here at all —
rather than a fourteenth hypothesis.
