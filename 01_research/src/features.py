"""Calcul features signal — Z-score (MR), RSI, ORB (opening range), GARCH rolling vol."""
from __future__ import annotations
import numpy as np
import pandas as pd


def compute_signal_features(df: pd.DataFrame, lookback: int = 20) -> pd.DataFrame:
    """Calcule mid/std/zscore rolling sur close. Utilisé par les signaux MR.

    Returns: copy de df + colonnes ['mid', 'std', 'zscore'].
    """
    out = df.copy()
    closes = out['close']
    out['mid']    = closes.rolling(lookback).mean()
    out['std']    = closes.rolling(lookback).std(ddof=0)
    out['zscore'] = (closes - out['mid']) / out['std'].replace(0, np.nan)
    return out


def compute_features_rsi(df: pd.DataFrame, period: int = 14, std_lookback: int = 20) -> pd.DataFrame:
    """RSI standard + mid/std (pour SL en std).

    Returns: copy de df + colonnes ['rsi', 'std', 'mid'].
    """
    out = df.copy()
    close = out['close']
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    out['rsi'] = 100 - (100 / (1 + rs))
    out['std'] = close.rolling(std_lookback).std(ddof=0)
    out['mid'] = close.rolling(std_lookback).mean()
    return out


def compute_features_orb(df: pd.DataFrame, or_minutes: int = 30, bar_size_min: int = 1,
                         std_lookback: int = 20) -> pd.DataFrame:
    """ORB : Opening Range high/low/range sur les `or_minutes` premières min de session.

    Nécessite df avec colonnes 'date', 'hour_ny', 'min_ny' (utiliser add_temporal_columns() d'abord).
    Returns: copy de df + colonnes ['or_high', 'or_low', 'or_range', 'in_or', 'post_or',
                                    'std', 'mid'].
    """
    out = df.copy()
    close_min_ny = out['hour_ny'] * 60 + out['min_ny'] + bar_size_min
    or_end = 9 * 60 + 30 + or_minutes
    out['in_or'] = (close_min_ny > 9 * 60 + 30) & (close_min_ny <= or_end)
    daily_or = out[out['in_or']].groupby('date').agg(or_high=('high', 'max'), or_low=('low', 'min'))
    daily_or['or_range'] = daily_or['or_high'] - daily_or['or_low']
    out = out.reset_index().merge(daily_or, on='date', how='left').set_index('bar')
    out['post_or'] = close_min_ny > or_end
    out['std'] = out['close'].rolling(std_lookback).std(ddof=0)
    out['mid'] = out['close'].rolling(std_lookback).mean()
    return out


def garch_rolling(rets: np.ndarray, omega: float = 1e-6, alpha: float = 0.1,
                  beta: float = 0.85) -> np.ndarray:
    """GARCH(1,1) rolling vol forecast. Verbatim depuis pages/5_Backtest.py:183-188."""
    n = len(rets)
    vs = np.full(n, np.var(rets) if np.var(rets) > 0 else 1e-6)
    for i in range(1, n):
        vs[i] = omega + alpha * rets[i - 1] ** 2 + beta * vs[i - 1]
    return vs
