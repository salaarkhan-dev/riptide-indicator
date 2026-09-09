"""One scorer, one reporting format, for every strategy question.

WHY THIS EXISTS
---------------
Every measurement in this project used to be a throwaway script with its own
copy of the scoring loop. On 7 Sep all of them turned out to share a bug: the
fill check and the outcome loop were separate, so a signal that filled on bar
i+5 was scored as though the position had existed since i+1. Entries are
RETRACEMENTS — before the fill, price sits on the profitable side of the entry
— so the error manufactured wins and almost never losses. It inflated early
signals by +0.115 R (9.1 SE) and confirmed by +0.135 (4.2 SE), and it survived
ten rewrites because each rewrite was a fresh chance to make the same mistake.

So the rule is: nothing measures anything by hand any more. A new question
supplies a feature function; this file supplies the outcome, the buckets, the
standard errors, the splits and the controls. If the scorer is wrong it is
wrong in one place, its tests fail, and every past result is re-runnable.

WINDOWS COME FROM riptide.config
--------------------------------
The old scripts used 12 fill bars and a 48-bar horizon while the live tracker
used 10 and 60, so backtests answered a different question from /stats without
anyone noticing. They are imported here, not retyped.

CONVENTIONS, FIXED
------------------
- Outcome is measured from the FILL bar. Never from the signal bar.
- Unfilled scores 0.0 and pays no fee. It is not a loss; it is a trade that
  did not happen, and dropping those rows instead would flatter every result
  that fills less often.
- Stop and target are checked intrabar. When one bar spans both, the STOP
  wins: bar data cannot resolve order, and the pessimistic read is the only
  honest one.
- A break-even stop arms on the CLOSE, not intrabar, for the same reason.
- Fees are charged once per filled trade, in R: FEE_PCT / risk_pct.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass

from riptide.config import TRACK_FILL_BARS, TRACK_HORIZON_BARS, TRACK_TARGET_R

# MEXC 0.02% maker + 0.06% taker. Cost in R is FEE_PCT / risk_pct, so a WIDE
# stop is cheaper per unit of risk, not dearer — the opposite of intuition.
FEE_PCT = 0.08


@dataclass
class Outcome:
    r: float                  # net R. Unfilled is 0.0, not a loss.
    filled: bool
    fill_bar: int | None
    mfe: float                # best excursion in R, from the fill
    mae: float                # worst, from the fill
    exit_bar: int | None
    # WHY the trade ended: "stop", "target", "timeout", or "" when it never
    # filled. Trailing with a default so every positional construction in the
    # existing studies keeps working untouched.
    #
    # Added because "win rate" alone cannot answer the question that actually
    # gets asked — how many were stopped, how many timed out, how many never
    # happened. A timeout that closes a hair above entry counts as a win under
    # `r > 0` and is nothing of the sort.
    exit: str = ""


def simulate(cs, signal_bar: int, entry: float, stop: float, is_long: bool, *,
             target_r: float = TRACK_TARGET_R,
             fill_bars: int = TRACK_FILL_BARS,
             horizon_bars: int = TRACK_HORIZON_BARS,
             be_arm_r: float = 0.0, be_lock_r: float = 0.0,
             part_at_r: float = 0.0, part_to_r: float = 0.0,
             trail: list | None = None,
             fee_pct: float = FEE_PCT,
             fee_maker: float = 0.0,
             fee_taker: float = 0.06) -> Outcome:
    """One trade, scored from the bar the entry was actually touched on.

    `trail`, when given, is a per-bar list of candidate stop levels — a
    structural line to rest the stop under, indexed the same as `cs`, with
    None on bars where there is none. It lives HERE rather than in a study's
    private copy for the reason the simulate_market docstring already gives:
    research/studies/mss_entry.py kept its own copy of a scorer and got the
    entry bar wrong, silently, for as long as nobody compared them.

    THE STOP ONLY EVER MOVES IN THE TRADE'S FAVOUR. A structural line can fall
    as well as rise, and a stop that follows it down would widen the risk after
    entry — which is not a stop, it is a hope. When the line vanishes the stop
    freezes where it was.

    The level for bar k is read from `trail[k - 1]`, never `trail[k]`: a line
    is only extended once bar k-1 has closed, so using bar k's own value would
    place the stop using a level that did not exist while the bar traded.
    """
    risk = abs(entry - stop)
    if risk <= 0 or entry <= 0:
        return Outcome(0.0, False, None, 0.0, 0.0, None)
    sgn = 1 if is_long else -1
    lvl = lambda r: entry + sgn * risk * r

    fill = None
    for k in range(signal_bar + 1, min(signal_bar + 1 + fill_bars, len(cs))):
        if (cs[k].l <= entry) if is_long else (cs[k].h >= entry):
            fill = k
            break
    if fill is None:
        return Outcome(0.0, False, None, 0.0, 0.0, None)

    # Fees, honestly. The entry is always a LIMIT order at the gap, so it pays
    # maker. The exit depends on how the trade ends: a target is a limit
    # (maker), a stop is a market order (taker). Charging taker on both sides
    # of every trade — which the flat fee_pct does — overstates the cost of
    # every winner. fee_maker/fee_taker model it properly; fee_pct alone keeps
    # the old flat behaviour so earlier numbers stay reproducible.
    fee_win = fee_maker * 2 if fee_maker else fee_pct
    fee_lose = (fee_maker + fee_taker) if fee_maker else fee_pct
    to_r = 1.0 / (100 * risk / entry)
    cur_stop, armed, part_done, banked, size = stop, False, False, 0.0, 1.0
    tgt = part_at_r or target_r
    mfe = mae = 0.0

    for k in range(fill, min(fill + horizon_bars, len(cs))):
        c = cs[k]
        fav = (c.h - entry) / risk if is_long else (entry - c.l) / risk
        adv = (c.l - entry) / risk if is_long else (entry - c.h) / risk
        mfe, mae = max(mfe, fav), min(mae, adv)

        # Raise the stop to the structural line BEFORE testing it, using the
        # previous bar's level — see the docstring. Never in the losing
        # direction, and never past the entry into a guaranteed profit that
        # the trade has not earned.
        if trail is not None and k - 1 >= 0 and k - 1 < len(trail):
            lv_ = trail[k - 1]
            if lv_ is not None:
                cur_stop = max(cur_stop, lv_) if is_long \
                    else min(cur_stop, lv_)

        if (c.l <= cur_stop) if is_long else (c.h >= cur_stop):
            r = banked + size * sgn * (cur_stop - entry) / risk
            return Outcome(r - fee_lose * to_r, True, fill, mfe, mae, k,
                           "stop")
        # On the FILL bar the target cannot resolve, and this is not fussiness.
        # A long entry is approached from ABOVE, so the bar's high may well
        # have printed before price came down to the entry — counting it as a
        # win credits a move the position was not open for. The STOP has no
        # such ambiguity: it sits beyond the entry, so reaching it means price
        # passed through the fill and kept going. Hence stop yes, target no.
        # riptide/tracker.py still resolves both on the fill bar and is
        # therefore mildly optimistic; see the note in research/README.md.
        if k == fill:
            continue
        if (c.h >= lvl(tgt)) if is_long else (c.l <= lvl(tgt)):
            if part_at_r and not part_done:
                banked += 0.5 * part_at_r
                size, part_done, tgt = 0.5, True, part_to_r
                cur_stop, armed = lvl(be_lock_r), True
                continue
            return Outcome(banked + size * tgt - fee_win * to_r,
                           True, fill, mfe, mae, k, "target")
        if be_arm_r and not armed:
            if (c.c >= lvl(be_arm_r)) if is_long else (c.c <= lvl(be_arm_r)):
                cur_stop, armed = lvl(be_lock_r), True

    last = min(fill + horizon_bars, len(cs)) - 1
    r = banked + size * sgn * (cs[last].c - entry) / risk
    return Outcome(r - fee_lose * to_r, True, fill, mfe, mae, last, "timeout")


def simulate_market(cs, signal_bar: int, entry: float, stop: float,
                    is_long: bool, *, target_r: float = TRACK_TARGET_R,
                    target_px: float | None = None,
                    horizon_bars: int = TRACK_HORIZON_BARS,
                    be_arm_r: float = 0.0, be_lock_r: float = 0.0,
                    part_at_r: float = 0.0, part_to_r: float = 0.0,
                    fee_maker: float = 0.02,
                    fee_taker: float = 0.06) -> Outcome | None:
    """A MARKET entry taken at `entry` on the CLOSE of `signal_bar`.

    simulate() cannot express this. It fills a limit by waiting for price to
    come back to the level, which for a long means waiting for a move DOWN; a
    market order is filled at once and pays TAKER on the way in.

    THE ENTRY BAR RESOLVES NOTHING — neither the stop nor the target.

    research/studies/mss_entry.py has a local copy of this helper that lets the
    STOP resolve on the entry bar, and that is wrong in a way worth spelling
    out. The entry is the bar's CLOSE, so every tick of that bar printed before
    the position existed. A long whose bar dipped 1.6 ATR below its own close
    has not been stopped out; it has been entered at the close of a large
    candle. Counting it as a loss makes market entries look worse than they
    are, which matters because that study's finding was that market entries
    lose. The Pine indicator this was written for gets it right
    (`bar_index > simulatedEntryBar`), and so does this.

    Everything else mirrors simulate() exactly so the two are comparable: stop
    wins a bar spanning both, fees are charged in R as fee / risk_pct, and a
    trade still open at the horizon is marked out at the close.

    Returns None — not an Outcome — when there is no room to score: no risk, or
    no bar after the entry. A zero would be a trade that happened and broke
    even, and this is a trade that cannot be measured.
    """
    risk = abs(entry - stop)
    if risk <= 0 or entry <= 0 or signal_bar >= len(cs) - 1:
        return None
    sgn = 1 if is_long else -1
    lvl = lambda r: entry + sgn * risk * r
    to_r = 1.0 / (100 * risk / entry)
    # Market in, so taker on entry. Out is maker on a target (a resting limit)
    # and taker on a stop (a market order), the same split simulate() uses.
    # One fee per trade, charged by how it ENDS — including for a partial,
    # which simulate() also approximates this way. Keeping the two scorers
    # identical matters more here than a second decimal place on the fee.
    fee_win = (fee_taker + fee_maker) * to_r
    fee_lose = (fee_taker + fee_taker) * to_r
    # Break-even and partial management, mirroring simulate() exactly: the
    # stop can move, a partial banks half at part_at_r and runs the rest to
    # part_to_r, and a break-even stop arms on the CLOSE rather than intrabar
    # because bar data cannot resolve order within a bar.
    cur_stop, armed, part_done, banked, size = stop, False, False, 0.0, 1.0
    tgt_r = part_at_r or target_r
    fixed_px = target_px if (target_px is not None and not part_at_r) else None
    mfe = mae = 0.0

    for k in range(signal_bar + 1, min(signal_bar + 1 + horizon_bars, len(cs))):
        c = cs[k]
        fav = (c.h - entry) / risk if is_long else (entry - c.l) / risk
        adv = (c.l - entry) / risk if is_long else (entry - c.h) / risk
        mfe, mae = max(mfe, fav), min(mae, adv)
        if (c.l <= cur_stop) if is_long else (c.h >= cur_stop):
            r = banked + size * sgn * (cur_stop - entry) / risk
            return Outcome(r - fee_lose, True, signal_bar, mfe, mae, k, "stop")
        tgt = fixed_px if fixed_px is not None else lvl(tgt_r)
        if (c.h >= tgt) if is_long else (c.l <= tgt):
            if part_at_r and not part_done:
                banked += 0.5 * part_at_r
                size, part_done, tgt_r = 0.5, True, part_to_r
                cur_stop, armed = lvl(be_lock_r), True
                continue
            hit_r = (sgn * (tgt - entry) / risk if fixed_px is not None
                     else tgt_r)
            return Outcome(banked + size * hit_r - fee_win,
                           True, signal_bar, mfe, mae, k, "target")
        if be_arm_r and not armed:
            if (c.c >= lvl(be_arm_r)) if is_long else (c.c <= lvl(be_arm_r)):
                cur_stop, armed = lvl(be_lock_r), True
    last = min(signal_bar + 1 + horizon_bars, len(cs)) - 1
    r = banked + size * sgn * (cs[last].c - entry) / risk
    return Outcome(r - fee_lose, True, signal_bar, mfe, mae, last, "timeout")


def mean_se(v) -> tuple[float, float]:
    if not v:
        return 0.0, 0.0
    if len(v) == 1:
        return v[0], 0.0
    return statistics.fmean(v), statistics.stdev(v) / len(v) ** 0.5


def quartiles(vals) -> list[float]:
    s = sorted(vals)
    return [s[len(s) * k // 4] for k in (1, 2, 3)]


def buckets(rows, feature, edges=None, labels=None):
    """[(label, [r, ...])]. edges=None splits the feature into quartiles;
    a binary feature (only 0/1 present) becomes two buckets automatically."""
    vals = [feature(x) for x in rows]
    vals = [v for v in vals if v is not None]
    if not vals:
        return []
    if set(vals) <= {0, 1, True, False}:
        return [("no", [x.r for x in rows if not feature(x)]),
                ("yes", [x.r for x in rows if feature(x)])]
    if edges is None:
        edges = quartiles(vals)
    cuts = [-float("inf")] + list(edges) + [float("inf")]
    out = []
    for n, (lo, hi) in enumerate(zip(cuts, cuts[1:])):
        lab = labels[n] if labels else f"{lo:.3g}"
        out.append((lab, [x.r for x in rows
                          if feature(x) is not None and lo <= feature(x) < hi]))
    return out


SPLITS = (
    ("all", lambda x: True),
    ("symbols A", lambda x: x.split_symbol == 0),
    ("symbols B", lambda x: x.split_symbol == 1),
    ("window 1st half", lambda x: x.split_window),
    ("window 2nd half", lambda x: not x.split_window),
)


def report(name: str, rows, feature, *, edges=None, labels=None,
           min_n: int = 25, se_bar: float = 3.0, control=None) -> dict:
    """The standard table: buckets, top-minus-bottom, and the four splits.

    Returns a verdict rather than leaving the reader to eyeball it. The bar is
    deliberately high — 3 SE plus a consistent sign on every split — because a
    batch of a dozen features at 2 SE will hand you one false positive by
    construction.
    """
    bs = [(lab, v) for lab, v in buckets(rows, feature, edges, labels)
          if len(v) >= min_n]
    print(f"\n{name}")
    if len(bs) < 2:
        print("  too few rows to bucket")
        return {"verdict": "insufficient"}
    stats = [(lab, *mean_se(v), len(v)) for lab, v in bs]
    print("  " + "  ".join(f"{lab}: {m:+.3f} (n={n})" for lab, m, _, n in stats))
    (_, m0, s0, _), (_, m1, s1, _) = stats[0], stats[-1]
    d, se = m1 - m0, (s0 ** 2 + s1 ** 2) ** 0.5
    mids = [m for _, m, _, _ in stats]
    mono = (all(a <= b for a, b in zip(mids, mids[1:]))
            or all(a >= b for a, b in zip(mids, mids[1:])))
    print(f"  top-bottom {d:+.3f} ± {se:.3f}"
          + (f"  {d / se:+.1f} SE" if se else "")
          + ("  monotone" if mono else "  NOT monotone"))

    signs, split_lines = [], []
    for lab, pred in SPLITS[1:]:
        sub = [x for x in rows if pred(x)]
        sb = [(l_, v) for l_, v in buckets(sub, feature, edges, labels)
              if len(v) >= min_n // 2]
        if len(sb) < 2:
            split_lines.append(f"  {lab:<18} too few")
            continue
        a, b = mean_se(sb[0][1])[0], mean_se(sb[-1][1])[0]
        signs.append(b - a)
        split_lines.append(f"  {lab:<18} {b - a:+.3f}")
    for l_ in split_lines:
        print(l_)
    same = bool(signs) and (all(s > 0 for s in signs) or all(s < 0 for s in signs))

    ok = se and abs(d / se) >= se_bar and mono and same
    if ok and control is not None:
        print(f"  control ({control.__name__}):")
        held = []
        for lab, sub in control(rows):
            sb = [(l_, v) for l_, v in buckets(sub, feature, edges, labels)
                  if len(v) >= min_n // 2]
            if len(sb) < 2:
                print(f"    {lab:<16} too few")
                continue
            a, b = mean_se(sb[0][1])[0], mean_se(sb[-1][1])[0]
            held.append(b - a)
            print(f"    {lab:<16} {b - a:+.3f}")
        if held and not (all(h > 0 for h in held) or all(h < 0 for h in held)):
            ok = False
            print("    -> sign flips inside the control; REJECTED")
    verdict = "CANDIDATE" if ok else "rejected"
    print(f"  => {verdict}"
          + ("" if ok else "  (needs monotone, >=%.0f SE, and one sign on "
                           "every split)" % se_bar))
    return {"verdict": verdict, "diff": d, "se": se, "monotone": mono,
            "same_sign": same, "n": sum(len(v) for _, v in bs)}


def risk_terciles(rows):
    """Standard control: wide stops score worse, so anything that correlates
    with stop size will look like an edge until it is held constant."""
    qs = sorted(x.risk_pct for x in rows)
    if len(qs) < 6:
        return []
    a, b = qs[len(qs) // 3], qs[2 * len(qs) // 3]
    return [("tight stops", [x for x in rows if x.risk_pct < a]),
            ("mid stops", [x for x in rows if a <= x.risk_pct < b]),
            ("wide stops", [x for x in rows if x.risk_pct >= b])]
