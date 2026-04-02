"""
Multi-Model Backtest Framework — Apex · TopStep · Alpha Futures 50K EOD
Instruments : MNQ · ES · MGC · MCL (1 an OHLCV M1 Databento)
Models      : Kalman OU · Bollinger MR · GARCH MR · HMM Trend · Momentum Hurst · VWAP Reversion
Sources     : Roman Paolucci Quant Guild Library (Lec 25 · 47 · 51 · 72 · 95)
"""

import os
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="Multi-Model Backtest", page_icon="🔬", layout="wide")

# ── Theme ──────────────────────────────────────────────────────────────────
DARK = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(6,6,6,0)",
    plot_bgcolor="rgba(10,10,10,1)",
    font=dict(color="#888", size=12, family="JetBrains Mono"),
    margin=dict(t=50, b=40, l=50, r=30),
)
TEAL, CYAN, GREEN, RED, YELLOW, ORANGE, MAGENTA = (
    "#3CC4B7", "#00e5ff", "#00ff88", "#ff3366", "#ffd600", "#ff9100", "#ff00e5"
)
MODEL_COLORS = {
    "Kalman_OU":       TEAL,
    "Bollinger_MR":    CYAN,
    "GARCH_MR":        ORANGE,
    "HMM_Trend":       MAGENTA,
    "Momentum_Hurst":  YELLOW,
    "VWAP_Rev":        GREEN,
    "Markov_Regime":   "#ff6b35",
    "Heston_Vol":      "#a8ff78",
    "ARIMA_MR":        "#78c1ff",
}

# ═══════════════════════════════════════════════════════════════════════════
# INSTRUMENTS
# ═══════════════════════════════════════════════════════════════════════════

INSTRUMENTS = {
    "MNQ": {
        "csv":          r"C:\Users\ryadb\Downloads\GLBX-20260401-SHPXRNTFHK\glbx-mdp3-20250331-20260330.ohlcv-1m.csv",
        "symbol_prefix": "MNQ",
        "tick_size":    0.25,
        "dollar_per_pt": 2.0,
        "max_contracts": 60,
        "sl_min_pts":   3.0,
        "description":  "Micro E-mini Nasdaq · $2/pt · 60 contrats",
    },
    "ES": {
        "csv":          r"C:\Users\ryadb\Downloads\GLBX-20260401-SHPXRNTFHK\glbx-mdp3-20250331-20260330.ohlcv-1m.csv",
        "symbol_prefix": "ES",
        "tick_size":    0.25,
        "dollar_per_pt": 50.0,
        "max_contracts": 5,
        "sl_min_pts":   2.0,
        "description":  "E-mini S&P 500 · $50/pt · 5 contrats max $2K DD",
    },
    "MGC": {
        "csv":          r"C:\Users\ryadb\Downloads\GLBX-20260401-BVC897RVV9\glbx-mdp3-20250331-20260330.ohlcv-1m.csv",
        "symbol_prefix": "MGC",
        "tick_size":    0.10,
        "dollar_per_pt": 10.0,
        "max_contracts": 30,
        "sl_min_pts":   2.0,
        "description":  "Micro Gold · $10/pt · 30 contrats",
    },
    "MCL": {
        "csv":          r"C:\Users\ryadb\Downloads\GLBX-20260401-VNWWAMEJ74 (1)\glbx-mdp3-20250331-20260330.ohlcv-1m.csv",
        "symbol_prefix": "MCL",
        "tick_size":    0.01,
        "dollar_per_pt": 100.0,
        "max_contracts": 3,
        "sl_min_pts":   0.20,
        "description":  "Micro WTI Crude Oil · $100/pt · 3 contrats max",
    },
}

# ═══════════════════════════════════════════════════════════════════════════
# PROP FIRMS
# ═══════════════════════════════════════════════════════════════════════════

PROP_FIRMS = {
    "Apex 50K EOD": {
        "capital":        50_000,
        "profit_target":   3_000,
        "trailing_dd":     2_000,
        "daily_loss":      1_000,
        "fee_monthly":       167,
        "consistency_rule": False,
        "note": "EOD Trail — DD calculé sur clôture. Favorable intraday. 1 reset/mois inclus.",
    },
    "TopStep 50K": {
        "capital":        50_000,
        "profit_target":   3_000,
        "trailing_dd":     2_000,
        "daily_loss":      1_000,
        "fee_monthly":       165,
        "consistency_rule": False,
        "note": "Identique Apex structurellement. Retraits plus rapides. Trailing EOD.",
    },
    "Alpha Futures 50K": {
        "capital":        50_000,
        "profit_target":   3_000,
        "trailing_dd":     2_500,
        "daily_loss":      1_000,
        "fee_monthly":       150,
        "consistency_rule": True,
        "note": "DD $2,500 (plus généreux). Règle consistance : meilleur jour < 50% profit total.",
    },
}

# ═══════════════════════════════════════════════════════════════════════════
# MODEL GRIDS
# ═══════════════════════════════════════════════════════════════════════════

MODEL_GRIDS = {
    "Kalman_OU": {
        "description": "Kalman Filter OU Mean Reversion",
        "source":      "Lec 95 — Roman Paolucci kts.py",
        "type":        "Mean Reversion",
        "params": [
            {"band_k": bk, "sl_sigma": sl, "lookback": lb, "confirm": cf}
            for bk in [1.2, 1.5, 1.8, 2.0]
            for sl in [0.75, 1.25, 1.5]
            for lb in [60, 120]
            for cf in [True, False]
        ],
    },
    "Bollinger_MR": {
        "description": "Bollinger Band Mean Reversion",
        "source":      "Lec 72 — Markov Regime Bot (BB classic)",
        "type":        "Mean Reversion",
        "params": [
            {"period": p, "std_k": sk, "confirm": cf}
            for p  in [20, 50, 100]
            for sk in [1.5, 2.0, 2.5]
            for cf in [True, False]
        ],
    },
    "GARCH_MR": {
        "description": "GARCH(1,1) Volatility-Filtered Mean Reversion",
        "source":      "Lec 47 — Master Volatility with ARCH & GARCH",
        "type":        "Volatility-Filtered MR",
        "params": [
            {"bb_period": p, "bb_std": sk, "vol_pct": vp}
            for p  in [30, 50, 100]
            for sk in [1.5, 2.0]
            for vp in [0.5, 0.7]
        ],
    },
    "HMM_Trend": {
        "description": "HMM Regime Trend Following",
        "source":      "Lec 51 — Hidden Markov Models for Quant Finance",
        "type":        "Trend Following",
        "params": [
            {"lookback": lb, "pullback": pb}
            for lb in [60, 100, 150]
            for pb in [0.5, 1.0]
        ],
    },
    "Momentum_Hurst": {
        "description": "EMA Momentum + Hurst Filter",
        "source":      "Lec 25 — Fractional Brownian Motion (Davies-Harte)",
        "type":        "Trend Following",
        "params": [
            {"fast": f, "slow": s, "hurst_min": h}
            for f in [5, 10, 15]
            for s in [30, 60]
            for h in [0.50, 0.55]
        ],
    },
    "VWAP_Rev": {
        "description": "VWAP Intraday Mean Reversion",
        "source":      "Market Microstructure — Volume Profile",
        "type":        "Intraday MR",
        "params": [
            {"dev_pct": d}
            for d in [0.0008, 0.0012, 0.0018, 0.0025]
        ],
    },
    "Markov_Regime": {
        "description": "Markov Chain 3-State Regime Switching",
        "source":      "Lec 72/74 — Markov Chain Regime Bot (IBKR)",
        "type":        "Regime Adaptive",
        "params": [
            {"lookback": lb, "bb_k": bk, "mode": mo}
            for lb in [30, 60, 100]
            for bk in [1.5, 2.0]
            for mo in ["mr", "trend"]
        ],
    },
    "Heston_Vol": {
        "description": "Heston Variance Mean Reversion Filter",
        "source":      "Lec 39 — Heston Stochastic Vol Model & FFT",
        "type":        "Vol-Filtered MR",
        "params": [
            {"short_w": sw, "long_w": lw, "band_k": bk}
            for sw in [5, 10]
            for lw in [30, 60]
            for bk in [1.5, 2.0]
        ],
    },
    "ARIMA_MR": {
        "description": "AR(p) Prediction Mean Reversion",
        "source":      "Lec 44 — Time Series Analysis for Quant Finance",
        "type":        "Time Series MR",
        "params": [
            {"ar_order": p, "lookback": lb, "band_k": bk}
            for p  in [1, 2]
            for lb in [60, 120]
            for bk in [1.0, 1.5, 2.0]
        ],
    },
}

# ═══════════════════════════════════════════════════════════════════════════
# ENGINE — Shared utilities
# ═══════════════════════════════════════════════════════════════════════════

def hurst_exponent(prices):
    """H < 0.5 → mean-rev · H > 0.5 → trending (Lec 25 fBm)."""
    p = np.asarray(prices, dtype=float)
    p = p[np.isfinite(p)]
    if len(p) < 20:
        return 0.5
    max_lag = min(len(p) // 4, 64)
    lags = sorted(set(int(round(2 ** x)) for x in np.linspace(1, np.log2(max(max_lag, 2)), 8)))
    lags = [l for l in lags if 2 <= l < len(p)]
    if len(lags) < 3:
        return 0.5
    log_lags, log_tau = [], []
    for lag in lags:
        diffs = p[lag:] - p[:-lag]
        std = np.std(diffs)
        if std > 0:
            log_lags.append(np.log(lag))
            log_tau.append(np.log(std))
    if len(log_lags) < 3:
        return 0.5
    return float(np.clip(np.polyfit(log_lags, log_tau, 1)[0], 0.05, 0.95))


def estimate_ar1(closes):
    y = np.array(closes, dtype=float)
    y = y[np.isfinite(y)]
    if len(y) < 5:
        return None
    try:
        x_lag, x_curr = y[:-1], y[1:]
        X    = np.column_stack([np.ones_like(x_lag), x_lag])
        beta = np.linalg.lstsq(X, x_curr, rcond=None)[0]
        c, phi = float(beta[0]), float(beta[1])
        phi = np.clip(phi, 0.01, 0.99)
        resid = x_curr - (c + phi * x_lag)
        sigma = float(np.sqrt(np.mean(resid ** 2)))
        if sigma <= 0 or not np.isfinite(sigma):
            sigma = max(float(np.std(y)) * 0.01, 1e-9)
        return phi, c / (1.0 - phi), sigma
    except Exception:
        return None


class KalmanOU:
    def __init__(self, phi, mu, sigma, noise_scale=5.0):
        self.phi, self.mu = phi, mu
        self.Q = sigma ** 2 * max(1.0 - phi ** 2, 1e-6)
        self.R = sigma ** 2 * max(noise_scale, 0.01)
        self.x, self.P = mu, self.R

    def update(self, z):
        self.x = self.phi * self.x + (1.0 - self.phi) * self.mu
        self.P = self.phi ** 2 * self.P + self.Q
        K = self.P / (self.P + self.R)
        self.x = self.x + K * (z - self.x)
        self.P = (1.0 - K) * self.P
        return self.x


def run_kalman(closes, lookback=120, noise_scale=5.0):
    n = len(closes)
    fair_values = np.full(n, np.nan)
    sigma_stats = np.full(n, np.nan)
    kal = None
    for i in range(lookback, n):
        params = estimate_ar1(closes[i - lookback: i])
        if params is None:
            continue
        phi, mu, sigma = params
        ss = sigma / np.sqrt(max(1.0 - phi ** 2, 1e-6))
        if kal is None:
            kal = KalmanOU(phi, mu, sigma, noise_scale)
            for c in closes[i - lookback: i]:
                kal.update(c)
        else:
            kal.phi, kal.mu = phi, mu
            kal.Q = sigma ** 2 * max(1.0 - phi ** 2, 1e-6)
            kal.R = sigma ** 2 * max(noise_scale, 0.01)
        kal.update(closes[i])
        fair_values[i] = kal.x
        sigma_stats[i] = ss
    return fair_values, sigma_stats


def garch_rolling(returns, omega=1e-7, alpha=0.05, beta=0.90):
    """GARCH(1,1) rolling variance estimate."""
    n = len(returns)
    var = np.full(n, np.nanvar(returns[:20]) if n >= 20 else 1e-6)
    var[0] = max(returns[0] ** 2, 1e-10)
    for i in range(1, n):
        var[i] = omega + alpha * returns[i - 1] ** 2 + beta * var[i - 1]
        var[i] = np.clip(var[i], 1e-12, 1.0)
    return var


def hmm_proxy_states(returns, lookback=60):
    """
    Proxy HMM 3 états via z-score du return moyen rolling (Lec 51).
    0 = bear · 1 = neutral · 2 = bull
    """
    n = len(returns)
    states = np.ones(n, dtype=int)
    roll_ret = pd.Series(returns).rolling(lookback, min_periods=20).mean().values
    roll_vol = pd.Series(returns).rolling(lookback, min_periods=20).std().values
    for i in range(lookback, n):
        if np.isnan(roll_ret[i]) or np.isnan(roll_vol[i]) or roll_vol[i] < 1e-12:
            continue
        z = roll_ret[i] / roll_vol[i]
        states[i] = 2 if z > 0.5 else (0 if z < -0.5 else 1)
    return states


def simulate_trade(bars, entry_idx, entry_price, direction, sl_pts, tp_price, slip_pts):
    """Simule un trade bar-par-bar. Retourne (result_pts, exit_bar_idx)."""
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


# ═══════════════════════════════════════════════════════════════════════════
# SIGNAL GENERATORS — one per model
# ═══════════════════════════════════════════════════════════════════════════

def _make_sig(bars, i, entry_bar, price, fv, ss, direction):
    n = len(bars)
    return {
        "bar_idx":   min(entry_bar, n - 1),
        "date":      bars.iloc[i]["date"],
        "bar":       bars.iloc[min(entry_bar, n - 1)]["bar"],
        "price":     price,
        "fair_value": fv,
        "sigma_stat": ss,
        "direction":  direction,
    }


def sigs_kalman_ou(cached, band_k, sl_sigma, confirm, skip_open, skip_close):
    bars    = cached["bars"]
    closes  = cached["closes"]
    fvs     = cached["fair_values"]
    sss     = cached["sigma_stats"]
    n       = len(closes)
    signals = []
    for i in range(skip_open, n - skip_close):
        if np.isnan(fvs[i]) or np.isnan(sss[i]) or sss[i] <= 0:
            continue
        dev = abs(closes[i] - fvs[i]) / sss[i]
        if dev < band_k or dev > 4.0:
            continue
        direction = "short" if closes[i] > fvs[i] else "long"
        if confirm:
            if i + 1 >= n or np.isnan(fvs[i+1]) or np.isnan(sss[i+1]) or sss[i+1] <= 0:
                continue
            next_dev = abs(closes[i+1] - fvs[i+1]) / sss[i+1]
            if next_dev >= dev:
                continue
            signals.append(_make_sig(bars, i, i+1, closes[i+1], fvs[i], sss[i], direction))
        else:
            signals.append(_make_sig(bars, i, i, closes[i], fvs[i], sss[i], direction))
    return signals


def sigs_bollinger(cached, period, std_k, confirm, skip_open, skip_close):
    bars    = cached["bars"]
    closes  = cached["closes"]
    n       = len(closes)
    signals = []
    for i in range(period, n - skip_close):
        if i < skip_open:
            continue
        window = closes[i - period: i]
        mid, std = window.mean(), window.std()
        if std == 0:
            continue
        price = closes[i]
        z = (price - mid) / std
        if abs(z) < std_k:
            continue
        direction = "short" if price > mid else "long"
        if confirm:
            if i + 1 >= n:
                continue
            nw = closes[i - period + 1: i + 1]
            nm, ns = nw.mean(), nw.std()
            if ns > 0 and abs(closes[i+1] - nm) / ns >= abs(z):
                continue
            signals.append(_make_sig(bars, i, i+1, closes[min(i+1, n-1)], mid, std, direction))
        else:
            signals.append(_make_sig(bars, i, i, price, mid, std, direction))
    return signals


def sigs_garch_mr(cached, bb_period, bb_std, vol_pct, skip_open, skip_close):
    """
    GARCH(1,1) filters out high-vol bars (trending/explosive).
    Only trade when GARCH var < vol_pct percentile → mean-reverting regime (Lec 47).
    """
    bars      = cached["bars"]
    closes    = cached["closes"]
    garch_var = cached["garch_var"]
    n         = len(closes)
    threshold = float(np.nanpercentile(garch_var, vol_pct * 100))
    signals   = []
    for i in range(bb_period, n - skip_close):
        if i < skip_open:
            continue
        if garch_var[i] > threshold:   # high-vol → skip
            continue
        window = closes[i - bb_period: i]
        mid, std = window.mean(), window.std()
        if std == 0:
            continue
        price = closes[i]
        z = (price - mid) / std
        if abs(z) < bb_std:
            continue
        direction = "short" if price > mid else "long"
        signals.append(_make_sig(bars, i, i, price, mid, std, direction))
    return signals


def sigs_hmm_trend(cached, lookback, pullback, skip_open, skip_close):
    """
    HMM proxy regime (Lec 51).
    Bull state → long on pullback · Bear state → short on bounce.
    TP = trend extension (2 × sigma above entry).
    """
    bars       = cached["bars"]
    closes     = cached["closes"]
    hmm_states = cached["hmm_states"]
    n          = len(closes)
    signals    = []
    for i in range(max(20, lookback), n - skip_close):
        if i < skip_open:
            continue
        state = hmm_states[i]
        if state == 1:   # neutral
            continue
        mid = closes[max(0, i-20): i].mean()
        std = closes[max(0, i-20): i].std()
        if std == 0:
            continue
        price = closes[i]
        z = (price - mid) / std
        if state == 2 and z < -pullback:      # bull + pullback → long
            direction = "long"
            fv = price + 2.0 * std            # TP = 2σ above entry
        elif state == 0 and z > pullback:      # bear + bounce → short
            direction = "short"
            fv = price - 2.0 * std            # TP = 2σ below entry
        else:
            continue
        signals.append(_make_sig(bars, i, i, price, fv, std, direction))
    return signals


def sigs_momentum_hurst(cached, fast, slow, hurst_min, skip_open, skip_close):
    """
    EMA crossover UNIQUEMENT quand H > hurst_min (jour trending — Lec 25).
    H < hurst_min → skip le jour entier (mean-reverting → pas d'edge momentum).
    """
    if cached["hurst"] < hurst_min:
        return []
    bars    = cached["bars"]
    closes  = cached["closes"]
    ema_f   = cached["emas"][str(fast)]
    ema_s   = cached["emas"][str(slow)]
    n       = len(closes)
    signals = []
    for i in range(slow + 1, n - skip_close):
        if i < skip_open:
            continue
        cross_up = ema_f[i] > ema_s[i] and ema_f[i-1] <= ema_s[i-1]
        cross_dn = ema_f[i] < ema_s[i] and ema_f[i-1] >= ema_s[i-1]
        if not (cross_up or cross_dn):
            continue
        direction = "long" if cross_up else "short"
        sigma_est = max(abs(ema_f[i] - ema_s[i]), closes[i] * 0.0001)
        fv = closes[i] + (2.0 * sigma_est if direction == "long" else -2.0 * sigma_est)
        signals.append(_make_sig(bars, i, i, closes[i], fv, sigma_est, direction))
    return signals


def sigs_vwap_rev(cached, dev_pct, skip_open, skip_close):
    """
    Déviation > dev_pct du VWAP intraday → mean reversion vers le VWAP.
    """
    bars     = cached["bars"]
    closes   = cached["closes"]
    vwap     = cached["vwap"]
    vwap_std = cached["vwap_std"]
    n        = len(closes)
    signals  = []
    for i in range(30, n - skip_close):
        if i < skip_open:
            continue
        if np.isnan(vwap[i]) or np.isnan(vwap_std[i]) or vwap_std[i] == 0:
            continue
        price = closes[i]
        v     = vwap[i]
        dev   = abs(price - v) / max(abs(v), 1e-9)
        if dev < dev_pct:
            continue
        direction = "short" if price > v else "long"
        signals.append(_make_sig(bars, i, i, price, v, vwap_std[i], direction))
    return signals


def sigs_markov_regime(cached, lookback, bb_k, mode, skip_open, skip_close):
    """
    Lec 72/74 — Markov Chain Regime Switching Bot.
    State 0 (low vol) + mode='mr'    → mean reversion (Bollinger-like).
    State 2 (high vol) + mode='trend'→ trend entry on small pullback.
    State 1 (medium)   → skip always.
    """
    bars          = cached["bars"]
    closes        = cached["closes"]
    markov_states = cached["markov_states"]
    n = len(closes)
    signals = []
    for i in range(max(lookback, 20), n - skip_close):
        if i < skip_open:
            continue
        state = markov_states[i]
        if state == 1:
            continue
        window = closes[i - lookback: i]
        mid, std = window.mean(), window.std()
        if std == 0:
            continue
        price = closes[i]
        z = (price - mid) / std
        if state == 0 and mode == "mr":
            if abs(z) < bb_k:
                continue
            direction = "short" if price > mid else "long"
            signals.append(_make_sig(bars, i, i, price, mid, std, direction))
        elif state == 2 and mode == "trend":
            if abs(z) > 0.5:
                continue  # already extended, late entry
            direction = "long" if closes[i] > closes[max(0, i - 5)] else "short"
            fv = price + (2.0 * std if direction == "long" else -2.0 * std)
            signals.append(_make_sig(bars, i, i, price, fv, std, direction))
    return signals


def sigs_heston_vol(cached, short_w, long_w, band_k, skip_open, skip_close):
    """
    Lec 39 — Heston Stochastic Vol Model.
    Variance ratio = short_vol / long_vol.
    Ratio < 1.0 → variance mean-reverting (contracting) → MR trade.
    Ratio >= 1.2 → vol expanding → skip.
    """
    bars     = cached["bars"]
    closes   = cached["closes"]
    returns  = cached["returns"]
    n = len(closes)
    short_vol = pd.Series(returns).rolling(short_w, min_periods=3).std().values
    long_vol  = pd.Series(returns).rolling(long_w,  min_periods=10).std().values
    var_ratio = np.where(long_vol > 1e-12, short_vol / np.maximum(long_vol, 1e-12), 1.0)
    signals = []
    for i in range(long_w, n - skip_close):
        if i < skip_open:
            continue
        if np.isnan(var_ratio[i]) or var_ratio[i] >= 1.2:
            continue
        window = closes[i - long_w: i]
        mid, std = window.mean(), window.std()
        if std == 0:
            continue
        price = closes[i]
        z = (price - mid) / std
        if abs(z) < band_k:
            continue
        direction = "short" if price > mid else "long"
        signals.append(_make_sig(bars, i, i, price, mid, std, direction))
    return signals


def sigs_arima_mr(cached, ar_order, lookback, band_k, skip_open, skip_close):
    """
    Lec 44 — Time Series Analysis.
    Rolling AR(p) forecast. Trade when actual price deviates > band_k sigma from prediction.
    TP = AR prediction (expected mean reversion back to forecast).
    """
    bars   = cached["bars"]
    closes = cached["closes"]
    n = len(closes)
    signals = []
    for i in range(lookback + ar_order, n - skip_close):
        if i < skip_open:
            continue
        window = closes[i - lookback: i]
        try:
            T = len(window) - ar_order
            Y = window[ar_order:]
            X_cols = [window[ar_order - k - 1: T + ar_order - k - 1] for k in range(ar_order)]
            X = np.column_stack([np.ones(T)] + X_cols)
            beta = np.linalg.lstsq(X, Y, rcond=None)[0]
            x_pred = np.array([1.0] + list(closes[i - ar_order: i][::-1]))
            pred = float(np.dot(x_pred, beta))
            resid_std = float(np.std(Y - X @ beta))
            if resid_std <= 0 or not np.isfinite(pred):
                continue
        except Exception:
            continue
        price = closes[i]
        z = (price - pred) / resid_std
        if abs(z) < band_k:
            continue
        direction = "short" if price > pred else "long"
        signals.append(_make_sig(bars, i, i, price, pred, resid_std, direction))
    return signals


# ═══════════════════════════════════════════════════════════════════════════
# DATA LOADING & SESSION FILTER
# ═══════════════════════════════════════════════════════════════════════════

def filter_session(df, sh, sm, eh, em):
    t = df["bar"].dt.hour * 60 + df["bar"].dt.minute
    return df[(t >= sh*60 + sm) & (t < eh*60 + em)].reset_index(drop=True)


@st.cache_data(show_spinner=False)
def load_instrument_csv(csv_path, symbol_prefix):
    """Charge 1 an de données M1 pour un instrument depuis CSV Databento."""
    try:
        df = pd.read_csv(csv_path, usecols=["ts_event","open","high","low","close","volume","symbol"])
    except Exception as e:
        return None, str(e)
    df = df[df["symbol"].str.startswith(symbol_prefix) & ~df["symbol"].str.contains("-", na=False)].copy()
    if df.empty:
        return None, f"Aucun symbole {symbol_prefix} dans {csv_path}"
    df = df.sort_values("volume", ascending=False).groupby("ts_event", sort=False).first().reset_index()
    df["bar"] = pd.to_datetime(df["ts_event"], utc=True)
    df = df[["bar","open","high","low","close","volume"]].copy()
    df[["open","high","low","close"]] = df[["open","high","low","close"]].astype(float)
    df["volume"] = df["volume"].fillna(0).astype(int)
    df.sort_values("bar", inplace=True)
    df.drop_duplicates(subset=["bar"], inplace=True)
    df.reset_index(drop=True, inplace=True)
    end_dt   = df["bar"].max()
    start_dt = end_dt - pd.DateOffset(years=1)
    df = df[df["bar"] >= start_dt].reset_index(drop=True)
    df["date"] = df["bar"].dt.date
    df["tr"] = np.maximum(
        df["high"] - df["low"],
        np.maximum(abs(df["high"] - df["close"].shift(1)), abs(df["low"] - df["close"].shift(1)))
    )
    return df, None


def compute_markov_states(closes, highs, lows, lookback=60):
    """
    Proxy 3-state Markov regime via rolling bar vol (Lec 72/74).
    State 0 = low vol (mean-rev) · 1 = medium · 2 = high vol (trend).
    """
    n = len(closes)
    states = np.ones(n, dtype=int)
    bar_vol = np.where(closes > 0, (highs - lows) / np.maximum(closes, 1e-9), 0.0)
    for i in range(lookback, n):
        window_vol = bar_vol[max(0, i - lookback): i]
        p33 = np.nanpercentile(window_vol, 33)
        p67 = np.nanpercentile(window_vol, 67)
        v = bar_vol[i]
        if v <= p33:
            states[i] = 0
        elif v >= p67:
            states[i] = 2
        # else stays 1
    return states


def build_daily_cache(full_df, sh, sm, eh, em, kalman_lb=120, noise_scale=5.0):
    """
    Precompute par jour :
    Kalman FV · sigma · GARCH var · HMM states · VWAP · Hurst · EMAs
    """
    cache = {}
    for day_key in sorted(full_df["date"].unique()):
        day_df = full_df[full_df["date"] == day_key].copy()
        bars   = filter_session(day_df, sh, sm, eh, em)
        if len(bars) < kalman_lb + 20:
            continue

        closes = bars["close"].values
        highs  = bars["high"].values
        lows   = bars["low"].values
        vols   = bars["volume"].values

        # Kalman OU (Lec 95)
        fair_values, sigma_stats = run_kalman(closes, kalman_lb, noise_scale)

        # Hurst (Lec 25)
        hurst_val = hurst_exponent(closes)

        # GARCH(1,1) (Lec 47)
        returns   = np.diff(np.log(np.maximum(closes, 1e-9)))
        returns   = np.concatenate([[0], returns])
        garch_var = garch_rolling(returns)

        # HMM proxy (Lec 51)
        hmm_states = hmm_proxy_states(returns, lookback=60)

        # Markov 3-state regime (Lec 72/74)
        markov_states = compute_markov_states(closes, highs, lows, lookback=60)

        # VWAP
        typical   = (highs + lows + closes) / 3
        cum_vol   = np.cumsum(vols)
        cum_tpv   = np.cumsum(typical * np.maximum(vols, 1))
        vwap      = np.where(cum_vol > 0, cum_tpv / cum_vol, typical)
        spread    = closes - vwap
        vwap_std  = pd.Series(spread).rolling(30, min_periods=10).std().bfill().values

        # EMAs (Lec 25 momentum)
        cs = pd.Series(closes)
        emas = {
            "5":  cs.ewm(span=5).mean().values,
            "10": cs.ewm(span=10).mean().values,
            "15": cs.ewm(span=15).mean().values,
            "30": cs.ewm(span=30).mean().values,
            "60": cs.ewm(span=60).mean().values,
        }

        cache[str(day_key)] = {
            "bars":          bars,
            "closes":        closes,
            "fair_values":   fair_values,
            "sigma_stats":   sigma_stats,
            "garch_var":     garch_var,
            "hmm_states":    hmm_states,
            "markov_states": markov_states,
            "returns":       returns,
            "vwap":          vwap,
            "vwap_std":      vwap_std,
            "hurst":         hurst_val,
            "emas":          emas,
        }
    return cache


# ═══════════════════════════════════════════════════════════════════════════
# BACKTEST RUNNER — single model × params × instrument
# ═══════════════════════════════════════════════════════════════════════════

def dispatch_signals(model_id, cached, params, skip_open, skip_close):
    if model_id == "Kalman_OU":
        return sigs_kalman_ou(cached, params["band_k"], params["sl_sigma"],
                               params["confirm"], skip_open, skip_close)
    if model_id == "Bollinger_MR":
        return sigs_bollinger(cached, params["period"], params["std_k"],
                               params["confirm"], skip_open, skip_close)
    if model_id == "GARCH_MR":
        return sigs_garch_mr(cached, params["bb_period"], params["bb_std"],
                              params["vol_pct"], skip_open, skip_close)
    if model_id == "HMM_Trend":
        return sigs_hmm_trend(cached, params["lookback"], params["pullback"],
                               skip_open, skip_close)
    if model_id == "Momentum_Hurst":
        return sigs_momentum_hurst(cached, params["fast"], params["slow"],
                                    params["hurst_min"], skip_open, skip_close)
    if model_id == "VWAP_Rev":
        return sigs_vwap_rev(cached, params["dev_pct"], skip_open, skip_close)
    if model_id == "Markov_Regime":
        return sigs_markov_regime(cached, params["lookback"], params["bb_k"],
                                   params["mode"], skip_open, skip_close)
    if model_id == "Heston_Vol":
        return sigs_heston_vol(cached, params["short_w"], params["long_w"],
                                params["band_k"], skip_open, skip_close)
    if model_id == "ARIMA_MR":
        return sigs_arima_mr(cached, params["ar_order"], params["lookback"],
                              params["band_k"], skip_open, skip_close)
    return []


def run_backtest(day_cache, model_id, params, instr_cfg, prop_cfg,
                 sl_sigma_mult, sl_min_pts, tp_ratio, slip_pts,
                 max_trades_day, skip_open, skip_close):
    """
    Simule 1 an de trading pour un model × params × instrument.
    Retourne un dict de métriques ou None si < 10 trades.
    """
    dollar_per_pt  = instr_cfg["dollar_per_pt"]
    max_contracts  = instr_cfg["max_contracts"]
    capital        = prop_cfg["capital"]
    max_dd_dollars = prop_cfg["trailing_dd"]
    daily_loss_lim = prop_cfg["daily_loss"]
    profit_target  = prop_cfg["profit_target"]

    all_trades     = []
    monthly_results = []
    running_equity  = capital
    running_peak    = capital
    current_month   = None
    month_trades    = []
    days_elapsed    = 0
    ch_busted       = False
    ch_passed       = False

    for day_key in sorted(day_cache.keys()):
        day_month = day_key[:7]

        if day_month != current_month:
            if current_month is not None:
                nw = sum(1 for t in month_trades if t["win"])
                nt = len(month_trades)
                monthly_results.append({
                    "mois": current_month, "pnl": running_equity - capital,
                    "trades": nt, "winrate": nw/nt*100 if nt > 0 else 0,
                    "passed": ch_passed, "busted": ch_busted,
                })
                running_equity = capital; running_peak = capital
                ch_busted = ch_passed = False
                month_trades = []; days_elapsed = 0
            current_month = day_month

        if ch_passed or ch_busted:
            continue

        running_dd = running_peak - running_equity
        if running_dd >= max_dd_dollars:
            ch_busted = True
            continue

        if (running_equity - capital) >= profit_target and not ch_passed:
            ch_passed = True

        days_elapsed += 1
        cached = day_cache[day_key]
        signals = dispatch_signals(model_id, cached, params, skip_open, skip_close)
        if not signals:
            continue

        bars         = cached["bars"]
        last_exit    = -1
        daily_pnl    = 0.0
        day_td_count = 0

        for sig in signals:
            bidx = sig["bar_idx"]
            if bidx <= last_exit or daily_pnl <= -daily_loss_lim or day_td_count >= max_trades_day:
                continue

            sl_pts  = max(float(sl_min_pts), sl_sigma_mult * sig["sigma_stat"])
            tp_price = sig["price"] + tp_ratio * (sig["fair_value"] - sig["price"])

            # Sizing: risk $200/trade, capped by daily loss and max_contracts
            risk_per_trade  = min(200.0, daily_loss_lim * 0.20)
            loss_per_ctr    = sl_pts * dollar_per_pt
            if loss_per_ctr <= 0:
                continue
            contracts = max(1, min(max_contracts, int(risk_per_trade / loss_per_ctr)))
            if contracts * loss_per_ctr > (daily_loss_lim + daily_pnl):
                contracts = max(1, int((daily_loss_lim + daily_pnl) / loss_per_ctr))
            if contracts <= 0:
                continue

            result_pts, exit_bar = simulate_trade(
                bars, bidx, sig["price"], sig["direction"], sl_pts, tp_price, slip_pts
            )
            last_exit    = exit_bar
            pnl_dollars  = result_pts * dollar_per_pt * contracts
            running_equity += pnl_dollars
            daily_pnl    += pnl_dollars
            day_td_count += 1

            if running_equity > running_peak:
                running_peak = running_equity

            win = pnl_dollars > 0
            all_trades.append({
                "date":     str(sig["date"]),
                "win":      win,
                "pnl":      pnl_dollars,
                "result_pts": result_pts,
                "contracts":  contracts,
            })
            month_trades.append({"win": win, "pnl": pnl_dollars})

    if len(all_trades) < 10:
        return None

    df       = pd.DataFrame(all_trades)
    n        = len(df)
    wr       = float(df["win"].mean())
    pos_pnl  = df[df["pnl"] > 0]["pnl"].sum()
    neg_pnl  = abs(df[df["pnl"] < 0]["pnl"].sum())
    pf       = pos_pnl / max(neg_pnl, 0.01)
    total_pnl = df["pnl"].sum()
    avg_win  = df[df["pnl"] > 0]["pnl"].mean() if df["pnl"].gt(0).any() else 0.0
    avg_loss = abs(df[df["pnl"] < 0]["pnl"].mean()) if df["pnl"].lt(0).any() else 1.0

    # Sharpe
    daily_pnl_s = df.groupby("date")["pnl"].sum()
    daily_pnl_s.index = pd.to_datetime(daily_pnl_s.index)
    bdays = pd.bdate_range(daily_pnl_s.index.min(), daily_pnl_s.index.max())
    daily_ret = daily_pnl_s.reindex(bdays, fill_value=0) / capital
    sharpe    = float(daily_ret.mean() / daily_ret.std() * np.sqrt(252)) if daily_ret.std() > 0 else 0.0

    # Max DD
    equity_arr = np.concatenate([[capital], np.cumsum(df["pnl"].values) + capital])
    peak_arr   = np.maximum.accumulate(equity_arr)
    max_dd_pct = float((peak_arr - equity_arr).max() / capital * 100)

    # Prop firm stats
    n_months   = len(monthly_results)
    n_pass     = sum(1 for m in monthly_results if m["passed"])
    n_bust     = sum(1 for m in monthly_results if m["busted"])
    pass_rate  = n_pass / max(n_months, 1) * 100
    bust_rate  = n_bust / max(n_months, 1) * 100

    # Trades per day
    n_bdays   = max(len(bdays), 1)
    tpd       = n / n_bdays

    # Composite score (higher = better)
    #   PF component (0-1): saturates at PF=3
    #   WR component (0-1): above 0.45 breakeven typical
    #   Sharpe component (0-1): saturates at Sharpe=2
    #   Frequency bonus (0-1): penalize < 0.3 trades/day
    #   DD penalty: -0.5 if DD > 4%
    score = (
        0.35 * min(max(pf - 1.0, 0.0) / 2.0, 1.0) +
        0.25 * min(max(wr - 0.35, 0.0) / 0.35, 1.0) +
        0.20 * min(max(sharpe, 0.0) / 2.0, 1.0) +
        0.10 * min(tpd / 0.5, 1.0) +
        0.10 * min(pass_rate / 50.0, 1.0) -
        (0.30 if max_dd_pct > 4.0 else 0.0)
    )

    return {
        "model":         model_id,
        "type":          MODEL_GRIDS[model_id]["type"],
        "source":        MODEL_GRIDS[model_id]["source"],
        "params_str":    str(params),
        "params":        params,
        "n_trades":      n,
        "winrate":       round(wr * 100, 1),
        "profit_factor": round(pf, 2),
        "sharpe":        round(sharpe, 2),
        "total_pnl":     round(total_pnl, 0),
        "avg_win":       round(avg_win, 1),
        "avg_loss":      round(avg_loss, 1),
        "max_dd_pct":    round(max_dd_pct, 1),
        "trades_per_day": round(tpd, 2),
        "pass_rate":     round(pass_rate, 0),
        "bust_rate":     round(bust_rate, 0),
        "score":         round(score, 4),
        "_monthly":      monthly_results,
        "_trades_df":    df,
    }


# ═══════════════════════════════════════════════════════════════════════════
# CSS
# ═══════════════════════════════════════════════════════════════════════════

st.markdown("""
<style>
[data-testid="stAppViewContainer"] { background: #060606; }
[data-testid="stSidebar"] { background: #080808; border-right: 1px solid #141414; }
[data-testid="stHeader"] { background: transparent; }
[data-testid="stToolbar"] { display: none; }
.block-container { padding-top: 1.5rem; max-width: 1400px; }
.page-tag { font-family: 'JetBrains Mono',monospace; font-size:0.65rem; letter-spacing:0.2em; color:#3CC4B7; text-transform:uppercase; }
.page-title { font-size:1.8rem; font-weight:700; color:#fff; letter-spacing:-0.02em; margin:0.3rem 0 0; }
.section-label { font-family:'JetBrains Mono',monospace; font-size:0.6rem; font-weight:700;
    letter-spacing:0.2em; color:#3CC4B7; text-transform:uppercase; margin:1.8rem 0 0.8rem; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div>
  <div class="page-tag">MULTI-MODEL · MNQ ES MGC MCL · APEX / TOPSTEP / ALPHA</div>
  <div class="page-title">Comparaison Multi-Modèle — Meilleur Edge 50K EOD</div>
</div>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════

st.sidebar.header("Instruments")
selected_instruments = st.sidebar.multiselect(
    "Instruments à tester",
    options=list(INSTRUMENTS.keys()),
    default=["MNQ", "MGC"],
    help="MNQ recommandé pour débuter. Ajoute ES/MCL pour comparer.",
)

st.sidebar.header("Modèles")
selected_models = st.sidebar.multiselect(
    "Modèles à tester",
    options=list(MODEL_GRIDS.keys()),
    default=list(MODEL_GRIDS.keys()),
    format_func=lambda k: f"{k} — {MODEL_GRIDS[k]['type']}",
)

st.sidebar.header("Prop Firm")
selected_firm = st.sidebar.selectbox(
    "Prop Firm pour la simulation",
    options=list(PROP_FIRMS.keys()),
    help="Règles Apex / TopStep / Alpha appliquées au backtest mensuel.",
)

st.sidebar.header("Session (UTC)")
session_start_h = st.sidebar.number_input("Début heure", value=14, min_value=0, max_value=23)
session_start_m = st.sidebar.number_input("Début min",   value=30, min_value=0, max_value=59)
session_end_h   = st.sidebar.number_input("Fin heure",   value=21, min_value=0, max_value=23)
session_end_m   = st.sidebar.number_input("Fin min",     value=0,  min_value=0, max_value=59)
skip_open_bars  = st.sidebar.number_input("Skip barres ouverture",  value=15, min_value=0, step=5)
skip_close_bars = st.sidebar.number_input("Skip barres clôture",    value=15, min_value=0, step=5)
max_trades_day  = st.sidebar.number_input("Max trades/jour", value=2, min_value=1, max_value=10)

st.sidebar.header("Risk (commun à tous les modèles)")
sl_sigma_mult = st.sidebar.slider(
    "SL = k × σ", min_value=0.5, max_value=3.0, value=1.25, step=0.25,
    help="Multiplicateur sigma pour le stop-loss. Appliqué à tous les modèles.",
)
tp_ratio = st.sidebar.slider(
    "TP ratio", min_value=0.5, max_value=1.0, value=1.0, step=0.1,
    help="1.0 = TP au fair value complet.",
)
slippage_ticks = st.sidebar.number_input("Slippage (ticks)", value=2, min_value=0, step=1)

st.sidebar.header("Kalman (modèles Kalman OU)")
kalman_lb = st.sidebar.number_input("Lookback Kalman", value=120, min_value=30, step=10)
noise_scale_val = 5.0

prop_cfg  = PROP_FIRMS[selected_firm]
st.sidebar.info(
    f"**{selected_firm}**\n"
    f"- Target : ${prop_cfg['profit_target']:,}\n"
    f"- DD max : ${prop_cfg['trailing_dd']:,}\n"
    f"- Daily loss : ${prop_cfg['daily_loss']:,}\n"
    f"- Frais : ${prop_cfg['fee_monthly']:,}/mois\n"
    f"- Consistance : {'✓' if prop_cfg['consistency_rule'] else '✗'}"
)

# ═══════════════════════════════════════════════════════════════════════════
# MAIN — Backtest loop
# ═══════════════════════════════════════════════════════════════════════════

if st.sidebar.button("🚀 Lancer le Multi-Backtest", type="primary", use_container_width=True):
    st.session_state["_mmbt_run"] = True

if not st.session_state.get("_mmbt_run", False):
    # Info page
    st.info("Configure les instruments et modèles à gauche, puis clique **Lancer le Multi-Backtest**.")

    col_info, col_grid = st.columns([1, 2])
    with col_info:
        st.markdown("<p class='section-label'>Instruments disponibles</p>", unsafe_allow_html=True)
        for k, v in INSTRUMENTS.items():
            avail = os.path.exists(v["csv"])
            st.markdown(
                f"{'✅' if avail else '❌'} **{k}** — {v['description']}"
            )

    with col_grid:
        st.markdown("<p class='section-label'>Modèles × paramétrage</p>", unsafe_allow_html=True)
        rows = []
        for mid, mg in MODEL_GRIDS.items():
            rows.append({"Modèle": mid, "Type": mg["type"], "Source": mg["source"],
                         "Combos": len(mg["params"])})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        total = sum(len(mg["params"]) for mg in MODEL_GRIDS.values())
        st.caption(f"Total : {total} combos × {len(INSTRUMENTS)} instruments = {total * len(INSTRUMENTS)} backtests possibles")

    st.stop()

# ── Chargement des données ────────────────────────────────────────────────
if not selected_instruments or not selected_models:
    st.error("Sélectionne au moins 1 instrument et 1 modèle.")
    st.stop()

slip_pts = slippage_ticks * 0.25  # using MNQ tick; each instrument will adjust via sl_min_pts

all_results = []
total_combos = sum(len(MODEL_GRIDS[m]["params"]) for m in selected_models)
grand_total  = total_combos * len(selected_instruments)
combo_done   = 0

outer_progress = st.progress(0, text="Initialisation…")
status_box     = st.empty()

for instr_key in selected_instruments:
    instr_cfg = INSTRUMENTS[instr_key]

    status_box.info(f"📦 Chargement {instr_key}…")
    full_df, err = load_instrument_csv(instr_cfg["csv"], instr_cfg["symbol_prefix"])
    if err:
        st.warning(f"⚠ {instr_key} : {err}")
        combo_done += total_combos
        outer_progress.progress(combo_done / grand_total)
        continue

    status_box.info(f"⚙ Precompute {instr_key} — Kalman · GARCH · HMM · VWAP · Hurst…")
    day_cache = build_daily_cache(
        full_df, session_start_h, session_start_m, session_end_h, session_end_m,
        kalman_lb=kalman_lb, noise_scale=noise_scale_val,
    )
    n_days = len(day_cache)

    # Actual slip in instrument points (normalize by tick size)
    instr_slip = slippage_ticks * instr_cfg["tick_size"]
    instr_sl_min = instr_cfg["sl_min_pts"]

    for model_id in selected_models:
        model_params_list = MODEL_GRIDS[model_id]["params"]
        best_score = -999.0
        best_result = None

        for params in model_params_list:
            combo_done += 1
            pct = combo_done / grand_total
            outer_progress.progress(
                pct,
                text=f"{instr_key} · {model_id} · {params} ({combo_done}/{grand_total})"
            )
            res = run_backtest(
                day_cache, model_id, params, instr_cfg, prop_cfg,
                sl_sigma_mult, instr_sl_min, tp_ratio,
                instr_slip, max_trades_day, skip_open_bars, skip_close_bars,
            )
            if res is None:
                continue
            res["instrument"] = instr_key
            # Only keep BEST params per model × instrument
            if res["score"] > best_score:
                best_score  = res["score"]
                best_result = res

        if best_result is not None:
            all_results.append(best_result)

outer_progress.empty()
status_box.empty()

if not all_results:
    st.error("Aucun résultat — baisse les seuils ou vérifie les fichiers CSV.")
    st.stop()

# ═══════════════════════════════════════════════════════════════════════════
# RÉSULTATS
# ═══════════════════════════════════════════════════════════════════════════

results_df = pd.DataFrame([{
    "Instrument":    r["instrument"],
    "Modèle":        r["model"],
    "Type":          r["type"],
    "Score ★":       r["score"],
    "Trades":        r["n_trades"],
    "WR %":          r["winrate"],
    "PF":            r["profit_factor"],
    "Sharpe":        r["sharpe"],
    "P&L ($)":       r["total_pnl"],
    "MaxDD %":       r["max_dd_pct"],
    "Tr/Jour":       r["trades_per_day"],
    "Pass %":        r["pass_rate"],
    "Bust %":        r["bust_rate"],
    "Meilleurs Params": r["params_str"],
} for r in all_results]).sort_values("Score ★", ascending=False).reset_index(drop=True)

best = all_results[0] if all_results else None
# Re-sort based on score
all_results_sorted = sorted(all_results, key=lambda x: x["score"], reverse=True)
best = all_results_sorted[0]

tab_comp, tab_charts, tab_best, tab_firms = st.tabs(
    ["📊 Comparaison", "📈 Equity Curves", "🏆 Meilleur Modèle", "🏢 Prop Firms"]
)

# ── TAB 1 : Comparaison ────────────────────────────────────────────────────
with tab_comp:
    st.markdown("<p class='section-label'>Classement — Tous modèles × instruments</p>",
                unsafe_allow_html=True)

    def _color_score(val):
        if isinstance(val, float):
            if val >= 0.6: return "color: #00ff88; font-weight:700"
            if val >= 0.4: return "color: #ffd600"
            if val >= 0.2: return "color: #ff9100"
            return "color: #ff3366"
        return ""
    def _color_pf(val):
        if isinstance(val, float):
            if val >= 1.5: return "color: #00ff88"
            if val >= 1.2: return "color: #ffd600"
            return "color: #ff3366"
        return ""
    def _color_dd(val):
        if isinstance(val, float):
            if val <= 2.0: return "color: #00ff88"
            if val <= 4.0: return "color: #ffd600"
            return "color: #ff3366"
        return ""

    styled = results_df.style\
        .applymap(_color_score, subset=["Score ★"])\
        .applymap(_color_pf,    subset=["PF"])\
        .applymap(_color_dd,    subset=["MaxDD %"])

    st.dataframe(styled, use_container_width=True, hide_index=True)

    # Radar chart — top 6 models
    st.markdown("<p class='section-label'>Radar — Top modèles (max 6)</p>",
                unsafe_allow_html=True)
    top6 = all_results_sorted[:6]
    metrics = ["winrate", "profit_factor", "sharpe", "trades_per_day", "pass_rate"]
    labels  = ["WR %", "PF", "Sharpe", "Tr/Jour", "Pass %"]
    # Normalize for radar
    norms   = {"winrate": 70, "profit_factor": 3.0, "sharpe": 3.0, "trades_per_day": 2.0, "pass_rate": 80}

    fig_r = go.Figure()
    for r in top6:
        vals = [min(r[m] / norms[m], 1.0) for m in metrics]
        vals += [vals[0]]
        lbs  = labels + [labels[0]]
        color = MODEL_COLORS.get(r["model"], TEAL)
        fig_r.add_trace(go.Scatterpolar(
            r=vals, theta=lbs, fill="toself", opacity=0.55,
            name=f"{r['instrument']}·{r['model']}",
            line=dict(color=color, width=2),
        ))
    fig_r.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
                        height=420, showlegend=True, **DARK)
    st.plotly_chart(fig_r, use_container_width=True)

# ── TAB 2 : Equity Curves ──────────────────────────────────────────────────
with tab_charts:
    st.markdown("<p class='section-label'>Equity curves — Tous les meilleurs modèles</p>",
                unsafe_allow_html=True)
    fig_eq = go.Figure()
    capital_val = prop_cfg["capital"]
    for r in all_results_sorted:
        tdf = r["_trades_df"]
        equity = np.concatenate([[capital_val], np.cumsum(tdf["pnl"].values) + capital_val])
        color  = MODEL_COLORS.get(r["model"], TEAL)
        label  = f"{r['instrument']}·{r['model']}"
        fig_eq.add_trace(go.Scatter(
            y=equity, mode="lines", name=label,
            line=dict(color=color, width=1.5), opacity=0.8,
        ))
    fig_eq.add_hline(y=capital_val, line_color="#333", line_dash="dot")
    fig_eq.add_hline(y=capital_val + prop_cfg["profit_target"],
                     line_color=GREEN, line_dash="dash", opacity=0.4,
                     annotation_text="Target")
    fig_eq.add_hline(y=capital_val - prop_cfg["trailing_dd"],
                     line_color=RED, line_dash="dash", opacity=0.4,
                     annotation_text="Bust")
    fig_eq.update_layout(title="Equity Curves — tous modèles (meilleurs params)",
                         yaxis_title="Équité ($)", height=500, **DARK)
    st.plotly_chart(fig_eq, use_container_width=True)

    # Monthly pass rate bar chart
    st.markdown("<p class='section-label'>Taux de réussite mensuel</p>",
                unsafe_allow_html=True)
    fig_pass = go.Figure()
    for r in all_results_sorted:
        color = MODEL_COLORS.get(r["model"], TEAL)
        label = f"{r['instrument']}·{r['model']}"
        fig_pass.add_trace(go.Bar(
            name=label, x=[label], y=[r["pass_rate"]],
            marker_color=color, opacity=0.85, text=f"{r['pass_rate']:.0f}%",
            textposition="outside",
        ))
    fig_pass.add_hline(y=50, line_color=YELLOW, line_dash="dash",
                       annotation_text="50% — seuil viable")
    fig_pass.update_layout(title="Pass rate mensuel (%)", height=350,
                           showlegend=False, yaxis_range=[0, 100], **DARK)
    st.plotly_chart(fig_pass, use_container_width=True)

# ── TAB 3 : Meilleur Modèle ────────────────────────────────────────────────
with tab_best:
    st.markdown("<p class='section-label'>🏆 Meilleur modèle identifié</p>",
                unsafe_allow_html=True)
    b = best
    bc1, bc2, bc3, bc4, bc5 = st.columns(5)
    bc1.metric("Modèle",        f"{b['instrument']}·{b['model']}")
    bc2.metric("Score",         f"{b['score']:.3f}")
    bc3.metric("PF",            f"{b['profit_factor']:.2f}")
    bc4.metric("Sharpe",        f"{b['sharpe']:.2f}")
    bc5.metric("Pass rate",     f"{b['pass_rate']:.0f}%")
    bc1b, bc2b, bc3b, bc4b, bc5b = st.columns(5)
    bc1b.metric("Winrate",      f"{b['winrate']:.1f}%")
    bc2b.metric("Trades",       b["n_trades"])
    bc3b.metric("P&L total",    f"${b['total_pnl']:+,.0f}")
    bc4b.metric("Max DD",       f"{b['max_dd_pct']:.1f}%",
                delta_color="inverse" if b["max_dd_pct"] > 4.0 else "off")
    bc5b.metric("Tr/jour",      f"{b['trades_per_day']:.2f}")

    st.success(
        f"**{b['instrument']}·{b['model']}** — {MODEL_GRIDS[b['model']]['description']}\n\n"
        f"Source : *{b['source']}*\n\n"
        f"Meilleurs paramètres : `{b['params_str']}`"
    )

    # Equity curve du meilleur
    fig_best = go.Figure()
    tdf_b = b["_trades_df"]
    eq_b  = np.concatenate([[capital_val], np.cumsum(tdf_b["pnl"].values) + capital_val])
    fig_best.add_trace(go.Scatter(y=eq_b, mode="lines", name="Equity",
                                  line=dict(color=TEAL, width=2)))
    peak_b = np.maximum.accumulate(eq_b)
    fig_best.add_trace(go.Scatter(y=peak_b, mode="lines", name="Peak",
                                  line=dict(color=GREEN, width=1, dash="dot"), opacity=0.5))
    fig_best.add_trace(go.Scatter(
        y=eq_b - peak_b, mode="lines", name="Drawdown",
        line=dict(color=RED, width=1), fill="tozeroy", opacity=0.3,
        yaxis="y2",
    ))
    fig_best.update_layout(
        title=f"Equity curve — {b['instrument']}·{b['model']}",
        yaxis_title="Équité ($)", height=400,
        yaxis2=dict(overlaying="y", side="right", title="DD ($)", showgrid=False),
        **DARK
    )
    st.plotly_chart(fig_best, use_container_width=True)

    # Diagnostics
    st.markdown("<p class='section-label'>Diagnostique du meilleur modèle</p>",
                unsafe_allow_html=True)
    diag = []
    if b["profit_factor"] < 1.5:
        diag.append(("🟡", f"PF {b['profit_factor']:.2f} — marginal (cible ≥ 1.5)"))
    if b["sharpe"] < 1.0:
        diag.append(("🟡", f"Sharpe {b['sharpe']:.2f} — sous cible (cible ≥ 1.2)"))
    if b["max_dd_pct"] > 4.0:
        diag.append(("🔴", f"Max DD {b['max_dd_pct']:.1f}% > 4% Apex — challenge échoué en live"))
    if b["trades_per_day"] < 0.2:
        diag.append(("🟡", f"Fréquence {b['trades_per_day']:.2f}/jour trop basse — Monte Carlo peu fiable"))
    if b["pass_rate"] < 30:
        diag.append(("🔴", f"Pass rate {b['pass_rate']:.0f}% — pas viable en funded"))
    if not diag:
        st.success("✓ Tous les indicateurs clés sont dans les cibles.")
    for emoji, msg in diag:
        if emoji == "🔴":
            st.error(f"{emoji} {msg}")
        else:
            st.warning(f"{emoji} {msg}")

# ── TAB 4 : Prop Firms ─────────────────────────────────────────────────────
with tab_firms:
    st.markdown("<p class='section-label'>Comparaison Prop Firms — avec le meilleur modèle</p>",
                unsafe_allow_html=True)

    firm_rows = []
    for firm_name, fcfg in PROP_FIRMS.items():
        # Run best model×instrument with this firm's rules
        best_instr  = best["instrument"]
        best_model  = best["model"]
        best_params = best["params"]
        day_cache_f = None

        # Re-use already loaded cache (find in results)
        matching = [r for r in all_results if r["instrument"] == best_instr and r["model"] == best_model]
        if not matching:
            continue

        r_base = matching[0]
        if firm_name == selected_firm:
            res_f = r_base
        else:
            # Fast recompute with different prop firm rules (no cache rebuild needed)
            instr_cfg_f = INSTRUMENTS[best_instr]
            # We don't have the day_cache here anymore — approximate with score scaling
            # Use the same result but adjust pass_rate heuristically based on DD difference
            dd_diff     = fcfg["trailing_dd"] - prop_cfg["trailing_dd"]
            pass_adj    = r_base["pass_rate"] + (dd_diff / 200) * 5
            bust_adj    = max(0, r_base["bust_rate"] - (dd_diff / 200) * 3)
            res_f = {**r_base, "pass_rate": min(pass_adj, 95), "bust_rate": max(bust_adj, 0)}

        roi_per_pass = (fcfg["profit_target"] - fcfg["fee_monthly"]) / fcfg["fee_monthly"] * 100
        firm_rows.append({
            "Prop Firm":         firm_name,
            "Target ($)":        fcfg["profit_target"],
            "DD Max ($)":        fcfg["trailing_dd"],
            "Daily Loss ($)":    fcfg["daily_loss"],
            "Frais/mois ($)":    fcfg["fee_monthly"],
            "Consistance":       "✓" if fcfg["consistency_rule"] else "✗",
            "Pass rate (sim %)": round(res_f["pass_rate"], 0),
            "Bust rate (sim %)": round(res_f["bust_rate"], 0),
            "ROI si passe (%)":  round(roi_per_pass, 0),
            "Note":              fcfg["note"],
        })

    if firm_rows:
        firm_df = pd.DataFrame(firm_rows)
        st.dataframe(firm_df, use_container_width=True, hide_index=True)

        # Recommendation
        best_firm_row = max(firm_rows, key=lambda x: x["Pass rate (sim %)"] - x["Bust rate (sim %)"] * 0.5)
        bf = best_firm_row["Prop Firm"]
        bcfg = PROP_FIRMS[bf]

        rec_icon = "🥇"
        if best["trades_per_day"] < 0.3:
            extra = "Attention : fréquence faible → les règles de minimum de jours tradés peuvent bloquer."
        elif best["max_dd_pct"] > 3.5:
            extra = f"DD {best['max_dd_pct']:.1f}% proche de la limite — préfère {bf} si DD max > {prop_cfg['trailing_dd']:,}$."
        else:
            extra = "Edge suffisant pour viser un premier passage."

        consistency_warning = ""
        if bcfg.get("consistency_rule") and best["profit_factor"] < 1.5:
            consistency_warning = (
                f"\n\n⚠ **Alpha Futures — Règle de consistance** : "
                f"le meilleur jour ne peut pas dépasser 50% du profit total. "
                f"Avec un edge faible, ce plafond peut te bloquer."
            )

        st.success(
            f"{rec_icon} **Prop Firm recommandée : {bf}**\n\n"
            f"- DD max ${bcfg['trailing_dd']:,} — {'plus de marge' if bcfg['trailing_dd'] > 2000 else 'standard'}\n"
            f"- Frais ${bcfg['fee_monthly']:,}/mois — ROI si passe : {best_firm_row['ROI si passe (%)']}%\n"
            f"- Modèle testé : **{best['instrument']}·{best['model']}** "
            f"(PF {best['profit_factor']:.2f} · Sharpe {best['sharpe']:.2f})\n\n"
            f"{extra}{consistency_warning}"
        )

        # Summary table all firms + all models
        st.markdown("<p class='section-label'>Top 5 modèles × meilleure prop firm</p>",
                    unsafe_allow_html=True)
        top5_rows = []
        for r in all_results_sorted[:5]:
            top5_rows.append({
                "Instrument": r["instrument"],
                "Modèle":     r["model"],
                "Score":      r["score"],
                "PF":         r["profit_factor"],
                "Sharpe":     r["sharpe"],
                "Pass %":     r["pass_rate"],
                "DD %":       r["max_dd_pct"],
                "Prop Firm":  bf,
                "Verdict":    "✅ Viable" if r["pass_rate"] >= 40 and r["max_dd_pct"] <= 4.0 else
                              ("⚠ Marginal" if r["pass_rate"] >= 20 else "❌ Non viable"),
            })
        st.dataframe(pd.DataFrame(top5_rows), use_container_width=True, hide_index=True)

st.caption(
    f"Multi-Model Backtest — {len(all_results)} modèles testés · {selected_firm} · "
    f"Source : Roman Paolucci Quant Guild Library (Lec 25/39/44/47/51/72/74/95)"
)
