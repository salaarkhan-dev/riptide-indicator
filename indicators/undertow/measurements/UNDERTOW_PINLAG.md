# The second-last candle of the pullback: a null, and a rarer rule

From [`undertow_pinlag.py`](../studies/undertow_pinlag.py). **DESCRIPTIVE** —
the spent 23-symbol set, no prereg, no holdout, nothing promoted. It exists to
answer whether there is an effect worth pre-registering, not to decide anything.

**THIS PAGE WAS CITED SEVEN TIMES BEFORE IT WAS WRITTEN.** The numbers below
were produced by running the study, and were then quoted as
"UNDERTOW_PINLAG.md is a null" in the port, the Pine tooltip, the watcher,
[`../CASES.md`](../CASES.md), the port check and two commit messages — while no
such file existed. The measurements were real and the citation was not, which
is the failure [`PROVENANCE.md`](PROVENANCE.md) exists to prevent wearing a new
face: not a superseded page quoted as current, but a page quoted into being.
Written here so every one of those references resolves.

## What was compared

| arm | rule |
|---|---|
| **A** | `pinLag 0` — the newest qualifying candle. What shipped at the time. |
| **B** | `pinLag 1` — the second-newest. The chart owner's stated rule. |

Paired **on the pullback** and restricted to the pullbacks where both rules
traded and chose a **different** candle, clustered by symbol. Shorts only.

## The verdict

| gate | tf | B − A | ± | z | pairs |
|---|---|---|---|---|---|
| strict | Min15 | −0.468 | 0.238 | −1.97 | 55 |
| strict | Min30 | *not reported — too few pairs* | | | |
| strict | Min60 | +0.219 | 0.156 | +1.41 | 36 |
| family | Min15 | −0.096 | 0.137 | −0.70 | 71 |
| family | Min30 | −0.056 | 0.098 | −0.57 | 63 |
| family | Min60 | **+0.870** | 0.274 | **+3.18** | 43 |

**THE TIMEFRAMES DISAGREE ON THE SIGN**, which is what noise looks like at
these sample sizes. The mechanism is real and the effect is not resolved.

**AND THE ONE LOUD CELL DOES NOT SURVIVE ITS OWN ROBUSTNESS LINES.** The
family/Min60 +0.870 rests on 43 pairs over 16 symbols, **nine of which
contribute two pullbacks or fewer**; ETH alone contributed +3.478 R from a
single pullback. Worst leave-one-out +0.696, pair-weighted +0.668, symbols
agreeing 11 of 16. Picking the loudest of six cells is the selection
[`UNDERTOW_PARAMS.md`](UNDERTOW_PARAMS.md) priced at **−0.31 R per trade of
pure illusion**.

## What the rule costs, which is not in R

A pullback offering only **one** qualifying candle gives lag 1 nothing to pick,
so it does not trade it at all. That is most of them:

| tf | gate | pullbacks lag 1 gave up | A armed | B armed |
|---|---|---|---|---|
| Min15 | family | 1398 | 491 | 450 |
| Min30 | family | 1442 | 465 | 401 |
| Min60 | family | 1445 | 396 | 334 |

On the shipped configuration the same effect is larger still — **202 armed
setups become 41** on Min30 across the 23. Rarity is not a defect, but a page
comparing R without saying so would be describing a strategy nobody runs.

## Two things this page has had to correct

**"82% of pullbacks offer only one candle."** Wrong. That came from grouping
armed setups within twelve bars of each other. Counted from the pullback each
candle actually belongs to, a choice exists on **36%** of pullbacks under the
strict shape gate and **62%** under the whole hammer family.

**"Re-run it, the pin counter was broken."** Also wrong. The `PIN_LOCAL`
pullback-boundary fix touched only code inside `if p.pinAt == PIN_LOCAL:` and
this study pins `pinAt = PIN_PULL`, so the bug could not reach it. Re-run
anyway on 2026-09-19: **bit-identical**, same pair counts, same leave-one-out.

## Staleness, stated rather than hidden

Its `BASE` is pinned to the configuration that shipped in **early September** —
`msLen 50`, the minor-swing stop, the tradeable bias gate. All three have since
moved. Both arms see the same trend read, so the comparison is fair; it is not
current. Re-pinning to today's defaults would be a **new measurement** on the
spent set, not a re-run.

## What was done with it

`pinLag 1` **shipped anyway**, on 2026-09-19, at the strategy author's
instruction and against this page. The stated reason is that it arms the setups
he actually takes (cases 2, 3 and 5 in [`../CASES.md`](../CASES.md)) and the
backtest has never seen which setups he takes or how long he holds them. That
is an argument for a forward record, and it is recorded as such rather than as
a result.

It has since been superseded in intent by
[`UNDERTOW_PINPICK.md`](UNDERTOW_PINPICK.md), which measures the rule `pinLag`
turned out to be a proxy for.
