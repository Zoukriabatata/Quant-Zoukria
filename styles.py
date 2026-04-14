"""
QuantMaster Design System — v2.0
Premium dark fintech UI (Tradytics-level) for all Streamlit pages.

Usage:
    from styles import inject
    inject()                        # Call after st.set_page_config()

Helper components (return HTML strings for st.markdown(..., unsafe_allow_html=True)):
    metric_card(value, label, delta=None, variant="neutral") → str
    section_header(icon, title, subtitle=None) → str
    badge(text, variant="blue") → str
    live_dot(color="green") → str
    divider() → str
"""
import streamlit as st
import streamlit.components.v1 as _stc

# ════════════════════════════════════════════════════════════════════════════
# DESIGN TOKENS (CSS custom properties)
# ════════════════════════════════════════════════════════════════════════════
_TOKENS = """
:root {
  /* Backgrounds — pure black */
  --bg-void:     #000000;
  --bg-base:     #050505;
  --bg-surface:  #0a0a0a;
  --bg-elevated: #111111;
  --bg-glass:    rgba(10,10,10,0.80);

  /* Accents */
  --accent-blue:   #3b82f6;
  --accent-cyan:   #06b6d4;
  --accent-green:  #10b981;
  --accent-red:    #ef4444;
  --accent-amber:  #f59e0b;
  --accent-purple: #8b5cf6;

  /* Gradients */
  --grad-primary: linear-gradient(135deg,#3b82f6 0%,#06b6d4 100%);
  --grad-green:   linear-gradient(135deg,#10b981 0%,#06b6d4 100%);
  --grad-red:     linear-gradient(135deg,#ef4444 0%,#f97316 100%);
  --grad-amber:   linear-gradient(135deg,#f59e0b 0%,#f97316 100%);
  --grad-surface: linear-gradient(145deg,rgba(59,130,246,0.05) 0%,rgba(6,182,212,0.02) 100%);
  --grad-glow:    radial-gradient(ellipse at top,rgba(59,130,246,0.12) 0%,transparent 60%);

  /* Text */
  --text-primary:   #f1f5f9;
  --text-secondary: #94a3b8;
  --text-muted:     #475569;

  /* Borders */
  --border-subtle:  rgba(148,163,184,0.06);
  --border-default: rgba(148,163,184,0.10);
  --border-active:  rgba(59,130,246,0.40);
  --border-glow:    rgba(59,130,246,0.20);

  /* Shadows */
  --shadow-card:  0 1px 3px rgba(0,0,0,0.4),0 4px 16px rgba(0,0,0,0.3);
  --shadow-glow:  0 0 20px rgba(59,130,246,0.15),0 0 60px rgba(59,130,246,0.05);
  --shadow-green: 0 0 20px rgba(16,185,129,0.15);
  --shadow-red:   0 0 20px rgba(239,68,68,0.15);

  /* Radius */
  --r-sm:  6px;
  --r-md:  10px;
  --r-lg:  16px;
  --r-xl:  20px;
  --r-pill: 999px;

  /* Transitions */
  --t-fast:   all .12s cubic-bezier(.16,1,.3,1);
  --t-normal: all .22s cubic-bezier(.16,1,.3,1);
  --t-slow:   all .40s cubic-bezier(.16,1,.3,1);
}
"""

# ════════════════════════════════════════════════════════════════════════════
# BASE — Body, app shell, layout
# ════════════════════════════════════════════════════════════════════════════
_BASE = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

html, body {
  background: var(--bg-void) !important;
  font-family: 'Inter','Space Grotesk',sans-serif !important;
  color: var(--text-primary) !important;
}

/* App container */
.stApp,
[data-testid="stAppViewContainer"] {
  background: var(--bg-void) !important;
}

/* Main content area */
.main .block-container,
[data-testid="stMainBlockContainer"] {
  padding: 1.8rem 2.2rem !important;
  max-width: 1440px !important;
}

/* Hide Streamlit chrome */
#MainMenu        { display: none !important; }
footer           { display: none !important; }
[data-testid="stToolbar"]     { display: none !important; }
[data-testid="stDecoration"]  { display: none !important; }
[data-testid="stHeader"]      { background: transparent !important; }

/* Sidebar — masquée par défaut, révélée par body.qm-open */
[data-testid="stSidebar"]        { display: none !important; }
[data-testid="collapsedControl"] { display: none !important; }
[data-testid="stSidebarCollapseButton"] { display: none !important; }
body.qm-open [data-testid="stSidebar"] { display: flex !important; }

/* Scrollbar */
::-webkit-scrollbar         { width: 4px; height: 4px; }
::-webkit-scrollbar-track   { background: transparent; }
::-webkit-scrollbar-thumb   { background: rgba(59,130,246,0.3); border-radius: var(--r-pill); }
::-webkit-scrollbar-thumb:hover { background: rgba(59,130,246,0.6); }
"""

# ════════════════════════════════════════════════════════════════════════════
# SIDEBAR — Premium navigation
# ════════════════════════════════════════════════════════════════════════════
_SIDEBAR = """
[data-testid="stSidebar"] {
  background: var(--bg-surface) !important;
  border-right: 1px solid var(--border-subtle) !important;
}
[data-testid="stSidebarContent"] { padding: 1rem 0.5rem; }

/* Nav links */
[data-testid="stSidebarNavLink"] {
  display: block !important;
  padding: 0.55rem 1rem !important;
  margin: 2px 4px !important;
  border-radius: var(--r-md) !important;
  font-family: 'Inter','Space Grotesk',sans-serif !important;
  font-size: 0.78rem !important;
  font-weight: 500 !important;
  letter-spacing: 0.02em !important;
  color: var(--text-muted) !important;
  text-decoration: none !important;
  border: 1px solid transparent !important;
  transition: var(--t-fast) !important;
  list-style: none !important;
}
[data-testid="stSidebarNavLink"]::before { display: none !important; }
[data-testid="stSidebarNavLink"] li       { list-style: none !important; }
[data-testid="stSidebarNavLink"]:hover {
  background: var(--bg-elevated) !important;
  color: var(--text-secondary) !important;
  border-color: var(--border-default) !important;
}
[data-testid="stSidebarNavLink"][aria-current="page"] {
  background: rgba(59,130,246,0.10) !important;
  color: var(--text-primary) !important;
  border-color: var(--border-active) !important;
  border-left: 3px solid var(--accent-blue) !important;
  padding-left: calc(1rem - 2px) !important;
}
[data-testid="stSidebarContent"] > div {
  animation: slideRight .22s cubic-bezier(.16,1,.3,1) both;
}
"""

# ════════════════════════════════════════════════════════════════════════════
# CARDS — Glassmorphism premium
# ════════════════════════════════════════════════════════════════════════════
_CARDS = """
/* ── New system card ──────────────────────────────────────── */
.qm-card {
  background: var(--bg-glass);
  backdrop-filter: blur(12px) saturate(180%);
  -webkit-backdrop-filter: blur(12px) saturate(180%);
  border: 1px solid var(--border-default);
  border-radius: var(--r-lg);
  box-shadow: var(--shadow-card);
  background-image: var(--grad-surface);
  transition: var(--t-normal);
  padding: 1.25rem 1.4rem;
}
.qm-card:hover {
  border-color: var(--border-active);
  box-shadow: var(--shadow-card), var(--shadow-glow);
  transform: translateY(-2px);
}

/* ── KPI / Metric card ─────────────────────────────────────── */
.qm-metric {
  position: relative;
  overflow: hidden;
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--r-lg);
  padding: 1.1rem 1.2rem 1rem;
  box-shadow: var(--shadow-card);
  transition: var(--t-normal);
}
.qm-metric::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 3px;
  background: var(--grad-primary);
  border-radius: var(--r-lg) var(--r-lg) 0 0;
}
.qm-metric--positive::before { background: var(--grad-green);   }
.qm-metric--negative::before { background: var(--grad-red);     }
.qm-metric--neutral::before  { background: var(--grad-primary); }
.qm-metric--amber::before    { background: var(--grad-amber);   }

.qm-metric:hover {
  border-color: var(--border-active);
  box-shadow: var(--shadow-card), var(--shadow-glow);
  transform: translateY(-2px);
}
.qm-metric__value {
  font-size: clamp(1.5rem,2.5vw,2.2rem);
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.02em;
  font-family: 'JetBrains Mono','Space Grotesk',monospace;
  line-height: 1.1;
  margin-bottom: 0.25rem;
}
.qm-metric__label {
  font-size: .68rem;
  font-weight: 600;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--text-muted);
}
.qm-metric__delta {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  margin-top: .35rem;
  font-size: .72rem;
  font-family: 'JetBrains Mono',monospace;
  padding: 2px 8px;
  border-radius: var(--r-pill);
}
.qm-metric__delta--up {
  background: rgba(16,185,129,0.12);
  color: #6ee7b7;
  border: 1px solid rgba(16,185,129,0.25);
}
.qm-metric__delta--down {
  background: rgba(239,68,68,0.12);
  color: #fca5a5;
  border: 1px solid rgba(239,68,68,0.25);
}

/* ── Backward compat: old kpi-card ─────────────────────────── */
.kpi-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--r-lg);
  padding: 1rem 1.2rem;
  text-align: center;
  transition: var(--t-normal);
  box-shadow: var(--shadow-card);
}
.kpi-card:hover {
  border-color: var(--border-active) !important;
  transform: translateY(-2px) !important;
  box-shadow: var(--shadow-card), var(--shadow-glow) !important;
}
.kpi-value { font-size:1.9rem; font-weight:700; font-family:'JetBrains Mono',monospace; line-height:1.1; }
.kpi-label { font-size:.68rem; color:var(--text-muted); text-transform:uppercase; letter-spacing:.12em; margin-top:.35rem; }
"""

# ════════════════════════════════════════════════════════════════════════════
# BADGES & PILLS
# ════════════════════════════════════════════════════════════════════════════
_BADGES = """
.qm-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 10px;
  border-radius: var(--r-pill);
  font-size: .65rem;
  font-weight: 600;
  letter-spacing: .06em;
  text-transform: uppercase;
  border: 1px solid transparent;
  line-height: 1;
}
.qm-badge--blue   { background:rgba(59,130,246,0.12); color:#93c5fd; border-color:rgba(59,130,246,0.25); }
.qm-badge--green  { background:rgba(16,185,129,0.12); color:#6ee7b7; border-color:rgba(16,185,129,0.25); }
.qm-badge--red    { background:rgba(239,68,68,0.12);  color:#fca5a5; border-color:rgba(239,68,68,0.25);  }
.qm-badge--amber  { background:rgba(245,158,11,0.12); color:#fcd34d; border-color:rgba(245,158,11,0.25); }
.qm-badge--purple { background:rgba(139,92,246,0.12); color:#c4b5fd; border-color:rgba(139,92,246,0.25); }
.qm-badge--cyan   { background:rgba(6,182,212,0.12);  color:#67e8f9; border-color:rgba(6,182,212,0.25);  }
"""

# ════════════════════════════════════════════════════════════════════════════
# BUTTONS
# ════════════════════════════════════════════════════════════════════════════
_BUTTONS = """
/* Streamlit primary button override */
[data-testid="baseButton-primary"] {
  background: var(--grad-primary) !important;
  border: none !important;
  color: #fff !important;
  font-weight: 600 !important;
  border-radius: var(--r-pill) !important;
  box-shadow: 0 4px 14px rgba(59,130,246,0.30) !important;
  transition: var(--t-fast) !important;
}
[data-testid="baseButton-primary"]:hover {
  transform: translateY(-1px) !important;
  box-shadow: 0 6px 20px rgba(59,130,246,0.45) !important;
}
[data-testid="baseButton-primary"]:active { transform: translateY(0) !important; }

/* Secondary button */
[data-testid="baseButton-secondary"] {
  background: transparent !important;
  border: 1px solid var(--border-default) !important;
  color: var(--text-secondary) !important;
  border-radius: var(--r-md) !important;
  transition: var(--t-fast) !important;
}
[data-testid="baseButton-secondary"]:hover {
  border-color: var(--border-active) !important;
  color: var(--text-primary) !important;
  background: var(--bg-elevated) !important;
  transform: translateY(-1px) !important;
}

/* Custom class buttons */
.qm-btn-primary {
  display: inline-flex; align-items: center; gap: 6px;
  background: var(--grad-primary);
  border: none;
  color: #fff;
  font-weight: 600;
  font-size: .85rem;
  padding: 10px 20px;
  border-radius: var(--r-pill);
  cursor: pointer;
  transition: var(--t-fast);
  box-shadow: 0 4px 14px rgba(59,130,246,0.30);
  text-decoration: none;
}
.qm-btn-primary:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 20px rgba(59,130,246,0.45);
}
.qm-btn-primary:active { transform: translateY(0); }

.qm-btn-ghost {
  display: inline-flex; align-items: center; gap: 6px;
  background: transparent;
  border: 1px solid var(--border-default);
  color: var(--text-secondary);
  font-size: .85rem;
  padding: 9px 18px;
  border-radius: var(--r-md);
  cursor: pointer;
  transition: var(--t-fast);
  text-decoration: none;
}
.qm-btn-ghost:hover {
  border-color: var(--border-active);
  color: var(--text-primary);
  background: var(--bg-elevated);
}
"""

# ════════════════════════════════════════════════════════════════════════════
# TABLES
# ════════════════════════════════════════════════════════════════════════════
_TABLES = """
/* Streamlit DataFrame override */
[data-testid="stDataFrame"] {
  border-radius: var(--r-lg) !important;
  border: 1px solid var(--border-default) !important;
  overflow: hidden !important;
  animation: fadeIn .25s ease both;
}
[data-testid="stDataFrame"] table {
  border-collapse: separate !important;
  border-spacing: 0 !important;
}
[data-testid="stDataFrame"] thead th {
  background: var(--bg-elevated) !important;
  color: var(--text-muted) !important;
  font-size: .65rem !important;
  font-weight: 600 !important;
  letter-spacing: .08em !important;
  text-transform: uppercase !important;
  border-bottom: 1px solid var(--border-default) !important;
  padding: 10px 14px !important;
}
[data-testid="stDataFrame"] tbody tr {
  border-bottom: 1px solid var(--border-subtle) !important;
  transition: var(--t-fast) !important;
}
[data-testid="stDataFrame"] tbody tr:hover {
  background: var(--bg-elevated) !important;
}
[data-testid="stDataFrame"] tbody td {
  padding: 8px 14px !important;
  color: var(--text-secondary) !important;
  font-size: .82rem !important;
  border: none !important;
}
"""

# ════════════════════════════════════════════════════════════════════════════
# INPUTS & FORM CONTROLS
# ════════════════════════════════════════════════════════════════════════════
_INPUTS = """
/* Text / number inputs */
[data-testid="stTextInput"] > div > div,
[data-testid="stNumberInput"] > div > div,
[data-testid="stTextArea"] > div > div,
[data-testid="stSelectbox"] > div > div,
[data-testid="stMultiSelect"] > div {
  background: var(--bg-elevated) !important;
  border: 1px solid var(--border-default) !important;
  border-radius: var(--r-md) !important;
  color: var(--text-primary) !important;
  transition: var(--t-fast) !important;
}
[data-testid="stTextInput"] > div > div:focus-within,
[data-testid="stNumberInput"] > div > div:focus-within,
[data-testid="stTextArea"] > div > div:focus-within {
  border-color: var(--accent-blue) !important;
  box-shadow: 0 0 0 3px rgba(59,130,246,0.12) !important;
}
[data-testid="stSelectbox"] > div > div:focus-within {
  border-color: var(--accent-blue) !important;
  box-shadow: 0 0 0 3px rgba(59,130,246,0.12) !important;
}

/* Slider track */
[data-testid="stSlider"] > div > div > div {
  background: var(--bg-elevated) !important;
}
[data-testid="stSlider"] > div > div > div > div {
  background: var(--grad-primary) !important;
}
"""

# ════════════════════════════════════════════════════════════════════════════
# TABS — Premium pill tabs
# ════════════════════════════════════════════════════════════════════════════
_TABS = """
/* Tab container */
.stTabs [data-baseweb="tab-list"] {
  background: var(--bg-surface) !important;
  border-radius: var(--r-lg) !important;
  padding: 4px !important;
  gap: 2px !important;
  border: 1px solid var(--border-subtle) !important;
}
/* Individual tab */
.stTabs [data-baseweb="tab"] {
  border-radius: var(--r-md) !important;
  color: var(--text-muted) !important;
  font-weight: 500 !important;
  font-size: .82rem !important;
  padding: 0.45rem 1rem !important;
  transition: var(--t-fast) !important;
  background: transparent !important;
  border: none !important;
}
.stTabs [data-baseweb="tab"]:hover:not([aria-selected="true"]) {
  background: var(--bg-elevated) !important;
  color: var(--text-secondary) !important;
}
/* Active tab */
.stTabs [data-baseweb="tab"][aria-selected="true"] {
  background: var(--grad-primary) !important;
  color: #fff !important;
  box-shadow: 0 2px 8px rgba(59,130,246,0.30) !important;
}
/* Tab content entrance */
[data-testid="stTabsContent"] > div {
  animation: fadeUp .18s cubic-bezier(.16,1,.3,1) both;
}
/* Tab border override */
.stTabs [data-baseweb="tab-border"] { display: none !important; }
"""

# ════════════════════════════════════════════════════════════════════════════
# EXPANDERS
# ════════════════════════════════════════════════════════════════════════════
_EXPANDERS = """
[data-testid="stExpander"] {
  background: var(--bg-surface) !important;
  border: 1px solid var(--border-default) !important;
  border-radius: var(--r-md) !important;
  overflow: hidden !important;
  transition: var(--t-fast) !important;
}
[data-testid="stExpander"]:hover {
  border-color: var(--border-active) !important;
}
[data-testid="stExpander"] summary,
.streamlit-expanderHeader {
  background: var(--bg-surface) !important;
  color: var(--text-secondary) !important;
  font-weight: 500 !important;
  transition: var(--t-fast) !important;
  border-radius: var(--r-md) !important;
}
[data-testid="stExpander"] summary:hover,
.streamlit-expanderHeader:hover {
  background: var(--bg-elevated) !important;
  color: var(--text-primary) !important;
}
"""

# ════════════════════════════════════════════════════════════════════════════
# METRICS (Streamlit native)
# ════════════════════════════════════════════════════════════════════════════
_METRICS = """
[data-testid="metric-container"] {
  background: var(--bg-surface) !important;
  border: 1px solid var(--border-default) !important;
  border-radius: var(--r-lg) !important;
  padding: 1rem 1.2rem !important;
  transition: var(--t-normal) !important;
  box-shadow: var(--shadow-card) !important;
}
[data-testid="metric-container"]:hover {
  border-color: var(--border-active) !important;
  box-shadow: var(--shadow-card), var(--shadow-glow) !important;
}
[data-testid="stMetricValue"] {
  font-family: 'JetBrains Mono',monospace !important;
  color: var(--text-primary) !important;
}
[data-testid="stMetricLabel"] {
  color: var(--text-muted) !important;
  font-size: .68rem !important;
  font-weight: 600 !important;
  letter-spacing: .08em !important;
  text-transform: uppercase !important;
}
[data-testid="stMetricDelta"] { font-family: 'JetBrains Mono',monospace !important; }
[data-testid="stMetric"] { animation: fadeUp .2s ease both; }
"""

# ════════════════════════════════════════════════════════════════════════════
# SECTION HEADERS, DIVIDERS
# ════════════════════════════════════════════════════════════════════════════
_LAYOUT = """
/* Section header */
.qm-section-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 1.4rem;
  padding-bottom: .75rem;
  border-bottom: 1px solid var(--border-subtle);
}
.qm-section-icon {
  width: 36px;
  height: 36px;
  background: rgba(59,130,246,0.10);
  border: 1px solid var(--border-active);
  border-radius: var(--r-md);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.05rem;
  flex-shrink: 0;
}
.qm-section-title {
  font-size: 1.05rem;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.2;
}
.qm-section-subtitle {
  font-size: .72rem;
  color: var(--text-muted);
  margin-top: 2px;
}

/* Divider */
.qm-divider {
  height: 1px;
  background: var(--border-subtle);
  margin: 1.5rem 0;
  border: none;
}

/* Live dot pulse */
.qm-live-dot {
  display: inline-block;
  width: 8px; height: 8px;
  border-radius: 50%;
  margin-right: 5px;
  vertical-align: middle;
  flex-shrink: 0;
}
.qm-live-dot--green  { background: var(--accent-green);  animation: pulseDot 1.6s ease-in-out infinite; }
.qm-live-dot--blue   { background: var(--accent-blue);   animation: pulseDot 1.6s ease-in-out infinite; }
.qm-live-dot--red    { background: var(--accent-red);    animation: pulseDot 1.6s ease-in-out infinite; }
.qm-live-dot--amber  { background: var(--accent-amber);  animation: pulseDot 2.0s ease-in-out infinite; }
"""

# ════════════════════════════════════════════════════════════════════════════
# CHARTS
# ════════════════════════════════════════════════════════════════════════════
_CHARTS = """
[data-testid="stPlotlyChart"] {
  animation: fadeIn .28s ease .05s both;
  border-radius: var(--r-lg) !important;
  overflow: hidden !important;
  border: 1px solid var(--border-subtle) !important;
  transition: border-color .22s ease, box-shadow .22s ease !important;
}
[data-testid="stPlotlyChart"]:hover {
  border-color: var(--border-default) !important;
  box-shadow: 0 0 24px rgba(59,130,246,0.08) !important;
}
/* Crosshair cursor on chart canvas */
[data-testid="stPlotlyChart"] canvas,
[data-testid="stPlotlyChart"] .js-plotly-plot {
  cursor: crosshair !important;
}
"""

# ════════════════════════════════════════════════════════════════════════════
# BACKWARD COMPAT — old class names re-styled with new tokens
# ════════════════════════════════════════════════════════════════════════════
_COMPAT = """
/* Old stat-row / stat-cell (Journal, Session Prep) */
.stat-row {
  display: flex;
  gap: 0;
  border: 1px solid var(--border-default);
  border-radius: var(--r-lg);
  overflow: hidden;
  margin: .5rem 0 1.2rem;
  box-shadow: var(--shadow-card);
}
.stat-cell {
  flex: 1;
  padding: 1rem .8rem;
  text-align: center;
  border-right: 1px solid var(--border-subtle);
  background: var(--bg-surface);
  transition: var(--t-fast) !important;
}
.stat-cell:last-child { border-right: none; }
.stat-cell:hover { background: var(--bg-elevated) !important; }
.stat-num {
  font-size: 1.4rem;
  font-weight: 700;
  font-family: 'JetBrains Mono',monospace;
  color: var(--text-primary);
}
.stat-lbl {
  font-size: .55rem;
  color: var(--text-muted);
  letter-spacing: .14em;
  text-transform: uppercase;
  margin-top: .2rem;
}

/* Old section-lbl (Backtest) */
.section-lbl, .sec-label {
  font-family: 'JetBrains Mono',monospace;
  font-size: .62rem;
  font-weight: 700;
  letter-spacing: .18em;
  color: var(--accent-cyan);
  text-transform: uppercase;
  margin: 1.4rem 0 .6rem;
  padding-bottom: .4rem;
  border-bottom: 1px solid var(--border-subtle);
}

/* Old gauge-track / gauge-fill / bar fills */
.gauge-track {
  background: var(--bg-elevated);
  border-radius: var(--r-pill);
  height: 5px;
  overflow: hidden;
  margin: 4px 0 8px;
}
.gauge-fill {
  height: 100%;
  border-radius: var(--r-pill);
  transition: width .4s cubic-bezier(.16,1,.3,1) !important;
}
.bar-fill, .bar-fill-teal, .bar-fill-dd {
  transition: width .6s cubic-bezier(.16,1,.3,1) !important;
}

/* Old ctx-box (Live Signal) */
.ctx-box {
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--r-lg);
  padding: 1.1rem 1.4rem;
  transition: var(--t-normal);
}
.ctx-box:hover { border-color: var(--border-active); }

/* Old sig-long / sig-short / sig-none (Live Signal) */
.sig-long {
  background: linear-gradient(135deg,rgba(16,185,129,0.06),rgba(16,185,129,0.03));
  border: 1.5px solid rgba(16,185,129,0.35);
  border-radius: var(--r-lg);
  padding: 1.4rem 1.6rem;
  box-shadow: var(--shadow-green);
  animation: pulseGlow--green 3s ease-in-out infinite;
}
.sig-short {
  background: linear-gradient(135deg,rgba(239,68,68,0.06),rgba(239,68,68,0.03));
  border: 1.5px solid rgba(239,68,68,0.35);
  border-radius: var(--r-lg);
  padding: 1.4rem 1.6rem;
  box-shadow: var(--shadow-red);
  animation: pulseGlow--red 3s ease-in-out infinite;
}
.sig-none {
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--r-lg);
  padding: 1.4rem 1.6rem;
  color: var(--text-muted);
  text-align: center;
}

/* Old lec-card, rule-card, check-item, mindset-card, card */
.lec-card, .rule-card, .card {
  transition: border-color .15s ease, transform .12s ease !important;
}
.lec-card:hover, .rule-card:hover, .card:hover {
  transform: translateY(-2px) !important;
  border-color: var(--border-active) !important;
}
.check-item {
  transition: border-color .15s ease, background .15s ease, transform .1s ease !important;
}
.check-item:hover { transform: translateX(2px) !important; }
.mindset-card {
  transition: border-color .2s ease, transform .12s ease !important;
}
.mindset-card:hover {
  border-color: var(--accent-cyan) !important;
  transform: translateX(2px) !important;
}

/* Old trade-row (Journal) */
.trade-row {
  padding: .5rem .8rem;
  border: 1px solid var(--border-subtle);
  border-radius: var(--r-md);
  margin: 3px 0;
  display: flex;
  gap: 1rem;
  align-items: center;
  font-family: 'JetBrains Mono',monospace;
  font-size: .78rem;
  background: var(--bg-surface);
  transition: var(--t-fast);
}
.trade-row:hover { background: var(--bg-elevated); }
.trade-row.win  { border-left: 3px solid var(--accent-green); }
.trade-row.loss { border-left: 3px solid var(--accent-red);   }

/* Old ph / ph-tag / ph-title headers */
.ph {
  padding: .9rem 0 .7rem;
  border-bottom: 1px solid var(--border-subtle);
  margin-bottom: 1.4rem;
}
.ph-tag {
  font-family: 'JetBrains Mono',monospace;
  font-size: .6rem;
  letter-spacing: .2em;
  color: var(--accent-cyan);
  text-transform: uppercase;
}
.ph-title {
  font-size: 1.7rem;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -.02em;
  margin: .2rem 0 0;
}

/* Old progress-bar-wrap (Session Prep) */
.progress-bar-wrap, .prog-row, .prog-label, .prog-val, .prog-bar, .prog-fill {
  transition: var(--t-normal);
}
"""

# ════════════════════════════════════════════════════════════════════════════
# ANIMATIONS
# ════════════════════════════════════════════════════════════════════════════
_ANIMATIONS = """
@keyframes fadeUp {
  from { opacity:0; transform:translateY(14px); }
  to   { opacity:1; transform:translateY(0);    }
}
@keyframes fadeIn {
  from { opacity:0; }
  to   { opacity:1; }
}
@keyframes slideRight {
  from { opacity:0; transform:translateX(-12px); }
  to   { opacity:1; transform:translateX(0);     }
}
@keyframes shimmer {
  0%   { background-position: -200% center; }
  100% { background-position:  200% center; }
}
@keyframes pulseGlow {
  0%,100% { box-shadow: var(--shadow-card); }
  50%     { box-shadow: var(--shadow-card), var(--shadow-glow); }
}
@keyframes pulseGlow--green {
  0%,100% { box-shadow: var(--shadow-green); }
  50%     { box-shadow: var(--shadow-green), 0 0 40px rgba(16,185,129,0.2); }
}
@keyframes pulseGlow--red {
  0%,100% { box-shadow: var(--shadow-red); }
  50%     { box-shadow: var(--shadow-red), 0 0 40px rgba(239,68,68,0.2); }
}
@keyframes pulseDot {
  0%,100% { transform:scale(1);   opacity:1;   }
  50%     { transform:scale(1.5); opacity:.55; }
}
@keyframes pulse {
  0%,100% { opacity:1; box-shadow:0 0 0 0 rgba(16,185,129,.4); }
  50%     { opacity:.7; box-shadow:0 0 0 5px rgba(16,185,129,0); }
}

/* Utility animation classes */
.anim-fade-up  { animation: fadeUp  .35s cubic-bezier(.16,1,.3,1) both; }
.anim-fade-in  { animation: fadeIn  .25s ease both; }
.anim-stagger-1 { animation-delay: .05s; }
.anim-stagger-2 { animation-delay: .10s; }
.anim-stagger-3 { animation-delay: .15s; }
.anim-stagger-4 { animation-delay: .20s; }
.anim-stagger-5 { animation-delay: .25s; }

/* Page entrance */
.main { animation: fadeIn .22s ease both; }

@keyframes skeletonShimmer {
  0%   { background-position: 200% center; }
  100% { background-position: -200% center; }
}
@keyframes toastSlide {
  from { opacity:0; transform:translateX(32px) scale(.95); }
  to   { opacity:1; transform:translateX(0)    scale(1);   }
}
@keyframes signalFlash {
  0%   { background-color: rgba(59,130,246,0.18); }
  50%  { background-color: rgba(59,130,246,0.06); }
  100% { background-color: rgba(59,130,246,0.18); }
}
@keyframes borderSpin {
  from { --_angle: 0deg;   }
  to   { --_angle: 360deg; }
}
@keyframes progressShrink {
  from { transform: scaleX(1); }
  to   { transform: scaleX(0); }
}
@keyframes checkPop {
  0%   { transform: scale(1);    }
  50%  { transform: scale(1.12); }
  100% { transform: scale(1);    }
}
"""

# ════════════════════════════════════════════════════════════════════════════
# ADVANCED — Skeleton, Toast, Empty State, Refresh Bar, Signal Flash,
#            Spinning-border card, Checkbox micro-animation
# ════════════════════════════════════════════════════════════════════════════
_ADVANCED = """
/* ── Skeleton loader ─────────────────────────────────────────── */
.qm-skeleton {
  border-radius: var(--r-md);
  background: linear-gradient(
    90deg,
    var(--bg-elevated) 25%,
    rgba(148,163,184,0.06) 50%,
    var(--bg-elevated) 75%
  );
  background-size: 200% 100%;
  animation: skeletonShimmer 1.6s ease-in-out infinite;
}
.qm-skeleton--text  { height: 12px; width: 100%; margin-bottom: 8px; }
.qm-skeleton--title { height: 20px; width: 60%; margin-bottom: 12px; }
.qm-skeleton--chart { height: 200px; width: 100%; }
.qm-skeleton--card  { height: 90px;  width: 100%; }

/* ── Toast notification ──────────────────────────────────────── */
.qm-toast {
  position: fixed;
  bottom: 1.5rem;
  right: 1.5rem;
  z-index: 9999;
  min-width: 260px;
  max-width: 360px;
  padding: .85rem 1.1rem;
  border-radius: var(--r-lg);
  background: var(--bg-elevated);
  border: 1px solid var(--border-default);
  box-shadow: 0 8px 32px rgba(0,0,0,0.5), var(--shadow-glow);
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: .82rem;
  font-weight: 500;
  color: var(--text-primary);
  animation: toastSlide .28s cubic-bezier(.16,1,.3,1) both;
}
.qm-toast--success { border-color: rgba(16,185,129,0.35);  box-shadow: 0 8px 32px rgba(0,0,0,0.5), var(--shadow-green); }
.qm-toast--error   { border-color: rgba(239,68,68,0.35);   box-shadow: 0 8px 32px rgba(0,0,0,0.5), var(--shadow-red);   }
.qm-toast--info    { border-color: rgba(59,130,246,0.35);  }
.qm-toast__icon    { font-size: 1.15rem; flex-shrink: 0; }

/* ── Empty state ─────────────────────────────────────────────── */
.qm-empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 3rem 2rem;
  border: 1px dashed var(--border-default);
  border-radius: var(--r-lg);
  background: var(--bg-surface);
  text-align: center;
  animation: fadeIn .3s ease both;
}
.qm-empty-state__icon { font-size: 2.4rem; opacity: .45; }
.qm-empty-state__title {
  font-size: .95rem;
  font-weight: 600;
  color: var(--text-secondary);
}
.qm-empty-state__sub {
  font-size: .78rem;
  color: var(--text-muted);
  max-width: 320px;
}

/* ── Refresh countdown bar ───────────────────────────────────── */
.qm-refresh-bar-wrap {
  width: 100%;
  height: 3px;
  background: var(--bg-elevated);
  border-radius: var(--r-pill);
  overflow: hidden;
  margin: .5rem 0;
}
.qm-refresh-bar {
  height: 100%;
  border-radius: var(--r-pill);
  background: var(--grad-primary);
  animation: progressShrink linear both;
  transform-origin: left center;
}

/* ── Signal flash (new signal detected) ─────────────────────── */
.qm-signal-new {
  animation: signalFlash .7s ease 3;
}

/* @property for conic-gradient rotation (Chrome 85+, Safari 16.4+) */
@property --_angle {
  syntax: '<angle>';
  initial-value: 0deg;
  inherits: false;
}

/* ── Animated conic border card ──────────────────────────────── */
.qm-card--border-spin {
  position: relative;
  background: var(--bg-surface);
  border-radius: var(--r-lg);
  padding: 1.25rem 1.4rem;
  overflow: hidden;
  isolation: isolate;
}
.qm-card--border-spin::before {
  content: '';
  position: absolute;
  inset: -2px;
  border-radius: inherit;
  background: conic-gradient(
    from var(--_angle, 0deg),
    var(--accent-blue),
    var(--accent-cyan),
    var(--accent-purple),
    var(--accent-blue)
  );
  animation: borderSpin 3s linear infinite;
  z-index: -1;
}
.qm-card--border-spin::after {
  content: '';
  position: absolute;
  inset: 1px;
  border-radius: calc(var(--r-lg) - 2px);
  background: var(--bg-surface);
  z-index: -1;
}

/* ── Checkbox micro-animation ────────────────────────────────── */
[data-testid="stCheckbox"] label:has(input:checked) {
  animation: checkPop .18s cubic-bezier(.16,1,.3,1) both;
}
[data-testid="stCheckbox"]:hover label {
  color: var(--text-primary) !important;
  transform: translateX(2px);
  transition: var(--t-fast);
}
"""

# ════════════════════════════════════════════════════════════════════════════
# FONT IMPORT
# ════════════════════════════════════════════════════════════════════════════
_FONT_LINK = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
    'family=Inter:wght@300;400;500;600;700'
    '&family=Space+Grotesk:wght@300;400;500;600;700'
    '&family=JetBrains+Mono:wght@400;500;700'
    '&display=swap">'
)


# ════════════════════════════════════════════════════════════════════════════
# inject() — public API
# ════════════════════════════════════════════════════════════════════════════
_HAMBURGER = """
<div id="qm-ham"><span></span><span></span><span></span></div>
<style>
#qm-ham{position:fixed;top:.65rem;left:.65rem;z-index:999999;
  width:2.4rem;height:2.4rem;background:#0a0a0a;border:1px solid #1e2433;
  border-radius:8px;display:flex;flex-direction:column;align-items:center;
  justify-content:center;gap:5px;cursor:pointer;padding:.55rem;
  transition:border-color .15s,box-shadow .15s;}
#qm-ham:hover{border-color:#3b82f6;box-shadow:0 0 0 3px rgba(59,130,246,.15);}
#qm-ham span{display:block;width:16px;height:2px;background:#94a3b8;
  border-radius:2px;}
</style>
"""

_HAMBURGER_JS = """
<script>
(function() {
  var p = window.parent.document;
  function init() {
    var btn = p.getElementById('qm-ham');
    if (!btn) { setTimeout(init, 50); return; }
    btn.addEventListener('click', function(e) {
      e.stopPropagation();
      p.body.classList.toggle('qm-open');
    });
    p.addEventListener('click', function(e) {
      if (!p.body.classList.contains('qm-open')) return;
      var sidebar = p.querySelector('[data-testid="stSidebar"]');
      var ham = p.getElementById('qm-ham');
      if (sidebar && !sidebar.contains(e.target) && !ham.contains(e.target)) {
        p.body.classList.remove('qm-open');
      }
    });
    p.addEventListener('keydown', function(e) {
      if (e.key === 'Escape') p.body.classList.remove('qm-open');
    });
  }
  init();
})();
</script>
"""


def inject():
    """Inject fonts + full design system CSS into the current Streamlit page.
    Call after st.set_page_config(), before page-specific CSS."""
    st.markdown(_FONT_LINK, unsafe_allow_html=True)
    css = (
        _TOKENS + _BASE + _SIDEBAR + _CARDS + _BADGES + _BUTTONS
        + _TABLES + _INPUTS + _TABS + _EXPANDERS + _METRICS
        + _LAYOUT + _CHARTS + _COMPAT + _ANIMATIONS + _ADVANCED
    )
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    # Sidebar peuplée avec st.page_link() — routing Streamlit natif (pas de rechargement)
    with st.sidebar:
        st.markdown('<div style="font-family:\'JetBrains Mono\',monospace;font-size:.58rem;letter-spacing:.2em;color:#3b82f6;padding:.4rem 0 .8rem;border-bottom:1px solid #1e2433;margin-bottom:.4rem;">⚡ QUANT MATHS</div>', unsafe_allow_html=True)
        st.page_link("Accueil.py",              label="⚡ Accueil",       use_container_width=True)
        st.page_link("pages/7_Etude.py",        label="🎓 Étude",         use_container_width=True)
        st.page_link("pages/5_Backtest.py",     label="📊 Backtest",      use_container_width=True)
        st.page_link("pages/3_Live_Signal.py",  label="📡 Live Signal",   use_container_width=True)
        st.page_link("pages/4_Journal.py",      label="📒 Journal",       use_container_width=True)
        st.page_link("pages/2_Session_Prep.py", label="🕐 Session Prep",  use_container_width=True)
        st.page_link("pages/6_Multi_Model.py",  label="🤖 Multi-Model",   use_container_width=True)
        st.page_link("pages/8_Library.py",      label="📚 Bibliothèque",  use_container_width=True)
        st.page_link("pages/9_BTC_DCA.py",      label="🪙 BTC DCA",       use_container_width=True)
        st.page_link("pages/1_Demarrage.py",    label="🔌 Démarrage",     use_container_width=True)
    st.markdown(_HAMBURGER, unsafe_allow_html=True)
    _stc.html(_HAMBURGER_JS, height=0)


# ════════════════════════════════════════════════════════════════════════════
# PYTHON HELPER COMPONENTS
# ════════════════════════════════════════════════════════════════════════════

def metric_card(
    value: str,
    label: str,
    delta: str | None = None,
    variant: str = "neutral",
    width: str = "100%",
) -> str:
    """Return a .qm-metric HTML block ready for st.markdown(..., unsafe_allow_html=True).

    Args:
        value:   Main displayed value — e.g. "2.03", "$+1 580", "29.4%"
        label:   Uppercase label below value
        delta:   Optional delta string — e.g. "+2.3%" or "-$120"
        variant: "positive" | "negative" | "neutral" | "amber"
        width:   CSS width string (default "100%")
    """
    delta_html = ""
    if delta is not None:
        is_up = not delta.startswith("-")
        cls = "up" if is_up else "down"
        arrow = "▲" if is_up else "▼"
        delta_html = (
            f'<div class="qm-metric__delta qm-metric__delta--{cls}">'
            f'{arrow} {delta}</div>'
        )
    return (
        f'<div class="qm-metric qm-metric--{variant}" style="width:{width}">'
        f'  <div class="qm-metric__value">{value}</div>'
        f'  <div class="qm-metric__label">{label}</div>'
        f'  {delta_html}'
        f'</div>'
    )


def section_header(icon: str, title: str, subtitle: str | None = None) -> str:
    """Return a .qm-section-header HTML block.

    Args:
        icon:     Emoji or single char — e.g. "📈", "⚡", "⚙"
        title:    Section title text
        subtitle: Optional smaller description line
    """
    sub = (f'<div class="qm-section-subtitle">{subtitle}</div>'
           if subtitle else "")
    return (
        f'<div class="qm-section-header">'
        f'  <div class="qm-section-icon">{icon}</div>'
        f'  <div>'
        f'    <div class="qm-section-title">{title}</div>'
        f'    {sub}'
        f'  </div>'
        f'</div>'
    )


def badge(text: str, variant: str = "blue") -> str:
    """Return a .qm-badge HTML span.
    variant: "blue" | "green" | "red" | "amber" | "purple" | "cyan"
    """
    return f'<span class="qm-badge qm-badge--{variant}">{text}</span>'


def live_dot(color: str = "green") -> str:
    """Return a pulsing live dot HTML span.
    color: "green" | "blue" | "red" | "amber"
    """
    return f'<span class="qm-live-dot qm-live-dot--{color}"></span>'


def divider() -> str:
    """Return a .qm-divider HTML element."""
    return '<hr class="qm-divider">'


def gradient_text(text: str, gradient: str = "var(--grad-primary)") -> str:
    """Return text with CSS gradient fill."""
    return (
        f'<span style="background:{gradient};-webkit-background-clip:text;'
        f'-webkit-text-fill-color:transparent;background-clip:text">{text}</span>'
    )


def toast(message: str, variant: str = "info", icon: str | None = None) -> str:
    """Return a fixed-position toast notification HTML.
    variant: "info" | "success" | "error"
    Inject via st.markdown(..., unsafe_allow_html=True).
    """
    _icons = {"info": "ℹ️", "success": "✅", "error": "❌"}
    _icon = icon or _icons.get(variant, "ℹ️")
    return (
        f'<div class="qm-toast qm-toast--{variant}">'
        f'  <span class="qm-toast__icon">{_icon}</span>'
        f'  <span>{message}</span>'
        f'</div>'
    )


def skeleton(variant: str = "text", count: int = 1) -> str:
    """Return skeleton loader HTML.
    variant: "text" | "title" | "chart" | "card"
    count: number of skeleton rows (ignored for chart/card).
    """
    if variant in ("chart", "card"):
        return f'<div class="qm-skeleton qm-skeleton--{variant}"></div>'
    rows = "".join(
        f'<div class="qm-skeleton qm-skeleton--{variant}" '
        f'style="width:{100 - (i * 12) % 35}%"></div>'
        for i in range(count)
    )
    return rows


def empty_state(
    icon: str = "📭",
    title: str = "Aucune donnée",
    subtitle: str = "Rien à afficher pour le moment.",
) -> str:
    """Return a centered empty-state HTML block."""
    return (
        f'<div class="qm-empty-state">'
        f'  <div class="qm-empty-state__icon">{icon}</div>'
        f'  <div class="qm-empty-state__title">{title}</div>'
        f'  <div class="qm-empty-state__sub">{subtitle}</div>'
        f'</div>'
    )


def refresh_bar(duration_s: float = 2.0) -> str:
    """Return a top-of-card countdown progress bar.
    duration_s: matches the autorefresh interval in seconds.
    """
    return (
        f'<div class="qm-refresh-bar-wrap">'
        f'  <div class="qm-refresh-bar" '
        f'style="animation-duration:{duration_s}s"></div>'
        f'</div>'
    )


def count_up_stats(stats: list[dict], height: int = 110) -> str:
    """Inject an animated count-up stat row via JS.

    Each stat dict keys:
      value    (number)  — final value to animate to
      label    (str)     — uppercase label below
      prefix   (str)     — e.g. "$", "+" — prepended as-is (not animated)
      suffix   (str)     — e.g. "%", "x"
      decimals (int)     — decimal places (default 0)
      color    (str)     — CSS color for the number (default "#06b6d4")
      sub      (str)     — tiny sub-label line (optional)
      static   (bool)    — if True skip animation, show value as-is (for "—" etc)

    Returns an HTML+JS string.
    Usage: st.components.v1.html(count_up_stats([...]), height=110)
    """
    import json as _json
    data_json = _json.dumps(stats)
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ background:transparent; font-family:'Inter',sans-serif; }}
  .cu-row {{
    display:flex; gap:0;
    border:1px solid rgba(148,163,184,0.10);
    border-radius:16px; overflow:hidden;
  }}
  .cu-cell {{
    flex:1; padding:1rem .6rem; text-align:center;
    border-right:1px solid rgba(148,163,184,0.06);
    background:rgba(10,10,10,0.85);
    transition:background .15s ease;
  }}
  .cu-cell:last-child {{ border-right:none; }}
  .cu-cell:hover {{ background:rgba(20,20,20,0.95); }}
  .cu-num {{
    font-size:1.5rem; font-weight:700;
    font-family:'JetBrains Mono',monospace;
    letter-spacing:-0.02em; line-height:1.1;
  }}
  .cu-lbl {{
    font-size:.52rem; color:#475569; letter-spacing:.14em;
    text-transform:uppercase; margin-top:.25rem;
  }}
  .cu-sub {{
    font-size:.5rem; color:#334155; letter-spacing:.1em;
    text-transform:uppercase; margin-top:.15rem;
  }}
</style>
</head><body>
<div class="cu-row" id="cu-row"></div>
<script>
(function() {{
  const stats = {data_json};
  const row = document.getElementById('cu-row');
  stats.forEach((s, i) => {{
    const cell = document.createElement('div');
    cell.className = 'cu-cell';
    const color = s.color || '#06b6d4';
    const sub = s.sub ? `<div class="cu-sub">${{s.sub}}</div>` : '';
    cell.innerHTML = `<div class="cu-num" id="cu-${{i}}" style="color:${{color}}">${{s.prefix||''}}0${{s.suffix||''}}</div>
                      <div class="cu-lbl">${{s.label}}</div>${{sub}}`;
    row.appendChild(cell);
  }});
  stats.forEach((s, i) => {{
    const el = document.getElementById('cu-' + i);
    if (s.static) {{
      el.textContent = (s.prefix||'') + s.value + (s.suffix||'');
      return;
    }}
    const dec = s.decimals || 0;
    const raw = parseFloat(String(s.value).replace(/[^0-9.\-]/g,'')) || 0;
    const sign = raw < 0 ? '-' : (s.prefix === '+' ? '+' : '');
    const target = Math.abs(raw);
    const duration = 900;
    const start = performance.now();
    const pfx = s.prefix && s.prefix !== '+' ? s.prefix : '';
    function step(now) {{
      const p = Math.min((now - start) / duration, 1);
      const ease = 1 - Math.pow(1 - p, 3);
      const cur = (target * ease).toFixed(dec);
      el.textContent = sign + pfx + cur + (s.suffix||'');
      if (p < 1) requestAnimationFrame(step);
    }}
    requestAnimationFrame(step);
  }});
}})();
</script>
</body></html>
"""
