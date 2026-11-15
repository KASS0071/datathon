"""Summarize city opportunity, shortfall remedies, occupations and college costs.

All inputs are read-only (data/processed + earlier pipeline outputs); all writes go to
outputs/analysis/.

    ../.venv/bin/python -B src/analysis/summarize_results.py      (run after run_equity.py)
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src import config  # noqa: E402
from src.market.build_market_inputs import posting_pay_points  # noqa: E402
from src.analysis.equity_analysis import load_benchmarks  # noqa: E402
from src.budget.calculate_budget import break_even_salary, estimate_effective_tax_rate  # noqa: E402

OUT = config.OUTPUT_DIR / "analysis"


# ---------------------------------------------------------------------------
# RQ1: which advertised wages cover typical housing, city by city?
# ---------------------------------------------------------------------------
def city_opportunity(rents: pd.DataFrame, pay: pd.DataFrame, median_debt: float) -> pd.DataFrame:
    ok = rents[rents["n_valid_rent"] >= config.MIN_VALID_RENT_LISTINGS]
    wide = ok.pivot_table(index=["county", "city"], columns="housing_type",
                          values=["median_monthly_rent", "n_valid_rent"], aggfunc="first")
    wide.columns = [f"{a}_{b}" for a, b in wide.columns]
    wide = wide.dropna(subset=["median_monthly_rent_1br", "median_monthly_rent_2br"]).reset_index()

    r1, r2 = wide["median_monthly_rent_1br"].to_numpy(), wide["median_monthly_rent_2br"].to_numpy()
    wide["break_even_alone"] = break_even_salary(r1, 0)
    wide["break_even_alone_median_debt"] = break_even_salary(r1, 0, median_debt)
    wide["break_even_shared"] = break_even_salary(r2, 1)
    wide["salary_for_30pct_rent_alone"] = r1 * 12 / config.RENT_BURDEN_THRESHOLD

    p = pay["annual_pay"].to_numpy()
    for col, label in [("break_even_alone", "share_postings_independent_alone"),
                       ("break_even_alone_median_debt", "share_postings_independent_alone_median_debt"),
                       ("break_even_shared", "share_postings_independent_shared"),
                       ("salary_for_30pct_rent_alone", "share_postings_rent_affordable_alone")]:
        wide[label] = [(p >= v).mean() for v in wide[col]]
    wide["n_postings"] = len(p)
    wide["posting_pay_median"] = float(np.median(p))
    return wide.sort_values("break_even_alone", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Actionability: how much would close a typical shortfall?
# ---------------------------------------------------------------------------
def actionability(results: pd.DataFrame) -> pd.DataFrame:
    short = results[results["feasibility_gap"] > 0].copy()
    short["raise_pct_needed"] = short["required_additional_gross_annual"] / short["median_annual_salary"]
    short["rent_cut_pct_needed"] = short["feasibility_gap"] / short["personal_rent"]
    short["closed_by_zero_loan"] = short["loan_payment"] >= short["feasibility_gap"]
    all_n = results.groupby("profile", sort=False).size()
    g = short.groupby("profile", sort=False)
    out = pd.DataFrame({
        "n_combinations": all_n,
        "n_short": g.size(),
        "median_monthly_shortfall": g["feasibility_gap"].median(),
        "median_extra_gross_salary": g["required_additional_gross_annual"].median(),
        "median_raise_pct_needed": g["raise_pct_needed"].median(),
        "median_rent_cut_pct_needed": g["rent_cut_pct_needed"].median(),
        "share_closed_by_eliminating_loan": g["closed_by_zero_loan"].mean(),
    }).reindex(all_n.index)
    out["n_short"] = out["n_short"].fillna(0).astype(int)
    return out.reset_index().rename(columns={"index": "profile"})


# ---------------------------------------------------------------------------
# College: Bay Area vs California (non-Bay) vs national, four-year only
# ---------------------------------------------------------------------------
def college_comparison(colleges: pd.DataFrame, afford: pd.DataFrame) -> pd.DataFrame:
    c = colleges.copy()
    c["group"] = np.select([c["is_bay_area"] == 1, c["state"] == "CA"],
                           ["Bay Area", "California (non-Bay)"], "National (other states)")
    four = c[c["institution_type_2021"].astype(str).str.contains(config.DEBT_INSTITUTION_TYPE_PATTERN, case=False)]
    rows = []
    metrics = {
        "completer_median_debt_2021_usd": "Median debt of completers (2021)",
        "graduation_rate_6yr_2021_pct": "6-year graduation rate, % (2021)",
        "median_earnings_10yr_after_entry_2021_usd": "Median earnings 10 yrs after entry (2021)",
        "low_income_net_price_2020_21_usd": "Net price, low-income students (2020-21)",
    }
    for col, label in metrics.items():
        # Guard: the raw "Median Earnings ... 10 Years After Entry" column has only
        # 3 distinct values across ~6,000 institutions (a source defect), so any
        # metric that is effectively categorical is skipped rather than reported.
        if pd.to_numeric(c[col], errors="coerce").nunique() < 20:
            print(f"SKIPPED {col}: only {pd.to_numeric(c[col], errors='coerce').nunique()} distinct values (source defect)")
            continue
        for grp, d in four.groupby("group"):
            v = pd.to_numeric(d[col], errors="coerce").dropna()
            rows.append({"metric": label, "source_column": col, "family_income_ceiling_usd": np.nan,
                         "group": grp, "n_institutions": len(v), "median": v.median() if len(v) else np.nan})
    a = afford.merge(c[["unit_id", "group", "institution_type_2021"]], on="unit_id", how="left")
    a = a[a["institution_type_2021"].astype(str).str.contains(config.DEBT_INSTITUTION_TYPE_PATTERN, case=False)]
    for col, label in {"net_price_2022_23_usd": "Net price by family income (2022-23)",
                       "affordability_gap_2022_23_usd": "Affordability gap by family income (2022-23)"}.items():
        for (grp, band), d in a.groupby(["group", "family_income_ceiling_usd"]):
            v = pd.to_numeric(d[col], errors="coerce").dropna()
            rows.append({"metric": label, "source_column": col, "family_income_ceiling_usd": band,
                         "group": grp, "n_institutions": len(v), "median": v.median() if len(v) else np.nan})
    out = pd.DataFrame(rows)
    out["scope"] = "four-year institutions; unweighted median of institution values"
    return out


KEY_PROFILES = {
    "none_debt | alone | no_support": "alone_no_debt",
    "median_debt | alone | no_support": "alone_median_debt",
    "none_debt | shared | no_support": "shared_no_debt",
    "student_parent (median_debt, 2br, childcare) | no_support": "student_parent",
}


def occupation_barrier(results: pd.DataFrame, pay_definition: str) -> pd.DataFrame:
    """Barrier Index per occupation for key profiles (independence, no support).
    Denominator = that occupation's eligible cities (same for every profile)."""
    r = results[results["profile"].isin(KEY_PROFILES)].copy()
    r["key"] = r["profile"].map(KEY_PROFILES)
    g = r.groupby(["occupation", "key"])
    wide = (1 - g["feasible"].mean()).unstack("key").add_prefix("barrier_")
    gap = g["feasibility_gap"].median().unstack("key").add_prefix("median_gap_")
    base = r[r["key"] == "alone_no_debt"].groupby("occupation")
    out = wide.join(gap)
    out.insert(0, "n_cities", base.size())
    out.insert(1, "median_salary", base["median_annual_salary"].median())
    out["pay_definition"] = pay_definition
    return out.reset_index().sort_values("median_salary")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rents = pd.read_csv(config.BUILT_MARKET_FILE.parent / "rent_by_city_housing.csv")
    pay = posting_pay_points(pd.read_csv(config.JOBS_FILE))
    bm = load_benchmarks()
    results = pd.read_csv(config.OUTPUT_DIR / "equity" / "combination_results.csv")

    opp = city_opportunity(rents, pay, bm.median_debt)
    act = actionability(results)
    col = college_comparison(pd.read_csv(config.COLLEGES_FILE, low_memory=False),
                             pd.read_csv(config.COLLEGE_AFFORDABILITY_FILE))
    occ = pd.concat([
        occupation_barrier(results, "city x occupation median, non-senior postings"),
        occupation_barrier(pd.read_csv(config.OUTPUT_DIR / "equity_entry_signal" / "combination_results.csv"),
                           "Bay-Area-wide entry-level-signal median"),
    ], ignore_index=True)
    occ.to_csv(OUT / "occupation_barrier.csv", index=False)
    opp.to_csv(OUT / "city_opportunity.csv", index=False)
    act.to_csv(OUT / "actionability.csv", index=False)
    col.to_csv(OUT / "college_comparison.csv", index=False)

    fmt = lambda df: df.to_string(index=False, float_format=lambda x: f"{x:,.2f}")  # noqa: E731
    print(f"RQ1: {len(opp)} cities; {len(pay)} postings (median ${np.median(pay.annual_pay):,.0f}); "
          f"effective tax at median pay {estimate_effective_tax_rate(np.median(pay.annual_pay)):.1%}")
    print(fmt(opp[["city", "median_monthly_rent_1br", "break_even_alone", "break_even_shared",
                   "share_postings_independent_alone", "share_postings_independent_shared"]].head(8)))
    print("...\n" + fmt(opp[["city", "median_monthly_rent_1br", "break_even_alone", "break_even_shared",
                            "share_postings_independent_alone", "share_postings_independent_shared"]].tail(5)))
    print("\nOccupation barrier:\n" + fmt(occ[["pay_definition", "occupation", "n_cities", "median_salary",
                                              "barrier_alone_no_debt", "barrier_shared_no_debt", "barrier_student_parent"]]))
    print("\nActionability:\n" + fmt(act))
    print("\nCollege (four-year):\n" + fmt(col[col.family_income_ceiling_usd.isna()][["metric", "group", "n_institutions", "median"]]))
    print(fmt(col[(col.metric.str.startswith("Net price by")) ][["group", "family_income_ceiling_usd", "n_institutions", "median"]]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
