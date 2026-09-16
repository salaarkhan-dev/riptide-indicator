"""The indicator registry: what a watchable indicator has to provide.

WHY THIS EXISTS. Two heads-up watches were written in this repository and the
second was a copy of the first. `watch.py` and `exhaust.py` were ~470 and ~485
lines, of which roughly 300 were identical: the dedupe table, the freshness
gate, the character budget, the "which timeframes just closed" scheduler, the
loop that never dies, the on/off override, the timeframe override, and the
`last_cycle` dict that lets /status say why a close was quiet. Every one of
those was fixed twice, and the digest character budget was fixed twice a month
apart because the second copy did not get the first one's lesson.

So the plumbing moved into `riptide/watch.py` and an indicator now declares
what is genuinely its own: how to find its hits, how to render one line, and
how to group them. Adding a third indicator is a module in this package and one
`register()` call — not another 470-line file to keep in step by hand.

WHAT THIS IS NOT. It is not a strategy framework. Nothing registered here may
arm an outcome row, carry an entry, a stop or a grade, or reach any table
/stats scores. A watch answers one question — "which chart should I open" —
and the separation is the whole reason a watch list is allowed to exist beside
measured alerts without contaminating them.

TO ADD AN INDICATOR, see `indicators/README.md` at the repo root. The short
version is four things:

    1. a detector: candles in, `Hit`s out
    2. an `Indicator(...)` describing it, built from the pieces here
    3. `register(...)` it, and add one import line to `__init__.py` beside it
    4. an entry in `indicators/<name>/INDICATOR.md` saying what was MEASURED

Step 3 is the whole deployment switch. `app.py` starts a loop for everything
registered, `storage.py` creates one table for all of them, and `commands.py`
routes `/<name>` to any of them — so there is no fourth place to remember.

Step 4 is not paperwork. Both watches that exist ship with a measured verdict
of "no edge", and the digest says so in its own subtitle. An indicator whose
claim has never been tested does not get a quieter caveat than the ones that
have been.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

# ---------------------------------------------------------------- one hit


class Hit:
    """One thing an indicator found, on one symbol, on one closed bar.

    `key` is the dedupe signature and must be stable across restarts: the same
    event seen twice has to produce the same string, or every restart replays
    the chat. It is namespaced by the indicator automatically, so an indicator
    only has to be unique within itself.

    `bar_time` is the bar's CLOSE, not its open. Both existing detectors got
    this wrong first and both have a comment about it: a hit is only true once
    the bar has closed, so the moment it became real is `t + step`, and that is
    what the freshness gate and the "Nm ago" row both measure from.

    `sort` orders the digest and `group` names the block a row belongs to;
    together they are the only recommendation a digest makes. `detail` is the
    indicator's own compact description, stored on the dedupe row so a
    measurement can be run later against what was actually sent.
    """

    __slots__ = ("key", "symbol", "tf", "is_long", "bar_time", "price",
                 "group", "sort", "detail", "extra")

    def __init__(self, key: str, symbol: str, tf: str, is_long: bool,
                 bar_time: int, price: float, group: str = "",
                 sort: tuple = (), detail: str = "", **extra):
        self.key, self.symbol, self.tf = key, symbol, tf
        self.is_long, self.bar_time, self.price = is_long, bar_time, price
        self.group, self.sort, self.detail = group, sort, detail
        self.extra = extra

    def __repr__(self) -> str:           # for a failing test, not for the chat
        return (f"Hit({self.symbol} {self.tf} "
                f"{'up' if self.is_long else 'down'} {self.detail})")


# ------------------------------------------------------------- one setting


@dataclass(frozen=True)
class Option:
    """A per-indicator switch the framework stores, validates and prints.

    The framework already owns on/off and the timeframe list because every
    watch needs them. Everything else an indicator wants to be adjustable from
    the chat is declared here and it gets `/name <key> <value>` for free.

    `kind` is "bool", "choice" or "number". `choices` applies to "choice";
    `lo`/`hi` clamp a "number". `blurb` is what /name prints beside it — say
    what the setting DOES to the volume, because on a heads-up list that is the
    only thing it decides.
    """
    key: str
    kind: str
    default: object
    blurb: str = ""
    choices: tuple = ()
    lo: float = 0.0
    hi: float = 1e9

    def parse(self, raw: str):
        """A chat string to a stored value, or None if it is not valid."""
        if self.kind == "bool":
            if raw in ("on", "1", "yes", "true"):
                return True
            if raw in ("off", "0", "no", "false"):
                return False
            return None
        if self.kind == "choice":
            return raw if raw in self.choices else None
        try:
            return min(self.hi, max(self.lo, float(raw)))
        except ValueError:
            return None

    def read(self, raw: str):
        """A stored string back to a value, falling back to the default.

        Validated on READ rather than on write, so a database carrying a value
        this build no longer understands falls back instead of taking the watch
        loop down. `watch.intervals` does the same thing for the same reason.
        """
        if raw == "":
            return self.default
        v = self.parse(raw)
        return self.default if v is None else v


# --------------------------------------------------------- the indicator


@dataclass(frozen=True)
class Indicator:
    """Everything the generic watch needs to run one indicator.

    Only `detect` and `row` are real work. The rest is description, and the
    defaults are the two existing watches' defaults because those were argued
    out against measured alert rates rather than picked.
    """

    # Identity. `name` is the slug: it is the command (`/exhaust`), the meta
    # key prefix (`exhaust_alerts`), and the dedupe namespace. Changing it
    # orphans a user's settings, so it is chosen once.
    name: str
    title: str                       # the digest header word, shouted
    glyph: str                       # one character, on the header
    unit: str                        # "count", "break" — pluralised with an s

    # THE CAVEAT IS MANDATORY AND IT IS NOT DECORATION. It goes under every
    # digest header. Both shipped watches measured at no edge and say so; an
    # indicator that has not been measured says THAT instead. There is no
    # value of this field that means "this is a trade", because nothing in a
    # watch list is one.
    caveat: str

    # candles, symbol, tf, settings -> (hits, dropped_by_own_gates)
    #
    # The second number is not bookkeeping. The only question a quiet alert
    # service ever raises is whether it is broken, and "18 found, 18 below the
    # gate" and "nothing happened" look identical from the chat. /status prints
    # both.
    detect: Callable[..., tuple]

    # hit, group_label -> one digest line. The label is "" on every row but the
    # first of its block, so the rows under it read as a list.
    row: Callable[..., str]

    # hit -> (sort_key, group_label). Decides the order of the digest and which
    # block each row falls in. Groups appear in first-seen sorted order.
    classify: Callable[..., tuple]

    min_bars: int = 60               # under this the symbol has no answer
    recent_bars: int = 6             # how far back a cycle looks for a hit
    fresh_bars: int = 2              # older than this is recorded, not sent
    max_lines: int = 25              # the digest's line cap
    label_w: int = 8                 # the group column's width
    default_enabled: bool = False
    default_intervals: tuple = ("Min60",)
    fallback_interval: str = "Min60"  # if config and overrides are all invalid
    options: tuple = ()              # extra Options, see Option

    # ---- what /name prints. Prose, because a heads-up list is read, not
    # ---- executed, and every one of these answers a question a reader has.
    blurb: str = ""                  # what the indicator actually marks
    evidence: str = ""               # what was MEASURED, at length
    examples: str = ""               # the /name lines worth copying

    # Timeframes whose ALERT RATE has been counted. The command refuses the
    # others — not because they would break anything, but because the rate is
    # the only thing that decides whether a heads-up stays readable, and an
    # uncounted timeframe is an unbounded one.
    tf_counted: tuple = ()
    # (db, tfs=None, **option_overrides) -> alerts a day across the universe.
    # Takes overrides so a reply can quote the rate a change WOULD produce.
    rate: Callable = None

    def option(self, key: str):
        for o in self.options:
            if o.key == key:
                return o
        return None


# ----------------------------------------------------------- the registry


_REGISTRY: dict = {}


def register(ind: Indicator) -> Indicator:
    """Add an indicator to the watch. Returns it, so a module can do

        SPEC = register(Indicator(...))

    Re-registering the same name is an error rather than a silent replacement:
    two modules claiming one slug would share a dedupe namespace and a settings
    namespace, and the symptom would be one of them going quiet.
    """
    if ind.name in _REGISTRY and _REGISTRY[ind.name] is not ind:
        raise ValueError(f"indicator {ind.name!r} is already registered")
    if not ind.caveat:
        raise ValueError(f"indicator {ind.name!r} has no caveat; see the "
                         f"module docstring — that field is mandatory")
    _REGISTRY[ind.name] = ind
    return ind


def get(name: str):
    return _REGISTRY.get(name)


def all_indicators() -> tuple:
    """Registered indicators, in registration order — which is import order,
    which is the order app.py starts their loops and /status lists them."""
    return tuple(_REGISTRY.values())


def unregister(name: str) -> None:
    """Only for tests. Production registers at import and never removes."""
    _REGISTRY.pop(name, None)
