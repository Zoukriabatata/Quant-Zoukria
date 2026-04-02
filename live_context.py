"""
Live Context Dashboard — QQQ Kalman + VIX9D + Hurst + Régime
Architecture : contexte quant → toi tu confirmes sur ATAS → entry mécanique MNQ

Usage: streamlit run live_context.py
"""

import time
import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as st_components
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timezone, timedelta

try:
    import yfinance as yf
    HAS_YF = True
except ImportError:
    HAS_YF = False

# ══════════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════════

TEAL   = "#3CC4B7"
GREEN  = "#00ff88"
RED    = "#ff3366"
YELLOW = "#ffd600"
ORANGE = "#ff9100"
CYAN   = "#00e5ff"

PARIS  = 2   # UTC offset Paris (CEST)

VIX_REGIMES = {
    "CALM":      (0,   15,  GREEN,  "Mean reversion fiable"),
    "NORMAL":    (15,  22,  TEAL,   "Kalman OU valide"),
    "ELEVATED":  (22,  30,  YELLOW, "Prudence — taille réduite"),
    "CRISIS":    (30, 999,  RED,    "NE PAS TRADER mean reversion"),
}

# ══════════════════════════════════════════════════════════════════════
# PAGE CONFIG
# ══════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="Live Context — MNQ",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
    'family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500;700&display=swap">',
    unsafe_allow_html=True,
)

def _css(raw):
    import re
    css = re.sub(r'/\*.*?\*/', '', raw, flags=re.DOTALL)
    st.markdown(f"<style>{' '.join(css.split())}</style>", unsafe_allow_html=True)

_css("""
*, *::before, *::after { box-sizing:border-box; }
[data-testid="stAppViewContainer"] { background:#060606; font-family:'Inter',sans-serif; }
[data-testid="stSidebar"]  { background:#080808; border-right:1px solid #141414; }
[data-testid="stHeader"]   { background:transparent; }
[data-testid="stToolbar"]  { display:none; }
.block-container           { padding-top:1.2rem; max-width:1300px; }
::-webkit-scrollbar        { width:4px; }
::-webkit-scrollbar-track  { background:#0a0a0a; }
::-webkit-scrollbar-thumb  { background:#3CC4B7; border-radius:2px; }

/* Context card */
.ctx-card {
    background:#080808; border:1px solid #1a1a1a; border-radius:12px;
    padding:1.4rem 1.6rem; margin:0.5rem 0;
}
.ctx-label {
    font-family:'JetBrains Mono',monospace; font-size:0.58rem;
    letter-spacing:0.22em; text-transform:uppercase; margin-bottom:0.6rem;
}
.ctx-value {
    font-family:'JetBrains Mono',monospace; font-size:1.6rem;
    font-weight:700; letter-spacing:-0.02em;
}
.ctx-sub {
    font-size:0.75rem; color:#444; margin-top:0.3rem;
    font-family:'JetBrains Mono',monospace;
}

/* GO card */
.go-card {
    border-radius:14px; padding:2rem 2.4rem;
    margin:1rem 0; border:1px solid; text-align:center;
    position:relative; overflow:hidden;
}
.go-card::before {
    content:''; position:absolute; top:0; left:0; right:0; height:3px;
}
.go-text {
    font-family:'JetBrains Mono',monospace; font-size:3rem;
    font-weight:700; letter-spacing:0.08em;
}
.go-sub {
    font-size:0.82rem; color:#555; margin-top:0.6rem;
    font-family:'JetBrains Mono',monospace; letter-spacing:0.06em;
}
.go-zone {
    font-family:'JetBrains Mono',monospace; font-size:1.1rem;
    font-weight:600; margin-top:0.8rem;
}

/* Checklist */
.chk-row {
    display:flex; align-items:center; gap:0.8rem;
    font-family:'JetBrains Mono',monospace; font-size:0.78rem;
    padding:0.5rem 0; border-bottom:1px solid #0f0f0f;
}
.chk-row:last-child { border-bottom:none; }
.chk-icon { font-size:1rem; min-width:22px; text-align:center; }
.chk-name { color:#888; min-width:160px; }
.chk-val  { color:#ccc; }
.chk-ok   { color:#00ff88; }
.chk-warn { color:#ffd600; }
.chk-bad  { color:#ff3366; }

/* Stats row */
.stat-row  { display:flex; gap:0; border:1px solid #141414; border-radius:10px; overflow:hidden; margin:0.8rem 0; }
.stat-cell { flex:1; padding:1rem; text-align:center; border-right:1px solid #141414; }
.stat-cell:last-child { border-right:none; }
.stat-num  { font-size:1.3rem; font-weight:700; font-family:'JetBrains Mono',monospace; }
.stat-lbl  { font-size:0.56rem; color:#444; letter-spacing:0.14em; text-transform:uppercase; margin-top:0.2rem; }

/* Section label */
.slabel {
    font-family:'JetBrains Mono',monospace; font-size:0.6rem; font-weight:700;
    letter-spacing:0.2em; color:#3CC4B7; text-transform:uppercase; margin:1.6rem 0 0.8rem;
}

/* Execution plan */
.exec-plan {
    background:#060606; border:1px solid rgba(60,196,183,0.15);
    border-radius:10px; padding:1.2rem 1.5rem; margin:0.8rem 0;
    font-family:'JetBrains Mono',monospace; font-size:0.82rem;
}
.exec-row  { display:flex; gap:1.5rem; flex-wrap:wrap; margin:0.4rem 0; }
.exec-key  { color:#3CC4B7; min-width:120px; font-weight:500; }
.exec-val  { color:#ddd; }
""")

# ══════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════

st.sidebar.header("Kalman OU — QQQ")
lookback = st.sidebar.number_input("Lookback (barres)", value=120, min_value=30, step=10,
    help="2h en 1-min. Fenêtre AR(1) pour calibrer φ, μ, σ.")
band_k     = st.sidebar.number_input("Bande k min (σ)", value=1.5, min_value=0.5, max_value=4.0, step=0.1)
band_k_max = st.sidebar.number_input("Bande k max (σ)", value=3.5, min_value=1.0, max_value=6.0, step=0.5)
_lev = st.sidebar.slider("Noise lever (0=adaptatif · 100=modèle OU)", 0, 100, 62)
noise_scale = round(0.1 + 19.9 * (_lev / 100) ** 2, 3)
st.sidebar.caption(f"noise_scale = {noise_scale:.2f}")

st.sidebar.markdown("---")
st.sidebar.header("Filtres contexte")
use_hurst = st.sidebar.toggle("Filtre Hurst", value=True,
    help="H < 0.5 = mean-reverting → valide. H > 0.5 = trending → WAIT.")
hurst_max  = st.sidebar.number_input("Hurst max", value=0.52, min_value=0.40, max_value=0.65, step=0.01)
use_vix    = st.sidebar.toggle("Filtre VIX9D", value=True,
    help="VIX9D > 30 → NE PAS trader mean reversion.")
vix_max    = st.sidebar.number_input("VIX9D max", value=28.0, min_value=10.0, max_value=50.0, step=1.0)

st.sidebar.markdown("---")
st.sidebar.header("Risk — Apex 50K EOD")
sl_sigma  = st.sidebar.slider("SL = k × σ_stat", 0.25, 3.0, 0.75, 0.25)
sl_min    = st.sidebar.number_input("SL min (pts MNQ)", value=4.0, step=0.5)
tp_ratio  = st.sidebar.slider("TP (% vers FV)", 0.25, 1.0, 1.0, 0.05)
n_contracts = st.sidebar.number_input("Contrats MNQ", value=1, min_value=1, max_value=60)
MNQ_PT    = 2.0

st.sidebar.markdown("---")
st.sidebar.header("Session")
sess_h0 = st.sidebar.number_input("Début (h UTC)", value=14, min_value=0, max_value=23)
sess_m0 = st.sidebar.number_input("Début (min)",   value=30, min_value=0, max_value=59)
sess_h1 = st.sidebar.number_input("Fin (h UTC)",   value=21, min_value=0, max_value=23)
sess_m1 = st.sidebar.number_input("Fin (min)",     value= 0, min_value=0, max_value=59)

st.sidebar.markdown("---")
refresh_sec = st.sidebar.number_input("Refresh (sec)", value=30, min_value=10, step=5)

# ══════════════════════════════════════════════════════════════════════
# KALMAN ENGINE
# ══════════════════════════════════════════════════════════════════════

def estimate_ar1(y):
    y = np.array(y, dtype=float)
    y = y[np.isfinite(y)]
    if len(y) < 5:
        return None
    try:
        xl, xc = y[:-1], y[1:]
        X = np.column_stack([np.ones_like(xl), xl])
        beta = np.linalg.lstsq(X, xc, rcond=None)[0]
        c, phi = float(beta[0]), float(beta[1])
        phi = np.clip(phi, 0.01, 0.99)
        resid = xc - (c + phi * xl)
        sigma = float(np.sqrt(np.mean(resid**2)))
        if sigma <= 0 or not np.isfinite(sigma):
            sigma = max(float(np.std(y)) * 0.01, 1e-9)
        return phi, c / (1.0 - phi), sigma
    except Exception:
        return None


class KalmanOU:
    def __init__(self, phi, mu, sigma, ns=1.0):
        self.phi = phi; self.mu = mu
        self.Q = sigma**2 * max(1.0 - phi**2, 1e-6)
        self.R = sigma**2 * max(ns, 0.01)
        self.x = mu; self.P = self.R

    def update(self, z):
        self.x = self.phi * self.x + (1.0 - self.phi) * self.mu
        self.P = self.phi**2 * self.P + self.Q
        K = self.P / (self.P + self.R)
        self.x += K * (z - self.x)
        self.P = (1.0 - K) * self.P
        return self.x


def run_kalman(prices, lb, ns):
    n  = len(prices)
    fv = np.full(n, np.nan)
    ss = np.full(n, np.nan)
    kal = None
    for i in range(lb, n):
        w = prices[i - lb:i]
        p = estimate_ar1(w)
        if p is None:
            continue
        phi, mu, sigma = p
        s = sigma / np.sqrt(max(1.0 - phi**2, 1e-6))
        if kal is None:
            kal = KalmanOU(phi, mu, sigma, ns)
            for c in w:
                kal.update(c)
        else:
            kal.phi = phi; kal.mu = mu
            kal.Q = sigma**2 * max(1.0 - phi**2, 1e-6)
            kal.R = sigma**2 * max(ns, 0.01)
        kal.update(prices[i])
        fv[i] = kal.x
        ss[i] = s
    return fv, ss

# ══════════════════════════════════════════════════════════════════════
# HURST (R/S)
# ══════════════════════════════════════════════════════════════════════

def hurst_rs(prices, lags=(8, 16, 32, 64)):
    try:
        rs_vals = []
        for lag in lags:
            if lag >= len(prices):
                continue
            chunks = [prices[i:i+lag] for i in range(0, len(prices)-lag, lag)]
            rs_lag = []
            for ch in chunks:
                m = np.mean(ch)
                dev = np.cumsum(ch - m)
                r = np.max(dev) - np.min(dev)
                s = np.std(ch, ddof=1)
                if s > 0:
                    rs_lag.append(r / s)
            if rs_lag:
                rs_vals.append((np.log(lag), np.log(np.mean(rs_lag))))
        if len(rs_vals) >= 3:
            xs, ys = zip(*rs_vals)
            return float(np.clip(np.polyfit(xs, ys, 1)[0], 0.0, 1.0))
    except Exception:
        pass
    return 0.5

# ══════════════════════════════════════════════════════════════════════
# DATA FETCH
# ══════════════════════════════════════════════════════════════════════

def fetch_qqq(days=3):
    try:
        df = yf.Ticker("QQQ").history(period=f"{days}d", interval="1m", auto_adjust=True)
        if df is None or df.empty:
            return None
        df = df.reset_index()
        tc = "Datetime" if "Datetime" in df.columns else df.columns[0]
        df.rename(columns={tc:"bar","Open":"open","High":"high",
                            "Low":"low","Close":"close","Volume":"volume"}, inplace=True)
        df["bar"] = pd.to_datetime(df["bar"], utc=True)
        return df[["bar","open","high","low","close","volume"]].sort_values("bar").reset_index(drop=True)
    except Exception as e:
        return None


def refresh_qqq(existing):
    try:
        df = yf.Ticker("QQQ").history(period="1d", interval="1m", auto_adjust=True)
        if df is None or df.empty:
            return existing
        df = df.reset_index()
        tc = "Datetime" if "Datetime" in df.columns else df.columns[0]
        df.rename(columns={tc:"bar","Open":"open","High":"high",
                            "Low":"low","Close":"close","Volume":"volume"}, inplace=True)
        df["bar"] = pd.to_datetime(df["bar"], utc=True)
        new = df[["bar","open","high","low","close","volume"]]
        combined = pd.concat([existing, new]).drop_duplicates(subset=["bar"]).sort_values("bar").reset_index(drop=True)
        return combined
    except Exception:
        return existing


def fetch_vix9d():
    try:
        v9  = yf.Ticker("^VIX9D").history(period="5d", interval="1m", auto_adjust=True)
        vix = yf.Ticker("^VIX").history(period="5d",   interval="1m", auto_adjust=True)
        v9_last  = float(v9["Close"].iloc[-1])  if not v9.empty  else None
        vix_last = float(vix["Close"].iloc[-1]) if not vix.empty else None
        return v9_last, vix_last
    except Exception:
        return None, None


def fetch_hv(qqq_df, window=20):
    if qqq_df is None or len(qqq_df) < window + 1:
        return None
    closes = qqq_df["close"].values
    rets   = np.diff(np.log(closes))
    if len(rets) < window:
        return None
    return float(np.std(rets[-window:]) * np.sqrt(252 * 390) * 100)

# ══════════════════════════════════════════════════════════════════════
# VIX REGIME
# ══════════════════════════════════════════════════════════════════════

def get_vix_regime(vix_val):
    if vix_val is None:
        return "INCONNU", "#444", "Données VIX indisponibles"
    for name, (lo, hi, color, desc) in VIX_REGIMES.items():
        if lo <= vix_val < hi:
            return name, color, desc
    return "CRISIS", RED, "Volatilité extrême"

# ══════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════

if not HAS_YF:
    st.error("`pip install yfinance`")
    st.stop()

# Header
st.html("""
<div style="padding:1rem 0 0.5rem; border-bottom:1px solid #141414; margin-bottom:1.2rem">
    <div style="font-family:'JetBrains Mono',monospace; font-size:0.65rem;
                letter-spacing:0.2em; color:#3CC4B7; text-transform:uppercase">
        LIVE CONTEXT · QQQ → MNQ · KALMAN + VIX9D + HURST
    </div>
    <div style="font-size:1.8rem; font-weight:700; color:#fff;
                letter-spacing:-0.02em; margin:0.3rem 0">
        Contexte de Trading
    </div>
</div>
""")

# Controls
col_b1, col_b2, col_b3 = st.columns([1, 1, 5])
if col_b1.button("Démarrer", type="primary"):
    st.session_state["ctx_running"] = True
    st.session_state.pop("qqq_cache", None)
if col_b2.button("Arrêter"):
    st.session_state["ctx_running"] = False

if not st.session_state.get("ctx_running"):
    st.info("Clique **Démarrer** pour activer le contexte live.")
    st.stop()

# ── Load QQQ ──────────────────────────────────────────────────────────
if "qqq_cache" not in st.session_state:
    with st.spinner("Chargement QQQ..."):
        qqq = fetch_qqq(days=3)
    if qqq is None or len(qqq) < lookback:
        st.error("QQQ indisponible — marché fermé ?")
        st.session_state["ctx_running"] = False
        st.stop()
    st.session_state["qqq_cache"] = qqq
else:
    qqq = refresh_qqq(st.session_state["qqq_cache"])
    st.session_state["qqq_cache"] = qqq

# ── Kalman ────────────────────────────────────────────────────────────
prices = qqq["close"].values.astype(float)
fv, ss = run_kalman(prices, lookback, noise_scale)

last_idx   = len(prices) - 1
last_price = prices[last_idx]
last_fv    = fv[last_idx]
last_ss    = ss[last_idx]

if np.isnan(last_fv) or np.isnan(last_ss):
    st.error("Kalman pas encore convergé — attends quelques minutes.")
    st.stop()

dev_sigma  = (last_price - last_fv) / last_ss
upper      = last_fv + band_k * last_ss
lower      = last_fv - band_k * last_ss

# ── Hurst ─────────────────────────────────────────────────────────────
hurst_window = min(120, len(prices) - 1)
h_val = hurst_rs(prices[-hurst_window:]) if use_hurst else 0.45

# ── VIX9D ─────────────────────────────────────────────────────────────
vix9, vix_daily = fetch_vix9d() if use_vix else (None, None)
vix_regime, vix_color, vix_desc = get_vix_regime(vix9)
hv20 = fetch_hv(qqq)

# ── Data age ─────────────────────────────────────────────────────────
try:
    last_bar_ts  = pd.to_datetime(qqq["bar"].iloc[-1], utc=True)
    data_age_min = (datetime.now(timezone.utc) - last_bar_ts.to_pydatetime()).total_seconds() / 60
except Exception:
    data_age_min = 0.0

# ── Session ───────────────────────────────────────────────────────────
now_utc    = datetime.now(timezone.utc)
sess_start = now_utc.replace(hour=sess_h0, minute=sess_m0, second=0, microsecond=0)
sess_end   = now_utc.replace(hour=sess_h1, minute=sess_m1, second=0, microsecond=0)
in_session = sess_start <= now_utc <= sess_end
paris_time = f"{(now_utc.hour + PARIS) % 24:02d}:{now_utc.strftime('%M')} Paris"

# ── Filtres ───────────────────────────────────────────────────────────
in_zone     = band_k <= abs(dev_sigma) <= band_k_max
hurst_ok    = (h_val < hurst_max) if use_hurst else True
vix_ok      = (vix9 is not None and vix9 < vix_max) if use_vix else True
session_ok  = in_session
data_ok     = data_age_min < 10

direction   = "SHORT" if dev_sigma > 0 else "LONG"
dir_color   = RED if direction == "SHORT" else GREEN

# Checklist complet
checks = [
    ("Zone Kalman",   in_zone,    f"|dév| = {abs(dev_sigma):.2f}σ (besoin {band_k}→{band_k_max}σ)"),
    ("Hurst ranging", hurst_ok,   f"H = {h_val:.3f} (max {hurst_max})"),
    ("VIX9D",         vix_ok,     f"VIX9D = {vix9:.1f}" if vix9 else "Indisponible"),
    ("Session",       session_ok, f"{paris_time}"),
    ("Données fresh", data_ok,    f"{data_age_min:.0f} min"),
]

all_green  = all(ok for _, ok, _ in checks)
n_ok       = sum(ok for _, ok, _ in checks)

# ── Signal alert ─────────────────────────────────────────────────────
prev_ctx = st.session_state.get("prev_ctx_signal", "WAIT")
new_ctx  = direction if all_green else "WAIT"
if new_ctx != prev_ctx and new_ctx in ("LONG", "SHORT"):
    freq = 880 if new_ctx == "SHORT" else 440
    beep_js = f"""<script>
    (function(){{
        var ctx=new(window.AudioContext||window.webkitAudioContext)();
        function beep(f,d,v){{
            var o=ctx.createOscillator(),g=ctx.createGain();
            o.connect(g);g.connect(ctx.destination);
            o.frequency.value=f;o.type='sine';
            g.gain.setValueAtTime(v,ctx.currentTime);
            g.gain.exponentialRampToValueAtTime(0.001,ctx.currentTime+d);
            o.start(ctx.currentTime);o.stop(ctx.currentTime+d);
        }}
        beep({freq},0.35,0.5);
        setTimeout(function(){{beep({freq},0.35,0.45);}},450);
        setTimeout(function(){{beep({freq},0.55,0.5);}},900);
    }})();
    </script>"""
    st_components.html(beep_js, height=0)
st.session_state["prev_ctx_signal"] = new_ctx

# ══════════════════════════════════════════════════════════════════════
# LAYOUT
# ══════════════════════════════════════════════════════════════════════

col_left, col_right = st.columns([1.4, 1], gap="large")

# ── COLONNE GAUCHE : GO CARD + CHECKLIST ─────────────────────────────
with col_left:

    # GO / WAIT card
    if all_green:
        go_bg     = f"rgba(0,255,136,0.05)"
        go_border = GREEN
        go_cls    = "long" if direction == "LONG" else "short"
        go_label  = f"CHERCHER {direction} SUR ATAS"
        go_color  = dir_color
        go_grad   = f"linear-gradient(90deg, {dir_color}, transparent)"
    elif n_ok >= 3:
        go_bg     = "rgba(255,214,0,0.04)"
        go_border = YELLOW
        go_label  = "PRESQUE — attendre"
        go_color  = YELLOW
        go_grad   = f"linear-gradient(90deg, {YELLOW}, transparent)"
    else:
        go_bg     = "rgba(255,255,255,0.02)"
        go_border = "#1a1a1a"
        go_label  = "PAS DE SETUP"
        go_color  = "#333"
        go_grad   = "linear-gradient(90deg, #1a1a1a, transparent)"

    st.markdown(f"""
    <div class="go-card" style="background:{go_bg}; border-color:{go_border}33">
        <div style="position:absolute;top:0;left:0;right:0;height:3px;
                    background:{go_grad}"></div>
        <div class="go-text" style="color:{go_color}">{go_label}</div>
        <div class="go-zone" style="color:{dir_color if all_green else '#333'}">
            {'Zone : ' + f'{lower:.2f} → {upper:.2f}' if all_green else ''}
        </div>
        <div class="go-sub">
            QQQ {last_price:.2f} · FV {last_fv:.2f} · Dév {dev_sigma:+.2f}σ · {paris_time}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Checklist
    st.markdown('<div class="slabel">Checklist contexte</div>', unsafe_allow_html=True)
    chk_html = '<div class="ctx-card">'
    for name, ok, detail in checks:
        icon  = "✓" if ok else "✗"
        cls   = "chk-ok" if ok else "chk-bad"
        chk_html += (
            f'<div class="chk-row">'
            f'<span class="chk-icon {cls}">{icon}</span>'
            f'<span class="chk-name">{name}</span>'
            f'<span class="chk-val">{detail}</span>'
            f'</div>'
        )
    chk_html += "</div>"
    st.markdown(chk_html, unsafe_allow_html=True)

    # Plan d'exécution si GO
    if all_green:
        sl_pts  = max(sl_sigma * last_ss, sl_min)
        tp_pts  = abs(last_price - last_fv) * tp_ratio
        rr      = tp_pts / sl_pts if sl_pts > 0 else 0

        if direction == "LONG":
            entry_zone = f"{lower:.2f} → {lower + last_ss * 0.2:.2f}"
            sl_price   = lower - sl_pts
            tp_price   = last_fv
        else:
            entry_zone = f"{upper - last_ss * 0.2:.2f} → {upper:.2f}"
            sl_price   = upper + sl_pts
            tp_price   = last_fv

        risk_usd = sl_pts * MNQ_PT * n_contracts
        tp_usd   = tp_pts * MNQ_PT * n_contracts

        st.markdown('<div class="slabel">Plan d\'exécution MNQ</div>', unsafe_allow_html=True)
        st.markdown(f"""
        <div class="exec-plan">
            <div class="exec-row">
                <span class="exec-key">Direction</span>
                <span class="exec-val" style="color:{dir_color};font-weight:700">{direction}</span>
            </div>
            <div class="exec-row">
                <span class="exec-key">Zone d'entrée</span>
                <span class="exec-val">{entry_zone}</span>
            </div>
            <div class="exec-row">
                <span class="exec-key">Stop Loss</span>
                <span class="exec-val" style="color:{RED}">{sl_price:.2f}
                    &nbsp;({sl_pts:.1f} pts · ${risk_usd:.0f})</span>
            </div>
            <div class="exec-row">
                <span class="exec-key">Take Profit</span>
                <span class="exec-val" style="color:{GREEN}">{tp_price:.2f}
                    &nbsp;({tp_pts:.1f} pts · ${tp_usd:.0f})</span>
            </div>
            <div class="exec-row">
                <span class="exec-key">R:R</span>
                <span class="exec-val">{rr:.1f}:1</span>
            </div>
            <div class="exec-row">
                <span class="exec-key">Contrats</span>
                <span class="exec-val">{n_contracts} MNQ</span>
            </div>
            <div style="margin-top:1rem; padding-top:0.8rem; border-top:1px solid #141414;
                        font-size:0.7rem; color:#555; letter-spacing:0.06em">
                TRIGGER : absorption visible sur ATAS à la zone d'entrée →
                delta diverge + close en haut (LONG) / bas (SHORT)
            </div>
        </div>
        """, unsafe_allow_html=True)

# ── COLONNE DROITE : MÉTRIQUES + RÉGIME VOL ──────────────────────────
with col_right:

    # Kalman metrics
    st.markdown('<div class="slabel">Kalman OU — QQQ</div>', unsafe_allow_html=True)

    def _ctx_card(label, value, sub, color="#fff"):
        return (
            f'<div class="ctx-card" style="margin-bottom:0.4rem">'
            f'<div class="ctx-label" style="color:#444">{label}</div>'
            f'<div class="ctx-value" style="color:{color}">{value}</div>'
            f'<div class="ctx-sub">{sub}</div>'
            f'</div>'
        )

    dev_color = RED if dev_sigma > 0 else GREEN
    st.markdown(
        _ctx_card("Déviation σ", f"{dev_sigma:+.2f}σ",
                  f"Prix {last_price:.2f} · FV {last_fv:.2f}",
                  dev_color if abs(dev_sigma) >= band_k else "#555"),
        unsafe_allow_html=True,
    )

    bandes_html = (
        f'<div class="ctx-card" style="margin-bottom:0.4rem">'
        f'<div class="ctx-label" style="color:#444">Bandes Kalman (±{band_k}σ)</div>'
        f'<div style="display:flex;gap:1.5rem;margin-top:0.3rem">'
        f'<div><div class="ctx-value" style="color:{RED};font-size:1.1rem">{upper:.2f}</div>'
        f'<div class="ctx-sub">Bande haute</div></div>'
        f'<div><div class="ctx-value" style="color:#555;font-size:1.1rem">{last_fv:.2f}</div>'
        f'<div class="ctx-sub">Fair Value</div></div>'
        f'<div><div class="ctx-value" style="color:{GREEN};font-size:1.1rem">{lower:.2f}</div>'
        f'<div class="ctx-sub">Bande basse</div></div>'
        f'</div></div>'
    )
    st.markdown(bandes_html, unsafe_allow_html=True)

    # Hurst
    h_color = GREEN if h_val < 0.5 else (YELLOW if h_val < 0.55 else RED)
    h_desc  = "mean-reverting ✓" if h_val < 0.5 else ("limite" if h_val < 0.55 else "trending ✗")
    st.markdown(
        _ctx_card("Hurst exponent", f"{h_val:.3f}", h_desc, h_color),
        unsafe_allow_html=True,
    )

    # VIX9D
    st.markdown('<div class="slabel">Volatilité</div>', unsafe_allow_html=True)
    if vix9 is not None:
        st.markdown(
            f'<div class="ctx-card">'
            f'<div class="ctx-label" style="color:#444">Régime VIX9D</div>'
            f'<div class="ctx-value" style="color:{vix_color}">{vix_regime}</div>'
            f'<div class="ctx-sub">'
            f'VIX9D {vix9:.1f} · VIX {vix_daily:.1f}' if vix_daily else f'VIX9D {vix9:.1f}'
            f' · {vix_desc}'
            f'</div></div>',
            unsafe_allow_html=True,
        )
        if hv20 is not None:
            iv_hv = vix9 / hv20 if hv20 > 0 else None
            iv_color = GREEN if iv_hv and iv_hv < 1.2 else YELLOW
            st.markdown(
                _ctx_card("IV/HV Ratio",
                          f"{iv_hv:.2f}x" if iv_hv else "N/A",
                          f"VIX9D {vix9:.1f} / HV20 {hv20:.1f}%",
                          iv_color),
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            '<div class="ctx-card"><div class="ctx-sub">VIX9D indisponible</div></div>',
            unsafe_allow_html=True,
        )

    # σ_stat
    ss_color = GREEN if last_ss < 2.0 else (YELLOW if last_ss < 5.0 else RED)
    st.markdown(
        _ctx_card("σ_stat Kalman", f"{last_ss:.2f} pts",
                  "bande en points réels QQQ", ss_color),
        unsafe_allow_html=True,
    )

    # Data info
    if data_age_min > 5:
        st.warning(f"Données en retard de {data_age_min:.0f} min")

# ══════════════════════════════════════════════════════════════════════
# CHART QQQ — KALMAN + BANDES + HURST
# ══════════════════════════════════════════════════════════════════════

st.markdown('<div class="slabel">QQQ — Kalman OU + Bandes + Déviation σ</div>',
            unsafe_allow_html=True)

show_n = 200
p_     = prices[-show_n:]
fv_    = fv[-show_n:]
ss_    = ss[-show_n:]
valid  = ~np.isnan(fv_)
upper_ = np.where(valid, fv_ + band_k * ss_, np.nan)
lower_ = np.where(valid, fv_ - band_k * ss_, np.nan)
fv_v   = np.where(valid, fv_, np.nan)
dev_   = np.where(valid & (ss_ > 0), (p_ - fv_v) / ss_, np.nan)

# Y range
vp = p_[valid]; vu = upper_[valid]; vl = lower_[valid]
if len(vp):
    pad   = max(1.0, float(np.nanstd(vp)) * 0.25)
    y_min = float(min(np.nanmin(vl), np.nanmin(vp))) - pad
    y_max = float(max(np.nanmax(vu), np.nanmax(vp))) + pad
else:
    y_min, y_max = last_price - 5, last_price + 5

try:
    bar_times = qqq["bar"].iloc[-show_n:].reset_index(drop=True)
    x_vals = list(
        pd.to_datetime(bar_times, utc=True)
        .map(lambda t: (t + pd.Timedelta(hours=PARIS)).strftime("%H:%M"))
    )
except Exception:
    x_vals = list(range(show_n))

_AX = dict(
    gridcolor="rgba(255,255,255,0.025)", linecolor="#111",
    tickfont=dict(color="#2e2e2e", size=10, family="JetBrains Mono"),
    zeroline=False, showgrid=True,
)

fig = make_subplots(rows=2, cols=1, row_heights=[0.72, 0.28],
                    shared_xaxes=True, vertical_spacing=0.03)

fig.add_trace(go.Scatter(x=x_vals, y=upper_, mode="lines",
    line=dict(color="rgba(60,196,183,0.2)", width=1, dash="dot"), name=f"+{band_k}σ"), row=1, col=1)
fig.add_trace(go.Scatter(x=x_vals, y=lower_, mode="lines",
    line=dict(color="rgba(60,196,183,0.2)", width=1, dash="dot"),
    fill="tonexty", fillcolor="rgba(60,196,183,0.03)", name=f"-{band_k}σ"), row=1, col=1)
fig.add_trace(go.Scatter(x=x_vals, y=fv_v, mode="lines",
    line=dict(color=TEAL, width=1.8), name="Fair Value"), row=1, col=1)
fig.add_trace(go.Scatter(x=x_vals, y=p_, mode="lines",
    line=dict(color="rgba(210,210,210,0.85)", width=1.2), name="QQQ"), row=1, col=1)
fig.add_trace(go.Scatter(
    x=[x_vals[-1]], y=[p_[-1]], mode="markers",
    marker=dict(color=dir_color if in_zone else TEAL, size=9, symbol="circle",
                line=dict(color="#060606", width=1.5)),
    name="Now", showlegend=False,
), row=1, col=1)

# Dév
dev_display = np.where(np.isnan(dev_), 0.0, dev_)
dev_opacity = [0.65 if valid[i] else 0.0 for i in range(len(valid))]
dev_colors  = [RED if d > 0 else GREEN for d in dev_display]
fig.add_trace(go.Bar(x=x_vals, y=dev_display, marker_color=dev_colors,
    marker_opacity=dev_opacity, name="Dév σ", showlegend=False), row=2, col=1)
fig.add_hline(y= band_k, line_dash="dot", line_color="rgba(255,51,102,0.35)", line_width=1, row=2, col=1)
fig.add_hline(y=-band_k, line_dash="dot", line_color="rgba(0,255,136,0.35)",  line_width=1, row=2, col=1)
fig.add_hline(y=0, line_dash="solid", line_color="rgba(255,255,255,0.05)", line_width=1, row=2, col=1)

dev_abs_max = float(np.nanmax(np.abs(dev_display[valid]))) if valid.any() else band_k
dev_range   = max(band_k * 1.6, min(dev_abs_max * 1.15, band_k_max * 1.1))

fig.update_layout(
    height=520,
    paper_bgcolor="rgba(6,6,6,0)", plot_bgcolor="rgba(8,8,8,1)",
    font=dict(color="#555", size=11, family="JetBrains Mono"),
    margin=dict(t=16, b=20, l=58, r=24),
    legend=dict(orientation="h", y=1.02, bgcolor="rgba(0,0,0,0)",
                font=dict(color="#444", size=10), borderwidth=0),
    hovermode="x unified",
    hoverlabel=dict(bgcolor="#0d0d0d", bordercolor="#1a1a1a",
                    font=dict(color="#ccc", size=11)),
    xaxis=dict(**_AX, showticklabels=False, nticks=20),
    yaxis=dict(**_AX, tickformat=".2f", range=[y_min, y_max]),
    xaxis2=dict(**_AX, nticks=20,
                title=dict(text="Heure Paris", font=dict(color="#333", size=10))),
    yaxis2=dict(**_AX, tickformat=".1f", range=[-dev_range, dev_range],
                title=dict(text="σ", font=dict(color="#333", size=10))),
    bargap=0.06, template="plotly_dark",
)
st.plotly_chart(fig, use_container_width=True)

# ── Footer info ──────────────────────────────────────────────────────
st.markdown(
    f"<div style='font-family:JetBrains Mono,monospace;font-size:0.65rem;color:#2a2a2a;"
    f"margin-top:-0.4rem'>"
    f"{len(qqq)} barres QQQ · σ_stat {last_ss:.2f} pts · "
    f"data {data_age_min:.0f} min · {paris_time}"
    f"</div>",
    unsafe_allow_html=True,
)

# ── Countdown + auto-refresh ─────────────────────────────────────────
countdown = st.empty()
for r in range(int(refresh_sec), 0, -1):
    countdown.markdown(
        f"<div style='font-family:JetBrains Mono,monospace;font-size:0.65rem;"
        f"color:#222;margin-top:0.5rem'>refresh dans {r}s</div>",
        unsafe_allow_html=True,
    )
    time.sleep(1)
countdown.empty()
st.rerun()
