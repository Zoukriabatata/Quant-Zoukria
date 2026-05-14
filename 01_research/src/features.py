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


def compute_features_opening_drive(df: pd.DataFrame,
                                   gap_std_window: int = 20,
                                   vol_regime_window: int = 60,
                                   relvol_window: int = 20) -> pd.DataFrame:
    """Features de l'hypothèse Opening Drive Failure Fade (cf. spec 2026-05-15).

    Calculée sur le df de session RTH COMPLET (toutes les journées) — les features
    gap/vol nécessitent du contexte inter-journées. Backward-looking : pas de leakage.

    Nécessite les colonnes : open, high, low, close, volume, date, hour_ny, min_ny.

    Args:
        gap_std_window: fenêtre rolling (jours) de l'écart-type des gaps overnight.
        vol_regime_window: fenêtre rolling (jours) de la médiane de vol réalisée.
        relvol_window: fenêtre rolling (jours) de la moyenne de volume par tranche horaire.

    Returns: copy de df + colonnes
        ['open_ref', 'prev_close', 'gap_z', 'spike_magnitude', 'rejection_body',
         'vol_regime', 'relvol_open'].
    """
    out = df.copy()

    # open_ref : open de la 1re bougie de chaque journée (le "corps", constant/jour).
    out['open_ref'] = out.groupby('date')['open'].transform('first')

    # prev_close : close de la dernière bougie de la session RTH précédente.
    daily_last_close = out.groupby('date')['close'].last()
    prev_close_by_date = daily_last_close.shift(1)
    out['prev_close'] = out['date'].map(prev_close_by_date)

    # gap_z : gap overnight (open du jour - close veille) normalisé par l'écart-type
    # rolling des gaps. Le prédicteur central (littérature overnight-intraday reversal).
    daily_open = out.groupby('date')['open'].first()
    daily_gap = daily_open - prev_close_by_date
    gap_std = daily_gap.rolling(gap_std_window).std()
    gap_z_by_date = daily_gap / gap_std.replace(0.0, np.nan)
    out['gap_z'] = out['date'].map(gap_z_by_date)

    # spike_magnitude : déplacement signé du close vs open_ref (en points).
    out['spike_magnitude'] = out['close'] - out['open_ref']

    # rejection_body : position de la clôture dans le range de la bougie.
    # ~1 = clôture en haut du range (rejet d'un down-spike) ; ~0 = rejet d'un up-spike.
    rng = out['high'] - out['low']
    out['rejection_body'] = np.where(rng > 0, (out['close'] - out['low']) / rng, 0.5)

    # vol_regime : vol réalisée intraday du jour > médiane rolling. L'effet reversal
    # est ~2x plus fort en régime de volatilité élevée.
    daily_rv = out.groupby('date')['close'].apply(lambda s: s.pct_change().std())
    rv_median = daily_rv.rolling(vol_regime_window).median()
    vol_regime_by_date = (daily_rv > rv_median)
    out['vol_regime'] = out['date'].map(vol_regime_by_date).fillna(False).astype(bool)

    # relvol_open : volume / moyenne rolling du volume à la même tranche horaire.
    tod = out['hour_ny'] * 60 + out['min_ny']
    vol_mean_tod = out.groupby(tod)['volume'].transform(
        lambda s: s.rolling(relvol_window).mean()
    )
    out['relvol_open'] = out['volume'] / vol_mean_tod.replace(0.0, np.nan)

    return out
