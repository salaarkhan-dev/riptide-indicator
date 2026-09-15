# Does our structure mark anything, and at which period?

Prereg: `research/studies/PREREG_structure_value.md`, committed before the run.

    python3 research/studies/structure_value.py

## First: the comparison you asked for cannot be run

"Which structure is better, ours or the reference's" has no answer available
from here. The reference's engine is inside `mickes/PriceAction/4` —
`PriceAction.ChangeOfCharacter()`, `PriceAction.BreakOfStructure()`,
`priceAction.Swing.Trend` — and that library is not fetchable
(`audit/LIQUIDITY_INDUCEMENTS_AUDIT.md` §0).

To run a head-to-head I would have to re-implement it from its call sites and
from how it behaves on a few screenshots. That is a guess at their code, and a
number produced by comparing against a guess measures my reconstruction, not
their indicator — whichever way it comes out. So it was declared impossible in
the prereg rather than approximated afterwards.

What follows measures **ours**, alone, against zero and against two controls.

## Result: 0 of 21 cells pass

```
══ CHOCH ══════════════════════════════════════════════════════════════
   msLen     n  per 1k bars    fwd@20     SE  SE units      C1      C2   held-out
      20   411          8.9    +0.036  0.189      +0.2  -0.069  -0.112    flipped
      15   501         10.9    -0.194  0.168      -1.2  +0.115  +0.083       held
      12   613         13.3    -0.320  0.148      -2.2  -0.004  +0.116       held
      10   713         15.5    -0.277  0.142      -1.9  -0.152  +0.005       held
       8   868         18.9    -0.412  0.120      -3.4  +0.083  +0.207       held
       6  1103         24.0    -0.308  0.105      -2.9  +0.052  -0.029       held
       5  1252         27.2    -0.307  0.103      -3.0  -0.295  +0.123       held

══ BOS ════════════════════════════════════ every arm UNDERPOWERED ════
      20   340          7.4    -0.089  0.244      -0.4  -0.242  -0.062    flipped
      15   379          8.2    -0.093  0.227      -0.4  -0.335  -0.287    flipped
      12   374          8.1    +0.154  0.230      +0.7  +0.151  -0.028    flipped
      10   357          7.8    -0.027  0.232      -0.1  -0.082  -0.091    flipped
       8   331          7.2    +0.100  0.240      +0.4  +0.017  +0.230    flipped
       6   292          6.4    +0.182  0.261      +0.7  +0.219  +0.096    flipped
       5   239          5.2    +0.328  0.332      +1.0  +0.264  +0.037       held

══ IDM ════════════════════════════════════════════════════════════════
      20   751         16.3    +0.305  0.116      +2.6  -0.087  +0.036       held
      15   852         18.5    +0.278  0.108      +2.6  -0.059  -0.038       held
      12   914         19.9    +0.291  0.107      +2.7  +0.077  -0.017       held
      10   942         20.5    +0.162  0.109      +1.5  +0.180  -0.174       held
       8   976         21.2    +0.160  0.112      +1.4  +0.134  +0.063       held
       6   922         20.1    +0.122  0.117      +1.0  -0.057  +0.045       held
       5   780         17.0    +0.079  0.126      +0.6  -0.060  +0.018       held
```

`fwd@20` is the mean forward move in ATR units over 20 bars, signed by the
event's own direction. C1 is the same bars with a coin-flip direction, C2 is
random bars with the same bull/bear mix. 14 of the 21 cells are powered; all
seven BOS cells are not, so their nulls are bounds rather than verdicts.

---

## 1. Your instinct about the IDM is the one the data likes

IDM is the best of the three by a distance: **+0.29 ATR at +2.7 SE**, the
held-out half agrees, and it beats both controls at `msLen` 12, 15 and 20. It
also strengthens with horizon — +0.29 at 20 bars, +0.77 at 40 — though the
prereg barred the 40-bar horizon from the verdict and that bar stays where it
was put.

It still **fails**. The bar was 3.0 SE because the family is 21 comparisons,
and 2.7 is not 3.0. That is the bar doing its job, not a technicality to
argue around: at 2 SE a family this size hands out a false positive by
construction, which is why the 3.0 was fixed in advance.

So: the closest thing to a real signal in this layer is the part you already
said you liked, and it is close enough to be worth its own study on fresh
data. It is not established.

## 2. CHoCH goes the WRONG WAY, and gets worse the more of them you ask for

This is the part that matters, and it contradicts what I was about to
recommend last message.

Read the CHoCH column down. At `msLen` 20 it is flat (+0.04). Every step
shorter makes it more negative, to **−0.41 ATR at −3.4 SE** at `msLen` 8.
Price moves *against* the CHoCH's direction.

It is not a market-drift artifact. Checked directly:

```
unconditional "always long" 20-bar move : +0.234 ATR ± 0.075  (n=2254)
    -> the market over this window drifted UP

CHoCH at msLen=8, split by direction:
    BULLISH CHoCH (dir +1): -0.306 ATR ± 0.171   (n=437)  -1.8 SE
    BEARISH CHoCH (dir -1): -0.519 ATR ± 0.167   (n=431)  -3.1 SE
```

A drift artifact would push one direction down and the other up. **Both are
negative**, and the bullish one is negative *against* a rising tape. The
controls sit near zero, as they should.

The reading that fits: a short `msLen` fires a CHoCH on every small
counter-trend bounce, and small counter-trend bounces get faded. The extra
CHoCH labels you get by lowering `msLen` are precisely the ones that are
wrong.

**This was not a preregistered hypothesis.** The prereg tested "is it
positive", and a significant negative is not the same claim. It cannot be
acted on as a fade signal without its own prereg on fresh data, and it is not
being acted on here. What it is sufficient for is a warning.

## 3. BOS is unmeasurable here

Every arm underpowered — 3 SE runs from 0.68 to 1.00 ATR against the 0.60
limit. BOS is the rarest event (5–8 per 1000 bars) and the noisiest. Nothing
in the table is evidence either way, and the held-out sign flips at six of
seven arms, which is what noise looks like.

---

## What this changes

**`msLen` stays at 15.** Nothing passed, so nothing licenses moving it. And I
withdraw the suggestion from the previous message that you set it to 8 to
match the reference's density: at 8, CHoCH is at its most negative, −0.41 ATR
at −3.4 SE with the held-out half agreeing. The change would have bought more
labels and worse ones.

If anything the table argues *upward* — `msLen` 20 is the only setting where
CHoCH is not negative — but "the only arm that isn't negative" is not a
finding either, and one default flip per week is enough.

**On keeping one structure.** Ours is the only one that can be measured at
all, which is an argument from availability rather than from quality. What
the measurement says about it, honestly: the IDM is near-significant and
positive, the CHoCH is significantly negative at fine periods, the BOS is
unresolvable. That is a thin basis for keeping it and no basis at all for
preferring it over an engine nobody here can read.

The defensible reason to keep ours is a different one and worth stating
plainly: it is the one whose source you have, whose conditions are checked
statement-by-statement against the Pine
(`deploy/ms-py-parity.py`), and whose failure modes are written down.

**None of it touches Riptide's signals.** Section 12 remains context. Every
alert, entry, stop and target is identical with it on, off, or set any way at
all.
