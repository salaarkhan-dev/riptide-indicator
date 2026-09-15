"""THE SECOND TRAP: PH_LOCK with two boundaries price never reaches.

Found while validating P9 and deliberately left unfixed there, because
patching a second defect inside the experiment validating the first is how a
measurement turns into a rolling redesign. This is its own diagnosis.

DIAGNOSIS ONLY. No policy is proposed, no arm is implemented, nothing is
selected. The point is to establish what the defect IS, how common it is, and
— the question that decides whether it can be repaired at all under this
project's rules — whether a stall is a DISTINCT state or merely the tail of a
continuous distribution of lock durations.

That last question matters more than the prevalence. `Pol`'s contract is "No
policy may introduce a number". If stalls are separable by a structural
property, a parameter-free rule can name them. If they are only the long end of
a continuum, every candidate rule reduces to a bar count, and the honest answer
is that this cannot be fixed the way P9 was.

    PYTHONPATH=. RIPTIDE_DEEP_CACHE=/tmp/deep \\
        python3 research/studies/lit_lock_stall.py
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import statistics                                       # noqa: E402
import time                                             # noqa: E402

import aiohttp                                          # noqa: E402

from research.deep import load_deep                     # noqa: E402
import research.lit_v3 as L                             # noqa: E402
import research.lit_repl as RP                          # noqa: E402

DAYS = 333
TFS = ("Min30", "Min15")
HELD_WANT = 80

PH = {getattr(L, n): n[3:].lower() for n in dir(L) if n.startswith("PH_")}
DR = {L.DIR_BULL: "bull", L.DIR_BEAR: "bear", L.DIR_NONE: "none"}


def cover(ctx, n):
    return (ctx.events[-1]["bar"] / n) if ctx.events else 0.0


def approach(cs, start, px):
    """How close price got to a level during the window, as a fraction of the
    gap it had to close at the start.

    1.0 = never moved toward it at all.  0.0 = touched it.
    """
    if px is None or start >= len(cs) - 1:
        return None
    p0 = cs[start].c
    gap0 = abs(px - p0)
    if gap0 <= 0:
        return 0.0
    # A level above needs price to RISE, so its closest approach is the
    # highest high; a level below, the lowest low. Clamped at the starting
    # gap so a move away from the level reads as 1.00 rather than >1.
    up = px > p0
    best = min(px - c.h for c in cs[start + 1:]) if up \
        else min(c.l - px for c in cs[start + 1:])
    return max(0.0, min(gap0, best)) / gap0


async def scan(sess, syms, label):
    rows = []
    for tf in TFS:
        for sym in syms:
            try:
                cs = await load_deep(sess, sym, tf, days=DAYS)
            except Exception:
                continue
            if len(cs) < 2000:
                continue
            m, it, _d, _g = L.engine(cs)
            n = len(cs)
            mc, ic = cover(m, n), cover(it, n)
            unhealthy = mc < 0.5 <= ic
            rows.append(dict(
                src=label, sym=sym, tf=tf, n=n, mcov=mc, icov=ic,
                phase=m.phase, dir=m.dir,
                bos=m.bos.px if m.bos.on else None,
                ch=m.ch.px if m.ch.on else None,
                phaseBar=m.phaseBar,
                stuck=n - m.phaseBar,
                maxlock=m.held.get("lock", 0),
                maxseek=m.held.get("seek", 0),
                stall=bool(unhealthy and m.phase == L.PH_LOCK),
                unhealthy=unhealthy,
                cs=cs,
            ))
    return rows


async def main():
    print("=" * 98)
    print("  THE PH_LOCK STALL — DIAGNOSIS, NO FIX")
    print("=" * 98)
    print(f"  engine     research.lit_v3 as it now ships "
          f"(POL.seekCh = {L.POL.seekCh!r})")
    print(f"  window     {DAYS} days, {', '.join(TFS)}")
    print("  asks       what the defect is, how common, and whether a stall")
    print("             is SEPARABLE from a long lock that resolved")
    print("=" * 98)

    t0 = time.time()
    async with aiohttp.ClientSession() as sess:
        rows = await scan(sess, RP.DISCOVERY[:30], "discovery")
        print(f"\n  discovery: {len(rows)} panels ({time.time()-t0:.0f}s)")
        try:
            held = await RP.heldout(sess, skip=len(RP.DISCOVERY),
                                    want=HELD_WANT)
            held = [s for s in held if s not in RP.DISCOVERY]
            rows += await scan(sess, held, "held-out")
        except Exception as e:                            # noqa: BLE001
            print(f"  held-out universe unavailable: {e}")
        print(f"  total:     {len(rows)} panels ({time.time()-t0:.0f}s)")

    stalls = [r for r in rows if r["stall"]]
    other_bad = [r for r in rows if r["unhealthy"] and not r["stall"]]

    print("\n" + "=" * 98)
    print("  1. PREVALENCE")
    print("=" * 98)
    print(f"  panels                       {len(rows)}")
    print(f"  unhealthy (Main dead, Internal alive)   "
          f"{sum(1 for r in rows if r['unhealthy'])}")
    print(f"    of those, PH_LOCK stalls   {len(stalls)}  "
          f"({100*len(stalls)/max(1,len(rows)):.1f}% of all panels)")
    print(f"    of those, anything else    {len(other_bad)}")
    for r in other_bad:
        print(f"      {r['sym']} {r['tf']}: phase={PH.get(r['phase'])}")

    print("\n" + "=" * 98)
    print("  2. THE STALLED PANELS — what the boundaries look like")
    print("=" * 98)
    print(f"  {'panel':<22}{'dir':<6}{'stuck':>8}{'BOS':>12}{'CHoCH':>12}"
          f"{'spread%':>9}{'→BOS':>7}{'→CH':>7}")
    for r in sorted(stalls, key=lambda x: -x["stuck"]):
        cs = r["cs"]
        p0 = cs[r["phaseBar"]].c
        spread = (abs(r["bos"] - r["ch"]) / p0 * 100
                  if r["bos"] and r["ch"] else float("nan"))
        ab = approach(cs, r["phaseBar"], r["bos"])
        ac = approach(cs, r["phaseBar"], r["ch"])
        print(f"  {(r['sym']+' '+r['tf']):<22}{DR.get(r['dir'],'?'):<6}"
              f"{r['stuck']:>8}{r['bos']:>12.6g}{r['ch']:>12.6g}"
              f"{spread:>9.1f}"
              f"{(f'{ab:.2f}' if ab is not None else '—'):>7}"
              f"{(f'{ac:.2f}' if ac is not None else '—'):>7}")
    print()
    print("  →BOS / →CH: how close price got, as a fraction of the gap it had")
    print("  to close when the lock began. 1.00 means it never moved toward")
    print("  that boundary at all; 0.00 means it touched it.")

    print("\n" + "=" * 98)
    print("  2b. WHY EACH ONE STALLED — counted, not inferred")
    print("=" * 98)
    print("  A stall needs a phase with no escape hatch AND a trigger. The")
    print("  trigger is not the same every time, so it is classified from the")
    print("  candles rather than described.")
    print()
    print(f"  {'panel':<20}{'level':<7}{'price':>12}{'wick reached':>14}"
          f"{'closed beyond':>15}{'extreme':>12}   trigger")
    for r in sorted(stalls, key=lambda x: -x["stuck"]):
        cs, up = r["cs"], r["dir"] == L.DIR_BULL
        w = cs[r["phaseBar"] + 1:]
        if not w:
            continue
        for nm, px, above in (("BOS", r["bos"], up), ("CHoCH", r["ch"], not up)):
            if px is None:
                continue
            wick = sum(1 for c in w if ((c.h >= px) if above else (c.l <= px)))
            clo = sum(1 for c in w if ((c.c > px) if above else (c.c < px)))
            ext = (max(c.h for c in w) if above else min(c.l for c in w))
            trig = ("reached, break declined" if wick and not clo
                    else "broke?? — investigate" if clo
                    else "never reached")
            print(f"  {(r['sym']+' '+r['tf']):<20}{nm:<7}{px:>12.6g}"
                  f"{wick:>14}{clo:>15}{ext:>12.6g}   {trig}")
        print()
    print("  'reached, break declined' means the level was touched and the")
    print("  break mode refused it. M_BOS and M_CH are Body & Sweep, which")
    print("  wants a sweep and THEN a body close, so a lone wick is not a")
    print("  break. That is the same trigger that produced two of the four")
    print("  PH_SEEK latches (ONDO and BTC) — see lit_main_latch.py.")

    print("\n" + "=" * 98)
    print("  3. THE QUESTION THAT DECIDES WHETHER THIS IS FIXABLE HERE")
    print("=" * 98)
    print("  Is a stall a DISTINCT state, or the long tail of normal locks?")
    print()
    locks = sorted(r["maxlock"] for r in rows if r["maxlock"] > 0)
    if locks:
        qs = [0.5, 0.75, 0.9, 0.95, 0.99, 1.0]
        print(f"  longest lock ever held, across {len(locks)} panels that "
              f"ever locked:")
        for q in qs:
            i = min(len(locks) - 1, int(q * (len(locks) - 1)))
            print(f"    p{int(q*100):<3} {locks[i]:>8} bars")
    print()
    healthy_long = sorted((r for r in rows if not r["unhealthy"]),
                          key=lambda x: -x["maxlock"])[:8]
    print("  the longest locks on panels that RECOVERED:")
    print(f"    {'panel':<22}{'longest lock':>14}{'final phase':>14}")
    for r in healthy_long:
        print(f"    {(r['sym']+' '+r['tf']):<22}{r['maxlock']:>14}"
              f"{PH.get(r['phase'],'?'):>14}")
    print()
    if stalls:
        sm = [r["stuck"] for r in stalls]
        hm = [r["maxlock"] for r in rows if not r["unhealthy"]]
        print(f"  stalled, still stuck at the end: "
              f"{min(sm)}–{max(sm)} bars")
        if hm:
            print(f"  recovered, longest lock held:    "
                  f"{min(hm)}–{max(hm)} bars, median "
                  f"{statistics.median(hm):.0f}")
        print()
        print("  OVERLAP is the finding to look for. If recovered panels hold")
        print("  locks as long as the stalled ones stay stuck, then duration")
        print("  does not separate them and no rule phrased on duration can")
        print("  either — and a rule phrased on duration is a bar count, which")
        print("  Pol's contract forbids.")

    print("\n" + "=" * 98)
    print("  4. MECHANISM, read from the code")
    print("=" * 98)
    print("""
  PH_LOCK is entered at the IDM break when a CHoCH already exists. Its only
  exits are step 7 (BOS breaks) and step 8 (CHoCH breaks). Step 5 will not
  publish a new IDM in LOCK — it caches the correction as `latent_cached`.
  There is no timeout and no invalidation. Exactly the shape of the PH_SEEK
  trap, one level up.

  Where the two levels come from, and why they go stale:

    BOS    set at the IDM break to the LEG extreme in the trend direction
           (legHi / legLo). Fresh, but anchored to the whole structural leg,
           so after a large impulse it can sit far beyond anything that
           follows.

    CHoCH  inherited. It was set at the PREVIOUS BOS break from phLo / phHi —
           the extreme reached while that cycle was in SEEK or LOCK. If price
           spiked once during that window, the CHoCH keeps the spike forever.

  Neither level is ever re-derived while the lock holds. A context that entered
  a lock during high volatility keeps boundaries scaled to that volatility, and
  a quiet regime afterwards may not reach either.

  BUT THE MISSING ESCAPE HATCH IS THE DEFECT, NOT THE DISTANCE. Section 2b
  shows the trigger is not always an unreachable level: one of the two stalls
  had its BOS WICKED and Body & Sweep declined the break. Same structure, a
  different way in. Two of the four PH_SEEK latches came in through that same
  door. So a diagnosis phrased purely as "the boundaries were too far away"
  would be wrong for half the cases, and any repair aimed only at distance
  would miss them.
""")

    print("=" * 98)
    print("  5. CANDIDATE ESCAPES — named, NOT chosen and NOT implemented")
    print("=" * 98)
    print("""
  re_leg      re-derive the CHoCH from the CURRENT leg at every IDM break,
              instead of only when none exists. This is P9's rule with its
              `if not ch.on` guard removed, so it is parameter-free and
              already implemented in spirit. It would also change every
              healthy cycle, so its retention will be far below P9's 99.8%
              and it is a different engine, not a repair.

  latent_out  let the correction that LOCK already caches as latent publish
              an IDM, which returns the context to TRACK. Parameter-free, and
              it uses state the engine is already keeping and discarding.

  stale_lvl   invalidate a boundary once the structural leg that produced it
              has been fully superseded. Parameter-free in principle, but
              "superseded" needs a definition that does not smuggle in a
              distance or a bar count.

  REJECTED BEFORE MEASURING, for the same reason the P9 expiry arm was:
  anything of the form "abandon the lock after N bars" or "abandon it once
  the boundaries are more than X% apart" introduces a number, and
  `Pol`'s contract forbids it.

  Choosing among these needs its own pre-registration with liveness gates and
  a retention selector, exactly as P9 had. Nothing here selects one.
""")


if __name__ == "__main__":
    asyncio.run(main())
