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

## Run 2

Against [`PREREG_undertow_pin_value_v2.md`](../prereg/PREREG_undertow_pin_value_v2.md).
Results appended below once it has run.
