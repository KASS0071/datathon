"""Equity & Barrier Index analysis (pipeline Stage 5).

Runs every financial-starting-condition profile over the SAME set of eligible
city x occupation combinations, so feasibility rates share one denominator.

Findings describe SIMULATED MARKET COMBINATIONS, not shares of real graduates.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from src import config
from src.budget.calculate_budget import compute_budget, estimate_effective_tax_rate

# ---------------------------------------------------------------------------
# Input contract (see docs/DATA_CONTRACT.md). Aliases let us accept reasonable
# alternative column names from the processing pipeline without editing it.
# ---------------------------------------------------------------------------
CANONICAL_COLUMNS = {
    "city": ["city", "city_norm", "city_clean"],
    "occupation": ["occupation", "occupation_group", "job_category", "occupation_category"],
    "housing_type": ["housing_type", "bedroom_type", "unit_type", "bedrooms_group"],
    "median_annual_salary": ["median_annual_salary", "median_salary", "salary_median", "median_salary_annual"],
    "n_valid_salary": ["n_valid_salary", "valid_salary_count", "salary_count", "n_salary"],
    "median_monthly_rent": ["median_monthly_rent", "median_rent", "rent_median", "median_asking_rent"],
    "n_valid_rent": ["n_valid_rent", "valid_rent_count", "rent_count", "n_rent"],
}
OPTIONAL_COLUMNS = {"sufficient_data": ["sufficient_data", "is_sufficient", "sufficient", "meets_threshold"]}

_HOUSING_PATTERNS = [
    (r"^(studio|0\s*(br|bd|bed|bedroom)s?|0)$", "studio"),
    (r"^(1\s*(br|bd|bed|bedroom)s?|1|one.?bed\w*)$", "1br"),
    (r"^(2\s*(br|bd|bed|bedroom)s?|2|two.?bed\w*)$", "2br"),
    (r"^(3\s*(br|bd|bed|bedroom)s?|3|three.?bed\w*)$", "3br"),
]


def normalize_housing_type(value) -> str:
    s = str(value).strip().lower().replace("-", " ").replace("_", " ")
    s = re.sub(r"\.0$", "", s)
    for pattern, label in _HOUSING_PATTERNS:
        if re.match(pattern, s):
            return label
    return s


def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    lower = {c.lower().strip(): c for c in df.columns}
    rename, missing = {}, []
    for canon, aliases in {**CANONICAL_COLUMNS, **OPTIONAL_COLUMNS}.items():
        hit = next((lower[a] for a in aliases if a in lower), None)
        if hit is not None:
            rename[hit] = canon
        elif canon in CANONICAL_COLUMNS:
            missing.append(canon)
    if missing:
        raise KeyError(
            f"market combinations file is missing required columns {missing}. "
            f"Found: {list(df.columns)}. See docs/DATA_CONTRACT.md."
        )
    out = df.rename(columns=rename).copy()
    out["housing_type"] = out["housing_type"].map(normalize_housing_type)
    out["city"] = out["city"].astype(str).str.strip()
    out["occupation"] = out["occupation"].astype(str).str.strip()
    return out


def load_market_combinations(path: Path | None = None) -> tuple[pd.DataFrame, str]:
    path = Path(path) if path else config.MARKET_COMBINATIONS_FILE
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Wait for the processing pipeline, or run with --fixture "
            "to exercise the code on clearly FAKE data."
        )
    return standardize_columns(pd.read_csv(path)), str(path)


# ---------------------------------------------------------------------------
# Eligibility: one shared denominator for every profile
# ---------------------------------------------------------------------------
def build_eligible_panel(market: pd.DataFrame, housing_types_needed: set[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (eligible wide panel, exclusion log).

    A city x occupation pair is eligible only if salary AND every needed
    housing type pass the sample thresholds. Nothing is imputed.
    """
    m = market.copy()
    m["salary_ok"] = (
        m["median_annual_salary"].gt(0) & np.isfinite(m["median_annual_salary"])
        & m["n_valid_salary"].ge(config.MIN_VALID_SALARY_POSTINGS)
    )
    m["rent_ok"] = (
        m["median_monthly_rent"].gt(0) & np.isfinite(m["median_monthly_rent"])
        & m["n_valid_rent"].ge(config.MIN_VALID_RENT_LISTINGS)
    )
    # NOTE: an upstream row-level `sufficient_data` flag usually mixes salary and
    # rent sufficiency, so applying it here would let a thin 2br sample knock out
    # the salary for a whole city. Thresholds are applied per dimension instead;
    # verify_processed.py reports any disagreement with the upstream flag.

    keys = ["city", "occupation"]
    salary = (m.groupby(keys)
                .agg(median_annual_salary=("median_annual_salary", "first"),
                     n_valid_salary=("n_valid_salary", "first"),
                     salary_ok=("salary_ok", "all"),
                     n_salary_values=("median_annual_salary", "nunique")))
    if (salary["n_salary_values"] > 1).any():
        bad = salary[salary["n_salary_values"] > 1].index.tolist()[:5]
        raise ValueError(f"Salary differs across housing rows for the same city x occupation, e.g. {bad}")

    rent = m.pivot_table(index=keys, columns="housing_type", values="median_monthly_rent", aggfunc="first")
    rent_n = m.pivot_table(index=keys, columns="housing_type", values="n_valid_rent", aggfunc="first")
    rent_ok = m.pivot_table(index=keys, columns="housing_type", values="rent_ok", aggfunc="all")

    panel = salary.drop(columns="n_salary_values")
    reasons = pd.Series("", index=panel.index)
    reasons[~panel["salary_ok"]] += "salary_insufficient;"
    for h in sorted(housing_types_needed):
        panel[f"rent_{h}"] = rent[h] if h in rent else np.nan
        panel[f"n_rent_{h}"] = rent_n[h] if h in rent_n else np.nan
        ok = rent_ok[h].reindex(panel.index).fillna(False).astype(bool) if h in rent_ok else pd.Series(False, index=panel.index)
        reasons[~ok] += f"rent_{h}_insufficient;"

    panel["exclusion_reason"] = reasons
    panel["eligible"] = reasons.eq("")
    log = panel.reset_index()[keys + ["eligible", "exclusion_reason"]]
    eligible = panel[panel["eligible"]].drop(columns=["eligible", "exclusion_reason", "salary_ok"]).reset_index()
    return eligible, log


# ---------------------------------------------------------------------------
# Debt / childcare benchmarks from College data
# ---------------------------------------------------------------------------
@dataclass
class Benchmarks:
    median_debt: float
    high_debt: float
    monthly_childcare: float
    debt_source: str
    childcare_source: str


def _find_col(df: pd.DataFrame, pattern: str) -> str | None:
    rx = re.compile(pattern, re.I)
    return next((c for c in df.columns if rx.search(str(c))), None)


def _is_true(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin(["true", "1", "1.0", "yes", "bay area", "bay_area"])


def _derive_monthly_childcare(path: Path) -> tuple[float | None, str]:
    """Center-based childcare = (student-parent gap - affordability gap) / 12.

    Verified on the processed data: constant across income bands within an institution.
    """
    if not path.exists():
        return None, ""
    a = pd.read_csv(path)
    pg = _find_col(a, r"parent_gap_center")
    ag = _find_col(a, r"^affordability_gap")
    bay = _find_col(a, r"is_bay_area|bay.?area")
    if not (pg and ag and bay):
        return None, ""
    b = a[_is_true(a[bay])].drop_duplicates(_find_col(a, r"unit_id") or a.columns[0])
    cc = ((b[pg] - b[ag]) / 12).dropna()
    if cc.empty:
        return None, ""
    return float(cc.median()), (f"{path.name}: ({pg} - {ag}) / 12, Bay Area median, n={len(cc)} institutions "
                                f"(source uses one statewide value: range ${cc.min():,.0f}-${cc.max():,.0f})")


def load_benchmarks(college_path: Path | None = None) -> Benchmarks:
    """Debt profiles from institution-level College data.

    median_debt = median across Bay Area FOUR-YEAR institutions of "Median Debt of Completers"
    high_debt   = 75th percentile across those institutions
    These are institutional benchmarks, NOT individual debt percentiles.
    Falls back to labelled PLACEHOLDERS if no usable college file exists.
    """
    candidates = [Path(college_path)] if college_path else [
        config.COLLEGE_EQUITY_FILE, config.PROCESSED_DIR / "college_clean.csv", config.COLLEGES_FILE]
    cc_value, cc_source = _derive_monthly_childcare(config.COLLEGE_AFFORDABILITY_FILE)
    for path in candidates:
        if not path.exists():
            continue
        df = pd.read_csv(path, low_memory=False)
        debt_col = _find_col(df, r"median.*debt.*complet|complet\w*_median_debt|debt.*complet")
        bay_col = _find_col(df, r"is_bay_area|bay.?area|is_bay|in_bay")
        if debt_col is None:
            continue
        sub, scope = df, "all institutions in file"
        if bay_col is not None:
            sub, scope = df[_is_true(df[bay_col])], f"Bay Area ({bay_col})"
        type_col = _find_col(sub, r"institution_type")
        if type_col is not None and config.DEBT_INSTITUTION_TYPE_PATTERN:
            sub = sub[sub[type_col].astype(str).str.contains(config.DEBT_INSTITUTION_TYPE_PATTERN, case=False, regex=True)]
            scope += f", {type_col} ~ '{config.DEBT_INSTITUTION_TYPE_PATTERN}'"
        debt = pd.to_numeric(sub[debt_col], errors="coerce").dropna()
        debt = debt[debt > 0]
        if len(debt) < 5:
            continue
        if cc_value is None:
            cc_col = _find_col(df, r"adjusted monthly center.?based child ?care")
            vals = pd.to_numeric(sub[cc_col], errors="coerce").dropna() if cc_col else pd.Series(dtype=float)
            if len(vals):
                cc_value, cc_source = float(vals.median()), f"{path.name}: '{cc_col}', median, n={len(vals)}"
        return Benchmarks(
            median_debt=float(debt.median()),
            high_debt=float(debt.quantile(0.75)),
            monthly_childcare=cc_value if cc_value is not None else config.FALLBACK_MONTHLY_CHILDCARE,
            debt_source=f"{path.name}: '{debt_col}', {scope}, n={len(debt)} institutions (median / P75 of institutional medians)",
            childcare_source=cc_source or "PLACEHOLDER config.FALLBACK_MONTHLY_CHILDCARE",
        )
    return Benchmarks(
        config.FALLBACK_MEDIAN_DEBT, config.FALLBACK_HIGH_DEBT,
        cc_value if cc_value is not None else config.FALLBACK_MONTHLY_CHILDCARE,
        "PLACEHOLDER config.FALLBACK_MEDIAN_DEBT / FALLBACK_HIGH_DEBT (college summary not available)",
        cc_source or "PLACEHOLDER config.FALLBACK_MONTHLY_CHILDCARE",
    )


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Profile:
    name: str
    debt_level: str        # none | median | high
    housing: str           # alone | shared | parent
    family_support: bool
    childcare: bool = False

    @property
    def index_type(self) -> str:
        return "assisted" if self.family_support else "independence"


def default_profiles() -> list[Profile]:
    profiles = []
    for debt in ("none", "median", "high"):
        for housing in ("alone", "shared"):
            for support in (False, True):
                name = f"{debt}_debt | {housing} | {'support' if support else 'no_support'}"
                profiles.append(Profile(name, debt, housing, support))
    for support in (False, True):
        profiles.append(Profile(f"student_parent (median_debt, 2br, childcare) | {'support' if support else 'no_support'}",
                                "median", "parent", support, childcare=True))
    return profiles


HOUSING_MAP = {"alone": config.HOUSING_ALONE, "shared": config.HOUSING_SHARED, "parent": config.HOUSING_PARENT}


def housing_types_for(profiles: list[Profile]) -> set[str]:
    return {HOUSING_MAP[p.housing][0] for p in profiles}


def run_profile(panel: pd.DataFrame, profile: Profile, bm: Benchmarks, *,
                tax_mode: str = config.TAX_MODE, flat_tax_rate: float = config.DEFAULT_EFFECTIVE_TAX_RATE,
                rent_multiplier: float = 1.0, essentials_multiplier: float = 1.0,
                debt_multiplier: float = 1.0, interest_rate: float = config.DEFAULT_LOAN_INTEREST_RATE) -> pd.DataFrame:
    htype, roommates = HOUSING_MAP[profile.housing]
    salary = panel["median_annual_salary"].to_numpy(float)
    rent = panel[f"rent_{htype}"].to_numpy(float) * rent_multiplier
    debt = {"none": 0.0, "median": bm.median_debt, "high": bm.high_debt}[profile.debt_level] * debt_multiplier
    tax = estimate_effective_tax_rate(salary) if tax_mode == "progressive" else np.full_like(salary, flat_tax_rate)
    res = compute_budget(
        annual_salary=salary, monthly_rent_total=rent, roommates=roommates,
        debt_principal=debt, annual_interest_rate=interest_rate, effective_tax_rate=tax,
        monthly_essentials=config.DEFAULT_MONTHLY_ESSENTIALS * essentials_multiplier,
        monthly_savings_target=config.DEFAULT_MONTHLY_SAVINGS_TARGET,
        monthly_family_support=config.FAMILY_SUPPORT_MONTHLY if profile.family_support else 0.0,
        monthly_childcare=bm.monthly_childcare if profile.childcare else 0.0,
    )
    out = panel[["city", "occupation", "median_annual_salary", "n_valid_salary"]].copy()
    out.insert(0, "profile", profile.name)
    out["index_type"] = profile.index_type
    out["housing_type"] = htype
    out["roommates"] = roommates
    out["debt_principal"] = debt
    out["n_valid_rent"] = panel[f"n_rent_{htype}"].to_numpy()
    for k, v in res.items():
        out[k] = np.broadcast_to(v, salary.shape)
    out["feasible"] = out["feasible_with_support"]  # given this profile's support setting
    return out


def summarize(results: pd.DataFrame) -> pd.DataFrame:
    g = results.groupby(["profile", "index_type"], sort=False)
    table = g.agg(
        n_combinations=("feasible", "size"),
        n_feasible=("feasible", "sum"),
        median_feasibility_gap=("feasibility_gap", "median"),
        p25_feasibility_gap=("feasibility_gap", lambda s: s.quantile(0.25)),
        p75_feasibility_gap=("feasibility_gap", lambda s: s.quantile(0.75)),
        median_monthly_balance=("monthly_balance", "median"),
        median_rent_burden=("rent_burden", "median"),
        share_rent_affordable=("rent_affordable", "mean"),
        median_shortfall_if_short=("required_additional_net_monthly", lambda s: s[s > 0].median() if (s > 0).any() else 0.0),
        median_extra_gross_salary_needed=("required_additional_gross_annual", lambda s: s[s > 0].median() if (s > 0).any() else 0.0),
    ).reset_index()
    table["feasibility_rate"] = table["n_feasible"] / table["n_combinations"]
    table["barrier_index"] = 1.0 - table["feasibility_rate"]
    cols = ["profile", "index_type", "n_combinations", "n_feasible", "feasibility_rate", "barrier_index"]
    return table[cols + [c for c in table.columns if c not in cols]]


def factor_effects(table: pd.DataFrame) -> pd.DataFrame:
    """Change each starting condition one at a time from the baseline
    (no debt, living alone, no family support)."""
    t = table.set_index("profile")
    base = "none_debt | alone | no_support"
    switches = {
        "median institutional debt": "median_debt | alone | no_support",
        "high institutional debt (P75)": "high_debt | alone | no_support",
        "shared housing (2br split)": "none_debt | shared | no_support",
        "family support": "none_debt | alone | support",
        "student parent (median debt + childcare + 2br)": "student_parent (median_debt, 2br, childcare) | no_support",
    }
    rows = []
    for label, prof in switches.items():
        if prof not in t.index or base not in t.index:
            continue
        rows.append({
            "change_from_baseline": label,
            "profile": prof,
            "delta_median_gap": t.at[prof, "median_feasibility_gap"] - t.at[base, "median_feasibility_gap"],
            "delta_barrier_index": t.at[prof, "barrier_index"] - t.at[base, "barrier_index"],
            "barrier_index": t.at[prof, "barrier_index"],
            "baseline_barrier_index": t.at[base, "barrier_index"],
        })
    return pd.DataFrame(rows).sort_values("delta_median_gap", ascending=False, key=abs)


def same_job_different_start(results: pd.DataFrame) -> pd.DataFrame:
    """The project's core narrative: one job, one city, different starting
    conditions. Picks the combination with the median salary."""
    base = results[results["profile"] == "none_debt | alone | no_support"]
    if base.empty:
        return pd.DataFrame()
    target = base.iloc[(base["median_annual_salary"] - base["median_annual_salary"].median()).abs().argsort()].iloc[0]
    sel = results[(results["city"] == target["city"]) & (results["occupation"] == target["occupation"])]
    cols = ["profile", "city", "occupation", "median_annual_salary", "net_monthly", "family_support",
            "personal_rent", "loan_payment", "essentials", "childcare", "savings_target",
            "monthly_balance", "feasibility_gap", "feasible"]
    return sel[cols].reset_index(drop=True)


def sensitivity(panel: pd.DataFrame, bm: Benchmarks, reference: Profile | None = None) -> pd.DataFrame:
    reference = reference or Profile("median_debt | alone | no_support", "median", "alone", False)
    rows = []
    for param, values in config.SENSITIVITY.items():
        for v in values:
            kwargs = {"tax_mode": "flat", "flat_tax_rate": v} if param == "flat_tax_rate" else {param: v}
            r = run_profile(panel, reference, bm, **kwargs)
            rows.append({
                "reference_profile": reference.name, "parameter": param, "value": v,
                "n_combinations": len(r), "feasibility_rate": r["feasible"].mean(),
                "barrier_index": 1 - r["feasible"].mean(),
                "median_feasibility_gap": r["feasibility_gap"].median(),
            })
    return pd.DataFrame(rows)


def run_all(market: pd.DataFrame, bm: Benchmarks, profiles: list[Profile] | None = None) -> dict[str, pd.DataFrame]:
    profiles = profiles or default_profiles()
    panel, log = build_eligible_panel(market, housing_types_for(profiles))
    if panel.empty:
        raise ValueError("No eligible city x occupation combinations; check thresholds and the exclusion log.")
    results = pd.concat([run_profile(panel, p, bm) for p in profiles], ignore_index=True)
    # Denominator check: every profile must see the identical set of combinations
    sizes = results.groupby("profile").size()
    assert sizes.nunique() == 1, f"Profiles have different denominators: {sizes.to_dict()}"
    table = summarize(results)
    return {
        "eligibility_log": log,
        "combination_results": results,
        "equity_table": table,
        "factor_effects": factor_effects(table),
        "same_job_different_start": same_job_different_start(results),
        "sensitivity": sensitivity(panel, bm),
    }
