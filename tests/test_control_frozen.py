"""The production signal path is the CONTROL. This test is what makes that
sentence enforceable instead of aspirational.

THE RULE THIS PROJECT KEEPS WRITING DOWN. "The current production strategy is
the control and does not change during research." Every study says it, every
commit message repeats it, and until now nothing checked it. Twice today an
engine or harness change was verified by hand — `Setup.span` against replayed
signal hashes on three symbols, `stale_bars` against 529 identical outcomes —
and a rule enforced by remembering to check is a rule that survives exactly as
long as somebody remembers.

WHY NOT TWO SEPARATE ENGINES. The obvious alternative is a RIPTIDE_CONTROL
object beside a RIPTIDE_RESEARCH one, so research literally cannot touch
production. It is worse. Two code paths drift: the research copy gains a fix
the production copy never gets, or the reverse, and every measurement after
that describes a strategy nobody is running — silently, because both still
work. That failure has no symptom until a live result disagrees with a
backtest and nobody can say why.

A frozen hash has the opposite property. There is ONE engine, so drift is
impossible by construction, and any change to what it emits is loud and
immediate. Research instrumentation stays welcome: add a field, add a column,
add a study — just not a different SIGNAL.

WHAT IS FROZEN, AND WHY THESE FIVE FIELDS. detected_time, is_long, entry, stop
and src are what a reader acts on and what every backtest scores. Prices are
rounded to 10 significant figures first, because a float that changes in its
last bit under a different libm build is not a strategy change and a test that
fails on it would be turned off within a week.

WHEN THIS TEST FAILS. It has found a real change to the signal. Two cases:

  NOT INTENDED — the usual one. Some refactor moved a comparison, reordered a
  loop, changed a default. Fix the code, not the expectation.

  INTENDED — you deliberately changed the strategy. Then the number below is
  updated IN THE SAME COMMIT as the change, the commit message says what moved
  and why, and every historical result in research/studies/ is understood to
  describe the OLD engine until re-run. Updating the constant to make a red
  test green, without that, is how a project loses the ability to compare
  anything to anything.

ONE TRAP, HIT WHILE WRITING THIS TEST, WORTH KNOWING BEFORE IT WASTES AN HOUR.
Verifying that the test catches a change meant editing `atr_len` from 28 to 27
and back. After restoring, the fingerprint STAYED at the changed value and the
engine looked non-deterministic. It was not: 28 and 27 are the same number of
BYTES, and the restore landed inside the same filesystem second, so the cached
bytecode still looked valid and Python reused the 27 version. Python validates
a .pyc on source mtime and SIZE, and a same-length edit inside one second
defeats both. If this test ever disagrees with what the source plainly says,
`rm -rf riptide/__pycache__` before believing it.

The fixture is 1500 Min30 bars for four symbols chosen to span the universe:
BTC and SOL for liquid majors, ONDO for a mid-cap, PEPE for a sub-cent tick
size where rounding behaves differently. No network, no cache, no clock.

    PYTHONPATH=. python3 tests/test_control_frozen.py   # exit 1 on any failure
"""
import gzip
import hashlib
import json
import os
import sys

sys.path.insert(0, ".")

from riptide.config import CFG                          # noqa: E402
from riptide.engine import Candle, run_engine           # noqa: E402

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures",
                       "engine_baseline.json.gz")

# The frozen signal. Regenerate ONLY alongside a deliberate strategy change,
# never to silence a red test. See the docstring.
EXPECTED = "0c5c03dad27d67a5966d85d8179f0c0a344a81190cd557586a03c077e6181791"

fails = []


def check(ok, what):
    print(f"  {'PASS' if ok else 'FAIL'}  {what}")
    if not ok:
        fails.append(what)


def fingerprint():
    """A stable digest of every signal the engine emits on the fixture."""
    data = json.load(gzip.open(FIXTURE, "rt"))
    rows = []
    for sym in sorted(data):
        cs = [Candle(*r) for r in data[sym]]
        early = []
        setups = run_engine(sym, cs, CFG, early_out=early)
        for kind, batch in (("setup", setups), ("early", early)):
            for x in batch:
                rows.append((sym, kind, x.detected_time, int(x.is_long),
                             f"{x.entry:.10g}", f"{x.stop:.10g}", x.src))
    rows.sort()
    blob = "\n".join("|".join(str(v) for v in r) for r in rows)
    return hashlib.sha256(blob.encode()).hexdigest(), rows


print("the fixture is self-contained")
check(os.path.exists(FIXTURE), "the candle fixture is committed, so this test "
                               "needs no network, no cache and no clock")

print("\nthe engine is deterministic")
a, rows_a = fingerprint()
b, _ = fingerprint()
check(a == b, "two runs over the same bars produce the same signals")
check(len(rows_a) > 50, f"the fixture actually exercises the engine "
                        f"({len(rows_a)} signals across 4 symbols)")

print("\nthe production signal is unchanged")
if EXPECTED == "REGENERATE":
    print(f"  ....  no baseline recorded yet. current fingerprint:\n"
          f"        {a}")
else:
    ok = a == EXPECTED
    check(ok, "the signal fingerprint matches the frozen baseline")
    if not ok:
        print(f"\n  expected {EXPECTED}\n  got      {a}\n")
        print("  THE ENGINE NOW EMITS DIFFERENT SIGNALS. If that was not")
        print("  intended, fix the code rather than this constant. If it WAS")
        print("  intended, update the constant in the same commit as the")
        print("  change, say what moved in the message, and treat every")
        print("  result in research/studies/ as describing the old engine")
        print("  until it is re-run.")

print("\nresearch instrumentation is still allowed")
check(hasattr(rows_a[0], "__len__") and len(rows_a[0]) == 7,
      "only five signal fields are frozen — adding a field to Setup, a column "
      "to outcomes, or a study is untouched by this test")

print("\n" + ("ALL PASS" if not fails
               else f"{len(fails)} FAILED:\n  " + "\n  ".join(fails)))
sys.exit(1 if fails else 0)
