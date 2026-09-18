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


# THE EIGHTH FRESH SET, for the swing-scale study — 50/5 against 6/2. Same
# frozen rule, rules 3b and 3c included.
#
# AND IT CORRECTS SOMETHING THE FRESH7 NOTE ABOVE GOT WRONG. That note read a
# steady ~25% decline off three consecutive sets and projected it forward. It
# was a one-day snapshot of a number that moves: re-ranked a day later, FRESH6
# reads 124-263k rather than the 181-242k recorded there, and FRESH8 is NOT
# thinner than FRESH7 --
#
#   FRESH6   min 124   median 197   max  263
#   FRESH7   min 111   median 159   max 1095
#   FRESH8   min 124   median 135   max 1222
#
# 24h turnover is a rolling window on a venue where a symbol can wake up, so
# the tail is noisy rather than monotone. What DOES hold from that note is the
# structural part: the top of the book is spent, 210 unused contracts remain,
# and every further set is drawn from further down. The projection was the
# wrong shape of claim to make from three points.
SYMBOLS_FRESH8 = (
    "BABY_USDT DRIFT_USDT ELSA_USDT TAC_USDT ATH_USDT XAN_USDT "
    "IOTA_USDT GRVT_USDT MEGA_USDT COLLECT_USDT NIL_USDT "
    "AIGENSYN_USDT ENSO_USDT 1000000BABYDOGE_USDT METIS_USDT "
    "INX_USDT XAI_USDT A_USDT BLUR_USDT LUNANEW_USDT POLYX_USDT "
    "TWT_USDT BANANAS31_USDT KAVA_USDT 1000RATS_USDT MOVE_USDT "
    "OPG_USDT MASK_USDT FIDA_USDT BENBSC_USDT HIVE_USDT OGN_USDT "
    "COMP_USDT HAJIMI_USDT YFI_USDT APR_USDT KAIA_USDT LA_USDT "
    "USUAL_USDT TNSR_USDT YGG_USDT AIXBT_USDT O_USDT IOTX_USDT "
    "BAND_USDT"
).split()


# THE NINTH FRESH SET, and it exists because the eighth was SPENT ON A VOID
# RUN. PREREG_undertow_scale.md registered an impossibility that fired, so its
# numbers are unpublishable -- but they were computed and read, so FRESH8
# cannot serve the same question twice. See
# ../indicators/undertow/measurements/UNDERTOW_SCALE.md.
#
# A universe can be spent by a study that produces nothing. That is the cost of
# a badly specified check and it is worth one comment here so the next person
# sees the price before writing one.
#
#   FRESH7   min 109   median 158   max 1095
#   FRESH8   min 118   median 138   max 1227
#   FRESH9   min 109   median 115   max  164
#
# 165 unused contracts remain.
SYMBOLS_FRESH9 = (
    "AIOZ_USDT JELLYJELLY_USDT RED_USDT FOGO_USDT YB_USDT NOM_USDT "
    "STBL_USDT BMT_USDT CELR_USDT ILV_USDT RARE_USDT PUFFER_USDT "
    "WAVES_USDT ME_USDT RLC_USDT ASTEROID_USDT CLANKER_USDT "
    "GMT_USDT MEW_USDT MANTA_USDT M_USDT PRL_USDT BP_USDT BIO_USDT "
    "1INCH_USDT ETHW_USDT TOSHI_USDT AIO_USDT XCN_USDT BIRB_USDT "
    "STEEM_USDT PIXEL_USDT SPELL_USDT CHILLGUY_USDT DEEP_USDT "
    "THE_USDT BANANA_USDT FLR_USDT TAKE_USDT WOO_USDT ICNT_USDT "
    "HUMA_USDT QTUM_USDT ACT_USDT GOAT_USDT"
).split()


# THE TENTH FRESH SET, for the leg-anchor study. 100-112k 24h turnover, and
# the band is narrowing as the tail flattens out: FRESH8 122-1230, FRESH9
# 109-168, FRESH10 100-112. 122 unused contracts remain, which is two more
# sets of this size at most before the population stops resembling the one
# every earlier page was measured on.
SYMBOLS_FRESH10 = (
    "KAT_USDT BIANRENSHENG_USDT GMX_USDT EUL_USDT AXL_USDT "
    "SOONNETWORK_USDT 1000000MOG_USDT MELANIA_USDT FLUX_USDT "
    "US_USDT SKL_USDT SSV_USDT DOOD_USDT SHELL_USDT CLO_USDT "
    "DIA_USDT NEWT_USDT CHR_USDT AUCTION_USDT VELODROME_USDT "
    "PHAROS_USDT HOME_USDT 1000BTT_USDT JIMOTHY_USDT ZKP_USDT "
    "CTSI_USDT ERA_USDT MAGIC_USDT B3_USDT ZEREBRO_USDT JCT_USDT "
    "HMSTR_USDT USTC_USDT AEVO_USDT OPENLEDGER_USDT HYPER_USDT "
    "STO_USDT ARPA_USDT COOKIE_USDT CTR_USDT ACU_USDT SFP_USDT "
    "TOAD_USDT BAS_USDT BLEND_USDT"
).split()


# THE ELEVENTH FRESH SET, for the complement study — the one finding in this
# project with a positive number behind it, which is exactly the kind that has
# to be replicated on data nobody has seen. 91-100k 24h turnover.
#
# THE ORDERING WAS RECOMPUTED ON 2026-09-18, not read off the 2026-09-17 run.
# 24h volume is a rolling window and the ranks move, so "ranks 496-540" is not
# a thing that survives a day. What IS stable is the RULE, and it is applied
# unchanged: the same filter, the same exclusions, sorted by 24h quote volume,
# then every symbol already in SYMBOLS or in FRESH..FRESH10 dropped — 473 of
# them — and the next 45 taken. 593 contracts passed the filter and 120 were
# unused, so this leaves 75: one more set of this size and nothing after it.
#
# AND THE BAND IS RUNNING OUT, which is a limit on the science and not just on
# the bookkeeping. FRESH8 122-1230k, FRESH9 109-168k, FRESH10 100-112k,
# FRESH11 91-100k. Thinner names are also NEWER listings, and 12,000 bars of
# 1h is 500 days: FRESH7 could only field 30 of 45 symbols on Min60. Any study
# whose primary timeframe is 1h should check its coverage before it reads a
# result, because "not reported" is a likelier outcome here than it was at
# FRESH2.
SYMBOLS_FRESH11 = (
    "KGEN_USDT BLUAI_USDT HOT_USDT BEAMX_USDT SAPIEN_USDT CAT_USDT "
    "CGPT_USDT FIGHT_USDT SANTOS_USDT SUPRA_USDT ANKR_USDT AZTEC_USDT "
    "AWE_USDT KNC_USDT APEX_USDT ALICE_USDT XPIN_USDT XVS_USDT "
    "MITO_USDT DOLO_USDT VANA_USDT AGT_USDT AGLD_USDT ZETA_USDT "
    "BROCCOLI_USDT LQTY_USDT KERNEL_USDT ARCSOL_USDT BROCCOLIF3B_USDT "
    "TRUTH_USDT NMR_USDT IRYS_USDT HANA_USDT LAYER_USDT "
    "WOTAMALAILE_USDT AVAAI_USDT TURTLE_USDT IN_USDT RON_USDT "
    "MIRA_USDT C_USDT IDOL_USDT MAV_USDT NXPC_USDT SAFE_USDT"
).split()



# THE TWELFTH FRESH SET, AND THE LAST ONE OF THIS SIZE. 86-156k 24h turnover.
# 592 contracts pass the filter, 518 were already spoken for, 74 were unused --
# so this takes 45 and leaves TWENTY-NINE. There is no thirteenth set of 45.
#
# WHAT THAT MEANS FOR THE PROGRAMME, said here rather than discovered later:
# the disjoint-holdout method this repository has run twelve times is over.
# A study after this one has three honest options and no fourth --
#
#   * 29 contracts, which will not field 20 symbols on Min60 and so cannot
#     report the timeframe most of these questions are asked on
#   * a smaller set, accepting that the population is now the thin tail and
#     no longer resembles the one every earlier page measured
#   * a different design entirely -- walk-forward on the spent sets, or a
#     prospective forward record, which is what the watch was built for
#
# This set is spent on the SHIPPED CONFIGURATION rather than on one more
# component, which is the right last use of it: twelve studies measured parts
# and none measured the chart anybody would actually trade.
SYMBOLS_FRESH12 = (
    "VELO_USDT GLM_USDT F_USDT WAL_USDT TAIKO_USDT RECALL_USDT ESP_USDT "
    "C98_USDT ALPINE_USDT SONIC_USDT CTC_USDT EPIC_USDT XEC_USDT "
    "TROLLSOL_USDT MAVIA_USDT XNY_USDT ZIG_USDT SPACE_USDT 2Z_USDT "
    "OFC_USDT EYE_USDT CTK_USDT RPL_USDT UMA_USDT AMP_USDT WCT_USDT "
    "SLP_USDT JOE_USDT LUMIA_USDT FRAX_USDT NPC_USDT ORDER_USDT "
    "GWEI_USDT TA_USDT ANIME_USDT GAS_USDT NEX_USDT BOBA_USDT OL_USDT "
    "Q_USDT PTB_USDT MOCA_USDT WAXP_USDT PUMPBTC_USDT PROMPT_USDT"
).split()


# 2026-09-18, RE-COUNTED AGAINST THE LIVE EXCHANGE, and the note above is
# WRONG in the direction that matters. It says 29 contracts remain. Today's
# contract/detail plus contract/ticker, filtered exactly as
# riptide/exchange.py::universe does it -- USDT quote, state 0, apiAllowed,
# no "tradfi" conceptPlate, 80k 24h turnover -- gives 585 eligible, 563
# spoken for, and **22 UNUSED**. One of those is USDC_USDT, a stablecoin this
# file already rejected once at the top of an unused list, so **21 are
# usable** and every one of them sits at the 80-85k floor.
#
# The first count was taken before this run's own filter was applied to the
# whole list; 447 contracts look unused until the tokenised equities, metals,
# indices and oil are removed, and those are most of what is left at the top
# of the exchange by turnover.
#
# WHAT THAT CHANGES. The note above offers "29 contracts, which will not field
# 20 symbols on Min60". The real position is worse and should be stated
# plainly: at the coverage the last three sets actually achieved -- 97% on
# Min15, 89% on Min30, 67% on Min60 -- 21 contracts field about 20 / 19 / 14.
# A thirteenth set cannot report Min30 either, and the symbols it would report
# Min15 on are the thinnest tail on the venue, which is not the population any
# earlier page measured.
#
# SO THE DISJOINT HOLDOUT IS NOT NEARLY OVER, IT IS OVER. The two honest
# designs left are the two already named above: walk-forward on the spent
# sets, and the prospective forward record the watch was built for. A study
# proposed after this line should say which of those it is before it says
# anything else.
REMAINING_ELIGIBLE = 21


def assert_disjoint():
    """A fresh holdout that shares a symbol with the training set is not one."""
    from research.data import SYMBOLS
    sets = {"SYMBOLS": set(SYMBOLS), "SYMBOLS_FRESH": set(SYMBOLS_FRESH),
            "SYMBOLS_FRESH2": set(SYMBOLS_FRESH2),
            "SYMBOLS_FRESH3": set(SYMBOLS_FRESH3),
            "SYMBOLS_FRESH4": set(SYMBOLS_FRESH4),
            "SYMBOLS_FRESH5": set(SYMBOLS_FRESH5),
            "SYMBOLS_FRESH6": set(SYMBOLS_FRESH6),
            "SYMBOLS_FRESH7": set(SYMBOLS_FRESH7),
            "SYMBOLS_FRESH8": set(SYMBOLS_FRESH8),
            "SYMBOLS_FRESH9": set(SYMBOLS_FRESH9),
            "SYMBOLS_FRESH10": set(SYMBOLS_FRESH10),
            "SYMBOLS_FRESH11": set(SYMBOLS_FRESH11),
            "SYMBOLS_FRESH12": set(SYMBOLS_FRESH12)}
    names = sorted(sets)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            both = sorted(sets[a] & sets[b])
            if both:
                raise AssertionError(f"{a} and {b} overlap: {both}")
    return True
