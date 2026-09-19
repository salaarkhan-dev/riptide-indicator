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

### AND THE SAME LESSON, IMMEDIATELY, AGAINST THIS SECTION

The paragraph above originally continued: *"`undertow_pinlag.py`'s null —
-0.468 / -0.056 / +0.870 — was measured on the same broken counter and should
be re-run before it is cited again."* **That was wrong.** Every line the fix
touched sits inside `if p.pinAt == PIN_LOCAL:`, and that study pins
`pinAt=PIN_PULL`; the bug could not reach it. Re-run anyway rather than argued
away, and it came back **bit-identical**: -0.468 / -0.056 / +0.870, same pair
counts, same leave-one-out.

So the null stands and is citable. Widening a bug's blast radius past what its
diff can touch is the same failure as the one this case corrects, pointed the
other way: there, an implementation fault was read as a fact about the trader;
here, a fact about the study was nearly discarded as an implementation fault.
The cure for both is the same and it is cheap — read the diff, then run it.

**What IS stale in that study** is its header, which calls its `BASE` "AS
SHIPPED, PINNED". The pinning works; the claim does not. Three of the values
have moved since it was written — `msLen` 50→14, `stopSrc` swing→pullback
extreme, `biasGate` tradeable→direction only — so the page measures the
configuration that shipped in early September, not the one that ships now.
That is the pinning discipline behaving exactly as designed, and it means the
headline compares A against B under an old trend read. Re-pinning it to the
current defaults is a NEW measurement on the spent set, not a re-run, and it
is not worth taking until there is a reason to prefer B.

---

## SHIPPED — `pinAt = local pullback`, `pinLag = 1`

At the strategy author's instruction, in all three copies, with the argument
above unchanged: **the measurement does not support this and the reason for it
is not in the measurement.** `UNDERTOW_PINLAG.md` is a null — -0.468 / -0.056 /
+0.870, signs disagreeing across timeframes, the one loud cell resting on nine
of sixteen symbols with two pullbacks or fewer. `PIN_LOCAL` finds the right
pullbacks at the same expectancy. Neither is measured as paying.

They ship because they arm cases 2, 3 and 5 — the setups he actually takes —
and the backtest has never seen which of the hundred and fifty he takes or how
long he holds them. That is a claim about the **detector**, and the instrument
that can settle it is the forward record.

### WHAT IT COST TO SHIP, which is the part worth keeping

| guard | what it caught |
|---|---|
| `test_studies_pin_their_settings` | `pinAt` and `pinLag` were **outside** `PINNED`; sixteen of twenty studies named neither, so the move would have silently re-pointed all sixteen |
| `undertow-port-check` | `pbLook`/`pinLag` listed as absent from the Pine **and** present as inputs — refused the move until the buckets agreed |
| `undertow-three-way-check` | the watcher **hardcoded** `pinAt` and assumed `pinLag 0`; its own header names this exact day as the failure it exists for |
| `undertow-pullback-check` | a second `pbStartX` assignment — and the port had had one all along that the check's regex could not see |
| `conftest.py` (new) | under `pytest` **none of these tests could fail**; the fingerprint printed FAIL and was reported as a pass |

Four of those five were guards catching the thing they were written for. The
fifth was a guard that had never been able to fire.

Procedure followed in order: pin the fields, update all twenty baselines,
re-run `undertow_anchor` as the reference, move the defaults, re-run —
**BIT-IDENTICAL** — then bump the fingerprint. The Pine and the watcher both
implement the local anchor and the lag gate; `test_watch_undertow` compares 141
setups field by field under the new defaults and they match.

**The shipped configuration is selective, not silent**: 1337 pins, 49 armed, 40
filled over 12,000 bars, with 1228 pullbacks refused for offering only one
qualifying candle. A new test asserts that, because a selective rule and a
broken one look identical from the outside and the difference is whether the
number is small or zero.

---

## Case 6 — RIVER_USDT Min15: why the green one, and why `pinLag` is the wrong rule

Not in the cache (23 symbols, RIVER is not one), so the pullback boundaries
cannot be checked against candles. What CAN be answered exactly is the
mechanism, and the mechanism is the answer.

### WHY IT CHOSE THAT CANDLE

`pinLag = 1` arms the candidate with **exactly one newer qualifying candle in
its pullback**. That is the whole test. It does not look at price, it does not
look at which working lines were broken, and it cannot prefer a higher entry.
So the candle it picked is simply the one that happened to have one qualifying
candle after it — nothing about that candle was judged.

### AND THE STATED RULE IS NOT THE STATED GOAL

Asked why he takes the second-last, the chart owner gave a different rule:

> "sometimes after the last candle market never closes above its working line
> and goes straight down, that's why we choose 2nd last so the next candle will
> go above its working line"

> "the main goal is for short trend how much up possible we can enter, not that
> much up so we miss the entry W→F"

"Second-last" is a **proxy** for that goal — a good one when the pullback offers
two candles and the newest usually fails to Work, and wrong otherwise. He said
so himself: *"in this case we can choose the last candle as the next candle
closes beyond the working line of it"*.

### THE GOAL IS DIRECTLY COMPUTABLE, WITH NO LOOKAHEAD

For a short the pin is a hammer, so **W is a close above its high and F a close
below its low**. Both are monotone in price:

* a bar closing above one candle's high closes above every **lower** candle's
  high — W spreads **downward**
* a bar closing below one candle's low closes below every **higher** candle's
  low — F spreads **upward**

So on any bar the set of candles that have confirmed is known exactly, and its
**highest member is the best short entry available at the moment an entry
exists**. Higher pin, same stop (the pullback extreme), so tighter risk and
better R. That is `pinPick = PICK_BEST`.

It handles all three cases the proxy gets wrong:

| the pullback | `pinLag 1` | `PICK_BEST` |
|---|---|---|
| last candle's working line WAS broken | refuses it, takes a worse entry | takes it |
| last candle's working line was NOT broken | takes the one below — correct | takes the one below — same |
| only ONE qualifying candle | **trades nothing at all** | trades it |

### WHAT IT MEASURES, on the spent 23 — R per pullback offered

`R/armed` flatters `pinLag 1`, because it is the average of a minority the rule
selected itself. The unit that decides is R per pullback **offered**, charging
each rule for the ones it passed on.

| | Min15 | Min30 | Min60 |
|---|---|---|---|
| lag 0 · newest | −0.044 | +0.019 | −0.005 |
| **lag 1 · ships** | **−0.013** | **+0.013** | **+0.007** |
| **PICK_BEST** | **−0.036** | **+0.047** | **−0.014** |
| C − B, clustered | −0.027 ±0.033 | +0.041 ±0.040 | −0.022 ±0.028 |

**Another null.** The signs disagree across timeframes and no z reaches 1.1.
What is not null is the frequency: **3236 / 3102 / 2990 armed against 447 / 456
/ 430** — seven times as many, because `pinLag` refuses every single-candle
pullback.

### WHAT THE PICK ACTUALLY DOES, on 72 real disagreements (Min30, 8 symbols)

* **63 of 72** keep the same candle and arm it **earlier** — `PICK_BEST` fires
  at the first confirmation, `pinLag` waits until its count comes true.
* **9 of 72** choose a genuinely different candle, and **all nine go later and
  higher** — exactly the case in this screenshot.
* Mean risk per trade **1.249% → 1.168%**, a 6.5% tighter stop on the
  disagreements, which is the mechanical benefit and the reason the rule exists.

### A REGRESSION THE SHIP INTRODUCED, found here

`pinLag > 0` skips the newest-wins supersede, so the candidate pool no longer
collapses to one per pullback — and the chart's `Live setups at once` default is
**4**. Measured on Min15, 6 symbols:

| rule | maxLive 4 | maxLive 8 |
|---|---|---|
| lag 0 (before the ship) | 0 pins refused | 0 |
| **lag 1 (ships now)** | **412 refused — 6.6% of pins** | 3 |
| PICK_BEST | 261 refused — 4.2% | 0 |

That is the `at cap 75` on the screenshot's panel. It costs about 4% of armed
setups and it was not flagged when `pinLag` shipped. **Immediate remedy: set
"Live setups at once" to 8.** Moving the default is a separate change and needs
`maxLive` pinned into `undertow_sweep.py` first — the one study of twenty-two
that does not name it.

---

## SHIPPED — `pinPick = best entry of those confirming`

In all three copies, on the strategy author's instruction, **against the
measurement**. Two other defaults moved with it because neither makes sense
alone:

| | | why |
|---|---|---|
| `pinPick` | PICK_READY → **PICK_BEST** | the rule, instead of the proxy for it |
| `pinLag` | 1 → **0** | the lag runs FIRST, so at 1 it refuses candles the pick would choose — the proxy still deciding |
| `maxLive` | 4 → **8** | both rules skip newest-wins, so a cap of 4 discards pins for no reason but pool size |

`UNDERTOW_PINPICK.md` is a null — −0.027 / +0.041 / −0.022 R per pullback
offered, signs disagreeing on all three timeframes. It ships because it is the
rule he described, not because it pays. **Seven times the alert rate** reaches
Telegram, which is the operational consequence and was stated before the ship,
not discovered after.

### THE FIFTH FIELD CAUGHT UNPINNED ON THE DAY ITS DEFAULT MOVED

`maxLive` was not in `PINNED`. Twenty-one of twenty-two studies passed
`maxLive=64` so nobody had noticed — but `undertow_sweep.py` ran at the
**default**, and a cap change unrelated to what it measures would have
re-pointed its page in silence. Pinned at 4 there and in `undertow_ablation.py`
before the default moved.

The count so far, all in two days: `stopSrc`, `biasGate`, `pinAt`, `pinLag`,
`maxLive`. Every one found by the same test, and every one found *because the
default was about to move* rather than in advance of it. **The guard works and
the habit does not** — nothing checks that a field is pinned until someone
tries to move it.

### AND FOUR TESTS DESCRIBED THE OLD DEFAULT

Moving three defaults broke four tests, none of which was testing what its name
said any more:

* the `pinLag` comparison ran both arms under the **new** pick, so "it trades
  candles the newest-wins rule never does" read **0**
* `test_pick_best_is_off_by_default` had a premise that was true for exactly
  one commit — renamed rather than patched, because a test whose title lies
  about what ships is worse than one that fails
* the shipped-configuration test asserted `lag 1`

That is the third time a test here has had to be renamed rather than fixed.
The rule that keeps being relearned: **a test must name every setting its claim
depends on, not just the one it is about.**

---

## SHIPPED — the chart owner's own inputs become the defaults

He sent a screenshot of his Undertow settings and asked for exactly those in
the Pine, the port and the watcher, **so the chart and the alerts fire on the
same candle**. Fourteen of the visible inputs already matched. Three did not:

| | | |
|---|---|---|
| `locTol` | 0 → **3** | **his.** Never a default — a real choice |
| `pinLag` | 0 → **1** | reverted, hours after moving to 0 |
| `maxLive` | 8 → **4** | reverted, hours after moving to 8 |

### TWO OF THE THREE WERE PROBABLY NOT CHOICES, and he was told so first

TradingView keeps the **saved** value for an input that already existed and
only takes the new default for a **new** one. His screenshot showed exactly
that pattern: `pinLag` and `maxLive` sat at the values that were default before
that morning, while the brand-new "Which candle arms" showed `PICK_BEST`. He
was shown the pattern, and the cost of each, and chose all three verbatim.

**Consistency between the chart and the bot is the reason, it is a good one,
and it is his to give.** Recorded here with the costs beside it so that if the
alert rate later looks wrong, the answer is one screen away instead of a day's
work.

### WHAT THEY COST — 8 symbols, both sides, measured before he decided

| config | armed | at cap | R/armed Min15 | R/armed Min30 |
|---|---|---|---|---|
| lag0 cap8 tol0 | 2186 | 0 | −0.018 | +0.051 |
| **shipped now** — lag1 cap4 tol3 | **629** | **2727** | −0.088 | +0.065 |
| lag1 only | 243 | 3 | −0.055 | −0.001 |
| cap4 only | 2141 | 325 | −0.018 | +0.050 |
| tol3 only | 3537 | 34 | −0.024 | +0.052 |

Two things are worth keeping in view:

* **`pinLag 1` runs BEFORE the pick**, so `PICK_BEST` now chooses from what the
  lag left rather than from the pullback. The pick is not disabled, but it is
  working on a filtered input.
* **2727 pins refused at the cap on Min15** is the largest number anywhere in
  this file. `locTol 3` finds 62% more pins and a pool of four cannot hold
  them. Raising "Live setups at once" is one input away on the chart and needs
  no code change.

### `locTol` WAS THE SIXTH FIELD CAUGHT UNPINNED ON THE DAY ITS DEFAULT MOVED

After `stopSrc`, `biasGate`, `pinAt`, `pinLag` and `maxLive` — **all six inside
two days.** Thirteen of the twenty-two studies did not name `locTol`, against a
setting that widens the funnel by 62%.

Six is not six unlucky fields. Every one was found by
`test_studies_pin_their_settings.py` **only because a move was already
underway** — nothing checks that a field is pinned before somebody wants to
move it. The guard is sound and the habit is missing, and the fix is a sweep
that flags any field a live study reads without naming, run before the next
default change rather than during it.
