"""Generate a small, deterministic, clearly FAKE market_combinations file.

City and occupation names are fictional on purpose so these numbers can never
be mistaken for findings. Includes deliberate edge cases:
  - one occupation with too few salary postings
  - one city with too few 2br listings
  - one city with no 2br row at all
"""
from pathlib import Path

import numpy as np
import pandas as pd

rng = np.random.default_rng(42)
cities = {"FAKE_City_A": 1.25, "FAKE_City_B": 1.0, "FAKE_City_C": 0.85, "FAKE_City_D": 0.95}
occupations = {"FAKE_Occ_Admin": 52_000, "FAKE_Occ_Analyst": 78_000,
               "FAKE_Occ_Engineer": 118_000, "FAKE_Occ_Retail": 41_000, "FAKE_Occ_Teacher": 60_000}
base_rent = {"studio": 2_100, "1br": 2_600, "2br": 3_400}

# Rent depends only on city x housing type (as a correct join would produce).
rent_table = {}
for city, cmult in cities.items():
    for h, r in base_rent.items():
        n_rent = 8 if (city == "FAKE_City_C" and h == "2br") else int(rng.integers(25, 300))
        rent_table[city, h] = (round(r * cmult * rng.uniform(0.97, 1.03), -1), n_rent)

rows = []
for city, cmult in cities.items():
    for occ, sal in occupations.items():
        salary = round(sal * (0.9 + 0.25 * (cmult - 0.85)) * rng.uniform(0.95, 1.05), -2)
        n_sal = 4 if occ == "FAKE_Occ_Teacher" else int(rng.integers(12, 60))
        for h, r in base_rent.items():
            if city == "FAKE_City_D" and h == "2br":
                continue
            rent, n_rent = rent_table[city, h]
            rows.append({
                "city": city, "occupation": occ, "housing_type": h,
                "median_annual_salary": salary, "n_valid_salary": n_sal, "n_postings": n_sal + 7,
                "median_monthly_rent": rent,
                "n_valid_rent": n_rent,
                "sufficient_data": n_sal >= 10 and n_rent >= 20,
                "DATA_IS_FAKE": True,
            })
out = Path(__file__).with_name("market_combinations_FAKE.csv")
pd.DataFrame(rows).to_csv(out, index=False)
print(f"wrote {len(rows)} rows -> {out}")
