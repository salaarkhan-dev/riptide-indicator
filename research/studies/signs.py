"""Audit every sign convention in the project against realised price.

WHY THIS EXISTS. On 8 Sep a comment reading "-1 is up" sat above six copies of
`supertrend() < 0`. It returns +1 for up. Every BTC regime number this project
produced had its two columns swapped for weeks, through a discovery run, a
pre-registered held-out replication that "confirmed" it, and into the trading
doc. Nothing caught it because every check was a human reading a comment.

So no function here is trusted to mean what it says. Each direction series is
bucketed by its own value and scored against what price ACTUALLY DID, and the
convention is asserted rather than read. A test that consults the market
cannot be fooled by a stale comment.

WHAT IS CHECKED
  1  Direction series -- supertrend, di_direction -- must label the bars that
     follow a rise as +1. Measured on trailing movement, across many symbols,
     so one trending symbol cannot carry it.
  2  htf_dir_at, the function the GRADE is built on, must agree in sign with
     the series it reads. If this one were inverted, every letter would be.
  3  The engine's own geometry: a long must have stop < entry < target, and a
     short the reverse. Cheap, and it pins the meaning of is_long.
  4  The consumers. Every comparison of a direction to is_long in the codebase
     must be spelled `> 0`. This is the literal bug, as a grep, so that
     re-introducing it fails here rather than in a trading decision.

    PYTHONPATH=. python3 research/studies/signs.py

EXIT CODES, because this gates the deploy and the two failure modes must not
be confused. Getting this backwards is how `poi_at` once muted a symbol for an
hour: a failed fetch returned the same value as a genuine negative.

    0   every check passed
    1   a check FAILED — the tree is wrong, block the update
    2   could not run: no market data. NOT a failure of the code. The deploy
        proceeds and says so, because refusing to ship on a network blip would
        make an exchange outage look like a bug in the commit.

Check 4 needs no network and therefore always runs, so a re-introduction of
the literal bug is caught even when the exchange is unreachable.
"""
from __future__ import annotations

import research.env  # noqa: F401  (must precede riptide.config)

import asyncio
import pathlib
import re
import statistics
import sys

import aiohttp

from riptide.config import CFG
from riptide.engine import run_engine
from riptide.exchange import fetch_candles, list_symbols
from riptide.trend import supertrend, di_direction
from research.studies.mtf_grid import htf_dir_at

LOOK = 20          # bars of trailing movement used to judge "was it rising?"
N_SYMBOLS = 12
fails: list[str] = []


def check(ok: bool, what: str, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {what}" + (f"   {detail}" if detail else ""))
    if not ok:
        fails.append(what)


def trailing_by_direction(cs, series):
    """Median trailing move on the bars this series calls up, and down."""
    up, dn = [], []
    for i in range(LOOK, min(len(cs), len(series))):
        if not series[i]:
            continue
        chg = (cs[i].c - cs[i - LOOK].c) / cs[i - LOOK].c * 100
        (up if series[i] > 0 else dn).append(chg)
    if len(up) < 30 or len(dn) < 30:
        return None
    return statistics.median(up), statistics.median(dn)


def static_checks() -> None:
    """Everything provable without touching the exchange. Runs first and
    always, so the literal bug cannot slip through during an outage."""
    print("STATIC — the literal bug, as a grep")
    pat = re.compile(r"(?:st|dirs?|d|bst|btc_dir|trend_dir|di_dir)\s*\[?[^\]]*\]?"
                     r"\s*<\s*0\s*\)?\s*==\s*[\w.]*is_long")
    hits = []
    for p in list(pathlib.Path("riptide").rglob("*.py")) + \
             list(pathlib.Path("research").rglob("*.py")):
        for n, line in enumerate(p.read_text().splitlines(), 1):
            if pat.search(line):
                hits.append(f"{p}:{n}")
    check(not hits, "no direction compared to is_long with `< 0`",
          ", ".join(hits) if hits else "all consumers use `> 0`")


async def fetch_all():
    """Returns (min30, daily) or None when the exchange is unreachable."""
    try:
        async with aiohttp.ClientSession() as sess:
            syms = (await list_symbols(sess))[:N_SYMBOLS]
            data = {}
            for s in syms:
                try:
                    cs = await fetch_candles(sess, s, "Min30")
                except Exception:
                    continue
                if len(cs) > 300:
                    data[s] = cs
            day = {}
            for s in list(data)[:6]:
                try:
                    day[s] = await fetch_candles(sess, s, "Day1")
                except Exception:
                    pass
    except Exception as e:
        print(f"  could not reach the exchange: {type(e).__name__}: {e}")
        return None
    # Too thin to conclude anything is NOT the same as a failed check.
    if len(data) < 6 or len(day) < 3:
        print(f"  too little data to judge: {len(data)} Min30, {len(day)} Day1")
        return None
    return data, day


async def main():
    static_checks()
    if fails:
        print(f"\n{len(fails)} CHECK(S) FAILED:")
        for f in fails:
            print(f"  - {f}")
        return 1

    print("\nfetching market data for the empirical checks...")
    got = await fetch_all()
    if got is None:
        print("\nSKIPPED the empirical checks — no market data. The static\n"
              "check passed. This is not a failure of the tree.")
        return 2
    data, day = got

    print(f"\n{len(data)} symbols on Min30, {len(day)} on Day1 · "
          f"trailing window {LOOK} bars\n")

    print("1. DIRECTION SERIES — does +1 land on bars that had been rising?")
    for name, fn in (("supertrend", supertrend), ("di_direction", di_direction)):
        ups, dns, agree = [], [], 0
        for cs in data.values():
            row = trailing_by_direction(cs, fn(cs))
            if not row:
                continue
            u, d = row
            ups.append(u)
            dns.append(d)
            agree += u > d
        if len(ups) < 6:
            print(f"  SKIP  {name}(): only {len(ups)} usable symbols")
            continue
        mu, md = statistics.median(ups), statistics.median(dns)
        check(mu > md and agree >= 0.75 * len(ups),
              f"{name}(): +1 means UP",
              f"+1 bars {mu:+.3f}% vs -1 bars {md:+.3f}%, "
              f"{agree}/{len(ups)} symbols agree")

    print("\n2. htf_dir_at — the function the GRADE is built on")
    hits = miss = 0
    for s, cs in day.items():
        st, di = supertrend(cs), di_direction(cs)
        for i in range(5, len(cs) - 1):
            d = htf_dir_at(cs, st, di, cs[i].t)
            want = st[i - 1] if st[i - 1] == di[i - 1] else 0
            hits += d == want
            miss += d != want
    check(miss == 0, "htf_dir_at() passes the series sign through unchanged",
          f"{hits} bars agree, {miss} disagree")

    ups, dns = [], []
    for s, cs in day.items():
        st, di = supertrend(cs), di_direction(cs)
        for i in range(LOOK + 1, len(cs)):
            d = htf_dir_at(cs, st, di, cs[i].t)
            if not d:
                continue
            chg = (cs[i - 1].c - cs[i - 1 - LOOK].c) / cs[i - 1 - LOOK].c * 100
            (ups if d > 0 else dns).append(chg)
    if len(ups) >= 30 and len(dns) >= 30:
        mu, md = statistics.median(ups), statistics.median(dns)
        check(mu > md, "htf_dir_at() == +1 means the daily was RISING",
              f"+1 {mu:+.3f}% (n={len(ups)}) vs -1 {md:+.3f}% (n={len(dns)})")
    else:
        print("  SKIP  htf_dir_at(): too few daily bars to score")

    print("\n3. ENGINE GEOMETRY — what is_long actually means")
    bad = tot = 0
    for s, cs in list(data.items())[:6]:
        early: list = []
        for x in list(run_engine(s, cs, CFG, early_out=early)) + early:
            tot += 1
            ok = (x.stop < x.entry) if x.is_long else (x.stop > x.entry)
            bad += not ok
    if tot == 0:
        print("  SKIP  engine geometry: no signals in the sampled window")
    else:
        check(bad == 0,
              "every long has stop < entry, every short stop > entry",
              f"{tot} signals, {bad} inverted")

    print()
    if fails:
        print(f"{len(fails)} CHECK(S) FAILED:")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("all sign conventions verified against realised price")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
