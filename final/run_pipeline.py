"""Rebuild every output in one command (run from the final/ folder).

    python run_pipeline.py                 # analysis from data/processed
    python run_pipeline.py --preprocess    # first rebuild data/processed from data/raw (needs the raw files)

Order: verify inputs -> market inputs -> equity analysis -> summary tables ->
figures (visualization/figures) and a saved configuration of the model inputs.
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from src import config  # noqa: E402



def step(title, fn, *args):
    print(f"\n=== {title} ===", flush=True)
    rc = fn(*args)
    if rc not in (0, None):
        raise SystemExit(f"{title} failed with code {rc}")


def main() -> int:
    if "--preprocess" in sys.argv[1:]:
        import subprocess
        print("\n=== Preprocess data/raw -> data/processed ===", flush=True)
        clean_data = Path(__file__).resolve().parent / "src/preprocess/clean_data.py"
        subprocess.run([sys.executable, "-B", str(clean_data)], check=True)
    from src.analysis import run_equity, summarize_results
    from src.analysis.equity_analysis import load_benchmarks
    from src.market import build_market_inputs
    from src.preprocess import verify_data
    from visualization import make_figures

    step("Verify data/processed", verify_data.main, [])
    step("Build market inputs", build_market_inputs.main)
    step("Equity analysis", run_equity.main, [])
    step("Equity analysis: entry-level-signal pay variant", run_equity.main,
         ["--input", str(config.BUILT_MARKET_ENTRY_FILE), "--out-name", "equity_entry_signal"])
    step("Summarize results", summarize_results.main)
    step("Figures", make_figures.main)

    out = config.OUTPUT_DIR
    out.mkdir(parents=True, exist_ok=True)
    bm = load_benchmarks()
    assumptions = {
        "_note": "Budget values identified as scenario parameters are project choices. See docs/ASSUMPTIONS.md.",
        "tax_mode": config.TAX_MODE,
        "tax_description": "approximate 2025 single filer: federal + CA income tax + FICA + CA SDI, standard deduction, no credits",
        "loan_interest_rate": config.DEFAULT_LOAN_INTEREST_RATE,
        "loan_interest_source": "2025-26 federal Direct Loan undergraduate rate",
        "loan_term_years": config.LOAN_TERM_YEARS,
        "monthly_essentials": {"value": config.DEFAULT_MONTHLY_ESSENTIALS, "source": "Project scenario parameter. See docs/ASSUMPTIONS.md."},
        "monthly_savings_target": {"value": config.DEFAULT_MONTHLY_SAVINGS_TARGET, "source": "Project savings target. See docs/ASSUMPTIONS.md."},
        "family_support_monthly": {"value": config.FAMILY_SUPPORT_MONTHLY, "source": "Project support scenario. See docs/ASSUMPTIONS.md."},
        "rent_burden_threshold": config.RENT_BURDEN_THRESHOLD,
        "min_valid_salary_postings": config.MIN_VALID_SALARY_POSTINGS,
        "min_valid_rent_listings": config.MIN_VALID_RENT_LISTINGS,
        "rent_plausible_range": list(config.RENT_PLAUSIBLE_RANGE),
        "housing": {"alone": config.HOUSING_ALONE, "shared": config.HOUSING_SHARED, "student_parent": config.HOUSING_PARENT},
        "benchmarks": asdict(bm),
    }
    (out / "assumptions.json").write_text(json.dumps(assumptions, indent=2) + "\n")
    print(f"\n=== Analysis tables, figures and assumptions in {out} ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
