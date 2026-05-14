"""Exposant de Hurst R/S vectorisé + rolling par session."""
from __future__ import annotations
import numpy as np
import pandas as pd


def hurst_rs(ts: np.ndarray) -> float:
    """R/S Hurst exponent vectorisé.

    Verbatim depuis pages/5_Backtest.py:150-179 (config champion v9).
    Méthodologie : 12 lags log-espacés [4..min(n/2, 50)], chunks non-chevauchants,
    std ddof=0, OLS log-log, clip [0, 1].

    Args:
        ts: array-like 1D (prix ou returns — la fonction est invariante).

    Returns:
        Exposant de Hurst dans [0.0, 1.0]. Retourne 0.5 si données insuffisantes
        (n < 20 ou < 3 lags valides).
    """
    ts = np.asarray(ts, dtype=float)
    n = len(ts)
    if n < 20:
        return 0.5
    lags = np.unique(np.round(
        np.exp(np.linspace(np.log(4), np.log(min(n // 2, 50)), 12))
    ).astype(int))
    lags = lags[lags >= 4]
    rs_vals = []
    for lag in lags:
        lag = int(lag)
        n_chunks = n // lag
        if n_chunks < 2:
            continue
        mat = ts[:n_chunks * lag].reshape(n_chunks, lag)
        mean = mat.mean(axis=1, keepdims=True)
        devs = np.cumsum(mat - mean, axis=1)
        R = devs.max(axis=1) - devs.min(axis=1)
        S = mat.std(axis=1, ddof=0)
        mask = S > 0
        if mask.sum() == 0:
            continue
        rs_vals.append(float((R[mask] / S[mask]).mean()))
    if len(rs_vals) < 3:
        return 0.5
    try:
        return float(np.clip(
            np.polyfit(np.log(lags[:len(rs_vals)]), np.log(rs_vals), 1)[0],
            0.0, 1.0,
        ))
    except Exception:
        return 0.5


def compute_rolling_hurst_by_session(df: pd.DataFrame, hwin: int = 50) -> pd.Series:
    """Hurst rolling par session (sans look-ahead), reset chaque jour.

    Pour chaque jour : H[i] = hurst_rs(log_rets[i-hwin:i]).
    Les hwin premières barres de chaque session sont NaN (warmup).

    Args:
        df: DataFrame avec colonnes 'close' et 'date' (date NY locale ou UTC, peu importe
            tant que les sessions sont identifiables).
        hwin: taille de la fenêtre rolling (default 50, config v9).

    Returns:
        Series indexée comme df, valeurs H dans [0.0, 1.0] ou NaN.
    """
    out = np.full(len(df), np.nan)
    closes = df['close'].values.astype(float)
    dates = df['date'].values
    day_starts = np.where(np.concatenate([[True], dates[1:] != dates[:-1]]))[0]
    day_starts = np.append(day_starts, len(df))
    for k in range(len(day_starts) - 1):
        a, b = day_starts[k], day_starts[k + 1]
        if b - a < hwin + 2:
            continue
        sess_close = closes[a:b]
        sess_rets = np.diff(np.log(np.maximum(sess_close, 1e-9)))
        sess_rets = np.concatenate([[0.0], sess_rets])
        for i in range(hwin, b - a):
            out[a + i] = hurst_rs(sess_rets[i - hwin: i])
    return pd.Series(out, index=df.index, name='hurst')
