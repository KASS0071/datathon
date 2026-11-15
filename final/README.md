# From College to Independence

**Who can afford to start adult life in the San Francisco Bay Area?**
8th Annual Datathon for Social Good

A college degree is often presented as the path to financial independence. Whether a new graduate can actually live on their own also depends on what job they get, where they live, how much student debt they carry and whether family can help. This project measures those barriers with a monthly budget simulation built from three public datasets:

- **46,970** screened Bay Area Indeed job postings, used for advertised pay
- **59,409** Zillow rental listings, used for asking rents
- **6,418** colleges and universities, used for debt, childcare and net-price benchmarks

The project does not predict what happens to individual graduates. It asks: *for a given city, occupation and starting point, does the typical advertised wage cover a basic budget?*

---

## Key findings

**Barrier Index:** the share of modeled city × occupation pairs where take-home pay does not cover rent, loan payments, essentials, childcare and a $250/month savings target. Within each pay model, every profile is scored on the same set of pairs.

| Household scenario (no family support) | Local pay model | Regional entry-signal model |
| --- | ---: | ---: |
| No debt, living alone (1br) | 51.1% | 65.0% |
| No debt, sharing a 2br | 23.7% | 23.8% |
| Median debt ($20,389), living alone | 55.0% | 72.3% |
| High debt ($25,000), living alone | 55.6% | 73.4% |
| Student parent (median debt, 2br, childcare) | 87.7% | 96.1% |
| Eligible pairs per profile | 333 across 53 cities | 812 across 58 cities |

What this means:

1. **Occupation sets the barrier.** With regional entry-signal pay, food service ($41,600) and retail ($43,680) fall short in all 58 cities for someone living alone. Software, data & IT ($121,000) falls short in none.
2. **Housing moves it most.** Sharing a two-bedroom cuts the Barrier Index by more than half. A $500/month family transfer helps less: 51.1% falls to 41.1% in the local model.
3. **Student debt adds a fixed monthly cost.** Median debt means about $230/month in loan payments on a 10-year plan at 6.39%. It raises the local-model barrier from 51.1% to 55.0%.
4. **Student parents face the steepest barrier.** Childcare (about $1,795/month) puts almost every pair out of reach, even with family support (83.8% local, 93.7% regional).
5. **Same job, different start.** A skilled-trades job in San Carlos ($68,318/year) leaves a $1,364/month shortfall for someone with no debt living alone. Sharing turns that into a $68 surplus. For a student parent the gap grows to $4,582.
6. **Break-even salaries.** The gross pay needed to live alone ranges from $53,650 (Vallejo) to $104,428 (Tiburon); San Francisco needs $92,077. The regional median advertised wage is $80,900.

The two pay models use different wage inputs and cover different pairs, so compare profiles within a column, not across columns. Full tables are in [outputs/equity/SUMMARY.md](outputs/equity/SUMMARY.md) and [outputs/equity_entry_signal/SUMMARY.md](outputs/equity_entry_signal/SUMMARY.md).

---

## Quick start

All commands run from this folder (`final/`) with the shared Python 3.11 environment in `../.venv`.

```sh
# 1. Rebuild every result table and figure from data/processed/
../.venv/bin/python -B run_pipeline.py

# 2. Run the unit tests (40 tests, standard-library unittest)
../.venv/bin/python -B -m unittest discover -s tests -t .

# 3. Optional: refresh the Tableau map CSVs
../.venv/bin/python -B visualization/build_tableau_maps.py

# 4. Optional: open the interactive dashboard
../.venv/bin/streamlit run visualization/dashboard/app.py
```

- **Rebuild from raw data:** add `--preprocess` to step 1 to regenerate `data/processed/` from `data/raw/` first.
- **Run only the cleaning step:** `../.venv/bin/python -B src/preprocess/clean_data.py`.
- **Notebook:** open [visualization/visualizations.ipynb](visualization/visualizations.ipynb) in VS Code and select the `.venv` interpreter.
- **Dependencies:** pinned in [requirements.txt](requirements.txt): pandas, numpy, matplotlib, openpyxl, plus streamlit and plotly for the dashboard.
- **Portable copy:** put the raw files in `data/raw/` or set `DATATHON_RAW_DIR`. `DATATHON_DATA_DIR` changes where `processed/` is read from.

The pipeline is deterministic: running it twice produces byte-identical outputs.

---

## How it works

```
data/raw ─1─▶ data/processed ─2─▶ outputs/market_inputs ─3,4─▶ outputs/equity*, outputs/analysis ─5─▶ visualization/
         clean               salary & rent              budgets & scenarios                       charts & dashboard
```

| Step | Code | What it does | Output |
| --- | --- | --- | --- |
| 1. Clean and verify | [src/preprocess/](src/preprocess/) | Joins college files by Unit ID, parses Indeed pay text into annual amounts, normalizes city names, keeps Zillow rental listings and removes duplicates. Then checks the result against the data contract. | [data/processed/](data/processed/), [verification report](outputs/verification_report.md) |
| 2. Market inputs | [src/market/](src/market/) | Classifies job titles into 15 occupation groups (plus "other") and screens out senior, part-time-only and reposted ads. Computes median pay by city × occupation and median rent by city × bedroom count. | [outputs/market_inputs/](outputs/market_inputs/) |
| 3. Budget engine | [src/budget/calculate_budget.py](src/budget/calculate_budget.py) | Estimates 2025 federal + California taxes, loan payments, the monthly gap and break-even salary. The dashboard uses the same code. | Used by step 4 |
| 4. Scenarios | [src/analysis/](src/analysis/) | Runs 14 household profiles on every eligible pair in both pay models. Adds sensitivity tests, city thresholds, occupation results and college comparisons. | [outputs/equity/](outputs/equity/), [outputs/equity_entry_signal/](outputs/equity_entry_signal/), [outputs/analysis/](outputs/analysis/) |
| 5. Visualization | [visualization/](visualization/) | Static figures, notebook, Tableau map data and Streamlit dashboard. | [visualization/figures/](visualization/figures/), [visualization/tableau/](visualization/tableau/) |

[run_pipeline.py](run_pipeline.py) runs the steps in order, from input verification through the figures, and records the model settings in [outputs/assumptions.json](outputs/assumptions.json). All parameters are in [src/config.py](src/config.py).

### Core formulas

| Metric | Definition |
| --- | --- |
| Take-home pay | Gross pay minus estimated federal + CA income tax, FICA and CA SDI (2025, single filer, standard deduction, no credits) |
| Personal rent | City median asking rent for the bedroom type, divided by the number of people sharing |
| Loan payment | Debt amortized over 10 years at 6.39% (2025-26 federal undergraduate rate) |
| **Feasibility gap** | rent + loan + essentials + childcare + savings target − (take-home pay + family support). **Positive = shortfall** |
| **Barrier Index** | 1 − feasible pairs ÷ eligible pairs, using the same pairs for every profile |
| Break-even salary | Gross annual pay that makes the gap exactly zero, found by bisection |
| Rent burden | 12 × personal rent ÷ gross pay, compared with the 30% HUD guideline |

### Household profiles

Each profile combines debt (none / median / high), housing (alone in a 1br / sharing a 2br) and family support ($0 / $500 a month), giving 12 profiles. Two student-parent profiles are added (median debt, a 2br, childcare, with and without support), for 14 in total. Profiles with $0 support form the **independence** index; those with $500 form the **assisted** index.

### Two pay models

| | Local pay model (main) | Regional entry-signal model |
| --- | --- | --- |
| Wage for a pair | Median of non-senior postings in that city and occupation | Bay-Area-wide median of postings with an entry-level signal (e.g. "junior", "new grad") for that occupation |
| Coverage rule | At least 10 postings in the city × occupation cell | At least 10 postings in the occupation, region-wide |
| Eligible pairs | 333 across 53 cities | 812 across 58 cities |

In both models a city needs at least 20 distinct rental listings for both 1br and 2br. Excluded pairs and the reasons are listed in each `eligibility_log.csv`.

---

## Project layout

```
final/
├── README.md                 this file
├── run_pipeline.py           one command to rebuild every output
├── requirements.txt          pinned package versions
├── data/
│   ├── raw/                  links to the shared raw files (Indeed, Zillow, college Excel files)
│   └── processed/            cleaned snapshot + MANIFEST.md (row counts and SHA-256)
├── src/
│   ├── config.py             every assumption and threshold in one place
│   ├── results.py            locates each result table for the viewers
│   ├── preprocess/           step 1: clean_data.py, verify_data.py
│   ├── market/               step 2: classify_occupations.py, build_market_inputs.py
│   ├── budget/               step 3: calculate_budget.py
│   └── analysis/             step 4: equity_analysis.py, run_equity.py, summarize_results.py
├── outputs/                  result tables (see docs/DATA_DICTIONARY.md)
│   ├── market_inputs/        salary and rent inputs for each pair
│   ├── equity/               local pay model results
│   ├── equity_entry_signal/  regional entry-signal model results
│   ├── analysis/             city thresholds, occupations, actionability, colleges
│   ├── assumptions.json      model configuration used for this run
│   └── verification_report.md
├── visualization/            step 5: every chart in one place
│   ├── make_figures.py       → figures/ (7 PNGs, run by the pipeline)
│   ├── visualizations.ipynb  the same 7 charts, interactive
│   ├── build_tableau_maps.py → tableau/ (2 map CSVs)
│   └── dashboard/app.py      Streamlit viewer and budget simulator
├── docs/                     methods, assumptions, data notes, guides
└── tests/                    unit tests + fixtures
```

### Figures

| File | Shows |
| --- | --- |
| [01_barrier_index_by_profile.png](visualization/figures/01_barrier_index_by_profile.png) | Barrier Index for each no-support profile |
| [02_break_even_salary_by_city.png](visualization/figures/02_break_even_salary_by_city.png) | Salary needed to live alone vs. shared in 20 cities, against the advertised pay range |
| [03_same_job_different_start.png](visualization/figures/03_same_job_different_start.png) | One job, one city, five starting points: where the money goes |
| [04_college_net_price_by_income.png](visualization/figures/04_college_net_price_by_income.png) | Four-year college net price by family income: Bay Area, rest of California, other states |
| [05_barrier_by_occupation.png](visualization/figures/05_barrier_by_occupation.png) | Shortfall rate by occupation, living alone vs. sharing |
| [06_rent_by_city.png](visualization/figures/06_rent_by_city.png) | One-bedroom asking rent: median and middle 50% by city |
| [07_gap_heatmap_city_occupation.png](visualization/figures/07_gap_heatmap_city_occupation.png) | Monthly gap for each city × occupation |

The dashboard has four pages: market overview, affordability heatmap, simulator and equity. The simulator lets a user pick a city, housing and occupation, then adjust salary, rent, roommates, debt, interest, taxes, essentials, savings, support and childcare.

---

## Assumptions

| Parameter | Value | Source / status |
| --- | --- | --- |
| Essentials (food, transport, health, phone…) | $1,500/month | Project scenario parameter; sensitivity ±20% |
| Savings target | $250/month | Project scenario parameter |
| Family support (assisted scenario) | $500/month | Project scenario parameter |
| Median / high student debt | $20,389 / $25,000 | Median and 75th percentile of median completer debt across 33 Bay Area four-year institutions (College Results 2021) |
| Childcare (student parent) | $1,795/month | Adjusted center-based childcare cost, Affordability Gap AY2022-23 |
| Loan terms | 10 years, 6.39% | Federal standard plan; 2025-26 Direct Loan rate |
| Taxes | Progressive estimate | Approximate 2025 federal + CA, single filer |

The three amounts marked "project scenario parameter" are project choices, not estimates from a source. They can be changed in [src/config.py](src/config.py) or in the dashboard. [docs/ASSUMPTIONS.md](docs/ASSUMPTIONS.md) lists the reference methods (MIT Living Wage, CFPB). [outputs/equity/sensitivity.csv](outputs/equity/sensitivity.csv) shows how results change with rent, essentials, debt, tax and interest.

---

## Data

| Source | Raw file | Used for |
| --- | --- | --- |
| Indeed job listings | `indeed_job_listings.csv` (140,816 rows) | Advertised pay by city and occupation |
| Zillow rental listings | `zillow_part2.csv`, `zillow_part3.csv` | Asking rent by city and bedroom count |
| College Results View 2021 | `College Results View 2021 Data Dump for Export.xlsx` | Completer debt, graduation outcomes |
| Affordability Gap AY2022-23 | `Affordability Gap Data AY2022-23 2.17.25.xlsx` | Net price by income, childcare cost |

Row counts and checksums for every processed file are in [data/processed/MANIFEST.md](data/processed/MANIFEST.md). Screening counts are in `data/processed/quality_report.json`. [docs/DATA_NOTES.md](docs/DATA_NOTES.md) explains coverage and caveats.

## Limitations

- **The datasets are not linked.** The project cannot follow one person from college to a job and an apartment. Results are scenario estimates for city × occupation pairs, not shares of real graduates.
- **Advertised, not actual.** Wages are posted pay and rents are asking prices, not what people actually earn or pay.
- **Equal weights.** Each eligible pair counts once, regardless of how many jobs or people it represents.
- **Classifier error.** Occupations are assigned from job titles; a hand-checked sample of 100 was 88% correct. Entry-level signals are keyword heuristics.
- **Simplified budget.** Single filer, no tax credits, one essentials amount for every city. Debt is an institution-level benchmark, not individual debt.
- **Snapshot in time.** Listings reflect the extract dates of the source files.

---

## Documentation

| Document | Contents |
| --- | --- |
| [docs/problem_statement.md](docs/problem_statement.md) | Research question, goals and social-good framing |
| [docs/METHODS.md](docs/METHODS.md) | Methods and reproducibility, step by step |
| [docs/ASSUMPTIONS.md](docs/ASSUMPTIONS.md) | Budget parameters and references |
| [docs/DATA_NOTES.md](docs/DATA_NOTES.md) | Data provenance, coverage and caveats |
| [docs/DATA_CONTRACT.md](docs/DATA_CONTRACT.md) | Columns the analysis expects from its inputs |
| [docs/DATA_DICTIONARY.md](docs/DATA_DICTIONARY.md) | Every result table and what one row means |
| [docs/guide/](docs/guide/) | Full guide to data, formulas, tables and figures ( .md and .pdf) |
| [docs/PROJECT_REPORT_ZH.pdf](docs/PROJECT_REPORT_ZH.pdf) | Project report (Chinese) |
