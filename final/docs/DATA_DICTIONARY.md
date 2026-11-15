# Result tables

Tables live in outputs/. Monetary fields are USD. Values are monthly unless marked annual, and proportions use decimal notation. See METHODS.md for model definitions and eligibility rules.

| Directory and file | Row unit and content |
| --- | --- |
| market_inputs/market_combinations.csv | City × occupation × bedroom type. Local median salary, local median asking rent and sample sizes |
| market_inputs/market_combinations_entry_signal.csv | Same structure using entry-signal occupation medians across the Bay Area |
| market_inputs/salary_by_city_occupation.csv | Observed city × occupation pay cells with median, quartiles and usable posting count |
| market_inputs/salary_by_occupation.csv | Full screened and entry-signal regional pay by occupation; also includes the unclassified group |
| market_inputs/salary_levels.csv | Three regional wage quantiles across 18,451 usable postings, for comparison |
| market_inputs/rent_by_city_housing.csv | City × bedroom type median asking rent, quartiles, listing count and distinct signatures used for eligibility |
| equity/ and equity_entry_signal/ → combination_results.csv | Profile × eligible city × occupation. Budget lines, net income, individual rent, sample counts, savings, gap and feasibility |
| equity/ and equity_entry_signal/ → eligibility_log.csv | Evaluated city × occupation. Eligibility and which salary or rent requirement failed |
| equity/ and equity_entry_signal/ → equity_table.csv | Profile summaries with eligible counts, feasible counts, shortfall rates and gap order statistics |
| equity/ and equity_entry_signal/ → factor_effects.csv | Differences versus the no-debt, living-alone, no-support profile |
| equity/ and equity_entry_signal/ → same_job_different_start.csv | A fixed place, occupation and salary; budgets across profiles |
| equity/ and equity_entry_signal/ → sensitivity.csv | Main reference profile under one change at a time in rent, essentials, debt, tax or interest |
| equity/ and equity_entry_signal/ → SUMMARY.md | Readable summaries for the two models |
| analysis/city_opportunity.csv | City-level gross pay thresholds and share of the regional wage points above each threshold; includes both housing sample counts |
| analysis/actionability.csv | Main-model profile-level shortfall estimates and changes in salary, rent or loan payment needed among short cases |
| analysis/occupation_barrier.csv | Occupation × salary model. Barrier estimates in selected profiles and number of eligible cities |
| analysis/college_comparison.csv | Region × four-year institution metric, with income bands when applicable and valid institution counts |
| assumptions.json | Defaults, thresholds and provenance of the debt and childcare benchmarks |
| verification_report.md | Validation of the processed inputs, including pay disclosure and annualization coverage |

The cleaned inputs and their hashes are listed in ../data/processed/MANIFEST.md. The seven generated figures are under visualization/figures/. The optional viewers use src/results.py to find canonical tables.
