# LIT_FORWARD_V2 — durable status

**Read this before proposing any LIT work.** It exists so a future session
cannot reopen research that is already closed.

## Historical status — FROZEN, DO NOT REOPEN

    Stage A   naked continuation, raid stop     INCONCLUSIVE
    Stage B   five stop definitions             INCONCLUSIVE
    Stage C   T6_PIVOT, untouched symbols       INCONCLUSIVE
    HISTORICAL LIT TRADING FAMILY: CLOSED

Stage C detail: T6_PIVOT standalone +0.114 R/bet (t≈2.4) PASSED its criterion;
paired delta vs control +0.068 (z≈1.5) FAILED. Effect roughly halved from
Stage B. Mark-to-market and realized-loss guards both passed.

**Do NOT**: re-slice history · pool samples · optimise T6_PIVOT · modify Active
Price · try other trailing variants · change entry or stop · filter symbols or
timeframes retrospectively · optimise Hidden Shadow or the break engine · add
FVG/POI/SCOB to rescue it · call the historical family profitable.

## Forward status

    State:            WIRED AND ARMED — awaiting the .env flag
    Pre-registration: PREREG_lit_forward_v1.md (rules), plus
                      PREREG_lit_seek_escape.md and _v2.md (the P9 change)
    Version:          LIT_FORWARD_V2
    Rules hash:       ec15663860a09853      (V1 was 4b105c593bc48469)

### V1 → V2 — what changed and what it costs

One thing changed: the engine's P9 policy is `"leg"` rather than `"none"`.
Entry, stop, exits, scoring and inference are all identical to V1.

P9 repairs a trap state. `PH_SEEK` with no CHoCH was a one-way door, so on
7.3% of symbol-timeframes — **BTC Min30 among them** — Main structure stopped
emitting inside the first 200 bars and never resumed. Those panels contributed
nothing to V1 at all. Evidence: `research/LIT_SEEK_ESCAPE.md`.

**V1 rows are not touched and are never pooled with V2.** Every query in
`forward.py` filters on `strategy_version`, and `signals.setup_id` mixes the
version into the key, so the two populations cannot collide even on the same
bar of the same symbol.

**The cost, stated plainly: any V1 setup still PENDING at the switch will
never resolve.** The resolver only reads rows matching the current
`FWD_VERSION`, so those become *censored* observations — not wins, not losses,
not timeouts. They must be reported as censored if V1 is ever written up.
Count them before or after the switch:

```bash
sqlite3 /home/ubuntu/riptide/riptide.db \
  "SELECT COUNT(*) FROM lit_forward
   WHERE state='pending' AND strategy_version='LIT_FORWARD_V1';"
```

Rewriting them to look finished would be worse than leaving them censored, so
nothing does that.
    Started:          (not started — no forward_start_timestamp stamped)
    Primary outcome:  paired_delta_R = t6_pivot_R − control_R
    Unit:             market-event bet (riptide/decide.py::event_span)

### OPEN PRECONDITION — activation is blocked on this

Pine↔Python parity is NOT established and cannot be in this environment (no
Pine compiler; `riptide-lit-v2.pine` has never been compiled). The
specification makes parity a precondition for collection. A human must compile
the Pine, compare its setup markers against the Python record on the same
symbol/timeframe, and record the outcome in PREREG §0 before enabling.

One divergence was already found and fixed during implementation: the Pine
entry layer reset the trail pivot at each IDM break, while the Python
`trails()` forward-fills it across cycles. That it existed is the argument for
running the check properly rather than assuming.

### Checkpoints — no other evaluation is permitted

    1.  250 bets  (~2 weeks)   health only, no efficacy read
    2. 1000 bets  (~8 weeks)   futility only: stop if paired delta ≤ −0.10
    3. 1857 bets  (~15 weeks)  THE READ, the only place V1 can be closed

Rate measured, not guessed: 0.068 setups per symbol-timeframe-day over 39
symbol-timeframes x 333 days, matching the 0.074 implied by Stage C. At
TOP_N=120 x 3 timeframes that is ~24 setups/day and ~18 bets/day. The
checkpoints are in BETS and do not move; only these calendar estimates did.

Powered for the Stage B effect (+0.120). **If the true effect is Stage C's
size (+0.068) this experiment needs ~5,800 bets ≈ 320 days** and a null at
checkpoint 3 means "no effect ≳0.12 detected", not "no effect".

### Enabling

The code path is live: `scanner.cycle` calls the hook every cycle and it
returns inert while the flag is unset. Enabling is one `.env` change on the
Oracle box (see DEPLOY.md), which no session working from a container can
make — `/home/ubuntu/riptide/.env` is `600`, owned by `ubuntu`, and is the only
copy of the deployment's configuration.

    RIPTIDE_LIT_FORWARD=1
    RIPTIDE_LIT_FORWARD_ALERTS=1     # optional

Both default 0 in code and that default is NOT changed: flipping it would arm
the experiment for every checkout, and PREREG §16 says it ships off.

`forward_start_timestamp` is stamped on the first enabled cycle and never
moves, so enabling cannot backfill history.

## Research ledger entry

The repository has no central research ledger file, so the entry lives here.

    ID:         LIT-FWD-001
    Hypothesis: T6_PIVOT produces positive incremental paired R versus the
                frozen control on future unseen LIT setups.
    Evidence:   prospective forward (not a backtest)
    Motivation: Stage C paired delta +0.068 R/bet at z=1.5 — NOT validated,
                and roughly half the Stage B discovery estimate.
    Primary:    paired_delta_R = t6_pivot_R − control_R, in bets
    Status:     PRE-REGISTERED, NOT ACTIVATED (parity precondition open)
    Revisit:    only at a pre-registered checkpoint (250 / 1000 / 1857 bets)
