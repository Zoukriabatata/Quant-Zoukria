import sqlite3
import pandas as pd
import streamlit as st
from styles import inject as _inject_styles

st.set_page_config(page_title="Quant Maths", page_icon="⚡", layout="wide")
_inject_styles()

# ── Journal stats ─────────────────────────────────────────────────────
JOURNAL_DB       = r"C:\tmp\mnq_journal.db"
CHALLENGE_DD     = 2500.0
CHALLENGE_TARGET = 3000.0

def _load_stats():
    try:
        con = sqlite3.connect(JOURNAL_DB)
        df  = pd.read_sql("SELECT * FROM trades", con)
        con.close()
        if df.empty:
            return dict(n=0, wr=0.0, pnl=0.0, dd_used=0.0, dd_rem=CHALLENGE_DD, prog=0.0, rr=0.0)
        n      = len(df)
        wins   = (df["pnl"] > 0).sum()
        wr     = wins / n * 100
        pnl    = df["pnl"].sum()
        dd_used = abs(df[df["pnl"] < 0]["pnl"].sum())
        dd_rem  = max(0., CHALLENGE_DD - dd_used)
        prog    = min(100., pnl / CHALLENGE_TARGET * 100)
        avg_win  = df[df["pnl"] > 0]["pnl"].mean() if wins > 0 else 0
        avg_loss = abs(df[df["pnl"] < 0]["pnl"].mean()) if (n - wins) > 0 else 1
        rr       = avg_win / avg_loss if avg_loss > 0 else 0
        return dict(n=n, wr=wr, pnl=pnl, dd_used=dd_used, dd_rem=dd_rem, prog=prog, rr=rr)
    except Exception:
        return dict(n=0, wr=0.0, pnl=0.0, dd_used=0.0, dd_rem=CHALLENGE_DD, prog=0.0, rr=0.0)

s = _load_stats()

# ── CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;700&display=swap');

*, *::before, *::after { box-sizing: border-box; }

[data-testid="stAppViewContainer"] {
    background: #060606;
    font-family: 'Space Grotesk', sans-serif;
}
[data-testid="stSidebar"]  { background: #0a0a0a; border-right: 1px solid #1a1a1a; }
[data-testid="stHeader"]   { background: transparent; }
[data-testid="stToolbar"]  { display: none; }
.block-container           { padding-top: 0 !important; max-width: 1100px; }

::-webkit-scrollbar       { width: 4px; }
::-webkit-scrollbar-track { background: #0a0a0a; }
::-webkit-scrollbar-thumb { background: #3CC4B7; border-radius: 2px; }

[data-testid="stSidebarNavLink"] {
    display: block; padding: 0.6rem 1.2rem; margin: 2px 8px;
    border-radius: 6px; font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem; letter-spacing: 0.08em; color: #555 !important;
    text-decoration: none !important; transition: background 0.15s, color 0.15s;
    border: 1px solid transparent;
}
[data-testid="stSidebarNavLink"]:hover {
    background: #111 !important; color: #ccc !important; border-color: #1a1a1a;
}
[data-testid="stSidebarNavLink"][aria-current="page"] {
    background: rgba(60,196,183,0.08) !important;
    color: #3CC4B7 !important; border-color: rgba(60,196,183,0.2);
}

/* ── Hero ── */
.hero {
    padding: 3.5rem 2rem 1.5rem;
    text-align: center;
}
.hero-tag {
    display: inline-block; padding: 0.3rem 1rem;
    border: 1px solid rgba(60,196,183,0.35); border-radius: 999px;
    font-size: 0.65rem; letter-spacing: 0.2em; color: #3CC4B7;
    margin-bottom: 1.5rem; font-family: 'JetBrains Mono', monospace;
}
.hero-title {
    font-size: clamp(2.8rem, 6vw, 5.5rem); font-weight: 700;
    line-height: 1.0; letter-spacing: -0.03em; color: #fff; margin: 0;
}
.hero-title span {
    background: linear-gradient(135deg, #3CC4B7 0%, #00e5ff 50%, #7b61ff 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
}
.hero-sub {
    color: #444; font-size: 0.88rem; margin-top: 1rem;
    font-family: 'JetBrains Mono', monospace; letter-spacing: 0.06em;
}

/* ── Challenge bar ── */
.challenge-wrap {
    max-width: 700px; margin: 1.5rem auto 0;
    background: #0a0a0a; border: 1px solid #1a1a1a;
    border-radius: 10px; padding: 1rem 1.5rem;
}
.challenge-header {
    display: flex; justify-content: space-between;
    font-family: 'JetBrains Mono', monospace; font-size: 0.7rem;
    color: #444; margin-bottom: 0.6rem;
}
.challenge-pct { color: #3CC4B7; font-weight: 700; }
.bar-track {
    background: #111; border-radius: 999px; height: 6px; overflow: hidden;
}
.bar-fill {
    height: 100%; border-radius: 999px;
    background: linear-gradient(90deg, #3CC4B7, #00e5ff);
    transition: width 0.6s ease;
}

/* ── Stats row ── */
.stats-row {
    display: flex; justify-content: center; gap: 0;
    border: 1px solid #1a1a1a; border-radius: 12px; overflow: hidden;
    margin: 1.5rem auto; max-width: 900px;
}
.stat-cell {
    flex: 1; padding: 1.2rem 1rem; text-align: center;
    border-right: 1px solid #1a1a1a; transition: background 0.2s;
}
.stat-cell:last-child { border-right: none; }
.stat-cell:hover { background: #0f0f0f; }
.stat-num {
    font-size: 1.8rem; font-weight: 700; color: #3CC4B7;
    font-family: 'JetBrains Mono', monospace; letter-spacing: -0.02em;
}
.stat-num.green { color: #00ff88; }
.stat-num.red   { color: #ff3366; }
.stat-num.white { color: #ffffff; }
.stat-lbl {
    font-size: 0.62rem; color: #444; letter-spacing: 0.15em;
    text-transform: uppercase; margin-top: 0.3rem;
}
.stat-live {
    font-size: 0.55rem; color: #3CC4B7; font-family: 'JetBrains Mono', monospace;
    letter-spacing: 0.1em; margin-top: 0.2rem;
}

/* ── Section label ── */
.sec-label {
    font-family: 'JetBrains Mono', monospace; font-size: 0.6rem;
    font-weight: 700; letter-spacing: 0.2em; color: #3CC4B7;
    text-transform: uppercase; margin: 2rem 0 0.8rem;
    padding-bottom: 0.4rem; border-bottom: 1px solid #1a1a1a;
}

/* ── Cards ── */
.cards-grid {
    display: grid; grid-template-columns: repeat(3, 1fr);
    gap: 1px; background: #111; border: 1px solid #111;
    border-radius: 12px; overflow: hidden; margin: 0.5rem 0;
}
.card { background: #060606; padding: 1.8rem; transition: background 0.2s; position: relative; }
.card:hover { background: #0d0d0d; }
.card::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px;
    opacity: 0; transition: opacity 0.3s;
}
.card:hover::before { opacity: 1; }
.card-1::before { background: linear-gradient(90deg, #3CC4B7, transparent); }
.card-2::before { background: linear-gradient(90deg, #7b61ff, transparent); }
.card-3::before { background: linear-gradient(90deg, #00e5ff, transparent); }
.card-num { font-family: 'JetBrains Mono', monospace; font-size: 0.65rem; color: #2a2a2a; letter-spacing: 0.1em; margin-bottom: 1.2rem; }
.card-title { font-size: 1rem; font-weight: 600; color: #fff; margin-bottom: 0.6rem; }
.card-desc { color: #555; font-size: 0.82rem; line-height: 1.75; }
.card-tag {
    display: inline-block; margin-top: 1.2rem; padding: 0.2rem 0.7rem;
    border-radius: 4px; font-size: 0.6rem; font-weight: 600;
    letter-spacing: 0.1em; font-family: 'JetBrains Mono', monospace;
}
.tag-teal   { background: rgba(60,196,183,0.1);  color: #3CC4B7; }
.tag-purple { background: rgba(123,97,255,0.1);  color: #7b61ff; }
.tag-cyan   { background: rgba(0,229,255,0.1);   color: #00e5ff; }

/* ── Arch ── */
.arch {
    background: #0a0a0a; border: 1px solid #1a1a1a; border-radius: 12px;
    padding: 1.4rem 1.8rem; font-family: 'JetBrains Mono', monospace;
    font-size: 0.8rem; line-height: 2.1; margin-top: 0.5rem;
}
.arch-row { display: flex; gap: 1rem; align-items: center; }
.arch-key   { color: #3CC4B7; min-width: 110px; font-weight: 700; }
.arch-arrow { color: #2a2a2a; }
.arch-val   { color: #666; }

/* ── DD gauge ── */
.dd-wrap {
    background: #0a0a0a; border: 1px solid #1a1a1a; border-radius: 10px;
    padding: 1rem 1.5rem; margin-top: 1rem;
}
.dd-header {
    display: flex; justify-content: space-between;
    font-family: 'JetBrains Mono', monospace; font-size: 0.68rem; color: #444;
    margin-bottom: 0.5rem;
}
.dd-pct { font-weight: 700; }
.dd-green { color: #00ff88; }
.dd-yellow { color: #ffd600; }
.dd-red { color: #ff3366; }
.bar-track-dd { background: #111; border-radius: 999px; height: 5px; overflow: hidden; }
.bar-fill-green  { height:100%; border-radius:999px; background: linear-gradient(90deg,#ff3366,#ff9100); }

.footer {
    text-align: center; padding: 2rem; color: #1e1e1e;
    font-size: 0.7rem; font-family: 'JetBrains Mono', monospace; letter-spacing: 0.12em;
}
</style>
""", unsafe_allow_html=True)

# ── Hero ─────────────────────────────────────────────────────────────
prog_pct = round(s["prog"], 1)
pnl_sign = "+" if s["pnl"] >= 0 else ""

st.markdown(f"""
<div class="hero">
    <div class="hero-tag">HURST MR · MNQ FUTURES · 4PROPTRADER 50K</div>
    <h1 class="hero-title">QUANT<br><span>MATHS</span></h1>
    <p class="hero-sub">Hurst_MR · HMM Regime · 10% DD Risk · 4PropTrader Challenge</p>
    <div class="challenge-wrap">
        <div class="challenge-header">
            <span>CHALLENGE PROGRESS</span>
            <span class="challenge-pct">{pnl_sign}{s['pnl']:.0f}$ / {CHALLENGE_TARGET:.0f}$ &nbsp;·&nbsp; {prog_pct}%</span>
        </div>
        <div class="bar-track">
            <div class="bar-fill" style="width:{min(prog_pct,100)}%"></div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# ── Stats live ────────────────────────────────────────────────────────
wr_col   = "green" if s["wr"] >= 50 else ("white" if s["n"] == 0 else "red")
pnl_col  = "green" if s["pnl"] >= 0 else "red"
dd_col   = "green" if s["dd_used"] < CHALLENGE_DD * 0.4 else ("yellow" if s["dd_used"] < CHALLENGE_DD * 0.7 else "red")
rr_col   = "green" if s["rr"] >= 1.5 else "white"

wr_disp  = f"{s['wr']:.0f}%" if s["n"] > 0 else "—"
pnl_disp = f"{pnl_sign}{s['pnl']:.0f}$"
dd_disp  = f"{s['dd_rem']:.0f}$"
rr_disp  = f"{s['rr']:.2f}x" if s["n"] > 0 else "—"

st.markdown(f"""
<div class="stats-row">
    <div class="stat-cell">
        <div class="stat-num {wr_col}">{wr_disp}</div>
        <div class="stat-lbl">Win Rate</div>
        <div class="stat-live">{'LIVE · ' + str(s['n']) + ' TRADES' if s['n'] > 0 else 'EN ATTENTE'}</div>
    </div>
    <div class="stat-cell">
        <div class="stat-num {rr_col}">{rr_disp}</div>
        <div class="stat-lbl">Risk / Reward</div>
        <div class="stat-live">AVG WIN / AVG LOSS</div>
    </div>
    <div class="stat-cell">
        <div class="stat-num {pnl_col}">{pnl_disp}</div>
        <div class="stat-lbl">P&L Challenge</div>
        <div class="stat-live">TARGET {CHALLENGE_TARGET:.0f}$</div>
    </div>
    <div class="stat-cell">
        <div class="stat-num {dd_col}">{dd_disp}</div>
        <div class="stat-lbl">DD Restant</div>
        <div class="stat-live">MAX {CHALLENGE_DD:.0f}$</div>
    </div>
    <div class="stat-cell">
        <div class="stat-num white">{s['n']}</div>
        <div class="stat-lbl">Trades</div>
        <div class="stat-live">CHALLENGE TOTAL</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ── DD gauge ──────────────────────────────────────────────────────────
dd_pct_used = min(100., s["dd_used"] / CHALLENGE_DD * 100)
dd_col_cls  = "dd-green" if dd_pct_used < 40 else ("dd-yellow" if dd_pct_used < 70 else "dd-red")

st.markdown(f"""
<div class="dd-wrap">
    <div class="dd-header">
        <span>DRAWDOWN UTILISÉ</span>
        <span class="{dd_col_cls} dd-pct">{s['dd_used']:.0f}$ / {CHALLENGE_DD:.0f}$ &nbsp;·&nbsp; {dd_pct_used:.1f}%</span>
    </div>
    <div class="bar-track-dd">
        <div class="bar-fill-green" style="width:{dd_pct_used}%"></div>
    </div>
</div>
""", unsafe_allow_html=True)

# ── Section pages ─────────────────────────────────────────────────────
st.markdown('<div class="sec-label">Navigation</div>', unsafe_allow_html=True)

st.markdown("""
<div class="cards-grid">
    <div class="card card-1">
        <div class="card-num">01</div>
        <div class="card-title">Étude</div>
        <div class="card-desc">
            Roadmap structurée — fBm, Hurst R/S,<br>
            HMM, GARCH, Z-score.<br>
            Fiches · Formules · Quizz.
        </div>
        <span class="card-tag tag-teal">THÉORIE</span>
    </div>
    <div class="card card-2">
        <div class="card-num">02</div>
        <div class="card-title">Backtest Hurst_MR</div>
        <div class="card-desc">
            5 ans MNQ M1 Databento.<br>
            Walk-forward · HMM filter · Monte Carlo.<br>
            Paramètres validés en production.
        </div>
        <span class="card-tag tag-purple">5 ANS · MNQ M1</span>
    </div>
    <div class="card card-3">
        <div class="card-num">03</div>
        <div class="card-title">Live Signal</div>
        <div class="card-desc">
            Ticks temps réel via dxFeed 4PropTrader.<br>
            Hurst rolling · HMM · Bip + Discord.<br>
            Journal intégré · Stats challenge live.
        </div>
        <span class="card-tag tag-cyan">DXFEED · MNQ</span>
    </div>
</div>
""", unsafe_allow_html=True)

# ── Architecture ──────────────────────────────────────────────────────
st.markdown('<div class="sec-label">Architecture du système</div>', unsafe_allow_html=True)

st.markdown("""
<div class="arch">
    <div class="arch-row"><span class="arch-key">SIGNAL</span><span class="arch-arrow">→</span><span class="arch-val">Hurst R/S rolling &lt; 0.45 + |Z-score| &gt; 3.0σ → Mean Reversion</span></div>
    <div class="arch-row"><span class="arch-key">FILTRE</span><span class="arch-arrow">→</span><span class="arch-val">HMM state ≠ 2 (skip sessions trending fort)</span></div>
    <div class="arch-row"><span class="arch-key">TP</span><span class="arch-arrow">→</span><span class="arch-val">60% retour vers la moyenne (fair value)</span></div>
    <div class="arch-row"><span class="arch-key">SL</span><span class="arch-arrow">→</span><span class="arch-val">0.75 × std (min 3 pts, max 20 pts)</span></div>
    <div class="arch-row"><span class="arch-key">SIZING</span><span class="arch-arrow">→</span><span class="arch-val">10% du DD restant par trade · 1 contrat fixe (phase validation)</span></div>
    <div class="arch-row"><span class="arch-key">DATA</span><span class="arch-arrow">→</span><span class="arch-val">dxFeed 4PropTrader → C:/tmp/mnq_live.json → Streamlit</span></div>
    <div class="arch-row"><span class="arch-key">ALERTE</span><span class="arch-arrow">→</span><span class="arch-val">Bip sonore + Discord push notification (téléphone)</span></div>
    <div class="arch-row"><span class="arch-key">CHALLENGE</span><span class="arch-arrow">→</span><span class="arch-val">4PropTrader 50K · DD max 2 500$ · Target 3 000$</span></div>
</div>
""", unsafe_allow_html=True)

st.markdown('<div class="footer">← SIDEBAR POUR NAVIGUER &nbsp;·&nbsp; ÉTUDE &nbsp;·&nbsp; BACKTEST &nbsp;·&nbsp; LIVE SIGNAL →</div>', unsafe_allow_html=True)
