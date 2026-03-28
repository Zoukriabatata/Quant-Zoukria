"""
Live Kalman OU Mean Reversion — MNQ
IBKR TWS → barres 1 min → Kalman fair value → bandes OU
→ Signal quand prix hors bande → alerte → trade sur Apex

Usage: streamlit run live_kalman.py
Prerequis: TWS ouvert avec API activee (port 7497)
"""

import os
import time
import asyncio
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from datetime import datetime, timezone

# Fix event loop pour ib_insync + Streamlit
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

try:
    from ib_insync import IB, Future, util
    HAS_IB = True
except ImportError:
    HAS_IB = False

# ── Theme ────────────────────────────────────────────────────────────
DARK = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(17,17,17,1)",
    font=dict(color="#e0e0e0", size=13),
    margin=dict(t=50, b=40, l=50, r=30),
)
CYAN, MAGENTA, GREEN, RED = "#00e5ff", "#ff00e5", "#00ff88", "#ff3366"
YELLOW, ORANGE = "#ffd600", "#ff9100"

st.set_page_config(page_title="Live Kalman OU", page_icon="KO", layout="wide")
st.title("Live Kalman OU — MNQ")

# ── Sidebar ──────────────────────────────────────────────────────────
st.sidebar.header("Kalman OU")
band_k = st.sidebar.number_input("Bande k (sigma)", value=1.0, min_value=0.3, max_value=3.0, step=0.1)
kalman_lookback = st.sidebar.number_input("Lookback (barres)", value=120, min_value=30, step=10)
kalman_R_mult = st.sidebar.number_input("R multiplier", value=5.0, min_value=0.5, step=0.5)

st.sidebar.markdown("---")
st.sidebar.header("Risk")
sl_atr_mult = st.sidebar.number_input("SL = ATR x", value=1.5, step=0.1)
max_sl = st.sidebar.number_input("SL max (pts)", value=15.0, step=1.0)

st.sidebar.markdown("---")
st.sidebar.header("IBKR")
ib_host = st.sidebar.text_input("Host", value="127.0.0.1")
ib_port = st.sidebar.number_input("Port", value=7497, step=1)
refresh_sec = st.sidebar.number_input("Refresh (sec)", value=30, min_value=10, step=5)


# ══════════════════════════════════════════════════════════════════════
# ENGINE
# ══════════════════════════════════════════════════════════════════════

def kalman_ou_filter(prices, lookback, R_mult=5.0):
    """Kalman OU → fair_value, sigma_stat, K."""
    n = len(prices)
    fair_values = np.full(n, np.nan)
    sigma_stats = np.full(n, np.nan)
    kalman_gains = np.full(n, np.nan)

    for i in range(lookback, n):
        window = prices[max(0, i - lookback):i]
        x_prev = window[:-1]
        x_curr = window[1:]
        m = len(x_prev)

        if np.std(x_prev) < 1e-10 or m < 10:
            fair_values[i] = prices[i]
            sigma_stats[i] = 5.0
            kalman_gains[i] = 0.5
            continue

        sx = np.sum(x_prev)
        sy = np.sum(x_curr)
        sxx = np.sum(x_prev ** 2)
        sxy = np.sum(x_prev * x_curr)
        denom = m * sxx - sx * sx

        if abs(denom) < 1e-10:
            fair_values[i] = prices[i]
            sigma_stats[i] = 5.0
            kalman_gains[i] = 0.5
            continue

        phi = np.clip((m * sxy - sx * sy) / denom, 0.5, 0.999)
        c = (sy - phi * sx) / m
        mu = c / (1 - phi) if abs(1 - phi) > 1e-6 else np.mean(window)
        residuals = x_curr - (phi * x_prev + c)
        sigma = max(np.std(residuals), 1.0)
        sigma_stat = sigma / np.sqrt(max(2 * (1 - phi), 0.001))

        Q = sigma ** 2 * (1 - phi ** 2)
        R = sigma ** 2 * R_mult
        x_est = window[0]
        P = sigma_stat ** 2

        for obs in window:
            x_pred = phi * x_est + (1 - phi) * mu
            P_pred = phi ** 2 * P + Q
            K = P_pred / (P_pred + R)
            x_est = x_pred + K * (obs - x_pred)
            P = (1 - K) * P_pred

        fair_values[i] = x_est
        sigma_stats[i] = sigma_stat
        kalman_gains[i] = K

    return fair_values, sigma_stats, kalman_gains


def compute_atr(highs, lows, closes, period=14):
    """ATR."""
    tr = np.maximum(
        highs - lows,
        np.maximum(abs(highs - np.roll(closes, 1)), abs(lows - np.roll(closes, 1)))
    )
    tr[0] = highs[0] - lows[0]
    return pd.Series(tr).rolling(period, min_periods=1).mean().values


@st.cache_resource
def connect_ib(host, port):
    """Connecte a TWS/IB Gateway."""
    ib = IB()
    try:
        ib.connect(host, port, clientId=10, timeout=10)
        return ib
    except Exception as e:
        return None


def fetch_bars_ibkr(ib, lookback_minutes=180):
    """Recupere les barres historiques 1 min de MNQ via IBKR."""
    # Contrat MNQ continuous
    contract = Future("MNQ", exchange="CME")
    ib.qualifyContracts(contract)

    duration = f"{lookback_minutes * 60} S"
    bars = ib.reqHistoricalData(
        contract,
        endDateTime="",
        durationStr=duration,
        barSizeSetting="1 min",
        whatToShow="TRADES",
        useRTH=False,
        formatDate=1,
    )

    if not bars:
        return None

    df = util.df(bars)
    df.rename(columns={"date": "bar"}, inplace=True)
    return df


# ══════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════

if not HAS_IB:
    st.error("pip install ib_insync")
    st.stop()

st.markdown("**Prerequis:** TWS ouvert avec API activee (port 7497)")

if st.button("Demarrer", type="primary"):

    # 1. Connexion IBKR
    with st.spinner("Connexion a TWS..."):
        ib = connect_ib(ib_host, ib_port)

    if ib is None or not ib.isConnected():
        st.error("Impossible de se connecter a TWS. Verifie que TWS est ouvert "
                 "et que 'Enable ActiveX and Socket Clients' est coche.")
        st.stop()

    st.success("Connecte a TWS")

    # 2. Charger les barres historiques
    with st.spinner("Chargement des barres MNQ..."):
        bars_df = fetch_bars_ibkr(ib, lookback_minutes=kalman_lookback + 60)

    if bars_df is None or len(bars_df) < kalman_lookback:
        st.error(f"Pas assez de barres ({len(bars_df) if bars_df is not None else 0}). "
                 f"Le marche est peut-etre ferme.")
        ib.disconnect()
        st.stop()

    st.info(f"{len(bars_df)} barres chargees")

    # 3. Kalman
    prices = bars_df["close"].values.astype(float)
    highs = bars_df["high"].values.astype(float)
    lows = bars_df["low"].values.astype(float)

    fair_values, sigma_stats, k_gains = kalman_ou_filter(prices, kalman_lookback, kalman_R_mult)
    atr = compute_atr(highs, lows, prices)

    # Derniere barre
    last_idx = len(prices) - 1
    last_price = prices[last_idx]
    fv = fair_values[last_idx]
    ss = sigma_stats[last_idx]
    kg = k_gains[last_idx]
    last_atr = atr[last_idx]

    if np.isnan(fv) or np.isnan(ss):
        st.error("Kalman pas encore calibre.")
        ib.disconnect()
        st.stop()

    upper = fv + band_k * ss
    lower = fv - band_k * ss
    sl_pts = min(last_atr * sl_atr_mult, max_sl)
    tp_pts = abs(last_price - fv)

    # Deconnecter IBKR (on a les donnees)
    ib.disconnect()

    # ── SIGNAL ───────────────────────────────────────────────────────
    st.markdown("---")
    deviation = (last_price - fv) / ss if ss > 0 else 0

    if last_price > upper:
        signal = "SHORT"
        signal_color = RED
        entry = last_price
        sl = entry + sl_pts
        tp = fv
    elif last_price < lower:
        signal = "LONG"
        signal_color = GREEN
        entry = last_price
        sl = entry - sl_pts
        tp = fv
    else:
        signal = "PAS DE SIGNAL"
        signal_color = YELLOW
        entry = sl = tp = None

    st.markdown(f"### Signal: <span style='color:{signal_color};font-size:2.5em'>"
                f"{signal}</span>", unsafe_allow_html=True)

    # Metriques
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Prix MNQ", f"{last_price:,.2f}")
    m2.metric("Fair Value", f"{fv:,.2f}")
    m3.metric("Deviation", f"{deviation:+.2f}σ")
    m4.metric("Bande haute", f"{upper:,.2f}")
    m5.metric("Bande basse", f"{lower:,.2f}")

    if entry:
        st.markdown("---")
        st.markdown("### Execution sur Apex")
        e1, e2, e3, e4 = st.columns(4)
        e1.metric("Entry", f"{entry:,.2f}")
        e2.metric("Stop Loss", f"{sl:,.2f}", delta=f"{sl_pts:.1f} pts")
        e3.metric("Take Profit", f"{tp:,.2f}", delta=f"{tp_pts:.1f} pts")
        e4.metric("R:R", f"{tp_pts/sl_pts:.1f}" if sl_pts > 0 else "N/A")

    # ── CHART ────────────────────────────────────────────────────────
    st.markdown("---")
    show_bars = min(120, len(prices))
    chart_prices = prices[-show_bars:]
    chart_fv = fair_values[-show_bars:]
    chart_upper = chart_fv + band_k * sigma_stats[-show_bars:]
    chart_lower = chart_fv - band_k * sigma_stats[-show_bars:]
    x_range = list(range(show_bars))

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x_range, y=chart_prices, mode="lines",
        line=dict(color="white", width=1.5), name="Prix"
    ))
    fig.add_trace(go.Scatter(
        x=x_range, y=chart_fv, mode="lines",
        line=dict(color=CYAN, width=2), name="Fair Value"
    ))
    fig.add_trace(go.Scatter(
        x=x_range, y=chart_upper, mode="lines",
        line=dict(color=RED, width=1, dash="dash"), name=f"Upper ({band_k}σ)"
    ))
    fig.add_trace(go.Scatter(
        x=x_range, y=chart_lower, mode="lines",
        line=dict(color=GREEN, width=1, dash="dash"), name=f"Lower ({band_k}σ)",
        fill="tonexty", fillcolor="rgba(0,229,255,0.05)"
    ))

    if entry:
        fig.add_hline(y=entry, line_dash="solid", line_color=signal_color, opacity=0.5,
                      annotation_text=f"{signal} @ {entry:,.2f}")
        fig.add_hline(y=sl, line_dash="dot", line_color=RED, opacity=0.3,
                      annotation_text=f"SL {sl:,.2f}")
        fig.add_hline(y=tp, line_dash="dot", line_color=GREEN, opacity=0.3,
                      annotation_text=f"TP {tp:,.2f}")

    fig.update_layout(
        title=f"MNQ — Kalman OU (lookback={kalman_lookback}, k={band_k}σ)",
        xaxis_title="Barres (1 min)",
        yaxis_title="Prix",
        height=500,
        **DARK
    )
    st.plotly_chart(fig, use_container_width=True)

    st.caption(f"ATR(14) = {last_atr:.2f} pts | SL = {sl_pts:.1f} pts | "
               f"Kalman K = {kg:.3f} | "
               f"Update: {datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC")

    st.info(f"Prochain refresh dans {refresh_sec}s. Clique 'Demarrer' pour actualiser.")