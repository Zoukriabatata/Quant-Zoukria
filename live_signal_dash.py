"""
Live Signal Dashboard — Hurst_MR (Lec 25 + Lec 51)
Source : yfinance NQ=F M1 (~15 min delay)
"""

import time
import warnings
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime

warnings.filterwarnings("ignore")

try:
    import yfinance as yf
    import pytz
except ImportError:
    st.error("pip install yfinance pytz")
    st.stop()

# ═══════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════

st.set_page_config(page_title="Live Signal", page_icon="⚡", layout="wide")

SYMBOL          = "NQ=F"
HURST_THRESHOLD = 0.45
LOOKBACK        = 30
BAND_K          = 2.5
HMM_LOOKBACK    = 60

SESSION_START   = (9,  30)
SESSION_END     = (16,  0)
SKIP_OPEN_BARS  = 5

NY = pytz.timezone("America/New_York")

TEAL   = "#3CC4B7"
GREEN  = "#00ff88"
RED    = "#ff3366"
YELLOW = "#ffd600"
CYAN   = "#00e5ff"
ORANGE = "#ff9100"
DARK   = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(10,10,10,1)",
    font=dict(color="#888", size=11, family="JetBrains Mono"),
    margin=dict(t=40, b=30, l=50, r=20),
)

# ═══════════════════════════════════════════════════════
# CSS
# ═══════════════════════════════════════════════════════

st.markdown("""
<style>
[data-testid="stAppViewContainer"] { background:#060606; }
[data-testid="stSidebar"]          { background:#080808; border-right:1px solid #141414; }
[data-testid="stHeader"]           { background:transparent; }
.block-container                   { padding-top:1rem; max-width:1400px; }
.kpi-card {
    background:#0a0a0a; border:1px solid #1a1a1a; border-radius:10px;
    padding:1rem 1.2rem; text-align:center;
}
.kpi-value  { font-size:2rem; font-weight:700; font-family:'JetBrains Mono',monospace; }
.kpi-label  { font-size:0.75rem; color:#555; text-transform:uppercase; letter-spacing:.08em; margin-top:.2rem; }
.sig-long  { background:#0a2a1a; border:2px solid #00ff88; border-radius:10px; padding:1.2rem 1.5rem; }
.sig-short { background:#2a0a10; border:2px solid #ff3366; border-radius:10px; padding:1.2rem 1.5rem; }
.sig-none  { background:#0a0a0a; border:1px solid #1a1a1a; border-radius:10px; padding:1.2rem 1.5rem; color:#444; text-align:center; }
.ctx-box   { background:#0a0a0a; border:1px solid #1a1a1a; border-radius:10px; padding:1rem 1.2rem; }
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════
# MATH
# ═══════════════════════════════════════════════════════

def hurst_exponent(ts):
    ts = np.asarray(ts, dtype=float)
    n = len(ts)
    if n < 20:
        return 0.5
    lags = range(2, min(n // 2, 50))
    rs_vals = []
    for lag in lags:
        chunks = [ts[i:i+lag] for i in range(0, n - lag + 1, lag)]
        rs_chunk = []
        for c in chunks:
            std = c.std()
            if std > 0:
                devs = np.cumsum(c - c.mean())
                rs_chunk.append((devs.max() - devs.min()) / std)
        if rs_chunk:
            rs_vals.append(np.mean(rs_chunk))
    if len(rs_vals) < 3:
        return 0.5
    try:
        h = np.polyfit(np.log(list(lags)[:len(rs_vals)]), np.log(rs_vals), 1)[0]
        return float(np.clip(h, 0.0, 1.0))
    except Exception:
        return 0.5


def hmm_proxy_state(closes, lookback=60):
    n = len(closes)
    if n < 3:
        return 1
    rets = np.abs(np.diff(np.log(np.maximum(closes, 1e-9))))
    if len(rets) < 3:
        return 1
    recent = rets[-min(len(rets), 200):]
    p33 = np.nanpercentile(recent, 33)
    p67 = np.nanpercentile(recent, 67)
    cur = rets[-1]
    if cur <= p33:
        return 0
    elif cur >= p67:
        return 2
    return 1


def compute_bands(closes):
    """Rolling mean + std bands pour chaque barre."""
    n = len(closes)
    mids  = np.full(n, np.nan)
    upper = np.full(n, np.nan)
    lower = np.full(n, np.nan)
    for i in range(LOOKBACK, n):
        w = closes[i - LOOKBACK: i]
        m, s = w.mean(), w.std()
        mids[i]  = m
        upper[i] = m + BAND_K * s
        lower[i] = m - BAND_K * s
    return mids, upper, lower


def find_signals(closes, times_str):
    """Retourne liste de signaux sur toute la session."""
    n = len(closes)
    sigs = []
    h = hurst_exponent(closes)
    if h >= HURST_THRESHOLD:
        return sigs, h

    mids, upper, lower = compute_bands(closes)

    for i in range(LOOKBACK + SKIP_OPEN_BARS, n):
        hmm = hmm_proxy_state(closes[:i+1], HMM_LOOKBACK)
        if hmm == 2:
            continue
        w   = closes[i - LOOKBACK: i]
        mid = w.mean()
        std = w.std()
        if std == 0:
            continue
        price = closes[i]
        z = (price - mid) / std
        if abs(z) < BAND_K:
            continue
        direction = "SHORT" if z > 0 else "LONG"
        sigs.append({
            "bar_idx":   i,
            "time":      times_str[i],
            "direction": direction,
            "price":     price,
            "fair_value": mid,
            "z_score":   z,
            "std":       std,
            "hurst":     h,
            "hmm_state": hmm,
        })
    return sigs, h


# ═══════════════════════════════════════════════════════
# DATA
# ═══════════════════════════════════════════════════════

@st.cache_data(ttl=55, show_spinner=False)
def fetch_session_data():
    try:
        df = yf.download(SYMBOL, period="1d", interval="1m",
                         progress=False, auto_adjust=True)
        if df is None or len(df) < 5:
            return None, "Pas de données yfinance"

        df.index = pd.to_datetime(df.index)
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC")
        df.index = df.index.tz_convert(NY)

        t = df.index.hour * 60 + df.index.minute
        df = df[(t >= SESSION_START[0]*60 + SESSION_START[1]) &
                (t <  SESSION_END[0]  *60 + SESSION_END[1])].copy()

        if len(df) < 5:
            return None, "Session non démarrée ou fermée"

        # Flatten MultiIndex si besoin (yfinance v0.2+)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df["close"] = df["Close"].astype(float)
        df["open"]  = df["Open"].astype(float)
        df["high"]  = df["High"].astype(float)
        df["low"]   = df["Low"].astype(float)
        df["time_str"] = [str(x)[:16] for x in df.index]
        return df, None
    except Exception as e:
        return None, str(e)


# ═══════════════════════════════════════════════════════
# PAGE
# ═══════════════════════════════════════════════════════

now_ny = datetime.now(NY)

# ── Sidebar ──────────────────────────────────────────
with st.sidebar:
    st.markdown(f"### ⚡ Live Signal")
    st.markdown(f"**{now_ny.strftime('%A %d %b %Y')}**")
    st.markdown(f"Heure NY : **{now_ny.strftime('%H:%M:%S')}**")
    st.divider()

    auto_refresh = st.checkbox("Auto-refresh (60s)", value=True)
    refresh_sec  = st.select_slider("Intervalle", [30, 60, 120, 300], value=60)

    st.divider()
    st.markdown("**Paramètres Hurst_MR**")
    st.markdown(f"- H < `{HURST_THRESHOLD}` → session MR")
    st.markdown(f"- Lookback : `{LOOKBACK}` barres")
    st.markdown(f"- Bande : `±{BAND_K}σ`")
    st.markdown(f"- HMM state ≠ 2 (pas trending)")
    st.divider()
    st.caption("Source : Lec 25 (fBm) + Lec 51 (HMM)")
    st.caption("Données : yfinance NQ=F M1 ~15 min delay")

# ── Header ───────────────────────────────────────────
col_title, col_refresh = st.columns([4, 1])
with col_title:
    in_session = (
        (now_ny.hour * 60 + now_ny.minute) >= SESSION_START[0]*60 + SESSION_START[1] and
        (now_ny.hour * 60 + now_ny.minute) <  SESSION_END[0]  *60 + SESSION_END[1]
    )
    status_icon = "🟢" if in_session else "🔴"
    status_txt  = "Session active" if in_session else "Hors session NY (9:30-16:00)"
    st.markdown(f"## ⚡ Live Signal — Hurst_MR &nbsp; {status_icon} {status_txt}")
with col_refresh:
    st.markdown("<br>", unsafe_allow_html=True)
    manual_refresh = st.button("🔄 Refresh")

# ── Fetch data ────────────────────────────────────────
with st.spinner("Chargement NQ=F..."):
    df, err = fetch_session_data()

if err or df is None:
    st.warning(f"⚠️ {err or 'Données indisponibles'}")
    if not in_session:
        st.info("Session NY fermée. Les données seront disponibles dès 9:30 NY.")
    if auto_refresh:
        time.sleep(refresh_sec)
        st.rerun()
    st.stop()

closes    = df["close"].values.flatten()
times_str = df["time_str"].tolist()
signals, h_val = find_signals(closes, times_str)
mids, upper_band, lower_band = compute_bands(closes)
hmm_now   = hmm_proxy_state(closes, HMM_LOOKBACK)
price_now = float(closes[-1])
bars_count = len(closes)

last_signal = signals[-1] if signals else None

# ── KPI Cards ─────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)

# Hurst
h_color = GREEN if h_val < HURST_THRESHOLD else RED
h_label = "MR ✓" if h_val < HURST_THRESHOLD else "Trending ✗"
with c1:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-value" style="color:{h_color}">{h_val:.3f}</div>
        <div class="kpi-label">Hurst H — {h_label}</div>
    </div>""", unsafe_allow_html=True)

# HMM
hmm_labels = {0: ("CALM", GREEN), 1: ("NORMAL", TEAL), 2: ("TREND", RED)}
hmm_txt, hmm_col = hmm_labels.get(hmm_now, ("?", "#888"))
with c2:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-value" style="color:{hmm_col}">{hmm_txt}</div>
        <div class="kpi-label">HMM State (barre)</div>
    </div>""", unsafe_allow_html=True)

# Prix
with c3:
    mnq_price = price_now / 10
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-value" style="color:{YELLOW}">{price_now:,.0f}</div>
        <div class="kpi-label">NQ=F &nbsp;·&nbsp; MNQ ≈ {mnq_price:,.0f}</div>
    </div>""", unsafe_allow_html=True)

# Signaux du jour
n_sigs = len(signals)
sig_col = GREEN if n_sigs > 0 else "#555"
with c4:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-value" style="color:{sig_col}">{n_sigs}</div>
        <div class="kpi-label">Signaux aujourd'hui</div>
    </div>""", unsafe_allow_html=True)

# Barres chargées
with c5:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-value" style="color:#888">{bars_count}</div>
        <div class="kpi-label">Barres M1 session</div>
    </div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Chart principal ───────────────────────────────────
x_idx = list(range(len(closes)))

fig = go.Figure()

# Fond zones signal
for sig in signals:
    color = "rgba(0,255,136,0.06)" if sig["direction"] == "LONG" else "rgba(255,51,102,0.06)"
    fig.add_vrect(x0=sig["bar_idx"]-0.5, x1=sig["bar_idx"]+5,
                  fillcolor=color, layer="below", line_width=0)

# Bandes MR
fig.add_trace(go.Scatter(
    x=x_idx, y=upper_band,
    name=f"+{BAND_K}σ", line=dict(color="rgba(255,51,102,0.4)", dash="dot", width=1),
    showlegend=True,
))
fig.add_trace(go.Scatter(
    x=x_idx, y=lower_band,
    name=f"−{BAND_K}σ", line=dict(color="rgba(0,255,136,0.4)", dash="dot", width=1),
    fill="tonexty", fillcolor="rgba(60,196,183,0.04)",
))

# Mean rolling
fig.add_trace(go.Scatter(
    x=x_idx, y=mids,
    name="Fair Value", line=dict(color=TEAL, width=1.5, dash="dash"),
))

# Prix (line)
fig.add_trace(go.Scatter(
    x=x_idx, y=closes,
    name="NQ=F M1", line=dict(color=YELLOW, width=1.8),
))

# Signal markers
long_x  = [s["bar_idx"] for s in signals if s["direction"] == "LONG"]
long_y  = [s["price"]   for s in signals if s["direction"] == "LONG"]
short_x = [s["bar_idx"] for s in signals if s["direction"] == "SHORT"]
short_y = [s["price"]   for s in signals if s["direction"] == "SHORT"]

if long_x:
    fig.add_trace(go.Scatter(
        x=long_x, y=[y * 0.9995 for y in long_y],
        mode="markers+text",
        marker=dict(symbol="triangle-up", size=14, color=GREEN,
                    line=dict(color="white", width=1)),
        text=["LONG"] * len(long_x),
        textposition="bottom center",
        textfont=dict(color=GREEN, size=9),
        name="LONG",
    ))
if short_x:
    fig.add_trace(go.Scatter(
        x=short_x, y=[y * 1.0005 for y in short_y],
        mode="markers+text",
        marker=dict(symbol="triangle-down", size=14, color=RED,
                    line=dict(color="white", width=1)),
        text=["SHORT"] * len(short_x),
        textposition="top center",
        textfont=dict(color=RED, size=9),
        name="SHORT",
    ))

# Prix actuel annotation
fig.add_annotation(
    x=len(closes)-1, y=price_now,
    text=f" ◄ {price_now:,.0f}",
    showarrow=False,
    font=dict(color=YELLOW, size=11),
    xanchor="left",
)

# Tick labels (toutes les 30 barres)
tick_step = max(1, bars_count // 12)
tick_vals = x_idx[::tick_step]
tick_text = [times_str[i][11:16] for i in tick_vals]

fig.update_layout(
    **DARK,
    title=dict(text=f"NQ=F M1 — Session du {now_ny.strftime('%d %b %Y')}  |  H={h_val:.3f}",
               font=dict(color="#aaa", size=13)),
    height=420,
    showlegend=True,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                font=dict(size=10)),
    xaxis=dict(tickvals=tick_vals, ticktext=tick_text, gridcolor="#111"),
    yaxis=dict(gridcolor="#111", tickformat=",.0f"),
    hovermode="x unified",
)

st.plotly_chart(fig, use_container_width=True)

# ── Signal actuel + Contexte ──────────────────────────
col_sig, col_ctx = st.columns([1, 1], gap="medium")

with col_sig:
    st.markdown("#### 🎯 Dernier signal")
    if last_signal:
        d   = last_signal["direction"]
        col = GREEN if d == "LONG" else RED
        cls = "sig-long" if d == "LONG" else "sig-short"
        icon = "▲" if d == "LONG" else "▼"
        tp   = last_signal["fair_value"]
        sl_dist = last_signal["std"] * 1.25
        st.markdown(f"""
        <div class="{cls}">
            <div style="font-size:1.6rem;font-weight:700;color:{col};font-family:monospace">
                {icon} {d}
            </div>
            <div style="margin-top:.6rem;line-height:1.9;font-family:monospace;font-size:.85rem">
                Heure&nbsp;&nbsp;&nbsp;&nbsp; : <b>{last_signal["time"][11:16]} NY</b><br>
                Prix entrée : <b>{last_signal["price"]:,.2f}</b> NQ (MNQ ≈ {last_signal["price"]/10:,.1f})<br>
                Fair value&nbsp; : <b style="color:{TEAL}">{tp:,.2f}</b> &nbsp;← cible TP<br>
                Z-score&nbsp;&nbsp;&nbsp; : <b>{last_signal["z_score"]:+.2f}σ</b><br>
                SL guide&nbsp;&nbsp; : ±<b>{sl_dist:.0f} pts NQ</b> ({sl_dist/10:.1f} pts MNQ)<br>
                HMM state&nbsp; : {last_signal["hmm_state"]} (0=calm 1=normal)
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        regime_txt = "Session MR — en attente de signal" if h_val < HURST_THRESHOLD else "Session trending — pas de trade"
        st.markdown(f"""
        <div class="sig-none">
            <div style="font-size:1rem">Aucun signal actif</div>
            <div style="font-size:.8rem;margin-top:.4rem">{regime_txt}</div>
        </div>
        """, unsafe_allow_html=True)

with col_ctx:
    st.markdown("#### 📊 Contexte session")

    # Hurst gauge textuel
    h_pct = min(100, int(h_val * 100))
    h_bar_green = int((1 - min(h_val, 1)) * 20)
    h_bar_str = "█" * h_bar_green + "░" * (20 - h_bar_green)
    h_desc = "Anti-persistante (MR ✓)" if h_val < HURST_THRESHOLD else "Persistante / Random Walk (trend)"

    # Z actuel
    if len(closes) >= LOOKBACK:
        w = closes[-LOOKBACK:]
        z_now = (closes[-1] - w.mean()) / (w.std() if w.std() > 0 else 1)
    else:
        z_now = 0.0

    z_col = (RED if z_now > BAND_K else GREEN if z_now < -BAND_K else TEAL)

    regime_color = GREEN if h_val < HURST_THRESHOLD else RED

    st.markdown(f"""
    <div class="ctx-box">
    <div style="font-family:monospace;font-size:.85rem;line-height:2.1">
        <span style="color:#555">Hurst H&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</span>
        <b style="color:{regime_color}">{h_val:.3f}</b> — {h_desc}<br>
        <span style="color:#555">Seuil MR&nbsp;&nbsp;&nbsp;&nbsp;</span> H &lt; {HURST_THRESHOLD}<br>
        <span style="color:#555">HMM state&nbsp;&nbsp;&nbsp;</span>
        <b style="color:{hmm_col}">{hmm_now}</b> — {hmm_txt}<br>
        <span style="color:#555">Z-score actuel</span>
        <b style="color:{z_col}">{z_now:+.2f}σ</b>
        {"&nbsp; ← SIGNAL ZONE" if abs(z_now) >= BAND_K else ""}<br>
        <span style="color:#555">Barres chargées</span> {bars_count} M1<br>
        <span style="color:#555">Màj données&nbsp;&nbsp;</span>
        {now_ny.strftime('%H:%M:%S')} NY<br>
    </div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Historique signaux ────────────────────────────────
st.markdown("#### 📋 Historique signaux — session du jour")
if signals:
    rows = []
    for s in signals:
        d = s["direction"]
        rows.append({
            "Heure":       s["time"][11:16] + " NY",
            "Direction":   s["direction"],
            "Prix NQ":     f"{s['price']:,.2f}",
            "Prix MNQ":    f"{s['price']/10:,.1f}",
            "Fair Value":  f"{s['fair_value']:,.2f}",
            "Z-score":     f"{s['z_score']:+.2f}σ",
            "Hurst H":     f"{s['hurst']:.3f}",
            "HMM":         str(s["hmm_state"]),
        })
    hist_df = pd.DataFrame(rows)

    def color_dir(val):
        if val == "LONG":
            return "color: #00ff88; font-weight:bold"
        elif val == "SHORT":
            return "color: #ff3366; font-weight:bold"
        return ""

    st.dataframe(
        hist_df.style.applymap(color_dir, subset=["Direction"]),
        use_container_width=True,
        hide_index=True,
    )
else:
    regime = "session MR active (H < 0.45), aucun signal encore" if h_val < HURST_THRESHOLD else "session trending (H ≥ 0.45) — pas de signal MR aujourd'hui"
    st.info(f"Aucun signal — {regime}")

# ── Hurst intraday (mini-chart) ───────────────────────
st.markdown("#### 📈 Évolution Hurst intraday")
hurst_vals = []
step = max(1, LOOKBACK)
for i in range(LOOKBACK, len(closes), step):
    hurst_vals.append((i, hurst_exponent(closes[:i+1])))

if len(hurst_vals) > 2:
    hx = [v[0] for v in hurst_vals]
    hy = [v[1] for v in hurst_vals]
    hx_labels = [times_str[i][11:16] for i in hx if i < len(times_str)]

    fig_h = go.Figure()
    fig_h.add_hline(y=HURST_THRESHOLD, line=dict(color=RED, dash="dash", width=1.5),
                    annotation_text=f"Seuil MR {HURST_THRESHOLD}", annotation_position="right")
    fig_h.add_hline(y=0.5, line=dict(color="#333", dash="dot", width=1))

    colors_h = [GREEN if v < HURST_THRESHOLD else ORANGE for v in hy]
    fig_h.add_trace(go.Scatter(
        x=hx[:len(hx_labels)], y=hy,
        mode="lines+markers",
        line=dict(color=TEAL, width=2),
        marker=dict(color=colors_h, size=6, line=dict(color="white", width=0.5)),
        name="Hurst H",
        hovertemplate="Heure: %{text}<br>H: %{y:.3f}<extra></extra>",
        text=hx_labels,
    ))
    fig_h.add_trace(go.Scatter(
        x=[hx[-1]], y=[hy[-1]],
        mode="markers+text",
        marker=dict(size=10, color=GREEN if hy[-1] < HURST_THRESHOLD else RED),
        text=[f"H={hy[-1]:.3f}"],
        textposition="top right",
        textfont=dict(size=11),
        showlegend=False,
    ))
    fig_h.update_layout(
        **DARK,
        height=220,
        title=dict(text="Hurst H — mis à jour chaque 30 barres", font=dict(size=12, color="#888")),
        yaxis=dict(range=[0, 1], gridcolor="#111",
                   title="H", tickvals=[0, 0.25, 0.45, 0.5, 0.75, 1.0]),
        xaxis=dict(tickvals=hx[:len(hx_labels)], ticktext=hx_labels, gridcolor="#111"),
        showlegend=False,
    )
    st.plotly_chart(fig_h, use_container_width=True)

# ── Footer ────────────────────────────────────────────
st.divider()
st.caption(
    f"⚡ Live Signal — Hurst_MR (Lec 25 + Lec 51) · "
    f"NQ=F yfinance ~15 min delay · "
    f"Màj : {now_ny.strftime('%H:%M:%S')} NY · "
    f"Auto-refresh : {'✓ ' + str(refresh_sec) + 's' if auto_refresh else '✗'}"
)

# ── Auto-refresh ──────────────────────────────────────
if auto_refresh or manual_refresh:
    if not manual_refresh:
        time.sleep(refresh_sec)
    st.rerun()
