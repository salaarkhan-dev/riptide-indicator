# Which of Undertow's gates is doing anything?

## Run 1 — VOID, by its own pre-registered rule

Against [`PREREG_undertow_pin_value.md`](../prereg/PREREG_undertow_pin_value.md).
Six arms, one frozen configuration (Pine defaults, `rr` 3.0, 7bp fees), 23
symbols, 12,000 bars per symbol per timeframe.

**Bar 2 failed on every timeframe: the arms are confounded by `maxLive`.**

| tf | arm | mean R | ± | n | **turned away at the cap** |
|---|---|---|---|---|---|
| Min15 | A0 FULL | −0.153 | 0.079 | 811 | 683 |
| | A3 location only | −0.061 | 0.061 | 1086 | **7879** |
| Min30 | A0 FULL | −0.044 | 0.072 | 651 | 640 |
| | A3 location only | −0.033 | 0.052 | 884 | **7846** |
| Min60 | A0 FULL | +0.061 | 0.109 | 665 | 719 |
| | A3 location only | −0.007 | 0.091 | 922 | **8233** |

A3 admits so many more candidates that `maxLive = 4` refuses **seven to nine
setups for every one it trades**. The two arms are not being compared on the
same terms — the looser one is throttled — so `A0 − A3` measures the cap as
much as the gate.

The prereg named this confound before the run, set the threshold (`nCap` above
the filled count), and said: *"If arms are confounded by the cap, that is the
reported outcome and the fix is a new prereg, not a rerun."* So this run is
void and the numbers above are published rather than quietly replaced.

**Worth being clear about the incentive**, because "the study was void, let me
run another" is exactly what a bad result looks like from the outside: the void
here is mechanical, was declared before the data was touched, and fired on the
design rather than on the answer. Every arm in the table is negative or within
noise of zero. There is nothing to rescue.

### What run 1 established anyway

**1. `maxLive = 4` is not a neutral setting, and it is distorting the chart
too.** Even the untouched baseline A0 turned away 683 of 1,494 candidates on
15m and 719 against 665 fills on 1h. The cap exists for the drawing budget —
`SPEC.md` says so — and it is silently deciding which setups get taken. The
panel row "at cap" was reading 76 on the user's ETH chart and that is the same
effect at a smaller scale.

**2. The population is far better powered than the parameter study was.** 651 to
1,086 trades per arm against 45–153 in the sweep, so SEs of 0.05–0.11 R instead
of 0.17. At that resolution A0 on 15m reads **−0.153 ± 0.079**, which is z ≈
−1.9 — not significantly positive, and closer to significantly *negative*.

**3. A5 sits awkwardly beside the ghost column, and this is the one real
tension.** Removing all five Ending rules gives −0.071 / −0.029 / −0.079 over
about 8,000 trades per timeframe, against A0's −0.153 / −0.044 / +0.061. On 15m
and 30m, *no bias gate at all* scored better than the gate. The ghost column in
the parameter study said the opposite: setups the gate cancelled were worth
−0.40 to −0.61 R each.

Both can be true — the ghost measures setups cancelled *after arming* inside a
population the gate otherwise shaped, while A5 changes which setups exist at
all — but the prereg said in advance that if A5 were not worse, that would be
the more interesting outcome. It is, and it is unresolved. A5 is also the most
cap-confounded arm in the table, which is reason enough not to read it yet.

---

## Run 2 — the candle is dead

Against [`PREREG_undertow_pin_value_v2.md`](../prereg/PREREG_undertow_pin_value_v2.md).
One change from run 1: `maxLive = 64`. **`nCap` is 0 for every arm on every
panel**, so bar 2 passes and the contrast is clean.

### The primary contrast

| tf | A0 FULL | A3 location only | **A0 − A3** | ± | z | verdict |
|---|---|---|---|---|---|---|
| Min15 | −0.144 (n 893) | −0.071 (n 1978) | **−0.073** | 0.104 | −0.71 | dead |
| Min30 | −0.035 (n 723) | +0.015 (n 1609) | **−0.049** | 0.099 | −0.50 | dead |
| Min60 | +0.070 (n 761) | −0.022 (n 1699) | **+0.092** | 0.132 | +0.70 | dead |

All three inside ±0.15 R, none within reach of significance, and the sign is
not even consistent. **The wick taxonomy and the counter-trend colour test add
nothing measurable.** On two of three timeframes the arm with *no candle test at
all* scored higher, while producing roughly twice as many trades.

That is the pre-registered bar 4, met on 3 of 3.

### Every arm, primary panel

| arm | Min15 | Min30 | Min60 | n (15m/30m/1h) |
|---|---|---|---|---|
| A0 FULL | −0.144 ± .080 | −0.035 ± .083 | **+0.070** ± .103 | 893 / 723 / 761 |
| A1 no wick | −0.130 | −0.068 | +0.047 | 1053 / 845 / 881 |
| A2 no colour | −0.088 | **+0.048** | +0.002 | 1673 / 1370 / 1480 |
| A3 location only | −0.071 | +0.015 | −0.022 | 1978 / 1609 / 1699 |
| A4 no location | −0.087 | −0.002 | +0.018 | 2394 / 2045 / 2175 |
| A5 no Ending rules | −0.054 ± .029 | −0.037 ± .027 | −0.070 ± .031 | 12203 / 11196 / 11661 |
| *their controls* | −0.03 to −0.11 | −0.00 to −0.15 | −0.01 to −0.08 | |

**No arm is significantly different from its own random control on any
timeframe.** The control SEs are of the same order as the arm SEs, so nothing in
this table approaches z = 2 against its control.

### The best-powered estimate in the project

A5 runs **11,000–12,000 trades** per timeframe, the largest sample anything here
has had, and it reads **−0.054 ± 0.029**, **−0.037 ± 0.027**, **−0.070 ± 0.031**
— z of −1.9, −1.4 and −2.3.

A5 is not "the strategy"; it is the strategy with the Ending rules removed. But
it is the cleanest available estimate of the underlying bet — *buy the pullback
extreme in a structural uptrend, 3R target, stop past the extreme* — and after
7bp of fees that bet is **slightly negative, consistently, on the largest sample
available.** Which is what a zero-edge entry with costs on looks like.

### The A5 / ghost-column tension, now partly resolved

Run 1 had A5 beating A0 on two of three timeframes, against a ghost column
saying the bias gate saves 0.40–0.61 R per cancelled setup. Uncapped:

| | Min15 | Min30 | Min60 |
|---|---|---|---|
| A0 (gate on) | −0.144 | −0.035 | **+0.070** |
| A5 (gate off) | −0.054 | −0.037 | −0.070 |

Mixed, not a contradiction: A5 is better on 15m, identical on 30m, clearly worse
on 1h. My second pre-registered prediction — "A5 stays at or above A0" — was
half right and is not supported as stated.

There is a coherent story that fits both measurements, and it is a **hypothesis,
not a finding**: the gate does two different jobs, and only one of them works.

* **Cancelling a setup that has already armed** — what the ghost column measures
  — looks strongly positive on all three timeframes.
* **Blocking new pins while the bias reads Ending** — the part A5 removes — looks
  neutral to slightly harmful.

If that is right, the gate should be split: keep the cancellation, drop the
admission block. Nothing here tests that, because nothing here varied the two
independently. It needs its own pre-registration and it is the most concrete
open question Undertow has.

### What run 2 does not say

It does not say Undertow loses money at a rate anyone could trade against, and
it does not say the location layer works. Every arm sits within about 0.1 R of
zero and within noise of its own control. The finding is **attribution**: the
candle is not where any effect lives, because there is no effect to locate.

The one number that is nearly a claim is A5 on 1h at z = −2.3, and it is one of
eighteen descriptive numbers in this study. The prereg says no significance
claim comes from those, so none is made.
