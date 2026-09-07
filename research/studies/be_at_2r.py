"""Break-even arming, at the 2R target.

It was measured against a 1.5R target, where arming at 1.5R or 2R could never
trigger — a no-op. At 2R the 1.5R arm CAN trigger, so the shipped advice
becomes live for the first time and has to be re-asked.
"""
import research.env                                     # noqa: F401  MUST be first
import asyncio                                          # noqa: E402
from research.data import load                          # noqa: E402
from research.harness import mean_se                    # noqa: E402


async def main():
    print(f"  {'policy':<30}{'n':>6}{'R/sig':>9}{'SE':>7}{'total':>9}{'vs none':>9}")
    for kind in ("confirmed", "early"):
        print(f"\n  -- {kind}, target 2R --")
        base = None
        for arm, lock in ((0.0, 0.0), (1.0, 0.1), (1.5, 0.1), (1.75, 0.1)):
            rows = await load(target_r=2.0, be_arm_r=arm, be_lock_r=lock)
            v = [r.r for r in rows if r.kind == kind]
            if base is None:
                base = v
            m, se = mean_se(v)
            lab = "no break-even" if not arm else f"arm {arm:g}R lock {lock:g}R"
            out = f"  {lab:<30}{len(v):>6}{m:>+9.3f}{se:>7.3f}{sum(v):>+9.1f}"
            if arm:
                d, sd = mean_se([a - b for a, b in zip(v, base)])
                out += f"{d:>+9.3f}" + (f"  {d/sd:+.1f}SE" if sd else "")
            print(out)

asyncio.run(main())
