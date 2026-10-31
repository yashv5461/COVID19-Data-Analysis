"""Generates notebooks/COVID19_Data_Analysis.ipynb (run once, then executed with nbconvert)."""
from pathlib import Path
import nbformat as nbf

nb = nbf.v4.new_notebook()
C = []
md = lambda s: C.append(nbf.v4.new_markdown_cell(s.strip()))
code = lambda s: C.append(nbf.v4.new_code_cell(s.strip()))

md("""
# COVID-19 Data Analysis and Visualisation
**HCLTech Career Shaper Programme | Project No. 48 | Domain: Data Analytics / Python**

| Field | Details |
|---|---|
| Learner | Yash Verma (Roll No. 2300320130290) |
| College | ABES EC |
| Mentor | Dipali Kedar Patki |
| Submission | 31 October 2026 |

**Data source:** Our World in Data (OWID) COVID-19 dataset, licensed CC BY 4.0 - https://github.com/owid/covid-19-data.
OWID compiles official figures reported to the WHO and national health authorities. All figures here are *reported* figures; true infections and deaths were higher in many countries because of limited testing.

**Notebook outline**
1. Setup
2. Audit of the dataset.csv supplied with the brief
3. Load and check the cleaned dataset
4. Feature engineering (daily values, per-million rates, case fatality rate, vaccination coverage)
5. Global overview and pandemic waves
6. Country and continent comparison
7. Vaccination analysis
8. Case study: India
9. Correlation analysis
10. Data-quality flags (anomalies)
11. Key findings
""")

md("## 1. Setup")
code("""
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import seaborn as sns
from scipy import stats

warnings.filterwarnings("ignore")
pd.set_option("display.float_format", lambda v: f"{v:,.2f}")
pd.set_option("display.width", 120)

ROOT = Path("..")
DATA = ROOT / "data"
IMG = ROOT / "images"
IMG.mkdir(exist_ok=True)

# Fixed colour per continent (same colour for the same continent in every chart)
CONTINENT_COLORS = {"Africa": "#2a78d6", "Asia": "#eb6834", "Europe": "#1baf7a",
                    "North America": "#eda100", "Oceania": "#e87ba4", "South America": "#008300"}
BLUE, ORANGE, GREY = "#2a78d6", "#eb6834", "#8a8984"

sns.set_theme(style="whitegrid", font_scale=0.95)
plt.rcParams.update({"figure.dpi": 110, "savefig.dpi": 160, "savefig.bbox": "tight",
                     "axes.spines.top": False, "axes.spines.right": False,
                     "grid.color": "#e6e5e1", "axes.edgecolor": "#b5b4ae",
                     "axes.titleweight": "bold", "axes.titlesize": 12})

def save(fig, name):
    fig.savefig(IMG / name)
    plt.show()

millions = mtick.FuncFormatter(lambda v, _: f"{v/1e6:,.0f}M" if abs(v) >= 1e6 else f"{v/1e3:,.0f}K")
""")

md("""
## 2. Audit of the dataset.csv supplied with the brief
The brief supplied a 500-row `dataset.csv` (10 countries x 50 days, Jan-Feb 2024). Before using it, its values were checked for internal consistency.
""")
code("""
orig = pd.read_csv(DATA / "dataset_original.csv")
print("Shape:", orig.shape)
print("Missing values:", orig.isna().sum().sum(), "| Duplicate rows:", orig.duplicated().sum())
orig.head()
""")
code("""
s = orig.sort_values("date")
audit = pd.DataFrame({
    "Check": [
        "Countries with more than one population value",
        "Countries assigned to more than one continent",
        "Rows where vaccinated > population",
        "Rows where deaths > confirmed",
        "Rows where recovered > confirmed",
        "Countries whose cumulative 'confirmed' ever falls",
    ],
    "Result": [
        f"{(orig.groupby('country')['population'].nunique() > 1).sum()} of {orig['country'].nunique()}",
        f"{(orig.groupby('country')['continent'].nunique() > 1).sum()} of {orig['country'].nunique()}",
        f"{(orig['vaccinated'] > orig['population']).sum()} of {len(orig)} ({(orig['vaccinated'] > orig['population']).mean():.0%})",
        f"{(orig['deaths'] > orig['confirmed']).sum()} of {len(orig)}",
        f"{(orig['recovered'] > orig['confirmed']).sum()} of {len(orig)} ({(orig['recovered'] > orig['confirmed']).mean():.0%})",
        f"{(~s.groupby('country')['confirmed'].apply(lambda x: x.is_monotonic_increasing)).sum()} of {orig['country'].nunique()}",
    ]})
audit
""")
code("""
# Example: the same country carries five different populations and continents
orig[orig["country"] == "India"][["date", "country", "population", "continent"]].head(5)
""")
md("""
**Conclusion of the audit.** The supplied file has no missing values, but its numbers are not internally consistent: each country has five different populations and continents (India appears as "Oceania" with 330 million people), vaccinated exceeds population in most rows, and cumulative counts rise and fall at random. Charts built on it would show noise, not the pandemic.

As the brief's dataset prompt recommends (*"Use Our World in Data COVID-19 dataset ... Clean and analyse 200,000+ rows across 200 countries"*), the analysis below uses the real OWID data, reshaped by `src/prepare_data.py` into **exactly the same 8 columns**. The supplied file is kept unchanged as `data/dataset_original.csv`.
""")

md("## 3. Load and check the cleaned dataset")
code("""
print(pd.read_csv(DATA / "cleaning_log.csv").to_string(index=False))
df = pd.read_csv(DATA / "dataset.csv", parse_dates=["date"])
print()
print("Rows x columns:", df.shape)
print("Countries:", df["country"].nunique(), "| Continents:", df["continent"].nunique())
print("Date range:", df["date"].min().date(), "to", df["date"].max().date())
print("Duplicate country-date rows:", df.duplicated(["country", "date"]).sum())
df.head()
""")
code("""
df.info()
""")
code("""
print("Missing values per column:")
print(df.isna().sum())
no_vax = df.loc[df["vaccinated"].isna(), "country"].unique()
print(f"\\nCountries that never reported vaccinations ({len(no_vax)}):", ", ".join(sorted(no_vax)))
""")
code("""
df.describe().T
""")

md("""
## 4. Feature engineering
The cleaned file holds **cumulative** totals. Daily new cases and deaths are the day-to-day differences (negative values, caused by data revisions, are set to 0). OWID takes these figures from the WHO, which publishes country totals once a week, so the cumulative value changes on one day each week and the daily difference is 0 on the other six days. Trends are therefore shown as weekly totals, or as 7-day averages (the weekly total divided by 7).
""")
code("""
df = df.sort_values(["country", "date"]).reset_index(drop=True)
g = df.groupby("country")
df["new_cases"] = g["confirmed"].diff().clip(lower=0).fillna(df["confirmed"])
df["new_deaths"] = g["deaths"].diff().clip(lower=0).fillna(df["deaths"])
df["cases_per_million"] = df["confirmed"] / df["population"] * 1e6
df["deaths_per_million"] = df["deaths"] / df["population"] * 1e6
df["vax_coverage_pct"] = (df["vaccinated"] / df["population"] * 100).clip(upper=100)

latest = df[df["date"] == df["date"].max()].copy()
latest["cfr_pct"] = latest["deaths"] / latest["confirmed"] * 100
latest.to_csv(DATA / "country_summary.csv", index=False)
big = latest[latest["population"] >= 1_000_000]          # used for per-capita rankings
print("Countries in latest snapshot:", len(latest), "| with population >= 1 million:", len(big))
""")

md("## 5. Global overview and pandemic waves")
code("""
world_pop = latest["population"].sum()
kpi = pd.Series({
    "Total confirmed cases": f"{latest['confirmed'].sum():,.0f}",
    "Total deaths": f"{latest['deaths'].sum():,.0f}",
    "Case fatality rate (deaths / cases)": f"{latest['deaths'].sum() / latest['confirmed'].sum():.2%}",
    "People with at least one vaccine dose": f"{latest['vaccinated'].sum():,.0f}",
    "Share of world population vaccinated (1+ dose)": f"{latest['vaccinated'].sum() / world_pop:.1%}",
    "Deaths per million people": f"{latest['deaths'].sum() / world_pop * 1e6:,.0f}",
}, name=f"As of {df['date'].max().date()}")
kpi.to_frame()
""")
code("""
weekly = df.set_index("date").groupby(pd.Grouper(freq="W"))[["new_cases", "new_deaths"]].sum()
weekly = weekly[weekly.index <= df["date"].max()]

fig, ax = plt.subplots(figsize=(11, 4.2))
ax.plot(weekly.index, weekly["new_cases"], color=BLUE, lw=2)
ax.yaxis.set_major_formatter(millions)
ax.set_title("Weekly new confirmed COVID-19 cases, world")
ax.set_ylabel("New cases per week"); ax.set_xlabel("")
peak = weekly["new_cases"].idxmax()
om = weekly.loc["2022-01":"2022-02", "new_cases"]; op = om.idxmax()
ax.annotate(f"Omicron wave\\n{om.max()/1e6:,.1f}M cases (week of {op:%d %b %Y})",
            xy=(op, om.max()), xytext=(op - pd.Timedelta(days=330), om.max()*1.15),
            arrowprops=dict(arrowstyle="-", color=GREY), fontsize=9)
ax.annotate(f"China reporting backlog\\n{weekly['new_cases'].max()/1e6:,.1f}M in one week ({peak:%d %b %Y})",
            xy=(peak, weekly["new_cases"].max()), xytext=(peak + pd.Timedelta(days=90), weekly["new_cases"].max()*0.8),
            arrowprops=dict(arrowstyle="-", color=GREY), fontsize=9)
d = weekly.loc["2021-03":"2021-07", "new_cases"]; dp = d.idxmax()
ax.annotate("Delta wave", xy=(dp, d.max()), xytext=(dp - pd.Timedelta(days=200), d.max()*2.2),
            arrowprops=dict(arrowstyle="-", color=GREY), fontsize=9)
save(fig, "fig01_weekly_cases.png")
china = df[(df["country"] == "China")].set_index("date")["new_cases"].resample("W").sum()
print("Highest week:", peak.date(), f"{weekly['new_cases'].max():,.0f} cases, of which China {china.loc[peak]:,.0f}")
print("Omicron peak week:", op.date(), f"{om.max():,.0f} cases")
""")
code("""
fig, ax = plt.subplots(figsize=(11, 4.2))
ax.plot(weekly.index, weekly["new_deaths"], color=ORANGE, lw=2)
ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"{v/1e3:,.0f}K"))
ax.set_title("Weekly new COVID-19 deaths, world")
ax.set_ylabel("Deaths per week"); ax.set_xlabel("")
pk = weekly["new_deaths"].idxmax()
ax.annotate(f"Peak: {weekly['new_deaths'].max():,.0f} deaths (week of {pk:%d %b %Y})",
            xy=(pk, weekly["new_deaths"].max()), xytext=(pk + pd.Timedelta(days=120), weekly["new_deaths"].max()*0.9),
            arrowprops=dict(arrowstyle="-", color=GREY), fontsize=9)
save(fig, "fig02_weekly_deaths.png")
yearly = df.groupby(df["date"].dt.year)[["new_cases", "new_deaths"]].sum()
yearly["cfr_pct"] = yearly["new_deaths"] / yearly["new_cases"] * 100
yearly
""")
md("""
The largest sustained wave of cases was Omicron in January 2022. The single highest week (late December 2022) is a reporting artefact: China reported about 40 million cases at once after ending its zero-COVID policy, and this row is caught by the spike rule in Section 10. Deaths peaked much earlier, in January 2021 and during the Delta period; the short spike in deaths in early 2023 is again China's backlog. The case fatality rate fell from 2.4% in 2020 to under 0.5% in 2022-23: more testing found milder cases, treatment improved, and vaccines reduced severe illness. The 2024 figure is unreliable because very few cases were still being tested and reported.
""")
code("""
monthly = df.set_index("date").groupby(pd.Grouper(freq="MS"))[["new_cases", "new_deaths"]].sum()
monthly = monthly[(monthly.index >= "2020-03-01") & (monthly.index < "2024-01-01")]  # 2024 reporting too sparse
monthly["cfr_pct"] = monthly["new_deaths"] / monthly["new_cases"] * 100

fig, ax = plt.subplots(figsize=(11, 3.8))
ax.plot(monthly.index, monthly["cfr_pct"], color=BLUE, lw=2, marker="o", ms=3)
ax.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=1))
ax.set_title("Monthly case fatality rate (deaths / new cases), world")
ax.set_ylabel("Case fatality rate"); ax.set_xlabel("")
save(fig, "fig03_cfr_trend.png")
""")

md("## 6. Country and continent comparison")
code("""
top = latest.nlargest(15, "confirmed").sort_values("confirmed")
fig, ax = plt.subplots(figsize=(10, 6))
ax.barh(top["country"], top["confirmed"], color=[CONTINENT_COLORS[c] for c in top["continent"]], height=0.65)
ax.xaxis.set_major_formatter(millions)
for y, v in enumerate(top["confirmed"]):
    ax.text(v, y, f"  {v/1e6:,.1f}M", va="center", fontsize=8.5, color="#333")
ax.set_title("Top 15 countries by total reported cases")
ax.set_xlabel("Total confirmed cases"); ax.grid(axis="y", visible=False)
handles = [plt.Rectangle((0, 0), 1, 1, color=CONTINENT_COLORS[c]) for c in CONTINENT_COLORS if c in set(top["continent"])]
ax.legend(handles, [c for c in CONTINENT_COLORS if c in set(top["continent"])], loc="lower right", frameon=False, title="Continent")
ax.set_xlim(0, top["confirmed"].max() * 1.15)
save(fig, "fig04_top15_cases.png")
""")
code("""
top_dpm = big.nlargest(15, "deaths_per_million").sort_values("deaths_per_million")
fig, ax = plt.subplots(figsize=(10, 6))
ax.barh(top_dpm["country"], top_dpm["deaths_per_million"],
        color=[CONTINENT_COLORS[c] for c in top_dpm["continent"]], height=0.65)
for y, v in enumerate(top_dpm["deaths_per_million"]):
    ax.text(v, y, f"  {v:,.0f}", va="center", fontsize=8.5, color="#333")
ax.set_title("Highest reported deaths per million people (countries with population >= 1M)")
ax.set_xlabel("Deaths per million people"); ax.grid(axis="y", visible=False)
present = [c for c in CONTINENT_COLORS if c in set(top_dpm["continent"])]
ax.legend([plt.Rectangle((0, 0), 1, 1, color=CONTINENT_COLORS[c]) for c in present], present,
          loc="lower right", frameon=False, title="Continent")
ax.set_xlim(0, top_dpm["deaths_per_million"].max() * 1.15)
save(fig, "fig05_top15_deaths_per_million.png")
""")
md("""
Total counts favour large countries (USA, China, India). Per-million rates give a fairer comparison of the burden: by this measure the highest reported death rates are in Peru and in Eastern and Central Europe.
""")
code("""
cont = latest.groupby("continent").agg(countries=("country", "count"), population=("population", "sum"),
                                       confirmed=("confirmed", "sum"), deaths=("deaths", "sum"),
                                       vaccinated=("vaccinated", "sum"))
cont["cases_per_million"] = cont["confirmed"] / cont["population"] * 1e6
cont["deaths_per_million"] = cont["deaths"] / cont["population"] * 1e6
cont["cfr_pct"] = cont["deaths"] / cont["confirmed"] * 100
cont["vaccinated_pct"] = cont["vaccinated"] / cont["population"] * 100
cont.sort_values("deaths_per_million", ascending=False)
""")
code("""
order = big.groupby("continent")["deaths_per_million"].median().sort_values(ascending=False).index
fig, ax = plt.subplots(figsize=(10, 4.8))
sns.boxplot(data=big, x="continent", y="deaths_per_million", order=order, palette=CONTINENT_COLORS,
            width=0.55, fliersize=0, boxprops=dict(alpha=0.35), ax=ax)
sns.stripplot(data=big, x="continent", y="deaths_per_million", order=order, palette=CONTINENT_COLORS,
              size=4, jitter=0.18, ax=ax)
ax.set_title("Deaths per million by continent (each dot is a country, population >= 1M)")
ax.set_xlabel(""); ax.set_ylabel("Deaths per million people")
save(fig, "fig06_continent_box.png")
""")
code("""
heat = (df.assign(month=df["date"].dt.to_period("Q").astype(str))
          .groupby(["continent", "month"]).agg(cases=("new_cases", "sum")).reset_index())
pop_c = latest.groupby("continent")["population"].sum()
heat["cases_per_million"] = heat["cases"] / heat["continent"].map(pop_c) * 1e6
pivot = heat.pivot(index="continent", columns="month", values="cases_per_million")
pivot = pivot.loc[:, (pivot.columns >= "2020Q1") & (pivot.columns <= "2024Q2")]
fig, ax = plt.subplots(figsize=(12, 3.8))
sns.heatmap(pivot, cmap="Blues", linewidths=1, linecolor="white", ax=ax,
            cbar_kws={"label": "New cases per million in quarter"}, annot=False)
ax.set_title("New cases per million people by continent and quarter")
ax.set_xlabel(""); ax.set_ylabel("")
save(fig, "fig07_continent_quarter_heatmap.png")
""")

md("## 7. Vaccination analysis")
code("""
vax = df.dropna(subset=["vaccinated"]).groupby(["date", "continent"]).agg(vaccinated=("vaccinated", "sum")).reset_index()
pop_rep = df.dropna(subset=["vaccinated"]).drop_duplicates("country").groupby("continent")["population"].sum()
vax["coverage_pct"] = vax["vaccinated"] / vax["continent"].map(pop_rep) * 100
vax = vax[vax["date"] >= "2020-12-01"]

fig, ax = plt.subplots(figsize=(11, 4.6))
ends = {}
for c, col in CONTINENT_COLORS.items():
    s = vax[vax["continent"] == c]
    ax.plot(s["date"], s["coverage_pct"], color=col, lw=2, label=c)
    ends[c] = s["coverage_pct"].iloc[-1]
# direct labels at the line ends, nudged apart so they do not overlap
prev = None
for c, y in sorted(ends.items(), key=lambda kv: -kv[1]):
    y_lab = y if prev is None else min(y, prev - 4)
    ax.text(vax["date"].max() + pd.Timedelta(days=12), y_lab, f"{c} {y:.0f}%", color="#333", fontsize=8.5, va="center")
    prev = y_lab
ax.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
ax.set_ylim(0, 100); ax.set_xlim(right=vax["date"].max() + pd.Timedelta(days=230))
ax.set_title("Share of population with at least one vaccine dose, by continent")
ax.set_ylabel("Population vaccinated (1+ dose)"); ax.set_xlabel("")
ax.legend(frameon=False, ncol=3, loc="upper left")
save(fig, "fig08_vaccination_by_continent.png")
vax[vax["date"] == vax["date"].max()][["continent", "coverage_pct"]].sort_values("coverage_pct", ascending=False)
""")
md("""
Vaccination rolled out from December 2020. Coverage rose fastest in North America and Europe at first, and South America reached the highest level (86%). Africa lagged far behind (39%), reflecting unequal access to vaccine supplies. The sudden step in Asia's line in mid-2021 is when China began reporting the number of people vaccinated, not a single-day event.
""")
code("""
# Does higher vaccination coverage by end-2021 go with fewer deaths in 2022?
end21 = df[df["date"] == "2021-12-31"].set_index("country")
d22 = (df[df["date"].dt.year == 2022].groupby("country")["new_deaths"].sum())
sc = pd.DataFrame({"vax_end_2021": end21["vax_coverage_pct"], "pop": end21["population"],
                   "continent": end21["continent"], "deaths_2022": d22}).dropna()
sc = sc[sc["pop"] >= 1_000_000]
sc["deaths_pm_2022"] = sc["deaths_2022"] / sc["pop"] * 1e6
rho, p = stats.spearmanr(sc["vax_end_2021"], sc["deaths_pm_2022"])
print(f"Countries: {len(sc)} | Spearman rho = {rho:.2f}, p = {p:.3g}")

fig, ax = plt.subplots(figsize=(10, 5))
for c, col in CONTINENT_COLORS.items():
    s = sc[sc["continent"] == c]
    ax.scatter(s["vax_end_2021"], s["deaths_pm_2022"], s=34, color=col, label=c, edgecolor="white", lw=0.8)
ax.set_title("Vaccination coverage at end-2021 vs deaths per million in 2022")
ax.set_xlabel("Population with 1+ dose on 31 Dec 2021 (%)"); ax.set_ylabel("Deaths per million during 2022")
ax.legend(frameon=False, fontsize=8.5, title="Continent")
save(fig, "fig09_vax_vs_deaths_scatter.png")
""")
md("""
The relationship is **positive** (Spearman rho about 0.6): countries that were more vaccinated at the end of 2021 *reported* more deaths per million in 2022. This seems surprising. It is a good example of *confounding*: countries with high vaccination are mostly richer countries with older populations and much more testing and death reporting, so they record more COVID deaths. A simple country-level correlation cannot show the effect of vaccines; clinical trials and studies that compare vaccinated and unvaccinated individuals are needed for that. This finding is reported as an association only.
""")

md("## 8. Case study: India")
code("""
india = df[df["country"] == "India"].set_index("date")
india_7d = india["new_cases"].rolling(7).mean()
fig, ax = plt.subplots(figsize=(11, 4))
ax.plot(india_7d.index, india_7d, color=BLUE, lw=2)
ax.yaxis.set_major_formatter(millions)
pk = india_7d.loc["2021"].idxmax()
ax.annotate(f"Delta wave peak: {india_7d.max():,.0f} cases/day\\n(7-day average, {pk:%d %b %Y})",
            xy=(pk, india_7d.loc[pk]), xytext=(pk + pd.Timedelta(days=90), india_7d.loc[pk]*0.85),
            arrowprops=dict(arrowstyle="-", color=GREY), fontsize=9)
ax.set_title("India, daily new cases (7-day average)")
ax.set_ylabel("New cases per day"); ax.set_xlabel("")
ax.set_xlim(pd.Timestamp("2020-03-01"), pd.Timestamp("2023-06-30"))
save(fig, "fig10_india_daily_cases.png")
il = latest[latest["country"] == "India"].iloc[0]
print(f"India: {il['confirmed']:,} cases | {il['deaths']:,} deaths | CFR {il['cfr_pct']:.2f}% | "
      f"{il['deaths_per_million']:,.0f} deaths per million | {il['vax_coverage_pct']:.1f}% vaccinated (1+ dose)")
""")

md("## 9. Correlation analysis")
code("""
corr_cols = {"cases_per_million": "Cases per million", "deaths_per_million": "Deaths per million",
             "cfr_pct": "Case fatality rate", "vax_coverage_pct": "Vaccinated %", "population": "Population"}
cm = big[list(corr_cols)].rename(columns=corr_cols).corr(method="spearman")
fig, ax = plt.subplots(figsize=(7, 5.5))
sns.heatmap(cm, annot=True, fmt=".2f", cmap="RdBu_r", vmin=-1, vmax=1, center=0, square=True,
            linewidths=1, linecolor="white", cbar_kws={"shrink": 0.8}, ax=ax)
ax.set_title("Spearman correlation of country-level metrics\\n(latest values, population >= 1M)")
save(fig, "fig11_correlation_heatmap.png")
""")
md("""
Cases per million is strongly correlated with deaths per million (0.85) and moderately with vaccination coverage (0.53): all three tend to be higher in countries with stronger testing and reporting systems. Case fatality rate is *negatively* correlated with cases per million (-0.52): countries that tested widely found many mild cases, which lowers the ratio. Population size has little relationship with any rate.
""")

md("## 10. Data-quality flags (anomalies)")
code("""
anom = pd.read_csv(DATA / "anomalies.csv")
flag_rows = anom[["date", "country"]].drop_duplicates().shape[0]
print(f"Flagged rows: {flag_rows:,} of {len(df):,} ({flag_rows/len(df):.2%})")
anom.groupby("issue").agg(rows=("country", "size"), countries=("country", "nunique")).sort_values("rows", ascending=False)
""")
md("""
| Rule | Meaning | Treatment |
|---|---|---|
| vaccinated_exceed_population | More people vaccinated than the official population (e.g. UAE, Qatar, Gibraltar vaccinate non-resident workers and visitors) | Kept; coverage capped at 100% in charts |
| case_spike_over_5x_4week_avg | A weekly total more than 5 times the average of the previous 4 weeks (and above 1,000), e.g. China's December 2022 backlog, or the first fast weeks of a new wave | Kept, labelled on the weekly cases chart (Section 5) |
| deaths_exceed_confirmed | Early-2020 reporting mismatches (e.g. France, Germany) | Kept and flagged |
| confirmed_decreased / deaths_decreased | Cumulative totals revised downwards | Daily values set to 0 for those days |

Rows were **flagged, not deleted**, so the cleaned dataset stays faithful to the official source.
""")

md("## 11. Key findings")
code("""
f = {
    "Total reported cases": f"{latest['confirmed'].sum()/1e6:,.1f} million",
    "Total reported deaths": f"{latest['deaths'].sum()/1e6:,.2f} million",
    "Overall case fatality rate": f"{latest['deaths'].sum()/latest['confirmed'].sum():.2%}",
    "Omicron peak week (cases)": f"{op:%d %b %Y}",
    "Peak week for deaths": f"{weekly['new_deaths'].idxmax():%d %b %Y}",
    "CFR in 2020 vs 2023": f"{yearly.loc[2020, 'cfr_pct']:.2f}% vs {yearly.loc[2023, 'cfr_pct']:.2f}%",
    "Most cases (total)": latest.nlargest(1, 'confirmed')['country'].iloc[0],
    "Highest deaths per million (pop >= 1M)": big.nlargest(1, 'deaths_per_million')['country'].iloc[0],
    "World population vaccinated (1+ dose)": f"{latest['vaccinated'].sum()/world_pop:.1%}",
    "Rows flagged by quality rules": f"{flag_rows/len(df):.2%}",
}
pd.Series(f, name="Value").to_frame()
""")
md("""
1. **Scale:** more than 775 million cases and about 7 million deaths were reported worldwide between January 2020 and August 2024.
2. **Waves:** the biggest wave of cases was Omicron (January 2022), while deaths peaked earlier, in January 2021 and during the Delta wave. The single highest week (December 2022) is a China reporting backlog, which the quality rules flag.
3. **Severity fell:** the case fatality rate fell from 2.36% in 2020 to 0.29% in 2022 and 0.47% in 2023.
4. **Fair comparison needs per-capita figures:** totals rank the USA, China and India first, but per-million rates show the heaviest reported death burden in Peru and Eastern and Central Europe.
5. **Unequal vaccination:** Africa's vaccination coverage stayed far behind other continents.
6. **Correlation is not causation:** the country-level association between vaccination and deaths is distorted by reporting quality and population age.

*Interactive dashboard:* run `python src/build_dashboard.py` and open `dashboard/covid_dashboard.html`.
""")

nb["cells"] = C
nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
out = Path(__file__).resolve().parents[1] / "notebooks" / "COVID19_Data_Analysis.ipynb"
nbf.write(nb, out)
print("written", out)
