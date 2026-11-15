# Data provenance and limits

The independent review and the current audit are recorded at different points in the project. Use data/processed/MANIFEST.md for the digest and row count of each current file, data/processed/quality_report.json for preprocessing counts, and outputs/verification_report.md for verification findings.

| Input | Current coverage and caveats |
| --- | --- |
| Indeed | 140,816 raw rows, 46,970 retained across 109 city labels after recognizing Saint Helena as St Helena. Another 781 rows named a Bay Area region without a usable city, so these are counted separately and excluded from city results. The 15 expired flags describe the extract. |
| Salary | 39,904 postings have pay text, 39,816 parse, and 7,066 disclose no pay text. Daily and unsupported pay, suspect hourly units above $500, and out-of-window annual values retain raw text. Annualized fields use the $15,000–$1,000,000 window. 88 strings remain unparsed, 84 parsed rows lack a supported annual period, 12 have suspect hourly units and 95 fall outside the annual window. The modeling step recomputes the representative wage from retained original amounts and applies separate repost and experience screens. |
| Zillow | 59,409 cleaned rental listings. The base rent and price values match in the 53,195 retained listings with both fields; the rest use the price field. 124 outliers are excluded at the market-input step. Equivalent listing signatures may describe different units. Postal cities are pooled for city-level rent analysis. |
| College | 6,418 distinct institutions and 124 Bay Area institutions. 20,112 institution and income-band rows. The graduation debt baseline uses 33 four-year institutions with reported data, so its $20,389 median differs from the $13,000 all-institution median. The 10-year earnings field was excluded from analysis because it has only three distinct values. |
| Childcare | The adjusted source cost is $1,795.42/month for all valid California rows. The difference between the student-parent and non-parent annual gaps divided by 12 reproduces the value to the cent for 316 matched Bay Area rows. |
| Occupation | Classifier uses titles. The original fresh check was 88 correct of 100, while 220 labeled titles are retained as regression fixtures. Title classifications and entry signals are proxies. |

The project cannot follow the same student across sources. Job ads and rental prices are asking amounts, and not every person or market has the same labor, tax or living-cost circumstances.
