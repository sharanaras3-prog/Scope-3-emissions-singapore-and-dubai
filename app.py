"""
Marcura Scope 3 Intelligence — Demonstration Platform
Synthetic data only. Company names, transactions, emissions and operational
events are fictional and generated for demo purposes.
"""
import json
import os
import pandas as pd
import numpy as np
import pydeck as pdk
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

# ---------------------------------------------------------------------
# Page config & palette (deliberately NOT blue — deep teal / charcoal / amber)
# ---------------------------------------------------------------------
st.set_page_config(
    page_title="Marcura Scope 3 Intelligence",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded",
)

BG = "#0F1B1E"          # deep charcoal-teal
PANEL = "#16292C"       # panel background
ACCENT = "#E8A93C"      # amber/gold accent
ACCENT_2 = "#C9642B"    # burnt orange secondary accent
GOOD = "#5FA37A"        # muted sea-green (positive)
WARN = "#D9724B"        # terracotta (risk)
TEXT = "#EAE4D8"        # warm off-white
MUTED = "#9BB0AE"

PALETTE = [ACCENT, "#7FB3A3", ACCENT_2, "#B98CC9", GOOD, WARN, "#5A87A0"]

CUSTOM_CSS = f"""
<style>
.stApp {{
    background: linear-gradient(180deg, {BG} 0%, #0B1315 100%);
    color: {TEXT};
}}
section[data-testid="stSidebar"] {{
    background-color: {PANEL};
    border-right: 1px solid #22383B;
}}
div[data-testid="stMetric"] {{
    background-color: {PANEL};
    border: 1px solid #22383B;
    border-radius: 10px;
    padding: 14px 16px;
}}
div[data-testid="stMetricLabel"] {{
    color: {MUTED} !important;
}}
div[data-testid="stMetricValue"] {{
    color: {ACCENT} !important;
}}
h1, h2, h3 {{
    color: {TEXT};
}}
.hub-banner {{
    background: linear-gradient(90deg, {PANEL} 0%, #1C3236 100%);
    border-left: 4px solid {ACCENT};
    padding: 14px 20px;
    border-radius: 6px;
    margin-bottom: 18px;
}}
.insight-card {{
    background-color: {PANEL};
    border: 1px solid #22383B;
    border-left: 4px solid {ACCENT_2};
    border-radius: 8px;
    padding: 14px 18px;
    margin-bottom: 12px;
}}
.disclaimer {{
    font-size: 0.78rem;
    color: {MUTED};
    border-top: 1px solid #22383B;
    padding-top: 10px;
    margin-top: 30px;
}}
[data-testid="stDataFrame"] {{
    background-color: {PANEL};
}}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

PLOTLY_TEMPLATE = dict(
    layout=go.Layout(
        paper_bgcolor=BG,
        plot_bgcolor=BG,
        font=dict(color=TEXT),
        colorway=PALETTE,
        legend=dict(bgcolor="rgba(0,0,0,0)"),
        xaxis=dict(gridcolor="#22383B", zerolinecolor="#22383B"),
        yaxis=dict(gridcolor="#22383B", zerolinecolor="#22383B"),
    )
)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


@st.cache_data
def load_json(path):
    if not os.path.exists(path):
        st.error(
            f"**Missing data file:** `{path}`\n\n"
            "This usually means the `data/` folder wasn't pushed to your GitHub repo, "
            "or the app was deployed from the wrong folder. Check that `data/singapore/`, "
            "`data/dubai/`, and `data/global-summary.json` exist alongside `app.py` in your repo."
        )
        st.stop()
    with open(path) as f:
        return json.load(f)


@st.cache_data
def load_hub(hub_key):
    d = os.path.join(DATA_DIR, hub_key)
    return {
        "summary": load_json(os.path.join(d, "executive-summary.json")),
        "vessels": pd.DataFrame(load_json(os.path.join(d, "vessels.json"))),
        "routes": load_json(os.path.join(d, "routes.json")),
        "suppliers": pd.DataFrame(load_json(os.path.join(d, "suppliers.json"))),
        "emissions": pd.DataFrame(load_json(os.path.join(d, "emissions.json"))),
        "shipments": pd.DataFrame(load_json(os.path.join(d, "shipments.json"))),
        "insights": load_json(os.path.join(d, "ai-insights.json")),
    }


@st.cache_data
def load_global():
    return load_json(os.path.join(DATA_DIR, "global-summary.json"))


# ---------------------------------------------------------------------
# Sidebar — hub selector & navigation
# ---------------------------------------------------------------------
st.sidebar.markdown("## 🧭 Marcura Scope 3\n### Intelligence Platform")
hub_choice = st.sidebar.radio(
    "Select Hub",
    ["Global Overview", "Singapore Hub", "Dubai Hub", "Hub Comparison"],
    index=0,
)

st.sidebar.markdown("---")
st.sidebar.caption(
    "Demonstration platform powered by synthetic data. Company names, "
    "transactions, emissions and operational events are fictional."
)

hub_key_map = {"Singapore Hub": "singapore", "Dubai Hub": "dubai"}


def kpi_row(summary):
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Scope 3 Emissions", f"{summary.get('total_scope3_tco2e', summary.get('global_scope3_tco2e', 0)):,.0f} tCO2e")
    c2.metric("Procurement Spend", f"${summary['total_procurement_spend_usd']:,.0f}")
    c3.metric("Active Suppliers", f"{summary['active_suppliers']}")
    c4.metric("Shipments Monitored", f"{summary['shipments_monitored']}")
    c5.metric("Reduction Opportunities", f"{summary['carbon_reduction_opportunities']}")


def render_3d_vessel_map(vessels_df, routes, anchor):
    """3D-tilted deck.gl map: vessel positions as elevated columns + route paths."""
    vessels_df = vessels_df.copy()
    color_map = {
        "Underway": [95, 163, 122],
        "At Anchor": [232, 169, 60],
        "Moored": [154, 176, 174],
        "Delayed": [217, 114, 75],
    }
    vessels_df["color"] = vessels_df["status"].map(color_map)
    vessels_df["elevation"] = vessels_df["speed_knots"] * 800 + 200

    path_data = [{"path": r["path"], "name": r["name"]} for r in routes]

    column_layer = pdk.Layer(
        "ColumnLayer",
        data=vessels_df,
        get_position=["lon", "lat"],
        get_elevation="elevation",
        elevation_scale=1,
        radius=8000,
        get_fill_color="color",
        pickable=True,
        auto_highlight=True,
    )

    path_layer = pdk.Layer(
        "PathLayer",
        data=path_data,
        get_path="path",
        get_color=[232, 169, 60, 120],
        width_scale=1,
        width_min_pixels=2,
        pickable=False,
    )

    view_state = pdk.ViewState(
        latitude=anchor[0], longitude=anchor[1],
        zoom=3.4, pitch=45, bearing=15,
    )

    tooltip = {
        "html": "<b>{vessel_name}</b><br/>Status: {status}<br/>Speed: {speed_knots} kn<br/>Route: {route}",
        "style": {"backgroundColor": PANEL, "color": TEXT},
    }

    r = pdk.Deck(
        layers=[path_layer, column_layer],
        initial_view_state=view_state,
        tooltip=tooltip,
        map_style="mapbox://styles/mapbox/dark-v10",
    )
    st.pydeck_chart(r, use_container_width=True)


def render_insights(insights):
    for ins in insights:
        impact_color = {"High": WARN, "Medium": ACCENT, "Low": GOOD}.get(ins["impact"], ACCENT)
        st.markdown(
            f"""<div class="insight-card">
            <b style="color:{ACCENT};">{ins['title']}</b>
            &nbsp;<span style="background-color:{impact_color}; color:#0F1B1E; padding:2px 8px;
            border-radius:10px; font-size:0.75rem; font-weight:600;">{ins['impact']} impact</span>
            &nbsp;<span style="color:{MUTED}; font-size:0.78rem;">{ins['category']}</span>
            <p style="margin:6px 0 0 0; color:{TEXT};">{ins['detail']}</p>
            </div>""",
            unsafe_allow_html=True,
        )


def emissions_chart(emissions_df):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=emissions_df["month"], y=emissions_df["scope3_tco2e"],
        mode="lines+markers", name="Scope 3 (tCO2e)",
        line=dict(color=ACCENT, width=3),
        marker=dict(size=6, color=ACCENT),
    ))
    fig.update_layout(**PLOTLY_TEMPLATE["layout"], title="Scope 3 Emissions Trend", height=380)
    st.plotly_chart(fig, use_container_width=True)

    fig2 = px.area(
        emissions_df, x="month",
        y=["transport_pct", "procurement_pct", "packaging_pct", "other_pct"],
        title="Emissions Composition (%)",
    )
    fig2.update_layout(**PLOTLY_TEMPLATE["layout"], height=340)
    st.plotly_chart(fig2, use_container_width=True)


def suppliers_view(suppliers_df):
    col1, col2 = st.columns([1.3, 1])
    with col1:
        fig = px.scatter(
            suppliers_df, x="scope3_emissions_tco2e", y="esg_score",
            size="spend_usd", color="esg_tier",
            hover_name="name",
            color_discrete_map={"Leading": GOOD, "Developing": ACCENT, "At Risk": WARN},
            title="Supplier ESG vs Scope 3 Emissions (bubble = spend)",
        )
        fig.update_layout(**PLOTLY_TEMPLATE["layout"], height=440)
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        tier_counts = suppliers_df["esg_tier"].value_counts().reset_index()
        tier_counts.columns = ["tier", "count"]
        fig3 = px.pie(
            tier_counts, names="tier", values="count", hole=0.5,
            color="tier",
            color_discrete_map={"Leading": GOOD, "Developing": ACCENT, "At Risk": WARN},
            title="Supplier ESG Tier Mix",
        )
        fig3.update_layout(**PLOTLY_TEMPLATE["layout"], height=440)
        st.plotly_chart(fig3, use_container_width=True)

    st.dataframe(
        suppliers_df.sort_values("scope3_emissions_tco2e", ascending=False),
        use_container_width=True, height=320,
    )


def shipments_view(shipments_df):
    c1, c2 = st.columns(2)
    with c1:
        status_counts = shipments_df["status"].value_counts().reset_index()
        status_counts.columns = ["status", "count"]
        fig = px.bar(
            status_counts, x="status", y="count", color="status",
            color_discrete_sequence=PALETTE, title="Shipments by Status",
        )
        fig.update_layout(**PLOTLY_TEMPLATE["layout"], height=360, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        fig2 = px.histogram(
            shipments_df, x="dwell_time_hours", nbins=20,
            title="Dwell Time Distribution (hrs)",
            color_discrete_sequence=[ACCENT_2],
        )
        fig2.update_layout(**PLOTLY_TEMPLATE["layout"], height=360)
        st.plotly_chart(fig2, use_container_width=True)
    st.dataframe(shipments_df, use_container_width=True, height=320)


def vessel_speed_view(vessels_df):
    c1, c2 = st.columns(2)
    with c1:
        fig = px.bar(
            vessels_df.sort_values("speed_knots", ascending=False).head(15),
            x="vessel_name", y="speed_knots", color="status",
            color_discrete_map={"Underway": GOOD, "At Anchor": ACCENT, "Moored": MUTED, "Delayed": WARN},
            title="Top Vessel Speeds (knots)",
        )
        fig.update_layout(**PLOTLY_TEMPLATE["layout"], height=380, xaxis_tickangle=-40)
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        fig2 = px.scatter(
            vessels_df, x="speed_knots", y="eta_hours", color="status",
            size="co2_tonnes_voyage", hover_name="vessel_name",
            color_discrete_map={"Underway": GOOD, "At Anchor": ACCENT, "Moored": MUTED, "Delayed": WARN},
            title="Speed vs ETA (bubble = voyage CO2)",
        )
        fig2.update_layout(**PLOTLY_TEMPLATE["layout"], height=380)
        st.plotly_chart(fig2, use_container_width=True)


# ---------------------------------------------------------------------
# GLOBAL OVERVIEW
# ---------------------------------------------------------------------
if hub_choice == "Global Overview":
    st.title("🧭 Marcura Scope 3 Intelligence")
    st.markdown(
        """<div class="hub-banner">
        <b>Global Platform</b> — unified visibility across the Singapore
        (maritime transshipment & operational intelligence) and Dubai
        (maritime procurement & supplier intelligence) hubs.
        </div>""",
        unsafe_allow_html=True,
    )
    g = load_global()
    kpi_row(g)

    st.markdown("### Hub Snapshot")
    c1, c2 = st.columns(2)
    for col, key, label in [(c1, "singapore", "Singapore Hub"), (c2, "dubai", "Dubai Hub")]:
        s = g[key]
        with col:
            st.markdown(f"#### {label}")
            st.write(f"**Primary hotspot:** {s['primary_hotspot']}")
            st.write(f"**Main opportunity:** {s['main_opportunity']}")
            st.write(f"Scope 3: **{s['total_scope3_tco2e']:,.0f} tCO2e** · "
                     f"Suppliers: **{s['active_suppliers']}** · "
                     f"Shipments: **{s['shipments_monitored']}**")

    st.markdown(
        '<p class="disclaimer">Demonstration platform powered by synthetic data. '
        'Company names, transactions, emissions and operational events are fictional.</p>',
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------
# HUB PAGES
# ---------------------------------------------------------------------
elif hub_choice in hub_key_map:
    hub_key = hub_key_map[hub_choice]
    hub = load_hub(hub_key)
    summary = hub["summary"]
    anchor = (1.2644, 103.8200) if hub_key == "singapore" else (25.0161, 55.0614)
    story = ("PSA, Tuas, ASEAN connectivity, transshipment & electronics"
              if hub_key == "singapore" else
              "Jebel Ali, JAFZA, Dubai South, sea–air corridors & GCC distribution")

    st.title(f"🧭 {hub_choice}")
    st.markdown(
        f"""<div class="hub-banner"><b>{hub_choice}</b> — {story}.</div>""",
        unsafe_allow_html=True,
    )
    kpi_row(summary)

    tabs = st.tabs([
        "Executive Overview", "Vessel & Route Map (3D)", "Shipment Intelligence",
        "Supplier / Procurement ESG", "Scope 3 Emissions", "AI Insights",
    ])

    with tabs[0]:
        st.subheader("Executive Overview")
        emissions_chart(hub["emissions"])
        st.markdown("##### Recent Shipment Activity")
        st.dataframe(hub["shipments"].head(10), use_container_width=True)

    with tabs[1]:
        st.subheader("Vessel Movement & Speed — 3D Map")
        st.caption("Column height ∝ vessel speed. Color = operational status. Lines = active trade routes.")
        render_3d_vessel_map(hub["vessels"], hub["routes"], anchor)
        vessel_speed_view(hub["vessels"])

    with tabs[2]:
        st.subheader("Shipment Intelligence")
        shipments_view(hub["shipments"])

    with tabs[3]:
        title = "Supplier Network & Scope 3 Intelligence" if hub_key == "singapore" else "Supplier ESG & Procurement Intelligence"
        st.subheader(title)
        suppliers_view(hub["suppliers"])

    with tabs[4]:
        st.subheader("Scope 3 Emissions Detail")
        emissions_chart(hub["emissions"])
        st.markdown("##### Emissions by Supplier (Top 10)")
        top10 = hub["suppliers"].sort_values("scope3_emissions_tco2e", ascending=False).head(10)
        fig = px.bar(top10, x="name", y="scope3_emissions_tco2e", color="esg_tier",
                     color_discrete_map={"Leading": GOOD, "Developing": ACCENT, "At Risk": WARN})
        fig.update_layout(**PLOTLY_TEMPLATE["layout"], height=400, xaxis_tickangle=-35)
        st.plotly_chart(fig, use_container_width=True)

    with tabs[5]:
        st.subheader("AI Insights & Reduction Opportunities")
        render_insights(hub["insights"])

    st.markdown(
        '<p class="disclaimer">Demonstration platform powered by synthetic data. '
        'Company names, transactions, emissions and operational events are fictional.</p>',
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------
# COMPARISON PAGE
# ---------------------------------------------------------------------
elif hub_choice == "Hub Comparison":
    st.title("🧭 Singapore vs Dubai — Hub Comparison")
    g = load_global()
    sg, dxb = g["singapore"], g["dubai"]

    comp_df = pd.DataFrame([
        {"Metric": "Total Scope 3 emissions (tCO2e)", "Singapore": sg["total_scope3_tco2e"], "Dubai": dxb["total_scope3_tco2e"]},
        {"Metric": "Active suppliers", "Singapore": sg["active_suppliers"], "Dubai": dxb["active_suppliers"]},
        {"Metric": "Shipments monitored", "Singapore": sg["shipments_monitored"], "Dubai": dxb["shipments_monitored"]},
        {"Metric": "Procurement spend (USD)", "Singapore": sg["total_procurement_spend_usd"], "Dubai": dxb["total_procurement_spend_usd"]},
    ])
    st.dataframe(comp_df, use_container_width=True, hide_index=True)

    st.markdown("| | Singapore | Dubai |\n|---|---|---|\n"
                f"| Primary hotspot | {sg['primary_hotspot']} | {dxb['primary_hotspot']} |\n"
                f"| Main opportunity | {sg['main_opportunity']} | {dxb['main_opportunity']} |")

    fig = go.Figure(data=[
        go.Bar(name="Singapore", x=comp_df["Metric"][:2], y=comp_df["Singapore"][:2], marker_color=ACCENT),
        go.Bar(name="Dubai", x=comp_df["Metric"][:2], y=comp_df["Dubai"][:2], marker_color=ACCENT_2),
    ])
    fig.update_layout(**PLOTLY_TEMPLATE["layout"], barmode="group", height=420, title="Emissions & Supplier Base")
    st.plotly_chart(fig, use_container_width=True)

    st.markdown(
        '<p class="disclaimer">Demonstration platform powered by synthetic data. '
        'Company names, transactions, emissions and operational events are fictional.</p>',
        unsafe_allow_html=True,
    )
