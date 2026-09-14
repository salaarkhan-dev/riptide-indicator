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

## Chapter 5 — Hidden Shadow

### [SRC] The rationale, and it is the same one as everywhere else

> "if the candle had closed just a few seconds earlier or later, or if we were
> looking at a different time frame, for example, a slightly higher one, that
> breakout that first looked like a body break might actually have been treated
> as a shadow break."

Same objection as the fixed-N pivot rejection (Chapter 2) and the
multi-timeframe rejection (Chapter 3): a result that depends on an arbitrary
boundary is not a result. Hidden Shadow exists to remove candle-boundary luck
from a body break. Consistent design philosophy across all five chapters.

### [SRC] The synthetic candle — exactly our construction

> "The open of the combined candle is the open of the first candle. The high and
> low become the highest and lowest points of those two candles. And the close
> of the combined candle is the close of the second candle."

Confirms §27. Our synthetic is open = candidate.open, high/low = span extremes,
close = resolver.close.

### [SRC] ONLY THE CLOSE DECIDES — stated twice, once by counter-example

> "Suppose the close of the second candle moves higher. The combined candle
> becomes BULLISH, but the break still happens with a shadow. So again, we have
> a hidden shadow."

> "Now suppose the close of the last candle goes above the BOS level. In that
> case, we can say a body break has happened."

The synthetic candle's DIRECTION is explicitly irrelevant. Only synthetic close
against the level decides. Confirms §28 / §29, and confirms that our `hsHi` /
`hsLo` being tracked-but-never-read is faithful rather than sloppy: the source
builds the combined high and low too, and also never uses them to decide.

### [SRC] Inside bars cannot resolve, and the test is against the FIRST candle

> "Suppose the high of the second candle came lower and that candle ended up
> inside the range of the FIRST candle. In that case, we have an inside bar
> candle and we shouldn't take it into account. That means we still can't draw
> the hidden shadow and we have to wait for the next candle."

Then three more inside bars, each skipped:

> "So basically the candles are just playing around inside an internal
> structure. Then the next candle comes in and its high moves outside the range.
> So now it's no longer an inside bar candle. Now we can combine these candles.
> The open is the open of the first candle and the close is the close of the
> last candle."

Confirms §26 and, importantly, WHICH range the containment test uses: the
candidate (breaking) candle's own range, not a running span. Our `hsMomHi` /
`hsMomLo` are set once from the candidate bar and never updated, and the skip
test is `h < b.hsMomHi and l > b.hsMomLo` — strict, matching Chapter 1.

Note the skipped bars cannot change the synthetic high/low anyway, since being
inside the candidate's range is exactly what disqualifies them.

### [SRC] One resolution attempt

The worked example resolves on the first non-inside candle and judges there.
Our `b.pend` clears on that bar and the outcome is either a confirmed break or
`b.shadow := true`. We do not re-arm and re-test. Matches.

### [SRC] Available on all four levels

> "You can turn on hidden shadow for level breaks, whether it's during pullback
> formation, an IDM break, a BOS break, or a change of character"

Confirms §60 and our four inputs.

### [GAP] What happens AFTER a rejection is not stated

The chapter ends at the rejection. It does not say whether the level survives
for a later break attempt, nor — for Body & Sweep — whether the threshold
resets to base or keeps the level it had already migrated to.

Our behaviour is [INF] and is commented as such in `brkStep`: the level stays
armed and Body & Sweep keeps its migrated `act`. §30 covers this in the master
prompt but the source does not confirm it.

### Verdict on Chapter 5

Hidden Shadow is implemented correctly on every point the source states. This
was the specific thing suspected missing at the start of the MD audit; it was
not missing then and it is now source-confirmed rather than merely
MD-conformant.

---

## Chapter 6 — The Published Indicator Description

Mostly restates the video chapters. Four things in it are new.

### [SRC] !! ORDER FLOW IS NOT A SEPARATELY ORIENTABLE STATE !!

> "Order Flow is the result of this sequence of corrections and continuation
> moves in price."

> "Index Algo tracks both: External Pullbacks, which shape the broader market
> flow; Internal Pullbacks, which can help identify more refined zones and more
> precise Block Orders"

This closes the question that has been open since v0.3.6. Order flow is the
EMERGENT RESULT of the pullback/continuation sequence — there is no separate
flow state with its own direction to orient.

The v0.3.6 experiment built MainOrderFlowState as an independent object and
tested the only two orientations the master prompt permitted:

    OF-A  flow carries the structural direction
    OF-B  an opposite-direction confirmation re-orients the flow

Both were measured and both were rejected. The finding now is that the PREMISE
was wrong, not the two arms. Nothing needs orienting because order flow is not
a thing that has an orientation of its own. The rejection stands and the
question is closed rather than still open — which is the right outcome, and it
means no further experiment is owed here.

### [SRC] Hidden Shadow candles are purple, and it is their own invention

> "Candles related to the activation of Hidden Shadow are displayed in purple on
> the indicator"

Confirms our `cHS = #9c27b0` and the `barcolor(anyHS ? cHS : ...)` tint.

> "This concept is introduced for the first time by Index Algo"

Worth knowing: Hidden Shadow is not standard LIT. No external material will
ever corroborate §24–§30 beyond this author's own description, so Chapter 5
plus this paragraph is the complete source and there is nothing further to
find.

### [SRC] Structure detection is SETTINGS-DEPENDENT, by the author's own account

> "Modify the available structure-detection settings according to the market,
> timeframe, and level of detail you want to observe. The goal is to make the
> plotted structure clear, consistent, and suitable for your preferred way of
> reading price behavior."

This is a caveat on the entire calibration exercise. The reference table we are
matching against — IDM races 20, BOS near 29, CHoCH near 14 — was produced by
whatever settings THAT chart had, and we do not know them. Chasing an exact
match to numbers generated under unknown settings is not a well-posed target.

It also reinforces the Chapter 4 conclusion. "Level of detail you want to
observe" is, mechanically, the break mode: Shadow is described here as "faster
and more aggressive", Body as "more conservative and requires stronger
confirmation". Detail level and pullback break mode are the same knob.

### [GAP] Internal pullbacks are described as serving ZONE refinement

> "Internal Pullbacks, which can help identify more refined zones and more
> precise Block Orders"

Our Internal context runs a full second structure engine with its own IDM, BOS
and CHoCH. The description frames internal pullbacks as feeding refined zones
and order blocks instead.

Do not act on this. The reference screenshots plainly draw iIDM, iChoch and
iiDM levels, so internal structure does have its own levels; and the release
notes say this build is structure-only, so the Block Order language is almost
certainly forward-looking to a later version. Recorded because it is the fourth
consecutive document to say something about how the child degree is fed, and at
some point that accumulation is worth a measurement.

### Restated, already confirmed

Inside bars (persistent mother range, previous-bar comparison named as the
common error), pivots from pullbacks only with no numerical input, pullback
definition, the IDM → BOS → CHoCH chain, the three breakout modes, Hidden
Shadow on all four levels. All consistent with Chapters 1–5 and with our
implementation.

---

## WHERE THIS LEAVES US AFTER SIX DOCUMENTS

CONFIRMED CORRECT, no change needed — the normalizer, pivot-from-pullback,
the two-level tracker with its frozen confirmation level, the pullback range
and its pivot, IDM migration, the §34 leg anchor, the boundary lock, CHoCH
retyping the old BOS, latent pullback reuse after a continuation, Body & Sweep
migrating and judging the swept level, the whole of Hidden Shadow, the
pullback-zone boundary input, the purple HS tint, and the absence of any pivot
numerical input.

CLOSED, no longer an open question — order-flow orientation. There is nothing
to orient.

ONE CONFIRMED DIVERGENCE — after a CHoCH flip the source looks back for an
opposite-direction pullback formed during the lock. We track only the trend
direction and discard on flip. Real engine change, needs measuring, not done.

ONE TEST THAT NEEDS NO CODE — pullback break mode. Ours defaults to Shadow,
the loosest of the three. The source names the break mode as the noise filter
and the author names it as the detail-level control. This is the leading
explanation for 31 lock episodes against the reference's 20.

ONE CAVEAT ON THE WHOLE CALIBRATION — the reference numbers came from unknown
settings, so an exact match is not a well-posed target. Matching the STRUCTURE
of the relationships is.

---

## Chapter 7 — The Course Diagrams

Three slides from the video. Read as GEOMETRY, with the caveat that these are
stylized teaching diagrams and not price charts, so proportions are
illustrative. Where a diagram only restates text already extracted it is not
repeated here.

### [SRC] Inside bars — the mother range is HIGH to LOW, wicks included

Left slide: one tall green mother, a dashed horizontal line at its HIGH and
another at its LOW, both extending right. One small candle entirely between
them is labelled "Inside bar Candle". The next candle's high clears the upper
dashed line and is labelled "Not Inside bar".

Right slide: same mother, then FIVE candles inside the dashed band, bracketed
together as one "Inside bar Candle" group, then a candle clearing the upper
line labelled "Not Inside bar".

Two things this pins down that the text left implicit:

  - The dashed boundaries sit at the mother's wick extremes, not its body. Our
    normalizer seeds from `h`/`l`. Correct.
  - Within the group of five, individual candles rise above and fall below each
    other freely — the 2nd dips below the 1st, the 4th is much taller than the
    3rd — and all five remain inside bars. Containment is judged against the
    MOTHER alone, never against the neighbour. Correct.

Neither slide shows a candle whose high exactly meets the dashed line, so the
equality [GAP] from Chapter 1 remains open.

### [SRC] The two stated failure modes of fixed-N pivots

Slide reads: "Identifying pivot points this way is the biggest mistake analysts
make !!!" and gives exactly two reasons:

    1 Candle or 2 Candle or 3 Candle or 4 Candle or 5 candle or 10 Candle or ...
    Considering Inside Bar Candles

An accompanying slide shows the ±1 / ±2 counting method applied to a "Pivot
Low" and a "Pivot High", each struck through with a red X, and a zigzag chart
where roughly half the marked turns carry a "?" — the point being that the
method produces candidates it cannot adjudicate.

Both reasons were already extracted from the text. Recorded because the second
one — inside bars being counted — is now stated as co-equal with the arbitrary
number, not as an aside.

### [SRC] !! COMPLEX PULLBACK GEOMETRY — one box, one pivot !!

Uptrend panel: three shaded boxes on the corrections only, never on the
impulses. Two are labelled "Pullback" and contain a single clean dip. The
middle one is labelled "Complex Pullback", is visibly WIDER, and contains
several oscillations — down, up, down, up, down. Each of the three boxes
carries exactly ONE orange "Pivot Low" dot, and in the complex box that dot is
at the lowest point of the WHOLE box, not at the first dip.

Downtrend panel mirrors it exactly: "Pullback", "Complex Pullback",
"Pullback", each with one "Pivot High" at the highest point of its box.

This confirms the Chapter 2 text visually and adds the box geometry:

  - The box spans from where the correction STARTS to where it is confirmed,
    horizontally. Our `hitFrom` → `hit` range. Correct.
  - The box's top edge (uptrend) is flat and sits at the correction-start
    level, and its bottom is the pivot. That is our `zone()` drawn from
    `hitEdge` to `hitPx`, with `pbEdge = "Initial level"`. Correct.
  - One box, one pivot. A complex pullback does NOT decompose into several
    pullbacks with several pivots.

### [INF] The diagram supports the break-mode explanation, and here is why

The decisive detail is where the internal oscillations of the complex pullback
sit relative to the box's top edge. In the slide they stay at or below it; the
stroke that leaves the box goes decisively above it.

That is the whole mechanism. Our detector freezes its confirmation level at the
correction-start candle and confirms when that level is validly broken. An
internal rally that merely WICKS through the top edge confirms the correction
immediately under Shadow mode — splitting one complex pullback into two simple
ones, each with its own pivot and therefore its own IDM. Under Body, and more
so under Body & Sweep, that same wick does not confirm, the correction survives
its internal oscillation, and it runs on to the true extreme exactly as drawn.

So "complex pullback" is not a rule that needs implementing. It is the
EMERGENT SHAPE of a correction under a strict-enough pullback break mode, and
under Shadow it cannot form at all. That is the same conclusion Chapter 4
reached from the text, now independently supported by the geometry.

This remains [INF] until the break-mode reading is actually taken on the
fixture. It is a prediction, not a result: switching Pullback confirmation from
Shadow to Body or Body & Sweep should cut the pullback count, cut the IDM race
Total from 31 toward 20, and produce visibly wider pullback boxes containing
internal oscillations — the shape in this slide.

If the boxes do NOT get wider and multi-peaked when the mode is tightened, this
explanation is wrong and the complex-pullback rule is something separate after
all.

---

## Chapter 8 — The SMC / SMC-Trap / LIT Master Diagrams

Again read as geometry from stylized slides. Confidence is noted per item,
because some of this is inferred from pixel positions rather than stated.

### The SMC slide — the strawman, no LIT rules

Classic SMC: a BOS label on every broken high, CHoCH when a low breaks the
other way. This is the model LIT replaces, per Chapter 3. Nothing to extract
beyond confirming what "all those moves we used to treat as BOS" refers to.

### [SRC] The SMC Trap slide — IDM line anchoring

Labels an early correction "Pullback", the SMC-style breaks "Invalid BOS", the
true structural high "Valid BOS", and a red dashed level "IDM / Inducement"
carrying "$ $ $" with a down arrow. Where price later returns to that level, a
circle is labelled "liquidity grab / Hunt", with a retail trader in a spider web
beside it.

The useful geometric detail: the IDM dashed line starts AT THE PULLBACK'S LOW
and extends rightward to the point where price comes back and takes it. It does
not begin at the correction's first candle.

That confirms the floating-IDM fix made earlier in this log. `idmAnchor`
defaults to "Pivot bar", which starts the line on the candle that made the
level. Correct, and now source-backed rather than inferred from a screenshot.

It also confirms the Chapter 4 definition applies here: the grab is price
touching the level, and it is drawn as a touch, not as a penetration.

### [SRC] !! THE ✗ MARKER — A LEVEL IS RETYPED IN PLACE !!

High confidence. The LIT master diagram carries two ✗ marks, and both sit at the
SAME PRICE as the dashed line running through them, with the label changing
across the mark:

    upper:   BOS ⋯⋯⋯⋯⋯ ✗ ⋯⋯⋯⋯⋯ Choch     (one line, one price)
    lower:   BOS ⋯⋯⋯⋯⋯ ✗ ⋯⋯⋯⋯⋯ Choch     (one line, one price)

The line does not stop and restart. The ✗ marks the moment the level's ROLE
changes from BOS to CHoCH while its price is unchanged, which is §41 drawn
rather than described:

> "the previous bullish BOS level becomes our bullish change of character level
> because that's still our valid high. ... Do not discard the prior valid
> external extreme. Retype its structural role."

Our engine does this correctly — `clearLvl(x.bos)` then
`setLvl(x.ch, oldBos, oldBar, oldT, ...)` carries the exact price. Our RENDERER
does not: it deletes the BOS line and label and starts a fresh CHoCH line, with
a comment explaining that keeping both would stack two lines at one price.

So the analytics match and the picture does not. The reference shows one
continuous level with a role-change marker on it; we show a retired line and a
new one at the same price. Worth changing, and cheap — but it is a rendering
change and nothing here is urgent. Recorded, not implemented.

### [SRC] IDM colour convention — bullish blue, bearish amber

High confidence. In the diagram's bullish (cyan) stretches the active IDM
labels render blue; in the bearish (red) stretches they render amber/yellow.

Our palette is already `cIDMBull = #2962ff` and `cIDMBear = #ffb300`. Match.

### [SRC] Retired IDMs stay on the chart, faded, with migration arrows

Medium-high confidence. The left bullish stretch shows a chain of GREY "IDM"
labels at successive pullback lows, each joined to the next by a curved yellow
arrow pointing up and right, ending at one BRIGHT "IDM" — the live one.

That is §33 migration drawn as a trail: grey for retired, bright for active,
arrow for the move. Our `showRetired` option instead leaves a small "x" where an
inducement was taken, and defaults OFF.

Different choice, same information. Not a defect — §56 explicitly permits
"optionally keep short historical segment, fade it". Recorded so the option is
understood as a deliberate divergence rather than an oversight.

### [SRC] Pullback boxes on every correction, coloured by side

The diagram shades a box on every correction in both directions — blue boxes in
bullish stretches, red/maroon in bearish. Matches §53 / §54 and our `zone()`.

Note the count: roughly five boxes before the first BOS in the left stretch.
Pullbacks are frequent; it is IDM PUBLICATION that is not, because each new
pullback retires the previous IDM rather than adding one.

### [SRC] Level colours track structure, not direction

BOS renders in the continuation colour and CHoCH in the reversal colour, which
swaps as the structure flips — green BOS with red CHoCH while bullish, red BOS
with green CHoCH while bearish. That is our `col = bull ? bu : be` for BOS and
the inverse for CHoCH. Match.

### Net from Chapter 8

Nothing here contradicts the engine. Two renderer items surface:

  1. A retyped level should be ONE continuous line with a role-change marker,
     not a deleted line plus a new one at the same price.
  2. Retired IDMs are shown as a faded trail with migration arrows rather than
     as a small "x".

Both are cosmetic and both are optional under §56. Neither is implemented in
this pass, and neither affects a single statistic.

---

## Chapter 9 — The Breakout and Hidden Shadow Diagrams

### [SRC] The three break types, drawn

Shadow: the level dashed across, the second candle's upper WICK crosses it,
lightning bolt at the crossing, "Breakout ok". A wick is enough.

Body: the same level, one candle's wick crosses with no break, then a later
candle's BODY crosses — "Breakout ok". The wick-only bar did not count.

Body & Sweep Level: a staircase. The original "Level", then a curved arrow
labelled "Sweep Level" lifting it to a higher line, then a second "Sweep Level"
arrow lifting it again, then a final candle whose body clears the last line —
"Breakout ok".

All three match `brkStep` exactly, including that under sweep it is the latest
migrated level and never the original that has to be cleared.

### [SRC] A swept level is marked with ✗ where it was abandoned

Each superseded level in the sweep staircase carries a small "x" sitting on it.
Same glyph the master diagram uses for a retyped BOS→CHoCH level, so ✗ is this
author's general "this level's role ended here" marker.

We have the equivalent as `markSweep`, which drops "S1", "S2" labels at each
swept wick — but it is gated behind `showDbg` and so is debug-only. Cosmetic
divergence, recorded, not changed.

### [SRC] All four levels take an independent break mode — numbered on the chart

The uptrend/downtrend slide numbers four break points ①②③④ — pullback
confirmation, IDM break, BOS break, CHoCH break — and puts the same three
checkboxes (Shadow / Body / Body & Sweep) beside every one of them, in both
trend directions.

Confirms §59 and our four separate inputs. Nothing about which is DEFAULT is
shown here, which leaves the Chapter 4 break-mode hypothesis untouched.

### [SRC] !! HIDDEN SHADOW — THE SYNTHETIC CANDLE, DRAWN TWICE, DECIDED ON CLOSE !!

Two panels, identical setup, opposite outcomes. Both draw the combined candle
separately with its High / Open / Close / Low each on its own guide line.

  LEFT — the candidate's body clears the level, the next candle pulls back.
  The combined candle renders RED. Its Open and its Close both sit BELOW the
  level; only the High is above it. Verdict: "Hidden Shadow".

  RIGHT — same candidate, but the second candle closes high. The combined
  candle renders GREEN and its Close sits ABOVE the level. Verdict: "Breakout
  With Body".

The only thing that differs between the two panels is where the combined CLOSE
lands relative to the level. This is §28/§29 and our `up ? c > b.hsLvl : c <
b.hsLvl` drawn as a controlled experiment, and it independently confirms that
the synthetic candle's colour/direction is not what decides — the left panel's
combined candle is red and the right's is green, but so is the answer in the
inside-bar panel below, where a GREEN combined candle still rejects.

### [SRC] Inside-bar skipping, drawn with four skipped bars

A tall candidate candle clears the level with its body. Four following candles
are each labelled "inside" and are skipped. A yellow arrow runs from the
candidate's high across all four to the fifth, which is tagged "NOT Insidebar
Candle" with a dot on its high — the first candle whose high escapes the
CANDIDATE's range.

The combined candle is then built across the whole span: High and Low at the
span extremes, Open from the candidate, Close from the resolver. It renders
GREEN, and its Close still sits below the level. Verdict: "Hidden Shadow".

Three things confirmed:

  - Containment is tested against the CANDIDATE candle's own range, not a
    running span and not the neighbour. Our `hsMomHi` / `hsMomLo` are set once
    from the candidate bar and never updated. Correct.
  - Any number of inside bars are skipped; the first escapee resolves.
  - A bullish combined candle whose close fails is still a rejection. Direction
    is irrelevant. Correct.

### [INF] Possible divergence — WHICH bars get the purple tint

Chapter 6 says "Candles related to the activation of Hidden Shadow are
displayed in purple". In these slides the purple tint covers more than one bar:
in the inside-bar panel the four skipped bars and the resolver are all purple,
and both panels box the whole candidate-through-resolver window.

We tint exactly ONE bar. `b.shadow` is cleared at the top of every `brkStep` and
set only on the resolver bar where the rejection fires, so `barcolor(anyHS ?
cHS : ...)` paints the rejection bar alone.

LOW CONFIDENCE — the two slides are not even consistent with each other on this
(the inside-bar panel's candidate is green, the other panel's is purple), so
the colouring may be purely illustrative. Not changed. If it is real, the fix is
to tint the whole pending window rather than the resolution bar, which is a
renderer change with no effect on any structural decision or statistic.

### Net from Chapter 9

Hidden Shadow is now confirmed by text (Chapter 5), by the author's own
description (Chapter 6), and by two controlled diagrams (here). Every stated
rule matches our implementation. The concept was the thing suspected missing
when this audit started; it is the single best-corroborated part of the engine.

Nothing in this chapter changes the code. Two cosmetic items recorded: the ✗
sweep marker being debug-only in ours, and the possible multi-bar purple tint.

---

## Chapter 10 — The Author's Own Annotated Statistics Table

The single most useful document so far: the reference table with the author's
definitions written beside it. Different chart and date from the ZEC 30m
comparison, so it is a SECOND independent reading, not the same one.

    Statistic                    Total  Count   Rate
    IDM → BOS touch                 15     12   80.0%
    IDM → Choch touch               15      3   20.0%
    HS IDM break                        HS not active
    HS IDM cancel                       HS not active
    HS BOS break                    19     16   84.2%
    HS BOS cancel                   19      3   15.8%
    HS Choch break                   5      5  100.0%
    HS Choch cancel                  5      0    0.0%
    BOS near → Opp PB reach         23     16   69.6%
    BOS near → BOS break            23      7   30.4%
    Choch near → Opp PB reach       16     13   81.3%
    Choch near → Choch break        16      3   18.8%

### [SRC] Rows 1–2

> "how often, after the IDM level was broken, the prediction was correct and
> price moved toward the BOS level, eventually reaching it"

> "the percentage of cases in which, after the IDM level was broken, price moved
> toward and reached the Choch level"

Matches our implementation: armed on the IDM break, resolved by first TOUCH of
either boundary. The accompanying slide states the thesis behind it — after the
liquidity grab at IDM, 70% continue to the Valid BOS and 30% reverse. Both
observed tables sit near that (80/20 here, 65/35 on the ZEC chart).

### [SRC] !! ROWS 3–6 ARE A STATISTIC WE DID NOT HAVE AT ALL !!

> "Rows three to six of this table show, when Hidden Shadow is enabled, the
> percentage of cases in which price returned back into the range after touching
> the level, causing HS to become inactive, as well as the percentage of cases
> in which the level was genuinely broken."

Six rows, three level pairs: for IDM, BOS and CHoCH, how many Hidden Shadow
candidates were GENUINE breaks versus CANCELLED. Our table simply omitted them.

Note the reference's own IDM rows read "HS not active" — its IDM break mode is
Shadow on those settings, and Shadow cannot produce an HS candidate. Same as our
defaults (mIDM = Shadow, hsIDM = false), so ours will read the same.

IMPLEMENTED THIS PASS. `Brk` gains `nHsArm` / `nHsBrk`, incremented inside
`brkStep` at the arm site and at the resolution site, deliberately NOT reset by
`arm()` so the tally spans every level that Brk has held. The table renders all
six rows and prints "HS not active" where the mode is Shadow or the HS switch
is off.

This is a NEW COMPARISON SURFACE, which is what makes it valuable: a second
independent measurement to check the engine against, on a part of it (Hidden
Shadow) that is otherwise only verifiable by eye.

### [SRC] !! ROWS 7–10 — "THE LAST OPPOSITE PULLBACK" !!

> "when price approaches or touches the BOS or CHOCH levels but does not break
> them, the percentage of cases in which price moves toward and reaches THE LAST
> OPPOSITE PULLBACK"

LAST. Most recent. We picked the NEAREST by price, which is a different
pullback whenever an older zone happens to sit closer to the boundary than the
newest one does.

IMPLEMENTED THIS PASS. `pickOppPb` keeps the same geometric eligibility — the
pullback must lie on the side away from the boundary approached — and now takes
the most recently published eligible entry instead of the closest.

Also note the arming language: "approaches or touches ... but does not break
them". Touch, not a distance band, and explicitly a FAILED approach. That is
what our arm does, and combined with Chapter 4's "A liquidity grab means that
price touches a level, but does not actually break it" the proximity-band
candidates in the calibration scan can be retired for good.

### HONEST NOTE ON WHAT THIS WILL AND WILL NOT FIX

The "last" change is correct because the source says so, not because it is
predicted to close the gap — and it may well move the wrong way. The NEAREST
pullback is by definition the easiest to reach, so switching to the LAST can
only make the reach target the same or harder, which pushes the reach rate DOWN.
Ours is already too low (50.0% and 33.3% against the reference's 69% and 50% on
ZEC, and 69.6% / 81.3% here).

So this is a correctness fix to a definition, and the split problem may survive
it. If the reach rate drops further after this change, that is informative
rather than a regression: it would mean the gap is not in which pullback is
chosen, and the remaining suspects are the arm rule's one-race-in-flight guard
and the pullback break mode from Chapter 4.

Both readings of the reference agree the reach side should dominate — 69.6% and
81.3% here, 69.0% and 50.0% on ZEC. Ours never exceeds 50%. Whatever is wrong
is systematic, not sampling.

---

## Chapter 11 — The Reference Indicator's Actual Settings Panel

### [SRC] The settings, verbatim

    [Market Structure Model]
      Show Structure ....................... on     Model: LIT
      Show Internal Structure .............. ON
      Show Deep Internal Structure ......... ON
      Show Premium / Equilibrium / Discount  off
      Label Swing .......................... ON
      Show Guidance ........................ off
      Show LIT Statistics Table ............ ON

    [Breakout Rules]
      Breakout type for Pullbacks Detection  Shadow
      Breakout type for IDM Level .......... Shadow
      Breakout type for BOS Level .......... Body & Sweep Level
      Breakout type for Choch Level ........ Body & Sweep Level
      Active Hidden Shadow for Pullbacks ... DISABLED (greyed out)
      Active Hidden Shadow for IDM ......... DISABLED (greyed out)
      Active Hidden Shadow for BOS ......... ON
      Active Hidden Shadow for Choch ....... ON

Tooltips captured:

> "LIT Pullback detection rule. Shadow confirms by wick; Body confirms by
> close; Body & Sweep Level keeps the sweep route."

> "Hidden Shadow for LIT Pullback detection ... Shadow mode is already
> wick-based, so Hidden Shadow is inactive there."

> "Enables the deepest tracked structure. It is available only when Internal
> Structure is enabled."

### !! THE BREAK-MODE HYPOTHESIS IS DEAD. I WAS WRONG. !!

Chapters 4 and 7 built a case that our Main structure runs 1.55x hotter than
the reference because our Pullback break mode defaults to Shadow, the loosest of
the three, and that switching it to Body or Body & Sweep would cut the IDM race
Total from 31 toward 20. It was stated as the leading explanation and as the
next test to run.

Their Pullback break mode IS Shadow. Identically ours. The hypothesis is
refuted outright and the test is not worth running.

What was wrong with the reasoning: Chapter 2 deferred a noise filter, Chapter 4
described break modes, and I treated the second as the answer to the first
because they fit. They may simply be different things, and the deferred filter
may be something not yet in any material we have.

### [SRC] Our defaults match theirs exactly — all eight of them

Every break mode and every Hidden Shadow switch:

    ours   mPB Shadow, mIDM Shadow, mBOS Body & Sweep, mCH Body & Sweep
           hsPB false, hsIDM false, hsBOS true, hsCH true
    theirs identical, all eight

Master prompt §59 and §60 were right, and this is now source-verified rather
than specified. Also confirms `Label Swing` (our `showSW`, default on) and the
Guidance panel defaulting off.

The greyed-out Hidden Shadow boxes for Pullback and IDM are a UI nicety we
cannot reproduce — Pine cannot disable an input — but the BEHAVIOUR matches:
`brkStep` gates on `b.useHS and b.mode != BRK_SHADOW`, so HS is inert under
Shadow mode either way, and our `hsPB` tooltip already says so.

### [SRC] Deep Internal only runs with Internal — confirmed

> "It is available only when Internal Structure is enabled."

Exactly our `runDeep = runInt and showDeep`. Confirmed.

### ONE REAL SETTING DIVERGENCE WE INTRODUCED

Their **Show Deep Internal Structure is ON**. We defaulted it OFF in v0.7.16,
following master prompt §58 ("Show Deep Internal = false") and §81 ("no Deep by
default").

So the spec and the actual reference profile disagree, and we followed the
spec. That is defensible for a clean first load, but it means our default chart
is NOT the reference's chart. Anyone comparing the two by eye should turn Deep
on first. The MD default stays unless asked otherwise — flagging it, not
changing it.

It should not affect a Main-depth statistic, since Main does not read Deep.

### [GAP] Their statistics table has no depth selector

"Show LIT Statistics Table" is a single checkbox. Ours has a
Statistics / debug depth dropdown defaulting to Main. Theirs must be fixed to
one depth, or pooled across depths, and the panel does not say which.

If theirs pools Main + Internal + Deep and ours reports Main alone, the 31-vs-20
comparison is not like-for-like at all — though the direction is wrong for that
to be the explanation, since pooling would make THEIR number larger, not
smaller.

### WHAT IS ACTUALLY LEFT ON THE 31-vs-20

With inside bars confirmed (Ch. 1), pivot-from-pullback confirmed (Ch. 2), the
two-level tracker and its frozen confirmation level confirmed (Ch. 4), and now
every break mode confirmed identical, the remaining suspects are narrow:

  1. The outside-group case. In `detStep`, a group that makes a new impulse
     extreme AND gives back the other side evaluates `started` first, so it
     opens a correction. The source never covers a group breaking both sides,
     so this is [INF] and it is one of the few remaining places our behaviour
     is a choice rather than a transcription.
  2. The deferred noise filter from Chapter 2, if it is genuinely a separate
     mechanism rather than the break modes.
  3. Whatever their statistics table actually cohorts over.

No hypothesis is promoted to leading. The last one was promoted on a fit and it
was wrong; the next one gets measured first.

---

## Chapter 12 — The Display Settings Panel

Short panel, three items, and two of them matter a lot.

### [SRC] "Show External Pullback (ORDER FLOW)"

The control is literally labelled with both names. Third independent
confirmation of Chapter 6: order flow IS the external pullback sequence, not a
separate orientable state. The v0.3.6 question is closed for good.

Options: Hide / Show All / **Show Latest Bullish & Bearish** (the one selected).

> "LIT draws its confirmed External Pullbacks. SMC draws confirmed
> Main-structure pullbacks using the same display mode. All pullback zones use
> the full tracked range."

### [SRC] !! "LATEST BULLISH & BEARISH" — SECOND INDEPENDENT WITNESS FOR DUAL TRACKING !!

You cannot offer to draw "the latest bullish AND the latest bearish external
pullback" unless you are maintaining both at once. A single trend-oriented
detector only ever has one.

This corroborates Chapter 3 from a completely different document:

> "First, we check whether there was already a bearish pullback before the
> change of character got broken."

Two independent sources now say the engine holds a latest pullback in EACH
direction simultaneously. Our `PBDet` is oriented to the current trend and
holds one; on a CHoCH flip we do `x.latPx := na` and reorient, so we start from
nothing and must wait for a fresh correction.

This is now the only confirmed engine divergence in the whole audit, and it has
gone from one mention to two. It is still not implemented — it is a real change
and it needs measuring — but it is no longer a single-sentence inference.

It also refines the near statistic. "The last opposite pullback" (Chapter 10)
most naturally means the latest pullback of the OPPOSITE DIRECTION, which is
precisely what "Latest Bullish & Bearish" maintains. Our `pickOppPb` now takes
the most recent GEOMETRICALLY eligible zone — the most recent one lying on the
far side of the boundary. In our engine those coincide, because we only ever
publish same-trend pullbacks. Under dual tracking they would not. So the
pickOppPb fix is correct as far as our engine can express it, and would need
revisiting if dual tracking is ever implemented.

### [SRC] !! INTERNAL PULLBACKS NEST INSIDE EXTERNAL PULLBACKS !!

> "In LIT, shows Internal Pullbacks nested inside visible External Pullbacks.
> In SMC, shows confirmed pullbacks from the visible Internal and Deep Internal
> structure depths."

This closes the [GAP] that has been accumulating since Chapter 1 and was raised
again in Chapters 2, 3 and 6 — how the child degree is fed.

It is NOT fed by the parent's discarded inside bars, which was the worry each
time "inside bar candles ... only form fractal and internal structures" came
up. Internal pullbacks are nested INSIDE external pullbacks.

That is exactly the v0.7 scoped hierarchy: a child context is owned by a parent
PULLBACK, `intScope` opened by a confirmed Main pullback and `deepScope` by an
Internal one. Our architecture is right, and the accumulated suspicion against
it was wrong. Recorded so it stops being re-raised.

Note also the LIT/SMC split in the tooltip: the "Internal and Deep Internal
structure depths" phrasing belongs to the SMC model. In LIT, internal pullbacks
are defined by nesting, not by a separate depth engine.

### [SRC] "Color Inside Bars" is CHECKED

Confirms the v0.7.16 default flip to ON was right, and that §58/§61 match the
reference's actual profile on this one.

### [INF] "All pullback zones use the full tracked range"

Our `zone()` draws from `det.hitEdge` to `det.hitPx` — confirmation level to
pivot. The full tracked range is `rngHi`..`rngLo`, which we maintain separately.

For a bullish correction these are nearly the same object: the range high
cannot exceed the confirmation level without confirming the correction, so the
range high sits at or just under it. The difference is at most one wick, and
under "Final swept level" it is zero.

Not changed. Recorded as a sub-pixel question, and one that `pbEdge` already
exposes both sides of.

### [GAP] Default of "Show Internal Pullback" is ambiguous

Unchecked in one capture, checked in the next — most likely toggled to surface
the tooltip. Ours (`pbIntOn`) defaults on. No action.

---

## Chapter 13 — Reference Screenshots: Nested Pullbacks, and the Window Question

### [SRC] External pullbacks CONTAIN internal pullbacks — seen on a live chart

Four ZEC 15m captures. The pullback zones are drawn as large translucent boxes,
and smaller, more saturated boxes sit INSIDE them: a wide teal external box with
several darker boxes nested within it, a pink external box with a deeper pink
box inside, and so on.

This is Chapter 12's tooltip made visible:

> "In LIT, shows Internal Pullbacks nested inside visible External Pullbacks."

Confirms the v0.7 scoped hierarchy on a real chart rather than in prose. A child
context is owned by a parent PULLBACK — `intScope` opened by a confirmed Main
pullback, `deepScope` by an Internal one — and the picture is exactly that
containment. The suspicion raised in Chapters 1, 2, 3 and 6 that the child
degree might be fed by the parent's discarded inside bars is now refuted twice,
once in prose and once on a chart.

Also visible and consistent with ours: i / ii label prefixes by depth, blue
bullish IDM against amber bearish IDM, BOS in the continuation colour with
CHoCH in the reversal colour, and ✗ marks on retired levels.

### [SRC] !! THE REFERENCE TABLE IS NOT VIEWPORT-COHORTED !!

The statistics table reads identically across all four captures:

    IDM → BOS touch            24  14  58.3%
    IDM → Choch touch          24  10  41.7%
    BOS near → Opp PB reach    38  26  68.4%
    BOS near → BOS break       38  12  31.6%
    Choch near → Opp PB reach  39  31  79.5%
    Choch near → Choch break   39   8  20.5%

Four very different viewports, one unchanging set of numbers. A viewport-
cohorted table cannot do that.

And Chapter 11 settles it independently of which indicator drew this particular
table: the reference's settings panel exposes **one checkbox** for the
statistics table and no window control of any kind. There is no way for it to
express viewport cohorting, so it does not do it.

CONSEQUENCE, AND IT IS NOT SMALL. Our `statsWindow` has defaulted to "Visible
chart" for the whole calibration effort. Every totals comparison in this log —
31 against 20, 34 against 29, 18 against 14 — put a viewport-cohorted count
next to a whole-history count. Those comparisons were not like-for-like, and the
"31 vs 20" density problem that has driven several rounds of investigation may
be partly or wholly an artefact of the cohorting, not a property of the engine.

CHANGED THIS PASS: `statsWindow` now defaults to "All loaded bars", and the
option order is flipped so the comparable setting is first. The tooltip records
why. "Visible chart" stays available for reading one stretch in isolation, with
a note that its totals are not comparable to the reference's.

This does not by itself make the numbers match. It makes them MEASURABLE
against each other for the first time, which every previous round assumed it
already had.

### Reading note on attribution

Riptide LIT appears hidden in the layer list of these captures while Index Algo
is visible, which points to the table being the reference's. The label formats
are not a discriminator — ours were calibrated to match its "HH | Weak High"
style deliberately.

The row set is six, where the annotated reference table in Chapter 10 carried
twelve including the Hidden Shadow rows, so the two do not obviously come from
the same build.

It does not matter for the conclusion above, which rests on the settings panel
rather than on this table's provenance. It does matter for treating 24 / 38 / 39
as reference targets, so those numbers are NOT recorded as targets here.

---

# PART TWO — THE TRADING SIDE

Chapters 14-20 come from the full Index Algo description and the POI/FVG
slides. Part One was structure; this is what the system does with it.

## Chapter 14 — FVG is the distance between two PULLBACKS

### [SRC] A pullback is a transactional node that can be consumed

> "Each Pullback can represent a transactional node where meaningful orders may
> still remain active, or where they may already have been consumed by later
> price action. If a new Pullback penetrates into the previous Pullback, the
> orders associated with the earlier area are considered to have been consumed,
> and that area loses its validity."

### [SRC] !! FVG IS NOT THE THREE-CANDLE WICK GAP !!

> "However, if there is a price gap between two Pullbacks and the market moves
> from one transactional node to the next through a sharp displacement, the
> orders from the previous Pullback may not have been fully consumed... This
> price gap and displacement are referred to as an FVG."

> "Contrary to the common simplified interpretation, an FVG is not merely the
> distance between the wicks of three consecutive candles."

The slide states it twice, once with a red ✗ over the three-candle version:
**"FVG is the Distance between two consecutive pullbacks"** and **"So FVG is not
necessarily the distance between the shadows in three consecutive candles."**

The same slide shows an inside bar invalidating a would-be three-candle FVG and
labels the move "Not Pullback". So FVG inherits the whole Part One machinery -
inside bars, valid pullbacks, pivots - rather than being a candle pattern.

This matters enormously for implementation: every generic SMC library computes
the three-candle version. That is the wrong object here.

## Chapter 15 — POI, and the four zone types

### [SRC] Decisional

> "When IDM is broken, Pullbacks that remain structurally valid and contain an
> FVG on the appropriate side may be drawn as Decisional POIs. In a bullish
> structure, these zones have a Demand nature. In a bearish structure, they have
> a Supply nature."

### [SRC] Extreme

> "An Extreme zone is derived from the last defensive point of the current
> market structure. After BOS is broken and Choch is formed, the final valid
> high or low of the prior structure can be treated as one of the most sensitive
> structural reference points. If the candle range associated with that level
> remains valid and price has not yet penetrated into it, that range can define
> the Extreme zone."

### [SRC] Breaker Block and Flip both require a JUMP

> "If the break of the Extreme zone occurs with a Jump, or sharp price
> displacement, the Breaker Block becomes valid."

> "If, after a Choch break, the market fails to react properly to the Breaker
> Block, price may extend toward the Flip zone... Flip formation is also linked
> to a Jump-based break of the Extreme zone."

### [SRC] Trade only WITH the trend, and zones expire structurally

> "We only enter trades in the direction of the prevailing trend... when price
> reaches Demand zones, the market must be in an uptrend, and only Long entry
> opportunities are evaluated."

> "if the BOS level is broken before price reaches these zones, a Change of
> Character level will then form above them... the market has already shifted
> into a downtrend before reaching the Decisional zones. As a result, these
> Demand zones lose their validity. For this reason, once the BOS level is
> broken, these zones are no longer extended."

### [SRC] POI RANGE — Internal pullbacks refine it, automatically

> "If the range is based on Order Flow, the focus is on the broader
> transactional node... If the range is based on an Order Block, the zone becomes
> more precise and compact, focusing on a more internal component of the
> structure, such as the pivot candle or internal Pullbacks."

> "Index Algo handles this automatically. If an External Pullback contains a
> valid Internal Pullback, the POI range is defined using the Internal Pullbacks.
> If the External Pullback is not extensive and does not contain a valid internal
> structure, the POI range is derived from the External Pullback itself."

**This is what the Internal degree is FOR.** Ch.12 said internal pullbacks nest
inside external ones; this says why it matters — they tighten the entry zone.
Our P7b work feeds directly into this and is no longer a display question.

### [SRC] Mitigation — the arbitrary 50% is rejected by name

> "The tool does not rely on a generic 50% threshold as a rough approximation.
> Instead, it uses the selected structural logic to determine how penetration
> into Order Flow or Order Block areas should be interpreted."

The slide is blunter: **"It is incorrect to assume or set an arbitrary and
subjective level such as 50%."** Same objection as the fixed-N pivot rejection
in Ch.2 and the multi-timeframe rejection in Ch.3. Consistent philosophy, and
it forbids the obvious shortcut.

### [SRC] Liquidity Grab Levels — the level-based entry family

> "These are not box-shaped zones. Instead, they are key structural levels...
> IDM Level, BOS Level, Choch Level."

## Chapter 16 — SCOB entry confirmation

> "Reaching a valid zone or level is not enough on its own to justify an entry...
> Index Algo does not merely check whether 'price has reached the zone.' It also
> evaluates 'how the market behaves after reaching that zone.'"

SCOB = Single Candle Order Block. Three modes, mirroring the structural break
modes: Shadow With SCOB / Body With SCOB / Level Sweep and Body With SCOB.

> "if SCOB confirmation is not issued, no trade entry is opened, even if the
> zone itself remains valid."

SCOB Level Behavior: **Move With Deeper Candle** (the reference shifts to each
new deeper candle) or **Keep First Penetration Candle** (the first valid
penetration stays the reference).

[GAP] The exact geometry of the SCOB level is never stated - only how it
BEHAVES and how it is broken. This is the single biggest hole on the trading
side and it cannot be closed by inference.

## Chapter 17 — Stop loss

> "the SL may be placed closer to or farther from the entry price - for example,
> below the relevant Block Order itself or below its associated Order Flow."

LowRisk = farther (beyond the Order Flow). HighRisk = closer (the Block Order).

> "Because the SL break and Stop Loss activation are evaluated on a body-break
> basis, and because the Hidden Shadow logic is also incorporated during position
> management, there is no need to apply an additional tolerance buffer."

Hidden Shadow is reused for SL management - the same synthetic-candle test that
guards structural breaks guards the stop.

Secondary Loss Cap: an optional second maximum loss as a % of balance, for when
a body-break or Hidden Shadow exit would exceed the risk calculated at entry.

## Chapter 18 — Active Price, and the obstacle check

> "Active Price is determined based on the Entry Price, Stop Loss, minimum
> required Reward/Risk ratio, and trading commission. It represents the level
> price must reach for the setup to satisfy the required trade-quality threshold.
> Once price reaches this level, the Trailing Stop logic becomes active."

### [SRC] !! THE OBSTACLE CHECK — a setup can be REJECTED after confirmation !!

> "Before entry, Index Algo also checks whether the path from Entry Price to
> Active Price is clear of meaningful structural obstacles. These may include:
> BOS levels, Opposing Pullbacks, Zones that have changed nature after a break,
> Other relevant broken structural levels. If Active Price is invalid or a
> structural obstacle blocks the path toward it, the setup is rejected even if
> SCOB has been confirmed."

A confirmed entry can still be thrown away because the road to its own target is
blocked. Nothing in master prompt §72-§75 contains this idea, and it is the kind
of filter that changes a distribution rather than shaving it.

## Chapter 19 — Position sizing

Balance (evolving, not the initial capital), entry, stop distance, max
acceptable loss as % of balance, and commission. Leverage derived where
applicable. Nothing exotic; the notable part is that commission is in the
sizing AND in the Active Price calculation.

## Chapter 20 — Exit is a TRAILING STOP, not a fixed target

> "For trade management, Index Algo relies on a Trailing Stop logic rather than
> fixed take-profit targets. This approach allows a trade to retain room for
> further expansion as long as price continues to move in line with the confirmed
> scenario."

The trailing stop arms when price reaches Active Price. Before that, the initial
stop is the only exit.

**This contradicts master prompt §74**, which names BOS as "the natural
structural target". The reference does not target BOS - it uses BOS-directional
logic to justify the trade and then trails. §74 is our own inference and the
source overrides it.

[GAP] What the trailing stop actually trails is never stated - structure,
a fraction of the move, or something else. Second-biggest hole after SCOB.

---

## Chapter 21 — SCOB geometry, Liquidity Grabs and SL placement, from the slides

These three slide sets close the two [GAP]s flagged in Ch.16 and Ch.17.

### [SRC] !! SCOB GEOMETRY — GAP CLOSED !!

Three panels, same setup, differing only in what confirms:

    Mode 1  SCOB With Shadow        a red candle, the SCOB level drawn at its
                                    top, then a green candle whose HIGH breaks
                                    it. Annotated "High/Low Candle".
    Mode 2  SCOB With Body          same level, confirmation only when a later
                                    candle CLOSES beyond it. "Close Candle".
    Mode 3  SCOB With Body & Sweep  the level RATCHETS upward, each abandoned
                                    level marked with the same ✗ glyph used for
                                    swept structural levels, until a candle
                                    closes beyond the latest one.

So SCOB is the Single Candle Order Block: **the last opposite-direction candle
before the reaction**, its level taken at the boundary facing the intended
move, and then broken under the same three-mode engine the structure already
uses. Mode 3 is `brkStep` in BRK_SWEEP exactly - same ratchet, same ✗.

That is a large simplification for implementation: SCOB needs no new break
engine, only a new level source.

### [SRC] !! STOP LOSS PLACEMENT — GAP CLOSED !!

The long-position slide draws a wide **OrderFlow** box containing a narrow
**Order Block** box, with two stop levels and two labelled outcomes:

    SL on Order Block  →  HIGH RISK   (closer to entry, below the OB's low)
    SL on Pullback     →  LOW RISK    (farther, below the whole pullback/
                                       OrderFlow low)

Exactly the Ch.17 text, now with the geometry attached. Mirrors for shorts.

### [SRC] Liquidity Grab entries — three levels, all gated by SCOB

    IDM Level    price dips THROUGH the IDM (the grab), "Check SCOB", then up.
    BOS Level    price pokes ABOVE the BOS (the grab), "Check SCOB", then DOWN.
    CHoCH Level  price dips through the CHoCH, "Check SCOB", then up.

Every one of the three routes through SCOB. The grab alone never enters.

### [GAP] The BOS-grab slide points AGAINST the prevailing trend

Ch.15 says plainly: *"We only enter trades in the direction of the prevailing
trend."* But the BOS slide shows a bullish structure, price sweeping above the
BOS, and a red arrow DOWN.

Two readings, and the source does not choose between them:

  1. Liquidity Grab Levels are a SEPARATE entry family from POI zones, and the
     with-trend rule was stated inside the POI section only.
  2. A failed BOS sweep is itself the signal that the leg is done.

Reading 2 is the one our own instrumentation already measures: "BOS near → Opp
PB reach" runs 69% in the reference and 55% in ours - price that touches the
BOS and fails mostly retraces rather than continuing. That is the same event.

Recorded as a genuine conflict, not resolved. It decides whether the strategy
has one direction rule or two, which is not a detail.

### [GAP] What the trailing stop trails is still unstated

Nothing in these slides addresses it. Ch.20's gap stands and is now the only
large hole left on the trading side.

---

## Chapter 22 — Active Price rejection, and the SL decision, drawn

### [SRC] The obstacle check, with the obstacle types NAMED on the chart

The "Active Price Set — Long Position" slide draws a long from a Decisional
zone and then **rejects it with a red 🚫**. Reading the level stack downward:

    BOS Level
    Valid opposite pullback        (a purple box just under the BOS)
    Breakout Zone
    Active Price          ┐
    Breakout Zone         │  the shaded Entry → Active Price corridor
    Entry Point           ┘
    Stop Loss

The rejection is the point of the slide: a **Breakout Zone sits inside the
Entry → Active Price corridor**, so the setup is thrown away even though the
zone and the entry are otherwise valid.

It also names the obstacle types visually, matching the text list: **BOS Level**,
**Valid opposite pullback**, **Breakout Zone** (a level that changed nature after
being broken). "Breakout Zone" is a term the text never used - it appears twice
on the slide at two different prices, so broken levels leave behind a ZONE, not
just a line.

This is the filter with no counterpart anywhere in master prompt §72-§75, and
it is the one most likely to change a distribution rather than shave it: it
removes setups that are structurally fine but have no room to pay.

### [SRC] The stop-loss decision, drawn as a question

The "Stop Loss Management" slide shows a Decisional zone, a SCOB, an Entry
Point, and the SL at the zone's lower boundary. Price rallies, collapses back,
and two candidates are both labelled **"Exit Point"** one bar apart - with
**"Close or Hold the Position"** and a visibly unsure trader beside them.

That is the Hidden Shadow decision transplanted onto the stop: the first candle
breaks the SL with its body, the next one is the resolver, and the synthetic
candle decides whether the break was real. Same machinery as Ch.5, applied to
risk instead of structure - which is exactly what Ch.17 said in words.

Nothing new mechanically. It does confirm that the two exit candidates are
ADJACENT candles, so the SL resolver is the immediate next non-inside bar, as
in the structural case.

---

## Chapter 23 — Hidden Shadow on the STOP LOSS, drawn

The same three-panel construction as Ch.9, with `SL` in place of the structural
level. Short position, so the stop sits above and a break is upward.

    LEFT   combined candle: High above SL, Open and Close both BELOW it.
           Only the wick got through.                    → "Hidden Shadow"
    RIGHT  same setup, the resolver closes higher, combined Close ABOVE SL.
                                                         → "Breakout With Body"
    THIRD  four candles labelled "inside" are skipped; the first one whose high
           escapes the candidate's range resolves it; the combined Close still
           sits below SL.                                → "Hidden Shadow"

### The finding is that there is NO new mechanism

Every element is identical to the structural case: synthetic candle built from
the candidate's open, the span's high and low, and the resolver's close; inside
bars skipped against the CANDIDATE's range; only the close decides; one
resolution attempt.

So guarding a stop needs **no new code at all** — arm a `Brk` on the SL price in
`BRK_BODY` with `useHS` on, and feed it the same stream. The existing engine
already does the whole thing, including the sweep variant if that is ever
wanted.

That is worth knowing before Stage F is scoped: SL management reads as a large
subsystem in the reference's description and is in fact a two-line application
of machinery we have had working since v0.7.

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
