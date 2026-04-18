"""
Apex Compliance Dashboard — Compte $50K EOD
Suivi en temps réel de toutes les règles Apex Trader Funding.
Évite toute infraction avant qu'elle se produise.
"""
import sqlite3
import json
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from config import (
    JOURNAL_DB,
    APEX_ACCOUNT_SIZE, APEX_TRAILING_DD, APEX_DAILY_LIMIT,
    APEX_PROFIT_TARGET, APEX_SAFETY_NET, APEX_SAFETY_NET_FLOOR,
    APEX_MAX_CONTRACTS_EVAL, APEX_MAX_CONTRACTS_PA_START, APEX_MAX_CONTRACTS_PA_FULL,
    APEX_CONSISTENCY_PCT, APEX_PAYOUT_MIN_DAYS, APEX_PAYOUT_QUAL_DAYS,
    APEX_PAYOUT_QUAL_MIN, APEX_PAYOUT_MIN_AMOUNT, APEX_EVAL_DAYS_MAX,
    APEX_PAYOUT_LADDER,
)

from styles import inject as _inj; _inj()

ET    = ZoneInfo("America/New_York")
PARIS = ZoneInfo("Europe/Paris")

# ═══════════════════════════════════════════════════════════════════════
# CSS
# ═══════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
.block-container { padding-top:1.2rem; max-width:1280px; }

.rule-card {
    background: var(--bg-surface);
    border: 1px solid var(--border-default);
    border-radius: 10px;
    padding: .85rem 1.1rem;
    margin-bottom: .5rem;
    display: flex; align-items: center; gap: .75rem;
    font-family: 'JetBrains Mono', monospace; font-size: .78rem;
}
.rule-ok   { border-left: 3px solid var(--accent-green); }
.rule-warn { border-left: 3px solid var(--accent-amber); }
.rule-bad  { border-left: 3px solid var(--accent-red);   background: rgba(239,68,68,.06); }
.rule-info { border-left: 3px solid var(--accent-cyan);  }

.rule-icon { font-size: 1rem; min-width: 1.2rem; text-align:center; }
.rule-label { color: var(--text-secondary); flex:1; }
.rule-val   { color: var(--text-primary); font-weight:600; }

.phase-banner {
    display:inline-flex; align-items:center; gap:.5rem;
    padding:.3rem 1rem; border-radius:99px;
    font-family:'JetBrains Mono',monospace; font-size:.7rem; font-weight:700;
    letter-spacing:.1em; text-transform:uppercase; margin-bottom:1rem;
}
.phase-eval { background:rgba(59,130,246,.12); border:1px solid rgba(59,130,246,.4); color:#3b82f6; }
.phase-pa   { background:rgba(16,185,129,.12); border:1px solid rgba(16,185,129,.4); color:#10b981; }

.payout-row {
    display:flex; align-items:center; gap:.6rem;
    padding:.5rem .8rem; border-radius:8px; margin-bottom:.3rem;
    font-family:'JetBrains Mono',monospace; font-size:.75rem;
}
.payout-current { background:rgba(59,130,246,.1); border:1px solid rgba(59,130,246,.3); }
.payout-done    { background:rgba(16,185,129,.06); color:var(--text-muted); }
.payout-future  { color:var(--text-muted); }

.metric-big {
    background:var(--bg-surface); border:1px solid var(--border-default);
    border-radius:12px; padding:1rem 1.2rem; text-align:center;
}
.metric-big .val  { font-size:1.6rem; font-weight:700; font-family:'JetBrains Mono',monospace; }
.metric-big .lbl  { font-size:.65rem; color:var(--text-muted); letter-spacing:.1em;
                    font-family:'JetBrains Mono',monospace; text-transform:uppercase; margin-top:.2rem; }
.metric-big .sub  { font-size:.7rem; color:var(--text-secondary); font-family:'JetBrains Mono',monospace; margin-top:.3rem; }

.section-title {
    font-family:'JetBrains Mono',monospace; font-size:.65rem; letter-spacing:.18em;
    text-transform:uppercase; color:var(--text-muted); margin:.6rem 0 .5rem;
    border-bottom:1px solid var(--border-subtle); padding-bottom:.3rem;
}
.alert-box {
    border-radius:10px; padding:.8rem 1.1rem; margin-bottom:.8rem;
    font-family:'JetBrains Mono',monospace; font-size:.78rem; line-height:1.8;
}
.alert-red    { background:rgba(239,68,68,.08);  border:1px solid rgba(239,68,68,.3);  color:#ef4444; }
.alert-amber  { background:rgba(245,158,11,.08); border:1px solid rgba(245,158,11,.3); color:#f59e0b; }
.alert-green  { background:rgba(16,185,129,.08); border:1px solid rgba(16,185,129,.3); color:#10b981; }
.alert-cyan   { background:rgba(6,182,212,.08);  border:1px solid rgba(6,182,212,.3);  color:#06b6d4; }
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════
# STATE DB
# ═══════════════════════════════════════════════════════════════════════
def _get_state_db():
    con = sqlite3.connect(JOURNAL_DB)
    con.execute("""
        CREATE TABLE IF NOT EXISTS apex_state (
            key   TEXT PRIMARY KEY,
            value TEXT
        )""")
    con.commit()
    return con

def _state_get(key: str, default=None):
    try:
        con = _get_state_db()
        row = con.execute("SELECT value FROM apex_state WHERE key=?", (key,)).fetchone()
        con.close()
        return row[0] if row else default
    except Exception:
        return default

def _state_set(key: str, value):
    try:
        con = _get_state_db()
        con.execute("INSERT OR REPLACE INTO apex_state (key,value) VALUES (?,?)", (key, str(value)))
        con.commit(); con.close()
    except Exception:
        pass

# ═══════════════════════════════════════════════════════════════════════
# JOURNAL DATA
# ═══════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=15, show_spinner=False)
def _load_trades() -> pd.DataFrame:
    try:
        con = sqlite3.connect(JOURNAL_DB)
        df = pd.read_sql("SELECT * FROM trades ORDER BY date ASC, time_ny ASC", con)
        con.close()
        if df.empty:
            return pd.DataFrame()
        df["date"] = pd.to_datetime(df["date"]).dt.date
        return df
    except Exception:
        return pd.DataFrame()

def _compute_metrics(df: pd.DataFrame, last_payout_date=None, last_payout_profit=0.0):
    """Calcule toutes les métriques depuis le journal."""
    now_et = datetime.now(ET)
    today  = now_et.date()

    # ── P&L global ──
    total_pnl   = df["pnl"].sum() if not df.empty else 0.0
    current_bal = APEX_ACCOUNT_SIZE + total_pnl

    # ── P&L aujourd'hui ──
    today_pnl = 0.0
    if not df.empty:
        today_df  = df[df["date"] == today]
        today_pnl = today_df["pnl"].sum() if not today_df.empty else 0.0

    # ── Trailing drawdown EOD ──
    mll_floor = APEX_ACCOUNT_SIZE - APEX_TRAILING_DD  # 48000
    safety_locked = False

    if not df.empty:
        daily = df.groupby("date")["pnl"].sum().sort_index()
        running = APEX_ACCOUNT_SIZE
        for d, pnl in daily.items():
            if d >= today:
                break  # floor ne se recalcule qu'au EOD — pas pour aujourd'hui
            running += pnl
            if not safety_locked:
                new_floor = running - APEX_TRAILING_DD
                if new_floor > mll_floor:
                    mll_floor = new_floor
                if running >= APEX_SAFETY_NET:
                    mll_floor    = APEX_SAFETY_NET_FLOOR
                    safety_locked = True

    buffer      = current_bal - mll_floor
    buffer_pct  = (buffer / APEX_TRAILING_DD) * 100

    # ── Daily loss used ──
    daily_loss_used = abs(min(today_pnl, 0))
    daily_loss_rem  = max(0, APEX_DAILY_LIMIT - daily_loss_used)

    # ── Eval progress ──
    eval_progress_pct = min(100, max(0, total_pnl / APEX_PROFIT_TARGET * 100))

    # ── Safety net progress ──
    sn_progress = min(100, max(0, (current_bal - APEX_ACCOUNT_SIZE) /
                               (APEX_SAFETY_NET - APEX_ACCOUNT_SIZE) * 100)) if not safety_locked else 100

    # ── Trading days (distinct dates with at least 1 trade) ──
    trading_days = df["date"].nunique() if not df.empty else 0

    # ── PA: consistance + payout depuis dernier payout ──
    if last_payout_date and not df.empty:
        lpd = pd.to_datetime(last_payout_date).date() if isinstance(last_payout_date, str) else last_payout_date
        since_df = df[df["date"] > lpd]
    else:
        since_df = df

    profit_since_payout = since_df["pnl"].sum() if not since_df.empty else 0.0
    best_day_since = 0.0
    qual_days = 0
    trading_days_since = 0

    if not since_df.empty:
        daily_since = since_df.groupby("date")["pnl"].sum()
        best_day_since    = daily_since.max()
        qual_days         = (daily_since >= APEX_PAYOUT_QUAL_MIN).sum()
        trading_days_since = daily_since.count()

    consistency_pct = (best_day_since / profit_since_payout * 100) if profit_since_payout > 0 else 0.0
    consistency_ok  = (consistency_pct < APEX_CONSISTENCY_PCT * 100) if profit_since_payout > 0 else True

    return dict(
        total_pnl        = total_pnl,
        current_bal      = current_bal,
        today_pnl        = today_pnl,
        mll_floor        = mll_floor,
        safety_locked    = safety_locked,
        buffer           = buffer,
        buffer_pct       = buffer_pct,
        daily_loss_used  = daily_loss_used,
        daily_loss_rem   = daily_loss_rem,
        eval_progress_pct= eval_progress_pct,
        sn_progress      = sn_progress,
        trading_days     = trading_days,
        profit_since_payout   = profit_since_payout,
        best_day_since        = best_day_since,
        qual_days             = qual_days,
        trading_days_since    = trading_days_since,
        consistency_pct       = consistency_pct,
        consistency_ok        = consistency_ok,
    )

# ═══════════════════════════════════════════════════════════════════════
# PAGE
# ═══════════════════════════════════════════════════════════════════════

# ── Header ────────────────────────────────────────────────────────────
st.markdown("""
<div class="ph anim-fade-up">
  <div class="ph-tag">APEX TRADER FUNDING · $50K EOD</div>
  <div class="ph-title">Compliance Dashboard</div>
  <div class="ph-sub" style="font-family:'JetBrains Mono',monospace;font-size:.8rem;color:var(--text-muted)">
    Suivi temps réel de toutes les règles · Zéro infraction involontaire
  </div>
</div>""", unsafe_allow_html=True)

# ── Phase selector ────────────────────────────────────────────────────
saved_phase = _state_get("phase", "eval")
col_ph, col_eval_start, col_payout_n, col_spacer = st.columns([1.5, 1.5, 1.5, 5])

with col_ph:
    phase = st.selectbox("Phase", ["eval", "pa"],
                         index=0 if saved_phase == "eval" else 1,
                         format_func=lambda x: "EVALUATION" if x == "eval" else "FUNDED (PA)",
                         key="phase_sel", label_visibility="collapsed")
    if phase != saved_phase:
        _state_set("phase", phase)

is_pa = (phase == "pa")

banner_cls  = "phase-pa" if is_pa else "phase-eval"
banner_txt  = "FUNDED · Performance Account" if is_pa else "EVALUATION · Challenge en cours"
banner_icon = "✦" if is_pa else "◈"
st.markdown(f'<div class="phase-banner {banner_cls}">{banner_icon} {banner_txt}</div>', unsafe_allow_html=True)

# ── Eval start date ──
with col_eval_start:
    if not is_pa:
        eval_start_saved = _state_get("eval_start_date", str(date.today()))
        try:
            eval_start_val = date.fromisoformat(eval_start_saved)
        except Exception:
            eval_start_val = date.today()
        eval_start = st.date_input("Début éval", value=eval_start_val, key="eval_start")
        if str(eval_start) != eval_start_saved:
            _state_set("eval_start_date", str(eval_start))
    else:
        eval_start = None

# ── Payout count (PA) ──
with col_payout_n:
    if is_pa:
        payout_count = st.number_input("Payout #", min_value=0, max_value=20,
                                       value=int(_state_get("payout_count", "0")),
                                       step=1, key="payout_count_inp")
        if payout_count != int(_state_get("payout_count", "0")):
            _state_set("payout_count", payout_count)

        last_payout_date_saved = _state_get("last_payout_date", "")
        try:
            lpd_val = date.fromisoformat(last_payout_date_saved) if last_payout_date_saved else None
        except Exception:
            lpd_val = None
    else:
        payout_count = 0
        lpd_val = None

# ── Load data ──────────────────────────────────────────────────────────
df = _load_trades()
m  = _compute_metrics(df, last_payout_date=lpd_val, last_payout_profit=0)

now_et    = datetime.now(ET)
now_paris = datetime.now(PARIS)
# Règle personnelle : fermeture obligatoire à 21h59 Paris (= 15h59 NY)
# 1 minute de marge avant la fin de session 22h00 Paris, bien avant le deadline Apex 16h59 ET
close_today = now_paris.replace(hour=21, minute=59, second=0, microsecond=0)
mins_to_close = int((close_today - now_paris).total_seconds() / 60)

# ═══════════════════════════════════════════════════════════════════════
# ALERTS — les choses urgentes en premier
# ═══════════════════════════════════════════════════════════════════════

# KO Alert
if m["current_bal"] <= m["mll_floor"] + 100:
    st.markdown(f"""
    <div class="alert-box alert-red">
        ⚠️ <b>DANGER — KNOCK-OUT IMMINENT</b><br>
        Balance ${m['current_bal']:,.0f} · Floor ${m['mll_floor']:,.0f} · Buffer ${m['buffer']:,.0f}
    </div>""", unsafe_allow_html=True)
elif m["buffer"] < 500:
    st.markdown(f"""
    <div class="alert-box alert-amber">
        ⚠ Buffer critique : ${m['buffer']:,.0f} restant avant knock-out
    </div>""", unsafe_allow_html=True)

# Daily limit alert
if m["daily_loss_used"] >= APEX_DAILY_LIMIT * 0.8:
    st.markdown(f"""
    <div class="alert-box alert-amber">
        ⚠ Daily Loss Limit : ${m['daily_loss_used']:,.0f} utilisés / ${APEX_DAILY_LIMIT:,.0f}
        — ${m['daily_loss_rem']:,.0f} restants. Stop trading si atteint.
    </div>""", unsafe_allow_html=True)

# Time alert
if 0 < mins_to_close <= 15:
    st.markdown(f"""
    <div class="alert-box alert-red">
        ⏱ <b>{mins_to_close} minutes</b> avant 21h59 Paris — Ferme TOUTES tes positions maintenant.
    </div>""", unsafe_allow_html=True)
elif 15 < mins_to_close <= 45:
    st.markdown(f"""
    <div class="alert-box alert-amber">
        ⏱ {mins_to_close} minutes avant clôture obligatoire (21h59 Paris · règle personnelle)
    </div>""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════
# MÉTRIQUES PRINCIPALES
# ═══════════════════════════════════════════════════════════════════════
st.markdown('<div class="section-title">Métriques Critiques</div>', unsafe_allow_html=True)

c1, c2, c3, c4, c5 = st.columns(5)

def _color(val, good_above=0, warn_above=None, bad_below=None):
    if bad_below is not None and val <= bad_below:   return "#ef4444"
    if warn_above is not None and val <= warn_above: return "#f59e0b"
    if val > good_above:                             return "#10b981"
    return "#ef4444"

bal_color    = "#10b981" if m["current_bal"] > m["mll_floor"] + 500 else ("#f59e0b" if m["current_bal"] > m["mll_floor"] + 200 else "#ef4444")
buf_color    = "#10b981" if m["buffer"] > 1000 else ("#f59e0b" if m["buffer"] > 400 else "#ef4444")
dll_color    = "#10b981" if m["daily_loss_used"] < 700 else ("#f59e0b" if m["daily_loss_used"] < 900 else "#ef4444")
pnl_color    = "#10b981" if m["today_pnl"] >= 0 else ("#f59e0b" if m["today_pnl"] > -700 else "#ef4444")
prog_color   = "#06b6d4"

with c1:
    st.markdown(f"""
    <div class="metric-big">
        <div class="val" style="color:{bal_color}">${m['current_bal']:,.0f}</div>
        <div class="lbl">Balance Compte</div>
        <div class="sub">Floor ${m['mll_floor']:,.0f}</div>
    </div>""", unsafe_allow_html=True)

with c2:
    st.markdown(f"""
    <div class="metric-big">
        <div class="val" style="color:{buf_color}">${m['buffer']:,.0f}</div>
        <div class="lbl">Buffer KO</div>
        <div class="sub">{m['buffer_pct']:.0f}% du MLL</div>
    </div>""", unsafe_allow_html=True)

with c3:
    st.markdown(f"""
    <div class="metric-big">
        <div class="val" style="color:{dll_color}">${m['daily_loss_used']:,.0f}</div>
        <div class="lbl">Daily Loss Utilisé</div>
        <div class="sub">${m['daily_loss_rem']:,.0f} restants / $1,000</div>
    </div>""", unsafe_allow_html=True)

with c4:
    st.markdown(f"""
    <div class="metric-big">
        <div class="val" style="color:{pnl_color}">{'+' if m['today_pnl']>=0 else ''}{m['today_pnl']:,.0f}$</div>
        <div class="lbl">P&L Aujourd'hui</div>
        <div class="sub">Total {'+' if m['total_pnl']>=0 else ''}{m['total_pnl']:,.0f}$</div>
    </div>""", unsafe_allow_html=True)

with c5:
    tc_color = "#ef4444" if mins_to_close <= 15 else ("#f59e0b" if mins_to_close <= 45 else "#06b6d4")
    tc_text  = f"{mins_to_close}min" if 0 < mins_to_close < 600 else ("CLÔTURE" if mins_to_close <= 0 else "OK")
    st.markdown(f"""
    <div class="metric-big">
        <div class="val" style="color:{tc_color}">{tc_text}</div>
        <div class="lbl">Avant 21h59 Paris</div>
        <div class="sub">{now_paris.strftime('%H:%M')} Paris · {now_et.strftime('%H:%M')} NY</div>
    </div>""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════
# JAUGES VISUELLES
# ═══════════════════════════════════════════════════════════════════════
st.markdown('<div class="section-title">Jauges de Risque</div>', unsafe_allow_html=True)

col_g1, col_g2 = st.columns(2)

# ── Jauge Trailing Drawdown ──
with col_g1:
    fig_dd = go.Figure()

    bal_range = [APEX_ACCOUNT_SIZE - APEX_TRAILING_DD - 200, APEX_SAFETY_NET + 500]
    bal_clamped = min(max(m["current_bal"], bal_range[0]), bal_range[1])

    # Zone KO (rouge)
    fig_dd.add_shape(type="rect", x0=0, x1=1,
                     y0=bal_range[0], y1=m["mll_floor"],
                     fillcolor="rgba(239,68,68,0.12)", line_width=0, layer="below")
    # Zone danger (amber)
    fig_dd.add_shape(type="rect", x0=0, x1=1,
                     y0=m["mll_floor"], y1=m["mll_floor"]+500,
                     fillcolor="rgba(245,158,11,0.08)", line_width=0, layer="below")

    # Floor line
    fig_dd.add_hline(y=m["mll_floor"], line_color="#ef4444", line_width=1.5,
                     line_dash="dash", annotation_text=f"MLL Floor ${m['mll_floor']:,.0f}",
                     annotation_font_color="#ef4444", annotation_font_size=10)
    # Safety Net line
    if not m["safety_locked"]:
        fig_dd.add_hline(y=APEX_SAFETY_NET, line_color="#10b981", line_width=1,
                         line_dash="dot", annotation_text=f"Safety Net ${APEX_SAFETY_NET:,.0f}",
                         annotation_font_color="#10b981", annotation_font_size=10,
                         annotation_position="top left")

    # Balance marker
    fig_dd.add_trace(go.Scatter(
        x=[0.5], y=[bal_clamped],
        mode="markers+text",
        marker=dict(size=16, color=bal_color, symbol="diamond",
                    line=dict(color="#ffffff", width=2)),
        text=[f"${m['current_bal']:,.0f}"],
        textposition="middle right",
        textfont=dict(color="#f1f5f9", size=11, family="JetBrains Mono"),
        showlegend=False,
    ))

    fig_dd.update_layout(
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#050505",
        margin=dict(t=30, b=30, l=70, r=80), height=220,
        title=dict(text="Trailing Drawdown EOD", font=dict(size=11, color="#94a3b8",
                   family="JetBrains Mono"), x=0),
        xaxis=dict(visible=False),
        yaxis=dict(range=bal_range, gridcolor="rgba(148,163,184,0.05)",
                   tickformat="$,.0f", tickfont=dict(color="#475569", size=9,
                   family="JetBrains Mono"), linecolor="rgba(148,163,184,0.08)"),
    )
    st.plotly_chart(fig_dd, use_container_width=True, config=dict(displayModeBar=False))

# ── Jauge Daily Loss Limit ──
with col_g2:
    dll_pct = min(100, m["daily_loss_used"] / APEX_DAILY_LIMIT * 100)
    dll_clr = "#10b981" if dll_pct < 70 else ("#f59e0b" if dll_pct < 90 else "#ef4444")

    fig_dll = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=m["daily_loss_used"],
        delta=dict(reference=0, valueformat="$.0f",
                   increasing=dict(color="#ef4444"),
                   decreasing=dict(color="#10b981")),
        number=dict(prefix="$", valueformat=",.0f",
                    font=dict(color=dll_clr, family="JetBrains Mono", size=26)),
        gauge=dict(
            axis=dict(range=[0, APEX_DAILY_LIMIT],
                      tickformat="$,.0f", tickfont=dict(size=9, color="#475569")),
            bar=dict(color=dll_clr, thickness=0.7),
            bgcolor="rgba(0,0,0,0)",
            bordercolor="rgba(148,163,184,0.1)",
            steps=[
                dict(range=[0, 700],       color="rgba(16,185,129,0.08)"),
                dict(range=[700, 900],     color="rgba(245,158,11,0.08)"),
                dict(range=[900, 1000],    color="rgba(239,68,68,0.12)"),
            ],
            threshold=dict(line=dict(color="#ef4444", width=2), thickness=0.8,
                           value=APEX_DAILY_LIMIT),
        ),
        title=dict(text="Daily Loss Limit · $1,000",
                   font=dict(size=11, color="#94a3b8", family="JetBrains Mono")),
    ))
    fig_dll.update_layout(
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=40, b=10, l=20, r=20), height=220,
    )
    st.plotly_chart(fig_dll, use_container_width=True, config=dict(displayModeBar=False))

# ═══════════════════════════════════════════════════════════════════════
# RÈGLES — CHECKLIST COMPLÈTE
# ═══════════════════════════════════════════════════════════════════════
st.markdown('<div class="section-title">Règles — Statut Temps Réel</div>', unsafe_allow_html=True)

col_r1, col_r2 = st.columns(2)

def rule_card(icon, label, value_str, status="ok"):
    cls = {"ok": "rule-ok", "warn": "rule-warn", "bad": "rule-bad", "info": "rule-info"}[status]
    return f"""
    <div class="rule-card {cls}">
        <span class="rule-icon">{icon}</span>
        <span class="rule-label">{label}</span>
        <span class="rule-val">{value_str}</span>
    </div>"""

with col_r1:
    st.markdown("**Règles Communes (EVAL + PA)**", unsafe_allow_html=False)

    # 1. MLL Floor
    buf_status = "ok" if m["buffer"] > 800 else ("warn" if m["buffer"] > 300 else "bad")
    html = rule_card("◈", "Balance > MLL Floor",
                     f"${m['current_bal']:,.0f} vs ${m['mll_floor']:,.0f} (+${m['buffer']:,.0f})",
                     buf_status)
    st.markdown(html, unsafe_allow_html=True)

    # 2. Daily Loss Limit
    dll_status = "ok" if m["daily_loss_used"] < 700 else ("warn" if m["daily_loss_used"] < 950 else "bad")
    html = rule_card("◈", "Daily Loss < $1,000",
                     f"${m['daily_loss_used']:,.0f} utilisé · ${m['daily_loss_rem']:,.0f} restant",
                     dll_status)
    st.markdown(html, unsafe_allow_html=True)

    # 3. Positions overnight
    pos_status = "bad" if mins_to_close <= 0 else ("warn" if mins_to_close <= 15 else "ok")
    pos_txt    = "21h59 DÉPASSÉ — FERME TOUT" if mins_to_close <= 0 else (f"{mins_to_close}min avant 21h59 Paris" if mins_to_close < 600 else "Session ouverte · OK")
    html = rule_card("◈", "Pas de position overnight",
                     pos_txt, pos_status)
    st.markdown(html, unsafe_allow_html=True)

    # 4. Contrats max
    max_c = APEX_MAX_CONTRACTS_PA_FULL if (is_pa and m["safety_locked"]) else \
            (APEX_MAX_CONTRACTS_PA_START if is_pa else APEX_MAX_CONTRACTS_EVAL)
    html = rule_card("◈", "Limite contrats MNQ",
                     f"Max {max_c} contrats{'  (Safety Net atteint)' if is_pa and m['safety_locked'] else ''}",
                     "info")
    st.markdown(html, unsafe_allow_html=True)

    # 5. Métaux interdits
    html = rule_card("◈", "Métaux interdits",
                     "GC · MGC · SI · SIL · HG · PL · PA",
                     "info")
    st.markdown(html, unsafe_allow_html=True)

    # 6. DCA interdit
    html = rule_card("◈", "DCA interdit",
                     "Entrées progressives sur position perdante = VIOLATION",
                     "info")
    st.markdown(html, unsafe_allow_html=True)

with col_r2:
    if not is_pa:
        st.markdown("**Règles Spécifiques EVALUATION**", unsafe_allow_html=False)

        # 7. Profit target
        prog_status = "ok" if m["eval_progress_pct"] >= 100 else ("warn" if m["eval_progress_pct"] > 60 else "info")
        html = rule_card("◈", f"Profit Target $3,000",
                         f"${m['total_pnl']:,.0f} / $3,000 ({m['eval_progress_pct']:.0f}%)",
                         prog_status)
        st.markdown(html, unsafe_allow_html=True)

        # 8. Délai 30 jours
        if eval_start:
            days_elapsed = (date.today() - eval_start).days
            days_rem     = APEX_EVAL_DAYS_MAX - days_elapsed
            d_status     = "ok" if days_rem > 10 else ("warn" if days_rem > 3 else "bad")
            html = rule_card("◈", "Délai 30 jours calendaires",
                             f"J+{days_elapsed} · {days_rem} jours restants",
                             d_status)
            st.markdown(html, unsafe_allow_html=True)

        # 9. Pas de consistency en eval
        html = rule_card("◈", "Consistency Rule",
                         "AUCUNE en évaluation",
                         "ok")
        st.markdown(html, unsafe_allow_html=True)

        # 10. Pas de R:R minimum
        html = rule_card("◈", "Règle R:R minimum",
                         "SUPPRIMÉE (mars 2026) — aucune restriction",
                         "ok")
        st.markdown(html, unsafe_allow_html=True)

        # 11. Safety Net
        sn_status = "ok" if m["safety_locked"] else ("warn" if m["sn_progress"] > 70 else "info")
        sn_txt    = "VERROUILLÉ — Floor fixe $50,100" if m["safety_locked"] else \
                    f"${m['current_bal']:,.0f} / $52,100 ({m['sn_progress']:.0f}%)"
        html = rule_card("◈", "Safety Net ($52,100)",
                         sn_txt, sn_status)
        st.markdown(html, unsafe_allow_html=True)

    else:
        st.markdown("**Règles Spécifiques FUNDED (PA)**", unsafe_allow_html=False)

        # 7. Consistency rule
        cons_status = "ok" if m["consistency_ok"] else "bad"
        if m["profit_since_payout"] <= 0:
            cons_txt = "Pas encore de profit à vérifier"
            cons_status = "info"
        else:
            cons_txt = f"Meilleur jour: ${m['best_day_since']:,.0f} = {m['consistency_pct']:.0f}% du total ${m['profit_since_payout']:,.0f}"
        html = rule_card("◈", "Consistency Rule < 50% / jour",
                         cons_txt, cons_status)
        st.markdown(html, unsafe_allow_html=True)

        # 8. Trading days depuis payout
        td_status = "ok" if m["trading_days_since"] >= APEX_PAYOUT_MIN_DAYS else "warn"
        html = rule_card("◈", f"8 jours de trading min",
                         f"{m['trading_days_since']} / {APEX_PAYOUT_MIN_DAYS} jours",
                         td_status)
        st.markdown(html, unsafe_allow_html=True)

        # 9. Qualifying days
        qd_status = "ok" if m["qual_days"] >= APEX_PAYOUT_QUAL_DAYS else "warn"
        html = rule_card("◈", f"5 jours qualifiants ($50+ / jour)",
                         f"{m['qual_days']} / {APEX_PAYOUT_QUAL_DAYS} jours",
                         qd_status)
        st.markdown(html, unsafe_allow_html=True)

        # 10. Solde au-dessus Safety Net
        sn_status_pa = "ok" if m["safety_locked"] or m["current_bal"] >= APEX_SAFETY_NET else "warn"
        html = rule_card("◈", "Solde ≥ $52,100 (Safety Net)",
                         "VERROUILLÉ ✓" if m["safety_locked"] else f"${m['current_bal']:,.0f} / $52,100",
                         sn_status_pa)
        st.markdown(html, unsafe_allow_html=True)

        # 11. Min retrait $500
        html = rule_card("◈", "Montant minimum payout",
                         "$500 par demande · 2x/mois max",
                         "info")
        st.markdown(html, unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════
# EVAL — BARRE DE PROGRESSION
# ═══════════════════════════════════════════════════════════════════════
if not is_pa:
    st.markdown('<div class="section-title">Progression Evaluation</div>', unsafe_allow_html=True)

    prog_color_hex = "#10b981" if m["eval_progress_pct"] >= 100 else (
                     "#06b6d4" if m["eval_progress_pct"] > 50 else "#3b82f6")
    prog_pct = m["eval_progress_pct"]

    st.markdown(f"""
    <div style="background:var(--bg-surface);border:1px solid var(--border-default);
         border-radius:12px;padding:1.2rem 1.5rem;margin-bottom:.5rem;">
        <div style="display:flex;justify-content:space-between;
             font-family:'JetBrains Mono',monospace;font-size:.72rem;color:var(--text-muted);
             margin-bottom:.6rem;">
            <span>Profit Target $3,000</span>
            <span style="color:{prog_color_hex};font-weight:700">{prog_pct:.1f}%</span>
        </div>
        <div style="background:var(--bg-elevated);border-radius:99px;height:8px;overflow:hidden;">
            <div style="width:{min(100,prog_pct):.1f}%;height:100%;
                 background:linear-gradient(90deg,#3b82f6,{prog_color_hex});
                 border-radius:99px;transition:width .3s;"></div>
        </div>
        <div style="display:flex;justify-content:space-between;margin-top:.5rem;
             font-family:'JetBrains Mono',monospace;font-size:.7rem;color:var(--text-muted);">
            <span>$0</span>
            <span style="color:var(--text-secondary)">${m['total_pnl']:,.0f} actuellement</span>
            <span>$3,000</span>
        </div>
    </div>""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════
# PA — PAYOUT TRACKER
# ═══════════════════════════════════════════════════════════════════════
if is_pa:
    st.markdown('<div class="section-title">Payout Tracker — Ladder $50K EOD</div>', unsafe_allow_html=True)

    # Vérifier toutes les conditions payout
    cond_days     = m["trading_days_since"] >= APEX_PAYOUT_MIN_DAYS
    cond_qual     = m["qual_days"] >= APEX_PAYOUT_QUAL_DAYS
    cond_cons     = m["consistency_ok"] and m["profit_since_payout"] > 0
    cond_sn       = m["safety_locked"] or m["current_bal"] >= APEX_SAFETY_NET
    cond_min      = m["profit_since_payout"] >= APEX_PAYOUT_MIN_AMOUNT

    # Cap du payout actuel
    next_payout_idx = payout_count  # 0-indexed
    if next_payout_idx < len(APEX_PAYOUT_LADDER):
        payout_cap = APEX_PAYOUT_LADDER[next_payout_idx]
        cap_txt = f"${payout_cap:,.2f}"
    else:
        payout_cap = None
        cap_txt = "Illimité"

    # Montant retiirable
    available = min(m["profit_since_payout"], payout_cap) if payout_cap else m["profit_since_payout"]
    all_ok = cond_days and cond_qual and cond_cons and cond_sn and cond_min

    # Summary box
    box_cls = "alert-green" if all_ok else "alert-amber"
    box_txt = f"✓ PAYOUT ELIGIBLE — Payout #{payout_count+1} · Cap {cap_txt} · Disponible ${available:,.0f}" if all_ok else \
              f"◈ Payout #{payout_count+1} — Conditions manquantes (voir ci-dessous)"
    st.markdown(f'<div class="alert-box {box_cls}">{box_txt}</div>', unsafe_allow_html=True)

    col_p1, col_p2 = st.columns([2, 1])

    with col_p1:
        st.markdown("**Conditions Payout**")
        for ok, label, detail in [
            (cond_days, f"8 jours de trading", f"{m['trading_days_since']}/{APEX_PAYOUT_MIN_DAYS} jours"),
            (cond_qual, f"5 jours qualifiants $50+", f"{m['qual_days']}/{APEX_PAYOUT_QUAL_DAYS} jours"),
            (cond_cons, "Consistency rule < 50%", f"{m['consistency_pct']:.0f}% (best day ${m['best_day_since']:,.0f})"),
            (cond_sn,   "Solde ≥ $52,100", f"${m['current_bal']:,.0f}"),
            (cond_min,  "Profit ≥ $500", f"${m['profit_since_payout']:,.0f}"),
        ]:
            icon   = "✓" if ok else "✗"
            status = "ok" if ok else "bad"
            st.markdown(rule_card(icon, label, detail, status), unsafe_allow_html=True)

        # Last payout date input
        st.markdown("---")
        new_lpd = st.date_input("Date dernier payout", value=lpd_val or date.today(), key="lpd_inp")
        if st.button("Enregistrer payout effectué", key="save_payout"):
            _state_set("last_payout_date", str(new_lpd))
            _state_set("payout_count", payout_count + 1)
            _load_trades.clear()
            st.success(f"Payout #{payout_count+1} enregistré — prochains critères réinitialisés.")
            st.rerun()

    with col_p2:
        st.markdown("**Payout Ladder**")
        for i, cap in enumerate(APEX_PAYOUT_LADDER):
            n = i + 1
            if i < payout_count:
                cls = "payout-done"
                icon = "✓"
            elif i == payout_count:
                cls = "payout-current"
                icon = "►"
            else:
                cls = "payout-future"
                icon = "○"
            st.markdown(f"""
            <div class="payout-row {cls}">
                <span>{icon}</span>
                <span style="flex:1">Payout #{n}</span>
                <span style="font-weight:700">${cap:,.0f}</span>
            </div>""", unsafe_allow_html=True)
        st.markdown(f"""
        <div class="payout-row {'payout-current' if payout_count >= len(APEX_PAYOUT_LADDER) else 'payout-future'}">
            <span>{'►' if payout_count >= len(APEX_PAYOUT_LADDER) else '○'}</span>
            <span style="flex:1">Payout #7+</span>
            <span style="font-weight:700;color:#10b981">Illimité</span>
        </div>""", unsafe_allow_html=True)

        st.markdown(f"""
        <div style="margin-top:1rem;padding:.8rem;background:var(--bg-elevated);
             border-radius:8px;font-family:'JetBrains Mono',monospace;font-size:.72rem;
             color:var(--text-muted);line-height:1.8">
            Split ≤ $25K profit<br>
            <span style="color:#10b981;font-weight:700">100% trader</span><br>
            Split > $25K profit<br>
            <span style="color:#06b6d4;font-weight:700">90% / 10% Apex</span>
        </div>""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════
# REFRESH
# ═══════════════════════════════════════════════════════════════════════
st.markdown("---")
col_rf1, col_rf2 = st.columns([1, 5])
with col_rf1:
    if st.button("Actualiser", use_container_width=True):
        _load_trades.clear()
        st.rerun()
with col_rf2:
    st.markdown(f"""
    <div style="font-family:'JetBrains Mono',monospace;font-size:.68rem;
         color:var(--text-muted);padding-top:.5rem;">
        Dernière MàJ : {now_et.strftime('%H:%M:%S')} ET ·
        Source : Journal SQLite ({len(df)} trades) ·
        Cache TTL 15s
    </div>""", unsafe_allow_html=True)
