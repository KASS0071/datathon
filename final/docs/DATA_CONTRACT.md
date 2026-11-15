# Data contract: processed files → equity analysis

This is what `src/analysis/equity_analysis.py` and `src/preprocess/verify_data.py` expect from
`data/processed/`. Reasonable alternative column names are accepted (see the alias lists in
`CANONICAL_COLUMNS` in `src/analysis/equity_analysis.py`), so you don't have to rename anything
that is already close.

## `market_combinations.csv` (required)

**One row per city × occupation × housing_type.** Insufficient rows stay in the file, unfilled.

| Column | Type | Meaning |
|---|---|---|
| `city` | str | Normalised Bay Area city name (same spelling in jobs and housing) |
| `occupation` | str | Occupation category |
| `housing_type` | str | `studio`, `1br`, `2br`, `3br` (variants like "1 Bedroom" / "2BR" are normalised) |
| `median_annual_salary` | float | Median **annualised** advertised salary of entry-level postings for city × occupation. Identical on every housing row of the pair. |
| `n_valid_salary` | int | Number of independent postings with a valid salary behind that median |
| `median_monthly_rent` | float | Median **monthly** asking rent (listing `price`, not `rentZestimate`) for city × housing_type. Identical for every occupation in that city × housing_type. |
| `n_valid_rent` | int | Number of valid rental listings behind that median |
| `sufficient_data` *(optional)* | bool | Upstream flag. The analysis recomputes sufficiency **per dimension** and only uses this flag as a cross-check |

Recommended extra columns (not required): `n_postings`, `salary_q1`, `salary_q3`, `rent_q1`, `rent_q3`, `pct_degree_required`.

Thresholds (`src/config.py`): ≥ 10 valid salaries and ≥ 20 valid rents.

**Eligibility for the equity analysis:** a city × occupation pair is used only if its salary
passes **and** both `1br` (living alone) and `2br` (shared, student parent) rents pass. Every
profile then runs on exactly that set of pairs, so all profiles share one denominator.

## College benchmarks (optional; placeholders are used if absent)

Read from `college_equity_summary.csv`, or else `college_clean.csv`, one row per institution:

| Column (matched by pattern) | Source column in raw data | Used for |
|---|---|---|
| `…median debt … completers…` | College Results 2021: `Median Debt of Completers` | median debt = median of Bay Area institutional medians; high debt = their 75th percentile |
| a Bay Area flag (`is_bay_area`, `bay_area`, …) with True/False | IPEDS county ∈ the 9 Bay Area counties | restricts debt and childcare to Bay Area schools |
| `adjusted monthly center-based child care cost` | Affordability Gap AY2022-23 | student-parent childcare cost (median) |

These are **institution-level benchmarks**, not individual debt percentiles. They come from
older cohorts than the current job postings, so don't read them causally.

## Other files `verify_data.py` checks if present

`jobs_clean.csv`, `housing_clean.csv`, `job_market_summary.csv` (keys `city, occupation`),
`housing_market_summary.csv` (keys `city, housing_type`). It checks: unique keys, plausible
salary/rent ranges, unconverted hourly pay, FOR_RENT-only listings, rentZestimate kept separate,
flags agreeing with thresholds, and medians in `market_combinations.csv` that trace back to the summaries.
