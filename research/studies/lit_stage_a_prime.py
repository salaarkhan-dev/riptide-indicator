"""LIT STAGE A-PRIME — the T8 countertrend question, measured not assumed.

THE CONFLICT [LIT_SOURCE.md Ch.21, recorded as unresolved]. The source states a
with-trend-only rule inside the POI section, but a separate slide shows a BOS
GRAB producing a countertrend reaction toward the opposite pullback. Two
readings, and the source does not choose:

  1. Liquidity Grab Levels are a SEPARATE entry family from POI zones, and the
     with-trend rule was stated inside the POI section only.
  2. A failed BOS sweep is itself the signal that the leg is done.

It decides whether the strategy has one direction rule or two, which is not a
detail.

THIS FILE MEASURES THE EVENT ONLY. No trade arm, no P&L, and nothing here is
ever combined with Stage A. Per the task specification: "Measure first:
opposite pullback reached vs BOS subsequently validly breaks. Do not assume
this is tradeable until measured."

WHY A STRUCTURAL MEASUREMENT IS THE RIGHT SCOPE RIGHT NOW. Stage A returned
INCONCLUSIVE because the specified stop — the IDM raid extreme with no buffer
— is the break bar's own wick, median 0.42% of price and 0.18% at the first
quartile. Every trade arm built on that stop inherits a risk unit that 99% of
losses exceed. A structural race between two price levels has no stop in it
and is unaffected, so it is measurable now while a trade arm is not.

    PYTHONPATH=. RIPTIDE_DEEP_CACHE=/tmp/deep \\
        python3 research/studies/lit_stage_a_prime.py
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import statistics                                       # noqa: E402
from collections import defaultdict                     # noqa: E402

import aiohttp                                          # noqa: E402

from research.deep import load_deep                     # noqa: E402
import research.lit_v3 as L                             # noqa: E402
import research.lit_repl as RP                          # noqa: E402

HORIZON = 500


def races(cs, events, scope):
    """Every BOS GRAB, and what resolved it first.

    A grab is a bar whose extreme reaches the live BOS level while the engine
    does NOT emit a bos_break on that bar — price touched the level and the
    break engine refused it. From there two outcomes are raced:

        OPP_PB   price reaches the most recent opposite-direction pullback
                 pivot (the countertrend hypothesis paying off)
        BOS      the BOS subsequently breaks validly (the grab was noise)

    Whichever comes first wins. Unresolved inside the horizon is recorded
    separately rather than being assigned to either side.
    """
    byBar = defaultdict(list)
    for e in events:
        byBar[e["bar"]].append(e)

    # Forward-filled state, exactly as the engine would have it live.
    bos = bosDir = None
    oppPb = {1: None, -1: None}
    grabs = []
    for i in range(len(cs)):
        broke = False
        for e in byBar.get(i, ()):
            k = e["kind"]
            if k == "pb":
                oppPb[1 if e["dir"] > 0 else -1] = e["px"]
            elif k == "idm_break":
                # A NEW BOS PHASE STARTS HERE, so the opposite pullback must
                # be re-earned inside it. Forward-filling one from an earlier
                # structure put the countertrend target a median 7.76% of
                # price away, which loses every race by construction and
                # measures nothing. Scoped to the live cycle instead.
                bos, bosDir = e["bos"], (1 if e["dir"] > 0 else -1)
                if scope == "cycle":
                    oppPb = {1: None, -1: None}
            elif k == "bos_break":
                broke = True
                bos = None
            elif k == "choch_break":
                bos = None
        if bos is None or broke:
            continue
        up = bosDir > 0
        touched = (cs[i].h >= bos) if up else (cs[i].l <= bos)
        if not touched:
            continue
        # The countertrend target is the opposite-side pullback pivot.
        tgt = oppPb[-bosDir]
        if tgt is None:
            continue
        if (tgt >= bos) if up else (tgt <= bos):
            continue            # not actually on the opposite side
        grabs.append((i, bos, tgt, up))
        bos = None              # one grab per BOS; do not double-count bars
    return grabs


def resolve(cs, events, grabs):
    """Race each grab forward. Returns (opp_first, bos_first, unresolved)."""
    brk = {e["bar"] for e in events if e["kind"] == "bos_break"}
    opp = bosw = unres = 0
    excursions = []
    for i, lvl, tgt, up in grabs:
        hitOpp = hitBos = None
        for k in range(i + 1, min(i + 1 + HORIZON, len(cs))):
            if hitOpp is None:
                if (cs[k].l <= tgt) if up else (cs[k].h >= tgt):
                    hitOpp = k
            if hitBos is None and k in brk:
                hitBos = k
            if hitOpp is not None or hitBos is not None:
                break
        if hitOpp is None and hitBos is None:
            unres += 1
        elif hitBos is None or (hitOpp is not None and hitOpp <= hitBos):
            opp += 1
            excursions.append(abs(lvl - tgt) / lvl * 100.0)
        else:
            bosw += 1
    return opp, bosw, unres, excursions


async def main():
    print("=" * 92)
    print("LIT STAGE A-PRIME — the T8 countertrend question")
    print("=" * 92)
    print("EVENT     a BOS GRAB: price reaches the live BOS level on a bar")
    print("          where the break engine does NOT confirm a break.")
    print("RACE      opposite pullback pivot reached  vs  BOS validly breaks.")
    print("SCOPE     STRUCTURAL ONLY. No entry, no stop, no P&L. Never")
    print("          combined with Stage A. Countertrend is NOT shipped.")
    print("=" * 92)

    tot = defaultdict(lambda: [0, 0, 0, []])
    async with aiohttp.ClientSession() as sess:
        held = (await RP.heldout(sess, skip=len(RP.DISCOVERY), want=70))[:30]
        for tf in RP.TFS:
            for symset, syms in (("discovery", RP.DISCOVERY),
                                 ("held-out", held)):
                for sym in syms:
                    try:
                        cs = await load_deep(sess, sym, tf, days=RP.DAYS)
                    except Exception:
                        continue
                    if len(cs) < 2000:
                        continue
                    m, _i, _d, _g = L.engine(cs)
                    for scope in ("carried", "cycle"):
                        g = [x for x in races(cs, m.events, scope)
                             if x[0] >= RP.WARMUP]
                        o, b, u, ex = resolve(cs, m.events, g)
                        for key in ("ALL", tf, symset):
                            t = tot[(scope, key)]
                            t[0] += o
                            t[1] += b
                            t[2] += u
                            t[3] += ex

    for scope, title in (
            ("carried", "A. opposite pullback CARRIED across cycles"),
            ("cycle", "B. opposite pullback scoped to the LIVE BOS cycle")):
        print(f"\n  {title}")
        print(f"  {'cell':<14}{'grabs':>8}{'OPP PB':>9}{'BOS brk':>9}"
              f"{'opp%':>8}{'unres':>8}")
        any_row = False
        for key in ("ALL", "Min15", "Min30", "Min60", "discovery",
                    "held-out"):
            o, b, u, ex = tot[(scope, key)]
            n = o + b
            if n < 20:
                continue
            any_row = True
            print(f"  {key:<14}{n + u:>8}{o:>9}{b:>9}"
                  f"{100 * o / n:>7.1f}%{u:>8}")
        if not any_row:
            print("  no qualifying grabs at all")
        o, b, u, ex = tot[(scope, "ALL")]
        if ex:
            ex.sort()
            print(f"  distance from BOS level to the target, when reached: "
                  f"median {ex[len(ex) // 2]:.2f}% of price")

    print(f"\n{'=' * 92}\n  READ — T8 IS NOT RESOLVED BY THIS, AND WHY"
          f"\n{'=' * 92}")
    print("  The two definitions BRACKET the source's object without hitting")
    print("  it, and neither result should be quoted as the T8 answer.")
    print()
    print("  A carries a pivot from an earlier structure, so the target sits")
    print("    a median 7.8% of price away and loses the race by construction.")
    print("  B scopes it to the live cycle and finds NO qualifying grabs at")
    print("    all: at the moment of a BOS grab the opposite pullback has not")
    print("    formed yet. It forms during the reaction the grab causes.")
    print()
    print("  So the countertrend target is not a level that exists in")
    print("  lit_v3's event stream when the grab happens. The Pine engine")
    print("  maintains BOTH directions live via the P8 idle observer, which")
    print("  is where its 'BOS near -> Opp PB reach' figure comes from; the")
    print("  Python engine used here does not expose that.")
    print()
    print("  T8 THEREFORE REMAINS UNRESOLVED. Resolving it needs the")
    print("  dual-direction detector ported to Python first. No countertrend")
    print("  behaviour is shipped, and no rate is claimed.")


if __name__ == "__main__":
    asyncio.run(main())
