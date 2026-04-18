"""
Crypto Swing Backtest — QuantMaster
Multi-pair × Multi-model swing trading comparison
Sources:
  - HURST_MR : Quant Guild Library · Lec 25 (fBm) — Mandelbrot & Van Ness (1968) · Adapté stratégie live MNQ
  - TSMOM    : Moskowitz, Ooi & Pedersen (2012) — JFE, SSRN #2089471
  - HMM      : Quant Guild Library · Lec 51 (Hidden Markov Models)
  - GARCH    : Engle (1982) + arch lib documentation
  - RSI      : Wilder (1978) + EMA trend filter
  - STL      : Cleveland et al. (1990) · StockFormer arXiv 2401.06139
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import yfinance as yf
from datetime import datetime
import warnings
warnings.filterwarnings("ignore")

try:
    from arch import arch_model
    HAS_ARCH = True
except ImportError:
    HAS_ARCH = False

HAS_HMM = False
HAS_GMM = False
HMM_BACKEND = "EMA200-fallback"

try:
    from hmmlearn import hmm as hmmlib
    HAS_HMM = True
    HMM_BACKEND = "hmmlearn"
except ImportError:
    try:
        from sklearn.mixture import GaussianMixture
        HAS_GMM = True
        HMM_BACKEND = "sklearn-GMM"
    except ImportError:
        pass

try:
    from statsmodels.tsa.seasonal import STL
    HAS_STL = True
except ImportError:
    HAS_STL = False

from styles import inject as _inj; _inj()

# ── Palette B&W/Grey ─────────────────────────────────────────────────────────
C = dict(
    bg="#050505", paper="rgba(0,0,0,0)",
    primary="#e2e8f0", green="#d4d4d8", red="#6b7280",
    yellow="#9ca3af", orange="#9ca3af", blue="#d1d5db",
    purple="#9ca3af", text="#94a3b8", white="#f1f5f9",
)

DARK = dict(
    template="plotly_dark",
    paper_bgcolor=C["paper"], plot_bgcolor=C["bg"],
    font=dict(color=C["text"], size=11,
              family="'JetBrains Mono','Space Grotesk',monospace"),
    margin=dict(t=48, b=40, l=52, r=24),
    hoverlabel=dict(bgcolor="#0a0a0a", bordercolor="rgba(255,255,255,0.15)",
                    font=dict(size=12, family="JetBrains Mono", color=C["white"])),
)

MODEL_COLOR = {
    "HURST_MR":   "#ffffff",
    "TSMOM":      "#d1d5db",
    "EMA_CROSS":  "#9ca3af",
    "HMM_REGIME": "#6b7280",
    "GARCH_VOL":  "#e5e7eb",
    "RSI_SWING":  "#4b5563",
    "STL_TREND":  "#94a3b8",
}

# ── Constants ─────────────────────────────────────────────────────────────────
PAIRS = {
    "BTC · Bitcoin":     "BTC-USD",
    "ETH · Ethereum":    "ETH-USD",
    "SOL · Solana":      "SOL-USD",
    "BNB · BNB Chain":   "BNB-USD",
    "AVAX · Avalanche":  "AVAX-USD",
    "LINK · Chainlink":  "LINK-USD",
    "ADA · Cardano":     "ADA-USD",
    "XRP · Ripple":      "XRP-USD",
}

MODELS = {
    "HURST_MR":   "Hurst Mean-Reversion",
    "TSMOM":      "Time-Series Momentum",
    "EMA_CROSS":  "Dual EMA Cross",
    "HMM_REGIME": "HMM Bull/Bear",
    "GARCH_VOL":  "GARCH Vol Target",
    "RSI_SWING":  "RSI Swing",
    "STL_TREND":  "STL Decomposition",
}

MODEL_SRC = {
    "HURST_MR":
        "Quant Guild Library · Lec 25 (fBm) — Mandelbrot & Van Ness (1968) · Adapté stratégie live MNQ",
    "TSMOM":
        "Moskowitz, Ooi & Pedersen — Journal of Financial Economics 2012 · SSRN #2089471",
    "EMA_CROSS":
        "Quant Guild Library · github.com/romanmichaelpaolucci — trend-following notebooks",
    "HMM_REGIME":
        "Quant Guild Library · Lec 51 — Hidden Markov Models",
    "GARCH_VOL":
        "Quant Guild Library · GARCH notebooks · arch lib docs (documentation officielle)",
    "RSI_SWING":
        "Wilder (1978) — New Concepts in Technical Trading Systems",
    "STL_TREND":
        "Cleveland et al. (1990) — STL · StockFormer arXiv 2401.06139",
}

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.cs-tag {
    display: inline-block; padding: .25rem .9rem;
    border: 1px solid rgba(255,255,255,.2); border-radius: 999px;
    font-size: .68rem; letter-spacing: .18em; color: #9ca3af;
    font-family: 'JetBrains Mono', monospace; margin-bottom: .6rem;
}
.cs-title {
    font-size: 1.8rem; font-weight: 700; color: #f1f5f9;
    letter-spacing: -.02em; margin: 0;
}
.cs-title span {
    color: #ffffff;
}
.cs-sub { color: #444; font-size: .8rem; font-family: 'JetBrains Mono', monospace; margin-top: .3rem; }

.mcard {
    background: #060606; border: 1px solid #1a1a1a; border-radius: 10px;
    padding: .75rem 1rem; font-family: 'JetBrains Mono', monospace;
}
.mcard:hover { border-color: rgba(255,255,255,.15); }
.mname { color: #f1f5f9; font-weight: 700; font-size: .78rem; margin-bottom: .25rem; }
.msrc  { color: #3a3a3a; font-size: .65rem; line-height: 1.5; }

.mrow  { display: flex; gap: 1px; background: #111; border-radius: 10px;
         overflow: hidden; margin: .5rem 0; border: 1px solid #111; }
.mbox  { flex: 1; background: #060606; padding: .85rem .7rem; text-align: center; }
.mbox:hover { background: #0c0c0c; }
.mlbl  { font-size: .57rem; color: #444; text-transform: uppercase;
         letter-spacing: .15em; font-family: 'JetBrains Mono', monospace; }
.mval  { font-size: 1.2rem; font-weight: 700; font-family: 'JetBrains Mono', monospace;
         margin-top: .2rem; }
.c-green  { color: #d4d4d8; } .c-red    { color: #6b7280; }
.c-blue   { color: #d1d5db; } .c-purple { color: #9ca3af; }
.c-teal   { color: #e2e8f0; } .c-orange { color: #9ca3af; }
.c-gray   { color: #555; }

.badge-best {
    display: inline-block; padding: .2rem .7rem;
    background: rgba(255,255,255,.05); border: 1px solid rgba(255,255,255,.2);
    border-radius: 6px; color: #e2e8f0; font-size: .65rem;
    font-family: 'JetBrains Mono', monospace; font-weight: 700;
}
.wf-box {
    background: #060606; border-radius: 10px; padding: .9rem 1.1rem;
    font-family: 'JetBrains Mono', monospace; font-size: .8rem; line-height: 1.9;
}

.badge-hurst {
    display: inline-block; padding: .2rem .7rem;
    background: rgba(255,255,255,.04); border: 1px solid rgba(255,255,255,.25);
    border-radius: 6px; color: #ffffff;
    font-size: .65rem; font-family: 'JetBrains Mono', monospace; font-weight: 700;
}
.top5-row {
    background: #060606; border: 1px solid #1a1a1a; border-radius: 8px;
    padding: .6rem 1rem; margin: .3rem 0;
    font-family: 'JetBrains Mono', monospace;
}
.rank-1 { border-left: 3px solid #ffffff; }
.rank-2 { border-left: 3px solid #d1d5db; }
.rank-3 { border-left: 3px solid #9ca3af; }
.rank-4 { border-left: 3px solid #6b7280; }
.rank-5 { border-left: 3px solid #4b5563; }
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
# DATA
# ════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600, show_spinner=False)
def load_data(ticker: str, start: str, end: str) -> pd.DataFrame:
    df = yf.download(ticker, start=start, end=end, auto_adjust=True, progress=False)
    if df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    df.index = pd.to_datetime(df.index)
    return df


# ════════════════════════════════════════════════════════════════════════════
# SIGNALS
# ════════════════════════════════════════════════════════════════════════════

# ── HURST_MR — Flagship ──────────────────────────────────────────────────────

def _rs_hurst(series: np.ndarray) -> float:
    """R/S Analysis Hurst estimator — 3 lags fixes pour rapidité"""
    n = len(series)
    if n < 20:
        return 0.5
    lags = [max(4, n // 8), max(8, n // 4), max(16, n // 2)]
    rs_vals, lags_used = [], []
    for lag in lags:
        sub = series[:lag]
        S = sub.std(ddof=1)
        if S < 1e-10:
            continue
        dev = np.cumsum(sub - sub.mean())
        rs_vals.append((dev.max() - dev.min()) / S)
        lags_used.append(lag)
    if len(rs_vals) < 2:
        return 0.5
    H = np.polyfit(np.log(lags_used), np.log(rs_vals), 1)[0]
    return float(np.clip(H, 0.01, 0.99))


def signal_hurst_mr(close: pd.Series, window: int = 120,
                    hurst_thr: float = 0.53, z_entry: float = 2.0) -> pd.Series:
    """
    HURST_MR — Adapté de la stratégie live MNQ
    Régime   : H < hurst_thr → mean-reversion confirmé
    Long     : régime MR + Z < -z_entry (prix sous la moyenne)
    Short    : régime MR + Z > +z_entry (prix au-dessus)
    TP       : Z revient à 0 (fair value)
    SL impl. : H dépasse le seuil (changement de régime)
    """
    arr = np.log(close / close.shift(1)).fillna(0).values
    n   = len(arr)
    h_arr = np.full(n, np.nan)
    for i in range(window, n):
        h_arr[i] = _rs_hurst(arr[i - window:i])
    hurst = pd.Series(h_arr, index=close.index)

    roll_mean = close.rolling(window).mean()
    roll_std  = close.rolling(window).std()
    z_score   = (close - roll_mean) / (roll_std + 1e-10)

    positions = np.zeros(n)
    pos = 0.0
    for i in range(window, n):
        h = hurst.iloc[i]
        z = z_score.iloc[i]
        if np.isnan(h) or np.isnan(z):
            positions[i] = pos
            continue
        mr_on = h < hurst_thr
        if pos == 0.0:
            if mr_on and z < -z_entry:
                pos = 1.0
            elif mr_on and z > z_entry:
                pos = -1.0
        elif pos == 1.0:
            if z >= 0.0 or not mr_on:
                pos = 0.0
        elif pos == -1.0:
            if z <= 0.0 or not mr_on:
                pos = 0.0
        positions[i] = pos
    return pd.Series(positions, index=close.index).shift(1).fillna(0)


def compute_rolling_hurst(close: pd.Series, window: int = 120) -> pd.Series:
    arr = np.log(close / close.shift(1)).fillna(0).values
    n   = len(arr)
    result = np.full(n, np.nan)
    for i in range(window, n):
        result[i] = _rs_hurst(arr[i - window:i])
    return pd.Series(result, index=close.index)


# ── STL_TREND ────────────────────────────────────────────────────────────────

def signal_stl_trend(close: pd.Series, period: int = 7,
                     ema_filter: int = 0) -> pd.Series:
    """STL Decomposition — Cleveland et al. 1990
    ema_filter > 0 : confirme direction trend avec EMA(ema_filter)
    """
    if not HAS_STL or len(close) < period * 3:
        ema = close.ewm(span=max(period * 4, ema_filter or period * 4),
                        adjust=False).mean()
        return (close > ema).astype(float).shift(1).fillna(0)
    try:
        stl = STL(np.log(close), period=period, robust=True)
        res = stl.fit()
        trend = pd.Series(res.trend, index=close.index)
        sig = np.sign(trend.diff()).clip(0, 1)
        if ema_filter > 0:
            ema = close.ewm(span=ema_filter, adjust=False).mean()
            sig = sig * (close > ema).astype(float)
        return sig.shift(1).fillna(0)
    except Exception:
        ema = close.ewm(span=max(period * 4, ema_filter or period * 4),
                        adjust=False).mean()
        return (close > ema).astype(float).shift(1).fillna(0)


# ── TSMOM ─────────────────────────────────────────────────────────────────────

def signal_tsmom(close: pd.Series, lookback: int = 60,
                 target_vol: float = 0.40) -> pd.Series:
    """
    Time-Series Momentum — Moskowitz, Ooi & Pedersen (2012)
    Signal = sign(r_lookback) × vol-scaling toward target_vol
    """
    ret = close.pct_change()
    direction = np.sign(close.pct_change(lookback))
    rvol = ret.rolling(20).std() * np.sqrt(252)
    sizing = (target_vol / rvol.clip(lower=0.01)).clip(upper=2.0)
    return (direction * sizing).clip(-1, 1).shift(1).fillna(0)


def signal_ema_cross(close: pd.Series, fast: int = 10,
                     slow: int = 50) -> pd.Series:
    """Dual EMA Cross — long-only trend baseline"""
    ema_f = close.ewm(span=fast, adjust=False).mean()
    ema_s = close.ewm(span=slow, adjust=False).mean()
    return (ema_f > ema_s).astype(float).shift(1).fillna(0)


def signal_hmm_regime(close: pd.Series) -> pd.Series:
    """
    Gaussian Mixture / HMM 2-state Bull/Bear — Quant Guild Lec 51
    Backend priority: hmmlearn > sklearn GaussianMixture > EMA200 fallback
    """
    signal = pd.Series(0.0, index=close.index)
    ret = np.log(close / close.shift(1)).dropna().values.reshape(-1, 1)

    try:
        if HAS_HMM:
            model = hmmlib.GaussianHMM(n_components=2, covariance_type="full",
                                        n_iter=300, random_state=42)
            model.fit(ret)
            states = model.predict(ret)
        elif HAS_GMM:
            model = GaussianMixture(n_components=2, covariance_type="full",
                                    random_state=42, max_iter=300)
            model.fit(ret)
            states = model.predict(ret)
        else:
            raise RuntimeError("no backend")

        means = [ret[states == i].mean() for i in range(2)]
        bull = int(np.argmax(means))
        signal.iloc[1:] = (states == bull).astype(float)
    except Exception:
        ema200 = close.ewm(span=200, adjust=False).mean()
        signal = (close > ema200).astype(float)

    return signal.shift(1).fillna(0)


def signal_garch_vol_target(close: pd.Series, fast: int = 10,
                             slow: int = 50, target_vol: float = 0.40) -> pd.Series:
    """
    GARCH(1,1) Vol Targeting — Engle (1982)
    Direction from EMA cross, position sized by target_vol / σ_GARCH
    Fallback to rolling realized vol if arch absent
    """
    ret = close.pct_change()
    direction = (close.ewm(span=fast, adjust=False).mean() >
                 close.ewm(span=slow, adjust=False).mean()).astype(float)

    if HAS_ARCH:
        try:
            ret_pct = (ret.dropna() * 100)
            am = arch_model(ret_pct, vol="Garch", p=1, q=1, dist="normal")
            res = am.fit(disp="off", show_warning=False)
            cond_vol = (res.conditional_volatility / 100 * np.sqrt(252))
            cond_vol = cond_vol.reindex(close.index).ffill()
        except Exception:
            cond_vol = ret.rolling(20).std() * np.sqrt(252)
    else:
        cond_vol = ret.rolling(20).std() * np.sqrt(252)

    cond_vol = cond_vol.fillna(cond_vol.mean()).clip(lower=0.05)
    sizing = (target_vol / cond_vol).clip(upper=2.0)
    return (direction * sizing).clip(0, 1).shift(1).fillna(0)


def signal_rsi_swing(close: pd.Series, rsi_p: int = 14,
                     trend_p: int = 200, oversold: int = 35,
                     overbought: int = 65) -> pd.Series:
    """
    RSI Swing + Trend Filter
    Entry: RSI crosses up from oversold zone AND price > EMA(trend_p)
    Exit:  RSI reaches overbought zone
    """
    delta = close.diff()
    avg_gain = delta.clip(lower=0).ewm(
        alpha=1 / rsi_p, min_periods=rsi_p, adjust=False).mean()
    avg_loss = (-delta.clip(upper=0)).ewm(
        alpha=1 / rsi_p, min_periods=rsi_p, adjust=False).mean()
    rsi = 100 - 100 / (1 + avg_gain / avg_loss.replace(0, np.nan))
    trend = close.ewm(span=trend_p, adjust=False).mean()

    entry = (rsi > oversold) & (rsi.shift(1) <= oversold) & (close > trend)
    exit_ = rsi > overbought

    positions = np.zeros(len(close))
    pos = 0
    for i in range(len(close)):
        if pos == 0 and entry.iloc[i]:
            pos = 1
        elif pos == 1 and exit_.iloc[i]:
            pos = 0
        positions[i] = pos

    return pd.Series(positions, index=close.index).shift(1).fillna(0)


# ════════════════════════════════════════════════════════════════════════════
# BACKTEST ENGINE
# ════════════════════════════════════════════════════════════════════════════

def run_backtest(close: pd.Series, signal: pd.Series,
                 commission: float = 0.001,
                 capital: float = 10_000) -> tuple:
    ret = close.pct_change().fillna(0)
    sig = signal.reindex(close.index).fillna(0)
    pos_chg = sig.diff().abs().fillna(0)
    strat_ret = sig * ret - pos_chg * commission
    equity = (1 + strat_ret).cumprod() * capital
    equity.iloc[0] = capital
    return equity, strat_ret


def compute_metrics(equity: pd.Series, strat_ret: pd.Series,
                    signal: pd.Series, ppy: int = 252) -> dict:
    years    = max(len(equity) / ppy, 0.01)
    total    = equity.iloc[-1] / equity.iloc[0] - 1
    cagr     = (1 + total) ** (1 / years) - 1
    ann_vol  = strat_ret.std() * np.sqrt(ppy)
    sharpe   = strat_ret.mean() * ppy / (ann_vol + 1e-10)
    dd       = (equity - equity.cummax()) / equity.cummax()
    max_dd   = dd.min()
    calmar   = cagr / abs(max_dd + 1e-10)
    active   = strat_ret[signal > 0]
    win_rate = (active > 0).mean() if len(active) > 0 else 0.0
    pf       = (strat_ret[strat_ret > 0].sum() /
                abs(strat_ret[strat_ret < 0].sum() + 1e-10))
    n_trades = int((signal.round(2).diff().abs() > 0.1).sum())
    return dict(Sharpe=sharpe, CAGR=cagr, MaxDD=max_dd, Calmar=calmar,
                WinRate=win_rate, PF=pf, TotalRet=total,
                NTrades=n_trades, AnnVol=ann_vol)


def _bh(close, commission, capital):
    sig = pd.Series(1.0, index=close.index)
    sig.iloc[0] = 0.0
    eq, sr = run_backtest(close, sig, commission, capital)
    return compute_metrics(eq, sr, sig), eq


def extract_trades(close: pd.Series, signal: pd.Series,
                   capital: float, commission: float) -> pd.DataFrame:
    """Extrait chaque trade individuel : entrée, sortie, PnL réalisé, durée."""
    trades = []
    pos = 0.0
    entry_date = None
    entry_price = None
    running_equity = capital

    sig = signal.reindex(close.index).fillna(0)

    for i in range(len(sig)):
        s = float(sig.iloc[i])
        p = float(close.iloc[i])
        d = close.index[i]

        if pos == 0.0 and s != 0.0:
            pos = s
            entry_date = d
            entry_price = p

        elif pos != 0.0 and (s == 0.0 or s != pos):
            exit_price = p
            pnl_pct = (exit_price / entry_price - 1) * pos
            comm_cost = commission * 2
            pnl_pct_net = pnl_pct - comm_cost
            # PnL $ sur capital FIXE — position size constante, pas de compounding
            pnl_usd = pnl_pct_net * capital
            running_equity += pnl_usd
            duration = max(1, (d - entry_date).days)

            trades.append({
                "Entrée":       entry_date,
                "Sortie":       d,
                "Direction":    "Long" if pos > 0 else "Short",
                "Prix entrée":  round(entry_price, 4),
                "Prix sortie":  round(exit_price, 4),
                "PnL %":        round(pnl_pct_net * 100, 2),
                "PnL $":        round(pnl_usd, 2),
                "Equity après": round(running_equity, 2),
                "Durée (j)":    duration,
                "Win":          pnl_usd > 0,
            })

            if s != 0.0:
                pos = s
                entry_date = d
                entry_price = p
                equity_at_entry = running_equity
            else:
                pos = 0.0
                entry_date = None
                entry_price = None

    return pd.DataFrame(trades) if trades else pd.DataFrame()


# ════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("### ⚙️ Configuration")
    st.divider()

    sel_pair_names = st.multiselect(
        "Paires crypto",
        list(PAIRS.keys()),
        default=["BTC · Bitcoin", "ETH · Ethereum", "SOL · Solana"],
    )
    st.divider()

    sel_model_keys = st.multiselect(
        "Modèles",
        list(MODELS.keys()),
        default=list(MODELS.keys()),
        format_func=lambda x: MODELS[x],
    )
    st.divider()

    c1, c2 = st.columns(2)
    with c1:
        start_date = st.date_input("Début", datetime(2019, 1, 1))
    with c2:
        end_date = st.date_input("Fin", datetime(2024, 12, 31))

    capital    = st.number_input("Capital ($)", value=10_000, step=1_000)
    comm_pct   = st.slider("Commission (%)", 0.0, 0.5, 0.10, 0.05)
    commission = comm_pct / 100

    st.divider()

    with st.expander("⚡ HURST_MR params"):
        p_hw   = st.slider("Fenêtre Hurst", 60, 252, 120)
        p_hthr = st.slider("Seuil Hurst H <", 0.40, 0.60, 0.53, 0.01)
        p_ze   = st.slider("Z-score entrée (σ)", 1.0, 4.0, 2.0, 0.25)

    with st.expander("⚡ TSMOM params"):
        p_lb  = st.slider("Lookback (jours)", 20, 120, 60)
        p_vol = st.slider("Vol target", 0.20, 0.80, 0.40, 0.05)

    with st.expander("⚡ EMA / GARCH params"):
        p_ef = st.slider("EMA fast", 5, 30, 10)
        p_es = st.slider("EMA slow", 20, 100, 50)

    with st.expander("⚡ RSI Swing params"):
        p_rp = st.slider("RSI période", 7, 21, 14)
        p_os = st.slider("Survente", 20, 45, 35)
        p_ob = st.slider("Surachat", 55, 80, 65)

    with st.expander("⚡ STL params"):
        p_stl = st.slider("STL période", 5, 30, 7)

    run_btn = st.button("🚀 LANCER L'ANALYSE", type="primary",
                        use_container_width=True)
    if run_btn:
        st.session_state["_cs_run"] = True
        st.session_state.pop("_cs_results", None)
        st.session_state.pop("_cs_raw_data", None)


# ════════════════════════════════════════════════════════════════════════════
# HEADER
# ════════════════════════════════════════════════════════════════════════════

st.markdown("""
<div style="padding:1.2rem 0 .8rem;border-bottom:1px solid #111;margin-bottom:1.2rem">
    <div class="cs-tag">QUANTMASTER · CRYPTO SWING</div>
    <h1 class="cs-title">Multi-Model <span>Swing Backtest</span></h1>
    <p class="cs-sub">
        HURST_MR · TSMOM · EMA Cross · HMM Regime · GARCH Vol Target · RSI Swing · STL Trend
        &nbsp;·&nbsp; 8 paires · walk-forward 70/30 · daily data
    </p>
</div>
""", unsafe_allow_html=True)

# ── Model cards ───────────────────────────────────────────────────────────────
with st.expander("📚 Modèles & sources institutionnelles"):
    cols = st.columns(len(MODELS))
    for col, (key, name) in zip(cols, MODELS.items()):
        with col:
            if key == "HMM_REGIME":
                avail = f"<span class='c-green'>✓ {HMM_BACKEND}</span>"
            elif key == "GARCH_VOL":
                avail = "<span class='c-green'>✓ arch</span>" if HAS_ARCH \
                    else "<span class='c-orange'>⚡ fallback rolling vol</span>"
            elif key == "STL_TREND":
                avail = "<span class='c-green'>✓ statsmodels</span>" if HAS_STL \
                    else "<span class='c-orange'>⚡ fallback EMA</span>"
            elif key == "HURST_MR":
                avail = "<span class='c-green'>✓ R/S Analysis</span>"
            else:
                avail = "<span class='c-green'>✓ numpy/pandas</span>"

            st.markdown(f"""
            <div class="mcard" style="border-left:3px solid {MODEL_COLOR[key]}">
                <div class="mname">{name} &nbsp; {avail}</div>
                <div class="msrc">{MODEL_SRC[key]}</div>
            </div>
            """, unsafe_allow_html=True)

if not st.session_state.get("_cs_run", False):
    st.info(
        "👈 Sélectionne les paires et les modèles dans le panneau gauche, "
        "puis clique **LANCER L'ANALYSE**"
    )
    st.stop()

# ════════════════════════════════════════════════════════════════════════════
# COMPUTATION
# ════════════════════════════════════════════════════════════════════════════

if not sel_pair_names or not sel_model_keys:
    st.warning("Sélectionne au moins une paire et un modèle.")
    st.stop()

sel_pairs  = {k: PAIRS[k] for k in sel_pair_names}
start_s    = str(start_date)
end_s      = str(end_date)
total_jobs = len(sel_pairs) * len(sel_model_keys)
step       = 0

SIGNAL_FNS = {
    "HURST_MR":   lambda c: signal_hurst_mr(c, p_hw, p_hthr, p_ze),
    "TSMOM":      lambda c: signal_tsmom(c, p_lb, p_vol),
    "EMA_CROSS":  lambda c: signal_ema_cross(c, p_ef, p_es),
    "HMM_REGIME": lambda c: signal_hmm_regime(c),
    "GARCH_VOL":  lambda c: signal_garch_vol_target(c, p_ef, p_es, p_vol),
    "RSI_SWING":  lambda c: signal_rsi_swing(c, p_rp, 200, p_os, p_ob),
    "STL_TREND":  lambda c: signal_stl_trend(c, p_stl),
}

if "_cs_results" not in st.session_state:
    results: dict = {}
    raw_data: dict = {}
    progress = st.progress(0, "Initialisation...")

    for pair_name, ticker in sel_pairs.items():
        progress.progress(min(step / max(total_jobs, 1), 1.0),
                          f"📥 Téléchargement {ticker}...")
        df = load_data(ticker, start_s, end_s)

        if df.empty or len(df) < 200:
            st.warning(f"⚠️ Données insuffisantes pour {ticker} — ignoré")
            step += len(sel_model_keys)
            continue

        raw_data[pair_name] = df
        close = df["Close"].squeeze()

        bh_m, bh_eq = _bh(close, commission, capital)

        for mk in sel_model_keys:
            progress.progress(
                min(step / max(total_jobs, 1), 1.0),
                f"⚙️  {ticker} × {MODELS[mk]}..."
            )
            try:
                sig        = SIGNAL_FNS[mk](close)
                eq, sr     = run_backtest(close, sig, commission, capital)
                m          = compute_metrics(eq, sr, sig)
                results[(pair_name, mk)] = dict(
                    metrics=m, equity=eq, signal=sig, strat_ret=sr,
                    bh_metrics=bh_m, bh_equity=bh_eq, close=close,
                )
            except Exception as e:
                st.warning(f"⚠️ Erreur {ticker} × {mk}: {e}")
            step += 1

    progress.empty()
    st.session_state["_cs_results"]  = results
    st.session_state["_cs_raw_data"] = raw_data

results  = st.session_state.get("_cs_results", {})
raw_data = st.session_state.get("_cs_raw_data", {})

if not results:
    st.error("Aucun résultat — vérifie les paires sélectionnées et la connexion.")
    st.stop()


# ════════════════════════════════════════════════════════════════════════════
# DISPLAY
# ════════════════════════════════════════════════════════════════════════════

tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "🏆 Classement Top 5",
    "📈 Equity Curves",
    "🔬 Deep Dive",
    "🔮 HURST_MR Study",
    "⚙️ Optimisation 3D",
    "📊 Stats Complètes",
    "🌐 Live Ranking STL",
])


# ── TAB 1 — Classement Top 5 + Heatmaps + Tableau ───────────────────────────
with tab1:
    # ── Top 5 ranking ─────────────────────────────────────────────────────────
    ranked = sorted(results.items(), key=lambda x: x[1]["metrics"]["Sharpe"], reverse=True)
    medal = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    rank_border = ["rank-1", "rank-2", "rank-3", "rank-4", "rank-5"]

    st.markdown("### 🏆 Top 5 — Meilleures combos par Sharpe")
    for rank, ((pair, model), d) in enumerate(ranked[:5]):
        m_r = d["metrics"]
        bh_r = d["bh_metrics"]
        sharpe_vs = m_r["Sharpe"] - bh_r["Sharpe"]
        st.markdown(f"""<div class="top5-row {rank_border[rank]}">
            {medal[rank]} <strong style="color:#f1f5f9">{pair}</strong> &nbsp;×&nbsp;
            <strong style="color:{MODEL_COLOR[model]}">{MODELS[model]}</strong>
            <span style="float:right;color:#6b7280;font-size:.75rem">
                Sharpe <strong style="color:#e5e7eb">{m_r['Sharpe']:.2f}</strong>
                &nbsp;·&nbsp; CAGR <strong style="color:#d1d5db">{m_r['CAGR']*100:.1f}%</strong>
                &nbsp;·&nbsp; DD <strong style="color:#9ca3af">{m_r['MaxDD']*100:.1f}%</strong>
                &nbsp;·&nbsp; PF <strong style="color:#d1d5db">{m_r['PF']:.2f}</strong>
                &nbsp;·&nbsp; Sharpe Δ vs B&H
                <strong style="color:{'#d4d4d8' if sharpe_vs > 0 else '#6b7280'}">{sharpe_vs:+.2f}</strong>
            </span>
        </div>""", unsafe_allow_html=True)

    st.markdown("")

    # ── Heatmaps ──────────────────────────────────────────────────────────────
    pairs_l  = [p for p in sel_pairs if any(k[0] == p for k in results)]
    models_l = [m for m in sel_model_keys if any(k[1] == m for k in results)]

    if pairs_l and models_l:
        sharpe_mat = np.full((len(pairs_l), len(models_l)), np.nan)
        for i, p in enumerate(pairs_l):
            for j, m in enumerate(models_l):
                if (p, m) in results:
                    sharpe_mat[i, j] = results[(p, m)]["metrics"]["Sharpe"]

        fig_h = go.Figure(go.Heatmap(
            z=sharpe_mat,
            x=[MODELS[m] for m in models_l],
            y=pairs_l,
            colorscale=[[0, "#111"], [0.4, "#333"], [1, "#e5e7eb"]],
            zmid=0,
            text=np.round(sharpe_mat, 2),
            texttemplate="%{text}",
            textfont={"size": 15, "family": "JetBrains Mono", "color": "#f1f5f9"},
            colorbar=dict(
                title="Sharpe",
                titlefont=dict(color=C["text"]),
                tickfont=dict(color=C["text"]),
            ),
        ))
        fig_h.update_layout(
            **DARK,
            title="Sharpe Ratio — Heatmap Pair × Modèle",
            height=max(300, len(pairs_l) * 75 + 120),
        )
        st.plotly_chart(fig_h, use_container_width=True)

        cagr_mat = np.full((len(pairs_l), len(models_l)), np.nan)
        for i, p in enumerate(pairs_l):
            for j, m in enumerate(models_l):
                if (p, m) in results:
                    cagr_mat[i, j] = round(
                        results[(p, m)]["metrics"]["CAGR"] * 100, 1)

        fig_c = go.Figure(go.Heatmap(
            z=cagr_mat,
            x=[MODELS[m] for m in models_l],
            y=pairs_l,
            colorscale=[[0, "#111"], [0.4, "#333"], [1, "#e5e7eb"]],
            zmid=0,
            text=[[f"{v:.1f}%" if not np.isnan(v) else "" for v in row]
                  for row in cagr_mat],
            texttemplate="%{text}",
            textfont={"size": 13, "family": "JetBrains Mono", "color": "#f1f5f9"},
            showscale=True,
            colorbar=dict(
                title="CAGR %",
                titlefont=dict(color=C["text"]),
                tickfont=dict(color=C["text"]),
            ),
        ))
        fig_c.update_layout(
            **DARK,
            title="CAGR % — Heatmap Pair × Modèle",
            height=max(300, len(pairs_l) * 75 + 120),
        )
        st.plotly_chart(fig_c, use_container_width=True)

    # ── Full metrics table ────────────────────────────────────────────────────
    st.markdown("### 📋 Tableau métriques complet")
    rows = []
    for (pair, model), d in results.items():
        m  = d["metrics"]
        bh = d["bh_metrics"]
        rows.append({
            "Paire":       pair,
            "Modèle":      MODELS[model],
            "Sharpe":      round(m["Sharpe"], 2),
            "CAGR %":      round(m["CAGR"] * 100, 1),
            "Max DD %":    round(m["MaxDD"] * 100, 1),
            "Calmar":      round(m["Calmar"], 2),
            "Win Rate %":  round(m["WinRate"] * 100, 1),
            "PF":          round(m["PF"], 2),
            "# Trades":    m["NTrades"],
            "BH Sharpe":   round(bh["Sharpe"], 2),
            "BH DD %":     round(bh["MaxDD"] * 100, 1),
        })
    df_t = (pd.DataFrame(rows)
            .sort_values("Sharpe", ascending=False)
            .reset_index(drop=True))
    st.dataframe(df_t, use_container_width=True, hide_index=True)


# ── TAB 2 — Equity Curves ────────────────────────────────────────────────────
with tab2:
    for pair_name in sel_pairs:
        pair_res = {k: v for k, v in results.items() if k[0] == pair_name}
        if not pair_res:
            continue

        fig = go.Figure()
        first = list(pair_res.values())[0]
        bh_n = first["bh_equity"] / first["bh_equity"].iloc[0] * 100

        fig.add_trace(go.Scatter(
            x=bh_n.index, y=bh_n.values,
            name="Buy & Hold",
            line=dict(color=C["text"], width=1, dash="dot"),
            opacity=0.45,
        ))

        for (p, mk), d in pair_res.items():
            n = d["equity"] / d["equity"].iloc[0] * 100
            fig.add_trace(go.Scatter(
                x=n.index, y=n.values,
                name=f"{MODELS[mk]}",
                line=dict(color=MODEL_COLOR[mk], width=2),
            ))

        fig.update_layout(
            **DARK,
            title=f"{pair_name} — Equity normalisée (base 100)",
            height=430,
            yaxis_title="Equity (base 100)",
            legend=dict(bgcolor="rgba(0,0,0,.85)",
                        bordercolor="rgba(255,255,255,.1)", borderwidth=1,
                        font=dict(color=C["text"], size=11)),
        )
        st.plotly_chart(fig, use_container_width=True)


# ── TAB 3 — Deep Dive ────────────────────────────────────────────────────────
with tab3:
    combos     = [f"{p} × {MODELS[m]}" for (p, m) in results]
    sel_combo  = st.selectbox("Sélectionne une combo pour l'analyse détaillée", combos)

    if not sel_combo:
        st.stop()

    sp  = sel_combo.split(" × ")[0]
    smn = sel_combo.split(" × ")[1]
    sm  = next(k for k, v in MODELS.items() if v == smn)

    d = results.get((sp, sm))
    if not d:
        st.warning("Combo non trouvée.")
        st.stop()

    m    = d["metrics"]
    bh   = d["bh_metrics"]
    eq   = d["equity"]
    sr   = d["strat_ret"]
    sig  = d["signal"]
    close = d["close"]

    # ── Metrics bar ───────────────────────────────────────────────────────────
    def _mc(v, pos_good=True):
        if pos_good:
            return "c-green" if v > 0 else "c-red"
        return "c-green" if v < 0 else "c-red"

    dd_cls = "c-green" if abs(m["MaxDD"]) < 0.25 else \
             ("c-orange" if abs(m["MaxDD"]) < 0.50 else "c-red")

    st.markdown(f"""
    <div class="mrow">
        <div class="mbox">
            <div class="mlbl">Sharpe</div>
            <div class="mval {_mc(m['Sharpe'])}">{m['Sharpe']:.2f}</div>
        </div>
        <div class="mbox">
            <div class="mlbl">CAGR</div>
            <div class="mval c-blue">{m['CAGR']*100:.1f}%</div>
        </div>
        <div class="mbox">
            <div class="mlbl">Max DD</div>
            <div class="mval {dd_cls}">{m['MaxDD']*100:.1f}%</div>
        </div>
        <div class="mbox">
            <div class="mlbl">Calmar</div>
            <div class="mval c-purple">{m['Calmar']:.2f}</div>
        </div>
        <div class="mbox">
            <div class="mlbl">Win Rate</div>
            <div class="mval c-teal">{m['WinRate']*100:.1f}%</div>
        </div>
        <div class="mbox">
            <div class="mlbl">Profit Factor</div>
            <div class="mval c-orange">{m['PF']:.2f}</div>
        </div>
        <div class="mbox">
            <div class="mlbl"># Trades</div>
            <div class="mval c-gray">{m['NTrades']}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── vs Buy & Hold ─────────────────────────────────────────────────────────
    c1, c2, c3 = st.columns(3)
    deltas = [
        ("Sharpe Δ vs B&H",
         m["Sharpe"] - bh["Sharpe"],
         f"{m['Sharpe']:.2f} vs {bh['Sharpe']:.2f}",
         True),
        ("CAGR Δ vs B&H",
         (m["CAGR"] - bh["CAGR"]) * 100,
         f"{m['CAGR']*100:.1f}% vs {bh['CAGR']*100:.1f}%",
         True),
        ("DD réduit vs B&H",
         abs(bh["MaxDD"]) - abs(m["MaxDD"]),
         f"{m['MaxDD']*100:.1f}% vs {bh['MaxDD']*100:.1f}%",
         True),
    ]
    for col, (lbl, delta, txt, pg) in zip([c1, c2, c3], deltas):
        cls = "c-green" if (delta > 0) == pg else "c-red"
        col.markdown(f"""
        <div style="background:#060606;border:1px solid #1a1a1a;border-radius:8px;
             padding:.75rem;text-align:center;margin-bottom:.5rem">
            <div class="mlbl">{lbl}</div>
            <div class="mval {cls}">{txt}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("")

    # ── Walk-Forward 70/30 ────────────────────────────────────────────────────
    split  = int(len(eq) * 0.70)
    eq_is  = eq.iloc[:split];  sr_is  = sr.iloc[:split];  sig_is  = sig.iloc[:split]
    eq_oos = eq.iloc[split:];  sr_oos = sr.iloc[split:];  sig_oos = sig.iloc[split:]

    if len(eq_oos) > 30:
        m_is  = compute_metrics(eq_is,  sr_is,  sig_is)
        m_oos = compute_metrics(eq_oos, sr_oos, sig_oos)
        split_dt = eq.index[split].strftime("%Y-%m-%d")

        st.markdown("#### 📊 Walk-Forward Validation — 70% In-Sample / 30% Out-of-Sample")
        st.caption(f"Split : {split_dt}")

        ca, cb = st.columns(2)
        for col, (label, mm, clr) in zip([ca, cb], [
            ("In-Sample (70%)",    m_is,  C["blue"]),
            ("Out-of-Sample (30%)", m_oos, C["green"]),
        ]):
            dd_c = "#6b7280" if abs(mm["MaxDD"]) > 0.40 else "#9ca3af"
            col.markdown(f"""
            <div class="wf-box" style="border:1px solid {clr}33;border-left:3px solid {clr}">
                <span style="color:{clr};font-size:.7rem">{label}</span><br>
                Sharpe &nbsp;&nbsp;&nbsp;: <strong style="color:{clr}">{mm['Sharpe']:.2f}</strong><br>
                CAGR &nbsp;&nbsp;&nbsp;&nbsp;: <strong style="color:{clr}">{mm['CAGR']*100:.1f}%</strong><br>
                Max DD &nbsp;&nbsp;: <strong style="color:{dd_c}">{mm['MaxDD']*100:.1f}%</strong><br>
                Calmar &nbsp;&nbsp;: <strong style="color:{clr}">{mm['Calmar']:.2f}</strong><br>
                Win Rate : <strong style="color:{clr}">{mm['WinRate']*100:.1f}%</strong>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("")

    # ── Equity + Drawdown + Signal chart ─────────────────────────────────────
    dd_ser    = (eq - eq.cummax()) / eq.cummax() * 100
    bh_scaled = d["bh_equity"] / d["bh_equity"].iloc[0] * eq.iloc[0]

    fig2 = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        row_heights=[0.55, 0.25, 0.20],
        vertical_spacing=0.02,
    )

    fig2.add_trace(go.Scatter(
        x=bh_scaled.index, y=bh_scaled.values,
        name="Buy & Hold",
        line=dict(color=C["text"], width=1, dash="dot"),
        opacity=0.4,
    ), row=1, col=1)

    fig2.add_trace(go.Scatter(
        x=eq.index, y=eq.values,
        name=MODELS[sm],
        line=dict(color=MODEL_COLOR[sm], width=2),
    ), row=1, col=1)

    if split < len(eq):
        fig2.add_vline(
            x=eq.index[split],
            line=dict(color="rgba(255,255,255,0.12)", dash="dot", width=1),
        )

    fig2.add_trace(go.Scatter(
        x=dd_ser.index, y=dd_ser.values,
        name="Drawdown",
        line=dict(color=C["red"], width=1),
        fill="tozeroy",
        fillcolor="rgba(107,114,128,0.07)",
    ), row=2, col=1)

    fig2.add_trace(go.Bar(
        x=sig.index, y=sig.values,
        name="Signal",
        marker_color=MODEL_COLOR[sm],
        opacity=0.55,
    ), row=3, col=1)

    fig2.update_layout(
        **DARK,
        title=f"{sp} × {MODELS[sm]} — Equity · Drawdown · Signal",
        height=640,
        legend=dict(bgcolor="rgba(0,0,0,.85)",
                    bordercolor="rgba(255,255,255,.1)", borderwidth=1,
                    font=dict(color=C["text"], size=11)),
    )
    fig2.update_yaxes(title_text="Equity ($)", row=1, col=1,
                      title_font=dict(color=C["text"]))
    fig2.update_yaxes(title_text="DD %",       row=2, col=1,
                      title_font=dict(color=C["text"]))
    fig2.update_yaxes(title_text="Signal",     row=3, col=1,
                      title_font=dict(color=C["text"]))
    st.plotly_chart(fig2, use_container_width=True)

    # ── Monthly Returns Heatmap ───────────────────────────────────────────────
    monthly = eq.resample("ME").last().pct_change().dropna() * 100
    mdf = pd.DataFrame({
        "Y": monthly.index.year,
        "M": monthly.index.month,
        "R": monthly.values,
    })

    if len(mdf) > 12:
        piv = mdf.pivot_table(index="Y", columns="M", values="R")
        MONTHS = ["Jan", "Fév", "Mar", "Avr", "Mai", "Jun",
                  "Jul", "Aoû", "Sep", "Oct", "Nov", "Déc"]
        piv.columns = MONTHS[: len(piv.columns)]

        fig3 = go.Figure(go.Heatmap(
            z=piv.values,
            x=piv.columns.tolist(),
            y=piv.index.tolist(),
            colorscale=[[0, "#1a1a1a"], [0.5, "#3a3a3a"], [1, "#e5e7eb"]],
            zmid=0,
            text=np.round(piv.values, 1),
            texttemplate="%{text}%",
            textfont={"size": 9, "family": "JetBrains Mono"},
            showscale=True,
            colorbar=dict(title="%", titlefont=dict(color=C["text"]),
                          tickfont=dict(color=C["text"])),
        ))
        fig3.update_layout(
            **DARK,
            title="Rendements mensuels (%)",
            height=290,
        )
        st.plotly_chart(fig3, use_container_width=True)


# ── TAB 4 — HURST_MR Study ───────────────────────────────────────────────────
with tab4:
    st.markdown("""
    <div style="margin-bottom:1rem">
        <span class="badge-hurst">HURST_MR STUDY</span>
        &nbsp;
        <span style="color:#6b7280;font-size:.75rem;font-family:'JetBrains Mono',monospace">
            R/S Analysis · Mandelbrot &amp; Van Ness (1968) · Adapté stratégie live MNQ
        </span>
    </div>
    """, unsafe_allow_html=True)

    # Sélecteur paire
    available_pairs_h = [p for p in sel_pair_names if p in raw_data]
    if not available_pairs_h:
        st.warning("Lance d'abord l'analyse avec au moins une paire.")
        st.stop()

    col_h1, col_h2 = st.columns([2, 1])
    with col_h1:
        sel_pair_h = st.selectbox("Paire", available_pairs_h, key="hurst_pair")
    with col_h2:
        hw_study = st.slider("Fenêtre Hurst (study)", 60, 252, p_hw, key="hw_study")

    close_h = raw_data[sel_pair_h]["Close"].squeeze()

    _hurst_key = f"_hurst_{sel_pair_h}_{hw_study}"
    if _hurst_key not in st.session_state:
        with st.spinner("Calcul rolling Hurst R/S..."):
            st.session_state[_hurst_key] = compute_rolling_hurst(close_h, hw_study)
    hurst_series = st.session_state[_hurst_key]

    # Métriques stats Hurst
    h_valid = hurst_series.dropna()
    if len(h_valid) > 0:
        h_mean = h_valid.mean()
        pct_mr     = (h_valid < p_hthr).mean() * 100
        pct_trend  = (h_valid > 0.55).mean() * 100
        pct_neutral = 100 - pct_mr - pct_trend

        col_s1, col_s2, col_s3, col_s4 = st.columns(4)
        col_s1.metric("H moyen", f"{h_mean:.3f}")
        col_s2.metric("% Régime MR", f"{pct_mr:.1f}%", help=f"H < {p_hthr}")
        col_s3.metric("% Neutre", f"{pct_neutral:.1f}%", help="0.45 ≤ H ≤ 0.55")
        col_s4.metric("% Trend", f"{pct_trend:.1f}%", help="H > 0.55")

    st.markdown("")

    # ── CHART 1 : Rolling H(t) + Prix ──────────────────────────────────────
    fig_h1 = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        row_heights=[0.45, 0.55],
        vertical_spacing=0.03,
        subplot_titles=["Exposant H(t)", "Prix"],
    )

    # Hurst line
    fig_h1.add_trace(go.Scatter(
        x=hurst_series.index,
        y=hurst_series.values,
        name="H(t)",
        line=dict(color="#ffffff", width=1.5),
        showlegend=True,
    ), row=1, col=1)

    # Fill zone MR (H < seuil) — tozeroy style
    h_clipped = hurst_series.where(hurst_series < p_hthr, np.nan)
    fig_h1.add_trace(go.Scatter(
        x=h_clipped.index,
        y=h_clipped.values,
        name="Zone MR",
        fill="tozeroy",
        fillcolor="rgba(255,255,255,0.05)",
        line=dict(color="rgba(0,0,0,0)", width=0),
        showlegend=True,
    ), row=1, col=1)

    # Ligne seuil p_hthr (tiretée grise)
    fig_h1.add_hline(
        y=p_hthr,
        line=dict(color="#6b7280", dash="dash", width=1),
        annotation_text=f"Seuil H={p_hthr}",
        annotation_font_color="#6b7280",
        annotation_font_size=10,
        row=1, col=1,
    )

    # Ligne H=0.5 (poinçonnée grise)
    fig_h1.add_hline(
        y=0.5,
        line=dict(color="#3a3a3a", dash="dot", width=1),
        annotation_text="H=0.5 (random walk)",
        annotation_font_color="#3a3a3a",
        annotation_font_size=10,
        row=1, col=1,
    )

    # Prix row=2
    fig_h1.add_trace(go.Scatter(
        x=close_h.index,
        y=close_h.values,
        name="Prix",
        line=dict(color="#d1d5db", width=1.2),
        showlegend=True,
    ), row=2, col=1)

    # Zone MR surlignée sur le prix — scatter area (plus stable que vrect)
    mr_mask = (hurst_series < p_hthr).reindex(close_h.index).fillna(False)
    price_mr = close_h.where(mr_mask)
    fig_h1.add_trace(go.Scatter(
        x=close_h.index,
        y=price_mr.values,
        name="Prix (régime MR)",
        line=dict(color="rgba(255,255,255,0.0)", width=0),
        fill="tozeroy",
        fillcolor="rgba(255,255,255,0.06)",
        showlegend=True,
    ), row=2, col=1)

    fig_h1.update_layout(
        **DARK,
        title=f"{sel_pair_h} — Rolling Hurst H(t) & Prix",
        height=620,
        legend=dict(bgcolor="rgba(0,0,0,.85)",
                    bordercolor="rgba(255,255,255,.1)", borderwidth=1,
                    font=dict(color=C["text"], size=11)),
    )
    fig_h1.update_yaxes(title_text="H(t)", row=1, col=1,
                        title_font=dict(color=C["text"]),
                        range=[0, 1])
    fig_h1.update_yaxes(title_text="Prix ($)", row=2, col=1,
                        title_font=dict(color=C["text"]))
    st.plotly_chart(fig_h1, use_container_width=True)

    # ── CHART 2 : Scatter Z-score × Hurst ──────────────────────────────────
    roll_mean_h = close_h.rolling(hw_study).mean()
    roll_std_h  = close_h.rolling(hw_study).std()
    z_score_h   = (close_h - roll_mean_h) / (roll_std_h + 1e-10)

    mask_valid = hurst_series.notna() & z_score_h.notna()
    h_v  = hurst_series[mask_valid].values
    z_v  = z_score_h[mask_valid].values

    colors_scatter = np.where(
        h_v < p_hthr, "#ffffff",
        np.where(h_v > 0.55, "#2a2a2a", "#6b7280")
    )

    fig_scatter = go.Figure()
    fig_scatter.add_trace(go.Scatter(
        x=z_v,
        y=h_v,
        mode="markers",
        marker=dict(
            color=colors_scatter,
            size=3,
            opacity=0.6,
        ),
        name="Obs.",
        text=[f"Z={z:.2f} H={h:.3f}" for z, h in zip(z_v, h_v)],
        hovertemplate="%{text}<extra></extra>",
    ))

    # Lignes verticales Z-score entrée
    for z_line, label in [(-p_ze, f"Z={-p_ze:.1f} (long)"), (p_ze, f"Z={p_ze:.1f} (short)")]:
        fig_scatter.add_vline(
            x=z_line,
            line=dict(color="#9ca3af", dash="dash", width=1),
            annotation_text=label,
            annotation_font_color="#9ca3af",
            annotation_font_size=10,
        )

    # Ligne horizontale seuil Hurst
    fig_scatter.add_hline(
        y=p_hthr,
        line=dict(color="#6b7280", dash="dash", width=1),
        annotation_text=f"H seuil={p_hthr}",
        annotation_font_color="#6b7280",
        annotation_font_size=10,
    )

    # Annotations zones
    fig_scatter.add_annotation(
        x=-p_ze - 0.5, y=p_hthr / 2,
        text="LONG ZONE",
        font=dict(color="#d4d4d8", size=11, family="JetBrains Mono"),
        showarrow=False,
        bgcolor="rgba(0,0,0,0.5)",
    )
    fig_scatter.add_annotation(
        x=p_ze + 0.5, y=p_hthr / 2,
        text="SHORT ZONE",
        font=dict(color="#6b7280", size=11, family="JetBrains Mono"),
        showarrow=False,
        bgcolor="rgba(0,0,0,0.5)",
    )

    fig_scatter.update_layout(
        **DARK,
        title="Scatter Z-score × Exposant H — Map des régimes",
        height=500,
        xaxis_title="Z-score (écart à la moyenne)",
        yaxis_title="H(t) — Exposant Hurst",
        yaxis=dict(range=[0, 1]),
    )
    st.plotly_chart(fig_scatter, use_container_width=True)


# ── TAB 5 — Optimisation 3D ──────────────────────────────────────────────────
with tab5:
    st.markdown("""
    <div style="margin-bottom:1rem">
        <span class="badge-hurst">OPTIMISATION 3D</span>
        &nbsp;
        <span style="color:#6b7280;font-size:.75rem;font-family:'JetBrains Mono',monospace">
            Grid search N×N · Surface Sharpe · Top combos
        </span>
    </div>
    """, unsafe_allow_html=True)
    st.markdown(
        "Explore l'espace des paramètres sur une grille N×N. "
        "La surface Sharpe révèle les régions robustes vs les pics isolés (overfit)."
    )

    available_pairs_opt = [p for p in sel_pair_names if p in raw_data]
    if not available_pairs_opt:
        st.warning("Lance d'abord l'analyse avec au moins une paire.")
        st.stop()

    col_o1, col_o2, col_o3 = st.columns([2, 2, 1])
    with col_o1:
        sel_pair_opt = st.selectbox("Paire", available_pairs_opt, key="opt_pair")
    with col_o2:
        sel_model_opt = st.selectbox(
            "Modèle",
            ["STL_TREND", "HURST_MR", "TSMOM", "RSI_SWING"],
            format_func=lambda x: MODELS[x],
            key="opt_model",
        )
    with col_o3:
        n_grid = st.slider("Résolution N×N", 5, 15, 8, key="opt_n")

    close_opt = raw_data[sel_pair_opt]["Close"].squeeze()

    # Paramètres selon modèle
    if sel_model_opt == "STL_TREND":
        x_label = "STL période (saisonnalité)"
        y_label = "EMA trend (filtre)"
        col_x1, col_x2, col_y1, col_y2 = st.columns(4)
        with col_x1:
            x_min = st.number_input("Période min", value=5, step=1, key="sx_min")
        with col_x2:
            x_max = st.number_input("Période max", value=30, step=1, key="sx_max")
        with col_y1:
            y_min = st.number_input("EMA min", value=10, step=5, key="sy_min")
        with col_y2:
            y_max = st.number_input("EMA max", value=100, step=5, key="sy_max")

    elif sel_model_opt == "HURST_MR":
        x_label = "Seuil Hurst H <"
        y_label = "Z-score entrée (σ)"
        col_x1, col_x2, col_y1, col_y2 = st.columns(4)
        with col_x1:
            x_min = st.number_input("H min", value=0.40, step=0.01, format="%.2f", key="hx_min")
        with col_x2:
            x_max = st.number_input("H max", value=0.65, step=0.01, format="%.2f", key="hx_max")
        with col_y1:
            y_min = st.number_input("Z min", value=1.0, step=0.25, format="%.2f", key="hy_min")
        with col_y2:
            y_max = st.number_input("Z max", value=4.0, step=0.25, format="%.2f", key="hy_max")

    elif sel_model_opt == "TSMOM":
        x_label = "Lookback (jours)"
        y_label = "Vol Target"
        col_x1, col_x2, col_y1, col_y2 = st.columns(4)
        with col_x1:
            x_min = st.number_input("Lookback min", value=20, step=5, key="tx_min")
        with col_x2:
            x_max = st.number_input("Lookback max", value=120, step=5, key="tx_max")
        with col_y1:
            y_min = st.number_input("Vol min", value=0.15, step=0.05, format="%.2f", key="ty_min")
        with col_y2:
            y_max = st.number_input("Vol max", value=0.80, step=0.05, format="%.2f", key="ty_max")

    else:  # RSI_SWING
        x_label = "RSI période"
        y_label = "Seuil survente"
        col_x1, col_x2, col_y1, col_y2 = st.columns(4)
        with col_x1:
            x_min = st.number_input("RSI min", value=5, step=1, key="rx_min")
        with col_x2:
            x_max = st.number_input("RSI max", value=25, step=1, key="rx_max")
        with col_y1:
            y_min = st.number_input("Survente min", value=20, step=5, key="ry_min")
        with col_y2:
            y_max = st.number_input("Survente max", value=50, step=5, key="ry_max")

    opt_btn = st.button("🔬 Lancer Optimisation", type="primary",
                        use_container_width=True, key="opt_btn")

    if opt_btn:
        # Génération grille
        if sel_model_opt == "STL_TREND":
            x_vals = np.linspace(int(x_min), int(x_max), n_grid, dtype=float)
            y_vals = np.linspace(int(y_min), int(y_max), n_grid, dtype=float)
        elif sel_model_opt == "HURST_MR":
            x_vals = np.linspace(float(x_min), float(x_max), n_grid)
            y_vals = np.linspace(float(y_min), float(y_max), n_grid)
        elif sel_model_opt == "TSMOM":
            x_vals = np.linspace(int(x_min), int(x_max), n_grid, dtype=float)
            y_vals = np.linspace(float(y_min), float(y_max), n_grid)
        else:
            x_vals = np.linspace(int(x_min), int(x_max), n_grid, dtype=float)
            y_vals = np.linspace(int(y_min), int(y_max), n_grid, dtype=float)

        total_combos = n_grid * n_grid
        sharpe_grid = np.full((n_grid, n_grid), np.nan)
        opt_progress = st.progress(0, "Optimisation en cours...")
        combo_results = []

        for i, xv in enumerate(x_vals):
            for j, yv in enumerate(y_vals):
                try:
                    if sel_model_opt == "STL_TREND":
                        sig_opt = signal_stl_trend(close_opt, int(xv), int(yv))
                    elif sel_model_opt == "HURST_MR":
                        sig_opt = signal_hurst_mr(close_opt, p_hw, float(xv), float(yv))
                    elif sel_model_opt == "TSMOM":
                        sig_opt = signal_tsmom(close_opt, int(xv), float(yv))
                    else:
                        sig_opt = signal_rsi_swing(close_opt, int(xv), 200, int(yv), p_ob)

                    eq_opt, sr_opt = run_backtest(close_opt, sig_opt, commission, capital)
                    m_opt = compute_metrics(eq_opt, sr_opt, sig_opt)
                    sharpe_grid[i, j] = m_opt["Sharpe"]
                    combo_results.append({
                        x_label: round(float(xv), 3),
                        y_label: round(float(yv), 3),
                        "Sharpe": round(m_opt["Sharpe"], 3),
                        "CAGR %": round(m_opt["CAGR"] * 100, 1),
                        "MaxDD %": round(m_opt["MaxDD"] * 100, 1),
                        "NTrades": m_opt["NTrades"],
                    })
                except Exception:
                    pass
                opt_progress.progress(
                    min((i * n_grid + j + 1) / total_combos, 1.0),
                    f"Combo {i*n_grid+j+1}/{total_combos}..."
                )

        opt_progress.empty()

        # ── Surface 3D ──────────────────────────────────────────────────────
        fig_3d = go.Figure(go.Surface(
            x=x_vals,
            y=y_vals,
            z=sharpe_grid,
            colorscale=[
                [0.0, "#050505"],
                [0.3, "#1a1a1a"],
                [0.6, "#6b7280"],
                [0.8, "#d1d5db"],
                [1.0, "#ffffff"],
            ],
            contours=dict(z=dict(show=True, usecolormap=True, project_z=True)),
            opacity=0.92,
        ))
        fig_3d.update_layout(
            **DARK,
            height=600,
            title=f"{sel_pair_opt} × {MODELS[sel_model_opt]} — Surface Sharpe {n_grid}×{n_grid}",
            scene=dict(
                xaxis=dict(
                    title=x_label,
                    backgroundcolor="#050505",
                    gridcolor="#1a1a1a",
                    showbackground=True,
                ),
                yaxis=dict(
                    title=y_label,
                    backgroundcolor="#050505",
                    gridcolor="#1a1a1a",
                    showbackground=True,
                ),
                zaxis=dict(
                    title="Sharpe",
                    backgroundcolor="#050505",
                    gridcolor="#1a1a1a",
                    showbackground=True,
                ),
                bgcolor="#050505",
            ),
        )
        st.plotly_chart(fig_3d, use_container_width=True)

        # ── Heatmap 2D ──────────────────────────────────────────────────────
        fig_2d = go.Figure(go.Heatmap(
            z=sharpe_grid,
            x=np.round(y_vals, 3),
            y=np.round(x_vals, 3),
            colorscale=[[0, "#111"], [0.4, "#333"], [1, "#e5e7eb"]],
            text=np.round(sharpe_grid, 2),
            texttemplate="%{text}",
            textfont={"size": 10, "family": "JetBrains Mono", "color": "#f1f5f9"},
            colorbar=dict(
                title="Sharpe",
                titlefont=dict(color=C["text"]),
                tickfont=dict(color=C["text"]),
            ),
        ))
        fig_2d.update_layout(
            **DARK,
            title=f"Heatmap 2D — Sharpe {x_label} × {y_label}",
            height=450,
            xaxis_title=y_label,
            yaxis_title=x_label,
        )
        st.plotly_chart(fig_2d, use_container_width=True)

        # ── Top 5 combos ────────────────────────────────────────────────────
        if combo_results:
            df_opt = pd.DataFrame(combo_results).sort_values("Sharpe", ascending=False)
            st.markdown("### 🏆 Top 5 — Meilleures combinaisons")
            for rank_o, (_, row_o) in enumerate(df_opt.head(5).iterrows()):
                rank_border_o = ["rank-1", "rank-2", "rank-3", "rank-4", "rank-5"][rank_o]
                medal_o = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"][rank_o]
                st.markdown(f"""<div class="top5-row {rank_border_o}">
                    {medal_o}
                    <strong style="color:#e5e7eb">{x_label}={row_o[x_label]}</strong>
                    &nbsp;·&nbsp;
                    <strong style="color:#d1d5db">{y_label}={row_o[y_label]}</strong>
                    <span style="float:right;color:#6b7280;font-size:.75rem">
                        Sharpe <strong style="color:#e5e7eb">{row_o['Sharpe']:.3f}</strong>
                        &nbsp;·&nbsp; CAGR <strong style="color:#d1d5db">{row_o['CAGR %']:.1f}%</strong>
                        &nbsp;·&nbsp; DD <strong style="color:#9ca3af">{row_o['MaxDD %']:.1f}%</strong>
                        &nbsp;·&nbsp; Trades <strong style="color:#6b7280">{row_o['NTrades']}</strong>
                    </span>
                </div>""", unsafe_allow_html=True)

            # Tableau complet
            st.markdown("### 📋 Toutes les combinaisons")
            st.dataframe(df_opt.reset_index(drop=True), use_container_width=True, hide_index=True)


# ── TAB 6 — STATS COMPLÈTES ──────────────────────────────────────────────────
with tab6:
    st.markdown("""
    <h3 style="color:#f1f5f9;margin-bottom:.3rem">📊 Stats Complètes — Trade Log & PnL Réalisé</h3>
    <p style="color:#555;font-family:'JetBrains Mono',monospace;font-size:.78rem">
        Chaque trade individuel · PnL réalisé · Distribution · Monthly · Drawdown
    </p>
    """, unsafe_allow_html=True)

    combos6 = [f"{p} × {MODELS[m]}" for (p, m) in results]
    sel6 = st.selectbox("Combo à analyser", combos6, key="stats_combo")

    if sel6:
        sp6  = sel6.split(" × ")[0]
        smn6 = sel6.split(" × ")[1]
        sm6  = next(k for k, v in MODELS.items() if v == smn6)
        d6   = results.get((sp6, sm6))

    if not sel6 or not d6:
        st.info("Sélectionne une combo.")
        st.stop()

    eq6   = d6["equity"]
    sr6   = d6["strat_ret"]
    sig6  = d6["signal"]
    cl6   = d6["close"]
    m6    = d6["metrics"]
    bh6   = d6["bh_metrics"]

    # ── Extraction trades ─────────────────────────────────────────────────────
    df_trades = extract_trades(cl6, sig6, capital, commission)

    # ── Métriques résumé ─────────────────────────────────────────────────────
    if len(df_trades) > 0:
        wins      = df_trades[df_trades["Win"]]
        losses    = df_trades[~df_trades["Win"]]
        avg_win   = wins["PnL $"].mean() if len(wins) > 0 else 0
        avg_loss  = losses["PnL $"].mean() if len(losses) > 0 else 0
        best      = df_trades["PnL $"].max()
        worst     = df_trades["PnL $"].min()
        avg_dur   = df_trades["Durée (j)"].mean()
        total_pnl = df_trades["PnL $"].sum()

        consec_w = consec_l = cur_w = cur_l = max_w = max_l = 0
        for w in df_trades["Win"]:
            if w:
                cur_w += 1; cur_l = 0; max_w = max(max_w, cur_w)
            else:
                cur_l += 1; cur_w = 0; max_l = max(max_l, cur_l)

        st.markdown(f"""
        <div class="mrow">
            <div class="mbox"><div class="mlbl">PnL total réalisé</div>
                <div class="mval {'c-white' if total_pnl>0 else 'c-red'}">${total_pnl:,.0f}</div></div>
            <div class="mbox"><div class="mlbl">Nb trades</div>
                <div class="mval c-gray">{len(df_trades)}</div></div>
            <div class="mbox"><div class="mlbl">Win Rate</div>
                <div class="mval c-white">{len(wins)/len(df_trades)*100:.1f}%</div></div>
            <div class="mbox"><div class="mlbl">Avg Win $</div>
                <div class="mval c-white">${avg_win:,.0f}</div></div>
            <div class="mbox"><div class="mlbl">Avg Loss $</div>
                <div class="mval c-red">${avg_loss:,.0f}</div></div>
            <div class="mbox"><div class="mlbl">Best Trade</div>
                <div class="mval c-white">${best:,.0f}</div></div>
            <div class="mbox"><div class="mlbl">Worst Trade</div>
                <div class="mval c-red">${worst:,.0f}</div></div>
            <div class="mbox"><div class="mlbl">Avg Durée</div>
                <div class="mval c-gray">{avg_dur:.1f}j</div></div>
        </div>
        <div class="mrow">
            <div class="mbox"><div class="mlbl">Max DD</div>
                <div class="mval c-red">{m6['MaxDD']*100:.1f}%</div></div>
            <div class="mbox"><div class="mlbl">Sharpe</div>
                <div class="mval c-white">{m6['Sharpe']:.2f}</div></div>
            <div class="mbox"><div class="mlbl">CAGR</div>
                <div class="mval c-blue">{m6['CAGR']*100:.1f}%</div></div>
            <div class="mbox"><div class="mlbl">Profit Factor</div>
                <div class="mval c-white">{m6['PF']:.2f}</div></div>
            <div class="mbox"><div class="mlbl">Calmar</div>
                <div class="mval c-purple">{m6['Calmar']:.2f}</div></div>
            <div class="mbox"><div class="mlbl">Max wins consec.</div>
                <div class="mval c-white">{max_w}</div></div>
            <div class="mbox"><div class="mlbl">Max losses consec.</div>
                <div class="mval c-red">{max_l}</div></div>
            <div class="mbox"><div class="mlbl">Ratio W/L</div>
                <div class="mval c-gray">{abs(avg_win/(avg_loss+1e-10)):.2f}x</div></div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("")

        # ── PnL cumulé par trade ──────────────────────────────────────────────
        df_trades["PnL cumulé $"] = df_trades["PnL $"].cumsum() + capital
        colors_bar = ["#e5e7eb" if w else "#4b5563" for w in df_trades["Win"]]

        fig_pnl = make_subplots(rows=2, cols=1, shared_xaxes=False,
                                 row_heights=[0.55, 0.45], vertical_spacing=0.08)

        fig_pnl.add_trace(go.Scatter(
            x=list(range(1, len(df_trades)+1)),
            y=df_trades["PnL cumulé $"].values,
            name="Equity cumulée",
            line=dict(color="#ffffff", width=2),
            fill="tozeroy", fillcolor="rgba(255,255,255,0.03)",
        ), row=1, col=1)
        fig_pnl.add_hline(y=capital, line=dict(color="#4b5563", dash="dot", width=1), row=1, col=1)

        fig_pnl.add_trace(go.Bar(
            x=list(range(1, len(df_trades)+1)),
            y=df_trades["PnL $"].values,
            name="PnL par trade",
            marker_color=colors_bar,
            opacity=0.85,
        ), row=2, col=1)
        fig_pnl.add_hline(y=0, line=dict(color="#4b5563", dash="dot", width=1), row=2, col=1)

        fig_pnl.update_layout(**DARK, title=f"{sp6} × {smn6} — PnL réalisé par trade",
                               height=580)
        fig_pnl.update_xaxes(title_text="N° trade", row=2, col=1)
        fig_pnl.update_yaxes(title_text="Equity ($)", row=1, col=1)
        fig_pnl.update_yaxes(title_text="PnL $ par trade", row=2, col=1)
        st.plotly_chart(fig_pnl, use_container_width=True)

        # ── Distribution PnL + Drawdown ───────────────────────────────────────
        gc1, gc2 = st.columns(2)

        with gc1:
            fig_dist = go.Figure()
            fig_dist.add_trace(go.Histogram(
                x=df_trades["PnL $"].values,
                nbinsx=30,
                name="Distribution PnL",
                marker_color=["#e5e7eb" if x > 0 else "#4b5563"
                              for x in df_trades["PnL $"].values],
                opacity=0.85,
            ))
            fig_dist.add_vline(x=0, line=dict(color="#9ca3af", dash="dash", width=1))
            fig_dist.add_vline(x=avg_win, line=dict(color="#ffffff", dash="dot", width=1),
                               annotation_text=f"Avg win ${avg_win:.0f}",
                               annotation_font_color="#ffffff", annotation_font_size=9)
            fig_dist.add_vline(x=avg_loss, line=dict(color="#6b7280", dash="dot", width=1),
                               annotation_text=f"Avg loss ${avg_loss:.0f}",
                               annotation_font_color="#6b7280", annotation_font_size=9)
            fig_dist.update_layout(**DARK, title="Distribution PnL par trade ($)",
                                   height=320, xaxis_title="PnL $", yaxis_title="Fréquence")
            st.plotly_chart(fig_dist, use_container_width=True)

        with gc2:
            dd6 = (eq6 - eq6.cummax()) / eq6.cummax() * 100
            fig_dd = go.Figure()
            fig_dd.add_trace(go.Scatter(
                x=dd6.index, y=dd6.values,
                name="Drawdown",
                line=dict(color="#6b7280", width=1),
                fill="tozeroy", fillcolor="rgba(107,114,128,0.08)",
            ))
            fig_dd.add_hline(y=dd6.min(), line=dict(color="#4b5563", dash="dash", width=1),
                             annotation_text=f"Max DD {dd6.min():.1f}%",
                             annotation_font_color="#9ca3af", annotation_font_size=9)
            fig_dd.update_layout(**DARK, title="Drawdown timeline (%)", height=320,
                                 yaxis_title="DD %")
            st.plotly_chart(fig_dd, use_container_width=True)

        # ── PnL mensuel ──────────────────────────────────────────────────────
        monthly6 = eq6.resample("ME").last().pct_change().dropna() * 100
        colors_m  = ["#e5e7eb" if v > 0 else "#4b5563" for v in monthly6.values]
        fig_mo = go.Figure(go.Bar(
            x=monthly6.index, y=monthly6.values,
            marker_color=colors_m, opacity=0.85, name="Rendement mensuel",
        ))
        fig_mo.add_hline(y=0, line=dict(color="#4b5563", dash="dot", width=1))
        fig_mo.update_layout(**DARK, title="PnL mensuel (%)", height=300,
                             yaxis_title="%", xaxis_title="Mois")
        st.plotly_chart(fig_mo, use_container_width=True)

        # ── Durée des trades ─────────────────────────────────────────────────
        gd1, gd2 = st.columns(2)
        with gd1:
            fig_dur = go.Figure(go.Histogram(
                x=df_trades["Durée (j)"].values, nbinsx=20,
                marker_color="#9ca3af", opacity=0.8, name="Durée",
            ))
            fig_dur.add_vline(x=avg_dur, line=dict(color="#ffffff", dash="dash", width=1),
                              annotation_text=f"Moy {avg_dur:.1f}j",
                              annotation_font_color="#ffffff", annotation_font_size=9)
            fig_dur.update_layout(**DARK, title="Distribution durée des trades (jours)",
                                  height=280, xaxis_title="Jours", yaxis_title="Fréquence")
            st.plotly_chart(fig_dur, use_container_width=True)

        with gd2:
            # Win rate par année
            df_trades["Année"] = pd.to_datetime(df_trades["Entrée"]).dt.year
            wr_year = df_trades.groupby("Année")["Win"].mean() * 100
            fig_wr = go.Figure(go.Bar(
                x=wr_year.index.astype(str), y=wr_year.values,
                marker_color=["#e5e7eb" if v > 50 else "#6b7280" for v in wr_year.values],
                opacity=0.85, name="Win Rate %",
            ))
            fig_wr.add_hline(y=50, line=dict(color="#4b5563", dash="dot", width=1))
            fig_wr.update_layout(**DARK, title="Win Rate par année (%)",
                                 height=280, yaxis_title="%", xaxis_title="Année")
            st.plotly_chart(fig_wr, use_container_width=True)

        # ── Trade log complet ─────────────────────────────────────────────────
        st.markdown("### 📋 Trade Log complet — PnL réalisé")
        df_show = df_trades.copy()
        df_show["Entrée"] = df_show["Entrée"].dt.strftime("%Y-%m-%d")
        df_show["Sortie"] = df_show["Sortie"].dt.strftime("%Y-%m-%d")
        df_show["Win"] = df_show["Win"].map({True: "✓", False: "✗"})
        st.dataframe(df_show.reset_index(drop=True), use_container_width=True, hide_index=True)

    else:
        st.info("Aucun trade extrait — vérifie le signal.")

# ════════════════════════════════════════════════════════════════════════════
# TAB 7 — LIVE RANKING STL (multi-crypto, signal actuel)
# ════════════════════════════════════════════════════════════════════════════
with tab7:
    st.markdown(
        '<div style="color:#444;font-size:.72rem;font-family:JetBrains Mono,monospace;'
        'letter-spacing:.1em;text-transform:uppercase;margin-bottom:.8rem;">'
        'Classement live — STL Decomposition · période=5 · EMA=10 · signal daily</div>',
        unsafe_allow_html=True
    )

    LIVE_PAIRS = {
        "SOL":  "SOLUSDT",
        "BTC":  "BTCUSDT",
        "ETH":  "ETHUSDT",
        "BNB":  "BNBUSDT",
        "AVAX": "AVAXUSDT",
        "LINK": "LINKUSDT",
        "ADA":  "ADAUSDT",
        "XRP":  "XRPUSDT",
    }
    STL_P_LIVE = 5
    EMA_F_LIVE = 10

    @st.cache_data(ttl=3600, show_spinner=False)
    def _fetch_binance(symbol: str, limit: int = 365) -> pd.Series:
        try:
            url = "https://api.binance.com/api/v3/klines"
            r = requests.get(url, params={"symbol": symbol, "interval": "1d",
                                          "limit": limit}, timeout=10)
            r.raise_for_status()
            raw = r.json()
            closes = [float(x[4]) for x in raw]
            dates  = pd.to_datetime([x[0] for x in raw], unit="ms").normalize()
            return pd.Series(closes, index=dates, name=symbol)
        except Exception:
            return pd.Series(dtype=float)

    def _stl_signal_live(close: pd.Series) -> tuple:
        try:
            from statsmodels.tsa.seasonal import STL as _STL
            res  = _STL(np.log(close.values.astype(float)),
                        period=STL_P_LIVE, robust=True).fit()
            trend = pd.Series(res.trend, index=close.index)
            ema   = close.ewm(span=EMA_F_LIVE, adjust=False).mean()
            sig   = np.sign(trend.diff()).clip(0, 1) * (close > ema).astype(float)
            sig   = sig.shift(1).fillna(0)
            rets  = close.pct_change().fillna(0)
            s_rets = sig * rets - 0.001 * sig.diff().abs().fillna(0)
            sharpe = (s_rets.mean() / s_rets.std() * np.sqrt(365)
                      if s_rets.std() > 1e-9 else 0.0)
            total_ret = float((1 + s_rets).prod() - 1) * 100
            current_sig = float(sig.iloc[-1])
            current_px  = float(close.iloc[-1])
            chg_24h     = float(close.pct_change().iloc[-1]) * 100
            return current_sig, current_px, chg_24h, round(sharpe, 2), round(total_ret, 1)
        except Exception:
            return 0.0, 0.0, 0.0, 0.0, 0.0

    if st.button("⚡ Actualiser le ranking", key="lr_refresh"):
        st.cache_data.clear()

    with st.spinner("Chargement données Binance…"):
        ranking = []
        for name, sym in LIVE_PAIRS.items():
            cl = _fetch_binance(sym)
            if len(cl) < 30:
                continue
            sig, px, chg, sh, ret = _stl_signal_live(cl)
            ranking.append({
                "Crypto":    name,
                "Prix":      px,
                "24h %":     chg,
                "Signal":    "🟢 LONG" if sig > 0 else "⬜ FLAT",
                "_sig":      sig,
                "Sharpe":    sh,
                "Return %":  ret,
            })

    ranking.sort(key=lambda x: (x["_sig"], x["Sharpe"]), reverse=True)

    # ── Tableau ranking ──
    for i, row in enumerate(ranking):
        sig_color = "#e5e7eb" if row["_sig"] > 0 else "#4b5563"
        chg_color = "#e5e7eb" if row["24h %"] >= 0 else "#6b7280"
        sh_color  = "#e5e7eb" if row["Sharpe"] > 1 else ("#9ca3af" if row["Sharpe"] > 0 else "#6b7280")
        rank_icon = ["🥇", "🥈", "🥉"][i] if i < 3 else f"#{i+1}"
        st.markdown(
            f'<div style="background:#060606;border:1px solid {"rgba(229,231,235,0.12)" if row["_sig"]>0 else "#0d0d0d"};'
            f'border-radius:10px;padding:.7rem 1.2rem;margin-bottom:.4rem;'
            f'font-family:JetBrains Mono,monospace;'
            f'display:flex;align-items:center;gap:2rem;flex-wrap:wrap;">'
            f'<span style="color:#333;font-size:.85rem;min-width:2rem;">{rank_icon}</span>'
            f'<span style="color:#f1f5f9;font-weight:700;min-width:3rem;">{row["Crypto"]}</span>'
            f'<span style="color:#94a3b8;">${row["Prix"]:,.3f}</span>'
            f'<span style="color:{chg_color};">{"+"if row["24h %"]>=0 else ""}{row["24h %"]:.2f}%</span>'
            f'<span style="color:{sig_color};font-weight:700;">{row["Signal"]}</span>'
            f'<span><span style="color:#333;font-size:.7rem;">Sharpe </span>'
            f'<span style="color:{sh_color};font-weight:700;">{row["Sharpe"]:.2f}</span></span>'
            f'<span><span style="color:#333;font-size:.7rem;">Ret 1an </span>'
            f'<span style="color:{"#e5e7eb" if row["Return %"]>0 else "#6b7280"};">'
            f'{row["Return %"]:+.1f}%</span></span>'
            f'</div>',
            unsafe_allow_html=True
        )

    # ── Graphique Sharpe ranking ──
    if ranking:
        names_r  = [r["Crypto"] for r in ranking]
        sharpes_r = [r["Sharpe"] for r in ranking]
        colors_r  = ["rgba(229,231,235,0.7)" if r["_sig"] > 0 else "rgba(75,85,99,0.4)"
                     for r in ranking]
        fig_lr = go.Figure(go.Bar(
            x=names_r, y=sharpes_r,
            marker_color=colors_r,
            hovertemplate="<b>%{x}</b><br>Sharpe : %{y:.2f}<extra></extra>",
        ))
        fig_lr.add_hline(y=1.0, line=dict(color="#4b5563", dash="dash", width=1))
        fig_lr.update_layout(
            **DARK, height=280,
            title=dict(text="Sharpe STL par crypto (365j) — Blanc = signal LONG actif",
                       font=dict(size=11, color="#94a3b8"), x=0),
            xaxis=dict(showgrid=False),
            yaxis=dict(showgrid=True, gridcolor="#111"),
            margin=dict(t=40, b=24, l=48, r=12),
        )
        st.plotly_chart(fig_lr, use_container_width=True)
        st.markdown(
            '<div style="color:#333;font-size:.68rem;font-family:JetBrains Mono,monospace;">'
            'Données Binance · actualisation toutes les heures · STL période=5 · EMA=10'
            '</div>', unsafe_allow_html=True
        )