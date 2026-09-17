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

Ported from section 12 of `indicators/riptide_ms/pine/riptide-indicator-v2.pine`,
which already emits CHoCH from long swings, BOS from the running extreme, and
IDM/CHoCH from short swings.

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

1. a **minor CHoCH against `D`** while the major is still `D`
2. a **sweep** of the running extreme that closes back inside
3. **no new extreme in `D` for `staleBars`** bars

Every one is decidable at a bar close and none of them repaint. They will
sometimes call Ending while the trend keeps running — that is the right
direction to be wrong in, because a false Ending costs a skipped setup and a
missed one costs a loss.

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
| **Stop** | dropdown: pin's own high/low · **pullback extreme** (default) · minor swing extreme |
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
candidate  ->  armed  ->  filled
     \           \           \
      dropped     expired     (v1 stops here — no outcome is scored)
```

- **One live setup per pullback, newest pin wins.** Input flips it to "first
  wins".

  **This is the biggest single effect in the funnel and it is not a rejection.**
  On a real chart it took 270 candidates down to 14 armed. A pullback that keeps
  extending replaces its own candidate every time, and worse: in a long bias the
  bar that closes below the pin's low — one of the two confirmations — is itself
  a new pullback low, so if it is also a valid pin it destroys the candidate it
  was confirming. A candidate survives mainly when the confirming bar happens
  *not* to be a pin, which is a strange thing to be selecting on. The panel
  counts supersessions on their own row rather than hiding them inside
  `candidates`. Whether "first wins" is the better rule is now an open
  question with evidence behind it.
- A setup is dropped when: the bias turns Ending · the confirm window runs out ·
  the fill window runs out · the stop is taken before the fill.
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
| **Entry** | triangle, `size.small`, `location.abovebar` / `belowbar` so it never sits on the candle. **Down = short, up = long** — direction carries the meaning, so it reads without colour |
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

This is a **status panel, not a stats table**. It says what the indicator is
currently seeing. It does not score outcomes, because v1 does not have any.

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

## 9. Inputs — grouped, ~25 total

| group | inputs |
|---|---|
| **Bias** | HTF on/off · HTF timeframe · major swing len · minor swing len · ending: minor CHoCH / sweep / stale · stale bars |
| **Candle** | wick edge · hammer family on/off · star family on/off |
| **Setup** | Working test · Failure test · confirm bars · fill bars · one per pullback |
| **Levels** | stop source · reward ratio |
| **Display** | zones on/off · keep N · 4 colours |
| **Debug** | debug on/off · show rejects |

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
| Any outcome scoring | v1 has no win rate, no R total, no stats table |

A backup fill **below** the Focus line degrades the trade — entry ~77,300
instead of 77,380 against the same stop takes risk from 257 to ~337, about 30%
worse R for the same target. When v2 draws it, it draws the **real** R at the
backup fill, not the planned one.

---

## 11. Open

- **Confirm and fill windows** default to 20 bars each; both are guesses and
  the chart will correct them.
- **`wickEdge` = 0.05** is a guess for the doji margin, same.
- Whether a **near-miss on location** (pin one or two bars off the pullback
  extreme) should count. Currently: no — and it rejects roughly 6 in 10 of the
  colour-correct pins, so it is the strictest gate before supersession.
- **Newest wins vs first wins**, given the supersession effect above.
