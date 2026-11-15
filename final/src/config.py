"""Central assumptions and paths for the simulator and equity analysis.

Every number here is an ASSUMPTION, not a finding. Each one is labelled with
its source or marked PLACEHOLDER so the dashboard and report can disclose it.
Change values here only; nothing else in src/ hard-codes them.
"""
from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------
# Paths (processed data is read-only; all writes go to outputs/)
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]   # the project folder (final/)
VER2_DIR = PROJECT_DIR = ROOT                # legacy names kept for compatibility
# Processed data: <DATATHON_DATA_DIR or ROOT/data>/processed. VER2_PROCESSED_DIR
# (legacy) can still point directly at a processed folder.
import os as _os
PROCESSED_DIR = Path(_os.environ.get("VER2_PROCESSED_DIR",
                     Path(_os.environ.get("DATATHON_DATA_DIR", PROJECT_DIR / "data")) / "processed")).resolve()
OUTPUT_DIR = ROOT / "outputs"
FIXTURE_DIR = ROOT / "tests" / "fixtures"

MARKET_COMBINATIONS_FILE = PROCESSED_DIR / "market_combinations.csv"
COLLEGE_EQUITY_FILE = PROCESSED_DIR / "college_equity_summary.csv"
FAKE_MARKET_FIXTURE = FIXTURE_DIR / "market_combinations_FAKE.csv"

# Processed inputs written by src/preprocess/clean_data.py (see data/processed/MANIFEST.md)
COLLEGES_FILE = PROCESSED_DIR / "colleges.csv"
COLLEGE_AFFORDABILITY_FILE = PROCESSED_DIR / "college_affordability_by_income.csv"
JOBS_FILE = PROCESSED_DIR / "jobs_bay_area.csv"
RENTALS_FILE = PROCESSED_DIR / "rentals_bay_area.csv"
# Market inputs built by src/market/build_market_inputs.py (pipeline output)
BUILT_MARKET_FILE = OUTPUT_DIR / "market_inputs" / "market_combinations.csv"
BUILT_MARKET_ENTRY_FILE = OUTPUT_DIR / "market_inputs" / "market_combinations_entry_signal.csv"

# ---------------------------------------------------------------------------
# Sample-size reliability thresholds (pipeline Stage 3, provisional)
# ---------------------------------------------------------------------------
MIN_VALID_SALARY_POSTINGS = 10

# Market design: "city_occupation" (full Indeed file) or "pay_levels" (sample fallback)
MARKET_MODE = "city_occupation"
# Annual pay plausibility for individual postings (wide on purpose: Bay Area
# physicians and senior engineers legitimately exceed $400k).
ANNUAL_PAY_RANGE = (15_000.0, 1_000_000.0)
# Hourly amounts above this are annual salaries typed into the hourly field.
MAX_HOURLY_AMOUNT = 500.0
MIN_VALID_RENT_LISTINGS = 20

# ---------------------------------------------------------------------------
# Loan assumptions
# ---------------------------------------------------------------------------
LOAN_TERM_YEARS = 10  # Standard federal repayment plan
# 2025-26 federal Direct Loan rate for undergraduates (studentaid.gov).
DEFAULT_LOAN_INTEREST_RATE = 0.0639

# ---------------------------------------------------------------------------
# Tax assumptions
# ---------------------------------------------------------------------------
# "flat": use DEFAULT_EFFECTIVE_TAX_RATE for every salary.
# "progressive": estimate an effective rate per salary with
#   simulator.estimate_effective_tax_rate (approximate 2025 single filer,
#   standard deduction, federal + CA income tax + FICA + CA SDI, no credits).
TAX_MODE = "progressive"
DEFAULT_EFFECTIVE_TAX_RATE = 0.22  # PLACEHOLDER flat rate, ~ $70k CA single filer

# ---------------------------------------------------------------------------
# Living-cost assumptions (monthly, USD, excluding rent and loan)
# ---------------------------------------------------------------------------
# Scenario baseline covering basic expenses separate from rent and childcare.
# See docs/ASSUMPTIONS.md for scope and external methodological references.
DEFAULT_MONTHLY_ESSENTIALS = 1500.0
# Scenario savings target used in the feasibility standard.
DEFAULT_MONTHLY_SAVINGS_TARGET = 250.0
# Plausibility window for individual listing rents (outside -> excluded)
RENT_PLAUSIBLE_RANGE = (500.0, 15000.0)
# Rent-burden affordability standard (HUD convention: <= 30% of gross income).
RENT_BURDEN_THRESHOLD = 0.30

# ---------------------------------------------------------------------------
# Equity-profile assumptions
# ---------------------------------------------------------------------------
# Cash transfer used in the assisted scenario.
FAMILY_SUPPORT_MONTHLY = 500.0

# Housing arrangements, expressed as (housing_type, number_of_roommates).
# Living alone = 1-bedroom with nobody else; shared = 2-bedroom split 2 ways.
# Student parent = 2-bedroom (parent + child), not shared with roommates.
HOUSING_ALONE = ("1br", 0)
HOUSING_SHARED = ("2br", 1)
HOUSING_PARENT = ("2br", 0)

# Fallback debt benchmarks used ONLY if college_equity_summary.csv is absent.
# These are PLACEHOLDERS. The real values must come from the College Results
# column "Median Debt of Completers" across Bay Area institutions:
#   median_debt = median of institutional medians
#   high_debt   = 75th percentile of institutional medians
# They are institution-level benchmarks, NOT individual debt percentiles.
# New bachelor's graduates: restrict debt benchmarks to four-year institutions
# (all Bay Area types mixed gives $13,000; four-year only gives ~$20,400).
DEBT_INSTITUTION_TYPE_PATTERN = "Four-Year"
FALLBACK_MEDIAN_DEBT = 20000.0
FALLBACK_HIGH_DEBT = 27000.0

# Fallback childcare cost used ONLY if the college summary lacks it.
# Real value should come from Affordability Gap "Adjusted Monthly Center-Based
# Child Care Cost" for Bay Area institutions. PLACEHOLDER.
FALLBACK_MONTHLY_CHILDCARE = 1800.0

# ---------------------------------------------------------------------------
# Sensitivity analysis ranges (one-at-a-time around the reference profile)
# ---------------------------------------------------------------------------
SENSITIVITY = {
    "flat_tax_rate": [0.17, 0.22, 0.27, 0.30],
    "rent_multiplier": [0.90, 1.00, 1.10, 1.20],
    "essentials_multiplier": [0.80, 1.00, 1.20],
    "debt_multiplier": [0.0, 0.5, 1.0, 1.5, 2.0],
    "interest_rate": [0.0, 0.04, 0.0639, 0.08],
}
