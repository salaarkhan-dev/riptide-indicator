"""Everything that has to pass before a deploy. One command, one exit code.

    python3 deploy/preflight.py              # all of it
    python3 deploy/preflight.py --quick      # skip anything that touches MEXC
    python3 deploy/preflight.py ccp          # one indicator's checks only
    python3 deploy/preflight.py --list       # what would run, and nothing else

WHY THIS EXISTS. The checks were all already here and nobody could run them in
one go: fifteen test files invoked by hand, six Pine checkers each with its own
arguments buried in its own docstring, and a syntax pass nobody had written.
The failure mode that produced this file was a large file move — every test
still passed because every test imported the modules it needed, and three
scripts that nothing imports pointed at paths that no longer existed. Nothing
said so until one of them was run weeks later.

FOUR STAGES, CHEAPEST FIRST, and it stops at the first stage that fails so the
output is the failure rather than a wall:

    1. SYNTAX    every .py compiles
    2. IMPORTS   every first-party import RESOLVES, without executing anything
    3. TESTS     tests/ and indicators/*/tests/
    4. PINE      the static and parity checks over the .pine sources

Stage 2 is the one that is new and it is the one that catches a move. It walks
the AST rather than importing, because importing a study runs it — several of
them fetch a thousand days of candles from the exchange on import, which is not
a thing a preflight may do.

DISCOVERY, NOT A LIST. Tests are found by glob, so a new test file in
`tests/` or in `indicators/<name>/tests/` is picked up with no edit here. The
Pine checks cannot be discovered — each takes its own arguments — so they are
declared in PINE_CHECKS below, which is the one place in this repository where
a Pine checker's correct invocation is written down.

NOTHING HERE TOUCHES THE NETWORK, ORDERS OR SECRETS. A study is not a check:
studies are measurements and they cost an hour and a data feed, so preflight
never runs one. `--quick` exists for the same reason at a smaller scale.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import os
import pathlib
import subprocess
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Packages whose imports must resolve. Anything else is a third-party import
# and is the environment's problem, not this repository's.
FIRST_PARTY = ("riptide", "research", "indicators", "deploy", "tests")

SKIP_DIRS = ("__pycache__", ".git", ".cache", "node_modules")

# The Pine checks, with the arguments each one needs. THIS IS THE MANIFEST —
# when a .pine file moves, this is what has to move with it, and stage 4 is
# what says so out loud instead of leaving a stale path in a docstring.
PINE = "indicators/{}/pine/{}"
PINE_CHECKS = [
    # (label, indicator or None for repo-wide, argv after the script)
    ("pine-static-check", None, [
        PINE.format("ccp", "riptide-ccp.pine"),
        PINE.format("riptide", "riptide-indicator.pine"),
        PINE.format("riptide_ms", "riptide-indicator-v2.pine"),
        PINE.format("exhaustion", "riptide-reversal.pine"),
        PINE.format("undertow", "riptide-undertow.pine")]),
    # The production indicator against the bot's own config. The one check
    # here that guards a live trading path rather than a research bench.
    ("check-parity", "riptide", []),
    # --check, never the writing mode. See stage_pine: a check that edits
    # the tree is not a check, and preflight fails one that does.
    ("pine-input-active", "riptide_ms", ["--check"]),
    ("ms-py-parity", "riptide_ms", [
        PINE.format("riptide_ms", "riptide-indicator-v2.pine"),
        "indicators/riptide_ms/port/ms_struct.py"]),
    ("ccp-grab-check", "ccp", []),
    ("undertow-ms-check", "undertow", []),
    ("undertow-port-check", "undertow", []),
]


def py_files():
    for p in sorted(ROOT.rglob("*.py")):
        if any(d in p.parts for d in SKIP_DIRS):
            continue
        yield p


def rel(p) -> str:
    return str(pathlib.Path(p).relative_to(ROOT))


def owner(p) -> str:
    """Which indicator a path belongs to, or "" for shared code."""
    parts = pathlib.Path(p).relative_to(ROOT).parts
    return parts[1] if len(parts) > 2 and parts[0] == "indicators" else ""


# ----------------------------------------------------------------- stages


def stage_syntax(only):
    """Parse, do not byte-compile. compile() to a throwaway .pyc would also
    work, but parsing is what this is actually asking and it leaves nothing
    behind in the tree."""
    bad, n = [], 0
    for p in py_files():
        if only and owner(p) not in ("", only):
            continue
        n += 1
        try:
            ast.parse(p.read_text(), str(p))
        except SyntaxError as e:
            bad.append((f"{rel(p)}:{e.lineno}", e.msg))
        except UnicodeDecodeError as e:
            bad.append((rel(p), f"not readable as text: {e}"))
    return n, bad


def stage_imports(only):
    """Every first-party import resolves — WITHOUT importing anything.

    Importing a study runs it, and several of them fetch a thousand days of
    candles at module scope. So this reads the AST and asks the import system
    whether each module could be found, which is the question a file move
    actually breaks.
    """
    sys.path.insert(0, str(ROOT))
    seen, bad, n = {}, [], 0
    for p in py_files():
        if only and owner(p) not in ("", only):
            continue
        try:
            tree = ast.parse(p.read_text(), str(p))
        except SyntaxError:
            continue                       # stage 1 already reported it
        for node in ast.walk(tree):
            mods = []
            if isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 \
                    and node.module:
                mods = [node.module]
            for m in mods:
                if m.split(".")[0] not in FIRST_PARTY:
                    continue
                n += 1
                if m not in seen:
                    try:
                        seen[m] = importlib.util.find_spec(m) is not None
                    except Exception:
                        seen[m] = False
                if not seen[m]:
                    bad.append((f"{rel(p)}:{node.lineno}",
                                f"cannot resolve {m}"))
    return n, bad


def _run(argv, timeout=900):
    r = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True,
                       timeout=timeout, env={**os.environ, "PYTHONPATH": ".",
                                             "RIPTIDE_DB": _scratch_db()})
    return r.returncode, (r.stdout + r.stderr)


def _scratch_db() -> str:
    """A throwaway database per test process. A test that wrote into the live
    riptide.db would be a preflight that damages what it is clearing."""
    return tempfile.mktemp(suffix=".db", prefix="preflight-")


def test_files(only):
    out = list(sorted((ROOT / "tests").glob("test_*.py")))
    for d in sorted((ROOT / "indicators").glob("*/tests")):
        out += sorted(d.glob("test_*.py"))
    if only:
        # An indicator's own tests, plus the shared ones — a change under
        # indicators/<name>/ can still break the bot, and the shared suite is
        # seconds.
        out = [p for p in out if owner(p) in ("", only)]
    return out


def stage_tests(only):
    files = test_files(only)
    bad = []
    for p in files:
        rc, out = _run([sys.executable, rel(p)])
        if rc != 0:
            tail = "\n".join(l for l in out.splitlines()
                             if "FAIL" in l or "Error" in l)[:600]
            bad.append((rel(p), tail or out.splitlines()[-1] if out else "?"))
    return len(files), bad


def _pine_state() -> dict:
    return {rel(p): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(ROOT.glob("indicators/*/pine/*.pine"))}


def stage_pine(only):
    """The Pine checks, and a guard that none of them WROTE anything.

    One of these scripts is a writer with a --check mode, and running the
    writing mode by mistake appended a duplicate `active =` argument to every
    gated input on every run — six runs, six duplicates, a file Pine would
    refuse, and no test anywhere noticed because no test reads the .pine.

    So the .pine sources are hashed either side. A check that modifies the tree
    is not a check, whatever it exits with, and this fails it by name.
    """
    before = _pine_state()
    bad, n = [], 0
    for label, ind, args in PINE_CHECKS:
        if only and ind not in (None, only):
            continue
        n += 1
        rc, out = _run([sys.executable, f"deploy/{label}.py", *args])
        after = _pine_state()
        touched = [f for f, h in after.items() if before.get(f) != h]
        if touched:
            bad.append((label, "MODIFIED " + ", ".join(touched)
                        + " — a check must not write to the tree"))
            before = after
        elif rc != 0:
            bad.append((label, (out.strip().splitlines() or ["?"])[-1][:200]))
    return n, bad


STAGES = [("SYNTAX", "files compile", stage_syntax),
          ("IMPORTS", "first-party imports resolve", stage_imports),
          ("TESTS", "test files pass", stage_tests),
          ("PINE", "pine checks pass", stage_pine)]


def main() -> int:
    argv = sys.argv[1:]
    quick = "--quick" in argv
    listing = "--list" in argv
    only = next((a for a in argv if not a.startswith("-")), "")
    if only and not (ROOT / "indicators" / only).is_dir():
        have = sorted(p.name for p in (ROOT / "indicators").iterdir()
                      if p.is_dir() and not p.name.startswith("__"))
        print(f"no indicator {only!r}; have: {', '.join(have)}")
        return 2

    if listing:
        print(f"tests ({len(test_files(only))}):")
        for p in test_files(only):
            print("   ", rel(p))
        print("pine checks:")
        for label, ind, args in PINE_CHECKS:
            if not only or ind in (None, only):
                print("   ", label, *args)
        return 0

    stages = STAGES[:2] if quick else STAGES
    head = f"PREFLIGHT{f' · {only}' if only else ''}" \
           f"{' · quick' if quick else ''}"
    print(f"{head}\n" + "─" * len(head))
    failed = False
    for name, what, fn in stages:
        t0 = time.time()
        n, bad = fn(only)
        dt = time.time() - t0
        mark = "FAIL" if bad else "ok  "
        print(f"  {mark}  {name:<8} {n:>4} {what}   {dt:.1f}s")
        for where, why in bad:
            print(f"          {where}\n             {why}")
        if bad:
            # Stop here. A failing syntax stage makes every later stage report
            # the same thing in a longer way, and the first failure is the one
            # worth reading.
            failed = True
            break
    print("─" * len(head))
    print("READY TO DEPLOY" if not failed else "NOT READY — fix the above")
    if quick and not failed:
        print("(--quick skipped TESTS and PINE; run without it before a "
              "deploy)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
