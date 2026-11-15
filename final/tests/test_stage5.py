"""Consistency checks for RQ1 opportunity, actionability and college comparison."""
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.analysis.summarize_results import actionability, city_opportunity, college_comparison  # noqa: E402

RENTS = pd.DataFrame([
    dict(county="C", city=c, housing_type=h, median_monthly_rent=r, n_valid_rent=n)
    for c, h, r, n in [("Cheap", "1br", 1800, 50), ("Cheap", "2br", 2400, 50),
                       ("Dear", "1br", 3800, 50), ("Dear", "2br", 5000, 50),
                       ("Thin", "1br", 2500, 50), ("Thin", "2br", 3000, 3)]])
PAY = pd.DataFrame({"annual_pay": np.linspace(35_000, 120_000, 40)})


class TestOpportunity(unittest.TestCase):
    def setUp(self):
        self.o = city_opportunity(RENTS, PAY, 20_000).set_index("city")

    def test_thin_city_excluded(self):
        self.assertNotIn("Thin", self.o.index)

    def test_orderings(self):
        for c in self.o.index:
            r = self.o.loc[c]
            self.assertLessEqual(r.break_even_shared, r.break_even_alone)
            self.assertGreaterEqual(r.break_even_alone_median_debt, r.break_even_alone)
            self.assertGreaterEqual(r.share_postings_independent_shared, r.share_postings_independent_alone)
        self.assertGreater(self.o.at["Dear", "break_even_alone"], self.o.at["Cheap", "break_even_alone"])

    def test_share_definition(self):
        be = self.o.at["Cheap", "break_even_alone"]
        self.assertAlmostEqual(self.o.at["Cheap", "share_postings_independent_alone"], (PAY.annual_pay >= be).mean())


class TestActionability(unittest.TestCase):
    def test_definitions(self):
        res = pd.DataFrame({
            "profile": ["p"] * 3, "feasibility_gap": [200.0, -50.0, 600.0],
            "required_additional_gross_annual": [3000.0, 0.0, 9000.0], "median_annual_salary": [60_000.0] * 3,
            "personal_rent": [2000.0] * 3, "loan_payment": [250.0] * 3})
        a = actionability(res).iloc[0]
        self.assertEqual((a.n_combinations, a.n_short), (3, 2))
        self.assertAlmostEqual(a.median_monthly_shortfall, 400.0)
        self.assertAlmostEqual(a.median_raise_pct_needed, 0.1)       # median(0.05, 0.15)
        self.assertAlmostEqual(a.share_closed_by_eliminating_loan, 0.5)  # 250 >= 200 only


class TestCollege(unittest.TestCase):
    def test_groups_and_categorical_guard(self):
        rng = np.random.default_rng(0)
        n = 60
        col = pd.DataFrame({
            "unit_id": range(n), "is_bay_area": [1] * 20 + [0] * 40, "state": ["CA"] * 40 + ["NY"] * 20,
            "institution_type_2021": ["Public Four-Year"] * n,
            "completer_median_debt_2021_usd": rng.uniform(5000, 30000, n),
            "graduation_rate_6yr_2021_pct": rng.uniform(20, 95, n),
            "median_earnings_10yr_after_entry_2021_usd": rng.choice([27937, 36041, 47921.5], n),
            "low_income_net_price_2020_21_usd": rng.uniform(5000, 30000, n)})
        aff = pd.DataFrame({"unit_id": list(range(n)) * 2, "family_income_ceiling_usd": [30000] * n + [75000] * n,
                            "net_price_2022_23_usd": rng.uniform(5000, 40000, 2 * n),
                            "affordability_gap_2022_23_usd": rng.uniform(0, 20000, 2 * n)})
        out = college_comparison(col, aff)
        self.assertEqual(set(out.group), {"Bay Area", "California (non-Bay)", "National (other states)"})
        self.assertNotIn("median_earnings_10yr_after_entry_2021_usd", set(out.source_column))
        bay = out[(out.group == "Bay Area") & (out.source_column == "completer_median_debt_2021_usd")]
        self.assertEqual(int(bay.n_institutions.iloc[0]), 20)


if __name__ == "__main__":
    unittest.main()
