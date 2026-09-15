# P9 — the bootstrap CHoCH: result

Two rounds. v1 rejected `leg` on a gate I had mis-specified; v2 re-ran it with
the gate written against the cause and an enlarged held-out set. Both
pre-registrations were committed before their runs
(`PREREG_lit_seek_escape.md`, `PREREG_lit_seek_escape_v2.md`), and both studies
are kept so either round can be reproduced
(`research/studies/lit_seek_escape.py`, `..._escape2.py`).

## Verdict

**`leg` PASSES.** It was proposed here with the default left at `none`, and
**subsequently turned on at the user's instruction** — `POL.seekCh` now
defaults to `"leg"`, which carried the forward record to `LIT_FORWARD_V2`
(rules hash `ec15663860a09853`). See the changelog entry "P9 TURNED ON".

It repairs **14 of 14** `PH_SEEK` latches across both samples — 5 in sample, 9
on 71 untouched symbols — with no invariant violations, no panel made
unhealthy, and 99.8% of existing events preserved where nothing was broken.

A **second, unrelated defect** (`PH_LOCK` stall, 3 of 191 panels here) is
characterised below and deliberately left unfixed. It has since had its own
diagnosis — `research/LIT_LOCK_STALL.md` — which measures it at 2 of 189 panels
under the repaired engine, corrects the "both boundaries unreachable" reading
below, and recommends leaving it alone.

---

## The defect P9 repairs

From `research/studies/lit_main_latch.py`: the CHoCH level is created when a
BOS *breaks*, so the first cycle after bootstrap reaches `PH_SEEK` with no
opposing boundary. Step 8 needs `ch.ready()`, step 5 will not publish an IDM
outside DISCOVER/TRACK, there is no timeout. If that first BOS is never broken,
the context emits nothing for the rest of the chart.

`POL.seekCh` gives the first cycle the shape every later one already has:

| arm | the first cycle's CHoCH |
|---|---|
| `none` | none — frozen behaviour, the incumbent |
| `leg` | the leg extreme **against** the trend: the mirror of the BOS |
| `raid` | the IDM raid extreme — the level Stage A takes as its stop |

An expiry arm was rejected before measurement: `Pol`'s contract is *"No policy
may introduce a number"* and a bar count is a number.

---

## Round 1 — rejected, correctly, on a gate that was wrong

`leg` cleared every in-sample gate. Out of sample on 24 symbols it repaired 5
of 6 unhealthy panels; XMR Min30 survived, G1 read *"zero latched panels"*, and
the arm was rejected.

XMR was never a `PH_SEEK` latch:

```
XMR_USDT Min30   phase = LOCK   dir = bear   stuck 10,385 bars
    ch.on  = True   px = 800.72     41% above the highest high that followed
    bos.on = True   px = 276.66      5% below the lowest low that followed
```

Both boundaries outside the range price went on to trade. A different trap, one
level up.

**The error was mine.** G1 tested the symptom where it needed to test the
cause, and as written it could not tell *the fix failed* from *something else
is broken* — which need opposite responses. I did not reinterpret it after
seeing which way it cut; the v1 verdict stands as REJECTED in the record.

---

## Round 2 — the corrected gate, and the price paid for a second look

Unhealthy panels are now classified by final engine state **before** being
counted: `SEEK_LATCH` (`phase == PH_SEEK and not ch.on`), `LOCK_STALL`
(`phase == PH_LOCK`), `OTHER`.

* **G1 scores `SEEK_LATCH` only** — an arm is judged on the defect it set out
  to repair.
* **G3 scores any unhealthy panel** — an arm may never make anything worse.

A corrected rule on the same symbols would be a free second attempt, so the
held-out universe was enlarged from 30 requested symbols to 80 — 71 resolved,
135 panels, none in `DISCOVERY`. And the prereg fixed that there is no v3.

### In sample — 30 symbols, 56 panels

| panel | `none` | `leg` | `raid` |
|---|---|---|---|
| BNB Min30 | SEEK_LATCH (cov 0.00) | healthy (0.99) | healthy (0.99) |
| BNB Min15 | SEEK_LATCH (0.00) | healthy (0.98) | **LOCK_STALL (0.00)** |
| BTC Min30 | SEEK_LATCH (0.05) | healthy (0.98) | healthy (0.98) |
| ONDO Min30 | SEEK_LATCH (0.00) | healthy (0.77) | healthy (0.77) |
| TIA Min30 | SEEK_LATCH (0.01) | healthy (0.99) | healthy (0.99) |

BTC Min30 goes from 1 IDM break in 333 days to 28. TIA from 1 to 51.

| arm | G1 `SEEK_LATCH` | G2 invariants | G3 new unhealthy | |
|---|---|---|---|---|
| `none` | 5 | 0 | 0 | fails — it *is* the defect |
| `leg` | 0 | 0 | 0 | **passes** |
| `raid` | 0 | 0 | 0 | passes |

### Selection

| arm | retention | inflation |
|---|---|---|
| `leg` | 99.8% (2467 / 2473) | 1.6% (41 new) |
| `raid` | 99.8% (2467 / 2473) | 1.7% (43 new) |

**Retention did not separate them — the kept counts are identical.** `leg` was
selected by the pre-registered tiebreak ("`leg` takes a tie, as the smaller
assumption"), not by a measured difference. Stating that plainly because a
tiebreak deciding an outcome is weaker evidence than a comparison winning one.

### A weakness in my own v2 gates, named

`raid` **passed** in sample while leaving BNB Min15 dead — it converts that
panel's `SEEK_LATCH` into a `LOCK_STALL`. G1 only counts `SEEK_LATCH`, and G3
only catches panels that were *healthy* beforehand, so nothing in the gate
structure caught it. A condition of the form *"an arm may not convert one
defect into another"* should have been there and was not.

`leg` won anyway, and the tiebreak happens to point the same way — but it got
there by luck rather than by the rules doing their job, and that is worth
knowing when reading this result. Not retrofitted.

### Confirmation — 71 untouched symbols, 135 panels

| | `none` | `leg` |
|---|---|---|
| SEEK_LATCH | **9** | **0** |
| LOCK_STALL | 3 | 2 |
| OTHER | 0 | 0 |
| healthy | 123 | **133** |

* **G1** — SEEK_LATCH remaining: **0**
* **G2** — invariant violations: **0**
* **G3** — panels made unhealthy: **0**

`leg` also incidentally cleared one `LOCK_STALL` (3 → 2), presumably by
changing the trajectory before that panel reached the bad lock. Noted, not
claimed — it was not designed to do that and one panel is not evidence.

### Economics — reported, and barred from the selection

| arm | bets | mean R | SE | total R |
|---|---|---|---|---|
| `none` | 1903 | 0.192 | 0.110 | 365.5 |
| `leg` | 2090 | 0.150 | 0.100 | 313.3 |
| `raid` | 2077 | 0.152 | 0.101 | 316.4 |

`none` is better per bet on fewer bets; the gap is well inside one SE either
way. It did not enter the decision, by design. Choosing a structure repair on
its returns is the curve-fit the settings grid already priced at ~0.95 R/bet
out of sample.

---

## The `PH_LOCK` stall — characterised, not fixed

3 of 191 panels (1.6%), all Min30:

| panel | dir | stuck | BOS | CHoCH |
|---|---|---|---|---|
| XMR Min30 | bear | 10,385 bars | 276.66 | 800.72 |
| KAS Min30 | bull | 8,452 bars | 0.04145 | 0.02475 |
| CATE Min30 | bull | 1,847 bars | 0.087 | 0.002765 |

Same shape of flaw one level up: no timeout and no invalidation. CATE's CHoCH
sits 97% below its BOS — a `phLo` set by a crash and then never revisited.

**Correction.** This paragraph first read "two boundaries, neither reachable".
That is true of XMR and false of KAS, whose BOS was wicked twice and refused by
Body & Sweep. The trigger is not always distance. See
`research/LIT_LOCK_STALL.md` §3.

Prevalence across all 191 panels: `PH_SEEK` **7.3%** (14), `PH_LOCK` **1.6%**
(3).

No policy is proposed for it, by the pre-registration. Fixing a second defect
discovered while validating the first, inside the same experiment, is how a
measurement turns into a rolling redesign. It needs its own diagnosis and its
own prereg.

---

## Standing constraints — unchanged

**As measured, `POL.seekCh` defaulted to `"none"`** and the engine was
byte-identical to the frozen one under it, verified by diffing the latch
study's output before and after the change.

**It has since been turned on.** The default is `"leg"`, `FWD_VERSION` is
`LIT_FORWARD_V2` and `rules_hash` is `ec15663860a09853`. Setting
`POL.seekCh = "none"` reproduces everything measured in this document and
everything recorded under V1.

What that switch did and did not carry:

* V1 rows are untouched and **never pooled** with V2 — every query filters on
  `strategy_version` and `setup_id` mixes the version into the key. Any V1
  setup still PENDING at the switch is a **censored** observation and will
  never resolve; `DEPLOY.md` carries the SQL to count them.
* It does not revisit stages A, B or C. Re-running those under a repaired
  engine is a new experiment needing its own pre-registration — and given that
  14 panels were previously contributing nothing, their samples would change.
