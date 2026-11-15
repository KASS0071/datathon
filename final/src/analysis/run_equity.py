"""Run the Stage 5 equity analysis and write CSVs + a short markdown summary.

    python src/analysis/run_equity.py                # real data/processed input
    python src/analysis/run_equity.py --fixture      # FAKE fixture, for testing
    python src/analysis/run_equity.py --input path/to/market_combinations.csv
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src import config  # noqa: E402
from src.analysis.equity_analysis import load_benchmarks, load_market_combinations, run_all  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", type=Path, help="market_combinations.csv path")
    ap.add_argument("--college", type=Path, help="college summary with 'Median Debt of Completers'")
    ap.add_argument("--fixture", action="store_true", help="use the FAKE fixture (outputs go to outputs/FAKE_fixture)")
    ap.add_argument("--out-name", default="equity", help="output folder name under outputs/ (default: equity)")
    args = ap.parse_args(argv)

    if args.fixture:
        market_path, out_dir = config.FAKE_MARKET_FIXTURE, config.OUTPUT_DIR / "FAKE_fixture"
    else:
        default = config.MARKET_COMBINATIONS_FILE if config.MARKET_COMBINATIONS_FILE.exists() else config.BUILT_MARKET_FILE
        market_path, out_dir = args.input or default, config.OUTPUT_DIR / args.out_name

    market, src = load_market_combinations(market_path)
    bm = load_benchmarks(args.college)
    outputs = run_all(market, bm)

    out_dir.mkdir(parents=True, exist_ok=True)
    for name, df in outputs.items():
        df.to_csv(out_dir / f"{name}.csv", index=False)

    log = outputs["eligibility_log"]
    table = outputs["equity_table"]
    fmt = lambda df: df.to_string(index=False, float_format=lambda x: f"{x:,.3f}")  # noqa: E731
    lines = [
        "# Equity analysis summary" + (" — FAKE FIXTURE DATA, NOT FINDINGS" if args.fixture else ""),
        "",
        f"- Market input: `{src}`",
        f"- Eligible city x occupation combinations: **{int(log['eligible'].sum())} of {len(log)}** "
        f"(thresholds: >= {config.MIN_VALID_SALARY_POSTINGS} salaries, >= {config.MIN_VALID_RENT_LISTINGS} rents per housing type)",
        f"- Debt benchmarks: median ${bm.median_debt:,.0f}, high ${bm.high_debt:,.0f} — {bm.debt_source}",
        f"- Childcare: ${bm.monthly_childcare:,.0f}/mo — {bm.childcare_source}",
        f"- Tax mode: {config.TAX_MODE}; essentials ${config.DEFAULT_MONTHLY_ESSENTIALS:,.0f}/mo; "
        f"savings target ${config.DEFAULT_MONTHLY_SAVINGS_TARGET:,.0f}/mo; family support ${config.FAMILY_SUPPORT_MONTHLY:,.0f}/mo",
        "- Barrier Index = share of the SAME modeled combinations that fail the standard. "
        "It is not the share of real graduates who cannot live independently.",
        "",
        "## Exclusions", "```", fmt(log[~log["eligible"]]) if (~log["eligible"]).any() else "none", "```",
        "## Equity table", "```",
        fmt(table[["profile", "n_combinations", "n_feasible", "feasibility_rate", "barrier_index", "median_feasibility_gap"]]),
        "```",
        "## What changes outcomes most (one change from baseline)", "```", fmt(outputs["factor_effects"]), "```",
        "## Same job, different starting conditions", "```",
        fmt(outputs["same_job_different_start"][["profile", "net_monthly", "family_support", "personal_rent",
                                                 "loan_payment", "childcare", "monthly_balance", "feasibility_gap"]]),
        "```",
    ]
    (out_dir / "SUMMARY.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"\nWrote {len(outputs)} CSVs + SUMMARY.md to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
