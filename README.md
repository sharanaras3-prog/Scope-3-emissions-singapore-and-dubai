# Marcura Scope 3 Carbon Intelligence Platform (Streamlit)

A single-file Streamlit dashboard (`app.py`) covering:
- Executive Dashboard (KPIs, monthly trends, Singapore vs Dubai comparison)
- Carbon & Emissions (CO2/CH4/N2O breakdown, anomalies, mode-based emissions)
- Shipment Intelligence (filterable shipment table, status breakdown)
- Supplier Intelligence (ESG ratings, carbon intensity, top spend suppliers)
- GIS / Network Map (ports, warehouses, suppliers on a world map)
- Reduction Opportunities (cost vs. carbon impact)
- AI Insights (expandable insight cards)

## Structure
```
your-repo/
├── app.py
├── requirements.txt
├── Dubai.xlsx        (one sheet per dataset: suppliers, shipments, emissions, ...)
└── Singapore.xlsx     (one sheet per dataset: suppliers, shipments, emissions, ...)
```
No `data/` subfolder needed — just upload `app.py`, `Dubai.xlsx`, and `Singapore.xlsx`
to the same repo root. All app logic lives in `app.py` — no other custom modules
are required.

## Run locally
```
pip install -r requirements.txt
streamlit run app.py
```

## Deploy
Push this folder to a GitHub repo, then deploy on
[Streamlit Community Cloud](https://streamlit.io/cloud) pointing at `app.py`.

*Demonstration platform powered by synthetic data. Company names, transactions,
emissions and operational events are fictional and for demonstration purposes only.*
