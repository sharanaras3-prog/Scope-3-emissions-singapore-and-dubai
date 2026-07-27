"""
Synthetic data generator for the Marcura Scope 3 Carbon Intelligence Platform.
All data here is fictional and generated for demonstration purposes only.
Cached with st.cache_data so it's generated once per session and reused
across all pages/hubs.
"""

import random
import numpy as np
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta

SEED = 42

HUB_CONFIG = {
    "Global": {
        "ports": ["PSA Singapore", "Tuas Mega Port", "Jurong Port", "Jebel Ali",
                  "JAFZA", "Port Rashid", "Rotterdam", "Shanghai", "Los Angeles", "Hamburg"],
        "center": [15.0, 60.0],
        "zoom": 2,
    },
    "Singapore": {
        "ports": ["PSA Singapore", "Tuas Mega Port", "Jurong Port", "Jurong Island", "Changi Cargo Terminal"],
        "center": [1.29, 103.85],
        "zoom": 10,
    },
    "Dubai": {
        "ports": ["Jebel Ali", "JAFZA", "Dubai South", "Port Rashid", "Dubai Industrial City"],
        "center": [25.0, 55.1],
        "zoom": 10,
    },
}

VESSEL_TYPES = ["Container Ship", "LPG Tanker", "Bulk Carrier", "Crude Tanker", "RoRo", "General Cargo"]
TRANSPORT_MODES = ["Sea Freight", "Air Freight", "Road", "Rail", "Sea-Air"]
SUPPLIER_CATEGORIES = ["Electronics", "Chemicals", "Machinery", "Textiles", "Food & Beverage", "Metals", "Automotive"]
STATUSES = ["In Transit", "Delivered", "Delayed", "Customs Hold", "Loading"]


def _rng(seed_offset=0, hub="Global"):
    hub_offset = {"Global": 0, "Singapore": 1000, "Dubai": 2000}.get(hub, 0)
    return np.random.default_rng(SEED + seed_offset + hub_offset)


@st.cache_data(show_spinner=False)
def get_ports(hub: str):
    cfg = HUB_CONFIG[hub if hub in HUB_CONFIG else "Global"]
    rng = _rng(1, hub)
    rows = []
    lat0, lon0 = cfg["center"]
    for i, name in enumerate(cfg["ports"]):
        rows.append({
            "port_id": f"PRT-{i:03d}",
            "name": name,
            "lat": lat0 + rng.uniform(-4, 4),
            "lon": lon0 + rng.uniform(-4, 4),
            "throughput_teu": int(rng.uniform(500_000, 5_000_000)),
            "carbon_intensity": round(rng.uniform(8, 45), 1),
        })
    return pd.DataFrame(rows)


@st.cache_data(show_spinner=False)
def get_vessels(hub: str, n: int = 60):
    cfg = HUB_CONFIG[hub if hub in HUB_CONFIG else "Global"]
    rng = _rng(2, hub)
    lat0, lon0 = cfg["center"]
    spread = 25 if hub == "Global" else 6
    rows = []
    names = [
        "YUYO SPIRITS", "OCEAN HORIZON", "PACIFIC DAWN", "EMERALD TRADER",
        "NORTHERN STAR", "GULF VOYAGER", "SILVER WAVE", "ASIA PIONEER",
        "MARINA GLORY", "CRIMSON CARGO", "AZURE MERIDIAN", "GOLDEN LOTUS"
    ]
    for i in range(n):
        speed = round(rng.uniform(8, 22), 1)
        rows.append({
            "vessel_id": f"VSL-{hub[:2].upper()}-{i:04d}",
            "name": f"{names[rng.integers(0, len(names))]} {i}",
            "type": VESSEL_TYPES[rng.integers(0, len(VESSEL_TYPES))],
            "lat": lat0 + rng.uniform(-spread, spread),
            "lon": lon0 + rng.uniform(-spread, spread),
            "heading": int(rng.uniform(0, 360)),
            "speed_kn": speed,
            "draught_m": round(rng.uniform(6, 16), 1),
            "fuel_pct": int(rng.uniform(15, 100)),
            "status": ["Underway Using Engine", "At Anchor", "Moored", "Not Under Command"][rng.integers(0, 4)],
            "eta": (datetime(2026, 8, 1) + timedelta(days=int(rng.uniform(1, 20)))).strftime("%Y-%m-%d %H:%M"),
            "co2e_tonnes": round(rng.uniform(50, 900), 1),
            "carbon_intensity_gco2_tkm": round(rng.uniform(5, 25), 2),
            "origin": cfg["ports"][rng.integers(0, len(cfg["ports"]))],
            "destination": cfg["ports"][rng.integers(0, len(cfg["ports"]))],
        })
    return pd.DataFrame(rows)


@st.cache_data(show_spinner=False)
def get_suppliers(hub: str, n: int = 80):
    rng = _rng(3, hub)
    rows = []
    prefixes = ['Meridian', 'Alaris', 'Kestrel', 'NovaTech', 'Trident', 'Falcon', 'Orion', 'Vantage']
    suffixes = ['Industries', 'Group', 'Holdings', 'Trading', 'Logistics', 'Manufacturing']
    countries = ["Singapore", "UAE", "China", "India", "Vietnam", "Malaysia", "Germany", "USA"]
    risks = ["Low", "Medium", "High"]
    for i in range(n):
        rows.append({
            "supplier_id": f"SUP-{hub[:2].upper()}-{i:04d}",
            "name": f"{prefixes[rng.integers(0, len(prefixes))]} {suffixes[rng.integers(0, len(suffixes))]}",
            "category": SUPPLIER_CATEGORIES[rng.integers(0, len(SUPPLIER_CATEGORIES))],
            "esg_score": round(rng.uniform(35, 98), 1),
            "carbon_emissions_tco2e": round(rng.uniform(200, 15000), 0),
            "spend_usd": round(rng.uniform(50_000, 4_000_000), 0),
            "risk_level": risks[rng.integers(0, 3)],
            "country": countries[rng.integers(0, len(countries))],
        })
    return pd.DataFrame(rows)


@st.cache_data(show_spinner=False)
def get_shipments(hub: str, n: int = 400):
    cfg = HUB_CONFIG[hub if hub in HUB_CONFIG else "Global"]
    rng = _rng(4, hub)
    rows = []
    for i in range(n):
        emissions = round(rng.uniform(0.5, 120), 2)
        rows.append({
            "shipment_id": f"SHP-{hub[:2].upper()}-{100000+i}",
            "origin": cfg["ports"][rng.integers(0, len(cfg["ports"]))],
            "destination": cfg["ports"][rng.integers(0, len(cfg["ports"]))],
            "mode": TRANSPORT_MODES[rng.integers(0, len(TRANSPORT_MODES))],
            "status": STATUSES[rng.integers(0, len(STATUSES))],
            "weight_tonnes": round(rng.uniform(1, 500), 1),
            "distance_km": int(rng.uniform(200, 18000)),
            "co2e_tonnes": emissions,
            "cost_usd": round(rng.uniform(500, 80000), 0),
            "eta": (datetime(2026, 7, 27) + timedelta(days=int(rng.uniform(-5, 25)))).strftime("%Y-%m-%d"),
        })
    return pd.DataFrame(rows)


@st.cache_data(show_spinner=False)
def get_monthly_emissions(hub: str, months: int = 24):
    rng = _rng(5, hub)
    base = 8000 if hub == "Global" else 3000
    dates = pd.date_range(end=pd.Timestamp("2026-07-01"), periods=months, freq="MS")
    trend = np.linspace(1.15, 0.9, months)
    noise = rng.uniform(0.9, 1.1, months)
    values = base * trend * noise
    return pd.DataFrame({"month": dates, "scope3_tco2e": values.round(1)})


@st.cache_data(show_spinner=False)
def get_kpis(hub: str):
    vessels = get_vessels(hub, n=60 if hub != "Global" else 150)
    shipments = get_shipments(hub, n=400 if hub != "Global" else 1200)
    suppliers = get_suppliers(hub, n=80 if hub != "Global" else 200)
    monthly = get_monthly_emissions(hub)
    return {
        "total_scope3": round(monthly["scope3_tco2e"].sum(), 0),
        "monthly_emissions": round(monthly["scope3_tco2e"].iloc[-1], 0),
        "carbon_target": round(monthly["scope3_tco2e"].iloc[-1] * 0.85, 0),
        "procurement_spend": round(suppliers["spend_usd"].sum(), 0),
        "esg_score": round(suppliers["esg_score"].mean(), 1),
        "active_suppliers": len(suppliers),
        "shipments": len(shipments),
        "vessels": len(vessels),
        "avg_speed": round(vessels["speed_kn"].mean(), 1),
    }
