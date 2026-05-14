"""Loader Databento .csv.zst avec exclusion rollover + resampling + colonnes temporelles."""
from __future__ import annotations
from pathlib import Path
from typing import Union

import pandas as pd


def load_continuous(path: Union[Path, str], root: str) -> pd.DataFrame:
    """Charge un fichier Databento .csv.zst, filtre par root symbol, exclut spreads et jours rollover.

    Verbatim depuis pages/5_Backtest.py:195-221 et les scripts run_*.py.

    Args:
        path: chemin .csv.zst Databento (format GLBX.MDP.3 OHLCV-1m).
        root: préfixe symbol à conserver ('MNQ', 'NQ', 'ES').

    Returns:
        DataFrame indexé sur datetime UTC (column 'bar'), colonnes [open, high, low, close, volume].
        Les jours de rollover ET adjacents sont exclus.
    """
    df = pd.read_csv(path, usecols=['ts_event', 'open', 'high', 'low', 'close', 'volume', 'symbol'])
    df = df[df['symbol'].str.startswith(root) & ~df['symbol'].str.contains('-', na=False)].copy()
    df = df.sort_values('volume', ascending=False).groupby('ts_event', sort=False).first().reset_index()
    df['bar'] = pd.to_datetime(df['ts_event'], utc=True)
    df[['open', 'high', 'low', 'close']] = df[['open', 'high', 'low', 'close']].astype(float)
    df['volume'] = df['volume'].fillna(0).astype(int)
    df.sort_values('bar', inplace=True)
    df.drop_duplicates(subset=['bar'], inplace=True)
    df.reset_index(drop=True, inplace=True)
    df['date'] = df['bar'].dt.date
    # Détection rollover : contrat dominant qui change d'un jour à l'autre
    day_sym = df.groupby('date').apply(
        lambda g: g.loc[g['volume'].idxmax(), 'symbol'] if len(g) > 0 else None,
        include_groups=False,
    ).reset_index()
    day_sym.columns = ['date', 'dominant']
    day_sym['prev'] = day_sym['dominant'].shift(1)
    day_sym['roll'] = (day_sym['dominant'] != day_sym['prev']) & day_sym['prev'].notna()
    day_sym['roll'] = (day_sym['roll'] | day_sym['roll'].shift(-1)).fillna(False).astype(bool)
    roll_dates = set(day_sym.loc[day_sym['roll'], 'date'].astype(str))
    df['is_roll'] = df['date'].astype(str).isin(roll_dates)
    df = df[~df['is_roll']].drop(columns=['is_roll', 'symbol']).reset_index(drop=True)
    df = df.set_index('bar').sort_index()
    return df[['open', 'high', 'low', 'close', 'volume']]


def resample_ohlcv(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Resample OHLCV en gardant first/max/min/last/sum.

    Args:
        df: DataFrame OHLCV indexé temporellement.
        rule: règle pandas (ex: '5min', '15min', '1H').

    Returns:
        DataFrame resamplé sans NaN sur close.
    """
    out = df.resample(rule).agg({
        'open': 'first', 'high': 'max', 'low': 'min',
        'close': 'last', 'volume': 'sum',
    }).dropna(subset=['close'])
    return out


def add_temporal_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Ajoute colonnes hour_ny, min_ny, month, dow, date (heure locale NY via tz_convert).

    Le DataFrame doit être indexé sur datetime UTC.
    """
    out = df.copy()
    out['ts_ny']   = out.index.tz_convert('America/New_York')
    out['hour_ny'] = out['ts_ny'].dt.hour
    out['min_ny']  = out['ts_ny'].dt.minute
    out['month']   = out.index.month
    out['dow']     = out.index.dayofweek
    out['date']    = out.index.date
    return out


def filter_session_ny(df: pd.DataFrame, start_h: int = 9, start_m: int = 30,
                      end_h: int = 16, end_m: int = 0) -> pd.DataFrame:
    """Filtre la session NY 9h30-16h locale.

    Nécessite add_temporal_columns() préalable (colonnes hour_ny, min_ny).
    """
    t_ny = df['hour_ny'] * 60 + df['min_ny']
    return df[(t_ny >= start_h * 60 + start_m) & (t_ny < end_h * 60 + end_m)].copy()
