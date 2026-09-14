"""Strategy namespaces.

The production Riptide strategy is NOT moved in here and is not refactored to
fit. It stays exactly where it is. This package exists so a second strategy can
hold its own state without sharing any with it.

What may be shared: candle loading, the symbol universe, the scheduler, tracker
persistence, the scorer, event grouping, reporting.

What may NOT be shared: strategy state, signal-generation assumptions,
entry/stop state, exit-policy state.
"""
