# PRE-REGISTRATION — v3, the corrected anchor

Committed before the first number. Run by
`indicators/undertow/studies/undertow_v3.py`.

## What changed since v2

[`SPEC.md` §2.3d](../SPEC.md) records the anchor correction, confirmed by the
strategy's author: **the counter-trend candle is not at the pullback's top, it
is the bounce attempt at the leg low.**

    downtrend makes a new leg low
      └─ GREEN HAMMER at the low          ← the 1CP
           ├─ W: close ABOVE its high     the bounce WORKS, price rallies
           └─ F: close BELOW its low      the bounce FAILS
                → limit SHORT at its open
                → stop at the rally's high — the new lower high

**The geometry argued for it before any measurement did.** The stated priority
shape in a bearish trend is the hammer, which has a long LOWER wick; a long
lower wick at the top of a rally is not a rejection. And the family mix
confirms it, with no priority rule applied:

| anchor | priority shape | hammer (bearish) | shooting star (bullish) |
|---|---|---|---|
| pullback extreme — v1 and v2 | **51.1%** | 49.2% | 54.3% |
| **trend extreme** | **76.7%** | **77.5%** | **75.7%** |

**Two parts of the strategy were already right and are not changed here.**
Colour: every bearish setup already takes a green candle, 2,675 of 2,675. Stop:
already at the pullback extreme with tracking and a 0.25 ATR buffer — measured,
453 of 453 bearish stops sit above the entry and the median gap from the
rally's high is exactly the buffer.

## v3 in full

| | v1 | v2 | **v3** |
|---|---|---|---|
| bias | riptide 6/2, all Ending rules | SMC 50/5, CHoCH+BOS only, after a BOS | **same as v2** |
| confirmation | either order | W → F | **same as v2** |
| pins per pullback | all independent | newest supersedes | **same as v2** |
| **anchor** | pullback extreme | pullback extreme | **TREND extreme — the leg low** |
| **family priority** | none | none | **hammer first bearish, star first bullish** |
| `locTol` | 0 | 0 | **2** |

`locTol = 2` is not a chosen parameter — it is the stated rule, *"we detect the
first candle; if that does not qualify, move to the second and third."* At 0 the
anchor admits 689 bearish pins against v1's 2,675, which is a coverage problem
as well as a departure from the rule.

## The arms

| id | | |
|---|---|---|
| **W0** | v1 exactly as shipped | **THE BASELINE** |
| **W1** | the full v3 stack | **THE PRIMARY** |
| W2 | v1 + the anchor only | descriptive — isolates the anchor |
| W3 | v3 without `famPriority` | descriptive |
| W4 | the v2 stack exactly | descriptive — v2 on this universe |
| **C** | seeded random entry matched to W1, whole series | **THE CONTROL** |

**W2 is the arm that answers the question that prompted this.** v1 differs from
it by the anchor and nothing else, so `W2 − W0` is what moving the pin to the
leg low is worth, with everything else held at v1.

**The anchor and its tolerance move together and cannot be separated here.** At
`locTol 0` the new anchor is not the stated rule, so `W2 − W0` is the anchor
AS STATED — `pinAt` and its 2-bar tolerance as one object. A study that
separated them would need a fourth arm and a reason to want one; the rule does
not come in halves.

Descriptive arms may not be promoted. Best-of-five is selection, and it is the
−0.31 R per trade [`UNDERTOW_PARAMS.md`](../measurements/UNDERTOW_PARAMS.md)
measured as the cost of picking from a chart.

## Population

**`SYMBOLS_FRESH6`** — ranks 226–270 under the frozen rule, disjoint from the
23 and from all five earlier fresh sets. Nothing from it has been seen.

* 45 symbols, 12,000 bars, Min15 / Min30 / Min60, ≥ 11,000 bars or dropped
* `maxLive = 64`, `rr` 3.5, pullback stop with tracking, 0.25 ATR buffer, 7bp
* the candle taxonomy, the levels and the exit are **unchanged**
* the control marks unresolved entries to market and samples the whole series —
  both bugs [`UNDERTOW_PULLBACK.md`](../measurements/UNDERTOW_PULLBACK.md)
  records

## Pre-registered bars, on W1

1. **COVERAGE.** ≥ 200 closed trades.
2. **NOT CONFOUNDED.** `nCap` 0 in every arm.
3. **BEATS v1.** W1 − W0 ≥ **+0.10 R per trade**, clustered |z| ≥ 2.
4. **BEATS ITS CONTROL.** ≥ 1 SE above the seeded random entry.
5. **POSITIVE.** Mean R per trade > 0 after fees.
6. **NOT ONE TIMEFRAME.** Positive on ≥ 2 of 3.

**PROMOTION RULE: v3 becomes the shipped rule — port, chart and watch — only if
W1 clears 3, 4, 5 and 6.** The anchor goes on the chart regardless *only* if
W2 shows it is not actively harmful; a correction that loses money is still a
correction, but it does not get drawn as the default.

## My prediction, recorded before the run

* **W1 fails bar 4.** Thirteen components measured, none has beaten a control.
  That prediction has been right thirteen times and I have no reason to think
  the fourteenth differs — but this is the first change that alters WHICH
  candle rather than how many, so it is the first time I hold it loosely.
* **W2 − W0 is the number I genuinely cannot call.** Everything before this
  moved counts; this moves the object. If the anchor matters at all, it shows
  here, and I would not be shocked by ±0.10 R.
* **`famPriority` (W3) barely moves R per trade.** The anchor already produces
  77% priority shapes; forcing the remaining 23% is a small population change.
* **v3 trades LESS than v1 and MORE than v2.** The anchor is stricter than v1's
  moving target, `locTol = 2` loosens it back, and v2's stack is stricter than
  both.
* **The win rate stays on the 22.2% line.** Every arm in thirteen studies has.
  If v3 breaks that pattern it is the first evidence of an edge in this
  project, and it would be visible in that column before any bar is read.

## What must be IMPOSSIBLE

Written down before the run, because the twice-burned failure in this
repository is not a wrong number, it is a **right-looking number measuring the
wrong thing**. A renamed constant that no longer matches falls through to the
old branch and prints a full table under a new name — which is exactly what
the `swingSrc` dropdown rename did to five published studies.

* **`W2 ≠ W0`.** They differ by the anchor and nothing else. Identical means
  `pinAt` never reached the pin.
* **`W1 ≠ W4`.** Same test inside the v2 stack.

Either one firing makes the run **VOID**, not "inconclusive", and the numbers
are not published.

## What cannot happen

* **No second value** of `locTol`, `smcSwingLen`, `smcInternalLen` or anything
  else. v3 is fixed above.
* **No promotion of W2, W3 or W4**, whatever they print.
* **No falling back to an earlier universe for the primary.**
* **No change to the candle taxonomy, the levels or the exit.** The stop is
  already correct and is not touched.
* **No production DEFAULT change unless the promotion rule is met.**
  `tests/test_control_frozen.py` must still pass.
* **No exchange API key and no order placement.**
* **One study, one run.**
