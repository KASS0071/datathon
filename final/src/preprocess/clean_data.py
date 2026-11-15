"""Prepare institution, Indeed posting and Zillow listing data for the Bay Area datathon."""
from __future__ import annotations

import argparse
import hashlib
import csv
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median
from tempfile import TemporaryDirectory

try:
    from openpyxl import load_workbook
except ImportError:
    raise SystemExit("This script requires openpyxl 3.1.5. See README.md for setup.")

import os
import sys

ROOT = Path(__file__).resolve().parents[2]
# Data lives in final/data unless DATATHON_DATA_DIR points elsewhere (e.g. the
# shared ../data folder that holds the 7.6 GB raw files).
DATA_DIR = Path(os.environ.get("DATATHON_DATA_DIR", ROOT / "data")).resolve()
WORKSPACE = DATA_DIR            # processed/ and temp files go here
RAW = Path(os.environ.get("DATATHON_RAW_DIR", DATA_DIR / "raw")).resolve()
if not __package__:
    sys.path.insert(0, str(ROOT))
from src.config import ANNUAL_PAY_RANGE, MAX_HOURLY_AMOUNT
AFFORDABILITY = "Affordability Gap Data AY2022-23 2.17.25.xlsx"
OUTCOMES = "College Results View 2021 Data Dump for Export.xlsx"
INDEED = "indeed_job_listings.csv"
INDEED_SAMPLE = "Indeed job listings information_sample.csv"
ZILLOW = (
    "Zillow_part1.csv", "zillow_part2.csv", "zillow_part3.csv",
    "Zillow properties listing information_sample.csv",
)
# ABAG's nine-county region and membership directory, plus some local postal names.
CITIES_BY_COUNTY = {
    "Alameda": "Alameda|Albany|Berkeley|Castro Valley|Dublin|Emeryville|Fremont|Hayward|Livermore|Newark|Oakland|Piedmont|Pleasanton|San Leandro|San Lorenzo|Sunol|Union City",
    "Contra Costa": "Alamo|Antioch|Bay Point|Brentwood|Clayton|Concord|Danville|El Cerrito|El Sobrante|Hercules|Kensington|Lafayette|Martinez|Moraga|Oakley|Orinda|Pinole|Pittsburg|Pleasant Hill|Richmond|Rodeo|San Pablo|San Ramon|Walnut Creek",
    "Marin": "Belvedere|Corte Madera|Fairfax|Greenbrae|Kentfield|Larkspur|Marin City|Mill Valley|Novato|Ross|San Anselmo|San Rafael|Sausalito|Tiburon",
    "Napa": "American Canyon|Calistoga|Napa|St Helena|Yountville",
    "San Francisco": "San Francisco",
    "San Mateo": "Atherton|Belmont|Brisbane|Burlingame|Colma|Daly City|East Palo Alto|Foster City|Half Moon Bay|Hillsborough|Menlo Park|Millbrae|Pacifica|Portola Valley|Redwood City|San Bruno|San Carlos|San Mateo|South San Francisco|Woodside",
    "Santa Clara": "Campbell|Cupertino|Gilroy|Los Altos|Los Altos Hills|Los Gatos|Milpitas|Monte Sereno|Morgan Hill|Mountain View|Palo Alto|San Jose|Santa Clara|Saratoga|Stanford|Sunnyvale",
    "Solano": "Benicia|Dixon|Fairfield|Rio Vista|Suisun City|Vacaville|Vallejo",
    "Sonoma": "Cloverdale|Cotati|Healdsburg|Petaluma|Rohnert Park|Santa Rosa|Sebastopol|Sonoma|Windsor",
}
FIPS = dict(zip(("06001", "06013", "06041", "06055", "06075", "06081", "06085", "06095", "06097"), CITIES_BY_COUNTY))
COUNTIES = {name.casefold(): name for name in CITIES_BY_COUNTY}
CITIES = {city.casefold(): (city, county) for county, cities in CITIES_BY_COUNTY.items() for city in cities.split("|")}
CITIES["saint helena"] = CITIES["st helena"]
REGION_ONLY_LOCATIONS = {"san francisco bay area", "bay area", "silicon valley", "east bay",
                         "north bay", "south bay"}
CITY_SUFFIX = re.compile(r"(?:^|[ ,])(" + "|".join(
    re.escape(city) for city in sorted(CITIES, key=len, reverse=True)
) + r")$", re.I)
JOB_LOCATION = re.compile(r"^(.+?),\s*(?:CA|California)(?:\s+\d{5}(?:-\d{4})?)?$", re.I)
AFF_FIELDS = {
    "institution_name": "Institution Name", "city": "City", "state": "State Abbreviation",
    "county_name_raw": "County Name", "county_code_raw": "County Code",
    "sector_2022_23": "Sector Name", "highest_degree_2022_23": "Highest Degree Offered Name",
    "msi_type_2022_23": "MSI Type",
    "cost_in_state_on_campus_2022_23_usd": "Cost of Attendance: In State, On Campus",
    "net_price_2022_23_usd": "Net Price",
    "family_income_ceiling_usd": "Student Family Earnings Ceiling",
    "annual_income_estimate_2022_23_usd": "Annual Income Estimate",
    "state_minimum_wage_2022_23_usd": "State Minimum Wage",
    "affordability_gap_2022_23_usd": "Affordability Gap (net price minus income earned working 10 hrs at min wage)",
    "weekly_hours_to_close_gap_2022_23": "Weekly Hours to Close Gap",
    "parent_gap_center_care_2022_23_usd": "Student Parent Affordability Gap: Center-Based Care",
    "parent_gap_home_care_2022_23_usd": "Student Parent Affordability Gap: Home-Based Care",
}
OUTCOME_FIELDS = {
    "institution_name_2021": "Institution Name", "city_2021": "City of Institution",
    "state_2021": "State of Institution", "institution_type_2021": "Institution Type",
    "bachelors_awarded_2021": "Number of Bachelor Degrees Grand Total",
    "graduation_rate_4yr_2021_pct": "Bachelor's Degree Graduation Rate Within 4 Years - Total",
    "graduation_rate_6yr_2021_pct": "Bachelor's Degree Graduation Rate Bachelor Degree Within 6 Years - Total",
    "net_price_2020_21_usd": "Average Net Price After Grants, 2020-21",
    "low_income_net_price_2020_21_usd": "Average Net Price for Low-Income Students, 2020-21",
    "completer_median_debt_2021_usd": "Median Debt of Completers",
    "dependent_median_debt_2021_usd": "Median Debt for Dependent Students",
    "independent_median_debt_2021_usd": "Median Debt for Independent Students",
    "median_earnings_10yr_after_entry_2021_usd": "Median Earnings of Students Working and Not Enrolled 10 Years After Entry",
}
BENCHMARK_METRICS = (
    "net_price_2022_23_usd", "affordability_gap_2022_23_usd",
    "parent_gap_center_care_2022_23_usd", "parent_gap_home_care_2022_23_usd",
    "completer_median_debt_2021_usd", "graduation_rate_6yr_2021_pct",
)
SALARY_AMOUNT = r"\$\s*([\d,]+(?:\.\d{1,2})?)"
SALARY = re.compile(
    rf"(from|up to|desde|hasta)?\s*{SALARY_AMOUNT}(?:\s*(?:-|–|—|to|a)\s*{SALARY_AMOUNT})?"
    r"\s*(?:an?\s+|per\s+|por\s+|/\s*)(hour|day|week|month|year|hr|yr|hora|día|dia|semana|mes|año|ano)"
    r"(?:\s*\+\s*tips)?", re.I,
)
SALARY_UNIT_ALIASES = {
    "hr": "hour", "yr": "year", "hora": "hour", "día": "day", "dia": "day",
    "semana": "week", "mes": "month", "año": "year", "ano": "year",
}
SALARY_BOUND_ALIASES = {"desde": "from", "hasta": "up to"}
ENTRY_TITLE = re.compile(r"\b(?:entry[- ]level|junior|jr\.?|new grad(?:uate)?|trainee|apprentice(?:ship)?)\b", re.I)
SENIOR_TITLE = re.compile(r"\b(?:senior|sr\.?|principal|lead|director|chief)\b", re.I)
ENTRY_TEXT = re.compile(r"\b(?:entry[- ]level|new grad(?:uate)?s? welcome|no (?:prior )?experience (?:is )?(?:required|necessary)|0\s*(?:-|–|to)\s*[12]\s+years?(?: of experience)?)\b", re.I)
EXPERIENCE = re.compile(r"\b(\d+)\s*(?:\+|(?:[-–]|to)\s*\d+)?\s*years?\s+(?:of\s+)?(?:[\w/-]+\s+){0,3}experience\b", re.I)
JOB_FIELDS = ("job_id", "job_title", "company", "city", "county", "job_type",
              "posted_date", "is_expired", "entry_signal", "experience_years_signal_max",
              "salary_original", "salary_status", "salary_unit", "salary_low_usd",
              "salary_high_usd", "annualized_low_usd", "annualized_high_usd", "source_file",
              "annual_pay_status")
RENT_FIELDS = ("zpid", "city", "state", "county", "county_method", "zipcode",
               "bedrooms", "bathrooms", "home_type", "monthly_rent_usd", "rent_price_field",
               "source_file")


def clean(value):
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    value = " ".join(str(value).split())
    return "" if value.casefold() in {"null", "na", "n/a", "nan", "none", "#n/a", "privacysuppressed"} else value


def number(value):
    try:
        n = float(clean(value).replace(",", "").removeprefix("$"))
    except ValueError:
        return None
    return n if math.isfinite(n) else None


def integral(value):
    n = number(value)
    return str(int(n)) if n is not None and n >= 0 and n.is_integer() else ""


def key(value):
    return clean(value).casefold().replace(".", "").replace("é", "e")


def positive(value):
    n = number(value)
    return n if n is not None and n > 0 else None


def load_institutions(raw, filename, id_label, fields, by_income_band=False):
    rows = {}
    counts = Counter()
    workbook = load_workbook(raw / filename, read_only=True, data_only=True)
    try:
        cells = iter(workbook.worksheets[0].values)
        header = {clean(name): i for i, name in enumerate(next(cells))}
        missing = {id_label, *fields.values()} - header.keys()
        if missing:
            raise ValueError(f"{filename}: missing columns {sorted(missing)}")
        for row in cells:
            if not any(v is not None for v in row):
                continue
            counts["rows_read"] += 1
            def get(label):
                index = header[label]
                return row[index] if index < len(row) else None
            uid = integral(get(id_label))
            if not uid or uid == "0":
                counts["missing_id"] += 1
                continue
            record = {field: (number(get(label)) if field.endswith(("_usd", "_pct"))
                              or field.startswith(("bachelors_", "weekly_hours_")) else clean(get(label)))
                      for field, label in fields.items()}
            record_key = uid
            if by_income_band:
                ceiling = record["family_income_ceiling_usd"]
                if ceiling is None or ceiling <= 0:
                    counts["missing_income_band"] += 1
                record_key = (uid, int(ceiling) if ceiling is not None and ceiling > 0 else None)
            if record_key in rows:
                if record != rows[record_key]:
                    raise ValueError(f"{filename}: conflicting records for key {record_key}")
                counts["duplicate_key"] += 1
                continue
            rows[record_key] = record
            counts["retained"] += 1
    finally:
        workbook.close()
    return rows, counts


def write_csv(path, fields, records):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fields)
        writer.writeheader()
        writer.writerows(records)


def county_match(name, fips):
    normalized = key(name).removesuffix(" county")
    code = integral(fips).zfill(5)
    if len(code) == 5 and code.startswith("06"):
        return FIPS.get(code, ""), "county_fips"
    if normalized:
        return COUNTIES.get(normalized, ""), "county_name"
    return "", ""


def prepare_colleges(raw, out):
    bands, aff_counts = load_institutions(raw, AFFORDABILITY, "Unit ID", AFF_FIELDS, by_income_band=True)
    outcomes, out_counts = load_institutions(raw, OUTCOMES, "UNIQUE_IDENTIFICATION_NUMBER_OF_THE_INSTITUTION", OUTCOME_FIELDS)
    profile_fields = ("institution_name", "city", "state", "sector_2022_23",
                      "highest_degree_2022_23", "msi_type_2022_23")
    location_fields = ("unit_id", "is_bay_area", "county", "county_method")
    aff_fields = tuple(k for k in AFF_FIELDS if not k.endswith("_raw"))
    benchmark = defaultdict(list)
    profiles = defaultdict(dict)
    ordered_bands = sorted(bands.items(), key=lambda pair: (int(pair[0][0]), pair[0][1] is None, pair[0][1] or 0))
    for (uid, _), aff in ordered_bands:
        for field in (*profile_fields, "county_name_raw", "county_code_raw"):
            if aff[field] and not profiles[uid].get(field):
                profiles[uid][field] = aff[field]

    records, counts = {}, Counter()
    for uid in sorted(profiles.keys() | outcomes.keys(), key=int):
        aff, results = profiles.get(uid, {}), outcomes.get(uid, {})
        state = aff.get("state") or results.get("state_2021") or ""
        city = aff.get("city") or results.get("city_2021") or ""
        county, method = "", ""
        if state == "CA":
            county, method = county_match(aff.get("county_name_raw"), aff.get("county_code_raw"))
            if not method and key(city) in CITIES:
                county, method = CITIES[key(city)][1], "city_lookup"
        record = {k: v for k, v in aff.items() if k in profile_fields}
        record.update(results)
        coverage = "both" if aff and results else "affordability_only" if aff else "outcomes_only"
        counts[coverage] += 1
        counts["bay_area"] += bool(county)
        record.update(unit_id=uid, source_coverage=coverage, county=county,
                      county_method=method, is_bay_area=int(bool(county)), city=city, state=state,
                      institution_name=aff.get("institution_name") or results.get("institution_name_2021"))
        records[uid] = record
        for field in BENCHMARK_METRICS[4:]:
            add_benchmark(benchmark, field, None, record.get(field), bool(county))

    affordability = []
    for (uid, ceiling), aff in ordered_bands:
        if ceiling is None:
            continue
        location = {k: records[uid][k] for k in location_fields}
        band = {k: aff[k] for k in aff_fields}
        band["family_income_ceiling_usd"] = ceiling
        affordability.append({**location, **band})
        for field in BENCHMARK_METRICS[:4]:
            add_benchmark(benchmark, field, ceiling, aff[field], bool(location["is_bay_area"]))

    fields = (*location_fields, "source_coverage", *profile_fields, *OUTCOME_FIELDS)
    write_csv(out / "colleges.csv", fields, records.values())
    write_csv(out / "colleges_bay_area.csv", fields, (r for r in records.values() if r["is_bay_area"]))
    write_csv(out / "college_affordability_by_income.csv", (*location_fields, *aff_fields), affordability)
    write_csv(out / "college_benchmarks.csv", ("group", "metric", "family_income_ceiling_usd", "institution_count", "median"),
              (dict(group=group, metric=field, family_income_ceiling_usd=ceiling,
                    institution_count=len(values), median=median(values))
               for (group, field, ceiling), values in sorted(benchmark.items())))
    counts["total_institutions"] = len(records)
    counts["affordability_bands"] = len(affordability)
    return {AFFORDABILITY: aff_counts, OUTCOMES: out_counts, "joined": counts}


def add_benchmark(benchmark, field, ceiling, value, is_bay_area):
    if value is not None:
        benchmark["all_workbook_institutions", field, ceiling].append(value)
        if is_bay_area:
            benchmark["bay_area", field, ceiling].append(value)


def salary_fields(raw):
    if not raw:
        return {"salary_status": "missing"}
    match = SALARY.fullmatch(raw)
    if not match:
        return {"salary_status": "unparsed"}
    modifier, first, second, unit = match.groups()
    unit = unit.lower()
    unit = SALARY_UNIT_ALIASES.get(unit, unit)
    modifier = (modifier or "").lower()
    modifier = SALARY_BOUND_ALIASES.get(modifier, modifier)
    first_amount = positive(first)
    second_amount = positive(second) if second else None
    if (first_amount is None or (second and (modifier or second_amount is None))
            or (second_amount is not None and first_amount > second_amount)):
        return {"salary_status": "unparsed"}
    low = None if modifier == "up to" else first_amount
    high = None if modifier == "from" else (second_amount or first_amount)
    factor = {"hour": 2080, "week": 52, "month": 12, "year": 1}.get(unit)
    annual_low, annual_high = None, None
    annual_status = "unsupported_period"
    if unit == "hour" and (high if high is not None else low) > MAX_HOURLY_AMOUNT:
        annual_status = "suspect_hourly_unit"
    elif factor:
        annual_low = round(low * factor, 2) if low is not None else None
        annual_high = round(high * factor, 2) if high is not None else None
        floor, ceiling = ANNUAL_PAY_RANGE
        if any(v is not None and not floor <= v <= ceiling for v in (annual_low, annual_high)):
            annual_status = "outside_benchmark_range"
            annual_low, annual_high = None, None
        else:
            annual_status = "usable"
    return dict(salary_status="parsed", salary_unit=unit, salary_low_usd=low, salary_high_usd=high,
                annualized_low_usd=annual_low, annualized_high_usd=annual_high,
                annual_pay_status=annual_status)


def prepare_jobs(raw, out, filename=INDEED):
    records, seen, counts = [], set(), Counter()
    with (raw / filename).open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"jobid", "location", "region", "country", "job_title", "description_text", "salary_formatted"}
        if missing := required - set(reader.fieldnames or ()):
            raise ValueError(f"{filename}: missing columns {sorted(missing)}")
        for row in reader:
            counts["rows_read"] += 1
            if None in row or None in row.values():
                counts["malformed_row_width"] += 1
                continue
            if row["region"] != "CA" or row["country"] != "US":
                counts["outside_california"] += 1
                continue
            location = JOB_LOCATION.fullmatch(clean(row["location"]))
            city_match = CITY_SUFFIX.search(key(location[1])) if location else None
            if not city_match:
                place = key(location[1]) if location else key(row["location"])
                if place in REGION_ONLY_LOCATIONS:
                    counts["bay_area_region_only"] += 1
                else:
                    counts["no_bay_area_city_match"] += 1
                continue
            city, county = CITIES[city_match[1]]
            job_id = clean(row["jobid"])
            if not job_id:
                counts["missing_id"] += 1
                continue
            if job_id in seen:
                counts["duplicate_id"] += 1
                continue
            seen.add(job_id)
            title, description = clean(row["job_title"]), clean(row["description_text"])
            years = max(map(int, EXPERIENCE.findall(description)), default=None)
            if SENIOR_TITLE.search(title) or (years is not None and years >= 3):
                entry = "senior_or_3plus_years_signal"
            elif ENTRY_TITLE.search(title):
                entry = "entry_title_signal"
            elif ENTRY_TEXT.search(description):
                entry = "entry_description_signal"
            else:
                entry = "unknown"
            salary = clean(row["salary_formatted"])
            pay = salary_fields(salary)
            counts["retained"] += 1
            counts[entry] += 1
            counts["salary_" + pay["salary_status"]] += 1
            if pay["salary_status"] == "parsed":
                counts["annual_pay_" + pay["annual_pay_status"]] += 1
            records.append(dict(job_id=job_id, job_title=title, company=clean(row.get("company_name")),
                                city=city, county=county, job_type=clean(row.get("job_type")),
                                posted_date=clean(row.get("date_posted_parsed"))[:10],
                                is_expired=clean(row.get("is_expired")), entry_signal=entry,
                                experience_years_signal_max=years, salary_original=salary,
                                source_file=filename, **pay))
    write_csv(out / "jobs_bay_area.csv", JOB_FIELDS, records)
    write_csv(out / "jobs_entry_candidates.csv", JOB_FIELDS,
              (r for r in records if r["entry_signal"].startswith("entry_")))
    return counts


def prepare_rentals(raw, out, sample_only):
    paths = ZILLOW[-1:] if sample_only else ZILLOW
    report, seen, groups = {}, set(), defaultdict(list)
    for filename in paths:
        report[filename] = Counter()
    with (out / "rentals_bay_area.csv").open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, RENT_FIELDS)
        writer.writeheader()
        for filename in paths:
            path = raw / filename
            counts = report[filename]
            if not path.exists():
                report[filename] = {"skipped": "file not found"}
                continue
            with path.open("rb") as handle:
                prefix = handle.read(32)
            if b"\x00" in prefix and prefix.startswith(b"book"):
                report[filename] = {"skipped": "macOS Finder alias, not a CSV"}
                continue
            print(f"Reading {filename}", flush=True)
            with path.open(encoding="utf-8-sig", newline="", errors="replace") as handle:
                rows = csv.reader(handle)
                header = next(rows, [])
                keys = ("zpid", "city", "state", "homeStatus", "county", "countyFIPS", "zipcode",
                        "bedrooms", "bathrooms", "homeType", "price", "base_rent", "currency",
                        "isRentalListingOffMarket")
                if missing := set(keys) - set(header):
                    raise ValueError(f"{filename}: missing columns {sorted(missing)}")
                indices = tuple(header.index(k) for k in keys)
                for row in rows:
                    counts["rows_read"] += 1
                    if len(row) != len(header):
                        counts["malformed_row_width"] += 1
                        continue
                    if row[indices[3]] != "FOR_RENT" or row[indices[2]] != "CA":
                        counts["not_california_for_rent"] += 1
                        continue
                    (zpid, city, state, _, county, fips, zipcode, beds, baths, home,
                     price, base, currency, off_market) = (row[i] for i in indices)
                    if off_market.lower() in {"true", "yes", "1"}:
                        counts["off_market"] += 1
                        continue
                    if currency.upper() not in {"USD", ""}:
                        counts["non_usd"] += 1
                        continue
                    matched_county, method = county_match(county, fips)
                    city_match = CITIES.get(key(city))
                    if not method and city_match:
                        matched_county, method = city_match[1], "city_lookup"
                    if not matched_county:
                        counts["no_bay_area_county_match"] += 1
                        continue
                    rent, field = positive(base), "base_rent"
                    if rent is None:
                        rent, field = positive(price), "price"
                    if rent is None:
                        counts["no_positive_listed_rent"] += 1
                        continue
                    zpid = clean(zpid)
                    if not zpid:
                        counts["missing_id"] += 1
                        continue
                    if zpid in seen:
                        counts["duplicate_id"] += 1
                        continue
                    seen.add(zpid)
                    city = city_match[0] if city_match and city_match[1] == matched_county else clean(city).title()
                    beds = integral(beds)
                    writer.writerow(dict(zpid=zpid, city=city, state=state, county=matched_county,
                                         county_method=method, zipcode=clean(zipcode),
                                         bedrooms=beds, bathrooms=number(baths), home_type=clean(home),
                                         monthly_rent_usd=rent, rent_price_field=field, source_file=filename))
                    counts["retained"] += 1
                    counts["missing_currency_assumed_usd"] += not currency
                    if city and beds and "ROOM" not in clean(home).upper():
                        groups[matched_county, city, int(beds)].append(rent)
    # A sample can happen to contain no rental records; a full run should have some.
    if not seen and not sample_only:
        raise ValueError("Full Zillow run retained no Bay Area rentals.")
    write_csv(out / "rent_by_city_bedrooms.csv",
              ("county", "city", "bedrooms", "listing_count", "median_monthly_rent_usd"),
              (dict(county=county, city=city, bedrooms=beds, listing_count=len(rents),
                    median_monthly_rent_usd=median(rents))
               for (county, city, beds), rents in sorted(groups.items())))
    return report


def write_manifest(out, report):
    lines = [
        "# Processed data manifest", "",
        f"Indeed input: {report['indeed_source']}. Sha256 identifies the generated snapshot.",
        "See ../../docs/DATA_NOTES.md for interpretation and source limitations.", "",
        "| File | Data rows | SHA-256 |", "| --- | ---: | --- |",
    ]
    for file in sorted(out.iterdir()):
        if file.suffix not in {".csv", ".json"}:
            continue
        with file.open("rb") as handle:
            digest = hashlib.file_digest(handle, "sha256").hexdigest()
        count = "—"
        if file.suffix == ".csv":
            with file.open(encoding="utf-8", newline="") as handle:
                count = f"{sum(1 for _ in csv.reader(handle)) - 1:,}"
        lines.append(f"| {file.name} | {count} | {digest} |")
    (out / "MANIFEST.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample-only", action="store_true", help="Use the small Indeed and Zillow samples; write to processed_sample/.")
    args = parser.parse_args()
    target = WORKSPACE / ("processed_sample" if args.sample_only else "processed")
    if target.is_symlink():
        parser.error(f"Output folder must not be a symlink: {target}")
    csv.field_size_limit(32 * 1024 * 1024)
    indeed = INDEED_SAMPLE if args.sample_only else INDEED
    if not (RAW / indeed).is_file():
        parser.error(f"Missing Indeed input: {RAW / indeed}. Use --sample-only for a development run.")
    with TemporaryDirectory(dir=WORKSPACE, prefix=".preprocess-") as tmp:
        staging = Path(tmp)
        print(f"Reading {indeed}", flush=True)
        jobs = prepare_jobs(RAW, staging, indeed)
        if not args.sample_only and not jobs["retained"]:
            raise ValueError(f"{indeed}: retained no Bay Area postings.")
        print("Preparing colleges", flush=True)
        report = {
            "sample_only": args.sample_only,
            "indeed_source": indeed,
            "colleges": prepare_colleges(RAW, staging),
            "jobs": jobs,
            "zillow": prepare_rentals(RAW, staging, args.sample_only),
        }
        (staging / "quality_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        write_manifest(staging, report)
        target.mkdir(exist_ok=True)
        for path in sorted(staging.iterdir()):
            path.replace(target / path.name)
    print(f"Saved {target}", flush=True)


if __name__ == "__main__":
    main()
