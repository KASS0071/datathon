"""Consistency checks for the equity analysis (Stage 5 acceptance gate)."""
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import config  # noqa: E402
from src.analysis.equity_analysis import (  # noqa: E402
    Benchmarks, Profile, build_eligible_panel, load_market_combinations,
    normalize_housing_type, run_all, run_profile, standardize_columns,
)

BM = Benchmarks(20_000, 30_000, 1_800, "test", "test")


def tiny_market(overrides=None):
    rows = []
    for city in ("X", "Y"):
        for h, rent in (("1br", 2500), ("2br", 3400)):
            rows.append(dict(city=city, occupation="Occ", housing_type=h,
                             median_annual_salary=70_000, n_valid_salary=30,
                             median_monthly_rent=rent, n_valid_rent=50))
    df = pd.DataFrame(rows)
    for (city, h, col), val in (overrides or {}).items():
        df.loc[(df.city == city) & (df.housing_type == h), col] = val
    return standardize_columns(df)


class TestEligibility(unittest.TestCase):
    def test_thin_rent_excludes_pair_without_imputing(self):
        m = tiny_market({("Y", "2br", "n_valid_rent"): config.MIN_VALID_RENT_LISTINGS - 1})
        panel, log = build_eligible_panel(m, {"1br", "2br"})
        self.assertEqual(panel["city"].tolist(), ["X"])
        self.assertIn("rent_2br_insufficient", log.set_index("city").at["Y", "exclusion_reason"])

    def test_thin_rent_does_not_mark_salary_insufficient(self):
        # Regression: a combined row-level flag used to leak across dimensions.
        m = tiny_market({("Y", "2br", "n_valid_rent"): 1})
        m["sufficient_data"] = m["n_valid_rent"] >= 20
        _, log = build_eligible_panel(m, {"1br", "2br"})
        self.assertNotIn("salary", log.set_index("city").at["Y", "exclusion_reason"])

    def test_missing_housing_row(self):
        m = tiny_market()
        m = m[~((m.city == "Y") & (m.housing_type == "2br"))]
        panel, _ = build_eligible_panel(m, {"1br", "2br"})
        self.assertEqual(panel["city"].tolist(), ["X"])

    def test_missing_required_column_is_explicit(self):
        with self.assertRaises(KeyError):
            standardize_columns(pd.DataFrame({"city": ["X"]}))

    def test_housing_normalisation(self):
        for raw, want in [("1 Bedroom", "1br"), ("2BR", "2br"), ("Studio", "studio"), ("0", "studio"), (2.0, "2br")]:
            self.assertEqual(normalize_housing_type(raw), want)


class TestProfiles(unittest.TestCase):
    def setUp(self):
        self.m = load_market_combinations(config.FAKE_MARKET_FIXTURE)[0]
        self.out = run_all(self.m, BM)

    def test_identical_denominator(self):
        t = self.out["equity_table"]
        self.assertEqual(t["n_combinations"].nunique(), 1)
        sets = self.out["combination_results"].groupby("profile").apply(
            lambda g: tuple(sorted(zip(g.city, g.occupation))), include_groups=False)
        self.assertEqual(sets.nunique(), 1)

    def test_barrier_index_definition(self):
        t = self.out["equity_table"]
        np.testing.assert_allclose(t["barrier_index"], 1 - t["n_feasible"] / t["n_combinations"])

    def test_support_shifts_gap_by_exact_amount(self):
        r = self.out["combination_results"].set_index(["profile", "city", "occupation"])["feasibility_gap"]
        a = r.xs("none_debt | alone | no_support").sort_index()
        b = r.xs("none_debt | alone | support").sort_index()
        np.testing.assert_allclose(a - b, config.FAMILY_SUPPORT_MONTHLY)

    def test_more_debt_never_helps(self):
        t = self.out["equity_table"].set_index("profile")
        for housing in ("alone", "shared"):
            rates = [t.at[f"{d}_debt | {housing} | no_support", "feasibility_rate"] for d in ("none", "median", "high")]
            self.assertTrue(rates[0] >= rates[1] >= rates[2])

    def test_primary_index_has_no_support(self):
        r = self.out["combination_results"]
        self.assertTrue((r.loc[r.index_type == "independence", "family_support"] == 0).all())

    def test_shared_rent_is_half_of_2br(self):
        panel, _ = build_eligible_panel(self.m, {"2br"})
        r = run_profile(panel, Profile("s", "none", "shared", False), BM)
        np.testing.assert_allclose(r["personal_rent"], panel["rent_2br"] / 2)


if __name__ == "__main__":
    unittest.main()
