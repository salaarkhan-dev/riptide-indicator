# The late backup: removing the tax removes the opportunity

Against [`PREREG_undertow_late_backup.md`](../prereg/PREREG_undertow_late_backup.md).
Same population, config and metric as
[`UNDERTOW_BACKUP_FILL.md`](UNDERTOW_BACKUP_FILL.md): 23 symbols, 12,000 bars,
`maxLive 64`, 7bp fees, mean R per **armed setup**.

## The one number that settles it

**Of the live backup's ADDED trades — the +0.6 R ones — 100% filled INSIDE the
20-bar Focus window.** On all three timeframes.

| tf | ADDED fills | median | p75 | p90 | max | inside the window |
|---|---|---|---|---|---|---|
| Min15 | 425 | 2 bars | 4 | 6 | 20 | **100%** |
| Min30 | 461 | 1 bar | 3 | 7 | 20 | **100%** |
| Min60 | 519 | 1 bar | 3 | 7 | 20 | **100%** |

A backup that waits for the Focus limit to expire cannot have a single one of
them. Not "fewer of them" — **none**. The median fill lands **one or two bars**
after arming, and the window is twenty.

That is a structural fact, not a statistical one, and it ends the line of
reasoning. The +0.6 R ADDED trades and the −0.28 R PRE-EMPTED trades are the
same population separated only by what price did *afterwards*.

## The arms, for completeness

| tf | L1 − L0 | ± | z | L1 − L2 (control) | L1 − L3 (live) | late backups |
|---|---|---|---|---|---|---|
| Min15 | +0.004 | 0.041 | +0.09 | +0.004 | **−0.022** | 34 |
| Min30 | −0.003 | 0.032 | −0.11 | −0.006 | **−0.037** | 24 |
| Min60 | −0.002 | 0.038 | −0.05 | +0.010 | **−0.029** | 31 |

**24 to 34 backups** against the live design's 1,070–1,229. Bar 1 declares every
panel UNDERPOWERED — the prereg set that threshold at 100 before the run, for
exactly this reason.

**Bar 5 — the hypothesis — failed 0 of 3.** Late is worse than live everywhere.
The per-trade value of what survives is +0.51, −0.65, −0.29 R on 32 / 24 / 31
trades, which at those counts says nothing in either direction.

Bars 3 and 4 failed too. Bar 2 passed after the fix below.

## Against the prediction

| predicted | actual | |
|---|---|---|
| 10–60 backups per tf (revised down from 100–180 after a disclosed structural check) | **24–34** | right, and only because the check was run first |
| zero pre-emption by construction | 0, after two bugs | see below |
| net 0.00 to +0.02, bar 3 fails, panel underpowered | −0.003 to +0.004, failed, underpowered | right |
| **bar 5 — "the one number I cannot call"** | **failed 0 of 3** | called it as uncertain; it was not close |
| the control matches | it does | right |
| median ADDED fill under 10 bars | **1–2 bars** | right, and more extreme than expected |

## THE PART WORTH KEEPING: an impossibility caught two bugs

The prereg contained a bar that tested **nothing about the hypothesis**:

> **NOT CONFOUNDED.** … **L1's PRE-EMPTED count must be exactly 0.** A non-zero
> pre-emption in a design where it is impossible means the implementation does
> not match this document and the run is VOID.

Pre-emption cannot happen when the Focus limit is cancelled before the backup
is placed. The first run reported **1**.

That single impossible count was the only visible symptom of a keying bug in
the setup matcher, present in the *previous* study too and invisible there. It
took two rounds to clear:

1. **The quadrant.** A panel spans both halves of every symbol and each half is
   indexed from 0, so `(symbol, arming bar)` matched a setup in the newer half
   against a different one in the older half.
2. **The pin bar.** Two candidates can arm on the *same bar* — a pullback holds
   several pins and their confirmations can land together. Keyed on the arming
   bar alone they shared a slot, and one filling at the Focus while the other
   filled at a backup read as a single setup that did both.

The key is now `(symbol, quadrant, pin bar, arming bar)` and is verified
collision-free: 4,442 filtered armed entries, 4,442 unique keys. Fixing it
moved the previous study's denominator by 19% and changed none of its
conclusions; both pages carry the corrected numbers.

**Write down what must be IMPOSSIBLE, not only what you expect.** An
expectation that fails tells you the world is surprising. An impossibility that
fails tells you the code is wrong — and nothing else in either study would have
said so.

## Where this leaves Undertow

Five components have now been ablated against pre-registered bars and a control:

| component | verdict |
|---|---|
| the candle taxonomy | adds nothing; removing it scored higher on 2 of 3 |
| the location | no effect |
| the exit rule | eight exits, none beat a coin's hit rate |
| the bias gate | cancellation helps, admission-blocking does not |
| the backup fill | +0.6 R and −0.28 R that cancel; zones lose to a midpoint |

None survived its control. The +0.6 R in ADDED is real, large and
**structurally uncapturable** — it lives only in trades that are
indistinguishable, at the moment of entry, from the ones that cost −0.28 R.

The one remaining explanation is the one no backtest can reach: whether a human
choosing which setup to take beats the machine taking all of them. The watch
exists for exactly that, it ships off, and the right move now is to stop
measuring history and start recording the future.
