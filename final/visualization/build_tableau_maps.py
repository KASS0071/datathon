"""Export aggregate Tableau map data from the submission's dashboard package."""
import argparse
from collections import defaultdict
import csv
from pathlib import Path
from statistics import median
import sys

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = ROOT / "outputs"
sys.path.insert(0, str(ROOT))
from src.results import table_path
CITY_MAP = HERE / "tableau" / "bay_area_break_even_map.csv"
SCENARIO_MAP = HERE / "tableau" / "bay_area_occupation_map.csv"


def read_points(raw, cities):
    # Match the selected Zillow records by ID and input file. Export only
    # rounded city-level medians. A city with too few coordinates fails closed.
    ids = defaultdict(dict)
    rentals = pd.read_csv(ROOT / "data/processed/rentals_bay_area.csv", dtype={"zpid": str})
    for row in rentals[rentals.city.isin(cities)].itertuples():
        ids[row.source_file][row.zpid] = row.city
    samples = defaultdict(list)
    csv.field_size_limit(32 * 1024 * 1024)
    for filename, expected in sorted(ids.items()):
        with (raw / filename).open(encoding="utf-8-sig", errors="replace", newline="") as f:
            reader = csv.reader(f)
            fields = next(reader)
            zpid, lat, lon, status = [fields.index(k) for k in ("zpid", "latitude", "longitude", "homeStatus")]
            seen = set()
            for row in reader:
                if len(row) != len(fields) or row[status] != "FOR_RENT":
                    continue
                identifier = row[zpid].strip()
                if identifier not in expected or identifier in seen:
                    continue
                try:
                    x, y = float(row[lat]), float(row[lon])
                except ValueError:
                    continue
                if 36.8 <= x <= 39.2 and -123.7 <= y <= -121.0:
                    samples[expected[identifier]].append((x, y))
                    seen.add(identifier)
        print(f"Read coordinates from {filename}", flush=True)
    missing = sorted(city for city in cities if len(samples[city]) < 5)
    if missing:
        raise ValueError(f"Fewer than five valid rental locations for: {', '.join(missing)}")
    return pd.DataFrame([
        {"city": city, "latitude": round(median(x for x, _ in samples[city]), 4),
         "longitude": round(median(y for _, y in samples[city]), 4),
         "n_location_observations": len(samples[city])}
        for city in sorted(cities)
    ])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path,
                        help="Rebuild city points using Zillow records. Otherwise reuse the packaged city points.")
    args = parser.parse_args()
    opportunity = pd.read_csv(table_path(DATA, "city_opportunity.csv"))
    fields = ["city", "county", "break_even_alone", "break_even_shared", "break_even_alone_median_debt",
              "median_monthly_rent_1br", "median_monthly_rent_2br", "n_valid_rent_1br", "n_valid_rent_2br"]
    if args.raw_dir is not None:
        points = read_points(args.raw_dir, set(opportunity.city))
    else:
        points = pd.read_csv(CITY_MAP, usecols=["city", "latitude", "longitude", "n_location_observations"])
    city = opportunity[fields].merge(points, on="city", how="left", validate="one_to_one")
    if city[["latitude", "longitude"]].isna().any().any():
        raise ValueError("Missing city points. Rebuild with --raw-dir.")
    city.insert(2, "state", "California")
    city.insert(3, "country", "United States")
    city["annual_pay_difference_alone_vs_shared"] = city.break_even_alone - city.break_even_shared
    city = city.sort_values("city")
    details = []
    for mode, suffix in (("City × occupation median", ""), ("Regional entry-signal occupation median", "_entry_signal")):
        result = pd.read_csv(table_path(DATA, f"combination_results{suffix}.csv"), usecols=[
            "profile", "city", "occupation", "housing_type", "median_annual_salary",
            "n_valid_salary", "n_valid_rent", "feasibility_gap", "rent_burden", "feasible",
        ])
        result["pay_definition"] = mode
        details.append(result)
    scenario = pd.concat(details, ignore_index=True).merge(
        city[["city", "county", "state", "country", "latitude", "longitude"]],
        on="city", how="left", validate="many_to_one",
    )
    if scenario[["latitude", "longitude", "feasibility_gap"]].isna().any().any():
        raise ValueError("Some scenario rows are missing coordinates or budget results.")
    if scenario.duplicated(["pay_definition", "profile", "city", "occupation"]).any():
        raise ValueError("Multiple rows for one pay definition, profile, city and occupation.")
    city.to_csv(CITY_MAP, index=False, float_format="%.4f")
    scenario.to_csv(SCENARIO_MAP, index=False, float_format="%.4f")
    print(f"Exported {len(city)} city rows and {len(scenario):,} modeled scenario rows.")


if __name__ == "__main__":
    main()
