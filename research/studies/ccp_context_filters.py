"""Do order blocks, FVGs or trend filters sort grabs?

Pre-registered in PREREG_ccp_context_filters.md, committed before this ran.

    python3 research/studies/ccp_context_filters.py

Six conditions, all defined in the prereg and none swept here:

    F1  order block   signal bar overlaps the last displaced opposite candle
    F2  FVG           unfilled three-bar gap in the trade's direction
    F3  EMA trend     EMA(50) vs EMA(200) agrees with the trade
    F4  ADX regime    Wilder ADX(14) >= 20, direction-agnostic
    F5  supertrend    Supertrend(10, 3.0) agrees with the trade
    F6  confluence    F1 and F2

Entry, stop, target and horizon are the exit study's X1 arm unchanged, so the
baseline here is that study's baseline and the two are directly comparable.

BAR 6 IS THE ONE THAT MATTERS. Every filter is also applied to seeded
random-bar entries. A trend filter that improves any entry equally has told us
something about the market, not about grabs.
"""
from __future__ import annotations

import asyncio
import collections
import math
import os
import random
import sys

import aiohttp

sys.path.insert(0, ".")
os.environ.setdefault("RIPTIDE_DEEP_CACHE", ".cache/deep")
os.makedirs(os.environ["RIPTIDE_DEEP_CACHE"], exist_ok=True)

from research.data import SYMBOLS                        # noqa: E402
from research.deep import load_universe                  # noqa: E402
from research.harness import simulate_market             # noqa: E402
from audit.ccp_merge_check import atr14                  # noqa: E402
from audit.ccp_at_grabs_check import grabs               # noqa: E402

PIVOT = 3
CCP_BACK = CCP_FWD = 2
ATR_BUF = 0.25
OB_LOOKBACK = 20
EMA_FAST, EMA_SLOW = 50, 200
ADX_LEN, ADX_MIN = 14, 20.0
ST_LEN, ST_MULT = 10, 3.0
MIN_BETS = 200
MDE_CEILING = 0.10
RANDOM_SPAN = 20
DAYS = 333
TFS = (("Min15", 192), ("Min30", 96), ("Min60", 48))
ARMS = ("F1", "F2", "F3", "F4", "F5", "F6")


def ema(vals, n):
    k, out, e = 2.0 / (n + 1), [], None
    for v in vals:
        e = v if e is None else v * k + e * (1 - k)
        out.append(e)
    return out


def adx_wilder(cs, n=ADX_LEN):
    """Wilder's ADX. None until it has enough history to be meaningful."""
    tr, pdm, ndm = [], [], []
    for i, c in enumerate(cs):
        if i == 0:
            tr.append(c.h - c.l)
            pdm.append(0.0)
            ndm.append(0.0)
            continue
        p = cs[i - 1]
        tr.append(max(c.h - c.l, abs(c.h - p.c), abs(c.l - p.c)))
        up, dn = c.h - p.h, p.l - c.l
        pdm.append(up if up > dn and up > 0 else 0.0)
        ndm.append(dn if dn > up and dn > 0 else 0.0)

    def smooth(xs):
        out, s = [], None
        for i, x in enumerate(xs):
            if i < n:
                out.append(None)
                s = x if s is None else s + x
                continue
            if i == n:
                s = s + x
            else:
                s = s - s / n + x
            out.append(s)
        return out

    str_, spdm, sndm = smooth(tr), smooth(pdm), smooth(ndm)
    dx, out, prev = [], [], None
    for i in range(len(cs)):
        if str_[i] is None or not str_[i]:
            dx.append(None)
            out.append(None)
            continue
        pdi = 100.0 * spdm[i] / str_[i]
        ndi = 100.0 * sndm[i] / str_[i]
        d = abs(pdi - ndi) / max(pdi + ndi, 1e-12) * 100.0
        dx.append(d)
        got = [v for v in dx[-n:] if v is not None]
        if len(got) < n:
            out.append(None)
            continue
        prev = sum(got) / n if prev is None else (prev * (n - 1) + d) / n
        out.append(prev)
    return out


def supertrend(cs, a, n=ST_LEN, mult=ST_MULT):
    """Direction only: +1 up, -1 down, None before ATR exists."""
    dirs, up, dn, d = [], None, None, 1
    for i, c in enumerate(cs):
        if a[i] is None:
            dirs.append(None)
            continue
        mid = (c.h + c.l) / 2.0
        bu, bl = mid + mult * a[i], mid - mult * a[i]
        up = bu if up is None else (min(bu, up) if cs[i - 1].c <= up else bu)
        dn = bl if dn is None else (max(bl, dn) if cs[i - 1].c >= dn else bl)
        if c.c > up:
            d = 1
        elif c.c < dn:
            d = -1
        dirs.append(d)
    return dirs


def order_block(cs, gb: int, sig: int, is_long: bool) -> bool:
    """F1, exactly as the prereg defines it."""
    lo = max(gb - OB_LOOKBACK, 1)
    best = None
    for i in range(gb, lo - 1, -1):
        c = cs[i]
        opp = (c.c < c.o) if is_long else (c.c > c.o)
        if not opp:
            continue
        # displaced: some later bar up to the signal broke past it
        disp = any((cs[k].h > c.h) if is_long else (cs[k].l < c.l)
                   for k in range(i + 1, sig + 1))
        if disp:
            best = c
            break
    if best is None:
        return False
    s = cs[sig]
    return s.l <= best.h and s.h >= best.l


def fvg(cs, gb: int, sig: int, is_long: bool) -> bool:
    """F2: an unfilled three-bar gap in the trade's direction."""
    for i in range(max(gb - 1, 1), sig):
        if i + 1 >= len(cs):
            break
        if is_long and cs[i + 1].l > cs[i - 1].h:
            lvl = cs[i - 1].h
            if all(cs[k].l > lvl for k in range(i + 2, sig + 1)):
                return True
        if not is_long and cs[i + 1].h < cs[i - 1].l:
            lvl = cs[i - 1].l
            if all(cs[k].h < lvl for k in range(i + 2, sig + 1)):
                return True
    return False


def clustered(vals, keys):
    n = len(vals)
    if n < 2:
        return (vals[0] if vals else 0.0), float("inf"), n
    m = sum(vals) / n
    by = collections.defaultdict(list)
    for v, k in zip(vals, keys):
        by[k].append(v - m)
    g = len(by)
    if g < 2:
        return m, float("inf"), n
    meat = sum(sum(d) ** 2 for d in by.values())
    return m, math.sqrt(meat * g / max(g - 1, 1)) / n, n


def diff(rows, arm, ctl=False):
    key = "c" + arm if ctl else arm
    rk = "cr" if ctl else "r"
    keep = [(r[rk], (r["sym"], r["t"] // 86400)) for r in rows
            if r.get(key) and r.get(rk) is not None]
    drop = [(r[rk], (r["sym"], r["t"] // 86400)) for r in rows
            if r.get(key) is False and r.get(rk) is not None]
    if not keep or not drop:
        return float("nan"), float("nan"), float("nan"), 0
    mk, sk, nk = clustered([v for v, _ in keep], [k for _, k in keep])
    md, sd, _ = clustered([v for v, _ in drop], [k for _, k in drop])
    se = math.sqrt(sk * sk + sd * sd)
    d = mk - md
    return d, se, mk, nk


def build(cs, a, tf, sym, horizon):
    closes = [c.c for c in cs]
    ef, es = ema(closes, EMA_FAST), ema(closes, EMA_SLOW)
    adx = adx_wilder(cs)
    st = supertrend(cs, a)
    out = []
    for pv, gb, is_high in grabs(cs, PIVOT, PIVOT):
        sig = gb + CCP_FWD
        lo_i, hi_i = gb - CCP_BACK, gb + CCP_FWD
        if lo_i < 0 or sig >= len(cs) - 1 or sig < EMA_SLOW + 5:
            continue
        if a[sig] is None or adx[sig] is None or st[sig] is None:
            continue
        is_long = not is_high
        entry = cs[sig].c
        buf = a[sig] * ATR_BUF
        stop = (min(cs[k].l for k in range(lo_i, hi_i + 1)) - buf if is_long
                else max(cs[k].h for k in range(lo_i, hi_i + 1)) + buf)
        if (stop >= entry) if is_long else (stop <= entry):
            continue
        o = simulate_market(cs, sig, entry, stop, is_long,
                            target_r=2.0, horizon_bars=horizon)
        if o is None:
            continue

        f1 = order_block(cs, gb, sig, is_long)
        f2 = fvg(cs, gb, sig, is_long)
        f3 = (ef[sig] > es[sig]) == is_long
        f4 = adx[sig] >= ADX_MIN
        f5 = (st[sig] > 0) == is_long
        row = {"sym": sym, "t": cs[sig].t, "r": o.r,
               "F1": f1, "F2": f2, "F3": f3, "F4": f4, "F5": f5,
               "F6": f1 and f2, "cr": None}

        # Bar 6's control: the SAME filters evaluated at a random bar, same
        # direction, same risk fraction. If a filter helps here as much as at a
        # grab, it is a fact about the market and not about grabs.
        rnd = random.Random(f"{sym}|{tf}|{gb}")
        frac = abs(entry - stop) / entry
        for _ in range(4):
            j = rnd.randrange(EMA_SLOW + 10, len(cs) - horizon - 1)
            if a[j] is None or adx[j] is None or st[j] is None:
                continue
            e2 = cs[j].c
            s2 = e2 - e2 * frac if is_long else e2 + e2 * frac
            co = simulate_market(cs, j, e2, s2, is_long,
                                 target_r=2.0, horizon_bars=horizon)
            if co is None:
                continue
            c1 = order_block(cs, j, j, is_long)
            c2 = fvg(cs, j, j, is_long)
            row["cr"] = co.r
            row["cF1"] = c1
            row["cF2"] = c2
            row["cF3"] = (ef[j] > es[j]) == is_long
            row["cF4"] = adx[j] >= ADX_MIN
            row["cF5"] = (st[j] > 0) == is_long
            row["cF6"] = c1 and c2
            break
        out.append(row)
    return out


async def main():
    print(__doc__.split("\n\n")[0])
    print("\nPre-registered in PREREG_ccp_context_filters.md. Six arms, six "
          "primary tests,\nabout a 26% chance of one false positive at z >= 2, "
          "so bar 5 alone carries nothing.\n")

    store = {}
    async with aiohttp.ClientSession() as sess:
        for tf, horizon in TFS:
            uni = await load_universe(sess, SYMBOLS, tf, DAYS)
            rows = []
            for sym, cs in uni.items():
                rows += build(cs, atr14(cs), tf, sym, horizon)
            rows.sort(key=lambda r: r["t"])
            store[tf] = rows
            base = [r["r"] for r in rows]
            print(f"{tf}: {len(rows)} grabs, unfiltered R "
                  f"{sum(base)/max(len(base),1):+.3f}")
    print()

    res = {}
    for tf, _ in TFS:
        rows = store[tf]
        if not rows:
            continue
        cut = len(rows) // 2
        print(f"═══ {tf} ═══")
        for half, sl in (("old", rows[:cut]), ("new", rows[cut:])):
            b = [r["r"] for r in sl]
            k = [(r["sym"], r["t"] // 86400) for r in sl]
            bm, bse, _ = clustered(b, k)
            print(f"  {half.upper()}  {len(sl)} bets   unfiltered "
                  f"{bm:+.3f} ± {bse:.3f}")
            for arm in ARMS:
                d, se, m, n = diff(sl, arm)
                cd, _, _, _ = diff(sl, arm, ctl=True)
                z = d / se if se and not math.isnan(se) and se > 0 else float("nan")
                flag = "" if n >= MIN_BETS else f"  BAR 1 FAIL n={n}"
                mde = 2 * se if se and not math.isnan(se) else float("inf")
                if mde > MDE_CEILING:
                    flag += f"  UNDERPOWERED MDE {mde:.2f}"
                print(f"    {arm}  kept {n:>6}  R {m:+.3f}   Δ {d:+.3f}  "
                      f"z {z:+.2f}   control Δ {cd:+.3f}{flag}")
                res[(tf, half, arm)] = (d, m, n, cd, mde)
        print()

    print("═══ VERDICT AGAINST THE PRE-REGISTERED BARS ═══")
    print("Six arms. At z >= 2.0 each the chance of at least one false")
    print("positive is about 26%, so bar 5 alone carries nothing.\n")
    for arm in ARMS:
        cells = [res.get((tf, h, arm)) for tf, _ in TFS for h in ("old", "new")]
        cells = [c for c in cells if c]
        if not cells:
            continue
        newer = [res.get((tf, "new", arm)) for tf, _ in TFS]
        newer = [c for c in newer if c]
        b1 = all(c[2] >= MIN_BETS for c in cells)
        b2 = len({c[0] > 0 for c in cells if not math.isnan(c[0])}) == 1
        b3 = bool(newer) and all(c[0] > 0 for c in newer)
        b4 = bool(newer) and all(c[1] > 0 for c in newer)
        b6 = bool(newer) and all(c[0] > c[3] for c in newer
                                 if not math.isnan(c[3]))
        worst = max(c[4] for c in cells)
        print(f"  {arm}")
        for n_, ok, what in ((1, b1, f"{MIN_BETS}+ kept bets in every panel"),
                             (2, b2, "one sign across six panels"),
                             (3, b3, "beats unfiltered, newer half"),
                             (4, b4, "positive standalone R, newer half"),
                             (6, b6, "beats the same filter on random bars")):
            print(f"      bar {n_}  {'PASS' if ok else 'FAIL'}  {what}")
        print(f"      power   worst MDE {worst:.3f} R"
              + ("  UNDERPOWERED" if worst > MDE_CEILING else "  (adequate)"))
        print(f"      → {'PASSES' if all((b1,b2,b3,b4,b6)) else 'FAILS'}\n")


asyncio.run(main())
