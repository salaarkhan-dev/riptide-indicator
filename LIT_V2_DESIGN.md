# Riptide LIT — Variant 2 Design

Design document. **No code yet.** `riptide-lit.pine` (v1) is untouched and stays
the working build until V2 is measured against it.

Sources: `LIT_SOURCE.md` (13 chapters of the reference author's own material),
`Riptide_LIT_Claude_Code_Master_Prompt.md`, and `LIT_CHANGELOG.md` (every
measurement taken so far, including the ones that failed).

---

## 1. What is settled. Do not re-open any of this.

Confirmed by source AND already correct in v1. V2 carries these across
unchanged, and no experiment is owed on them:

| Rule | Source |
|---|---|
| Persistent mother range; inside = `h < mHi and l > mLo`; exit on `h > mHi or l < mLo`, geometric | Ch.1 |
| Inside bars carry zero weight in parent structure and are excluded from pivot detection | Ch.1, Ch.2 |
| Pivots come from pullbacks and from nothing else. No numerical pivot input, ever | Ch.2 |
| Pullback = temporary counter-trend move. Uptrend → decline, downtrend → rally | Ch.2 |
| A complex pullback is ONE pullback with ONE pivot at the extreme of the whole range | Ch.2, Ch.7 |
| Two-level tracker: both levels move together on continuation; correction opens when the opposite level breaks; confirmation level FROZEN at that candle | Ch.4 |
| Pullback range = confirmation-level fix → confirmation-level break. Pivot = the correction-side extreme inside it | Ch.4, Ch.7 |
| IDM migrates to each new pullback; one active IDM per depth | Ch.3 |
| Leg anchor: BOS = the extreme from the START OF THE MOVE to the IDM break, NOT from the latest IDM | Ch.3 |
| BOS break → new CHoCH from the lowest/highest point of that BOS leg | Ch.3 |
| Boundary lock: BOS + CHoCH both active → stop publishing IDM, wait | Ch.3 |
| CHoCH break → old BOS RETYPED as the new CHoCH, same price | Ch.3, Ch.8 |
| Latent pullback reused after a continuation | Ch.3 |
| Three break modes; Body & Sweep migrates the threshold and judges the migrated one | Ch.4 |
| Hidden Shadow: synthetic candle open=candidate.open, high/low=span, close=resolver.close; ONLY the close decides; inside bars skipped, tested against the CANDIDATE's range | Ch.5, Ch.9 |
| Internal pullbacks NEST INSIDE external pullbacks — the child degree is owned by a parent pullback | Ch.12, Ch.13 |
| Order flow IS the external pullback sequence. Nothing to orient | Ch.6, Ch.12 |
| Defaults: mPB/mIDM Shadow, mBOS/mCH Body & Sweep; hsPB/hsIDM off, hsBOS/hsCH on | Ch.11 |
| "Liquidity grab" / "near" = price TOUCHES a level but does not break it | Ch.4, Ch.10 |
| Near target = the LAST opposite pullback | Ch.10 |
| The statistics table is NOT viewport-cohorted | Ch.11, Ch.13 |

---

## 2. What is actually wrong with v1

Not the rules. **The undefined cases.**

Every place the source is silent, v1 resolved it implicitly — by statement
order, by an `if/else` arm winning, by a default nobody chose. Those decisions
are real and they change the output, but they are invisible in the code and were
never measured. That is why three rounds of calibration argued in circles.

Two concrete examples found while writing this:

**A. The outside group.** In `detStep`'s impulse phase, `started` is tested
before `cont`. A group that makes a new impulse extreme AND gives back the
opposite side therefore opens a correction. Nothing chose that; `started`
is simply written first. The source never covers a group breaking both sides.

**B. Re-seed after confirmation.** `d.trkHi := h; d.trkLo := l` puts the
trackers on the confirming group. That group is by construction a strong
impulse group, so its low sits high, so the next mild dip opens a new
correction. Defensible — it is the literal continuation of the source's
candle-by-candle walk — but it was never stated as a choice.

**V2's central design decision: every such case becomes a named POLICY with an
explicit default and a switch, so it can be measured instead of argued.**

---

## 3. Policy register

Each policy: the undefined question, the options, the V2 default, and why.
Defaults reproduce v1 where v1 is defensible, so **Variant 2 at default
settings must be bit-identical to v1's engine.** That is the acceptance test
for the port before any policy is moved.

### P1 — Outside group during IMPULSE
Group breaks BOTH tracker levels.
- `correction` — opposite side wins, correction opens *(v1 behaviour)*
- `impulse` — impulse side wins, trackers extend
- **`close` (DEFAULT)** — the group's close direction decides: closes with the
  impulse → extend; closes against → correction opens.

Why `close`: master prompt §12 is the only guidance anywhere for a both-sides
break — *"allow the close direction to guide the next mother-range
orientation"* — and it is the only option that uses information OHLC actually
contains rather than an arbitrary precedence.

### P2 — Outside group during CORRECTION
Group breaks the confirmation level AND makes a new correction extreme.
- **`confirm` (DEFAULT, = v1)** — the break resolves the correction; the new
  extreme still counts toward the range first, so the pivot is correct.
- `extend` — a new extreme keeps the correction alive.

Why: Ch.4 says the correction ends when the level is broken, full stop. Order
matters though — range update MUST precede the break test, or the pivot is lost.
v1 gets this right.

### P3 — Tracker re-seed after confirmation
- **`resolver` (DEFAULT, = v1)** — trackers take the confirming group's h/l.
- `next` — trackers take the following group.
- `pivot` — impulse-side tracker from the resolver, opposite tracker held at the
  pivot.

Why `resolver`: it is the literal continuation of Ch.4's candle-by-candle walk.
`pivot` is the interesting arm for the density question and is the first one to
measure.

### P4 — Equality
A group's extreme exactly equals a level.
- **`not-broken` (DEFAULT, = v1)** — §11. Equality therefore resolves as
  *inside* for the normalizer.
- `broken`

Unresolved by source (Ch.1 [GAP]). Kept switchable because it is cheap and round
numbers make it non-rare on crypto.

### P5 — Near re-arm
- `once-per-level` — one race per level instance, ever
- **`rising-edge` (DEFAULT, = v1)** — one race in flight; a NEW touch after the
  previous race resolved arms again
- `every-touch` — every touch bar arms

Ch.10 says *"the percentage of cases in which price approaches or touches"* —
cases, plural, per level. `rising-edge` is the reading that makes a still-live
boundary able to produce a later independent race.

### P6 — Near race abandoned by the other boundary
BOS breaks while a CHoCH-near race is live.
- **`discard` (DEFAULT, = v1)** — the race leaves the sample entirely
- `count-as-reach` — price demonstrably travelled to the far side

Measured in v0.7.17 reasoning: `count-as-reach` overshoots the reference totals.
Default stays `discard`; switch retained because the reference's reach rates
(69–81%) are still far above ours and this is one of the few remaining levers.

### P7 — Child scope ownership
- **`parent-pullback` (DEFAULT, = v1 v0.7)** — Ch.12/Ch.13, confirmed
- `boundary-lock` — the Ch.3 [GAP] reading

Default is source-confirmed. The switch exists only because Ch.3's
internal-structure section was cut off mid-sentence.

### P8 — Opposite-direction pullback tracking
- `single` — one detector oriented to the trend *(v1)*
- **`dual` (DEFAULT)** — a latest pullback maintained in EACH direction

**This is the one confirmed engine divergence in the whole audit**, and it has
two independent witnesses: Ch.3 (*"we check whether there was already a bearish
pullback before the change of character got broken"*) and Ch.12 (the display
option is literally **"Show Latest Bullish & Bearish"** — you cannot draw both
unless you hold both).

Default flips to `dual` in V2 because the source is explicit. It must be proven
not to change the default-settings engine output before anything else is
measured — see §8.

---

## 4. Pullback algorithm — Variant 2 specification

Runs per depth on that depth's normalized (inside-bar-free) group stream.

```
STATE: IMPULSE | CORRECTION
FIELDS: dir, trkHi, trkLo, conf, confBar,
        rngHi, rngHiBar, rngLo, rngLoBar, startBar, brk
```

### IMPULSE
Classify the group against the trackers. `up = dir is bullish`.

```
extended = up ? h > trkHi : l < trkLo
gaveBack = up ? l < trkLo : h > trkHi
```

| extended | gaveBack | action |
|---|---|---|
| yes | no | EXTEND — trkHi := h, trkLo := l |
| no | yes | OPEN CORRECTION |
| yes | yes | **P1** |
| no | no | impossible post-normalizer. Assert and count it |

The last row is an invariant, not a case. If it ever fires, the normalizer is
broken — it is tracked as a counter and surfaced in Debug.

**OPEN CORRECTION** — all fixed on this group, none of it moves again:
```
startBar := i
conf     := up ? h : l          // impulse-side extreme. FROZEN. Ch.4.
rngHi    := h ; rngLo := l      // range seeded from the opening group
arm(brk, conf, up ? +1 : -1, pbMode, pbHiddenShadow)
state    := CORRECTION
```

### CORRECTION
**Order is load-bearing.** Range first, break second — otherwise the group that
confirms cannot contribute its own extreme and the pivot is silently wrong:

```
1. rngHi := max(rngHi, h)   with its bar
   rngLo := min(rngLo, l)   with its bar
2. if brkStep(brk, o, h, l, c):
       pivot    = up ? rngLo : rngHi        // Ch.4, Ch.7
       pivotBar = the bar that made it
       range    = startBar .. i
       edge     = pbEdge == initial ? conf : brk.act
       emit PULLBACK{ dir, startBar, i, pivot, pivotBar, edge, conf }
       re-seed trackers per P3
       state := IMPULSE
```

### Why this produces complex pullbacks correctly

There is no "complex pullback" rule and there must not be one. A complex
pullback is the EMERGENT SHAPE of this machine: internal oscillations that fail
to break the frozen `conf` leave the correction running, `rngLo` keeps ratcheting
down, and one pullback with one pivot at the true extreme comes out — which is
exactly Ch.7's diagram, where the internal peaks sit at or below the box's top
edge and only the confirming move clears it.

The break MODE is what sets how much internal movement survives: Shadow ends the
correction on the first wick through `conf`, Body needs a close, Body & Sweep
keeps lifting the bar. Ch.11 confirms the reference runs Shadow here, so we do
too — but this is now a stated consequence rather than a hidden default.

### Dual orientation (P8)

Two instances per depth: `detBull` and `detBear`, fed the same stream, both
always running. Consequences:

- `latestPullback[dir]` is always available — the Ch.12 display option becomes
  expressible, and the Ch.3 post-flip lookback works without waiting.
- On a CHoCH flip the new trend's IDM comes from the opposite detector's latest
  pullback if one exists, otherwise we wait. That is Ch.3 verbatim.
- **Publication stays single-direction.** Only the detector matching the current
  structural direction may publish an IDM or open a child scope. The other is
  observed, never acted on. This is what keeps P8 from re-opening the order-flow
  question that Ch.6 closed — the opposite detector has no say in direction.

---

## 5. "Near" — specification

```
NEAR EVENT
  precondition : phase == BOUNDARY_LOCK (BOS and CHoCH both active)
  arm          : price TOUCHES the boundary       Ch.4 "touches a level, but
                 (up: h >= px, down: l <= px)     does not actually break it"
                 AND no confirmed break of it on this bar
                 AND the previous race on this boundary has resolved   (P5)
  target       : the LAST pullback of the opposite direction,          Ch.10
                 snapshotted at arm time so IDM migration cannot
                 move the goalposts
  resolve      : confirmed break of the boundary        → BREAK
                 price enters the target zone           → REACH
                 the other boundary breaks              → P6
  ambiguity    : both on the same bar → excluded. OHLC cannot order them.
```

**No distance band. No percentage. No ATR.** Ch.2's determinism requirement
forbids it, and the rescored calibration scan already showed every proximity
band scoring 50+ error against raw touch's 6.

Under P8 `dual`, "the last opposite pullback" becomes literal — the opposite
detector's latest confirmed pullback — instead of v1's geometric approximation
(most recent zone lying on the far side). Those coincide only while publication
is single-direction, which is why P8 and the near definition must land together.

---

## 6. Structure layer — BOS / CHoCH / IDM at three depths

One engine, instantiated three times. **No depth has a special case.** The only
differences between depths are what feeds them and what owns them.

```
MAIN      feed: the whole normalized chart        owner: nothing
INTERNAL  feed: raw candles inside the owning     owner: a confirmed MAIN
                scope, through its OWN normalizer          pullback
DEEP      feed: same, one level down              owner: a confirmed INTERNAL
                                                          pullback
```

Per depth, per Ch.3, with labels `BOS/CHoCH/IDM`, `iBOS/iCHoCH/iIDM`,
`iiBOS/iiCHoCH/iiIDM`:

```
DISCOVER  no IDM. A confirmed pullback publishes IDM = its pivot.
TRACK     IDM active. A new confirmed pullback MIGRATES it (retire, replace).
          The leg anchor does NOT move.                          Ch.3, §34
          IDM breaks → BOS = the leg extreme from leg start to the break.
SEEK      BOS active, no opposing CHoCH. BOS breaks →
          CHoCH = the opposite extreme over that BOS leg.        Ch.3
LOCK      BOS and CHoCH both active. No IDM published.           Ch.3, §39
          Pullbacks still observed and cached (both directions, P8).
          BOS breaks   → continuation. New CHoCH from the leg. Activate the
                         cached same-direction pullback.         Ch.3, §42
          CHoCH breaks → FLIP. Old BOS retyped as the new CHoCH, same price.
                         Activate the cached OPPOSITE-direction pullback
                         if one exists, else wait.               Ch.3
```

**Invariants, asserted every bar, surfaced in Debug — not assumed:**

- I1 Only a CHoCH break flips direction.
- I2 An IDM break never flips direction.
- I5 In LOCK, no IDM is active.
- I7 IDM migration never moves the leg anchor.
- I11 Bullish → `bos.px > ch.px`; bearish → `bos.px < ch.px`.
- I-NEW A level may not be broken by the bar that created it (`createdBar`).
- I-NEW At most one major transition per bar per depth.
- I-NEW A child scope never outlives its owning parent pullback.

### Weak / Strong

Derived display only. Nothing in the engine reads them.       §47, Ch.11

```
bullish:  BOS side (continuation high) = HH | Weak High
          CHoCH side (reversal low)    = HL | Strong Low
bearish:  BOS side (continuation low)  = LL | Weak Low
          CHoCH side (reversal high)   = LH | Strong High
```

Marked at the structural extreme itself, not parked at the right edge.
Currently Main-only; V2 extends to Internal and Deep behind one switch, since
`Label Swing` is a single toggle in the reference.

---

## 7. UI, floating inducements, statistics

The user's stated priority order for V2 after the algorithm.

### 7.1 Floating inducements — solve it structurally, not with an input

v1 carries an `idmAnchor` input with "Pivot bar" / "Pullback start". Ch.8 shows
the reference anchors the IDM line at the pullback's low and extends it right to
the grab. **There is one correct answer, so V2 drops the input**: the line starts
at the pivot bar and ends at the current bar while live, frozen at the break bar
when taken. A line segment is never drawn across prices the market had not
reached.

### 7.2 A retyped level is ONE line

Ch.8: both ✗ marks sit at the same price as the dashed line running through
them, with the label changing across the mark. V2 keeps the line object alive
across a BOS→CHoCH retype, changes its label and colour, and drops a ✗ at the
retype bar — instead of v1's delete-and-recreate.

### 7.3 Retired IDMs are DELETED, not faded

**User decision, and it overrides the earlier recommendation here.** The
reference keeps a faded grey trail with migration arrows (Ch.8). V2 does not:
when an IDM migrates, the previous IDM's line and label are deleted outright.

> "only we move the idm up and after moving we will delete the previous IDM
> that we created in a float so that our chart will be cleaned"

§56 permits either ("optionally keep short historical segment"). One live IDM
per depth, nothing behind it. Retired BOS/CHoCH segments still fade into the
capped history — only IDMs are deleted, because they are the level that
migrates repeatedly and so the only one that accumulates.

### 7.4 Pullback zones

Nested rendering is the point (Ch.12, Ch.13): external boxes large and
translucent, internal smaller and more saturated inside them, deep fainter
still. Display mode gets the reference's three options — Hide / Show All /
**Show Latest Bullish & Bearish** (default), which P8 `dual` finally makes
expressible.

### 7.5 Statistics

Twelve rows, matching the reference exactly (Ch.10), not six:

```
IDM → BOS touch              IDM → Choch touch
HS IDM break                 HS IDM cancel          ("HS not active" under Shadow)
HS BOS break                 HS BOS cancel
HS Choch break               HS Choch cancel
BOS near → Opp PB reach      BOS near → BOS break
Choch near → Opp PB reach    Choch near → Choch break
```

- Cohort: **all loaded bars** by default. The reference has no window control
  and its table does not move with the viewport (Ch.11, Ch.13). Every earlier
  comparison in this log was invalid on this alone.
- Depth selector retained; the reference has none, so which depth theirs reports
  is unknown and must not be assumed.
- The near-rule calibration scan moves OUT of the shipped indicator into a
  research build. It is research scaffolding and §81 wants a clean default.

### 7.6 Default view

§58/§81, with the one known conflict noted: the master prompt says Deep off by
default, the reference profile has it ON (Ch.11). V2 follows the master prompt
and the tooltip says the reference differs, so a like-for-like visual comparison
starts by turning Deep on.

---

## 8. Build order and acceptance

Nothing merges on argument. Each step has a test that can fail.

1. **Port at parity.** V2 with every policy at its v1-equivalent default
   (including P8 `single`) must produce identical engine output to v1 on the ZEC
   fixture: same pullback count, same pivots, same IDM/BOS/CHoCH sequence.
   Any difference is a porting bug, not an improvement. *No new behaviour until
   this passes.*
2. **P8 → `dual`, publication still single-direction.** Engine output must STILL
   be identical. The opposite detector is observed only. If anything moves, the
   isolation is leaking and that is a bug.
3. **Enable the Ch.3 post-flip lookback.** First intentional behaviour change.
   Expected: IDM appears sooner after a flip. Measure IDM count, lock-episode
   count, and the twelve statistics.
4. **Sweep P1 and P3.** The two undefined cases most likely to move density.
   Report the full statistics grid per arm. Pick on the evidence, and record the
   losers — a rejected arm is a result.
5. **Re-measure against the reference** on a matched cohort (all loaded bars,
   both indicators, same symbol and timeframe, Deep on).
6. **UI pass** — §7.1 through §7.6.

### The open question, stated honestly

Our Main structure resolved 31 lock episodes where the reference resolved 20 on
the same bars. Every explanation offered so far has failed:

- complex-pullback rule → no such rule exists; it is emergent (Ch.2, Ch.7)
- pullback break mode → theirs is Shadow, same as ours (Ch.11)
- order-flow orientation → nothing to orient (Ch.6, Ch.12)
- child degree fed by inside bars → it is nesting (Ch.12, Ch.13)

What remains untested: P1, P3, P8, and the very real possibility that the gap
was substantially the viewport-cohorting artefact fixed at the end of Ch.13, in
which case there may be much less to explain than assumed.

**Step 5 gets measured before any further theory is proposed.** The last two
theories were promoted on how well they fit and both were wrong.
