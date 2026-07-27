# 🧭 Marcura Scope 3 Intelligence — Demonstration Platform

> **Demonstration platform powered by synthetic data.** Company names, transactions,
> emissions and operational events are fictional and generated for demo purposes only.

A Streamlit app with two hubs — **Singapore** (maritime transshipment & operational
intelligence) and **Dubai** (maritime procurement & supplier intelligence) — sharing
one consistent interface, navigation, and visual identity.

## Features
- Global overview with combined KPIs
- Singapore Hub: Executive Overview, 3D vessel/route map, Shipment Intelligence,
  Supplier Network, Scope 3 Emissions, AI Insights
- Dubai Hub: Executive Overview, 3D vessel/route map, Procurement/Supplier ESG,
  Shipment Intelligence, Scope 3 Emissions, AI Procurement Assistant insights
- **3D vessel-movement map** (pydeck `ColumnLayer` + `PathLayer`) — column height =
  vessel speed, color = operational status, lines = trade routes
- Singapore vs Dubai comparison page
- Custom dark teal/amber theme (no default Streamlit blue)

## Project structure
```
marcura-scope3/
├── app.py                     # Main Streamlit app
├── requirements.txt
├── .streamlit/config.toml     # Custom color theme
├── scripts/generate_data.py   # Synthetic data generator
└── data/
    ├── global-summary.json
    ├── singapore/  (vessels, routes, suppliers, emissions, shipments, ai-insights, executive-summary)
    └── dubai/      (same structure)
```

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Regenerate synthetic data
```bash
cd scripts
python3 generate_data.py
```

## Deploy — GitHub + Streamlit Community Cloud
1. Create a new GitHub repo (e.g. `marcura-scope3-platform`) and push this folder:
   ```bash
   git init
   git add .
   git commit -m "Initial commit: Marcura Scope 3 Intelligence platform"
   git branch -M main
   git remote add origin https://github.com/<your-username>/marcura-scope3-platform.git
   git push -u origin main
   ```
2. Go to **https://share.streamlit.io** → **New app**.
3. Select your repo, branch `main`, and main file path `app.py`.
4. Deploy. Streamlit Cloud will install `requirements.txt` automatically and read
   `.streamlit/config.toml` for the color theme.

No API keys or secrets are required — all data is local, static JSON.
