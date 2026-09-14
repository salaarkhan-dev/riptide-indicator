"""The smallest abstraction that keeps two strategies from mixing.

Deliberately not a plugin framework. A strategy is a name, a way to be fed
closed candles, and a way to emit records; nothing here forces the existing
production engine through a rewrite to satisfy an interface.
"""

from __future__ import annotations

from typing import Protocol, Any, Sequence


class StrategyEngine(Protocol):
    """A strategy that can be fed bars and asked what it found.

    `update` is given CLOSED candles only. Implementations must not reach for
    data after the bar they are reasoning about.
    """

    name: str
    version: str

    def update(self, symbol: str, tf: str, candles: Sequence[Any]) -> None:
        ...

    def events(self) -> list[dict]:
        ...

    def snapshot(self) -> dict:
        ...
