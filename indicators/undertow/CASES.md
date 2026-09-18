# Three setups the chart owner took and the chart did not

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
