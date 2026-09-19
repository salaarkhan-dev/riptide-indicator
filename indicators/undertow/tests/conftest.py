"""MAKE THESE FILES ABLE TO FAIL UNDER PYTEST.

All three test files here are written the same way: a module-level `good` list,
an `ok(cond, msg)` that APPENDS a result and prints it, and a `main()` that
reads the list at the end and exits 1. Run as `python3 <file>` they are honest.

PYTEST NEVER CALLS main(). It calls the test functions directly, and a function
whose only effect is appending False to a list passes. So under pytest every
check in this directory was advisory, and had been since they were written.

WHAT IT COST, on the day this was found: moving `pinAt` and `pinLag` to their
new defaults left test_undertow_port.py genuinely broken -- the pinLag test
compares `U.P()` against `U.P(pinLag=1)`, which are now the same run -- and
`pytest indicators/undertow/tests` reported `46 passed`. The fingerprint check,
whose whole job is to make a moved default impossible to miss, printed FAIL to
stdout and was recorded as a pass.

AND THE PROJECT'S REAL GATE WAS NEVER FOOLED, which is worth stating plainly
rather than letting the paragraph above imply otherwise. deploy/preflight.py
runs each of these files as `python3 <file>`, so it reads main()'s exit code
and has always been honest; it is what said NOT READY here. The blind spot was
`pytest` run by hand, which is how a person checks one directory mid-change --
the fast loop, not the gate. A guard that only works when you run the slow
thing is a guard you will skip exactly when you are moving fastest.

This is the subject of test_studies_pin_their_settings.py turned on the tests
themselves: a guard whose failure channel is the one nobody reads.

THE FIXTURE ASSERTS AFTER THE TEST rather than making `ok()` raise. Raising
would stop at the first bad check, and the printout of every check is the part
that makes these files diagnosable -- the list is the report.
"""
import pytest


@pytest.fixture(autouse=True)
def _fail_on_recorded_failures(request):
    mod = request.module
    good = getattr(mod, "good", None)
    if good is None:
        yield
        return
    bad = getattr(mod, "bad", None)
    start, bstart = len(good), 0 if bad is None else len(bad)
    yield
    fresh = good[start:]
    n = fresh.count(False)
    if not n:
        return
    detail = ""
    if bad is not None:
        detail = "\n  " + "\n  ".join(bad[bstart:])
    raise AssertionError(
        f"{n} of {len(fresh)} recorded checks failed (see captured "
        f"stdout for the full list){detail}")
