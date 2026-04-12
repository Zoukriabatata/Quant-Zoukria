"""
Global design system — base CSS + transitions + animations shared across all pages.
Usage: from styles import inject; inject()
       Call AFTER st.set_page_config(), before your own page-specific CSS.
"""
import streamlit as st

# ══ Base — socle commun à toutes les pages ═══════════════════════════════
_BASE_CSS = """
*, *::before, *::after { box-sizing: border-box; }

[data-testid="stAppViewContainer"] {
    background: #060606 !important;
    font-family: 'Space Grotesk', sans-serif !important;
}
[data-testid="stSidebar"]  { background: #080808 !important; border-right: 1px solid #141414 !important; }
[data-testid="stHeader"]   { background: transparent !important; }
[data-testid="stToolbar"]  { display: none !important; }
.block-container           { padding-top: 1.2rem; }

::-webkit-scrollbar       { width: 4px; }
::-webkit-scrollbar-track { background: #0a0a0a; }
::-webkit-scrollbar-thumb { background: #3CC4B7; border-radius: 2px; }

[data-testid="stSidebarNavLink"] {
    display: block; padding: 0.55rem 1rem; margin: 2px 6px;
    border-radius: 6px; font-family: 'JetBrains Mono', monospace;
    font-size: 0.73rem; letter-spacing: 0.07em; color: #555 !important;
    text-decoration: none !important; border: 1px solid transparent;
}
[data-testid="stSidebarNavLink"]:hover {
    background: #111 !important; color: #bbb !important; border-color: #1a1a1a;
}
[data-testid="stSidebarNavLink"][aria-current="page"] {
    background: rgba(60,196,183,0.08) !important;
    color: #3CC4B7 !important; border-color: rgba(60,196,183,0.2);
}
"""

# ══ Keyframes ════════════════════════════════════════════════════════════
_CSS = """
@keyframes fadeUp {
    from { opacity:0; transform:translateY(10px); }
    to   { opacity:1; transform:translateY(0);    }
}
@keyframes fadeIn {
    from { opacity:0; }
    to   { opacity:1; }
}
@keyframes slideRight {
    from { opacity:0; transform:translateX(-8px); }
    to   { opacity:1; transform:translateX(0);    }
}
@keyframes pulseBorder {
    0%,100% { border-color:rgba(60,196,183,.2); }
    50%     { border-color:rgba(60,196,183,.6); }
}

/* ══ Page entrance ═══════════════════════════════════════════════════ */
.main { animation: fadeIn .22s ease both; }
[data-testid="stMainBlockContainer"] > div > div > div {
    animation: fadeUp .22s cubic-bezier(.16,1,.3,1) both;
}

/* ══ Tabs ════════════════════════════════════════════════════════════ */
[data-testid="stTabsContent"] > div {
    animation: fadeUp .18s cubic-bezier(.16,1,.3,1) both;
}
[data-baseweb="tab"]:not([aria-selected="true"]) {
    transition: color .15s ease, background .15s ease !important;
}
[data-baseweb="tab"]:not([aria-selected="true"]):hover {
    color: #aaa !important;
    background: rgba(255,255,255,.03) !important;
}
[data-baseweb="tab"][aria-selected="true"] {
    transition: color .15s ease !important;
}

/* ══ Charts & data ═══════════════════════════════════════════════════ */
[data-testid="stPlotlyChart"] {
    animation: fadeIn .3s ease .06s both;
    border-radius: 10px;
    overflow: hidden;
}
[data-testid="stDataFrame"] {
    animation: fadeIn .25s ease both;
}
[data-testid="stMetric"] {
    animation: fadeUp .2s ease both;
}

/* ══ Buttons ═════════════════════════════════════════════════════════ */
[data-testid="baseButton-primary"] {
    transition: transform .12s cubic-bezier(.16,1,.3,1),
                box-shadow .12s ease,
                background .12s ease !important;
    border-radius: 8px !important;
}
[data-testid="baseButton-primary"]:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 20px rgba(60,196,183,.3) !important;
}
[data-testid="baseButton-primary"]:active {
    transform: translateY(0) !important;
}
[data-testid="baseButton-secondary"] {
    transition: transform .12s ease, box-shadow .12s ease !important;
    border-radius: 8px !important;
}
[data-testid="baseButton-secondary"]:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 3px 10px rgba(0,0,0,.4) !important;
}

/* ══ Expander ════════════════════════════════════════════════════════ */
[data-testid="stExpander"] {
    border-radius: 10px !important;
    transition: border-color .15s ease !important;
    overflow: hidden;
}
[data-testid="stExpander"]:hover {
    border-color: #222 !important;
}
[data-testid="stExpander"] summary {
    transition: background .12s ease !important;
}
[data-testid="stExpander"] summary:hover {
    background: rgba(255,255,255,.02) !important;
}

/* ══ Cards (shared across pages) ═════════════════════════════════════ */
.kpi-card {
    transition: border-color .15s ease,
                transform .12s cubic-bezier(.16,1,.3,1),
                box-shadow .12s ease !important;
}
.kpi-card:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 4px 20px rgba(0,0,0,.5) !important;
    border-color: #2a2a2a !important;
}
.lec-card {
    transition: border-color .15s ease, transform .12s ease !important;
}
.lec-card:hover {
    transform: translateY(-1px) !important;
    border-color: #2a2a2a !important;
}
.rule-card {
    transition: border-color .15s ease, background .15s ease, transform .12s ease !important;
}
.rule-card:hover {
    transform: translateY(-1px) !important;
    border-color: #2a2a2a !important;
}
.check-item {
    transition: border-color .15s ease, background .15s ease, transform .1s ease !important;
}
.check-item:hover { transform: translateX(2px) !important; }
.card {
    transition: background .15s ease, transform .12s ease !important;
}
.card:hover { transform: translateY(-1px) !important; }
.stat-cell {
    transition: background .15s ease !important;
}
.mindset-card {
    transition: border-color .2s ease, transform .12s ease !important;
}
.mindset-card:hover {
    border-color: #5ad4cc !important;
    transform: translateX(2px) !important;
}

/* ══ Sidebar nav ═════════════════════════════════════════════════════ */
[data-testid="stSidebarNavLink"] {
    transition: background .12s ease,
                color .12s ease,
                border-color .12s ease !important;
}

/* ══ Inputs & selects ════════════════════════════════════════════════ */
[data-testid="stTextInput"] > div > div,
[data-testid="stNumberInput"] > div > div,
[data-testid="stSelectbox"] > div > div,
[data-testid="stTextArea"] > div > div {
    transition: border-color .15s ease !important;
}
[data-testid="stTextInput"] > div > div:focus-within,
[data-testid="stNumberInput"] > div > div:focus-within,
[data-testid="stTextArea"] > div > div:focus-within {
    border-color: rgba(60,196,183,.5) !important;
    box-shadow: 0 0 0 2px rgba(60,196,183,.08) !important;
}

/* ══ Spinner ══════════════════════════════════════════════════════════ */
[data-testid="stSpinner"] > div {
    animation: fadeIn .2s ease both;
}

/* ══ Sidebar entrance ════════════════════════════════════════════════ */
[data-testid="stSidebarContent"] > div {
    animation: slideRight .2s cubic-bezier(.16,1,.3,1) both;
}

/* ══ Progress bar ════════════════════════════════════════════════════ */
.bar-fill, .bar-fill-teal, .bar-fill-green {
    transition: width .6s cubic-bezier(.16,1,.3,1) !important;
}
.gauge-fill {
    transition: width .4s cubic-bezier(.16,1,.3,1) !important;
}
"""

_FONT_LINK = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
    'family=Space+Grotesk:wght@300;400;500;600;700'
    '&family=JetBrains+Mono:wght@400;500;700&display=swap">'
)

def inject():
    """Inject font + global base CSS + transitions into the current page."""
    st.markdown(_FONT_LINK, unsafe_allow_html=True)
    st.markdown(f"<style>{_BASE_CSS}{_CSS}</style>", unsafe_allow_html=True)
