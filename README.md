# Marcura Scope 3 Carbon Intelligence Platform (Streamlit)

A demonstration Streamlit application for maritime logistics, procurement, and
Scope 3 carbon intelligence. All data is synthetic and generated at runtime —
no real company, vessel, or emissions data is used.

> Demonstration platform powered by synthetic data. Company names, transactions,
> emissions and operational events are fictional and are for demonstration
> purposes only.

## What's included

| Page | File | Description |
|---|---|---|
| Home | `app.py` | Landing page, hub selector (Global / Singapore / Dubai), top-line KPIs, port map preview |
| Executive Dashboard | `pages/1_📊_Executive_Dashboard.py` | KPI grid, emissions trend, transport-mode split, top suppliers by emissions, shipment status, shipment register |
| Live Vessel Map | `pages/2_🛰️_Live_Vessel_Map.py` | MarineTraffic-style dark map (pydeck), search/type/speed filters, floating vessel detail card, fleet table |
| Scope 3 Calculator | `pages/3_🧮_Scope3_Calculator.py` | Shipment-level emissions estimator: CO₂ / CH₄ / N₂O breakdown, GWP-weighted CO₂e, carbon cost, reduction suggestions |

Supporting modules:
- `data/synthetic.py` — cached, hub-seeded synthetic data generators (ports, vessels, suppliers, shipments, monthly emissions, KPIs)
- `utils/style.py` — dark glassmorphism theme, KPI card component, hub selector, footer disclaimer
- `.streamlit/config.toml` — dark theme config
- `requirements.txt` — pinned dependencies

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Then open the local URL Streamlit prints (usually `http://localhost:8501`).

## Deploy to Streamlit Community Cloud

1. Push this folder to a GitHub repository (keep the folder structure as-is).
2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in.
3. Click **New app**, select your repo/branch, and set the main file path to `app.py`.
4. Deploy. Streamlit Cloud will install from `requirements.txt` automatically.

No secrets, API keys, or external services are required — everything is generated in-memory.

## Known limitations / next steps

- **Scaled-down data volumes.** The original spec called for 5,000 shipments, 300 vessels, 800 trucks, etc. Numbers here are reduced (60–150 vessels, 400–1,200 shipments) so the free tier of Streamlit Cloud can render maps and tables smoothly. Bump the `n=` parameters in `data/synthetic.py` if you're on a paid tier or need bigger scale.
- **Pages not yet built:** Shipment Intelligence, Procurement Dashboard, Supplier Dashboard, GIS Dashboard (heatmaps/layers), Live Truck Dashboard, Digital Twin, AI Carbon Copilot, Predictive Analytics, Reports, Settings.
- **Map tiles:** `pydeck` uses Mapbox's dark style by default. If you hit a Mapbox token limit on Streamlit Cloud, switch `map_style` in `2_🛰️_Live_Vessel_Map.py` to `"road"` or a CARTO basemap URL, or set a `MAPBOX_API_KEY` in Streamlit secrets.
- **Data is re-seeded per hub** (Global / Singapore / Dubai) using fixed offsets, so numbers are stable across reruns but differ meaningfully between hubs.

## Folder structure

```
marcura/
├── app.py
├── requirements.txt
├── .streamlit/
│   └── config.toml
├── data/
│   └── synthetic.py
├── utils/
│   └── style.py
└── pages/
    ├── 1_📊_Executive_Dashboard.py
    ├── 2_🛰️_Live_Vessel_Map.py
    └── 3_🧮_Scope3_Calculator.py
```
