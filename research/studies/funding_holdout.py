"""THE FUNDING EFFECT, WITH THE CUT CHOSEN BLIND.

WHY THIS EXISTS. research/studies/funding.py found the pre-registered
positioning signature — as funding rises, longs deteriorate and shorts improve,
moving in opposite directions — clearing a 200-shuffle placebo and holding
directionally on both halves. That is the best entry-side result this project
has produced.

IT IS ALSO THE EXACT SHAPE OF A RESULT THAT HAS FAILED HERE BEFORE. The
trendline confluence scored +0.206 offline, cleared a placebo floor in all five
panels, and came back +0.7 SE on the half it was not found on. Twenty-one entry
filters have failed. The one thing funding.py did NOT do is choose its
threshold without looking, and a decile boundary picked after seeing the table
is a fitted parameter wearing a round number's clothes.

So this re-asks the question the only way that can answer it:

    1. On the DISCOVERY half only, score a FIXED, PRE-DECLARED list of
       candidate rules and take whichever wins. The threshold each rule needs
       is computed from discovery-half data alone.
    2. Apply that winner, with that threshold, to the HELD-OUT half. Read it
       once.
    3. Swap the halves and repeat, because which half is called "first" is
       arbitrary and a result that only survives one assignment is not one.

The candidate list is fixed here in source, before the run, so the "choice" in
step 1 is a choice among four declared options rather than a search.

──────────────────────────────────────────────────────────────────────────────
PRE-REGISTERED

  THE RULE FAMILY, all of the form "skip LONG picks when funding is above X",
  because that is the side funding.py found and the only side a direction-taking
  bot can act on. Thresholds are computed on the discovery half:

      A   funding > 0                      (sign only, no parameter at all)
      B   funding > discovery median
      C   funding > discovery 80th pct     (the quintile cut)
      D   funding > discovery 90th pct     (the decile cut)

  PRIMARY. Net R per trade of the LONGS THE RULE KEEPS on the held-out half,
  against the held-out baseline of all longs. A rule that improves the kept
  trades is doing something; one that does not is a filter that costs volume
  for nothing.

  SECONDARY, AND THE ONE THAT DECIDES DEPLOYMENT. The same rule run through the
  account simulator used by phase2_rule.py, as a rule rather than a bucket
  table, reported as return per unit of drawdown. An improvement in R per trade
  that does not survive slots, margin and compounding is not worth shipping.

  THE CONTROL. The same threshold applied to SHORTS. Funding's story says the
  short side should move the OTHER way; if skipping high-funding shorts helps
  too, the rule is removing bad trades generally rather than reading
  positioning, and the mechanism is wrong even if the number is good.

  WHAT WOULD FALSIFY IT. The winning discovery rule failing to beat baseline on
  the held-out half in EITHER half-assignment; or a ret/DD no better than
  not filtering at all.

    PYTHONPATH=. RIPTIDE_DEEP_CACHE=/tmp/deep \
        python3 research/studies/funding_holdout.py
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import json                                             # noqa: E402
import os                                               # noqa: E402
from bisect import bisect_right                         # noqa: E402

import aiohttp                                          # noqa: E402

from riptide.config import BAR_SECONDS                  # noqa: E402
from research.deep import load_universe                 # noqa: E402
from research.harness import mean_se                    # noqa: E402
from research.studies.poi_tf import DAY, DAYS, H8       # noqa: E402
from research.studies.poi_tf import collect, context, universe  # noqa: E402
from research.studies.pick_rule import TFS, pick_rolling  # noqa: E402
from research.studies.band_key import COOLDOWN, KEYS    # noqa: E402
from research.studies.funding import funding_at, funding_table  # noqa: E402
from research.studies.portfolio import Rules, simulate  # noqa: E402

CACHE = os.getenv("RIPTIDE_DEEP_CACHE", "/tmp/deep")


def pct(vals, p):
    s = sorted(vals)
    return s[min(int(len(s) * p), len(s) - 1)] if s else 0.0


# The candidate rules, fixed before the run. Each returns the threshold to use,
# computed from discovery-half funding values only.
CANDIDATES = [
    ("A  funding > 0", lambda v: 0.0),
    ("B  funding > median", lambda v: pct(v, 0.50)),
    ("C  funding > 80th pct", lambda v: pct(v, 0.80)),
    ("D  funding > 90th pct", lambda v: pct(v, 0.90)),
]


class Sig:
    __slots__ = ("is_long",)

    def __init__(self, v):
        self.is_long = v


class Adapt:
    """A deep-pipeline row wearing the names portfolio.simulate() expects."""
    __slots__ = ("filled", "fill_time", "exit_time", "r", "risk_pct",
                 "kind", "signal", "src")

    def __init__(self, t):
        self.src = t
        self.filled = t.filled
        self.fill_time = t.fill_t or 0
        self.exit_time = t.exit_t or 0
        self.r = t.r
        self.risk_pct = t.risk_pct
        self.kind = t.kind
        self.signal = Sig(t.is_long)


def score(rows, FR, thr, is_long=True):
    """R per trade of the trades a 'skip above thr' rule KEEPS."""
    sel = [r for r in rows if r.is_long == is_long and id(r) in FR]
    kept = [r.r for r in sel if FR[id(r)] <= thr]
    dropped = [r.r for r in sel if FR[id(r)] > thr]
    base, _ = mean_se([r.r for r in sel]) if sel else (0.0, 0.0)
    m, se = mean_se(kept) if kept else (0.0, 0.0)
    dm, _ = mean_se(dropped) if dropped else (0.0, 0.0)
    return dict(n_kept=len(kept), n_drop=len(dropped), kept=m, se=se,
                dropped=dm, base=base, lift=m - base)


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
        table = await funding_table(sess, syms)

    sent = [t for tf in TFS for t in by_tf[tf] if t.day]
    picks = pick_rolling(sent, KEYS["A  tf > band > confd  (shipped)"], COOLDOWN)
    FR = {}
    for t in picks:
        v = funding_at(table, t.sym, t.t)
        if v is not None:
            FR[id(t)] = v
    have = [t for t in picks if id(t) in FR]
    have.sort(key=lambda t: t.fill_t or 0)
    mid = have[len(have) // 2].fill_t
    first = [t for t in have if (t.fill_t or 0) <= mid]
    second = [t for t in have if (t.fill_t or 0) > mid]

    print("FUNDING — THE CUT CHOSEN BLIND")
    print(f"{len(syms)} symbols · {DAYS} days · {len(picks)} picks, "
          f"{len(have)} with funding")
    print(f"halves: {len(first)} / {len(second)}\n")
    print("Every threshold is computed on the DISCOVERY half only and read")
    print("once on the other. 'lift' is the kept trades against that half's")
    print("own baseline — a filter that costs volume must earn it.\n")

    verdicts = []
    for tag, disc, hold in (("first -> second", first, second),
                            ("second -> first", second, first)):
        print(f"{'=' * 92}\nDISCOVER ON {tag.split(' -> ')[0].upper()} HALF, "
              f"READ ON THE {tag.split(' -> ')[1].upper()}\n{'=' * 92}")
        vals = [FR[id(t)] for t in disc if t.is_long]
        print(f"  {'candidate':<24}{'thr':>11}{'disc kept':>11}"
              f"{'disc lift':>11}{'kept n':>8}{'dropped R':>11}")
        best, best_lift = None, -9e9
        for name, fn in CANDIDATES:
            thr = fn(vals)
            d = score(disc, FR, thr)
            print(f"  {name:<24}{thr:>+11.5f}{d['kept']:>+11.3f}"
                  f"{d['lift']:>+11.3f}{d['n_kept']:>8}{d['dropped']:>+11.3f}")
            if d["lift"] > best_lift and d["n_drop"] >= 20:
                best, best_lift, best_thr = name, d["lift"], thr
        if best is None:
            print("  no candidate dropped enough trades to judge")
            continue

        h = score(hold, FR, best_thr)
        hs = score(hold, FR, best_thr, is_long=False)
        print(f"\n  DISCOVERY PICKED: {best}  (threshold {best_thr:+.5f}, "
              f"lift {best_lift:+.3f} on discovery)")
        print(f"\n  {'HELD-OUT half':<24}{'n kept':>9}{'kept R':>10}{'SE':>8}"
              f"{'baseline':>11}{'LIFT':>9}{'n dropped':>11}{'dropped R':>11}")
        print(f"  {'longs (the claim)':<24}{h['n_kept']:>9}{h['kept']:>+10.3f}"
              f"{h['se']:>8.3f}{h['base']:>+11.3f}{h['lift']:>+9.3f}"
              f"{h['n_drop']:>11}{h['dropped']:>+11.3f}")
        print(f"  {'shorts (the control)':<24}{hs['n_kept']:>9}{hs['kept']:>+10.3f}"
              f"{hs['se']:>8.3f}{hs['base']:>+11.3f}{hs['lift']:>+9.3f}"
              f"{hs['n_drop']:>11}{hs['dropped']:>+11.3f}")
        verdicts.append((tag, best, best_thr, h["lift"], hs["lift"]))
        print()

    print(f"{'=' * 92}\nAS A RULE, NOT A TABLE — the account simulator\n{'=' * 92}")
    print("  A lift in R per trade that does not survive slots, margin and")
    print("  compounding is not worth shipping. Same judge as phase2_rule.py.\n")
    print(f"  {'arm':<40}{'taken':>8}{'win':>6}{'ret':>9}{'maxDD':>8}{'ret/DD':>9}")
    allrows = [Adapt(t) for t in have]
    base = simulate(allrows, Rules(name="x", max_open=8, risk_pct=0.5))
    print(f"  {'PICK + max 8 (no funding rule)':<40}{base['n']:>8}"
          f"{base['win']:>5.0f}%{base['ret']:>+9.0f}%{base['dd']:>7.0f}%"
          f"{base['score']:>9.2f}")
    for name, fn in CANDIDATES:
        thr = fn([FR[id(t)] for t in have if t.is_long])
        kept = [a for a in allrows
                if not (a.signal.is_long and FR.get(id(a.src), -9e9) > thr)]
        res = simulate(kept, Rules(name=name, max_open=8, risk_pct=0.5))
        if res is None:
            print(f"  {'skip longs ' + name:<40}  BLEW UP")
            continue
        print(f"  {'skip longs ' + name:<40}{res['n']:>8}{res['win']:>5.0f}%"
              f"{res['ret']:>+9.0f}%{res['dd']:>7.0f}%{res['score']:>9.2f}")
    print("\n  (thresholds here use the WHOLE window and are therefore")
    print("   optimistic — this panel sizes the effect, the panels above")
    print("   are the ones that test it.)")

    print(f"\n{'=' * 92}\nVERDICT\n{'=' * 92}")
    for tag, name, thr, lift, ctrl in verdicts:
        ok = "HELD" if lift > 0 else "FAILED"
        note = ("control moved as much — mechanism suspect"
                if lift > 0 and ctrl >= lift * 0.7 else "")
        print(f"  {tag:<18}{name:<24}long lift {lift:+.3f}  "
              f"short lift {ctrl:+.3f}   {ok} {note}")
    if len(verdicts) == 2 and all(v[3] > 0 for v in verdicts):
        print("\n  Held on BOTH half-assignments. That is the bar this project")
        print("  sets, and the trendline confluence did not clear it.")
    else:
        print("\n  Did NOT hold on both assignments. Treat as unproven and do")
        print("  not filter on it — the same verdict 21 other filters got.")


if __name__ == "__main__":
    asyncio.run(main())
