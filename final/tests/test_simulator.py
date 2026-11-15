"""Hand-calculated checks for the Financial Independence Engine.

Every expected number below was worked out by hand (arithmetic in comments)
BEFORE running the code, per the Stage 4 acceptance gate.

Run (from final/):  ../.venv/bin/python -B -m unittest discover -s tests -t . -v
"""
import math
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.budget.calculate_budget import (  # noqa: E402
    MissingDataError,
    break_even_salary,
    ScenarioInputs,
    compute_budget,
    estimate_effective_tax_rate,
    monthly_loan_payment,
    simulate,
)


class TestHandCalculatedScenarios(unittest.TestCase):
    def test_A_zero_debt_living_alone(self):
        # salary 60,000 -> gross 5,000/mo; tax 20% -> net 4,000
        # rent 2,400 alone; loan 0; essentials 1,500; savings 250
        # balance  = 4000 - 2400 - 0 - 1500          = 100
        # required = 2400 + 0 + 1500 + 250           = 4150
        # gap      = 4150 - 4000                     = 150 (shortfall)
        # rent burden = 2400*12 / 60000              = 0.48
        # extra gross = 150 * 12 / 0.8               = 2,250 per year
        r = simulate(ScenarioInputs(60_000, 2_400, roommates=0, debt_principal=0,
                                    effective_tax_rate=0.20, monthly_essentials=1_500,
                                    monthly_savings_target=250))
        self.assertAlmostEqual(r["net_monthly"], 4000.0, places=6)
        self.assertAlmostEqual(r["loan_payment"], 0.0, places=6)
        self.assertAlmostEqual(r["monthly_balance"], 100.0, places=6)
        self.assertAlmostEqual(r["feasibility_gap"], 150.0, places=6)
        self.assertAlmostEqual(r["rent_burden"], 0.48, places=6)
        self.assertAlmostEqual(r["required_additional_gross_annual"], 2250.0, places=6)
        self.assertFalse(r["feasible_independent"])
        self.assertFalse(r["rent_affordable"])

    def test_B_zero_interest_with_roommate(self):
        # debt 24,000 at 0% over 120 months -> 200/mo
        # salary 90,000 -> gross 7,500; tax 25% -> net 5,625
        # rent 3,000 split with 1 roommate -> 1,500
        # balance  = 5625 - 1500 - 200 - 1500        = 2,425
        # required = 1500 + 200 + 1500 + 250         = 3,450
        # gap      = 3450 - 5625                     = -2,175 (surplus)
        # rent burden = 1500*12 / 90000              = 0.20
        r = simulate(ScenarioInputs(90_000, 3_000, roommates=1, debt_principal=24_000,
                                    annual_interest_rate=0.0, effective_tax_rate=0.25,
                                    monthly_essentials=1_500, monthly_savings_target=250))
        self.assertAlmostEqual(r["loan_payment"], 200.0, places=6)
        self.assertAlmostEqual(r["personal_rent"], 1500.0, places=6)
        self.assertAlmostEqual(r["monthly_balance"], 2425.0, places=6)
        self.assertAlmostEqual(r["feasibility_gap"], -2175.0, places=6)
        self.assertAlmostEqual(r["rent_burden"], 0.20, places=6)
        self.assertAlmostEqual(r["required_additional_net_monthly"], 0.0, places=6)
        self.assertTrue(r["feasible_independent"])
        self.assertTrue(r["rent_affordable"])

    def test_C_interest_and_family_support(self):
        # debt 30,000 at 6%/yr, 10 yrs: r = 0.005, n = 120
        # (1.005)^120 = 1.819397 ; payment = 150 / (1 - 1/1.819397) = 333.06
        # salary 50,000 -> gross 4,166.67; tax 18% -> net 3,416.67
        # rent 2,200 alone; essentials 1,400; savings 200; support 500
        # balance  = 3416.67 + 500 - 2200 - 333.06 - 1400   = -16.39
        # required = 2200 + 333.06 + 1400 + 200             = 4,133.06
        # gap (with support)    = 4133.06 - 3916.67         = 216.39
        # gap (without support) = 4133.06 - 3416.67         = 716.39
        r = simulate(ScenarioInputs(50_000, 2_200, debt_principal=30_000,
                                    annual_interest_rate=0.06, effective_tax_rate=0.18,
                                    monthly_essentials=1_400, monthly_savings_target=200,
                                    monthly_family_support=500))
        self.assertAlmostEqual(r["loan_payment"], 333.06, delta=0.01)
        self.assertAlmostEqual(r["monthly_balance"], -16.39, delta=0.02)
        self.assertAlmostEqual(r["feasibility_gap"], 216.39, delta=0.02)
        self.assertAlmostEqual(r["feasibility_gap_without_support"], 716.39, delta=0.02)
        self.assertFalse(r["feasible_with_support"])
        self.assertFalse(r["feasible_independent"])

    def test_D_student_parent_childcare(self):
        # salary 70,000 -> gross 5,833.33; tax 22% -> net 4,550
        # 2br rent 3,200 not shared; essentials 1,500; childcare 1,800; savings 250
        # balance = 4550 - 3200 - 1500 - 1800 = -1,950
        # gap     = 3200 + 1500 + 1800 + 250 - 4550 = 2,200
        r = simulate(ScenarioInputs(70_000, 3_200, effective_tax_rate=0.22,
                                    monthly_essentials=1_500, monthly_childcare=1_800,
                                    monthly_savings_target=250))
        self.assertAlmostEqual(r["monthly_balance"], -1950.0, places=6)
        self.assertAlmostEqual(r["feasibility_gap"], 2200.0, places=6)

    def test_support_only_changes_assisted_measure(self):
        base = dict(annual_salary=55_000, monthly_rent_total=2_500, effective_tax_rate=0.2)
        a = simulate(ScenarioInputs(**base))
        b = simulate(ScenarioInputs(**base, monthly_family_support=800))
        self.assertAlmostEqual(a["feasibility_gap_without_support"], b["feasibility_gap_without_support"])
        self.assertAlmostEqual(a["feasibility_gap"] - 800, b["feasibility_gap"])


class TestBreakEvenSalary(unittest.TestCase):
    def test_flat_tax_hand_calculated(self):
        # need = 2400 rent + 1500 + 250 = 4150 net/mo; flat 20% ->
        # gross = 4150 * 12 / 0.8 = 62,250
        s = break_even_salary(2400, effective_tax_rate=0.20, monthly_essentials=1500, monthly_savings_target=250)
        self.assertAlmostEqual(s, 62_250.0, places=6)

    def test_progressive_lands_exactly_on_zero_gap(self):
        for rent, roommates, debt in [(2500, 0, 0), (3400, 1, 20_000), (4000, 0, 30_000)]:
            s = break_even_salary(rent, roommates, debt)
            gap = compute_budget(s, rent, roommates, debt,
                                 effective_tax_rate=estimate_effective_tax_rate(s))["feasibility_gap"]
            self.assertAlmostEqual(gap, 0.0, delta=0.01)

    def test_vectorised_and_support(self):
        s = break_even_salary(np.array([2000, 3000]), monthly_family_support=500, effective_tax_rate=0.2)
        np.testing.assert_allclose(s, 12 * (np.array([2000, 3000]) + 1500 + 250 - 500) / 0.8)


class TestLoanPayment(unittest.TestCase):
    def test_known_amortisation(self):
        # Standard reference: $10,000 at 5% for 10 yrs = $106.07/mo
        self.assertAlmostEqual(monthly_loan_payment(10_000, 0.05, 10), 106.07, delta=0.01)

    def test_zero_principal(self):
        self.assertEqual(monthly_loan_payment(0, 0.07), 0.0)

    def test_total_repaid_exceeds_principal_when_interest(self):
        self.assertGreater(monthly_loan_payment(20_000, 0.0639) * 120, 20_000)


class TestTaxEstimate(unittest.TestCase):
    def test_hand_calculated_60k(self):
        # Federal: taxable 60000-15750 = 44,250 -> 1,192.50 + 32,325*0.12 = 5,071.50
        # CA: taxable 54,460 -> 107.56 + 294.86 + 589.84 + 14,215*0.06 = 1,845.16
        # SS 3,720 + Medicare 870 + SDI 720
        # total 12,226.66 / 60,000 = 0.203778
        self.assertAlmostEqual(estimate_effective_tax_rate(60_000), 12_226.66 / 60_000, places=5)

    def test_monotonic_and_bounded(self):
        rates = estimate_effective_tax_rate(np.array([20_000, 45_000, 80_000, 150_000, 400_000]))
        self.assertTrue(np.all(np.diff(rates) > 0))
        self.assertTrue(np.all((rates > 0) & (rates < 0.5)))

    def test_zero_salary(self):
        self.assertEqual(estimate_effective_tax_rate(0), 0.0)


class TestValidation(unittest.TestCase):
    def test_missing_salary(self):
        with self.assertRaises(MissingDataError):
            simulate(ScenarioInputs(float("nan"), 2000))
        with self.assertRaises(MissingDataError):
            simulate(ScenarioInputs(60_000, None))

    def test_invalid_values(self):
        bad = [
            dict(annual_salary=-1, monthly_rent_total=2000),
            dict(annual_salary=60_000, monthly_rent_total=-5),
            dict(annual_salary=60_000, monthly_rent_total=2000, roommates=1.5),
            dict(annual_salary=60_000, monthly_rent_total=2000, annual_interest_rate=6.39),
            dict(annual_salary=60_000, monthly_rent_total=2000, effective_tax_rate=22),
            dict(annual_salary=60_000, monthly_rent_total=2000, debt_principal=-100),
            dict(annual_salary=60_000, monthly_rent_total=2000, monthly_family_support=-1),
            dict(annual_salary=float("inf"), monthly_rent_total=2000),
        ]
        for kwargs in bad:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                simulate(ScenarioInputs(**kwargs))

    def test_suspicious_salary_warns(self):
        r = simulate(ScenarioInputs(25, 1000, effective_tax_rate=0.1))
        self.assertTrue(any("ANNUAL" in w for w in r["warnings"]))


class TestVectorisedMatchesScalar(unittest.TestCase):
    def test_arrays(self):
        salaries = np.array([45_000, 60_000, 90_000])
        rents = np.array([2_000, 2_400, 3_000])
        debts = np.array([0, 15_000, 24_000])
        rates = np.array([0.0639, 0.0, 0.05])
        vec = compute_budget(salaries, rents, 1, debts, rates, 0.2)
        for i in range(3):
            s = simulate(ScenarioInputs(int(salaries[i]), int(rents[i]), 1, int(debts[i]),
                                        float(rates[i]), 0.2))
            self.assertAlmostEqual(vec["feasibility_gap"][i], s["feasibility_gap"], places=6)
            self.assertAlmostEqual(vec["loan_payment"][i], s["loan_payment"], places=6)
        self.assertFalse(np.any(np.isnan(vec["feasibility_gap"])))
        self.assertTrue(math.isfinite(vec["rent_burden"][0]))


if __name__ == "__main__":
    unittest.main()
