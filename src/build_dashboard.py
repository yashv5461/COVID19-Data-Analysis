"""
build_dashboard.py
------------------
Builds an interactive Plotly dashboard as a single HTML file:
    dashboard/covid_dashboard.html

Plotly.js is embedded, so the file opens in any web browser, even offline.
Run from the project root:
    python src/build_dashboard.py
"""

import json
from pathlib import Path

import pandas as pd
from plotly.offline import get_plotlyjs

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "dashboard" / "covid_dashboard.html"

CONTINENT_COLORS = {"Africa": "#2a78d6", "Asia": "#eb6834", "Europe": "#1baf7a",
                    "North America": "#eda100", "Oceania": "#e87ba4", "South America": "#008300"}


def build_data() -> dict:
    df = pd.read_csv(DATA / "dataset.csv", parse_dates=["date"]).sort_values(["country", "date"])
    codes = pd.read_csv(DATA / "country_codes.csv")
    g = df.groupby("country")
    df["new_cases"] = g["confirmed"].diff().clip(lower=0).fillna(0)
    df["new_deaths"] = g["deaths"].diff().clip(lower=0).fillna(0)

    # Weekly series per country
    wk = (df.set_index("date").groupby("country")[["new_cases", "new_deaths"]]
            .resample("W").sum().reset_index())
    weeks = sorted(wk["date"].dt.strftime("%Y-%m-%d").unique())
    series = {}
    for c, s in wk.groupby("country"):
        s = s.set_index(s["date"].dt.strftime("%Y-%m-%d")).reindex(weeks).fillna(0)
        series[c] = {"cases": s["new_cases"].astype(int).tolist(),
                     "deaths": s["new_deaths"].astype(int).tolist()}
    world = wk.groupby("date")[["new_cases", "new_deaths"]].sum()
    series["World"] = {"cases": world["new_cases"].astype(int).tolist(),
                       "deaths": world["new_deaths"].astype(int).tolist()}

    # Latest snapshot per country
    last = df[df["date"] == df["date"].max()].merge(codes, on="country", how="left")
    last["cases_pm"] = last["confirmed"] / last["population"] * 1e6
    last["deaths_pm"] = last["deaths"] / last["population"] * 1e6
    last["vax_pct"] = (last["vaccinated"] / last["population"] * 100).clip(upper=100)
    last["cfr"] = last["deaths"] / last["confirmed"].where(last["confirmed"] > 0) * 100
    snap = last[["country", "iso_code", "continent", "population", "confirmed", "deaths",
                 "vaccinated", "cases_pm", "deaths_pm", "vax_pct", "cfr"]].round(2)
    snap = snap.astype(object).where(snap.notna(), None)

    # Vaccination coverage by continent (weekly)
    v = df.dropna(subset=["vaccinated"])
    pop = v.drop_duplicates("country").groupby("continent")["population"].sum()
    vc = (v[v["date"].dt.dayofweek == 6].groupby(["date", "continent"])["vaccinated"].sum()
            .reset_index())
    vc = vc[vc["date"] >= "2020-12-01"]
    vc["pct"] = (vc["vaccinated"] / vc["continent"].map(pop) * 100).round(2)
    vax = {c: {"x": s["date"].dt.strftime("%Y-%m-%d").tolist(), "y": s["pct"].tolist()}
           for c, s in vc.groupby("continent")}

    # Monthly world case fatality rate
    m = df.set_index("date")[["new_cases", "new_deaths"]].resample("MS").sum()
    m = m[(m.index >= "2020-03-01") & (m.index < "2024-01-01")]
    cfr = {"x": m.index.strftime("%Y-%m-%d").tolist(),
           "y": (m["new_deaths"] / m["new_cases"] * 100).round(3).tolist()}

    kpi = {"cases": int(last["confirmed"].sum()), "deaths": int(last["deaths"].sum()),
           "vaccinated": int(last["vaccinated"].sum()), "population": int(last["population"].sum()),
           "countries": int(last["country"].nunique()), "asof": df["date"].max().strftime("%d %b %Y"),
           "rows": int(len(df))}
    # Country outlines (Natural Earth 1:110m via the world-atlas package), embedded so the map works offline
    geo = json.loads((ROOT / "dashboard" / "world_countries_110m.geojson").read_text())
    return {"geo": geo, "weeks": weeks, "series": series, "snapshot": snap.to_dict("records"),
            "vax": vax, "cfr": cfr, "kpi": kpi, "colors": CONTINENT_COLORS}


HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>COVID-19 Dashboard</title>
<script>
// Country shapes are embedded below (geojson), so Plotly's online base-map file is not needed.
// An empty base map is registered here so the dashboard works fully offline.
(function () {
  var empty = { type: "GeometryCollection", geometries: [] };
  var objs = {};
  ["land", "ocean", "lakes", "rivers", "coastlines", "countries", "subunits"].forEach(function (k) { objs[k] = empty; });
  window.PlotlyGeoAssets = { topojson: { "world_110m": { type: "Topology", arcs: [], objects: objs } } };
})();
</script>
<script>__PLOTLYJS__</script>
<style>
  :root { --bg:#f6f6f3; --card:#ffffff; --ink:#1b1b1a; --muted:#5f5e5a; --line:#e4e3de; --accent:#2a78d6; }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--ink);
         font-family: "Segoe UI", system-ui, -apple-system, Roboto, Arial, sans-serif; }
  header { padding:24px 32px 8px; }
  h1 { margin:0; font-size:24px; }
  .sub { color:var(--muted); font-size:13px; margin-top:4px; }
  .wrap { padding:8px 32px 32px; display:grid; gap:16px; grid-template-columns: repeat(12, 1fr); }
  .card { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:14px 16px; min-width:0; }
  .kpi { grid-column: span 2; }
  .kpi .label { color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.04em; }
  .kpi .value { font-size:24px; font-weight:650; margin-top:4px; font-variant-numeric: tabular-nums; }
  .w12 { grid-column: span 12; } .w7 { grid-column: span 7; } .w5 { grid-column: span 5; } .w6 { grid-column: span 6; }
  .card h2 { font-size:15px; margin:0 0 2px; }
  .card p.note { color:var(--muted); font-size:12px; margin:0 0 8px; }
  .controls { display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin-bottom:6px; font-size:13px; }
  select, button { font:inherit; font-size:13px; padding:5px 10px; border:1px solid var(--line); border-radius:6px; background:#fff; color:var(--ink); }
  button.on { background:var(--ink); color:#fff; border-color:var(--ink); }
  .chart { width:100%; height:360px; }
  footer { color:var(--muted); font-size:12px; padding:0 32px 28px; line-height:1.5; }
  @media (max-width: 1000px) { .kpi { grid-column: span 4; } .w7,.w5,.w6 { grid-column: span 12; } }
  @media (max-width: 600px) { header, .wrap, footer { padding-left:16px; padding-right:16px; } .kpi { grid-column: span 6; } }
</style>
</head>
<body>
<header>
  <h1>COVID-19 Data Analysis Dashboard</h1>
  <div class="sub">Yash Verma (2300320130290), ABES EC | HCLTech Career Shaper Project No. 48 | Data: Our World in Data / WHO, as of <span id="asof"></span></div>
</header>
<section class="wrap">
  <div class="card kpi"><div class="label">Reported cases</div><div class="value" id="k1"></div></div>
  <div class="card kpi"><div class="label">Reported deaths</div><div class="value" id="k2"></div></div>
  <div class="card kpi"><div class="label">Case fatality rate</div><div class="value" id="k3"></div></div>
  <div class="card kpi"><div class="label">Vaccinated (1+ dose)</div><div class="value" id="k4"></div></div>
  <div class="card kpi"><div class="label">Deaths per million</div><div class="value" id="k5"></div></div>
  <div class="card kpi"><div class="label">Countries / rows</div><div class="value" id="k6"></div></div>

  <div class="card w12">
    <h2>Weekly trend by country</h2>
    <p class="note">Weekly new cases or deaths. Pick a country or the world total.</p>
    <div class="controls">
      <label for="country">Country</label> <select id="country"></select>
      <button data-m="cases" class="on">Cases</button><button data-m="deaths">Deaths</button>
    </div>
    <div id="trend" class="chart"></div>
  </div>

  <div class="card w7">
    <h2>World map</h2>
    <p class="note">Latest cumulative values. Hover a country for details.</p>
    <div class="controls">
      <select id="mapMetric">
        <option value="deaths_pm">Deaths per million</option>
        <option value="cases_pm">Cases per million</option>
        <option value="vax_pct">Vaccinated, % of population (1+ dose)</option>
      </select>
    </div>
    <div id="map" class="chart"></div>
  </div>

  <div class="card w5">
    <h2>Top 15 countries</h2>
    <p class="note">Per-million rankings include countries with population of 1 million or more.</p>
    <div class="controls">
      <select id="topMetric">
        <option value="confirmed">Total cases</option>
        <option value="deaths">Total deaths</option>
        <option value="deaths_pm">Deaths per million</option>
        <option value="cases_pm">Cases per million</option>
      </select>
      <select id="topCont"><option value="">All continents</option></select>
    </div>
    <div id="top" class="chart"></div>
  </div>

  <div class="card w6">
    <h2>Vaccination coverage by continent</h2>
    <p class="note">Share of population with at least one dose.</p>
    <div id="vax" class="chart"></div>
  </div>

  <div class="card w6">
    <h2>Case fatality rate, world (monthly)</h2>
    <p class="note">Reported deaths divided by reported cases in each month, Mar 2020 to Dec 2023.</p>
    <div id="cfr" class="chart"></div>
  </div>
</section>
<footer>
  Source: Our World in Data COVID-19 dataset (CC BY 4.0), compiled from WHO and national reports - github.com/owid/covid-19-data.
  Figures are officially reported numbers; true infections and deaths were higher where testing was limited. Country totals are published weekly.
</footer>
<script>
const D = __DATA__;
const fmt = n => n >= 1e9 ? (n/1e9).toFixed(2)+"B" : n >= 1e6 ? (n/1e6).toFixed(1)+"M" : n >= 1e3 ? (n/1e3).toFixed(1)+"K" : String(Math.round(n));
const base = { margin:{l:56,r:16,t:8,b:40}, paper_bgcolor:"#fff", plot_bgcolor:"#fff",
  font:{family:'"Segoe UI", system-ui, Arial, sans-serif', size:12, color:"#1b1b1a"},
  xaxis:{gridcolor:"#eeede8", linecolor:"#c9c8c2"}, yaxis:{gridcolor:"#eeede8", linecolor:"#c9c8c2", rangemode:"tozero"},
  hoverlabel:{bgcolor:"#fff", bordercolor:"#c9c8c2", font:{color:"#1b1b1a"}} };
const cfg = { responsive:true, displaylogo:false, modeBarButtonsToRemove:["lasso2d","select2d"] };
const L = extra => Object.assign(JSON.parse(JSON.stringify(base)), extra || {});

// KPIs
const k = D.kpi;
document.getElementById("asof").textContent = k.asof;
document.getElementById("k1").textContent = fmt(k.cases);
document.getElementById("k2").textContent = fmt(k.deaths);
document.getElementById("k3").textContent = (k.deaths / k.cases * 100).toFixed(2) + "%";
document.getElementById("k4").textContent = (k.vaccinated / k.population * 100).toFixed(1) + "%";
document.getElementById("k5").textContent = Math.round(k.deaths / k.population * 1e6).toLocaleString();
document.getElementById("k6").textContent = k.countries + " / " + fmt(k.rows);

// Trend
const sel = document.getElementById("country");
["World", ...Object.keys(D.series).filter(c => c !== "World").sort()].forEach(c => sel.add(new Option(c, c)));
sel.value = "India";
let metric = "cases";
function drawTrend() {
  const c = sel.value, y = D.series[c][metric];
  Plotly.react("trend", [{ x: D.weeks, y, type:"scatter", mode:"lines", line:{color: metric==="cases" ? "#2a78d6" : "#eb6834", width:2},
    hovertemplate:"Week ending %{x|%d %b %Y}<br>" + (metric==="cases"?"New cases":"New deaths") + ": %{y:,}<extra>"+c+"</extra>" }],
    L({ hovermode:"x", yaxis:Object.assign({}, base.yaxis, {title:{text: metric==="cases"?"New cases per week":"Deaths per week"}}) }), cfg);
}
sel.onchange = drawTrend;
document.querySelectorAll("button[data-m]").forEach(b => b.onclick = () => {
  document.querySelectorAll("button[data-m]").forEach(x => x.classList.remove("on")); b.classList.add("on");
  metric = b.dataset.m; drawTrend(); });
drawTrend();

// Map
const mapLabels = { deaths_pm:"Deaths per million", cases_pm:"Cases per million", vax_pct:"Vaccinated %" };
function drawMap() {
  const m = document.getElementById("mapMetric").value;
  const rows = D.snapshot.filter(r => r.iso_code && r[m] !== null);
  Plotly.react("map", [{ type:"choropleth", geojson: D.geo, featureidkey:"properties.iso", locations: rows.map(r => r.iso_code), z: rows.map(r => r[m]),
    text: rows.map(r => r.country), colorscale:[[0,"#eef4fc"],[0.5,"#6aa6e8"],[1,"#0d3a78"]],
    marker:{line:{color:"#fff", width:0.4}}, colorbar:{thickness:10, len:0.8, title:{text:mapLabels[m], side:"right"}},
    hovertemplate:"<b>%{text}</b><br>" + mapLabels[m] + ": %{z:,.1f}<extra></extra>" }],
    L({ margin:{l:0,r:0,t:0,b:0}, geo:{visible:false, projection:{type:"natural earth"}, bgcolor:"#fff", lataxis:{range:[-58,85]}} }), cfg);
}
document.getElementById("mapMetric").onchange = drawMap; drawMap();

// Top 15
const tc = document.getElementById("topCont");
Object.keys(D.colors).forEach(c => tc.add(new Option(c, c)));
const topLabels = { confirmed:"Total cases", deaths:"Total deaths", deaths_pm:"Deaths per million", cases_pm:"Cases per million" };
function drawTop() {
  const m = document.getElementById("topMetric").value, cont = tc.value;
  let rows = D.snapshot.filter(r => (!cont || r.continent === cont) && r[m] !== null);
  if (m.endsWith("_pm")) rows = rows.filter(r => r.population >= 1e6);
  rows = rows.sort((a, b) => b[m] - a[m]).slice(0, 15).reverse();
  Plotly.react("top", [{ type:"bar", orientation:"h", y: rows.map(r => r.country), x: rows.map(r => r[m]),
    marker:{color: rows.map(r => D.colors[r.continent])}, customdata: rows.map(r => r.continent),
    hovertemplate:"<b>%{y}</b> (%{customdata})<br>" + topLabels[m] + ": %{x:,.0f}<extra></extra>" }],
    L({ margin:{l:130,r:16,t:8,b:36}, yaxis:{automargin:true}, xaxis:Object.assign({}, base.xaxis, {title:{text:topLabels[m]}}) }), cfg);
}
document.getElementById("topMetric").onchange = drawTop; tc.onchange = drawTop; drawTop();

// Vaccination
Plotly.newPlot("vax", Object.keys(D.colors).map(c => ({ x: D.vax[c].x, y: D.vax[c].y, name: c, type:"scatter", mode:"lines",
  line:{color: D.colors[c], width:2}, hovertemplate:"%{y:.1f}%<extra>"+c+"</extra>" })),
  L({ hovermode:"x unified", legend:{orientation:"h", y:1.12}, yaxis:Object.assign({}, base.yaxis, {range:[0,100], ticksuffix:"%"}) }), cfg);

// CFR
Plotly.newPlot("cfr", [{ x: D.cfr.x, y: D.cfr.y, type:"scatter", mode:"lines+markers", line:{color:"#2a78d6", width:2}, marker:{size:5},
  hovertemplate:"%{x|%b %Y}: %{y:.2f}%<extra></extra>" }],
  L({ hovermode:"x", yaxis:Object.assign({}, base.yaxis, {ticksuffix:"%", title:{text:"Case fatality rate"}}) }), cfg);
</script>
</body>
</html>
"""


def main() -> None:
    data = build_data()
    OUT.parent.mkdir(exist_ok=True)
    html = HTML.replace("__DATA__", json.dumps(data, separators=(",", ":")))
    OUT.write_text(html.replace("__PLOTLYJS__", get_plotlyjs()), encoding="utf-8")
    print(f"Saved {OUT} ({OUT.stat().st_size/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
