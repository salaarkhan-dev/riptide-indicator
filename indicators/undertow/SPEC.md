# Riptide Undertow — v1 specification

**Status: SPEC ONLY. No Pine written yet. Nothing here is measured.**

v1 is a **visual bench**: it finds setups and draws them. No alerts, no outcome
scoring, no win rate, no port. The one thing v1 has to get right is
**detection** — bias, structure, pullback, pin — because everything later is
built on it being correct.

**Riptide Undertow.** An undertow is the current beneath the surface that
drags you back out, which is the thesis exactly: the pullback is the surface
move, the trend is the current under it, and the setup fires when the surface
fails and the undertow takes price back.

    Pine title   Riptide Undertow — Structure Bias & Pin Continuation
    slug         undertow          /undertow · RIPTIDE_UNDERTOW_ALERTS
    pine         pine/riptide-undertow.pine

---

## 1. Bias — from market structure

> **THE ENGINE IS LuxAlgo's "Smart Money Concepts" NOW** (CC BY-NC-SA 4.0),
> transcribed in the Pine's section 3, in [`port/smc.py`](port/smc.py) and in
> the watcher. It replaced the copy of v2's engine described below, by decision
> rather than by measurement, and the honest accounting is:
>
> * **the DETECTOR is the same expression either way** — `smc.py` proves
>   `leg()` and `bar_swings()` are pivot-for-pivot identical, and the CHoCH
>   bars are the same list
> * **the SCALE is not** — **14 and 5** against 6 and 2. It shipped at 50/5,
>   LuxAlgo's own default, and moved to 14/5 by preference after
>   [`UNDERTOW_SCALE.md`](measurements/UNDERTOW_SCALE.md) measured 50/5 against
>   6/2 and found nothing to separate them. A null there meant the preference
>   was free, which is not what a null means everywhere — compare
>   [`UNDERTOW_ANCHOR.md`](measurements/UNDERTOW_ANCHOR.md), where it meant a
>   stated rule cost half the setups for no gain
> * **the BOS is not** — LuxAlgo's is a close beyond the last pivot in the
>   trend's direction; riptide's was a close beyond the running extreme with an
>   inducement swept. `msBosNeedsIdm` has no counterpart and is gone
> * there is **no sweep** in LuxAlgo's structure, so `endSweep` has nothing to
>   read; that is stated rather than faked
>
> [`UNDERTOW_V2.md`](measurements/UNDERTOW_V2.md) scored the engine swap at
> **+0.002 / +0.065 / +0.006 R per trade**. Nothing has scored the LENGTH, and
> 50 against 6 is much the larger change. Every page in `measurements/` was
> produced on the engine below, and all twelve studies now pin
> `biasSrc=BS_STRUCT` so they keep reproducing.

The text below describes the engine that WAS here — ported from section 12 of
`indicators/riptide_ms/pine/riptide-indicator-v2.pine`, which emits CHoCH from
long swings, BOS from the running extreme, and IDM/CHoCH from short swings. It
is kept because the port can still run it and every measurement page does.

**The engine is COPIED, and that is a risk this repo has seen before.** Pine
files cannot import, so the structure engine will exist in two files and is
free to drift. `deploy/ccp-grab-check.py` already solves exactly this for the
grab engine; v1 ships the same check for this one, wired into
`deploy/preflight.py`. A copy without a check is how the two charts start
disagreeing and nobody finds out.

### The three states

Direction `D` is set by the most recent **major CHoCH**.

| state | rule | trade? |
|---|---|---|
| **None** | no major CHoCH yet | no |
| **Immature** | CHoCH into `D`, **no BOS in `D` yet** | **yes** |
| **Running** | ≥1 BOS in `D` since that CHoCH, and no ending condition | **yes** |
| **Ending** | any ending condition below | **never** |

**Ending conditions** — three independent toggles, so the chart shows which one
fires and any that prove too twitchy can be turned off:

1. the **minor structure against `D`** while the major is still `D` — either on
   the bar it flips, or the whole time it is opposed. The flip is an edge and
   can be missed when the minor turned at an awkward moment; "while opposed" is
   a level and cannot be, at the cost of far more Ending
2. ~~a **sweep** of the running extreme that closes back inside~~ — **off the
   chart.** Shipped off, never measured on, port-only now
3. ~~**no new extreme in `D` for `staleBars`** bars~~ — **off the chart**, same
   reason
4. **retraced ≥ `retraceMax`% of the impulse** (default 70). The strongest chop
   guard here and it needs no extra indicator: the impulse is the leg the engine
   already tracks from the CHoCH, `msMin` to `msMax`. This exists because the
   chart showed a LONG still reading "running" after price had given back a
   3,000-point impulse in full — the major structure was not wrong, it simply
   had not broken its last swing low yet, and by then it was useless as a trade
   bias
5. ~~**ADX(14) below `adxMin`**~~ — **off the chart.** ADX was measured as a
   filter in this project and failed: it improved seeded random entries *more*
   than real ones (`indicators/ccp/measurements/CCP_CONTEXT_FILTERS.md`). It
   was on the chart switched off, because it had been asked for and nothing
   supported it; that is not a good enough reason for an input, so it is
   port-only now

**So two Ending rules ship, not five** — minor structure and retrace. The other
three were toggles offering settings no measurement supports, which is what
[`SETTINGS.md`](SETTINGS.md) exists to stop. The port still has all five and
the studies that name them still reproduce.

Every one is decidable at a bar close and none of them repaint. They will
sometimes call Ending while the trend keeps running — that is the right
direction to be wrong in, because a false Ending costs a skipped setup and a
missed one costs a loss.

### The ghost column — measuring the gate instead of asserting it

That last paragraph is an **assumption**, and the first three charts made it
the most expensive one in the file. A triggered setup whose bias turns Ending
while the limit is resting is cancelled, and on BTCUSDT.P 30m, XAUUSD and
XAUUSDT.P that cancellation was the **largest single bucket** of no-entries —
39 of 62, 25 of 34, 13 of 15. On two of the three it killed more setups than
the strategy entered.

There is also a structural reason to distrust it, and it is not subtle. Arming
requires a close beyond **both** of the pin's extremes, which in a long means a
close below the pin's low — so a setup always arms while the pullback is still
deepening. A deepening pullback is exactly when the minor structure turns
against `D` (condition 1) and when `retraced` grows (condition 4). **The bias
gate is anti-correlated with the setup by construction**: it is most likely to
fire during the very move the strategy is waiting on.

So the gate is now measured rather than trusted. A cancelled setup is no longer
deleted — it is marked a **ghost** and walked forward through the same fill,
the same stop and the same target, into counters of its own. It draws nothing,
it takes no live slot, and it cannot touch any number above it. The panel then
reports two things it could not before:

| row | what it answers |
|---|---|
| `minor · retrace` | **which** rule did the cancelling |
| `gate cost` | what the cancelled setups **would have done**: `saved NR` if they were losers, `cost NR` if the gate is throwing trades away |

`saved` means the gate is earning its place. `cost` is its price, in R, on the
bars on screen. Both numbers carry the same in-sample caveat as everything else
here and neither settles anything — what they do is turn *"should a triggered
setup survive a bias flip"* from an opinion into a quantity that can be
pre-registered and then tested out of sample.

### Higher-timeframe bias

Off by default; the chart timeframe is the bias. When on, the HTF read uses
`lookahead_off` on the **previous** confirmed HTF bar. Anything else paints
bias onto history that did not exist yet, and every setup on the chart would
look better than it was.

---

## 2. The pin

Size is irrelevant. Body size is irrelevant. Three tests only.

### 2.1 Family — which wick dominates

```
rng = high - low
up  = (high - max(open, close)) / rng
dn  = (min(open, close) - low)  / rng
```

| family | test |
|---|---|
| **hammer / hanging man** | `dn - up >= wickEdge` |
| **inverted hammer / shooting star** | `up - dn >= wickEdge` |
| **doji — rejected** | neither, i.e. the wicks are balanced |

`wickEdge` is the doji exclusion and there is no second test for it. Without a
margin, `dn = 0.21` against `up = 0.20` passes as a hammer while looking
exactly like the doji being excluded.

### 2.2 Colour — counter-trend

| bias | pin colour | names in play |
|---|---|---|
| bearish | **green** | hammer, inverted hammer |
| bullish | **red** | hanging man, shooting star |

**Both families qualify.** The candle's own direction is ignored — the bias
decides the trade, the pin only supplies the levels.

### 2.3 Location — at the pullback extreme

> In a bearish bias, the pin's **high must be the highest high since the
> pullback began**. Mirrored for bullish.

The pullback begins at the most recent structural extreme in the trend
direction — for a downtrend, the low that ended the last impulse leg.

Written this way rather than "at the swing high" for two reasons: it is true
**at the pin's own close**, where a swing high is not confirmed until several
bars later; and if the pullback pushes higher, a new pin takes over by itself,
which is the newest-wins behaviour we want anyway.

### 2.3b THREE DEFECTS IN 2.3, FOUND BY READING IT AGAINST THE CODE

Measured on `SYMBOLS_FRESH3`, at the full funnel — family **and** colour
**and** location, so these are real setups and not raw bars:

| | Min15 | Min30 | Min60 |
|---|---|---|---|
| pin has a **ZERO-bar pullback** | **25.3%** | **30.8%** | **33.6%** |
| pullback ≤ 1 bar | 47.3% | 56.0% | 61.4% |
| pullback ≤ 3 bars | 70.9% | 80.5% | 85.2% |
| median pullback age | 2 bars | 1 bar | 1 bar |

**DEFECT 1 — the impulse bar can be its own pullback extreme.** `pbReset`
fires on the bar that makes a new extreme in the trend direction, and the same
line sets `pbExtX = i`. So on that bar `locOk` is already true and the bar's own
high (in a downtrend) is treated as "the top of the pullback" when no pullback
has happened. A quarter to a third of all setups are this. The counter-trend
colour test removes most of them — before it, 55–65% of location-passing bars
are zero-age — but not all, because a bar that makes a new low can still close
green.

**DEFECT 2 — there is no minimum pullback at all**, in bars or in price. §2.3
says "the pin's high must be the highest high since the pullback began" and
that is all it says. Nothing requires the pullback to have *happened*. The
median is one to two bars.

**DEFECT 3 — only ONE bar can ever be the pin.** `locOk` is
`(i - pbExtX) <= locTol` and `locTol` ships at 0, so the pin must BE the bar
that made the extreme. If that bar is a doji, or the wrong colour, the entire
pullback is discarded — a textbook pin on the next bar, one tick lower, cannot
qualify. §2.3's "if the pullback pushes higher, a new pin takes over by itself"
only covers the case where price extends; it says nothing about the case where
the extreme bar is simply not a pin, which is the common one.

### 2.3c WHICH candle, and WHERE — measured on SYMBOLS_FRESH5, Min15

Asked directly: "are we finding the candle in a correct place?" Three answers,
and only the first is yes.

**COLOUR IS CORRECT.** Every bearish setup takes a green candle, every bullish
one a red candle. 2,675 bearish and 1,563 bullish, no exceptions — the rule is
mechanical and it works.

**THERE IS NO FAMILY PRIORITY, and there is supposed to be one.**

| bearish (green) | | bullish (red) | |
|---|---|---|---|
| hammer — LOWER wick | **49.2%** | shooting star — UPPER wick | **54.3%** |
| inverted hammer — UPPER wick | **50.8%** | hanging man — LOWER wick | **45.7%** |

The stated intent is hammer first in a bearish trend and shooting star first in
a bullish one, with the other shape acceptable. What the code does is take
whichever of the two happens to sit at the extreme — a coin flip. §2.1 has no
ordering in it and never did.

**THE PULLBACK IS BARELY A PULLBACK.** Depth at the pin, as a fraction of the
impulse leg the engine already tracks:

| | median | p10 | p90 |
|---|---|---|---|
| bearish | **0.14** | 0.04 | 0.39 |
| bullish | **0.17** | 0.05 | 0.41 |

**A median retracement of 14%.** Nine in ten setups are taken before the
pullback has given back 40% of the leg. Read with the age numbers above — a
quarter have NO pullback at all and the median age is one to two bars — the
picture is consistent: **the pin is taken as the pullback BEGINS, not where it
turns.**

The mechanism is `pbExt` being a RUNNING extreme. The first counter-trend
candle at the running extreme qualifies immediately, and every bar that extends
the pullback qualifies again as a new candidate. Nothing waits for the pullback
to finish, because at the pin's own close it cannot be known that it has.

### 2.3d THE ANCHOR WAS AT THE WRONG END OF THE LEG

Confirmed by the strategy's author, and the geometry gives it away before any
measurement does.

**The stated priority in a bearish trend is the HAMMER — a long LOWER wick.**
A long lower wick at the TOP of a rally is a candle that dipped and recovered;
the rejection shape there is the long UPPER wick. **A hammer belongs at a LOW.**

So the counter-trend candle is not at the pullback's top. It is the **bounce
attempt at the leg low**, and that fits §8.3's W→F exactly:

    downtrend makes a new leg low
      └─ GREEN HAMMER at the low          ← the 1CP
           ├─ W: close ABOVE its high     the bounce WORKS, price rallies
           └─ F: close BELOW its low      the bounce FAILS
                → limit SHORT at its open

`pinAt = "trend extreme"` anchors there. Bullish mirrors: the shooting star at
the leg high.

**THE FAMILY MIX IS THE EVIDENCE**, and no priority rule is applied to produce
it — it falls out of looking in the right place. Measured on `SYMBOLS_FRESH5`,
Min15:

| | priority shape | hammer (bearish) | shooting star (bullish) |
|---|---|---|---|
| pullback extreme — v1 and v2 | **51.1%** | 49.2% | 54.3% |
| **trend extreme** | **76.7%** | **77.5%** | **75.7%** |

A coin flip becomes three in four. The shape the strategy says should dominate
starts dominating as soon as the anchor moves, which is about as direct a
confirmation as a location rule can get.

> **THAT LAST SENTENCE IS WRONG, and
> [`UNDERTOW_V3.md`](measurements/UNDERTOW_V3.md) is where it broke.** The
> table above is measured at `locTol 0`, and the effect lives entirely there:
> on `SYMBOLS_FRESH6` the trend anchor gives **75.6%** at tolerance 0, **53.2%**
> at 1 and **51.5%** at 2. At tolerance 0 the pinned bar *is* the bar that made
> the leg low, so a green bar there has its low below its body by construction
> — which is the definition of a hammer. The mix was the anchor describing
> itself, not evidence that it finds the right candle.
>
> The anchor may still be the correct reading — it is the author's own, the
> geometry argument above stands on its own, and the trades it adds scored
> **+0.054 / +0.107 / +0.089 R**, positive on 3 of 3 and significant on none.
> But this table is not what supports it.

**And it re-reads defect 1.** §2.3b called it a defect that "the impulse bar can
be its own pullback extreme" — a quarter to a third of setups. Under the
corrected anchor **those are the only correct ones**, and the other two-thirds
were the mistake.

`famPriority` adds the ordering §2.1 never had: hammer before inverted hammer
in a bearish trend, shooting star before hanging man in a bullish one, the
other shape used only while the priority one is absent, newest of the priority
shape winning.

**Both default to v1** so the fourteen measurement pages keep reproducing.
**Both are now measured** —
[`UNDERTOW_V3.md`](measurements/UNDERTOW_V3.md). The anchor cleared neither of
the two bars that matter and was not actively harmful, so it is **on the chart
as an input, off by default**. `famPriority` did nothing recoverable (−0.05 to
+0.10 R on 354–490 trades) and stays port-only.

> **AMENDED. `famPriority` AND `pinNewest` BOTH SHIP ON, IN ALL THREE COPIES.**
> The paragraph above is the state after V3 and it is no longer current. The
> pair went out as a CORRECTION on the footing W→F went out on: the author's
> stated rule goes on the chart, and measurement decides only the defaults it
> has an opinion about. V3 measured the pair at nothing, so it has none.
>
> **THE ANCHOR WAS THEN MEASURED PROPERLY AND IS STILL OFF.**
> [`UNDERTOW_ANCHOR.md`](measurements/UNDERTOW_ANCHOR.md) is the study V3's
> anchor arm was reaching for and missed: `pinAt = leg extreme` is the running
> extreme since the last INTERNAL break, which is the per-leg object the
> diagram shows, where V3's `trend extreme` was one stale point per trend. It
> delivered the mechanism — **86–88% of its pins were the priority shape**,
> against 53% for the shipped anchor — and the trades were **worse on 3 of 3**.
> That is the cleanest negative in the project, because it is the one that
> cannot be read as "the rule never detected what it claimed".
>
> **`famStrict` MAKES THE RANKING A GATE, and is OFF.** Only the shooting star
> in a bull trend, only the hammer in a bear trend; the hanging man and the
> inverted hammer stop being setups. With the colour rule that leaves exactly
> one code per direction and the four-code taxonomy of §2.1 collapses to two.
> It cuts **42–46%** of the armed setups, measured on the spent 23-symbol set,
> and the two surviving codes are untouched — 474 shooting stars become 475 —
> so the cut is entirely the other two leaving. A rule that removes that much
> gets a pre-registration before it becomes a default, which is the standard
> the anchor study set, and the anchor study is also why: a stated rule that
> demonstrably finds its intended candle can still trade worse.

**MEASURED — see [`UNDERTOW_PULLBACK.md`](measurements/UNDERTOW_PULLBACK.md).**
Defect 3 is real and costs setups rather than money: pins 1–2 bars after the
extreme score within **±0.025 R** of pins at it, and admitting them nearly
doubles the population (0.63 → 1.06 trades a day on 15m) at the same
expectancy. Defect 2 is a correct description and a useless filter — the
shallow-pullback setups are **not** systematically worse (+0.055 / −0.015 /
−0.065). `pbMinAge` is confirmed timeframe-dependent, keeping 39.9% / 29.8% /
23.6% of setups for one setting. **Nothing was promoted**; all three still ship
at the values below.

The original text of this paragraph read: `locTol` has only ever been tested at 0 and
at 50 — the ablation's "no location test" arm, which is a destroy-it control,
not a 1-to-3-bar tolerance. The parameters below exist so the three can be
measured separately, and **all three default to current behaviour**, so nothing
changes until a prereg says it should.

| input | ships | what it does |
|---|---|---|
| `locTol` | **0** | bars after the extreme a pin may still sit. Defect 3. |
| `pbMinAge` | **0** | bars the pullback must have run before a pin counts. Defect 1 and 2. |
| `pbMinDepth` | **0.0** | fraction of the impulse leg the pullback must have retraced. Defect 2. |

### 2.4 Grade — a label, never a gate

Tagged and shown, gating nothing:

| tag | meaning |
|---|---|
| `normal` / `partial` | body ≤ 0.35 of range, or above it |
| `+wick` | the opposite wick is ≥ 0.05 of range |

Free to record, and if partials later behave differently we can already tell
them apart instead of re-running everything.

### 2.5 Known: this filter is loose

Wick dominance plus a colour is roughly a quarter to a third of all bars. That
is expected, not a bug — **the pin is not the filter here**, it supplies the
three levels and the bias and the confirmation do the selecting. But it means
the funnel in §7 is mandatory: without it we will not know which stage leaks.

---

## 3. The three lines

**Working is the direction the candle's shape predicts. Failure is the
opposite.** They are not fixed to high and low.

| family | Working | Failure | Focus |
|---|---|---|---|
| hammer / hanging man | **high** | **low** | **open** |
| inverted hammer / shooting star | **low** | **high** | **open** |

Because both confirmations are required in either order (§4), the two labels
are mechanically identical today — a close beyond the high and a close beyond
the low. They stop being cosmetic the moment `workTest` and `failTest` differ,
which is exactly what those two inputs exist to find out.

---

## 4. Confirmation

Both required, in **either order**, within `confirmBars` of the pin.

Each line gets its own comparison, as a dropdown:

| option | meaning |
|---|---|
| `close beyond` | the close is strictly past the line |
| `close at or beyond` | a touch counts |
| `whole body beyond` | open **and** close are past it |

**The window is not optional.** With no bound the rule is eventually true for
almost every candle — price will close above some bar's high and below its low
given enough time — so a pin from 300 bars ago would arm today at a level
nowhere near price, in a trend that has since reversed. Every such setup would
look fine on the chart.

Two further conditions at the trigger bar:

- the bias must **still** be Immature or Running — not only when the pin formed
- the stop level must not already have been taken

The completion order (`W→F` or `F→W`) is **tagged**. They are two different
trades: one leaves price below the Focus line so the limit fills on a rally
into it, the other leaves price above so it fills on a drop into it. Tagging
now costs nothing and lets a later measurement split them.

---

## 5. Entry, stop, target

| | rule |
|---|---|
| **Entry** | limit at the **Focus line** (the pin's open) |
| **Fill window** | `fillBars` after the trigger, then the setup expires |
| **Stop** | dropdown: pin's own high/low · **pullback extreme** (default) · minor swing extreme, plus an **ATR buffer** (0.25, as the CCP entry model used) so a one-tick undercut does not take it |
| **Stop follows the pullback** | on. A long cannot arm without a close below the pin's low, so **every** setup arms while the pullback is still deepening and freezing the stop there sets it on an unfinished move. Two pins with the same entry were seen stopping at 77,568 and surviving at 77,432 purely on which bar they armed. Nothing is lost by moving the stop on an unfilled order — there is no position — but risk grows, the target moves with it, and *stop taken before the fill* becomes impossible by construction |
| **Target** | `rr` × risk from entry, default **3.0** |

Verified against the worked example on BTCUSDT.P 15m:

```
Focus / entry   77,380.2
Stop            77,637.5     risk  257.3
Target          76,608.5  =  77,380.2 - 3 x 257.3      exact
```

Only swings **confirmed at or before the trigger bar** may be used for the
stop. A stop drawn from a swing confirmed later is a stop that did not exist
when the trade was taken.

---

## 6. Lifecycle

```
candidate  ->  armed  ->  filled  ->  target | stop
     \           \           \
      dropped     missed      (still open at the right edge)
```

**`missed` is split four ways and the split is the point.** `no return` is the
one that sizes the OB/FVG work: the setup was valid, the limit was placed, and
price simply never came back to it. Those are exactly the setups a backup fill
would have caught. The other three — stop taken first, target reached first,
bias turned — are not the same problem and should not be counted as if they
were.

- **Every qualifying pin becomes its own candidate**, up to `maxLive` (4).
  There is no newest-wins / first-wins choice, and removing it is the point.

  > **AMENDED TWICE.** `pinNewest` came back — see the amendment in §2.3 — so
  > there IS a newest-wins rule again, ranked by the priority shape. The table
  > below is v1's measurement of the choice this section removed.
  >
  > **AND THE CAP'S ORDER WAS WRONG IN TWO OF THE THREE COPIES.** The Pine and
  > the watcher counted the live candidates BEFORE the supersede ran; the port
  > has always counted after. Counting first turns a pin away because of rivals
  > it was about to delete, so the chart drew nothing where the port — every
  > measurement page, and the reference the parity test calls truth — armed the
  > setup. **5.4 / 5.4 / 7.3% of setups differed** on 15m / 30m / 1h at the
  > shipped cap of 4. All three now count after.
  >
  > It survived because the parity test ran only at `maxLive 64`, where the
  > pool never reaches the cap and the two orders agree. A test that pins the
  > shipped value is the fix, and it now runs at both.

  A pullback does not contain one pin, it contains several. Keeping exactly one
  forced a choice with no good answer, and the chart measured both:

  | | superseded | armed | entries |
  |---|---|---|---|
  | newest wins | 256 | 14 | 5 |
  | first wins | 0 | 28 | 13 |

  Newest-wins also had a perverse edge: in a long bias the bar that closes below
  the pin's low — one of the two confirmations — is itself a new pullback low,
  so when it is also a pin it destroys the candidate it was confirming. A
  candidate survived mainly when the confirming bar happened *not* to be a pin.
  First-wins locks onto the first pin of the pullback, which is almost never the
  extreme, so its three levels are the wrong ones.

  Neither is the rule. Any of those pins might be the one that works and v1
  exists to find out which, so they all run independently. Pins arriving at the
  cap are turned away and counted on their own panel row.
- A setup is dropped when: the bias turns Ending · the confirm window runs out ·
  the fill window runs out · the stop is taken before the fill · **the target is
  reached before the fill**.

  That last one was found on a real chart and it matters more than it sounds.
  Price left the pin, ran past the target, came back, filled the limit, and then
  collapsed through the stop — and a clean "2R" was drawn over the whole thing.
  The move was available in full and the order was not on. A limit that fills
  after its own target has printed is entering a spent move at a price that only
  looks good.
- `keepN` caps how many completed setups stay drawn. Pine has a hard object
  limit and a busy chart will hit it.

---

## 7. What is drawn

The previous indicators failed on exactly this, so it is specified rather than
left to taste: **tiny labels, hidden behind candles, colliding with each other.**

### On the chart

**Every mark names itself.** CHoCH and BOS carry their own text on the bar,
because three different things were drawing circles in the first cut and a
legend you have to remember is the same failure as a label you cannot read.
The two that cannot carry text — the swing dots and the entry triangle — are
named in the panel's `marks` row.

| thing | how |
|---|---|
| **The setup candle** | named on the bar the setup was built from — `HAM` · `HGM` · `IH` · `SS` — placed outside the pin so it never covers it. Not a debug mark: which candle a trade came from is part of the setup |
| **Entry** | triangle at the **entry price**, `size.small`. **Down = short, up = long** — direction carries the meaning, so it reads without colour. It was `location.belowbar` first, which put a long's triangle under a tall candle's low, hundreds of points from the entry it was marking |
| **Working / Failure** | thin solid lines, from the pin to the trigger bar |
| **Focus** | dashed, extended to the fill bar or expiry |
| **Risk zone** | entry→stop, tinted red |
| **Reward zone** | entry→target, tinted green |
| **Labels** | `size.normal`, anchored to the **right end** of their line with `label.style_label_left` and a background, never floating over candles |
| **Unfilled setups** | armed then stopped or expired: muted dashed line and an **×**, behind `Draw setups that never filled`. Off by default; on is how past detection gets checked without waiting for live ones |
| **Rejected candidates** | not drawn at all unless debug is on |

All colours are inputs, in one group, and default to a palette that reads on
both the light and dark chart themes.

### The status panel — top right

It says what the indicator is currently seeing, and **it does now count wins
and losses** — that was added on request, and it comes with a warning printed
on its own row's hover:

> **In-sample and not evidence.** Whatever settings happen to be loaded, scored
> on the bars on screen, with no pre-registration and no control. A filter
> picked by watching a number like this scored **+0.089 in sample and −0.082
> out** elsewhere in this project (`CCP_FILTER_OVERFIT.md`). Use it to check the
> detection looks sane. Never to choose settings.

Every row carries its caveat as a **cell tooltip** rather than in the text,
because the panel was getting too wide to read. The glyph legend moved into the
`bias` row's hover for the same reason.

```
bias        SHORT · Running · 15m
pullback    active, 6 bars
candidates  14
armed       3
entries     2
last reject location (not the pullback high)
```

The last row is the whole reason the panel exists — *why was nothing found* is
the only question a quiet indicator ever raises, and a count alone cannot
answer it.

### Debug mode

Off by default. On, it adds:

- a **dot** on every pin that was detected, including rejected ones
- a **one-line** tooltip, not a paragraph:
  `H · green · partial · W✓ F✗ · 7b`
- a **funnel** in the panel: `pins → colour → location → confirmed → filled`

---

## 8. No repaint — the rules v1 must not break

1. Every decision on a **confirmed** bar.
2. HTF bias: `lookahead_off`, previous confirmed HTF bar only.
3. The stop uses only swings confirmed at or before the trigger.
4. The pullback extreme is the running extreme **so far**, never the final one.

Each of these is a place where the chart could show a setup the live scanner
can never reproduce — which would not be a cosmetic bug, it would make every
number that follows a lie.

---

## 9. Inputs — 35, of which 18 decide anything

Twenty-one came off. The rule, from
[`SETTINGS.md`](SETTINGS.md): **an input earns its place only if the strategy's
definition needs it, a study showed the choice matters, or it is display.**

| group | inputs |
|---|---|
| **1 · Bias** | swing structure · internal structure · End: minor structure · End: retraced % |
| **2 · Candle** | wick edge · hammer family · star family |
| **3 · Setup** | confirmations (W→F) · confirm within · fill within · live setups at once · anchor the pin at · anchor tolerance |
| **4 · Levels** | stop · stop follows the pullback · stop buffer · reward ratio · round-trip fee |
| **5 · Display** | overlapping setups · RR zones · unfilled setups · market structure · stats table · order blocks + colour · fair value gaps + colour · extend zones · auto threshold · keep last N · 3 colours |
| **6 · Debug** | debug marks · show rejected pins |

**What went, and why:** the backup fill's eight (measured twice, worthless —
and two of the eight were never wired up at all), `endSweep` / `endStale` /
`staleBars` / `adxMin` (all shipped off, never measured on), `pbMinAge` /
`pbMinDepth` (measured; the setups they remove are not worse), and
`workTest` / `failTest` (three unmeasured variants each of something §4 defines
as *a close beyond*), and `swingK` / `swingKMinor` / `swingHours` — the first
two being the training winner of a sweep that failed its own holdout, which is
the strongest case on the list for not offering a dial.

**All nineteen are still in the port**, where the studies that name them keep
reproducing their pages. That is the standing arrangement for an option nobody
has measured: the port can express it, the chart does not offer it.

Compact tooltips. One sentence each, saying what the setting *does to the
count*, because on a detector that is the only thing any of them decides.

---

## 10. Explicitly out of v1

| | why |
|---|---|
| OB / FVG backup fill | real work with its own rules — and in the worked example it *is* the entry, so it deserves its own build rather than riding along while detection is still being fixed |
| Lower-TF stop refinement | depends on the OB logic above |
| Liquidity-based targets | needs the liquidity model; 1:3 stands in |
| Alerts and the multi-symbol port | one module in `riptide/watchers/` once detection is trusted |
| Any claim from the won/lost count | it exists so the detection can be sanity-checked, not to choose settings — see below |

A backup fill **below** the Focus line degrades the trade — entry ~77,300
instead of 77,380 against the same stop takes risk from 257 to ~337, about 30%
worse R for the same target. When v2 draws it, it draws the **real** R at the
backup fill, not the planned one.

---

## 11. Open

- **Confirm and fill windows** default to 20 bars each; both are guesses and
  the chart will correct them.
- **`wickEdge` = 0.05** is a guess for the doji margin, same.
- **`locTol`**, the location tolerance, is 0 — the pin must BE the pullback
  extreme, which rejects roughly 6 in 10 colour-correct pins. Raising it is the
  loosest single change available here.
- Whether `retraceMax` 70 is the right depth, and whether ADX earns its place
  at all.
- **Whether the bias gate should cancel a setup that has already triggered** —
  the ghost column above exists to answer it, and the answer is not in yet.
  Note that it is two separate questions: whether the gate should stop *new*
  pins (nobody disputes that) and whether it should cancel a limit order that
  is already resting (nothing supports that, and the anti-correlation argument
  above is against it).
- **`msLen` = 15** is the default and the first charts were run at 3, which
  makes the major structure twitchy enough to change what "the trend" means.
  Any comparison across symbols or settings has to hold it fixed.
- **Results across venues are not comparable as they stand.** XAUUSD on a
  broker CFD feed and XAUUSDT.P on a crypto perp are the same metal on
  different session boundaries, different bar alignments, different history
  depth and different wick microstructure — and every gate in section 2 is a
  wick-shape test. They produced +15R and −12R. That gap is a statement about
  the feeds and the sample size, not about the strategy.


---

# 8. v2 — THE RULE CORRECTIONS

**Added after twelve studies had been run.** The strategy's author read the
spec back against the intent and found that **§4 describes a different event
from the one the strategy is about.** Everything in `measurements/` was
produced under §4 as written. None of it is withdrawn — it is all correctly
measured — but it measured **v1**, and v1 is not the rule below.

Bearish is written out in full. **Bullish mirrors, and only mirrors** — every
"green" becomes red, every high becomes a low, every "above" becomes below.

## 8.1 The bias is CHoCH and BOS, and nothing else

The five Ending rules go. Direction comes from the most recent major **CHoCH**;
a **BOS** in that direction makes it a trend worth trading. No minor structure,
no sweep rule, no stale rule, no retrace cap, no ADX.

This is already expressible: `endMinor = off`, `endSweep = false`,
`endStale = false`, `retraceMax = 0`, `adxMin = 0`.

**And the pullback is looked for AFTER the BOS.** A fresh CHoCH with no break
of structure behind it is not yet a trend to fade a pullback in — `needBos`.

## 8.2 The counter-trend candle, newest wins ACROSS families

In a bearish trend the candle working against it is **green**. Two shapes
qualify and **the most recent one is the one in play**:

* hammer, then an inverted hammer appears → use the **inverted hammer**
* inverted hammer, then a hammer appears → use the **hammer**

v1 ran every qualifying pin as its own independent candidate and let them all
live at once. `pinNewest` makes the newest supersede the un-armed ones before
it. A candidate that has already confirmed has an order behind it and is not
superseded — it is a live setup, not a second opinion.

The lines are unchanged and are worth restating because they are what the
ordering rule below acts on:

| shape | Working | Failure | Focus |
|---|---|---|---|
| hammer | **high** | low | open |
| inverted hammer | **low** | high | open |

## 8.3 THE ORDERING RULE, and this is the correction that matters

§4 says both confirmations are required **in either order**. That is wrong.

> **A WORKING break must come first, and a FAILURE break after it.**
> The limit goes at the Focus line on that failure.

| sequence | v1 | **v2** |
|---|---|---|
| W → F | arms | **arms** |
| F → W → F | arms on the W | **arms on the second F** |
| F → W | arms on the W | **does not arm** — waits for an F |
| F only | no | no |
| W only | no | no |

**Why it is a rule and not a detail.** The pin is a counter-trend candle. W is
that candle appearing to *work* as a reversal; F is the reversal *failing*.
The setup is the failure of a counter-trend attempt — so the attempt has to
happen first. "Either order" admits bars where the reversal never worked at
all, which is a different event that happens to touch the same two lines.

**A bar that spans both lines does not arm.** Intrabar order is unknowable, and
this repository already resolves that ambiguity against the trade everywhere
else — a bar spanning entry and stop counts as the loss. A later F arms it,
which is exactly what makes `F → W → F` work.

`confirmOrder = "working then failure"`.

## 8.4 What this does to everything already measured

**Every page in `measurements/` measured v1.** Twelve studies, all null. That
is now two claims, not one:

1. v1 has no edge — measured, repeatedly, on five symbol universes.
2. **v1 is not the strategy.** Whether v2 has an edge is untested.

**MEASURED — see [`UNDERTOW_V2.md`](measurements/UNDERTOW_V2.md), and v2 is
null too.** Negative on 3 of 3 timeframes, beaten by its own random-entry
control on 2 of 3, and worse than v1 on 15m and 30m. Every win rate in that
study sits between 20.3% and 23.5% against a 22.2% break-even.

So the two claims in §8.4 resolve like this: v1 has no edge, **and neither does
v2**. The correction was real — v1 detected a different event — and correcting
it did not produce one.

**W→F ships anyway, in the chart, the port and the watch**, because it is a
correction and not a promotion. The remaining v2 components did not earn their
defaults and are off.

**v3 — the anchor — is measured too, and it is the fourteenth null**
([`UNDERTOW_V3.md`](measurements/UNDERTOW_V3.md)). It is the first arm here to
be positive on 3 of 3 and above its control on 3 of 3, and it cleared neither
bar, because every margin is a third of a standard error.

That page also corrects a number quoted throughout this directory:
**22.2% is the break-even win rate BEFORE fees.** The fee is charged in price
and the trade is scored in R, so the drag is `fee / risk` and the line moves
with the timeframe — 23.5% / 23.2% / 22.9% on 15m / 30m / 1h. v1's own win rate
on an unseen universe is 23.6% / 23.6% / 22.9%. **The shipped rule sits on its
fee-inclusive break-even to a tenth of a point on all three**, which is a
sharper statement of fourteen nulls than the old line ever was.

**The three switches all default to v1**, so every page keeps reproducing and
`test_studies_pin_their_settings.py` holds them to it. v2 is measured on its
own, on a universe nothing has seen, before anything moves — and if it is
promoted, every page produced under v1 is superseded rather than quietly
reinterpreted.

**v2 is not on the chart yet, on purpose.** Putting an unmeasured rule in the
inputs is the habit that gave group 1 twenty inputs for four settings the
measurements warned against. Port first, measure, then the Pine.
