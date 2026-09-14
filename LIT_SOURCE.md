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

## Curriculum stated in the intro — what is still to come

> "In the market structure section, we go through these: inside bar candles,
> pivot points, or what we also call swing points, pullback and order flow,
> market structure, which can be analyzed through either SMC or LIT, how market
> structure forms with LIT, different types of level breaks"

    1. inside bar candles              ← done, Chapter 1
    2. pivot points / swing points     ← done, Chapter 2
    3. pullback AND order flow         ← NEXT. Carries the deferred noise
                                          filter. Decides the 31-vs-20.
    4. market structure, SMC or LIT
    5. how market structure forms with LIT
    6. different types of level breaks ← Shadow / Body / Body & Sweep

Two things worth noting in advance:

  - "pullback and order flow" is presented as a SINGLE topic. Our longest-
    standing open question is what re-orients Main order flow, and both
    permitted readings of the master prompt were measured and rejected
    (v0.3.6). If order flow is defined through the pullback rather than
    separately from it, that chapter settles it.

  - Chapter 2 is where the 31-vs-20 answer should be, because how a swing
    point is taken determines how many corrections exist at all.
