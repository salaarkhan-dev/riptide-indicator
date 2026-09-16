"""The 30-symbol discovery universe the older studies were measured on.

This list used to live in `research/lit_exit.py` as `SYMS`, and reached the
studies that need it through `research.lit_repl.DISCOVERY`. The LIT engine and
everything around it has been removed from this repository; the list is kept
here, byte for byte, so the studies that were run against it stay reproducible.

**It is a symbol list and nothing else.** No LIT code survives in it, and no
new work should use it — `research.data.SYMBOLS` is the current universe.
Keeping the old one separate is what stops a re-run of an old study silently
producing different numbers than the committed output beside it.
"""

DISCOVERY = ["ZEC_USDT", "BTC_USDT", "ETH_USDT", "SOL_USDT", "ONDO_USDT",
             "LINK_USDT", "AVAX_USDT", "DOGE_USDT", "XRP_USDT", "ADA_USDT",
             "TON_USDT", "NEAR_USDT", "BNB_USDT", "LTC_USDT", "DOT_USDT",
             "ATOM_USDT", "FIL_USDT", "APT_USDT", "ARB_USDT", "OP_USDT",
             "INJ_USDT", "SUI_USDT", "TIA_USDT", "SEI_USDT", "RUNE_USDT",
             "AAVE_USDT", "UNI_USDT", "ETC_USDT", "BCH_USDT", "TRX_USDT"]
