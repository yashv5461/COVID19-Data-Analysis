"""
prepare_data.py
---------------
Builds the cleaned project dataset (data/dataset.csv) from the public
Our World in Data (OWID) COVID-19 dataset, using the same 8 columns as the
dataset.csv supplied with the project brief:

    date, country, confirmed, deaths, recovered, vaccinated, population, continent

It also writes:
    data/anomalies.csv         rows flagged by the data-quality rules
    data/cleaning_log.csv      row counts at each cleaning step

Source: Our World in Data, COVID-19 dataset (CC BY 4.0)
        https://github.com/owid/covid-19-data

Run from the project root:
    python src/prepare_data.py
"""

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "owid-covid-data.csv"
OUT = ROOT / "data" / "dataset.csv"
ANOM = ROOT / "data" / "anomalies.csv"
LOG = ROOT / "data" / "cleaning_log.csv"

OWID_URL = ("https://raw.githubusercontent.com/owid/covid-19-data/"
            "master/public/data/owid-covid-data.csv")

# Days after which a confirmed case is assumed to have recovered (if not dead).
# OWID does not publish recoveries, so this column is an ESTIMATE.
RECOVERY_DAYS = 14

USE_COLS = ["iso_code", "continent", "location", "date", "total_cases",
            "total_deaths", "people_vaccinated", "population"]


def load_raw() -> pd.DataFrame:
    if not RAW.exists():
        print("Raw file not found, downloading from OWID GitHub ...")
        RAW.parent.mkdir(parents=True, exist_ok=True)
        pd.read_csv(OWID_URL).to_csv(RAW, index=False)
    return pd.read_csv(RAW, usecols=USE_COLS)


def main() -> None:
    log = []
    df = load_raw()
    log.append(("1. Raw OWID file", len(df), df["location"].nunique()))

    # Step 2: keep countries only. OWID aggregates (World, continents, income
    # groups, EU, UK nations) have iso codes that start with OWID_. Kosovo is
    # a country but also uses an OWID_ code, so it is kept.
    is_aggregate = df["iso_code"].str.startswith("OWID_") & (df["iso_code"] != "OWID_KOS")
    df = df[~is_aggregate & df["continent"].notna()].copy()
    # ISO codes are not part of the 8-column schema; saved separately for maps
    (df[["location", "iso_code"]].drop_duplicates()
       .rename(columns={"location": "country"})
       .to_csv(ROOT / "data" / "country_codes.csv", index=False))
    log.append(("2. Remove regional / income aggregates", len(df), df["location"].nunique()))

    # Step 3: drop rows before a country started reporting cases
    df = df[df["total_cases"].notna() & df["total_deaths"].notna()].copy()
    log.append(("3. Remove rows before reporting began", len(df), df["location"].nunique()))

    # Step 4: types, names, duplicates, sort
    df["date"] = pd.to_datetime(df["date"], format="%Y-%m-%d")
    df["location"] = df["location"].str.strip()
    df = df.drop_duplicates(subset=["location", "date"]).sort_values(["location", "date"])
    log.append(("4. Remove duplicate country-date rows", len(df), df["location"].nunique()))

    # Step 5: vaccinated (people with at least one dose) is reported irregularly.
    # It is a running total, so the last known value is carried forward; days
    # before a country's first report are set to 0. Countries that never
    # reported vaccinations stay empty (NaN) rather than being invented.
    g = df.groupby("location")["people_vaccinated"]
    first_vax = df.loc[df["people_vaccinated"].notna()].groupby("location")["date"].min()
    df["vaccinated"] = g.ffill()
    before_first = df["date"] < df["location"].map(first_vax)
    df.loc[before_first, "vaccinated"] = 0

    # Step 6: recovered = confirmed 14 days earlier minus deaths to date (>= 0)
    lagged = df.groupby("location")["total_cases"].shift(RECOVERY_DAYS).fillna(0)
    df["recovered"] = (lagged - df["total_deaths"]).clip(lower=0)

    # Step 7: rename to the project schema
    df = df.rename(columns={"location": "country", "total_cases": "confirmed",
                            "total_deaths": "deaths"})
    df = df[["date", "country", "confirmed", "deaths", "recovered",
             "vaccinated", "population", "continent"]]
    for col in ["confirmed", "deaths", "recovered", "population"]:
        df[col] = df[col].round().astype("int64")
    df["vaccinated"] = df["vaccinated"].round().astype("Int64")
    log.append(("5-7. Fill vaccinated, estimate recovered, rename columns", len(df), df["country"].nunique()))

    # ---------------- Data-quality rules (rows are flagged, not deleted) -----
    df = df.sort_values(["country", "date"]).reset_index(drop=True)
    grp = df.groupby("country")
    new_cases = grp["confirmed"].diff()
    new_deaths = grp["deaths"].diff()
    # OWID/WHO totals change once a week, so compare each reported value with
    # the average weekly total of the previous 4 weeks (28 days / 4).
    avg_week = new_cases.clip(lower=0).groupby(df["country"]).transform(
        lambda s: s.rolling(28, min_periods=28).sum().shift(1) / 4)

    rules = {
        "confirmed_decreased": new_cases < 0,
        "deaths_decreased": new_deaths < 0,
        "deaths_exceed_confirmed": df["deaths"] > df["confirmed"],
        "vaccinated_exceed_population": df["vaccinated"].astype("float") > df["population"],
        "case_spike_over_5x_4week_avg": (new_cases > 5 * avg_week) & (new_cases > 1000),
    }
    flags = []
    for name, mask in rules.items():
        hit = df.loc[mask.fillna(False), ["date", "country", "confirmed", "deaths",
                                         "vaccinated", "population"]].copy()
        hit["issue"] = name
        flags.append(hit)
    anomalies = pd.concat(flags).sort_values(["country", "date"])
    anomalies["date"] = anomalies["date"].dt.strftime("%Y-%m-%d")

    # ---------------- Save ---------------------------------------------------
    df["date"] = df["date"].dt.strftime("%Y-%m-%d")
    df.to_csv(OUT, index=False)
    anomalies.to_csv(ANOM, index=False)
    pd.DataFrame(log, columns=["step", "rows", "countries"]).to_csv(LOG, index=False)

    flagged_rows = anomalies[["date", "country"]].drop_duplicates().shape[0]
    print(f"Saved {OUT.name}: {len(df):,} rows, {df['country'].nunique()} countries, "
          f"{df['date'].min()} to {df['date'].max()}")
    print(f"Flagged rows: {flagged_rows:,} ({flagged_rows / len(df):.2%})")
    print(anomalies["issue"].value_counts())


if __name__ == "__main__":
    main()
