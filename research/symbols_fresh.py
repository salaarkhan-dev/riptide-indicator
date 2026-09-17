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


# THE THIRD FRESH SET, ranks 91-135, frozen for the shipped-configuration
# comparison in UNDERTOW_MTF_DEFAULT.md. Sets 1 and 2 both have published
# baselines by now, so neither is untouched for a new contrast.
#
# RULE 3b, ADDED HERE: drop PEGGED bases. `USDC_USDT` ranked inside the top 45
# and a stablecoin pair is a peg -- near-zero range, no trend to be right or
# wrong about, and pure noise in a study of direction. It is a judgement, so it
# is written down as a list rather than a volatility threshold nobody can
# check. IT CHANGES NOTHING RETROACTIVELY: verified that no symbol in the 23,
# in SYMBOLS_FRESH or in SYMBOLS_FRESH2 is excluded by it.
PEGGED = frozenset("USDC USDE FDUSD DAI TUSD USDD BUSD PYUSD USD1 EURT EURS "
                   "XAUT PAXG".split())
SYMBOLS_FRESH3 = (
    "CHIP_USDT CRO_USDT ZCAT_USDT AIA_USDT BLESS_USDT AR_USDT ALLO_USDT "
    "ON_USDT MONAD_USDT RAVE_USDT KAITO_USDT EDEN_USDT JASMY_USDT MAGMA_USDT "
    "THETA_USDT 0G_USDT LUNC_USDT KSM_USDT BOME_USDT TUT_USDT MORPHO_USDT "
    "MINA_USDT CVC_USDT VELVET_USDT CNPY_USDT ZIL_USDT CC_USDT SOPH_USDT "
    "VET_USDT TRB_USDT STX_USDT BILL_USDT ARX_USDT NAORIS_USDT GIGGLE_USDT "
    "COAI_USDT ROSE_USDT CATE_USDT MEMEROBINHOOD_USDT AIOT_USDT MOODENG_USDT "
    "XDC_USDT BASED_USDT MMT_USDT ZAMA_USDT"
).split()


# THE FOURTH FRESH SET, ranks 136-180, for the pullback-defect study in
# PREREG_undertow_pullback.md. Same frozen rule, including 3b.
SYMBOLS_FRESH4 = (
    "S_USDT SOLV_USDT B_USDT JST_USDT FLORKBSC_USDT GRASS_USDT SKR_USDT "
    "CVX_USDT AEON1_USDT CYS_USDT CHZ_USDT UP_USDT QNT_USDT SKY_USDT "
    "EDGE_USDT ENS_USDT RVN_USDT AXS_USDT CAP_USDT CROSS_USDT PHA_USDT "
    "DUSK_USDT H_USDT ARKM_USDT MYX_USDT MET_USDT POPCAT_USDT EVAA_USDT "
    "PEOPLE_USDT W_USDT VTHO_USDT STRK_USDT NOT_USDT DGAI_USDT ZKSYNC_USDT "
    "FOLKS_USDT ZEST_USDT PIPPIN_USDT LRC_USDT LINEA_USDT BICO_USDT "
    "CKB_USDT KMNO_USDT DYDX_USDT ACE_USDT"
).split()


# THE FIFTH FRESH SET, ranks 181-225, for the v2 rule study.
SYMBOLS_FRESH5 = (
    "BONER_USDT SUSHI_USDT LPT_USDT TAG_USDT XVG_USDT XTZ_USDT SHROOM_USDT "
    "RSR_USDT IO_USDT BANK_USDT FF_USDT GRT_USDT RE_USDT DOS_USDT ALCH_USDT "
    "ENJ_USDT MOVR_USDT ZBCN_USDT PNUT_USDT NEO_USDT ROBO_USDT ARK_USDT "
    "OKB_USDT T_USDT STG_USDT STAR_USDT STABLE_USDT SYRUP_USDT ANSEM_USDT "
    "APE_USDT AVNT_USDT SOMI_USDT BTR_USDT PORTAL_USDT GUA_USDT RUNE_USDT "
    "UB_USDT TURBO_USDT SPK_USDT PLUME_USDT OPN_USDT STANDARD_USDT "
    "NIGHT_USDT FLOW_USDT MUBARAK_USDT"
).split()


# THE SIXTH FRESH SET, ranks 226-270, for the v3 anchor study.
SYMBOLS_FRESH6 = (
    "AGI_USDT TLM_USDT CP_USDT HEMI_USDT STORJ_USDT PEAQ_USDT DATA_USDT "
    "FHE_USDT SUN_USDT PLAY_USDT SNX_USDT MNT_USDT ZORA_USDT TRIA_USDT "
    "SENT_USDT PUNDIX_USDT BB_USDT SCR_USDT LIGHT_USDT MANA_USDT DYM_USDT "
    "FLOCK_USDT CATI_USDT RESOLV_USDT DOGS_USDT ESPORTS_USDT BASECAT_USDT "
    "BERA_USDT ZKC_USDT PARTI_USDT SQD_USDT KOMA_USDT SXT_USDT SLX_USDT "
    "SIGN_USDT FONE_USDT ZBT_USDT DEXE_USDT CELO_USDT MEME_USDT COW_USDT "
    "SOCK_USDT EDU_USDT NEIROCTO_USDT ALT_USDT"
).split()


# THE SEVENTH FRESH SET, for the pin-selection study, and it adds RULE 3c.
#
# `USDC_USDT` came top of the unused list at 0.6M 24h turnover — a stablecoin
# pair, price pinned near 1.0000, which is not a market with trends and would
# have gone into a trend-following study as 12,000 bars of flat. Rule 3b drops
# a base containing `PEGGED` and USDC does not contain it, so the rule is
# widened HERE, explicitly, rather than by deleting the name:
#
#   3c. DROP a base coin in the stablecoin list. Not "looks like a stablecoin"
#       — the list is written down and a name is either on it or not.
#
# STABLE = USDC USDE FDUSD DAI TUSD USD1 BUSD PYUSD USDD USDP USDY RLUSD
#          USDF USDX
#
# THE VENUE'S LIQUID END IS NOW SPENT, and this is worth recording before the
# next set is wanted. 594 contracts qualify and 293 were already taken, so what
# remains is the tail. Each set has been one step further down it, and the
# steps are even rather than a cliff — 24h turnover in thousands of dollars:
#
#   FRESH5   min 227   median 278   max 376
#   FRESH6   min 181   median 206   max 242
#   FRESH7   min 145   median 163   max 190
#
# So FRESH7 is the same kind of population as FRESH6, about 25% thinner, which
# is the same gap FRESH6 was from FRESH5. 255 unused contracts remain after
# this one and they keep thinning. An eighth set is available; a twelfth is
# not, and by then "liquid crypto perpetuals" will have stopped being a true
# description of the population.
SYMBOLS_FRESH7 = (
    "CORE_USDT MTL_USDT SWARM_USDT BAT_USDT FORM_USDT IMX_USDT "
    "ACH_USDT SUPER_USDT MANTRA_USDT BSB_USDT DODO_USDT SAHARA_USDT "
    "PROVE_USDT POWR_USDT GUN_USDT SIREN_USDT INIT_USDT GPS_USDT "
    "AT_USDT BAN_USDT OG_USDT HOLO_USDT PROM_USDT BIGTIME_USDT "
    "BREV_USDT ONT_USDT HAEDAL_USDT G_USDT ASTR_USDT LISTA_USDT "
    "TMX_USDT TST_USDT AKT_USDT ORCA_USDT NES_USDT ONG_USDT "
    "CFG_USDT API3_USDT ZRX_USDT ID_USDT GRIFFAIN_USDT BARD_USDT "
    "TRADOOR_USDT TOWNS_USDT LYN_USDT"
).split()


def assert_disjoint():
    """A fresh holdout that shares a symbol with the training set is not one."""
    from research.data import SYMBOLS
    sets = {"SYMBOLS": set(SYMBOLS), "SYMBOLS_FRESH": set(SYMBOLS_FRESH),
            "SYMBOLS_FRESH2": set(SYMBOLS_FRESH2),
            "SYMBOLS_FRESH3": set(SYMBOLS_FRESH3),
            "SYMBOLS_FRESH4": set(SYMBOLS_FRESH4),
            "SYMBOLS_FRESH5": set(SYMBOLS_FRESH5),
            "SYMBOLS_FRESH6": set(SYMBOLS_FRESH6),
            "SYMBOLS_FRESH7": set(SYMBOLS_FRESH7)}
    names = sorted(sets)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            both = sorted(sets[a] & sets[b])
            if both:
                raise AssertionError(f"{a} and {b} overlap: {both}")
    return True
