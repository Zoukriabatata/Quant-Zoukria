import re
import json
import streamlit as st
from pathlib import Path
from charts import CHARTS, INLINE_CHARTS

PROGRESS_FILE = Path(__file__).parent.parent / ".progress.json"

def load_progress():
    try:
        return set(json.loads(PROGRESS_FILE.read_text()))
    except Exception:
        return set()

def save_progress(completed: set):
    try:
        PROGRESS_FILE.write_text(json.dumps(list(completed)))
    except Exception:
        pass

st.set_page_config(page_title="Quant Maths — Étude", page_icon="QM", layout="wide")

# ══════════════════════════════════════════════════════════════════════
# CSS — Design system complet
# ══════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:ital,wght@0,400;0,500;0,600;1,400&family=JetBrains+Mono:wght@400;500;700&display=swap');

/* ── Base ─────────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; }

[data-testid="stAppViewContainer"] {
    background: #060606;
    font-family: 'Inter', sans-serif;
}
[data-testid="stSidebar"] {
    background: #080808;
    border-right: 1px solid #141414;
}
[data-testid="stHeader"]  { background: transparent; }
[data-testid="stToolbar"] { display: none; }
.block-container          { padding-top: 1.5rem; max-width: 1100px; }

/* ── Scrollbar ────────────────────────────────────── */
::-webkit-scrollbar       { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: #0a0a0a; }
::-webkit-scrollbar-thumb { background: #3CC4B7; border-radius: 2px; }

/* ── Sidebar nav ──────────────────────────────────── */
[data-testid="stSidebarNavLink"] {
    display: block; padding: 0.5rem 1rem; margin: 1px 6px;
    border-radius: 6px; font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem; letter-spacing: 0.06em; color: #444 !important;
    text-decoration: none !important; transition: all 0.12s;
    border: 1px solid transparent;
}
[data-testid="stSidebarNavLink"]:hover {
    background: #111 !important; color: #aaa !important; border-color: #1a1a1a;
}
[data-testid="stSidebarNavLink"][aria-current="page"] {
    background: rgba(60,196,183,0.07) !important;
    color: #3CC4B7 !important; border-color: rgba(60,196,183,0.18);
}

/* ── Sidebar buttons ──────────────────────────────── */
section[data-testid="stSidebar"] .stButton > button {
    background: transparent; border: none; color: #444;
    font-family: 'JetBrains Mono', monospace; font-size: 0.72rem;
    text-align: left; padding: 0.4rem 0.6rem; border-radius: 5px;
    transition: all 0.12s; width: 100%;
}
section[data-testid="stSidebar"] .stButton > button:hover {
    background: #111; color: #bbb;
}

/* ── Typography — content ─────────────────────────── */
[data-testid="stMarkdownContainer"] {
    font-family: 'Inter', sans-serif;
    font-size: 0.95rem;
    line-height: 1.85;
    color: #bdbdbd;
}
[data-testid="stMarkdownContainer"] p {
    margin: 0.55rem 0;
    color: #c0c0c0;
}
[data-testid="stMarkdownContainer"] strong {
    color: #ffffff;
    font-weight: 600;
}
[data-testid="stMarkdownContainer"] em {
    color: #aaa;
    font-style: italic;
}

/* ── Headings ─────────────────────────────────────── */
[data-testid="stMarkdownContainer"] h1 {
    font-size: 1.5rem; font-weight: 700; color: #fff;
    letter-spacing: -0.02em; margin: 1.5rem 0 0.8rem;
}
[data-testid="stMarkdownContainer"] h2 {
    font-size: 1rem; font-weight: 600; color: #fff;
    border-left: 3px solid #3CC4B7;
    padding-left: 12px;
    margin: 2rem 0 0.7rem;
    letter-spacing: 0;
}
[data-testid="stMarkdownContainer"] h3 {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem; font-weight: 700;
    color: #3CC4B7; letter-spacing: 0.14em;
    text-transform: uppercase;
    margin: 1.5rem 0 0.5rem;
}
[data-testid="stMarkdownContainer"] h4 {
    font-size: 0.9rem; font-weight: 600; color: #ddd;
    margin: 1.2rem 0 0.4rem;
}

/* ── Blockquotes → callout ────────────────────────── */
[data-testid="stMarkdownContainer"] blockquote {
    background: rgba(60,196,183,0.04);
    border-left: 3px solid rgba(60,196,183,0.35);
    padding: 0.8rem 1.1rem;
    border-radius: 0 6px 6px 0;
    margin: 1rem 0;
    color: #888;
    font-size: 0.88rem;
    line-height: 1.7;
}
[data-testid="stMarkdownContainer"] blockquote a {
    color: #3CC4B7;
    text-decoration: none;
}
[data-testid="stMarkdownContainer"] blockquote a:hover {
    text-decoration: underline;
}
[data-testid="stMarkdownContainer"] blockquote strong {
    color: #ccc;
}

/* ── Code blocks — terminal style ────────────────── */
[data-testid="stMarkdownContainer"] pre {
    background: #080808 !important;
    border: 1px solid #1c1c1c !important;
    border-radius: 8px !important;
    margin: 0.8rem 0 !important;
    position: relative;
}
[data-testid="stMarkdownContainer"] pre::before {
    content: '';
    display: block;
    height: 0;
}
[data-testid="stMarkdownContainer"] pre code {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.8rem !important;
    line-height: 1.75 !important;
    color: #3CC4B7 !important;
    background: transparent !important;
    padding: 1rem 1.2rem !important;
    display: block;
    white-space: pre;
    overflow-x: auto;
}

/* ── Inline code ──────────────────────────────────── */
[data-testid="stMarkdownContainer"] code {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.82em;
    background: rgba(60,196,183,0.08);
    color: #5de0d3;
    padding: 1px 6px;
    border-radius: 4px;
    border: 1px solid rgba(60,196,183,0.12);
}
[data-testid="stMarkdownContainer"] pre code {
    border: none !important;
    padding: 0 !important;
}

/* ── Tables ───────────────────────────────────────── */
[data-testid="stMarkdownContainer"] table {
    border-collapse: collapse;
    width: 100%;
    margin: 1rem 0;
    font-size: 0.87rem;
    border-radius: 8px;
    overflow: hidden;
    border: 1px solid #1a1a1a;
}
[data-testid="stMarkdownContainer"] thead {
    background: #0d0d0d;
}
[data-testid="stMarkdownContainer"] th {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.68rem;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #3CC4B7;
    padding: 10px 14px;
    text-align: left;
    border-bottom: 1px solid #1a1a1a;
    font-weight: 700;
}
[data-testid="stMarkdownContainer"] td {
    padding: 9px 14px;
    color: #b8b8b8;
    border-bottom: 1px solid #0f0f0f;
    vertical-align: top;
}
[data-testid="stMarkdownContainer"] tr:last-child td { border-bottom: none; }
[data-testid="stMarkdownContainer"] tr:nth-child(even) td { background: rgba(255,255,255,0.01); }
[data-testid="stMarkdownContainer"] tbody tr:hover td { background: rgba(60,196,183,0.025); }

/* ── Lists ────────────────────────────────────────── */
[data-testid="stMarkdownContainer"] ul {
    padding-left: 1.4rem; margin: 0.5rem 0;
}
[data-testid="stMarkdownContainer"] ol {
    padding-left: 1.6rem; margin: 0.5rem 0;
}
[data-testid="stMarkdownContainer"] li {
    margin: 0.3rem 0; line-height: 1.75; color: #bbb;
}
[data-testid="stMarkdownContainer"] li::marker { color: #3CC4B7; }
[data-testid="stMarkdownContainer"] li strong  { color: #fff; }

/* ── Links ────────────────────────────────────────── */
[data-testid="stMarkdownContainer"] a {
    color: #3CC4B7; text-decoration: none;
}
[data-testid="stMarkdownContainer"] a:hover { text-decoration: underline; }

/* ── HR ───────────────────────────────────────────── */
[data-testid="stMarkdownContainer"] hr {
    border: none; border-top: 1px solid #141414; margin: 1.5rem 0;
}

/* ── LaTeX (KaTeX) ───────────────────────────────── */
[data-testid="stLatexContainer"] {
    display: flex;
    justify-content: center;
    padding: 1.2rem 2rem;
    background: rgba(60,196,183,0.025);
    border: 1px solid rgba(60,196,183,0.08);
    border-radius: 8px;
    margin: 1rem 0;
    overflow-x: auto;
}
[data-testid="stLatexContainer"] .katex {
    font-size: 1.15rem;
    color: #e8e8e8;
}
[data-testid="stLatexContainer"] .katex-display {
    margin: 0;
}

/* ── Tabs ─────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    gap: 2px;
    background: #0a0a0a;
    padding: 4px;
    border-radius: 10px;
    border: 1px solid #1a1a1a;
    margin-bottom: 0.5rem;
}
.stTabs [data-baseweb="tab"] {
    background: transparent;
    border-radius: 7px;
    padding: 8px 22px;
    color: #444;
    font-weight: 600;
    font-size: 0.72rem;
    letter-spacing: 0.1em;
    font-family: 'JetBrains Mono', monospace;
    border: 1px solid transparent;
    transition: all 0.12s;
    text-transform: uppercase;
}
.stTabs [data-baseweb="tab"]:hover {
    color: #888;
    background: rgba(255,255,255,0.03);
}
.stTabs [aria-selected="true"] {
    background: rgba(60,196,183,0.1) !important;
    color: #3CC4B7 !important;
    border-color: rgba(60,196,183,0.2) !important;
}
.stTabs [data-baseweb="tab-highlight"] { display: none; }
.stTabs [data-baseweb="tab-border"]    { display: none; }

/* ── Input fields ─────────────────────────────────── */
[data-testid="stNumberInput"] input,
[data-testid="stTextInput"]   input {
    background: #0d0d0d !important;
    border: 1px solid #222 !important;
    color: #ccc !important;
    border-radius: 6px !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.88rem !important;
}
[data-testid="stNumberInput"] input:focus,
[data-testid="stTextInput"]   input:focus {
    border-color: rgba(60,196,183,0.4) !important;
    box-shadow: 0 0 0 2px rgba(60,196,183,0.08) !important;
}

/* ── Buttons ──────────────────────────────────────── */
.stButton > button[kind="primary"] {
    background: rgba(60,196,183,0.15);
    border: 1px solid rgba(60,196,183,0.35);
    color: #3CC4B7;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem;
    letter-spacing: 0.08em;
    border-radius: 6px;
    transition: all 0.12s;
}
.stButton > button[kind="primary"]:hover {
    background: rgba(60,196,183,0.25);
    border-color: rgba(60,196,183,0.5);
}
.stButton > button[kind="secondary"] {
    background: transparent;
    border: 1px solid #222;
    color: #555;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    border-radius: 6px;
}
.stButton > button[kind="secondary"]:hover {
    border-color: #333; color: #888;
}

/* ── Alert / info boxes ───────────────────────────── */
[data-testid="stAlert"] {
    border-radius: 8px;
    font-family: 'Inter', sans-serif;
    font-size: 0.88rem;
}

/* ── Progress bar ─────────────────────────────────── */
[data-testid="stProgressBar"] > div {
    background: rgba(60,196,183,0.15);
    border-radius: 4px;
}
[data-testid="stProgressBar"] > div > div {
    background: #3CC4B7;
    border-radius: 4px;
}

/* ── Download button ──────────────────────────────── */
[data-testid="stDownloadButton"] > button {
    background: transparent;
    border: 1px solid #222;
    color: #555;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    border-radius: 6px;
    transition: all 0.12s;
}
[data-testid="stDownloadButton"] > button:hover {
    border-color: #3CC4B7;
    color: #3CC4B7;
}

/* ── Plotly charts ────────────────────────────────── */
[data-testid="stPlotlyChart"] {
    border: 1px solid #141414;
    border-radius: 10px;
    overflow: hidden;
    background: #080808;
}

/* ── Success / Error states ───────────────────────── */
[data-testid="stAlert"][data-baseweb="notification"][kind="positive"] {
    background: rgba(0,255,136,0.06);
    border-color: rgba(0,255,136,0.2);
}
[data-testid="stAlert"][data-baseweb="notification"][kind="negative"] {
    background: rgba(255,51,102,0.06);
    border-color: rgba(255,51,102,0.2);
}

/* ── Custom classes ───────────────────────────────── */
.module-header {
    padding: 1.2rem 0 1rem;
    border-bottom: 1px solid #141414;
    margin-bottom: 1.2rem;
}
.module-tag {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.6rem; letter-spacing: 0.25em;
    color: #3CC4B7; text-transform: uppercase;
    margin-bottom: 0.4rem;
}
.module-title {
    font-size: 1.7rem; font-weight: 700;
    color: #fff; letter-spacing: -0.025em;
    line-height: 1.2;
}
.module-desc {
    font-size: 0.85rem; color: #555; margin-top: 0.3rem;
}
.level-badge {
    display: inline-block;
    padding: 3px 10px; border-radius: 20px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.62rem; font-weight: 700;
    letter-spacing: 0.1em; text-transform: uppercase;
}
.quiz-card {
    background: #090909;
    border: 1px solid #1a1a1a;
    border-radius: 10px;
    padding: 1.4rem 1.6rem;
    margin: 1.5rem 0;
}
.quiz-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.6rem; letter-spacing: 0.22em;
    color: #ffd600; text-transform: uppercase;
    margin-bottom: 1rem;
    display: flex; align-items: center; gap: 8px;
}
.quiz-label::before {
    content: '';
    display: inline-block; width: 6px; height: 6px;
    background: #ffd600; border-radius: 50%;
}
.nav-footer {
    border-top: 1px solid #141414;
    padding-top: 1.2rem;
    margin-top: 2rem;
}
.charts-header {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.6rem; letter-spacing: 0.22em;
    color: #555; text-transform: uppercase;
    margin: 1.2rem 0 0.8rem;
    display: flex; align-items: center; gap: 10px;
}
.charts-header::after {
    content: '';
    flex: 1; height: 1px; background: #141414;
}
.sidebar-level {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.58rem; letter-spacing: 0.2em;
    font-weight: 700; text-transform: uppercase;
    margin: 14px 0 5px 8px;
    padding: 0;
}
.sidebar-done-bar {
    background: #0d0d0d;
    border: 1px solid #1a1a1a;
    border-radius: 8px;
    padding: 0.8rem 1rem;
    margin: 0.5rem 0;
}
</style>
""", unsafe_allow_html=True)

LEARNING_DIR = Path(__file__).parent.parent / "learning"

# ── Module registry ──────────────────────────────────────────────────
MODULES = {
    "00_ROADMAP.md":                  ("//",  "Roadmap",        "Plan de route",               0),
    "00b_retail_vs_institutional.md": ("00b", "Retail vs Instit","Comprendre le jeu",           0),
    "00c_maths_notation.md":          ("00c", "Notation Maths", "Symboles et lettres grecques", 0),
    "01_time_series.md":              ("01",  "Time Series",    "Comprendre les donnees",       1),
    "02_central_limit_theorem.md":    ("02",  "CLT",            "Pourquoi les stats marchent",  1),
    "02b_asymptotics.md":             ("02b", "Asymptotics",    "Quand n devient grand",        1),
    "03_ergodicity.md":               ("03",  "Ergodicity",     "Pourquoi les traders perdent", 1),
    "03b_monte_carlo.md":             ("03b", "Monte Carlo",    "Comprendre la stabilite",      1),
    "04_garch.md":                    ("04",  "GARCH",          "Filtre de volatilite",         2),
    "04b_trading_metrics.md":         ("04b", "Metrics",        "Mesurer ton edge",             2),
    "05_hidden_markov_models.md":     ("05",  "HMM",            "Regime de marche (theorie)",   2),
    "05b_regime_switching.md":        ("05b", "Regime Switch",  "QUAND trader (live)",          2),
    "05c_hawkes.md":                  ("05c", "Hawkes",         "Microstructure orderflow",     2),
    "06_kalman_filter.md":            ("06",  "Kalman Filter",  "Signal propre",                3),
    "06b_kalman_mean_reversion.md":   ("06b", "Kalman MR",      "Mean reversion trading",       3),
    "06c_halflife_ou.md":             ("06c", "Demi-vie OU",    "Filtrer les signaux lents",    3),
    "06d_confirmation_reversal.md":   ("06d", "Confirmation",   "Timing d'entree optimal",      3),
    "07_pipeline_integration.md":     ("07",  "Pipeline",       "Tout connecter",               4),
    "08_kelly_criterion.md":          ("08",  "Kelly Criterion","Combien risquer par trade",    4),
    "09_backtesting_pitfalls.md":     ("09",  "Backtest Pitfalls","Pourquoi ton backtest ment", 4),
    "09b_profitable_vs_tradable.md":  ("09b", "Live Tradable",  "Pourquoi ca meurt en live",   4),
}

LEVEL_LABELS = {
    0: "",
    1: "NIVEAU 1 — FONDATIONS",
    2: "NIVEAU 2 — OUTILS",
    3: "NIVEAU 3 — SIGNAL",
    4: "NIVEAU 4 — LIVE",
}
LEVEL_COLORS = {
    0: "#555",
    1: "#00e5ff",
    2: "#ff00e5",
    3: "#ffd600",
    4: "#ff3366",
}

VIDEO_LINKS = {
    "00b_retail_vs_institutional.md": ("https://youtu.be/j1XAcdEHzbU",  "#40 Retail vs Institutional Trading"),
    "01_time_series.md":              ("https://youtu.be/JwqjuUnR8OY",  "#44 Time Series Analysis"),
    "02_central_limit_theorem.md":    ("https://youtu.be/q2era-4pnic",  "#61 Central Limit Theorem"),
    "03_ergodicity.md":               ("https://youtu.be/dryV1qJYUw8",  "#81 Ergodicity for Quant Trading"),
    "03b_monte_carlo.md":             ("https://youtu.be/-4sf43SLL3A",  "#33 Why Monte Carlo Simulation Works"),
    "04_garch.md":                    ("https://youtu.be/iImtlBRcczA",  "#47 ARCH & GARCH Models"),
    "04b_trading_metrics.md":         ("https://youtu.be/xziwmju7x2s",  "#48 Why Trading Metrics are Misleading"),
    "05_hidden_markov_models.md":     ("https://youtu.be/Bru4Mkr601Q",  "#51 Hidden Markov Models"),
    "05b_regime_switching.md":        ("https://youtu.be/mais1dsB_1g",  "#72/74 Markov Regime Switching Bot"),
    "05c_hawkes.md":                  ("https://youtu.be/BotPHbWFRUA",  "#94 Hawkes Processes"),
    "06_kalman_filter.md":            ("https://youtu.be/zVJY_oaVh-0",  "#92 Kalman Filter"),
    "06b_kalman_mean_reversion.md":   ("https://youtu.be/BuPil7nXvMU",  "#95 Trading Mean Reversion with Kalman Filters"),
    "06c_halflife_ou.md":             ("https://youtu.be/BuPil7nXvMU",  "#95 Trading Mean Reversion — Half-life OU"),
    "06d_confirmation_reversal.md":   ("https://youtu.be/mais1dsB_1g",  "#72 Markov Regime Switching Bot — Timing"),
    "08_kelly_criterion.md":          ("https://github.com/romanmichaelpaolucci/Quant-Guild-Library/tree/main/2025%20Video%20Lectures/36.%20How%20to%20Trade%20with%20the%20Kelly%20Criterion", "#36 Kelly Criterion"),
    "09_backtesting_pitfalls.md":     ("https://github.com/romanmichaelpaolucci/Quant-Guild-Library/tree/main/2026%20Video%20Lectures/97.%203%20Backtesting%20Pitfalls%20That%20Ruin%20Your%20Strategy", "#97 3 Backtesting Pitfalls"),
    "09b_profitable_vs_tradable.md":  ("https://github.com/romanmichaelpaolucci/Quant-Guild-Library/tree/main/2025%20Video%20Lectures/77.%20Profitable%20vs%20Tradable%20-%20Why%20Most%20Strategies%20Fail%20Live", "#77 Profitable vs Tradable"),
}

# ── State ────────────────────────────────────────────────────────────
if "completed" not in st.session_state:
    st.session_state.completed = load_progress()
if "selected" not in st.session_state:
    st.session_state.selected = "00_ROADMAP.md"

# ── Sidebar ──────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="padding:1rem 0.5rem 0.5rem;">
        <div style="font-family:'JetBrains Mono',monospace; font-size:0.6rem;
                    letter-spacing:0.25em; color:#3CC4B7; text-transform:uppercase;
                    margin-bottom:4px;">Quant Maths</div>
        <div style="font-size:1.1rem; font-weight:700; color:#fff;">Étude</div>
    </div>
    """, unsafe_allow_html=True)

    n_done  = len(st.session_state.completed - {"00_ROADMAP.md"})
    n_total = len(MODULES) - 1
    pct     = n_done / max(n_total, 1)

    st.markdown(f"""
    <div class="sidebar-done-bar">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
            <span style="font-family:'JetBrains Mono',monospace; font-size:0.65rem; color:#555;">
                Progression
            </span>
            <span style="font-family:'JetBrains Mono',monospace; font-size:0.72rem; color:#3CC4B7; font-weight:700;">
                {n_done}/{n_total}
            </span>
        </div>
        <div style="background:#141414; border-radius:3px; height:3px; overflow:hidden;">
            <div style="width:{pct*100:.0f}%; background:#3CC4B7; height:100%; border-radius:3px;
                        transition:width 0.3s;"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<div style='height:6px;'></div>", unsafe_allow_html=True)

    current_level = -1
    for fname, (icon, name, desc, level) in MODULES.items():
        if level != current_level and level > 0:
            current_level = level
            col = LEVEL_COLORS[level]
            lbl = LEVEL_LABELS[level]
            st.markdown(
                f"<div class='sidebar-level' style='color:{col};'>{lbl}</div>",
                unsafe_allow_html=True,
            )
        is_done = fname in st.session_state.completed
        is_sel  = fname == st.session_state.selected
        dot     = "● " if is_done else "○ "
        dot_col = "#3CC4B7" if is_done else "#2a2a2a"
        sel_bg  = "background:rgba(60,196,183,0.06); border:1px solid rgba(60,196,183,0.15); color:#3CC4B7;" if is_sel else ""
        st.markdown(
            f"<div style='display:flex; align-items:center; gap:6px; padding:3px 6px;"
            f"border-radius:5px; {sel_bg}'>"
            f"<span style='color:{dot_col}; font-size:0.55rem;'>{dot}</span>"
            f"<span style='font-family:JetBrains Mono,monospace; font-size:0.7rem; color:#444;'>{icon}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
        if st.button(name, key=f"nav_{fname}", use_container_width=True):
            st.session_state.selected = fname
            st.rerun()

    if n_done == n_total:
        st.balloons()
        st.markdown("""
        <div style="background:rgba(60,196,183,0.08); border:1px solid rgba(60,196,183,0.2);
                    border-radius:8px; padding:0.7rem 1rem; margin-top:1rem;
                    font-family:'JetBrains Mono',monospace; font-size:0.72rem; color:#3CC4B7;">
            Tous les modules termines
        </div>
        """, unsafe_allow_html=True)


# ── Content helpers ──────────────────────────────────────────────────

def render_math_markdown(text):
    """Render markdown with LaTeX support + inline chart markers."""
    parts = re.split(r'(\$\$.*?\$\$)', text, flags=re.DOTALL)
    for part in parts:
        if not part.strip():
            continue
        if part.startswith('$$') and part.endswith('$$'):
            latex_content = part[2:-2].strip()
            if latex_content:
                st.latex(latex_content)
        else:
            lines = part.split('\n')
            buffer = []
            for line in lines:
                chart_match = re.match(r'^\s*<!--\s*CHART:(\w+)\s*-->\s*$', line)
                if chart_match:
                    if buffer:
                        st.markdown('\n'.join(buffer), unsafe_allow_html=True)
                        buffer = []
                    chart_fn = INLINE_CHARTS.get(chart_match.group(1))
                    if chart_fn:
                        st.plotly_chart(chart_fn(), use_container_width=True,
                                        key=f"inline_{chart_match.group(1)}")
                    continue
                is_table_row = line.strip().startswith('|')
                has_inline_math = re.search(r'(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)', line)
                if has_inline_math and not is_table_row:
                    if buffer:
                        st.markdown('\n'.join(buffer), unsafe_allow_html=True)
                        buffer = []
                    st.markdown(line, unsafe_allow_html=True)
                else:
                    buffer.append(line)
            if buffer:
                st.markdown('\n'.join(buffer), unsafe_allow_html=True)


def split_content(content):
    separator = "# ============================================"
    chunks = content.split(separator)
    sections = {"apprentissage": "", "model": "", "lecon": "", "resume": ""}
    current_key = None
    for chunk in chunks:
        cl = chunk.lower()
        if "apprentissage" in cl and "c'est quoi" in cl:
            current_key = "apprentissage"
        elif "model" in cl and ("comment" in cl or "les maths" in cl):
            current_key = "model"
        elif "lecon" in cl and "exercice" in cl:
            current_key = "lecon"
        elif "resume" in cl and ("fiche" in cl or "revision" in cl):
            current_key = "resume"
        if current_key:
            sections[current_key] += chunk
    for key in sections:
        s = sections[key].replace(separator, "")
        lines = s.split("\n")
        cleaned = []
        skip_next = False
        for line in lines:
            if line.strip().startswith("# " + key.upper()) or line.strip().startswith("# " + key.capitalize()):
                skip_next = True
                continue
            if skip_next and line.strip().startswith("#"):
                skip_next = False
                continue
            skip_next = False
            cleaned.append(line)
        sections[key] = "\n".join(cleaned)
    return sections


def render_charts(selected_file):
    chart_list = CHARTS.get(selected_file, [])
    if not chart_list:
        return
    st.markdown(
        "<div class='charts-header'>Visualisations interactives</div>",
        unsafe_allow_html=True,
    )
    for title, chart_fn in chart_list:
        st.plotly_chart(chart_fn(), use_container_width=True, key=f"chart_{title}")


def render_quiz(selected):
    """Render the interactive quiz card for this module."""
    st.markdown("""
    <div class="quiz-card">
        <div class="quiz-label">Verification rapide</div>
    </div>
    """, unsafe_allow_html=True)

    if "time_series" in selected:
        val = st.number_input("Calcule MA(3) pour [100, 102, 101] :", min_value=0.0, step=0.1, key="quiz_ts")
        if val > 0:
            if abs(val - 101.0) < 0.2:
                st.success("Correct — (100+102+101)/3 = 101.0")
            else:
                st.error("Indice : (100 + 102 + 101) / 3 = ?")

    elif "clt" in selected or "central" in selected:
        val = st.number_input("Erreur standard si sigma=60, n=100 :", min_value=0.0, step=0.1, key="quiz_clt")
        if val > 0:
            if abs(val - 6.0) < 0.3:
                st.success("Correct — 60 / sqrt(100) = 6.0")
            else:
                st.error("Formule : sigma / sqrt(n) = 60 / 10 = 6.0")

    elif "ergodicity" in selected:
        val = st.number_input("g = E[r] - sigma²/2. Si E[r]=5%, sigma=20%, g = ? (%)",
                              min_value=-10.0, max_value=10.0, step=0.1, key="quiz_ergo")
        if val != 0:
            if abs(val - 3.0) < 0.3:
                st.success("Correct — 5% - (20%)²/2 = 3%")
            else:
                st.error("g = 5% - (0.20)²/2 = 5% - 2% = 3%")

    elif "garch" in selected:
        val = st.number_input("GARCH: alpha0=0.00001, alpha1=0.1, beta1=0.85 → sigma²_LT × 10⁴ = ?",
                              min_value=0.0, step=0.1, key="quiz_garch")
        if val > 0:
            expected = 0.00001 / (1 - 0.1 - 0.85) * 10000
            if abs(val - expected) < 0.3:
                st.success(f"Correct — 0.00001 / (1-0.95) = {expected:.1f} × 10⁻⁴")
            else:
                st.error(f"alpha0 / (1 - alpha1 - beta1) = 0.00001 / 0.05 = {expected:.1f} × 10⁻⁴")

    elif "kalman" in selected:
        val = st.number_input("K = P/(P+R). Si P=2, R=4, K = ?",
                              min_value=0.0, max_value=1.0, step=0.01, key="quiz_kf")
        if val > 0:
            if abs(val - 0.333) < 0.02:
                st.success("Correct — K = 2 / (2+4) = 0.333")
            else:
                st.error("K = P / (P+R) = 2 / 6 = 0.333")

    elif "kelly" in selected:
        val = st.number_input("Kelly — WR=60%, R:R=2:1. f* = ? (%)",
                              min_value=0.0, max_value=100.0, step=1.0, key="quiz_kelly")
        if val > 0:
            expected = (0.60 * 2 - 0.40) / 2 * 100
            if abs(val - expected) < 2.0:
                st.success(f"Correct — (0.60×2 - 0.40) / 2 = {expected:.0f}%")
            else:
                st.error(f"f* = (p×b - (1-p)) / b = (0.6×2 - 0.4) / 2 = {expected:.0f}%")

    elif "pitfall" in selected or "backtest" in selected.lower():
        val = st.number_input("6 params libres → combien de trades minimum ?",
                              min_value=0, step=10, key="quiz_pitfalls")
        if val > 0:
            if abs(val - 300) < 50:
                st.success("Correct — 50 × 6 params = 300 trades minimum")
            else:
                st.error("Regle : N > 50 × k_params → 50 × 6 = 300")

    elif "tradable" in selected or "profitable" in selected.lower():
        val = st.number_input("Sharpe IS=1.4, OOS=0.9 → ratio generalisation = ?",
                              min_value=0.0, max_value=2.0, step=0.01, key="quiz_tradable")
        if val > 0:
            expected = round(0.9 / 1.4, 2)
            if abs(val - expected) < 0.05:
                st.success(f"Correct — 0.9/1.4 = {expected} → robuste (> 0.7)")
            else:
                st.error(f"Ratio = Sharpe_OOS / Sharpe_IS = 0.9/1.4 = {expected}")


# ── Main content ─────────────────────────────────────────────────────
selected = st.session_state.selected
meta     = MODULES.get(selected, ("", selected, "", 0))
icon, name, desc, level = meta
file_path = LEARNING_DIR / selected

if not file_path.exists():
    st.error(f"Fichier introuvable : {file_path}")
    st.stop()

content = file_path.read_text(encoding="utf-8")

# ── Header ───────────────────────────────────────────────────────────
col_h1, col_h2 = st.columns([4, 1])

with col_h1:
    if level > 0:
        col_lbl = LEVEL_COLORS[level]
        lbl     = LEVEL_LABELS[level]
        st.markdown(
            f"<div style='font-family:JetBrains Mono,monospace; font-size:0.6rem;"
            f"letter-spacing:0.2em; color:{col_lbl}; text-transform:uppercase;"
            f"margin-bottom:4px;'>{lbl}</div>",
            unsafe_allow_html=True,
        )
    st.markdown(
        f"<div style='font-size:2rem; font-weight:700; color:#fff;"
        f"letter-spacing:-0.025em; line-height:1.1;'>{icon} {name}</div>"
        f"<div style='font-size:0.85rem; color:#444; margin-top:5px;'>{desc}</div>",
        unsafe_allow_html=True,
    )

with col_h2:
    if selected in VIDEO_LINKS:
        url, video_title = VIDEO_LINKS[selected]
        is_yt = "youtu" in url
        if is_yt:
            btn_html = (
                f"<a href='{url}' target='_blank' style='text-decoration:none;'>"
                f"<div style='background:#c00; color:#fff; padding:8px 14px; border-radius:7px;"
                f"font-family:JetBrains Mono,monospace; font-size:0.7rem; font-weight:700;"
                f"letter-spacing:0.05em; text-align:center; margin-top:14px;"
                f"transition:background 0.12s;'>▶ Voir la video</div></a>"
                f"<div style='font-family:JetBrains Mono,monospace; font-size:0.6rem;"
                f"color:#333; margin-top:5px; text-align:center;'>{video_title}</div>"
            )
        else:
            btn_html = (
                f"<a href='{url}' target='_blank' style='text-decoration:none;'>"
                f"<div style='background:#0d0d0d; color:#555; padding:8px 14px; border-radius:7px;"
                f"border:1px solid #222; font-family:JetBrains Mono,monospace; font-size:0.7rem;"
                f"font-weight:700; text-align:center; margin-top:14px;'>GH Code source</div></a>"
                f"<div style='font-family:JetBrains Mono,monospace; font-size:0.6rem;"
                f"color:#333; margin-top:5px; text-align:center;'>{video_title}</div>"
            )
        st.markdown(btn_html, unsafe_allow_html=True)

st.markdown("<div style='border-bottom:1px solid #141414; margin:1rem 0 1.2rem;'></div>",
            unsafe_allow_html=True)

# ── Roadmap: simple render ───────────────────────────────────────────
if selected == "00_ROADMAP.md":
    render_math_markdown(content)
    st.stop()

# ── Module: 4 tabs ───────────────────────────────────────────────────
sections    = split_content(content)
has_content = any(s.strip() for s in sections.values())

if not has_content:
    render_math_markdown(content)
    st.stop()

# Charts above tabs
render_charts(selected)

tab_a, tab_m, tab_l, tab_r = st.tabs([
    "CONCEPTS",
    "FORMULES",
    "PRATIQUE",
    "FICHE",
])

with tab_a:
    if sections["apprentissage"].strip():
        render_math_markdown(sections["apprentissage"])
    else:
        st.markdown(
            "<div style='color:#333; font-family:JetBrains Mono,monospace;"
            "font-size:0.8rem; padding:2rem; text-align:center;'>Section en cours.</div>",
            unsafe_allow_html=True,
        )

with tab_m:
    if sections["model"].strip():
        render_math_markdown(sections["model"])
    else:
        st.markdown(
            "<div style='color:#333; font-family:JetBrains Mono,monospace;"
            "font-size:0.8rem; padding:2rem; text-align:center;'>Section en cours.</div>",
            unsafe_allow_html=True,
        )

with tab_l:
    if sections["lecon"].strip():
        render_math_markdown(sections["lecon"])
        st.markdown("<div style='height:1rem;'></div>", unsafe_allow_html=True)
        render_quiz(selected)
    else:
        st.markdown(
            "<div style='color:#333; font-family:JetBrains Mono,monospace;"
            "font-size:0.8rem; padding:2rem; text-align:center;'>Section en cours.</div>",
            unsafe_allow_html=True,
        )

with tab_r:
    if sections["resume"].strip():
        render_math_markdown(sections["resume"])
        st.markdown("<div style='height:1rem;'></div>", unsafe_allow_html=True)
        st.download_button(
            "Telecharger la fiche",
            sections["resume"],
            file_name=f"fiche_{name.lower().replace(' ', '_')}.md",
            mime="text/markdown",
        )
    else:
        st.markdown(
            "<div style='color:#333; font-family:JetBrains Mono,monospace;"
            "font-size:0.8rem; padding:2rem; text-align:center;'>Section en cours.</div>",
            unsafe_allow_html=True,
        )

# ── Footer ───────────────────────────────────────────────────────────
st.markdown("<div class='nav-footer'>", unsafe_allow_html=True)
col1, col2, col3 = st.columns([1, 1, 3])

with col1:
    if selected not in st.session_state.completed:
        if st.button("Marquer termine", type="primary", use_container_width=True):
            st.session_state.completed.add(selected)
            save_progress(st.session_state.completed)
            st.rerun()
    else:
        st.markdown(
            "<div style='font-family:JetBrains Mono,monospace; font-size:0.7rem;"
            "color:#3CC4B7; padding:8px 0;'>Termine</div>",
            unsafe_allow_html=True,
        )

with col2:
    if selected in st.session_state.completed:
        if st.button("Recommencer", use_container_width=True):
            st.session_state.completed.discard(selected)
            save_progress(st.session_state.completed)
            st.rerun()

with col3:
    keys = list(MODULES.keys())
    idx  = keys.index(selected)
    if idx < len(keys) - 1:
        next_key  = keys[idx + 1]
        next_meta = MODULES[next_key]
        next_name = next_meta[1]
        next_icon = next_meta[0]
        next_lv   = next_meta[3]
        next_col  = LEVEL_COLORS[next_lv]
        if st.button(
            f"Suivant : {next_icon} {next_name}",
            use_container_width=True,
        ):
            st.session_state.selected = next_key
            st.rerun()

st.markdown("</div>", unsafe_allow_html=True)
