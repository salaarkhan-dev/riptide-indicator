"""ONE COOLDOWN FOR BOTH DIRECTIONS, OR ONE EACH?

THE QUESTION, AND WHY IT IS NOT OBVIOUS EITHER WAY.

The shipped rule (riptide/decide.py) holds a SEPARATE 120-minute window for
longs and for shorts. That was never measured; it was inherited. Every grouping
in this project keys on direction — by_event, by_bar, by_arrival all do — on the
reasoning that an up-raid and a down-raid are two different market moves. The
cooldown copied the key without asking whether the same reasoning applies to a
COOLDOWN, which is a different kind of object: the groupings answer "is this the
same event", and a cooldown answers "how much should I be holding at once".

The argument FOR separate windows: a long and a short are not correlated the way
two longs are. Taking one of each is a hedge, or at worst two independent bets,
so forcing them to share a window throws away half the opportunities for no risk
reduction.

The argument FOR one global window: correlation across a crypto universe is not
symmetric around zero. When BTC moves, everything moves, and the losing side of
that move is a pool of stops, not a hedge. The deployed stream's worst run is
forty trades inside twelve hours — one move taking out everything open. If the
long and short windows fire at the same minute, the reader holds two positions
in one move and the pick rule's entire purpose (size once per move) has been
half-defeated.

And there is a practical argument the measurement cannot see: two 🎯 in one
minute, pointing opposite ways, is the message most likely to make a reader
stop trusting the rule.

PRE-REGISTERED, BEFORE THE FIRST NUMBER

  PRIMARY. Recovery factor (total R / max drawdown) of the picked stream.
  Recovery rather than total R for the reason every study here gives: any rule
  that simply trades less shrinks both and is worth nothing.

  SECONDARY. Compounded account at 1% risk with at most ten open, alerts a day,
  win rate, and both halves of the window reported separately — an advantage
  sitting in one half is a non-result.

  TERTIARY, and specific to this question: how often the two windows actually
  fire close together. If longs and shorts rarely collide, the two rules are
  nearly the same rule and the choice is cosmetic. This is measured directly
  (COLLISIONS below) rather than inferred from the score gap.

  EXPECTATION. The global window takes roughly HALF the trades, so if the two
  score within noise of each other the global one is the better rule at equal
  recovery — fewer decisions for the same ratio. I expect per-direction to have
  the higher TOTAL R and global to have the higher RECOVERY, because the
  drawdown is where correlated opposite-side entries show up. I do NOT expect a
  large gap: at 120 minutes the collision rate should be modest.

  WHAT WOULD CHANGE MY MIND. If global wins on recovery in only one half of the
  window, or if the collision rate is under ~10%, the difference is not real and
  the shipped rule stays on the grounds that it is already deployed.

  A HONEST LIMIT STATED UP FRONT. Both arms are scored at 2R with the same
  harness, entries and exits are per-trade, and NOTHING here models the margin a
  real account would need to hold a long and a short at once. compound() caps
  open positions at ten and that is the only portfolio constraint in the number.
  So if global wins here it wins on signal quality alone, and the real-account
  case for it is stronger than the number says, not weaker.

    PYTHONPATH=. python3 research/studies/cooldown_dir.py
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
from collections import defaultdict                     # noqa: E402

import aiohttp                                          # noqa: E402

from riptide.config import BAR_SECONDS                  # noqa: E402
from research.deep import load_universe                 # noqa: E402
from research.studies.poi_tf import DAY, DAYS, H8       # noqa: E402
from research.studies.poi_tf import collect, context, universe  # noqa: E402
from research.studies.report import START, compound, drawdown  # noqa: E402
from research.studies.pick_rule import (NSYM, TFS, arrival,  # noqa: E402
                                        band_of, by_event, key_band,
                                        key_tf_first)

COOLDOWNS = (30, 60, 120, 240)


def pick_rolling(rows, key, cooldown, per_direction=True):
    """The rolling cooldown, with the direction key switchable.

    `per_direction=True` is the shipped rule: longs and shorts hold separate
    windows. `False` is one window across both.

    Strictly causal, processed in ARRIVAL order — the scan cycle that first
    sees a signal, not the bar it closed on. A scan arriving inside the
    cooldown contributes nothing, so a pick acted on at 11:30 is never
    contradicted at 12:00.

    The two arms differ in ONE place, the grouping key, and share everything
    else — the same ranking, the same arrival clock, the same ordering. That
    is deliberate: a difference in the score has exactly one thing it can be.
    """
    byscan = defaultdict(list)
    for t in rows:
        seen = arrival(t.t + BAR_SECONDS[t.tf])
        byscan[(seen, t.is_long if per_direction else 0)].append(t)
    last, out = {}, []
    for seen, up in sorted(byscan):
        if seen - last.get(up, -(1 << 40)) < cooldown:
            continue
        out.append(min(byscan[(seen, up)], key=key))
        last[up] = seen
    return out


def collisions(rows, key, cooldown):
    """How often the per-direction rule names a long and a short close together.

    This is the whole question in one number. If the two windows rarely
    overlap, the global rule is the same rule with extra words; if they overlap
    constantly, the global rule is a materially different amount of risk.

    Returns (picks, pairs within 15m, pairs within the cooldown).
    """
    picks = sorted(pick_rolling(rows, key, cooldown, True),
                   key=lambda t: arrival(t.t + BAR_SECONDS[t.tf]))
    near_scan = near_window = 0
    for i, a in enumerate(picks):
        ta = arrival(a.t + BAR_SECONDS[a.tf])
        for b in picks[i + 1:]:
            tb = arrival(b.t + BAR_SECONDS[b.tf])
            if tb - ta >= cooldown:
                break
            if b.is_long == a.is_long:
                continue          # cannot happen inside one window, but cheap
            near_window += 1
            if tb - ta <= 900:
                near_scan += 1
            break                 # only the NEXT opposite pick counts as a pair
    return len(picks), near_scan, near_window


HEAD = (f"  {'rule':<34}{'/day':>7}{'n':>7}{'R':>9}{'maxDD':>8}"
        f"{'recov':>8}{'1st':>7}{'2nd':>7}{'win':>7}{'acct':>9}{'accDD':>6}")


def score(name, rows):
    if len(rows) < 40:
        print(f"  {name:<34}{len(rows):>6}   too thin")
        return None
    rs = [t.r for t in sorted(rows, key=lambda x: x.exit_t)]
    dd, _ = drawdown(rs)
    wins = sum(1 for r in rs if r > 0)
    bal, ddc, _ = compound(rows, max_open=10)
    order = sorted(rows, key=lambda x: x.exit_t)
    halves = []
    for part in (order[:len(order) // 2], order[len(order) // 2:]):
        h = [t.r for t in part]
        d, _ = drawdown(h)
        halves.append(sum(h) / d if d else 0.0)
    rec = sum(rs) / dd if dd else 0
    print(f"  {name:<34}{len(rows) / DAYS / NSYM * 120:>7.1f}"
          f"{len(rows):>7}{sum(rs):>9.1f}{dd:>8.1f}{rec:>8.2f}"
          f"{halves[0]:>7.2f}{halves[1]:>7.2f}{wins / len(rs):>7.0%}"
          f"{100 * (bal / START - 1):>+9.0f}%{ddc:>6.0%}")
    return rec, halves, sum(rs), len(rows)


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

    # The DEPLOYED stream, exactly as pick_rule.py defines it: POI_REQUIRED=1
    # and MIN_GRADE=B means what actually sends is in a daily zone with the
    # trend agreeing. Scoring a rule on signals the bot does not send would
    # answer a different question.
    rows = [t for tf in TFS for t in by_tf[tf] if t.day]
    ev = by_event(rows)
    longs = sum(1 for t in rows if t.is_long)

    print("ONE COOLDOWN, OR ONE PER DIRECTION")
    print(f"{len(syms)} symbols, {DAYS} days, 15m+30m+1h, the stream the bot")
    print("actually sends: in a daily POI, 8h trend agreeing, grade A or B.")
    print(f"\n  {len(rows)} filled trades in {len(ev)} market events "
          f"· {longs} long / {len(rows) - longs} short")

    print("\n" + HEAD)
    for key_name, key in (("tf-first", key_tf_first), ("band-first", key_band)):
        print(f"  -- {key_name.upper()} " + "-" * (72 - len(key_name)))
        for mins in COOLDOWNS:
            a = score(f"{mins}m  per direction (shipped)",
                      pick_rolling(rows, key, mins * 60, True))
            b = score(f"{mins}m  ONE global window",
                      pick_rolling(rows, key, mins * 60, False))
            if a and b:
                print(f"  {'':34}{'':7}{'':7}{'':9}{'':8}"
                      f"{b[0] - a[0]:>+8.2f}{b[1][0] - a[1][0]:>+7.2f}"
                      f"{b[1][1] - a[1][1]:>+7.2f}   <- global minus shipped")
        print()

    # HOW OFTEN THE TWO WINDOWS ACTUALLY COLLIDE. The score gap alone cannot
    # say whether the rules differ in kind or only in volume, and this can.
    print("  -- HOW OFTEN A LONG AND A SHORT PICK LAND TOGETHER " + "-" * 22)
    print(f"  {'cooldown':<12}{'picks':>8}{'opposite pair':>16}"
          f"{'same scan':>12}{'rate':>8}")
    for mins in COOLDOWNS:
        n, same_scan, in_window = collisions(rows, key_tf_first, mins * 60)
        print(f"  {str(mins) + 'm':<12}{n:>8}{in_window:>16}"
              f"{same_scan:>12}{in_window / n if n else 0:>8.0%}")
    print("\n  'opposite pair' counts picks followed by an opposite-direction")
    print("  pick inside the same cooldown — exactly the case the global")
    print("  window would have suppressed. 'same scan' is the subset arriving")
    print("  in the SAME 15-minute cycle: two 🎯 in one minute, opposite ways.")

    # The composition of what each rule takes, since a rule that quietly
    # becomes long-only or confirmed-only has changed more than its count.
    print("\n  -- WHAT EACH RULE ENDS UP TAKING, at 120m tf-first " + "-" * 22)
    print(f"  {'rule':<28}{'long':>8}{'early':>8}{'normal':>8}"
          f"{'tight':>8}{'wide':>8}")
    for label, per_dir in (("per direction (shipped)", True),
                           ("ONE global window", False)):
        p = pick_rolling(rows, key_tf_first, 7200, per_dir)
        n = len(p)
        bands = [sum(1 for t in p if band_of(t) == b) for b in (0, 1, 2)]
        print(f"  {label:<28}"
              f"{sum(1 for t in p if t.is_long) / n:>8.0%}"
              f"{sum(1 for t in p if t.kind == 'early') / n:>8.0%}"
              f"{bands[0] / n:>8.0%}{bands[1] / n:>8.0%}{bands[2] / n:>8.0%}")


if __name__ == "__main__":
    asyncio.run(main())
