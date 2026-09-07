"""Fetch once, run many. Every study takes its rows from here.

The signal loop was also copy-pasted into every old script, which is how the
symbol list, the timeframe and the freshness rules drifted between studies
that were supposed to be comparable.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import aiohttp

from riptide.config import CFG, Cfg
from riptide.engine import atr_series, run_engine
from riptide.exchange import fetch_candles
from research.harness import simulate

SYMBOLS = ("BTC_USDT ETH_USDT SOL_USDT XRP_USDT ZEC_USDT HYPE_USDT PEPE_USDT "
           "DOGE_USDT SUI_USDT ARB_USDT ENA_USDT USELESS_USDT TAO_USDT "
           "UNI_USDT LINK_USDT ADA_USDT WLD_USDT PUMPFUN_USDT AKE_USDT "
           "DASH_USDT AVAX_USDT LTC_USDT ONDO_USDT").split()


@dataclass
class Row:
    """One signal, its outcome, and everything a feature might want.

    Carries `r` directly so research.harness.report can bucket a list of these
    without knowing what produced them.
    """
    symbol: str
    kind: str                 # "early" | "confirmed"
    r: float
    filled: bool
    mfe: float
    mae: float
    risk_pct: float
    split_symbol: int         # 0/1, for the symbol-half split
    split_window: bool        # True in the first half of the window
    bar: int
    signal: object            # the Setup or Early itself
    candles: list = field(repr=False, default_factory=list)


async def load(symbols=SYMBOLS, cfg: Cfg = CFG, interval: str = "",
               lookback: int = 2000, **exit_opts) -> list[Row]:
    """Every signal on every symbol, scored once with the shared simulator.

    exit_opts go straight to research.harness.simulate, so a study that wants
    a different target or a break-even rule changes nothing else.
    """
    import os
    os.environ.setdefault("RIPTIDE_LOOKBACK", str(lookback))
    rows: list[Row] = []
    async with aiohttp.ClientSession() as sess:
        for n, sym in enumerate(symbols):
            try:
                cs = await fetch_candles(sess, sym, interval)
            except Exception:
                continue
            if len(cs) < 300:
                continue
            early: list = []
            setups = run_engine(sym, cs, cfg, early_out=early)
            idx = {c.t: i for i, c in enumerate(cs)}
            mid = cs[len(cs) // 2].t
            for kind, sigs, key in (("early", early, "fvg_time"),
                                    ("confirmed", setups, "detected_time")):
                for x in sigs:
                    i = idx.get(getattr(x, key))
                    if i is None:
                        continue
                    risk = abs(x.entry - x.stop)
                    if risk <= 0 or x.entry <= 0:
                        continue
                    o = simulate(cs, i, x.entry, x.stop, x.is_long, **exit_opts)
                    # A signal too close to the end of the data has not had
                    # its window; including it would score an unfinished trade
                    # as a timeout at whatever price the fetch happened to end
                    # on, which is noise dressed as an outcome.
                    if o.exit_bar is None and o.filled:
                        continue
                    rows.append(Row(symbol=sym, kind=kind, r=o.r,
                                    filled=o.filled, mfe=o.mfe, mae=o.mae,
                                    risk_pct=100 * risk / x.entry,
                                    split_symbol=n % 2,
                                    split_window=cs[i].t < mid,
                                    bar=i, signal=x, candles=cs))
    return rows


def load_sync(**kw) -> list[Row]:
    return asyncio.run(load(**kw))


def atr_at(row: Row, length: int = 0) -> float:
    """ATR on the signal bar, cached per symbol."""
    key = (id(row.candles), length or CFG.atr_len)
    cache = atr_at.__dict__.setdefault("_c", {})
    if key not in cache:
        cache[key] = atr_series(row.candles, length or CFG.atr_len)
    return cache[key][row.bar]
