"""Stage 6 dashboard for the Bay Area datathon."""
from dataclasses import asdict
import json
from pathlib import Path
import sys

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import os

PROJECT = Path(__file__).resolve().parents[2]
DATA = PROJECT / "outputs"
JOBS = Path(os.environ.get("DATATHON_DATA_DIR", PROJECT / "data")) / "processed" / "jobs_bay_area.csv"
sys.path.insert(0, str(PROJECT))
from src.results import table_path
from src.budget.calculate_budget import ScenarioInputs, break_even_salary, simulate

PAGES = ("Market overview", "Affordability heatmap", "Simulator", "Equity")
PAY = {"pay_P25": "P25", "pay_P50": "P50", "pay_P75": "P75"}
HOUSING = {"studio": "Studio", "1br": "1 bedroom", "2br": "2 bedrooms", "3br": "3 bedrooms"}
SHORT = "#a84c2e"
COVERED = "#16766f"
LIMIT = (
    "Results describe simulated city × occupation combinations. Pay comes from "
    "Bay Area Indeed postings after excluding senior and part-time-only signals. "
    "These are advertised pay figures. Listing status reflects the source snapshot. "
    "Entry-level signals are heuristic. Debt is an institution-level benchmark."
)


def read_csv(name):
    return pd.read_csv(table_path(DATA, f"{name}.csv"))


def model_suffix():
    model = st.radio("Salary model", ("City × occupation", "Regional entry-level signals"), horizontal=True)
    suffix = "_entry_signal" if model.startswith("Regional") else ""
    st.caption(
        "Each occupation uses one Bay Area pay estimate based on entry-level signals."
        if suffix else "Pay is estimated separately for each eligible city and occupation."
    )
    return suffix


def money(value, digits=0):
    sign = "-" if value < 0 else ""
    return f"{sign}${abs(value):,.{digits}f}"


def profile_label(profile):
    if profile.startswith("student_parent"):
        return "Student parent / " + ("no support" if profile.endswith("no_support") else "with support")
    debt, housing, support = profile.split(" | ")
    label = {"none_debt": "No debt", "median_debt": "Median debt", "high_debt": "High debt"}[debt]
    return f"{label} / {housing} / {'no support' if support == 'no_support' else 'with support'}"


def figure(fig, **layout):
    fig.update_layout(margin=dict(l=10, r=15, t=25, b=10), **layout)
    st.plotly_chart(fig, width="stretch")


def rent_chart(rows):
    rows = rows.sort_values("median_monthly_rent")
    fig = go.Figure(go.Scatter(
        x=rows.median_monthly_rent, y=rows.city, mode="markers",
        marker=dict(color=COVERED, size=9),
        error_x=dict(type="data", symmetric=False, array=rows.rent_q3 - rows.median_monthly_rent,
                     arrayminus=rows.median_monthly_rent - rows.rent_q1, color="#72948e"),
        customdata=rows[["rent_q1", "rent_q3", "n_valid_rent"]],
        hovertemplate="%{y}<br>Median $%{x:,.0f}<br>P25–P75 $%{customdata[0]:,.0f}–$%{customdata[1]:,.0f}"
                      "<br>Distinct listing signatures %{customdata[2]:,.0f}<extra></extra>",
    ))
    fig.update_xaxes(title="Monthly asking rent", tickprefix="$")
    figure(fig, height=max(350, len(rows) * 25))


def market_page(assumptions):
    rents, pay, eligibility = (read_csv(name) for name in ("rent_by_city_housing", "salary_levels", "eligibility_log"))
    jobs = pd.read_csv(JOBS)
    disclosed = jobs.salary_original.fillna("").str.strip().ne("").sum()
    total = len(jobs)
    city_status = eligibility.groupby("city", as_index=False).agg(
        eligible=("eligible", "any"),
        eligible_occupations=("eligible", "sum"),
        evaluated_occupations=("eligible", "size"),
    )
    cards = st.columns(3)
    cards[0].metric("Postings with advertised pay", f"{disclosed}/{total}", f"{disclosed/total:.0%} of sampled postings", delta_color="off")
    cards[1].metric("Postings in pay benchmark", int(pay.n_valid_salary.iloc[0]))
    cards[2].metric("Eligible cities", f"{int(city_status.eligible.sum())}/{len(city_status)}")

    entry = int(jobs.entry_signal.str.startswith("entry_", na=False).sum())
    expired = int(jobs.is_expired.astype(str).str.lower().eq("true").sum())
    st.caption(f"{entry:,} postings have an entry-level signal. {expired:,} are marked expired in the source snapshot.")

    st.subheader("Regional advertised pay")
    for panel, row in zip(st.columns(len(pay)), pay.itertuples()):
        panel.metric(PAY[row.salary_level], money(row.annual_pay_usd))
    st.caption("These quartiles give regional context. The affordability model uses occupation-specific salaries.")
    with st.expander("Pay by occupation"):
        st.dataframe(read_csv("salary_by_occupation"), hide_index=True, width="stretch")

    st.subheader("How asking rent varies by city")
    a, b = st.columns(2)
    housing = a.selectbox("Housing type", HOUSING, index=1, format_func=HOUSING.get)
    minimum = assumptions["min_valid_rent_listings"]
    qualified = b.checkbox(f"Require at least {minimum} distinct listing signatures", value=True)
    rows = rents[rents.housing_type.eq(housing)]
    if qualified:
        rows = rows[rows.n_valid_rent.ge(minimum)]
    selected = st.multiselect(
        "Cities in rent chart", sorted(rows.city.unique()),
        default=[city for city in ("Oakland", "San Francisco", "San Jose", "Vallejo") if city in set(rows.city)],
    )
    if selected:
        rent_chart(rows[rows.city.isin(selected)])
    st.caption("Dots are medians. Lines span the 25th to 75th percentiles. Counts use distinct combinations of listing attributes.")
    st.dataframe(rows[["city", "median_monthly_rent", "rent_q1", "rent_q3", "n_valid_rent", "n_listings"]],
                 hide_index=True, width="stretch")
    with st.expander("City eligibility and exclusions"):
        st.caption(f"A city qualifies if at least one occupation has {assumptions['min_valid_salary_postings']} usable salaries "
                   f"and both 1BR and 2BR have at least {minimum} distinct listing signatures.")
        st.dataframe(city_status, hide_index=True, width="stretch")
        excluded = eligibility.loc[~eligibility.eligible, ["city", "occupation", "exclusion_reason"]]
        st.dataframe(excluded, hide_index=True, width="stretch")


def heatmap_page():
    suffix = model_suffix()
    results = read_csv("combination_results" + suffix)
    opportunity = read_csv("city_opportunity").sort_values("break_even_alone")
    first, second = st.columns(2)
    profile = first.selectbox("Scenario profile", results.profile.unique(), format_func=profile_label)
    metric = second.radio("Colour by", ("Monthly feasibility gap", "Rent burden"), horizontal=True)
    rows = results[results.profile.eq(profile)]
    st.caption(f"{len(rows):,} modeled combinations across {rows.city.nunique()} cities. Blank cells have insufficient data.")
    value = "feasibility_gap" if metric == "Monthly feasibility gap" else "rent_burden"
    order = read_csv("salary_by_occupation").occupation
    heat = rows.pivot(index="city", columns="occupation", values=value)
    heat = heat.reindex(columns=[name for name in order if name in heat.columns])
    def matrix(field):
        return rows.pivot(index="city", columns="occupation", values=field).reindex_like(heat).to_numpy()

    fmt = "$%{z:,.0f}" if value == "feasibility_gap" else "%{z:.0%}"
    style = dict(colorscale=[[0, COVERED], [.5, "#f7f5ef"], [1, SHORT]], zmid=0) if value == "feasibility_gap" else dict(colorscale="YlOrRd")
    import numpy as np

    fig = go.Figure(go.Heatmap(
        z=heat.to_numpy(), x=heat.columns.tolist(), y=heat.index.tolist(),
        customdata=np.stack([matrix("n_valid_rent"), matrix("n_valid_salary")], axis=-1),
        hoverongaps=False, colorbar=dict(tickformat="$,.0f" if value == "feasibility_gap" else ".0%"),
        hovertemplate="%{y} · %{x}<br>" + fmt + "<br>Rent signatures %{customdata[0]:,.0f}"
                      "<br>Usable salaries %{customdata[1]:,.0f}<extra></extra>", **style,
    ))
    fig.update_xaxes(title="Occupation", tickangle=-45, side="top")
    fig.update_yaxes(autorange="reversed", tickfont=dict(size=11))
    figure(fig, height=1100)
    st.caption("A positive gap means that take-home pay and any included support fall short of expenses plus the savings target.")

    st.subheader("Break-even salary by city")
    pay = read_csv("salary_levels")
    series = {"break_even_alone": "Alone, no debt", "break_even_shared": "Shared, no debt",
              "break_even_alone_median_debt": "Alone, median debt"}
    chart = opportunity.rename(columns=series).melt(
        id_vars=["city", "n_valid_rent_1br", "n_valid_rent_2br"], value_vars=list(series.values()),
        var_name="scenario", value_name="Annual gross salary",
    )
    fig = px.scatter(chart, x="city", y="Annual gross salary", color="scenario",
                     hover_data=["n_valid_rent_1br", "n_valid_rent_2br"], color_discrete_sequence=[SHORT, COVERED, "#6475a1"])
    p25, p50, p75 = (float(pay.set_index("salary_level").loc[k, "annual_pay_usd"]) for k in PAY)
    fig.add_hrect(y0=p25, y1=p75, fillcolor="#c4d8d1", opacity=.4, line_width=0, layer="below")
    fig.add_hline(y=p50, line_dash="dash", line_color=COVERED, annotation_text="Regional median pay")
    fig.update_yaxes(tickprefix="$")
    fig.update_xaxes(tickangle=-65, title=None)
    figure(fig, height=540)
    st.caption(f"Shaded band spans advertised pay P25–P75 ({money(p25)}–{money(p75)}).")


def simulator_page(assumptions):
    rents = read_csv("rent_by_city_housing")
    pay = read_csv("salary_by_occupation").set_index("occupation")
    pay = pay.loc[pay.index != "Other / unclassified"]
    basis = st.radio("Salary estimate", ("Entry-level signals", "All screened postings"), horizontal=True)
    group = "entry_signal" if basis.startswith("Entry") else "all"
    qualified_pay = pay[pay[f"n_valid_salary_{group}"].ge(assumptions["min_valid_salary_postings"])]
    occupation = st.selectbox("Occupation for salary default", qualified_pay.index)
    wages = qualified_pay.loc[occupation]
    salary_default = float(wages[f"median_annual_salary_{group}"])
    st.caption(f"Regional median {money(salary_default)} from {int(wages[f'n_valid_salary_{group}']):,} usable salaries. "
               "You can enter a different salary below.")
    benchmarks = assumptions["benchmarks"]
    cities = sorted(rents.city.unique())
    a, b, c = st.columns(3)
    city = a.selectbox("City", cities, index=cities.index("Oakland") if "Oakland" in cities else 0)
    options = rents[rents.city.eq(city)].set_index("housing_type")
    types = [key for key in HOUSING if key in options.index]
    housing = b.selectbox("Housing", types, index=types.index("1br") if "1br" in types else 0, format_func=HOUSING.get)
    roommates = c.slider("Roommates (excluding you)", 0, 6, 0)
    listing = options.loc[housing]
    sample = int(listing.n_valid_rent)
    st.caption(f"{city} {HOUSING[housing].lower()} median asking rent {money(listing.median_monthly_rent)}/mo "
               f"from {sample:,} distinct listing signatures.")
    if sample < assumptions["min_valid_rent_listings"]:
        st.warning("This rent estimate falls below the market analysis sample threshold.")
    override = st.checkbox("Use a custom rent")
    rent = float(listing.median_monthly_rent)
    if override:
        rent = st.number_input("Monthly rent for entire unit", min_value=0.0, max_value=25000.0, value=rent, step=50.0)

    a, b, c = st.columns(3)
    salary = a.number_input("Gross annual salary", min_value=1.0, max_value=1_000_000.0, value=salary_default, step=500.0, key=f"gross_pay_{group}_{occupation}")
    debt = b.number_input("Student debt principal", min_value=0.0, max_value=1_000_000.0, value=float(benchmarks["median_debt"]), step=500.0)
    rate = c.number_input("Annual loan interest (%)", min_value=0.0, max_value=99.0, value=100 * assumptions["loan_interest_rate"], step=.1)
    a, b, c = st.columns(3)
    term = a.slider("Loan term (years)", 1, 30, int(assumptions["loan_term_years"]))
    mode = b.selectbox("Tax method", ("Progressive estimate", "Flat effective rate"))
    tax = c.number_input("Flat effective tax (%)", min_value=0.0, max_value=99.0, value=22.0, step=1.0) / 100 if mode.startswith("Flat") else None
    a, b, c, d = st.columns(4)
    essentials = a.number_input("Essentials per month", min_value=0.0, value=float(assumptions["monthly_essentials"]["value"]), step=50.0)
    savings = b.number_input("Savings target per month", min_value=0.0, value=float(assumptions["monthly_savings_target"]["value"]), step=50.0)
    support = c.number_input("Family support per month", min_value=0.0, value=0.0, step=50.0)
    childcare = d.number_input("Childcare per month", min_value=0.0, value=0.0, step=50.0)
    st.caption(f"Editable assumptions include essentials, savings and support. The modeled childcare benchmark is "
               f"{money(benchmarks['monthly_childcare'])}/mo. Progressive tax is an {assumptions['tax_description']}.")

    inputs = ScenarioInputs(
        annual_salary=salary, monthly_rent_total=rent, roommates=roommates, debt_principal=debt,
        annual_interest_rate=rate / 100, effective_tax_rate=tax, monthly_essentials=essentials,
        monthly_savings_target=savings, monthly_family_support=support, monthly_childcare=childcare,
        loan_term_years=term,
    )
    result = simulate(inputs)
    params = asdict(inputs)
    for key in ("warnings", "annual_salary"):
        del params[key]
    break_even = break_even_salary(**params)
    a, b, c, d = st.columns(4)
    a.metric("Monthly balance before savings", money(result["monthly_balance"], 2))
    b.metric("Gap after savings", money(result["feasibility_gap"], 2), help="Positive means shortfall.")
    c.metric("Rent share of gross pay", f"{result['rent_burden']:.1%}")
    d.metric("Break-even gross pay", money(break_even) if break_even < 2_000_000 or tax is not None else "Above $2M")
    st.caption(f"The gap without family support is {money(result['feasibility_gap_without_support'], 2)}/mo. "
               f"Effective tax rate {result['effective_tax_rate']:.4%}. Break-even pay includes any support entered above.")
    for warning in result["warnings"]:
        st.warning(warning)
    labels = {"net_monthly": "Take-home pay", "family_support": "Family support", "personal_rent": "Personal rent",
              "loan_payment": "Student loan", "essentials": "Essentials", "childcare": "Childcare", "savings_target": "Savings target"}
    budget = pd.DataFrame({"Budget line": list(labels.values()), "Monthly amount": [result[k] for k in labels]})
    st.dataframe(budget, hide_index=True, width="stretch", column_config={"Monthly amount": st.column_config.NumberColumn(format="$%.2f")})


def equity_page():
    suffix = model_suffix()
    equity = read_csv("equity_table" + suffix)
    same_job = read_csv("same_job_different_start")
    effects = read_csv("factor_effects" + suffix)
    action, sensitivity, colleges = (read_csv(name) for name in ("actionability", "sensitivity", "college_comparison"))
    kind = st.radio("Profile group", ("independence", "assisted"), horizontal=True, format_func=lambda key: {
        "independence": "Without family support", "assisted": "With family support"}[key])
    rows = equity[equity.index_type.eq(kind)].assign(Lab=lambda df: df.profile.map(profile_label))
    st.subheader("Share of scenarios that fall short")
    st.caption(f"{int(rows.n_combinations.iloc[0])} simulated city × occupation combinations per profile.")
    fig = px.bar(rows, x="barrier_index", y="Lab", orientation="h", hover_data=["n_feasible", "n_combinations", "median_feasibility_gap"],
                 labels={"barrier_index": "Barrier Index", "Lab": ""}, color_discrete_sequence=[SHORT])
    fig.update_xaxes(tickformat=".0%", range=[0, 1.02])
    fig.update_yaxes(autorange="reversed")
    figure(fig, height=320)

    st.subheader("Shortfall by occupation")
    occupation = read_csv("occupation_barrier")
    prefix = "Bay-Area-wide entry" if suffix else "city x occupation"
    occupation = occupation[occupation.pay_definition.str.startswith(prefix)]
    bars = occupation.melt(
        id_vars=["occupation", "n_cities"], value_vars=["barrier_alone_no_debt", "barrier_shared_no_debt"],
        var_name="Housing", value_name="Shortfall rate",
    )
    bars["Housing"] = bars.Housing.map({"barrier_alone_no_debt": "Living alone", "barrier_shared_no_debt": "Sharing"})
    fig = px.bar(bars, x="Shortfall rate", y="occupation", color="Housing", barmode="group",
                 orientation="h", hover_data=["n_cities"], color_discrete_map={"Living alone": SHORT, "Sharing": COVERED})
    fig.update_xaxes(tickformat=".0%", range=[0, 1.02])
    figure(fig, height=650)

    st.subheader("Same pay, different starting points")
    if suffix:
        entry = read_csv("combination_results_entry_signal")
        reference = entry[entry.profile.eq(rows.profile.iloc[0])].copy()
        median = reference.median_annual_salary.median()
        closest = reference.assign(distance=(reference.median_annual_salary - median).abs())
        example = closest.sort_values(["distance", "city", "occupation"]).iloc[0]
        same_job = entry[entry.city.eq(example.city) & entry.occupation.eq(example.occupation)]
    example = same_job.iloc[0]
    st.caption(f"{example.city} · {example.occupation} · {money(example.median_annual_salary)} gross annual pay. "
               "Bars show monthly feasibility gaps under each profile.")
    same_job = same_job[same_job.profile.isin(rows.profile)].assign(
        Profile=lambda df: df.profile.map(profile_label), Shortfall=lambda df: df.feasibility_gap.gt(0)
    )
    fig = px.bar(same_job, x="feasibility_gap", y="Profile", color="Shortfall", orientation="h",
                 color_discrete_map={True: SHORT, False: COVERED}, hover_data=["personal_rent", "loan_payment", "childcare", "family_support"],
                 labels={"feasibility_gap": "Monthly feasibility gap"})
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(tickprefix="$")
    figure(fig, showlegend=False)
    with st.expander("Factor effects, actionability and sensitivity"):
        tables = [("One change from baseline", effects)]
        if not suffix:
            tables.extend([("Ways to close shortfalls", action), ("Sensitivity across assumptions", sensitivity)])
        for label, table in tables:
            st.markdown(f"**{label}**")
            st.dataframe(table, hide_index=True, width="stretch")
    st.subheader("Four-year college benchmarks")
    selected = st.selectbox("Measure", colleges.metric.unique())
    rows = colleges[colleges.metric.eq(selected)].copy()
    rows["Income ceiling"] = rows.family_income_ceiling_usd.map(lambda x: money(x) if pd.notna(x) else "All")
    if rows["Income ceiling"].nunique() > 1:
        fig = px.line(rows.sort_values("family_income_ceiling_usd"), x="Income ceiling", y="median", color="group",
                      markers=True, hover_data=["n_institutions"], labels={"median": "Median", "group": "Region"})
        figure(fig)
    st.dataframe(rows[["group", "Income ceiling", "median", "n_institutions"]], hide_index=True, width="stretch")


def main():
    st.set_page_config(page_title="From College to Independence", page_icon="🏠", layout="wide")
    st.title("From College to Independence")
    st.caption("Housing and financial barriers for new graduates in the San Francisco Bay Area")
    page = st.sidebar.radio("View", PAGES)
    st.header(page)
    st.caption(LIMIT)
    try:
        assumptions = json.loads((DATA / "assumptions.json").read_text())
        if page == "Market overview":
            market_page(assumptions)
        elif page == "Affordability heatmap":
            heatmap_page()
        elif page == "Simulator":
            simulator_page(assumptions)
        else:
            equity_page()
    except FileNotFoundError as exc:
        st.error(f"Missing pipeline output: {Path(exc.filename).name}. Run final/run_pipeline.py before starting the dashboard.")


if __name__ == "__main__":
    main()
