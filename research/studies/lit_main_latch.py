"""MAIN STRUCTURE LATCHES. A trap state in the frozen LIT engine.

Found while designing the inducement measurement, not looked for. It is
reported first because every candidate inducement definition that reads Main
structure is downstream of it.

THE CLAIM

    `PH_SEEK` with no CHoCH is a one-way door. Its only exit is a BOS break,
    and if that BOS is never broken the Main context emits nothing for the
    rest of the chart.

WHY THE FIRST CYCLE IS THE ONLY ONE THAT CAN TRAP

The CHoCH level is created at step 7, *when a BOS breaks*:

    # 7. BOS - continuation.
    if not moved and x.bos.ready(i) and brk_step(x.bos.b, o, h, l, c):
        newCh = x.phLo if x.dir == DIR_BULL else x.phHi
        x.ch.set(newCh, ...)

So after bootstrap the very first BOS has no opposing boundary. Step 8 (CHoCH,
the only event allowed to flip the trend) needs `x.ch.ready(i)`, which needs
`x.ch.on`. Step 5 will not publish a new IDM outside DISCOVER/TRACK — it caches
it as `latent_cached`. There is no timeout and no invalidation.

Every later cycle owns both boundaries and can race between them. The bootstrap
cycle cannot. That is why every latched symbol below latches between bar 20 and
bar 164 and never recovers.

TWO DIFFERENT TRIGGERS, ONE DEAD END

    BNB, TIA   price topped out 4.2% and 2.7% BELOW the BOS and stayed there
               for 333 days. The market never delivered it.
    ONDO, BTC  price DID trade through the level - and 3 bars and 1 bar
               respectively ever closed beyond it. M_BOS is Body & Sweep, which
               wants a sweep and then a body close, so a lone poke does not
               count. After that poke price never returned.

WHAT THIS AFFECTS

    riptide-lit-v2.pine        renders Main; a faithful port has the same trap
    LIT_FORWARD_V1             collects Main setups
    PREREG stages A, B, C      all measured Main

It does NOT overturn the three INCONCLUSIVE verdicts: a smaller sample is less
power, and those stages failed to find evidence rather than finding a negative.
It does mean their effective sample was smaller than reported, and selected
toward symbols whose first BOS happened to break.

    PYTHONPATH=. RIPTIDE_DEEP_CACHE=/tmp/deep \\
        python3 research/studies/lit_main_latch.py
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402

import aiohttp                                          # noqa: E402

from research.deep import load_deep                     # noqa: E402
import research.lit_v3 as L                             # noqa: E402
import research.lit_repl as RP                          # noqa: E402

DAYS = 333
SYMS = RP.DISCOVERY[:30]
TFS = ("Min30", "Min15")

PH = {getattr(L, n): n[3:].lower() for n in dir(L) if n.startswith("PH_")}
DR = {getattr(L, n): n[4:].lower() for n in dir(L) if n.startswith("DIR_")}


def coverage(ctx, n):
    """How far through the window the LAST event landed. A live tracker ends
    near 1.0; anything under 0.5 stopped and did not resume."""
    return (ctx.events[-1]["bar"] / n) if ctx.events else 0.0


async def main():
    print("=" * 88)
    print("  LIT MAIN STRUCTURE — A TRAP STATE IN PH_SEEK")
    print("=" * 88)
    print("  Internal runs on the exact same candles, so where Internal keeps")
    print("  emitting and Main does not, the silence belongs to the engine.")
    print()

    latched = {}
    async with aiohttp.ClientSession() as sess:
        for tf in TFS:
            rows = []
            for sym in SYMS:
                try:
                    cs = await load_deep(sess, sym, tf, days=DAYS)
                except Exception:
                    continue
                if len(cs) < 2000:
                    continue
                m, it, _d, _g = L.engine(cs)
                rows.append((sym, cs, len(cs), m, it))

            print("=" * 88)
            print(f"  1. PREVALENCE — {tf}, {len(rows)} symbols, {DAYS} days")
            print("=" * 88)
            print(f"  {'symbol':<14}{'main n':>8}{'main cov':>10}"
                  f"{'int n':>8}{'int cov':>9}   verdict")
            dead = []
            for sym, cs, n, m, it in sorted(
                    rows, key=lambda r: coverage(r[3], r[2])):
                mc, ic = coverage(m, n), coverage(it, n)
                v = ""
                if mc < 0.5 and ic >= 0.5:
                    v = "MAIN LATCHED"
                    dead.append((sym, cs, n, m))
                elif mc < 0.5 and ic < 0.5:
                    v = "both quiet — not this bug"
                print(f"  {sym:<14}{len(m.events):>8}{mc:>10.2f}"
                      f"{len(it.events):>8}{ic:>9.2f}   {v}")
            print(f"\n  Main latched on {len(dead)}/{len(rows)} "
                  f"({100*len(dead)/max(1,len(rows)):.0f}%) of symbols on {tf}")
            print()
            latched[tf] = dead

    print("=" * 88)
    print("  2. THE STUCK STATE — identical on every latched symbol")
    print("=" * 88)
    print(f"  {'symbol':<12}{'tf':<7}{'phase':>9}{'dir':>7}{'ch.on':>7}"
          f"{'bos.on':>8}{'stuck at':>10}{'stuck for':>11}")
    for tf, dead in latched.items():
        for sym, cs, n, m in dead:
            print(f"  {sym:<12}{tf:<7}{PH.get(m.phase, '?'):>9}"
                  f"{DR.get(m.dir, '?'):>7}{str(m.ch.on):>7}"
                  f"{str(m.bos.on):>8}{m.phaseBar:>10}"
                  f"{n - m.phaseBar:>11}")
    print()
    print("  phase=seek, ch.on=False, bos.on=True. Step 8 needs ch.ready(),")
    print("  step 5 will not publish an IDM outside discover/track. The only")
    print("  door is step 7, and it is shut.")
    print()

    print("=" * 88)
    print("  3. WAS THE BOS EVER REACHABLE?")
    print("=" * 88)
    print(f"  {'symbol':<12}{'tf':<7}{'BOS':>14}{'max high after':>16}"
          f"{'vs level':>10}{'closes beyond':>15}   trigger")
    for tf, dead in latched.items():
        for sym, cs, n, m in dead:
            bp, bbar = m.bos.px, m.bos.createdBar
            after = cs[bbar + 1:]
            if not after or bp is None:
                continue
            hi = max(c.h for c in after)
            closes = sum(1 for c in after if c.c >= bp)
            trig = ("never reached" if hi < bp
                    else "poked, no body close")
            print(f"  {sym:<12}{tf:<7}{bp:>14.4f}{hi:>16.4f}"
                  f"{100*(hi/bp-1):>9.1f}%{closes:>15}   {trig}")
    print()
    print("  Both triggers land in the same dead end. The engine has no way")
    print("  to give up on a BOS, so a level the market declines to deliver")
    print("  ends the structure permanently.")
    print()

    print("=" * 88)
    print("  READ")
    print("=" * 88)
    print("  This is a defect, not a market fact. Internal structure on the")
    print("  same bars stays healthy throughout on every latched symbol.")
    print()
    print("  Any escape is a NEW RULE and needs a name, a default and its own")
    print("  measurement. Two candidates, neither picked here:")
    print("    choch_at_idm  create the opposing boundary when the IDM breaks,")
    print("                  so the bootstrap cycle owns both like every other")
    print("    bos_expiry    abandon an unbroken BOS after N bars and")
    print("                  re-bootstrap; N is a parameter and needs a prereg")
    print()
    print("  Until one is chosen and measured, the frozen engine stands and")
    print("  the latched symbol-timeframes are simply absent from the sample.")


if __name__ == "__main__":
    asyncio.run(main())
