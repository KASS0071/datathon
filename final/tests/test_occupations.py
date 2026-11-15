"""Occupation classifier and pay-point rules."""
import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import config  # noqa: E402
from src.market.build_market_inputs import posting_pay_points  # noqa: E402
from src.market.classify_occupations import GROUPS, UNCLASSIFIED, classify, classify_title  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "occupation_validation.csv"


class TestClassifier(unittest.TestCase):
    def test_hand_labelled_accuracy(self):
        # 220 titles hand-labelled by the ver2 agent. 'fresh' was drawn after the
        # first tuning round; its accuracy at labelling time was 88%.
        v = pd.read_csv(FIXTURE)
        v["now"] = classify(v["job_title"])
        for name, g in v.groupby("sample"):
            with self.subTest(sample=name):
                self.assertGreaterEqual((g["now"] == g["label"]).mean(), 0.85)

    def test_known_titles(self):
        cases = {
            "Software Engineer": "Software, data & IT", "Sales Associate": "Retail & customer service",
            "Medical Assistant": "Healthcare practitioners & support", "Teacher Assistant": "Education & childcare",
            "Data Entry Clerk": "Office & administrative support", "Restaurant Manager": "Food service",
            "Delivery Driver - Medical Equipment": "Transportation, warehouse & logistics",
            "Software Dev Engineer II, Stores": "Software, data & IT", "Dishwashers": "Food service",
            "Assistant Branch Manager": "Management (general)", "Its a great job": UNCLASSIFIED,
        }
        for title, want in cases.items():
            with self.subTest(title=title):
                self.assertEqual(classify_title(title), want)

    def test_outputs_are_known_groups(self):
        self.assertTrue(set(classify(pd.Series(["Cook", None, "zzz", "Nurse"]))) <= set(GROUPS))


class TestPayPoints(unittest.TestCase):
    def jobs(self, **over):
        base = dict(job_title="Cook", company="A", city="Oakland", salary_original="x", salary_status="parsed",
                    entry_signal="unknown", job_type="Full-time", salary_unit="hour",
                    salary_low_usd=20.0, salary_high_usd=24.0)
        base.update(over)
        return pd.DataFrame([base])

    def test_hourly_midpoint_annualised(self):
        p = posting_pay_points(self.jobs())
        self.assertAlmostEqual(p["annual_pay"].iloc[0], 22 * 2080)

    def test_exclusions(self):
        cases = {
            "unit error": dict(salary_low_usd=65_000, salary_high_usd=96_500),
            "senior": dict(entry_signal="senior_or_3plus_years_signal"),
            "part-time only": dict(job_type="Part-time"),
            "daily": dict(salary_unit="day"),
            "too low": dict(salary_unit="year", salary_low_usd=5_000, salary_high_usd=6_000),
            "too high": dict(salary_unit="year", salary_low_usd=2_000_000, salary_high_usd=3_000_000),
        }
        for name, over in cases.items():
            with self.subTest(name):
                self.assertEqual(len(posting_pay_points(self.jobs(**over))), 0)

    def test_high_but_plausible_kept_and_reposts_dropped(self):
        j = pd.concat([self.jobs(salary_unit="year", salary_low_usd=320_000, salary_high_usd=625_000)] * 2)
        p = posting_pay_points(j)
        self.assertEqual(len(p), 1)  # repost removed
        self.assertLessEqual(p["annual_pay"].iloc[0], config.ANNUAL_PAY_RANGE[1])


if __name__ == "__main__":
    unittest.main()
