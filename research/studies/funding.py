"""DOES THE FUNDING RATE AT SIGNAL TIME PREDICT ANYTHING?

WHY THIS IS ASKABLE AT ALL. riptide/market.py said for months that funding
"cannot be backtested at all — not with more effort, not with a better script",
and that was simply false: /api/v1/contract/funding_rate/history is public and
carries 539 days, longer than the 333-day window every study here runs on. This
is the study that claim was preventing.

WHAT FUNDING IS. A perpetual has no expiry, so an 8-hourly payment keeps it
pinned to spot. Positive funding: longs pay shorts, which happens when the perp
trades above index — crowded long. Negative: shorts pay longs — crowded short.
It is a direct, public read on positioning, which is why it is worth asking.

THE TWO STORIES ARE OPPOSITE, AND THAT IS THE WARNING.

    SQUEEZE     A long into NEGATIVE funding has fuel: shorts are crowded and
                pay to stay, so a move up forces them out.
    TREND       A long into POSITIVE funding is confirmed: the crowd and the
                trend agree, and paying to hold is what conviction looks like.

Both are plausible, both are widely believed, and they predict opposite signs.
Anything that can be explained either way explains nothing in advance — so the
sign is not a prediction here, it is the thing being measured, and the control
below is what decides whether either story survives.

THE PRIOR IS BAD AND SHOULD BE STATED FIRST. Twenty-one entry filters have
failed in this project. Funding is among the most watched numbers in crypto,
which is exactly the kind of input least likely to carry unpriced information.
The base rate for this working is low, and the purpose of running it is that it
is now cheap to ask rather than that it is likely to pay.

──────────────────────────────────────────────────────────────────────────────
PRE-REGISTERED, BEFORE THE FIRST NUMBER

  PRIMARY. Net R per trade on the PICKED stream (what phase 2 will actually
  trade), split into quintiles of the funding rate in force at signal time,
  reported separately for LONG and SHORT signals. The claim, if any, is about
  what the bot should skip.

  THE CONTROL, AND IT IS WHAT MATTERS. The same split on the OPPOSITE
  direction. If low funding helps longs AND helps shorts equally, the mechanism
  is not positioning — it is whatever both share, most likely a volatility or
  trend regime. The exhaustion study died on exactly this test and it is the
  reason this one reports the control beside every number rather than beneath.

  SECONDARY. The full SENT stream, which has three times the trades and can see
  an effect the picked stream is too thin for.

  BOTH HALVES of the window, for every cut. An effect living in one half is a
  non-result here as everywhere else.

  A PLACEBO FLOOR. The funding values are shuffled across signals 200 times,
  keeping the distribution and destroying the pairing. The real top-minus-
  bottom difference is reported as a percentile of that null. A result inside
  the null band is noise no matter how large it looks, and with five quintiles
  x two directions x two streams the table takes twenty looks — roughly one
  will clear 2 SE by chance.

  ALSO REPORTED, because the crowding story is about extremes rather than sign:
  the top and bottom DECILE against everything else, and a per-symbol
  percentile version that removes symbols whose funding is structurally high.

  WHAT WOULD FALSIFY IT: no monotone relationship across quintiles; or one that
  reverses between halves; or one whose control moves as much as the signal.

CAUSALITY IS THE WHOLE IMPLEMENTATION RISK. Funding settles every 8 hours. A
signal at time t must be joined to the most recent settlement AT OR BEFORE t —
never the one after, which is partly determined by the move the signal is
trying to predict. A lookahead here would make every number below meaningless
and would look completely normal. `funding_at` below is bisect-right minus one
and nothing else, for that reason.

    PYTHONPATH=. RIPTIDE_DEEP_CACHE=/tmp/deep \
        python3 research/studies/funding.py
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import json                                             # noqa: E402
import os                                               # noqa: E402
import random                                           # noqa: E402
from bisect import bisect_right                         # noqa: E402

import aiohttp                                          # noqa: E402

from riptide.config import BASE, BAR_SECONDS            # noqa: E402
from research.deep import load_universe                 # noqa: E402
from research.studies.poi_tf import DAY, DAYS, H8       # noqa: E402
from research.studies.poi_tf import collect, context, universe  # noqa: E402
from research.studies.pick_rule import TFS, pick_rolling  # noqa: E402
from research.studies.band_key import COOLDOWN, KEYS    # noqa: E402
from research.harness import mean_se                    # noqa: E402

CACHE = os.getenv("RIPTIDE_DEEP_CACHE", "/tmp/deep")
PACE = 0.7
SEEDS = 200


# ── the funding history ──────────────────────────────────────────────────────

async def fetch_funding(sess, symbol, pages=12):
    """Every settlement for one symbol, newest first, flattened to (t, rate)."""
    out = []
    for page in range(1, pages + 1):
        url = (f"{BASE}/api/v1/contract/funding_rate/history"
               f"?symbol={symbol}&page_num={page}&page_size=100")
        try:
            async with sess.get(url, timeout=aiohttp.ClientTimeout(total=20)) as r:
                d = json.loads(await r.text())
        except Exception:
            break
        if not (isinstance(d, dict) and d.get("success")):
            break
        data = d.get("data") or {}
        rows = data.get("resultList") or []
        out += [(int(x["settleTime"]) // 1000, float(x["fundingRate"]))
                for x in rows]
        await asyncio.sleep(PACE)
        if page >= (data.get("totalPage") or 1):
            break
    out.sort()
    return out


async def funding_table(sess, symbols):
    """{symbol: ([times], [rates])}, cached on disk — it is ~600 requests."""
    path = os.path.join(CACHE, "funding.json")
    if os.path.exists(path):
        raw = json.load(open(path))
        if all(s in raw for s in symbols):
            return {s: (raw[s][0], raw[s][1]) for s in raw}
    raw = {}
    for i, s in enumerate(symbols):
        rows = await fetch_funding(sess, s)
        raw[s] = ([t for t, _ in rows], [v for _, v in rows])
        print(f"    funding {i + 1}/{len(symbols)} {s}: {len(rows)} settlements")
    os.makedirs(CACHE, exist_ok=True)
    json.dump(raw, open(path, "w"))
    return raw


def funding_at(table, sym, t):
    """The rate in force at time t. STRICTLY causal: the last settlement at or
    before t, never the next one. Returns None when the symbol has no history
    covering t, which must stay distinct from a rate of zero."""
    got = table.get(sym)
    if not got:
        return None
    times, rates = got
    i = bisect_right(times, t) - 1
    return rates[i] if 0 <= i < len(rates) else None


# ── the cuts ─────────────────────────────────────────────────────────────────

def quintiles(vals):
    s = sorted(vals)
    return [s[int(len(s) * f)] for f in (0.2, 0.4, 0.6, 0.8)] if s else []


def bucket_of(v, edges):
    i = 0
    for e in edges:
        if v > e:
            i += 1
    return i


def block(title, rows, key, edges, labels):
    """One table per cut.

    EACH DIRECTION IS MEASURED AGAINST ITS OWN BASELINE, and the first version
    of this function did not do that. It printed long R beside short R and
    called the second one a control, which it is not: shorts out-scored longs
    in every single bucket, so the comparison only said "shorts did better in
    this window" — a fact about the window, not about funding.

    The question funding actually poses is whether a bucket moves a direction
    away from ITS OWN average. And the signature of real positioning
    information is specific: as funding goes from negative (crowded shorts) to
    positive (crowded longs), the long delta and the short delta must move in
    OPPOSITE directions. Two columns drifting the same way is a shared regime.
    """
    longs = [r.r for r in rows if r.is_long]
    shorts = [r.r for r in rows if not r.is_long]
    bl = sum(longs) / len(longs) if longs else 0.0
    bs = sum(shorts) / len(shorts) if shorts else 0.0
    print(f"\n  {title}")
    print(f"    baseline: all longs {bl:+.3f} (n={len(longs)}), "
          f"all shorts {bs:+.3f} (n={len(shorts)})")
    print(f"    {'bucket':<22}{'nL':>5}{'long R':>9}{'vs base':>9}"
          f"{'nS':>6}{'short R':>9}{'vs base':>9}{'L-S spread':>12}")
    out = []
    for b, lab in enumerate(labels):
        sel = [r for r in rows if key(r) is not None
               and bucket_of(key(r), edges) == b]
        L = [r.r for r in sel if r.is_long]
        S = [r.r for r in sel if not r.is_long]
        if not L and not S:
            continue
        m1 = sum(L) / len(L) if L else 0.0
        m2 = sum(S) / len(S) if S else 0.0
        d1, d2 = m1 - bl, m2 - bs
        out.append((lab, len(L), d1, len(S), d2))
        print(f"    {lab:<22}{len(L):>5}{m1:>+9.3f}{d1:>+9.3f}"
              f"{len(S):>6}{m2:>+9.3f}{d2:>+9.3f}{d1 - d2:>+12.3f}")
    return out


def placebo(rows, key, edges, n_bucket):
    """Where the real top-minus-bottom sits against a shuffled null."""
    live = [(key(r), r.r) for r in rows if key(r) is not None]
    if len(live) < 50:
        return None
    def spread(pairs):
        lo = [r for v, r in pairs if bucket_of(v, edges) == 0]
        hi = [r for v, r in pairs if bucket_of(v, edges) == n_bucket - 1]
        if not lo or not hi:
            return 0.0
        return sum(hi) / len(hi) - sum(lo) / len(lo)
    real = spread(live)
    vals = [v for v, _ in live]
    rs = [r for _, r in live]
    rnd = random.Random(20260912)
    null = []
    for _ in range(SEEDS):
        rnd.shuffle(vals)
        null.append(spread(list(zip(vals, rs))))
    null.sort()
    pct = 100.0 * sum(1 for x in null if x < real) / len(null)
    return real, null[int(SEEDS * 0.05)], null[SEEDS // 2], null[int(SEEDS * 0.95)], pct


async def main():
    by_tf = {}
    async with aiohttp.ClientSession() as sess:
        syms = await universe(sess)
        zday = await context(sess, syms, DAY)
        z8h = await context(sess, syms, H8)
        for tf in TFS:
            cs = await load_universe(
                sess, syms, tf, DAYS,
                min_bars=int(0.8 * DAYS * 86400 // BAR_SECONDS[tf]))
            r = await collect(sess, cs, zday, z8h, interval=tf)
            by_tf[tf] = [t for t in r if t.filled and t.exit_t is not None]
        print("  fetching funding history…")
        table = await funding_table(sess, syms)

    sent = [t for tf in TFS for t in by_tf[tf] if t.day]
    picks = pick_rolling(sent, KEYS["A  tf > band > confd  (shipped)"], COOLDOWN)
    pick_ids = {id(t) for t in picks}

    # SIDE TABLES, NOT ATTRIBUTES. poi_tf.T declares __slots__, so t.fr = ...
    # raises AttributeError. Keyed by id(t), which is safe because `sent` holds
    # every row alive for the life of this function.
    FR, FRP = {}, {}
    per_sym = {}
    for t in sent:
        v = funding_at(table, t.sym, t.t)
        if v is not None:
            FR[id(t)] = v
            per_sym.setdefault(t.sym, []).append(v)
    ranked = {s: sorted(v) for s, v in per_sym.items()}
    for t in sent:
        v = FR.get(id(t))
        if v is not None:
            col = ranked[t.sym]
            FRP[id(t)] = bisect_right(col, v) / max(len(col), 1)

    fr_of = lambda r: FR.get(id(r))      # noqa: E731
    frp_of = lambda r: FRP.get(id(r))    # noqa: E731
    have = [t for t in sent if id(t) in FR]
    print(f"\nFUNDING AT SIGNAL TIME — does it predict anything?")
    print(f"{len(syms)} symbols · {DAYS} days · {'+'.join(TFS)}")
    print(f"{len(sent)} sent, {len(picks)} picked · funding matched on "
          f"{len(have)} ({100 * len(have) / max(len(sent), 1):.0f}%)")
    if have:
        fr = sorted(FR[id(t)] for t in have)
        print(f"funding range: {fr[0]:+.5f} … {fr[-1]:+.5f} per 8h "
              f"(median {fr[len(fr) // 2]:+.6f})")
    print("\nEach direction is measured against ITS OWN baseline, because shorts")
    print("out-scored longs in every bucket and comparing the two columns would")
    print("only restate that. THE SIGNATURE OF REAL POSITIONING INFORMATION is")
    print("that as funding rises the long delta and the short delta move in")
    print("OPPOSITE directions. Both drifting the same way is a shared regime,")
    print("which is how the exhaustion study died.")

    edges = quintiles([FR[id(t)] for t in have])
    labels = ["Q1 most negative", "Q2", "Q3", "Q4", "Q5 most positive"]
    pedges = [0.2, 0.4, 0.6, 0.8]
    plabels = ["P1 lowest for sym", "P2", "P3", "P4", "P5 highest for sym"]

    pick_rows = [t for t in have if id(t) in pick_ids]
    print(f"\n{'=' * 92}\nPRIMARY — THE 🎯 PICKS ({len(pick_rows)} with funding)"
          f"\n{'=' * 92}")
    block("raw funding quintile", pick_rows, fr_of, edges, labels)
    block("per-symbol percentile", pick_rows, frp_of, pedges, plabels)

    print(f"\n{'=' * 92}\nSECONDARY — EVERY ALERT SENT ({len(have)})\n{'=' * 92}")
    block("raw funding quintile", have, fr_of, edges, labels)
    block("per-symbol percentile", have, frp_of, pedges, plabels)

    print(f"\n{'=' * 92}\nPLACEBO FLOOR — top quintile minus bottom, against "
          f"{SEEDS} shuffles\n{'=' * 92}")
    print(f"  {'stream':<26}{'real':>9}{'null 5th':>10}{'median':>9}"
          f"{'95th':>9}{'percentile':>12}")
    for lab, rows in (("picks, longs", [r for r in pick_rows if r.is_long]),
                      ("picks, shorts", [r for r in pick_rows if not r.is_long]),
                      ("sent, longs", [r for r in have if r.is_long]),
                      ("sent, shorts", [r for r in have if not r.is_long])):
        got = placebo(rows, fr_of, edges, 5)
        if got:
            real, lo, med, hi, pct = got
            flag = "" if lo <= real <= hi else "   <- outside the null band"
            print(f"  {lab:<26}{real:>+9.3f}{lo:>+10.3f}{med:>+9.3f}"
                  f"{hi:>+9.3f}{pct:>11.0f}%{flag}")

    print(f"\n{'=' * 92}\nBOTH HALVES — an effect in one half is a non-result"
          f"\n{'=' * 92}")
    ok = sorted(have, key=lambda r: r.fill_t or 0)
    mid = ok[len(ok) // 2].fill_t
    for lab, part in (("FIRST half", [r for r in have if (r.fill_t or 0) <= mid]),
                      ("SECOND half", [r for r in have if (r.fill_t or 0) > mid])):
        sub = [r for r in part if id(r) in pick_ids]
        print(f"\n  ── {lab}: {len(sub)} picks, {len(part)} sent ──")
        block(f"picks, raw quintile", sub, fr_of, edges, labels)

    print(f"\n{'=' * 92}\nEXTREMES — the crowding story is about tails, not sign"
          f"\n{'=' * 92}")
    if have:
        fr = sorted(FR[id(t)] for t in have)
        d1, d9 = fr[len(fr) // 10], fr[9 * len(fr) // 10]
        for lab, rows in (("picks", pick_rows), ("sent", have)):
            for name, sel in (("bottom decile", lambda r: fr_of(r) <= d1),
                              ("middle 80%", lambda r: d1 < fr_of(r) < d9),
                              ("top decile", lambda r: fr_of(r) >= d9)):
                same = [r.r for r in rows if sel(r) and r.is_long]
                opp = [r.r for r in rows if sel(r) and not r.is_long]
                if not same and not opp:
                    continue
                m1, s1 = mean_se(same) if same else (0, 0)
                m2, s2 = mean_se(opp) if opp else (0, 0)
                print(f"  {lab:<7}{name:<16}long n={len(same):>5} {m1:>+7.3f}"
                      f" ±{s1:.3f}   short n={len(opp):>5} {m2:>+7.3f} ±{s2:.3f}")
            print()


if __name__ == "__main__":
    asyncio.run(main())
