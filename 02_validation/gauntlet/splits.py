"""Splits López de Prado : Train / Valid / Holdout, avec embargo.

Les dates sont figées dans 01_research/src/config.py. L'embargo jette les dernières
barres d'une fenêtre pour éviter qu'un trade ouvert près de la frontière "fuite" son
résultat dans la fenêtre suivante.
"""
from __future__ import annotations

import pandas as pd

from src.config import (
    TRAIN_START, TRAIN_END, VALID_START, VALID_END, HOLDOUT_START, HOLDOUT_END,
)


def _slice(df: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp,
           embargo_bars: int) -> pd.DataFrame:
    """Slice [start, end) puis jette les `embargo_bars` dernières barres."""
    s = df.loc[(df.index >= start) & (df.index < end)]
    if embargo_bars > 0:
        s = s.iloc[:-embargo_bars]
    return s.copy()


def split_train(df: pd.DataFrame, embargo_bars: int = 0) -> pd.DataFrame:
    """Fenêtre Train (2021-05-13 -> 2024-05-13)."""
    return _slice(df, TRAIN_START, TRAIN_END, embargo_bars)


def split_valid(df: pd.DataFrame, embargo_bars: int = 0) -> pd.DataFrame:
    """Fenêtre Valid (2024-05-13 -> 2025-05-13)."""
    return _slice(df, VALID_START, VALID_END, embargo_bars)


def split_holdout(df: pd.DataFrame, embargo_bars: int = 0) -> pd.DataFrame:
    """Fenêtre Holdout (2025-05-13 -> 2026-05-13) — intouchable jusqu'au verdict final.

    Note : partiellement contaminée par le grid-search du dual-config HurstMR (2026-05-14).
    """
    return _slice(df, HOLDOUT_START, HOLDOUT_END, embargo_bars)
