"""Locate the canonical CSV for each result table, without copied exports."""

from pathlib import Path

TABLE_FILES = {
    "equity_table.csv": "equity/equity_table.csv",
    "factor_effects.csv": "equity/factor_effects.csv",
    "same_job_different_start.csv": "equity/same_job_different_start.csv",
    "sensitivity.csv": "equity/sensitivity.csv",
    "combination_results.csv": "equity/combination_results.csv",
    "eligibility_log.csv": "equity/eligibility_log.csv",
    "city_opportunity.csv": "analysis/city_opportunity.csv",
    "actionability.csv": "analysis/actionability.csv",
    "occupation_barrier.csv": "analysis/occupation_barrier.csv",
    "college_comparison.csv": "analysis/college_comparison.csv",
    "salary_levels.csv": "market_inputs/salary_levels.csv",
    "salary_by_occupation.csv": "market_inputs/salary_by_occupation.csv",
    "salary_by_city_occupation.csv": "market_inputs/salary_by_city_occupation.csv",
    "equity_table_entry_signal.csv": "equity_entry_signal/equity_table.csv",
    "factor_effects_entry_signal.csv": "equity_entry_signal/factor_effects.csv",
    "combination_results_entry_signal.csv": "equity_entry_signal/combination_results.csv",
    "rent_by_city_housing.csv": "market_inputs/rent_by_city_housing.csv",
}



def table_path(outputs: Path, filename: str) -> Path:
    return outputs / TABLE_FILES[filename]
