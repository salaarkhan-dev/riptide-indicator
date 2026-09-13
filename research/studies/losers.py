"""How losing trades actually fail. Diagnosis, not a filter hunt.

Twenty-one attempts to find something that separates winners from losers
BEFORE the fact have failed. This asks a different question: given that a
trade lost, what happened — was the entry wrong, the stop wrong, or the
market simply against it?

    PYTHONPATH=. python3 research/studies/losers.py
"""
import research.env                                     # noqa: F401  MUST be first
import asyncio, statistics, time                        # noqa: E402
from collections import Counter                         # noqa: E402

from riptide.config import TRACK_TARGET_R               # noqa: E402
from research.data import load                          # noqa: E402

TGT = TRACK_TARGET_R


def after_stop(r):
    """Once stopped, did price still reach the original target inside the
    horizon? If it usually did, the stop is the problem, not the entry."""
    cs, sg = r.candles, r.signal
    risk = abs(sg.entry - sg.stop)
    s = 1 if sg.is_long else -1
    tgt = sg.entry + s * risk * TGT
    i0 = next((i for i, c in enumerate(cs) if c.t == r.exit_time), None)
    if i0 is None:
        return None
    for c in cs[i0 + 1:i0 + 60]:
        if (c.h >= tgt) if sg.is_long else (c.l <= tgt):
            return True
    return False


def bars_held(r):
    cs = r.candles
    a = next((i for i, c in enumerate(cs) if c.t == r.fill_time), None)
    b = next((i for i, c in enumerate(cs) if c.t == r.exit_time), None)
    return None if a is None or b is None else b - a


def pct(n, d):
    return f"{100 * n / d:.0f}%" if d else "-"


async def main():
    rows = await load(target_r=TGT, fee_maker=0.02, fee_taker=0.06)
    for kind in ("confirmed", "early"):
        sub = [r for r in rows if r.kind == kind and r.filled and r.exit_time]
        lose = [r for r in sub if r.r < 0]
        win = [r for r in sub if r.r > 0]
        print(f"\n{'='*64}\n{kind.upper()}  {len(sub)} filled · "
              f"{len(win)} winners · {len(lose)} losers\n{'='*64}")

        # 1. how far into profit did losers get?
        buckets = Counter()
        for r in lose:
            m = r.mfe
            buckets["never in profit" if m < 0.05 else
                    "under 0.5R" if m < 0.5 else
                    "0.5 - 1R" if m < 1.0 else
                    "1 - 1.5R" if m < 1.5 else
                    f"1.5R+ (target was {TGT:g})"] += 1
        print("\n  how far losers got before stopping")
        for k in ("never in profit", "under 0.5R", "0.5 - 1R", "1 - 1.5R",
                  f"1.5R+ (target was {TGT:g})"):
            if buckets[k]:
                print(f"    {k:<28}{buckets[k]:>5}  {pct(buckets[k], len(lose))}")

        # 2. was the stop the problem?
        reached = [after_stop(r) for r in lose]
        ok = [x for x in reached if x is not None]
        print(f"\n  after the stop, price still reached {TGT:g}R: "
              f"{sum(ok)} of {len(ok)}  ({pct(sum(ok), len(ok))})")

        # 3. how long do they take to die?
        held_l = [b for b in (bars_held(r) for r in lose) if b is not None]
        held_w = [b for b in (bars_held(r) for r in win) if b is not None]
        if held_l and held_w:
            print(f"  bars held — losers median {statistics.median(held_l):.0f}, "
                  f"winners median {statistics.median(held_w):.0f}")
            fast = sum(1 for b in held_l if b <= 3)
            print(f"  stopped within 3 bars of filling: {fast}  "
                  f"({pct(fast, len(held_l))})")

        # 4. do losers cluster in time? one market move, not N bad signals
        days = Counter(time.strftime("%d %b", time.gmtime(r.fill_time)) for r in lose)
        top = days.most_common(5)
        share = sum(n for _, n in top)
        print(f"\n  worst 5 days hold {share} of {len(lose)} losers "
              f"({pct(share, len(lose))}): "
              + ", ".join(f"{d} {n}" for d, n in top))
        hours = Counter(time.gmtime(r.fill_time).tm_hour // 6 for r in lose)
        print("  by 6h block (UTC): "
              + "  ".join(f"{h*6:02d}-{h*6+6:02d}h {hours[h]}" for h in range(4)))

        # 5. winners vs losers, on things known at entry
        print("\n  winners vs losers, on what was knowable at the entry")
        for lab, fn in (("median stop %", lambda r: r.risk_pct),
                        ("median bars to fill",
                         lambda r: next((i for i, c in enumerate(r.candles)
                                         if c.t == r.fill_time), 0) - r.bar)):
            a = statistics.median([fn(r) for r in win])
            b = statistics.median([fn(r) for r in lose])
            print(f"    {lab:<24}winners {a:>7.2f}   losers {b:>7.2f}")

asyncio.run(main())
