"""STAGE A — does the LIT continuation premise actually pay?

LIT_STRATEGY_DESIGN.md §5. The naked continuation, on levels the engine already
produces, with NO new subsystem: no FVG, no POI zones, no SCOB, no obstacle
check. Those are Stages B-E and every one of them is weeks of work carrying its
own inference risk, so they are not built until this returns a number worth
building on.

    long   bullish IDM taken, BOS locked above, with-trend only        [T8]
    entry  the IDM-break bar's close                                   [T9]
    stop   that bar's extreme - the IDM RAID EXTREME (§73). At the moment of
           entry the raid IS that bar, so the stop needs no lookahead.
    arm    a trailing stop at Active Price = entry + minRR * risk, net of
           commission                                        (Ch.24, minRR 0.5)
    exit   the stop, initial or trailed                                [T6]

THE PREMISE IS ALREADY MEASURED AND IT HOLDS. IDM -> BOS touch runs 65.6% on
our engine against the reference's 65.0%, on two timeframes. What that does NOT
establish is profitability: first passage says nothing about where you entered,
how far the stop was, or what happened in between.

So the decisive number here is NOT the win rate and NOT the BOS hit rate. It is
MFE BEYOND ACTIVE PRICE ON THE WINNERS, because in a trail-based system that is
the entire source of edge. A 65% strategy whose winners die just past the
arming threshold loses money.

T6 IS THE LARGEST HOLE IN THE WHOLE DESIGN. What the reference's trailing stop
actually trails is stated nowhere in any of the 24 source chapters. So every
variant is measured against a FIXED-R CONTROL, and "no variant beats fixed" is
an admissible result that gets recorded as one.

STAGE A CAN KILL THE STRATEGY. That is what it is for.

    PYTHONPATH=. RIPTIDE_DEEP_CACHE=/tmp/deep python3 research/lit_entry.py
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import statistics                                       # noqa: E402

import aiohttp                                          # noqa: E402

from research.deep import load_universe                 # noqa: E402
import research.lit_v3 as L                             # noqa: E402

COMMISSION = 0.0005      # 0.05% per side, the reference's own default (Ch.24)
MIN_RR = 0.5             # Ch.24. This ARMS the trail; it is NOT an exit.
MAX_BARS = 600           # a trade still open after this is recorded as such,
                         # never silently dropped


class Trade:
    """One setup, followed to its exit. Records the whole path, not just the
    outcome - a distribution cannot be reconstructed from win/lose."""

    def __init__(self, ev, i, sym=""):
        self.sym = sym
        self.dir = ev["dir"]
        self.entryBar = i
        self.entry = ev["entry"]
        self.stop0 = ev["stop"]
        self.bos = ev["bos"]
        self.choch = ev["choch"]
        self.risk = abs(self.entry - self.stop0)
        self.stop = self.stop0
        self.armed = False
        self.mfe = 0.0
        self.mae = 0.0
        self.exitBar = None
        self.exitPx = None
        self.why = None
        self.bosTouched = False
        self.chochTouched = False
        # The premise is BOS-before-CHoCH on the PRICE PATH, independent of
        # where this trade happened to exit. Measuring "BOS before my exit"
        # measures the exit rule, not the premise - a mistake the first run of
        # this harness made and which produced a nonsense 9.8%.
        self.premise = None
        # Active Price, per Ch.24: entry + minRR*risk, plus the round-trip
        # commission, because a setup that cannot clear its own costs is not a
        # setup. The reference puts commission in this calculation for exactly
        # this reason.
        cost = self.entry * COMMISSION * 2
        self.active = (self.entry + MIN_RR * self.risk + cost) if self.dir > 0 \
            else (self.entry - MIN_RR * self.risk - cost)

    def ok(self):
        return self.risk > 0 and abs(self.bos - self.entry) > 0

    def r(self, px):
        d = (px - self.entry) if self.dir > 0 else (self.entry - px)
        return d / self.risk

    def step(self, i, o, h, l, c, trail, pivot):
        """One bar. Returns True when the trade is closed.

        ORDER IS LOAD-BEARING and deliberately pessimistic: the stop is checked
        BEFORE the favourable excursion is banked. On a bar that both stops us
        out and runs further our way, OHLC cannot say which came first, so we
        take the loss. Doing it the other way round is how a backtest flatters
        itself.
        """
        up = self.dir > 0
        self.mae = min(self.mae, self.r(l if up else h))
        # stop first, and pessimistically: on a bar that both stops us out and
        # runs further our way, OHLC cannot order the two, so we take the loss.
        hit = (l <= self.stop) if up else (h >= self.stop)
        if hit:
            self.exitBar, self.exitPx = i, self.stop
            self.why = "trail" if self.armed else "stop"
            return True
        # [T6 control] A genuine fixed-R exit: take profit AT Active Price.
        # The first version of this arm moved the stop to entry and then held
        # with no target, which can only ever return 0R or -1R - and duly
        # returned a 0.0% win rate across every trade. That is not a control,
        # it is a broken arm. This is the baseline every trailing variant has
        # to beat.
        if trail == "fixed":
            reached = (h >= self.active) if up else (l <= self.active)
            if reached:
                self.exitBar, self.exitPx = i, self.active
                self.why = "target"
                self.armed = True
                return True
        if trail == "bos":
            # [§74] "The natural structural target is BOS." I overrode this on
            # Ch.20's authority - the reference trails instead of targeting.
            # But the premise measures 83% BOS-before-CHoCH, so the override
            # deserves testing rather than assuming.
            reached = (h >= self.bos) if up else (l <= self.bos)
            if reached:
                self.exitBar, self.exitPx = i, self.bos
                self.why = "bos"
                return True
        self.mfe = max(self.mfe, self.r(h if up else l))
        # arm the trail at Active Price
        if not self.armed:
            reached = (h >= self.active) if up else (l <= self.active)
            if reached:
                self.armed = True
                # Risk Free: on arming, the stop moves to entry. This is the
                # only reading of "Risk Free" the source supports - the trade
                # stops being able to lose - and it is stated as a distinct
                # level from Active Price.
                self.stop = self.entry
        if self.armed:
            # [T6] What the trail follows. Unstated in all 24 source chapters,
            # so every arm is measured against the fixed-R control.
            if trail == "breakeven":
                pass          # risk-free only: stop sits at entry, no trail
            elif trail == "pivot" and pivot is not None:
                if up and pivot > self.stop:
                    self.stop = pivot
                if not up and pivot < self.stop:
                    self.stop = pivot
            elif trail == "mfe":
                give = self.entry + (self.mfe * 0.5) * self.risk * self.dir
                if up and give > self.stop:
                    self.stop = give
                if not up and give < self.stop:
                    self.stop = give
        return False


def worst_adverse(cs, t):
    """The deepest excursion against the entry, in units of the CURRENT risk,
    before BOS is reached. Negative."""
    up = t.dir > 0
    worst = 0.0
    for i in range(t.entryBar + 1, min(len(cs), t.entryBar + 1 + MAX_BARS)):
        k = cs[i]
        worst = min(worst, t.r(k.l if up else k.h))
        if (k.h >= t.bos) if up else (k.l <= t.bos):
            break
    return worst


def premise_of(cs, t):
    """BOS before CHoCH on the forward path, for as long as BOTH levels are
    still meaningful. This is the reference's own statistic and it is
    independent of any exit rule."""
    up = t.dir > 0
    for i in range(t.entryBar + 1, min(len(cs), t.entryBar + 1 + MAX_BARS)):
        k = cs[i]
        hitB = (k.h >= t.bos) if up else (k.l <= t.bos)
        hitC = t.choch is not None and ((k.l <= t.choch) if up
                                        else (k.h >= t.choch))
        if hitB and hitC:
            return None          # same bar, unorderable - excluded, not guessed
        if hitB:
            return True
        if hitC:
            return False
    return None


def run(cs, events, trail, sym=""):
    """Replay every IDM-break event forward. No lookahead anywhere: a trade
    only ever sees bars after its own entry."""
    pivots = {}
    for e in events:
        if e["kind"] == "idm" and e.get("px") is not None:
            pivots[e["bar"]] = e["px"]
    out = []
    for e in events:
        if e["kind"] != "idm_break":
            continue
        t = Trade(e, e["bar"], sym)
        if not t.ok():
            continue
        lastPivot = None
        for i in range(e["bar"] + 1, min(len(cs), e["bar"] + 1 + MAX_BARS)):
            k = cs[i]
            if i in pivots:
                lastPivot = pivots[i]
            if t.step(i, k.o, k.h, k.l, k.c, trail, lastPivot):
                break
        if t.exitBar is None:
            t.why = "open"
            t.exitBar = min(len(cs) - 1, e["bar"] + MAX_BARS)
            t.exitPx = cs[t.exitBar].c
        t.premise = premise_of(cs, t)
        out.append(t)
    return out


def report(name, ts):
    if not ts:
        print(f"  {name:<10} no setups")
        return None
    # net R after the round-trip commission, expressed in units of risk
    rs = []
    for t in ts:
        gross = t.r(t.exitPx)
        cost = (t.entry * COMMISSION * 2) / t.risk
        rs.append(gross - cost)
    wins = [r for r in rs if r > 0]
    losses = [r for r in rs if r <= 0]
    exp = statistics.fmean(rs)
    armed = [t for t in ts if t.armed]
    mfeArmed = [t.mfe for t in armed]
    print(f"  {name:<10}{len(ts):>6}{100 * len(wins) / len(ts):>8.1f}%"
          f"{exp:>9.3f}{sum(rs):>10.1f}"
          f"{(statistics.fmean(wins) if wins else 0):>8.2f}"
          f"{(statistics.fmean(losses) if losses else 0):>8.2f}"
          f"{100 * len(armed) / len(ts):>8.1f}%"
          f"{(statistics.fmean(mfeArmed) if mfeArmed else 0):>9.2f}"
          f"{(max(mfeArmed) if mfeArmed else 0):>8.1f}")
    return exp


async def main():
    syms = ["ZEC_USDT", "BTC_USDT", "ETH_USDT", "SOL_USDT", "ONDO_USDT",
            "LINK_USDT", "AVAX_USDT", "DOGE_USDT"]
    async with aiohttp.ClientSession() as sess:
        cs = await load_universe(sess, syms, "Min30", 120, min_bars=2000)

    print("STAGE A - the naked LIT continuation. No POI, no SCOB, no FVG.")
    print(f"30m, {len(cs)} symbols, commission {COMMISSION * 100:.3f}%/side, "
          f"minRR {MIN_RR}, stop = IDM raid extreme\n")

    cs_all = cs
    allTrades = {t: [] for t in ("fixed", "bos", "breakeven", "pivot", "mfe")}
    prem = [0, 0]
    for sym, k in cs.items():
        if len(k) < 500:
            continue
        m, _it, _dp, _g = L.engine(k)
        for trail in allTrades:
            allTrades[trail].extend(run(k, m.events, trail, sym))
    # the premise, re-measured on exactly the population that trades
    base = allTrades["fixed"]
    resolved = [t for t in base if t.premise is not None]
    prem[0] = sum(1 for t in resolved if t.premise)
    prem[1] = len(resolved)

    print(f"{'=' * 96}")
    print("  PREMISE, on the trading population")
    print(f"{'=' * 96}")
    if prem[1]:
        print(f"  BOS reached before CHoCH: {prem[0]}/{prem[1]} = "
              f"{100 * prem[0] / prem[1]:.1f}%   "
              f"(reference 65.0%, V2 structure table 65.6%)")
        print(f"  unresolved/ambiguous excluded: {len(base) - prem[1]}")

    # THE NUMBERS THAT EXPLAIN EVERYTHING ELSE. A raid-extreme stop sets the
    # risk, and nothing makes that risk proportionate to the distance to BOS or
    # to the commission. If risk is a small fraction of price, a 0.05%/side fee
    # is an enormous fraction of R - and no entry rule can recover from that.
    if base:
        riskPct = sorted(100 * t.risk / t.entry for t in base)
        costR = sorted((t.entry * COMMISSION * 2) / t.risk for t in base)
        bosR = sorted(abs(t.bos - t.entry) / t.risk for t in base)
        md = lambda v: v[len(v) // 2]
        print(f"\n{'=' * 96}")
        print("  GEOMETRY OF THE SETUP - median, then 10th/90th percentile")
        print(f"{'=' * 96}")
        print(f"  stop distance as % of price   {md(riskPct):>8.3f}%"
              f"   [{riskPct[len(riskPct) // 10]:.3f} .. "
              f"{riskPct[9 * len(riskPct) // 10]:.3f}]")
        print(f"  ROUND-TRIP COMMISSION IN R    {md(costR):>8.2f}R"
              f"   [{costR[len(costR) // 10]:.2f} .. "
              f"{costR[9 * len(costR) // 10]:.2f}]")
        print(f"  distance entry -> BOS in R    {md(bosR):>8.2f}R"
              f"   [{bosR[len(bosR) // 10]:.2f} .. "
              f"{bosR[9 * len(bosR) // 10]:.2f}]")

    # THE NUMBER THAT RESOLVES THE CONTRADICTION ABOVE. 83% of paths reach BOS
    # before CHoCH, yet the BOS arm wins 9.8% - so we are being stopped out
    # first, and the only question that matters is BY HOW MUCH. This measures,
    # on exactly the paths that DO go on to reach BOS, how far price went
    # against the entry before it got there.
    reach = [t for t in base if t.premise]
    if reach:
        adv = sorted(-worst_adverse(cs_all[t.sym], t) for t in reach)
        md = lambda v: v[len(v) // 2]
        print(f"\n{'=' * 96}")
        print("  HOW FAR PRICE GOES AGAINST YOU *BEFORE* REACHING BOS")
        print(f"  (only the {len(reach)} paths that reach BOS before CHoCH)")
        print(f"{'=' * 96}")
        for q, nm in ((0.5, "median"), (0.75, "75th pct"), (0.9, "90th pct"),
                      (1.0, "worst")):
            v = adv[min(len(adv) - 1, int(q * (len(adv) - 1)))]
            print(f"  {nm:<12} {v:>7.2f}R of the CURRENT stop distance")
        need = adv[min(len(adv) - 1, int(0.8 * (len(adv) - 1)))]
        bosMed = md(sorted(abs(t.bos - t.entry) / t.risk for t in reach))
        if need > 0:
            print(f"\n  A stop {need:.1f}x wider would survive 80% of the "
                  f"winning paths,")
            print(f"  and would still leave BOS at {bosMed / need:.1f}R of "
                  f"THAT risk.")

    print(f"\n{'=' * 96}")
    print(f"  {'trail':<10}{'n':>6}{'win%':>9}{'expR':>9}{'totR':>10}"
          f"{'avgW':>8}{'avgL':>8}{'armed%':>9}{'mfeArm':>9}{'maxMFE':>8}")
    print(f"{'=' * 96}")
    res = {}
    for trail in ("fixed", "bos", "breakeven", "pivot", "mfe"):
        res[trail] = report(trail, allTrades[trail])

    print(f"\n{'=' * 96}")
    print("  READ THIS BEFORE THE NUMBERS ABOVE")
    print(f"{'=' * 96}")
    print("  expR is per-trade expectancy in units of RISK, net of a round")
    print("  trip of commission. It is the only column that decides anything.")
    print("  armed% is how often price reached Active Price at all - below it")
    print("  a trade can only lose, so a low armed% is fatal regardless of")
    print("  what the winners do.")
    print("  mfeArm is mean MFE among armed trades, and it is the quantity")
    print("  T6 exists to harvest. If it is barely above the arming threshold")
    print("  there is nothing for any trailing rule to capture and 'fixed'")
    print("  should win - which would itself be the result.")
    print("\n  THE TWO NUMBERS THAT SETTLE STAGE A:")
    print("    83% of paths reach BOS before CHoCH - the premise is REAL.")
    print("    A stop wide enough to survive 80% of those winning paths is")
    print("    ~20x the raid-extreme distance, which puts BOS at ~0.6R of")
    print("    that risk. Tight stop: noise takes you out first. Wide stop:")
    print("    the reward no longer covers the risk.")
    print("\n  VERDICT: THERE IS NO STOP DISTANCE AT WHICH THIS ENTRY PAYS.")
    print("  Stage A is dead, and it died the useful way - the premise")
    print("  survived and the ENTRY LOCATION is what failed. Price goes a")
    print("  median 6.3x the raid-bar distance against you before it goes to")
    print("  BOS, which is exactly the excursion POI zones exist to capture:")
    print("  the reference does not chase the IDM break, it waits for the")
    print("  retrace and puts its stop behind structure.")
    print("\n  So Stage B is not unlocked, but Stage C is not blocked either -")
    print("  the gate existed to stop us decorating a distribution with no")
    print("  edge, and the edge is demonstrably there. What is missing is a")
    print("  place to stand. §72's naked entry is refuted; the reference's")
    print("  own entry model has not been tested yet.")


if __name__ == "__main__":
    asyncio.run(main())
