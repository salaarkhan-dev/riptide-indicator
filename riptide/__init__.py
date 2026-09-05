"""
Riptide scanner — phase 1 (alerts only, no API key, no orders).

Port of the Riptide Pine indicator: liquidity pool -> sweep -> market structure
shift -> fair value gap. Polls MEXC futures candles just after each bar close,
runs the same engine, and sends new setups to Telegram.

Deliberately read-only. There is no exchange key anywhere in this package and
no code path that can place an order.

Layout
------
    config    settings from the environment, and Cfg — the engine's calibrated
              defaults, which mirror the Pine inputs
    engine    the state machine. Pure and synchronous: no I/O, no clock
    exchange  MEXC reads: contracts, turnover, candles
    storage   SQLite dedupe and key/value bookkeeping
    telegram  delivery and message formatting
    scanner   the scan cycle and the loop that drives it
    commands  Telegram command handling
    app       startup and task supervision

Sources: pivot pools, previous day high/low, previous week high/low. Sessions
are not implemented here; they are off by default in the indicator too.
"""

__all__ = ["config", "engine", "exchange", "storage", "telegram",
           "scanner", "commands", "app"]
