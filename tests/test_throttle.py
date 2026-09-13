"""A rate-limited scan must not look like a quiet market.

WHY THIS FILE EXISTS. On 12 Sep a live scan logged this, dozens of times a
cycle, for hours:

    WARNING SAGA_USDT Min15: no candles returned —
      {'success': False, 'code': 510, 'message': 'Requests are too frequent'}
    INFO   Min15  115 symbols · 0-599 bars · median 599 · 24 TOO SHORT TO SCAN
    INFO   scanned 115 symbols, sent 0 confirmed, 0 early

Roughly a quarter of the universe was never scanned, and the summary line said
"scanned 115 symbols". The bot was healthy, the logs were full, and the answer
was wrong.

THE BUG WAS A CATEGORY ERROR, NOT A THRESHOLD. get_json retried on HTTP 429 —
but MEXC does not send 429. It sends HTTP **200** with the refusal in the JSON
body, so raise_for_status() passed, the retry branch never ran, and a throttle
was handed downstream as "this symbol had no candles". Every layer below then
did the right thing with the wrong input.

So the two things pinned here are: a 200-with-510 is recognised as a refusal
rather than as data, and the pacer widens itself when it happens. Neither is
observable from a passing scan, which is exactly why they need a test.

    PYTHONPATH=. python3 tests/test_throttle.py     # exit 1 on any failure
"""
import asyncio
import sys

sys.path.insert(0, ".")

import riptide.exchange as ex                      # noqa: E402

fails = []


def check(ok, what):
    print(f"  {'PASS' if ok else 'FAIL'}  {what}")
    if not ok:
        fails.append(what)


THROTTLE = {"success": False, "code": 510,
            "message": "Requests are too frequent, please try again later"}
GOOD = {"success": True, "data": {"time": [1, 2], "open": [1.0, 1.0],
                                  "high": [1.0, 1.0], "low": [1.0, 1.0],
                                  "close": [1.0, 1.0], "vol": [1.0, 1.0]}}

print("THE REFUSAL IS RECOGNISED AS A REFUSAL")
check(ex._throttled_body(THROTTLE),
      "the exact body MEXC returned on 12 Sep is detected as throttling")
for code in sorted(ex.THROTTLE_CODES):
    check(ex._throttled_body({"success": False, "code": code}),
          f"code {code} is treated as a rate limit")
check(not ex._throttled_body(GOOD), "a normal response is not")
check(not ex._throttled_body({"success": False, "code": 1002}),
      "an unrelated failure code is NOT swallowed as throttling — it must "
      "keep reaching the caller as an error")
check(not ex._throttled_body(None) and not ex._throttled_body([]),
      "a missing or non-dict body does not raise")


class FakeResp:
    def __init__(self, payload, status=200):
        self._p, self.status = payload, status

    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False
    async def json(self): return self._p
    def raise_for_status(self): pass


class FakeSess:
    """Answers with a scripted queue, and counts what was asked."""

    def __init__(self, script):
        self.script, self.calls = list(script), 0

    def get(self, url, params=None, timeout=None):
        self.calls += 1
        p = self.script.pop(0) if self.script else GOOD
        return FakeResp(p)


def run(script, tries=3):
    ex._gap_mult = 1.0                      # a known starting point
    sess = FakeSess(script)
    # No real sleeping: the retry backoff is seconds and this is a unit test.
    real_sleep = asyncio.sleep

    async def no_sleep(_s): return await real_sleep(0)
    ex.asyncio.sleep = no_sleep
    try:
        out = asyncio.run(ex.get_json(sess, "http://x/kline/AAA_USDT",
                                      tries=tries))
    finally:
        ex.asyncio.sleep = real_sleep
    return out, sess.calls


print("\nA THROTTLED REQUEST IS RETRIED, NOT ACCEPTED AS DATA")
out, calls = run([THROTTLE, THROTTLE, GOOD])
check(out == GOOD, "two refusals then success returns the real candles")
check(calls == 3, f"and it actually retried rather than giving up: {calls} GETs")

out, calls = run([THROTTLE, THROTTLE, THROTTLE])
check(out is None,
      "a refusal that survives every retry returns None, not the refusal body")
check(calls == 3, f"having used all its tries: {calls} GETs")

out, calls = run([GOOD])
check(out == GOOD and calls == 1, "a clean response is returned on the first GET")

# THE REGRESSION ITSELF. Before the fix this returned the refusal dict, whose
# .get("data") is None — so fetch_candles logged "no candles returned" and the
# scan carried on as though the symbol were quiet.
out, _ = run([THROTTLE, THROTTLE, THROTTLE])
check(not (isinstance(out, dict) and out.get("code") == 510),
      "the refusal body NEVER reaches the caller, which is the 12 Sep bug")

print("\nTHE PACER WIDENS WHEN REFUSED AND NARROWS WHEN CLEAR")
ex._gap_mult = 1.0
ex.note_throttled()
first = ex.gap_mult()
check(first > 1.0, f"one refusal widens the gap: x{first:.2f}")
for _ in range(40):
    ex.note_throttled()
check(ex.gap_mult() <= ex.GAP_MULT_MAX,
      f"and it is capped rather than unbounded: x{ex.gap_mult():.1f} "
      f"<= x{ex.GAP_MULT_MAX:g}")
# THE CEILING MUST TRACK THE SCAN INTERVAL, NOT A REMEMBERED NUMBER. The
# first version of this cap was hardcoded at x12, which was fine at a 0.07s
# floor and became 16.8 minutes per cycle — longer than the scan itself — as
# soon as the floor moved to 0.12. This asserts the relationship instead.
from riptide.config import BAR_SECONDS, SCAN_INTERVAL   # noqa: E402
_budget = BAR_SECONDS[SCAN_INTERVAL] * ex.GAP_BUDGET
_worst = ex.MIN_REQUEST_GAP * ex.GAP_MULT_MAX * ex.EXPECTED_REQUESTS
check(_worst <= _budget + 1,
      f"even fully widened, a full cycle fits its budget: {_worst:.0f}s "
      f"<= {_budget:.0f}s (half of one {SCAN_INTERVAL} scan)")
check(_worst < BAR_SECONDS[SCAN_INTERVAL],
      f"and therefore cannot overrun the scan interval itself "
      f"({BAR_SECONDS[SCAN_INTERVAL]}s)")

# The decay runs inside _pace, once per paced request.
ex._gap_mult = 4.0


async def drain(n):
    for _ in range(n):
        await ex._pace()

real_sleep = asyncio.sleep


async def no_sleep(_s): return await real_sleep(0)

ex.asyncio.sleep = no_sleep
try:
    asyncio.run(drain(300))
finally:
    ex.asyncio.sleep = real_sleep
check(ex.gap_mult() < 4.0,
      f"clean requests narrow it again: x{ex.gap_mult():.2f} after 300")
check(ex.gap_mult() >= 1.0, "but never below the configured gap")

ex._gap_mult = 1.0
asyncio.run(drain(5))
check(ex.gap_mult() == 1.0,
      "and an unthrottled process stays exactly at the configured gap")

print("\n" + ("ALL PASS" if not fails
               else f"{len(fails)} FAILED:\n  " + "\n  ".join(fails)))
sys.exit(1 if fails else 0)
