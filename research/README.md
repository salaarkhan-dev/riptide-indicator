# research/

One scorer, one data loader, one reporting format. Studies live in
`studies/` and are re-runnable at any time.

## Why it exists

Before this directory, every measurement was a throwaway script with its own
copy of the scoring loop. On 7 Sep all of them turned out to share a bug: the
fill check and the outcome loop were separate, so a signal that filled on bar
i+5 was scored as though the position had existed since i+1. Entries are
retracements — before the fill, price sits on the profitable side of the entry
— so the error manufactured wins and almost never losses. It inflated early
signals by +0.115 R (9.1 SE) and confirmed by +0.135 (4.2 SE), and it survived
about ten rewrites because each rewrite was a fresh chance to make the same
mistake.

Copy-paste was the root cause, so the fix is structural, not a patch.

## Running

    python3 research/test_harness.py            # always, before trusting a study
    PYTHONPATH=. python3 research/studies/di_direction.py

## Writing a study

    import research.env          # FIRST, before anything from riptide
    from research.data import load
    from research.harness import report, risk_terciles

    rows = await load()                      # every signal, already scored
    report("my idea", [r for r in rows if r.kind == "confirmed"],
           lambda row: some_number_from(row), control=risk_terciles)

`report` prints the buckets, the top-minus-bottom with its standard error,
the four splits, and a verdict. It says CANDIDATE only when the effect is
monotone, at least 3 SE, and the same sign on every split — and, if a control
is given, only when the sign survives inside every control group.

**Write down what you expect before you run it.** A predicted direction that
comes back reversed is a different and weaker result than one that was never
predicted, and the difference is invisible afterwards.

## Conventions the scorer enforces

- Outcome is measured from the FILL bar, never the signal bar.
- Unfilled scores 0.0 and pays no fee. Dropping those rows would flatter every
  result that fills less often.
- Stop and target are checked intrabar; when one bar spans both, the stop wins.
- **On the fill bar the target cannot resolve, only the stop.** A long entry is
  approached from above, so the bar's high may have printed before price came
  down to the entry. The stop has no such ambiguity: it sits beyond the entry,
  so reaching it means price passed through the fill and kept going.
- A break-even stop arms on the close, not intrabar.
- Fill and horizon windows are imported from `riptide.config`, never retyped.
  The old scripts used 12 and 48 while the live tracker used 10 and 60, so
  backtests answered a different question from `/stats`.

## Known divergence from the live tracker

`riptide/tracker.py` still lets the TARGET resolve on the fill bar, so `/stats`
is mildly optimistic on wins in the way described above. It is otherwise
correct — it holds a row PENDING until the entry is touched, which is exactly
what the old research scripts failed to do. Changing it would make already
settled rows incomparable with future ones, so it is recorded here rather than
silently altered.
