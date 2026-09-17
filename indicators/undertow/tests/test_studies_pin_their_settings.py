"""A published study must still reproduce its published page.

    PYTHONPATH=. python3 indicators/undertow/tests/test_studies_pin_their_settings.py

THIS EXISTS BECAUSE IT HAPPENED, TWICE, IN ONE AFTERNOON.

`swingSrc` moved from the bar pivot to "price move", and `slopeUnit` from
"bars" to "hours". Neither commit touched a study script, and both silently
re-pointed arms that had been leaning on P's defaults:

  * undertow_bias's S0 and S1 became the range arm, making them duplicates of
    S6 -- the page reports 2.2 flips a day for S0/S1 and 0.7 for S6
  * undertow_bias's S4 became the hours variant of Slope
  * undertow_ablation, _exits, _backup and _late_backup all inherited a swing
    definition their measurements were never run under

Nothing failed. Every script still ran, still printed a table, and every number
in it would have been wrong under the name of a page that says otherwise. That
is the worst failure mode a measurement repository has, because the output
looks exactly like the output.

THE RULE: a study that constructs a baseline `U.P(...)` names the settings
below explicitly, even when they match the current default. A study that is
SUPPOSED to track whatever ships says so with the marker comment and is exempt
-- undertow_rate.py is the real case, because its tables describe the live
watcher.

The check is on the SOURCE TEXT, not on an import, because importing a study
runs it and several of them fetch candles.
"""
import os
import pathlib
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))))

STUDIES = pathlib.Path(__file__).resolve().parents[1] / "studies"

# The fields whose defaults have actually moved under a published study. Add to
# this list when you move another one -- that is cheaper than the alternative,
# which is finding out from a table that silently disagrees with its page.
PINNED = ("swingSrc", "msLen", "msShortLen", "rr", "endSweep", "endStale")
# A study whose whole job is to describe what currently ships puts this on the
# line that reads the default. It is a deliberate, visible opt-out.
EXEMPT = "TRACKS THE CURRENT DEFAULT"
# sha256 of P's field defaults, first 16 hex. See the third test for what to do
# when this fails -- the answer is not to paste the new value.
DEFAULTS_FINGERPRINT = "0c4fc370d72b4df7"
DEFAULTS_COUNT = 51

good = []


def ok(cond, msg):
    good.append(bool(cond))
    print(("  ok   " if cond else "  FAIL ") + msg)


def test_every_study_pins_or_opts_out():
    files = sorted(p for p in STUDIES.glob("*.py")
                   if not p.name.startswith("_"))
    ok(len(files) >= 6, f"found the studies: {len(files)}")
    for p in files:
        src = p.read_text()
        if EXEMPT in src:
            print(f"       {p.name}: exempt — {EXEMPT}")
            good.append(True)
            continue
        # The baseline is whatever this file passes to P(...) -- under any
        # alias, because the first version of this check looked for `U.P(`
        # only and waved undertow_rate.py through for the wrong reason: it
        # reads `_P().swingSrc` and is exactly the case the exemption is for.
        if not re.search(r"\b_?P\(\)?", src):
            print(f"       {p.name}: reads no P at all")
            good.append(True)
            continue
        missing = [f for f in PINNED if not re.search(rf"\b{f}\s*=", src)]
        ok(not missing,
           f"{p.name} pins its settings"
           + ("" if not missing else f" — MISSING {', '.join(missing)}"))


def test_the_marker_is_not_a_blank_cheque():
    """An exempt study still has to say WHY on the line that reads the default,
    not once at the top of the file as a way of skipping the check."""
    for p in sorted(STUDIES.glob("*.py")):
        src = p.read_text()
        if EXEMPT not in src:
            continue
        lines = [ln for ln in src.splitlines() if EXEMPT in ln]
        ok(all(ln.lstrip().startswith("#") for ln in lines),
           f"{p.name}: the exemption is a comment, not a string in output")
        near = src.split(EXEMPT, 1)[1][:400]
        ok("_P()" in near or "U.P(" in near or "swingSrc" in near,
           f"{p.name}: the exemption sits next to the default it reads")


def test_the_defaults_have_not_moved_unnoticed():
    """THE GUARD THAT DOES NOT NEED A LIST, and the reason it exists is that
    the list above was WRONG on its first outing.

    PINNED named swingSrc, msLen, msShortLen and rr. It missed `endSweep` and
    `endStale`, which had also flipped, so undertow_exits still failed to
    reproduce -- it chose a different exit arm on two of three timeframes --
    and only a full re-run found it. Enumerating consequences does not work,
    because the enumerator is the thing that is out of date.

    So this fails on ANY default moving, which is the CAUSE. It is meant to be
    updated deliberately: change a default, re-run the studies, confirm they
    still reproduce their pages or pin what they need, then paste the new
    fingerprint. The failure message is the procedure.
    """
    import dataclasses
    import hashlib
    import json

    from indicators.undertow.port import undertow as U

    fields = {f.name: f.default for f in dataclasses.fields(U.P)}
    got = hashlib.sha256(
        json.dumps(fields, sort_keys=True, default=str).encode()).hexdigest()
    ok(got.startswith(DEFAULTS_FINGERPRINT),
       "P's defaults are the ones the studies were audited against"
       if got.startswith(DEFAULTS_FINGERPRINT) else
       f"P's DEFAULTS MOVED — fingerprint {got[:16]}, expected "
       f"{DEFAULTS_FINGERPRINT}.\n"
       "         Every study that does not pin the field you changed is now\n"
       "         measuring something its page does not describe. Re-run them,\n"
       "         confirm each reproduces its measurement, pin what it needs,\n"
       "         then paste the new fingerprint here. Do not just paste it.")
    ok(len(fields) == DEFAULTS_COUNT,
       f"P has {len(fields)} fields (audited against {DEFAULTS_COUNT})")


def main():
    for fn in (test_every_study_pins_or_opts_out,
               test_the_marker_is_not_a_blank_cheque,
               test_the_defaults_have_not_moved_unnoticed):
        print(f"\n{fn.__name__}")
        fn()
    print(f"\n{'ALL PASS' if all(good) else 'FAILURES'}  "
          f"{sum(good)}/{len(good)}")
    return 0 if all(good) else 1


if __name__ == "__main__":
    sys.exit(main())
