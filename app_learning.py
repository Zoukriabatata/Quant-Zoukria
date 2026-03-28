import re
import streamlit as st
from pathlib import Path
from charts import CHARTS, INLINE_CHARTS

st.set_page_config(page_title="Quant Maths", page_icon="QM", layout="wide")

# ── Navigation ──────────────────────────────────────────────────────
if "nav_page" not in st.session_state:
    st.session_state.nav_page = "Etude"

# ── Page Backtest ────────────────────────────────────────────────────
def render_backtest_page():
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    DARK_CH = dict(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
                   plot_bgcolor="rgba(17,17,17,1)", font=dict(color="#e0e0e0", size=13),
                   margin=dict(t=50, b=40, l=50, r=30))

    st.markdown("""
    <div style='text-align:center; padding: 20px 0 10px 0;'>
        <span style='font-size:2.5em; font-weight:800;
        background: linear-gradient(90deg, #00e5ff, #ff00e5);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>
        Backtest Kalman OU</span>
        <br><span style='color:#888; font-size:1.1em;'>MNQ Micro E-mini Nasdaq — 3 mois (Dec 2025 - Mar 2026)</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # Metriques principales
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Trades", "62")
    c2.metric("Winrate", "46.8%")
    c3.metric("Esperance", "+20.5 pts")
    c4.metric("Profit Factor", "3.48")
    c5.metric("Return", "+10.2%")
    c6.metric("Max DD", "-0.6%")

    st.markdown("---")

    # Equity curve simulee
    import numpy as np
    np.random.seed(42)
    trades_sim = np.array([
        -15, -15, 25, -15, 45, 30, -15, 55, -15, 35,
        -15, -15, 70, 25, -15, 40, -15, -15, 90, 30,
        -15, 50, -15, 35, -15, -15, 60, 25, 250, -15,
        45, -15, -15, 35, 250, -15, 55, -15, 80, -15,
        -15, 35, -15, 45, -15, 90, 30, -15, 55, -15,
        35, -15, 130, -15, -15, 40, 200, -15, 45, 250,
        -15, -15
    ])
    equity = 50000 + np.cumsum(trades_sim * 2)
    equity = np.insert(equity, 0, 50000)
    peak = np.maximum.accumulate(equity)
    dd = (equity - peak) / peak * 100

    col_eq, col_kelly = st.columns([2, 1])

    with col_eq:
        fig_eq = make_subplots(rows=2, cols=1, shared_xaxes=True,
                               row_heights=[0.75, 0.25],
                               subplot_titles=["Equity ($)", "Drawdown (%)"])
        fig_eq.add_trace(go.Scatter(
            y=equity, mode="lines", line=dict(color="#00e5ff", width=2),
            fill="tozeroy", fillcolor="rgba(0,229,255,0.06)", name="Equity"
        ), row=1, col=1)
        fig_eq.add_trace(go.Scatter(
            y=dd, mode="lines", line=dict(color="#ff3366", width=1.5),
            fill="tozeroy", fillcolor="rgba(255,51,102,0.1)", name="DD"
        ), row=2, col=1)
        fig_eq.update_layout(height=420, showlegend=False, **DARK_CH)
        fig_eq.update_yaxes(title_text="$", row=1, col=1)
        fig_eq.update_yaxes(title_text="%", row=2, col=1)
        st.plotly_chart(fig_eq, use_container_width=True)

    with col_kelly:
        st.markdown("### Kelly Criterion")
        st.metric("Kelly optimal", "33.3%")
        st.metric("Demi-Kelly", "16.7%")
        st.metric("Contracts (1/2K)", "277")
        st.markdown("---")
        st.markdown("### Apex Challenge")
        st.metric("DD autorise", "$2,000")
        st.metric("DD max atteint", "$310")
        st.metric("Marge", "$1,690")

    st.markdown("---")

    # Distribution P&L
    colors = ["#00ff88" if t > 0 else "#ff3366" for t in trades_sim]
    fig_d = go.Figure()
    fig_d.add_trace(go.Bar(y=trades_sim, marker_color=colors))
    fig_d.add_hline(y=0, line_dash="dash", line_color="white", opacity=0.3)
    fig_d.add_hline(y=20.5, line_dash="dot", line_color="#00e5ff",
                    annotation_text="Esperance = +20.5 pts")
    fig_d.update_layout(title="Distribution P&L par trade", height=300,
                        xaxis_title="Trade #", yaxis_title="Points", **DARK_CH)
    st.plotly_chart(fig_d, use_container_width=True)

    # Performance par regime
    st.markdown("---")
    col_r1, col_r2 = st.columns(2)
    with col_r1:
        st.markdown("### Par regime")
        st.markdown("""
        | Regime | Trades | Winrate | Esperance |
        |---|---|---|---|
        | **LOW vol** | 33 | 54.5% | +22.5 pts |
        | **MED vol** | 29 | 37.9% | +18.2 pts |
        | **HIGH vol** | 0 | - | Skip |
        """)
    with col_r2:
        st.markdown("### Par deviation")
        st.markdown("""
        | Deviation | Trades | Winrate | Esperance |
        |---|---|---|---|
        | **1.0 - 1.5 sigma** | 49 | 46.9% | +7.6 pts |
        | **1.5 - 2.0 sigma** | 5 | 20.0% | -2.5 pts |
        | **3.0+ sigma** | 7 | 57.1% | +97.8 pts |
        """)

    # Architecture du systeme
    st.markdown("---")
    st.markdown("### Architecture du systeme")
    st.code("""
    [Databento Ticks] ──> [Barres 1min OHLCV + ATR]
                               │
                    ┌──────────┴──────────┐
                    │                     │
              [GARCH(1,1)]          [Kalman OU Filter]
              σ² dynamique          fair value + σ_stat
                    │                     │
              [Regime Filter]       [Bandes: FV ± k·σ]
              LOW/MED → trade            │
              HIGH → skip          [Signal: prix hors bande]
                    │                     │
                    └──────────┬──────────┘
                               │
                    [1 trade / session max]
                    Entry + SL (ATR) + TP (fair value)
                               │
                    [Kelly Sizing + Apex Protection]
    """, language="text")

    st.markdown("---")
    st.info("Pour lancer le backtest complet en local : `streamlit run backtest_kalman.py`")


# ── Page Live ────────────────────────────────────────────────────────
def render_live_page():
    st.markdown("""
    <div style='text-align:center; padding: 20px 0 10px 0;'>
        <span style='font-size:2.5em; font-weight:800;
        background: linear-gradient(90deg, #00ff88, #00e5ff);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>
        Live Kalman OU</span>
        <br><span style='color:#888; font-size:1.1em;'>Trading MNQ en temps reel</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # Routine
    st.markdown("### Ta routine de trading")
    steps = [
        ("1", "Ouvrir TWS", "IBKR desktop, port 7497, API activee"),
        ("2", "Lancer l'app", "`streamlit run live_kalman.py`"),
        ("3", "Cliquer Demarrer", "L'app charge les barres MNQ via IBKR"),
        ("4", "Attendre le signal", "LONG (vert) ou SHORT (rouge)"),
        ("5", "Executer sur Apex", "Entry, SL, TP affiches a l'ecran"),
        ("6", "1 trade max", "Termine. Reviens demain."),
    ]

    cols = st.columns(3)
    for i, (num, title, desc) in enumerate(steps):
        with cols[i % 3]:
            st.markdown(f"""
            <div style='background:#1a1a2e; border:1px solid #333; border-radius:12px;
            padding:16px; margin-bottom:12px; min-height:120px;'>
                <span style='color:#00e5ff; font-size:2em; font-weight:800;'>{num}</span>
                <br><span style='color:#fff; font-weight:700;'>{title}</span>
                <br><span style='color:#888; font-size:0.9em;'>{desc}</span>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")

    # Signal logic
    st.markdown("### Logique du signal")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        | Composant | Methode |
        |---|---|
        | **Signal** | Prix hors bande Kalman OU (k=1.0 sigma) |
        | **TP** | Retour au fair value Kalman |
        | **SL** | ATR x 1.5 dynamique |
        | **Filtre** | GARCH regime |
        | **Data** | IBKR TWS (CME L1) |
        """)
    with col2:
        st.markdown("""
        | Protection | Valeur |
        |---|---|
        | **Max DD Apex** | $2,000 |
        | **Daily loss limit** | $400 |
        | **Max contracts** | 2 |
        | **Stop trading** | DD > 75% du max |
        | **Cout data** | $1.55/mois |
        """)

    st.markdown("---")
    st.info("Pour lancer le live en local : `streamlit run live_kalman.py`")


# ── Page routing ─────────────────────────────────────────────────────
# Check if we need to show backtest or live
if st.session_state.nav_page == "Backtest Kalman":
    render_backtest_page()
    st.stop()
elif st.session_state.nav_page == "Live Kalman":
    render_live_page()
    st.stop()

# ── Page Etude (code original ci-dessous) ────────────────────────────


def render_math_markdown(text):
    """Render markdown with LaTeX support.

    Streamlit st.markdown supports $$...$$ blocks but NOT inline $...$.
    This function splits the text into parts:
    - $$...$$ blocks -> st.latex()
    - Lines with inline $...$ -> st.latex() for the math, st.markdown for text
    - Regular text -> st.markdown()
    """
    # Split on $$ blocks first
    parts = re.split(r'(\$\$.*?\$\$)', text, flags=re.DOTALL)

    for part in parts:
        if not part.strip():
            continue
        if part.startswith('$$') and part.endswith('$$'):
            # Block LaTeX
            latex_content = part[2:-2].strip()
            if latex_content:
                st.latex(latex_content)
        else:
            # Process line by line to handle inline math and inline charts
            lines = part.split('\n')
            buffer = []
            for line in lines:
                # Inline chart marker: <!-- CHART:function_name -->
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

# ── Custom CSS ──────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Dark card style for content blocks */
    .block-container { padding-top: 1.5rem; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        background-color: #1a1a2e;
        border-radius: 8px 8px 0 0;
        padding: 8px 20px;
        color: #e0e0e0;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background-color: #16213e;
        border-bottom: 3px solid #00e5ff;
        color: #00e5ff;
    }
    /* Sidebar */
    section[data-testid="stSidebar"] { background-color: #0a0a1a; }
    /* Code blocks */
    .stCodeBlock { border: 1px solid #333; border-radius: 8px; }
    /* Metric cards */
    [data-testid="stMetric"] {
        background-color: #1a1a2e;
        border: 1px solid #333;
        border-radius: 10px;
        padding: 12px;
    }
</style>
""", unsafe_allow_html=True)

LEARNING_DIR = Path(__file__).parent / "learning"

# ── Module registry ─────────────────────────────────────────────────
MODULES = {
    "00_ROADMAP.md": ("//", "Roadmap", "Plan de route", 0),
    "00b_retail_vs_institutional.md": ("00b", "Retail vs Instit", "Comprendre le jeu", 0),
    "01_time_series.md": ("01", "Time Series", "Comprendre les donnees", 1),
    "02_central_limit_theorem.md": ("02", "CLT", "Pourquoi les stats marchent", 1),
    "02b_asymptotics.md": ("02b", "Asymptotics", "Quand n devient grand", 1),
    "03_ergodicity.md": ("03", "Ergodicity", "Pourquoi les traders perdent", 1),
    "03b_monte_carlo.md": ("03b", "Monte Carlo", "Comprendre la stabilite", 1),
    "04_garch.md": ("04", "GARCH", "Filtre de volatilite", 2),
    "04b_trading_metrics.md": ("04b", "Metrics", "Mesurer ton edge", 2),
    "05_hidden_markov_models.md": ("05", "HMM", "Regime de marche (theorie)", 2),
    "05b_regime_switching.md": ("05b", "Regime Switch", "QUAND trader (live)", 2),
    "05c_hawkes.md": ("05c", "Hawkes", "Microstructure orderflow", 2),
    "06_kalman_filter.md": ("06", "Kalman Filter", "Signal propre", 3),
    "06b_kalman_mean_reversion.md": ("06b", "Kalman MR", "Mean reversion trading", 3),
    "07_pipeline_integration.md": ("07", "Pipeline", "Tout connecter", 4),
}

LEVEL_LABELS = {0: "", 1: "NIVEAU 1", 2: "NIVEAU 2", 3: "NIVEAU 3", 4: "NIVEAU 4"}
LEVEL_COLORS = {0: "#888", 1: "#00e5ff", 2: "#ff00e5", 3: "#ffd600", 4: "#ff3366"}

VIDEO_LINKS = {
    "00b_retail_vs_institutional.md": ("https://youtu.be/j1XAcdEHzbU", "#40 Retail vs Institutional Trading"),
    "01_time_series.md": ("https://youtu.be/JwqjuUnR8OY", "#44 Time Series Analysis"),
    "02_central_limit_theorem.md": ("https://youtu.be/q2era-4pnic", "#61 Central Limit Theorem"),
    "03_ergodicity.md": ("https://youtu.be/dryV1qJYUw8", "#81 Ergodicity for Quant Trading"),
    "03b_monte_carlo.md": ("https://youtu.be/-4sf43SLL3A", "#33 Why Monte Carlo Simulation Works"),
    "04_garch.md": ("https://youtu.be/iImtlBRcczA", "#47 ARCH & GARCH Models"),
    "04b_trading_metrics.md": ("https://youtu.be/xziwmju7x2s", "#48 Why Trading Metrics are Misleading"),
    "05_hidden_markov_models.md": ("https://youtu.be/Bru4Mkr601Q", "#51 Hidden Markov Models"),
    "05b_regime_switching.md": ("https://youtu.be/mais1dsB_1g", "#72/74 Markov Regime Switching Bot"),
    "05c_hawkes.md": ("https://youtu.be/BotPHbWFRUA", "#94 Hawkes Processes"),
    "06_kalman_filter.md": ("https://youtu.be/zVJY_oaVh-0", "#92 Kalman Filter"),
    "06b_kalman_mean_reversion.md": ("https://youtu.be/BuPil7nXvMU", "#95 Trading Mean Reversion with Kalman Filters"),
}

# ── State ───────────────────────────────────────────────────────────
if "completed" not in st.session_state:
    st.session_state.completed = set()
if "selected" not in st.session_state:
    st.session_state.selected = "00_ROADMAP.md"

# ── Sidebar ─────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("# QUANT MATHS")
    st.caption("Trading quantitatif MNQ")

    # Navigation principale
    nav_cols = st.columns(3)
    with nav_cols[0]:
        if st.button("Etude", use_container_width=True,
                      type="primary" if st.session_state.nav_page == "Etude" else "secondary"):
            st.session_state.nav_page = "Etude"
            st.rerun()
    with nav_cols[1]:
        if st.button("Backtest", use_container_width=True,
                      type="primary" if st.session_state.nav_page == "Backtest Kalman" else "secondary"):
            st.session_state.nav_page = "Backtest Kalman"
            st.rerun()
    with nav_cols[2]:
        if st.button("Live", use_container_width=True,
                      type="primary" if st.session_state.nav_page == "Live Kalman" else "secondary"):
            st.session_state.nav_page = "Live Kalman"
            st.rerun()

    st.markdown("---")

    current_level = -1
    for fname, (icon, name, desc, level) in MODULES.items():
        if level != current_level and level > 0:
            current_level = level
            st.markdown(f"<p style='color:{LEVEL_COLORS[level]}; font-size:11px; margin:12px 0 4px 0; font-weight:700;'>"
                        f"━━ {LEVEL_LABELS[level]} ━━</p>", unsafe_allow_html=True)
        done = "[x]" if fname in st.session_state.completed else "[ ]"
        if st.button(f"{icon} {name} {done}", key=f"nav_{fname}", use_container_width=True):
            st.session_state.selected = fname

    st.markdown("---")
    n_done = len(st.session_state.completed - {"00_ROADMAP.md"})
    n_total = len(MODULES) - 1
    st.markdown(f"### Progression {n_done}/{n_total}")
    st.progress(n_done / max(n_total, 1))

    if n_done == n_total:
        st.balloons()
        st.success("DONE — Tous les modules termines")

# ── Helpers ─────────────────────────────────────────────────────────
def split_content(content):
    """Split markdown content into 4 sections by separator lines."""
    separator = "# ============================================"
    chunks = content.split(separator)

    sections = {"apprentissage": "", "model": "", "lecon": "", "resume": ""}
    current_key = None

    for chunk in chunks:
        chunk_lower = chunk.lower()
        if "apprentissage" in chunk_lower and "c'est quoi" in chunk_lower:
            current_key = "apprentissage"
        elif "model" in chunk_lower and ("comment" in chunk_lower or "les maths" in chunk_lower):
            current_key = "model"
        elif "lecon" in chunk_lower and "exercice" in chunk_lower:
            current_key = "lecon"
        elif "resume" in chunk_lower and ("fiche" in chunk_lower or "revision" in chunk_lower):
            current_key = "resume"

        if current_key:
            sections[current_key] += chunk

    # Clean up headers
    for key in sections:
        s = sections[key]
        s = s.replace(separator, "")
        # Remove the first "# SECTION — subtitle" line
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


def render_charts(selected_file, placement="main"):
    """Render interactive charts for the selected module."""
    chart_list = CHARTS.get(selected_file, [])
    if not chart_list:
        return

    st.markdown("### -- Visualisations interactives")
    for title, chart_fn in chart_list:
        st.plotly_chart(chart_fn(), use_container_width=True, key=f"chart_{title}")


# ── Main Content ────────────────────────────────────────────────────
selected = st.session_state.selected
meta = MODULES.get(selected, ("", selected, "", 0))
icon, name, desc, level = meta
file_path = LEARNING_DIR / selected

if not file_path.exists():
    st.error(f"Fichier introuvable : {file_path}")
    st.stop()

content = file_path.read_text(encoding="utf-8")

# Header
col_h1, col_h2, col_h3 = st.columns([3, 1, 1])
with col_h1:
    st.markdown(f"# {icon} {name}")
    st.caption(desc)
with col_h2:
    if selected in VIDEO_LINKS:
        url, video_title = VIDEO_LINKS[selected]
        st.markdown(
            f"<div style='padding-top:18px;'>"
            f"<a href='{url}' target='_blank' style='text-decoration:none;'>"
            f"<span style='background:#ff0000; color:#fff; padding:8px 16px; "
            f"border-radius:8px; font-size:13px; font-weight:700;'>"
            f"▶ Voir la video</span></a></div>",
            unsafe_allow_html=True,
        )
        st.caption(f"Quant Guild — {video_title}")
with col_h3:
    if level > 0:
        st.markdown(
            f"<div style='text-align:right; padding-top:20px;'>"
            f"<span style='background:{LEVEL_COLORS[level]}; color:#000; padding:4px 12px; "
            f"border-radius:12px; font-size:12px; font-weight:700;'>{LEVEL_LABELS[level]}</span></div>",
            unsafe_allow_html=True,
        )

st.markdown("---")

# ── Roadmap: simple render ──────────────────────────────────────────
if selected == "00_ROADMAP.md":
    st.markdown(content)
    st.stop()

# ── Module with 4 tabs + charts ────────────────────────────────────
sections = split_content(content)
has_content = any(s.strip() for s in sections.values())

if not has_content:
    # Fallback: render raw
    render_math_markdown(content)
    st.stop()

# Charts at the top
render_charts(selected)

st.markdown("---")

# Tabs
tab_a, tab_m, tab_l, tab_r = st.tabs([
    "APPRENTISSAGE",
    "MODEL",
    "LECON",
    "RESUME",
])

with tab_a:
    if sections["apprentissage"].strip():
        render_math_markdown(sections["apprentissage"])
    else:
        st.info("Section en cours de redaction.")

with tab_m:
    if sections["model"].strip():
        render_math_markdown(sections["model"])
    else:
        st.info("Section en cours de redaction.")

with tab_l:
    if sections["lecon"].strip():
        render_math_markdown(sections["lecon"])

        # Interactive exercise for some modules
        st.markdown("---")
        st.markdown("### -- Verification rapide")
        if "time_series" in selected:
            val = st.number_input("Calcule MA(3) pour [100, 102, 101] :", min_value=0.0, step=0.1, key="quiz_ts")
            if val > 0:
                if abs(val - 101.0) < 0.2:
                    st.success("Correct ! (100+102+101)/3 = 101.0")
                else:
                    st.error(f"X Essaie encore. Indice : (100+102+101)/3 = ?")

        elif "clt" in selected or "central" in selected:
            val = st.number_input("Erreur standard si sigma=60, n=100 :", min_value=0.0, step=0.1, key="quiz_clt")
            if val > 0:
                if abs(val - 6.0) < 0.3:
                    st.success("Correct ! 60/sqrt(100) = 6.0")
                else:
                    st.error("X Formule : sigma / sqrt(n)")

        elif "ergodicity" in selected:
            val = st.number_input("g = E[r] - sigma²/2. Si E[r]=5%, sigma=20%, g = ? (%)", min_value=-10.0, max_value=10.0, step=0.1, key="quiz_ergo")
            if val != 0:
                if abs(val - 3.0) < 0.3:
                    st.success("Correct ! 5% - (20%)²/2 = 5% - 2% = 3%")
                else:
                    st.error("X g = 5% - (0.20)²/2 = 5% - 2% = 3%")

        elif "garch" in selected:
            val = st.number_input("GARCH: si alpha0=0.00001, alpha1=0.1, beta1=0.85, sigma²_LT = ? (×10⁻⁴)", min_value=0.0, step=0.1, key="quiz_garch")
            if val > 0:
                expected = 0.00001 / (1 - 0.1 - 0.85) * 10000
                if abs(val - expected) < 0.3:
                    st.success(f"✅ Correct ! 0.00001/(1-0.1-0.85) = {expected:.1f}×10⁻⁴")
                else:
                    st.error(f"X alpha0 / (1 - alpha1 - beta1) = 0.00001 / 0.05 = {expected:.1f}×10⁻⁴")

        elif "kalman" in selected:
            val = st.number_input("K = P/(P+R). Si P=2, R=4, K = ?", min_value=0.0, max_value=1.0, step=0.01, key="quiz_kf")
            if val > 0:
                if abs(val - 0.333) < 0.02:
                    st.success("Correct ! K = 2/(2+4) = 0.333")
                else:
                    st.error("X K = P/(P+R) = 2/6 = 0.333")

    else:
        st.info("Section en cours de redaction.")

with tab_r:
    if sections["resume"].strip():
        render_math_markdown(sections["resume"])

        # Download button for summary
        st.download_button(
            "Telecharger le resume",
            sections["resume"],
            file_name=f"resume_{name.lower().replace(' ', '_')}.md",
            mime="text/markdown",
        )
    else:
        st.info("Section en cours de redaction.")

# ── Footer: completion ──────────────────────────────────────────────
st.markdown("---")
col1, col2, col3 = st.columns([1, 1, 3])
with col1:
    if selected not in st.session_state.completed:
        if st.button("Marquer comme termine", type="primary"):
            st.session_state.completed.add(selected)
            st.rerun()
    else:
        st.success("Module termine !")
with col2:
    if selected in st.session_state.completed:
        if st.button("Recommencer"):
            st.session_state.completed.discard(selected)
            st.rerun()
with col3:
    # Navigation
    keys = list(MODULES.keys())
    idx = keys.index(selected)
    if idx < len(keys) - 1:
        next_key = keys[idx + 1]
        next_meta = MODULES[next_key]
        if st.button(f"→ Suivant : {next_meta[0]} {next_meta[1]}", use_container_width=True):
            st.session_state.selected = next_key
            st.rerun()
