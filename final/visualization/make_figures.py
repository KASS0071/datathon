"""Static PNG figures for the report (light theme, validated palette).

    ../.venv/bin/python -B visualization/make_figures.py   (after run_equity.py and summarize_results.py)
Writes visualization/figures/*.png
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import config  # noqa: E402

# Reference palette (validated: adjacent CVD dE >= 9.1, normal-vision >= 19.6)
SURFACE, INK, INK2, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#e1e0d9", "#c3c2b7"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]
NEUTRAL_BAND = "#f0efec"
FIG = Path(__file__).resolve().parent / "figures"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 11, "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "xtick.color": INK2,
    "ytick.color": INK2, "text.color": INK, "axes.titlesize": 14, "axes.titleweight": "bold",
    "axes.titlelocation": "left", "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE, "axes.spines.top": False, "axes.spines.right": False,
})


def _hbar(ax, y, x0, width, height, color):
    """Horizontal bar with ~4px rounded data end (2px surface gap via edge)."""
    if width <= 0:
        return
    ax.add_patch(FancyBboxPatch((x0, y - height / 2), width, height,
                                boxstyle="round,pad=0,rounding_size=0.08", mutation_aspect=1 / 40,
                                facecolor=color, edgecolor=SURFACE, linewidth=2))


def _finish(fig, ax, name, source):
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    fig.text(0.01, -0.03, source.replace("$", r"\$"), fontsize=8.5, color=INK2, ha="left", va="top")
    fig.savefig(FIG / name, dpi=200, bbox_inches="tight")
    plt.close(fig)


def fig_barrier(table: pd.DataFrame, n: int):
    t = table[table["index_type"] == "independence"].copy()
    t["label"] = (t["profile"].str.replace(" | no_support", "", regex=False)
                  .str.replace("none_debt", "no debt").str.replace("_debt", " debt").str.replace(" | ", ", ")
                  .str.replace("student_parent (median debt, 2br, childcare)", "student parent (median debt, childcare)"))
    t = t.sort_values("barrier_index")
    fig, ax = plt.subplots(figsize=(9, 4.6))
    for i, (_, r) in enumerate(t.iterrows()):
        _hbar(ax, i, 0, r["barrier_index"], 0.62, SERIES[0])
        ax.text(r["barrier_index"] + 0.012, i, f"{r['barrier_index']:.0%}", va="center", fontsize=10, color=INK)
    ax.set_yticks(range(len(t)), t["label"])
    ax.set_xlim(0, 1.08)
    ax.set_ylim(-0.6, len(t) - 0.4)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.set_title("Barrier Index: share of city × occupation combinations that fail\n"
                 "independence (no family support)", pad=12)
    ax.set_xlabel(f"Barrier Index (same {n} combinations for every profile)")
    _finish(fig, ax, "01_barrier_index_by_profile.png",
            "Simulated city × occupation combinations, not shares of real graduates. Pay: median of non-senior, "
            "not-part-time-only Bay Area Indeed postings per city and occupation; rent: Zillow median asking rent.")


def fig_break_even(opp: pd.DataFrame, top: int = 20):
    d = opp.copy()
    d["n"] = d["n_valid_rent_1br"]
    d = d.nlargest(top, "n").sort_values("break_even_alone")
    pay = pd.read_csv(config.BUILT_MARKET_FILE.parent / "salary_levels.csv").set_index("salary_level")["annual_pay_usd"]
    fig, ax = plt.subplots(figsize=(9, 7))
    ax.axvspan(pay["pay_P25"], pay["pay_P75"], color=NEUTRAL_BAND, zorder=0)
    ax.axvline(pay["pay_P50"], color=AXIS, linewidth=1.5, zorder=1)
    ax.text(pay["pay_P50"], len(d) - 0.2, f"median non-senior advertised pay ${pay['pay_P50'] / 1000:.1f}k\n(band = middle 50% of postings)",
            ha="center", va="bottom", fontsize=9, color=INK2)
    y = np.arange(len(d))
    ax.hlines(y, d["break_even_shared"], d["break_even_alone"], color=GRID, linewidth=2, zorder=2)
    ax.scatter(d["break_even_shared"], y, s=64, color=SERIES[0], edgecolor=SURFACE, linewidth=2, zorder=3, label="Sharing a 2br")
    ax.scatter(d["break_even_alone"], y, s=64, color=SERIES[1], edgecolor=SURFACE, linewidth=2, zorder=3, label="Living alone (1br)")
    top_row = d.iloc[-1]
    ax.text(top_row["break_even_shared"], len(d) - 1 + 0.45, "shared", ha="center", fontsize=9, color=INK2)
    ax.text(top_row["break_even_alone"], len(d) - 1 + 0.45, "alone", ha="center", fontsize=9, color=INK2)
    ax.set_yticks(y, d["city"])
    ax.set_ylim(-0.7, len(d) + 0.9)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"${v / 1000:.0f}k"))
    ax.set_xlabel("Gross salary needed to cover rent, essentials and savings (no debt, no support)")
    ax.set_title(f"Break-even salary by city vs. advertised pay ({top} cities with most listings)", pad=26)
    ax.legend(loc="lower right", frameon=False)
    _finish(fig, ax, "02_break_even_salary_by_city.png",
            f"Assumes essentials ${config.DEFAULT_MONTHLY_ESSENTIALS:,.0f}/mo, savings ${config.DEFAULT_MONTHLY_SAVINGS_TARGET:,.0f}/mo, "
            "approximate 2025 federal + CA + payroll tax. Rent: Zillow median asking rent.")


def fig_same_job(sj: pd.DataFrame):
    keep = ["none_debt | alone | no_support", "median_debt | alone | no_support", "high_debt | alone | no_support",
            "median_debt | shared | no_support", "student_parent (median_debt, 2br, childcare) | no_support"]
    labels = ["No debt, alone", "Median debt, alone", "High debt, alone", "Median debt, shared 2br", "Student parent"]
    d = sj.set_index("profile").loc[keep]
    parts = [("personal_rent", "Rent"), ("loan_payment", "Loan"), ("childcare", "Childcare"),
             ("essentials", "Essentials"), ("savings_target", "Savings target")]
    fig, ax = plt.subplots(figsize=(9.5, 4.4))
    for i, (_, r) in enumerate(d.iterrows()):
        x = 0.0
        for k, (col, name) in enumerate(parts):
            w = r[col]
            if w > 0:
                ax.barh(i, w, left=x, height=0.62, color=SERIES[k], edgecolor=SURFACE, linewidth=2)
                if w > 380:
                    ax.text(x + w / 2, i, f"${w:,.0f}", ha="center", va="center", fontsize=8.5, color=INK)
            x += w
        gap = r["feasibility_gap"]
        ax.text(max(x, d["net_monthly"].iloc[0]) + 80, i, ("short " if gap > 0 else "surplus ") + f"${abs(gap):,.0f}", va="center", fontsize=9.5,
                color=INK, fontweight="bold" if gap > 0 else "normal")
    net = d["net_monthly"].iloc[0]
    ax.axvline(net, color=INK, linewidth=1.5, linestyle=(0, (4, 3)))
    ax.text(net, len(d) - 0.45, f"take-home pay ${net:,.0f}", ha="center", va="top", fontsize=9, color=INK,
            bbox=dict(facecolor=SURFACE, edgecolor="none", pad=1.5))
    ax.set_yticks(range(len(d)), labels)
    ax.set_ylim(len(d) - 0.2, -0.6)
    ax.set_xlim(0, d[[c for c, _ in parts]].sum(axis=1).max() * 1.18)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"${v:,.0f}"))
    city, occ, sal = sj["city"].iloc[0], sj["occupation"].iloc[0], sj["median_annual_salary"].iloc[0]
    ax.set_title(f"Same job, same city, different starting conditions\n"
                 f"{occ}, {city}: salary ${sal:,.0f}, monthly budget", pad=22)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=SERIES[k], label=n) for k, (_, n) in enumerate(parts)],
              ncol=5, loc="lower left", bbox_to_anchor=(0, 1.0), frameon=False, fontsize=9)
    _finish(fig, ax, "03_same_job_different_start.png",
            "Debt = Bay Area four-year institutional median / P75 of 'Median Debt of Completers' (institution benchmark, not individual). "
            "Childcare = Affordability Gap data.")


def fig_college(col: pd.DataFrame):
    d = col[col["metric"].str.startswith("Net price by family income")]
    groups = ["Bay Area", "California (non-Bay)", "National (other states)"]
    ticks = sorted(d["family_income_ceiling_usd"].unique())
    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    for k, g in enumerate(groups):
        s = d[d["group"] == g].sort_values("family_income_ceiling_usd")
        xs = [ticks.index(v) for v in s["family_income_ceiling_usd"]]
        ax.plot(xs, s["median"], color=SERIES[k], linewidth=2, marker="o", markersize=8,
                markeredgecolor=SURFACE, markeredgewidth=2, label=f"{g} (n≈{int(s['n_institutions'].median())})")
        last = s.iloc[-1]
        ax.text(len(ticks) - 1 + 0.12, last["median"], g, va="center", fontsize=9.5, color=INK)
    ax.set_xticks(range(len(ticks)), [f"≤\\${t / 1000:.0f}k" for t in ticks])
    ax.set_xlim(-0.3, len(ticks) + 0.9)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"${v / 1000:.0f}k"))
    ax.set_xlabel("Family income band")
    ax.set_ylabel("Median annual net price")
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_title("Four-year college net price by family income, 2022-23", pad=12)
    ax.legend(frameon=False, fontsize=9, loc="upper left")
    _finish(fig, ax, "04_college_net_price_by_income.png",
            "Unweighted median across four-year institutions. Source: Affordability Gap Data AY2022-23.")


def fig_occupation(occ: pd.DataFrame):
    d = occ[occ["pay_definition"].str.startswith("Bay-Area-wide entry")].sort_values("median_salary")
    fig, ax = plt.subplots(figsize=(9.5, 6.2))
    y = np.arange(len(d))
    ax.hlines(y, d["barrier_shared_no_debt"], d["barrier_alone_no_debt"], color=GRID, linewidth=2, zorder=1)
    ax.scatter(d["barrier_shared_no_debt"], y, s=64, color=SERIES[0], edgecolor=SURFACE, linewidth=2, zorder=3,
               label="Sharing a 2br")
    ax.scatter(d["barrier_alone_no_debt"], y, s=64, color=SERIES[1], edgecolor=SURFACE, linewidth=2, zorder=3,
               label="Living alone (1br)")
    labels = [f"{o}  (${m / 1000:.0f}k)" for o, m in zip(d["occupation"], d["median_salary"])]
    ax.set_yticks(y, labels)
    ax.set_xlim(-0.03, 1.05)
    ax.set_ylim(-0.7, len(d) - 0.3)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.set_xlabel(f"Barrier Index: share of {int(d['n_cities'].iloc[0])} Bay Area cities where the budget fails "
                  "(no debt, no family support)")
    ax.set_title("What you do sets the barrier; how you live moves it\n"
                 "Occupation (median entry-level advertised pay), living alone vs sharing", pad=12)
    ax.legend(loc="upper right", frameon=False)
    _finish(fig, ax, "05_barrier_by_occupation.png",
            "Pay: Bay-Area-wide median of Indeed postings with an entry-level signal, per occupation group (title-based classification, "
            "88% accurate on a fresh hand-checked sample). Rent: Zillow median asking rent per city.")


def fig_rent(rents: pd.DataFrame, housing_type: str = "1br", min_listings: int = None, top: int = 12):
    """Median one-bedroom asking rent with the interquartile range (notebook section 1)."""
    min_listings = config.MIN_VALID_RENT_LISTINGS if min_listings is None else min_listings
    d = (rents[(rents["housing_type"] == housing_type) & (rents["n_valid_rent"] >= min_listings)]
         .nlargest(top, "n_valid_rent").sort_values("median_monthly_rent"))
    y = np.arange(len(d))
    fig, ax = plt.subplots(figsize=(9, 5.4))
    ax.hlines(y, d["rent_q1"], d["rent_q3"], color=GRID, linewidth=3, zorder=2, label="25th to 75th percentile")
    ax.scatter(d["median_monthly_rent"], y, s=64, color=SERIES[0], edgecolor=SURFACE, linewidth=2, zorder=3, label="Median")
    for i, r in enumerate(d.itertuples()):
        ax.text(r.rent_q3 + 40, i, f"${r.median_monthly_rent:,.0f}", va="center", fontsize=9, color=INK2)
    ax.set_yticks(y, [f"{r.city} (n={r.n_valid_rent:,})" for r in d.itertuples()])
    ax.set_ylim(-0.6, len(d) - 0.4)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"${v:,.0f}"))
    ax.set_xlabel("Monthly asking rent")
    ax.set_title(f"One-bedroom asking rents by city ({top} cities with most listings)", pad=12)
    ax.legend(loc="lower right", frameon=False)
    _finish(fig, ax, "06_rent_by_city.png",
            f"Zillow asking rent (listing price). n = distinct listings; cities need at least {min_listings}.")


def fig_gap_heatmap(results: pd.DataFrame, opp: pd.DataFrame, occupations: pd.Series,
                    profile: str = "none_debt | alone | no_support", top: int = 15):
    """Monthly feasibility gap for each city x occupation (notebook section 2)."""
    from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
    rows = results[results["profile"] == profile]
    cities = opp[opp["city"].isin(rows["city"])].nlargest(top, "n_valid_rent_1br")["city"]
    gap = rows[rows["city"].isin(cities)].pivot(index="city", columns="occupation", values="feasibility_gap")
    gap = gap.reindex(index=cities, columns=[o for o in occupations if o in gap])
    bound = max(1.0, float(gap.abs().max().max()))
    cmap = LinearSegmentedColormap.from_list("gap", [SERIES[0], SURFACE, SERIES[1]]).with_extremes(bad="#bdbcb4")
    fig, ax = plt.subplots(figsize=(12, 7.2))
    heat = ax.imshow(np.ma.masked_invalid(gap.to_numpy()), aspect="auto", cmap=cmap,
                     norm=TwoSlopeNorm(vmin=-bound, vcenter=0, vmax=bound))
    ax.set_xticks(range(len(gap.columns)), gap.columns, rotation=40, ha="right", fontsize=9)
    ax.set_yticks(range(len(gap)), list(gap.index))
    ax.spines[["left", "bottom"]].set_visible(False)
    ax.tick_params(length=0)
    bar = fig.colorbar(heat, ax=ax, fraction=0.03, pad=0.02,
                       format=matplotlib.ticker.FuncFormatter(lambda v, _: ("−" if v < 0 else "") + f"${abs(v):,.0f}"))
    bar.set_label("Monthly gap after savings (positive = shortfall)", color=INK2)
    bar.outline.set_visible(False)
    ax.set_title("Monthly budget gap by city and occupation: no debt, living alone, no family support", pad=12)
    note = ("Pay: median of non-senior Bay Area Indeed postings per city and occupation. Rent: Zillow median "
            f"1br asking rent. {top} cities with most 1br listings; dark grey = not enough data.")
    ax.set_xlabel(note.replace("$", r"\$"), fontsize=8.5, color=INK2, loc="left", labelpad=10)
    fig.savefig(FIG / "07_gap_heatmap_city_occupation.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    FIG.mkdir(parents=True, exist_ok=True)
    eq = config.OUTPUT_DIR / "equity"
    an = config.OUTPUT_DIR / "analysis"
    table = pd.read_csv(eq / "equity_table.csv")
    fig_barrier(table, int(table["n_combinations"].iloc[0]))
    fig_break_even(pd.read_csv(an / "city_opportunity.csv"))
    fig_same_job(pd.read_csv(eq / "same_job_different_start.csv"))
    fig_college(pd.read_csv(an / "college_comparison.csv"))
    fig_occupation(pd.read_csv(an / "occupation_barrier.csv"))
    mi = config.BUILT_MARKET_FILE.parent
    fig_rent(pd.read_csv(mi / "rent_by_city_housing.csv"))
    fig_gap_heatmap(pd.read_csv(eq / "combination_results.csv"), pd.read_csv(an / "city_opportunity.csv"),
                    pd.read_csv(mi / "salary_by_occupation.csv")["occupation"])
    print("Wrote:", *sorted(p.name for p in FIG.glob("*.png")), sep="\n  ")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
