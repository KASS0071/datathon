"""Financial Independence Engine (pipeline Stage 4).

One set of formulas, used everywhere (dashboard, equity analysis, tests):

    gross_monthly      = annual_salary / 12
    net_monthly        = gross_monthly * (1 - effective_tax_rate)
    personal_rent      = monthly_rent_total / (roommates + 1)
    loan_payment       = P * r / (1 - (1 + r) ** -n)   r = annual_rate / 12
                       = P / n                         when r == 0
    rent_burden        = 12 * personal_rent / annual_salary         (gross)
    monthly_balance    = net + support - rent - loan - essentials - childcare
    required_spending  = rent + loan + essentials + childcare + savings_target
    feasibility_gap    = required_spending - (net + support)  (> 0 = shortfall)

"Rental affordability" (rent_burden <= 30%) and "financial independence"
(feasibility gap <= 0 with ZERO family support) are reported separately on
purpose: a graduate can pass the first and still fail the second.

`compute_budget` works on plain floats and on numpy arrays alike, so the
interactive simulator and the vectorised equity analysis share one code path.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np

from src import config


class MissingDataError(ValueError):
    """Salary or rent is missing (NaN/None); the scenario cannot be evaluated."""


# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------
def monthly_loan_payment(principal, annual_rate, term_years=config.LOAN_TERM_YEARS):
    """Fixed monthly payment for a fully amortising loan.

    Handles zero principal and zero interest exactly. Accepts scalars or arrays.
    """
    principal = np.asarray(principal, dtype=float)
    annual_rate = np.asarray(annual_rate, dtype=float)
    n = float(term_years) * 12.0
    r = annual_rate / 12.0
    with np.errstate(divide="ignore", invalid="ignore"):
        amortised = principal * r / (1.0 - (1.0 + r) ** (-n))
    payment = np.where(r == 0.0, principal / n, amortised)
    return _unwrap(payment)


def personal_rent_share(monthly_rent_total, roommates):
    """Rent paid by one person when the unit is split evenly with `roommates`."""
    return _unwrap(np.asarray(monthly_rent_total, float) / (np.asarray(roommates, float) + 1.0))


# Approximate 2025 tax parameters, single filer, standard deduction, no credits.
# Good enough to show that effective rates differ strongly between a $45k and a
# $130k job; NOT a substitute for real tax software.
_FED_STD_DEDUCTION = 15_750.0
_FED_BRACKETS = [  # (upper bound of bracket, marginal rate)
    (11_925, 0.10), (48_475, 0.12), (103_350, 0.22), (197_300, 0.24),
    (250_525, 0.32), (626_350, 0.35), (math.inf, 0.37),
]
_CA_STD_DEDUCTION = 5_540.0
_CA_BRACKETS = [  # 2024 CA brackets (latest published at time of writing)
    (10_756, 0.01), (25_499, 0.02), (40_245, 0.04), (55_866, 0.06),
    (70_606, 0.08), (360_659, 0.093), (432_787, 0.103), (721_314, 0.113),
    (math.inf, 0.123),
]
_SS_RATE, _SS_WAGE_BASE = 0.062, 176_100.0
_MEDICARE_RATE, _ADDL_MEDICARE_RATE, _ADDL_MEDICARE_THRESHOLD = 0.0145, 0.009, 200_000.0
_CA_SDI_RATE = 0.012


def _bracket_tax(taxable, brackets):
    taxable = np.maximum(np.asarray(taxable, float), 0.0)
    tax = np.zeros_like(taxable)
    lower = 0.0
    for upper, rate in brackets:
        tax += np.clip(taxable - lower, 0.0, upper - lower) * rate
        lower = upper
    return tax


def estimate_effective_tax_rate(annual_salary):
    """Approximate total effective tax rate (federal + CA + FICA + SDI) on wages.

    Returns a share of gross salary. Scalars or arrays.
    """
    s = np.asarray(annual_salary, float)
    total = (
        _bracket_tax(s - _FED_STD_DEDUCTION, _FED_BRACKETS)
        + _bracket_tax(s - _CA_STD_DEDUCTION, _CA_BRACKETS)
        + np.minimum(s, _SS_WAGE_BASE) * _SS_RATE
        + s * _MEDICARE_RATE
        + np.maximum(s - _ADDL_MEDICARE_THRESHOLD, 0.0) * _ADDL_MEDICARE_RATE
        + s * _CA_SDI_RATE
    )
    with np.errstate(divide="ignore", invalid="ignore"):
        rate = np.where(s > 0, total / s, 0.0)
    return _unwrap(rate)


def resolve_tax_rate(annual_salary, effective_tax_rate=None, tax_mode=None):
    """Use an explicit rate if given; otherwise follow config.TAX_MODE."""
    if effective_tax_rate is not None:
        return effective_tax_rate
    mode = tax_mode or config.TAX_MODE
    if mode == "flat":
        return config.DEFAULT_EFFECTIVE_TAX_RATE
    if mode == "progressive":
        return estimate_effective_tax_rate(annual_salary)
    raise ValueError(f"Unknown tax_mode {mode!r}; use 'flat' or 'progressive'.")


# ---------------------------------------------------------------------------
# Core budget (vectorisable)
# ---------------------------------------------------------------------------
def compute_budget(
    annual_salary,
    monthly_rent_total,
    roommates=0,
    debt_principal=0.0,
    annual_interest_rate=config.DEFAULT_LOAN_INTEREST_RATE,
    effective_tax_rate=config.DEFAULT_EFFECTIVE_TAX_RATE,
    monthly_essentials=config.DEFAULT_MONTHLY_ESSENTIALS,
    monthly_savings_target=config.DEFAULT_MONTHLY_SAVINGS_TARGET,
    monthly_family_support=0.0,
    monthly_childcare=0.0,
    loan_term_years=config.LOAN_TERM_YEARS,
    rent_burden_threshold=config.RENT_BURDEN_THRESHOLD,
) -> dict[str, Any]:
    """Monthly budget for one or many scenarios. No input validation here;
    use `simulate()` for checked single scenarios."""
    salary = np.asarray(annual_salary, float)
    tax = np.asarray(effective_tax_rate, float)
    support = np.asarray(monthly_family_support, float)

    gross = salary / 12.0
    net = gross * (1.0 - tax)
    rent = np.asarray(personal_rent_share(monthly_rent_total, roommates), float)
    loan = np.asarray(monthly_loan_payment(debt_principal, annual_interest_rate, loan_term_years), float)
    essentials = np.asarray(monthly_essentials, float)
    childcare = np.asarray(monthly_childcare, float)
    savings = np.asarray(monthly_savings_target, float)

    with np.errstate(divide="ignore", invalid="ignore"):
        rent_burden = np.where(salary > 0, 12.0 * rent / salary, np.inf)

    balance = net + support - rent - loan - essentials - childcare
    required = rent + loan + essentials + childcare + savings
    gap = required - (net + support)
    gap_no_support = required - net
    shortfall = np.maximum(gap, 0.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        extra_gross_annual = np.where(tax < 1, shortfall * 12.0 / (1.0 - tax), np.inf)

    out = {
        "gross_monthly": gross,
        "effective_tax_rate": tax,
        "net_monthly": net,
        "personal_rent": rent,
        "loan_payment": loan,
        "essentials": essentials,
        "childcare": childcare,
        "savings_target": savings,
        "family_support": support,
        "rent_burden": rent_burden,
        "rent_affordable": rent_burden <= rent_burden_threshold,
        "monthly_balance": balance,
        "required_spending": required,
        "feasibility_gap": gap,
        "feasibility_gap_without_support": gap_no_support,
        "feasible_with_support": gap <= 0,
        "feasible_independent": gap_no_support <= 0,
        # Actionability: how much would close the shortfall (same $ either way)
        "required_additional_net_monthly": shortfall,
        "required_additional_gross_annual": extra_gross_annual,
    }
    return {k: _unwrap(v) for k, v in out.items()}


def break_even_salary(
    monthly_rent_total,
    roommates=0,
    debt_principal=0.0,
    annual_interest_rate=config.DEFAULT_LOAN_INTEREST_RATE,
    monthly_essentials=config.DEFAULT_MONTHLY_ESSENTIALS,
    monthly_savings_target=config.DEFAULT_MONTHLY_SAVINGS_TARGET,
    monthly_family_support=0.0,
    monthly_childcare=0.0,
    effective_tax_rate=None,
    tax_mode=None,
    loan_term_years=config.LOAN_TERM_YEARS,
):
    """Lowest gross annual salary with feasibility gap <= 0 (scalars or arrays).

    Flat tax: closed form 12 * need / (1 - t). Progressive tax: bisection,
    valid because net pay rises monotonically with gross pay.
    """
    need = (np.asarray(personal_rent_share(monthly_rent_total, roommates), float)
            + np.asarray(monthly_loan_payment(debt_principal, annual_interest_rate, loan_term_years), float)
            + monthly_essentials + monthly_childcare + monthly_savings_target - monthly_family_support)
    need = np.maximum(need, 0.0)
    mode = "flat" if effective_tax_rate is not None else (tax_mode or config.TAX_MODE)
    if mode == "flat":
        t = config.DEFAULT_EFFECTIVE_TAX_RATE if effective_tax_rate is None else effective_tax_rate
        return _unwrap(12.0 * need / (1.0 - t))
    lo = np.zeros_like(need)
    hi = np.full_like(need, 2_000_000.0)
    for _ in range(60):  # ~2e6 / 2^60: far below a cent
        mid = (lo + hi) / 2
        net = mid / 12 * (1 - np.asarray(estimate_effective_tax_rate(mid), float))
        short = net < need
        lo = np.where(short, mid, lo)
        hi = np.where(short, hi, mid)
    return _unwrap(hi)


# ---------------------------------------------------------------------------
# Checked single-scenario API (for the dashboard)
# ---------------------------------------------------------------------------
@dataclass
class ScenarioInputs:
    annual_salary: float
    monthly_rent_total: float
    roommates: int = 0
    debt_principal: float = 0.0
    annual_interest_rate: float = config.DEFAULT_LOAN_INTEREST_RATE
    effective_tax_rate: float | None = None  # None -> config.TAX_MODE
    monthly_essentials: float = config.DEFAULT_MONTHLY_ESSENTIALS
    monthly_savings_target: float = config.DEFAULT_MONTHLY_SAVINGS_TARGET
    monthly_family_support: float = 0.0
    monthly_childcare: float = 0.0
    loan_term_years: int = config.LOAN_TERM_YEARS
    warnings: list[str] = field(default_factory=list, repr=False)

    def validate(self) -> None:
        for name in ("annual_salary", "monthly_rent_total"):
            v = getattr(self, name)
            if v is None or (isinstance(v, float) and math.isnan(v)):
                raise MissingDataError(f"{name} is missing; this market combination has insufficient data.")
        _require(self.annual_salary > 0, "annual_salary must be > 0")
        _require(self.monthly_rent_total >= 0, "monthly_rent_total must be >= 0")
        _require(float(self.roommates).is_integer() and self.roommates >= 0, "roommates must be a non-negative integer")
        _require(self.debt_principal >= 0, "debt_principal must be >= 0")
        _require(0 <= self.annual_interest_rate < 1, "annual_interest_rate must be a decimal in [0, 1), e.g. 0.0639")
        if self.effective_tax_rate is not None:
            _require(0 <= self.effective_tax_rate < 1, "effective_tax_rate must be a decimal in [0, 1), e.g. 0.22")
        for name in ("monthly_essentials", "monthly_savings_target", "monthly_family_support", "monthly_childcare"):
            _require(getattr(self, name) >= 0, f"{name} must be >= 0")
        _require(self.loan_term_years > 0, "loan_term_years must be > 0")
        for name in ("annual_salary", "monthly_rent_total", "debt_principal"):
            _require(math.isfinite(getattr(self, name)), f"{name} must be finite")

        self.warnings = []
        if self.annual_salary < 1000:
            self.warnings.append("annual_salary looks like an hourly or monthly figure; enter ANNUAL salary.")
        if self.annual_interest_rate > 0.25:
            self.warnings.append("annual_interest_rate above 25%: did you enter a percentage instead of a decimal?")


def simulate(inputs: ScenarioInputs) -> dict[str, Any]:
    """Validate inputs and return the monthly budget plus any warnings."""
    inputs.validate()
    tax = resolve_tax_rate(inputs.annual_salary, inputs.effective_tax_rate)
    params = {k: v for k, v in asdict(inputs).items() if k != "warnings"}
    params["effective_tax_rate"] = tax
    result = compute_budget(**params)
    result = {k: (bool(v) if isinstance(v, (bool, np.bool_)) else float(v)) for k, v in result.items()}
    result["warnings"] = list(inputs.warnings)
    if result["rent_affordable"] and not result["feasible_independent"]:
        result["warnings"].append("Rent is 'affordable' by the 30% rule, but the full budget is still short.")
    return result


# ---------------------------------------------------------------------------
def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _unwrap(x):
    """Return a Python scalar for 0-d arrays, else the array unchanged."""
    arr = np.asarray(x)
    return arr.item() if arr.ndim == 0 else arr
