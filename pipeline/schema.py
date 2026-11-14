"""Column order of the four published CSVs. The pipeline refuses to write a file whose columns differ."""

HOUSE = """
state district code dem_nominee rep_nominee n_dem n_rep winner_party prior_party incumbent_2025
result_text dem_votes rep_votes total_votes dem_pct rep_pct dem_margin pct_expected_vote called
nbc_dem_name nbc_rep_name results_source nbc_winner_party alt_dem_margin alt_source source_disagree
harris24 trump24 pres24_margin pres24_source redrawn_2026 pres24_from_memory hisp_share_acs24
ba_plus_share_acs24 overperf incumbency jd_endorsed dsa_endorsed sanders_endorsed ourrev_endorsed
cpcpac_endorsed newdem_endorsed bluedog_endorsed welcome_endorsed endorse_lines_found
endorse_source cpc_member newdem_member bluedog_member faction_sources contested_ok d_inc r_inc
prog mod prog_strict mod_strict prog_member mod_member faction prog_only mod_only prog_mod_both
faction_strict prog_strict_only mod_strict_only prog_strict_mod_strict_both faction_member
prog_member_only mod_member_only prog_member_mod_member_both competitive flip d_win_trump_seat
""".split()

STATEWIDE = """
state st office dem_nominee dem_type rep_nominee dem_pct rep_pct dem_margin dem_margin_2party
pres2024_margin swing_vs_2024 faction faction_confidence sanders_endorsed left_groups m4a ice
israel trans self_description dem_incumbent rep_incumbent prior_incumbent opp_prior_office
opp_favorability opp_scandals rep_officeholder opp_weak_flag opp_note cook_final cook_num
white_share_pct dem_pct_white dem_pct_nonwhite exit_source outside_against_dem_usd
outside_for_dem_usd total_outside_usd spending_source spending_notes house_dem_margin_2party
senate_minus_house_2party faction_sources results_source
""".split()

SENATE_MONEY = """
state st office democrat republican faction question_group cook_final cook_num dem_pct rep_pct
vap_2024 total_votes_2026 gov_outside_for_dem gov_outside_against_dem gov_outside_source
gov_outside_notes dem_cand_id rep_cand_id dem_fec_name rep_fec_name dem_receipts dem_disbursements
dem_cash_on_hand dem_fec_coverage_end rep_receipts rep_disbursements rep_cash_on_hand
rep_fec_coverage_end nomination_date_used pro_dem_party_gen pro_dem_party_pre pro_dem_prog_gen
pro_dem_prog_pre pro_dem_other_gen pro_dem_other_pre pro_dem_total_gen pro_dem_total_pre
against_dem_party_gen against_dem_party_pre against_dem_aipac_gen against_dem_aipac_pre
against_dem_crypto_gen against_dem_crypto_pre against_dem_other_gen against_dem_other_pre
against_dem_total_gen against_dem_total_pre pro_dem_crypto_gen party_ie_first_date
party_ie_share_by_sep30 party_ie_by_month party_ie_breakdown_gen pro_dem_party_gen_excl_lcn
progressive_ie_breakdown dem_coord_party rep_coord_party dscc_direct_contrib nrsc_direct_contrib
top_pro_dem_gen top_against_dem_gen general_ie_total race_total_2nominees party_pro_dem_per_vap
pro_dem_total_per_vap against_dem_total_per_vap dem_receipts_per_vap race_total_per_vap
coverage_note senate2020_all_in_total senate2020_all_in_per_vap senate2022_all_in_total
senate2022_all_in_per_vap senate2026_all_in_total senate2026_all_in_per_vap
past_senate_mean_per_vap ratio_2026_vs_past rating_mean_all_in_per_vap ratio_vs_rating_mean
rating_mean_party_pro_dem_per_vap senate2024_all_in_total senate2024_all_in_per_vap
""".split()

HOUSE_MONEY = """
code dem_nominee rep_nominee faction incumbency pres24_margin dem_margin overperf total_votes
dem_cand_id dem_receipts dem_disbursements dem_cash_on_hand dem_indiv_contrib dem_cand_self_funding
dem_cvg_end rep_cand_id rep_receipts rep_cash_on_hand rep_cvg_end dccc_coord_dem dccc_contrib_dem
ie_pro_a_estab estab_total ie_pro_b_prog_core ie_pro_b2_prog_broad ie_pro_c_mod_core
ie_pro_c2_mod_broad ie_pro_d_crypto ie_pro_d_other ie_pro_total pro_dem_outside_total
ie_pro_total_after_oct14 ie_pro_a_estab_after_oct14 hmp_first_ie_date nrcc_coord_rep ie_anti_clf
ie_anti_aipac_udp ie_anti_crypto ie_anti_other ie_anti_total anti_dem_outside_total estab_per_voter
pro_dem_outside_per_voter anti_dem_outside_per_voter dem_receipts_per_voter rep_receipts_per_voter
net_outside_per_voter red_to_blue_primary_pick_lost red_to_blue red_to_blue_date
dccc_emerging_or_other_tier dccc_emerging_date frontline frontline_date cook_final sabato_final
inside_final rating_source rating_bucket rating_source_used in_competitive_set faction2 dem_won
lean_bin challenger_or_open flag_prog flag_mod
""".split()

# Columns that pandas wrote as floats / ints / booleans in the research build (house files only).
HOUSE_FLOAT = set("dem_votes rep_votes dem_pct rep_pct dem_margin pct_expected_vote alt_dem_margin harris24 trump24 "
                  "pres24_margin hisp_share_acs24 ba_plus_share_acs24 overperf".split())
HOUSE_BOOL = {"contested_ok", "competitive"}
HOUSE_MONEY_FLOAT = set("pres24_margin dem_margin overperf dem_receipts dem_disbursements dem_cash_on_hand dem_indiv_contrib "
                        "dem_cand_self_funding rep_receipts rep_cash_on_hand dccc_coord_dem dccc_contrib_dem ie_pro_a_estab "
                        "estab_total ie_pro_b_prog_core ie_pro_b2_prog_broad ie_pro_c_mod_core ie_pro_c2_mod_broad "
                        "ie_pro_d_crypto ie_pro_d_other ie_pro_total pro_dem_outside_total ie_pro_total_after_oct14 "
                        "ie_pro_a_estab_after_oct14 nrcc_coord_rep ie_anti_clf ie_anti_aipac_udp ie_anti_crypto "
                        "ie_anti_other ie_anti_total anti_dem_outside_total estab_per_voter pro_dem_outside_per_voter "
                        "anti_dem_outside_per_voter dem_receipts_per_voter rep_receipts_per_voter net_outside_per_voter".split())
HOUSE_MONEY_BOOL = {"in_competitive_set"}
