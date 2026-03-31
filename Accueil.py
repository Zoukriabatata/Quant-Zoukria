import streamlit as st

st.set_page_config(page_title="Quant Maths", page_icon="⚡", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;700&display=swap');

* { box-sizing: border-box; }

[data-testid="stAppViewContainer"] {
    background: #060606;
    font-family: 'Space Grotesk', sans-serif;
}
[data-testid="stSidebar"] {
    background: #0a0a0a;
    border-right: 1px solid #1a1a1a;
}
[data-testid="stHeader"]           { background: transparent; }
[data-testid="stToolbar"]          { display: none; }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: #0a0a0a; }
::-webkit-scrollbar-thumb { background: #3CC4B7; border-radius: 2px; }

/* ── Sidebar Nav ── */
[data-testid="stSidebarNav"] {
    padding: 0.5rem 0;
}
[data-testid="stSidebarNavLink"] {
    display: block;
    padding: 0.6rem 1.2rem;
    margin: 2px 8px;
    border-radius: 6px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem;
    letter-spacing: 0.08em;
    color: #555 !important;
    text-decoration: none !important;
    transition: background 0.15s, color 0.15s;
    border: 1px solid transparent;
}
[data-testid="stSidebarNavLink"]:hover {
    background: #111 !important;
    color: #ccc !important;
    border-color: #1a1a1a;
}
[data-testid="stSidebarNavLink"][aria-current="page"] {
    background: rgba(60,196,183,0.08) !important;
    color: #3CC4B7 !important;
    border-color: rgba(60,196,183,0.2);
}
[data-testid="stSidebarNavLink"] span {
    font-size: 0.75rem !important;
}

/* ── Hero ── */
.hero {
    padding: 4rem 2rem 2rem;
    text-align: center;
    position: relative;
}
.hero-tag {
    display: inline-block;
    padding: 0.3rem 1rem;
    border: 1px solid rgba(60,196,183,0.4);
    border-radius: 999px;
    font-size: 0.7rem;
    letter-spacing: 0.2em;
    color: #3CC4B7;
    margin-bottom: 1.5rem;
    font-family: 'JetBrains Mono', monospace;
}
.hero-title {
    font-size: clamp(2.5rem, 6vw, 5rem);
    font-weight: 700;
    line-height: 1.05;
    letter-spacing: -0.02em;
    color: #fff;
    margin: 0;
}
.hero-title span {
    background: linear-gradient(135deg, #3CC4B7 0%, #00e5ff 50%, #7b61ff 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}
.hero-sub {
    color: #555;
    font-size: 1rem;
    margin-top: 1rem;
    font-family: 'JetBrains Mono', monospace;
    letter-spacing: 0.05em;
}

/* ── Stats bar ── */
.stats-row {
    display: flex;
    justify-content: center;
    gap: 0;
    border: 1px solid #1a1a1a;
    border-radius: 12px;
    overflow: hidden;
    margin: 2rem auto;
    max-width: 900px;
}
.stat-cell {
    flex: 1;
    padding: 1.2rem 1rem;
    text-align: center;
    border-right: 1px solid #1a1a1a;
    transition: background 0.2s;
}
.stat-cell:last-child { border-right: none; }
.stat-cell:hover { background: #0f0f0f; }
.stat-num {
    font-size: 1.8rem;
    font-weight: 700;
    color: #3CC4B7;
    font-family: 'JetBrains Mono', monospace;
    letter-spacing: -0.02em;
}
.stat-lbl {
    font-size: 0.65rem;
    color: #444;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    margin-top: 0.3rem;
}

/* ── Cards ── */
.cards-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 1px;
    background: #111;
    border: 1px solid #111;
    border-radius: 12px;
    overflow: hidden;
    margin: 0.5rem 0;
}
.card {
    background: #060606;
    padding: 2rem;
    transition: background 0.2s;
    position: relative;
}
.card:hover { background: #0c0c0c; }
.card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    opacity: 0;
    transition: opacity 0.3s;
}
.card:hover::before { opacity: 1; }
.card-1::before { background: linear-gradient(90deg, #3CC4B7, transparent); }
.card-2::before { background: linear-gradient(90deg, #7b61ff, transparent); }
.card-3::before { background: linear-gradient(90deg, #00e5ff, transparent); }

.card-num {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.7rem;
    color: #333;
    letter-spacing: 0.1em;
    margin-bottom: 1.5rem;
}
.card-title {
    font-size: 1.1rem;
    font-weight: 600;
    color: #fff;
    margin-bottom: 0.8rem;
}
.card-desc {
    color: #555;
    font-size: 0.85rem;
    line-height: 1.7;
}
.card-tag {
    display: inline-block;
    margin-top: 1.5rem;
    padding: 0.25rem 0.8rem;
    border-radius: 4px;
    font-size: 0.65rem;
    font-weight: 600;
    letter-spacing: 0.1em;
    font-family: 'JetBrains Mono', monospace;
}
.tag-teal    { background: rgba(60,196,183,0.1);  color: #3CC4B7; }
.tag-purple  { background: rgba(123,97,255,0.1);  color: #7b61ff; }
.tag-cyan    { background: rgba(0,229,255,0.1);   color: #00e5ff; }

/* ── Architecture ── */
.arch {
    background: #0a0a0a;
    border: 1px solid #1a1a1a;
    border-radius: 12px;
    padding: 1.5rem 2rem;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.82rem;
    line-height: 2;
    margin-top: 1rem;
}
.arch-row { display: flex; gap: 1rem; align-items: center; }
.arch-key   { color: #3CC4B7; min-width: 120px; font-weight: 700; }
.arch-arrow { color: #333; }
.arch-val   { color: #888; }

.footer {
    text-align: center;
    padding: 2rem;
    color: #2a2a2a;
    font-size: 0.75rem;
    font-family: 'JetBrains Mono', monospace;
    letter-spacing: 0.1em;
}
</style>
""", unsafe_allow_html=True)

# ── Hero ─────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
    <div class="hero-tag">ALGORITHMIC TRADING SYSTEM · MNQ FUTURES</div>
    <h1 class="hero-title">QUANT<br><span>MATHS</span></h1>
    <p class="hero-sub">Kalman OU · GARCH Regime · Half-Kelly · Apex 50K EOD</p>
</div>
""", unsafe_allow_html=True)

# ── Stats ─────────────────────────────────────────────────────────────
st.markdown("""
<div class="stats-row">
    <div class="stat-cell">
        <div class="stat-num">42%</div>
        <div class="stat-lbl">Win Rate</div>
    </div>
    <div class="stat-cell">
        <div class="stat-num">2.75x</div>
        <div class="stat-lbl">Win / Loss Ratio</div>
    </div>
    <div class="stat-cell">
        <div class="stat-num">~21%</div>
        <div class="stat-lbl">Kelly Fraction</div>
    </div>
    <div class="stat-cell">
        <div class="stat-num">$3K</div>
        <div class="stat-lbl">Apex Target</div>
    </div>
    <div class="stat-cell">
        <div class="stat-num">22d</div>
        <div class="stat-lbl">Challenge Window</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ── Cards ─────────────────────────────────────────────────────────────
st.markdown("""
<div class="cards-grid">
    <div class="card card-1">
        <div class="card-num">01</div>
        <div class="card-title">Etude</div>
        <div class="card-desc">
            Roadmap structurée en 4 niveaux.<br>
            Time Series → CLT → Ergodicity →<br>
            GARCH → HMM → Kalman → Pipeline.
        </div>
        <span class="card-tag tag-teal">6 MODULES</span>
    </div>
    <div class="card card-2">
        <div class="card-num">02</div>
        <div class="card-title">Backtest Kalman OU</div>
        <div class="card-desc">
            Simulation mois par mois sur données<br>
            Databento MNQ 1-min.<br>
            Phase MM · GARCH filter · Reset mensuel.
        </div>
        <span class="card-tag tag-purple">APEX 50K EOD</span>
    </div>
    <div class="card card-3">
        <div class="card-num">03</div>
        <div class="card-title">Live Kalman OU</div>
        <div class="card-desc">
            Signal temps réel via QQQ (yfinance).<br>
            Fair value · Bandes OU ·<br>
            Entry / SL / TP · MM Apex auto.
        </div>
        <span class="card-tag tag-cyan">QQQ → MNQ</span>
    </div>
</div>
""", unsafe_allow_html=True)

# ── Architecture ──────────────────────────────────────────────────────
st.markdown("""
<div class="arch">
    <div class="arch-row"><span class="arch-key">SIGNAL</span><span class="arch-arrow">→</span><span class="arch-val">Kalman OU Mean Reversion — prix hors bande k × sigma_stat</span></div>
    <div class="arch-row"><span class="arch-key">TP</span><span class="arch-arrow">→</span><span class="arch-val">Retour au fair value Kalman</span></div>
    <div class="arch-row"><span class="arch-key">SL</span><span class="arch-arrow">→</span><span class="arch-val">ATR × 1.5 (dynamique, max 15 pts)</span></div>
    <div class="arch-row"><span class="arch-key">FILTRE</span><span class="arch-arrow">→</span><span class="arch-val">GARCH regime — skip HIGH volatility</span></div>
    <div class="arch-row"><span class="arch-key">SIZING</span><span class="arch-arrow">→</span><span class="arch-val">Half-Kelly — 10% du trailing DD restant par trade</span></div>
    <div class="arch-row"><span class="arch-key">DATA</span><span class="arch-arrow">→</span><span class="arch-val">QQQ via yfinance (gratuit) → execution MNQ sur Apex</span></div>
    <div class="arch-row"><span class="arch-key">CHALLENGE</span><span class="arch-arrow">→</span><span class="arch-val">Apex 50K EOD Trail — $3,000 en 1 mois</span></div>
</div>

<div class="footer">← SIDEBAR POUR NAVIGUER &nbsp;·&nbsp; ETUDE &nbsp;·&nbsp; BACKTEST &nbsp;·&nbsp; LIVE →</div>
""", unsafe_allow_html=True)
