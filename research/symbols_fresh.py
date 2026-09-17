"""A SECOND symbol universe, disjoint from `research.data.SYMBOLS`.

WHY IT EXISTS. Eight Undertow studies have now been run on the same 23
symbols, and all four quadrants of that set (even/odd symbols x older/newer
bars) have been scored for something. Reusing a quadrant for a new question is
not fatal, but the more questions one dataset is asked, the more the whole
programme is a garden of forking paths — and "every quadrant is spent" had
already been written on two measurement pages as a limit on what could be
tested next.

It turned out not to be a limit. The exchange lists **594 crypto USDT perpetuals**
that pass the filter below, against the 23 in use. This is the fresh holdout
that the earlier pages said did not exist.

THE SELECTION RULE, fixed and mechanical, applied once on 2026-09-17:

  1. every `*_USDT` perpetual from `contract/ticker`
  2. keep it only if `contract/detail` says `apiAllowed` and not `isHidden`
  3. DROP anything whose `conceptPlate` contains `mc-trade-zone-tradfi` —
     tokenised stocks, metals, oil and index products. They are on the venue
     and they are not the population: they have session breaks, and a session
     break is exactly what `bars_per()` and `range_basis()` mis-read. This
     repository has been bitten by it once already, in the note about XAUUSD
     and XAUUSDT.P disagreeing.
  4. sort by 24h quote volume, descending
  5. drop the 23 already in `research.data.SYMBOLS`
  6. take the first 45

THE LIST IS FROZEN HERE AS A LITERAL, not recomputed. A universe defined by
"today's top 45 by volume" is a different universe every day, and a study run
against a moving population cannot be reproduced.

WHAT THIS IS NOT. It is not a random sample of the venue. It is the liquid end
of it, chosen the same way the original 23 evidently were, which makes the two
sets comparable — but a result that holds here is a result about liquid crypto
perpetuals and not about the 594.
"""

SYMBOLS_FRESH = (
    "NEAR_USDT LSK_USDT BR_USDT SYN_USDT XLM_USDT ONE_USDT AAVE_USDT "
    "ASTER_USDT WLFI_USDT SHIB_USDT INJ_USDT FARTCOIN_USDT HBAR_USDT "
    "DOT_USDT BNB_USDT LIT_USDT BULLA_USDT HNT_USDT ZEN_USDT PONS_USDT "
    "AIN_USDT APT_USDT FILECOIN_USDT XPL_USDT TIA_USDT MERL_USDT "
    "PENGU_USDT FET_USDT CRV_USDT SEI_USDT TRUMPOFFICIAL_USDT VVV_USDT "
    "OP_USDT AVA_USDT XMR_USDT BCH_USDT ICP_USDT RAY_USDT ETHFI_USDT "
    "MARSCOIN_USDT CAKE_USDT POWER_USDT WIF_USDT BEAT_USDT ETC_USDT"
).split()


# THE SECOND FRESH SET, ranks 46-90 under the identical rule, frozen the same
# day. It exists because UNDERTOW_HTF.md has now been read on SYMBOLS_FRESH:
# the numbers there are known, so that set is no longer untouched for a new
# question. Fetching another 45 costs ten minutes and 594 qualify, which is a
# better answer than arguing about how much contamination a known baseline is.
#
# ONE NAME LOOKS WRONG AND IS NOT. `4STOCK_USDT` and `SPX_USDT` are MEMECOINS
# named after equities -- the venue tags them `mc-trade-zone-MEME` and they
# trade 24/7. The genuinely tokenised stocks carry `mc-trade-zone-tradfi`, as
# TESLA_USDT does, and rule 3 excludes those. Do not "fix" this by name.
SYMBOLS_FRESH2 = (
    "1000BONK_USDT BTW_USDT IOST_USDT BRETT_USDT BATON_USDT PYTH_USDT "
    "GENIUS_USDT LDO_USDT COTI_USDT SKYAI_USDT UAI_USDT KAS_USDT JUP_USDT "
    "HEI_USDT EGLD_USDT SPX_USDT SAGA_USDT POL_USDT PENDLE_USDT ALGO_USDT "
    "ATOM_USDT LONGXIA_USDT RENDER_USDT ORDI_USDT EIGEN_USDT GALA_USDT "
    "VIRTUAL_USDT ZRO_USDT PI_USDT CFX_USDT FLOKI_USDT LAB_USDT RIVER_USDT "
    "JTO_USDT PIEVERSE_USDT GRAM_USDT REZ_USDT 4_USDT TRX_USDT SAND_USDT "
    "BSV_USDT 4STOCK_USDT NIULAI_USDT AERO_USDT KITE_USDT"
).split()


def assert_disjoint():
    """A fresh holdout that shares a symbol with the training set is not one."""
    from research.data import SYMBOLS
    sets = {"SYMBOLS": set(SYMBOLS), "SYMBOLS_FRESH": set(SYMBOLS_FRESH),
            "SYMBOLS_FRESH2": set(SYMBOLS_FRESH2)}
    names = sorted(sets)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            both = sorted(sets[a] & sets[b])
            if both:
                raise AssertionError(f"{a} and {b} overlap: {both}")
    return True
