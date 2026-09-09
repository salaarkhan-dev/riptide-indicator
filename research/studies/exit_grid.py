"""Exit policy, done properly: targets x rules, on Min30 and Min15.

WHY THIS IS A RE-RUN. `win_rate_price.py` answered the same question and two of
its inputs were wrong.

  THE FEE WAS TWICE THE TRUE RATE. Corrected against a real settlement to
  0.010% maker / 0.022% taker. That matters more here than anywhere else,
  because a PARTIAL books half the position early and therefore pays the fee
  twice — the rule the old rate punished hardest.

  THE DRAWDOWN CAME FROM A CHAOTIC SIMULATION. `portfolio.simulate` caps
  concurrency at eight slots, so which trades get one depends on which earlier
  trades filled and a small change cascades. Two runs of the SAME rule across
  the fee correction gave +20% and +11%. Any conclusion resting on that is
  resting on noise.

  THE FIX IS A DETERMINISTIC DRAWDOWN. Every signal is taken at one unit of
  risk, in time order, uncapped. The equity curve is then a pure function of
  the R sequence — no slots, no compounding, no path dependence, no seed. It
  answers a narrower question than the account simulation, but it answers it
  the same way every time, and the comparison between exit rules is exactly
  what it is for.

WHAT IS SWEPT: targets 1.0 / 1.5 / 2.0 / 2.5 / 3.0 crossed with plain,
break-even at 1R and 1.5R, and a partial at 0.5R and 1R. Twenty-five policies
per timeframe per signal type.

TWENTY-FIVE CELLS IS AN OPTIMISATION, NOT A DISCOVERY, and the honest way to
report an optimisation is out of sample. So the best cell is chosen on the
DISCOVERY half by R per signal, and then that cell — chosen blind to the
held-out data — is reported on the HELD-OUT half beside the deployed policy.
That estimates the decision procedure rather than the winning cell, which is
the number a person actually gets by running this sweep and acting on it.

PRE-REGISTERED, BEFORE THE FIRST NUMBER

  PRIMARY   The discovery-chosen policy must beat plain 2R on the HELD-OUT
            half, on R PER SIGNAL, at 2 SE.

  SECONDARY Win rate, full stop-out rate and R-drawdown for every cell, since
            the request was for more wins as well as more money and those are
            different columns.

  Fees at the corrected 0.010/0.022. The zero-fee case is printed alongside
  because MEXC runs zero-fee promotions on many pairs and the right reading of
  any fee-sensitive rule is a RANGE.

  EXPECTATION: plain at 2R or 1.5R wins on R, the partial wins on win rate and
  on drawdown, and the two do not coincide. Recorded so it cannot be revised.

    PYTHONPATH=. python3 research/studies/exit_grid.py
"""
import research.env                                     # noqa: F401  MUST be first

import statistics                                       # noqa: E402

from research.data import load_sync                     # noqa: E402
from research.harness import mean_se, simulate          # noqa: E402

TARGETS = (1.0, 1.5, 2.0, 2.5, 3.0)
RULES = (
    ("plain", {}),
    ("BE at 1R", dict(be_arm_r=1.0, be_lock_r=0.0)),
    ("BE at 1.5R", dict(be_arm_r=1.5, be_lock_r=0.0)),
    ("half at 0.5R", dict(part_at_r=0.5, be_lock_r=0.0)),
    ("half at 1R", dict(part_at_r=1.0, be_lock_r=0.0)),
)
DEPLOYED = ("plain", 2.0)


def exit_time(r, o):
    return r.candles[o.exit_bar].t if o.exit_bar is not None else 0


def score(rows, rule, tgt, **fee):
    """(per-signal R list, filled outcomes with times) for one policy."""
    opts = dict(rule)
    if "part_at_r" in opts:
        opts["part_to_r"] = tgt
    per, filled = [], []
    for r in rows:
        o = simulate(r.candles, r.bar, r.signal.entry, r.signal.stop,
                     r.signal.is_long, target_r=tgt, **opts, **fee)
        if o.exit_bar is None and o.filled:
            continue                       # ran out of candles, not an outcome
        per.append(o.r if o.filled else 0.0)
        if o.filled:
            filled.append((exit_time(r, o), o))
    return per, filled


def drawdown_r(filled):
    """Max peak-to-trough of the R equity curve, one unit per trade.

    DETERMINISTIC, which is the entire point. No position cap, no compounding,
    no ordering ambiguity beyond exit time — so two runs of the same rule give
    the same number and a difference between rules is a difference between
    rules.
    """
    bal = peak = dd = 0.0
    for _, o in sorted(filled, key=lambda x: x[0]):
        bal += o.r
        peak = max(peak, bal)
        dd = max(dd, peak - bal)
    return dd


def cell(rows, rule_name, opts, tgt, **fee):
    per, filled = score(rows, opts, tgt, **fee)
    if len(filled) < 40:
        return None
    m, se = mean_se(per)
    win = sum(1 for _, o in filled if o.r > 0) / len(filled)
    full = sum(1 for _, o in filled
               if o.exit == "stop" and o.r < -0.5) / len(filled)
    dd = drawdown_r(filled)
    tot = sum(per)
    return dict(name=f"{rule_name} @ {tgt:g}R", m=m, se=se, win=win, full=full,
                dd=dd, tot=tot, n=len(filled),
                score=(tot / dd) if dd > 0 else float("inf"))


def grid(rows, label, **fee):
    print(f"\n{label}   n={len(rows)}")
    print(f"  {'policy':<18}{'fills':>7}{'win':>6}{'fullSL':>8}"
          f"{'R/signal':>10}{'SE':>7}{'total R':>9}{'maxDD':>8}{'R/DD':>7}")
    out = []
    for rn, opts in RULES:
        for t in TARGETS:
            c = cell(rows, rn, opts, t, **fee)
            if not c:
                continue
            out.append(c)
            star = "  <-- deployed" if (rn, t) == DEPLOYED else ""
            print(f"  {c['name']:<18}{c['n']:>7}{c['win']:>6.0%}"
                  f"{c['full']:>8.0%}{c['m']:>+10.3f}{c['se']:>7.3f}"
                  f"{c['tot']:>+9.1f}{c['dd']:>8.1f}{c['score']:>7.2f}{star}")
    return out


def panel(name, rows, **fee):
    disc = [r for r in rows if not r.split_window]
    held = [r for r in rows if r.split_window]
    if len(disc) < 200 or len(held) < 200:
        print(f"\n{name}: too few to split")
        return
    print(f"\n{'=' * 96}\n{name}\n{'=' * 96}")
    d = grid(disc, "DISCOVERY (newer half) — the sweep, for choosing only",
             **fee)
    if not d:
        return
    # Chosen on discovery, blind to everything below.
    best = max(d, key=lambda c: c["m"])
    best_dd = max(d, key=lambda c: c["score"])
    print(f"\n  chosen on DISCOVERY by R per signal:   {best['name']}")
    print(f"  chosen on DISCOVERY by R per drawdown: {best_dd['name']}")

    print(f"\n  HELD OUT — only the deployed policy and the two chosen above")
    print(f"  {'policy':<18}{'fills':>7}{'win':>6}{'fullSL':>8}"
          f"{'R/signal':>10}{'SE':>7}{'total R':>9}{'maxDD':>8}{'R/DD':>7}")
    want = {f"{DEPLOYED[0]} @ {DEPLOYED[1]:g}R", best["name"], best_dd["name"]}
    got = {}
    for rn, opts in RULES:
        for t in TARGETS:
            nm = f"{rn} @ {t:g}R"
            if nm not in want:
                continue
            c = cell(held, rn, opts, t, **fee)
            if not c:
                continue
            got[nm] = c
            print(f"  {c['name']:<18}{c['n']:>7}{c['win']:>6.0%}"
                  f"{c['full']:>8.0%}{c['m']:>+10.3f}{c['se']:>7.3f}"
                  f"{c['tot']:>+9.1f}{c['dd']:>8.1f}{c['score']:>7.2f}")
    base = got.get(f"{DEPLOYED[0]} @ {DEPLOYED[1]:g}R")
    if base:
        for nm, c in got.items():
            if nm == base["name"]:
                continue
            dd_ = c["m"] - base["m"]
            dse = (c["se"] ** 2 + base["se"] ** 2) ** 0.5
            print(f"    {nm + ' vs deployed':<34}{dd_:>+9.3f}{dse:>7.3f}"
                  f"   {dd_ / dse if dse else 0:+.1f} SE")


def main():
    import asyncio
    import aiohttp
    from riptide.exchange import list_symbols

    async def _s():
        async with aiohttp.ClientSession() as sess:
            return await list_symbols(sess)
    syms = asyncio.run(_s()) or None
    print("EXIT POLICY — 25 policies, chosen on discovery, read on held out\n"
          "drawdown is the UNCAPPED R equity curve, so it is deterministic\n"
          "fees corrected to 0.010% maker / 0.022% taker")
    for tf in ("Min30", "Min15"):
        rows = load_sync(symbols=syms, interval=tf)
        for kind in ("early", "confirmed"):
            sub = [r for r in rows if r.kind == kind]
            panel(f"{tf} · {kind}", sub)
        # The zero-fee bound, on the one panel that carries the traffic.
        e = [r for r in rows if r.kind == "early"]
        print(f"\n{'-' * 96}\n{tf} · early · ZERO FEES — the promotional-pair "
              f"bound\n{'-' * 96}")
        grid([r for r in e if r.split_window], "held out, no fees",
             fee_pct=0.0)


if __name__ == "__main__":
    main()
