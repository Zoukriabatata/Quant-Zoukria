"""
Live Kalman OU Mean Reversion — MNQ
Alpaca → QQQ barres 1 min → Kalman fair value → bandes OU
→ Signal quand prix hors bande → alerte → trade MNQ sur Apex
(QQQ correlation ~99% avec MNQ — meme direction, 0 delai, gratuit)

Usage: streamlit run live_kalman.py
Prerequis: Cle API Alpaca gratuite sur alpaca.markets
"""

import os
import time
import calendar
import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as st_components
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timezone, timedelta, date

try:
    import yfinance as yf
    HAS_YF = True
except ImportError:
    HAS_YF = False

# ── Theme ────────────────────────────────────────────────────────────
DARK = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(6,6,6,0)",
    plot_bgcolor="rgba(10,10,10,1)",
    font=dict(color="#888", size=12, family="JetBrains Mono"),
    margin=dict(t=50, b=40, l=50, r=30),
)
TEAL, CYAN, MAGENTA, GREEN, RED = "#3CC4B7", "#00e5ff", "#ff00e5", "#00ff88", "#ff3366"
YELLOW, ORANGE = "#ffd600", "#ff9100"

st.set_page_config(page_title="Live Kalman OU", page_icon="⚡", layout="wide")

def _inject_css(raw_css: str) -> None:
    import re as _re
    css = _re.sub(r'/\*.*?\*/', '', raw_css, flags=_re.DOTALL)
    css = ' '.join(css.split())
    st.markdown(f'<style>{css}</style>', unsafe_allow_html=True)

st.markdown(
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:ital,wght@0,400;0,500;0,600;1,400&family=JetBrains+Mono:wght@400;500;700&display=swap">',
    unsafe_allow_html=True,
)

_inject_css("""
/* Base */
*, *::before, *::after { box-sizing: border-box; }
[data-testid="stAppViewContainer"] { background: #060606; font-family: 'Inter', sans-serif; }
[data-testid="stSidebar"] { background: #080808; border-right: 1px solid #141414; }
[data-testid="stHeader"] { background: transparent; }
[data-testid="stToolbar"] { display: none; }
.block-container { padding-top: 1.5rem; max-width: 1200px; }
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: #0a0a0a; }
::-webkit-scrollbar-thumb { background: #3CC4B7; border-radius: 2px; }
/* Sidebar nav */
[data-testid="stSidebarNav"] { padding: 0.5rem 0; }
[data-testid="stSidebarNavLink"] {
    display: block; padding: 0.6rem 1.2rem; margin: 2px 8px; border-radius: 6px;
    font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; letter-spacing: 0.08em;
    color: #555 !important; text-decoration: none !important;
    transition: background 0.15s, color 0.15s; border: 1px solid transparent;
}
[data-testid="stSidebarNavLink"]:hover { background: #111 !important; color: #ccc !important; border-color: #1a1a1a; }
[data-testid="stSidebarNavLink"][aria-current="page"] {
    background: rgba(60,196,183,0.08) !important; color: #3CC4B7 !important; border-color: rgba(60,196,183,0.2);
}
[data-testid="stSidebarNavLink"] span { font-size: 0.75rem !important; }
/* Page header */
.page-header { padding: 1.5rem 0 0.5rem; border-bottom: 1px solid #1a1a1a; margin-bottom: 1.5rem; }
.page-tag { font-family: 'JetBrains Mono', monospace; font-size: 0.65rem; letter-spacing: 0.2em; color: #3CC4B7; text-transform: uppercase; }
.page-title { font-size: 1.8rem; font-weight: 700; color: #fff; letter-spacing: -0.02em; margin: 0.3rem 0 0; }
/* Signal box */
.signal-box { text-align: center; padding: 2.5rem 2rem; border-radius: 12px; margin: 1rem 0; border: 1px solid; position: relative; overflow: hidden; }
.signal-box::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px; }
.signal-box.long::before { background: linear-gradient(90deg, #00ff88, transparent); }
.signal-box.short::before { background: linear-gradient(90deg, #ff3366, transparent); }
.signal-box.none::before { background: linear-gradient(90deg, #ffd600, transparent); }
.signal-text { font-size: 4rem; font-weight: 700; letter-spacing: 0.05em; font-family: 'JetBrains Mono', monospace; }
.signal-sub { font-size: 0.85rem; color: #555; margin-top: 0.5rem; font-family: 'JetBrains Mono', monospace; letter-spacing: 0.08em; }
/* Stats row */
.stat-row { display: flex; gap: 0; border: 1px solid #141414; border-radius: 10px; overflow: hidden; margin: 1rem 0; }
.stat-cell { flex: 1; padding: 1rem; text-align: center; border-right: 1px solid #141414; transition: background 0.15s; }
.stat-cell:last-child { border-right: none; }
.stat-cell:hover { background: #0d0d0d; }
.stat-num { font-size: 1.4rem; font-weight: 700; font-family: 'JetBrains Mono', monospace; letter-spacing: -0.02em; }
.stat-lbl { font-size: 0.58rem; color: #444; letter-spacing: 0.14em; text-transform: uppercase; margin-top: 0.25rem; }
/* Exec block */
.exec-block { background: #080808; border: 1px solid #141414; border-radius: 10px; padding: 1.2rem 1.5rem; margin: 0.8rem 0; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; }
.exec-row { display: flex; gap: 2rem; flex-wrap: wrap; }
.exec-key { color: #3CC4B7; font-weight: 500; min-width: 80px; }
.exec-val { color: #ccc; }
/* Section label */
.section-label { font-family: 'JetBrains Mono', monospace; font-size: 0.6rem; font-weight: 700; letter-spacing: 0.2em; color: #3CC4B7; text-transform: uppercase; margin: 1.8rem 0 0.8rem; }
""")

st.markdown("""
<div class="page-header">
    <div class="page-tag">LIVE · QQQ → MNQ · APEX 50K EOD</div>
    <div class="page-title">Live Kalman OU</div>
</div>
""", unsafe_allow_html=True)

# ── Sidebar ──────────────────────────────────────────────────────────
st.sidebar.header("Kalman OU")
kalman_lookback = st.sidebar.number_input(
    "Lookback calibration (barres)", value=120, min_value=30, step=10,
    help="Fenêtre AR(1) pour calibrer φ, μ, σ. 120 barres = 2h en 1m."
)
band_k = st.sidebar.number_input(
    "Bande k min (σ)", value=1.5, min_value=0.3, max_value=4.0, step=0.1,
    help="Signal quand |prix - FV| > k × σ_stat."
)
band_k_max = st.sidebar.number_input(
    "Bande k max (σ)", value=4.0, min_value=0.5, max_value=10.0, step=0.5,
    help="Ignore si déviation > k_max (évite les gaps/spikes extrêmes)."
)
kalman_R_mult = st.sidebar.number_input(
    "Noise scale (confiance modèle)", min_value=0.1, max_value=20.0, value=5.0, step=0.5,
    help="R = σ² × noise_scale. Élevé = fait confiance au modèle OU, lisse."
)
confirm_reversal_live = st.sidebar.toggle(
    "Confirmation reversion (Lec 72/95)",
    value=True,
    help="Signal valide seulement si la barre en cours est déjà plus proche du FV que la précédente."
)
max_sigma_stat = st.sidebar.number_input(
    "σ_stat max (filtre vol)", value=15.0, min_value=0.0, max_value=100.0, step=1.0,
    help="Skip si σ_stat > seuil. Marché trending → mean reversion peu fiable. 0 = désactivé."
)

st.sidebar.markdown("---")
st.sidebar.header("Risk")
sl_sigma_mult = st.sidebar.slider(
    "SL = k × σ_kalman", min_value=0.25, max_value=3.0, value=0.75, step=0.25,
    help="Stop = sl_sigma × σ_stat au-delà de l'entrée. 0.75 avec band_k=1.5 → R:R≈2:1."
)
min_sl_pts = st.sidebar.number_input("SL min (pts)", value=4.0, step=0.5)
tp_ratio = st.sidebar.slider(
    "TP ratio (% distance vers FV)", min_value=0.25, max_value=1.0, value=1.0, step=0.05,
    help="1.0 = TP au FV complet."
)

st.sidebar.markdown("---")
st.sidebar.header("Session")
session_start_h = st.sidebar.number_input("Début (h UTC)", value=14, min_value=0, max_value=23)
session_start_m = st.sidebar.number_input("Début (min)", value=30, min_value=0, max_value=59)
session_end_h   = st.sidebar.number_input("Fin (h UTC)", value=21, min_value=0, max_value=23)
session_end_m   = st.sidebar.number_input("Fin (min)", value=0, min_value=0, max_value=59)
max_trades_per_day = st.sidebar.number_input(
    "Max trades/jour", value=2, min_value=1, max_value=10, step=1,
    help="Limite pour respecter le DLL Apex."
)

st.sidebar.markdown("---")
st.sidebar.header("Challenge Apex 50K EOD")

# ── Regles Apex 50K EOD (fixes) ──────────────────────────────────────
APEX_50K = {
    "capital":        50_000,
    "profit_target":  3_000,   # objectif du challenge
    "trailing_dd":    2_000,   # drawdown trailing EOD max (Apex 50K EOD Trail)
    "daily_loss":     1_000,   # perte max par jour
    "max_contracts":  60,      # 60 micro (MNQ) pendant l'eval
    "max_contracts_pa": 40,    # 40 micro en Performance Account
    "trading_days":   22,      # objectif 1 mois — mais Min Days To Pass = 1
    "consistency_pa": 0.50,    # regle PA : aucun jour > 50% du profit total
}

# Calendrier — fenetre = date de debut du challenge → fin du mois calendaire
_today = date.today()

challenge_start = st.sidebar.date_input(
    "Date de debut du challenge",
    value=_today,
    help="Le jour ou tu as active ton compte Apex. La fenetre se termine le dernier jour de CE mois."
)
challenge_start = pd.Timestamp(challenge_start).date()

# Fin de fenetre = dernier jour calendaire du mois de debut
_window_year  = challenge_start.year
_window_month = challenge_start.month
_month_last_day = calendar.monthrange(_window_year, _window_month)[1]
_month_end = date(_window_year, _window_month, _month_last_day)

# Jours business depuis le debut du challenge jusqu'a aujourd'hui (inclus)
_bdays_done = len(pd.bdate_range(
    start=challenge_start.strftime("%Y-%m-%d"),
    end=_today.strftime("%Y-%m-%d")
))
# Jours business restants (demain → fin du mois de debut)
_tomorrow = (_today + timedelta(days=1)).strftime("%Y-%m-%d")
_bdays_left = len(pd.bdate_range(
    start=_tomorrow,
    end=_month_end.strftime("%Y-%m-%d")
)) if _today < _month_end else 0

_bdays_total = _bdays_done + _bdays_left
# Jours calendaires restants (pour l'affichage)
_cal_days_left = max(0, (_month_end - _today).days)

days_elapsed = _bdays_done
days_remaining_override = st.sidebar.number_input(
    "Jours tradables restants (auto)", value=_bdays_left,
    min_value=0, max_value=23, step=1,
    help="Jours business restants jusqu'a fin du mois de ton challenge. Modifie si besoin."
)

st.sidebar.markdown("---")

# ── Import CSV Rithmic/Apex (optionnel) ──────────────────────────────
def parse_rithmic_csv(uploaded):
    """
    Parse l'export CSV de Rithmic Trader (historique des trades).
    Colonnes attendues (noms Rithmic) : Date, P/L, Buy/Sell ou similaire.
    Retourne : pnl_total_challenge, pnl_today, consec_losses, trades_today,
               trailing_dd_used, peak_equity, df_trades
    """
    try:
        df = pd.read_csv(uploaded)
        df.columns = df.columns.str.strip().str.lower()

        # Normaliser les colonnes — Rithmic a plusieurs formats selon la version
        col_map = {}
        for c in df.columns:
            if "p/l" in c or "pnl" in c or "profit" in c:
                col_map["pnl"] = c
            if "date" in c and "time" not in c:
                col_map["date"] = c
            if "time" in c and "date" not in c:
                col_map["time"] = c

        if "pnl" not in col_map:
            return None, "Colonne P/L introuvable. Exporte depuis Rithmic : Trade History → Export CSV."

        df["_pnl"] = pd.to_numeric(df[col_map["pnl"]], errors="coerce").fillna(0)

        # Date
        if "date" in col_map:
            df["_date"] = pd.to_datetime(df[col_map["date"]], errors="coerce")
        else:
            df["_date"] = pd.Timestamp(_today)

        df = df.dropna(subset=["_date"])
        df = df[df["_date"].dt.date >= challenge_start]  # seulement depuis debut challenge

        if df.empty:
            return None, f"Aucun trade depuis le {challenge_start} dans ce fichier."

        # Metriques challenge
        pnl_total = df["_pnl"].sum()

        today_mask = df["_date"].dt.date == _today
        pnl_today_csv = df.loc[today_mask, "_pnl"].sum()
        trades_today_csv = today_mask.sum()

        # Trailing DD (max peak → current depuis le debut du challenge)
        cumulative = df["_pnl"].cumsum()
        peak_series = cumulative.cummax()
        drawdowns = peak_series - cumulative
        trailing_dd_csv = drawdowns.max()

        # Pertes consecutives (dernieres N lignes)
        consec = 0
        for p in reversed(df["_pnl"].tolist()):
            if p < 0:
                consec += 1
            else:
                break

        return {
            "pnl_total":     round(pnl_total, 2),
            "pnl_today":     round(pnl_today_csv, 2),
            "trades_today":  int(trades_today_csv),
            "consec_losses": consec,
            "trailing_dd":   round(trailing_dd_csv, 2),
            "df":            df[["_date", "_pnl"]].rename(columns={"_date": "Date", "_pnl": "P&L ($)"}),
        }, None
    except Exception as e:
        return None, f"Erreur lecture CSV : {e}"

with st.sidebar.expander("Importer CSV Rithmic (auto-track)", expanded=False):
    st.caption("Rithmic Trader Pro → Account → Trade History → Export CSV")
    uploaded_csv = st.file_uploader("CSV export Rithmic", type=["csv"], label_visibility="collapsed")

_csv_data = None
if uploaded_csv is not None:
    _csv_data, _csv_err = parse_rithmic_csv(uploaded_csv)
    if _csv_err:
        st.sidebar.warning(f"CSV : {_csv_err}")
    else:
        st.sidebar.success(
            f"CSV charge — P&L challenge : ${_csv_data['pnl_total']:+,.0f} | "
            f"Aujourd'hui : ${_csv_data['pnl_today']:+,.0f}"
        )

# Valeurs : CSV si disponible, sinon saisie manuelle
_default_pnl_today   = float(_csv_data["pnl_today"])   if _csv_data else 0.0
_default_consec      = int(_csv_data["consec_losses"])  if _csv_data else 0
_default_trades      = int(_csv_data["trades_today"])   if _csv_data else 0
_default_total       = float(_csv_data["pnl_total"])    if _csv_data else 0.0
_default_dd          = float(_csv_data["trailing_dd"])  if _csv_data else 0.0

# ── Challenge progress (apres CSV pour que les defaults CSV fonctionnent) ─
challenge_pnl_total = st.sidebar.number_input(
    "P&L total challenge ($)",
    value=_default_total, step=50.0,
    help="Cumul de tous tes trades depuis le 1er jour du challenge. Auto si CSV charge."
)
trailing_dd_used = st.sidebar.number_input(
    "Trailing DD utilise ($)",
    value=_default_dd, min_value=0.0, max_value=float(APEX_50K["trailing_dd"]), step=50.0,
    help="Perte max depuis ton plus haut balance. Auto si CSV charge."
)

st.sidebar.subheader("Aujourd'hui")
pnl_today = st.sidebar.number_input("P&L aujourd'hui ($)", value=_default_pnl_today, step=25.0,
    help="Positif si gain, negatif si perte. Auto si CSV charge.")
consec_losses = st.sidebar.number_input("Pertes consecutives", value=_default_consec,
    min_value=0, max_value=5, step=1,
    help="Auto si CSV charge.")
trades_today = st.sidebar.number_input("Nb trades pris aujourd'hui", value=_default_trades,
    min_value=0, step=1,
    help="Auto si CSV charge.")

st.sidebar.markdown("---")
st.sidebar.header("Source données")
st.sidebar.caption("QQQ via yfinance — gratuit, ~1-2 min delai")
refresh_sec = st.sidebar.number_input("Refresh (sec)", value=30, min_value=15, step=5)


# ══════════════════════════════════════════════════════════════════════
# ENGINE
# ══════════════════════════════════════════════════════════════════════

def estimate_ar1(closes):
    """
    Calibre AR(1) : X_t = c + φ·X_{t-1} + ε
    Retourne (φ, μ, σ) ou None.
    Source : kts.py — Roman Paolucci Lec 95
    """
    y = np.array(closes, dtype=float)
    y = y[np.isfinite(y)]
    if len(y) < 5:
        return None
    try:
        x_lag  = y[:-1]
        x_curr = y[1:]
        X      = np.column_stack([np.ones_like(x_lag), x_lag])
        beta   = np.linalg.lstsq(X, x_curr, rcond=None)[0]
        c, phi = float(beta[0]), float(beta[1])
        phi    = np.clip(phi, 0.01, 0.99)
        resid  = x_curr - (c + phi * x_lag)
        sigma  = float(np.sqrt(np.mean(resid ** 2)))
        if sigma <= 0 or not np.isfinite(sigma):
            sigma = max(float(np.std(y)) * 0.01, 1e-9)
        mu = c / (1.0 - phi)
        return phi, mu, sigma
    except Exception:
        return None


class KalmanOU:
    """
    Filtre de Kalman 1D pour processus OU — kts.py Roman Paolucci Lec 95.
    Unifie backtest et live sur le meme moteur.
    """
    def __init__(self, phi, mu, sigma, noise_scale=1.0):
        self.phi = phi
        self.mu  = mu
        self.Q   = sigma ** 2 * max(1.0 - phi ** 2, 1e-6)
        self.R   = sigma ** 2 * max(noise_scale, 0.01)
        self.x   = mu
        self.P   = self.R

    def update(self, z):
        self.x = self.phi * self.x + (1.0 - self.phi) * self.mu
        self.P = self.phi ** 2 * self.P + self.Q
        K      = self.P / (self.P + self.R)
        self.x = self.x + K * (z - self.x)
        self.P = (1.0 - K) * self.P
        return self.x, K


def run_kalman_live(prices, lookback, noise_scale):
    """
    Kalman OU barre par barre — meme algorithme que backtest_kalman.py.
    Retourne : fair_values, sigma_stats, kalman_gains, half_lives
    """
    n            = len(prices)
    fair_values  = np.full(n, np.nan)
    sigma_stats  = np.full(n, np.nan)
    kalman_gains = np.full(n, np.nan)
    half_lives   = np.full(n, np.nan)
    kal          = None

    for i in range(lookback, n):
        window = prices[i - lookback: i]
        params = estimate_ar1(window)
        if params is None:
            continue
        phi, mu, sigma = params
        ss = sigma / np.sqrt(max(1.0 - phi ** 2, 1e-6))
        hl = -np.log(2) / np.log(phi) if phi > 0.001 else 999.0

        if kal is None:
            kal = KalmanOU(phi, mu, sigma, noise_scale)
            for c in window:
                kal.update(c)
        else:
            kal.phi = phi
            kal.mu  = mu
            kal.Q   = sigma ** 2 * max(1.0 - phi ** 2, 1e-6)
            kal.R   = sigma ** 2 * max(noise_scale, 0.01)

        _, K = kal.update(prices[i])
        fair_values[i]  = kal.x
        sigma_stats[i]  = ss
        kalman_gains[i] = K
        half_lives[i]   = hl

    return fair_values, sigma_stats, kalman_gains, half_lives


def clean_price_spikes(df, spike_mult=6.0):
    """
    Supprime les barres avec un prix aberrant (bad tick IBKR).
    Methode : si le close s'ecarte de plus de spike_mult * rolling_std
    de la mediane glissante sur 20 barres → remplace par NaN puis forward-fill.
    """
    closes = df["close"].values.astype(float).copy()
    n = len(closes)
    window = 20

    for i in range(window, n):
        local = closes[max(0, i - window):i]
        median = np.median(local)
        std = np.std(local)
        if std < 1e-6:
            continue
        if abs(closes[i] - median) > spike_mult * std:
            closes[i] = np.nan

    # Forward-fill les NaN
    s = pd.Series(closes)
    s = s.ffill().bfill()
    df = df.copy()
    df["close"] = s.values
    return df


def compute_atr(highs, lows, closes, period=14):
    """ATR."""
    tr = np.maximum(
        highs - lows,
        np.maximum(abs(highs - np.roll(closes, 1)), abs(lows - np.roll(closes, 1)))
    )
    tr[0] = highs[0] - lows[0]
    return pd.Series(tr).rolling(period, min_periods=1).mean().values


def fetch_bars_yf(days=3):
    """Recupere les barres 1 min de QQQ via yfinance (~1-2 min de delai, gratuit)."""
    try:
        df = yf.Ticker("QQQ").history(period=f"{days}d", interval="1m", auto_adjust=True)
        if df is None or df.empty:
            return None
        df = df.reset_index()
        ts_col = "Datetime" if "Datetime" in df.columns else df.columns[0]
        df.rename(columns={ts_col: "bar", "Open": "open", "High": "high",
                            "Low": "low", "Close": "close", "Volume": "volume"}, inplace=True)
        df["bar"] = pd.to_datetime(df["bar"], utc=True)
        return df[["bar", "open", "high", "low", "close", "volume"]].sort_values("bar").reset_index(drop=True)
    except Exception as e:
        st.error(f"Erreur yfinance : {e}")
        return None


def refresh_bars_yf(existing_df):
    """Mise a jour incrementale : recupere la journee en cours."""
    try:
        df = yf.Ticker("QQQ").history(period="1d", interval="1m", auto_adjust=True)
        if df is None or df.empty:
            return existing_df
        df = df.reset_index()
        ts_col = "Datetime" if "Datetime" in df.columns else df.columns[0]
        df.rename(columns={ts_col: "bar", "Open": "open", "High": "high",
                            "Low": "low", "Close": "close", "Volume": "volume"}, inplace=True)
        df["bar"] = pd.to_datetime(df["bar"], utc=True)
        new_df = df[["bar", "open", "high", "low", "close", "volume"]]
        combined = pd.concat([existing_df, new_df], ignore_index=True)
        return combined.drop_duplicates(subset=["bar"]).sort_values("bar").reset_index(drop=True)
    except Exception:
        return existing_df


# ══════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════

if not HAS_YF:
    st.error("pip install yfinance")
    st.stop()

st.markdown("**Source:** QQQ via yfinance (gratuit) → signal MNQ sur Apex")

col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 4])
if col_btn1.button("Demarrer", type="primary"):
    st.session_state["live_running"] = True
    st.session_state.pop("bars_cache", None)

if col_btn2.button("Arreter"):
    st.session_state["live_running"] = False
    st.session_state.pop("bars_cache", None)

if not st.session_state.get("live_running"):
    st.stop()

# ── Chargement des barres ─────────────────────────────────────────────
is_first_load = "bars_cache" not in st.session_state

if is_first_load:
    with st.spinner("Chargement des barres QQQ..."):
        bars_df = fetch_bars_yf(days=3)

    if bars_df is None or len(bars_df) < kalman_lookback:
        st.error(f"Pas assez de barres ({len(bars_df) if bars_df is not None else 0}). "
                 f"Le marche est peut-etre ferme (QQQ trade 9h30-16h00 ET).")
        st.session_state["live_running"] = False
        st.stop()

    st.session_state["bars_cache"] = bars_df
    st.success(f"Connecte — {len(bars_df)} barres QQQ chargees")
else:
    existing = st.session_state["bars_cache"]
    bars_df = refresh_bars_yf(existing)
    st.session_state["bars_cache"] = bars_df

# ── Nettoyage spikes avant Kalman ─────────────────────────────────────
bars_df = clean_price_spikes(bars_df, spike_mult=6.0)

# ── Kalman ───────────────────────────────────────────────────────────
prices = bars_df["close"].values.astype(float)
highs = bars_df["high"].values.astype(float)
lows = bars_df["low"].values.astype(float)

fair_values, sigma_stats, k_gains, half_lives = run_kalman_live(prices, kalman_lookback, kalman_R_mult)
atr = compute_atr(highs, lows, prices)

last_idx = len(prices) - 1
last_price = prices[last_idx]
fv = fair_values[last_idx]
ss = sigma_stats[last_idx]
kg = k_gains[last_idx]
last_atr = atr[last_idx]
last_hl = half_lives[last_idx]

if np.isnan(fv) or np.isnan(ss):
    st.error("Kalman pas encore calibre.")
    st.stop()

# ── Filtres signal (identiques backtest) ─────────────────────────────
now_utc_bar = datetime.now(timezone.utc)
sess_start = now_utc_bar.replace(hour=session_start_h, minute=session_start_m, second=0, microsecond=0)
sess_end   = now_utc_bar.replace(hour=session_end_h,   minute=session_end_m,   second=0, microsecond=0)
in_session = sess_start <= now_utc_bar <= sess_end

# Déviation en σ
deviation_sigma = (last_price - fv) / ss if ss > 0 else 0.0

# Confirmation reversion
reversal_ok = True
if confirm_reversal_live and last_idx > 0 and not np.isnan(fair_values[last_idx - 1]):
    prev_dev = abs(prices[last_idx - 1] - fair_values[last_idx - 1])
    curr_dev = abs(last_price - fv)
    reversal_ok = (curr_dev < prev_dev)

# Filtre σ_stat max (marché trending → OU invalide)
vol_ok = (max_sigma_stat == 0) or (ss <= max_sigma_stat)

# Filtre band_k_max (spike/gap extrême → ignorer)
dev_ok = abs(deviation_sigma) <= band_k_max

# Filtre max trades/jour
trades_ok = trades_today < max_trades_per_day

filters_pass = reversal_ok and vol_ok and dev_ok and in_session and trades_ok

# ── Detection donnees perimees ─────────────────────────────────────────
try:
    last_bar_ts = pd.to_datetime(bars_df["bar"].iloc[-1], utc=True)
    data_age_min = (datetime.now(timezone.utc) - last_bar_ts.to_pydatetime()).total_seconds() / 60
except Exception:
    data_age_min = 0.0

DATA_STALE_WARN = 5
DATA_STALE_ERROR = 20

upper = fv + band_k * ss
lower = fv - band_k * ss
# SL identique backtest : sl_sigma_mult × σ_kalman, min sl_min_pts
sl_pts = max(sl_sigma_mult * ss, min_sl_pts)
tp_pts = abs(last_price - fv) * tp_ratio

# ══════════════════════════════════════════════════════════════════════
# CHALLENGE APEX 50K EOD — MONEY MANAGEMENT
# Basé sur backtest : WR=42%, PF=2, ratio win/loss=2.75
# Kelly fraction = WR - (1-WR)/ratio = 0.42 - 0.58/2.75 = 21%
# Half-Kelly utilisé = 10% du trailing DD restant par trade
# ══════════════════════════════════════════════════════════════════════
st.markdown("---")
MNQ_POINT = 2.0  # 1 point MNQ = $2

# ── Calculs challenge ─────────────────────────────────────────────────
trailing_dd_remaining = APEX_50K["trailing_dd"] - trailing_dd_used
days_remaining        = max(1, days_remaining_override)  # jours business restants ce mois
pnl_needed            = max(0.0, APEX_50K["profit_target"] - challenge_pnl_total)
daily_needed          = pnl_needed / days_remaining
losses_today          = max(0.0, -pnl_today)   # pertes du jour (positif)

# ── Determination de la phase ─────────────────────────────────────────
# Phase SECURITE : 80%+ de l'objectif atteint → proteger le gain
# Phase PRUDENTE : premiers 5 jours OU >50% du DD utilise → taille mini
# Phase PUSH     : derniers 5 jours ET <80% objectif ET DD intact → taille max
# Phase STANDARD : tous les autres cas → taille normale

dd_pct_used = trailing_dd_used / APEX_50K["trailing_dd"]   # 0→1
challenge_pct_done = challenge_pnl_total / APEX_50K["profit_target"]

# Pas de limite de trades imposee par Apex — on trade tant que le signal existe
# et que les stops internes (daily loss, consecutive losses, DD) ne sont pas atteints
if challenge_pct_done >= 0.80:
    phase = "SECURITE"
    phase_color = CYAN
    risk_pct_dd = 0.04   # 4% du DD restant → ultra-conservateur
    phase_desc = "80%+ atteint — taille mini, protege le gain"
elif dd_pct_used > 0.50 or trailing_dd_remaining < 400:
    phase = "PRUDENTE"
    phase_color = YELLOW
    risk_pct_dd = 0.05   # 5% du DD restant
    phase_desc = "DD > 50% utilise — taille reduite, qualite avant tout"
elif days_remaining <= 5 and challenge_pct_done < 0.80:
    phase = "PUSH"
    phase_color = ORANGE
    risk_pct_dd = 0.15   # 15% du DD restant
    phase_desc = "Derniers jours — taille augmentee si signal fort"
elif days_elapsed <= 5:
    phase = "PRUDENTE"
    phase_color = YELLOW
    risk_pct_dd = 0.05
    phase_desc = "Debut du challenge — taille mini, apprends le marche"
else:
    phase = "STANDARD"
    phase_color = GREEN
    risk_pct_dd = 0.10   # 10% du DD restant = Half-Kelly
    phase_desc = "Execution mecanique — risque 10% du DD restant par trade"

# ── Calcul du risque et des contrats ─────────────────────────────────
risk_per_trade = max(80.0, min(trailing_dd_remaining * risk_pct_dd, 600.0))
sl_dollars_per_contract = sl_pts * MNQ_POINT
nb_contracts = max(1, int(risk_per_trade / sl_dollars_per_contract)) if sl_dollars_per_contract > 0 else 1
nb_contracts = min(nb_contracts, APEX_50K["max_contracts"])
total_risk_trade  = nb_contracts * sl_dollars_per_contract
total_tp_trade    = nb_contracts * tp_pts * MNQ_POINT

# Daily hard stops
# Regle Apex EOD 50K : $1 000/jour fixe
# On stop a $800 pour garder $200 de marge (evite de toucher exactement la limite)
daily_loss_hard   = min(APEX_50K["daily_loss"] * 0.80, trailing_dd_remaining * 0.32)

# ── EOD check ────────────────────────────────────────────────────────
now_utc = datetime.now(timezone.utc)
eod_utc = now_utc.replace(hour=21, minute=45, second=0, microsecond=0)
past_eod = now_utc.time() > eod_utc.time()
near_eod = (not past_eod) and (now_utc.hour == 21 and now_utc.minute >= 30)
if past_eod:
    mins_to_eod = 0
else:
    mins_to_eod = max(0, int((eod_utc - now_utc).total_seconds() / 60))

# ── Autorisation de trader ───────────────────────────────��────────────
# Pas de limite de trades Apex — on stop uniquement sur DD, daily loss, consec, EOD
block_daily_loss = losses_today >= daily_loss_hard
block_consec     = consec_losses >= 2
block_dd         = trailing_dd_remaining <= 100
block_eod        = past_eod or near_eod
can_trade = not any([block_daily_loss, block_consec, block_dd, block_eod])

# ══════════════════════════════════════════════════════════════════════
# AFFICHAGE CHALLENGE
# ══════════════════════════════════════════════════════════════════════
st.markdown("""<div style='font-family:JetBrains Mono,monospace;font-size:0.65rem;letter-spacing:0.2em;color:#3CC4B7;text-transform:uppercase;margin:1.5rem 0 0.8rem'>CHALLENGE APEX 50K EOD TRAIL</div>""", unsafe_allow_html=True)

# ── Ligne 1 : Progression challenge ──────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric(
    "Objectif",
    f"${challenge_pnl_total:+,.0f} / ${APEX_50K['profit_target']:,}",
    delta=f"{challenge_pct_done*100:.0f}% atteint",
    delta_color="normal"
)
c2.metric(
    f"Mois en cours ({_today.strftime('%b %Y')})",
    f"Jour {days_elapsed} / {_bdays_total}",
    delta=f"{days_remaining} jours restants ce mois",
    delta_color="inverse" if days_remaining <= 3 else "normal"
)
c3.metric(
    "A faire / jour",
    f"${daily_needed:.0f}",
    delta="objectif journalier"
)
c4.metric(
    "Trailing DD restant",
    f"${trailing_dd_remaining:,.0f}",
    delta=f"{dd_pct_used*100:.0f}% utilise",
    delta_color="inverse" if dd_pct_used > 0.3 else "normal"
)
c5.metric(
    f"Phase : {phase}",
    f"{risk_pct_dd*100:.0f}% DD / trade",
    delta=phase_desc
)

# Barre progression objectif
st.markdown(f"**Progression objectif : {challenge_pct_done*100:.0f}%**")
st.progress(min(challenge_pct_done, 1.0))

# Barre trailing DD
st.markdown(f"**Trailing drawdown utilise : {dd_pct_used*100:.0f}%** (max ${APEX_50K['trailing_dd']:,} EOD)")
st.progress(min(dd_pct_used, 1.0))

# ── Alerte fenetre mensuelle ──────────────────────────────────────────
_month_name = f"{challenge_start.strftime('%d %b')} → {_month_end.strftime('%d %b %Y')}"
if challenge_pct_done >= 1.0:
    st.success(f"CHALLENGE PASSE — Objectif ${APEX_50K['profit_target']:,} atteint ce mois !")
elif days_remaining == 0:
    st.error(
        f"FIN DE MOIS ({_month_name}) — Objectif non atteint "
        f"(${challenge_pnl_total:+,.0f} / ${APEX_50K['profit_target']:,}). "
        f"Le challenge repart de zero le 1er du mois prochain."
    )
elif days_remaining <= 3:
    daily_needed_push = pnl_needed / days_remaining if days_remaining > 0 else pnl_needed
    st.error(
        f"URGENCE — {days_remaining} jour(s) restant(s) en {_month_name}. "
        f"Il faut ${pnl_needed:.0f} en {days_remaining} jours "
        f"(${daily_needed_push:.0f}/jour). Phase PUSH activee si DD intact."
    )
elif days_remaining <= 5:
    st.warning(
        f"{days_remaining} jours business restants en {_month_name}. "
        f"Encore ${pnl_needed:.0f} a faire — "
        f"${daily_needed:.0f}/jour necessaires."
    )

# ── Ligne 2 : Regles du jour ──────────────────────────────────────────
st.markdown(f"#### Regles d'aujourd'hui — Phase <span style='color:{phase_color};font-weight:bold'>{phase}</span>", unsafe_allow_html=True)
r1, r2, r3, r4, r5 = st.columns(5)

r1.metric("Risque / trade", f"${risk_per_trade:.0f}",
          delta=f"{risk_pct_dd*100:.0f}% du DD restant")
r2.metric(f"Contrats x{nb_contracts}",
          f"SL ${total_risk_trade:.0f} / TP ${total_tp_trade:.0f}",
          delta=f"SL = {sl_pts:.1f} pts")
r3.metric("Daily loss stop", f"${daily_loss_hard:.0f}",
          delta=f"-${losses_today:.0f} aujourd'hui",
          delta_color="inverse" if losses_today > 0 else "off")
r4.metric("Trades aujourd'hui", f"{trades_today}",
          delta=f"{consec_losses} pertes consec.",
          delta_color="inverse" if consec_losses >= 1 else "off")

# EOD
paris_offset = 2
eod_paris = f"{(21 + paris_offset) % 24:02d}:45"
if past_eod:
    r5.metric("EOD", "FERME", delta="Flat obligatoire", delta_color="inverse")
elif near_eod:
    r5.metric("EOD", f"{mins_to_eod} min", delta="FERME TES POSITIONS !", delta_color="inverse")
else:
    r5.metric("EOD (flat)", eod_paris + " Paris", delta=f"dans {mins_to_eod} min")

# ── Status GO / STOP ──────────────────────────────────────────────────
if block_dd:
    st.error("ARRET TOTAL — Trailing drawdown critique (<$100 restant). Ne trade plus ce compte.")
elif block_eod and past_eod:
    st.error("SESSION FERMEE — Apres 21h45 UTC. Verifie que tu es flat sur Apex.")
elif block_eod and near_eod:
    st.warning("FERME TES POSITIONS — Moins de 15 min avant EOD obligatoire (21h45 UTC).")
elif block_daily_loss:
    st.error(f"STOP DU JOUR — Daily loss atteinte (${losses_today:.0f} / ${daily_loss_hard:.0f}). Ne trade plus aujourd'hui.")
elif block_consec:
    st.error("STOP DU JOUR — 2 pertes consecutives. Regle absolue : arrete maintenant.")
else:
    st.success(f"GO — Phase {phase} | Risque ${risk_per_trade:.0f} | {nb_contracts} contrat(s) MNQ | Daily loss restant : ${daily_loss_hard - losses_today:.0f}")

# ── SIGNAL ───────────────────────────────────────────────────────────
st.markdown("---")
deviation = deviation_sigma  # alias pour l'affichage

# Guard : deviation > band_k_max = probable bad tick → ignorer (filtre déjà dans filters_pass)
MAX_VALID_DEVIATION = band_k_max
data_error = not dev_ok

if data_error:
    signal = "PAS DE SIGNAL"
    signal_color = YELLOW
    entry = sl = tp = None
elif last_price > upper:
    if filters_pass:
        signal = "SHORT"
        signal_color = RED
    else:
        signal = "ATTENDRE"
        signal_color = YELLOW
    entry = last_price
    sl = entry + sl_pts
    tp = fv
elif last_price < lower:
    if filters_pass:
        signal = "LONG"
        signal_color = GREEN
    else:
        signal = "ATTENDRE"
        signal_color = YELLOW
    entry = last_price
    sl = entry - sl_pts
    tp = fv
else:
    signal = "PAS DE SIGNAL"
    signal_color = YELLOW
    entry = sl = tp = None

# ── Alerte son sur changement de signal ──────────────────────────────
prev_signal = st.session_state.get("prev_signal", "PAS DE SIGNAL")
signal_changed = (signal != prev_signal) and (signal in ("LONG", "SHORT"))
st.session_state["prev_signal"] = signal

if signal_changed:
    # Frequence differente selon direction
    freq = 880 if signal == "SHORT" else 440  # SHORT = aigu, LONG = grave
    beep_js = f"""
    <script>
    (function() {{
        var ctx = new (window.AudioContext || window.webkitAudioContext)();
        function beep(freq, duration, vol) {{
            var osc = ctx.createOscillator();
            var gain = ctx.createGain();
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.frequency.value = freq;
            osc.type = 'sine';
            gain.gain.setValueAtTime(vol, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);
            osc.start(ctx.currentTime);
            osc.stop(ctx.currentTime + duration);
        }}
        beep({freq}, 0.4, 0.5);
        setTimeout(function() {{ beep({freq}, 0.4, 0.4); }}, 500);
        setTimeout(function() {{ beep({freq}, 0.6, 0.5); }}, 1000);
    }})();
    </script>
    """
    st_components.html(beep_js, height=0)

# ── Alertes donnees ───────────────────────────────────────────────────
if data_error:
    st.error(f"BAD TICK — deviation {deviation:+.1f}σ > {MAX_VALID_DEVIATION}σ. Signal IGNORE.")
elif data_age_min > DATA_STALE_ERROR:
    st.error(f"DONNEES PERIMEES — {data_age_min:.0f} min. Verifie yfinance.")
elif data_age_min > DATA_STALE_WARN:
    st.warning(f"Donnees en retard de {data_age_min:.0f} min.")

# ── Signal principal (grand affichage) ───────────────────────────────
_sig_bg = {"LONG": "rgba(0,255,136,0.06)", "SHORT": "rgba(255,51,102,0.06)"}.get(signal, "rgba(255,214,0,0.04)")
_sig_border = signal_color
_sig_cls = {"LONG": "long", "SHORT": "short"}.get(signal, "none")

# Indicateurs filtres
_rev_icon  = "✓" if reversal_ok else "✗"
_vol_icon  = "✓" if vol_ok      else "✗"
_sess_icon = "✓" if in_session  else "✗"
_trd_icon  = "✓" if trades_ok   else "✗"
_filter_detail = (
    f"Reversion {_rev_icon} &nbsp;·&nbsp; Vol {_vol_icon} "
    f"&nbsp;·&nbsp; Session {_sess_icon} &nbsp;·&nbsp; Trades {trades_today}/{max_trades_per_day} {_trd_icon}"
)

st.markdown(f"""
<div class="signal-box {_sig_cls}" style="background:{_sig_bg};border-color:{_sig_border}22">
    <div class="signal-text" style="color:{signal_color}">{signal}</div>
    <div class="signal-sub">QQQ → MNQ &nbsp;·&nbsp; Deviation: {deviation:+.2f}σ &nbsp;·&nbsp; Data: {data_age_min:.0f} min</div>
    <div class="signal-sub" style="margin-top:4px;font-size:0.7rem;color:#444">{_filter_detail}</div>
</div>
""", unsafe_allow_html=True)

# ── Metriques prix ────────────────────────────────────────────────────
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Prix QQQ", f"{last_price:,.2f}")
m2.metric("Fair Value", f"{fv:,.2f}")
m3.metric("Deviation", f"{deviation:+.2f}σ")
m4.metric("Bande haute", f"{upper:,.2f}")
m5.metric("Bande basse", f"{lower:,.2f}")

# ── Execution ─────────────────────────────────────────────────────────
if entry:
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(f"<p style='color:#888;font-size:0.8rem;letter-spacing:0.1em'>EXECUTION SUR APEX — {nb_contracts} CONTRAT(S) MNQ</p>", unsafe_allow_html=True)
    e1, e2, e3, e4, e5 = st.columns(5)
    e1.metric("Entry", f"{entry:,.2f}")
    e2.metric("Stop Loss", f"{sl:,.2f}", delta=f"{sl_pts:.1f} pts")
    e3.metric("Take Profit", f"{tp:,.2f}", delta=f"{tp_pts:.1f} pts")
    e4.metric("R:R", f"{tp_pts/sl_pts:.1f}" if sl_pts > 0 else "N/A")
    e5.metric("Risque trade", f"${total_risk_trade:.0f}", delta=f"+${total_tp_trade:.0f} si TP")

    if not can_trade:
        st.error("NE PAS TRADER — voir les regles du jour ci-dessus")

# ── CHART ────────────────────────────────────────────────────────────
show_bars = min(160, len(prices))
chart_prices  = prices[-show_bars:]
chart_fv      = fair_values[-show_bars:]
chart_ss      = sigma_stats[-show_bars:]
chart_upper   = chart_fv + band_k * chart_ss
chart_lower   = chart_fv - band_k * chart_ss
chart_dev     = np.where(chart_ss > 0, (chart_prices - chart_fv) / chart_ss, 0.0)

paris_offset = 2
try:
    bar_times = bars_df["bar"].iloc[-show_bars:].reset_index(drop=True)
    x_vals = list(
        pd.to_datetime(bar_times, utc=True)
        .map(lambda t: (t + pd.Timedelta(hours=paris_offset)).strftime("%H:%M"))
    )
except Exception:
    x_vals = list(range(show_bars))

_AXIS = dict(
    gridcolor="rgba(255,255,255,0.03)",
    linecolor="#111",
    tickfont=dict(color="#333", size=10, family="JetBrains Mono"),
    zeroline=False,
    showgrid=True,
)

fig = make_subplots(
    rows=2, cols=1,
    row_heights=[0.72, 0.28],
    shared_xaxes=True,
    vertical_spacing=0.04,
)

# ── Panneau 1 : Prix + Kalman ─────────────────────────────────────────
# Zone entre les bandes (remplissage subtil)
fig.add_trace(go.Scatter(
    x=x_vals, y=chart_upper, mode="lines",
    line=dict(color="rgba(60,196,183,0.25)", width=1, dash="dot"),
    name=f"+{band_k}σ", showlegend=False,
), row=1, col=1)

fig.add_trace(go.Scatter(
    x=x_vals, y=chart_lower, mode="lines",
    line=dict(color="rgba(60,196,183,0.25)", width=1, dash="dot"),
    fill="tonexty", fillcolor="rgba(60,196,183,0.04)",
    name=f"Bande {band_k}σ",
), row=1, col=1)

# Fair Value
fig.add_trace(go.Scatter(
    x=x_vals, y=chart_fv, mode="lines",
    line=dict(color=TEAL, width=1.5),
    name="Fair Value",
), row=1, col=1)

# Prix
fig.add_trace(go.Scatter(
    x=x_vals, y=chart_prices, mode="lines",
    line=dict(color="rgba(255,255,255,0.75)", width=1.2),
    name="QQQ",
), row=1, col=1)

# Dernier prix — point accentué
fig.add_trace(go.Scatter(
    x=[x_vals[-1]], y=[chart_prices[-1]], mode="markers",
    marker=dict(color=signal_color, size=7, symbol="circle",
                line=dict(color="#060606", width=1.5)),
    name="Now", showlegend=False,
), row=1, col=1)

# Lignes d'exécution si signal actif
if entry is not None:
    fig.add_hline(y=entry, line_dash="solid", line_color=signal_color, line_width=1,
                  opacity=0.6, row=1, col=1,
                  annotation_text=f"  {signal}  {entry:,.2f}",
                  annotation_font=dict(color=signal_color, size=11, family="JetBrains Mono"),
                  annotation_position="top left")
    fig.add_hline(y=sl, line_dash="dot", line_color=RED, line_width=1,
                  opacity=0.4, row=1, col=1,
                  annotation_text=f"  SL  {sl:,.2f}",
                  annotation_font=dict(color=RED, size=10, family="JetBrains Mono"),
                  annotation_position="bottom left")
    fig.add_hline(y=tp, line_dash="dot", line_color=GREEN, line_width=1,
                  opacity=0.4, row=1, col=1,
                  annotation_text=f"  TP  {tp:,.2f}",
                  annotation_font=dict(color=GREEN, size=10, family="JetBrains Mono"),
                  annotation_position="top left")

# ── Panneau 2 : Déviation z-score ─────────────────────────────────────
dev_colors = [RED if d > 0 else GREEN for d in chart_dev]

fig.add_trace(go.Bar(
    x=x_vals, y=chart_dev,
    marker_color=dev_colors,
    marker_opacity=0.55,
    name="Déviation σ",
    showlegend=False,
), row=2, col=1)

# Lignes seuil bande
fig.add_hline(y=band_k,  line_dash="dot", line_color="rgba(255,51,102,0.4)",  line_width=1, row=2, col=1)
fig.add_hline(y=-band_k, line_dash="dot", line_color="rgba(0,255,136,0.4)",   line_width=1, row=2, col=1)
fig.add_hline(y=0,       line_dash="solid", line_color="rgba(255,255,255,0.06)", line_width=1, row=2, col=1)

fig.update_layout(
    height=780,
    paper_bgcolor="rgba(6,6,6,0)",
    plot_bgcolor="rgba(8,8,8,1)",
    font=dict(color="#555", size=11, family="JetBrains Mono"),
    margin=dict(t=16, b=24, l=54, r=20),
    legend=dict(
        orientation="h", y=1.02, x=0,
        bgcolor="rgba(0,0,0,0)",
        font=dict(color="#444", size=10),
        borderwidth=0,
    ),
    hovermode="x unified",
    hoverlabel=dict(bgcolor="#0d0d0d", bordercolor="#1a1a1a", font=dict(color="#ccc", size=11)),
    xaxis=dict(**_AXIS, tickangle=-30, nticks=16, showticklabels=False),
    yaxis=dict(**_AXIS, title=dict(text="Prix", font=dict(color="#333", size=10)), tickformat=".2f"),
    xaxis2=dict(**_AXIS, tickangle=-30, nticks=16, title=dict(text="Heure Paris", font=dict(color="#333", size=10))),
    yaxis2=dict(**_AXIS, title=dict(text="σ", font=dict(color="#333", size=10)), tickformat=".1f",
                range=[-max(band_k * 1.8, abs(float(np.nanmin(chart_dev))) * 1.1),
                        max(band_k * 1.8, abs(float(np.nanmax(chart_dev))) * 1.1)]),
    bargap=0.1,
    template="plotly_dark",
)

st.plotly_chart(fig, use_container_width=True)

now_utc = datetime.now(timezone.utc)
paris_time = f"{(now_utc.hour + paris_offset) % 24:02d}:{now_utc.strftime('%M:%S')} Paris"
st.markdown(
    f"<div style='font-family:JetBrains Mono,monospace;font-size:0.68rem;color:#333;margin-top:-0.5rem'>"
    f"{len(bars_df)} barres &nbsp;·&nbsp; ATR {last_atr:.2f} pts &nbsp;·&nbsp; "
    f"SL {sl_pts:.1f} pts &nbsp;·&nbsp; K {kg:.3f} &nbsp;·&nbsp; {paris_time}"
    f"</div>",
    unsafe_allow_html=True,
)

# ── Countdown + auto-refresh ──────────────────────────────────────────
countdown = st.empty()
for remaining in range(int(refresh_sec), 0, -1):
    countdown.info(f"Prochain refresh dans **{remaining}s**...")
    time.sleep(1)
countdown.empty()
st.rerun()