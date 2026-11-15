# Processed-data verification report

Source directory: `/Users/skevin/datathon/final/data/processed` (read-only). Summary: {'PASS': 14, 'WARN': 2}

| File | Check | Status | Detail |
|---|---|---|---|
| jobs_bay_area.csv | file loads | **PASS** | 46,970 rows x 19 cols |
| jobs_bay_area.csv | exact duplicate rows | **PASS** | 0 duplicates in 46970 rows |
| jobs_bay_area.csv | annualised salary plausible range (annualized_low_usd) | **PASS** | 0 of 39432 values outside [15,000.0, 1,000,000.0]; 7538 missing |
| jobs_bay_area.csv | hourly values left unconverted | **PASS** | 0 annual-salary values between 7 and 200 (look like hourly pay) |
| jobs_bay_area.csv | annual pay field coverage | **PASS** | 16.0% missing in annualized_low_usd, including upper-bound-only and unannualized pay |
| jobs_bay_area.csv | salary disclosure | **PASS** | 7,066 of 46,970 postings (15.0%) have no salary text |
| jobs_bay_area.csv | unparsed salaries | **WARN** | 88 unparsed, 2 of them Spanish-language ('por hora/por año') |
| rentals_bay_area.csv | file loads | **PASS** | 59,409 rows x 12 cols |
| rentals_bay_area.csv | exact duplicate rows | **PASS** | 0 duplicates in 59409 rows |
| rentals_bay_area.csv | duplicate listing ids (zpid) | **PASS** | 0 repeated zpid values |
| rentals_bay_area.csv | monthly asking rent plausible range (monthly_rent_usd) | **WARN** | 124 of 59409 values outside [500, 15,000]; examples [20280.0, 23000.0, 16500.0, 30000.0, 16898.0]; 0 missing |
| colleges.csv | file loads | **PASS** | 6,418 rows x 24 cols |
| colleges.csv | Unit ID unique | **PASS** | 0 duplicated IDs in 6418 rows |
| colleges.csv | Unit ID standardised to integer | **PASS** | 0 non-integer IDs |
| colleges.csv | 'Median Debt of Completers' available for debt profiles | **PASS** | completer_median_debt_2021_usd |
| colleges.csv | Bay Area institutions identified | **PASS** | 124 institutions flagged (is_bay_area) |
