"""
Marcura Scope 3 Carbon Intelligence Platform
=============================================
A single-file Streamlit dashboard for exploring synthetic Scope 3 carbon
emissions, procurement, shipment and supplier data across two operational
hubs: Singapore (Maritime Operations Hub) and Dubai (Procurement & Supplier
Intelligence Hub).

USAGE
-----
1. Keep this file (app.py) together with the `data/` folder in the same
   GitHub repo:

    your-repo/
    ├── app.py
    └── data/
        ├── dubai/*.csv
        └── singapore/*.csv

2. Run locally:      streamlit run app.py
3. Deploy on Streamlit Community Cloud by pointing it at this repo + app.py.

All logic (data loading, charts, maps, filters, pages) lives in this single
file on purpose, so nothing else needs to be imported or wired up.

Note: All company names, transactions, emissions and operational events are
synthetic and for demonstration purposes only.
"""

import os
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

try:
    import folium
    from streamlit_folium import st_folium
    FOLIUM_AVAILABLE = True
except ImportError:
    FOLIUM_AVAILABLE = False

try:
    import anthropic
    ANTHROPIC_SDK_AVAILABLE = True
except ImportError:
    ANTHROPIC_SDK_AVAILABLE = False

# ----------------------------------------------------------------------------
# PAGE CONFIG & GLOBAL STYLE
# ----------------------------------------------------------------------------
st.set_page_config(
    page_title="Marcura Scope 3 Carbon Intelligence Platform",
    page_icon="🚢",
    layout="wide",
    initial_sidebar_state="expanded",
)

CUSTOM_CSS = """
<style>
    .stApp { background-color: #ffffff; color: #0f172a; }
    #MainMenu, footer {visibility: hidden;}

    .kpi-card {
        background: linear-gradient(135deg, #f8fafc, #f1f5f9);
        border: 1px solid #dbeafe;
        border-radius: 14px;
        padding: 18px 20px;
        margin-bottom: 8px;
        box-shadow: 0 1px 3px rgba(15,23,42,0.06);
    }
    .kpi-label { font-size: 0.78rem; color: #475569; text-transform: uppercase; letter-spacing: 0.05em; }
    .kpi-value { font-size: 1.65rem; font-weight: 700; color: #0f172a; margin-top: 4px; }
    .kpi-sub { font-size: 0.78rem; color: #0369a1; margin-top: 2px; }

    .hub-banner {
        background: linear-gradient(90deg, #e0f2fe, #ffffff);
        border-left: 4px solid #0ea5e9;
        border-radius: 8px;
        padding: 10px 16px;
        margin-bottom: 18px;
        color: #1e293b;
        font-size: 0.92rem;
    }
    .footer-note {
        text-align: center;
        color: #64748b;
        font-size: 0.75rem;
        padding: 18px 0 6px 0;
        border-top: 1px solid #e2e8f0;
        margin-top: 32px;
    }
    section[data-testid="stSidebar"] { background-color: #f8fafc; border-right: 1px solid #e2e8f0; }
    h1, h2, h3, h4, p, span, label, div { color: #0f172a; }

    /* Vessel info popup card, MarineTraffic style */
    .vessel-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        box-shadow: 0 6px 20px rgba(15,23,42,0.12);
        padding: 18px 20px;
        margin-top: 10px;
    }
    .vessel-card-title { font-size: 1.15rem; font-weight: 700; color: #0f172a; }
    .vessel-card-sub { font-size: 0.85rem; color: #64748b; margin-bottom: 10px; }
    .vessel-route-row { display: flex; justify-content: space-between; font-weight: 700; font-size: 1.05rem; color: #0f172a; margin: 10px 0; }
    .vessel-stat-label { font-size: 0.75rem; color: #64748b; text-transform: uppercase; }
    .vessel-stat-value { font-size: 0.95rem; font-weight: 600; color: #0f172a; }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ----------------------------------------------------------------------------
# DATA LOADING
# ----------------------------------------------------------------------------
DATA_ROOT = os.path.dirname(os.path.abspath(__file__))

FILES = [
    "kpi_monthly", "executive_dashboard_kpis", "suppliers", "supplier_esg_scores",
    "ports", "vessels", "routes", "reduction_opportunities", "ai_insights",
    "shipments", "emissions", "emission_factors", "ais_records", "warehouses",
    "trucks", "hubs", "companies", "customers",
]

# Workbook file names, keyed by hub. Each workbook is expected to sit right
# next to this script (no data/ subfolder needed) with one sheet per dataset
# (sheet name == dataset name, e.g. "suppliers", "shipments", "emissions"...).
HUB_WORKBOOKS = {
    "dubai": "Dubai.xlsx",
    "singapore": "Singapore.xlsx",
}


# Approximate country centroids, used to correct supplier/customer coordinates
# that in the raw synthetic data are randomly generated and don't correspond to
# their listed country (which otherwise causes markers to land in the ocean).
COUNTRY_CENTROIDS = {
    "UAE": (24.0, 54.0), "United Arab Emirates": (24.0, 54.0),
    "Saudi Arabia": (24.5, 45.0), "Oman": (21.0, 57.0), "Qatar": (25.3, 51.2),
    "Kuwait": (29.3, 47.5), "Bahrain": (26.0, 50.5),
    "Egypt": (26.8, 30.8), "Turkey": (39.0, 35.0),
    "China": (35.0, 103.0), "India": (22.0, 79.0), "Japan": (36.2, 138.3),
    "South Korea": (36.5, 127.9), "Vietnam": (16.0, 106.0),
    "Singapore": (1.35, 103.82), "Indonesia": (-2.5, 118.0),
    "Malaysia": (4.2, 101.9), "Thailand": (15.0, 101.0), "Taiwan": (23.7, 121.0),
    "Philippines": (12.9, 121.8), "Netherlands": (52.1, 5.3),
    "Germany": (51.2, 10.4), "United States": (39.8, -98.6),
    "United Kingdom": (54.0, -2.0), "France": (46.6, 2.2),
}


def fix_country_coordinates(df, country_col="country", lat_col="latitude", lon_col="longitude", jitter_deg=1.2):
    """Replace lat/lon with a small deterministic jitter around the entity's actual
    country centroid, so map markers land on the right country instead of in the ocean."""
    if df.empty or country_col not in df.columns or lat_col not in df.columns:
        return df
    df = df.copy()
    for i, row in df.iterrows():
        country = row.get(country_col)
        centroid = COUNTRY_CENTROIDS.get(country)
        if centroid:
            # Deterministic jitter from a stable hash of the row index, so re-runs
            # place the same entity at the same point rather than jumping around.
            seed = abs(hash((country, i))) % 10_000
            rng = np.random.default_rng(seed)
            dlat, dlon = (rng.random(2) - 0.5) * 2 * jitter_deg
            df.at[i, lat_col] = centroid[0] + dlat
            df.at[i, lon_col] = centroid[1] + dlon
    return df


@st.cache_data(show_spinner="Loading synthetic Scope 3 datasets...")
def load_hub_data(hub_folder: str) -> dict:
    """Load every sheet of a hub's Excel workbook ('dubai' or 'singapore') into a dict of DataFrames."""
    data = {}
    workbook_path = os.path.join(DATA_ROOT, HUB_WORKBOOKS[hub_folder])

    sheets = {}
    if os.path.exists(workbook_path):
        try:
            sheets = pd.read_excel(workbook_path, sheet_name=None, engine="openpyxl")
        except Exception:
            sheets = {}

    # Sheet names may be truncated to Excel's 31-character limit, so match
    # loosely (case-insensitive prefix match) rather than requiring exact names.
    lower_sheets = {name.lower(): df for name, df in sheets.items()}
    for name in FILES:
        match = None
        if name.lower() in lower_sheets:
            match = lower_sheets[name.lower()]
        else:
            for sheet_name, df in lower_sheets.items():
                if sheet_name.startswith(name.lower()[:31]) or name.lower().startswith(sheet_name):
                    match = df
                    break
        data[name] = match if match is not None else pd.DataFrame()

    # Fallback: some hub workbooks ship an "emissions_ledger" sheet instead of
    # "emissions", with a slightly different schema. Normalize so the rest of
    # the app can rely on a consistent set of columns either way.
    if data.get("emissions", pd.DataFrame()).empty:
        ledger = lower_sheets.get("emissions_ledger")
        if ledger is not None and not ledger.empty:
            normalized = pd.DataFrame()
            normalized["emission_id"] = ledger.get("ledger_id")
            normalized["shipment_id"] = ledger.get("shipment_id")
            normalized["total_co2e_kg"] = ledger.get("co2e_kg")
            normalized["methodology"] = ledger.get("assurance_status")
            normalized["confidence_score"] = ledger.get("data_quality_score")
            normalized["calculation_date"] = ledger.get("period")
            data["emissions"] = normalized

    # Correct supplier/customer coordinates so they land within their listed
    # country rather than at random (sometimes oceanic) points.
    if not data.get("suppliers", pd.DataFrame()).empty:
        data["suppliers"] = fix_country_coordinates(data["suppliers"])
    if not data.get("customers", pd.DataFrame()).empty:
        data["customers"] = fix_country_coordinates(data["customers"])

    return data


def combine(dubai_df: pd.DataFrame, sgp_df: pd.DataFrame) -> pd.DataFrame:
    """Concatenate two hub dataframes and tag origin hub, for the Global view."""
    frames = []
    if not dubai_df.empty:
        d = dubai_df.copy()
        d["_hub"] = "Dubai"
        frames.append(d)
    if not sgp_df.empty:
        s = sgp_df.copy()
        s["_hub"] = "Singapore"
        frames.append(s)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True, sort=False)


dubai_data = load_hub_data("dubai")
sgp_data = load_hub_data("singapore")

DATA_AVAILABLE = any(not df.empty for df in dubai_data.values()) or any(
    not df.empty for df in sgp_data.values()
)

# ----------------------------------------------------------------------------
# SIDEBAR — NAVIGATION & HUB SELECTOR
# ----------------------------------------------------------------------------
st.sidebar.markdown("### 🚢 Marcura Scope 3 Intelligence")

hub = st.sidebar.selectbox("Operational Hub", ["Global", "Singapore", "Dubai"], index=0)

page = st.sidebar.radio(
    "Navigate",
    [
        "🧮 Scope 3 Calculator",
        "📊 Executive Dashboard",
        "🔬 AI Copilot",
        "🚢 Live Vessel Map",
        "🚚 Live Truck Map",
        "🌍 Carbon & Emissions",
        "📦 Shipment Intelligence",
        "🏭 Supplier Intelligence",
        "🗺️ GIS / Network Map",
        "🎯 Reduction Opportunities",
        "🤖 AI Insights",
    ],
)
page = page.split(" ", 1)[1]  # strip the leading icon for internal routing

st.sidebar.markdown("---")
st.sidebar.caption(
    "Singapore = Maritime Operations Hub\n\nDubai = Procurement & Supplier Intelligence Hub"
)

with st.sidebar.expander("🔑 AI Copilot settings (optional)"):
    st.caption(
        "Add an Anthropic API key to enable AI-generated narrative summaries "
        "in the AI Copilot page. Without a key, a rule-based summary is used instead."
    )
    key_input = st.text_input("Anthropic API key", type="password", key="anthropic_api_key_input")
    model_input = st.text_input("Model", value="claude-sonnet-5", key="anthropic_model_input")
    if key_input:
        st.session_state["anthropic_api_key"] = key_input
    st.session_state["anthropic_model"] = model_input or "claude-sonnet-5"

if not DATA_AVAILABLE:
    st.sidebar.error("No data found. Make sure Dubai.xlsx and Singapore.xlsx "
                     "are placed in the same folder as app.py.")

# Resolve active dataset(s) based on hub selection
if hub == "Dubai":
    active = dubai_data
elif hub == "Singapore":
    active = sgp_data
else:
    active = {name: combine(dubai_data.get(name, pd.DataFrame()), sgp_data.get(name, pd.DataFrame()))
              for name in FILES}

st.markdown(
    f'<div class="hub-banner">Currently viewing: <b>{hub}</b> hub — '
    f'{"Consolidated Global view across Singapore and Dubai" if hub == "Global" else ("Maritime Operations Hub" if hub == "Singapore" else "Procurement & Supplier Intelligence Hub")}'
    f'</div>',
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------------
# HELPERS
# ----------------------------------------------------------------------------
def value_counts_df(series, label):
    """Return a 2-column DataFrame [label, 'count'] from a Series, robust across pandas versions
    (avoids relying on the exact column names produced by value_counts().reset_index())."""
    vc = series.value_counts(dropna=True)
    return pd.DataFrame({label: vc.index.tolist(), "count": vc.values})


def kpi_card(label, value, sub=""):
    st.markdown(
        f"""<div class="kpi-card">
                <div class="kpi-label">{label}</div>
                <div class="kpi-value">{value}</div>
                <div class="kpi-sub">{sub}</div>
            </div>""",
        unsafe_allow_html=True,
    )


def fmt_num(x, suffix=""):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return "—"
    if abs(x) >= 1_000_000:
        return f"{x/1_000_000:,.2f}M{suffix}"
    if abs(x) >= 1_000:
        return f"{x/1_000:,.1f}K{suffix}"
    return f"{x:,.1f}{suffix}"


PLOTLY_TEMPLATE = "plotly_white"


def style_fig(fig):
    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#0f172a"),
        margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
    )
    return fig


HUB_CENTERS = {
    "Dubai": {"center": [25.05, 55.15], "zoom": 9},
    "Singapore": {"center": [1.30, 103.80], "zoom": 10},
    "Global": {"center": [20.0, 60.0], "zoom": 3},
}

TYPE_COLORS = [
    "#0ea5e9", "#f97316", "#22c55e", "#a855f7", "#ef4444",
    "#0891b2", "#eab308", "#ec4899", "#14b8a6", "#6366f1",
]


def build_marinetraffic_map(df, lat_col, lon_col, popup_fields, name_col, color_col=None, key_col=None):
    """Build a real zoomable/pannable Folium map (like MarineTraffic) with clickable markers."""
    view = HUB_CENTERS.get(hub, HUB_CENTERS["Global"])
    m = folium.Map(location=view["center"], zoom_start=view["zoom"], tiles="CartoDB positron",
                    control_scale=True)

    color_map = {}
    if color_col and color_col in df.columns:
        cats = df[color_col].dropna().unique().tolist()
        color_map = {c: TYPE_COLORS[i % len(TYPE_COLORS)] for i, c in enumerate(cats)}

    for _, r in df.iterrows():
        if pd.isna(r.get(lat_col)) or pd.isna(r.get(lon_col)):
            continue
        color = color_map.get(r.get(color_col), "#0ea5e9") if color_map else "#0ea5e9"
        popup_lines = [f"<b>{r.get(name_col, '—')}</b>"]
        for field, label in popup_fields:
            if field in r:
                popup_lines.append(f"{label}: {r.get(field, '—')}")
        popup_html = "<br>".join(popup_lines)
        folium.CircleMarker(
            location=[r[lat_col], r[lon_col]],
            radius=6,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.85,
            weight=1,
            popup=folium.Popup(popup_html, max_width=250),
            tooltip=str(r.get(name_col, "")),
        ).add_to(m)

    return m


def get_ai_client():
    """Return an Anthropic client if an API key is available (via secrets or session), else None."""
    if not ANTHROPIC_SDK_AVAILABLE:
        return None
    api_key = st.session_state.get("anthropic_api_key")
    if not api_key:
        try:
            api_key = st.secrets.get("ANTHROPIC_API_KEY", None)
        except Exception:
            api_key = None
    if not api_key:
        return None
    try:
        return anthropic.Anthropic(api_key=api_key)
    except Exception:
        return None


def generate_ai_narrative(entity_label, context_text):
    """Try a real Claude-generated narrative; fall back to a rule-based summary if no API key."""
    client = get_ai_client()
    if client is not None:
        try:
            resp = client.messages.create(
                model=st.session_state.get("anthropic_model", "claude-sonnet-5"),
                max_tokens=600,
                messages=[{
                    "role": "user",
                    "content": (
                        f"You are a Scope 3 carbon intelligence copilot for a maritime logistics platform. "
                        f"Based on the following data about {entity_label}, write a concise (150-220 word) "
                        f"executive summary covering: overall carbon/ESG risk profile, notable emissions or "
                        f"cost patterns, and 2-3 concrete recommended actions. Be specific and use the numbers "
                        f"given. Do not invent data not present below.\n\n{context_text}"
                    ),
                }],
            )
            return "".join(b.text for b in resp.content if hasattr(b, "text")), True
        except Exception as e:
            return f"(AI generation failed: {e}. Showing rule-based summary instead.)\n\n" + rule_based_narrative(entity_label, context_text), False
    return rule_based_narrative(entity_label, context_text), False


def rule_based_narrative(entity_label, context_text):
    """A deterministic, no-API-key-needed fallback summary generator."""
    lines = [f"**Summary for {entity_label}** (rule-based — add an Anthropic API key for a richer AI narrative):"]
    for row in context_text.split("\n"):
        if row.strip():
            lines.append(f"- {row.strip()}")
    lines.append(
        "Review the figures above for concentration risk (a small number of high-emission relationships "
        "driving most of the footprint) and prioritize the reduction opportunities and AI insights flagged below."
    )
    return "\n".join(lines)


# ----------------------------------------------------------------------------
# PAGE: SCOPE 3 CALCULATOR
# ----------------------------------------------------------------------------
if page == "Scope 3 Calculator":
    st.title("Scope 3 Emissions Calculator")
    st.caption(
        "Estimate the CO2e footprint of a shipment leg using activity-based "
        "emission factors (kg CO2e per tonne-km), aligned with a GLEC "
        "Framework / ISO 14083-style methodology."
    )

    factors = active.get("emission_factors", pd.DataFrame())
    ports = active.get("ports", pd.DataFrame())
    suppliers = active.get("suppliers", pd.DataFrame())
    companies = active.get("companies", pd.DataFrame())

    if factors.empty:
        st.warning(
            "No emission factor table found for this hub (expected a sheet "
            "named `emission_factors`). You can still estimate emissions "
            "below using a manual factor."
        )

    st.markdown("#### 1. Shipment Details")
    c1, c2, c3 = st.columns(3)
    with c1:
        buyer = st.selectbox(
            "Buyer (optional)",
            ["None"] + (sorted(companies["company_name"].dropna().unique().tolist()) if "company_name" in companies else []),
        )
        origin = st.selectbox(
            "Origin",
            sorted(ports["port_name"].dropna().unique().tolist()) if "port_name" in ports else ["Origin A"],
        )
    with c2:
        seller = st.selectbox(
            "Seller (optional)",
            ["None"] + (sorted(companies["company_name"].dropna().unique().tolist()) if "company_name" in companies else []),
        )
        destination = st.selectbox(
            "Destination",
            sorted(ports["port_name"].dropna().unique().tolist()) if "port_name" in ports else ["Destination A"],
        )
    with c3:
        supplier_pick = st.selectbox(
            "Supplier (optional)",
            ["None"] + (sorted(suppliers["supplier_name"].dropna().unique().tolist()) if "supplier_name" in suppliers else []),
        )

    st.markdown("#### 2. Transport & Load")
    c4, c5, c6 = st.columns(3)
    with c4:
        weight_tonnes = st.number_input("Weight (tonnes)", min_value=0.0, value=20.0, step=1.0)
    with c5:
        distance_km = st.number_input("Distance (km)", min_value=0.0, value=500.0, step=10.0)
    with c6:
        container_type = st.selectbox(
            "Container / Load Type",
            ["Standard Container", "Bulk Parcel", "Air Pallet", "Refrigerated Container", "Tanker Parcel", "Other"],
        )

    if not factors.empty and "factor_name" in factors:
        factor_names = factors["factor_name"].dropna().unique().tolist()
        chosen_factor_name = st.selectbox("Emission Factor (mode & fuel)", factor_names)
        factor_row = factors[factors["factor_name"] == chosen_factor_name].iloc[0]
        factor_value = float(factor_row["factor_value"])
        factor_unit = factor_row.get("factor_unit", "kg CO2e/tonne-km")
        factor_source = factor_row.get("factor_source", "—")
        st.caption(f"Selected factor: **{factor_value} {factor_unit}** — Source: {factor_source}")
    else:
        chosen_factor_name = "Manual Entry"
        factor_value = st.number_input("Manual emission factor (kg CO2e per tonne-km)", min_value=0.0, value=0.05, step=0.001, format="%.4f")
        factor_unit = "kg CO2e/tonne-km"
        factor_source = "Manual entry"

    st.markdown("#### 3. Results")
    tonne_km = weight_tonnes * distance_km
    total_co2e_kg = tonne_km * factor_value
    total_co2e_tonnes = total_co2e_kg / 1000

    # Rough gas-level split assumption for illustrative purposes (CO2-dominant,
    # small CH4/N2O share), consistent with typical freight combustion profiles.
    co2_kg = total_co2e_kg * 0.98
    ch4_kg = total_co2e_kg * 0.015
    n2o_kg = total_co2e_kg * 0.005

    # Illustrative carbon cost using a representative shadow carbon price (USD/tCO2e).
    carbon_price_usd_per_tonne = 85.0
    carbon_cost_usd = total_co2e_tonnes * carbon_price_usd_per_tonne

    gcol1, gcol2 = st.columns([1, 1.4])
    with gcol1:
        gauge_max = max(total_co2e_tonnes * 1.6, 1.0)
        gauge = go.Figure(go.Indicator(
            mode="gauge+number",
            value=total_co2e_tonnes,
            number={"suffix": " t CO2e", "font": {"size": 34, "color": "#0f172a"}},
            gauge={
                "axis": {"range": [0, gauge_max], "tickcolor": "#94a3b8"},
                "bar": {"color": "#0ea5e9"},
                "bgcolor": "#f8fafc",
                "borderwidth": 1,
                "bordercolor": "#e2e8f0",
                "steps": [
                    {"range": [0, gauge_max * 0.4], "color": "#dcfce7"},
                    {"range": [gauge_max * 0.4, gauge_max * 0.75], "color": "#fef9c3"},
                    {"range": [gauge_max * 0.75, gauge_max], "color": "#fee2e2"},
                ],
            },
            title={"text": "Estimated Shipment CO2e", "font": {"size": 15, "color": "#475569"}},
        ))
        gauge.update_layout(height=280, margin=dict(l=20, r=20, t=50, b=10),
                             paper_bgcolor="rgba(0,0,0,0)", font=dict(color="#0f172a"))
        st.plotly_chart(gauge, use_container_width=True)
    with gcol2:
        r1, r2 = st.columns(2)
        with r1:
            kpi_card("Total CO2e", f"{total_co2e_tonnes:,.3f} t", f"{total_co2e_kg:,.1f} kg")
            kpi_card("CH4", f"{ch4_kg:,.2f} kg")
            kpi_card("Activity", f"{tonne_km:,.0f} tonne-km")
        with r2:
            kpi_card("CO2", f"{co2_kg:,.1f} kg")
            kpi_card("N2O", f"{n2o_kg:,.2f} kg")
            kpi_card("Estimated Carbon Cost", f"${carbon_cost_usd:,.2f}", f"@ ${carbon_price_usd_per_tonne}/tCO2e")
        kpi_card("Emission Factor Used", f"{factor_value} {factor_unit}", chosen_factor_name)

    st.markdown("#### 4. Emissions Breakdown")
    col1, col2 = st.columns(2)
    with col1:
        gases = pd.DataFrame({"Gas": ["CO2", "CH4", "N2O"], "kg CO2e-equivalent": [co2_kg, ch4_kg, n2o_kg]})
        fig = px.pie(gases, names="Gas", values="kg CO2e-equivalent", hole=0.5, title="Estimated Gas Breakdown")
        st.plotly_chart(style_fig(fig), use_container_width=True)
    with col2:
        if not factors.empty and "factor_name" in factors and "factor_value" in factors:
            comp = factors[["factor_name", "factor_value"]].copy()
            comp["is_selected"] = comp["factor_name"] == chosen_factor_name
            fig2 = px.bar(
                comp.sort_values("factor_value"), x="factor_value", y="factor_name", orientation="h",
                color="is_selected", color_discrete_map={True: "#0284c7", False: "#cbd5e1"},
                title="Selected Factor vs. Other Available Modes",
            )
            fig2.update_layout(showlegend=False)
            st.plotly_chart(style_fig(fig2), use_container_width=True)

    st.markdown("#### 5. Reduction Suggestions")
    suggestions = []
    if not factors.empty and "factor_value" in factors and "factor_name" in factors:
        lower_factors = factors[factors["factor_value"] < factor_value].sort_values("factor_value")
        if not lower_factors.empty:
            best = lower_factors.iloc[0]
            saving_pct = (1 - best["factor_value"] / factor_value) * 100
            suggestions.append(
                f"Switching from **{chosen_factor_name}** to **{best['factor_name']}** could cut this "
                f"leg's emissions by roughly **{saving_pct:.0f}%** (factor {best['factor_value']} vs. {factor_value} {factor_unit})."
            )
    if weight_tonnes > 0 and distance_km > 200:
        suggestions.append("For long-haul legs over 200km, consolidating shipments to improve load factor typically reduces emissions per tonne-km.")
    if not suggestions:
        suggestions.append("This is already a relatively low-carbon option for the selected route and load.")
    for s in suggestions:
        st.info(s)

    st.caption(
        "This calculator provides an activity-based estimate for demonstration purposes "
        "using synthetic emission factors. It is not a substitute for a certified Scope 3 "
        "accounting methodology."
    )

    if buyer != "None" or seller != "None" or supplier_pick != "None":
        st.markdown("#### 6. Look up in AI Copilot")
        jc1, jc2, jc3 = st.columns(3)
        with jc1:
            if buyer != "None" and st.button(f"🔬 Analyze buyer: {buyer}"):
                st.session_state["copilot_entity_type"] = "Buyer / Company"
                st.session_state["copilot_entity_pick"] = buyer
                st.info("Open **AI Copilot** from the sidebar to see the full dossier.")
        with jc2:
            if seller != "None" and st.button(f"🔬 Analyze seller: {seller}"):
                st.session_state["copilot_entity_type"] = "Buyer / Company"
                st.session_state["copilot_entity_pick"] = seller
                st.info("Open **AI Copilot** from the sidebar to see the full dossier.")
        with jc3:
            if supplier_pick != "None" and st.button(f"🔬 Analyze supplier: {supplier_pick}"):
                st.session_state["copilot_entity_type"] = "Supplier"
                st.session_state["copilot_entity_pick"] = supplier_pick
                st.info("Open **AI Copilot** from the sidebar to see the full dossier.")

# ----------------------------------------------------------------------------
# PAGE: EXECUTIVE DASHBOARD
# ----------------------------------------------------------------------------
elif page == "Executive Dashboard":
    st.title("Executive Dashboard")

    kpi_df = active.get("executive_dashboard_kpis", pd.DataFrame())
    monthly = active.get("kpi_monthly", pd.DataFrame())
    shipments = active.get("shipments", pd.DataFrame())
    suppliers = active.get("suppliers", pd.DataFrame())

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        val = monthly["total_co2e_tonnes"].sum() if "total_co2e_tonnes" in monthly else np.nan
        kpi_card("Total Scope 3 Emissions", fmt_num(val, " t"), "24-month reconciled")
    with c2:
        val = monthly["procurement_spend_musd"].sum() if "procurement_spend_musd" in monthly else np.nan
        kpi_card("Procurement Spend", f"${fmt_num(val)}", "USD millions, cumulative")
    with c3:
        kpi_card("Active Suppliers", f"{len(suppliers):,}" if not suppliers.empty else "—", "in network")
    with c4:
        kpi_card("Total Shipments", f"{len(shipments):,}" if not shipments.empty else "—", "recorded")

    st.markdown("#### Key Performance Indicators")
    if not kpi_df.empty:
        st.dataframe(kpi_df, use_container_width=True, hide_index=True)
    else:
        st.info("No executive KPI data available for this hub.")

    st.markdown("#### Monthly Emissions & Procurement Spend")
    if not monthly.empty and "period" in monthly:
        m = monthly.sort_values("period")
        col1, col2 = st.columns(2)
        with col1:
            fig = px.bar(m, x="period", y="total_co2e_tonnes", color="_hub" if "_hub" in m else None,
                         title="Total CO2e (tonnes) by Month")
            st.plotly_chart(style_fig(fig), use_container_width=True)
        with col2:
            fig = px.line(m, x="period", y="procurement_spend_musd", color="_hub" if "_hub" in m else None,
                          markers=True, title="Procurement Spend (USD M) by Month")
            st.plotly_chart(style_fig(fig), use_container_width=True)

        col3, col4 = st.columns(2)
        with col3:
            fig = px.line(m, x="period", y="shipment_count", color="_hub" if "_hub" in m else None,
                          markers=True, title="Shipment Count by Month")
            st.plotly_chart(style_fig(fig), use_container_width=True)
        with col4:
            if "delayed_shipment_count" in m:
                fig = px.bar(m, x="period", y="delayed_shipment_count", color="_hub" if "_hub" in m else None,
                             title="Delayed Shipments by Month")
                st.plotly_chart(style_fig(fig), use_container_width=True)
    else:
        st.info("No monthly KPI trend data available for this hub.")

    if hub == "Global" and "_hub" in monthly:
        st.markdown("#### Singapore vs Dubai — Regional Comparison")
        comp = monthly.groupby("_hub")[["total_co2e_tonnes", "procurement_spend_musd", "shipment_count"]].sum().reset_index()
        fig = px.bar(comp.melt(id_vars="_hub"), x="_hub", y="value", color="variable", barmode="group",
                     title="Regional Comparison: Emissions, Spend, Shipments")
        st.plotly_chart(style_fig(fig), use_container_width=True)

# ----------------------------------------------------------------------------
# PAGE: AI COPILOT — ENTITY DOSSIER
# ----------------------------------------------------------------------------
elif page == "AI Copilot":
    st.title("AI Carbon Copilot")
    st.caption(
        "Select a supplier, buyer/company, or vessel to get a complete Scope 3 "
        "dossier — profile, emissions history, ESG standing, related shipments, "
        "AI insights, and reduction opportunities — plus an AI-generated summary."
    )

    has_key = bool(st.session_state.get("anthropic_api_key"))
    if not has_key:
        try:
            has_key = bool(st.secrets.get("ANTHROPIC_API_KEY", None))
        except Exception:
            has_key = False

    if not ANTHROPIC_SDK_AVAILABLE:
        st.warning("The `anthropic` package isn't installed, so only the rule-based summary is available. "
                   "Add `anthropic` to requirements.txt to enable real AI-generated narratives.")
    elif not has_key:
        st.info("No Anthropic API key set — showing a rule-based summary. Add a key in the "
                "sidebar under **AI Copilot settings** for a richer AI-generated narrative.")

    suppliers = active.get("suppliers", pd.DataFrame())
    esg = active.get("supplier_esg_scores", pd.DataFrame())
    companies = active.get("companies", pd.DataFrame())
    vessels = active.get("vessels", pd.DataFrame())
    shipments = active.get("shipments", pd.DataFrame())
    ai_insights = active.get("ai_insights", pd.DataFrame())
    reduction = active.get("reduction_opportunities", pd.DataFrame())

    entity_types = []
    if not suppliers.empty:
        entity_types.append("Supplier")
    if not companies.empty:
        entity_types.append("Buyer / Company")
    if not vessels.empty:
        entity_types.append("Vessel")

    if not entity_types:
        st.info("No supplier, company, or vessel data available for this hub.")
    else:
        default_type = st.session_state.get("copilot_entity_type", entity_types[0])
        entity_type = st.selectbox("Entity Type", entity_types,
                                    index=entity_types.index(default_type) if default_type in entity_types else 0)

        # ---- Build entity-specific lookup ----
        if entity_type == "Supplier":
            names = sorted(suppliers["supplier_name"].dropna().unique().tolist())
        elif entity_type == "Buyer / Company":
            names = sorted(companies["company_name"].dropna().unique().tolist())
        else:
            names = sorted(vessels["vessel_name"].dropna().unique().tolist())

        default_pick = st.session_state.get("copilot_entity_pick")
        default_idx = names.index(default_pick) if default_pick in names else 0
        picked = st.selectbox("Select entity", names, index=default_idx if names else 0)

        st.markdown("---")
        context_lines = []

        if entity_type == "Supplier":
            srow = suppliers[suppliers["supplier_name"] == picked].iloc[0]
            supplier_id = srow.get("supplier_id")
            erow = esg[esg["supplier_id"] == supplier_id].iloc[0] if not esg.empty and (esg["supplier_id"] == supplier_id).any() else None

            st.markdown(
                f"""<div class="vessel-card">
                        <div class="vessel-card-title">🏭 {srow.get('supplier_name', '—')}</div>
                        <div class="vessel-card-sub">{srow.get('industry', '—')} · {srow.get('country', '—')} · Tier: {srow.get('supplier_tier', '—')}</div>
                    </div>""",
                unsafe_allow_html=True,
            )
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                kpi_card("Annual Spend", f"${fmt_num(srow.get('annual_spend_usd'))}")
            with c2:
                kpi_card("Carbon Intensity Score", f"{srow.get('carbon_intensity_score', '—')}")
            with c3:
                kpi_card("Supplier Risk", str(srow.get("supplier_risk", "—")))
            with c4:
                kpi_card("ESG Rating", str(erow.get("esg_rating", "—")) if erow is not None else "—")

            context_lines += [
                f"Supplier: {srow.get('supplier_name')} ({srow.get('industry')}, {srow.get('country')})",
                f"Annual spend: ${srow.get('annual_spend_usd'):,.0f}" if pd.notna(srow.get("annual_spend_usd")) else "",
                f"Carbon intensity score: {srow.get('carbon_intensity_score')}",
                f"Supplier risk: {srow.get('supplier_risk')}",
            ]
            if erow is not None:
                context_lines += [
                    f"ESG rating: {erow.get('esg_rating')}, sustainability score: {erow.get('sustainability_score')}",
                    f"Decarbonization commitment: {erow.get('decarbonization_commitment')}, reduction target: {erow.get('reduction_target_pct')}%",
                ]

            linked_ship = shipments[shipments["supplier_id"] == supplier_id] if not shipments.empty and "supplier_id" in shipments else pd.DataFrame()
            linked_insights = ai_insights[ai_insights["affected_entity_id"] == supplier_id] if not ai_insights.empty and "affected_entity_id" in ai_insights else pd.DataFrame()
            linked_reduction = reduction[reduction["target_entity_id"] == supplier_id] if not reduction.empty and "target_entity_id" in reduction else pd.DataFrame()

        elif entity_type == "Buyer / Company":
            crow = companies[companies["company_name"] == picked].iloc[0]
            company_id = crow.get("company_id")

            st.markdown(
                f"""<div class="vessel-card">
                        <div class="vessel-card-title">🏢 {crow.get('company_name', '—')}</div>
                        <div class="vessel-card-sub">{crow.get('type', '—')} · {crow.get('industry', '—')} · {crow.get('country', '—')}</div>
                    </div>""",
                unsafe_allow_html=True,
            )
            c1, c2, c3 = st.columns(3)
            with c1:
                kpi_card("Carbon Target", str(crow.get("carbon_target", "—")))
            with c2:
                kpi_card("Annual Shipments", f"{crow.get('annual_shipments', '—'):,}" if pd.notna(crow.get("annual_shipments")) else "—")
            with c3:
                kpi_card("Type", str(crow.get("type", "—")))

            context_lines += [
                f"Company: {crow.get('company_name')} ({crow.get('type')}, {crow.get('industry')}, {crow.get('country')})",
                f"Carbon target: {crow.get('carbon_target')}",
                f"Annual shipments: {crow.get('annual_shipments')}",
            ]

            linked_ship = shipments[(shipments.get("buyer_company_id") == company_id) | (shipments.get("seller_company_id") == company_id)] if not shipments.empty else pd.DataFrame()
            linked_insights = pd.DataFrame()
            linked_reduction = pd.DataFrame()

        else:  # Vessel
            vrow = vessels[vessels["vessel_name"] == picked].iloc[0]
            vessel_id = vrow.get("vessel_id")

            st.markdown(
                f"""<div class="vessel-card">
                        <div class="vessel-card-title">🚢 {vrow.get('vessel_name', '—')}</div>
                        <div class="vessel-card-sub">{vrow.get('vessel_type', '—')} · IMO {vrow.get('imo_number', '—')} · Fuel: {vrow.get('fuel_type', '—')}</div>
                    </div>""",
                unsafe_allow_html=True,
            )
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                kpi_card("CII Rating", str(vrow.get("cii_rating", "—")))
            with c2:
                kpi_card("Carbon Intensity", f"{vrow.get('carbon_intensity_gco2_tnm', '—')} gCO2/t-nm")
            with c3:
                kpi_card("Deadweight", f"{vrow.get('deadweight_tonnage', '—'):,}" if pd.notna(vrow.get("deadweight_tonnage")) else "—")
            with c4:
                kpi_card("Build Year", str(vrow.get("build_year", "—")))

            context_lines += [
                f"Vessel: {vrow.get('vessel_name')} ({vrow.get('vessel_type')}, built {vrow.get('build_year')})",
                f"Fuel type: {vrow.get('fuel_type')}, CII rating: {vrow.get('cii_rating')}",
                f"Carbon intensity: {vrow.get('carbon_intensity_gco2_tnm')} gCO2/tonne-nm",
                f"Deadweight tonnage: {vrow.get('deadweight_tonnage')}",
            ]

            linked_ship = shipments[shipments["carrier_vessel_id"] == vessel_id] if not shipments.empty and "carrier_vessel_id" in shipments else pd.DataFrame()
            linked_insights = pd.DataFrame()
            linked_reduction = pd.DataFrame()

        # ---- Shared: related shipments / emissions ----
        st.markdown("#### Related Scope 3 Shipments & Emissions")
        if not linked_ship.empty:
            sc1, sc2, sc3 = st.columns(3)
            with sc1:
                kpi_card("Shipments", f"{len(linked_ship):,}")
            with sc2:
                kpi_card("Total CO2e",
                         fmt_num(linked_ship["total_co2e_tonnes_from_legs"].sum(), " t")
                         if "total_co2e_tonnes_from_legs" in linked_ship else "—")
            with sc3:
                kpi_card("Total Cost", f"${fmt_num(linked_ship['cost_usd'].sum())}" if "cost_usd" in linked_ship else "—")

            context_lines += [
                f"Related shipments: {len(linked_ship)}",
                f"Total CO2e across related shipments: {fmt_num(linked_ship['total_co2e_tonnes_from_legs'].sum(), ' t') if 'total_co2e_tonnes_from_legs' in linked_ship else 'n/a'}",
                f"Total cost across related shipments: ${fmt_num(linked_ship['cost_usd'].sum()) if 'cost_usd' in linked_ship else 'n/a'}",
            ]

            if "mode" in linked_ship:
                by_mode = linked_ship.groupby("mode").size().reset_index(name="count")
                fig = px.bar(by_mode, x="mode", y="count", title="Related Shipments by Transport Mode")
                st.plotly_chart(style_fig(fig), use_container_width=True)
            st.dataframe(linked_ship.head(20), use_container_width=True, hide_index=True)
        else:
            st.caption("No directly linked shipments found for this entity in the current dataset.")

        if not linked_insights.empty:
            st.markdown("#### AI Insights Flagged for this Entity")
            for _, r in linked_insights.head(5).iterrows():
                st.info(f"**{r.get('title', 'Insight')}** — {r.get('finding', '')}")
                context_lines.append(f"AI insight: {r.get('title')} — {r.get('finding')}")

        if not linked_reduction.empty:
            st.markdown("#### Reduction Opportunities Targeting this Entity")
            st.dataframe(linked_reduction, use_container_width=True, hide_index=True)
            for _, r in linked_reduction.iterrows():
                context_lines.append(
                    f"Reduction opportunity: {r.get('opportunity_type')} — potential reduction "
                    f"{r.get('potential_co2e_reduction_tonnes')} tCO2e at cost ${r.get('estimated_cost_usd')}"
                )

        st.markdown("#### 🤖 AI-Generated Summary")
        context_text = "\n".join([l for l in context_lines if l])
        with st.spinner("Generating summary..."):
            narrative, was_ai = generate_ai_narrative(picked, context_text)
        if was_ai:
            st.success("Generated by Claude")
        st.markdown(narrative)

# ----------------------------------------------------------------------------
# PAGE: LIVE VESSEL MAP (MarineTraffic-style)
# ----------------------------------------------------------------------------
elif page == "Live Vessel Map":
    st.title("Live Vessel Dashboard")
    st.caption(
        "Synthetic AIS-style vessel positions plotted on a world map, in the "
        "style of a professional vessel-tracking platform. Select a vessel to "
        "see its route, ETA, speed, heading and estimated emissions."
    )

    vessels = active.get("vessels", pd.DataFrame())
    ais = active.get("ais_records", pd.DataFrame())
    ports = active.get("ports", pd.DataFrame())

    if vessels.empty or ais.empty:
        st.info("No vessel or AIS position data available for this hub.")
        with st.expander("Why am I seeing this? (diagnostics)"):
            st.write(f"`vessels` sheet rows: **{len(vessels)}**")
            st.write(f"`ais_records` sheet rows: **{len(ais)}**")
            st.write(
                "If both show 0, the `Dubai.xlsx` / `Singapore.xlsx` files in your repo are "
                "missing the `vessels` and/or `ais_records` sheets, or you're on the **Global** "
                "hub and at least one of the two workbooks is missing that sheet — Global "
                "combines both, so a missing sheet in either file shows up here as empty. "
                "Re-check both workbooks have sheet tabs named exactly `vessels` and `ais_records`."
            )
    else:
        # Latest known position per vessel
        ais_sorted = ais.copy()
        if "timestamp" in ais_sorted:
            ais_sorted["timestamp"] = pd.to_datetime(ais_sorted["timestamp"], errors="coerce")
            latest = ais_sorted.sort_values("timestamp").groupby("vessel_id").tail(1)
        else:
            latest = ais_sorted.groupby("vessel_id").tail(1)

        fleet = vessels.merge(latest, on="vessel_id", how="inner")

        fc1, fc2 = st.columns(2)
        with fc1:
            vtypes = ["All"] + sorted(fleet["vessel_type"].dropna().unique().tolist()) if "vessel_type" in fleet else ["All"]
            vtype_sel = st.selectbox("Vessel Type Filter", vtypes)
        with fc2:
            search = st.text_input("Search MarineTraffic-style (vessel name)", placeholder="e.g. Dubai Pugh")

        filtered_fleet = fleet.copy()
        if vtype_sel != "All":
            filtered_fleet = filtered_fleet[filtered_fleet["vessel_type"] == vtype_sel]
        if search:
            filtered_fleet = filtered_fleet[filtered_fleet["vessel_name"].str.contains(search, case=False, na=False)]

        st.markdown(f"**{len(filtered_fleet):,} vessels shown** (of {len(fleet):,} tracked)")

        # Real interactive, zoomable/pannable map — MarineTraffic-style
        if FOLIUM_AVAILABLE:
            vessel_map = build_marinetraffic_map(
                filtered_fleet, "latitude", "longitude",
                popup_fields=[
                    ("vessel_type", "Type"), ("fuel_type", "Fuel"),
                    ("speed_knots", "Speed (kn)"), ("heading_deg", "Heading (°)"),
                    ("nav_status", "Status"), ("cii_rating", "CII"),
                ],
                name_col="vessel_name", color_col="vessel_type",
            )
            map_result = st_folium(vessel_map, use_container_width=True, height=600, key="vessel_folium_map")
            clicked = map_result.get("last_object_clicked_tooltip") if map_result else None
            if clicked and clicked in filtered_fleet["vessel_name"].values:
                st.session_state["vessel_pick_default"] = clicked
        else:
            st.warning("Install `folium` and `streamlit-folium` for a real zoomable/pannable map "
                       "(see requirements.txt). Showing a static world map instead.")
            fig = px.scatter_geo(
                filtered_fleet,
                lat="latitude", lon="longitude",
                color="vessel_type" if "vessel_type" in filtered_fleet else None,
                hover_name="vessel_name",
                hover_data={"speed_knots": True, "heading_deg": True, "nav_status": True, "latitude": False, "longitude": False},
                projection="natural earth",
            )
            fig.update_traces(marker=dict(size=9, line=dict(width=0.5, color="white")))
            fig.update_geos(
                showland=True, landcolor="#f1f5f9",
                showocean=True, oceancolor="#e0f2fe",
                showcountries=True, countrycolor="#cbd5e1",
                bgcolor="rgba(0,0,0,0)",
            )
            fig.update_layout(height=600, margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(style_fig(fig), use_container_width=True)

        # Vessel selection -> MarineTraffic-style popup card
        st.markdown("#### Vessel Details")
        vessel_names = filtered_fleet["vessel_name"].dropna().unique().tolist()
        if vessel_names:
            default_pick = st.session_state.get("vessel_pick_default")
            default_idx = vessel_names.index(default_pick) if default_pick in vessel_names else 0
            picked = st.selectbox("Select a vessel", vessel_names, index=default_idx)
            row = filtered_fleet[filtered_fleet["vessel_name"] == picked].iloc[0]

            origin_name = destination_name = "—"
            if not ports.empty and "port_id" in ports.columns:
                if "home_port_id" in row and pd.notna(row.get("home_port_id")):
                    m = ports[ports["port_id"] == row["home_port_id"]]
                    if not m.empty:
                        origin_name = m.iloc[0]["port_name"]
                if "destination_port_id" in row and pd.notna(row.get("destination_port_id")):
                    m = ports[ports["port_id"] == row["destination_port_id"]]
                    if not m.empty:
                        destination_name = m.iloc[0]["port_name"]

            eta = row["timestamp"] if "timestamp" in row and pd.notna(row.get("timestamp")) else None
            est_co2e = None
            if "average_speed_knots" in row and "carbon_intensity_gco2_tnm" in row and "deadweight_tonnage" in row:
                # Rough illustrative estimate: intensity (g CO2/tonne-nm) x deadweight x nominal 500nm leg
                est_co2e = (float(row["carbon_intensity_gco2_tnm"]) * float(row["deadweight_tonnage"]) * 500) / 1_000_000

            st.markdown(
                f"""
                <div class="vessel-card">
                    <div class="vessel-card-title">🚢 {row.get('vessel_name', '—')}</div>
                    <div class="vessel-card-sub">{row.get('vessel_type', '—')} · IMO {row.get('imo_number', '—')} · Fuel: {row.get('fuel_type', '—')}</div>
                    <div class="vessel-route-row"><span>{origin_name}</span><span>→</span><span>{destination_name}</span></div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            m1, m2, m3, m4 = st.columns(4)
            with m1:
                kpi_card("Navigational Status", str(row.get("nav_status", "—")))
            with m2:
                kpi_card("Speed / Heading", f"{row.get('speed_knots', '—')} kn / {row.get('heading_deg', '—')}°")
            with m3:
                kpi_card("Deadweight Tonnage", f"{row.get('deadweight_tonnage', '—'):,}" if pd.notna(row.get("deadweight_tonnage")) else "—")
            with m4:
                kpi_card("Last Report", str(eta) if eta is not None else "—")

            m5, m6, m7 = st.columns(3)
            with m5:
                kpi_card("CII Rating", str(row.get("cii_rating", "—")))
            with m6:
                kpi_card("Capacity (TEU)", f"{row.get('capacity_teu', '—'):,}" if pd.notna(row.get("capacity_teu")) else "—")
            with m7:
                kpi_card("Est. CO2e (leg)", f"{est_co2e:,.1f} t" if est_co2e is not None else "—", "illustrative estimate")

            vessel_shipments = active.get("shipments", pd.DataFrame())
            if not vessel_shipments.empty and "carrier_vessel_id" in vessel_shipments:
                linked = vessel_shipments[vessel_shipments["carrier_vessel_id"] == row.get("vessel_id")]
                if not linked.empty:
                    st.markdown("##### Scope 3 Emissions History for this Vessel")
                    lc1, lc2, lc3 = st.columns(3)
                    with lc1:
                        kpi_card("Shipments Carried", f"{len(linked):,}")
                    with lc2:
                        kpi_card("Total CO2e",
                                 fmt_num(linked["total_co2e_tonnes_from_legs"].sum(), " t")
                                 if "total_co2e_tonnes_from_legs" in linked else "—")
                    with lc3:
                        kpi_card("Total Cost", f"${fmt_num(linked['cost_usd'].sum())}" if "cost_usd" in linked else "—")
                    st.dataframe(linked.head(20), use_container_width=True, hide_index=True)

            if st.button(f"🔬 Analyze {row.get('vessel_name', 'this vessel')} in AI Copilot"):
                st.session_state["copilot_entity_type"] = "Vessel"
                st.session_state["copilot_entity_pick"] = row.get("vessel_name")
                st.info("Now open **AI Copilot** from the sidebar to see the full dossier.")

        st.markdown("#### Fleet Summary")
        col1, col2 = st.columns(2)
        with col1:
            if "vessel_type" in filtered_fleet:
                counts = filtered_fleet["vessel_type"].value_counts().reset_index()
                counts.columns = ["Vessel Type", "Count"]
                fig2 = px.bar(counts, x="Vessel Type", y="Count", title="Fleet by Vessel Type")
                st.plotly_chart(style_fig(fig2), use_container_width=True)
        with col2:
            if "fuel_type" in filtered_fleet:
                fig3 = px.pie(filtered_fleet, names="fuel_type", title="Fleet by Fuel Type", hole=0.45)
                st.plotly_chart(style_fig(fig3), use_container_width=True)

        st.dataframe(
            filtered_fleet[[c for c in ["vessel_name", "vessel_type", "fuel_type", "speed_knots",
                                          "heading_deg", "nav_status", "cii_rating"] if c in filtered_fleet]].head(300),
            use_container_width=True, hide_index=True,
        )

# ----------------------------------------------------------------------------
# PAGE: LIVE TRUCK MAP
# ----------------------------------------------------------------------------
elif page == "Live Truck Map":
    st.title("Live Truck Dashboard")
    st.caption(
        "Synthetic GPS positions for the last-mile / inland trucking fleet, "
        "with driver, fuel type, and capacity details on selection."
    )

    trucks = active.get("trucks", pd.DataFrame())
    warehouses = active.get("warehouses", pd.DataFrame())

    if trucks.empty:
        st.info("No truck fleet data available for this hub.")
        with st.expander("Why am I seeing this? (diagnostics)"):
            st.write(f"`trucks` sheet rows: **{len(trucks)}**")
            st.write(
                "Make sure `Dubai.xlsx` / `Singapore.xlsx` both have a sheet tab named "
                "exactly `trucks` with `current_lat` / `current_lon` columns."
            )
    else:
        fc1, fc2 = st.columns(2)
        with fc1:
            fuels = ["All"] + sorted(trucks["fuel_type"].dropna().unique().tolist()) if "fuel_type" in trucks else ["All"]
            fuel_sel = st.selectbox("Fuel Type Filter", fuels)
        with fc2:
            search = st.text_input("Search by driver name", placeholder="e.g. Beverly Hanna")

        filtered_trucks = trucks.copy()
        if fuel_sel != "All":
            filtered_trucks = filtered_trucks[filtered_trucks["fuel_type"] == fuel_sel]
        if search:
            filtered_trucks = filtered_trucks[filtered_trucks["driver_name"].str.contains(search, case=False, na=False)]

        c1, c2, c3 = st.columns(3)
        with c1:
            kpi_card("Trucks Shown", f"{len(filtered_trucks):,}", f"of {len(trucks):,} total")
        with c2:
            kpi_card("Total Capacity", f"{filtered_trucks['capacity_tonnes'].sum():,.0f} t" if "capacity_tonnes" in filtered_trucks else "—")
        with c3:
            kpi_card("Fuel Types in Fleet", f"{trucks['fuel_type'].nunique()}" if "fuel_type" in trucks else "—")

        st.markdown(f"**{len(filtered_trucks):,} trucks shown**")

        if {"current_lat", "current_lon"}.issubset(filtered_trucks.columns):
            if FOLIUM_AVAILABLE:
                truck_map = build_marinetraffic_map(
                    filtered_trucks, "current_lat", "current_lon",
                    popup_fields=[("fuel_type", "Fuel"), ("capacity_tonnes", "Capacity (t)"),
                                  ("base_warehouse_id", "Base Warehouse")],
                    name_col="driver_name", color_col="fuel_type",
                )
                truck_map_result = st_folium(truck_map, use_container_width=True, height=600, key="truck_folium_map")
                clicked = truck_map_result.get("last_object_clicked_tooltip") if truck_map_result else None
                if clicked and "driver_name" in filtered_trucks and clicked in filtered_trucks["driver_name"].values:
                    st.session_state["truck_pick_default"] = filtered_trucks[filtered_trucks["driver_name"] == clicked].iloc[0]["truck_id"]
            else:
                st.warning("Install `folium` and `streamlit-folium` for a real zoomable/pannable map.")
                fig = px.scatter_geo(
                    filtered_trucks,
                    lat="current_lat", lon="current_lon",
                    color="fuel_type" if "fuel_type" in filtered_trucks else None,
                    hover_name="driver_name" if "driver_name" in filtered_trucks else None,
                    hover_data={"capacity_tonnes": True, "current_lat": False, "current_lon": False},
                    projection="natural earth",
                )
                fig.update_traces(marker=dict(size=8, symbol="triangle-up", line=dict(width=0.5, color="white")))
                fig.update_geos(
                    showland=True, landcolor="#f1f5f9",
                    showocean=True, oceancolor="#e0f2fe",
                    showcountries=True, countrycolor="#cbd5e1",
                    bgcolor="rgba(0,0,0,0)",
                    fitbounds="locations",
                )
                fig.update_layout(height=600, margin=dict(l=0, r=0, t=10, b=0))
                st.plotly_chart(style_fig(fig), use_container_width=True)

        st.markdown("#### Truck Details")
        if "truck_id" in filtered_trucks and not filtered_trucks.empty:
            truck_ids = filtered_trucks["truck_id"].dropna().unique().tolist()
            default_truck = st.session_state.get("truck_pick_default")
            default_idx = truck_ids.index(default_truck) if default_truck in truck_ids else 0
            picked = st.selectbox("Select a truck", truck_ids, index=default_idx)
            row = filtered_trucks[filtered_trucks["truck_id"] == picked].iloc[0]

            base_wh_name = "—"
            if not warehouses.empty and "warehouse_id" in warehouses.columns and pd.notna(row.get("base_warehouse_id")):
                m = warehouses[warehouses["warehouse_id"] == row["base_warehouse_id"]]
                if not m.empty:
                    base_wh_name = m.iloc[0].get("warehouse_name", "—")

            st.markdown(
                f"""
                <div class="vessel-card">
                    <div class="vessel-card-title">🚚 {row.get('truck_id', '—')} — {row.get('driver_name', '—')}</div>
                    <div class="vessel-card-sub">Fuel: {row.get('fuel_type', '—')} · Base Warehouse: {base_wh_name}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            m1, m2, m3 = st.columns(3)
            with m1:
                kpi_card("Capacity", f"{row.get('capacity_tonnes', '—')} t")
            with m2:
                kpi_card("Current Position", f"{row.get('current_lat', '—'):.4f}, {row.get('current_lon', '—'):.4f}"
                         if pd.notna(row.get("current_lat")) else "—")
            with m3:
                kpi_card("Base Warehouse", base_wh_name)

        st.markdown("#### Fleet by Fuel Type")
        if "fuel_type" in filtered_trucks:
            fig2 = px.pie(filtered_trucks, names="fuel_type", title="Truck Fleet by Fuel Type", hole=0.45)
            st.plotly_chart(style_fig(fig2), use_container_width=True)

        st.dataframe(filtered_trucks.head(300), use_container_width=True, hide_index=True)

# ----------------------------------------------------------------------------
# PAGE: CARBON & EMISSIONS
# ----------------------------------------------------------------------------
elif page == "Carbon & Emissions":
    st.title("Carbon Dashboard")

    emissions = active.get("emissions", pd.DataFrame())
    shipments = active.get("shipments", pd.DataFrame())

    if emissions.empty:
        st.info("No emissions ledger data available for this hub.")
    else:
        c1, c2, c3 = st.columns(3)
        with c1:
            kpi_card("Total CO2 (kg)", fmt_num(emissions["co2_kg"].sum()) if "co2_kg" in emissions else "—")
        with c2:
            kpi_card("Total CH4 (kg)", fmt_num(emissions["ch4_kg"].sum()) if "ch4_kg" in emissions else "—")
        with c3:
            if "n2o_kg" in emissions:
                kpi_card("Total N2O (kg)", fmt_num(emissions["n2o_kg"].sum()))
            elif "total_co2e_kg" in emissions:
                kpi_card("Total CO2e (kg)", fmt_num(emissions["total_co2e_kg"].sum()))
            else:
                kpi_card("Total CO2e (kg)", "—")

        has_gas_breakdown = {"co2_kg", "ch4_kg", "n2o_kg"}.issubset(emissions.columns)

        if has_gas_breakdown:
            st.markdown("#### Emissions Breakdown")
            col1, col2 = st.columns(2)
            with col1:
                gases = pd.DataFrame({
                    "Gas": ["CO2", "CH4", "N2O"],
                    "Total (kg)": [
                        emissions["co2_kg"].sum(),
                        emissions["ch4_kg"].sum(),
                        emissions["n2o_kg"].sum(),
                    ],
                })
                fig = px.pie(gases, names="Gas", values="Total (kg)", hole=0.5, title="Emissions by Gas Type")
                st.plotly_chart(style_fig(fig), use_container_width=True)
            with col2:
                if "methodology" in emissions and "total_co2e_kg" in emissions:
                    by_method = emissions.groupby("methodology")["total_co2e_kg"].sum().reset_index()
                    fig = px.bar(by_method, x="methodology", y="total_co2e_kg", title="CO2e by Calculation Methodology")
                    fig.update_xaxes(tickangle=-25)
                    st.plotly_chart(style_fig(fig), use_container_width=True)
        elif "methodology" in emissions and "total_co2e_kg" in emissions:
            st.markdown("#### Emissions by Assurance Status")
            by_method = emissions.groupby("methodology")["total_co2e_kg"].sum().reset_index()
            fig = px.bar(by_method, x="methodology", y="total_co2e_kg", title="Total CO2e (kg) by Assurance Status")
            st.plotly_chart(style_fig(fig), use_container_width=True)

        if "is_anomaly" in emissions:
            st.markdown("#### Anomaly Flags")
            anomalies = emissions[emissions["is_anomaly"] == 1]
            st.metric("Flagged Anomalous Emission Records", len(anomalies))
            if not anomalies.empty:
                st.dataframe(anomalies.head(50), use_container_width=True, hide_index=True)

        if not shipments.empty and "mode" in shipments and "total_co2e_tonnes_from_legs" in shipments:
            st.markdown("#### Emissions by Transport Mode")
            by_mode = shipments.groupby("mode")["total_co2e_tonnes_from_legs"].sum().reset_index()
            fig = px.bar(by_mode.sort_values("total_co2e_tonnes_from_legs", ascending=False),
                         x="mode", y="total_co2e_tonnes_from_legs", title="Total CO2e (tonnes) by Transport Mode")
            st.plotly_chart(style_fig(fig), use_container_width=True)

# ----------------------------------------------------------------------------
# PAGE: SHIPMENT INTELLIGENCE
# ----------------------------------------------------------------------------
elif page == "Shipment Intelligence":
    st.title("Shipment Intelligence")

    shipments = active.get("shipments", pd.DataFrame())
    if shipments.empty:
        st.info("No shipment data available for this hub.")
    else:
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            kpi_card("Total Shipments", f"{len(shipments):,}")
        with c2:
            kpi_card("Total Cost", f"${fmt_num(shipments['cost_usd'].sum())}" if "cost_usd" in shipments else "—")
        with c3:
            delivered = (shipments["status"] == "Delivered").sum() if "status" in shipments else 0
            kpi_card("Delivered", f"{delivered:,}")
        with c4:
            kpi_card("Total CO2e", fmt_num(shipments["total_co2e_tonnes_from_legs"].sum(), " t")
                     if "total_co2e_tonnes_from_legs" in shipments else "—")

        st.markdown("#### Filters")
        fc1, fc2 = st.columns(2)
        with fc1:
            modes = ["All"] + sorted(shipments["mode"].dropna().unique().tolist()) if "mode" in shipments else ["All"]
            mode_sel = st.selectbox("Mode", modes)
        with fc2:
            statuses = ["All"] + sorted(shipments["status"].dropna().unique().tolist()) if "status" in shipments else ["All"]
            status_sel = st.selectbox("Status", statuses)

        filtered = shipments.copy()
        if mode_sel != "All":
            filtered = filtered[filtered["mode"] == mode_sel]
        if status_sel != "All":
            filtered = filtered[filtered["status"] == status_sel]

        st.markdown(f"#### Shipment Table ({len(filtered):,} records)")
        st.dataframe(filtered.head(500), use_container_width=True, hide_index=True)

        if "status" in shipments:
            st.markdown("#### Status Distribution")
            fig = px.pie(shipments, names="status", title="Shipment Status Breakdown", hole=0.45)
            st.plotly_chart(style_fig(fig), use_container_width=True)

# ----------------------------------------------------------------------------
# PAGE: SUPPLIER INTELLIGENCE
# ----------------------------------------------------------------------------
elif page == "Supplier Intelligence":
    st.title("Supplier Intelligence")

    suppliers = active.get("suppliers", pd.DataFrame())
    esg = active.get("supplier_esg_scores", pd.DataFrame())

    if suppliers.empty:
        st.info("No supplier data available for this hub.")
    else:
        merged = suppliers.merge(esg, on="supplier_id", how="left", suffixes=("", "_esg")) if not esg.empty else suppliers

        c1, c2, c3 = st.columns(3)
        with c1:
            kpi_card("Total Suppliers", f"{len(suppliers):,}")
        with c2:
            kpi_card("Total Annual Spend", f"${fmt_num(suppliers['annual_spend_usd'].sum())}"
                     if "annual_spend_usd" in suppliers else "—")
        with c3:
            if "esg_rating" in merged:
                top_rating = merged["esg_rating"].mode().iloc[0] if not merged["esg_rating"].mode().empty else "—"
                kpi_card("Most Common ESG Rating", str(top_rating))

        col1, col2 = st.columns(2)
        with col1:
            if "carbon_intensity_score" in suppliers:
                fig = px.histogram(suppliers, x="carbon_intensity_score", nbins=30,
                                    title="Supplier Carbon Intensity Distribution")
                st.plotly_chart(style_fig(fig), use_container_width=True)
        with col2:
            if "esg_rating" in merged:
                counts = merged["esg_rating"].value_counts().reset_index()
                counts.columns = ["ESG Rating", "Count"]
                fig = px.bar(counts, x="ESG Rating", y="Count", title="Supplier ESG Rating Distribution")
                st.plotly_chart(style_fig(fig), use_container_width=True)

        st.markdown("#### Top Suppliers by Annual Spend")
        if "annual_spend_usd" in suppliers:
            top = suppliers.sort_values("annual_spend_usd", ascending=False).head(15)
            fig = px.bar(top, x="supplier_name", y="annual_spend_usd", color="country" if "country" in top else None,
                         title="Top 15 Suppliers by Annual Spend (USD)")
            fig.update_xaxes(tickangle=-30)
            st.plotly_chart(style_fig(fig), use_container_width=True)

        st.markdown("#### Supplier Scorecard Table")
        st.dataframe(merged.head(300), use_container_width=True, hide_index=True)

# ----------------------------------------------------------------------------
# PAGE: GIS / NETWORK MAP
# ----------------------------------------------------------------------------
elif page == "GIS / Network Map":
    st.title("GIS Dashboard — Network Map")

    ports = active.get("ports", pd.DataFrame())
    vessels = active.get("vessels", pd.DataFrame())
    warehouses = active.get("warehouses", pd.DataFrame())
    suppliers = active.get("suppliers", pd.DataFrame())

    layer_choice = st.multiselect(
        "Layers", ["Ports", "Warehouses", "Suppliers"], default=["Ports", "Warehouses", "Suppliers"]
    )

    fig = go.Figure()

    if "Ports" in layer_choice and not ports.empty and {"latitude", "longitude"}.issubset(ports.columns):
        fig.add_trace(go.Scattergeo(
            lon=ports["longitude"], lat=ports["latitude"],
            text=ports.get("port_name", ""), mode="markers",
            marker=dict(size=10, color="#0284c7", symbol="square"),
            name="Ports",
        ))

    if "Warehouses" in layer_choice and not warehouses.empty and {"latitude", "longitude"}.issubset(warehouses.columns):
        fig.add_trace(go.Scattergeo(
            lon=warehouses["longitude"], lat=warehouses["latitude"],
            text=warehouses.get("warehouse_name", ""), mode="markers",
            marker=dict(size=7, color="#d97706", symbol="triangle-up"),
            name="Warehouses",
        ))

    if "Suppliers" in layer_choice and not suppliers.empty and {"latitude", "longitude"}.issubset(suppliers.columns):
        fig.add_trace(go.Scattergeo(
            lon=suppliers["longitude"], lat=suppliers["latitude"],
            text=suppliers.get("supplier_name", ""), mode="markers",
            marker=dict(size=6, color="#db2777", opacity=0.7),
            name="Suppliers",
        ))

    fig.update_geos(
        projection_type="natural earth",
        showland=True, landcolor="#f1f5f9",
        showocean=True, oceancolor="#e0f2fe",
        showcountries=True, countrycolor="#cbd5e1",
        bgcolor="rgba(0,0,0,0)",
    )
    fig.update_layout(height=650, title="Network: Ports, Warehouses & Suppliers")
    st.plotly_chart(style_fig(fig), use_container_width=True)

    if not vessels.empty:
        st.markdown("#### Vessel Fleet Summary")
        col1, col2 = st.columns(2)
        with col1:
            if "vessel_type" in vessels:
                fig2 = px.bar(value_counts_df(vessels["vessel_type"], "vessel_type"),
                              x="vessel_type", y="count", title="Vessel Fleet by Type")
                st.plotly_chart(style_fig(fig2), use_container_width=True)
        with col2:
            if "fuel_type" in vessels:
                fig3 = px.pie(vessels, names="fuel_type", title="Vessel Fleet by Fuel Type", hole=0.45)
                st.plotly_chart(style_fig(fig3), use_container_width=True)
        st.dataframe(vessels.head(200), use_container_width=True, hide_index=True)

# ----------------------------------------------------------------------------
# PAGE: REDUCTION OPPORTUNITIES
# ----------------------------------------------------------------------------
elif page == "Reduction Opportunities":
    st.title("Carbon Reduction Opportunities")

    red = active.get("reduction_opportunities", pd.DataFrame())
    if red.empty:
        st.info("No reduction opportunity data available for this hub.")
    else:
        c1, c2, c3 = st.columns(3)
        with c1:
            kpi_card("Opportunities Identified", f"{len(red):,}")
        with c2:
            kpi_card("Total Potential CO2e Reduction",
                     fmt_num(red["potential_co2e_reduction_tonnes"].sum(), " t")
                     if "potential_co2e_reduction_tonnes" in red else "—")
        with c3:
            kpi_card("Total Estimated Cost", f"${fmt_num(red['estimated_cost_usd'].sum())}"
                     if "estimated_cost_usd" in red else "—")

        col1, col2 = st.columns(2)
        with col1:
            if "status" in red:
                fig = px.pie(red, names="status", title="Opportunity Status", hole=0.45)
                st.plotly_chart(style_fig(fig), use_container_width=True)
        with col2:
            if "implementation_difficulty" in red:
                fig = px.bar(value_counts_df(red["implementation_difficulty"], "difficulty"),
                             x="difficulty", y="count", title="Opportunities by Implementation Difficulty")
                st.plotly_chart(style_fig(fig), use_container_width=True)

        if {"estimated_cost_usd", "potential_co2e_reduction_tonnes"}.issubset(red.columns):
            st.markdown("#### Cost vs. Carbon Impact")
            fig = px.scatter(
                red, x="estimated_cost_usd", y="potential_co2e_reduction_tonnes",
                color="implementation_difficulty" if "implementation_difficulty" in red else None,
                size="potential_co2e_reduction_tonnes", hover_name="opportunity_type",
                title="Estimated Cost vs. Potential CO2e Reduction",
            )
            st.plotly_chart(style_fig(fig), use_container_width=True)

        st.markdown("#### All Opportunities")
        st.dataframe(red, use_container_width=True, hide_index=True)

# ----------------------------------------------------------------------------
# PAGE: AI INSIGHTS
# ----------------------------------------------------------------------------
elif page == "AI Insights":
    st.title("AI Carbon Insights")

    insights = active.get("ai_insights", pd.DataFrame())
    if insights.empty:
        st.info("No AI insight data available for this hub.")
    else:
        c1, c2, c3 = st.columns(3)
        with c1:
            kpi_card("Total Insights", f"{len(insights):,}")
        with c2:
            if "priority" in insights:
                high = (insights["priority"] == "High").sum()
                kpi_card("High Priority", f"{high:,}")
        with c3:
            if "estimated_co2e_impact_tonnes" in insights:
                kpi_card("Total Potential CO2e Impact",
                         fmt_num(insights["estimated_co2e_impact_tonnes"].sum(), " t"))

        colf1, colf2 = st.columns(2)
        with colf1:
            types = ["All"] + sorted(insights["insight_type"].dropna().unique().tolist()) if "insight_type" in insights else ["All"]
            type_sel = st.selectbox("Insight Type", types)
        with colf2:
            priorities = ["All"] + sorted(insights["priority"].dropna().unique().tolist()) if "priority" in insights else ["All"]
            prio_sel = st.selectbox("Priority", priorities)

        filtered = insights.copy()
        if type_sel != "All":
            filtered = filtered[filtered["insight_type"] == type_sel]
        if prio_sel != "All":
            filtered = filtered[filtered["priority"] == prio_sel]

        st.markdown(f"#### {len(filtered):,} Insight(s)")
        for _, row in filtered.head(30).iterrows():
            with st.expander(f"[{row.get('priority', '—')}] {row.get('title', 'Insight')}"):
                st.write(f"**Finding:** {row.get('finding', '—')}")
                st.write(f"**Recommended Action:** {row.get('recommended_action', '—')}")
                st.write(f"**Business Impact:** {row.get('business_impact', '—')}")
                cA, cB, cC = st.columns(3)
                cA.metric("CO2e Impact (t)", fmt_num(row.get("estimated_co2e_impact_tonnes", np.nan)))
                cB.metric("Cost Impact (USD)", fmt_num(row.get("estimated_cost_impact_usd", np.nan)))
                cC.metric("Confidence", f"{row.get('confidence_score', '—')}")

# ----------------------------------------------------------------------------
# FOOTER
# ----------------------------------------------------------------------------
st.markdown(
    '<div class="footer-note">Demonstration platform powered by synthetic data. '
    'Company names, transactions, emissions and operational events are fictional '
    'and are for demonstration purposes only.</div>',
    unsafe_allow_html=True,
)
