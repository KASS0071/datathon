"""Build market inputs from the processed data (config.PROCESSED_DIR).

Two designs (config.MARKET_MODE):

* "city_occupation" (default, full Indeed file): median advertised pay of
  non-senior, non-part-time-only postings per city x occupation group
  (src/market/classify_occupations.py), crossed with that city's rents. A cell needs
  >= MIN_VALID_SALARY_POSTINGS distinct postings; nothing is imputed.
* "pay_levels" (fallback for the 1,000-row sample): Bay-Area-wide P25/P50/P75
  pay levels crossed with city rents; salary does not vary by city.

Annual pay is recomputed here from salary_low/high_usd and salary_unit so that
it does not depend on the upstream plausibility blanking:
  hour x 2,080 · week x 52 · month x 12 · year x 1; day/other excluded;
  hourly amounts > MAX_HOURLY_AMOUNT are treated as unit errors (annual salary
  typed into the hourly field) and excluded; annual pay must lie in
  ANNUAL_PAY_RANGE. Likely reposts (same title, company, city, salary text)
  are counted once.

Output (under outputs/, never data/):
    outputs/market_inputs/market_combinations.csv   (CONTRACT.md format)
    outputs/market_inputs/salary_by_city_occupation.csv
    outputs/market_inputs/salary_by_occupation.csv  (incl. entry-level-signal variant)
    outputs/market_inputs/salary_levels.csv
    outputs/market_inputs/rent_by_city_housing.csv

    ../.venv/bin/python -B src/market/build_market_inputs.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src import config  # noqa: E402
from src.market.classify_occupations import UNCLASSIFIED, classify  # noqa: E402

BEDROOM_LABEL = {0: "studio", 1: "1br", 2: "2br", 3: "3br"}
SALARY_LEVELS = {"pay_P25": 0.25, "pay_P50": 0.50, "pay_P75": 0.75}


UNIT_FACTOR = {"hour": 2080, "week": 52, "month": 12, "year": 1}


def posting_pay_points(jobs: pd.DataFrame) -> pd.DataFrame:
    """One annual pay figure per posting (midpoint of a range, else the single
    stated bound). Excludes senior / 3+ years signals, part-time-only postings
    (hourly pay is annualised at 2,080 h), unsupported periods, unit errors,
    implausible amounts and likely reposts. Adds an `occupation` column."""
    j = jobs[jobs["salary_status"].eq("parsed")].copy()
    j = j[~j["entry_signal"].eq("senior_or_3plus_years_signal")]
    types = j["job_type"].fillna("").astype(str).str.lower()
    j = j[~(types.str.contains("part-time") & ~types.str.contains("full-time"))]
    factor = pd.to_numeric(j["salary_unit"].map(UNIT_FACTOR), errors="coerce").astype(float)
    lo_amt = pd.to_numeric(j["salary_low_usd"], errors="coerce")
    hi_amt = pd.to_numeric(j["salary_high_usd"], errors="coerce")
    unit_error = j["salary_unit"].eq("hour") & (hi_amt.fillna(lo_amt) > config.MAX_HOURLY_AMOUNT)
    lo, hi = lo_amt * factor, hi_amt * factor
    j["annual_pay"] = np.where(lo.notna() & hi.notna(), (lo + hi) / 2, lo.fillna(hi))
    j["pay_basis"] = np.where(lo.notna() & hi.notna(), "range_midpoint", "single_bound")
    a, b = config.ANNUAL_PAY_RANGE
    j = j[factor.notna() & ~unit_error & j["annual_pay"].between(a, b)]
    j = j.drop_duplicates(["job_title", "company", "city", "salary_original"])
    j["occupation"] = classify(j["job_title"])
    return j


def salary_levels(pay: pd.DataFrame) -> pd.DataFrame:
    n = len(pay)
    rows = [{"salary_level": k, "quantile": q, "annual_pay_usd": round(float(pay["annual_pay"].quantile(q)), -2),
             "n_valid_salary": n} for k, q in SALARY_LEVELS.items()]
    return pd.DataFrame(rows)


def rent_table(rentals: pd.DataFrame) -> pd.DataFrame:
    lo, hi = config.RENT_PLAUSIBLE_RANGE
    r = rentals.copy()
    r["bedrooms"] = pd.to_numeric(r["bedrooms"], errors="coerce")
    r = r[r["bedrooms"].isin(BEDROOM_LABEL)]
    r = r[~r["home_type"].astype(str).str.upper().str.contains("ROOM")]
    r = r[r["monthly_rent_usd"].between(lo, hi)]
    r["housing_type"] = r["bedrooms"].astype(int).map(BEDROOM_LABEL)
    # Conservative sample size: count distinct unit signatures, because ~24% of
    # listings repeat city/zip/beds/baths/rent/type (likely one building).
    sig = ["zipcode", "bedrooms", "bathrooms", "monthly_rent_usd", "home_type"]
    # A few postal cities straddle county lines (e.g. 94303 "Palo Alto" in San
    # Mateo County); group by postal city and label it with its modal county.
    r["county"] = r.groupby("city")["county"].transform(lambda s: s.mode().iat[0])
    g = r.groupby(["county", "city", "housing_type"])
    out = g.agg(
        median_monthly_rent=("monthly_rent_usd", "median"),
        rent_q1=("monthly_rent_usd", lambda s: s.quantile(0.25)),
        rent_q3=("monthly_rent_usd", lambda s: s.quantile(0.75)),
        n_listings=("monthly_rent_usd", "size"),
    )
    out["n_valid_rent"] = g.apply(lambda d: len(d.drop_duplicates(sig)), include_groups=False)
    return out.reset_index()


def _quantiles(g, col="annual_pay"):
    return g.agg(median_annual_salary=(col, "median"), salary_q1=(col, lambda x: x.quantile(0.25)),
                 salary_q3=(col, lambda x: x.quantile(0.75)), n_valid_salary=(col, "size"))


def salary_by_occupation(pay: pd.DataFrame) -> pd.DataFrame:
    """Bay-Area-wide pay per occupation, all non-senior vs entry-level signal only."""
    allp = _quantiles(pay.groupby("occupation")).add_suffix("_all")
    entry = _quantiles(pay[pay["entry_signal"].str.startswith("entry_")].groupby("occupation")).add_suffix("_entry_signal")
    return allp.join(entry, how="left").reset_index().sort_values("median_annual_salary_all")


def main() -> int:
    jobs = pd.read_csv(config.JOBS_FILE, low_memory=False)
    rentals = pd.read_csv(config.RENTALS_FILE, low_memory=False)
    pay = posting_pay_points(jobs)
    levels = salary_levels(pay)
    rents = rent_table(rentals)
    assert not rents.duplicated(["city", "housing_type"]).any(), "city x housing_type must be unique"
    out = config.BUILT_MARKET_FILE.parent
    out.mkdir(parents=True, exist_ok=True)

    by_occ = salary_by_occupation(pay)
    classified = pay[pay["occupation"] != UNCLASSIFIED]
    cell = _quantiles(classified.groupby(["city", "occupation"])).reset_index()

    if config.MARKET_MODE == "city_occupation":
        salary = cell
        definition = ("Median advertised annual pay of non-senior, non-part-time-only Indeed postings "
                      "in this city and occupation group (not entry-level-verified)")
    elif config.MARKET_MODE == "pay_levels":
        salary = levels.rename(columns={"salary_level": "occupation", "annual_pay_usd": "median_annual_salary"})
        definition = "Bay-Area-wide advertised pay level of non-senior Indeed postings (not entry-level-verified)"
    else:
        raise ValueError(f"Unknown MARKET_MODE {config.MARKET_MODE!r}")

    on = ["city"] if "city" in salary.columns else None
    market = rents.merge(salary, on=on, how="inner") if on else rents.merge(salary, how="cross")
    market["salary_definition"] = definition
    market["sufficient_data"] = (market["n_valid_salary"] >= config.MIN_VALID_SALARY_POSTINGS) & \
                                (market["n_valid_rent"] >= config.MIN_VALID_RENT_LISTINGS)
    cols = ["county", "city", "occupation", "housing_type", "median_annual_salary", "n_valid_salary",
            "median_monthly_rent", "rent_q1", "rent_q3", "n_valid_rent", "n_listings", "sufficient_data",
            "salary_definition"]
    market[cols].to_csv(config.BUILT_MARKET_FILE, index=False)

    # Entry-level variant: Bay-Area-wide median of postings with an entry-level
    # signal, per occupation (>= MIN_VALID_SALARY_POSTINGS), crossed with city rents.
    e = by_occ[(by_occ["occupation"] != UNCLASSIFIED)].rename(columns={
        "median_annual_salary_entry_signal": "median_annual_salary", "n_valid_salary_entry_signal": "n_valid_salary"})
    e = e[["occupation", "median_annual_salary", "n_valid_salary"]].dropna()
    entry = rents.merge(e, how="cross")
    entry["salary_definition"] = ("Bay-Area-wide median advertised pay of postings with an entry-level signal "
                                  "in this occupation group; salary does not vary by city")
    entry["sufficient_data"] = (entry["n_valid_salary"] >= config.MIN_VALID_SALARY_POSTINGS) & \
                               (entry["n_valid_rent"] >= config.MIN_VALID_RENT_LISTINGS)
    entry[cols].to_csv(config.BUILT_MARKET_ENTRY_FILE, index=False)
    levels.to_csv(out / "salary_levels.csv", index=False)
    rents.to_csv(out / "rent_by_city_housing.csv", index=False)
    cell.to_csv(out / "salary_by_city_occupation.csv", index=False)
    by_occ.to_csv(out / "salary_by_occupation.csv", index=False)

    unmatched = sorted(set(cell["city"]) - set(rents["city"]))
    print(f"Mode: {config.MARKET_MODE}")
    print(f"Pay points: {len(pay):,} postings (non-senior, not part-time-only, plausible, reposts removed); "
          f"{(pay.occupation == UNCLASSIFIED).mean():.1%} unclassified")
    print(levels.to_string(index=False))
    ok_cells = cell[cell.n_valid_salary >= config.MIN_VALID_SALARY_POSTINGS]
    print(f"City x occupation cells with >= {config.MIN_VALID_SALARY_POSTINGS} salaries: {len(ok_cells)} of {len(cell)} "
          f"({ok_cells.city.nunique()} cities, {ok_cells.occupation.nunique()} occupations)")
    if unmatched:
        print(f"Job cities with no rent data ({len(unmatched)}): {unmatched[:12]}")
    print(f"Wrote {config.BUILT_MARKET_FILE} ({len(market):,} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
