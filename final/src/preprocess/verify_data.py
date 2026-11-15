"""Independent verification of the shared processed datasets (read-only).

Checks whatever exists in data/processed/ and writes
outputs/verification_report.md. Never modifies the inputs.

    ../.venv/bin/python -B src/preprocess/verify_data.py [--dir data/processed]

Status levels: PASS · WARN (review by hand) · FAIL (likely bug) · SKIP (file/column absent)
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src import config  # noqa: E402
from src.analysis.equity_analysis import CANONICAL_COLUMNS, OPTIONAL_COLUMNS  # noqa: E402

# Plausibility bounds (WARN, not FAIL: they flag records for manual review)
ANNUAL_SALARY_RANGE = config.ANNUAL_PAY_RANGE
MONTHLY_RENT_RANGE = (500, 15_000)


@dataclass
class Check:
    file: str
    check: str
    status: str
    detail: str


def find(df: pd.DataFrame, *patterns: str) -> str | None:
    for p in patterns:
        rx = re.compile(p, re.I)
        for c in df.columns:
            if rx.fullmatch(str(c)) or rx.search(str(c)):
                return c
    return None


def canon(df: pd.DataFrame, name: str) -> str | None:
    aliases = {**CANONICAL_COLUMNS, **OPTIONAL_COLUMNS}.get(name, [name])
    lower = {c.lower(): c for c in df.columns}
    return next((lower[a] for a in aliases if a in lower), None)


def range_check(df, col, lo, hi, file, label) -> Check:
    v = pd.to_numeric(df[col], errors="coerce")
    n_missing = int(v.isna().sum())
    out = v[(v < lo) | (v > hi)]
    status = "PASS" if out.empty else ("FAIL" if (v <= 0).any() else "WARN")
    detail = (f"{len(out)} of {v.notna().sum()} values outside [{lo:,}, {hi:,}]"
              f"{'; examples ' + str(out.head(5).round(0).tolist()) if len(out) else ''}; {n_missing} missing")
    return Check(file, f"{label} plausible range ({col})", status, detail)


def check_jobs_clean(df, f) -> list[Check]:
    c = []
    c.append(Check(f, "exact duplicate rows", "PASS" if not df.duplicated().any() else "FAIL",
                   f"{int(df.duplicated().sum())} duplicates in {len(df)} rows"))
    sal = find(df, r"annual.*salary|salary.*annual|salary_annual|annualized_low")
    if sal:
        c.append(range_check(df, sal, *ANNUAL_SALARY_RANGE, f, "annualised salary"))
        hourly_like = pd.to_numeric(df[sal], errors="coerce").between(7, 200).sum()
        c.append(Check(f, "hourly values left unconverted", "PASS" if hourly_like == 0 else "FAIL",
                       f"{int(hourly_like)} annual-salary values between 7 and 200 (look like hourly pay)"))
        missing_share = pd.to_numeric(df[sal], errors="coerce").isna().mean()
        c.append(Check(f, "annual pay field coverage", "PASS",
                       f"{missing_share:.1%} missing in {sal}, including upper-bound-only and unannualized pay"))
        original_salary = find(df, r"salary_original")
        if original_salary:
            undisclosed = df[original_salary].fillna("").astype(str).str.strip().eq("")
            c.append(Check(f, "salary disclosure", "PASS",
                           f"{undisclosed.sum():,} of {len(df):,} postings ({undisclosed.mean():.1%}) have no salary text"))
    else:
        c.append(Check(f, "annual salary column", "SKIP", "no column matching 'annual salary'"))
    status = find(df, r"salary_status")
    if status:
        un = df[df[status].eq("unparsed")]
        orig = find(df, r"salary_original")
        spanish = int(un[orig].astype(str).str.contains("por hora|por año|por mes", case=False).sum()) if orig else 0
        c.append(Check(f, "unparsed salaries", "PASS" if len(un) == 0 else "WARN",
                       f"{len(un)} unparsed, {spanish} of them Spanish-language ('por hora/por año')"))
    deg = find(df, r"degree")
    if deg:
        vals = df[deg].astype(str).str.lower()
        no_deg = vals.str.contains("no|none|not required").mean()
        unknown = (vals.isin(["nan", "unknown", ""])).mean()
        c.append(Check(f, "degree requirement: unknown kept separate from 'none'",
                       "PASS" if unknown > 0 else "WARN",
                       f"unknown/missing {unknown:.1%}, 'no degree' {no_deg:.1%} (missing text must not become 'no degree')"))
    return c


def check_housing_clean(df, f) -> list[Check]:
    c = [Check(f, "exact duplicate rows", "PASS" if not df.duplicated().any() else "FAIL",
               f"{int(df.duplicated().sum())} duplicates in {len(df)} rows")]
    zp = find(df, r"zpid")
    if zp:
        d = int(df[zp].duplicated().sum())
        c.append(Check(f, "duplicate listing ids (zpid)", "PASS" if d == 0 else "WARN", f"{d} repeated zpid values"))
    rent = find(df, r"^price$", r"monthly.*rent|rent.*monthly|asking.*rent|^rent$")
    if rent:
        c.append(range_check(df, rent, *MONTHLY_RENT_RANGE, f, "monthly asking rent"))
    rz = find(df, r"rentzestimate")
    if rent and rz and rent != rz:
        same = (pd.to_numeric(df[rent], errors="coerce") == pd.to_numeric(df[rz], errors="coerce")).mean()
        c.append(Check(f, "listing rent kept separate from rentZestimate", "PASS" if same < 0.5 else "WARN",
                       f"{same:.1%} of rows have price == rentZestimate"))
    st = find(df, r"homestatus")
    if st:
        bad = (~df[st].astype(str).str.upper().eq("FOR_RENT")).sum()
        c.append(Check(f, "only FOR_RENT listings", "PASS" if bad == 0 else "FAIL", f"{int(bad)} rows not FOR_RENT"))
    return c


def check_summary(df, f, value_col_name, n_col_name, threshold, keys, value_range) -> list[Check]:
    c = []
    keycols = [canon(df, k) or find(df, k) for k in keys]
    if None in keycols:
        return [Check(f, "key columns", "FAIL", f"missing one of {keys}; found {list(df.columns)}")]
    dup = int(df.duplicated(keycols).sum())
    c.append(Check(f, f"unique keys {keys}", "PASS" if dup == 0 else "FAIL", f"{dup} duplicated key rows of {len(df)}"))
    val, n = canon(df, value_col_name), canon(df, n_col_name)
    if val:
        c.append(range_check(df[df[val].notna()], val, *value_range, f, value_col_name))
    if n:
        thin = df[pd.to_numeric(df[n], errors="coerce") < threshold]
        c.append(Check(f, f"{n_col_name} reported", "PASS", f"{len(thin)} of {len(df)} rows below threshold {threshold}"))
        flag = canon(df, "sufficient_data")
        if flag:
            fl = df[flag].astype(str).str.lower().isin(["true", "1", "yes"])
            wrong = int((fl & (pd.to_numeric(df[n], errors="coerce") < threshold)).sum())
            c.append(Check(f, "sufficient_data flag consistent with sample size",
                           "PASS" if wrong == 0 else "FAIL", f"{wrong} rows flagged sufficient but {n_col_name} < {threshold}"))
    return c


def check_market_combinations(df, f, jobs: pd.DataFrame | None, housing: pd.DataFrame | None) -> list[Check]:
    c = []
    missing = [k for k in CANONICAL_COLUMNS if canon(df, k) is None]
    c.append(Check(f, "contract columns (docs/DATA_CONTRACT.md)", "PASS" if not missing else "FAIL",
                   "all present" if not missing else f"missing {missing}"))
    if missing:
        return c
    col = {k: canon(df, k) for k in CANONICAL_COLUMNS}
    keys = [col["city"], col["occupation"], col["housing_type"]]
    dup = int(df.duplicated(keys).sum())
    c.append(Check(f, "one row per city x occupation x housing", "PASS" if dup == 0 else "FAIL",
                   f"{dup} duplicates (many-to-many join?) in {len(df)} rows"))
    per_pair = df.groupby([col["city"], col["occupation"]])[col["median_annual_salary"]].nunique()
    c.append(Check(f, "salary constant across housing rows of a pair", "PASS" if (per_pair <= 1).all() else "FAIL",
                   f"{int((per_pair > 1).sum())} pairs with differing salary"))
    per_rent = df.groupby([col["city"], col["housing_type"]])[col["median_monthly_rent"]].nunique()
    c.append(Check(f, "rent constant across occupations of a city x housing", "PASS" if (per_rent <= 1).all() else "FAIL",
                   f"{int((per_rent > 1).sum())} city x housing groups with differing rent"))
    thin_sal = pd.to_numeric(df[col["n_valid_salary"]], errors="coerce") < config.MIN_VALID_SALARY_POSTINGS
    thin_rent = pd.to_numeric(df[col["n_valid_rent"]], errors="coerce") < config.MIN_VALID_RENT_LISTINGS
    flag = canon(df, "sufficient_data")
    if flag:
        fl = df[flag].astype(str).str.lower().isin(["true", "1", "yes"])
        wrong = int((fl & (thin_sal | thin_rent)).sum())
        c.append(Check(f, "sufficient_data agrees with thresholds", "PASS" if wrong == 0 else "FAIL",
                       f"{wrong} rows marked sufficient despite thin samples"))
    c.append(Check(f, "coverage", "PASS",
                   f"{df[col['city']].nunique()} cities, {df[col['occupation']].nunique()} occupations, "
                   f"housing types {sorted(df[col['housing_type']].astype(str).unique())}; "
                   f"{int((~thin_sal & ~thin_rent).sum())} of {len(df)} rows pass both thresholds"))
    # Traceability back to the component summaries
    if jobs is not None:
        jc = {k: canon(jobs, k) for k in ("city", "occupation", "median_annual_salary")}
        if None not in jc.values():
            mg = df.merge(jobs[[*jc.values()]].rename(columns={v: f"j_{k}" for k, v in jc.items()}),
                          left_on=[col["city"], col["occupation"]], right_on=["j_city", "j_occupation"], how="left")
            diff = (mg[col["median_annual_salary"]] - mg["j_median_annual_salary"]).abs() > 0.5
            unmatched = mg["j_median_annual_salary"].isna() & mg[col["median_annual_salary"]].notna()
            c.append(Check(f, "salaries trace to job_market_summary", "PASS" if not (diff.any() or unmatched.any()) else "FAIL",
                           f"{int(diff.sum())} mismatched, {int(unmatched.sum())} with no source row"))
    if housing is not None:
        hc = {k: canon(housing, k) for k in ("city", "housing_type", "median_monthly_rent")}
        if None not in hc.values():
            h = housing[[*hc.values()]].rename(columns={v: f"h_{k}" for k, v in hc.items()})
            mg = df.merge(h, left_on=[col["city"], col["housing_type"]], right_on=["h_city", "h_housing_type"], how="left")
            diff = (mg[col["median_monthly_rent"]] - mg["h_median_monthly_rent"]).abs() > 0.5
            c.append(Check(f, "rents trace to housing_market_summary", "PASS" if not diff.any() else "FAIL",
                           f"{int(diff.sum())} mismatched"))
    return c


def check_college(df, f) -> list[Check]:
    c = []
    uid = find(df, r"unit.?id|unique_identification")
    if uid:
        d = int(df[uid].duplicated().sum())
        c.append(Check(f, "Unit ID unique", "PASS" if d == 0 else "FAIL", f"{d} duplicated IDs in {len(df)} rows"))
        frac = (pd.to_numeric(df[uid], errors="coerce") % 1 != 0).sum()
        c.append(Check(f, "Unit ID standardised to integer", "PASS" if frac == 0 else "WARN", f"{int(frac)} non-integer IDs"))
    debt = find(df, r"median.*debt.*complet|complet\w*_median_debt")
    c.append(Check(f, "'Median Debt of Completers' available for debt profiles", "PASS" if debt else "WARN",
                   debt or "not found: the analysis will fall back to PLACEHOLDER debt values"))
    bay = find(df, r"bay.?area|is_bay|in_bay")
    if bay:
        n = int(df[bay].astype(str).str.lower().isin(["true", "1", "yes"]).sum())
        c.append(Check(f, "Bay Area institutions identified", "PASS" if n >= 10 else "WARN", f"{n} institutions flagged ({bay})"))
    else:
        c.append(Check(f, "Bay Area flag", "WARN", "no Bay Area flag column found"))
    return c


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, default=config.PROCESSED_DIR)
    ap.add_argument("--out", type=Path, default=config.OUTPUT_DIR / "verification_report.md")
    args = ap.parse_args(argv)

    def load(name):
        p = args.dir / name
        return (pd.read_csv(p, low_memory=False), name) if p.exists() else (None, name)

    checks: list[Check] = []
    files = {n: load(n) for n in ["jobs_clean.csv", "housing_clean.csv", "college_clean.csv", "college_equity_summary.csv",
                                  "job_market_summary.csv", "housing_market_summary.csv", "market_combinations.csv",
                                  # preprocess.py naming
                                  "jobs_bay_area.csv", "rentals_bay_area.csv", "colleges.csv"]}
    # Skip whichever naming scheme is absent instead of reporting both as missing
    files = {n: v for n, v in files.items() if v[0] is not None} or files
    for name, (df, _) in files.items():
        if df is None:
            checks.append(Check(name, "file exists", "SKIP", f"not found in {args.dir}"))
            continue
        checks.append(Check(name, "file loads", "PASS", f"{len(df):,} rows x {df.shape[1]} cols"))
        if name in ("jobs_clean.csv", "jobs_bay_area.csv"):
            checks += check_jobs_clean(df, name)
        elif name in ("housing_clean.csv", "rentals_bay_area.csv"):
            checks += check_housing_clean(df, name)
        elif name.startswith("college") or name == "colleges.csv":
            checks += check_college(df, name)
        elif name == "job_market_summary.csv":
            checks += check_summary(df, name, "median_annual_salary", "n_valid_salary",
                                    config.MIN_VALID_SALARY_POSTINGS, ["city", "occupation"], ANNUAL_SALARY_RANGE)
        elif name == "housing_market_summary.csv":
            checks += check_summary(df, name, "median_monthly_rent", "n_valid_rent",
                                    config.MIN_VALID_RENT_LISTINGS, ["city", "housing_type"], MONTHLY_RENT_RANGE)
        elif name == "market_combinations.csv":
            checks += check_market_combinations(df, name, files["job_market_summary.csv"][0],
                                                files["housing_market_summary.csv"][0])

    rep = pd.DataFrame([c.__dict__ for c in checks])
    counts = rep["status"].value_counts().to_dict()
    md = ["# Processed-data verification report", "",
          f"Source directory: `{args.dir}` (read-only). Summary: {counts}", "",
          "| File | Check | Status | Detail |", "|---|---|---|---|"]
    md += [f"| {c.file} | {c.check} | **{c.status}** | {c.detail.replace('|', '/')} |" for c in checks]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(md) + "\n")
    print("\n".join(md))
    print(f"\nReport written to {args.out}")
    return 1 if counts.get("FAIL") else 0


if __name__ == "__main__":
    raise SystemExit(main())
