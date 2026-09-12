"""SCALPER LAB — seven 1m models, one pipeline, gross R only.

Riptide Min30 is FROZEN and is the control. Nothing here touches it.

WHY ONE PIPELINE INSTEAD OF SEVEN. Every model in SCALPER.md is the same four
steps with different parts swapped in:

    liquidity level  ->  1m raid  ->  confirmation  ->  first 1m FVG  ->  limit

So the pipeline is written once and the models are combinations. Seven
implementations would mean seven chances for a lookahead bug, and the bug that
matters here is invisible: a level "known" before it was formed, or an entry
filled on the bar that created it, produces beautiful numbers and no warning.

CAUSALITY, WHICH IS THE ONLY THING THAT CAN SILENTLY INVALIDATE ALL OF THIS.
Every step carries the time it became KNOWN, not the time it happened:

  * a pivot at HTF bar i is not known until bar i+right CLOSES. Using it from
    bar i is the classic lookahead and it is worth several free R.
  * the raid must start strictly after the level is known.
  * confirmation must close after the raid bar.
  * the FVG must complete after confirmation.
  * the limit may only fill on a bar that opens after the FVG bar closed.
  * stop and target are checked on the same bar with the STOP WINNING ties.

GROSS R ONLY, AND THAT IS NOT A SHORTCUT. Spread has no history on this
exchange (exchange_surface.out), so a net 1m number cannot be computed from
candles at any effort. scalp_viability.out measured the live cost at ~0.05R
median on qualifying symbols and BTC at 0.23R — but that was one calm snapshot,
and stop-outs happen in the opposite conditions. Anything below is what the
PATTERN is worth before execution, and the branch is judged net only after the
forward spread log has rows.

THE UNIVERSE IS PART OF THE STRATEGY. Admission needs takerFeeRate == 0 and 1m
ATR >= 0.15%, both from scalp_viability: on a fee-paying symbol with a tight
1m ATR the cost ratio is ten times a 30m trade's, which is exactly why 15m
measures net negative in fee_key.out. BTC fails this gate. That is the finding,
not an oversight.

──────────────────────────────────────────────────────────────────────────────
PRE-REGISTERED, BEFORE THE FIRST NUMBER

  PRIMARY. Gross R per trade at each of 0.75 / 1 / 1.25 / 1.5 / 2 R, per model.
  A model is interesting only if it is positive at a target whose R also
  survives the measured cost band.

  THE CONTROL. The same setup traded the OPPOSITE way. If a long-side raid pays
  the same when taken short, the pipeline found volatility, not liquidity. Two
  studies in this project died on this test and it is reported beside every
  number rather than beneath.

  BOTH HALVES, split on fill time. An edge in one half is a non-result.

  A PLACEBO. Entries shuffled to random bars in the same symbol, 100 draws,
  same stop distance and target. A model must beat its own placebo band, not
  zero — a 1m pipeline that simply buys dips in an up-drifting sample will show
  positive R without any edge at all.

  FREE PARAMETERS ARE DECLARED AND HELD OUT. Only LSR-1/3/6 have one (the
  displacement threshold). It is chosen on the FIRST half and read on the
  second, never fitted on the whole. LSR-2/4/5 have none, which is why LSR-2
  leads.

  WHAT WOULD FALSIFY A MODEL: gross R under +0.15 at every target; or inside
  its placebo band; or reversing across halves; or a control that moves as far.

    PYTHONPATH=. python3 research/studies/scalp_lab.py
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import gzip                                             # noqa: E402
import json                                             # noqa: E402
import os                                               # noqa: E402
import random                                           # noqa: E402
import time                                             # noqa: E402

import aiohttp                                          # noqa: E402

from riptide.config import BASE, MIN_VOL_USDT           # noqa: E402
from riptide.exchange import get_json                    # noqa: E402
from riptide.engine import Candle, atr_series           # noqa: E402
from riptide.engine import is_pivot_high, is_pivot_low  # noqa: E402
from research.harness import mean_se                    # noqa: E402

CACHE = os.path.join(os.getenv("RIPTIDE_DEEP_CACHE", "/tmp/deep"), "scalp")
DAYS = 30            # MEXC serves ~31 days of 1m and no more; see fetch note
MAX_BARS = 2000
PACE = 0.15
TIMEOUT = aiohttp.ClientTimeout(total=30)

MIN_ATR_PCT = 0.15          # scalp_viability: below this, costs eat the stop
MIN_BARS = 30000            # of a possible ~43k in 30 days
MAX_SYMBOLS = 25

FILL_BARS = 10              # 1m bars a limit may wait, same rule as Riptide
HORIZON = 120               # 2 hours; a scalp that is not done is a failure
TARGETS = (0.75, 1.0, 1.25, 1.5, 2.0)
PIVOT_L, PIVOT_R = 2, 2     # HTF pivot shape
COOLDOWN_BARS = 30          # per symbol+direction, so one move is one trade
PLACEBO = 100


# ── data ─────────────────────────────────────────────────────────────────────

async def klines(sess, symbol, interval, days=DAYS):
    """Paged at MEXC's 2000-bar ceiling, cached gzipped on disk.

    THREE THINGS HERE ARE SCAR TISSUE FROM THE FIRST RUN, which returned zero
    bars for all 84 symbols and cached the emptiness so a rerun could not
    repair itself:

      1. MEXC SERVES ABOUT 31 DAYS OF 1m AND NO MORE. A window older than that
         returns success=true with an empty body — not an error, just nothing.
         The first version asked for 90 days, started at the oldest end, got
         nothing, and broke out of the loop before reaching the data that does
         exist. An empty window now advances instead of aborting.
      2. IT USES riptide.exchange.get_json, which retries MEXC's in-body 510.
         The first version was raw aiohttp with no throttle handling — the
         exact bug fixed in the live bot hours earlier, reintroduced here.
      3. AN EMPTY RESULT IS NEVER CACHED. Caching a failure turns a transient
         fetch problem into a permanent one.
    """
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, f"{symbol}.{interval}.{days}.json.gz")
    if os.path.exists(path):
        with gzip.open(path, "rt") as f:
            raw = json.load(f)
        if raw:
            return [Candle(*r) for r in raw]
    end = int(time.time())
    step = {"Min1": 60, "Min3": 180, "Min5": 300}[interval]
    cur = end - days * 86400
    got, blanks = {}, 0
    while cur < end and blanks < 4:
        stop = min(cur + MAX_BARS * step, end)
        d = await get_json(sess, f"{BASE}/api/v1/contract/kline/{symbol}",
                           {"interval": interval, "start": cur, "end": stop})
        k = (d or {}).get("data") or {}
        ts = k.get("time") or []
        if not ts:
            blanks += 1
            cur = stop                      # step over the gap, do not abort
            continue
        blanks = 0
        vols = k.get("vol") or [0.0] * len(ts)
        for t, o, h, lo, c, v in zip(ts, k["open"], k["high"], k["low"],
                                     k["close"], vols):
            got[int(t)] = (int(t), float(o), float(h), float(lo), float(c),
                           float(v))
        cur = max(ts) + step
    rows = [got[t] for t in sorted(got)]
    if rows:
        with gzip.open(path, "wt") as f:
            json.dump(rows, f)
    return [Candle(*r) for r in rows]


# ── liquidity sources: each returns (known_at, price, is_high) ───────────────

def liq_pivots(cs, step):
    """HTF swing highs and lows. KNOWN only once the right-hand bars close."""
    out = []
    for i in range(PIVOT_L, len(cs) - PIVOT_R):
        known = cs[i + PIVOT_R].t + step      # the confirming bar has CLOSED
        if is_pivot_high(cs, i, PIVOT_L, PIVOT_R):
            out.append((known, cs[i].h, True))
        if is_pivot_low(cs, i, PIVOT_L, PIVOT_R):
            out.append((known, cs[i].l, False))
    return out


def liq_prev_bar(cs, step):
    """The previous completed HTF bar's high and low. No parameters at all."""
    out = []
    for i in range(len(cs) - 1):
        known = cs[i].t + step
        out.append((known, cs[i].h, True))
        out.append((known, cs[i].l, False))
    return out


def liq_opening_range(cs, step, minutes=60):
    """The first N minutes of each UTC day, known once that window closes."""
    out, day, hi, lo, start = [], None, None, None, None
    for c in cs:
        d = c.t // 86400
        if d != day:
            day, hi, lo, start = d, c.h, c.l, c.t
            continue
        if c.t - start < minutes * 60:
            hi, lo = max(hi, c.h), min(lo, c.l)
        elif hi is not None:
            known = start + minutes * 60
            out.append((known, hi, True))
            out.append((known, lo, False))
            hi = None
    return out


# ── confirmations: given the raid, return the bar index confirmation CLOSED ──

def confirm_reclaim(m, j, is_long, level, atr, k):
    """The raid bar itself closed back through the level. Nothing else."""
    return j


def confirm_mss(m, j, is_long, level, atr, k):
    """A 1m structure shift: close beyond the opposing swing formed BEFORE the
    raid. No threshold — the swing is where it is."""
    lo = max(0, j - 60)
    if is_long:
        ref = max((m[i].h for i in range(lo, j)
                   if is_pivot_high(m, i, 2, 2) and i + 2 < j), default=None)
        if ref is None:
            return None
        for i in range(j + 1, min(j + 30, len(m))):
            if m[i].c > ref:
                return i
    else:
        ref = min((m[i].l for i in range(lo, j)
                   if is_pivot_low(m, i, 2, 2) and i + 2 < j), default=None)
        if ref is None:
            return None
        for i in range(j + 1, min(j + 30, len(m))):
            if m[i].c < ref:
                return i
    return None


def confirm_displacement(m, j, is_long, level, atr, k):
    """A candle whose BODY exceeds k x ATR in the trade's direction.

    k is this lab's only free parameter and it is chosen on the first half and
    read on the second — see the holdout panel.
    """
    for i in range(j, min(j + 20, len(m))):
        a = atr[i] or 0
        if a <= 0:
            continue
        body = m[i].c - m[i].o
        if is_long and body > k * a:
            return i
        if not is_long and -body > k * a:
            return i
    return None


# ── the shared pipeline ──────────────────────────────────────────────────────

class Trade:
    __slots__ = ("sym", "model", "is_long", "fill_t", "entry", "stop",
                 "risk_pct", "r", "bar")


def first_fvg(m, after, is_long):
    """First 3-bar imbalance completing strictly after `after`.

    Returns (bar index, entry price) where entry is the NEAR edge — the first
    price a retrace touches. The favourable far edge would fill less often and
    flatter the result.
    """
    for i in range(after + 2, min(after + 25, len(m))):
        if is_long and m[i].l > m[i - 2].h:
            return i, m[i].l
        if not is_long and m[i].h < m[i - 2].l:
            return i, m[i].h
    return None, None


def simulate(m, fvg_bar, entry, stop, is_long, target_r):
    """Limit fill within FILL_BARS, then stop-or-target. Ties go to the STOP."""
    risk = abs(entry - stop)
    if risk <= 0:
        return None
    fill = None
    for i in range(fvg_bar + 1, min(fvg_bar + 1 + FILL_BARS, len(m))):
        if (is_long and m[i].l <= entry) or (not is_long and m[i].h >= entry):
            fill = i
            break
    if fill is None:
        return None
    tgt = entry + (risk * target_r if is_long else -risk * target_r)
    for i in range(fill, min(fill + HORIZON, len(m))):
        hit_s = m[i].l <= stop if is_long else m[i].h >= stop
        hit_t = m[i].h >= tgt if is_long else m[i].l <= tgt
        if hit_s:
            return fill, -1.0
        # ON THE FILL BAR THE TARGET IS NOT AVAILABLE. The limit filled because
        # this bar traded through the entry, but the bar's extreme may have
        # happened BEFORE that — awarding the target here credits a move that
        # occurred before the position existed. The stop above is still checked
        # on the fill bar, because assuming the adverse side came first is the
        # conservative reading of an unknown intrabar order.
        if hit_t and i > fill:
            return fill, target_r
    last = m[min(fill + HORIZON, len(m)) - 1].c
    return fill, ((last - entry) if is_long else (entry - last)) / risk


def run_model(sym, m, atr, levels, confirm, k, target_r, flip=False,
              min_stop_pct=0.0):
    """One symbol, one model, one target. `flip` trades every setup backwards —
    the control."""
    out = []
    idx = {c.t: i for i, c in enumerate(m)}
    times = [c.t for c in m]
    last_fire = {}
    for known, price, is_high in levels:
        # long setups raid a LOW; short setups raid a HIGH
        is_long = not is_high
        j0 = None
        for t in times:
            if t >= known:
                j0 = idx[t]
                break
        if j0 is None:
            continue
        for j in range(j0, min(j0 + 240, len(m))):
            beyond = m[j].l < price if is_long else m[j].h > price
            back = m[j].c > price if is_long else m[j].c < price
            if not (beyond and back):
                continue
            key = (sym, is_long)
            if j - last_fire.get(key, -10 ** 9) < COOLDOWN_BARS:
                break
            cbar = confirm(m, j, is_long, price, atr, k)
            if cbar is None:
                break
            fb, entry = first_fvg(m, cbar, is_long)
            if fb is None:
                break
            stop = (min(m[x].l for x in range(j, fb + 1)) if is_long
                    else max(m[x].h for x in range(j, fb + 1)))
            stop = stop * (0.9995 if is_long else 1.0005)
            # A FLOOR ON THE STOP, because cost in R is cost%/stop% and the
            # structural stop is whatever the raid happened to be. 0 keeps the
            # original behaviour; see scalp_wide.py for what the floor buys.
            if min_stop_pct > 0:
                floor = entry * min_stop_pct / 100
                stop = (min(stop, entry - floor) if is_long
                        else max(stop, entry + floor))
            d_long = (not is_long) if flip else is_long
            if flip:
                entry, stop = entry, entry + (entry - stop)
            got = simulate(m, fb, entry, stop, d_long, target_r)
            if got:
                fill, r = got
                tr = Trade()
                tr.sym, tr.model, tr.is_long = sym, "", d_long
                tr.fill_t, tr.entry, tr.stop, tr.r, tr.bar = (
                    m[fill].t, entry, stop, r, fill)
                tr.risk_pct = 100 * abs(entry - stop) / entry
                out.append(tr)
                last_fire[key] = j
            break
    return out


def placebo_band(m, trades, target_r, seeds=PLACEBO):
    """Same count, same risk %, random bars. What no-edge looks like here."""
    if not trades or len(m) < 300:
        return None
    rnd = random.Random(20260912)
    means = []
    for _ in range(seeds):
        got = []
        for tr in trades:
            i = rnd.randrange(100, len(m) - HORIZON - 2)
            entry = m[i].c
            risk = entry * tr.risk_pct / 100
            stop = entry - risk if tr.is_long else entry + risk
            res = simulate(m, i - 1, entry, stop, tr.is_long, target_r)
            if res:
                got.append(res[1])
        if got:
            means.append(sum(got) / len(got))
    means.sort()
    if not means:
        return None
    return means[int(len(means) * 0.05)], means[len(means) // 2], \
        means[int(len(means) * 0.95)]


MODELS = [
    ("LSR-2  5m liq -> 1m MSS -> FVG", "Min5", liq_pivots, confirm_mss, False),
    ("LSR-4  prev 5m H/L -> reclaim", "Min5", liq_prev_bar, confirm_reclaim, False),
    ("LSR-5  micro MSS (1m only)", "Min1", liq_pivots, confirm_mss, False),
    ("LSR-1  5m liq -> displacement", "Min5", liq_pivots, confirm_displacement, True),
    ("LSR-3  3m liq -> displacement", "Min3", liq_pivots, confirm_displacement, True),
    ("LSR-6  prev 5m H/L -> displacement", "Min5", liq_prev_bar,
     confirm_displacement, True),
    ("LSR-7  opening range -> reclaim", "Min5", liq_opening_range,
     confirm_reclaim, False),
]


async def qualifying(sess):
    async with sess.get(f"{BASE}/api/v1/contract/detail", timeout=TIMEOUT) as r:
        spec = {d["symbol"]: d for d in json.loads(await r.text())["data"]}
    await asyncio.sleep(PACE)
    async with sess.get(f"{BASE}/api/v1/contract/ticker", timeout=TIMEOUT) as r:
        vol = {t["symbol"]: (t.get("amount24") or 0)
               for t in json.loads(await r.text())["data"]}
    cand = [s for s in spec
            if s.endswith("_USDT") and spec[s].get("state") == 0
            and (spec[s].get("takerFeeRate") or 0) == 0
            and vol.get(s, 0) >= MIN_VOL_USDT]
    cand.sort(key=lambda s: -vol[s])
    return cand, spec, vol


async def main():
    async with aiohttp.ClientSession() as sess:
        cand, spec, vol = await qualifying(sess)
        print("SCALPER LAB — seven 1m models, gross R, Riptide untouched")
        print(f"{len(cand)} zero-taker-fee symbols above "
              f"{MIN_VOL_USDT / 1e6:g}M turnover\n")

        data, kept = {}, []
        for sym in cand:
            if len(kept) >= MAX_SYMBOLS:
                break
            m = await klines(sess, sym, "Min1")
            if len(m) < MIN_BARS:
                print(f"  rejected {sym:<16} only {len(m)} 1m bars")
                continue
            a = atr_series(m, 14)
            px = m[-1].c or 1
            atr_pct = 100 * (sum(a[-500:]) / 500) / px
            if atr_pct < MIN_ATR_PCT:
                print(f"  rejected {sym:<16} 1m ATR {atr_pct:.3f}% "
                      f"< {MIN_ATR_PCT}% — costs would eat the stop")
                continue
            h5 = await klines(sess, sym, "Min5")
            h3 = await klines(sess, sym, "Min3")
            data[sym] = dict(m=m, atr=a, Min5=h5, Min3=h3, Min1=m)
            kept.append(sym)
            print(f"  admitted {sym:<16} 1m ATR {atr_pct:.3f}%  "
                  f"{len(m)} 1m bars")

    print(f"\n{len(kept)} symbols admitted · {DAYS} days of 1m\n")

    # The displacement threshold, chosen on the FIRST half only.
    print(f"{'=' * 98}\nFREE PARAMETER — displacement k, chosen on the first "
          f"half\n{'=' * 98}")
    best_k = 1.0
    if kept:
        sym0 = kept[0]
        half = data[sym0]["m"][len(data[sym0]["m"]) // 2:]
        print(f"  {'k':<6}{'trades':>9}{'gross R @1R':>14}")
        scores = []
        for k in (0.5, 0.75, 1.0, 1.5, 2.0):
            tot = []
            for sym in kept[:6]:
                d = data[sym]
                m = d["m"]
                cut = len(m) // 2
                mm = m[:cut]
                aa = d["atr"][:cut]
                lv = liq_pivots(d["Min5"], 300)
                lv = [x for x in lv if x[0] <= mm[-1].t]
                tot += run_model(sym, mm, aa, lv, confirm_displacement, k, 1.0)
            mr = sum(t.r for t in tot) / len(tot) if tot else 0.0
            scores.append((mr, k, len(tot)))
            print(f"  {k:<6}{len(tot):>9}{mr:>+14.3f}")
        scores = [s for s in scores if s[2] >= 30]
        best_k = max(scores)[1] if scores else 1.0
        print(f"\n  chosen on the first half: k = {best_k}  "
              f"(read on the second half only, never refitted)")

    print(f"\n{'=' * 98}\nRESULTS — gross R per trade, by model and target"
          f"\n{'=' * 98}")
    print("  'ctrl' is the identical setup traded BACKWARDS. If it moves as far")
    print("  as the signal, the pipeline found volatility, not liquidity.\n")

    summary = []
    for name, tf, liqfn, conf, needs_k in MODELS:
        step = {"Min1": 60, "Min3": 180, "Min5": 300}[tf]
        print(f"  {name}")
        print(f"    {'target':<9}{'n':>7}{'gross R':>10}{'SE':>8}{'win%':>7}"
              f"{'ctrl R':>9}{'1st half':>10}{'2nd half':>10}"
              f"{'placebo 5-95':>18}")
        row_best = None
        for tgt in TARGETS:
            allt, ctrl, pb = [], [], []
            for sym in kept:
                d = data[sym]
                m, a = d["m"], d["atr"]
                src = d[tf]
                lv = (liq_opening_range(src, step) if liqfn is liq_opening_range
                      else liqfn(src, step))
                t1 = run_model(sym, m, a, lv, conf, best_k, tgt)
                t2 = run_model(sym, m, a, lv, conf, best_k, tgt, flip=True)
                allt += t1
                ctrl += t2
                band = placebo_band(m, t1, tgt)
                if band:
                    pb.append(band)
            if not allt:
                continue
            mr, se = mean_se([t.r for t in allt])
            cr, _ = mean_se([t.r for t in ctrl]) if ctrl else (0.0, 0.0)
            win = 100 * sum(1 for t in allt if t.r > 0) / len(allt)
            allt.sort(key=lambda t: t.fill_t)
            h = len(allt) // 2
            m1, _ = mean_se([t.r for t in allt[:h]]) if h else (0.0, 0.0)
            m2, _ = mean_se([t.r for t in allt[h:]]) if h else (0.0, 0.0)
            lo = sum(b[0] for b in pb) / len(pb) if pb else 0.0
            hi = sum(b[2] for b in pb) / len(pb) if pb else 0.0
            out = (f"    {tgt:<9g}{len(allt):>7}{mr:>+10.3f}{se:>8.3f}"
                   f"{win:>6.0f}%{cr:>+9.3f}{m1:>+10.3f}{m2:>+10.3f}"
                   f"{lo:>+9.3f}{hi:>+9.3f}")
            beats = mr > hi and m1 > 0 and m2 > 0 and mr > cr
            print(out + ("   <-" if beats else ""))
            if row_best is None or mr > row_best[1]:
                row_best = (tgt, mr, se, len(allt), cr, m1, m2, lo, hi, beats)
        if row_best:
            summary.append((name, row_best))
        print()

    print(f"{'=' * 98}\nVERDICT — a model must clear ALL of it\n{'=' * 98}")
    print(f"  {'model':<38}{'best tgt':>9}{'gross R':>9}{'n':>7}"
          f"{'> ctrl':>8}{'both halves':>13}{'> placebo':>11}{'VERDICT':>10}")
    for name, (tgt, mr, se, n, cr, m1, m2, lo, hi, beats) in summary:
        c1 = "yes" if mr > cr else "NO"
        c2 = "yes" if (m1 > 0 and m2 > 0) else "NO"
        c3 = "yes" if mr > hi else "NO"
        v = "KEEP" if (beats and mr >= 0.15) else "reject"
        print(f"  {name:<38}{tgt:>9g}{mr:>+9.3f}{n:>7}{c1:>8}{c2:>13}"
              f"{c3:>11}{v:>10}")
    print("\n  KEEP needs: beats its control, positive in BOTH halves, above")
    print("  the placebo 95th, and gross R >= 0.15 — the floor below which the")
    print("  unmeasured spread and slippage decide the outcome, not the edge.")


if __name__ == "__main__":
    asyncio.run(main())
