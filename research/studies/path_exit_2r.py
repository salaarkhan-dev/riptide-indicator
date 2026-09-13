"""THE DECISION AT 2R. Does the route to the target say whether to let it run?

THIS IS THE SECOND PASS AT PATH DEPENDENCE, NOT THE FIRST.
`research/studies/path_exit.py` already asked whether the path predicts, and
answered it on 9699 signals: the path predicts POWERFULLY and converts to
nothing. A trade that reaches 1R fast and clean is twice as likely to reach 2R
(57% against 29%) and every path-conditional policy still came in below flat
3R. Its own summary of why is the sentence this study starts from —

    "Filtering on a predictor only helps when the excluded group is NEGATIVE,
     and this one is merely less positive. A prediction is not a decision."

so nothing here re-asks whether the path predicts. It takes three specific
weaknesses that study named or left open, and closes them.

  1. IT CONDITIONED AT 1R, NOT AT THE BRANCH POINT. Features were read when 1R
     was first touched, because that is provably before the policies diverge.
     Safe, but early: everything between 1R and 2R is discarded, and that is
     exactly the stretch a person watching the trade would be reading. Here the
     features are read at the 2R touch itself, from bars that CLOSED strictly
     before it — the latest moment that is still not lookahead.

  2. ITS TWO FEATURES WERE THE SAME INFORMATION, and it said so: "give-back
     still correlates heavily with plain adverse excursion... clean-vs-choppy
     is therefore close to small-MAE-vs-large-MAE, which is why it splits
     almost identically to fast-vs-slow." So a null across them is one test,
     not two. The four here are deliberately less collinear: elapsed bars, MAE
     against entry, give-back from the RUNNING PEAK, and a close-based test of
     whether price ever fell back under 1R after closing above it.

  3. EVERY POLICY WAS SCORED AGAINST PLAIN 2R ALONE. That is what left flat 3R
     on top at +2.1 SE with four paragraphs of hedging around it, because
     beating 2R is not the claim — a path rule has to beat the blind long
     target as well, or it is a longer target wearing a costume. Here a rule
     must clear BOTH always-2R and always-3R, and an inverted control besides.

  4. ITS THRESHOLDS WERE FULL-SAMPLE MEDIANS. Declared in advance and not
     swept, so not fitted — but read on the same rows they were computed from.
     Here they come off a discovery half and are read once on the other, in
     both assignments, the bar funding_holdout.py set.

──────────────────────────────────────────────────────────────────────────────
THE DESIGN, AND WHY IT HAS MORE POWER THAN ANYTHING ELSE HERE

Control and treatment are THE SAME TRADE until the instant 2R is touched. A
trade that never reaches 2R is byte-identical in both arms — same fill, same
stop, same timeout — so it contributes EXACTLY ZERO to the paired difference
and adds no variance to it. The effective sample is the 2R-reachers alone.

NO SECOND SCORER. The bug that cost this project ten rewrites was every script
keeping its own copy of the outcome loop. So nothing here scores a trade:

    control    = simulate(target_r=2.0)          exit at 2R
    hold       = simulate(target_r=3.0)          run it, ORIGINAL stop
    reached 2R = control.exit == "target"
    touch bar  = control.exit_bar

and a conditional rule is just `hold.r if (reached and P) else control.r`. The
harness decides every outcome; this file only decides which of the two to read.

TRAILING AND BREAK-EVEN ARE OUT, BY INSTRUCTION, AND IT COSTS THIS LAB
SOMETHING. "Hold to 3R with the ORIGINAL stop" is the only form of "let it run"
the ban list permits, and it is the harshest one: a trade that reaches 2R and
reverses gives back the whole 3R. The reading is therefore asymmetric — if path
dependence shows up even under the harshest hold rule it is real, and a gentler
rule would only help; if it does not, this has ruled out the harsh version and
NOT the gentle one. `path_exit.py` did test the locked runner (arm at 2R, lock
at 2R, run to 3R) and found it positive but beaten by flat 3R, so the gentle
version is not unmeasured — it is measured and it did not win either.

THE HORIZON IS A REAL CONSTRAINT, NOT AN ARTEFACT. TRACK_HORIZON_BARS is 60, so
a trade that reaches 2R on bar 55 has five bars to make 3R and is then marked
to market at the close. That is what the live tracker does.

──────────────────────────────────────────────────────────────────────────────
PRE-REGISTERED, BEFORE THE FIRST NUMBER

  THE FOUR CANDIDATE PATHS, fixed here in source. Each is a rule of the form
  "hold to 3R when the path to 2R was X, otherwise take 2R". Thresholds are
  medians computed on the DISCOVERY half only:

      P1  FAST        bars from fill to the 2R touch <= discovery median
      P2  SHALLOW     MAE before the touch >= discovery median (went against
                      it less; MAE is negative, so >= is shallower)
      P3  CLEAN       price never CLOSED back below 1R after first closing
                      above it — the "0 -> 1R -> 2R" path rather than
                      "0 -> 1R -> retrace -> 2R"
      P4  EFFICIENT   largest give-back from the running peak, before the
                      touch, <= discovery median

  PRIMARY. On the HELD-OUT half, R per signal of the winning discovery rule
  against BOTH blind policies — always-2R and always-3R — paired, at 2 SE.

  THE INTERACTION IS THE CLAIM. The same rule inverted — hold on the OTHER side
  of the cut — is reported beside it. Path dependence means holding pays on one
  side and not the other. If both sides pay, the finding is about 3R.

  BOTH HALF-ASSIGNMENTS, because which half is called "discovery" is arbitrary.

  MULTIPLE COMPARISONS, COUNTED. Four candidates, two half-assignments, eight
  looks. At 5% that is 0.4 expected false positives — so a single rule at 2 SE
  in one assignment is noise, and only agreement across both counts.

  WHAT WOULD FALSIFY IT. The winning discovery rule failing to beat EITHER
  blind policy on the held-out half, in EITHER assignment. Or the inverted rule
  paying as much as the rule.

  EXPECTATION, recorded so it cannot be revised. I expect P3 (CLEAN) to lead on
  discovery and to die on the held-out read. If anything survives I expect P1
  (FAST), the one feature that is not a restatement of "it did not retrace". I
  expect flat 3R to beat flat 2R by about the +2.1 SE `path_exit.py` measured.

    PYTHONPATH=. RIPTIDE_MIN_GRADE=B RIPTIDE_DEEP_CACHE=/tmp/deep \\
        python3 research/studies/path_exit_2r.py

──────────────────────────────────────────────────────────────────────────────
RESULT, 13 Sep 2026 — NO PATH RULE SURVIVES, AND THE FLAT 3R ROW IS WORSE THAN
IT LOOKED.

8953 A/B signals, 101 symbols, 333 days, Min30. 2212 reach 2R (25%), and those
are the entire effective sample. 1572 of them go on to 3R (71%), 640 give it
back. MDE at 2 SE for a rule holding half the reachers is 0.0115 R per signal.

  NOTHING CLEARS THE BAR, IN EITHER ASSIGNMENT.

    discover on first, read on second   P4 EFFICIENT  vs 2R +2.3   vs 3R -2.8
    discover on second, read on first   P1 FAST       vs 2R -0.1   vs 3R +1.2

  The first assignment is exactly the failure mode the design was built to
  catch. The rule beats always-2R at +2.3 SE — on its own that reads as a
  finding — and loses to always-3R at -2.8 on the same rows. The inverted
  control settles it: holding the OTHER half beats 2R by MORE, at +2.8. Both
  sides pay, so the split is doing nothing; the rule is catching half of a
  blanket 3R benefit. Scored against plain 2R alone, this study would have
  reported a path effect at +2.3 SE.

  The second assignment loses even that: -0.1 against 2R, and the two
  assignments do not even pick the same candidate (P4 then P1) — four rules
  whose discovery lifts sit within 0.003 R of each other are being separated
  by noise.

  THE UNPLANNED RESULT, AND IT IS THE ONE THAT MATTERS. Flat 3R over the whole
  window is +0.0147 ±0.0081, +1.8 SE — close to `path_exit.py`'s +2.1 on its
  own sample, so the replication holds. Split in two it REVERSES:

      first half    always 2R +0.0157   always 3R +0.0060   diff -0.0097  -0.8
      second half   always 2R +0.0045   always 3R +0.0437   diff +0.0391  +3.6

  The entire flat-3R advantage lives in the second half of the window, and the
  first half points the other way. That is the two-halves check this project
  applies to everything, and the row fails it outright. `path_exit.py` listed
  four reasons to discount its +2.1 SE and one reason not to; this is a fifth
  and the strongest. Flat 3R is not a marginal result worth forward data — it
  is a window effect, and it should come off the watch list rather than onto
  it.

  MY EXPECTATIONS WERE WRONG IN BOTH DIRECTIONS AND THAT IS THE USEFUL PART. I
  predicted P3 (CLEAN) would lead on discovery; it led in neither assignment
  and came last in one. I predicted flat 3R would reproduce at about +2.1 SE;
  it reproduced at +1.8 and then dissolved when halved, which no amount of
  re-running the full window would have shown.

WHAT THIS CLOSES, TOGETHER WITH path_exit.py. Path-dependent exits as a family,
under a hold rule that keeps the original stop. Two studies, eleven rules
between them, two feature sets, two conditioning points (1R and 2R), full-
sample and held-out thresholds. The path predicts and does not pay, and the
blind long target that kept topping the board turns out to be half a window.
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import statistics                                       # noqa: E402

import aiohttp                                          # noqa: E402

from riptide.config import CFG                          # noqa: E402
from riptide.engine import atr_series, grade_of, run_engine  # noqa: E402
from riptide.exchange import fetch_candles, list_symbols  # noqa: E402
from riptide.trend import di_at, direction_at, poi_at   # noqa: E402
from research.deep import load_universe                 # noqa: E402
from research.harness import mean_se, simulate          # noqa: E402

DAYS = 333
INTERVAL = "Min30"
BASE_R, HOLD_R = 2.0, 3.0


class Row:
    """One signal, scored twice, with the route between the two recorded."""
    __slots__ = ("sym", "t", "kind", "is_long", "risk_pct",
                 "base", "hold", "reached", "bars", "mae", "clean", "give")


def path_of(cs, fill_bar, touch_bar, entry, stop, is_long):
    """Path features over CLOSED bars strictly before the 2R touch.

    Returns (bars, mae, clean, giveback), all in R except `bars`.

    The touch bar itself is excluded on purpose. Its high and low cannot be
    ordered against each other, so anything read from it is a fact the trader
    did not have when the 2R limit filled. research/harness.py refuses to
    resolve a target on the fill bar for the identical reason.
    """
    risk = abs(entry - stop)
    if risk <= 0 or touch_bar is None or fill_bar is None:
        return None
    mae, peak, give = 0.0, 0.0, 0.0
    above1 = clean = True
    seen1 = False
    for k in range(fill_bar, touch_bar):
        c = cs[k]
        # For a short the FAVOURABLE extreme is the bar's low and the adverse
        # one its high, so both are written out rather than sign-flipped.
        fav = (c.h - entry) / risk if is_long else (entry - c.l) / risk
        adv = (c.l - entry) / risk if is_long else (entry - c.h) / risk
        mae = min(mae, adv)
        peak = max(peak, fav)
        give = max(give, peak - fav)
        # CLOSE, not intrabar: a wick back under 1R that closes above it is not
        # a retracement, and a bar's high cannot be ordered against its low.
        cl = (c.c - entry) / risk if is_long else (entry - c.c) / risk
        if cl >= 1.0:
            seen1, above1 = True, True
        elif seen1 and above1:
            above1, clean = False, False
    return touch_bar - fill_bar, mae, (clean if seen1 else True), give


async def collect(sess, candles):
    """Every A/B signal, scored at 2R and at 3R, with the route recorded.

    The signal set, the grade floor and the POI gate are copied from
    entry_deep.py deliberately — this lab has to be comparable with the two it
    is the third of, and forking the selection would make its numbers
    incommensurable with theirs.
    """
    rows = []
    for sym, cs in candles.items():
        early = []
        try:
            setups = run_engine(sym, cs, CFG, early_out=early)
        except Exception:
            continue
        idx = {c.t: i for i, c in enumerate(cs)}
        atr = atr_series(cs, CFG.atr_len)
        for kind, batch in (("confirmed", setups), ("early", early)):
            for x in batch:
                i = idx.get(x.detected_time)
                if i is None or x.entry <= 0 or abs(x.entry - x.stop) <= 0:
                    continue
                if not (atr[i] if i < len(atr) else 0.0):
                    continue
                w = x.detected_time
                poi = await poi_at(sess, sym, w, x.stop, x.is_long,
                                   fetch_candles)
                if not (True if poi is None else bool(poi)):
                    continue
                d = await direction_at(sess, sym, w, fetch_candles)
                di = await di_at(sess, sym, w, fetch_candles)
                if grade_of(kind == "early", True, d or 0, x.is_long,
                            di or 0)[0] not in "AB":
                    continue

                o2 = simulate(cs, i, x.entry, x.stop, x.is_long,
                              target_r=BASE_R)
                o3 = simulate(cs, i, x.entry, x.stop, x.is_long,
                              target_r=HOLD_R)
                z = Row()
                z.sym, z.t, z.kind, z.is_long = sym, w, kind, bool(x.is_long)
                z.risk_pct = 100 * abs(x.entry - x.stop) / x.entry
                z.base, z.hold = o2.r, o3.r
                z.reached = o2.filled and o2.exit == "target"
                z.bars = z.mae = z.give = None
                z.clean = None
                if z.reached:
                    got = path_of(cs, o2.fill_bar, o2.exit_bar, x.entry,
                                  x.stop, x.is_long)
                    if got:
                        z.bars, z.mae, z.clean, z.give = got
                    else:
                        z.reached = False
                rows.append(z)
    return rows


def med(vals):
    v = [x for x in vals if x is not None]
    return statistics.median(v) if v else 0.0


# The four candidates, fixed before the run. Each takes the discovery-half
# medians and returns a predicate on a row: True means HOLD to 3R.
CANDIDATES = [
    ("P1  FAST  to 2R", lambda m: (lambda z: z.bars <= m["bars"])),
    ("P2  SHALLOW  MAE", lambda m: (lambda z: z.mae >= m["mae"])),
    ("P3  CLEAN  no dip under 1R", lambda m: (lambda z: z.clean)),
    ("P4  EFFICIENT  small giveback", lambda m: (lambda z: z.give <= m["give"])),
]


def apply(rows, pred, invert=False):
    """R per signal under 'hold when pred, else take 2R'."""
    out = []
    for z in rows:
        if z.reached and (pred(z) != invert):
            out.append(z.hold)
        else:
            out.append(z.base)
    return out


def paired(a, b):
    d = [x - y for x, y in zip(a, b)]
    if len(d) < 2:
        return 0.0, 0.0
    return statistics.fmean(d), statistics.pstdev(d) / len(d) ** 0.5


def medians(rows):
    hit = [z for z in rows if z.reached]
    return dict(bars=med([z.bars for z in hit]),
                mae=med([z.mae for z in hit]),
                give=med([z.give for z in hit]))


def arm(label, vals, base, hold):
    md, sd = paired(vals, base)
    mh, sh = paired(vals, hold)
    zb = md / sd if sd else 0.0
    zh = mh / sh if sh else 0.0
    print(f"  {label:<30}{statistics.fmean(vals):>+10.4f}"
          f"{md:>+10.4f}{zb:>+7.1f}{mh:>+11.4f}{zh:>+7.1f}"
          + ("   BEATS BOTH" if zb >= 2 and zh >= 2 else ""))
    return zb, zh


async def main():
    async with aiohttp.ClientSession() as sess:
        syms = await list_symbols(sess)
        candles = await load_universe(sess, syms, INTERVAL, DAYS)
        rows = await collect(sess, candles)

    rows.sort(key=lambda z: z.t)
    hit = [z for z in rows if z.reached]
    print("THE PATH-DEPENDENT EXIT LAB")
    print(f"{len(rows)} A/B signals, {len(candles)} symbols, {DAYS} days, "
          f"{INTERVAL}.")
    print(f"{len(hit)} of them reach {BASE_R:g}R "
          f"({len(hit) / max(len(rows), 1):.0%}) — those are the only rows "
          f"where the\ntwo arms can differ, so they are the whole effective "
          f"sample.")

    base = [z.base for z in rows]
    hold = [z.hold for z in rows]
    md, sd = paired(hold, base)
    print(f"\n{'=' * 96}\nTHE BLIND POLICIES, for reference\n{'=' * 96}")
    print(f"  always {BASE_R:g}R                    "
          f"{statistics.fmean(base):>+10.4f} R per signal")
    print(f"  always {HOLD_R:g}R                    "
          f"{statistics.fmean(hold):>+10.4f} R per signal"
          f"   paired {md:+.4f} ±{sd:.4f}"
          f"  {md / sd if sd else 0:+.1f} SE")
    if hit:
        on = sum(1 for z in hit if z.hold > z.base)
        print(f"\n  of the {len(hit)} that reached {BASE_R:g}R, {on} went on to "
              f"{HOLD_R:g}R ({on / len(hit):.0%}) and\n  {len(hit) - on} gave "
              f"it back. that ratio is why the blind version is a wash.")
        print(f"\n  path of the {BASE_R:g}R-reachers: median "
              f"{med([z.bars for z in hit]):.0f} bars to target, median MAE "
              f"{med([z.mae for z in hit]):+.2f} R,\n  median giveback "
              f"{med([z.give for z in hit]):.2f} R, "
              f"{sum(1 for z in hit if z.clean) / len(hit):.0%} never closed "
              f"back under 1R.")
        sd_h = statistics.pstdev([z.hold - z.base for z in hit])
        print(f"\n  POWER. the paired difference is zero on every row that "
              f"misses {BASE_R:g}R, so\n  its sd over all {len(rows)} signals "
              f"is {statistics.pstdev([a - b for a, b in zip(hold, base)]):.3f}"
              f" (sd {sd_h:.2f} on the {len(hit)} reachers).\n  a rule holding "
              f"half of them moves ~{len(hit) // 2} rows; MDE at 2 SE is about "
              f"{2 * sd_h * (len(hit) // 2) ** 0.5 / len(rows):.4f} R "
              f"per signal.")

    mid = rows[len(rows) // 2].t
    first = [z for z in rows if z.t <= mid]
    second = [z for z in rows if z.t > mid]

    # THE TWO-HALVES CHECK, APPLIED TO THE BLIND POLICY ITSELF. path_exit.py
    # left flat 3R on the board at +2.1 SE with four reasons to discount it.
    # None of them was this one: an advantage that lives in one half of the
    # window is a non-result by the same standard every filter here was held
    # to, and it is cheaper to check than any of the four.
    print(f"\n  THE TWO-HALVES CHECK ON THE BLIND ROW — the one thing "
          f"path_exit.py\n  did not ask about its own best policy.")
    print(f"  {'':<14}{'always ' + f'{BASE_R:g}R':>12}"
          f"{'always ' + f'{HOLD_R:g}R':>12}{'diff':>10}{'SE':>8}")
    for lab, half in (("first half", first), ("second half", second)):
        hb = [z.base for z in half]
        hh = [z.hold for z in half]
        d, s = paired(hh, hb)
        print(f"  {lab:<14}{statistics.fmean(hb):>+12.4f}"
              f"{statistics.fmean(hh):>+12.4f}{d:>+10.4f}"
              f"{d / s if s else 0:>+8.1f}")

    verdicts = []
    for tag, disc, hold_half in (("first -> second", first, second),
                                 ("second -> first", second, first)):
        a, b = tag.split(" -> ")
        print(f"\n{'=' * 96}\nDISCOVER ON THE {a.upper()} HALF, READ ON THE "
              f"{b.upper()}\n{'=' * 96}")
        m = medians(disc)
        dh = [z for z in disc if z.reached]
        print(f"  discovery: {len(disc)} signals, {len(dh)} reach "
              f"{BASE_R:g}R.  cuts: bars<={m['bars']:.0f}  "
              f"mae>={m['mae']:+.2f}  giveback<={m['give']:.2f}")
        db, dhold = [z.base for z in disc], [z.hold for z in disc]
        print(f"\n  {'candidate':<30}{'R/signal':>10}{'vs 2R':>10}{'SE':>7}"
              f"{'vs 3R':>11}{'SE':>7}")
        best, best_lift = None, -9e9
        for name, mk in CANDIDATES:
            pred = mk(m)
            v = apply(disc, pred)
            lift, _ = paired(v, db)
            arm(name, v, db, dhold)
            if lift > best_lift:
                best, best_lift, best_pred = name, lift, pred
        print(f"\n  DISCOVERY PICKED: {best}  "
              f"(+{best_lift:.4f} R per signal over always {BASE_R:g}R)")

        hb = [z.base for z in hold_half]
        hh = [z.hold for z in hold_half]
        nh = sum(1 for z in hold_half if z.reached and best_pred(z))
        print(f"\n  {'HELD-OUT half':<30}{'R/signal':>10}{'vs 2R':>10}{'SE':>7}"
              f"{'vs 3R':>11}{'SE':>7}")
        print(f"  {'always ' + f'{BASE_R:g}R':<30}"
              f"{statistics.fmean(hb):>+10.4f}")
        print(f"  {'always ' + f'{HOLD_R:g}R':<30}"
              f"{statistics.fmean(hh):>+10.4f}")
        zb, zh = arm("the rule", apply(hold_half, best_pred), hb, hh)
        izb, _ = arm("  INVERTED (the control)",
                     apply(hold_half, best_pred, invert=True), hb, hh)
        print(f"\n  the rule holds {nh} of the "
              f"{sum(1 for z in hold_half if z.reached)} reachers on this half.")
        verdicts.append((tag, best, zb, zh, izb))

    print(f"\n{'=' * 96}\nVERDICT\n{'=' * 96}")
    for tag, name, zb, zh, izb in verdicts:
        ok = zb >= 2 and zh >= 2
        note = ""
        if ok and izb >= zb * 0.7:
            note = "  — but the INVERTED rule pays too: not path dependence"
            ok = False
        print(f"  {tag:<18}{name:<30}vs 2R {zb:+.1f} SE   vs 3R {zh:+.1f} SE"
              f"   {'HELD' if ok else 'FAILED'}{note}")
    held = [v for v in verdicts if v[2] >= 2 and v[3] >= 2 and v[4] < v[2] * 0.7]
    if len(held) == 2 and held[0][1] == held[1][1]:
        print(f"\n  {held[0][1]} beat BOTH blind policies on BOTH "
              f"half-assignments, with the\n  inverted control failing. That "
              f"is the bar this project sets, and it is\n  the first exit "
              f"result to clear it.")
    else:
        print("\n  No rule beat both blind policies on both half-assignments.")
        print("  The route to 2R does not carry information the level does")
        print("  not — at least not under a hold rule that keeps the original")
        print("  stop, which is the only form the ban list permits.")


if __name__ == "__main__":
    asyncio.run(main())
