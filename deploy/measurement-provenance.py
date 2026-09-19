"""Which measurement pages still reproduce, and which describe a dead engine?

    PYTHONPATH=. python3 deploy/measurement-provenance.py          # report
    PYTHONPATH=. python3 deploy/measurement-provenance.py --write  # + PROVENANCE.md

NOT A PREFLIGHT CHECK. Every study here reads twelve thousand bars across
forty-odd symbols and three timeframes; the full sweep is most of an hour.
This is the tool you run after moving something shared, which is exactly when
the question matters.

WHAT IT IS FOR, and it took a bad afternoon to work out that these are two
different failures wearing the same face:

  PIN DRIFT       a default moved under a study that read it from P, so the
                  script now measures something its page never described.
                  The page was ALWAYS WRONG -- or rather, the page was right
                  and the script stopped being able to produce it, which is
                  worse, because the script still prints a table.
                  Guarded by indicators/undertow/tests/
                  test_studies_pin_their_settings.py, cheap, and a bug.

  SUPERSESSION    the ENGINE was deliberately corrected -- the anchor rule,
                  the confirm order, the internal pass built without its
                  reference -- so a page produced before the fix cannot
                  reproduce after it. The page was RIGHT WHEN WRITTEN and
                  describes an engine that no longer exists. Not a bug, and
                  pinning cannot and should not prevent it.

The discriminator is mechanical: run the study at the commit that published
its page. UNDERTOW_EXITS.md reproduces 9/9 there and 0/9 at HEAD, across forty
port commits. That is supersession, and no amount of pinning would have
changed it.

THE COMPARISON IS ON TABLE ROWS ONLY. A page's prose quotes other pages --
UNDERTOW_STRICT.md discusses the complement study's +0.258 in a block quote --
and counting those made three sound pages look broken. The study's OUTPUT is
read whole, because a number it prints anywhere is a number it produced.
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
M = ROOT / "indicators/undertow/measurements"
STUDIES = ROOT / "indicators/undertow/studies"

# study stem -> the page it produces. A study with no page (undertow_sweep is
# the 48-config search, undertow_rate describes the live watcher) is absent on
# purpose, and `undertow_pin` is a retired prereg whose universe was released.
PAGES = {
    "anchor": "UNDERTOW_ANCHOR.md", "backup": "UNDERTOW_BACKUP_FILL.md",
    "bias": "UNDERTOW_BIAS_SOURCE.md", "complement": "UNDERTOW_COMPLEMENT.md",
    "default": "UNDERTOW_DEFAULT.md", "exits": "UNDERTOW_EXITS.md",
    "htf": "UNDERTOW_HTF.md", "late_backup": "UNDERTOW_LATE_BACKUP.md",
    "mtf_default": "UNDERTOW_MTF_DEFAULT.md", "mtf": "UNDERTOW_MTF_EMA.md",
    "overlap": "UNDERTOW_OVERLAP.md", "pullback": "UNDERTOW_PULLBACK.md",
    # REGISTERED THE DAY THEY WERE WRITTEN, and the reason is what they are
    # about. UNDERTOW_PINLAG.md was cited seven times before it existed; a page
    # outside this map is a page nothing will notice going stale, which is the
    # same gap one step later.
    "pinlag": "UNDERTOW_PINLAG.md", "pinpick": "UNDERTOW_PINPICK.md",
    "scale": "UNDERTOW_SCALE.md", "slope": "UNDERTOW_SLOPE_DEFAULT.md",
    "strict": "UNDERTOW_STRICT.md", "v2": "UNDERTOW_V2.md",
    "v3": "UNDERTOW_V3.md",
}
# Three decimals is an R value. Two-decimal numbers are z scores and
# percentages; they move for reasons that are not a re-pointing.
NUM = re.compile(r"[-+−]\d\.\d{3}")


def values(text: str, tables_only: bool = False) -> set:
    if tables_only:
        text = "\n".join(ln for ln in text.splitlines()
                         if ln.lstrip().startswith("|"))
    return {n.replace("−", "-").lstrip("+") for n in NUM.findall(text)}


def git(*args: str) -> str:
    return subprocess.run(("git",) + args, cwd=ROOT, capture_output=True,
                          text=True).stdout.strip()


def published_at(page: str) -> str:
    """The commit that last wrote the page -- i.e. the engine it describes."""
    return git("log", "-n1", "--format=%h", "--",
               f"indicators/undertow/measurements/{page}")


def run_study(stem: str, timeout: int = 3000) -> str:
    p = subprocess.run([sys.executable, str(STUDIES / f"undertow_{stem}.py")],
                       cwd=ROOT, capture_output=True, text=True,
                       timeout=timeout, env={"PYTHONPATH": str(ROOT),
                                             "PATH": "/usr/bin:/bin"})
    return p.stdout + p.stderr


def report(only: list | None = None) -> int:
    rows, bad = [], 0
    for stem in sorted(PAGES):
        if only and stem not in only:
            continue
        page = M / PAGES[stem]
        want = values(page.read_text(), tables_only=True)
        try:
            got = values(run_study(stem))
        except subprocess.TimeoutExpired:
            print(f"  {'TIMEOUT':<12} {stem}")
            bad += 1
            continue
        missing = sorted(want - got)
        kept = len(want) - len(missing)
        state = "reproduces" if not missing else "SUPERSEDED"
        bad += bool(missing)
        rows.append((stem, PAGES[stem], published_at(PAGES[stem]),
                     kept, len(want), state))
        print(f"  {state:<12} {stem:<12} {kept:3}/{len(want):<3} "
              f"published at {published_at(PAGES[stem])}"
              + ("" if not missing else f"   missing {' '.join(missing[:8])}"))
    # THE SUMMARY AND THE ROWS DO AGREE, and a 2026-09-19 commit message says
    # they do not. They were read through `| tail -18` against a 19-line
    # report, which drops exactly one line: the first row, `anchor`, which
    # sorts first. The conclusion drawn was that a page had gone through the
    # loop without printing -- a defect in this file. There was none. Recorded
    # so nobody spends an hour looking for it, and because a tool that says
    # "17" while sixteen rows are visible is worth two seconds of `wc -l`
    # before it is worth a bug report.
    print(f"\n{bad} of {len(rows)} pages no longer reproduce at HEAD")
    return rows


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    report(args or None)
