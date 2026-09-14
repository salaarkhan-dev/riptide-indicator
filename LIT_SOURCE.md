# LIT — Source Transcript Extractions

Rules taken from the reference author's own training material, chapter by
chapter. The reference indicator's source code is not available; this is the
next best thing and it is the only place a rule gets to be called `[SRC]`.

Per master prompt §79, every line below is one of:

    [SRC]  stated outright in the source. Quoted.
    [INF]  our inference. The source does not settle it.
    [GAP]  the source raises it and leaves it open.

Marketing, product positioning and the four-challenges framing are skipped —
they carry no rules.

---

## Chapter 1 — Inside Bar Candles

### [SRC] Definition — strict inequality, both sides

> "An inside bar is a candle that forms completely inside the range of the
> mother candle. That means this candle's high is lower than the mother
> candle's high, and it's low is higher than the mother candle's low."

    inside = high < motherHigh AND low > motherLow

Confirms master prompt §8 verbatim, including "default to strict inequality".

### [SRC] The mother range PERSISTS — this is the whole point of the chapter

> "Look at this candle. After it, a few more candles form, and all of them stay
> inside its range until eventually a candle comes in and breaks out of that
> range. So, within that range, all of those internal candles count as inside
> bar candles and have no analytical value."

The author then names the common error explicitly:

> "One mistake people make is only comparing each candle to the one right
> before it. So, here, they say only these two candles are inside bar candles
> ... But that way of looking at it is just wrong. Once a candle forms until
> its high or low gets broken, every candle that stays within its range is an
> inside bar candle and has no analytical value."

Confirms §9. A mother candle owns every following candle until its own high or
low is broken — NOT a previous-bar comparison.

### [SRC] Exit is geometric, not a structural break mode

> "until its high or low gets broken"

High OR low. Nothing about bodies, closes or sweeps. Confirms §10, including
its warning not to apply Body / Body & Sweep to inside-bar classification.

### [SRC] Inside bars carry zero weight in parent structure

> "These candles have no real value in market structure analysis. Let me be
> clear about that. They have no value at all."

Confirms §8's list: an inside bar may not start a parent pullback, confirm one,
migrate a parent level, create a parent pivot, or break IDM/BOS/CHoCH.

### [SRC] Colouring inside bars is a real reference feature

> "Even in the indicator settings, there's a change the color of the inside bar
> candles option, so you can make them easier to spot on the chart."

Confirms §61 and supports the v0.7.16 default flip to ON.

### [GAP] Exact equality is still unresolved

The source defines INSIDE with strict inequality ("lower than", "higher than")
and defines the EXIT with strict language ("gets broken"). A candle whose high
exactly equals the mother high is therefore neither inside nor breaking. The
transcript does not close this.

Our resolution stands as [INF], not [SRC]: §11 says "treat exact equality as
not broken", so by elimination equality resolves as inside. That is what
`normStep` does — `inside = not (rh > n.hi) and not (rl < n.lo)`.

Worth knowing this is an inference and not a confirmed rule, because it is
ours to revisit if a later chapter contradicts it. On round-number crypto
levels exact equality is not as rare as it sounds.

### [GAP] Outside bars — the source does not mention them

Nothing in this chapter about a candle that breaks BOTH sides of the mother
range in one move. §12's OUTSIDE_BOTH handling remains entirely [INF].

### [GAP] "They only form fractal and internal structures."

The one sentence in this chapter that may matter beyond inside-bar detection.
It says inside bars are the raw material of INTERNAL structure — they are
worthless to the parent, but they are what the child degree is made of.

Our Internal and Deep contexts currently normalize RAW candles inside a parent
pullback scope, which includes candles that were never inside bars for Main.
If the source means internal structure is built specifically from the parent's
discarded inside bars, that is a different feed and a real architectural
difference.

Do NOT act on one sentence. Flagged to be re-tested when the pullback /
order-flow and market-structure chapters arrive, which is where the child
degree actually gets defined.

---

## Audit of our implementation against Chapter 1

`normStep` in riptide-lit.pine:

    bool over  = rh > n.hi
    bool under = rl < n.lo
    if not over and not under
        insideNow := true          // stays in the mother range
    else
        ...emit the closed group, then seed the new mother from THIS candle

Conforms on every confirmed point: persistent mother range, geometric exit on
high or low, inside bars excluded from parent structure, raw OHLC retained.
The only divergence from the source's literal wording is at exact equality,
covered above.

**Nothing in this chapter changes the code.** It also does not touch the open
problem — our Main structure resolves 31 lock episodes where the reference
resolves 20 on the same bars. Inside-bar handling is upstream of that and is
now confirmed correct, which usefully narrows where the 1.55x can come from:
not the normalizer.

---

## Chapter 2 — Pivot Points and Pullbacks

### [SRC] Fixed-N pivot detection is rejected outright, and by name

The chapter spends most of its length demolishing two methods: "N candles
higher/lower on each side", and the refinement that adds a required bullish /
bearish sequence on either side.

> "But both of these views are flawed from the start and are completely wrong.
> Why? Because when we use a fixed number to identify a pivot point like 1 2 3
> 5 or 10 candles before and after, we're introducing a completely arbitrary
> criterion into the analysis. And the result is that different traders end up
> seeing different market structures."

> "Almost all the indicators out there right now identify pivot points exactly
> like this. And that's wrong."

Confirms master prompt §3's NEVER list — `ta.pivothigh` / `ta.pivotlow` and any
user-supplied pivot length. We comply: zero occurrences in the file, and there
is no pivot-length input.

### [SRC] Determinism is the stated design goal

> "In reality, there's only one true market structure in each time frame. And
> when we're looking at one time frame, everyone shouldn't be seeing their own
> version of market structure."

This is the reason there are no tuning knobs on the engine, and it is why every
calibration round in this log has refused to add one.

### [SRC] THE CENTRAL RULE — pivots are defined BY pullbacks, and only by them

> "To identify pivot points correctly, we have to use the concept of pullback.
> The only correct way to identify pivot points is by using pullbacks. There is
> no other way. Pivot points form exactly at the highs and lows of pullbacks."

Confirms §16 and our architecture: the pivot is the extreme of the correction,
emitted by the pullback detector. Nothing else in the engine may create one.

### [SRC] Inside bars are excluded from pivot detection

> "Also, inside bar candles which belong to internal structures are not taken
> into account in this process."

And, as the stated failure mode of the fixed-N methods:

> "because these models are just counting candles, inside bar candles end up
> getting counted too, and that causes the market's internal structures to get
> pulled into the analysis, too. As a result, the internal structure and the
> main market structure get mixed together in the same time frame."

Confirms the normalizer sitting upstream of the detector, which is what we do.

Note this is the SECOND time inside bars are bound to internal structure by
name ("inside bar candles WHICH BELONG TO internal structures"). The Chapter 1
[GAP] on that point is now stronger, not weaker.

### [SRC] Pullback definition

> "A pullback is a temporary move against the trend or a temporary price
> correction during a trend. ... In an uptrend, a pullback is a temporary drop
> in price. And in a downtrend, it's a temporary move up in price."

Confirms §13 / §17.

### [SRC] COMPLEX PULLBACKS — new, and the most important thing in this chapter

> "Then we have another pullback. This one is a complex pullback, meaning
> sometimes a pullback has smaller moves or pauses inside it. So, it's no
> longer a simple pullback. We call those complex pullbacks."

The counting in both worked examples is the part that matters:

> uptrend:   "So overall in this uptrend we had three pullbacks. Two were
>             simple and one was complex."
> downtrend: "So, in this trend, we had three pullbacks. Two were simple and
>             one was complex."

A complex pullback counts as **ONE** pullback and yields **ONE** pivot, at the
extreme of the whole thing — not one per internal sub-move. The master prompt
never uses the word "complex" and never states this.

### [GAP] The noise filter is deferred, and the chapter says so explicitly

> "Now, in a market that's highly volatile and full of small moves. How do we
> identify pullbacks the right way? Because if we're not careful, we might
> mistake internal market noise for pullbacks, too. How do we filter out that
> noise and find the real pullbacks? We'll get to that in a bit."

This is the mechanism. It is not in this chapter. Do not invent it.

---

## What Chapter 2 means for the 31-vs-20 problem

LEADING HYPOTHESIS, NOT A CONCLUSION.

Our Main structure resolves 31 lock episodes in the fixture window where the
reference resolves 20 — about 1.55x. Lock episodes are downstream of IDMs,
IDMs are downstream of confirmed pullbacks, and this chapter says a correction
containing smaller moves is ONE pullback with ONE pivot.

If our detector confirms and re-seeds on an internal sub-move of a complex
correction, we would emit two or more pullbacks where the reference emits one,
and the inflation would propagate exactly as observed. The source's own worked
example — 3 pullbacks where a naive reading counts 4 — is 1.33x, the same order
as our 1.55x.

ARGUING THE OTHER WAY, HONESTLY. Our detector freezes its confirmation level at
the correction-START candle and only confirms on a valid break back through
that level. Sub-moves genuinely contained inside the correction cannot reach
it, so simple containment is already handled. The hypothesis only bites if the
reference treats a correction as still running after price HAS come back
through the start level — which is precisely the "filter out the noise"
mechanism the chapter defers.

So this chapter narrows the problem and does not close it. What it does settle:
the normalizer is right (Chapter 1) and the pivot-from-pullback architecture is
right (this chapter). Whatever produces the 1.55x is inside the pullback
lifecycle, between correction start and correction confirmation. That is a much
smaller place to look than it was two chapters ago.

NOTHING CHANGED IN THE CODE. The deferred noise filter decides it, and
inventing it now is the exact failure mode §3 and this chapter both warn about.

---

## Chapter 3 — Formation of Market Structure (LIT)

### [SRC] The LIT reframing of SMC

An SMC "change of character" is, in LIT, a liquidity grab:

> "In LIIT, when that low gets broken, it's seen as a liquidity grab, meaning
> the market just takes the liquidity below that low and nothing more. So, this
> move isn't a real change of character at all. ... And from here on, we call it
> inducement or IDM for short. So, in this model, the breaks we used to call BOS
> aren't really valid BOS's at all. ... And all those moves we used to treat as
> BOS were actually just pullbacks."

### [SRC] IDM migration

> "Once a pullback forms, we draw the IDM level from the low of that pullback,
> which is the pivot low. Now, two things can happen. Either price comes down
> and breaks the IDM level or price keeps moving higher and a new pullback
> forms. ... In that case, we move the IDM level to the low of the new pullback."

Confirms §33. One active IDM, retired and replaced by each new pullback.

### [SRC] The leg anchor — confirmed word for word

> "Once the IDM gets broken, we take the highest point from the start of the
> move up to the moment of that break as the BOS level."

"From the start of the move", not from the latest IDM. Confirms §34 exactly,
and confirms our legHi/legLo, which IDM migration never resets.

### [SRC] BOS break sets the new CHoCH from the BOS leg

> "Once the BOS level gets broken, we take the lowest point from the start of
> that BOS up to the moment it breaks as a valid low. And from there, we draw
> the change of character level."

### [SRC] Boundary lock

> "Now, we have a BOS level and a change of character level. So, we stop looking
> for a new pullback or drawing a new IDM and wait to see which one price
> breaks."

Confirms §39 / §40 and our PH_LOCK.

### [SRC] Latent pullback after a CONTINUATION — confirmed

> "The trend is still bullish and from here we start identifying pullbacks
> again. ... But here before the BOS gets broken, we already had a pullback. So
> before a new pullback forms, we use this pullback and draw the IDM level from
> its low."

Confirms §42, and we implement it: the BOS-break branch activates the cached
latent pullback.

### [SRC] CHoCH break retypes the old BOS

> "the previous bullish BOS level becomes our bullish change of character level
> because that's still our valid high."

Confirms §41. We do this.

### [SRC] !! LATENT PULLBACK AFTER A FLIP — AND WE DO NOT DO THIS !!

> "From here on, we don't draw the IDM level from the lows of bullish pullbacks
> anymore. and we have to draw it from the highs of bearish pullbacks. **First,
> we check whether there was already a bearish pullback before the change of
> character got broken.** If there was, we draw the IDM level from the high of
> that same pullback. If there wasn't, we have to wait for a new bearish
> pullback to form here."

And again after the bearish BOS break:

> "let's see whether there was a bearish pullback before the BOS got broken.
> Here before the BOS got broken, we didn't have a bearish pullback. So we wait
> for a bearish pullback to form."

Read it carefully. While the structure is BULLISH and locked, the engine is
already observing BEARISH pullbacks — otherwise there would be nothing to look
back at the moment the CHoCH breaks. Both orientations are live during the lock.

OUR CODE DOES NOT. `x.det` is oriented to the current trend, so during a bullish
lock we track bullish corrections only. The CHoCH-break branch then does
`x.latPx := na` and reorients the detector, so the flip starts from nothing and
must wait for a fresh bearish pullback.

THIS IS ALSO THE ANSWER TO A QUESTION THAT HAS BEEN OPEN SINCE v0.3.6. The
"what orients Main order flow" experiment tested two readings and rejected both:
OF-A (flow carries the structural direction) and OF-B (an opposite confirmation
RE-ORIENTS the flow). The source describes a third that was never tested — the
opposite-direction pullback is merely OBSERVED so it is ready, and the flow
direction is still set by the structural break, never by the pullback. Neither
rejected arm is this.

Not implemented in this pass. It is a real engine change and it needs measuring.

### [SRC] Internal structure replaces multi-timeframe analysis

> "When you analyze the market on a time frame like the five-minute chart ...
> looking at that same structure on the one five-minute chart basically means
> you're combining three five-minute candles together. ... So whether you
> combine three candles, six candles, or any other number, you're still using an
> arbitrary number. Instead of using multi-time frame analysis, it makes much
> more sense to stay on the same main time frame where the structure is forming
> and use the internal structure inside that same time frame."

### [GAP] Internal structure looks like it is owned by the BOUNDARY LOCK

The internal-structure section opens on the lock, and then the transcript ends:

> "Sometimes in the market, price gets trapped between a valid high and a valid
> low. In other words, when we have both a BOS level and a change of character
> level at the same time ... we stop looking for a new pullback or an IDM break.
> In this situation, price is just moving between those two levels."

Our Internal context is owned by a parent PULLBACK scope (v0.7 hierarchy), not
by the boundary lock. If internal structure exists specifically to read the
lock, that is a different ownership model. The chapter is cut off exactly here,
so this is unresolved — flagged, not acted on. Third consecutive chapter
pointing at how the child degree is fed.

---

## Chapter 4 — Level Breakouts

### [SRC] Three break types, per level, user-selectable

> "In the indicator settings, you can choose the breakout type for pullback,
> IDM, BOS, and change of character."

Confirms §59 and our four inputs. Also confirms the recommended defaults:

> "Of course, the shadow option is used less often for BOS breaks, and usually
> body or body and sweep level is used instead. A change of character break
> works exactly the same way as a BOS break."

### [SRC] Shadow is intrabar

> "In this case, as soon as price moves past the level, the breakout counts as
> valid and there's no need to wait for the candle to close."

We evaluate on closed bars (`cfgConfirm` default on). Same LEVEL, same bar's
high/low, so historically identical; the difference is one bar of live latency
in exchange for not repainting. Noted, not a defect — §4 requires it.

### [SRC] Body & Sweep — the sweep target is the poking candle's extreme

> "we don't keep extending that same level. We sweep it instead, meaning we move
> the level up to the high of the new candle. And now, this new level has to be
> broken with the body. **And even if the previous level gets broken with the
> body, it still doesn't count.**"

Confirms §21 and our Brk.base / Brk.act split, including that `act` and not
`base` is what judges once a sweep has happened.

### [SRC] !! THE TWO-LEVEL PULLBACK TRACKER, STATED OUTRIGHT !!

> "The first candle comes in. It has a high and a low. We mark these two levels
> and wait for the next candle. In a bullish trend ... if the upper level gets
> broken, but the lower one doesn't, we move BOTH levels to the new candle. ...
> The next candle comes and this time breaks the lower level. That means the low
> gets taken, and that shows price is starting to pull back. From here on, we
> don't move the levels anymore."

> "So, we fix the upper level at the high of this same candle and keep going
> until this level gets broken."

This is our detector exactly: trkHi and trkLo advance together while the
impulse side breaks; the correction OPENS when the opposite side breaks; the
confirmation level is FROZEN at that same candle's high and never chases price.
§14 confirmed, and the v0.1 deviation that was struck out is confirmed struck.

### [SRC] Pullback range and pivot

> "From the moment that level gets fixed, meaning the pullback starts, until the
> moment it gets broken, we treat that whole area as the pullback range. The
> lowest point inside that range is the pivot low. Pay attention here. We didn't
> count the candles before and after the pivot low, and the number of candles on
> each side might not even be the same."

Confirms §15 / §16 and our hitFrom → hit range with the pivot at the extreme.

### [SRC] The pullback-zone boundary input is a real reference setting

> "Should the upper level of the pullback be on the initial level or on the
> final level that got swept? Both ways are valid, which is why you can choose
> in the indicator settings under pullback level where the pullback level should
> be placed."

Confirms §23 and our `pbEdge` input, including both of its options by name.

### [SRC] "Liquidity grab" is defined — and it is the NEAR geometry

> "A liquidity grab means that price touches a level, but does not actually
> break it."

Touch without break. That is exactly what our Near statistic arms on, and it is
what the rescored scan ranked best (Raw level touch, error 6, against 50+ for
every proximity band). The word "near" is not used, so this stays [INF] for the
statistic — but the geometry the source cares about is a touch, not a distance
band. The percentage-band candidates can be retired.

---

## THE 31-vs-20 ANSWER IS PROBABLY AN INPUT, NOT A BUG

Chapter 2 deferred the noise filter — "How do we filter out that noise and find
the real pullbacks? We'll get to that in a bit." Chapter 4 IS that answer, and
it is not a new mechanism. Noise is filtered by two things already in the
engine: the inside-bar normalizer, and THE BREAK TYPE CHOSEN FOR PULLBACK
DETECTION.

> "But one view is that the breakout has to happen with the body, otherwise the
> pullback doesn't count as valid."

Our `mPB` defaults to Shadow, which confirms a correction on the first wick back
through the frozen level. Body, and more so Body & Sweep, confirm strictly
later and therefore strictly fewer times — fewer pullbacks, fewer IDMs, fewer
lock episodes. Our 31 against the reference's 20 is exactly the shape of a
looser pullback break mode.

NEXT TEST, and it needs no code change: set Pullback confirmation to Body, read
the IDM race Total; then Body & Sweep, read it again. If either lands near 20
the density question is closed and the near-statistic splits should move with
it. The master prompt's §59 default of Shadow would then be wrong for the
reference profile, which is a documentation fix, not an engine one.

No "complex pullback" rule needs inventing if this is the explanation — a
complex pullback is simply what a stricter break mode produces, because the
internal sub-moves fail to confirm and the correction keeps running to its true
extreme. That also matches Chapter 2's worked examples, where a complex
pullback yields ONE pivot at the overall extreme.

---

## Curriculum stated in the intro — what is still to come

> "In the market structure section, we go through these: inside bar candles,
> pivot points, or what we also call swing points, pullback and order flow,
> market structure, which can be analyzed through either SMC or LIT, how market
> structure forms with LIT, different types of level breaks"

    1. inside bar candles              ← done, Chapter 1
    2. pivot points / swing points     ← done, Chapter 2
    3. pullback AND order flow         ← done, Chapters 2 and 4
    4. market structure, SMC or LIT    ← done, Chapter 3
    5. how market structure forms with LIT   ← done, Chapter 3
    6. different types of level breaks ← done, Chapter 4

Still wanted: the internal-structure chapter, which was cut off mid-sentence,
and anything on the statistics table.

Two things worth noting in advance:

  - "pullback and order flow" is presented as a SINGLE topic. Our longest-
    standing open question is what re-orients Main order flow, and both
    permitted readings of the master prompt were measured and rejected
    (v0.3.6). If order flow is defined through the pullback rather than
    separately from it, that chapter settles it.

  - Chapter 2 is where the 31-vs-20 answer should be, because how a swing
    point is taken determines how many corrections exist at all.
