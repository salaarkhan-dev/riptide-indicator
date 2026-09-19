# Setups the chart owner took, and what the chart did with them

Diagnosed with `run(trace=True)` and [`why.py`](why.py). Each was located in the
cached candles by its levels rather than its timestamp — the OHLC in a
screenshot header identifies a bar to a tenth of a point, a remembered time does
not, and the first attempt at case 1 analysed the wrong bar because of it.

**REMEMBERED SETUPS ARE A BIASED SAMPLE.** These are three that worked. So only
MECHANISM is taken from them: a reason that would still be a reason if the trade
had lost. A threshold that merely sat on the wrong side of one of them is not
a defect, and none of the fixes below is a threshold move.

## The three

| | tf | bar | what refused it | is it a defect? |
|---|---|---|---|---|
| **1** | Min30 | 11624, 09-09 12:00 | bias **Ending**, legitimately — 82.7% retraced against a 70 threshold. Then shape: `dnW − upW` **0.019** against `wickEdge` 0.05 | the shape cut is a THRESHOLD, and it is finer than the gap between two price feeds |
| **2** | Min30 | 11658, 09-10 05:00 | bias **Ending** on a STALE latch (39% retraced), then **location**: the anchor was 41 bars and **4.86 ATR** away | **yes, twice** — `retraceLatch` and the anchor |
| **3** | Min15 | 11271, 09-09 19:00 | the bias direction was **LONG**. He was short | **yes** — `msLen` 50 |

## What each one taught

### Case 2 — the pullback anchor is not a pullback

The code's "pullback extreme" was 79,735.5 from **twenty hours earlier**, while
price had fallen twelve hundred points through a series of small pullbacks it
does not see as pullbacks at all. `pbExt` only resets when the structure makes a
new low, and at `msLen 50` those are fifty bars apart.

All three existing anchors are tied to structure and all three are worse:
`PIN_PULL` 41 bars, `PIN_LEG` and `PIN_TREND` 79.

`PIN_LOCAL` — the rally since the lowest low of the last `pbLook` bars, no
structure in it — puts both Min30 pins **on** the extreme (0.00 and 0.13 ATR)
and reproduces his stop on case 2 to **14 points in 78,500**. Stable from
`pbLook` 6 to 12; it collapses back onto the structural high at 16.

**And it does not make money.** ~50% more setups at the same expectancy per
setup: −0.058 against −0.057 on Min15, −0.073 against −0.087 on Min30, worse on
Min60. A real defect, correctly fixed, no edge — which is worth knowing.

### Case 3 — `msLen 50` gets the DIRECTION wrong

| bias length | direction at his pin | tradeable |
|---|---|---|
| **50/3 — ships** | **+1 LONG** | no |
| 14/3 | −1 SHORT | yes |
| 6/2 | −1 SHORT | yes |
| SMC structure | −1 SHORT | yes |

He was short and he was right: price fell to 77,725 and his stop was never hit —
the high reached 78,549.5 against a stop at 78,552.6, **3.1 points**.

With `msLen 14` and `PIN_LOCAL` the setup ARMS, and with the backup on — which
ships — it FILLS VIA FVG, which is exactly the entry he proposed
("use the fvg... after W→F find the first fvg and get entry from there"). That
machinery already existed; nothing needed building.

### `msLen 50` is the thread through all three

* case 3 — the direction is wrong
* case 2 — `pbExt` cannot reset, because it waits on a structural low
* case 1 — `ending` cannot clear, because it waits on a CHoCH or a with-trend
  BOS and at fifty bars those are a hundred bars apart

Measured separately: at 50 the bias is tradeable **24%** of the time, holds a
median of **172 bars**, and turns **3.5 times per thousand bars**. At 14 it is
41%, 52 bars, 11.5 turns.

## What was changed, and what was not

**Changed — all additive, all off by default, none of them a threshold move:**

| | |
|---|---|
| `retraceLatch` | the retrace rule stops latching. It is a continuous, recoverable condition and `bias()` already argues, for `mixed`, that latching such a thing "would turn one bar of disagreement into a permanent cancellation" |
| `locAtr` | location as a price distance in ATR instead of a bar count |
| `PIN_LOCAL` / `pbLook` | the local pullback anchor |
| `biasGate` | the bias for its DIRECTION only, no veto on its state |

**Not changed:**

* **`wickEdge`.** Case 1 misses it by 0.019 and my cached feed differs from his
  by 12–15 points on a 175-point range, so I cannot even resolve whether it
  passes on his data. That is the argument for the continuous score in
  [`SPEC_DETECTION.md`](SPEC_DETECTION.md), not for moving the cut to catch one
  remembered winner.
* **`rr`.** See below.

## Two things I had wrong, corrected here

**"The risk unit is inflated sevenfold."** It is not. Median risk per trade is
1.30% under the shipped anchor and 1.32% under `PIN_LOCAL` on Min15 — the same.
`locTol = 0` forces the pin to BE the extreme, so every trade the code actually
takes already has a tight stop. The 7× gap was real for his case 2 and is not a
property of the population.

**"Median MFE is 0.98R, so the 3.5R target sits past where the money is."**
That number is from `UNDERTOW_EXITS.md`, which [`PROVENANCE.md`](measurements/PROVENANCE.md)
lists as SUPERSEDED — an older engine at `rr 3.0`. Re-measured on what ships:

| | median MFE | p90 | ≥3.5R | ≥10R |
|---|---|---|---|---|
| Min15 `PIN_LOCAL` | **2.72 R** | 8.71 | 38.0% | 5.6% |
| Min30 `PIN_LOCAL` | 2.89 R | 8.23 | 41.1% | 5.7% |
| Min60 `PIN_LOCAL` | 2.66 R | 8.25 | 37.5% | 6.1% |

**`rr 3.5` is reached by 34–41% of fills.** The target is roughly where the
distribution puts it. His 10.73R and 10.11R sit in the top ~6%.

Quoting a superseded page as though it described what ships is the exact failure
`PROVENANCE.md` was written to prevent, and it was written the same day.

---

## SHIPPED: `msLen` 14 and `biasGate` "direction only"

And the first thing to say is that **`msLen 14` fixed case 3 and broke case 1.**

| case | he went | msLen 50 | msLen 14 |
|---|---|---|---|
| 1 (Min30) | SHORT | **SHORT** | **LONG** |
| 3 (Min15) | SHORT | **LONG** | **SHORT** |

Case 1 flips at 20 and below; case 3 needs 14 or shorter. **No single length
agrees with him on both.** The recommendation was made on four legs and one of
them — "it agrees with his direction" — had only ever been checked on the case
it was derived from. Checking the other two first was one command.

It is not a reason to revert: 50 was wrong on case 3, is the root of the
blockers on 1 and 2, and the population favours 14 (Min30 spread +0.200 against
+0.140, Min15 t 3.26 against 2.86). But the claim is 1 of 2, not 2 of 2.

### Where the three stand on what now ships

| | bias | blocked at |
|---|---|---|
| 1 | LONG, ending | shape — the direction now disagrees too |
| 2 | SHORT, ending | **location**, anchor 4 bars back |
| 3 | SHORT, immature | **location**, anchor 10 bars back |

The bias gate is gone as a blocker on all three. Cases 2 and 3 fail on LOCATION
alone, which is what `PIN_LOCAL` fixes and which was deliberately held back so
that one change shipped at a time. The blocker moved cleanly from one gate to
the next, which is the whole argument for shipping them singly.

### Two guards that were not guarding

* **`msLen` sat in the three-way check's ABSENT bucket** as "bar-pivot bias
  only" while the watcher had `MS_LEN` and fed it straight to `_bar_pivots`.
  The check that exists to stop the chart and the bot drifting apart was blind
  to the largest lever on either, and this change could have reached one and
  not the other in silence. Now MIRRORED, with `msShortLen` and `biasGate`.
* **`biasGate` was not in `PINNED`**, so moving it would have re-pointed all
  twenty studies. Fielded, pinned at `tradeable` in all twenty, and only then
  moved — with `anchor`, `htf` and `slope` bit-identical first.

### Now that Ending trades

| tf | ending | running | immature |
|---|---|---|---|
| Min15 | 20 | 19 | 13 |
| Min30 | 21 | 16 | 14 |

Roughly a third each. The state rides on every armed setup and every alert, so
the three are scoreable apart whenever that is asked for — which is the reason
for taking all three rather than a claim that Ending is as good as Running.

---

## Case 4 — Min15, bar 10481, 2026-09-01 13:30. THE FIRST ONE THAT LOSES.

The first setup that needed no fix: on what ships now it is **already
detected** — bias SHORT, immature, ARMED, no gate refused it. His observation
was exactly right and the code agrees with it: **the Focus limit never
filled.** Price left without coming back.

| backup setting | outcome |
|---|---|
| backup OFF — Focus limit only | armed, never filled → **R 0** |
| **OB + FVG — ships** | filled via **OB** at 77,392 → **R −1.05** |
| FVG only — what he proposed | armed, never filled → **R 0** |

**The machinery he asked for is already there, and it fired via an ORDER BLOCK,
not an FVG** — there was no FVG to catch it. Restricting to FVG-only would have
skipped this trade, which on this instance is better (0 beats −1.05) and across
the 15m series is worse:

| | armed | filled | via backup | mean R |
|---|---|---|---|---|
| backup OFF | 52 | 39 | 0 | −0.127 |
| **OB + FVG — ships** | 52 | **47** | 17 | **−0.090** |
| FVG only | 52 | 44 | 11 | −0.135 |

The order blocks are doing the useful half.

**WHY THIS CASE IS WORTH MORE THAN THE THREE WINNERS.** Cases 1–3 were trades
that worked and were missed, so they can only ever say what the code fails to
find. This one says the code is not merely missing winners: it found a setup,
took it, and lost. Remembered setups are a biased sample and four is not a
sample at all, but a losing case is the only kind that can push back.

It is consistent with the re-run backup measurement — +0.011 / +0.030 / +0.035
R per armed setup, positive on all three timeframes and not established, with
ADDED trades worth +0.65 to +0.96 R each against PRE-EMPTED at −0.26 to −0.28.
This is an ADDED trade that went the wrong way.

## Where this stands, and what is still unmeasured

Four cases in, the score is: two real mechanism defects found and fixed
(`retraceLatch`, the pullback anchor), one shipped default corrected (`msLen`),
one shipped default corrected in the wrong direction for one case out of two,
one threshold deliberately left alone (`wickEdge`), and one case that needed
nothing.

**No edge has been demonstrated by any of it.** `PIN_LOCAL` finds the right
pullbacks and earns the same per setup. `msLen 14` reads the trend better and
the population says it is no better paid. Detection has improved and
expectancy has not moved, which narrows the remaining candidates to two:
**which setups he takes** — still entirely unmeasured, and what
[`label_setups.py`](label_setups.py) exists for — and **how long he holds**,
where his 10.73R and 10.11R sit in the top 6% of a distribution the fixed 3.5R
target caps off.

---

## Case 5 — VVV_USDT Min15, the FIRST LONG, and it overturns a conclusion

Not in the cache (it ends 09-17 at 24.58; this is live at 28.05), so it is
recorded from the chart rather than diagnosed from candles. Two qualifying
candles in the dip; he was asked which he would take and answered **the earlier
one** — the second-last qualified, mirrored to the long side exactly as stated.

Entry 27.730, stop 27.132, target 29.483 — RR **2.9**, against the 8–10 on his
shorts. Worth noting rather than explaining: the long side may simply not offer
the same reward, and nothing here has measured that.

### THE CONCLUSION IT OVERTURNS, and the bug under it

CASES.md previously recorded: *"his stated rule is not the one his trades fit"*
— `pinLag 1` armed case 2 and not case 3, while `pinNewest` off armed both.

**That was a bug in `pinLag`, not a fact about his trading.** `pinSeen`, the
per-pullback count of qualifying candles the lag reads, was reset inside the
block that handles the STRUCTURAL pullback boundary, while `PIN_LOCAL` set its
own boundary two hundred lines later. The counter was therefore running across
what PIN_LOCAL treats as several separate pullbacks, and "exactly one newer
candle" fired at the wrong moments. The rule was never fairly tested.

With the boundary unified — PIN_LOCAL now computes its pullback at the top of
the bar, where the reset happens:

| rule | case 1 | case 2 | case 3 | Min30 armed |
|---|---|---|---|---|
| `pinNewest` on — ships | refused: shape | no arm | ARMED +3.32R | 102 |
| `pinNewest` off | refused: shape | ARMED +3.25R | ARMED +3.32R | 202 |
| **`pinLag 1` — his rule** | refused: shape | **ARMED +3.25R** | **ARMED +3.25R** | **41** |

**His stated rule fits every case that can be tested**, and case 5 confirms it
on the long side. It is also far the most selective — 41 armed against 102 and
202 — which is the shape of a rule belonging to someone who takes one or two
setups a day out of a hundred and fifty found.

Case 1 is still refused, still on `wickEdge`, still left alone.

**The lesson is the one this file keeps recording**: a rule that fails a test
has two possible causes, and the implementation is the one to rule out first.
`undertow_pinlag.py`'s null — -0.468 / -0.056 / +0.870 — was measured on the
same broken counter and should be re-run before it is cited again.
