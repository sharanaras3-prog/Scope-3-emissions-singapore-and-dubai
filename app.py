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
    .stApp { background-color: #0b1220; }
    #MainMenu, footer {visibility: hidden;}

    .kpi-card {
        background: linear-gradient(135deg, rgba(30,41,59,0.85), rgba(15,23,42,0.85));
        border: 1px solid rgba(56,189,248,0.25);
        border-radius: 14px;
        padding: 18px 20px;
        margin-bottom: 8px;
    }
    .kpi-label { font-size: 0.78rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; }
    .kpi-value { font-size: 1.65rem; font-weight: 700; color: #e2e8f0; margin-top: 4px; }
    .kpi-sub { font-size: 0.78rem; color: #38bdf8; margin-top: 2px; }

    .hub-banner {
        background: linear-gradient(90deg, rgba(14,116,144,0.35), rgba(15,23,42,0.05));
        border-left: 4px solid #22d3ee;
        border-radius: 8px;
        padding: 10px 16px;
        margin-bottom: 18px;
        color: #cbd5e1;
        font-size: 0.92rem;
    }
    .footer-note {
        text-align: center;
        color: #64748b;
        font-size: 0.75rem;
        padding: 18px 0 6px 0;
        border-top: 1px solid rgba(148,163,184,0.15);
        margin-top: 32px;
    }
    section[data-testid="stSidebar"] { background-color: #0f172a; }
    h1, h2, h3 { color: #e2e8f0; }
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
    "shipments", "emissions", "warehouses", "trucks", "hubs",
]

# Workbook file names, keyed by hub. Each workbook is expected to sit right
# next to this script (no data/ subfolder needed) with one sheet per dataset
# (sheet name == dataset name, e.g. "suppliers", "shipments", "emissions"...).
HUB_WORKBOOKS = {
    "dubai": "Dubai.xlsx",
    "singapore": "Singapore.xlsx",
}


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
        "Executive Dashboard",
        "Carbon & Emissions",
        "Shipment Intelligence",
        "Supplier Intelligence",
        "GIS / Network Map",
        "Reduction Opportunities",
        "AI Insights",
    ],
)

st.sidebar.markdown("---")
st.sidebar.caption(
    "Singapore = Maritime Operations Hub\n\nDubai = Procurement & Supplier Intelligence Hub"
)

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


PLOTLY_TEMPLATE = "plotly_dark"


def style_fig(fig):
    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e2e8f0"),
        margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
    )
    return fig


# ----------------------------------------------------------------------------
# PAGE: EXECUTIVE DASHBOARD
# ----------------------------------------------------------------------------
if page == "Executive Dashboard":
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
            marker=dict(size=10, color="#22d3ee", symbol="square"),
            name="Ports",
        ))

    if "Warehouses" in layer_choice and not warehouses.empty and {"latitude", "longitude"}.issubset(warehouses.columns):
        fig.add_trace(go.Scattergeo(
            lon=warehouses["longitude"], lat=warehouses["latitude"],
            text=warehouses.get("warehouse_name", ""), mode="markers",
            marker=dict(size=7, color="#facc15", symbol="triangle-up"),
            name="Warehouses",
        ))

    if "Suppliers" in layer_choice and not suppliers.empty and {"latitude", "longitude"}.issubset(suppliers.columns):
        fig.add_trace(go.Scattergeo(
            lon=suppliers["longitude"], lat=suppliers["latitude"],
            text=suppliers.get("supplier_name", ""), mode="markers",
            marker=dict(size=6, color="#f472b6", opacity=0.7),
            name="Suppliers",
        ))

    fig.update_geos(
        projection_type="natural earth",
        showland=True, landcolor="#1e293b",
        showocean=True, oceancolor="#0b1220",
        showcountries=True, countrycolor="#334155",
        bgcolor="rgba(0,0,0,0)",
    )
    fig.update_layout(height=650, title="Network: Ports, Warehouses & Suppliers")
    st.plotly_chart(style_fig(fig), use_container_width=True)

    if not vessels.empty:
        st.markdown("#### Vessel Fleet Summary")
        col1, col2 = st.columns(2)
        with col1:
            if "vessel_type" in vessels:
                fig2 = px.bar(vessels["vessel_type"].value_counts().reset_index(name="count").rename(columns={"index": "vessel_type"}),
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
                fig = px.bar(red["implementation_difficulty"].value_counts().reset_index(name="count").rename(columns={"index": "difficulty"}),
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
