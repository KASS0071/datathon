# From College to Independence | A guide to the data, formulas, forms, and figures

Bay Area Datathon · English guide for the November 15, 2026 submission layout

Use this guide to trace a number back to its source, rebuild the results, or choose a chart for the presentation. The pipeline code lives under `src/`, analysis tables under `outputs/`, and the figure scripts, PNGs, notebook, Tableau inputs, and optional dashboard under `visualization/`. **Break-even salary** is the minimum gross annual pay needed to meet a budget given a city's rent and the household's expenses. **Feasibility Gap** starts with a wage and calculates the resulting monthly shortfall or surplus. **Barrier Index** is the share of modeled combinations with a shortfall. State the denominator whenever you present that share.

## 1. How the data enters the model

The project asks whether recent graduates in the San Francisco Bay Area could cover monthly expenses and meet a savings goal under different wages, rents, student debt levels, and household arrangements. It combines pay and rent by city, occupation, and housing type, then uses education data to set common debt and childcare benchmarks. Wages and rents come from advertisements. The sources contain separate records and cannot follow a person from college through employment and housing. The model evaluates combinations of conditions.

| Step | Program | Method, rationale, and output |
|---|---|---|
| 1. Clean and verify | `src/preprocess/clean_data.py`, `verify_data.py` | Standardize institution IDs, locations, and monetary units. Preserve original salary text, the selected rent field, and audit information in `data/processed/`. |
| 2. Build market inputs | `src/market/build_market_inputs.py`, `classify_occupations.py` | Classify jobs, annualize usable pay, and summarize salaries and rents. Medians reduce the influence of individual extremes. P25, P75, and sample counts show spread and coverage. |
| 3. Calculate budgets | `src/budget/calculate_budget.py` | Apply common tax, rent-sharing, loan, and savings rules to calculate the monthly gap and minimum annual pay. Sharing one implementation keeps scenarios comparable. |
| 4. Simulate and summarize | `src/analysis/run_equity.py`, `equity_analysis.py`, `summarize_results.py` | Run 14 profiles for each eligible city–occupation pair. Save individual budgets, eligibility reasons, overall rates, sensitivity tests, and college comparisons. |
| 5. Present | `visualization/` (scripts, notebook, dashboard, figures, Tableau CSVs) | `make_figures.py` produces seven PNGs, the VS Code notebook has seven chart sections, and `build_tableau_maps.py` exports two map CSVs. The dashboard reads the same analysis tables. |

[Pipeline entry point](../../run_pipeline.py) · [Research question](../../docs/problem_statement.md) · [Methods](../../docs/METHODS.md) · [Current repository layout](../../README.md)

## 2. Raw datasets and fields read by the pipeline

The shared `data/raw/` contains **7 files**. Links in `final/data/raw/` point to them. **Five files contributed data to the full run.** The Zillow sample was read and contributed zero additional records. The Indeed sample is used in test mode.

| Raw file | Coverage and use | Effect on results |
|---|---|---|
| `indeed_job_listings.csv` | Of 140,816 records read, 46,970 matched Bay Area cities and 1,344 showed entry-level signals. | Supplies advertised pay and eligible salary counts for the budget gap, occupation comparisons, and regional pay shares above city salary thresholds. |
| `Indeed job listings information_sample.csv` | Replaces the full Indeed file with `--sample-only`. | Tests job screening, salary parsing, and output format quickly. The full file supplies pay for the main analysis. |
| `zillow_part2.csv` | 78,424 rows read and 39,565 retained. | With Part 3, supplies rents by city and bedroom count, plus coordinates for city markers. |
| `zillow_part3.csv` | 39,867 rows read and 19,844 retained. Both parts contribute 59,409 listings. | Qualifying listings from both parts form the pooled city and housing samples used to calculate median rent. |
| `Zillow properties listing information_sample.csv` | The full run read 1,000 rows after Parts 2 and 3. Of those, 978 failed the California rental screen, 18 lacked a Bay Area county match, and 4 had duplicate IDs. The sample is the only Zillow file read in sample mode. | Provides a small test input. The full run added zero listings from it, so rents and coordinates in the main results come from Parts 2 and 3. |
| `Affordability Gap Data AY2022-23 2.17.25.xlsx` | Of 21,299 records read on the first worksheet, 20,112 have a usable family-income band. | Supplies net price and education affordability gaps by income band. The difference between the student-parent and regular gaps supplies the center-based childcare estimate. |
| `College Results View 2021 Data Dump for Export.xlsx` | First worksheet, 6,289 institutional records. | Supplies the four-year institution filter, completer debt, graduation rates, and prices for low-income students. It affects debt and student-parent scenarios, the break-even threshold with debt, and college comparisons. |

The code also checks for `Zillow_part1.csv`. The file is absent from the current raw directory and the log records `file not found`. The education workbooks combine to **6,418 institutions**: 6,127 in both, 129 only in Affordability Gap, and 162 only in College Results. The combined data identifies 124 Bay Area institutions. Each metric uses the institutions that report the relevant value. [Raw inputs](../../data/raw) · [Preprocessing counts](../../data/processed/quality_report.json)

### Indeed | 11 fields

| Raw field | How and why it is used |
|---|---|
| `jobid` | Exclude rows without an ID and remove duplicate IDs so each posting appears once. |
| `country`, `region` | Require the United States and California. |
| `location` | Assign a Bay Area postal city and county. The 781 postings with only a regional label are counted separately because they lack a usable city for local wage comparisons. |
| `job_title` | Classify the occupation, identify entry-level or senior signals, and help identify likely reposts. |
| `description_text` | Detect entry-level wording and years of experience. A senior title or a three-plus-years signal takes precedence. Some preferred qualifications can trigger this rule. |
| `salary_formatted` | Extract amounts and pay periods from dollar-denominated text. Preserve the original wording for review. The parser recognizes some Spanish pay formats. |
| `job_type` | Exclude postings marked part-time with no full-time label from the wage model, where hourly wages are annualized using full-time hours. |
| `company_name` | Combine with title, standardized city, and original salary text to flag likely reposts. |
| `date_posted_parsed`, `is_expired` | Retain dates and expiration flags for auditing. The wage model includes historical advertisements and applies no additional date or expiration filter. |

Of the 46,970 retained postings, 39,904 contain pay text, 39,816 parse successfully, and 39,625 pass the preprocessing annualization checks. After further seniority, employment type, pay, and repost screening, **18,451** postings contribute to the regional pay quartiles. Entry-signal candidates, parsed salaries, and model wage records count different stages. [Indeed preprocessing](../../src/preprocess/clean_data.py) · [Market wage calculation](../../src/market/build_market_inputs.py)

### Zillow | 16 fields

| Raw field | How and why it is used |
|---|---|
| `zpid` | Deduplicate across raw files. Use the source filename and listing ID to match a retained rental to its original coordinates. |
| `state`, `homeStatus`, `isRentalListingOffMarket`, `currency` | Require California and a rental listing, exclude explicit off-market flags, and accept USD or a blank currency value. This keeps sales and rental prices separate. |
| `countyFIPS`, `county`, `city` | Identify the Bay Area using county code or name, with a city lookup where needed. The market stage groups by postal city and uses that city's most common county label. |
| `bedrooms` | Group rents by housing type for solo living, sharing, and student-parent scenarios. |
| `homeType` | Exclude listings labeled as rooms from the market analysis and help identify possible duplicate units. |
| `zipcode`, `bathrooms` | Combine with bedroom count, home type, and rent as a listing signature. The count helps screen out thin rental samples. |
| `base_rent`, `price` | Use a positive `base_rent` when available, then fall back to a positive `price`. The fields agree on all 53,195 retained records where both are present. The market stage uses rents of $500–$15,000 per month. |
| `latitude`, `longitude` | Rebuilding the maps takes separate city-level medians of the matched coordinates. The code restricts coordinates to a regional bounding box, requires 5 usable locations per city, and rounds to 4 decimal places. |

`n_valid_rent` counts distinct listing signatures. `n_listings` counts listings after filtering. Median rents and quartiles use the filtered listings. The signature count applies to eligibility. Two units can have the same signature, so this count is a conservative proxy for sample size. [Rental preprocessing](../../src/preprocess/clean_data.py) · [Market rent calculation](../../src/market/build_market_inputs.py) · [Coordinate export](../../visualization/build_tableau_maps.py)

### Affordability Gap | 18 fields

| Raw field | How and why it is used |
|---|---|
| `Unit ID`, `Student Family Earnings Ceiling` | Identify each institution and income band. Preserve the different prices and costs faced by households at different income levels within a school. |
| `Institution Name`, `City`, `State Abbreviation`, `County Name`, `County Code` | Supply the institution name and location for identification and Bay Area classification. |
| `Sector Name`, `Highest Degree Offered Name`, `MSI Type` | Retain institutional characteristics. The four-year filter uses `Institution Type` from the other workbook. |
| `Cost of Attendance: In State, On Campus`, `Annual Income Estimate`, `State Minimum Wage`, `Weekly Hours to Close Gap` | Retain in-state residential cost, source income estimates, minimum wage, and weekly hours needed to close the education gap so readers can understand the source calculation. |
| `Net Price` | Supplies academic-year net prices for income-band comparisons. |
| `Affordability Gap (net price minus income earned working 10 hrs at min wage)` | Supplies the education gap comparison and the base amount for estimating childcare costs. |
| `Student Parent Affordability Gap: Center-Based Care` | Subtract the regular annual affordability gap and divide by 12 to estimate monthly center-based childcare. |
| `Student Parent Affordability Gap: Home-Based Care` | Preserve the home-based care gap in the early education benchmarks. The current student-parent budget uses center-based care. |

The **college affordability gap** describes the cost of studying. The **monthly feasibility gap** describes living costs after graduation. The childcare estimate links the two stages. [Education field mapping](../../src/preprocess/clean_data.py) · [Childcare calculation](../../src/analysis/equity_analysis.py)

### College Results | 14 fields

| Raw field | How and why it is used |
|---|---|
| `UNIQUE_IDENTIFICATION_NUMBER_OF_THE_INSTITUTION` | Standardize as `unit_id` and join to the other workbook. An ID avoids errors from institutions with similar names. |
| `Institution Name`, `City of Institution`, `State of Institution` | Retain the 2021 institution name and location. Use these values when the other workbook lacks the corresponding information. |
| `Institution Type` | Identify four-year institutions for graduate debt benchmarks and college comparisons. |
| `Number of Bachelor Degrees Grand Total`, `Bachelor's Degree Graduation Rate Within 4 Years - Total` | Retain degree counts and four-year graduation rates for reference and auditing. |
| `Bachelor's Degree Graduation Rate Bachelor Degree Within 6 Years - Total` | Supplies the six-year graduation rate comparison across regions. |
| `Average Net Price After Grants, 2020-21` | Retain the earlier overall net price for traceability. |
| `Average Net Price for Low-Income Students, 2020-21` | Supplies the low-income net price comparison among four-year institutions. |
| `Median Debt of Completers` | Take the median and P75 of the reported institution-level medians from 33 Bay Area four-year institutions. This produces model debt levels of $20,389 and $25,000. |
| `Median Debt for Dependent Students`, `Median Debt for Independent Students` | Retain the two debt figures for auditing. The main budget benchmarks use completer debt. |
| `Median Earnings of Students Working and Not Enrolled 10 Years After Entry` | Retain in the cleaned data. The final comparison excludes this field because it contains only three distinct values. |

[Field mapping and merge](../../src/preprocess/clean_data.py) · [Debt benchmark](../../src/analysis/equity_analysis.py) · [Data notes](../../docs/DATA_NOTES.md)

## 3. Formulas, parameters, and rationale

### Making salary and rent estimates comparable

- Use the midpoint of a salary range or the single available bound. Each advertisement then contributes one wage estimate. Annualize hourly pay by 2,080, weekly pay by 52, monthly pay by 12, and annual pay by 1. Keep unsupported pay periods such as daily pay in the audit data without assigning them a model wage. An annualized hourly wage assumes a standardized full-time year.
- Allow annual salary values from **$15,000 to $1,000,000**. Treat hourly amounts above **$500** as suspect. The broad annual range retains legitimate high salaries. Tightening it can remove valid advertisements, while widening it can admit more unit errors.
- Require at least **10 usable salary records** and **20 distinct listing signatures each for one- and two-bedroom units**. Requiring both housing types lets the model compare arrangements on the same city–occupation pairs.
- **Local pay** uses the median screened advertised wage by city and occupation, with **333 pairs per profile across 53 cities**. **Regional entry-signal pay** uses the Bay Area median for each occupation's postings with an entry-level signal, with **812 pairs per profile across 58 cities and 14 occupations**. Holding that wage constant across cities lets differences in rent drive the city comparison. The two models differ in coverage as well as their wage definitions.

### Monthly budget formulas

| Measure | Formula or rule | Use |
|---|---|---|
| Monthly gross income | Gross annual salary ÷ 12. | Puts wage and expenses on the same time scale. |
| Monthly take-home income | Monthly gross income × (1 − effective tax rate). | Estimates cash available after modeled taxes. |
| Personal rent | Monthly rent for the whole unit ÷ (roommates + 1). | Solo renters and student parents pay the whole rent in their respective baseline arrangements. Two people split a two-bedroom unit in the shared scenario. |
| Student loan payment | Principal × monthly rate ÷ [1 − (1 + monthly rate) raised to the negative number of payments]. At zero interest, divide principal by the number of months. | Converts principal into a fixed monthly expense. |
| Monthly balance before savings | Take-home pay + support − rent − loan payment − essentials − childcare. | Shows available cash after modeled monthly expenses, before setting aside savings. |
| Monthly Feasibility Gap | Rent + loan payment + essentials + childcare + savings goal − take-home pay − support. | **Positive means shortfall. Negative means money left after meeting the savings goal. Zero defines the boundary.** `feasible` uses the selected support level. `feasible_independent` uses zero support. |
| Break-even salary | Lowest gross annual salary with a monthly gap of zero or less. The progressive model uses bisection. The flat-tax version divides required annual net income by the after-tax share. | Gives the required gross pay for a city and household arrangement. |
| Rent burden | Annual personal rent ÷ gross annual income. The separate rent-burden threshold is at most 30%. Its solo salary threshold is monthly one-bedroom rent × 12 ÷ 0.30. | Measures housing cost relative to gross pay. The full feasibility measure also includes taxes, other expenses, and savings. |
| Barrier Index | Modeled combinations with a positive gap ÷ eligible combinations. Feasibility rate = 1 − Barrier Index. | Measures how often a shortfall occurs in the model. Pairs have equal weight. An occupation-specific calculation uses that occupation's eligible cities. |
| Changes needed to close a gap | Required net increase = positive gap. Approximate annual raise = positive gap × 12 ÷ (1 − current effective tax rate). Required rent cut = positive gap ÷ personal rent. Removing a loan payment closes a gap if its payment covers the gap. | Shows the scale of change required. The break-even calculation is the direct way to solve for minimum salary under the selected tax model. |

[Budget implementation](../../src/budget/calculate_budget.py) · [Summary calculations](../../src/analysis/summarize_results.py)

### Defaults, sources, and effects

| Parameter | Current setting | Rationale and effect |
|---|---|---|
| Housing | Solo: whole one-bedroom unit. Shared: half of a two-bedroom unit. Student parent: whole two-bedroom unit. | Defines comparable housing choices. Actual unit size, roommates, and rent division can vary. |
| Essentials | **$1,500/month**, an editable project assumption. | Provides a common baseline. Every $100 increase raises the monthly gap by $100. |
| Savings target | **$250/month**, an editable project assumption. | Includes savings in the feasibility test. Setting the target to zero reduces the monthly gap by $250 and affects the after-savings measure. |
| Family support | **$0 or $500/month**, an editable project assumption. | Adds a fixed transfer for comparison. $500 of support reduces the assisted gap by $500. Independence uses zero support. |
| Student debt | **$0, $20,389, or $25,000**. The latter two come from the median and P75 of institutional debt medians. | Distinguishes no debt from typical and higher institutional benchmarks. Individual debt percentiles require borrower records. |
| Loan term and interest | **10 years at 6.39%**. Uses the 2025–26 federal undergraduate Direct Loan reference rate and a fixed payment schedule. | Higher interest or principal raises payments. A longer term typically reduces the monthly payment and increases total interest. The model uses a single repayment structure. |
| Childcare | **$1,795.42/month**, a statewide center-based childcare estimate. | Used for the student-parent profile, which also includes median debt and an unshared two-bedroom unit. |
| Taxes | Approximate 2025 single filer: federal and California income tax, Social Security, Medicare, and CA SDI, with standard deductions and zero credits. The code uses 2024 brackets for California. | Makes wage comparisons consistent. Actual take-home pay depends on filing status, credits, and deductions. The project applies the same tax treatment to student parents. |
| Fallback settings | **22%** default in flat-tax mode, with **$20,000 and $27,000** fallback debt and **$1,800/month** fallback childcare. | The current project results use progressive tax and the derived education benchmarks. The fallback settings allow a run without usable benchmarks, or with a user-selected flat rate. |

There are **14 profiles**: 3 debt levels × 2 housing arrangements × 2 support levels, plus student-parent scenarios with and without support. Sensitivity tests hold the reference profile at median debt, solo living, and no support. They change one parameter at a time: rent at **0.9 / 1 / 1.1 / 1.2** times baseline, essentials at **0.8 / 1 / 1.2**, debt at **0 / 0.5 / 1 / 1.5 / 2**, and interest at **0% / 4% / 6.39% / 8%**. Flat-tax checks use **17% / 22% / 27% / 30%**. This design shows which assumptions drive changes. [Configuration](../../src/config.py) · [Recorded run settings](../../outputs/assumptions.json) · [Assumption sources and scope](../../docs/ASSUMPTIONS.md)

## 4. All 32 CSVs and supporting files

Row counts exclude headers. The pipeline generates cleaned data, market inputs, simulation results, and then summaries and map exports. Money is in US dollars. Each monetary field indicates a monthly or annual amount.

### Eight cleaned input tables

| File | Rows | What one row represents and how to use it |
|---|---:|---|
| `jobs_bay_area.csv` | 46,970 | One cleaned job advertisement. Audit the original pay text, annualization, city, and experience signal. |
| `jobs_entry_candidates.csv` | 1,344 | One job posting with an entry-level signal. Review the coverage of the rules. Wage estimates apply further pay, experience, and repost screening. |
| `rentals_bay_area.csv` | 59,409 | One cleaned rental listing. Used to model rents, audit the selected rent field, and find coordinates by listing ID. |
| `rent_by_city_bedrooms.csv` | 676 | One county, postal city, and bedroom count. Shows the number of listings and median rent as a preprocessing check. |
| `colleges.csv` | 6,418 | One institution after joining the workbooks. Used for education benchmarks, debt principal, and the four-year filter. |
| `colleges_bay_area.csv` | 124 | One institution identified as Bay Area. Helps audit geographic coverage. |
| `college_affordability_by_income.csv` | 20,112 | One institution and family-income band. Supplies the education net-price chart and childcare estimate. |
| `college_benchmarks.csv` | 44 | One region and metric, with income bands where applicable. An early education summary for tracking institution counts and medians. |

[Cleaned data](../../data/processed) · [Row counts and checksums](../../data/processed/MANIFEST.md)

### Six market input tables

| File | Rows | What one row represents and how to use it |
|---|---:|---|
| `salary_by_city_occupation.csv` | 1,156 | One city and occupation, with a usable pay count, median, P25, and P75. Used for local wages and coverage checks. |
| `salary_by_occupation.csv` | 16 | One occupational group with regional pay summaries for all screened postings and the entry-signal subset. Includes an unclassified group for auditing. Used for the regional model, chart ordering, and simulator defaults. |
| `salary_levels.csv` | 3 | Regional wage P25, P50, and P75 from 18,451 postings are $52,700, $80,900, and $146,500. These provide a wage reference and support the fallback pay-level mode. |
| `rent_by_city_housing.csv` | 437 | One city and housing type, with filtered listing count, distinct signature count, and rent distribution. Used for budgets and rent charts. |
| `market_combinations.csv` | 4,312 | One city, occupation, and housing type. Contains local wages, local rent, sample sizes, and a data sufficiency flag. Both housing types need adequate coverage for the pair to enter the simulation. |
| `market_combinations_entry_signal.csv` | 6,555 | Same row structure, with one Bay Area entry-signal median per occupation in place of local wages. |

[Market input tables](../../outputs/market_inputs)

### Twelve simulation results tables

Both `outputs/equity/` and `outputs/equity_entry_signal/` contain the following six tables.

| File | Local / regional rows | What one row represents and how to use it |
|---|---:|---|
| `combination_results.csv` | 4,662 / 11,368 | One profile, city, and occupation. Stores salary, effective tax rate, rent, debt payment, support, childcare, savings, gap, and feasibility flags. Feeds the heatmap and occupation map. |
| `eligibility_log.csv` | 1,140 / 2,190 | One evaluated city–occupation pair with its eligibility flag and exclusion reason. Explains absent map markers and blank heatmap cells. |
| `equity_table.csv` | 14 / 14 | One profile with eligible and feasible counts, Barrier Index, gap median and quartiles, monthly balance, and rent burden. |
| `factor_effects.csv` | 5 / 5 | One change from the no-debt, solo, no-support baseline. Measures changes in the shortfall rate and median gap. The student-parent profile changes three conditions together. |
| `same_job_different_start.csv` | 14 / 14 | One household profile applied to a fixed city, occupation, and wage. Shows how different starting conditions change outcomes at the same pay. |
| `sensitivity.csv` | 20 / 20 | One parameter test for the solo profile with median debt and no support. Measures sensitivity to taxes, rent, essentials, debt, or interest. |

[Local-pay results](../../outputs/equity) · [Regional entry-signal results](../../outputs/equity_entry_signal)

### Six analysis and map tables

| File | Rows | What one row represents and how to use it |
|---|---:|---|
| `city_opportunity.csv` | 58 | One city with rents, thresholds for living alone, sharing, and living alone with median debt, plus a 30% rent-burden threshold and shares of wages above each line. Wage shares compare every city's threshold against the same regional wage pool. |
| `actionability.csv` | 14 | One local-pay profile. Among the combinations with a shortfall, estimates the typical gap, the wage increase or rent cut needed, and the share of gaps eliminated by removing the loan payment. |
| `occupation_barrier.csv` | 29 | One wage definition and occupation, with eligible city count, wage benchmark, and shortfall rates and median gaps for four profiles. Used for occupation comparisons. |
| `college_comparison.csv` | 39 | One region and four-year institution metric, by income band where applicable. Reports an unweighted institutional median and institution count. The regions are the Bay Area, the rest of California, and other US states. |
| `bay_area_break_even_map.csv` | 58 | One city with solo and shared salary thresholds, the solo threshold with median debt, rents, sample sizes, coordinates, and the salary difference between solo and shared housing. |
| `bay_area_occupation_map.csv` | 16,030 | One wage definition, profile, city, and occupation. Combines the 4,662 and 11,368 simulation rows and adds city coordinates. |

[Analysis tables](../../outputs/analysis) · [Tableau CSVs](../../visualization/tableau) · [Results dictionary](../../docs/DATA_DICTIONARY.md)

The supporting files serve different purposes. `MANIFEST.md` records hashes and row counts. `quality_report.json` records filter counts. `verification_report.md` records **14 passes and 2 warnings** for 88 unparsed salary strings and 124 rents outside the market range. Each model has a `SUMMARY.md`. `assumptions.json` records the settings used by the run. The data contract documents the columns, aliases, and threshold checks expected by the analysis. For the current file locations and salary definitions, use the pipeline layout and market table descriptions above. [Verification report](../../outputs/verification_report.md) · [Data contract](../../docs/DATA_CONTRACT.md) · [Chinese guide](../../docs/guide/datathon_data_tables_and_figures_zh.md)

## 5. Seven static figures

[Figure generation script](../../visualization/make_figures.py) · [PNG exports](../../visualization/figures)

| PNG | Data, chart form, and how to read it | Why this form works and when to use it |
|---|---|---|
| `01_barrier_index_by_profile.png` | Horizontal bars from local-pay `equity_table.csv`, limited to profiles without family support. Each bar shows the share with a shortfall out of 333 eligible pairs. | A common denominator makes housing, debt, and parent profiles comparable. For no debt, about 51.1% fall short when living alone and 23.7% when sharing. |
| `02_break_even_salary_by_city.png` | Selects the 20 cities with the most valid one-bedroom rental signatures from `city_opportunity.csv`. Two linked points per city show the no-debt, no-support salary thresholds for renting alone and sharing. A band shows regional wage P25–P75, and a line marks P50. | The distance between the two points shows how much sharing lowers the gross salary threshold in that city. The pay band gives a reference from the full screened regional wages. The 20 cities are a high-coverage display subset. |
| `03_same_job_different_start.png` | Five no-support profiles from the local `same_job_different_start.csv`. Fixes annual gross pay at $68,318 for skilled trades, maintenance, and repair in San Carlos. Stacks rent, loan payment, childcare, essentials, and savings. The marker at about $4,443/month shows take-home pay. | Fixing pay shows which expense pushes the total past take-home pay. The underlying example has a gap of about $1,364/month for solo living without debt and a surplus of about $68/month for shared housing without debt. The static figure plots five selected profiles. |
| `04_college_net_price_by_income.png` | Draws on 2022–23 income-band net prices in `college_comparison.csv`. The horizontal axis shows income bands, the vertical axis shows annual net price, and each line represents a region's unweighted median across four-year institutions. | Shows how net price changes across income bands and regions. The connecting lines help trace the bands. Use the notebook or source table for exact institution counts. |
| `05_barrier_by_occupation.png` | Uses regional entry-signal results from `occupation_barrier.csv`. Two points per occupation show the shortfall rate across 58 cities when living alone and when sharing, with no debt or support. Labels include each occupation's wage. | Read along each line to compare housing at the same wage. Compare across occupations to see how different wages change feasibility. Food service and retail both fall short in all 58 cities when living alone. |
| `06_rent_by_city.png` | Uses `rent_by_city_housing.csv` to select the 12 cities with the most valid one-bedroom signatures after applying the 20-signature minimum. Dots show median monthly rent, lines show P25 to P75, and labels give counts and median dollar values. | Shows how much asking rents vary within each city as well as between cities. The 12 cities are selected by sample size. |
| `07_gap_heatmap_city_occupation.png` | Uses local-pay `combination_results.csv` for solo living with no debt or support. Selects up to 15 eligible cities by one-bedroom signature count. Blue shows surplus, orange shows shortfall, and gray shows missing combinations. The scale is centered at $0/month. | Shows where a budget falls short and by how much. The static PNG fixes the local wage model and profile. The notebook lets the reader change the model and profile in code. |

## 6. Seven VS Code notebook chart sections

Open `visualization/visualizations.ipynb` with the project Python interpreter in VS Code. Set `salary_model` to `city_occupation` for local wages or `entry_signal` for regional entry-signal wages. This switches the heatmap, profile shortfall chart, and occupation comparison. The fixed-job budget chart uses the local example. The rent, college, and break-even views use their own result tables. [VS Code notebook](../../visualization/visualizations.ipynb)

| Notebook section | Data, form, and use |
|---|---|
| 1. Monthly asking rents | Uses eligible one-bedroom groups from `rent_by_city_housing.csv` and selects the 12 cities with the most valid signatures. The dot is the median, the line is P25–P75, and the label gives the count. Shows how much rent varies within a city as well as across cities. |
| 2. Monthly budget gap by city and occupation | Uses the selected model's `combination_results.csv`, defaulting to solo living with no debt or support. Shows up to 15 eligible cities ranked by one-bedroom sample size. Cities are rows and occupations are columns. Colors are centered at $0, with gray for missing combinations. Use it to look up a specific city, occupation, and gap. |
| 3. Share of scenarios that fall short | Uses no-support profiles from `equity_table.csv`. Horizontal bars show the shortfall rate, and color distinguishes sharing from other arrangements. Every profile uses the same eligible pairs within its model. |
| 4. Same pay, different starting points | Stacks the individual expense lines from the local `same_job_different_start.csv` and marks take-home pay. The notebook shows all seven no-support profiles, while the static chart shows five. |
| 5. College net price by reported family-income ceiling | Shows three regional lines for four-year institution net price from `college_comparison.csv`. The table below shows the valid institution count for every region and income band. Read the price alongside the sample size. |
| 6. Housing arrangements by occupation | Uses `occupation_barrier.csv` for the selected pay definition. Linked points show solo and shared rates without debt or support. Labels show each occupation's eligible city count, which matters when comparing occupations in the local model. |
| 7. Break-even salary by city | Uses `city_opportunity.csv` and `salary_levels.csv`. Selects 20 cities by one-bedroom signature count, then sorts by solo break-even pay. Linked dots compare solo and shared gross annual thresholds. The shaded band is the middle half of screened regional pay and the line is its median. Use it to put housing thresholds in context with advertised wages. |

## 7. Two Tableau maps

`visualization/build_tableau_maps.py` reads `city_opportunity.csv` and both versions of `combination_results.csv`, joins them to city coordinates, and exports the two map CSVs. Tableau handles filtering and visual encoding. Use the latitude and longitude provided in the CSVs. [Map export program](../../visualization/build_tableau_maps.py)

| Map | Tableau fields and encoding | How to read and use it |
|---|---|---|
| **Annual Salary Needed to Live Alone in the Bay Area** | Load `bay_area_break_even_map.csv`. Put averaged Longitude on Columns and averaged Latitude on Rows. Put City on Detail and Break Even Alone on Color. Add Break Even Shared and Annual Pay Difference Alone Vs Shared to Tooltip. The tooltip can also show the threshold with median debt and the sample counts. | One marker per city, 58 in all. Color shows where solo living requires higher gross pay. Hover over a city to compare the two housing arrangements. In San Francisco the annual thresholds are $92,077 for solo living and $67,454 for sharing, a difference of $24,623. |
| **Monthly Budget Gap by City and Occupation** | Load `bay_area_occupation_map.csv` and use the same coordinate and City fields. Select one value each for Pay Definition, Profile, and Occupation. Color by Feasibility Gap with $0 at the center. Tooltip can show Median Annual Salary, N Valid Salary, N Valid Rent, and Rent Burden. | Shows the monthly gap or surplus at the selected occupational wage. Each filtered city has one row. An absent marker means the combination did not enter the model. Label both sides of the color scale so viewers can distinguish shortfall from surplus. |

### Recommended setup for the occupation map example

- **Pay Definition = `Regional entry-signal occupation median`.** Each city uses the same regional wage for the occupation. **`City × occupation median`** uses that city's own advertised wage, subject to sample coverage.
- **Profile = `none_debt | alone | no_support`.** Set solo living, zero debt, and zero support. Switch to `none_debt | shared | no_support` to see the housing effect at the same wage.
- **Occupation = `Food service`.** The median is $41,600/year from 36 usable salary records. In San Francisco, the $3,886 median one-bedroom rent plus $1,500 for essentials and $250 for savings requires $5,636/month. Estimated take-home pay is $2,853, leaving a shortfall of about $2,783/month. Sharing reduces it to about $1,546/month. Across the model, **0 of 58** cities meet this budget when living alone, while **3 of 58** meet it when sharing: Antioch, Suisun City, and Vallejo.
- In a presentation, place the $92,077 solo threshold alongside the $41,600 advertised wage benchmark and the $2,783 monthly gap. The first two values use annual gross pay. The last is the remaining gap after modeled taxes.

[Break-even map CSV](../../visualization/tableau/bay_area_break_even_map.csv) · [Occupation map CSV](../../visualization/tableau/bay_area_occupation_map.csv) · [Published break-even map](https://public.tableau.com/app/profile/karissa.song/viz/AnnualSalaryNeededtoLiveAloneintheBayArea/1)

## 8. Forms and interactive views

The editable budget form is the **Simulator** in the optional Streamlit app at `visualization/dashboard/app.py`. Launch it with Streamlit from the terminal so the app runs in a browser session. See the command in Section 11. It uses the same Python budget function as the batch analysis, so a user can adjust individual assumptions and see the effects.

| Simulator inputs or outputs | Default or behavior | Why it is useful |
|---|---|---|
| Pay basis, occupation, and gross annual salary | Choose regional entry-signal or all screened regional pay. An occupation sets the median default. The salary can be edited. | A real offer may differ from an occupation's advertised median. |
| City, housing type, roommates, and custom rent | Starts with the local housing-type median for the whole unit. An override takes the full monthly rent. Roommate count excludes the user. | Calculates a personal rent share and shows the rental sample size. |
| Debt principal, annual interest, and loan term | Defaults to median debt, 6.39%, and 10 years. | Converts different loan terms and debt balances into monthly costs. |
| Tax method and flat rate | Defaults to the progressive approximation. Flat-tax mode defaults to 22%. | Lets the user test a different effective rate. |
| Essentials, savings, support, and childcare | Essentials and savings use the model settings. Support and childcare start at zero and can be edited. | Reflects different living costs, transfers, and household needs. |
| Outputs | Before-savings balance, gap after savings, rent share of gross pay, break-even salary, gap without support, effective tax rate, and a line-item budget table. | Shows what drives a shortfall and what changes might close it. |

| Streamlit page | Charts, tables, and use |
|---|---|
| Market overview | Pay disclosure and sample-count cards, eligible-city count, regional wage quartiles, occupational wage table, selectable city and housing rent chart with interquartile ranges, rent table, and eligibility and exclusion tables. Establishes the inputs' coverage and distributions. |
| Affordability heatmap | City-by-occupation heatmap that switches between monthly gap and rent burden. A city chart compares the solo, shared, and median-debt solo wage thresholds with the regional wage band. Shows where shortfalls occur and the pay needed to address them. |
| Simulator | Editable budget inputs, summary cards, and a line-item table. Shows how one household budget changes when assumptions change. |
| Equity | Horizontal Barrier Index bars, grouped solo and shared bars by occupation, fixed-pay gap bars, factor effects, and local-model actionability and sensitivity tables. Four-year metrics also have a selectable line chart and sample-count table. Connects the individual budget to results across eligible pairs. |

[Streamlit source](../../visualization/dashboard/app.py)

## 9. Presentation sequence using the current assets

The current `final/` package supplies presentation material as PNGs, the notebook, and Tableau CSVs. Use the following sequence to assemble a presentation from those files.

| Topic | Current source | What to explain |
|---|---|---|
| Opening result | Regional `equity_table.csv` or notebook section 3 in regional mode | 65.0% of 812 modeled pairs fall short in the no-debt solo profile without support. |
| Coverage and inputs | Preprocessing counts and the two eligibility logs. Use static figure 06 for a rent example. | Separate posting counts, rental sample counts, institutions, and modeled pairs. Explain why both housing types need sufficient coverage. |
| Housing and salary thresholds | Static figures 01 and 02, or the break-even Tableau map | Use 333 local pairs for the profile comparison, and use the 58-city map to show the gross thresholds and the change from sharing. |
| Same wage, different expenses | Static figure 03 or notebook section 4 | Point to take-home pay, then show how rent, debt, and childcare add to the monthly total. |
| Where and for whom | Static figures 05 and 07, or the occupation Tableau map | Figure 05 uses regional entry-signal wages and 58 cities per occupation. Figure 07 uses local wages with visible gaps in coverage. On the map, fix the occupation and pay definition before switching the housing profile. |
| Education context | Static figure 04 and notebook section 5 | Show four-year college net prices by family income and region. Explain how the education workbooks inform debt and childcare scenarios. |
| Close with assumptions | The sensitivity table or the optional Simulator | Change one input to show how the budget responds. Explain that the study estimates modeled scenarios and that individual outcomes would require individual data. |

[Current figures](../../visualization/figures) · [Notebook](../../visualization/visualizations.ipynb) · [Tableau inputs](../../visualization/tableau)

## 10. Findings and interpretation limits

| Finding | How to interpret it |
|---|---|
| With no debt or support in the regional entry-signal model, **65.0%** of solo-living combinations fall short. Sharing brings the figure to **23.8%**. | The same 812 pairs are used in both cases, giving about a 41.3 percentage-point change. Each arrangement uses the representative market rent for its housing type. |
| The same housing switch yields **51.1% → 23.7%** in the local model. | Both values use 333 pairs. Comparison with the regional model also reflects differences in wage definitions and coverage. |
| Adding median debt to solo living without support raises the regional shortfall rate from **65.0% to 72.3%**. Raising rent 10% in that debt profile brings it to **77.8%**. | Isolates the modeled changes in loan and rent costs. With rent 10% higher, the median gap rises from **$601 to $864/month**. |
| The student-parent profile without support falls short in **96.1%** of regional pairs and **87.7%** of local pairs. | Each estimate combines median debt, the full rent on a two-bedroom unit, and center-based childcare. To isolate one of those effects, hold the other two fixed. |

These percentages use **equally weighted simulated pairs**. Listings show advertised wages and asking rents, which can differ from accepted pay and leased prices. The datasets span different periods and cannot follow a single graduate across sources. Entry signals and occupations rely on text rules. In a separate manual check, the occupation classifier got **88 of 100** titles right. Essentials, savings, and support are common scenario inputs. Childcare uses a statewide estimate, and taxes use a common single-filer approximation. The strongest uses are comparisons of specified conditions, cities, and budget mechanisms.

[Assumptions and scope](../../docs/ASSUMPTIONS.md) · [Local profile results](../../outputs/equity/equity_table.csv) · [Regional profile results](../../outputs/equity_entry_signal/equity_table.csv) · [Regional sensitivity results](../../outputs/equity_entry_signal/sensitivity.csv)

## 11. Rebuild the tables, figures, and views

Run from `/Users/skevin/datathon/final` using the project environment.

```sh
../.venv/bin/python -B run_pipeline.py
../.venv/bin/python -B visualization/build_tableau_maps.py
../.venv/bin/python -B -m unittest discover -s tests -t .
../.venv/bin/python -m streamlit run visualization/dashboard/app.py
```

| Task | What the command does |
|---|---|
| Rebuild | `run_pipeline.py` verifies the processed snapshot, rebuilds market and analysis tables in `outputs/`, writes the assumptions, and generates the seven PNGs under `visualization/figures/`. Add `--preprocess` to start with the raw files. |
| Refresh the Tableau CSVs | `visualization/build_tableau_maps.py` refreshes both CSVs under `visualization/tableau/`, reusing packaged coordinates by default. Add `--raw-dir data/raw` to rebuild coordinates from Zillow. |
| Run tests | The unittest command runs the budget, occupation-classification, and analysis tests. |
| Open the dashboard | The Streamlit command starts the optional dashboard. Open the Local URL printed in the terminal. |
| Open the notebook | Open `visualization/visualizations.ipynb` in VS Code and use the project's Python interpreter. |
| Use Tableau | Upload or refresh the workbook with the matching CSV. The occupation map description in this guide comes from the local CSV and export script. Its publication status remains unverified. |

[Notebook](../../visualization/visualizations.ipynb) · [Tableau inputs](../../visualization/tableau) · [Project README](../../README.md)
