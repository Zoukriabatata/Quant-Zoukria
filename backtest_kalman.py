"""
Backtest Kalman OU Mean Reversion — MNQ M1 CSV / Apex 50K EOD Trail
Basé sur Roman Paolucci Lec 95 — Trading Mean Reversion with Kalman Filters
github.com/romanmichaelpaolucci/Quant-Guild-Library

Architecture :
  Signal : MNQ M1 CSV (Databento, front-month par volume) — 1 an ou 2 ans
  Execution : MNQ sur Apex ($2/pt direct)
Pipeline :
  AR(1) calibration rolling → KalmanOU filter (fair value adaptatif)
  Entrée : |prix MNQ - FV| > k × σ_stat
  TP : retour au FV (tp_ratio × distance)
  SL : sl_sigma × σ_stat au-delà de l'entrée
  P&L : result_pts × $2/pt MNQ × contrats
"""

import os
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ── Theme ─────────────────────────────────────────────────────────────
DARK = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(6,6,6,0)",
    plot_bgcolor="rgba(10,10,10,1)",
    font=dict(color="#888", size=12, family="JetBrains Mono"),
    margin=dict(t=50, b=40, l=50, r=30),
)
TEAL, CYAN, MAGENTA, GREEN, RED = "#3CC4B7", "#00e5ff", "#ff00e5", "#00ff88", "#ff3366"
YELLOW, ORANGE = "#ffd600", "#ff9100"

st.set_page_config(page_title="Backtest Kalman OU", page_icon="📊", layout="wide")

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
/* Page header */
.page-header { padding: 1.5rem 0 0.5rem; border-bottom: 1px solid #1a1a1a; margin-bottom: 1.5rem; }
.page-tag { font-family: 'JetBrains Mono', monospace; font-size: 0.65rem; letter-spacing: 0.2em; color: #3CC4B7; text-transform: uppercase; }
.page-title { font-size: 1.8rem; font-weight: 700; color: #fff; letter-spacing: -0.02em; margin: 0.3rem 0 0; }
/* Section label */
.section-label { font-family: 'JetBrains Mono', monospace; font-size: 0.6rem; font-weight: 700;
    letter-spacing: 0.2em; color: #3CC4B7; text-transform: uppercase; margin: 1.8rem 0 0.8rem; }
/* Stats row */
.stat-row { display: flex; gap: 0; border: 1px solid #1a1a1a; border-radius: 10px; overflow: hidden; margin: 0.5rem 0 1rem; }
.stat-cell { flex: 1; padding: 1.2rem 1rem; text-align: center; border-right: 1px solid #1a1a1a; background: #060606; transition: background 0.15s; }
.stat-cell:last-child { border-right: none; }
.stat-cell:hover { background: #0d0d0d; }
.stat-num { font-size: 1.6rem; font-weight: 700; font-family: 'JetBrains Mono', monospace; letter-spacing: -0.02em; }
.stat-lbl { font-size: 0.58rem; color: #444; letter-spacing: 0.14em; text-transform: uppercase; margin-top: 0.25rem; }
/* Result block */
.result-block { background: #080808; border: 1px solid #141414; border-radius: 10px;
    padding: 1.2rem 1.5rem; font-family: 'JetBrains Mono', monospace; font-size: 0.82rem; line-height: 2; margin: 0.5rem 0; }
.result-row { display: flex; gap: 1rem; align-items: center; }
.result-key { color: #3CC4B7; min-width: 160px; font-weight: 500; }
.result-val { color: #888; }
.result-val.green { color: #00ff88; }
.result-val.red { color: #ff3366; }
/* Info card */
.info-card { background: #080808; border: 1px solid #141414; border-radius: 10px; padding: 1.2rem 1.5rem; margin: 0.5rem 0; }
.info-card-title { font-family: 'JetBrains Mono', monospace; font-size: 0.6rem; letter-spacing: 0.18em; color: #3CC4B7; text-transform: uppercase; margin-bottom: 0.6rem; }
""")

st.markdown("""
<div class="page-header">
    <div class="page-tag">BACKTEST · MNQ M1 CSV · APEX 50K EOD</div>
    <div class="page-title">Backtest Kalman OU — MNQ M1</div>
</div>
""", unsafe_allow_html=True)

CSV_PATH = r"C:\Users\ryadb\Downloads\data OHLCV M1\glbx-mdp3-20240330-20260329.ohlcv-1m.csv"

if not os.path.exists(CSV_PATH):
    st.error(f"Fichier CSV introuvable : `{CSV_PATH}`")
    st.stop()

# ── Sidebar ───────────────────────────────────────────────────────────
st.sidebar.header("Données — MNQ M1 CSV")
st.sidebar.caption("Databento MNQ 1-min, front-month par volume. Mar 2024 → Mar 2026.")

csv_years = st.sidebar.radio(
    "Période",
    options=[1, 2],
    index=1,
    format_func=lambda x: f"{x} an{'s' if x > 1 else ''}",
    help="1 an = avr 2025 → mars 2026 | 2 ans = avr 2024 → mars 2026",
    horizontal=True,
)

st.sidebar.markdown("---")
st.sidebar.header("Kalman OU")
kalman_lookback = st.sidebar.number_input(
    "Lookback calibration (barres)", value=120, min_value=30, step=10,
    help="Fenêtre AR(1) pour calibrer φ, μ, σ. 120 barres = 2h en 1m."
)
band_k = st.sidebar.number_input(
    "Bande k min (σ)", value=1.5, min_value=0.3, max_value=4.0, step=0.1,
    help="Entrée quand |prix - FV| > k × σ_stat. 1.5 = bon équilibre fréquence/edge."
)
band_k_max = st.sidebar.number_input(
    "Bande k max (σ)", value=4.0, min_value=0.5, max_value=10.0, step=0.5,
    help="Ignore si déviation > k_max (évite les crashes/gaps extrêmes)"
)
noise_scale = st.sidebar.slider(
    "Noise lever (confiance modèle OU vs prix)", min_value=0.1, max_value=20.0, value=5.0, step=0.1,
    help=(
        "R = σ² × noise_scale — contrôle l'adaptabilité du Kalman (kts.py Roman Paolucci).\n"
        "Faible (0.1) = suit les prix de près → très adaptatif → sensible au bruit.\n"
        "Élevé (20) = fait confiance au modèle OU → lisse → lent à s'adapter."
    )
)
confirm_reversal = st.sidebar.toggle(
    "Confirmation reversion (Lec 72)",
    value=True,
    help="N'entrer qu'à la barre i+1 si elle est déjà plus proche du FV que la barre signal.\n"
         "Réduit les faux signaux au prix de moins de trades."
)
max_sigma_stat = st.sidebar.number_input(
    "σ_stat max (filtre vol)", value=15.0, min_value=0.0, max_value=100.0, step=1.0,
    help="Skip si σ_stat > seuil. σ_stat élevé = marché trending/volatile → mean reversion peu fiable. "
         "0 = désactivé."
)

st.sidebar.markdown("---")
st.sidebar.header("Risk")
sl_sigma_mult = st.sidebar.slider(
    "SL = k × σ_kalman", min_value=0.25, max_value=3.0, value=0.75, step=0.25,
    help="Stop = sl_sigma × σ_stat au-delà de l'entrée. 0.75 avec band_k=1.5 → R:R=2:1."
)
min_sl_pts = st.sidebar.number_input("SL min (pts)", value=4.0, step=0.5)
tp_ratio = st.sidebar.slider(
    "TP ratio (% distance vers FV)", min_value=0.25, max_value=1.0, value=1.0, step=0.05,
    help="1.0 = TP au FV complet. 0.5 = mi-chemin (WR ~50%, R:R plus faible)."
)

st.sidebar.markdown("---")
st.sidebar.header("Réalisme")
slippage_ticks = st.sidebar.number_input("Slippage (ticks)", value=2, min_value=0, step=1)

st.sidebar.markdown("---")
st.sidebar.header("Session")
session_start_h = st.sidebar.number_input("Début (h UTC)", value=14, min_value=0, max_value=23)
session_start_m = st.sidebar.number_input("Début (min)", value=30, min_value=0, max_value=59)
session_end_h   = st.sidebar.number_input("Fin (h UTC)", value=21, min_value=0, max_value=23)
session_end_m   = st.sidebar.number_input("Fin (min)", value=0, min_value=0, max_value=59)
skip_open_bars  = st.sidebar.number_input(
    "Skip barres ouverture", value=15, min_value=0, step=5,
    help="Évite la volatilité d'ouverture (Roman #72)"
)
skip_close_bars = st.sidebar.number_input(
    "Skip barres clôture", value=15, min_value=0, step=5,
    help="Évite le closing gamma (Roman #74)"
)
max_trades_per_day = st.sidebar.number_input(
    "Max trades/jour", value=2, min_value=1, max_value=10, step=1,
    help="Apex DLL $1k/jour appliqué dans les 2 modes."
)

st.sidebar.markdown("---")
mode_funded = st.sidebar.toggle("Mode Funded PA — sans reset mensuel", value=False)
st.sidebar.header("Challenge Apex 50K EOD Trail" if not mode_funded else "Funded PA — Apex 50K")

APEX_50K = {
    "capital":          50_000,
    "profit_target":     3_000,
    "trailing_dd":       2_000,
    "daily_loss":        1_000,
    "max_contracts":        60,   # eval
    "max_contracts_pa":     40,   # PA
    "consistency_pa":     0.50,
}
capital_initial      = st.sidebar.number_input("Capital ($)", value=APEX_50K["capital"], step=1000)
max_drawdown_dollars = APEX_50K["trailing_dd"]
daily_loss_limit     = APEX_50K["daily_loss"]
max_contracts        = APEX_50K["max_contracts_pa"] if mode_funded else APEX_50K["max_contracts"]

fixed_contracts = st.sidebar.number_input(
    "Contrats fixes (0 = Half-Kelly auto)",
    value=0 if mode_funded else 60,
    min_value=0, max_value=max_contracts, step=1,
    help=f"0 = Half-Kelly automatique. Max Apex : {max_contracts} contrats."
)

if mode_funded:
    st.sidebar.info(
        f"Funded PA\n- DD max : ${max_drawdown_dollars:,} (EOD Trail)\n"
        f"- Daily loss : ${daily_loss_limit:,}/jour\n"
        f"- Max contracts : {max_contracts} MNQ"
    )
else:
    st.sidebar.info(
        f"Apex 50K EOD\n- DD max : ${max_drawdown_dollars:,} (EOD Trail)\n"
        f"- Daily loss : ${daily_loss_limit:,}/jour\n"
        f"- Max contracts : {max_contracts} MNQ (eval)"
    )

# Phase risk management (Half-Kelly dynamique)
PHASE_RISK = {"PRUDENTE": 0.04, "STANDARD": 0.10, "SECURITE": 0.04}
RISK_MIN_DOLLARS  = 200
RISK_MAX_DOLLARS  = 800
DAILY_LOSS_HARD   = APEX_50K["daily_loss"]
TICK_SIZE         = 0.25
# MNQ direct : 1 point MNQ = $2
DOLLAR_PER_PT     = 2.0

# ══════════════════════════════════════════════════════════════════════
# ENGINE — Kalman OU (basé sur kts.py Roman Paolucci Lec 95)
# ══════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=0)
def load_mnq_csv(csv_path, years):
    """
    Charge MNQ M1 depuis CSV Databento.
    Sélectionne le front-month par volume à chaque barre.
    years=1 : 12 derniers mois du dataset | years=2 : 24 derniers mois.
    Retourne (df, erreur_str).
    """
    try:
        df = pd.read_csv(csv_path, usecols=["ts_event", "open", "high", "low", "close", "volume", "symbol"])
    except Exception as e:
        return None, str(e)
    if df.empty:
        return None, "CSV vide."
    # Exclure les spreads (symboles contenant '-')
    df = df[~df["symbol"].str.contains("-", na=False)].copy()
    # Front-month : pour chaque barre, garder le symbole avec le plus grand volume
    df = df.sort_values("volume", ascending=False).groupby("ts_event", sort=False).first().reset_index()
    df["bar"] = pd.to_datetime(df["ts_event"], utc=True)
    df = df[["bar", "open", "high", "low", "close", "volume"]].copy()
    df[["open", "high", "low", "close"]] = df[["open", "high", "low", "close"]].astype(float)
    df["volume"] = df["volume"].fillna(0).astype(int)
    df.sort_values("bar", inplace=True)
    df.drop_duplicates(subset=["bar"], inplace=True)
    df.reset_index(drop=True, inplace=True)
    # Filtre période
    end_dt   = df["bar"].max()
    start_dt = end_dt - pd.DateOffset(years=years)
    df = df[df["bar"] >= start_dt].reset_index(drop=True)
    df["tr"] = np.maximum(
        df["high"] - df["low"],
        np.maximum(abs(df["high"] - df["close"].shift(1)),
                   abs(df["low"]  - df["close"].shift(1)))
    )
    df["returns"] = df["close"].pct_change().fillna(0)
    df["date"] = df["bar"].dt.date
    return df, None


def filter_session(df, start_h, start_m, end_h, end_m):
    t_min = df["bar"].dt.hour * 60 + df["bar"].dt.minute
    mask  = (t_min >= start_h * 60 + start_m) & (t_min < end_h * 60 + end_m)
    return df[mask].reset_index(drop=True)


# ── Kalman OU (exact de kts.py Roman Paolucci) ───────────────────────

def estimate_ar1(closes):
    """
    Calibre un AR(1) : X_t = c + φ·X_{t-1} + ε
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
        mu = c / (1.0 - phi)   # moyenne long-terme de l'AR(1)
        return phi, mu, sigma
    except Exception:
        return None


class KalmanOU:
    """
    Filtre de Kalman 1D pour processus OU — kts.py Roman Paolucci Lec 95.

    État x = fair value (moyenne estimée adaptative).
    Q = bruit processus (OU step variance).
    R = bruit observation = σ² × noise_scale.
      noise_scale faible → suit les prix (Kalman gain élevé)
      noise_scale élevé  → fait confiance au modèle OU (Kalman gain faible)
    """
    def __init__(self, phi, mu, sigma, noise_scale=1.0):
        self.phi = phi
        self.mu  = mu
        self.Q   = sigma ** 2 * max(1.0 - phi ** 2, 1e-6)
        self.R   = sigma ** 2 * max(noise_scale, 0.01)
        self.x   = mu
        self.P   = self.R

    def update(self, z):
        # Predict (OU step)
        self.x = self.phi * self.x + (1.0 - self.phi) * self.mu
        self.P = self.phi ** 2 * self.P + self.Q
        # Update (blend avec observation)
        K      = self.P / (self.P + self.R)
        self.x = self.x + K * (z - self.x)
        self.P = (1.0 - K) * self.P
        return self.x


def run_kalman(closes, lookback, noise_scale):
    """
    Calibration AR(1) rolling + filtre KalmanOU barre par barre.

    Pour chaque barre i ≥ lookback :
      1. estimate_ar1 sur closes[i-lookback:i]
      2. Mise à jour des params KalmanOU (non-stationarité — Lec 95)
      3. KalmanOU.update(closes[i]) → fair_value
      4. σ_stat = σ / √(1 - φ²)  (écart-type stationnaire du processus OU)

    Retourne : (fair_values, sigma_stats)
    """
    n           = len(closes)
    fair_values = np.full(n, np.nan)
    sigma_stats = np.full(n, np.nan)
    kal         = None

    for i in range(lookback, n):
        window = closes[i - lookback: i]
        params = estimate_ar1(window)
        if params is None:
            continue
        phi, mu, sigma = params
        ss = sigma / np.sqrt(max(1.0 - phi ** 2, 1e-6))

        if kal is None:
            kal = KalmanOU(phi, mu, sigma, noise_scale)
            for c in window:
                kal.update(c)
        else:
            # Mise à jour des params pour traquer la non-stationnarité (clé Lec 95)
            kal.phi = phi
            kal.mu  = mu
            kal.Q   = sigma ** 2 * max(1.0 - phi ** 2, 1e-6)
            kal.R   = sigma ** 2 * max(noise_scale, 0.01)

        kal.update(closes[i])
        fair_values[i] = kal.x
        sigma_stats[i] = ss

    return fair_values, sigma_stats


def find_signals(bars, fair_values, sigma_stats, band_k, band_k_max,
                 skip_open=0, skip_close=0, confirm_reversal=False, max_sigma_stat=0.0):
    """
    Génère les signaux d'entrée mean reversion.

    Confirmation reversal (Roman Lec 72) :
      N'entrer qu'à la barre i+1 si elle est déjà plus proche du FV → reversion confirmée.
    """
    n         = len(bars)
    signals   = []
    valid_end = n - skip_close

    for i in range(skip_open, valid_end):
        if np.isnan(fair_values[i]) or np.isnan(sigma_stats[i]):
            continue
        ss = sigma_stats[i]
        if ss <= 0:
            continue
        if max_sigma_stat > 0 and ss > max_sigma_stat:
            continue

        close     = bars.iloc[i]["close"]
        fv        = fair_values[i]
        deviation = abs(close - fv) / ss

        if deviation < band_k or deviation > band_k_max:
            continue

        direction = "short" if close > fv else "long"

        if confirm_reversal:
            if i + 1 >= n:
                continue
            if np.isnan(fair_values[i + 1]) or np.isnan(sigma_stats[i + 1]):
                continue
            ss1      = sigma_stats[i + 1]
            next_dev = abs(bars.iloc[i + 1]["close"] - fair_values[i + 1]) / ss1 if ss1 > 0 else deviation
            if next_dev >= deviation:
                continue
            entry_bar   = i + 1
            entry_price = bars.iloc[i + 1]["close"]
        else:
            entry_bar   = i
            entry_price = close

        signals.append({
            "bar_idx":   entry_bar,
            "date":      bars.iloc[i]["date"],
            "bar":       bars.iloc[entry_bar]["bar"],
            "price":     entry_price,
            "fair_value": fv,
            "sigma_stat": ss,
            "direction":  direction,
            "deviation":  deviation,
        })

    return signals


def simulate_trade(bars, entry_idx, entry_price, direction, sl_pts, tp_price, slip_pts):
    """Simule un trade, retourne (result_pts, exit_bar_idx)."""
    if direction == "long":
        real_entry = entry_price + slip_pts
        sl_price   = real_entry - sl_pts
    else:
        real_entry = entry_price - slip_pts
        sl_price   = real_entry + sl_pts

    for i in range(entry_idx + 1, min(entry_idx + 120, len(bars))):
        bar = bars.iloc[i]
        if direction == "long":
            if bar["low"]  <= sl_price: return -(sl_pts + slip_pts), i
            if bar["high"] >= tp_price: return (tp_price - slip_pts) - real_entry, i
        else:
            if bar["high"] >= sl_price: return -(sl_pts + slip_pts), i
            if bar["low"]  <= tp_price: return real_entry - (tp_price + slip_pts), i

    exit_idx = min(entry_idx + 119, len(bars) - 1)
    last = bars.iloc[exit_idx]["close"]
    if direction == "long":
        return (last - slip_pts) - real_entry, exit_idx
    else:
        return real_entry - (last + slip_pts), exit_idx


def kelly_fraction(results):
    wins   = results[results > 0]
    losses = results[results < 0]
    if len(wins) == 0 or len(losses) == 0:
        return 0.0, 0.0
    p = len(wins) / len(results)
    b = wins.mean() / abs(losses.mean())
    k = (p * b - (1 - p)) / b
    return max(0.0, k), max(0.0, k / 2)


# ══════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════

if st.sidebar.button("Lancer le Backtest", type="primary"):

    with st.spinner(f"Chargement MNQ M1 CSV ({csv_years} an{'s' if csv_years > 1 else ''})..."):
        full_df, _err = load_mnq_csv(CSV_PATH, csv_years)

    if _err:
        st.error(f"Erreur CSV : {_err}")
        st.stop()
    if full_df is None or full_df.empty:
        st.error("Aucune donnee. Verifie le chemin CSV.")
        st.stop()

    dates = sorted(full_df["date"].unique())
    st.info(
        f"{len(dates)} jours MNQ M1 ({dates[0]} → {dates[-1]}) | "
        f"${DOLLAR_PER_PT:.1f}/pt MNQ | "
        f"Pipeline: AR(1) rolling → KalmanOU → Bandes → Apex 50K EOD"
    )

    progress = st.progress(0)
    slip     = slippage_ticks * TICK_SIZE

    def get_month_key(d):
        return str(d)[:7]

    dates_sorted = sorted(dates)

    all_trades      = []
    all_daily_stats = []
    monthly_results = []

    skipped_no_signal = 0
    skipped_dd        = 0
    skipped_daily     = 0
    skipped_consec    = 0

    running_equity = capital_initial
    running_peak   = capital_initial
    consec_losses  = 0
    days_elapsed   = 0
    challenge_busted  = False
    challenge_passed  = False
    month_trades      = []
    current_month     = None
    month_equity_start = capital_initial
    funded_peak_global = capital_initial

    def _save_month(mk, re_, rp_, mt_, dbt_, cb_, cp_):
        mp = re_ - capital_initial
        md = rp_ - re_
        nw = sum(1 for t in mt_ if t["win"])
        nt = len(mt_)
        monthly_results.append({
            "mois": mk, "pnl": round(mp, 2), "trades": nt,
            "winrate": round(nw / nt * 100, 1) if nt > 0 else 0,
            "max_dd": round(md, 2), "jours": dbt_,
            "passe": cp_, "bust": cb_,
            "statut": "PASSE" if cp_ else ("BUST" if cb_ else "ECHOUE"),
        })

    def _save_month_funded(mk, pnl_month, mt_, dbt_):
        nw = sum(1 for t in mt_ if t["win"])
        nt = len(mt_)
        monthly_results.append({
            "mois": mk, "pnl": round(pnl_month, 2), "trades": nt,
            "winrate": round(nw / nt * 100, 1) if nt > 0 else 0,
            "jours": dbt_, "statut": "PA",
        })

    for file_idx, day_key in enumerate(dates_sorted):
        progress.progress((file_idx + 1) / len(dates_sorted),
                          text=f"Jour {file_idx + 1}/{len(dates_sorted)}")

        day_month = get_month_key(day_key)

        # ── Changement de mois ─────────────────────────────────────────
        if day_month != current_month:
            if current_month is not None:
                if mode_funded:
                    _save_month_funded(current_month,
                                       running_equity - month_equity_start,
                                       month_trades, days_elapsed)
                    month_equity_start = running_equity
                    days_elapsed       = 0
                    month_trades       = []
                else:
                    _save_month(current_month, running_equity, running_peak,
                                month_trades, days_elapsed, challenge_busted, challenge_passed)
                    running_equity   = capital_initial
                    running_peak     = capital_initial
                    consec_losses    = 0
                    days_elapsed     = 0
                    challenge_busted = False
                    challenge_passed = False
                    month_trades     = []
            current_month = day_month

        if not mode_funded and (challenge_passed or challenge_busted):
            continue
        if mode_funded and challenge_busted:
            break

        # Phase MM
        running_dd            = running_peak - running_equity
        trailing_dd_remaining = max(0.0, max_drawdown_dollars - running_dd)

        if mode_funded:
            dd_pct_used   = running_dd / max_drawdown_dollars
            challenge_pct = 1.0
        else:
            challenge_pnl = running_equity - capital_initial
            challenge_pct = challenge_pnl / APEX_50K["profit_target"]
            dd_pct_used   = running_dd / max_drawdown_dollars

        if challenge_pct >= 0.80 and not mode_funded:
            phase_risk = PHASE_RISK["SECURITE"]
        elif dd_pct_used > 0.50 or trailing_dd_remaining < 400:
            phase_risk = PHASE_RISK["PRUDENTE"]
        elif days_elapsed <= 5:
            phase_risk = PHASE_RISK["PRUDENTE"]
        else:
            phase_risk = PHASE_RISK["STANDARD"]

        # Stop DD Apex
        if running_dd >= max_drawdown_dollars:
            challenge_busted = True
            if mode_funded:
                break
            continue

        # Objectif mensuel atteint
        if not mode_funded:
            challenge_pnl = running_equity - capital_initial
            if challenge_pnl >= APEX_50K["profit_target"] and not challenge_passed:
                challenge_passed = True

        # Stop consec inter-journées
        if consec_losses >= 2:
            skipped_consec += 1
            consec_losses = 0
            all_daily_stats.append({
                "date": str(day_key), "action": "SKIP",
                "reason": "2 pertes consécutives — pause 1 jour",
            })
            continue

        days_elapsed += 1

        # ── Barres du jour ────────────────────────────────────────────
        day_df = full_df[full_df["date"] == day_key].copy()
        bars   = filter_session(day_df, session_start_h, session_start_m,
                                session_end_h, session_end_m)

        if len(bars) < kalman_lookback + 20:
            skipped_no_signal += 1
            continue

        # ── Kalman OU ─────────────────────────────────────────────────
        fair_values, sigma_stats = run_kalman(bars["close"].values, kalman_lookback, noise_scale)

        # ── Signaux ───────────────────────────────────────────────────
        signals = find_signals(
            bars, fair_values, sigma_stats,
            band_k, band_k_max,
            skip_open=skip_open_bars, skip_close=skip_close_bars,
            confirm_reversal=confirm_reversal,
            max_sigma_stat=float(max_sigma_stat),
        )

        if not signals:
            skipped_no_signal += 1
            all_daily_stats.append({
                "date": str(day_key), "action": "SKIP",
                "reason": "Pas de signal (prix dans les bandes)",
            })
            continue

        # ── Boucle trades ─────────────────────────────────────────────
        last_exit_bar  = -1
        daily_pnl      = 0.0
        day_consec     = 0
        day_trade_count = 0

        for sig in signals:
            bar_idx = sig["bar_idx"]

            if bar_idx <= last_exit_bar:
                continue
            if daily_pnl <= -DAILY_LOSS_HARD:
                break
            if day_consec >= 2:
                break
            if day_trade_count >= max_trades_per_day:
                break

            # SL sigma-based (cohérent avec le modèle OU — Lec 95)
            sl_pts = max(float(min_sl_pts), sl_sigma_mult * sig["sigma_stat"])

            # TP : retour au FV (ou fraction)
            tp_price = sig["price"] + tp_ratio * (sig["fair_value"] - sig["price"])

            # Sizing
            if fixed_contracts > 0:
                contracts = min(int(fixed_contracts), max_contracts)
            else:
                risk_dollars = np.clip(trailing_dd_remaining * phase_risk,
                                       RISK_MIN_DOLLARS, RISK_MAX_DOLLARS)
                risk_dollars = min(risk_dollars, DAILY_LOSS_HARD)
                contracts    = max(1, int(risk_dollars / (sl_pts * DOLLAR_PER_PT)))
                contracts    = min(contracts, max_contracts)

            loss_if_sl = sl_pts * DOLLAR_PER_PT * contracts
            if loss_if_sl > DAILY_LOSS_HARD:
                contracts  = max(1, int(DAILY_LOSS_HARD / (sl_pts * DOLLAR_PER_PT)))
                loss_if_sl = sl_pts * DOLLAR_PER_PT * contracts
            if loss_if_sl > trailing_dd_remaining:
                skipped_dd += 1
                continue

            result_pts, exit_bar = simulate_trade(
                bars, bar_idx, sig["price"], sig["direction"], sl_pts, tp_price, slip
            )
            last_exit_bar = exit_bar

            pnl_dollars    = result_pts * DOLLAR_PER_PT * contracts
            running_equity += pnl_dollars
            daily_pnl      += pnl_dollars

            if running_equity > running_peak:
                running_peak = running_equity

            if pnl_dollars < 0:
                consec_losses += 1
                day_consec    += 1
            else:
                consec_losses = 0
                day_consec    = 0

            tp_pts    = abs(sig["fair_value"] - sig["price"])
            rr_target = tp_pts / sl_pts if sl_pts > 0 else 0.0

            trade = {
                "date":       sig["date"],
                "time":       sig["bar"],
                "price":      round(sig["price"], 2),
                "fair_value": round(sig["fair_value"], 2),
                "sigma_stat": round(sig["sigma_stat"], 2),
                "deviation":  round(sig["deviation"], 2),
                "direction":  sig["direction"],
                "sl_pts":     round(sl_pts, 2),
                "tp_pts":     round(tp_pts, 2),
                "rr_target":  round(rr_target, 1),
                "result_pts": round(result_pts, 2),
                "contracts":  contracts,
                "pnl_dollars": round(pnl_dollars, 2),
                "win":        result_pts > 0,
                "equity":     round(running_equity, 2),
                "dd_from_peak": round(running_peak - running_equity, 2),
            }
            all_trades.append(trade)
            month_trades.append(trade)
            day_trade_count += 1

            all_daily_stats.append({
                "date":   str(sig["date"]),
                "action": "TRADE",
                "reason": f"{sig['direction']} @ {sig['price']:.2f}, "
                          f"FV={sig['fair_value']:.2f}, dev={sig['deviation']:.1f}σ",
            })

            if not mode_funded and running_equity - capital_initial >= APEX_50K["profit_target"]:
                challenge_passed = True
                break
            if mode_funded:
                if running_peak - running_equity >= max_drawdown_dollars:
                    challenge_busted = True
                    break

    # Dernier mois
    if current_month is not None:
        if mode_funded:
            _save_month_funded(current_month,
                               running_equity - month_equity_start,
                               month_trades, days_elapsed)
        else:
            _save_month(current_month, running_equity, running_peak,
                        month_trades, days_elapsed, challenge_busted, challenge_passed)

    progress.empty()

    # ══════════════════════════════════════════════════════════════════
    # RÉSULTATS
    # ══════════════════════════════════════════════════════════════════

    if not all_trades:
        st.warning("Aucun trade. Baisse band_k ou le lookback.")
        st.stop()

    trades_df  = pd.DataFrame(all_trades)
    daily_df   = pd.DataFrame(all_daily_stats)
    monthly_df = pd.DataFrame(monthly_results)

    tab1_label = "💰 Funded PA" if mode_funded else "📅 Bilan Mensuel"
    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        [tab1_label, "📈 Résultats", "🔧 Pipeline", "📉 Charts", "🎲 Monte Carlo"]
    )

    results    = trades_df["result_pts"].values
    final_pnl  = trades_df["pnl_dollars"].sum()
    n_total    = len(trades_df)
    n_wins     = int(trades_df["win"].sum())
    winrate    = n_wins / n_total if n_total > 0 else 0
    wins_r     = results[results > 0]
    losses_r   = results[results < 0]
    avg_win    = wins_r.mean() if len(wins_r) > 0 else 0
    avg_loss   = abs(losses_r.mean()) if len(losses_r) > 0 else 1
    expectancy = (winrate * avg_win) - ((1 - winrate) * avg_loss)
    profit_factor = wins_r.sum() / max(abs(losses_r.sum()), 0.01) if len(losses_r) > 0 else 99.0
    rr_mean    = avg_win / avg_loss if avg_loss > 0 else 0
    max_dd     = trades_df["dd_from_peak"].max() / capital_initial * 100
    total_return = final_pnl / capital_initial * 100

    kelly_full, kelly_half = kelly_fraction(results)
    kc = max(1, int(kelly_half * capital_initial / (avg_loss * DOLLAR_PER_PT))) if avg_loss > 0 else 1

    # Business days for Sharpe
    all_dates_pd = pd.to_datetime(trades_df["date"].unique())
    all_bdays = pd.bdate_range(start=all_dates_pd.min(), end=all_dates_pd.max())
    n_bdays = max(len(all_bdays), 1)

    daily_pnl_series = trades_df.groupby("date")["pnl_dollars"].sum()
    daily_pnl_series.index = pd.to_datetime(daily_pnl_series.index)
    daily_returns = daily_pnl_series.reindex(all_bdays, fill_value=0) / capital_initial
    sharpe_real = (daily_returns.mean() / daily_returns.std() * np.sqrt(252)
                   if daily_returns.std() > 0 else 0)
    sharpe_stress = sharpe_real / 3.0

    neg_ret = daily_returns[daily_returns < 0]
    sortino = (daily_returns.mean() / neg_ret.std() * np.sqrt(252)
               if len(neg_ret) > 1 and neg_ret.std() > 0 else 0)
    calmar = (total_return / max_dd) if max_dd > 0 else 0

    equity     = np.concatenate([[capital_initial], np.cumsum(trades_df["pnl_dollars"].values) + capital_initial])
    peak_arr   = np.maximum.accumulate(equity)
    drawdown   = (peak_arr - equity) / capital_initial * -100

    max_dd_actual = trades_df["dd_from_peak"].max()
    dd_pct        = max_dd_actual / max_drawdown_dollars * 100

    # ── TAB 1 : Bilan mensuel / Funded ────────────────────────────────
    with tab1:
        if mode_funded:
            st.markdown("<p class='section-title'>Funded PA — Simulation continue</p>", unsafe_allow_html=True)
            n_months   = len(monthly_df)
            avg_pnl_m  = monthly_df["pnl"].mean() if n_months > 0 else 0
            pos_months = (monthly_df["pnl"] > 0).sum()
            f1, f2, f3, f4 = st.columns(4)
            f1.metric("Mois simulés", n_months)
            f2.metric("Mois profitables", f"{pos_months}/{n_months}")
            f3.metric("P&L moyen/mois", f"${avg_pnl_m:+,.0f}")
            f4.metric("P&L total", f"${final_pnl:+,.0f}")
            st.dataframe(monthly_df, use_container_width=True, hide_index=True)
        else:
            st.markdown("<p class='section-title'>Challenge Apex 50K EOD — Fenêtre 1 mois (reset mensuel)</p>",
                        unsafe_allow_html=True)
            n_months = len(monthly_df)
            n_pass   = (monthly_df["statut"] == "PASSE").sum()
            n_bust   = (monthly_df["statut"] == "BUST").sum()
            n_fail   = n_months - n_pass - n_bust

            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Mois simulés", n_months)
            c2.metric("PASSES", n_pass)
            c3.metric("ECHOUES", n_fail)
            c4.metric("BUST", n_bust)

            avg_days_pass = monthly_df[monthly_df["statut"] == "PASSE"]["jours"].mean()
            c5.metric("Jours moy pour passer", f"{avg_days_pass:.1f}" if n_pass > 0 else "—")

            pass_rate = n_pass / n_months * 100 if n_months > 0 else 0
            if pass_rate >= 50:
                st.success(f"↑ {pass_rate:.0f}% taux de réussite")
            elif pass_rate >= 25:
                st.warning(f"↑ {pass_rate:.0f}% taux de réussite — edge marginal")
            else:
                st.error(f"Taux de réussite {pass_rate:.0f}% — revoir le sizing ou les conditions d'entrée")

            def color_statut(val):
                if val == "PASSE": return "color: #00ff88"
                if val == "BUST":  return "color: #ff3366"
                return "color: #ffd600"

            disp = monthly_df.rename(columns={
                "mois": "Mois", "pnl": "P&L ($)", "trades": "Trades",
                "winrate": "WR %", "max_dd": "DD max ($)", "jours": "Jours trades", "statut": "Statut"
            })[["Mois", "P&L ($)", "Trades", "WR %", "DD max ($)", "Jours trades", "Statut"]]
            st.dataframe(
                disp.style.applymap(color_statut, subset=["Statut"]),
                use_container_width=True, hide_index=True
            )

            lm = monthly_df.iloc[-1]
            lm1, lm2, lm3, lm4, lm5 = st.columns(5)
            lm1.metric("P&L dernier mois", f"${lm['pnl']:+,.0f}",
                       delta=f"↑ {lm['pnl']/APEX_50K['profit_target']:.0%} objectif")
            lm2.metric("DD max", f"${max_dd_actual:,.0f}",
                       delta=f"↑ {dd_pct:.0f}% du max ${max_drawdown_dollars:,}",
                       delta_color="inverse")
            lm3.metric("DD autorisé", f"${max_drawdown_dollars:,}", delta="EOD Trail")
            lm4.metric("Jours trades (dernier mois)", int(lm["jours"]))
            daily_stop = int(DAILY_LOSS_HARD * 0.80)
            lm5.metric("Daily stop interne", f"${daily_stop:,}")

    # ── TAB 2 : Résultats ─────────────────────────────────────────────
    with tab2:
        st.markdown("<p class='section-title'>Performance globale</p>", unsafe_allow_html=True)
        r1c1, r1c2, r1c3, r1c4, r1c5 = st.columns(5)
        r1c1.metric("Trades", n_total)
        r1c2.metric("Winrate", f"{winrate:.1%}")
        r1c3.metric("Espérance", f"{expectancy:.1f} pts")
        r1c4.metric("Gain moyen", f"{avg_win:.1f} pts")
        r1c5.metric("Max Drawdown", f"{max_dd:.1f}%")

        r2c1, r2c2, r2c3, r2c4, r2c5 = st.columns(5)
        r2c1.metric("W / L", f"{n_wins} / {n_total - n_wins}")
        r2c2.metric("Profit Factor", f"{profit_factor:.2f}")
        r2c3.metric("R:R moyen", f"{rr_mean:.1f}")
        r2c4.metric("Perte moy.", f"{avg_loss:.1f} pts")
        r2c5.metric("P&L total", f"${final_pnl:+,.0f}")

        st.markdown("<p class='section-title'>Métriques de risque ajustées</p>", unsafe_allow_html=True)
        s1, s2, s3, s4, s5 = st.columns(5)
        s1.metric("Sharpe brut", f"{sharpe_real * 3:.2f}", delta="biaisé — ignorer", delta_color="off")
        s2.metric("Sharpe réel", f"{sharpe_real:.2f}",
                  delta=f"R-normalisé · {n_total/n_bdays:.1f} trades/jour")
        s3.metric("Sharpe stress (live)", f"{sharpe_stress:.2f}",
                  delta="+3× slippage · estimation live")
        s4.metric("Sortino réel", f"{sortino:.2f}", delta="vol. négative seule")
        n_pos = (daily_returns > 0).sum()
        n_neg = (daily_returns < 0).sum()
        n_zero = (daily_returns == 0).sum()
        s5.metric("Jours +/0/−", f"{n_pos}/{n_zero}/{n_neg}",
                  delta=f"{n_bdays} j. business | Calmar {calmar:.1f}")

        # Verdict Sharpe
        if 1.2 <= sharpe_real <= 1.8:
            st.success(f"Edge confirmé — Sharpe réel {sharpe_real:.2f} (cible 1.2-1.5) | "
                       f"Stress live {sharpe_stress:.2f} | {n_total/n_bdays:.1f} trades/jour corrigé")
        elif sharpe_real > 1.8:
            st.warning(f"Sharpe réel {sharpe_real:.2f} hors cible — trop élevé → probable overfitting. "
                       f"Cible : 1.2-1.5")
        else:
            st.error(f"Sharpe réel {sharpe_real:.2f} hors cible — trop faible → edge insuffisant. "
                     f"Cible : 1.2-1.5")

        # Kelly
        st.markdown("<p class='section-title'>Kelly Criterion</p>", unsafe_allow_html=True)
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Kelly optimal", f"{kelly_full:.1%}")
        k2.metric("Demi-Kelly", f"{kelly_half:.1%}")
        k3.metric("Contrats (½ Kelly)", kc)

        f_range = np.linspace(0, min(0.6, kelly_full * 2 + 0.1), 200)
        kelly_growth = [
            (winrate * np.log(1 + f * rr_mean) + (1 - winrate) * np.log(1 - f))
            if (1 - f) > 0 and (1 + f * rr_mean) > 0 else -np.inf
            for f in f_range
        ]
        fig_k = go.Figure()
        fig_k.add_trace(go.Scatter(x=f_range, y=kelly_growth, mode="lines",
                                   line=dict(color=CYAN, width=2), name="Kelly growth"))
        if kelly_full > 0:
            fig_k.add_vline(x=kelly_full, line_color=YELLOW, line_dash="dash",
                            annotation_text=f"K={kelly_full:.1%}")
            fig_k.add_vline(x=kelly_half, line_color=GREEN, line_dash="dot",
                            annotation_text=f"½K={kelly_half:.1%}")
        fig_k.update_layout(title="Kelly Curve", xaxis_title="f", yaxis_title="E[log growth]",
                            height=300, **DARK)
        k4.plotly_chart(fig_k, use_container_width=True)

    # ── TAB 3 : Pipeline ──────────────────────────────────────────────
    with tab3:
        st.markdown("<p class='section-title'>Filtres pipeline</p>", unsafe_allow_html=True)
        p1, p2, p3 = st.columns(3)
        p1.metric("Jours analysés", len(dates_sorted))
        p2.metric("Skip pas de signal", skipped_no_signal)
        p3.metric("Skip 2 pertes consec", skipped_consec)
        st.info(f"**{n_total} trades** sur {len(dates_sorted)} jours | "
                f"MNQ M1 {csv_years}an{'s' if csv_years > 1 else ''} | Apex 50K EOD | "
                f"Daily ${DAILY_LOSS_HARD:,} | DD ${max_drawdown_dollars:,} | "
                f"band_k={band_k}σ | noise={noise_scale} | SL={sl_sigma_mult}σ | TP={tp_ratio:.0%} | "
                f"${DOLLAR_PER_PT:.1f}/pt MNQ/contrat")

    # ── TAB 4 : Charts ────────────────────────────────────────────────
    with tab4:
        st.markdown("<p class='section-title'>Equity curve</p>", unsafe_allow_html=True)
        fig_eq = make_subplots(rows=2, cols=1, shared_xaxes=True,
                               row_heights=[0.7, 0.3],
                               subplot_titles=["Equity ($)", "Drawdown (%)"])
        fig_eq.add_trace(go.Scatter(
            x=trades_df["date"].astype(str).tolist(),
            y=equity[1:], mode="lines+markers",
            line=dict(color=CYAN, width=2),
            marker=dict(size=5, color=[GREEN if w else RED for w in trades_df["win"]]),
            text=[f"{'W' if w else 'L'} {r:+.1f}pts | FV={fv:.0f}"
                  for w, r, fv in zip(trades_df["win"], results, trades_df["fair_value"])],
            hovertemplate="%{x}<br>%{text}<br>$%{y:,.0f}<extra></extra>"
        ), row=1, col=1)
        fig_eq.add_trace(go.Scatter(
            x=trades_df["date"].astype(str).tolist(), y=drawdown[1:], mode="lines",
            line=dict(color=RED, width=1.5), fill="tozeroy", fillcolor="rgba(255,51,102,0.12)"
        ), row=2, col=1)
        fig_eq.update_layout(height=500, showlegend=False, **DARK)
        fig_eq.update_yaxes(title_text="$", row=1, col=1)
        fig_eq.update_yaxes(title_text="%", row=2, col=1)
        st.plotly_chart(fig_eq, use_container_width=True)

        # Distribution P&L par trade
        st.markdown("<p class='section-title'>Distribution P&L</p>", unsafe_allow_html=True)
        colors = [GREEN if r > 0 else RED for r in results]
        fig_d = go.Figure()
        fig_d.add_trace(go.Bar(
            x=trades_df["date"].astype(str).tolist(), y=results,
            marker_color=colors, text=[f"{r:+.1f}" for r in results],
            textposition="outside", textfont=dict(size=9)
        ))
        fig_d.add_hline(y=0, line_dash="dash", line_color="white", opacity=0.3)
        fig_d.add_hline(y=expectancy, line_dash="dot", line_color=CYAN,
                        annotation_text=f"Espérance = {expectancy:.1f} pts")
        fig_d.update_layout(height=350, xaxis_title="Date", yaxis_title="Points", **DARK)
        st.plotly_chart(fig_d, use_container_width=True)

        # Stats par déviation
        st.markdown("---")
        st.subheader("Performance par déviation (σ)")
        bins = [(1.0, 1.5), (1.5, 2.0), (2.0, 3.0), (3.0, 10.0)]
        dev_stats = []
        for lo, hi in bins:
            sub = trades_df[(trades_df["deviation"] >= lo) & (trades_df["deviation"] < hi)]
            if len(sub) == 0:
                continue
            r  = sub["result_pts"].values
            w  = r[r > 0]
            l_ = r[r < 0]
            wr = len(w) / len(r)
            exp_ = (wr * w.mean() if len(w) else 0) - ((1 - wr) * abs(l_.mean()) if len(l_) else 0)
            dev_stats.append({
                "Déviation": f"{lo}-{hi}σ", "Trades": len(r),
                "Winrate": f"{wr:.1%}", "Espérance": f"{exp_:.1f} pts",
                "Total": f"{r.sum():.1f} pts",
            })
        if dev_stats:
            st.dataframe(pd.DataFrame(dev_stats), use_container_width=True, hide_index=True)

        # Journal
        st.markdown("---")
        st.subheader("Journal des trades")
        display = trades_df.copy()
        display["win"] = display["win"].map({True: "TP", False: "SL"})
        st.dataframe(display, use_container_width=True, hide_index=True)
        st.download_button("Télécharger CSV", display.to_csv(index=False),
                           "backtest_kalman.csv", "text/csv")

        # Log journalier
        st.markdown("---")
        st.subheader("Log journalier")
        st.dataframe(daily_df, use_container_width=True, hide_index=True)

        # Verdict
        st.markdown("---")
        if expectancy > 0 and profit_factor > 1.5:
            st.success(
                f"**EDGE CONFIRME** — {winrate:.1%} WR, {expectancy:.1f} pts MNQ/trade, "
                f"PF {profit_factor:.2f}, ½Kelly {kelly_half:.1%}\n\n"
                f"Signal: MNQ Kalman OU (k={band_k}σ) | "
                f"TP {tp_ratio:.0%} vers FV | SL = {sl_sigma_mult}×σ-kalman | "
                f"${DOLLAR_PER_PT:.1f}/pt MNQ/contrat\n\n"
                f"Return: **{total_return:+.1f}%** | Max DD: **{max_dd:.1f}%**"
            )
        elif expectancy > 0:
            st.warning(
                f"**Edge marginal** — {winrate:.1%} WR, {expectancy:.1f} pts/trade, "
                f"PF {profit_factor:.2f}\n\nEssaie : baisser band_k ou ajuster noise_scale."
            )
        else:
            st.error(
                f"**Pas d'edge** — {winrate:.1%} WR, {expectancy:.1f} pts/trade, "
                f"PF {profit_factor:.2f}\n\nAjuste : band_k, noise_scale, ou SL ratio."
            )

    # ── TAB 5 : Monte Carlo ───────────────────────────────────────────
    with tab5:
        st.markdown("<p class='section-title'>Monte Carlo — Probabilité de réussir le challenge Apex 50K EOD</p>",
                    unsafe_allow_html=True)
        st.caption(
            "Bootstrap sur la distribution empirique des trades. "
            "Donne la vraie probabilité de passer, bust, ou échouer avant de risquer de l'argent."
        )

        mc1, mc2, mc3 = st.columns(3)
        n_sims    = mc1.number_input("Simulations", value=10_000, min_value=1000, step=1000)
        trades_pm = mc2.number_input(
            "Trades/mois estimés",
            value=max(1, int(n_total / max(1, n_bdays / 22))),
            min_value=1, step=1
        )
        mc_contracts = mc3.number_input(
            "Contrats (MC)",
            value=min(int(fixed_contracts) if fixed_contracts > 0 else max(1, kc), max_contracts),
            min_value=1, max_value=max_contracts, step=1
        )

        if st.button("Lancer Monte Carlo", type="primary"):
            rng                = np.random.default_rng(42)
            trade_results_pts  = trades_df["result_pts"].values
            n_pass = n_bust = n_fail = 0
            final_pnls = []
            peak_dds   = []
            sim_paths  = []

            for sim in range(int(n_sims)):
                equity_mc  = capital_initial
                peak_mc    = capital_initial
                day_pnl_arr = np.zeros(22)
                busted = passed = False
                max_dd_sim = 0.0

                sampled      = rng.choice(trade_results_pts, size=int(trades_pm), replace=True)
                sampled_days = rng.integers(0, 22, size=int(trades_pm))

                for r_pts, day in zip(sampled, sampled_days):
                    pnl = r_pts * DOLLAR_PER_PT * mc_contracts
                    if day_pnl_arr[day] <= -daily_loss_limit:
                        continue
                    day_pnl_arr[day] += pnl
                    equity_mc += pnl
                    if equity_mc > peak_mc:
                        peak_mc = equity_mc
                    dd = peak_mc - equity_mc
                    if dd > max_dd_sim:
                        max_dd_sim = dd
                    if dd >= max_drawdown_dollars:
                        busted = True
                        break
                    if equity_mc - capital_initial >= APEX_50K["profit_target"]:
                        passed = True
                        break

                # Règle consistance 50%
                if passed and not busted:
                    total_profit = equity_mc - capital_initial
                    best_day     = day_pnl_arr.max()
                    if total_profit > 0 and best_day / total_profit > 0.50:
                        passed = False

                if busted:   n_bust += 1
                elif passed: n_pass += 1
                else:        n_fail += 1

                final_pnls.append(equity_mc - capital_initial)
                peak_dds.append(max_dd_sim)
                if sim < 200:
                    cum = np.concatenate([[0], np.cumsum(
                        [r * DOLLAR_PER_PT * mc_contracts for r in sampled]
                    )])
                    sim_paths.append(cum[:int(trades_pm) + 1])

            pass_rate = n_pass / int(n_sims) * 100
            bust_rate = n_bust / int(n_sims) * 100
            fail_rate = n_fail / int(n_sims) * 100

            mc_a, mc_b, mc_c, mc_d, mc_e = st.columns(5)
            color_pass = "normal" if pass_rate >= 50 else ("off" if pass_rate >= 30 else "inverse")
            mc_a.metric("Taux de réussite", f"{pass_rate:.1f}%",
                        delta="✓ cible atteinte" if pass_rate >= 50 else "✗ insuffisant",
                        delta_color=color_pass)
            mc_b.metric("Taux de bust",   f"{bust_rate:.1f}%", delta_color="inverse")
            mc_c.metric("Taux d'échec",   f"{fail_rate:.1f}%", delta_color="inverse")
            mc_d.metric("P&L médian / mois", f"${np.median(final_pnls):+,.0f}")
            mc_e.metric("DD max médian",      f"${np.median(peak_dds):,.0f}")

            if pass_rate >= 70:
                st.success(f"**EDGE TRADABLE** — {pass_rate:.1f}% de chance de passer. Objectif 50-80% atteint.")
            elif pass_rate >= 50:
                st.warning(f"**EDGE MARGINAL** — {pass_rate:.1f}% de chance. Augmente les contrats ou baisse band_k.")
            else:
                st.error(f"**EDGE INSUFFISANT** — {pass_rate:.1f}% de chance. "
                         f"Augmente la fréquence (baisse band_k) ou les contrats.")

            # Graphe 200 chemins
            st.markdown("<p class='section-title'>200 chemins simulés</p>", unsafe_allow_html=True)
            fig_mc = go.Figure()
            for path in sim_paths:
                fig_mc.add_trace(go.Scatter(
                    y=path, mode="lines",
                    line=dict(width=0.5, color="rgba(60,196,183,0.12)"),
                    showlegend=False, hoverinfo="skip"
                ))
            fig_mc.add_hline(y=APEX_50K["profit_target"], line_color=GREEN,
                             line_dash="dash", annotation_text="Objectif $3 000")
            fig_mc.add_hline(y=-max_drawdown_dollars, line_color=RED,
                             line_dash="dash", annotation_text="Bust $-2 000")
            fig_mc.add_hline(y=0, line_color="rgba(255,255,255,0.2)")
            fig_mc.update_layout(height=400, yaxis_title="P&L ($)", xaxis_title="Trade #", **DARK)
            st.plotly_chart(fig_mc, use_container_width=True)

            # Distribution P&L finaux
            st.markdown("<p class='section-title'>Distribution P&L fin de mois</p>", unsafe_allow_html=True)
            fig_dist = go.Figure()
            fig_dist.add_trace(go.Histogram(x=final_pnls, nbinsx=60,
                                            marker_color=TEAL, opacity=0.8))
            fig_dist.add_vline(x=APEX_50K["profit_target"], line_color=GREEN,
                               line_dash="dash", annotation_text="Target $3k")
            fig_dist.add_vline(x=0, line_color="white", opacity=0.3)
            fig_dist.add_vline(x=-max_drawdown_dollars, line_color=RED,
                               line_dash="dash", annotation_text="Bust")
            fig_dist.update_layout(height=300, xaxis_title="P&L ($)", **DARK)
            st.plotly_chart(fig_dist, use_container_width=True)

            st.markdown(f"""
<div class='result-block'>
<div class='result-row'><span class='result-key'>Simulations</span><span class='result-val'>{int(n_sims):,}</span></div>
<div class='result-row'><span class='result-key'>Trades/mois</span><span class='result-val'>{int(trades_pm)}</span></div>
<div class='result-row'><span class='result-key'>Contrats</span><span class='result-val'>{mc_contracts} MNQ</span></div>
<div class='result-row'><span class='result-key'>WR empirique</span><span class='result-val'>{winrate:.1%}</span></div>
<div class='result-row'><span class='result-key'>Espérance/trade</span><span class='result-val'>{expectancy:.1f} pts</span></div>
<div class='result-row'><span class='result-key'>E[P&L]/mois</span>
  <span class='result-val {"green" if expectancy * int(trades_pm) * DOLLAR_PER_PT * mc_contracts > 0 else "red"}'>
    ${expectancy * int(trades_pm) * DOLLAR_PER_PT * mc_contracts:+,.0f}
  </span></div>
</div>
""", unsafe_allow_html=True)
