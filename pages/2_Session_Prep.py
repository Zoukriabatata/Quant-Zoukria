"""
Session Prep — Checklist + Règles + Mindset avant 15h30
"""
import json
import sqlite3
from pathlib import Path
from datetime import datetime
import streamlit as st
import pytz
from streamlit_autorefresh import st_autorefresh
from config import JOURNAL_DB, CHALLENGE_DD, CHALLENGE_TARGET, DAILY_LOSS_LIM

st.set_page_config(page_title="Session Prep", page_icon="🎯", layout="wide")
from styles import inject as _inj; _inj()
st_autorefresh(interval=30_000, key="sp_refresh")  # rafraîchit le countdown toutes les 30s

# ── Config ────────────────────────────────────────────────────────────
PARIS          = pytz.timezone("Europe/Paris")
CHECKLIST_FILE = Path(__file__).parent.parent / ".checklist.json"

# ── Journal stats ─────────────────────────────────────────────────────
def _load_stats():
    try:
        import pandas as pd
        con = sqlite3.connect(JOURNAL_DB)
        df  = pd.read_sql("SELECT * FROM trades", con); con.close()
        if df.empty:
            return dict(n=0, pnl=0.0, dd_used=0.0, dd_rem=CHALLENGE_DD)
        pnl     = df["pnl"].sum()
        dd_used = abs(df[df["pnl"] < 0]["pnl"].sum())
        return dict(n=len(df), pnl=pnl, dd_used=dd_used, dd_rem=max(0., CHALLENGE_DD - dd_used))
    except Exception:
        return dict(n=0, pnl=0.0, dd_used=0.0, dd_rem=CHALLENGE_DD)

# ── Checklist persistence ─────────────────────────────────────────────
def load_checklist():
    try:
        data = json.loads(CHECKLIST_FILE.read_text())
        # Reset si c'est un nouveau jour
        today = datetime.now(PARIS).strftime("%Y-%m-%d")
        if data.get("date") != today:
            return {"date": today, "checked": []}
        return data
    except Exception:
        return {"date": datetime.now(PARIS).strftime("%Y-%m-%d"), "checked": []}

def save_checklist(data):
    try: CHECKLIST_FILE.write_text(json.dumps(data))
    except: pass

# ── CSS page-specific ─────────────────────────────────────────────────
st.markdown("""
<style>
.block-container { padding-top: 1.2rem; max-width: 1100px; }

.ph { padding: 1rem 0 0.8rem; border-bottom: 1px solid #1a1a1a; margin-bottom: 1.5rem; }
.ph-tag { font-family:'JetBrains Mono',monospace; font-size:0.6rem; letter-spacing:0.2em; color:#3CC4B7; text-transform:uppercase; }
.ph-title { font-size:1.8rem; font-weight:700; color:#fff; letter-spacing:-0.02em; margin:.2rem 0 0; }

.sec-label {
    font-family:'JetBrains Mono',monospace; font-size:0.6rem; font-weight:700;
    letter-spacing:0.2em; color:#3CC4B7; text-transform:uppercase;
    margin:1.8rem 0 0.8rem; padding-bottom:0.4rem; border-bottom:1px solid #1a1a1a;
}

.check-item {
    display:flex; align-items:flex-start; gap:0.8rem;
    background:#0a0a0a; border:1px solid #1a1a1a; border-radius:8px;
    padding:0.8rem 1rem; margin:4px 0; transition:border-color 0.15s;
}
.check-item.done { border-color:#3CC4B7; background:rgba(60,196,183,0.04); }
.check-icon { font-size:1rem; flex-shrink:0; margin-top:1px; }
.check-text { font-size:0.88rem; color:#888; line-height:1.5; }
.check-text.done { color:#ccc; }
.check-sub { font-size:0.75rem; color:#444; margin-top:2px; font-family:'JetBrains Mono',monospace; }

.rule-card {
    background:#0a0a0a; border:1px solid #1a1a1a; border-radius:10px;
    padding:1.2rem 1.4rem; margin:6px 0;
}
.rule-num { font-family:'JetBrains Mono',monospace; font-size:0.6rem; color:#333; letter-spacing:0.15em; }
.rule-title { font-size:1rem; font-weight:600; color:#fff; margin:.3rem 0 .4rem; }
.rule-body { font-size:0.85rem; color:#666; line-height:1.7; }

.cond-grid {
    display:grid; grid-template-columns:1fr 1fr; gap:1px;
    background:#111; border:1px solid #111; border-radius:10px; overflow:hidden;
}
.cond-cell {
    background:#0a0a0a; padding:1.1rem 1.2rem;
}
.cond-label { font-family:'JetBrains Mono',monospace; font-size:0.6rem; color:#444; letter-spacing:0.15em; text-transform:uppercase; }
.cond-val { font-size:1.1rem; font-weight:600; color:#fff; margin:.25rem 0 .1rem; }
.cond-hint { font-size:0.75rem; color:#555; }

.mindset-card {
    background:#080808; border-left:3px solid #3CC4B7;
    padding:1rem 1.3rem; border-radius:0 8px 8px 0; margin:6px 0;
}
.mindset-text { font-size:0.88rem; color:#888; line-height:1.8; }
.mindset-text strong { color:#fff; }

.progress-bar-wrap {
    background:#0a0a0a; border:1px solid #1a1a1a; border-radius:10px;
    padding:1rem 1.4rem; margin-bottom:1rem;
}
.prog-row { display:flex; justify-content:space-between; align-items:center; margin-bottom:6px; }
.prog-label { font-family:'JetBrains Mono',monospace; font-size:0.65rem; color:#444; }
.prog-val { font-family:'JetBrains Mono',monospace; font-size:0.75rem; font-weight:700; }
.bar-track { background:#111; border-radius:999px; height:5px; overflow:hidden; }
.bar-fill-teal { height:100%; border-radius:999px; background:linear-gradient(90deg,#3CC4B7,#00e5ff); }
.bar-fill-red  { height:100%; border-radius:999px; background:linear-gradient(90deg,#ff3366,#ff9100); }
</style>
""", unsafe_allow_html=True)

# ── Header + Countdown ───────────────────────────────────────────────
now_paris = datetime.now(PARIS)
s = _load_stats()
cl_data   = load_checklist()

# Calcul countdown vers 15h30
_session_open = now_paris.replace(hour=15, minute=30, second=0, microsecond=0)
_session_close = now_paris.replace(hour=22, minute=0, second=0, microsecond=0)
_in_session = _session_open <= now_paris < _session_close
_before_session = now_paris < _session_open

if _in_session:
    _remaining = _session_close - now_paris
    _h, _rem = divmod(int(_remaining.total_seconds()), 3600)
    _m, _s   = divmod(_rem, 60)
    _countdown_txt = f"SESSION ACTIVE — ferme dans {_h}h{_m:02d}m{_s:02d}s"
    _countdown_col = "#10b981"
    _countdown_badge = "qm-badge--green"
elif _before_session:
    _remaining = _session_open - now_paris
    _h, _rem = divmod(int(_remaining.total_seconds()), 3600)
    _m, _s   = divmod(_rem, 60)
    _countdown_txt = f"Session dans {_h}h{_m:02d}m{_s:02d}s"
    _countdown_col = "#f59e0b" if _remaining.total_seconds() < 1800 else "#94a3b8"
    _countdown_badge = "qm-badge--amber" if _remaining.total_seconds() < 1800 else "qm-badge--blue"
else:
    _countdown_txt = "Session NY terminee — 9h30 demain"
    _countdown_col = "#475569"
    _countdown_badge = "qm-badge--blue"

st.markdown(f"""
<div class="ph" style="display:flex; align-items:flex-end; justify-content:space-between; flex-wrap:wrap; gap:.5rem">
    <div>
        <div class="ph-tag">PRÉPARATION SESSION · MNQ · 4PROPTRADER</div>
        <div class="ph-title">Session Prep</div>
    </div>
    <span class="qm-badge {_countdown_badge}" style="font-size:.72rem; padding:5px 14px; margin-bottom:.6rem">
        {'<span class="qm-live-dot qm-live-dot--green" style="width:6px;height:6px;margin:0 6px 0 0"></span>' if _in_session else ''}
        {_countdown_txt}
    </span>
</div>
""", unsafe_allow_html=True)

# ── KPIs challenge ────────────────────────────────────────────────────
pnl_col  = "#00ff88" if s["pnl"] >= 0 else "#ff3366"
dd_pct   = s["dd_used"] / CHALLENGE_DD * 100
dd_col   = "#00ff88" if dd_pct < 40 else ("#ffd600" if dd_pct < 70 else "#ff3366")
prog_pct = min(100., s["pnl"] / CHALLENGE_TARGET * 100)
daily_max = DAILY_LOSS_LIM

st.markdown(f"""
<div class="progress-bar-wrap">
    <div class="prog-row">
        <span class="prog-label">CHALLENGE PROGRESS</span>
        <span class="prog-val" style="color:{pnl_col}">{s['pnl']:+.0f}$ / {CHALLENGE_TARGET:.0f}$</span>
    </div>
    <div class="bar-track" style="margin-bottom:8px;">
        <div class="bar-fill-teal" style="width:{max(0,prog_pct):.0f}%"></div>
    </div>
    <div class="prog-row">
        <span class="prog-label">DD UTILISÉ</span>
        <span class="prog-val" style="color:{dd_col}">{s['dd_used']:.0f}$ / {CHALLENGE_DD:.0f}$ &nbsp;·&nbsp; {dd_pct:.1f}%</span>
    </div>
    <div class="bar-track">
        <div class="bar-fill-red" style="width:{dd_pct:.0f}%"></div>
    </div>
</div>
""", unsafe_allow_html=True)

# ── Deux colonnes principales ─────────────────────────────────────────
col_left, col_right = st.columns([1.1, 1], gap="large")

with col_left:

    # ── Checklist interactive ─────────────────────────────────────────
    st.markdown('<div class="sec-label">Checklist avant 15h30</div>', unsafe_allow_html=True)

    ITEMS = [
        ("setup",    "15h15 — Ouvre ATAS",
                     "Vérifie que dxFeed prop est connecté (point vert)"),
        ("bridge",   "15h18 — Lance le bridge dxFeed",
                     "Page Demarrage → colle l URL Volumetric → copie la commande → node dxfeed_bridge.js"),
        ("streamlit","15h20 — Lance Streamlit",
                     "streamlit run Accueil.py → ouvre localhost:8501 → Live Signal"),
        ("discord",  "15h22 — Vérifie Discord",
                     "Notifs activées sur téléphone pour le channel MNQ Signal"),
        ("atas_ctx", "15h25 — Contexte ATAS",
                     "Regarde le chart 5min — pas d'actualité macro en cours (FOMC, NFP, CPI ?)"),
        ("hurst_ok", "15h30 — Lis le Hurst H",
                     "H < 0.52 → système actif · H ≥ 0.52 → session observation, pas de trade"),
        ("rules_ok", "15h30 — Rappelle les règles",
                     "1 contrat · max 600$ perte · max 5 trades · SL immédiat après entrée"),
    ]

    checked = set(cl_data.get("checked", []))

    for key, title, subtitle in ITEMS:
        is_done = key in checked
        done_cls = "done" if is_done else ""
        icon = "✅" if is_done else "⬜"
        st.markdown(f"""
        <div class="check-item {done_cls}">
            <span class="check-icon">{icon}</span>
            <div>
                <div class="check-text {done_cls}">{title}</div>
                <div class="check-sub">{subtitle}</div>
            </div>
        </div>""", unsafe_allow_html=True)
        if st.button("Cocher" if not is_done else "Décocher", key=f"chk_{key}",
                     use_container_width=False):
            if is_done: checked.discard(key)
            else: checked.add(key)
            cl_data["checked"] = list(checked)
            save_checklist(cl_data)
            st.rerun()

    n_done = len(checked)
    n_total = len(ITEMS)
    ready_pct = n_done / n_total * 100
    ready_col = "#00ff88" if n_done == n_total else ("#ffd600" if n_done >= 4 else "#ff3366")
    ready_txt = "PRÊT À TRADER" if n_done == n_total else f"{n_done}/{n_total} COMPLÉTÉS"

    st.markdown(f"""
    <div style="margin-top:1rem; background:#0a0a0a; border:1px solid #1a1a1a;
                border-radius:10px; padding:1rem 1.4rem;">
        <div style="display:flex; justify-content:space-between; margin-bottom:6px;">
            <span style="font-family:'JetBrains Mono',monospace;font-size:0.65rem;color:#444;">PRÉPARATION</span>
            <span style="font-family:'JetBrains Mono',monospace;font-size:0.75rem;
                         font-weight:700;color:{ready_col}">{ready_txt}</span>
        </div>
        <div class="bar-track">
            <div class="bar-fill-teal" style="width:{ready_pct:.0f}%"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if st.button("🔄 Reset checklist", key="reset_cl"):
        cl_data["checked"] = []
        save_checklist(cl_data)
        st.rerun()

with col_right:

    # ── Conditions de trading ─────────────────────────────────────────
    st.markdown('<div class="sec-label">Conditions du jour</div>', unsafe_allow_html=True)

    st.markdown("""
    <div class="cond-grid">
        <div class="cond-cell">
            <div class="cond-label">Seuil Hurst</div>
            <div class="cond-val" style="color:#3CC4B7;">H &lt; 0.52</div>
            <div class="cond-hint">Session MR → trade autorisé</div>
        </div>
        <div class="cond-cell">
            <div class="cond-label">Z-score entrée</div>
            <div class="cond-val" style="color:#3CC4B7;">|Z| &gt; 3.25σ</div>
            <div class="cond-hint">Prix suffisamment étiré</div>
        </div>
        <div class="cond-cell">
            <div class="cond-label">Lookback Z</div>
            <div class="cond-val" style="color:#fff;">30 barres</div>
            <div class="cond-hint">Fenêtre moyenne / std</div>
        </div>
        <div class="cond-cell">
            <div class="cond-label">Session</div>
            <div class="cond-val" style="color:#fff;">15h30 → 22h00</div>
            <div class="cond-hint">Paris · RTH NY</div>
        </div>
        <div class="cond-cell">
            <div class="cond-label">Skip ouverture</div>
            <div class="cond-val" style="color:#ffd600;">5 barres</div>
            <div class="cond-hint">Pas de trade avant 15h35</div>
        </div>
        <div class="cond-cell">
            <div class="cond-label">Max trades/jour</div>
            <div class="cond-val" style="color:#ffd600;">5</div>
            <div class="cond-hint">Après 5 trades → stop</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Règles MM ──────────────────────────────────────────────────────
    st.markdown('<div class="sec-label">Money Management — Phase 1</div>', unsafe_allow_html=True)

    dd_rem_col = "#00ff88" if s["dd_rem"] > CHALLENGE_DD * 0.6 else ("#ffd600" if s["dd_rem"] > CHALLENGE_DD * 0.3 else "#ff3366")

    st.markdown(f"""
    <div class="rule-card">
        <div class="rule-num">01</div>
        <div class="rule-title">1 contrat MNQ — fixe</div>
        <div class="rule-body">Phase validation. Tu ne scales pas avant 10 trades loggués avec résultats cohérents.</div>
    </div>
    <div class="rule-card">
        <div class="rule-num">02</div>
        <div class="rule-title">Perte max journalière : <span style="color:#ff3366">600$</span></div>
        <div class="rule-body">Si tu perds 600$ dans la session → tu fermes tout immédiatement. Tu ne retrades pas aujourd'hui.</div>
    </div>
    <div class="rule-card">
        <div class="rule-num">03</div>
        <div class="rule-title">SL immédiat après l'entrée</div>
        <div class="rule-body">Tu n'es jamais dans le marché sans stop. L'ordre SL est posé dans la seconde qui suit ton entrée.</div>
    </div>
    <div class="rule-card">
        <div class="rule-num">04</div>
        <div class="rule-title">DD restant : <span style="color:{dd_rem_col}">{s['dd_rem']:.0f}$</span></div>
        <div class="rule-body">10% du DD restant = risque max par trade. Aujourd'hui : max <b style="color:{dd_rem_col}">{s['dd_rem']*0.10:.0f}$</b> / trade.</div>
    </div>
    """, unsafe_allow_html=True)

    # ── Mindset ────────────────────────────────────────────────────────
    st.markdown('<div class="sec-label">Mindset — les 3 absolus</div>', unsafe_allow_html=True)

    st.markdown("""
    <div class="mindset-card">
        <div class="mindset-text">
            <strong>1. Tu ne trades pas le filtre.</strong><br>
            Si H ≥ 0.52 → pas de trade. Même si le prix a l'air parfait. Même si tu as raté hier.
            Le filtre est là précisément pour les situations où tu veux forcer.
        </div>
    </div>
    <div class="mindset-card">
        <div class="mindset-text">
            <strong>2. Tu ne modifies pas le SL.</strong><br>
            Une fois posé, le SL ne bouge pas. Élargir un SL en live = transformer une perte gérée
            en perte incontrôlée. C'est le début de la fin.
        </div>
    </div>
    <div class="mindset-card">
        <div class="mindset-text">
            <strong>3. Tu trades le signal, pas l'émotion.</strong><br>
            Bip → ATAS → entrée → SL → attente. C'est tout.
            Pas d'analyse en cours de trade. Pas de sortie anticipée sur "feeling".
            Le backtest a été validé sur 5 ans — fais confiance au système.
        </div>
    </div>
    """, unsafe_allow_html=True)

# ── Footer ─────────────────────────────────────────────────────────────
st.markdown(f"""
<div style="margin-top:2rem; text-align:center; font-family:'JetBrains Mono',monospace;
            font-size:0.65rem; color:#1e1e1e; letter-spacing:0.1em;">
    {now_paris.strftime('%A %d %B %Y · %H:%M')} Paris &nbsp;·&nbsp;
    {'⚡ SESSION ACTIVE' if 15*60+30 <= now_paris.hour*60+now_paris.minute <= 22*60 else '⏳ Avant session'}
</div>
""", unsafe_allow_html=True)
