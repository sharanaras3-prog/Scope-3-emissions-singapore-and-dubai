import streamlit as st
from utils.style import inject_css, hub_selector, footer, kpi_card
from data.synthetic import get_kpis, get_ports

st.set_page_config(
    page_title="Marcura Scope 3 Carbon Intelligence",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_css()
hub = hub_selector()

st.sidebar.markdown("---")
st.sidebar.caption(
    "Executive Dashboard · Live Vessel Map · Scope 3 Calculator "
    "are available in the pages panel above."
)

# ---------------- HERO ----------------
st.markdown(
    """
    <div class="glass-card" style="text-align:center; padding: 40px 20px;">
        <div class="hub-pill">SCOPE 3 CARBON INTELLIGENCE</div>
        <h1 style="margin-top:14px; margin-bottom:6px;">Marcura Carbon Intelligence Platform</h1>
        <p style="color:#94a3b8; font-size:1.05rem; max-width:720px; margin:0 auto;">
            AI-powered operational intelligence for maritime logistics, procurement,
            supply chains, and Scope 3 emissions — unified across Singapore and Dubai.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.write("")

kpis = get_kpis(hub)
c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    kpi_card("Total Scope 3 (24mo)", f"{kpis['total_scope3']:,.0f} tCO₂e")
with c2:
    kpi_card("Procurement Spend", f"${kpis['procurement_spend']/1e6:,.1f}M")
with c3:
    kpi_card("Active Suppliers", f"{kpis['active_suppliers']:,}")
with c4:
    kpi_card("Active Shipments", f"{kpis['shipments']:,}")
with c5:
    kpi_card("Avg ESG Score", f"{kpis['esg_score']}")

st.write("")
st.write("")

st.markdown(f"### {hub} Hub — Port Network Preview")
ports = get_ports(hub)
st.map(ports.rename(columns={"lat": "latitude", "lon": "longitude"}), size=20, color="#22d3ee")

st.write("")
st.markdown(
    """
    <div class="glass-card">
        <b>Navigate using the sidebar pages:</b><br><br>
        📊 <b>Executive Dashboard</b> — KPIs, emissions trends, regional comparison, top suppliers/routes<br>
        🛰️ <b>Live Vessel Map</b> — MarineTraffic-style fleet tracking with vessel detail popups<br>
        🧮 <b>Scope 3 Calculator</b> — interactive shipment-level emissions estimator
    </div>
    """,
    unsafe_allow_html=True,
)

footer()
