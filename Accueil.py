import os
import sqlite3
from pathlib import Path
import pandas as pd
import streamlit as st
import streamlit.components.v1 as _components
from styles import inject as _inject_styles, count_up_stats
from config import JOURNAL_DB, CHALLENGE_DD, CHALLENGE_TARGET

st.set_page_config(page_title="Quant Maths", page_icon="⚡", layout="wide")
_inject_styles()

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

# ── CSS page-specific ─────────────────────────────────────────────────
st.markdown("""
<style>
.block-container { padding-top: 0 !important; max-width: 1100px; }

/* ── Hero ── */
.hero { padding: 3rem 1.5rem 1.2rem; text-align: center; }
.hero-tag {
    display: inline-flex; align-items: center; gap: 8px;
    padding: .32rem 1rem;
    border: 1px solid var(--border-active); border-radius: var(--r-pill);
    font-size: .64rem; letter-spacing: .18em; color: var(--accent-cyan);
    margin-bottom: 1.4rem; font-family: 'JetBrains Mono',monospace;
    background: rgba(59,130,246,0.06);
}
.hero-title {
    font-size: clamp(2.8rem,6vw,5.2rem); font-weight: 700;
    line-height: 1.0; letter-spacing: -0.03em;
    color: var(--text-primary); margin: 0;
}
.hero-title span {
    background: var(--grad-primary);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
}
.hero-sub {
    color: var(--text-muted); font-size: .85rem; margin-top: 1rem;
    font-family: 'JetBrains Mono',monospace; letter-spacing: .06em;
}

/* ── Challenge bar ── */
.challenge-wrap {
    max-width: 680px; margin: 1.4rem auto 0;
    background: var(--bg-surface); border: 1px solid var(--border-default);
    border-radius: var(--r-lg); padding: 1rem 1.5rem;
    box-shadow: var(--shadow-card);
}
.challenge-header {
    display: flex; justify-content: space-between;
    font-family: 'JetBrains Mono',monospace; font-size: .7rem;
    color: var(--text-muted); margin-bottom: .6rem;
}
.challenge-pct { color: var(--accent-cyan); font-weight: 700; }
.bar-track {
    background: var(--bg-elevated); border-radius: var(--r-pill); height: 6px; overflow: hidden;
}
.bar-fill {
    height: 100%; border-radius: var(--r-pill);
    background: var(--grad-primary); transition: width .6s ease;
}

/* ── Stats row ── */
.stats-row {
    display: flex; justify-content: center; gap: 0;
    border: 1px solid var(--border-default); border-radius: var(--r-lg);
    overflow: hidden; margin: 1.2rem auto; max-width: 920px;
    box-shadow: var(--shadow-card);
}
.stat-cell {
    flex: 1; padding: 1.2rem 1rem; text-align: center;
    border-right: 1px solid var(--border-subtle);
    background: var(--bg-surface); transition: var(--t-fast);
}
.stat-cell:last-child { border-right: none; }
.stat-cell:hover { background: var(--bg-elevated); }
.stat-num {
    font-size: 1.8rem; font-weight: 700; color: var(--accent-cyan);
    font-family: 'JetBrains Mono',monospace; letter-spacing: -0.02em;
}
.stat-num.green { color: var(--accent-green); }
.stat-num.red   { color: var(--accent-red);   }
.stat-num.white { color: var(--text-primary);  }
.stat-lbl {
    font-size: .62rem; color: var(--text-muted); letter-spacing: .15em;
    text-transform: uppercase; margin-top: .3rem;
}
.stat-live {
    font-size: .55rem; color: var(--accent-cyan);
    font-family: 'JetBrains Mono',monospace; letter-spacing: .1em; margin-top: .2rem;
}

/* ── Cards ── */
.cards-grid {
    display: grid; grid-template-columns: repeat(3,1fr);
    gap: 12px; margin: .5rem 0;
}
.card {
    background: var(--bg-glass);
    backdrop-filter: blur(12px) saturate(180%);
    border: 1px solid var(--border-default);
    border-radius: var(--r-lg); padding: 1.8rem;
    box-shadow: var(--shadow-card);
    background-image: var(--grad-surface);
    transition: var(--t-normal); position: relative; overflow: hidden;
}
.card::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px;
    border-radius: var(--r-lg) var(--r-lg) 0 0;
}
.card-1::before { background: var(--grad-primary); }
.card-2::before { background: linear-gradient(135deg,#8b5cf6,#3b82f6); }
.card-3::before { background: var(--grad-green); }
.card:hover { border-color: var(--border-active); box-shadow: var(--shadow-card),var(--shadow-glow); transform: translateY(-3px); }
.card-num {
    font-family: 'JetBrains Mono',monospace; font-size: .62rem;
    color: var(--text-muted); letter-spacing: .12em; margin-bottom: 1rem;
    opacity: .5;
}
.card-title { font-size: 1rem; font-weight: 600; color: var(--text-primary); margin-bottom: .55rem; }
.card-desc { color: var(--text-muted); font-size: .82rem; line-height: 1.75; }
.card-tag {
    display: inline-flex; align-items: center; margin-top: 1.2rem;
    padding: .25rem .75rem; border-radius: var(--r-pill);
    font-size: .6rem; font-weight: 600; letter-spacing: .08em;
    font-family: 'JetBrains Mono',monospace;
    border: 1px solid transparent;
}
.tag-teal   { background:rgba(6,182,212,0.12);  color:#67e8f9; border-color:rgba(6,182,212,0.25); }
.tag-purple { background:rgba(139,92,246,0.12); color:#c4b5fd; border-color:rgba(139,92,246,0.25); }
.tag-cyan   { background:rgba(59,130,246,0.12); color:#93c5fd; border-color:rgba(59,130,246,0.25); }

/* ── Arch ── */
.arch {
    background: var(--bg-surface); border: 1px solid var(--border-default);
    border-radius: var(--r-lg); padding: 1.4rem 1.8rem;
    font-family: 'JetBrains Mono',monospace; font-size: .8rem; line-height: 2.1;
    margin-top: .5rem; box-shadow: var(--shadow-card);
}
.arch-row { display: flex; gap: 1rem; align-items: center; }
.arch-key   { color: var(--accent-cyan); min-width: 110px; font-weight: 700; }
.arch-arrow { color: var(--border-default); }
.arch-val   { color: var(--text-muted); }

/* ── DD gauge ── */
.dd-wrap {
    background: var(--bg-surface); border: 1px solid var(--border-default);
    border-radius: var(--r-lg); padding: 1rem 1.5rem; margin-top: 1rem;
    box-shadow: var(--shadow-card);
}
.dd-header {
    display: flex; justify-content: space-between;
    font-family: 'JetBrains Mono',monospace; font-size: .68rem;
    color: var(--text-muted); margin-bottom: .5rem;
}
.dd-pct { font-weight: 700; }
.dd-green  { color: var(--accent-green); }
.dd-yellow { color: var(--accent-amber); }
.dd-red    { color: var(--accent-red);   }
.bar-track-dd { background: var(--bg-elevated); border-radius: var(--r-pill); height: 5px; overflow: hidden; }
.bar-fill-dd  { height:100%; border-radius:var(--r-pill); background: var(--grad-red); }

.footer {
    text-align: center; padding: 2rem; color: var(--border-default);
    font-size: .7rem; font-family: 'JetBrains Mono',monospace; letter-spacing: .12em;
}
</style>
""", unsafe_allow_html=True)

# ── Banner Cloud ─────────────────────────────────────────────────────
if not Path(JOURNAL_DB).exists():
    st.markdown("""
    <div style="background:rgba(60,196,183,0.06);border:1px solid rgba(60,196,183,0.2);
         border-radius:8px;padding:.6rem 1.1rem;margin-bottom:.5rem;
         font-family:'JetBrains Mono',monospace;font-size:.72rem;color:#3CC4B7">
        📡 Mode Cloud — stats challenge en attente de connexion locale
        &nbsp;<span style="color:#333">|</span>&nbsp;
        <span style="color:#444">Configurer <code>JOURNAL_DB</code> dans les secrets pour persister les trades</span>
    </div>
    """, unsafe_allow_html=True)

# ── Hero ─────────────────────────────────────────────────────────────
prog_pct = round(s["prog"], 1)
pnl_sign = "+" if s["pnl"] >= 0 else ""

st.markdown(f"""
<div class="hero anim-fade-up">
    <div class="hero-tag">
        <span class="qm-live-dot qm-live-dot--green"></span>
        HURST MR · MNQ FUTURES · 4PROPTRADER 50K
    </div>
    <h1 class="hero-title">QUANT<br><span>MATHS</span></h1>
    <p class="hero-sub">Hurst_MR · K=3.25σ · Walk-Forward Validated · 4PropTrader Challenge</p>
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

# ── Stats live (animated count-up) ───────────────────────────────────
_wr_color  = "#10b981" if s["wr"] >= 50 else ("#f1f5f9" if s["n"] == 0 else "#ef4444")
_pnl_color = "#10b981" if s["pnl"] >= 0 else "#ef4444"
_dd_color  = "#10b981" if s["dd_used"] < CHALLENGE_DD * 0.4 else ("#f59e0b" if s["dd_used"] < CHALLENGE_DD * 0.7 else "#ef4444")
_rr_color  = "#10b981" if s["rr"] >= 1.5 else "#f1f5f9"

_cu_stats = [
    {
        "value":    round(s["wr"], 1) if s["n"] > 0 else 0,
        "label":    "Win Rate",
        "suffix":   "%",
        "decimals": 1,
        "color":    _wr_color,
        "sub":      f"LIVE · {s['n']} TRADES" if s["n"] > 0 else "EN ATTENTE",
        "static":   s["n"] == 0,
    },
    {
        "value":    round(s["rr"], 2) if s["n"] > 0 else 0,
        "label":    "Risk / Reward",
        "suffix":   "x",
        "decimals": 2,
        "color":    _rr_color,
        "sub":      "AVG WIN / AVG LOSS",
        "static":   s["n"] == 0,
    },
    {
        "value":    abs(round(s["pnl"])),
        "label":    "P&L Challenge",
        "prefix":   ("+" if s["pnl"] >= 0 else "-"),
        "suffix":   "$",
        "decimals": 0,
        "color":    _pnl_color,
        "sub":      f"TARGET {CHALLENGE_TARGET:.0f}$",
    },
    {
        "value":    round(s["dd_rem"]),
        "label":    "DD Restant",
        "suffix":   "$",
        "decimals": 0,
        "color":    _dd_color,
        "sub":      f"MAX {CHALLENGE_DD:.0f}$",
    },
    {
        "value":    s["n"],
        "label":    "Trades",
        "decimals": 0,
        "color":    "#f1f5f9",
        "sub":      "CHALLENGE TOTAL",
    },
]
_components.html(count_up_stats(_cu_stats), height=115, scrolling=False)

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
        <div class="bar-fill-dd" style="width:{dd_pct_used}%"></div>
    </div>
</div>
""", unsafe_allow_html=True)

# ── Section pages ─────────────────────────────────────────────────────
st.markdown('<div class="sec-label">Navigation</div>', unsafe_allow_html=True)

st.markdown("""
<div class="cards-grid">
    <div class="card card-1 anim-fade-up anim-stagger-1">
        <div class="card-num">01 — FORMATION</div>
        <div class="card-title">📚 Étude</div>
        <div class="card-desc">
            Roadmap structurée — fBm, Hurst R/S,<br>
            HMM, GARCH, Z-score.<br>
            Fiches · Formules · Visualisations.
        </div>
        <span class="card-tag tag-teal">THÉORIE QUANTITATIVE</span>
    </div>
    <div class="card card-2 anim-fade-up anim-stagger-2">
        <div class="card-num">02 — RECHERCHE</div>
        <div class="card-title">📊 Backtest Hurst_MR</div>
        <div class="card-desc">
            5 ans MNQ M1 Databento.<br>
            Walk-forward · PF 2.03 · Sharpe 2.50.<br>
            Validé hors-sample sur 8 fenêtres OOS.
        </div>
        <span class="card-tag tag-purple">5 ANS · WALK-FORWARD ✓</span>
    </div>
    <div class="card card-3 anim-fade-up anim-stagger-3">
        <div class="card-num">03 — EXÉCUTION</div>
        <div class="card-title">⚡ Live Signal</div>
        <div class="card-desc">
            Ticks temps réel via dxFeed 4PropTrader.<br>
            Hurst rolling · Z-score · Discord push.<br>
            Journal intégré · Stats challenge live.
        </div>
        <span class="card-tag tag-cyan">DXFEED · TEMPS RÉEL</span>
    </div>
</div>
""", unsafe_allow_html=True)

# ── Architecture ──────────────────────────────────────────────────────
st.markdown('<div class="sec-label">Architecture du système</div>', unsafe_allow_html=True)

st.markdown("""
<div class="arch">
    <div class="arch-row"><span class="arch-key">SIGNAL</span><span class="arch-arrow">→</span><span class="arch-val">Hurst R/S rolling &lt; 0.52 + |Z-score| &gt; 3.25σ → Mean Reversion</span></div>
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
