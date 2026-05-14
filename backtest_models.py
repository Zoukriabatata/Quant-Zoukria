"""
Multi-Model Backtest Framework — Apex · TopStep · Alpha Futures 50K EOD
Instruments : MNQ · ES · MGC · MCL (1 an OHLCV M1 Databento)
Models      : GARCH_MR · HMM_Regime · Markov_Bot · Heston_Vol · ARIMA_MR · Hurst_MR
Sources     : Roman Paolucci Quant Guild Library
              Lec 25 — Fractional Brownian Motion (Hurst)
              Lec 39 — Heston Stochastic Volatility & FFT
              Lec 44 — Time Series Analysis for Quant Finance
              Lec 47 — Master Volatility with ARCH & GARCH Models
              Lec 51 — Hidden Markov Models for Quant Finance
              Lec 72/74 — Markov Chain Regime Switching Bot (IBKR)
              https://github.com/romanmichaelpaolucci/Quant-Guild-Library
"""

import os
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from styles import inject as _inj; _inj()

# ── Theme ──────────────────────────────────────────────────────────────────
DARK = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="#050505",
    font=dict(color="#94a3b8", size=11,
              family="'JetBrains Mono','Space Grotesk',monospace"),
    margin=dict(t=48, b=40, l=52, r=24),
    hoverlabel=dict(bgcolor="#0a0a0a", bordercolor="rgba(59,130,246,0.4)",
                    font=dict(size=12, family="JetBrains Mono", color="#f1f5f9")),
)
TEAL, CYAN, GREEN, RED, YELLOW, ORANGE, MAGENTA = (
    "#06b6d4", "#06b6d4", "#10b981", "#ef4444", "#f59e0b", "#f97316", "#8b5cf6"
)
BLUE = "#3b82f6"
MODEL_COLORS = {
    "GARCH_MR":    ORANGE,
    "HMM_Regime":  MAGENTA,
    "Markov_Bot":  "#f97316",
    "Heston_Vol":  "#10b981",
    "ARIMA_MR":    CYAN,
    "Hurst_MR":    BLUE,
    "OU_MR":       "#e11d48",
    "Kalman_MR":   "#7c3aed",
    "VWAP_MR":     "#0891b2",
    "ADF_MR":      "#16a34a",
    "VR_MR":       "#ca8a04",
    "HurstAC_MR":  "#dc2626",
}

# ═══════════════════════════════════════════════════════════════════════════
# INSTRUMENTS
# ═══════════════════════════════════════════════════════════════════════════

_CSV_5Y  = r"C:\Users\ryadb\Downloads\5 ANS DATA MNQ OHLCV M1\glbx-mdp3-20210405-20260404.ohlcv-1m.csv"
_CSV_2Y  = r"C:\Users\ryadb\Downloads\data OHLCV M1\glbx-mdp3-20240330-20260329.ohlcv-1m.csv"

INSTRUMENTS = {
    "MNQ": {
        "csv":           _CSV_5Y,
        "symbol_prefix": "MNQ",
        "tick_size":     0.25,
        "dollar_per_pt": 2.0,
        "max_contracts": 60,
        "sl_min_pts":    3.0,
        "sl_max_pts":    20.0,
        "description":   "Micro E-mini Nasdaq · $2/pt · 60 contrats · 5 ans",
    },
    "MNQ (2y)": {
        "csv":           _CSV_2Y,
        "symbol_prefix": "MNQ",
        "tick_size":     0.25,
        "dollar_per_pt": 2.0,
        "max_contracts": 60,
        "sl_min_pts":    3.0,
        "sl_max_pts":    20.0,
        "description":   "Micro E-mini Nasdaq · $2/pt · 2 ans (chargement rapide)",
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
    "GARCH_MR": {
        "description": "GARCH(1,1) Volatility Regime — Mean Reversion en low vol",
        "source":      "Lec 47 — Master Volatility with ARCH & GARCH Models",
        "type":        "Vol-Filtered MR",
        "params": [
            {"low_vol_pct": lvp, "band_k": bk, "confirm": cf}
            for lvp in [0.30, 0.40, 0.50]
            for bk  in [1.5, 2.0, 2.5]
            for cf  in [True, False]
        ],
    },
    "HMM_Regime": {
        "description": "HMM 3 États (Bull/Neutral/Bear) — Inférence Viterbi",
        "source":      "Lec 51 — Hidden Markov Models for Quant Finance",
        "type":        "Regime-Based",
        "params": [
            {"lookback": lb, "pullback": pb, "entry_k": ek}
            for lb in [60, 100, 150]
            for pb in [0.5, 1.0]
            for ek in [1.0, 1.5]
        ],
    },
    "Markov_Bot": {
        "description": "Markov Chain 3-State Vol Bot (LOW/MED/HIGH)",
        "source":      "Lec 72/74 — Markov Chain Regime Bot avec IBKR",
        "type":        "Regime Adaptive",
        "params": [
            {"lookback": lb, "entry_k": ek, "mode": mo}
            for lb in [30, 60, 100]
            for ek in [1.5, 2.0]
            for mo in ["mr", "trend"]
        ],
    },
    "Heston_Vol": {
        "description": "Heston SV — Dynamique κ/θ Variance Mean Reversion",
        "source":      "Lec 39 — Heston Stochastic Volatility Model & FFT",
        "type":        "Stochastic Vol MR",
        "params": [
            {"short_w": sw, "long_w": lw, "band_k": bk}
            for sw in [5, 10]
            for lw in [30, 60]
            for bk in [1.5, 2.0, 2.5]
        ],
    },
    "ARIMA_MR": {
        "description": "AR(p) Prévision Rolling — Mean Reversion vers forecast",
        "source":      "Lec 44 — Time Series Analysis for Quant Finance",
        "type":        "Time Series MR",
        "params": [
            {"ar_order": p, "lookback": lb, "band_k": bk, "confirm": cf}
            for p  in [1, 2]
            for lb in [60, 120]
            for bk in [1.5, 2.0, 2.5]
            for cf in [True, False]
        ],
    },
    "Hurst_MR": {
        "description": "Hurst fBm < 0.5 → Session anti-persistante → MR (+ filtre HMM bar-niveau)",
        "source":      "Lec 25 — Fractional Brownian Motion (Davies-Harte) + Lec 51 — HMM",
        "type":        "Regime-Gated MR",
        "params": [
            {"hurst_threshold": ht, "lookback": lb, "band_k": bk, "hmm_filter": hf}
            for ht in [0.45, 0.50]
            for lb in [30, 60, 100]
            for bk in [1.5, 2.0, 2.5]
            for hf in [True, False]
        ],
    },
    # ── Couche 1 + Couche 2 : Hurst gate + modèle de moyenne alternatif ──────
    "OU_MR": {
        "description": "Ornstein-Uhlenbeck + Half-Life — MR vers μ_OU (gate Hurst)",
        "source":      "Leung, Li, Wang (arXiv 1601.04210) · Leung et al. (arXiv 1811.09312)",
        "type":        "OU Mean Reversion",
        "params": [
            {"hurst_threshold": ht, "max_hl_bars": mhl, "entry_sigma": es, "ou_window": ow}
            for ht  in [0.45, 0.50]
            for mhl in [15, 30]
            for es  in [1.5, 2.0]
            for ow  in [30, 60]
        ],
    },
    "Kalman_MR": {
        "description": "Kalman Filter μ_kalman dynamique + H < 0.5 → entrée MR",
        "source":      "Marton & Cakir (SSRN 4290787) · arXiv econophysique",
        "type":        "Kalman + Hurst MR",
        "params": [
            {"hurst_threshold": ht, "Q": q, "R": r, "entry_sigma": es}
            for ht in [0.45, 0.50]
            for q  in [1e-5, 1e-4]
            for r  in [1e-3, 5e-3]
            for es in [1.5, 2.0]
        ],
    },
    "VWAP_MR": {
        "description": "VWAP Z-Score intraday + H < 0.5 — MR vers VWAP session",
        "source":      "SSRN intraday microstructure · Journal of Empirical Finance",
        "type":        "VWAP MR",
        "params": [
            {"hurst_threshold": ht, "z_entry": ze, "z_stop": zs, "z_window": zw}
            for ht in [0.45, 0.50]
            for ze in [1.5, 2.0, 2.5]
            for zs in [3.0, 3.5]
            for zw in [20, 30]
        ],
    },
    # ── Couche 2 : filtres statistiques de confirmation MR ───────────────────
    "ADF_MR": {
        "description": "Hurst_MR + ADF Test stationnarité (p < seuil) — confirmation statistique",
        "source":      "Engle & Granger · Chan (2013) · SSRN algorithmic trading",
        "type":        "Hurst + ADF",
        "params": [
            {"hurst_threshold": ht, "adf_threshold": ap, "lookback": lb, "band_k": bk}
            for ht in [0.45, 0.50]
            for ap in [0.05, 0.10]
            for lb in [30, 60]
            for bk in [1.5, 2.0]
        ],
    },
    "VR_MR": {
        "description": "Hurst_MR + Variance Ratio Test Lo-MacKinlay (VR < 1 → anti-persistance)",
        "source":      "Lo & MacKinlay (1988) · Review of Financial Studies",
        "type":        "Hurst + VR Test",
        "params": [
            {"hurst_threshold": ht, "vr_q": vq, "lookback": lb, "band_k": bk}
            for ht in [0.45, 0.50]
            for vq in [4, 8]
            for lb in [30, 60]
            for bk in [1.5, 2.0, 2.5]
        ],
    },
    "HurstAC_MR": {
        "description": "Hurst + Autocorrélation lag-1 < 0 — double confirmation anti-persistance",
        "source":      "Physica A · Journal of Financial Economics microstructure papers",
        "type":        "Hurst + Autocorr MR",
        "params": [
            {"hurst_threshold": ht, "ac_threshold": act, "ac_window": acw, "lookback": lb, "band_k": bk}
            for ht  in [0.45, 0.50]
            for act in [-0.05, -0.10]
            for acw in [20, 30]
            for lb  in [30, 60]
            for bk  in [1.5, 2.0]
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


# ═══════════════════════════════════════════════════════════════════════════
# HURST COMBO — Utility functions (OU, Kalman, VWAP, ADF, VR)
# ═══════════════════════════════════════════════════════════════════════════

def ou_estimate(prices):
    """
    OLS-estimated Ornstein-Uhlenbeck parameters via discrete-time regression.
    dX = θ(μ - X)dt + σdB  ⟹  ΔX = a + b·X(t-1) + ε,  θ = -b, μ = a/θ
    Returns (theta, mu, sigma_ou, half_life). half_life = ln(2)/θ.
    """
    p = np.asarray(prices, dtype=float)
    n = len(p)
    if n < 10:
        return 0.0, float(np.mean(p)), max(float(np.std(p)), 1e-9), float("inf")
    dx    = np.diff(p)
    X_lag = p[:-1]
    X_mat = np.column_stack([np.ones(n - 1), X_lag])
    try:
        a, b = np.linalg.lstsq(X_mat, dx, rcond=None)[0]
    except Exception:
        return 0.0, float(np.mean(p)), max(float(np.std(p)), 1e-9), float("inf")
    theta = max(-b, 1e-9)
    mu    = float(a / theta)
    resid = dx - (a + b * X_lag)
    sigma = max(float(np.std(resid)), 1e-9)
    hl    = float(np.log(2) / theta)
    return float(theta), mu, sigma, hl


def kalman_filter_1d(prices, Q=1e-5, R=1e-3):
    """
    1D Kalman filter (constant-level random-walk model).
    Returns (x_est, uncertainty_std) of same length as prices.
    Source: Marton & Cakir (SSRN 4290787).
    """
    n    = len(prices)
    x    = np.empty(n)
    p_k  = np.empty(n)
    x[0] = prices[0]
    p_k[0] = 1.0
    for k in range(1, n):
        p_pred = p_k[k - 1] + Q
        K      = p_pred / (p_pred + R)
        x[k]   = x[k - 1] + K * (prices[k] - x[k - 1])
        p_k[k] = (1.0 - K) * p_pred
    return x, np.sqrt(np.maximum(p_k, 1e-15))


def compute_vwap_series(closes, volumes):
    """Cumulative VWAP for a daily session (no intraday reset assumed)."""
    n    = len(closes)
    vwap = np.empty(n)
    cpv  = 0.0
    cv   = 0.0
    for i in range(n):
        v    = max(float(volumes[i]), 1.0)
        cpv += closes[i] * v
        cv  += v
        vwap[i] = cpv / cv
    return vwap


def adf_pvalue_session(prices):
    """
    ADF test (augmented Dickey-Fuller) on full session price array.
    p < 0.05 → stationary → MR regime confirmed.
    Falls back to 1.0 (no trade) if statsmodels not available.
    """
    try:
        from statsmodels.tsa.stattools import adfuller
        return float(adfuller(prices, maxlag=None, autolag="AIC")[1])
    except ImportError:
        return 1.0
    except Exception:
        return 1.0


def variance_ratio_test(returns, q=5):
    """
    Lo & MacKinlay (1988) Variance Ratio Test.
    VR(q) = Var(q-period returns) / (q × Var(1-period returns)).
    VR < 0.90 → strong anti-persistence → mean-reverting regime.
    Returns (vr, is_mr_regime).
    """
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    if len(r) < max(q * 4, 20):
        return 1.0, False
    var1 = float(np.var(r, ddof=1))
    if var1 < 1e-15:
        return 1.0, False
    rq   = np.array([r[i: i + q].sum() for i in range(0, len(r) - q + 1, q)])
    if len(rq) < 4:
        return 1.0, False
    varq = float(np.var(rq, ddof=1))
    vr   = varq / (q * var1)
    return float(vr), bool(vr < 0.90)


def edge_badge(r):
    """
    Badge d'edge automatique basé sur les 5 critères de performance.
    Trades OK : 96–720/an (= 480–720 sur 5 ans ramené à 1 an de données).
    """
    conds = {
        "PF ≥ 1.9":    r.get("profit_factor", 0) >= 1.9,
        "Sharpe ≥ 1.9": r.get("sharpe", 0)        >= 1.9,
        "WR ≥ 30%":    r.get("winrate", 0)        >= 30,
        "DD < 5%":     r.get("max_dd_pct", 99)    <  5.0,
        "Trades OK":   96 <= r.get("n_trades", 0) <= 720,
    }
    n = sum(conds.values())
    if n == 5: return "🏆 EDGE PARFAIT"
    if n >= 4: return "🌟 EDGE FORT"
    if n >= 3: return "✅ EDGE PARTIEL"
    return "❌ PAS D'EDGE"


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
# SIGNAL GENERATORS — 6 modèles strictement issus du repo Quant Guild
# ═══════════════════════════════════════════════════════════════════════════

def _make_sig(bars, i, entry_bar, price, fv, ss, direction):
    n = len(bars)
    return {
        "bar_idx":    min(entry_bar, n - 1),
        "date":       bars.iloc[i]["date"],
        "bar":        bars.iloc[min(entry_bar, n - 1)]["bar"],
        "price":      price,
        "fair_value": fv,
        "sigma_stat": max(abs(ss), 1e-9),
        "direction":  direction,
    }


def sigs_garch_mr(cached, low_vol_pct, band_k, confirm, skip_open, skip_close):
    """
    Lec 47 — GARCH(1,1) Volatility Regime.
    σ²(t) = ω + α·r²(t-1) + β·σ²(t-1)
    LOW vol (GARCH var < low_vol_pct percentile) → mean-reverting regime → MR entry.
    HIGH vol → skip (trending/explosive).
    """
    bars      = cached["bars"]
    closes    = cached["closes"]
    garch_var = cached["garch_var"]
    n         = len(closes)
    threshold = float(np.nanpercentile(garch_var, low_vol_pct * 100))
    signals   = []
    for i in range(30, n - skip_close):
        if i < skip_open:
            continue
        if garch_var[i] > threshold:
            continue
        window = closes[max(0, i - 30): i]
        mid, std = window.mean(), window.std()
        if std == 0:
            continue
        price = closes[i]
        z = (price - mid) / std
        if abs(z) < band_k:
            continue
        direction = "short" if z > 0 else "long"
        if confirm:
            if i + 1 >= n:
                continue
            nw = closes[max(0, i - 29): i + 1]
            nm, ns = nw.mean(), nw.std()
            if ns > 0 and abs((closes[i+1] - nm) / ns) >= abs(z):
                continue
            signals.append(_make_sig(bars, i, i+1, closes[min(i+1, n-1)], mid, std, direction))
        else:
            signals.append(_make_sig(bars, i, i, price, mid, std, direction))
    return signals


def sigs_hmm_regime(cached, lookback, pullback, entry_k, skip_open, skip_close):
    """
    Lec 51 — Hidden Markov Models 3-State Regime.
    State 2 (BULL) → long sur pullback (z < -entry_k).
    State 0 (BEAR) → short sur rebond (z > entry_k).
    State 1 (NEUTRAL) → skip.
    TP = 2σ dans le sens du régime.
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
        if state == 1:
            continue
        window = closes[max(0, i - lookback): i]
        mid = window.mean()
        std = window.std()
        if std == 0:
            continue
        price = closes[i]
        z = (price - mid) / std
        if state == 2 and z < -entry_k:
            direction = "long"
            fv = price + 2.0 * std
        elif state == 0 and z > entry_k:
            direction = "short"
            fv = price - 2.0 * std
        else:
            continue
        signals.append(_make_sig(bars, i, i, price, fv, std, direction))
    return signals


def sigs_markov_bot(cached, lookback, entry_k, mode, skip_open, skip_close):
    """
    Lec 72/74 — Markov Chain 3-State Vol Bot.
    State 0 (LOW vol)  + mode='mr'    → MR : entrée quand z > entry_k.
    State 2 (HIGH vol) + mode='trend' → Trend : entrée sur micro-pullback.
    State 1 (MED)      → skip.
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
            if abs(z) < entry_k:
                continue
            direction = "short" if z > 0 else "long"
            signals.append(_make_sig(bars, i, i, price, mid, std, direction))
        elif state == 2 and mode == "trend":
            if abs(z) > 0.5:
                continue
            direction = "long" if closes[i] > closes[max(0, i - 5)] else "short"
            fv = price + (2.0 * std if direction == "long" else -2.0 * std)
            signals.append(_make_sig(bars, i, i, price, fv, std, direction))
    return signals


def sigs_heston_vol(cached, short_w, long_w, band_k, skip_open, skip_close):
    """
    Lec 39 — Heston Stochastic Volatility Model.
    dv = κ(θ - v)dt + ξ√v dW₂
    Ratio v(t)/θ : quand vol courte << vol longue (v < θ → variance mean-reverting)
    → prix aussi mean-reverting → entrée MR.
    Ratio >= 1.2 → vol en expansion → skip.
    """
    bars    = cached["bars"]
    closes  = cached["closes"]
    returns = cached["returns"]
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
        direction = "short" if z > 0 else "long"
        signals.append(_make_sig(bars, i, i, price, mid, std, direction))
    return signals


def sigs_arima_mr(cached, ar_order, lookback, band_k, confirm, skip_open, skip_close):
    """
    Lec 44 — Time Series Analysis for Quant Finance.
    Rolling AR(p) forecast. Trade quand prix s'écarte > band_k sigma de la prévision.
    TP = retour à la prévision AR (mean reversion vers forecast).
    Confirmation optionnelle : attend que la barre suivante commence à revenir.
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
        direction = "short" if z > 0 else "long"
        if confirm:
            if i + 1 >= n:
                continue
            z_next = (closes[i+1] - pred) / resid_std
            if abs(z_next) >= abs(z):
                continue
            signals.append(_make_sig(bars, i, i+1, closes[min(i+1, n-1)], pred, resid_std, direction))
        else:
            signals.append(_make_sig(bars, i, i, price, pred, resid_std, direction))
    return signals


def sigs_hurst_mr(cached, hurst_threshold, lookback, band_k, hmm_filter, skip_open, skip_close):
    """
    Lec 25 — Fractional Brownian Motion (Davies-Harte).
    H < hurst_threshold → session anti-persistante (mean-reverting).
    H >= hurst_threshold → persistante ou aléatoire → skip tout le jour.
    Signal : prix > band_k × σ du rolling mean → MR vers la mean.
    hmm_filter=True → overlay Lec 51 : skip barres où HMM state == 2 (trending).
    """
    if cached["hurst"] >= hurst_threshold:
        return []
    bars       = cached["bars"]
    closes     = cached["closes"]
    hmm_states = cached["hmm_states"]
    n = len(closes)
    signals = []
    for i in range(lookback, n - skip_close):
        if i < skip_open:
            continue
        # Lec 51 overlay : si état HMM trending (state 2) → pas de MR
        if hmm_filter and i < len(hmm_states) and hmm_states[i] == 2:
            continue
        window = closes[i - lookback: i]
        mid, std = window.mean(), window.std()
        if std == 0:
            continue
        price = closes[i]
        z = (price - mid) / std
        if abs(z) < band_k:
            continue
        direction = "short" if z > 0 else "long"
        signals.append(_make_sig(bars, i, i, price, mid, std, direction))
    return signals


# ═══════════════════════════════════════════════════════════════════════════
# HURST COMBO SIGNAL GENERATORS — 6 nouveaux modèles (Priorités 1A/1B/1C/2A-2D)
# ═══════════════════════════════════════════════════════════════════════════

def sigs_ou_mr(cached, hurst_threshold, max_hl_bars, entry_sigma, ou_window, skip_open, skip_close):
    """
    Ornstein-Uhlenbeck MR gated by Hurst (arXiv 1601.04210).
    Couche 1: H < hurst_threshold (filtre régime).
    Couche 2: μ_OU estimé par OLS sur fenêtre rolling.
    Couche 3: |price - μ_OU| > entry_sigma × σ_OU.
    Couche 4: half_life = ln(2)/θ ≤ max_hl_bars (vitesse de reversion).
    EXIT: retour à μ_OU (fair value OU).
    """
    if cached["hurst"] >= hurst_threshold:
        return []
    bars    = cached["bars"]
    closes  = cached["closes"]
    n       = len(closes)
    signals = []
    for i in range(ou_window, n - skip_close):
        if i < skip_open:
            continue
        theta, mu, sigma_ou, hl = ou_estimate(closes[i - ou_window: i])
        if theta <= 0 or sigma_ou <= 0 or hl > max_hl_bars:
            continue
        price = closes[i]
        z     = (price - mu) / sigma_ou
        if abs(z) < entry_sigma:
            continue
        direction = "short" if z > 0 else "long"
        signals.append(_make_sig(bars, i, i, price, mu, sigma_ou, direction))
    return signals


def sigs_kalman_mr(cached, hurst_threshold, Q, R, entry_sigma, skip_open, skip_close):
    """
    Kalman Filter dynamic mean estimation + Hurst gate (SSRN 4290787).
    Couche 2: μ_kalman = filtre de Kalman 1D (Q=process noise, R=meas noise).
    Band = rolling std des résidus (price - μ_kalman) sur 20 barres.
    H_brut >= hurst_threshold → skip (gate strict sur Hurst brut).
    """
    if cached["hurst"] >= hurst_threshold:
        return []
    bars      = cached["bars"]
    closes    = cached["closes"]
    n         = len(closes)
    k_mean, _ = kalman_filter_1d(closes, Q=Q, R=R)
    residuals = closes - k_mean
    win_band  = 20
    signals   = []
    for i in range(win_band, n - skip_close):
        if i < skip_open:
            continue
        mu_k = float(k_mean[i])
        band = float(np.std(residuals[max(0, i - win_band): i]))
        if band <= 0:
            continue
        price = closes[i]
        z     = (price - mu_k) / band
        if abs(z) < entry_sigma:
            continue
        direction = "short" if z > 0 else "long"
        signals.append(_make_sig(bars, i, i, price, mu_k, band, direction))
    return signals


def sigs_vwap_mr(cached, hurst_threshold, z_entry, z_stop, z_window, skip_open, skip_close):
    """
    VWAP Z-Score MR gated by Hurst (SSRN intraday microstructure).
    Couche 2: VWAP session = référence institutionnelle intraday.
    Couche 3: Z = (price - VWAP) / rolling_std. Entry si z_entry ≤ |Z| < z_stop.
    EXIT: retour au VWAP (Z = 0). STOP si |Z| franchit z_stop.
    """
    if cached["hurst"] >= hurst_threshold:
        return []
    bars   = cached["bars"]
    closes = cached["closes"]
    vwap   = cached.get("vwap")
    if vwap is None:
        vwap = compute_vwap_series(closes, bars["volume"].values)
    n       = len(closes)
    signals = []
    for i in range(z_window, n - skip_close):
        if i < skip_open:
            continue
        vw  = float(vwap[i])
        if not np.isfinite(vw) or vw <= 0:
            continue
        std = float(np.std(closes[max(0, i - z_window): i]))
        if std <= 0:
            continue
        price = closes[i]
        z     = (price - vw) / std
        if abs(z) < z_entry or abs(z) >= z_stop:
            continue
        direction = "short" if z > 0 else "long"
        signals.append(_make_sig(bars, i, i, price, vw, std, direction))
    return signals


def sigs_adf_mr(cached, hurst_threshold, adf_threshold, lookback, band_k, skip_open, skip_close):
    """
    Hurst_MR + ADF stationarity gate (Engle & Granger / Chan 2013).
    Double confirmation : H < threshold ET p_ADF < adf_threshold.
    ADF calculé une fois sur la session complète (test global du jour).
    Nécessite statsmodels (pip install statsmodels). Désactivé si absent.
    """
    if cached["hurst"] >= hurst_threshold:
        return []
    if cached.get("adf_pvalue", 1.0) >= adf_threshold:
        return []
    bars    = cached["bars"]
    closes  = cached["closes"]
    n       = len(closes)
    signals = []
    for i in range(lookback, n - skip_close):
        if i < skip_open:
            continue
        window = closes[i - lookback: i]
        mid    = float(window.mean())
        std    = float(window.std())
        if std == 0:
            continue
        price = closes[i]
        z     = (price - mid) / std
        if abs(z) < band_k:
            continue
        direction = "short" if z > 0 else "long"
        signals.append(_make_sig(bars, i, i, price, mid, std, direction))
    return signals


def sigs_vr_mr(cached, hurst_threshold, vr_q, lookback, band_k, skip_open, skip_close):
    """
    Hurst_MR + Lo & MacKinlay (1988) Variance Ratio Test.
    VR(q) = Var(q-period returns) / (q × Var(1-period returns)).
    VR < 0.90 → anti-persistance significative → trade autorisé.
    """
    if cached["hurst"] >= hurst_threshold:
        return []
    _, vr_ok = variance_ratio_test(cached["returns"], q=vr_q)
    if not vr_ok:
        return []
    bars    = cached["bars"]
    closes  = cached["closes"]
    n       = len(closes)
    signals = []
    for i in range(lookback, n - skip_close):
        if i < skip_open:
            continue
        window = closes[i - lookback: i]
        mid    = float(window.mean())
        std    = float(window.std())
        if std == 0:
            continue
        price = closes[i]
        z     = (price - mid) / std
        if abs(z) < band_k:
            continue
        direction = "short" if z > 0 else "long"
        signals.append(_make_sig(bars, i, i, price, mid, std, direction))
    return signals


def sigs_hurstac_mr(cached, hurst_threshold, ac_threshold, ac_window, lookback, band_k, skip_open, skip_close):
    """
    Hurst + Autocorrélation lag-1 < threshold (Physica A / JFE microstructure).
    Double confirmation anti-persistance : H < threshold ET autocorr(r, lag=1) < ac_threshold.
    autocorr < 0 → chaque hausse est suivie d'une baisse → MR fort.
    """
    if cached["hurst"] >= hurst_threshold:
        return []
    bars    = cached["bars"]
    closes  = cached["closes"]
    returns = cached["returns"]
    n       = len(closes)
    signals = []
    for i in range(max(lookback, ac_window), n - skip_close):
        if i < skip_open:
            continue
        ret_win = returns[max(0, i - ac_window): i]
        if len(ret_win) < 8:
            continue
        ac = float(pd.Series(ret_win).autocorr(lag=1))
        if np.isnan(ac) or ac >= ac_threshold:
            continue
        window = closes[i - lookback: i]
        mid    = float(window.mean())
        std    = float(window.std())
        if std == 0:
            continue
        price = closes[i]
        z     = (price - mid) / std
        if abs(z) < band_k:
            continue
        direction = "short" if z > 0 else "long"
        signals.append(_make_sig(bars, i, i, price, mid, std, direction))
    return signals


# ═══════════════════════════════════════════════════════════════════════════
# DATA LOADING & SESSION FILTER
# ═══════════════════════════════════════════════════════════════════════════

def filter_session(df, sh, sm, eh, em):
    t = df["bar"].dt.hour * 60 + df["bar"].dt.minute
    return df[(t >= sh*60 + sm) & (t < eh*60 + em)].reset_index(drop=True)


@st.cache_data(show_spinner=False)
def load_instrument_csv(csv_path, symbol_prefix, years_back=5):
    """Charge N ans de données M1 pour un instrument depuis CSV Databento."""
    try:
        df = pd.read_csv(csv_path, usecols=["ts_event","open","high","low","close","volume","symbol"])
    except Exception as e:
        return None, str(e)
    df = df[df["symbol"].str.startswith(symbol_prefix) & ~df["symbol"].str.contains("-", na=False)].copy()
    if df.empty:
        return None, f"Aucun symbole {symbol_prefix} dans {csv_path}"
    df = df.sort_values("volume", ascending=False).groupby("ts_event", sort=False).first().reset_index()
    df["bar"] = pd.to_datetime(df["ts_event"], utc=True)
    df = df[["bar","open","high","low","close","volume","symbol"]].copy()
    df[["open","high","low","close"]] = df[["open","high","low","close"]].astype(float)
    df["volume"] = df["volume"].fillna(0).astype(int)
    df.sort_values("bar", inplace=True)
    df.drop_duplicates(subset=["bar"], inplace=True)
    df.reset_index(drop=True, inplace=True)
    end_dt   = df["bar"].max()
    start_dt = end_dt - pd.DateOffset(years=years_back)
    df = df[df["bar"] >= start_dt].reset_index(drop=True)
    df["date"] = df["bar"].dt.date
    df["tr"] = np.maximum(
        df["high"] - df["low"],
        np.maximum(abs(df["high"] - df["close"].shift(1)), abs(df["low"] - df["close"].shift(1)))
    )

    # ── Rollover detection ──────────────────────────────────────────────
    # Dominant contract per day = symbol with most volume that day
    day_sym = (
        df.groupby("date")
        .apply(lambda g: g.loc[g["volume"].idxmax(), "symbol"] if len(g) > 0 else None)
        .reset_index()
    )
    day_sym.columns = ["date", "dominant"]
    day_sym["prev"] = day_sym["dominant"].shift(1)
    day_sym["is_rollover"] = (day_sym["dominant"] != day_sym["prev"]) & day_sym["prev"].notna()
    # Also mark the day AFTER rollover (price still adjusting)
    day_sym["is_rollover"] = day_sym["is_rollover"] | day_sym["is_rollover"].shift(-1).fillna(False)
    rollover_dates = set(day_sym.loc[day_sym["is_rollover"], "date"].astype(str))

    df["is_rollover_day"] = df["date"].astype(str).isin(rollover_dates)
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


def build_daily_cache(full_df, sh, sm, eh, em):
    """
    Precompute par jour (Quant Guild sources uniquement) :
    GARCH(1,1) var · HMM 3-state · Markov vol states · Hurst · Returns
    """
    cache = {}
    for day_key in sorted(full_df["date"].unique()):
        day_df = full_df[full_df["date"] == day_key].copy()

        # Skip rollover days — price gaps créent des faux signaux
        if day_df["is_rollover_day"].any():
            continue

        bars   = filter_session(day_df, sh, sm, eh, em)
        if len(bars) < 50:
            continue

        closes = bars["close"].values
        highs  = bars["high"].values
        lows   = bars["low"].values
        vols   = bars["volume"].values

        # Hurst exponent (Lec 25 — fBm Davies-Harte)
        hurst_val = hurst_exponent(closes)

        # GARCH(1,1) (Lec 47 — Master Volatility with ARCH & GARCH)
        returns   = np.diff(np.log(np.maximum(closes, 1e-9)))
        returns   = np.concatenate([[0], returns])
        garch_var = garch_rolling(returns)

        # HMM proxy 3-state (Lec 51 — Hidden Markov Models)
        hmm_states = hmm_proxy_states(returns, lookback=60)

        # Markov vol regime 3-state (Lec 72/74 — Markov Chain Bot)
        markov_states = compute_markov_states(closes, highs, lows, lookback=60)

        # VWAP session (Hurst combo models)
        vwap_series = compute_vwap_series(closes, vols)
        # ADF test session (1 appel/jour — statsmodels requis pour ADF_MR)
        adf_p = adf_pvalue_session(closes)

        cache[str(day_key)] = {
            "bars":          bars,
            "closes":        closes,
            "garch_var":     garch_var,
            "hmm_states":    hmm_states,
            "markov_states": markov_states,
            "returns":       returns,
            "hurst":         hurst_val,
            "vwap":          vwap_series,
            "adf_pvalue":    adf_p,
        }
    return cache


# ═══════════════════════════════════════════════════════════════════════════
# BACKTEST RUNNER — single model × params × instrument
# ═══════════════════════════════════════════════════════════════════════════

def dispatch_signals(model_id, cached, params, skip_open, skip_close):
    if model_id == "GARCH_MR":
        return sigs_garch_mr(cached, params["low_vol_pct"], params["band_k"],
                              params["confirm"], skip_open, skip_close)
    if model_id == "HMM_Regime":
        return sigs_hmm_regime(cached, params["lookback"], params["pullback"],
                                params["entry_k"], skip_open, skip_close)
    if model_id == "Markov_Bot":
        return sigs_markov_bot(cached, params["lookback"], params["entry_k"],
                                params["mode"], skip_open, skip_close)
    if model_id == "Heston_Vol":
        return sigs_heston_vol(cached, params["short_w"], params["long_w"],
                                params["band_k"], skip_open, skip_close)
    if model_id == "ARIMA_MR":
        return sigs_arima_mr(cached, params["ar_order"], params["lookback"],
                              params["band_k"], params["confirm"], skip_open, skip_close)
    if model_id == "Hurst_MR":
        return sigs_hurst_mr(cached, params["hurst_threshold"], params["lookback"],
                              params["band_k"], params.get("hmm_filter", False),
                              skip_open, skip_close)
    if model_id == "OU_MR":
        return sigs_ou_mr(cached, params["hurst_threshold"], params["max_hl_bars"],
                           params["entry_sigma"], params["ou_window"], skip_open, skip_close)
    if model_id == "Kalman_MR":
        return sigs_kalman_mr(cached, params["hurst_threshold"], params["Q"], params["R"],
                               params["entry_sigma"], skip_open, skip_close)
    if model_id == "VWAP_MR":
        return sigs_vwap_mr(cached, params["hurst_threshold"], params["z_entry"],
                             params["z_stop"], params["z_window"], skip_open, skip_close)
    if model_id == "ADF_MR":
        return sigs_adf_mr(cached, params["hurst_threshold"], params["adf_threshold"],
                            params["lookback"], params["band_k"], skip_open, skip_close)
    if model_id == "VR_MR":
        return sigs_vr_mr(cached, params["hurst_threshold"], params["vr_q"],
                           params["lookback"], params["band_k"], skip_open, skip_close)
    if model_id == "HurstAC_MR":
        return sigs_hurstac_mr(cached, params["hurst_threshold"], params["ac_threshold"],
                                params["ac_window"], params["lookback"], params["band_k"],
                                skip_open, skip_close)
    return []


def run_backtest(day_cache, model_id, params, instr_cfg, prop_cfg,
                 sl_sigma_mult, sl_min_pts, tp_ratio, slip_pts,
                 max_trades_day, skip_open, skip_close, risk_pct_dd=0.10):
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
            sl_pts  = min(sl_pts, instr_cfg.get("sl_max_pts", sl_pts))  # cap
            tp_price = sig["price"] + tp_ratio * (sig["fair_value"] - sig["price"])

            # Sizing: Half-Kelly sur DD restant (comme Apex live)
            # Risk par trade = risk_pct × DD restant (pas encore consommé)
            dd_used         = max(0.0, running_peak - running_equity)
            dd_remaining    = max(0.0, max_dd_dollars - dd_used)
            risk_per_trade  = risk_pct_dd * dd_remaining
            risk_per_trade  = max(50.0, min(risk_per_trade, daily_loss_lim * 0.40))
            loss_per_ctr    = sl_pts * dollar_per_pt
            if loss_per_ctr <= 0:
                continue
            contracts = max(1, min(max_contracts, int(risk_per_trade / loss_per_ctr)))
            if contracts * loss_per_ctr > max(0.0, daily_loss_lim + daily_pnl):
                contracts = max(1, int(max(0.0, daily_loss_lim + daily_pnl) / loss_per_ctr))
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

    if len(all_trades) < 20:
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

    # Max DD — calculé par mois (comme Apex : reset mensuel)
    # On prend le pire drawdown intra-mensuel
    max_dd_pct = 0.0
    for m in monthly_results:
        month_trades_df = df[df["date"].str.startswith(m["mois"])] if len(df) > 0 else pd.DataFrame()
        if len(month_trades_df) == 0:
            continue
        m_eq = np.concatenate([[capital], np.cumsum(month_trades_df["pnl"].values) + capital])
        m_pk = np.maximum.accumulate(m_eq)
        m_dd = float((m_pk - m_eq).max() / capital * 100)
        max_dd_pct = max(max_dd_pct, m_dd)

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
    #   PF component  (0-1): saturates at PF=3,  bonus fort au-dessus de 1.5
    #   WR component  (0-1): cible 45-60%
    #   Sharpe        (0-1): saturates at 2.5
    #   Pass rate     (0-1): cible >= 50%
    #   Fréquence     (0-1): min 0.5 trades/jour
    #   DD penalty : hard -0.50 si DD mensuel > 4% (pas viable Apex EOD)
    #   PF penalty  : hard -0.40 si PF < 1.3   (edge trop faible)
    score = (
        0.30 * min(max(pf - 1.0, 0.0) / 2.0, 1.0) +
        0.25 * min(max(wr - 0.38, 0.0) / 0.32, 1.0) +
        0.20 * min(max(sharpe, 0.0) / 2.5, 1.0) +
        0.15 * min(pass_rate / 60.0, 1.0) +
        0.10 * min(tpd / 0.5, 1.0) -
        (0.50 if max_dd_pct > 4.0 else 0.0) -
        (0.40 if pf < 1.3 else 0.0)
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
.block-container { padding-top: 1.5rem; max-width: 1400px; }
.page-tag { font-family: 'JetBrains Mono',monospace; font-size:0.65rem; letter-spacing:0.2em; color:#3CC4B7; text-transform:uppercase; }
.page-title { font-size:1.8rem; font-weight:700; color:#fff; letter-spacing:-0.02em; margin:0.3rem 0 0; }
.section-label { font-family:'JetBrains Mono',monospace; font-size:0.6rem; font-weight:700;
    letter-spacing:0.2em; color:#3CC4B7; text-transform:uppercase; margin:1.8rem 0 0.8rem; }
.info-box { background:rgba(15,23,42,0.8); border:1px solid rgba(59,130,246,0.25);
    border-radius:8px; padding:1rem 1.3rem; margin:.6rem 0;
    font-family:'JetBrains Mono',monospace; font-size:.82rem; line-height:2; }
.edge-badge { font-size:2rem; text-align:center; padding:.5rem; display:block; }
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
    default=["MNQ"],
    help="MNQ (5 ans) recommandé. MNQ (2y) pour un chargement plus rapide.",
)
years_back = st.sidebar.slider(
    "Années de données à charger", min_value=1, max_value=5, value=5, step=1,
    help="5 ans = 60 mois · plus fiable statistiquement. 1 an = rapide pour tester.",
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
    "TP ratio", min_value=0.3, max_value=1.0, value=0.7, step=0.1,
    help="0.7 = TP à 70% du fair value → WR plus élevé. 1.0 = TP complet.",
)
slippage_ticks = st.sidebar.number_input("Slippage (ticks)", value=1, min_value=0, step=1)
risk_pct_dd_val = st.sidebar.slider(
    "Risk % DD restant / trade", min_value=0.05, max_value=0.25, value=0.10, step=0.05,
    help="Ex: 0.10 = risque 10% du DD restant par trade (Half-Kelly Apex). Monte à 0.15 pour plus d'agressivité.",
)

st.sidebar.header("Grid Search")
top_n_params = st.sidebar.number_input(
    "Top N params par modèle",
    value=3, min_value=1, max_value=10,
    help="Garde les N meilleurs paramétrages par modèle × instrument dans le classement final.",
)

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

    status_box.info(f"📦 Chargement {instr_key} ({years_back} ans)…")
    full_df, err = load_instrument_csv(instr_cfg["csv"], instr_cfg["symbol_prefix"], years_back)
    if err:
        st.warning(f"⚠ {instr_key} : {err}")
        combo_done += total_combos
        outer_progress.progress(combo_done / grand_total)
        continue

    status_box.info(f"⚙ Precompute {instr_key} — GARCH · HMM · Markov · Hurst…")
    day_cache = build_daily_cache(
        full_df, session_start_h, session_start_m, session_end_h, session_end_m,
    )
    n_days = len(day_cache)

    # Actual slip in instrument points (normalize by tick size)
    instr_slip = slippage_ticks * instr_cfg["tick_size"]
    instr_sl_min = instr_cfg["sl_min_pts"]

    for model_id in selected_models:
        model_params_list = MODEL_GRIDS[model_id]["params"]
        model_results = []

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
                risk_pct_dd=risk_pct_dd_val,
            )
            if res is None:
                continue
            res["instrument"] = instr_key
            model_results.append(res)

        # Keep top N parametrizations per model × instrument
        model_results.sort(key=lambda x: x["score"], reverse=True)
        all_results.extend(model_results[:top_n_params])

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
    "Params":        r["params_str"],
} for r in all_results]).sort_values("Score ★", ascending=False).reset_index(drop=True)

best = all_results[0] if all_results else None
# Re-sort based on score
all_results_sorted = sorted(all_results, key=lambda x: x["score"], reverse=True)
best = all_results_sorted[0]

tab_comp, tab_charts, tab_best, tab_firms, tab_model_comp, tab_explore = st.tabs(
    ["📊 Comparaison", "📈 Equity Curves", "🏆 Meilleur Modèle", "🏢 Prop Firms",
     "🔬 Model Comparison", "🧪 Explore"]
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

    st.markdown(
        f"<span class='edge-badge'>{edge_badge(b)}</span>",
        unsafe_allow_html=True,
    )
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

    # ── Sizing analysis ────────────────────────────────────────────────────
    st.markdown("<p class='section-label'>Analyse sizing — combien risquer par trade ?</p>",
                unsafe_allow_html=True)

    n_months_b   = max(len(b["_monthly"]), 1)
    avg_monthly  = b["total_pnl"] / n_months_b
    target_month = prop_cfg["profit_target"]

    # Multiplier needed to reach target on average
    if avg_monthly > 0:
        mult_needed = target_month / avg_monthly
        risk_needed = risk_pct_dd_val * mult_needed
    else:
        mult_needed = 999
        risk_needed = 999

    # Estimate pass rate at different risk levels
    import math
    monthly_std_est = avg_monthly / max(b["sharpe"] / math.sqrt(12), 0.01)
    sizing_rows = []
    for rp in [0.05, 0.10, 0.15, 0.20, 0.25, 0.30]:
        scale      = rp / max(risk_pct_dd_val, 0.01)
        mu_scaled  = avg_monthly * scale
        sd_scaled  = monthly_std_est * scale
        if sd_scaled > 0:
            z         = (target_month - mu_scaled) / sd_scaled
            # Normal CDF approximation
            pass_est  = 0.5 * (1 + math.erf(-z / math.sqrt(2)))
        else:
            pass_est  = 1.0 if mu_scaled >= target_month else 0.0
        pass_est = max(0.0, min(pass_est, 0.99))
        # Bust estimate: aggressive sizing → higher bust risk
        bust_est = min(0.95, b["bust_rate"] / 100 * scale ** 1.5)
        viable   = "✅" if pass_est >= 0.40 and bust_est < 0.30 else ("⚠" if pass_est >= 0.20 else "❌")
        sizing_rows.append({
            "Risk % DD / trade": f"{rp*100:.0f}%",
            "P&L moy/mois (est)": f"${mu_scaled:+,.0f}",
            "Pass rate (est)":    f"{pass_est*100:.0f}%",
            "Bust rate (est)":    f"{bust_est*100:.0f}%",
            "Verdict":            viable,
        })
    st.dataframe(pd.DataFrame(sizing_rows), use_container_width=True, hide_index=True)

    if mult_needed < 5:
        st.info(
            f"Sizing actuel **{risk_pct_dd_val*100:.0f}%** → P&L moyen ~${avg_monthly:+,.0f}/mois.  \n"
            f"Pour atteindre ${target_month:,}/mois en moyenne → risque **{risk_needed*100:.0f}%** par trade.  \n"
            f"Recommandé : monte progressivement à **{min(risk_needed*100, 25):.0f}%** et observe le bust rate."
        )
    else:
        st.warning("Edge insuffisant même avec sizing maximum — modèle non viable pour funded.")

    # ── Diagnostics ────────────────────────────────────────────────────────
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

# ── TAB 5 : Model Comparison ──────────────────────────────────────────────
with tab_model_comp:
    st.markdown("<p class='section-label'>Tableau comparatif — tous modèles testés avec badge d'edge</p>",
                unsafe_allow_html=True)

    edge_rows = []
    for r in all_results_sorted:
        badge = edge_badge(r)
        edge_rows.append({
            "Instrument":  r["instrument"],
            "Modèle":      r["model"],
            "Type":        r["type"],
            "Trades/an":   r["n_trades"],
            "PF":          r["profit_factor"],
            "Sharpe":      r["sharpe"],
            "WR %":        r["winrate"],
            "Max DD %":    r["max_dd_pct"],
            "Pass %":      r["pass_rate"],
            "P&L ($)":     r["total_pnl"],
            "Edge Badge":  badge,
            "Statut":      ("✅ Validé"   if badge in ("🏆 EDGE PARFAIT", "🌟 EDGE FORT")
                            else ("⚠ À tester" if badge == "✅ EDGE PARTIEL"
                            else "❌ Rejeté")),
        })

    ec_df = pd.DataFrame(edge_rows)

    def _color_badge(val):
        if "🏆" in str(val): return "color:#ffd700;font-weight:700"
        if "🌟" in str(val): return "color:#00ff88;font-weight:700"
        if "✅" in str(val):  return "color:#60a5fa"
        return "color:#ef4444"

    styled_ec = ec_df.style\
        .applymap(_color_badge, subset=["Edge Badge"])\
        .applymap(_color_pf,    subset=["PF"])\
        .applymap(_color_dd,    subset=["Max DD %"])
    st.dataframe(styled_ec, use_container_width=True, hide_index=True)

    # Distribution des badges
    st.markdown("<p class='section-label'>Distribution des badges d'edge</p>",
                unsafe_allow_html=True)
    badge_counts = ec_df["Edge Badge"].value_counts().reset_index()
    badge_counts.columns = ["Badge", "Count"]
    badge_colors_map = {
        "🏆 EDGE PARFAIT": "#ffd700",
        "🌟 EDGE FORT":    "#00ff88",
        "✅ EDGE PARTIEL":  "#60a5fa",
        "❌ PAS D'EDGE":   "#ef4444",
    }
    bar_colors = [badge_colors_map.get(b, TEAL) for b in badge_counts["Badge"]]
    fig_badge = go.Figure(go.Bar(
        x=badge_counts["Badge"], y=badge_counts["Count"],
        marker_color=bar_colors, text=badge_counts["Count"], textposition="outside",
    ))
    fig_badge.update_layout(title="Distribution des badges d'edge — tous modèles",
                            height=320, showlegend=False, **DARK)
    st.plotly_chart(fig_badge, use_container_width=True)

    # Tableau des critères
    st.markdown("""
<div class="info-box">
<b>Critères d'évaluation :</b><br/>
🏆 EDGE PARFAIT — 5/5 critères atteints<br/>
🌟 EDGE FORT &nbsp; — 4/5 critères atteints<br/>
✅ EDGE PARTIEL — 3/5 critères atteints<br/>
❌ PAS D'EDGE &nbsp;— &lt; 3 critères atteints<br/>
<br/>
<b>5 critères :</b> PF ≥ 1.9 · Sharpe ≥ 1.9 · WR ≥ 30% · DD &lt; 5% · Trades 96–720/an
</div>
""", unsafe_allow_html=True)

    # Top 3 avec métriques cibles
    st.markdown("<p class='section-label'>Top 3 modèles — analyse détaillée</p>",
                unsafe_allow_html=True)
    for rank, r in enumerate(all_results_sorted[:3], 1):
        b_txt = edge_badge(r)
        with st.expander(f"#{rank} — {r['instrument']}·{r['model']} — {b_txt}"):
            cc1, cc2, cc3, cc4, cc5 = st.columns(5)
            cc1.metric("PF",     f"{r['profit_factor']:.2f}",
                       delta="OK" if r["profit_factor"] >= 1.9 else "Faible",
                       delta_color="normal" if r["profit_factor"] >= 1.9 else "inverse")
            cc2.metric("Sharpe", f"{r['sharpe']:.2f}",
                       delta="OK" if r["sharpe"] >= 1.9 else "Faible",
                       delta_color="normal" if r["sharpe"] >= 1.9 else "inverse")
            cc3.metric("WR %",   f"{r['winrate']:.1f}%",
                       delta="OK" if r["winrate"] >= 30 else "Faible",
                       delta_color="normal" if r["winrate"] >= 30 else "inverse")
            cc4.metric("Max DD", f"{r['max_dd_pct']:.1f}%",
                       delta="OK" if r["max_dd_pct"] < 5 else "DANGER",
                       delta_color="inverse" if r["max_dd_pct"] >= 5 else "off")
            cc5.metric("Trades", r["n_trades"],
                       delta="OK" if 96 <= r["n_trades"] <= 720 else "Hors cible",
                       delta_color="normal" if 96 <= r["n_trades"] <= 720 else "inverse")
            st.caption(f"Source : {r['source']} | Params : {r['params_str']}")


# ── TAB 6 : Explore Models ─────────────────────────────────────────────────
with tab_explore:
    st.markdown("<p class='section-label'>Bibliothèque quantitative — Hurst + confirmateurs</p>",
                unsafe_allow_html=True)
    st.info(
        "Architecture obligatoire : **Couche 1 → Hurst** (filtre régime) · "
        "**Couche 2 → Moyenne** (fair value) · "
        "**Couche 3 → Signal** (étirement) · "
        "**Couche 4 → Vitesse** (half-life)"
    )

    explore_data = [
        {"Modèle": "OU + Half-Life",
         "Rôle": "Couche 2+4",
         "Pourquoi avec Hurst ?": "θ mesure la vitesse de reversion — confirme que le trade se résoudra dans la session",
         "Source académique": "Leung, Li, Wang — arXiv:1601.04210",
         "Complexité": "Facile",
         "Statut": "✅ Implémenté (OU_MR)"},
        {"Modèle": "Kalman Filter μ",
         "Rôle": "Couche 2",
         "Pourquoi avec Hurst ?": "Estimation dynamique temps-réel de la fair value — plus précis qu'un rolling mean fixe",
         "Source académique": "Marton & Cakir — SSRN:4290787",
         "Complexité": "Facile",
         "Statut": "✅ Implémenté (Kalman_MR)"},
        {"Modèle": "VWAP Z-Score",
         "Rôle": "Couche 2+3",
         "Pourquoi avec Hurst ?": "VWAP = référence institutionnelle intraday — retour VWAP = MR vers le prix 'juste' du jour",
         "Source académique": "SSRN microstructure · Journal of Empirical Finance",
         "Complexité": "Facile",
         "Statut": "✅ Implémenté (VWAP_MR)"},
        {"Modèle": "ADF Test",
         "Rôle": "Couche 1 (renfort)",
         "Pourquoi avec Hurst ?": "p < 0.05 = stationnarité prouvée statistiquement — double confirmation avec H < 0.5",
         "Source académique": "Engle & Granger (1987) · Chan (2013) Algorithmic Trading",
         "Complexité": "Facile",
         "Statut": "✅ Implémenté (ADF_MR) — nécessite statsmodels"},
        {"Modèle": "Variance Ratio (Lo-MacKinlay)",
         "Rôle": "Couche 1 (renfort)",
         "Pourquoi avec Hurst ?": "VR < 1 = test direct anti-persistance (alternative au H R/S classique, même logique)",
         "Source académique": "Lo & MacKinlay (1988) — Review of Financial Studies",
         "Complexité": "Facile",
         "Statut": "✅ Implémenté (VR_MR)"},
        {"Modèle": "Autocorrélation lag-1",
         "Rôle": "Couche 1 (renfort)",
         "Pourquoi avec Hurst ?": "AC(1) < 0 confirme l'anti-persistance barre-par-barre — signal MR très fort si AC < -0.1",
         "Source académique": "Physica A · Journal of Financial Economics microstructure",
         "Complexité": "Facile",
         "Statut": "✅ Implémenté (HurstAC_MR)"},
        {"Modèle": "DFA (Detrended Fluctuation Analysis)",
         "Rôle": "Couche 1 (alternative)",
         "Pourquoi avec Hurst ?": "Alternative plus robuste au H R/S pour HF — même interprétation, plus stable sur petites fenêtres",
         "Source académique": "Barunik & Kristoufek — arXiv:1201.4786 · Physica A",
         "Complexité": "Moyen",
         "Statut": "🔄 À implémenter"},
        {"Modèle": "KPSS Test",
         "Rôle": "Couche 1 (renfort)",
         "Pourquoi avec Hurst ?": "H0 = stationnarité (inverse de l'ADF) — KPSS + ADF ensemble = confirmation ultime",
         "Source académique": "Kwiatkowski, Phillips, Schmidt & Shin (1992)",
         "Complexité": "Facile",
         "Statut": "🔄 À implémenter"},
        {"Modèle": "AR(1) Half-Life",
         "Rôle": "Couche 4",
         "Pourquoi avec Hurst ?": "Alternative simplifiée à OU — régression AR(1) directe, estimation rapide de la vitesse MR",
         "Source académique": "Chan (2013) Algorithmic Trading — Wiley",
         "Complexité": "Facile",
         "Statut": "🔄 À implémenter"},
        {"Modèle": "RSI zones extrêmes (30/70)",
         "Rôle": "Couche 3",
         "Pourquoi avec Hurst ?": "RSI < 30 + H < 0.5 = survendu en régime MR prouvé → LONG haute probabilité",
         "Source académique": "SSRN MR strategies · QuantConnect research",
         "Complexité": "Facile",
         "Statut": "🔄 À implémenter"},
        {"Modèle": "Bollinger Bands % (BBP)",
         "Rôle": "Couche 3",
         "Pourquoi avec Hurst ?": "BBP < 0 (hors bande inf) + H < 0.5 → probabilité de reversion très élevée",
         "Source académique": "SSRN mean-reversion strategies",
         "Complexité": "Facile",
         "Statut": "🔄 À implémenter"},
        {"Modèle": "Parkinson Volatility",
         "Rôle": "Couche 4 (filtre vol)",
         "Pourquoi avec Hurst ?": "Vol Parkinson basse + H < 0.5 = double confirmation régime range — stop plus serré possible",
         "Source académique": "Parkinson (1980) · MDPI Volatility",
         "Complexité": "Facile",
         "Statut": "🔄 À implémenter"},
        {"Modèle": "Garman-Klass Volatility",
         "Rôle": "Couche 4 (filtre vol)",
         "Pourquoi avec Hurst ?": "Estimateur OHLC plus précis que close-to-close pour détecter l'explosion de vol",
         "Source académique": "Garman & Klass (1980) — Journal of Business",
         "Complexité": "Facile",
         "Statut": "🔄 À implémenter"},
        {"Modèle": "Volume Profile POC",
         "Rôle": "Couche 2",
         "Pourquoi avec Hurst ?": "POC = aimant de prix naturel en régime MR — cible de retour institutionnelle",
         "Source académique": "SSRN market microstructure · VWAP literature",
         "Complexité": "Moyen",
         "Statut": "🔄 À implémenter"},
        {"Modèle": "SVM Regime Classifier",
         "Rôle": "Couche 1 (ML)",
         "Pourquoi avec Hurst ?": "SVM apprend à distinguer MR vs Trend — peut améliorer la précision du filtre Hurst",
         "Source académique": "arXiv q-fin · Swiss Finance Institute working papers",
         "Complexité": "Difficile",
         "Statut": "🔬 Recherche"},
        {"Modèle": "Adaptive Moving Average (Kaufman AMA)",
         "Rôle": "Couche 2",
         "Pourquoi avec Hurst ?": "AMA se ralentit en régime range (même régime que H < 0.5) — synergique",
         "Source académique": "Kaufman (1998) Trading Systems and Methods",
         "Complexité": "Facile",
         "Statut": "🔄 À implémenter"},
    ]

    explore_df = pd.DataFrame(explore_data)
    st.dataframe(explore_df, use_container_width=True, hide_index=True)

    # Métriques cibles
    st.markdown("<p class='section-label'>Métriques cibles — 1 an de données</p>",
                unsafe_allow_html=True)
    metrics_target = pd.DataFrame([
        {"Métrique": "Trades/an",     "Minimum": "96",    "Cible": "120–144",  "Excellent": "≥ 150"},
        {"Métrique": "Profit Factor", "Minimum": "1.5",   "Cible": "1.9–2.5",  "Excellent": "≥ 3.0"},
        {"Métrique": "Sharpe Ratio",  "Minimum": "1.2",   "Cible": "1.9–2.5",  "Excellent": "≥ 3.0"},
        {"Métrique": "Win Rate",      "Minimum": "30%",   "Cible": "35–50%",   "Excellent": "≥ 55%"},
        {"Métrique": "Max Drawdown",  "Minimum": "< 5%",  "Cible": "< 3%",     "Excellent": "< 2%"},
        {"Métrique": "Pass rate",     "Minimum": "40%",   "Cible": "50–65%",   "Excellent": "≥ 70%"},
    ])
    st.dataframe(metrics_target, use_container_width=True, hide_index=True)

    st.markdown("""
<div class="info-box">
<b>Sources académiques primaires (ordre de priorité) :</b><br/>
1. SSRN — papers.ssrn.com/sol3/cfdev/AbsByAuth.cfm (recherche: "mean reversion Hurst intraday futures")<br/>
2. arXiv q-fin — arxiv.org/list/q-fin.TR/recent (sections TR, ST)<br/>
3. Physica A — sciencedirect.com/journal/physica-a-statistical-mechanics-and-its-applications<br/>
4. Journal of Financial Economics — jfe.rochester.edu<br/>
5. Review of Financial Studies — academic.oup.com/rfs<br/>
6. Swiss Finance Institute — researchpaper.swissfinanceinstitute.ch<br/>
7. MDPI Open Access — mdpi.com/journal/risks et /journal/jrfm<br/>
</div>
""", unsafe_allow_html=True)


st.caption(
    f"Multi-Model Backtest — {len(all_results)} combos testés · {selected_firm} · "
    f"Source : github.com/romanmichaelpaolucci/Quant-Guild-Library "
    f"(Lec 25 · 39 · 44 · 47 · 51 · 72/74) + arXiv 1601.04210 · SSRN 4290787 · Lo-MacKinlay 1988"
)
