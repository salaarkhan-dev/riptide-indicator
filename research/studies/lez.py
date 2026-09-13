"""Phase 1 for Liquidity Entry Zones: does it clear zero after fees?

A faithful Python port of liquidity-entry-zones.pine, scored by the shared
harness, on Min5 / Min15 / Min30. No bot code exists for this strategy and none
is written until this passes.

THE EXIT GATE, WRITTEN BEFORE THE FIRST RUN (STRATEGIES.md, Phase 1)

    Net R per signal > 0 after fees on the full sample, AND the same sign in
    both window halves and both symbol halves.

That is the whole bar. It is deliberately low — this is not asking the strategy
to beat Riptide, only to exist — and it is deliberately fixed in advance,
because a bar chosen after the numbers arrive is not a bar. PREREG_btc.md and
PREREG_mitigation.md are both in this directory because that discipline caught
something twice.

WHAT IS PORTED, AND WHAT IS DELIBERATELY NOT

Ported exactly: pivot storage and its 20-slot FIFO, the ATR-scaled sweep
distance, the reclaim rule, the wick/body/range quality gates, the confirmation
window (INCLUDING the fact that the sweep bar itself qualifies — see below),
the EMA-50 filter, the cooldown, the ATR stop, the 3R target, and the exit
convention (stop wins a bar spanning both, and the entry bar resolves nothing).

NOT ported: `blockSignalsInTrade`. It decides whether a setup is shown by
whether the PREVIOUS setup is still open, which makes the visible sample
path-dependent on outcomes — you cannot measure a strategy on a sample its own
results selected. The primary numbers here score every setup. The chart's
default view is reported separately, as "serialised", because that is the view
the strategy was judged good on and it deserves its own honest number.

THE CONFIRMATION BAR. In the Pine, `pendingBullSweepBar := bar_index` is
assigned on the sweep bar and `bullWindowOpen` then tests `0 <= 2`, so the
sweep bar can be its own confirmation. That is ported as written rather than
"fixed", and the two arms are reported separately: a model where most signals
are a single candle is a different model from one that waits.

FAIR ACROSS TIMEFRAMES, which is most of the work — the lesson from scalp.py:

  same calendar window   pages are sized per timeframe so Min5 and Min30 see
                         the same DAYS, not the same bar count.
  same symbols           a timeframe that quietly drops thin symbols would
                         flatter itself.
  same horizon in HOURS  not in bars. A 3R target needs 4.5 ATR of travel and
                         that is a wall-clock distance, not a bar count.
  fees in R              cost is fee / risk_pct, and risk here is 1.5 ATR, so
                         a quiet symbol pays twice what a volatile one does.

    PYTHONPATH=. python3 research/studies/lez.py
"""
from __future__ import annotations

import research.env  # noqa: F401  (must precede riptide.config)

import asyncio
import statistics
import random
from dataclasses import dataclass, field, replace

import aiohttp

from riptide.config import CFG, BAR_SECONDS
from riptide.engine import atr_series, run_engine
from riptide.exchange import list_symbols
from riptide.trend import di_direction, supertrend
from research.harness import Outcome, mean_se, simulate_market
from research.studies.mtf_grid import fetch_paged, htf_dir_at

# --------------------------------------------------------------------- config

HTF = "Day1"
# Pages chosen so every timeframe covers the same ~41 days. 2000 bars is 41.6d
# of Min30, 20.8d of Min15, 6.9d of Min5.
TFS = (("Min30", 1), ("Min15", 2), ("Min5", 6))
SYMBOLS = 30
HORIZON_HOURS = 48        # wall-clock, identical on every timeframe
FEE = dict(fee_maker=0.02, fee_taker=0.06)
LADDER = (1.5, 2.0, 3.0, 4.0, 5.0)


@dataclass(frozen=True)
class Params:
    """The Pine input defaults, in one place so a future parity check can
    compare them field by field the way deploy/check-parity.py does for
    Riptide. Changing one here changes one thing, not three."""
    ema_len: int = 50
    use_ema: bool = True
    pivot_len: int = 5
    stored_levels: int = 20
    min_sweep_atr: float = 0.10
    strong_reclaim: bool = False          # "Close Back Inside" is the default
    min_wick_pct: float = 0.35
    max_body_pct: float = 0.65
    min_range_atr: float = 0.20
    require_bull_body: bool = True
    require_bear_body: bool = True
    confirm_window: int = 2
    require_midline: bool = True
    cooldown_bars: int = 10
    atr_len: int = 14
    stop_atr: float = 1.50
    target_r: float = 3.0


P = Params()


@dataclass
class Sig:
    bar: int                  # the confirmation bar; entry is its close
    is_long: bool
    entry: float
    stop: float               # the ATR stop, as the indicator places it
    struct_stop: float        # just beyond the raid extreme, for comparison
    atr: float
    sweep_bar: int
    sweep_hi: float
    sweep_lo: float
    level: float              # the liquidity level that was taken
    score: float              # the Pine quality score, floor 60 by construction
    bars_to_confirm: int
    # filled in later, once the context fetches have happened
    htf_dir: int = 0
    o: Outcome | None = field(default=None, repr=False)


# ----------------------------------------------------------------------- port

def ema_series(cs, length: int) -> list[float | None]:
    """ta.ema: na until `length` bars exist, seeded with the SMA, then
    recursive with alpha = 2/(length+1). Seeding matters only for the first
    few hundred bars and the study runs on thousands, but getting it wrong
    would be an invisible difference from the chart rather than a loud one."""
    out: list[float | None] = [None] * len(cs)
    if len(cs) < length:
        return out
    a = 2.0 / (length + 1)
    prev = statistics.fmean(c.c for c in cs[:length])
    out[length - 1] = prev
    for i in range(length, len(cs)):
        prev = a * cs[i].c + (1 - a) * prev
        out[i] = prev
    return out


def pivots(cs, n: int):
    """(confirm_bar, pivot_bar, price) for highs and lows, strict on both
    sides. A pivot at bar j is only KNOWN at bar j+n, which is what the
    confirm_bar is for — nothing may consult a level before it exists.

    A just-confirmed pivot high can never be swept on its confirmation bar:
    its right-strength guarantees the last n highs sit below it. So there is
    no look-ahead here even though the level is dated n bars back.
    """
    hi, lo = [], []
    for j in range(n, len(cs) - n):
        h, l = cs[j].h, cs[j].l
        if all(cs[k].h < h for k in range(j - n, j)) and \
           all(cs[k].h < h for k in range(j + 1, j + n + 1)):
            hi.append((j + n, j, h))
        if all(cs[k].l > l for k in range(j - n, j)) and \
           all(cs[k].l > l for k in range(j + 1, j + n + 1)):
            lo.append((j + n, j, l))
    return hi, lo


def quality(wick_pct, body_pct, range_atr, ema_ok, reclaim_ok, mid_ok,
            p: Params = P) -> float:
    """f_quality_score, ported as written.

    Note what it does on a signal that actually prints: wick divides by the
    same threshold that gated it, so it clamps at 32; range likewise clamps at
    18; reclaim is a precondition, so it is always 10. Sixty of the hundred
    points are pinned. The number is kept because ordering within the
    remaining forty may still carry information — but it is not a 0-100 scale
    and nothing should ever threshold on its absolute value.
    """
    clamp = lambda v, lo, hi: max(lo, min(hi, v))
    return clamp(
        (clamp((wick_pct / p.min_wick_pct) * 32.0, 0.0, 32.0)
         if p.min_wick_pct > 0 else 32.0)
        + (clamp(((p.max_body_pct - body_pct) / p.max_body_pct) * 24.0,
                 0.0, 24.0) if p.max_body_pct > 0 else 24.0)
        + (clamp((range_atr / p.min_range_atr) * 18.0, 0.0, 18.0)
           if p.min_range_atr > 0 else 18.0)
        + (10.0 if ema_ok else 0.0)
        + (10.0 if reclaim_ok else 0.0)
        + (6.0 if mid_ok else 0.0), 0.0, 100.0)


def lez_signals(cs, p: Params = P) -> list[Sig]:
    """Every signal the indicator would print, in bar order, with
    blockSignalsInTrade OFF. One pass, mirroring the Pine's bar-by-bar order:
    store pivots -> find the swept level -> validate -> set pending ->
    test confirmation -> cooldown -> clear expired pendings.
    """
    atr = atr_series(cs, p.atr_len)
    ema = ema_series(cs, p.ema_len)
    hi_piv, lo_piv = pivots(cs, p.pivot_len)
    hi_at: dict[int, list] = {}
    lo_at: dict[int, list] = {}
    for c, j, px in hi_piv:
        hi_at.setdefault(c, []).append((j, px))
    for c, j, px in lo_piv:
        lo_at.setdefault(c, []).append((j, px))

    stored_hi: list[tuple[int, float]] = []      # (pivot_bar, price), oldest first
    stored_lo: list[tuple[int, float]] = []
    pend_bull = pend_bear = None                 # dict or None
    last_sig_bar: int | None = None
    out: list[Sig] = []

    for i, c in enumerate(cs):
        # --- pivot storage, with the 20-slot FIFO
        for j, px in hi_at.get(i, []):
            stored_hi.append((j, px))
            del stored_hi[:-p.stored_levels]
        for j, px in lo_at.get(i, []):
            stored_lo.append((j, px))
            del stored_lo[:-p.stored_levels]

        a = atr[i]
        if a <= 0:
            continue
        rng = c.h - c.l
        if rng <= 0:
            continue
        body = abs(c.c - c.o)
        body_pct = body / rng
        up_wick = (c.h - max(c.o, c.c)) / rng
        dn_wick = (min(c.o, c.c) - c.l) / rng
        rng_atr = rng / a
        mid = (c.h + c.l) / 2.0
        min_sweep = p.min_sweep_atr * a

        # --- the newest stored level this bar exceeded by enough
        swept_hi = swept_lo = None
        for j, px in reversed(stored_hi):
            if j < i and c.h > px and (c.h - px) >= min_sweep:
                swept_hi = px
                break
        for j, px in reversed(stored_lo):
            if j < i and c.l < px and (px - c.l) >= min_sweep:
                swept_lo = px
                break

        bear_reclaim = swept_hi is not None and (
            (c.c < swept_hi and c.c < mid) if p.strong_reclaim
            else c.c < swept_hi)
        bull_reclaim = swept_lo is not None and (
            (c.c > swept_lo and c.c > mid) if p.strong_reclaim
            else c.c > swept_lo)

        valid_sell = (bear_reclaim and up_wick >= p.min_wick_pct
                      and body_pct <= p.max_body_pct
                      and rng >= p.min_range_atr * a)
        valid_buy = (bull_reclaim and dn_wick >= p.min_wick_pct
                     and body_pct <= p.max_body_pct
                     and rng >= p.min_range_atr * a)

        e = ema[i]
        ema_known = e is not None
        bull_ema = (not p.use_ema) or (ema_known and c.c > e)
        bear_ema = (not p.use_ema) or (ema_known and c.c < e)
        bull_mid_now = (not p.require_midline) or c.c > mid
        bear_mid_now = (not p.require_midline) or c.c < mid

        # --- pending sweeps. Set BEFORE the window test, exactly as the Pine
        # does, which is why the sweep bar can be its own confirmation bar.
        if valid_buy:
            pend_bull = dict(bar=i, hi=c.h, lo=c.l, mid=mid, level=swept_lo,
                             score=quality(dn_wick, body_pct, rng_atr,
                                           bull_ema, True, bull_mid_now, p))
        if valid_sell:
            pend_bear = dict(bar=i, hi=c.h, lo=c.l, mid=mid, level=swept_hi,
                             score=quality(up_wick, body_pct, rng_atr,
                                           bear_ema, True, bear_mid_now, p))

        bull_open = pend_bull and (i - pend_bull["bar"] <= p.confirm_window)
        bear_open = pend_bear and (i - pend_bear["bar"] <= p.confirm_window)

        buy = bool(bull_open
                   and ((not p.require_bull_body) or c.c > c.o)
                   and bull_ema
                   and ((not p.require_midline) or c.c > pend_bull["mid"]))
        sell = bool(bear_open
                    and ((not p.require_bear_body) or c.c < c.o)
                    and bear_ema
                    and ((not p.require_midline) or c.c < pend_bear["mid"]))

        cool = last_sig_bar is None or (i - last_sig_bar > p.cooldown_bars)
        buy_sig = buy and cool
        sell_sig = sell and cool and not buy_sig      # longs win ties, as in Pine

        for is_long, fired, pend in ((True, buy_sig, pend_bull),
                                     (False, sell_sig, pend_bear)):
            if not fired:
                continue
            entry = c.c
            dist = a * p.stop_atr
            stop = entry - dist if is_long else entry + dist
            # The structural alternative, for arm 4: just beyond the raid
            # extreme, which is where Riptide puts it and where stop_buffer.py
            # found the peak (buffer 0).
            struct = pend["lo"] if is_long else pend["hi"]
            out.append(Sig(bar=i, is_long=is_long, entry=entry, stop=stop,
                           struct_stop=struct, atr=a, sweep_bar=pend["bar"],
                           sweep_hi=pend["hi"], sweep_lo=pend["lo"],
                           level=pend["level"], score=pend["score"],
                           bars_to_confirm=i - pend["bar"]))

        if buy_sig or sell_sig:
            last_sig_bar = i
        if buy_sig or (pend_bull and i - pend_bull["bar"] > p.confirm_window):
            pend_bull = None
        if sell_sig or (pend_bear and i - pend_bear["bar"] > p.confirm_window):
            pend_bear = None
    return out


# -------------------------------------------------------------------- scoring

def score(cs, sigs, horizon: int, *, target_r=P.target_r, structural=False):
    """Attach an Outcome to each signal, dropping the ones whose horizon runs
    off the end of the data.

    The drop is decided by the signal's POSITION, never by how it turned out,
    so it cannot bias the sample. Scoring them instead would mark an open trade
    out at whatever price the fetch happened to stop on, which is noise wearing
    an outcome's clothes.
    """
    kept = []
    for s in sigs:
        if s.bar + 1 + horizon > len(cs):
            continue
        entry, stop = s.entry, s.stop
        if structural:
            # Same entry, stop at the raid extreme. Risk changes, so the target
            # moves with it: this is a different trade, not a better fill.
            stop = s.struct_stop
            if (stop >= entry) if s.is_long else (stop <= entry):
                continue
        o = simulate_market(cs, s.bar, entry, stop, s.is_long,
                            target_r=target_r, horizon_bars=horizon, **FEE)
        if o is None:
            continue
        # The row carries the stop it was SCORED with. Sharing the Sig across
        # arms printed the ATR stop's risk beside the structural arm's returns
        # — two different trades under one risk column, which is exactly the
        # kind of quiet mislabelling this project keeps finding.
        kept.append((replace(s, stop=stop) if structural else s, o))
    return kept


def random_entries(cs, n: int, horizon: int, atr, seed: int):
    """THE CONTROL, and it is the whole difference between three readings of
    a negative number.

    Same symbols, same timeframe, same market-in-at-the-close, same 1.5 ATR
    stop, same 3R target, same fees — entries at uniformly random bars in a
    random direction. It measures what this TRADE SHAPE costs before any
    signal is involved.

      random ~ LEZ            the indicator is neutral; the loss is the shape,
                              not the signal, and the fix is the shape.
      random << LEZ           the signal has real skill that the shape spends.
      random ~ 0 and LEZ < 0  the signal is actively harmful.

    Without this, "-0.12 R" is unreadable. A 3R target on a volatility stop
    taken at market has a cost of its own and it has never been measured here.
    """
    rnd = random.Random(seed)
    lo, hi = 60, len(cs) - horizon - 2
    if hi <= lo or n <= 0:
        return []
    out = []
    for _ in range(n):
        i = rnd.randrange(lo, hi)
        a = atr[i]
        if a <= 0:
            continue
        is_long = rnd.random() < 0.5
        entry = cs[i].c
        stop = entry - a * P.stop_atr if is_long else entry + a * P.stop_atr
        o = simulate_market(cs, i, entry, stop, is_long,
                            target_r=P.target_r, horizon_bars=horizon, **FEE)
        if o is None:
            continue
        out.append((Sig(bar=i, is_long=is_long, entry=entry, stop=stop,
                        struct_stop=stop, atr=a, sweep_bar=i, sweep_hi=cs[i].h,
                        sweep_lo=cs[i].l, level=entry, score=0.0,
                        bars_to_confirm=0), o))
    return out


def serialise(pairs):
    """The chart's default view: blockSignalsInTrade = true. Walk in time
    order and skip any signal that opens while the previous trade is still
    running. Reported on its own because it is the view the strategy was
    judged good on — but it is a path-dependent sample and it is not the
    primary."""
    out, busy_until = [], -1
    for s, o in sorted(pairs, key=lambda x: x[0].bar):
        if s.bar <= busy_until:
            continue
        out.append((s, o))
        busy_until = o.exit_bar if o.exit_bar is not None else s.bar
    return out


# ------------------------------------------------------------------ reporting

HEAD = (f"  {'':<30}{'n':>6}{'win':>7}{'wins':>7}{'stops':>7}{'t/out':>7}"
        f"{'risk':>7}{'R/sig':>9}{'±SE':>7}{'total':>9}")


def line(lab, pairs, note=""):
    """One row of the table the /stats screen is going to grow into: how many
    trades, how many won, how many were STOPPED, how many ran out of time.
    A win rate on its own hides the difference between a 3R target being hit
    and a timeout closing a hair the right side of entry."""
    if len(pairs) < 25:
        print(f"  {lab:<30}{len(pairs):>6}   too few")
        return None
    rs = [o.r for _, o in pairs]
    wins = sum(1 for _, o in pairs if o.exit == "target")
    stops = sum(1 for _, o in pairs if o.exit == "stop")
    outs = sum(1 for _, o in pairs if o.exit == "timeout")
    risk = statistics.fmean(100 * abs(s.entry - s.stop) / s.entry
                            for s, _ in pairs)
    m, se = mean_se(rs)
    print(f"  {lab:<30}{len(pairs):>6}{sum(r > 0 for r in rs) / len(rs):>7.0%}"
          f"{wins:>7}{stops:>7}{outs:>7}{risk:>6.2f}%"
          f"{m:>+9.3f}{se:>7.3f}{sum(rs):>+9.1f}  {note}")
    return m


def decompose(pairs, rand):
    """Split the headline into the part the TRADE SHAPE costs and the part the
    SIGNAL contributes. Without this the headline is unreadable: a market entry
    with a volatility stop and a distant target has a price of its own, and it
    is paid whether the entry was chosen by an indicator or by a coin toss."""
    if len(pairs) < 25 or len(rand) < 25:
        return
    m, se = mean_se([o.r for _, o in pairs])
    rm, rse = mean_se([o.r for _, o in rand])
    d, dse = m - rm, (se ** 2 + rse ** 2) ** 0.5
    print(f"\n  -- what the {m:+.3f} is made of --")
    print(f"    {'trade shape alone (random timing)':<40}{rm:+.3f}")
    print(f"    {'what the signal adds on top':<40}{d:+.3f} ± {dse:.3f}"
          f"   {d / dse:+.1f} SE" if dse else "")


def splits(pairs):
    """The gate. Same sign in both window halves and both symbol halves, or it
    does not pass, however good the headline looks."""
    if not pairs:
        return
    print(f"  {'-- the exit gate: sign must hold on every split --':<30}")
    ms = []
    for lab, pred in (("symbols A", lambda s: s.split_symbol == 0),
                      ("symbols B", lambda s: s.split_symbol == 1),
                      ("window 1st half", lambda s: s.split_window),
                      ("window 2nd half", lambda s: not s.split_window)):
        sub = [(s, o) for s, o in pairs if pred(s)]
        if len(sub) < 25:
            print(f"    {lab:<28} n={len(sub)} too few")
            continue
        m, se = mean_se([o.r for _, o in sub])
        ms.append(m)
        print(f"    {lab:<28} n={len(sub):<5} {m:+.3f} ± {se:.3f}")
    full = mean_se([o.r for _, o in pairs])[0]
    ok = full > 0 and len(ms) == 4 and all(m > 0 for m in ms)
    print(f"    => {'PASSES' if ok else 'FAILS'} the pre-registered Phase 1 gate")


def bucket(lab, pairs, key):
    """Two- or few-way split, printed as R per signal. No verdict attached:
    these are descriptive, and the gate above is the only thing that decides."""
    groups: dict = {}
    for s, o in pairs:
        groups.setdefault(key(s, o), []).append(o.r)
    if len(groups) < 2:
        return
    print(f"  {lab}")
    for k in sorted(groups, key=str):
        v = groups[k]
        if len(v) < 25:
            print(f"    {str(k):<28} n={len(v)} too few")
            continue
        m, se = mean_se(v)
        print(f"    {str(k):<28} n={len(v):<5} {m:+.3f} ± {se:.3f}"
              f"  win {sum(r > 0 for r in v) / len(v):.0%}")


# ------------------------------------------------------------------ collection

async def collect(tf: str, pages: int, sess, syms, hcache: dict):
    """Every signal on every symbol at one timeframe, plus the context each
    pre-registered question needs."""
    horizon = max(1, HORIZON_HOURS * 3600 // BAR_SECONDS[tf])
    all_pairs, struct_pairs, ladders = [], [], {r: [] for r in LADDER}
    rand_pairs = []
    days, overlap_hit, overlap_n, stop_inside = [], 0, 0, 0

    for n, sym in enumerate(syms):
        try:
            cs = await fetch_paged(sess, sym, tf, pages)
            # Daily bars are the same for all three timeframes, so they are
            # fetched once per symbol rather than once per (symbol, timeframe).
            if sym not in hcache:
                hcache[sym] = await fetch_paged(sess, sym, HTF, 1)
            hcs = hcache[sym]
        except Exception:
            continue
        if len(cs) < 300 or len(hcs) < 40:
            continue
        days.append((cs[-1].t - cs[0].t) / 86400)
        hst, hdi = supertrend(hcs), di_direction(hcs)
        mid_t = cs[len(cs) // 2].t

        sigs = lez_signals(cs)
        for s in sigs:
            s.htf_dir = htf_dir_at(hcs, hst, hdi, cs[s.bar].t)
            s.split_symbol = n % 2                      # type: ignore[attr-defined]
            s.split_window = cs[s.bar].t < mid_t        # type: ignore[attr-defined]
            # §1.6: is the ATR stop even beyond the candle that triggered it?
            inside = (s.stop > s.sweep_lo) if s.is_long else (s.stop < s.sweep_hi)
            s.stop_inside = inside                      # type: ignore[attr-defined]

        # Riptide's own signals on the same candles, for the overlap check. A
        # strategy that is mostly the same trades is not a second strategy.
        try:
            early: list = []
            rip = run_engine(sym, cs, CFG, early_out=early)
            rip_keys = set()
            idx = {c.t: i for i, c in enumerate(cs)}
            for x in list(rip) + list(early):
                i = idx.get(x.detected_time)
                if i is not None:
                    for d in (-1, 0, 1):
                        rip_keys.add((i + d, x.is_long))
        except Exception:
            rip_keys = set()

        pairs = score(cs, sigs, horizon)
        for s, _ in pairs:
            overlap_n += 1
            overlap_hit += (s.bar, s.is_long) in rip_keys
            stop_inside += bool(getattr(s, "stop_inside", False))
        all_pairs += pairs
        struct_pairs += score(cs, sigs, horizon, structural=True)
        for r in LADDER:
            ladders[r] += score(cs, sigs, horizon, target_r=r)
        # Matched count per symbol, so the control has the same symbol mix.
        rand_pairs += random_entries(cs, len(pairs), horizon,
                                     atr_series(cs, P.atr_len), seed=n)

    return dict(tf=tf, horizon=horizon, days=days, pairs=all_pairs,
                struct=struct_pairs, ladders=ladders, rand=rand_pairs,
                overlap=(overlap_hit, overlap_n), stop_inside=stop_inside)


def report(d):
    tf, pairs = d["tf"], d["pairs"]
    print(f"\n{'=' * 110}")
    print(f"{tf}   horizon {d['horizon']} bars = {HORIZON_HOURS}h   "
          f"{statistics.median(d['days']):.0f} days x {len(d['days'])} symbols"
          if d["days"] else f"{tf}   no data")
    print("=" * 110)
    if not pairs:
        print("  no signals")
        return
    print(HEAD)
    line("1. ALL setups (primary)", pairs)
    line("   serialised (chart default)", serialise(pairs))
    line("   CONTROL: random entries", d["rand"],
         "same shape, no signal")
    decompose(pairs, d["rand"])
    print()
    splits(pairs)

    print("\n  -- 7. the target ladder, and what it costs --")
    print(HEAD)
    for r in LADDER:
        line(f"   target {r:g}R", d["ladders"][r])

    print("\n  -- 4. ATR stop vs the raid extreme, same signals --")
    print(HEAD)
    line(f"   ATR x {P.stop_atr:g} (as shipped)", pairs)
    line("   just beyond the raid", d["struct"])

    hit, n = d["overlap"]
    print(f"\n  -- 3. stops landing inside the sweep candle: "
          f"{d['stop_inside']}/{n} ({d['stop_inside'] / n:.1%})" if n else "")
    print(f"  -- 8. also a Riptide signal within one bar: "
          f"{hit}/{n} ({hit / n:.1%})" if n else "")

    print()
    bucket("2. same-bar confirmation vs a later one",
           pairs, lambda s, o: "same bar" if s.bars_to_confirm == 0
           else f"+{s.bars_to_confirm} bars")
    bucket("5. daily trend (the +4.5 SE variable this model ignores)",
           pairs, lambda s, o: "agrees" if s.htf_dir == (1 if s.is_long else -1)
           else ("against" if s.htf_dir else "flat"))
    qs = sorted(s.score for s, _ in pairs)
    cut = [qs[len(qs) * k // 3] for k in (1, 2)]
    bucket("6. quality score in terciles (floor is 60, not 0)",
           pairs, lambda s, o: ("low" if s.score < cut[0]
                                else "mid" if s.score < cut[1] else "high"))
    bucket("   direction", pairs, lambda s, o: "long" if s.is_long else "short")


async def main():
    async with aiohttp.ClientSession() as sess:
        syms = (await list_symbols(sess))[:SYMBOLS]
        print(f"Liquidity Entry Zones — Phase 1\n{len(syms)} symbols, "
              f"entry at the confirmation close (taker in), stop "
              f"{P.stop_atr:g} x ATR({P.atr_len}), target {P.target_r:g}R, "
              f"fees {FEE['fee_maker']}/{FEE['fee_taker']}%")
        hcache: dict = {}
        for tf, pages in TFS:
            report(await collect(tf, pages, sess, syms, hcache))


if __name__ == "__main__":
    asyncio.run(main())
