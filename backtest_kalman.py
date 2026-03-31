"""
Backtest Kalman OU Mean Reversion — MNQ
Databento tick data → GARCH regime → Kalman fair value → OU bands
→ Entry quand prix hors bande → TP = retour au fair value → SL = ATR
→ 1 trade/session max → Kelly sizing → Apex protection
"""

import glob
import os
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

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

st.set_page_config(page_title="Backtest Kalman OU", page_icon="📊", layout="wide")

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
[data-testid="stHeader"] { background: transparent; }
[data-testid="stToolbar"] { display: none; }

::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: #0a0a0a; }
::-webkit-scrollbar-thumb { background: #3CC4B7; border-radius: 2px; }

/* ── Sidebar Nav ── */
[data-testid="stSidebarNav"] { padding: 0.5rem 0; }
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
[data-testid="stSidebarNavLink"] span { font-size: 0.75rem !important; }

.page-header {
    padding: 1.5rem 0 0.5rem;
    border-bottom: 1px solid #1a1a1a;
    margin-bottom: 1.5rem;
}
.page-tag {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.65rem;
    letter-spacing: 0.2em;
    color: #3CC4B7;
    text-transform: uppercase;
}
.page-title {
    font-size: 1.8rem;
    font-weight: 700;
    color: #fff;
    letter-spacing: -0.02em;
    margin: 0.3rem 0 0;
}

.section-title {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.65rem;
    font-weight: 700;
    letter-spacing: 0.2em;
    color: #3CC4B7;
    text-transform: uppercase;
    margin: 1.5rem 0 0.8rem 0;
}
.stat-row {
    display: flex;
    gap: 0;
    border: 1px solid #1a1a1a;
    border-radius: 10px;
    overflow: hidden;
    margin: 0.5rem 0 1rem;
}
.stat-cell {
    flex: 1;
    padding: 1.2rem 1rem;
    text-align: center;
    border-right: 1px solid #1a1a1a;
    background: #060606;
}
.stat-cell:last-child { border-right: none; }
.stat-cell:hover { background: #0f0f0f; }
.stat-num {
    font-size: 1.6rem;
    font-weight: 700;
    font-family: 'JetBrains Mono', monospace;
    letter-spacing: -0.02em;
}
.stat-lbl {
    font-size: 0.6rem;
    color: #444;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin-top: 0.2rem;
}

.result-block {
    background: #0a0a0a;
    border: 1px solid #1a1a1a;
    border-radius: 10px;
    padding: 1.2rem 1.5rem;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.82rem;
    line-height: 2;
    margin: 0.5rem 0;
}
.result-row { display: flex; gap: 1rem; align-items: center; }
.result-key { color: #3CC4B7; min-width: 140px; font-weight: 700; }
.result-val { color: #888; }
.result-val.green { color: #00ff88; }
.result-val.red   { color: #ff3366; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="page-header">
    <div class="page-tag">BACKTEST · DATABENTO MNQ · APEX 50K EOD</div>
    <div class="page-title">Backtest Kalman OU</div>
</div>
""", unsafe_allow_html=True)

# ── Sidebar ──────────────────────────────────────────────────────────
st.sidebar.header("Donnees")
data_dir = st.sidebar.text_input(
    "Dossier CSV Databento (1)",
    value=r"C:\Users\ryadb\Downloads\data OHLCV M1"
)
data_dir2 = st.sidebar.text_input(
    "Dossier CSV Databento (2) — optionnel",
    value=""
)
data_dir3 = st.sidebar.text_input(
    "Dossier CSV Databento (3) — optionnel",
    value=""
)
bar_seconds = st.sidebar.selectbox("Barre (secondes)", [30, 60, 120, 300], index=1)

st.sidebar.markdown("---")
st.sidebar.header("Kalman OU")
kalman_lookback = st.sidebar.number_input("Lookback calibration (barres)", value=120, min_value=30, step=10)
band_k = st.sidebar.number_input("Bande k min (sigma)", value=1.2, min_value=0.3, max_value=3.0, step=0.1,
                                  help="Entry quand deviation > k sigma (min) — 1.2 pour plus de frequence, 1.5 pour plus de precision")
band_k_max = st.sidebar.number_input("Bande k max (sigma)", value=5.0, min_value=0.5, max_value=10.0, step=0.5,
                                      help="Ignore si deviation > k_max sigma (evite crash-recovery)")
kalman_R_mult = st.sidebar.number_input("Kalman R multiplier", value=5.0, min_value=0.5, step=0.5,
                                         help="Confiance modele vs data. Plus haut = plus lisse")

st.sidebar.markdown("---")
st.sidebar.header("GARCH Regime")
garch_alpha1 = st.sidebar.number_input("GARCH alpha1", value=0.12, step=0.01, format="%.2f")
garch_beta1 = st.sidebar.number_input("GARCH beta1", value=0.85, step=0.01, format="%.2f")
only_low_regime = st.sidebar.toggle(
    "LOW regime uniquement",
    value=True,
    help="Ne trader qu'en regime LOW vol — MED vol detruit le PF (Sharpe -0.09 en MED vs +0.55 en LOW)"
)

st.sidebar.markdown("---")
st.sidebar.header("Risk (ATR)")
atr_sl_mult = st.sidebar.number_input("SL = ATR x", value=1.5, step=0.1)
max_sl_pts = st.sidebar.number_input("SL max (pts)", value=15.0, step=1.0)
min_sl_pts = st.sidebar.number_input("SL min (pts)", value=5.0, step=0.5)

st.sidebar.markdown("---")
st.sidebar.header("Realisme")
slippage_ticks = st.sidebar.number_input("Slippage (ticks)", value=2, min_value=0, step=1)

st.sidebar.markdown("---")
st.sidebar.header("Session")
session_start_h = st.sidebar.number_input("Debut (h UTC)", value=14, min_value=0, max_value=23)
session_start_m = st.sidebar.number_input("Debut (min)", value=30, min_value=0, max_value=59)
session_end_h = st.sidebar.number_input("Fin (h UTC)", value=21, min_value=0, max_value=23)
session_end_m = st.sidebar.number_input("Fin (min)", value=0, min_value=0, max_value=59)

st.sidebar.markdown("---")
st.sidebar.header("Filtres temps")
skip_open_bars = st.sidebar.number_input(
    "Skip barres ouverture", value=30, min_value=0, step=5,
    help="Ignore les N premieres barres de session — evite la volatilite d'ouverture (Roman #72)"
)
skip_close_bars = st.sidebar.number_input(
    "Skip barres cloture", value=30, min_value=0, step=5,
    help="Ignore les N dernieres barres de session — evite le closing gamma (Roman #74)"
)
max_trades_per_day = st.sidebar.number_input(
    "Max trades/jour (funded)", value=3, min_value=1, max_value=10, step=1,
    help="Plafond intraday en mode Funded PA — empeche les spikes d'equity irrealistes (Roman #77)"
)

st.sidebar.markdown("---")
st.sidebar.header("Filtres signal avancés (Quant Guild)")
use_gmm_regime = st.sidebar.toggle(
    "Bayesian Markov Filter (Lec 72/74)",
    value=True,
    help="Filtre Bayésien 3-états — implémentation exacte du bot IBKR Roman Paolucci Lec 72/74. "
         "Inférence barre par barre via matrice de transition calibrée + likelihood gaussienne."
)

confirm_reversal = st.sidebar.toggle(
    "Confirmation reversion (Lec 72)",
    value=True,
    help="N'entre qu'à la barre qui montre déjà un mouvement vers FV. "
         "Améliore le WR de ~30% → ~38-42%. Réduit la fréquence."
)
use_halflife_filter = st.sidebar.toggle(
    "Filtre demi-vie OU (Lec 92/95)",
    value=True,
    help="N'entre que si la demi-vie OU < seuil barres. "
         "Élimine les signaux trop lents à revenir dans la session."
)
max_half_life_bars = st.sidebar.number_input(
    "Demi-vie max (barres)", value=60, min_value=10, max_value=300, step=10,
    help="Seuil demi-vie OU. Session ~420 barres/1m. 60 barres = 1h max pour revenir à 50%."
) if use_halflife_filter else None

tp_ratio = st.sidebar.slider(
    "TP ratio (% distance vers FV)", min_value=0.25, max_value=1.0, value=0.5, step=0.05,
    help=(
        "1.0 = TP au fair value complet (WR ~33%, gros gains)\n"
        "0.5 = TP à mi-chemin du FV (WR ~50%, distribution stable → challenge faisable)\n"
        "0.3 = TP court (WR ~60%, mais R:R faible)"
    )
)

st.sidebar.markdown("---")
st.sidebar.header("Mode de simulation")

mode_funded = st.sidebar.toggle(
    "Mode Funded PA — sans reset mensuel",
    value=False,
    help=(
        "OFF = Challenge Apex (reset mensuel, objectif $3K/mois, 60 contrats)\n"
        "ON  = Compte Funded PA (simulation continue 4-5 mois, 40 contrats max)"
    )
)

st.sidebar.markdown("---")
st.sidebar.header("Challenge Apex 50K EOD Trail" if not mode_funded else "Funded PA — Apex 50K")

# Regles officielles Apex 50K EOD Trail (Rithmic)
APEX_50K = {
    "capital":           50_000,
    "profit_target":     3_000,   # objectif challenge mensuel
    "trailing_dd":       2_000,   # drawdown trailing EOD max
    "daily_loss":        1_000,   # perte max par jour
    "max_contracts":     60,      # eval
    "max_contracts_pa":  40,      # performance account
    "consistency_pa":    0.50,    # regle PA : aucun jour > 50% du profit total
}
capital_initial        = st.sidebar.number_input("Capital ($)", value=APEX_50K["capital"], step=1000)
max_drawdown_dollars   = APEX_50K["trailing_dd"]
daily_loss_limit       = APEX_50K["daily_loss"]
max_contracts          = APEX_50K["max_contracts_pa"] if mode_funded else APEX_50K["max_contracts"]

fixed_contracts = st.sidebar.number_input(
    "Contrats fixes (0 = Half-Kelly auto)",
    value=0 if mode_funded else 30,
    min_value=0, max_value=max_contracts, step=1,
    help=(
        "0 = sizing Half-Kelly automatique\n"
        f"Exemple : 30 contrats → E[P&L] ≈ ${int(14*2.3*2*30):,}/mois\n"
        f"Max Apex : {max_contracts} contrats"
    )
)

if mode_funded:
    st.sidebar.info(
        "Regles Funded PA\n"
        f"- DD max : ${max_drawdown_dollars:,} (EOD Trail — global)\n"
        f"- Daily loss : ${daily_loss_limit:,}/jour\n"
        f"- Max contracts : {max_contracts} MNQ\n"
        "- Pas de reset mensuel — simulation continue"
    )
else:
    st.sidebar.info(
        "Regles Apex 50K EOD\n"
        f"- DD max : ${max_drawdown_dollars:,} (EOD Trail)\n"
        f"- Daily loss : ${daily_loss_limit:,}/jour\n"
        f"- Max contracts : {max_contracts} MNQ (eval)"
    )

# Phases MM (identiques au live) — Half-Kelly base = 10% du DD restant
# SECURITE  >= 80% objectif     → 4% DD restant
# PRUDENTE  DD>50% ou <$400 ou jours 1-5 → 5% DD restant
# STANDARD  jours 6-17           → 10% DD restant (Half-Kelly)
PHASE_RISK = {"SECURITE": 0.04, "PRUDENTE": 0.05, "STANDARD": 0.10}
RISK_MIN_DOLLARS = 80.0    # plancher
RISK_MAX_DOLLARS = 600.0   # plafond par trade

TICK_VALUE = 0.50
TICK_SIZE = 0.25
DOLLAR_PER_PT = TICK_VALUE / TICK_SIZE  # $2/pt MNQ
DAILY_LOSS_HARD = daily_loss_limit * 0.80  # stop interne a $800 (80% du limit)


# ══════════════════��═══════════════════════════════════════════════════
# ENGINE
# ══════════════════════════════════════════════════════════════════════

@st.cache_data
def load_ohlcv_csv(filepath):
    """
    Charge le CSV ohlcv-1m Databento.
    Gere les fichiers multi-contrats (plusieurs expiries MNQ par timestamp) :
    - Exclut les spreads (symboles contenant '-')
    - Garde uniquement le front month (contrat le plus liquide a chaque barre)
    """
    df = pd.read_csv(filepath,
                     usecols=["ts_event", "open", "high", "low", "close", "volume", "symbol"])
    df["bar"] = pd.to_datetime(df["ts_event"], utc=True)
    df.drop(columns=["ts_event"], inplace=True)
    df[["open", "high", "low", "close"]] = df[["open", "high", "low", "close"]].astype(float)
    df["volume"] = df["volume"].astype(int)

    # Exclure les spreads (MNQM4-MNQU4, etc.)
    df = df[~df["symbol"].str.contains("-", na=False)].copy()

    # Front month = contrat le plus liquide par barre → 1 ligne par timestamp
    df.sort_values(["bar", "volume"], ascending=[True, False], inplace=True)
    df = df.drop_duplicates(subset=["bar"], keep="first")

    df.drop(columns=["symbol"], inplace=True)
    df.reset_index(drop=True, inplace=True)

    # ATR et returns
    df["tr"] = np.maximum(
        df["high"] - df["low"],
        np.maximum(
            abs(df["high"] - df["close"].shift(1)),
            abs(df["low"] - df["close"].shift(1))
        )
    )
    df["atr_14"] = df["tr"].rolling(14, min_periods=1).mean()
    df["returns"] = df["close"].pct_change().fillna(0)
    df["date"] = df["bar"].dt.date
    return df


def filter_session(df, start_h, start_m, end_h, end_m):
    """Filtre les barres sur la session de trading."""
    t_min = df["bar"].dt.hour * 60 + df["bar"].dt.minute
    mask = (t_min >= start_h * 60 + start_m) & (t_min < end_h * 60 + end_m)
    return df[mask].reset_index(drop=True)


def load_single_day(filepath, start_h, start_m, end_h, end_m):
    """Legacy: charge un fichier ticks Databento, filtre session."""
    df = pd.read_csv(filepath, usecols=["ts_event", "side", "price", "size"])
    df["ts"] = pd.to_datetime(df["ts_event"], utc=True)
    df["price"] = df["price"].astype(float)
    df["size"] = df["size"].astype(int)
    df.drop(columns=["ts_event"], inplace=True)
    t_min = df["ts"].dt.hour * 60 + df["ts"].dt.minute
    mask = (t_min >= start_h * 60 + start_m) & (t_min < end_h * 60 + end_m)
    return df[mask].sort_values("ts").reset_index(drop=True)


def build_bars(df, freq_seconds):
    """Legacy: ticks → barres OHLCV + ATR."""
    df = df.copy()
    df["bar"] = df["ts"].dt.floor(f"{freq_seconds}s")
    bars = df.groupby("bar").agg(
        open=("price", "first"), high=("price", "max"),
        low=("price", "min"), close=("price", "last"),
        volume=("size", "sum"),
    ).reset_index()
    bars["tr"] = np.maximum(
        bars["high"] - bars["low"],
        np.maximum(abs(bars["high"] - bars["close"].shift(1)),
                   abs(bars["low"] - bars["close"].shift(1)))
    )
    bars["atr_14"] = bars["tr"].rolling(14, min_periods=1).mean()
    bars["returns"] = bars["close"].pct_change().fillna(0)
    bars["date"] = bars["bar"].dt.date
    return bars


def compute_garch_vol(returns, alpha1=0.12, beta1=0.85):
    """GARCH(1,1) volatility."""
    alpha0 = 0.00001
    n = len(returns)
    sigma2 = np.zeros(n)
    sigma2[0] = alpha0 / max(1 - alpha1 - beta1, 0.01)
    for t in range(1, n):
        sigma2[t] = alpha0 + alpha1 * returns[t - 1] ** 2 + beta1 * sigma2[t - 1]
    return np.sqrt(sigma2)


def classify_regime(garch_vol, window=60):
    """LOW / MED / HIGH vol regime via GARCH percentiles."""
    regimes = np.full(len(garch_vol), 1)
    for i in range(window, len(garch_vol)):
        history = garch_vol[max(0, i - window):i]
        p33 = np.percentile(history, 33)
        p67 = np.percentile(history, 67)
        if garch_vol[i] < p33:
            regimes[i] = 0
        elif garch_vol[i] > p67:
            regimes[i] = 2
        else:
            regimes[i] = 1
    return regimes


class MarkovRegime:
    """
    Filtre de régime Bayésien 3-états — implémentation exacte Quant Guild Lec 72/74.

    Architecture identique au bot IBKR de Roman Paolucci :
    - Calibration sur données historiques (percentile 33/67 → params émission + matrice transition)
    - Inférence barre par barre : prior = T^T @ state_probs → likelihood gaussienne → posterior Bayes
    - States : 0=LOW vol, 1=MED vol, 2=HIGH vol

    Vs GMM : le Bayesian filter garde la mémoire des états précédents via state_probs.
    Chaque mise à jour incorpore l'historique complet via la matrice de transition.
    """

    def __init__(self):
        # Matrice de transition (Lec 72 defaults — transitions collantes)
        self.A = np.array([
            [0.90, 0.08, 0.02],   # LOW  → LOW 90%, MED 8%, HIGH 2%
            [0.10, 0.80, 0.10],   # MED  → LOW 10%, MED 80%, HIGH 10%
            [0.02, 0.08, 0.90],   # HIGH → LOW 2%,  MED 8%,  HIGH 90%
        ])
        # Paramètres d'émission (seront calibrés)
        self.mu  = np.array([0.0005, 0.002, 0.005])
        self.sig = np.array([0.0003, 0.001, 0.003])
        # Croyance courante sur les états (uniform prior)
        self.state_probs = np.array([1/3, 1/3, 1/3])
        self.calibrated = False

    def calibrate(self, returns):
        """Calibre les paramètres d'émission + matrice de transition depuis les données."""
        vols = np.abs(returns)
        vols = vols[vols > 0]
        if len(vols) < 20:
            return
        p33, p67 = np.percentile(vols, 33), np.percentile(vols, 67)
        labels = np.zeros(len(vols), dtype=int)
        labels[vols >= p33] = 1
        labels[vols >= p67] = 2
        # Paramètres d'émission par régime
        for s in range(3):
            rv = vols[labels == s]
            if len(rv) >= 3:
                self.mu[s]  = np.mean(rv)
                self.sig[s] = max(np.std(rv), 1e-8)
        # Matrice de transition par comptage + Laplace smoothing
        counts = np.zeros((3, 3))
        for t in range(1, len(labels)):
            counts[labels[t-1], labels[t]] += 1
        for i in range(3):
            row = counts[i].sum()
            if row > 0:
                self.A[i] = (counts[i] + 0.1) / (row + 0.3)
        self.state_probs = np.array([1/3, 1/3, 1/3])
        self.calibrated = True

    def update(self, vol_obs):
        """Mise à jour Bayésienne sur une nouvelle observation de volatilité."""
        # 1. Prédiction : prior = A^T @ state_probs
        prior = self.A.T @ self.state_probs
        # 2. Vraisemblance gaussienne par état
        lk = np.array([self._gauss(vol_obs, s) for s in range(3)])
        # 3. Posterior : Bayes
        post = prior * lk
        total = post.sum()
        self.state_probs = post / total if total > 0 else prior
        return int(np.argmax(self.state_probs))

    def _gauss(self, x, s):
        c = 1.0 / (self.sig[s] * np.sqrt(2 * np.pi))
        return c * np.exp(-0.5 * ((x - self.mu[s]) / self.sig[s]) ** 2)

    def run_on_series(self, returns):
        """Applique le filtre sur toute une série. Retourne array de régimes 0/1/2."""
        n = len(returns)
        regimes = np.ones(n, dtype=int)
        self.state_probs = np.array([1/3, 1/3, 1/3])
        for i in range(n):
            regimes[i] = self.update(abs(returns[i]))
        return regimes


def kalman_ou_filter(prices, lookback, R_mult=5.0):
    """
    Kalman filter sur un modele OU (Ornstein-Uhlenbeck).
    Ref: Quant Guild #92 + #95

    Retourne pour chaque barre:
    - fair_value  : estimation Kalman du prix moyen
    - sigma_stat  : deviation stationnaire (bandes de reversion)
    - kalman_gain : K du filtre
    - half_lives  : demi-vie OU en barres = -log(2)/log(phi)
                    Filtre : n'entrer que si half_life < seuil (reversion rapide)
    """
    n = len(prices)
    fair_values = np.full(n, np.nan)
    sigma_stats = np.full(n, np.nan)
    kalman_gains = np.full(n, np.nan)
    half_lives   = np.full(n, np.nan)

    for i in range(lookback, n):
        window = prices[max(0, i - lookback):i]

        # Calibration AR(1): X_t = phi * X_{t-1} + c + eps
        x_prev = window[:-1]
        x_curr = window[1:]
        m = len(x_prev)

        if np.std(x_prev) < 1e-10 or m < 10:
            fair_values[i] = prices[i]
            sigma_stats[i] = 5.0
            kalman_gains[i] = 0.5
            half_lives[i]   = 999.0
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
            half_lives[i]   = 999.0
            continue

        phi = np.clip((m * sxy - sx * sy) / denom, 0.5, 0.999)
        c = (sy - phi * sx) / m
        mu = c / (1 - phi) if abs(1 - phi) > 1e-6 else np.mean(window)
        residuals = x_curr - (phi * x_prev + c)
        sigma = np.std(residuals)
        if sigma < 1e-10:
            sigma = 1.0

        sigma_stat = sigma / np.sqrt(max(2 * (1 - phi), 0.001))

        # Demi-vie OU : nombre de barres pour revenir à 50% de l'écart
        # half_life = -log(2) / log(phi)   (phi proche de 1 → slow mean reversion)
        hl = -np.log(2) / np.log(phi) if phi > 0 else 999.0

        # Kalman filter
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
        half_lives[i]   = hl

    return fair_values, sigma_stats, kalman_gains, half_lives


def find_signals(bars, fair_values, sigma_stats, regimes, band_k, band_k_max=3.0,
                 allow_multiple=False, min_bar_idx=0,
                 skip_open=0, skip_close=0, only_low=False,
                 half_lives=None, max_half_life=None,
                 confirm_reversal=False):
    """
    Genere les signaux d'entree.

    Filtres Quant Guild :
    - only_low        : uniquement régime LOW vol (Lec 51/72/74)
    - max_half_life   : demi-vie OU max en barres — filtre les signaux trop lents à revenir
                        (Lec 92/95 : n'entrer que si la reversion est probable dans la session)
    - confirm_reversal: n'entrer qu'à la barre i+1 si elle est déjà plus proche du FV que i
                        (Lec 72 timing : confirmation que la reversion a commencé)
    - skip_open/close : filtre horaire (évite ouverture + gamma closing)
    """
    n = len(bars)
    signals = []
    traded_today = set()
    valid_end = max(skip_open, n - skip_close)

    for i in range(n):
        if i < skip_open or i >= valid_end:
            continue
        if i < min_bar_idx:
            continue
        if np.isnan(fair_values[i]) or np.isnan(sigma_stats[i]):
            continue

        date = bars.iloc[i]["date"]
        if not allow_multiple and date in traded_today:
            continue

        if regimes[i] == 2:
            continue
        if only_low and regimes[i] != 0:
            continue

        close = bars.iloc[i]["close"]
        fv = fair_values[i]
        ss = sigma_stats[i]
        deviation = abs(close - fv) / ss if ss > 0 else 0

        if deviation < band_k or deviation > band_k_max:
            continue

        # Filtre demi-vie OU (Quant Guild #92/#95)
        # Ne trader que si la reversion est assez rapide pour se produire dans la session
        if max_half_life is not None and half_lives is not None:
            hl = half_lives[i]
            if np.isnan(hl) or hl > max_half_life:
                continue

        # Confirmation de reversion (Quant Guild #72 — timing d'entrée)
        # N'entrer que si la barre suivante montre déjà un mouvement vers FV
        if confirm_reversal:
            if i + 1 >= n:
                continue
            if np.isnan(fair_values[i + 1]) or np.isnan(sigma_stats[i + 1]):
                continue
            next_dev = abs(bars.iloc[i + 1]["close"] - fair_values[i + 1]) / sigma_stats[i + 1] \
                       if sigma_stats[i + 1] > 0 else deviation
            if next_dev >= deviation:   # pas encore en train de revenir
                continue
            # Entrer à la barre i+1 (confirmation)
            entry_bar = i + 1
            entry_close = bars.iloc[i + 1]["close"]
        else:
            entry_bar = i
            entry_close = close

        direction = None
        if close > fv:
            direction = "short"
        elif close < fv:
            direction = "long"

        if direction:
            if not allow_multiple:
                traded_today.add(date)
            signals.append({
                "bar_idx": entry_bar,
                "date": date,
                "bar": bars.iloc[entry_bar]["bar"],
                "price": entry_close,
                "fair_value": fv,
                "sigma_stat": ss,
                "direction": direction,
                "deviation": deviation,
                "regime": regimes[i],
            })

    return signals


def simulate_trade(bars, entry_idx, entry_price, direction, sl_pts, tp_price, slip_pts):
    """
    Simule un trade.
    Retourne (result_pts, exit_bar_idx) pour permettre les trades sequentiels en mode funded.
    """
    if direction == "long":
        real_entry = entry_price + slip_pts
        sl_price = real_entry - sl_pts
    else:
        real_entry = entry_price - slip_pts
        sl_price = real_entry + sl_pts

    for i in range(entry_idx + 1, min(entry_idx + 120, len(bars))):
        bar = bars.iloc[i]

        if direction == "long":
            if bar["low"] <= sl_price:
                return -(sl_pts + slip_pts), i
            if bar["high"] >= tp_price:
                return (tp_price - slip_pts) - real_entry, i
        else:
            if bar["high"] >= sl_price:
                return -(sl_pts + slip_pts), i
            if bar["low"] <= tp_price:
                return real_entry - (tp_price + slip_pts), i

    # Timeout → close at market
    exit_idx = min(entry_idx + 119, len(bars) - 1)
    last = bars.iloc[exit_idx]["close"]
    if direction == "long":
        return (last - slip_pts) - real_entry, exit_idx
    else:
        return real_entry - (last + slip_pts), exit_idx


def kelly_fraction(results):
    """Kelly et demi-Kelly."""
    wins = results[results > 0]
    losses = results[results < 0]
    if len(wins) == 0 or len(losses) == 0:
        return 0, 0
    p = len(wins) / len(results)
    b = wins.mean() / abs(losses.mean())
    k = (p * b - (1 - p)) / b
    return max(0, k), max(0, k / 2)


# ══════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════

if st.sidebar.button("Lancer le Backtest", type="primary"):
    # Collecte les fichiers depuis les 2 dossiers (dossier 2 optionnel)
    dirs_to_scan = [d for d in [data_dir, data_dir2, data_dir3] if d.strip()]

    csv_files   = []
    legacy_files = []
    for d in dirs_to_scan:
        csv_files   += sorted(glob.glob(os.path.join(d, "*.ohlcv-1m.csv")))
        legacy_files += sorted(glob.glob(os.path.join(d, "*.trades.csv")))

    if csv_files:
        # Nouveau format: CSV ohlcv-1m
        with st.spinner("Chargement des CSV ohlcv-1m..."):
            frames = [load_ohlcv_csv(f) for f in csv_files]
            full_df = pd.concat(frames, ignore_index=True)
            full_df.sort_values("bar", inplace=True)
            full_df.drop_duplicates(subset=["bar"], inplace=True)
            full_df.reset_index(drop=True, inplace=True)
        dates = sorted(full_df["date"].unique())
        st.info(f"{len(dates)} jours ({dates[0]} → {dates[-1]}). Pipeline: GARCH regime → Kalman OU → Bandes → 1 trade/session")
    elif legacy_files:
        # Format ticks Databento (1 fichier par jour)
        # Tri par la DATE dans le nom de fichier (YYYYMMDD), pas par le chemin complet
        # (sinon GLBX-20260327 serait trié avant GLBX-20260330 même si Nov < Dec)
        import re as _re_sort
        def _sort_key(p):
            m = _re_sort.search(r'(\d{8})', os.path.basename(p))
            return m.group(1) if m else p
        legacy_files = sorted(set(legacy_files), key=_sort_key)
        full_df = None
        dates = legacy_files
        _first = os.path.basename(legacy_files[0])
        _last  = os.path.basename(legacy_files[-1])
        st.info(f"{len(dates)} fichiers ticks ({_first[:19]} → {_last[:19]}). Pipeline: GARCH regime → Kalman OU → Bandes → 1 trade/session")
    else:
        st.error("Aucun fichier CSV trouve. Verifie les dossiers Databento ci-dessus.")
        st.stop()

    progress = st.progress(0)
    slip = slippage_ticks * TICK_SIZE

    import re as _re

    def get_month_key(d):
        """
        Retourne 'YYYY-MM' depuis :
        - une date string "2026-03-24"
        - un chemin de fichier legacy "C:\\...\\GLBX-20260324-xxx.csv"
        """
        s = str(d)
        # Cherche un pattern YYYYMMDD dans le chemin (fichiers Databento)
        m = _re.search(r'(\d{4})(\d{2})(\d{2})', s)
        if m:
            return f"{m.group(1)}-{m.group(2)}"
        # Sinon suppose format date "YYYY-MM-DD"
        return s[:7]

    dates_sorted = sorted(dates, key=lambda d: str(d))

    all_trades = []
    all_daily_stats = []
    monthly_results = []

    skipped_high_vol = 0
    skipped_no_signal = 0
    skipped_dd = 0
    skipped_daily_loss = 0
    skipped_consec = 0

    # État — en mode funded: simulation continue; en mode challenge: reset mensuel
    running_equity  = capital_initial
    running_peak    = capital_initial
    consec_losses   = 0
    days_elapsed_bt = 0
    challenge_busted  = False
    challenge_passed  = False
    month_trades    = []
    current_month   = None

    # En mode funded : equity de référence pour le sizing (peak global, pas mensuel)
    funded_peak_global = capital_initial

    def _save_month(mk, re_, rp_, mt_, dbt_, cb_, cp_):
        # P&L du mois = equity fin - equity debut de mois
        mp = re_ - capital_initial  # pour le challenge (equity repart de capital_initial)
        md = rp_ - re_
        nw = sum(1 for t in mt_ if t["win"])
        nt = len(mt_)
        monthly_results.append({
            "mois":    mk,
            "pnl":     round(mp, 2),
            "trades":  nt,
            "winrate": round(nw / nt * 100, 1) if nt > 0 else 0,
            "max_dd":  round(md, 2),
            "jours":   dbt_,
            "passe":   cp_,
            "bust":    cb_,
            "statut":  "PASSE" if cp_ else ("BUST" if cb_ else "ECHOUE"),
        })

    def _save_month_funded(mk, pnl_month, mt_, dbt_):
        nw = sum(1 for t in mt_ if t["win"])
        nt = len(mt_)
        monthly_results.append({
            "mois":    mk,
            "pnl":     round(pnl_month, 2),
            "trades":  nt,
            "winrate": round(nw / nt * 100, 1) if nt > 0 else 0,
            "jours":   dbt_,
            "statut":  "PA",
        })

    month_equity_start = capital_initial  # suivi du P&L mensuel en mode funded

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
                                       month_trades, days_elapsed_bt)
                    month_equity_start = running_equity
                    days_elapsed_bt    = 0
                    month_trades       = []
                else:
                    _save_month(current_month, running_equity, running_peak,
                                month_trades, days_elapsed_bt, challenge_busted, challenge_passed)
                    # Reset mensuel (mode challenge uniquement)
                    running_equity    = capital_initial
                    running_peak      = capital_initial
                    consec_losses     = 0
                    days_elapsed_bt   = 0
                    challenge_busted  = False
                    challenge_passed  = False
                    month_trades      = []
            current_month = day_month

        # En mode challenge : skip si deja passe ou bust ce mois
        if not mode_funded and (challenge_passed or challenge_busted):
            continue

        # En mode funded : stop global si DD depasse la limite
        if mode_funded and challenge_busted:
            break

        # ── Phase MM (identique au live) ─────────────────────────────
        running_dd = running_peak - running_equity
        trailing_dd_remaining = max(0.0, max_drawdown_dollars - running_dd)

        if mode_funded:
            # En funded : phase basee sur le DD global (pas sur l'objectif mensuel)
            dd_pct_used  = running_dd / max_drawdown_dollars
            challenge_pct = 1.0   # pas d'objectif a atteindre
        else:
            challenge_pnl = running_equity - capital_initial
            challenge_pct = challenge_pnl / APEX_50K["profit_target"]
            dd_pct_used   = running_dd / max_drawdown_dollars

        if challenge_pct >= 0.80 and not mode_funded:
            phase_risk = PHASE_RISK["SECURITE"]
        elif dd_pct_used > 0.50 or trailing_dd_remaining < 400:
            phase_risk = PHASE_RISK["PRUDENTE"]
        elif days_elapsed_bt <= 5:
            phase_risk = PHASE_RISK["PRUDENTE"]
        else:
            phase_risk = PHASE_RISK["STANDARD"]

        # ── Stop DD Apex ──────────────────────────────────────────────
        if running_dd >= max_drawdown_dollars:
            challenge_busted = True
            if mode_funded:
                break
            # en mode challenge: le mois est bust, on continue le mois suivant

        # ── Check objectif mensuel atteint (challenge uniquement) ─────
        if not mode_funded:
            challenge_pnl = running_equity - capital_initial
            if challenge_pnl >= APEX_50K["profit_target"] and not challenge_passed:
                challenge_passed = True

        # ── Stop consec inter-journees ────────────────────────────────
        if consec_losses >= 2:
            skipped_consec += 1
            consec_losses = 0   # reset apres pause d'un jour
            all_daily_stats.append({
                "date": day_key, "regime": "SKIP",
                "action": "SKIP", "reason": "2 pertes consecutives — pause 1 jour",
            })
            continue

        days_elapsed_bt += 1

        # 1. Barres du jour
        if full_df is not None:
            # Format ohlcv-1m: filtrer par date puis par session
            day_df = full_df[full_df["date"] == day_key].copy()
            bars = filter_session(day_df, session_start_h, session_start_m,
                                  session_end_h, session_end_m)
        else:
            # Legacy ticks
            ticks = load_single_day(day_key, session_start_h, session_start_m,
                                    session_end_h, session_end_m)
            if len(ticks) < 100:
                skipped_no_signal += 1
                continue
            bars = build_bars(ticks, bar_seconds)
            del ticks

        if len(bars) < kalman_lookback + 20:
            skipped_no_signal += 1
            continue

        # 3. Régime vol — Bayesian Markov Filter (Lec 72/74) ou GARCH fallback
        garch_vol = compute_garch_vol(bars["returns"].values, garch_alpha1, garch_beta1)
        if use_gmm_regime:
            mr = MarkovRegime()
            mr.calibrate(bars["returns"].values)
            regimes = mr.run_on_series(bars["returns"].values)
        else:
            regimes = classify_regime(garch_vol)

        # Regime dominant
        regime_counts = np.bincount(regimes, minlength=3)
        dominant_regime = regime_counts.argmax()
        if dominant_regime == 2:
            skipped_high_vol += 1
            all_daily_stats.append({
                "date": bars.iloc[0]["date"], "regime": "HIGH",
                "action": "SKIP", "reason": "Regime HIGH vol",
            })
            continue

        # 4. Kalman OU filter (retourne aussi half_lives)
        prices = bars["close"].values
        fair_values, sigma_stats, k_gains, half_lives = kalman_ou_filter(
            prices, kalman_lookback, kalman_R_mult
        )

        # 5. Signaux
        signals = find_signals(
            bars, fair_values, sigma_stats, regimes, band_k, band_k_max,
            allow_multiple=mode_funded,
            skip_open=skip_open_bars, skip_close=skip_close_bars,
            only_low=only_low_regime,
            half_lives=half_lives if use_halflife_filter else None,
            max_half_life=max_half_life_bars,
            confirm_reversal=confirm_reversal,
        )

        if not signals:
            skipped_no_signal += 1
            all_daily_stats.append({
                "date": bars.iloc[0]["date"],
                "regime": ["LOW", "MED", "HIGH"][dominant_regime],
                "action": "SKIP", "reason": "Pas de signal (prix dans les bandes)",
            })
            continue

        # 6. Boucle sur les signaux du jour
        # En challenge : 1 signal (signals[0]). En funded : tous, séquentiels (attente exit).
        signals_to_trade = signals if mode_funded else [signals[0]]
        last_exit_bar    = -1   # barre de sortie du dernier trade (funded uniquement)
        daily_pnl        = 0.0  # P&L intra-journée (funded uniquement)
        day_consec       = 0    # pertes consec intra-journée (funded uniquement)
        day_trade_count  = 0    # compteur trades dans la journée (funded uniquement)

        for sig in signals_to_trade:
            bar_idx = sig["bar_idx"]

            # En funded : ne pas entrer pendant qu'un trade est ouvert
            if mode_funded and bar_idx <= last_exit_bar:
                continue

            # En funded : stop journalier intra-day
            if mode_funded and daily_pnl <= -DAILY_LOSS_HARD:
                break
            if mode_funded and day_consec >= 2:
                break
            # En funded : plafond max trades/jour (evite spikes irrealistes)
            if mode_funded and day_trade_count >= max_trades_per_day:
                break

            # 7. SL dynamique ATR
            atr = bars.iloc[bar_idx]["atr_14"]
            if np.isnan(atr) or atr <= 0:
                atr = bars["tr"].mean()
            if np.isnan(atr) or atr <= 0:
                atr = 8.0
            sl_pts = np.clip(atr * atr_sl_mult, min_sl_pts, max_sl_pts)

            # 8. TP = retour au fair value Kalman
            # TP à tp_ratio * distance vers FV (0.5 = mi-chemin → WR ~50%)
            tp_price = sig["price"] + tp_ratio * (sig["fair_value"] - sig["price"])

            # 9. Sizing
            if fixed_contracts > 0:
                # Mode contrats fixes : bypass Kelly, respecte quand meme les protections DD
                contracts = min(fixed_contracts, max_contracts)
            else:
                # Mode Half-Kelly automatique
                risk_dollars = np.clip(
                    trailing_dd_remaining * phase_risk,
                    RISK_MIN_DOLLARS, RISK_MAX_DOLLARS
                )
                risk_dollars = min(risk_dollars, DAILY_LOSS_HARD)
                contracts = max(1, int(risk_dollars / (sl_pts * DOLLAR_PER_PT)))
                contracts = min(contracts, max_contracts)

            loss_if_sl = sl_pts * DOLLAR_PER_PT * contracts

            if loss_if_sl > DAILY_LOSS_HARD:
                contracts = max(1, int(DAILY_LOSS_HARD / (sl_pts * DOLLAR_PER_PT)))
                loss_if_sl = sl_pts * DOLLAR_PER_PT * contracts

            if loss_if_sl > trailing_dd_remaining:
                skipped_dd += 1
                continue

            # 10. Simuler
            result_pts, exit_bar = simulate_trade(bars, bar_idx, sig["price"],
                                                  sig["direction"], sl_pts, tp_price, slip)
            last_exit_bar = exit_bar

            pnl_dollars = result_pts * DOLLAR_PER_PT * contracts
            running_equity += pnl_dollars
            daily_pnl += pnl_dollars

            # EOD Trail : peak mis à jour après chaque trade
            if running_equity > running_peak:
                running_peak = running_equity

            # Tracking consec inter-journées (challenge) / intra-journée (funded)
            if pnl_dollars < 0:
                consec_losses += 1
                day_consec += 1
            else:
                consec_losses = 0
                day_consec = 0

            tp_pts = abs(sig["fair_value"] - sig["price"])
            rr_target = tp_pts / sl_pts if sl_pts > 0 else 0

            trade = {
                "date": sig["date"],
                "time": sig["bar"],
                "price": round(sig["price"], 2),
                "fair_value": round(sig["fair_value"], 2),
                "sigma_stat": round(sig["sigma_stat"], 2),
                "deviation": round(sig["deviation"], 2),
                "direction": sig["direction"],
                "regime": ["LOW", "MED", "HIGH"][sig["regime"]],
                "sl_pts": round(sl_pts, 2),
                "tp_pts": round(tp_pts, 2),
                "rr_target": round(rr_target, 1),
                "result_pts": round(result_pts, 2),
                "contracts": contracts,
                "pnl_dollars": round(pnl_dollars, 2),
                "win": result_pts > 0,
                "equity": round(running_equity, 2),
                "dd_from_peak": round(running_peak - running_equity, 2),
            }
            all_trades.append(trade)
            month_trades.append(trade)
            day_trade_count += 1

            all_daily_stats.append({
                "date": sig["date"],
                "regime": trade["regime"],
                "action": "TRADE",
                "reason": f"{sig['direction']} @ {sig['price']:.2f}, "
                          f"FV={sig['fair_value']:.2f}, dev={sig['deviation']:.1f}σ",
            })

            # Verifier objectif mensuel (challenge uniquement)
            if not mode_funded and running_equity - capital_initial >= APEX_50K["profit_target"]:
                challenge_passed = True
                break

            # En funded : stop si DD global atteint après ce trade
            if mode_funded:
                running_dd_check = running_peak - running_equity
                if running_dd_check >= max_drawdown_dollars:
                    challenge_busted = True
                    break

    # ── Sauvegarder le dernier mois apres la boucle ───────────────────
    if current_month is not None:
        if mode_funded:
            _save_month_funded(current_month,
                               running_equity - month_equity_start,
                               month_trades, days_elapsed_bt)
        else:
            _save_month(current_month, running_equity, running_peak,
                        month_trades, days_elapsed_bt, challenge_busted, challenge_passed)

    progress.empty()

    # ══════════════════════════════════════════════════════════════════
    # RESULTATS
    # ══════════════════════════════════════════════════════════════════

    if not all_trades:
        st.warning("Aucun trade. Baisse k (bande) ou le lookback.")
        st.stop()

    trades_df = pd.DataFrame(all_trades)
    daily_df = pd.DataFrame(all_daily_stats)

    # ── Onglets resultats ─────────────────────────────────────────────
    tab1_label = "💰 Funded PA" if mode_funded else "📅 Bilan Mensuel"
    tab1, tab2, tab3, tab4, tab5 = st.tabs([tab1_label, "📈 Resultats", "🔧 Pipeline", "📉 Charts", "🎲 Monte Carlo"])

    monthly_df    = pd.DataFrame(monthly_results)
    final_pnl     = trades_df["pnl_dollars"].sum()
    max_dd_actual = trades_df["dd_from_peak"].max()
    dd_pct        = max_dd_actual / max_drawdown_dollars * 100

    with tab1:
        if mode_funded:
            st.markdown("<p class='section-title'>Funded PA — Simulation continue (pas de reset mensuel)</p>", unsafe_allow_html=True)

            n_months  = len(monthly_df)
            avg_pnl   = monthly_df["pnl"].mean()
            best_m    = monthly_df.loc[monthly_df["pnl"].idxmax(), "mois"] if n_months > 0 else "—"
            worst_m   = monthly_df.loc[monthly_df["pnl"].idxmin(), "mois"] if n_months > 0 else "—"
            pos_months = (monthly_df["pnl"] > 0).sum()

            fa1, fa2, fa3, fa4, fa5 = st.columns(5)
            fa1.metric("P&L total (4-5 mois)", f"${final_pnl:+,.0f}")
            fa2.metric("DD max global", f"${max_dd_actual:,.0f}",
                       delta=f"{dd_pct:.0f}% du max $2 000",
                       delta_color="inverse" if dd_pct > 50 else "normal")
            fa3.metric("Mois positifs", f"{pos_months} / {n_months}")
            fa4.metric("P&L moyen / mois", f"${avg_pnl:+,.0f}")
            fa5.metric("Contrats max PA", f"{max_contracts} MNQ")

            if challenge_busted:
                st.error(f"BUST — DD global depasse ${max_drawdown_dollars:,} → compte coupe")
            elif dd_pct > 50:
                st.warning(f"DD {dd_pct:.0f}% du max — attention au risque de bust")
            else:
                st.success(f"Compte intact — DD max ${max_dd_actual:,.0f} / ${max_drawdown_dollars:,}")

            # Tableau mensuel funded
            def color_pnl_funded(val):
                try:
                    return "color: #00ff88" if float(val) >= 0 else "color: #ff3366"
                except Exception:
                    return ""

            monthly_display = monthly_df.rename(columns={
                "mois": "Mois", "pnl": "P&L ($)", "trades": "Trades",
                "winrate": "WR %", "jours": "Jours trades", "statut": "Mode"
            })[["Mois", "P&L ($)", "Trades", "WR %", "Jours trades"]]

            st.dataframe(
                monthly_display.style.applymap(color_pnl_funded, subset=["P&L ($)"]),
                use_container_width=True, hide_index=True
            )

        else:
            st.markdown("<p class='section-title'>Challenge Apex — Fenetre 1 mois calendaire (reset mensuel)</p>", unsafe_allow_html=True)

            n_months    = len(monthly_df)
            n_passed    = (monthly_df["statut"] == "PASSE").sum()
            n_failed    = (monthly_df["statut"] == "ECHOUE").sum()
            n_busted    = (monthly_df["statut"] == "BUST").sum()
            pass_rate   = n_passed / n_months * 100 if n_months > 0 else 0
            avg_days    = monthly_df[monthly_df["passe"]]["jours"].mean() if n_passed > 0 else float("nan")

            mb1, mb2, mb3, mb4, mb5 = st.columns(5)
            mb1.metric("Mois simules", n_months)
            mb2.metric("PASSES", n_passed,
                       delta=f"{pass_rate:.0f}% taux de reussite", delta_color="normal")
            mb3.metric("ECHOUES", n_failed, delta_color="inverse")
            mb4.metric("BUST", n_busted, delta_color="inverse")
            mb5.metric("Jours moy pour passer", f"{avg_days:.1f}" if not pd.isna(avg_days) else "N/A")

            if pass_rate >= 70:
                st.success(f"Taux de reussite {pass_rate:.0f}% — edge robuste pour l'eval Apex")
            elif pass_rate >= 50:
                st.warning(f"Taux de reussite {pass_rate:.0f}% — acceptable mais optimiser les parametres")
            else:
                st.error(f"Taux de reussite {pass_rate:.0f}% — revoir le sizing ou les conditions d'entree")

            def color_statut(val):
                if val == "PASSE":  return "background-color: #1a3a1a; color: #00ff88"
                if val == "BUST":   return "background-color: #3a1a1a; color: #ff3366"
                return "background-color: #2a2a1a; color: #ffd600"

            monthly_display = monthly_df.rename(columns={
                "mois": "Mois", "pnl": "P&L ($)", "trades": "Trades",
                "winrate": "WR %", "max_dd": "DD max ($)", "jours": "Jours trades", "statut": "Statut"
            })[["Mois", "P&L ($)", "Trades", "WR %", "DD max ($)", "Jours trades", "Statut"]]

            st.dataframe(
                monthly_display.style.applymap(color_statut, subset=["Statut"]),
                use_container_width=True, hide_index=True
            )

            ca1, ca2, ca3, ca4, ca5 = st.columns(5)
            ca1.metric("P&L dernier mois", f"${running_equity - capital_initial:+,.0f}",
                       delta=f"{(running_equity - capital_initial)/APEX_50K['profit_target']*100:.0f}% objectif")
            ca2.metric("DD max", f"${max_dd_actual:,.0f}",
                       delta=f"{dd_pct:.0f}% du max $2 000",
                       delta_color="inverse" if dd_pct > 50 else "normal")
            ca3.metric("DD autorise", f"${max_drawdown_dollars:,}", delta="EOD Trail")
            ca4.metric("Jours trades (dernier mois)", days_elapsed_bt)
            ca5.metric("Daily stop interne", f"${DAILY_LOSS_HARD:.0f}", delta="80% de $1 000/j")

    # ── Calculs communs (utilises dans tab2 et tab4) ───────────────────
    results = trades_df["result_pts"].values
    pnl = trades_df["pnl_dollars"].values
    wins = results[results > 0]
    losses = results[results < 0]
    n_total = len(results)
    n_wins = len(wins)
    winrate = n_wins / n_total if n_total > 0 else 0
    avg_win = wins.mean() if len(wins) > 0 else 0
    avg_loss = abs(losses.mean()) if len(losses) > 0 else 0
    expectancy = (winrate * avg_win) - ((1 - winrate) * avg_loss)
    gross_profit = wins.sum() if len(wins) > 0 else 0
    gross_loss = abs(losses.sum()) if len(losses) > 0 else 1
    profit_factor = gross_profit / gross_loss
    kelly_full, kelly_half = kelly_fraction(results)

    # Sharpe sur returns JOURNALIERS — inclut les jours sans trade (= 0)
    # Fix : convertir l'index date → DatetimeIndex avant reindex (sinon mismatch silencieux)
    daily_pnl = trades_df.groupby("date")["pnl_dollars"].sum()
    daily_pnl.index = pd.to_datetime(daily_pnl.index)
    date_min = pd.to_datetime(trades_df["date"].min())
    date_max = pd.to_datetime(trades_df["date"].max())
    all_bdays = pd.bdate_range(date_min, date_max)
    daily_ret = daily_pnl.reindex(all_bdays, fill_value=0.0) / capital_initial
    n_bdays = len(all_bdays)
    # ── Sharpe journalier (référence uniquement — biaisé par stops asymétriques) ──
    sharpe = (daily_ret.mean() / daily_ret.std() * np.sqrt(252)) if daily_ret.std() > 0 else 0

    # ── Sharpe RÉEL — corrigé pour les trades intraday corrélés ──────────────────
    # Formule : mean(R) / std(R) × √(252 / avg_trades_par_jour)
    # R = result_pts / sl_pts  →  normalise par le risque réel de chaque trade
    # Annualise par sessions indépendantes, pas par nombre de trades
    r_series = trades_df["result_pts"] / trades_df["sl_pts"].replace(0, np.nan)
    r_series = r_series.dropna()
    avg_tpd = max(1.0, len(trades_df) / max(1, n_bdays))   # trades par jour (business)
    sharpe_real = (r_series.mean() / r_series.std() * np.sqrt(252 / avg_tpd)) if r_series.std() > 0 else 0

    # ── Stress-test : +3× slippage sur chaque trade ───────────────────────────
    pnl_stress = trades_df["pnl_dollars"] - trades_df["contracts"] * DOLLAR_PER_PT * slippage_ticks * TICK_SIZE * 2
    r_stress = (trades_df["result_pts"] - slippage_ticks * TICK_SIZE * 2) / trades_df["sl_pts"].replace(0, np.nan)
    r_stress = r_stress.dropna()
    sharpe_stress = (r_stress.mean() / r_stress.std() * np.sqrt(252 / avg_tpd)) if r_stress.std() > 0 else 0

    # ── Sortino réel (downside R uniquement) ─────────────────────────────────
    r_down = r_series[r_series < 0]
    sortino_std = r_down.std() if len(r_down) > 1 else r_series.std()
    sortino = (r_series.mean() / sortino_std * np.sqrt(252 / avg_tpd)) if sortino_std > 0 else 0

    equity = capital_initial + np.cumsum(pnl)
    equity = np.insert(equity, 0, capital_initial)
    peak = np.maximum.accumulate(equity)
    drawdown = (equity - peak) / peak * 100
    max_dd = drawdown.min()
    total_return = (equity[-1] - capital_initial) / capital_initial * 100

    annual_return = daily_ret.mean() * 252
    calmar = annual_return / abs(max_dd / 100) if max_dd != 0 else 0

    n_pos_days = (daily_ret > 0).sum()
    n_neg_days = (daily_ret < 0).sum()
    n_zero_days = (daily_ret == 0).sum()

    with tab2:
        st.markdown("<p class='section-title'>Performance globale</p>", unsafe_allow_html=True)
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Trades", n_total)
        c1.metric("W / L", f"{n_wins} / {len(losses)}")
        c2.metric("Winrate", f"{winrate:.1%}")
        c2.metric("Profit Factor", f"{profit_factor:.2f}")
        c3.metric("Esperance", f"{expectancy:.1f} pts")
        c3.metric("R:R moyen", f"{trades_df['rr_target'].mean():.1f}")
        c4.metric("Gain moyen", f"{avg_win:.1f} pts")
        c4.metric("Perte moy.", f"{avg_loss:.1f} pts")
        c5.metric("Max Drawdown", f"{max_dd:.1f}%")
        c5.metric("P&L total", f"${pnl.sum():,.0f}")

        st.markdown("<p class='section-title'>Métriques de risque ajustées</p>", unsafe_allow_html=True)
        r1, r2, r3, r4, r5 = st.columns(5)
        r1.metric("Sharpe brut", f"{sharpe:.2f}",
                  delta="biaisé — ignorer",
                  delta_color="off")
        r2.metric("Sharpe réel", f"{sharpe_real:.2f}",
                  delta=f"R-normalisé · {avg_tpd:.1f} trades/jour",
                  delta_color="normal" if 1.0 <= sharpe_real <= 3.0 else "inverse")
        r3.metric("Sharpe stress (live)", f"{sharpe_stress:.2f}",
                  delta="+3× slippage · estimation live",
                  delta_color="normal" if sharpe_stress >= 1.0 else "inverse")
        r4.metric("Sortino réel", f"{sortino:.2f}",
                  delta="vol. négative seule",
                  delta_color="normal" if sortino > 1.2 else "inverse")
        r5.metric("Jours +/0/−", f"{n_pos_days}/{n_zero_days}/{n_neg_days}",
                  delta=f"{n_bdays} j. business | Calmar {calmar:.1f}")

        cible_ok = 1.0 <= sharpe_real <= 2.5
        stress_ok = sharpe_stress >= 0.8
        if cible_ok and stress_ok:
            st.success(
                f"**Edge confirmé** — Sharpe réel {sharpe_real:.2f} (cible 1.2–1.5) | "
                f"Stress live {sharpe_stress:.2f} | {avg_tpd:.1f} trades/jour corrigé"
            )
        elif not cible_ok:
            st.warning(
                f"**Sharpe réel {sharpe_real:.2f} hors cible** — "
                f"{'trop élevé → probable overfitting' if sharpe_real > 2.5 else 'trop faible → edge insuffisant'}. "
                f"Cible : 1.2–1.5"
            )

        st.markdown("<p class='section-title'>Kelly Criterion</p>", unsafe_allow_html=True)
        ck1, ck2 = st.columns(2)
    with ck1:
        st.markdown("<p class='section-title'>Kelly Criterion</p>", unsafe_allow_html=True)
        st.metric("Kelly optimal", f"{kelly_full:.1%}")
        st.metric("Demi-Kelly", f"{kelly_half:.1%}")
        avg_sl = trades_df["sl_pts"].mean()
        kc = max(1, int(capital_initial * kelly_half / (avg_sl * DOLLAR_PER_PT))) if kelly_half > 0 else 1
        st.metric("Contracts (1/2 Kelly)", kc)

    with ck2:
        if kelly_full > 0:
            p = winrate
            b_r = avg_win / avg_loss if avg_loss > 0 else 1
            f_range = np.linspace(0, min(1, kelly_full * 3), 200)
            g = p * np.log(1 + b_r * f_range) + (1 - p) * np.log(np.maximum(1 - f_range, 1e-10))
            fig_k = go.Figure()
            fig_k.add_trace(go.Scatter(x=f_range, y=g, mode="lines", line=dict(color=CYAN, width=2)))
            g_k = p * np.log(1 + b_r * kelly_full) + (1 - p) * np.log(max(1 - kelly_full, 1e-10))
            fig_k.add_trace(go.Scatter(x=[kelly_full], y=[g_k], mode="markers",
                                       marker=dict(color=GREEN, size=12), name=f"K={kelly_full:.1%}"))
            fig_k.add_trace(go.Scatter(
                x=[kelly_half],
                y=[p * np.log(1 + b_r * kelly_half) + (1 - p) * np.log(max(1 - kelly_half, 1e-10))],
                mode="markers", marker=dict(color=YELLOW, size=12), name=f"½K={kelly_half:.1%}"))
            fig_k.update_layout(title="Kelly Curve", height=300, xaxis_title="f",
                                yaxis_title="g(f)", **DARK)
            st.plotly_chart(fig_k, use_container_width=True)

    with tab3:
        st.markdown("<p class='section-title'>Filtres pipeline</p>", unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Jours analyses", len(dates))
        c2.metric("Skip HIGH vol", skipped_high_vol)
        c3.metric("Skip pas de signal", skipped_no_signal)
        c4.metric("Skip 2 pertes consec", skipped_consec)
        st.info(f"**{len(trades_df)} trades** sur {len(dates)} jours — Apex 50K EOD | Daily $1 000 | DD $2 000 | Half-Kelly")

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
            text=[f"{'W' if w else 'L'} {r:+.1f}pts | FV={fv:.0f}" for w, r, fv
                  in zip(trades_df["win"], results, trades_df["fair_value"])],
            hovertemplate="%{x}<br>%{text}<br>$%{y:,.0f}<extra></extra>"
        ), row=1, col=1)
        fig_eq.add_trace(go.Scatter(
            x=trades_df["date"].astype(str).tolist(),
            y=drawdown[1:], mode="lines",
            line=dict(color=RED, width=1.5),
            fill="tozeroy", fillcolor="rgba(255,51,102,0.12)"
        ), row=2, col=1)
        fig_eq.update_layout(height=500, showlegend=False, **DARK)
        fig_eq.update_yaxes(title_text="$", row=1, col=1)
        fig_eq.update_yaxes(title_text="%", row=2, col=1)
        st.plotly_chart(fig_eq, use_container_width=True)
    
        # Distribution P&L
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
                        annotation_text=f"Esperance = {expectancy:.1f} pts")
        fig_d.update_layout(height=350, xaxis_title="Date", yaxis_title="Points", **DARK)
        st.plotly_chart(fig_d, use_container_width=True)
    
        # Distribution P&L conditionnelle par regime (Propriete de Markov)
        st.markdown("---")
        st.subheader("Distribution P&L par regime (Propriete de Markov)")
        st.caption(
            "Chaque regime produit une distribution de P&L differente. "
            "Mixer tous les trades donne des statistiques trompeuses (Roman Paolucci #71)."
        )
    
        reg_col_low, reg_col_med = st.columns(2)
        for col_widget, rname in zip([reg_col_low, reg_col_med], ["LOW", "MED"]):
            sub = trades_df[trades_df["regime"] == rname]
            if len(sub) == 0:
                col_widget.info(f"Pas de trades en regime {rname}")
                continue
    
            r = sub["result_pts"].values
            wins_r = r[r > 0]
            losses_r = r[r < 0]
            wr_r = len(wins_r) / len(r) if len(r) > 0 else 0
            avg_w_r = wins_r.mean() if len(wins_r) > 0 else 0
            avg_l_r = abs(losses_r.mean()) if len(losses_r) > 0 else 0
            exp_r = (wr_r * avg_w_r) - ((1 - wr_r) * avg_l_r)
            pf_r = wins_r.sum() / max(abs(losses_r.sum()), 0.01) if len(losses_r) > 0 else 99.0
    
            # Sharpe conditionnel: sur les jours de ce regime uniquement
            sub_daily = sub.groupby("date")["pnl_dollars"].sum()
            regime_sharpe = 0.0
            if len(sub_daily) > 1:
                sub_days_ret = sub_daily.reindex(all_bdays, fill_value=0) / capital_initial
                if sub_days_ret.std() > 0:
                    regime_sharpe = sub_days_ret.mean() / sub_days_ret.std() * np.sqrt(252)
    
            bar_color = CYAN if rname == "LOW" else ORANGE
    
            fig_r = go.Figure()
            fig_r.add_trace(go.Histogram(
                x=r, nbinsx=max(8, len(r) // 2),
                marker_color=bar_color, opacity=0.85,
                name=f"P&L {rname}"
            ))
            fig_r.add_vline(x=exp_r, line_dash="dash", line_color="white",
                            annotation_text=f"E[PL]={exp_r:.1f}pts",
                            annotation_font_color="white")
            fig_r.add_vline(x=0, line_color="rgba(255,255,255,0.25)")
            fig_r.update_layout(
                title=(
                    f"Regime {rname} — {len(r)} trades | WR {wr_r:.0%} | "
                    f"PF {pf_r:.2f} | Sharpe {regime_sharpe:.2f}"
                ),
                height=300, showlegend=False,
                xaxis_title="Points", yaxis_title="Frequence",
                **DARK
            )
            col_widget.plotly_chart(fig_r, use_container_width=True)
    
        # Comparaison et interpretation automatique
        low_sub = trades_df[trades_df["regime"] == "LOW"]["result_pts"].values
        med_sub = trades_df[trades_df["regime"] == "MED"]["result_pts"].values
        low_exp = (low_sub[low_sub > 0].mean() * (low_sub > 0).mean()
                   - abs(low_sub[low_sub < 0].mean()) * (low_sub < 0).mean()) if len(low_sub) > 0 else 0
        med_exp = (med_sub[med_sub > 0].mean() * (med_sub > 0).mean()
                   - abs(med_sub[med_sub < 0].mean()) * (med_sub < 0).mean()) if len(med_sub) > 0 else 0
    
        if low_exp > 0 and med_exp > 0:
            st.success(
                f"**Edge robuste** : positif en LOW ({low_exp:+.1f} pts) ET en MED ({med_exp:+.1f} pts). "
                "Les deux regimes contribuent a l'edge."
            )
        elif low_exp > 0 > med_exp:
            st.warning(
                f"**Edge regime-dependant** : positif en LOW ({low_exp:+.1f} pts) mais negatif en MED "
                f"({med_exp:+.1f} pts). Envisage de desactiver les trades MED vol."
            )
        elif med_exp > 0 > low_exp:
            st.warning(
                f"**Edge regime-dependant** : positif en MED ({med_exp:+.1f} pts) mais negatif en LOW "
                f"({low_exp:+.1f} pts). Comportement inhabituel — verifier les parametres."
            )
        else:
            st.error(
                f"**Pas d'edge dans aucun regime** : LOW={low_exp:+.1f} pts, MED={med_exp:+.1f} pts."
            )
    
        # Stats par deviation
        st.markdown("---")
        st.subheader("Performance par deviation (sigma)")
        bins = [(1.0, 1.5), (1.5, 2.0), (2.0, 3.0), (3.0, 10.0)]
        dev_stats = []
        for lo, hi in bins:
            sub = trades_df[(trades_df["deviation"] >= lo) & (trades_df["deviation"] < hi)]
            if len(sub) == 0:
                continue
            r = sub["result_pts"].values
            w = r[r > 0]
            l = r[r < 0]
            wr = len(w) / len(r)
            avg_w = w.mean() if len(w) > 0 else 0
            avg_l = abs(l.mean()) if len(l) > 0 else 0
            exp = (wr * avg_w) - ((1 - wr) * avg_l)
            dev_stats.append({
                "Deviation": f"{lo}-{hi}σ", "Trades": len(r),
                "Winrate": f"{wr:.1%}", "Esperance": f"{exp:.1f} pts",
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
        csv = display.to_csv(index=False)
        st.download_button("Telecharger CSV", csv, "backtest_kalman.csv", "text/csv")
    
        # Log journalier
        st.markdown("---")
        st.subheader("Log journalier")
        st.dataframe(daily_df, use_container_width=True, hide_index=True)
    
        # Verdict
        st.markdown("---")
        st.subheader("Verdict")
        if expectancy > 0 and profit_factor > 1.5:
            st.success(
                f"**EDGE CONFIRME** — {winrate:.1%} WR, {expectancy:.1f} pts/trade, "
                f"PF {profit_factor:.2f}, Kelly {kelly_full:.1%}\n\n"
                f"Signal: Kalman OU (k={band_k}σ) | TP {tp_ratio:.0%} vers FV | SL = ATR\n\n"
                f"Return: **{total_return:+.1f}%** | Max DD: **{max_dd:.1f}%** | "
                f"Demi-Kelly: **{kelly_half:.1%}** = {kc} contracts"
            )
        elif expectancy > 0 and profit_factor > 1.0:
            st.warning(
                f"**Edge marginal** — {winrate:.1%} WR, {expectancy:.1f} pts/trade, "
                f"PF {profit_factor:.2f}\n\n"
                f"Essaie: augmenter k (bande plus large) ou ajuster le lookback."
            )
        else:
            st.error(
                f"**Pas d'edge** — {winrate:.1%} WR, {expectancy:.1f} pts/trade, "
                f"PF {profit_factor:.2f}\n\n"
                f"Ajuste: k, lookback, ou parametres GARCH."
            )
    
    # ══════════════════════════════════════════════════════════════════
    # TAB 5 — MONTE CARLO CHALLENGE SIMULATOR
    # Ref : Quant Guild Lec 75 (Backtesting with Poker) + Lec 28 (Gambler's Ruin)
    # ══════════════════════════════════════════════════════════════════
    with tab5:
        st.markdown("<p class='section-title'>Monte Carlo — Probabilité de réussir le challenge Apex 50K EOD</p>",
                    unsafe_allow_html=True)
        st.caption(
            "Simule N fois un mois de challenge en tirant aléatoirement dans la distribution "
            "empirique des trades (bootstrap). Donne la vraie probabilité de passer, bust, ou échouer."
        )

        mc1, mc2, mc3 = st.columns(3)
        n_sims    = mc1.number_input("Simulations", value=10_000, min_value=1000, step=1000)
        trades_pm = mc2.number_input("Trades/mois estimés", value=max(1, int(n_total / max(1, n_bdays / 22))),
                                     min_value=1, step=1)
        mc_contracts = mc3.number_input("Contrats (MC)", value=int(fixed_contracts) if fixed_contracts > 0 else max(1, kc),
                                         min_value=1, max_value=max_contracts, step=1)

        if st.button("Lancer Monte Carlo", type="primary"):
            rng = np.random.default_rng(42)
            trade_results_pts = trades_df["result_pts"].values
            avg_sl_mc = trades_df["sl_pts"].mean()

            n_pass = 0; n_bust = 0; n_fail = 0
            final_pnls = []
            peak_dds   = []
            sim_paths  = []   # garder 200 paths pour le graphe

            for sim in range(int(n_sims)):
                equity   = capital_initial
                peak_eq  = capital_initial
                pnl_day  = {}   # date fictive → P&L (pour règle consistance)
                busted   = False
                passed   = False
                max_dd_sim = 0.0

                # Tirage avec remplacement (bootstrap)
                sampled = rng.choice(trade_results_pts, size=int(trades_pm), replace=True)
                sampled_days = rng.integers(0, 22, size=int(trades_pm))  # jour fictif 0-21

                day_pnl_arr = np.zeros(22)
                for r_pts, day in zip(sampled, sampled_days):
                    pnl = r_pts * DOLLAR_PER_PT * mc_contracts
                    # Daily loss limit
                    if day_pnl_arr[day] <= -daily_loss_limit:
                        continue
                    day_pnl_arr[day] += pnl
                    equity += pnl
                    if equity > peak_eq:
                        peak_eq = equity
                    dd = peak_eq - equity
                    if dd > max_dd_sim:
                        max_dd_sim = dd
                    # Bust : EOD threshold touché
                    if dd >= max_drawdown_dollars:
                        busted = True
                        break
                    # Objectif atteint
                    if equity - capital_initial >= APEX_50K["profit_target"]:
                        passed = True
                        break

                # Règle consistance 50% : aucun jour > 50% du profit total
                if passed and not busted:
                    total_profit = equity - capital_initial
                    best_day = day_pnl_arr.max()
                    if total_profit > 0 and best_day / total_profit > 0.50:
                        passed = False  # consistance violée

                if busted:
                    n_bust += 1
                elif passed:
                    n_pass += 1
                else:
                    n_fail += 1

                final_pnls.append(equity - capital_initial)
                peak_dds.append(max_dd_sim)
                if sim < 200:
                    # Path cumulatif simplifié
                    cum = np.concatenate([[0], np.cumsum(
                        [r * DOLLAR_PER_PT * mc_contracts for r in sampled]
                    )])
                    sim_paths.append(cum[:int(trades_pm)+1])

            pass_rate = n_pass / int(n_sims) * 100
            bust_rate = n_bust / int(n_sims) * 100
            fail_rate = n_fail / int(n_sims) * 100

            # Métriques
            mc_a, mc_b, mc_c, mc_d, mc_e = st.columns(5)
            color_pass = "normal" if pass_rate >= 50 else ("off" if pass_rate >= 30 else "inverse")
            mc_a.metric("Taux de réussite", f"{pass_rate:.1f}%",
                        delta=f"{'✓ cible atteinte' if pass_rate >= 50 else '✗ insuffisant'}",
                        delta_color=color_pass)
            mc_b.metric("Taux de bust", f"{bust_rate:.1f}%", delta_color="inverse")
            mc_c.metric("Taux d'échec", f"{fail_rate:.1f}%", delta_color="inverse")
            mc_d.metric("P&L médian / mois", f"${np.median(final_pnls):+,.0f}")
            mc_e.metric("DD max médian", f"${np.median(peak_dds):,.0f}")

            if pass_rate >= 70:
                st.success(f"**EDGE TRADABLE** — {pass_rate:.1f}% de chance de passer le challenge. "
                           f"Objectif 50-80% atteint.")
            elif pass_rate >= 50:
                st.warning(f"**EDGE MARGINAL** — {pass_rate:.1f}% de chance. "
                           f"Augmente les contrats ou baisse le tp_ratio.")
            else:
                st.error(f"**EDGE INSUFFISANT** — {pass_rate:.1f}% de chance. "
                         f"Distribution trop dispersée. Baisse tp_ratio ou augmente band_k.")

            # Graphe paths Monte Carlo
            st.markdown("<p class='section-title'>200 chemins simulés — P&L cumulatif</p>",
                        unsafe_allow_html=True)
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
            fig_mc.update_layout(height=400, yaxis_title="P&L ($)",
                                 xaxis_title="Trade #", **DARK)
            st.plotly_chart(fig_mc, use_container_width=True)

            # Distribution des P&L finaux
            st.markdown("<p class='section-title'>Distribution des P&L finaux (fin de mois)</p>",
                        unsafe_allow_html=True)
            fig_dist = go.Figure()
            fig_dist.add_trace(go.Histogram(
                x=final_pnls, nbinsx=60,
                marker_color=TEAL, opacity=0.8, name="P&L final"
            ))
            fig_dist.add_vline(x=APEX_50K["profit_target"], line_color=GREEN,
                               line_dash="dash", annotation_text="Target $3k")
            fig_dist.add_vline(x=0, line_color="white", opacity=0.3)
            fig_dist.add_vline(x=-max_drawdown_dollars, line_color=RED,
                               line_dash="dash", annotation_text="Bust")
            fig_dist.update_layout(height=300, xaxis_title="P&L ($)", **DARK)
            st.plotly_chart(fig_dist, use_container_width=True)

            # Table résumé
            st.markdown(f"""
<div class='result-block'>
<div class='result-row'><span class='result-key'>Simulations</span>
<span class='result-val'>{int(n_sims):,}</span></div>
<div class='result-row'><span class='result-key'>Trades/mois</span>
<span class='result-val'>{int(trades_pm)}</span></div>
<div class='result-row'><span class='result-key'>Contrats</span>
<span class='result-val'>{mc_contracts} MNQ</span></div>
<div class='result-row'><span class='result-key'>WR empirique</span>
<span class='result-val'>{winrate:.1%}</span></div>
<div class='result-row'><span class='result-key'>E[trade]</span>
<span class='result-val'>{expectancy:.1f} pts = ${expectancy * DOLLAR_PER_PT * mc_contracts:.0f}</span></div>
<div class='result-row'><span class='result-key'>Taux réussite</span>
<span class='result-val {"green" if pass_rate>=50 else "red"}'>{pass_rate:.1f}%</span></div>
<div class='result-row'><span class='result-key'>Taux bust</span>
<span class='result-val {"red" if bust_rate>10 else ""}'>{bust_rate:.1f}%</span></div>
</div>
""", unsafe_allow_html=True)