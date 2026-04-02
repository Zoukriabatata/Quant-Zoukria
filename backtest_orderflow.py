"""
Backtest Orderflow — MNQ Tick Data + Kalman OU
Architecture: Ticks → Delta/CVD → Absorption → Hawkes → Kalman Zone → XGBoost → Apex 50K EOD

Usage: streamlit run backtest_orderflow.py
"""

import os, glob, warnings
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path

warnings.filterwarnings("ignore")

try:
    from xgboost import XGBClassifier
    from sklearn.metrics import accuracy_score
    HAS_XGB = True
except ImportError:
    HAS_XGB = False

# ══════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════

TRADES_DIRS = [
    r"C:\Users\ryadb\Downloads\GLBX-20260330-USUQRNFTNL",   # Sep-Oct 2025
    r"C:\Users\ryadb\Downloads\GLBX-20260330-7GNMBUEQF3",   # Nov-Dec 2025
    r"C:\Users\ryadb\Downloads\GLBX-20260327-P8LBCQVG8R",   # Dec 2025-Mar 2026
]

OHLCV_PATH = r"C:\Users\ryadb\Downloads\GLBX-20260328-9GRAVAQAHX\glbx-mdp3-20250325-20260324.ohlcv-1m.csv"

MNQ_POINT = 2.0    # $2 / point MNQ
SESS_H0, SESS_M0 = 14, 30   # 09:30 ET = 14:30 UTC
SESS_H1, SESS_M1 = 21,  0   # 16:00 ET = 21:00 UTC

TEAL   = "#3CC4B7"
GREEN  = "#00ff88"
RED    = "#ff3366"
YELLOW = "#ffd600"
ORANGE = "#ff9100"

# ══════════════════════════════════════════════════════════════════════
# PAGE CONFIG + CSS
# ══════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="Backtest Orderflow MNQ",
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

def _inject_css(raw):
    import re
    css = re.sub(r'/\*.*?\*/', '', raw, flags=re.DOTALL)
    st.markdown(f"<style>{' '.join(css.split())}</style>", unsafe_allow_html=True)

_inject_css("""
*, *::before, *::after { box-sizing: border-box; }
[data-testid="stAppViewContainer"] { background:#060606; font-family:'Inter',sans-serif; }
[data-testid="stSidebar"]  { background:#080808; border-right:1px solid #141414; }
[data-testid="stHeader"]   { background:transparent; }
[data-testid="stToolbar"]  { display:none; }
.block-container           { padding-top:1.5rem; max-width:1200px; }
::-webkit-scrollbar        { width:4px; }
::-webkit-scrollbar-track  { background:#0a0a0a; }
::-webkit-scrollbar-thumb  { background:#3CC4B7; border-radius:2px; }
[data-testid="stSidebarNavLink"] {
    display:block; padding:0.5rem 1rem; margin:1px 6px; border-radius:6px;
    font-family:'JetBrains Mono',monospace; font-size:0.72rem; letter-spacing:0.06em;
    color:#444 !important; text-decoration:none !important; border:1px solid transparent;
}
[data-testid="stSidebarNavLink"][aria-current="page"] {
    background:rgba(60,196,183,0.07) !important;
    color:#3CC4B7 !important; border-color:rgba(60,196,183,0.18);
}
.page-tag   { font-family:'JetBrains Mono',monospace; font-size:0.65rem; letter-spacing:0.2em; color:#3CC4B7; text-transform:uppercase; }
.page-title { font-size:1.8rem; font-weight:700; color:#fff; letter-spacing:-0.02em; margin:0.3rem 0; }
.slabel     { font-family:'JetBrains Mono',monospace; font-size:0.6rem; font-weight:700;
              letter-spacing:0.2em; color:#3CC4B7; text-transform:uppercase; margin:1.8rem 0 0.8rem; }
.stat-row   { display:flex; gap:0; border:1px solid #1a1a1a; border-radius:10px; overflow:hidden; margin:0.5rem 0 1rem; }
.stat-cell  { flex:1; padding:1.1rem 0.8rem; text-align:center; border-right:1px solid #141414; background:#060606; }
.stat-cell:last-child { border-right:none; }
.stat-num   { font-size:1.35rem; font-weight:700; font-family:'JetBrains Mono',monospace; }
.stat-lbl   { font-size:0.56rem; color:#444; letter-spacing:0.14em; text-transform:uppercase; margin-top:0.2rem; }
""")

# ══════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════

st.sidebar.header("Kalman OU")
kalman_lookback = st.sidebar.number_input("Lookback (barres)", value=120, min_value=30, step=10,
    help="Fenêtre AR(1) pour calibrer φ, μ, σ — 120 barres = 2h en 1-min.")
band_k     = st.sidebar.number_input("Bande k min (σ)", value=1.5, min_value=0.5, max_value=4.0, step=0.1)
band_k_max = st.sidebar.number_input("Bande k max (σ)", value=3.5, min_value=1.0, max_value=6.0, step=0.5)
noise_scale = st.sidebar.number_input("Noise scale", value=5.0, min_value=0.1, max_value=20.0, step=0.5)

st.sidebar.markdown("---")
st.sidebar.header("Orderflow — Absorption")
abs_vol_mult = st.sidebar.number_input(
    "Volume min (× moy 20)", value=1.2, min_value=1.0, max_value=3.0, step=0.1,
    help="Volume barre ≥ mult × moyenne 20 barres → signal d'activité institutionnelle.")
abs_close_pct = st.sidebar.number_input(
    "Close position min (%)", value=60, min_value=30, max_value=90, step=5,
    help="Absorption bull : close dans le top X% de la barre malgré sell pressure.")

st.sidebar.markdown("---")
st.sidebar.header("Orderflow — Hawkes")
hawkes_alpha = st.sidebar.number_input(
    "α self-exciting", value=0.6, min_value=0.05, max_value=0.95, step=0.05,
    help="Chaque trade amplifie l'intensité suivante de ce facteur.")
hawkes_beta = st.sidebar.number_input(
    "β decay (par barre)", value=0.15, min_value=0.01, max_value=1.0, step=0.01,
    help="Vitesse de décroissance de l'intensité entre barres.")
min_hawkes_imbalance = st.sidebar.number_input(
    "Imbalance min", value=1.3, min_value=1.0, max_value=4.0, step=0.1,
    help="Ratio hawkes_buy/hawkes_sell ≥ seuil pour valider absorption bull.")

st.sidebar.markdown("---")
st.sidebar.header("Régime — Hurst")
use_hurst  = st.sidebar.toggle("Filtre Hurst", value=True,
    help="H < 0.5 = mean-reverting → signal valide. H > 0.5 = trending → skip.")
hurst_max  = st.sidebar.number_input("H max", value=0.55, min_value=0.40, max_value=0.65, step=0.01)

st.sidebar.markdown("---")
st.sidebar.header("Risk — Apex 50K EOD")
sl_sigma = st.sidebar.slider("SL = k × σ_stat", 0.25, 3.0, 0.75, 0.25)
sl_min   = st.sidebar.number_input("SL min (pts)", value=4.0, step=0.5)
tp_ratio = st.sidebar.slider("TP (% vers FV)", 0.25, 1.0, 1.0, 0.05)
max_tpd  = st.sidebar.number_input("Max trades/jour", value=2, min_value=1, max_value=5)

st.sidebar.markdown("---")
st.sidebar.header("XGBoost")
use_xgb   = st.sidebar.toggle("Activer XGBoost", value=HAS_XGB,
    help="Filtre ML — entraîne sur IS, filtre OOS par P(win) ≥ seuil.")
xgb_thr   = st.sidebar.slider("Seuil P(win)", 0.40, 0.75, 0.55, 0.05) if use_xgb else 0.55
xgb_oos   = st.sidebar.slider("% OOS", 10, 30, 20, 5) if use_xgb else 20

# ══════════════════════════════════════════════════════════════════════
# PAGE HEADER
# ══════════════════════════════════════════════════════════════════════

st.html("""
<div style="padding:1.5rem 0 0.5rem; border-bottom:1px solid #1a1a1a; margin-bottom:1.5rem">
    <div class="page-tag">BACKTEST · MNQ TICK DATA · ORDERFLOW + KALMAN OU + HAWKES</div>
    <div class="page-title">Backtest Orderflow — MNQ</div>
</div>
""")

# ══════════════════════════════════════════════════════════════════════
# KALMAN ENGINE
# ══════════════════════════════════════════════════════════════════════

def estimate_ar1(closes):
    y = np.array(closes, dtype=float)
    y = y[np.isfinite(y)]
    if len(y) < 5:
        return None
    try:
        xl, xc = y[:-1], y[1:]
        X    = np.column_stack([np.ones_like(xl), xl])
        beta = np.linalg.lstsq(X, xc, rcond=None)[0]
        c, phi = float(beta[0]), float(beta[1])
        phi  = np.clip(phi, 0.01, 0.99)
        resid = xc - (c + phi * xl)
        sigma = float(np.sqrt(np.mean(resid ** 2)))
        if sigma <= 0 or not np.isfinite(sigma):
            sigma = max(float(np.std(y)) * 0.01, 1e-9)
        return phi, c / (1.0 - phi), sigma
    except Exception:
        return None


class KalmanOU:
    def __init__(self, phi, mu, sigma, ns=1.0):
        self.phi = phi; self.mu = mu
        self.Q = sigma ** 2 * max(1.0 - phi ** 2, 1e-6)
        self.R = sigma ** 2 * max(ns, 0.01)
        self.x = mu; self.P = self.R

    def update(self, z):
        self.x = self.phi * self.x + (1.0 - self.phi) * self.mu
        self.P = self.phi ** 2 * self.P + self.Q
        K = self.P / (self.P + self.R)
        self.x += K * (z - self.x)
        self.P = (1.0 - K) * self.P
        return self.x


def run_kalman(prices, lookback, ns):
    n  = len(prices)
    fv = np.full(n, np.nan)
    ss = np.full(n, np.nan)
    kal = None
    for i in range(lookback, n):
        w = prices[i - lookback:i]
        p = estimate_ar1(w)
        if p is None:
            continue
        phi, mu, sigma = p
        s = sigma / np.sqrt(max(1.0 - phi ** 2, 1e-6))
        if kal is None:
            kal = KalmanOU(phi, mu, sigma, ns)
            for c in w:
                kal.update(c)
        else:
            kal.phi = phi; kal.mu = mu
            kal.Q = sigma ** 2 * max(1.0 - phi ** 2, 1e-6)
            kal.R = sigma ** 2 * max(ns, 0.01)
        kal.update(prices[i])
        fv[i] = kal.x
        ss[i] = s
    return fv, ss

# ══════════════════════════════════════════════════════════════════════
# HURST EXPONENT (R/S analysis)
# ══════════════════════════════════════════════════════════════════════

def compute_hurst(prices, window=60):
    n = len(prices)
    h = np.full(n, np.nan)
    lags = [4, 8, 16, 32]
    for i in range(window, n):
        ts = prices[i - window:i]
        try:
            rs_vals = []
            for lag in lags:
                if lag >= len(ts) // 2:
                    continue
                chunks = [ts[j:j + lag] for j in range(0, len(ts) - lag, lag)]
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
                slope = np.polyfit(xs, ys, 1)[0]
                h[i] = float(np.clip(slope, 0.0, 1.0))
        except Exception:
            pass
    return h

# ══════════════════════════════════════════════════════════════════════
# TICK DATA — LOAD & AGGREGATE
# ══════════════════════════════════════════════════════════════════════

@st.cache_data(show_spinner="Chargement et agrégation tick data MNQ...")
def load_tick_bars():
    """
    Load all trades CSVs → aggregate to 1-min OHLCV bars + orderflow features.
    Columns: open/high/low/close/volume/buy_vol/sell_vol/delta/n_trades/large_vol
    """
    all_files = []
    for d in TRADES_DIRS:
        all_files += sorted(glob.glob(os.path.join(d, "*.trades.csv")))

    if not all_files:
        return None, f"Aucun fichier trades.csv trouvé dans {TRADES_DIRS}"

    bar_list = []
    prog = st.progress(0.0, text="Traitement tick data...")

    for fi, fp in enumerate(all_files):
        prog.progress((fi + 1) / len(all_files), text=f"{os.path.basename(fp)}")
        try:
            df = pd.read_csv(fp, usecols=["ts_event", "price", "size", "side"])
        except Exception:
            continue

        if df.empty:
            continue

        df["ts"]    = pd.to_datetime(df["ts_event"], utc=True)
        df["price"] = df["price"].astype(float)
        df["size"]  = df["size"].astype(float)

        # Session filter 14:30 → 21:00 UTC
        h = df["ts"].dt.hour
        m = df["ts"].dt.minute
        in_sess = (
            ((h == SESS_H0) & (m >= SESS_M0)) |
            ((h > SESS_H0) & (h < SESS_H1)) |
            ((h == SESS_H1) & (m <= SESS_M1))
        )
        df = df[in_sess]
        if df.empty:
            continue

        df = df.set_index("ts").sort_index()

        # Vectorized buy/sell split
        is_buy  = df["side"] == "B"
        df["buy_sz"]  = df["size"].where(is_buy,  0.0)
        df["sell_sz"] = df["size"].where(~is_buy, 0.0)

        # Large prints (top 10% size this day)
        p90 = float(df["size"].quantile(0.90))
        df["lg_sz"] = df["size"].where(df["size"] >= p90, 0.0)

        g = df.groupby(pd.Grouper(freq="1min"))
        ohlcv = g["price"].ohlc()
        ohlcv.columns = ["open", "high", "low", "close"]
        ohlcv["volume"]   = g["size"].sum()
        ohlcv["buy_vol"]  = g["buy_sz"].sum()
        ohlcv["sell_vol"] = g["sell_sz"].sum()
        ohlcv["n_trades"] = g["size"].count()
        ohlcv["large_vol"] = g["lg_sz"].sum()

        ohlcv = ohlcv[ohlcv["volume"] > 0]
        bar_list.append(ohlcv)

    prog.empty()

    if not bar_list:
        return None, "Aucune barre générée — vérifier les dossiers TRADES_DIRS."

    bars = pd.concat(bar_list).sort_index()
    bars = bars[~bars.index.duplicated(keep="last")]
    bars["delta"]             = bars["buy_vol"] - bars["sell_vol"]
    bars["delta_imbalance"]   = bars["delta"] / bars["volume"].clip(lower=1)
    bars["large_print_ratio"] = bars["large_vol"] / bars["volume"].clip(lower=1)
    return bars, None


@st.cache_data(show_spinner="Chargement OHLCV MNQ...")
def load_ohlcv():
    path = OHLCV_PATH
    if not os.path.exists(path):
        alt = r"C:\Users\ryadb\Downloads\data OHLCV M1\glbx-mdp3-20240330-20260329.ohlcv-1m.csv"
        if os.path.exists(alt):
            path = alt
        else:
            return None
    try:
        df = pd.read_csv(path, usecols=["ts_event", "open", "high", "low", "close", "volume"])
        df["bar"] = pd.to_datetime(df["ts_event"], utc=True)
        df = df.set_index("bar").sort_index()
        return df[["open", "high", "low", "close", "volume"]].dropna(subset=["close"])
    except Exception as e:
        st.warning(f"OHLCV non chargé : {e}")
        return None

# ══════════════════════════════════════════════════════════════════════
# FEATURE ENGINEERING
# ══════════════════════════════════════════════════════════════════════

def hawkes_intensity(series: np.ndarray, alpha: float, beta: float) -> np.ndarray:
    """
    Recursive Hawkes process intensity per bar.
    λ_t = μ + alpha * x_t + e^{-beta} * λ_{t-1}
    x_t = normalized volume (buy or sell)
    """
    n     = len(series)
    decay = np.exp(-beta)
    lam   = np.zeros(n)
    mu    = float(series[series > 0].mean()) * 0.1 if (series > 0).any() else 0.1
    for i in range(1, n):
        lam[i] = mu + alpha * series[i] + decay * lam[i - 1]
    return lam


def compute_features(bars: pd.DataFrame, fv: np.ndarray, ss: np.ndarray,
                     vol_mult: float, close_pct: float,
                     alpha: float, beta: float) -> pd.DataFrame:
    df = bars.copy()
    df["fv"] = fv
    df["ss"] = ss
    df["dev"] = np.where(df["ss"] > 0, (df["close"] - df["fv"]) / df["ss"], np.nan)

    # CVD + slope
    df["cvd"]        = df["delta"].cumsum()
    df["cvd_slope5"] = df["cvd"].diff(5)

    # Volume rolling mean
    df["vol_ma20"] = df["volume"].rolling(20, min_periods=5).mean()

    # Bar close position (0=low, 1=high)
    rng       = (df["high"] - df["low"]).clip(lower=1e-6)
    close_pos = (df["close"] - df["low"]) / rng

    vol_ok = df["volume"] >= df["vol_ma20"] * vol_mult

    # Absorption
    # Bull: net sell pressure BUT close in top X% → buyers absorbed sellers
    df["abs_bull"] = (
        (df["sell_vol"] > df["buy_vol"]) &
        (close_pos >= close_pct / 100.0) &
        vol_ok
    )
    # Bear: net buy pressure BUT close in bottom X% → sellers absorbed buyers
    df["abs_bear"] = (
        (df["buy_vol"] > df["sell_vol"]) &
        (close_pos <= 1.0 - close_pct / 100.0) &
        vol_ok
    )

    # Hawkes intensity (buy side / sell side)
    buy_arr  = df["buy_vol"].fillna(0).values
    sell_arr = df["sell_vol"].fillna(0).values
    h_buy  = hawkes_intensity(buy_arr,  alpha, beta)
    h_sell = hawkes_intensity(sell_arr, alpha, beta)
    df["hawkes_buy"]  = h_buy
    df["hawkes_sell"] = h_sell
    # Imbalance ratios
    df["h_imb_bull"] = np.where(h_sell > 0.01, h_buy  / h_sell, 1.0)
    df["h_imb_bear"] = np.where(h_buy  > 0.01, h_sell / h_buy,  1.0)

    return df

# ══════════════════════════════════════════════════════════════════════
# SIGNAL GENERATION
# ══════════════════════════════════════════════════════════════════════

def generate_signals(df: pd.DataFrame, bk: float, bk_max: float,
                     min_himb: float, h_max: float, use_h: bool) -> pd.Series:
    sig = pd.Series("NONE", index=df.index)

    valid  = ~df["dev"].isna() & ~df["ss"].isna()
    in_lng = (df["dev"] < -bk) & (df["dev"] > -bk_max)
    in_sht = (df["dev"] >  bk) & (df["dev"] <  bk_max)

    # Hurst: ranging regime
    if use_h and "hurst" in df.columns:
        ranging = df["hurst"].fillna(0.5) < h_max
    else:
        ranging = pd.Series(True, index=df.index)

    # Reversion confirmation: current bar moving back toward FV
    prev_dev_abs = df["dev"].shift(1).abs()
    curr_dev_abs = df["dev"].abs()
    reverting = curr_dev_abs < prev_dev_abs

    long_cond = (
        valid & in_lng & df["abs_bull"] &
        (df["h_imb_bull"] >= min_himb) &
        ranging & reverting
    )
    short_cond = (
        valid & in_sht & df["abs_bear"] &
        (df["h_imb_bear"] >= min_himb) &
        ranging & reverting
    )

    sig[long_cond]  = "LONG"
    sig[short_cond] = "SHORT"
    return sig

# ══════════════════════════════════════════════════════════════════════
# BACKTEST ENGINE
# ══════════════════════════════════════════════════════════════════════

def backtest(df: pd.DataFrame, signals: pd.Series,
             sl_sigma: float, sl_min: float, tp_r: float, max_tpd: int):
    prices = df["close"].values
    fvs    = df["fv"].values
    sss    = df["ss"].values
    times  = df.index
    n      = len(df)

    trades    = []
    equity    = np.full(n, 50_000.0)
    eq        = 50_000.0
    peak      = eq
    trail_dd  = 0.0

    APEX_DD   = 2_000.0
    DAILY_LIM = 800.0

    daily_cnt  = {}
    daily_loss = {}

    for i in range(1, n - 1):
        sig = signals.iloc[i]
        equity[i] = eq
        if sig == "NONE":
            continue

        ts  = times[i]
        day = ts.date()
        daily_cnt.setdefault(day, 0)
        daily_loss.setdefault(day, 0.0)

        if daily_cnt[day] >= max_tpd:          continue
        if daily_loss[day] >= DAILY_LIM:       continue
        if trail_dd >= APEX_DD:                continue
        if np.isnan(sss[i]) or np.isnan(fvs[i]): continue

        entry  = prices[i]
        ss_i   = sss[i]
        fv_i   = fvs[i]
        sl_pts = max(sl_sigma * ss_i, sl_min)
        tp_pts = abs(entry - fv_i) * tp_r

        if tp_pts < 0.5:
            continue

        sl_p = entry - sl_pts if sig == "LONG" else entry + sl_pts
        tp_p = entry + tp_pts if sig == "LONG" else entry - tp_pts

        result = "OPEN"
        exit_p = np.nan
        exit_t = None
        max_bars = min(i + 240, n - 1)

        for j in range(i + 1, max_bars + 1):
            p = prices[j]
            if sig == "LONG":
                if p <= sl_p: result = "LOSS"; exit_p = sl_p; exit_t = times[j]; break
                if p >= tp_p: result = "WIN";  exit_p = tp_p; exit_t = times[j]; break
            else:
                if p >= sl_p: result = "LOSS"; exit_p = sl_p; exit_t = times[j]; break
                if p <= tp_p: result = "WIN";  exit_p = tp_p; exit_t = times[j]; break

        if result == "OPEN":
            exit_p = prices[max_bars]
            exit_t = times[max_bars]

        pnl_pts = (exit_p - entry) if sig == "LONG" else (entry - exit_p)
        pnl_usd = pnl_pts * MNQ_POINT
        result  = "WIN" if pnl_pts > 0 else "LOSS"

        eq += pnl_usd
        equity[i] = eq
        peak     = max(peak, eq)
        trail_dd = peak - eq

        daily_cnt[day]  += 1
        if pnl_usd < 0:
            daily_loss[day] += abs(pnl_usd)

        trades.append({
            "entry_time":  ts,
            "exit_time":   exit_t,
            "signal":      sig,
            "entry":       round(entry, 2),
            "exit":        round(exit_p, 2),
            "sl_pts":      round(sl_pts, 2),
            "tp_pts":      round(tp_pts, 2),
            "pnl_pts":     round(pnl_pts, 2),
            "pnl_$":       round(pnl_usd, 2),
            "result":      result,
            "dev_entry":   round(float(df["dev"].iloc[i]), 3),
            "h_imb_bull":  round(float(df["h_imb_bull"].iloc[i]), 3),
            "h_imb_bear":  round(float(df["h_imb_bear"].iloc[i]), 3),
            "abs_bull":    bool(df["abs_bull"].iloc[i]),
            "abs_bear":    bool(df["abs_bear"].iloc[i]),
            "hurst":       round(float(df["hurst"].iloc[i]), 3) if "hurst" in df.columns else np.nan,
        })

    # Forward fill equity for non-trade bars
    last = 50_000.0
    for i in range(n):
        if equity[i] != 50_000.0 or i == 0:
            last = equity[i]
        else:
            equity[i] = last

    tdf = pd.DataFrame(trades) if trades else pd.DataFrame()
    return tdf, equity

# ══════════════════════════════════════════════════════════════════════
# XGBOOST FILTER
# ══════════════════════════════════════════════════════════════════════

def run_xgb_filter(df: pd.DataFrame, tdf: pd.DataFrame,
                   oos_pct: int, threshold: float):
    if not HAS_XGB:
        return tdf, None, "pip install xgboost scikit-learn"
    if tdf.empty or len(tdf) < 30:
        return tdf, None, "Minimum 30 trades requis pour XGBoost."

    feat_cols = [
        "dev", "delta_imbalance", "cvd_slope5",
        "h_imb_bull", "h_imb_bear", "large_print_ratio", "ss",
    ]
    if "hurst" in df.columns:
        feat_cols.append("hurst")

    X_all = df[feat_cols].reindex(tdf["entry_time"]).fillna(0).values
    y_all = (tdf["result"] == "WIN").astype(int).values

    split = int(len(X_all) * (1 - oos_pct / 100))
    if split < 10 or (len(X_all) - split) < 5:
        return tdf, None, "Split IS/OOS insuffisant."

    model = XGBClassifier(
        n_estimators=150, max_depth=3, learning_rate=0.08,
        subsample=0.8, colsample_bytree=0.8,
        eval_metric="logloss", verbosity=0, random_state=42,
    )
    model.fit(X_all[:split], y_all[:split])

    prob_oos = model.predict_proba(X_all[split:])[:, 1]
    acc_oos  = accuracy_score(y_all[split:], (prob_oos >= 0.5).astype(int))

    tdf_oos = tdf.iloc[split:].copy()
    tdf_oos["p_win"] = prob_oos
    filtered = tdf_oos[tdf_oos["p_win"] >= threshold].copy()

    info = {
        "acc_oos":   acc_oos,
        "n_is":      split,
        "n_oos":     len(X_all) - split,
        "n_kept":    len(filtered),
        "wr_filtered": (filtered["result"] == "WIN").mean() * 100 if not filtered.empty else 0,
        "importance": dict(zip(feat_cols, model.feature_importances_)),
    }
    return filtered, info, None

# ══════════════════════════════════════════════════════════════════════
# DISPLAY HELPERS
# ══════════════════════════════════════════════════════════════════════

def _ax():
    return dict(
        gridcolor="rgba(255,255,255,0.025)", linecolor="#111",
        tickfont=dict(color="#333", size=10, family="JetBrains Mono"),
        zeroline=False, showgrid=True,
    )

def _layout(**kw):
    return dict(
        paper_bgcolor="rgba(6,6,6,0)", plot_bgcolor="rgba(8,8,8,1)",
        font=dict(color="#555", size=11, family="JetBrains Mono"),
        margin=dict(t=24, b=28, l=54, r=20),
        **kw,
    )

def stat_cell(val, lbl, color="#fff"):
    return (
        f'<div class="stat-cell">'
        f'<div class="stat-num" style="color:{color}">{val}</div>'
        f'<div class="stat-lbl">{lbl}</div></div>'
    )

def render_stats(tdf: pd.DataFrame, equity: np.ndarray):
    if tdf.empty:
        st.warning("Aucun trade généré — essaie de baisser band_k ou abs_vol_mult.")
        return

    n     = len(tdf)
    wins  = (tdf["result"] == "WIN").sum()
    loss  = n - wins
    wr    = wins / n * 100
    esp   = tdf["pnl_pts"].mean()
    pnl   = tdf["pnl_$"].sum()
    avg_w = tdf.loc[tdf["result"] == "WIN",  "pnl_pts"].mean()
    avg_l = tdf.loc[tdf["result"] == "LOSS", "pnl_pts"].mean()
    pf    = abs(avg_w * wins / (avg_l * loss)) if loss > 0 and avg_l != 0 else float("inf")

    dd     = equity - np.maximum.accumulate(equity)
    max_dd = abs(dd.min()) / max(equity.max(), 1) * 100

    dp = tdf.groupby(tdf["entry_time"].dt.date)["pnl_$"].sum()
    sharpe = (dp.mean() / dp.std() * np.sqrt(252)) if dp.std() > 0 else 0.0

    c_wr  = GREEN if wr >= 55 else (YELLOW if wr >= 45 else RED)
    c_pf  = GREEN if pf >= 1.5 else (YELLOW if pf >= 1.2 else RED)
    c_pnl = GREEN if pnl > 0 else RED
    c_dd  = RED if max_dd > 4 else YELLOW

    st.markdown(
        '<div class="stat-row">'
        + stat_cell(n, "Trades")
        + stat_cell(f"{wr:.1f}%", "Winrate", c_wr)
        + stat_cell(f"{esp:.1f} pts", "Espérance", GREEN if esp > 0 else RED)
        + stat_cell(f"{avg_w:.1f} pts", "Gain moy.", GREEN)
        + stat_cell(f"{abs(avg_l):.1f} pts", "Perte moy.", RED)
        + stat_cell(f"{pf:.2f}", "Profit Factor", c_pf)
        + stat_cell(f"{sharpe:.2f}", "Sharpe")
        + stat_cell(f"{max_dd:.1f}%", "Max DD", c_dd)
        + stat_cell(f"${pnl:+,.0f}", "P&L total", c_pnl)
        + "</div>",
        unsafe_allow_html=True,
    )

    if pf >= 1.5 and esp >= 5.0 and max_dd <= 4.0:
        st.success(f"Edge solide — PF {pf:.2f} | Espérance {esp:.1f} pts | DD {max_dd:.1f}%")
    else:
        issues = []
        if pf < 1.5:  issues.append(f"PF {pf:.2f} < 1.5")
        if esp < 5.0: issues.append(f"Espérance {esp:.1f} pts < 5 pts")
        if max_dd > 4.0: issues.append(f"DD {max_dd:.1f}% > 4% Apex")
        st.warning("Problèmes : " + " · ".join(issues))


def render_equity(tdf: pd.DataFrame, equity: np.ndarray, index):
    fig = make_subplots(rows=2, cols=1, row_heights=[0.65, 0.35],
                        shared_xaxes=False, vertical_spacing=0.06)

    x = index
    fig.add_trace(go.Scatter(x=x, y=equity, mode="lines",
        line=dict(color=TEAL, width=1.5), name="Equity"), row=1, col=1)

    if not tdf.empty:
        for res, color, sym in [("WIN", GREEN, "triangle-up"), ("LOSS", RED, "triangle-down")]:
            sub = tdf[tdf["result"] == res]
            if sub.empty: continue
            eq_ser = pd.Series(equity, index=x)
            yv = eq_ser.reindex(sub["entry_time"], method="nearest")
            fig.add_trace(go.Scatter(
                x=sub["entry_time"], y=yv.values, mode="markers",
                marker=dict(color=color, size=7, symbol=sym), name=res,
            ), row=1, col=1)

    dd = equity - np.maximum.accumulate(equity)
    fig.add_trace(go.Scatter(
        x=x, y=dd / max(equity.max(), 1) * 100,
        fill="tozeroy", fillcolor="rgba(255,51,102,0.07)",
        line=dict(color=RED, width=1), name="DD%",
    ), row=2, col=1)
    fig.add_hline(y=-4.0, line_dash="dot", line_color="rgba(255,51,102,0.4)",
                  line_width=1, row=2, col=1,
                  annotation_text="  Apex 4%",
                  annotation_font=dict(color=RED, size=9, family="JetBrains Mono"))

    fig.update_layout(height=480, **_layout(
        hovermode="x unified",
        legend=dict(orientation="h", y=1.02, bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#444", size=10)),
        xaxis=dict(**_ax()), yaxis=dict(**_ax(), title="Equity ($)"),
        xaxis2=dict(**_ax()), yaxis2=dict(**_ax(), title="DD %"),
    ))
    st.plotly_chart(fig, use_container_width=True)


def render_signal_chart(df: pd.DataFrame, fv: np.ndarray, ss: np.ndarray,
                        signals: pd.Series, bk: float, n_show: int):
    d  = df.iloc[-n_show:]
    fv_ = fv[-n_show:]
    ss_ = ss[-n_show:]
    sg_ = signals.iloc[-n_show:]
    x   = d.index

    valid = ~np.isnan(fv_)
    upper = np.where(valid, fv_ + bk * ss_, np.nan)
    lower = np.where(valid, fv_ - bk * ss_, np.nan)
    fv_v  = np.where(valid, fv_, np.nan)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=upper, mode="lines",
        line=dict(color="rgba(60,196,183,0.18)", width=1, dash="dot"), name=f"+{bk}σ"))
    fig.add_trace(go.Scatter(x=x, y=lower, mode="lines",
        line=dict(color="rgba(60,196,183,0.18)", width=1, dash="dot"),
        fill="tonexty", fillcolor="rgba(60,196,183,0.03)", name=f"-{bk}σ"))
    fig.add_trace(go.Scatter(x=x, y=fv_v, mode="lines",
        line=dict(color=TEAL, width=1.8), name="Fair Value"))
    fig.add_trace(go.Scatter(x=x, y=d["close"].values, mode="lines",
        line=dict(color="rgba(210,210,210,0.8)", width=1.1), name="MNQ"))

    for s, color, sym in [("LONG", GREEN, "triangle-up"), ("SHORT", RED, "triangle-down")]:
        mask = sg_ == s
        if mask.any():
            fig.add_trace(go.Scatter(
                x=d.index[mask], y=d["close"].values[mask], mode="markers",
                marker=dict(color=color, size=9, symbol=sym), name=s,
            ))

    fig.update_layout(height=400, **_layout(
        hovermode="x unified",
        legend=dict(orientation="h", y=1.02, bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#444", size=10)),
        xaxis=dict(**_ax()), yaxis=dict(**_ax(), tickformat=".2f"),
    ))
    st.plotly_chart(fig, use_container_width=True)


def render_delta_chart(df: pd.DataFrame, n_show: int):
    d = df.iloc[-n_show:]
    x = d.index
    colors = [GREEN if v >= 0 else RED for v in d["delta"].values]
    fig = make_subplots(rows=2, cols=1, row_heights=[0.5, 0.5],
                        shared_xaxes=True, vertical_spacing=0.04)
    fig.add_trace(go.Bar(x=x, y=d["delta"].values,
        marker_color=colors, marker_opacity=0.65, name="Delta"), row=1, col=1)
    fig.add_trace(go.Scatter(x=x, y=d["cvd"].values, mode="lines",
        line=dict(color=YELLOW, width=1.5), name="CVD"), row=2, col=1)
    fig.add_hline(y=0, line_color="rgba(255,255,255,0.06)", line_width=1, row=1, col=1)
    fig.add_hline(y=0, line_color="rgba(255,255,255,0.06)", line_width=1, row=2, col=1)
    fig.update_layout(height=340, **_layout(
        hovermode="x unified",
        legend=dict(orientation="h", y=1.02, bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#444", size=10)),
        xaxis=dict(**_ax(), showticklabels=False),
        yaxis=dict(**_ax(), title="Delta"),
        xaxis2=dict(**_ax()), yaxis2=dict(**_ax(), title="CVD"),
        bargap=0.05,
    ))
    st.plotly_chart(fig, use_container_width=True)


def render_hawkes_chart(df: pd.DataFrame, n_show: int):
    d = df.iloc[-n_show:]
    x = d.index
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=d["hawkes_buy"].values, mode="lines",
        line=dict(color=GREEN, width=1.2), name="Hawkes Buy"))
    fig.add_trace(go.Scatter(x=x, y=d["hawkes_sell"].values, mode="lines",
        line=dict(color=RED, width=1.2), name="Hawkes Sell"))
    fig.update_layout(height=240, **_layout(
        hovermode="x unified",
        legend=dict(orientation="h", y=1.02, bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#444", size=10)),
        xaxis=dict(**_ax()), yaxis=dict(**_ax(), title="Intensité Hawkes"),
    ))
    st.plotly_chart(fig, use_container_width=True)


def render_importance(imp: dict):
    if not imp: return
    items = sorted(imp.items(), key=lambda x: x[1], reverse=True)
    fig = go.Figure(go.Bar(
        x=[v for _, v in items], y=[k for k, _ in items],
        orientation="h", marker_color=TEAL, marker_opacity=0.75,
    ))
    fig.update_layout(height=280, **_layout(
        xaxis=dict(**_ax(), title="Importance"),
        yaxis=dict(**_ax()),
    ))
    st.plotly_chart(fig, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════

# ── Load data ─────────────────────────────────────────────────────────
bars_df, err = load_tick_bars()
if err or bars_df is None:
    st.error(err or "Impossible de charger les ticks.")
    st.stop()

ohlcv_df = load_ohlcv()

# ── Kalman prices — OHLCV si dispo, sinon bars_df ─────────────────────
if ohlcv_df is not None:
    kal_prices = ohlcv_df["close"].reindex(bars_df.index, method="nearest").fillna(bars_df["close"])
else:
    kal_prices = bars_df["close"]

# ── Kalman OU ─────────────────────────────────────────────────────────
with st.spinner("Kalman OU..."):
    fv_arr, ss_arr = run_kalman(kal_prices.values, kalman_lookback, noise_scale)

# ── Hurst ─────────────────────────────────────────────────────────────
if use_hurst:
    with st.spinner("Hurst R/S..."):
        bars_df["hurst"] = compute_hurst(kal_prices.values)
else:
    bars_df["hurst"] = 0.45

# ── Features ──────────────────────────────────────────────────────────
with st.spinner("Features orderflow..."):
    bars_df = compute_features(
        bars_df, fv_arr, ss_arr,
        abs_vol_mult, abs_close_pct,
        hawkes_alpha, hawkes_beta,
    )

# ── Signals ───────────────────────────────────────────────────────────
signals = generate_signals(bars_df, band_k, band_k_max,
                           min_hawkes_imbalance, hurst_max, use_hurst)

n_long  = (signals == "LONG").sum()
n_short = (signals == "SHORT").sum()

st.markdown(
    f"<div style='font-family:JetBrains Mono,monospace;font-size:0.7rem;color:#444;margin-bottom:1rem'>"
    f"{len(bars_df):,} barres · {n_long} LONG · {n_short} SHORT · "
    f"{bars_df.index[0].strftime('%Y-%m-%d')} → {bars_df.index[-1].strftime('%Y-%m-%d')}"
    f"</div>",
    unsafe_allow_html=True,
)

# ── Backtest ──────────────────────────────────────────────────────────
with st.spinner("Backtest..."):
    trades_df, equity = backtest(
        bars_df, signals, sl_sigma, sl_min, tp_ratio, max_tpd,
    )

# ══════════════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════════════

tab_res, tab_eq, tab_sig, tab_of, tab_xg, tab_log = st.tabs([
    "📊 Résultats",
    "📈 Equity",
    "🎯 Signaux",
    "🌊 Orderflow",
    "🤖 XGBoost",
    "📋 Log trades",
])

# ── Résultats ─────────────────────────────────────────────────────────
with tab_res:
    st.markdown('<div class="slabel">Performance globale</div>', unsafe_allow_html=True)
    render_stats(trades_df, equity)

    if not trades_df.empty:
        n = len(trades_df)
        wins = (trades_df["result"] == "WIN").sum()
        loss = n - wins
        wr   = wins / n * 100
        esp  = trades_df["pnl_pts"].mean()
        pnl  = trades_df["pnl_$"].sum()
        avg_w = trades_df.loc[trades_df["result"]=="WIN",  "pnl_pts"].mean()
        avg_l = trades_df.loc[trades_df["result"]=="LOSS", "pnl_pts"].mean()
        pf    = abs(avg_w * wins / (avg_l * loss)) if loss > 0 and avg_l != 0 else 0

        st.markdown('<div class="slabel">Résumé</div>', unsafe_allow_html=True)
        st.code(
            f"ORDERFLOW BACKTEST — {n} trades | WR {wr:.1f}% | PF {pf:.2f} | "
            f"Esp {esp:.1f} pts | P&L ${pnl:+,.0f}\n"
            f"Params: band_k={band_k}σ | abs_vol={abs_vol_mult}× | "
            f"abs_close={abs_close_pct}% | hawkes_min={min_hawkes_imbalance} | "
            f"SL={sl_sigma}σ | TP={tp_ratio*100:.0f}%"
        )

# ── Equity ────────────────────────────────────────────────────────────
with tab_eq:
    st.markdown('<div class="slabel">Equity curve + Drawdown</div>', unsafe_allow_html=True)
    render_equity(trades_df, equity, bars_df.index)

# ── Signaux ───────────────────────────────────────────────────────────
with tab_sig:
    n_show = st.slider("Barres à afficher", 100, 800, 300, 50, key="ns_sig")
    st.markdown('<div class="slabel">Prix + Kalman OU + Signaux orderflow</div>',
                unsafe_allow_html=True)
    render_signal_chart(bars_df, fv_arr, ss_arr, signals, band_k, n_show)

    if not trades_df.empty:
        st.markdown('<div class="slabel">Distribution déviation à l\'entrée</div>',
                    unsafe_allow_html=True)
        fig_d = go.Figure(go.Histogram(
            x=trades_df["dev_entry"], nbinsx=25,
            marker_color=TEAL, marker_opacity=0.7,
        ))
        fig_d.update_layout(height=220, **_layout(
            xaxis=dict(**_ax(), title="Déviation σ"),
            yaxis=dict(**_ax()),
        ))
        st.plotly_chart(fig_d, use_container_width=True)

# ── Orderflow ─────────────────────────────────────────────────────────
with tab_of:
    n_show_of = st.slider("Barres à afficher", 100, 800, 300, 50, key="ns_of")
    st.markdown('<div class="slabel">Delta + CVD</div>', unsafe_allow_html=True)
    render_delta_chart(bars_df, n_show_of)

    st.markdown('<div class="slabel">Intensité Hawkes — Buy vs Sell</div>',
                unsafe_allow_html=True)
    render_hawkes_chart(bars_df, n_show_of)

    if use_hurst and "hurst" in bars_df.columns:
        st.markdown('<div class="slabel">Hurst exponent (ranging < 0.5)</div>',
                    unsafe_allow_html=True)
        fig_h = go.Figure()
        fig_h.add_trace(go.Scatter(
            x=bars_df.index[-n_show_of:],
            y=bars_df["hurst"].values[-n_show_of:],
            mode="lines", line=dict(color=ORANGE, width=1.2), name="Hurst",
        ))
        fig_h.add_hline(y=0.5, line_dash="dot",
                        line_color="rgba(255,255,255,0.2)", line_width=1,
                        annotation_text="  H=0.5",
                        annotation_font=dict(color="#555", size=9, family="JetBrains Mono"))
        fig_h.add_hline(y=hurst_max, line_dash="dot",
                        line_color=f"rgba(60,196,183,0.4)", line_width=1,
                        annotation_text=f"  seuil {hurst_max}",
                        annotation_font=dict(color=TEAL, size=9, family="JetBrains Mono"))
        fig_h.update_layout(height=220, **_layout(
            xaxis=dict(**_ax()), yaxis=dict(**_ax(), range=[0.2, 0.8]),
        ))
        st.plotly_chart(fig_h, use_container_width=True)

# ── XGBoost ───────────────────────────────────────────────────────────
with tab_xg:
    st.markdown('<div class="slabel">XGBoost — Filtre ML sur les features orderflow</div>',
                unsafe_allow_html=True)
    st.markdown(
        "Principe : entraîne sur les trades IS, prédit P(win) sur OOS. "
        "Ne garde que les trades avec P(win) ≥ seuil. "
        "Si WR OOS filtré > WR brut → le modèle apprend quelque chose de réel.",
        unsafe_allow_html=False,
    )

    if not HAS_XGB:
        st.warning("`pip install xgboost scikit-learn` pour activer ce module.")
    elif not use_xgb:
        st.info("Active le filtre XGBoost dans la sidebar.")
    elif trades_df.empty:
        st.warning("Aucun trade à filtrer.")
    else:
        if st.button("Entraîner XGBoost", type="primary"):
            with st.spinner("Entraînement..."):
                filt, info, xgb_err = run_xgb_filter(bars_df, trades_df, xgb_oos, xgb_thr)
            if xgb_err:
                st.warning(xgb_err)
            else:
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Accuracy OOS", f"{info['acc_oos']*100:.1f}%")
                c2.metric("Trades IS",    info["n_is"])
                c3.metric("Trades OOS",   info["n_oos"])
                c4.metric("Gardés OOS",   info["n_kept"])

                wr_brut = (trades_df.iloc[info["n_is"]:]["result"] == "WIN").mean() * 100
                wr_filt = info["wr_filtered"]
                if wr_filt > wr_brut:
                    st.success(f"WR filtré {wr_filt:.1f}% > WR brut {wr_brut:.1f}% — XGBoost améliore le signal.")
                else:
                    st.warning(f"WR filtré {wr_filt:.1f}% ≤ WR brut {wr_brut:.1f}% — signal trop faible pour XGBoost.")

                st.markdown('<div class="slabel">Feature importance</div>', unsafe_allow_html=True)
                render_importance(info["importance"])

                if not filt.empty:
                    pnl_f = filt["pnl_$"].sum()
                    st.markdown('<div class="slabel">Trades filtrés (OOS)</div>', unsafe_allow_html=True)
                    st.dataframe(
                        filt[["entry_time","signal","entry","exit","pnl_pts","pnl_$","result","p_win"]],
                        use_container_width=True, height=300,
                    )
                    st.markdown(
                        f"<div style='font-family:JetBrains Mono,monospace;font-size:0.75rem;color:#555'>"
                        f"P&L OOS filtré : <span style='color:{'#00ff88' if pnl_f>0 else '#ff3366'}'>"
                        f"${pnl_f:+,.0f}</span></div>",
                        unsafe_allow_html=True,
                    )

# ── Log ───────────────────────────────────────────────────────────────
with tab_log:
    st.markdown('<div class="slabel">Log journalier</div>', unsafe_allow_html=True)
    if trades_df.empty:
        st.info("Aucun trade — baisse band_k, abs_vol_mult ou min_hawkes_imbalance.")
    else:
        def _color_result(val):
            return "color:#00ff88" if val == "WIN" else "color:#ff3366"

        st.dataframe(
            trades_df[[
                "entry_time","signal","entry","exit",
                "sl_pts","tp_pts","pnl_pts","pnl_$","result",
                "dev_entry","h_imb_bull","h_imb_bear","hurst",
            ]].style.map(_color_result, subset=["result"]),
            use_container_width=True, height=420,
        )
        st.download_button(
            "Télécharger CSV",
            trades_df.to_csv(index=False),
            "orderflow_trades.csv",
            "text/csv",
        )
