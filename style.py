import streamlit as st

DISCLAIMER = (
    "Demonstration platform powered by synthetic data. Company names, transactions, "
    "emissions and operational events are fictional and are for demonstration purposes only."
)

PRIMARY = "#22d3ee"   # cyan
ACCENT = "#6366f1"    # indigo
BG = "#0b1220"
CARD_BG = "rgba(255,255,255,0.04)"


def inject_css():
    st.markdown(
        f"""
        <style>
        .stApp {{
            background: radial-gradient(circle at 10% 0%, #0f1b2d 0%, {BG} 55%) !important;
            color: #e5e7eb;
        }}
        section[data-testid="stSidebar"] {{
            background: #0a0f1c;
            border-right: 1px solid rgba(255,255,255,0.06);
        }}
        h1, h2, h3, h4 {{
            font-family: 'Inter', 'Segoe UI', sans-serif;
            letter-spacing: -0.01em;
        }}
        .glass-card {{
            background: {CARD_BG};
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 16px;
            padding: 18px 20px;
            backdrop-filter: blur(10px);
            box-shadow: 0 4px 30px rgba(0,0,0,0.25);
        }}
        .kpi-label {{
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: #94a3b8;
            margin-bottom: 4px;
        }}
        .kpi-value {{
            font-size: 1.6rem;
            font-weight: 700;
            color: #f8fafc;
        }}
        .kpi-delta-pos {{ color: #34d399; font-size: 0.85rem; }}
        .kpi-delta-neg {{ color: #f87171; font-size: 0.85rem; }}
        .hub-pill {{
            display:inline-block;
            padding: 4px 14px;
            border-radius: 999px;
            font-size: 0.75rem;
            font-weight: 600;
            letter-spacing: 0.04em;
            background: linear-gradient(90deg, {PRIMARY}, {ACCENT});
            color: #06131f;
        }}
        .footer-disclaimer {{
            margin-top: 40px;
            padding-top: 14px;
            border-top: 1px solid rgba(255,255,255,0.08);
            font-size: 0.72rem;
            color: #64748b;
            text-align: center;
        }}
        div[data-testid="stMetric"] {{
            background: {CARD_BG};
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 14px;
            padding: 12px 16px;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def hub_selector(default="Global"):
    if "hub" not in st.session_state:
        st.session_state.hub = default
    st.sidebar.markdown("### 🌐 Operational Hub")
    hub = st.sidebar.radio(
        "Select hub",
        ["Global", "Singapore", "Dubai"],
        index=["Global", "Singapore", "Dubai"].index(st.session_state.hub),
        label_visibility="collapsed",
    )
    st.session_state.hub = hub
    st.sidebar.markdown(f'<span class="hub-pill">{hub} HUB</span>', unsafe_allow_html=True)
    return hub


def footer():
    st.markdown(f'<div class="footer-disclaimer">{DISCLAIMER}</div>', unsafe_allow_html=True)


def kpi_card(label, value, delta=None, positive=True):
    delta_html = ""
    if delta is not None:
        cls = "kpi-delta-pos" if positive else "kpi-delta-neg"
        arrow = "▲" if positive else "▼"
        delta_html = f'<div class="{cls}">{arrow} {delta}</div>'
    st.markdown(
        f"""
        <div class="glass-card">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
            {delta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )
