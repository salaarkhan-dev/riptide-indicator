# Exhaustion — the 9-count and the 13-count

**Status: ships as a watch, OFF by default. Measured, and the measurement came
back negative.**

```
pine/riptide-reversal.pine     the chart source
port/td.py                     the counts in Python, what the study ran on
studies/exhaustion.py          does a completed count predict anything?
studies/exhaust_rate.py        how many rows a day would it send?
tests/test_exhaust.py          the two ports agree, and it cannot flood the chat
```

The live adapter is **`riptide/watchers/exhaust.py`** — see
[`../README.md`](../README.md) for why the runtime code lives in the bot
package instead of here.

## What was measured

`studies/exhaustion.py` joined completed counts to Riptide's own signals over
333 days and 9118 trades. A 🎯 landing near a completed count scored no better
than one landing anywhere else — **and the control settles it**: the OPPOSITE
direction benefited more (+0.273 against +0.093 on the picks, +0.281 against
+0.096 on the full stream), and the only cells clearing 2 SE anywhere in the
table were control cells.

Whatever these counts mark, it is not exhaustion. It is a regime both sides
ride. The digest says so in its own subtitle, every time it sends.

## Why it ships off

`studies/exhaust_rate.py`, 59 symbols over 333 days — rows a day across the
universe, not messages:

```
tf     M9/day   M9*/day   T13/day    both   both*
15m      128        96        40      167     136
30m       66        49        19       85      68
1h        34        24         9       43      34
ALL      227       169        68      295     237
```

Everything on is 295 rows a day: three and a half times the bot's entire alert
volume and sixteen times its 🎯 picks. Turning it on with `/exhaust on` starts
in the quiet corner — 1h only, perfected 9s only, about 33 a day.

## The drift that would otherwise be silent

The counts exist in two places: `port/td.py`, which the measurement ran on, and
`riptide/watchers/exhaust.py`, which the bot runs. They are deliberately not
one module — the research tree must never be importable from a live scanner.
The cost of that is drift, so `tests/test_exhaust.py` runs both over the same
candles and asserts they agree bar for bar, on three different series shapes.
It also pins the rate table above, which was wrong once in every file that
quoted it because it had been written from memory.
