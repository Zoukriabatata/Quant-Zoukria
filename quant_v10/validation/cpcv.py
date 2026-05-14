"""
Combinatorial Purged Cross-Validation (CPCV) — Lopez de Prado 2018, AFML Ch.12.

Pour stratégies déterministes (sans training ML), CPCV génère des paths OOS
en sélectionnant K groupes test parmi N. Chaque path donne un Sharpe OOS.
La distribution révèle la robustesse.
"""
from __future__ import annotations

from itertools import combinations
from typing import List, Tuple

import numpy as np
import pandas as pd


def generate_cpcv_paths(n_groups: int, k_test: int) -> List[Tuple[int, ...]]:
    """
    Génère toutes les combinaisons de k_test groupes parmi n_groups.

    Returns
    -------
    list of tuples
        Chaque tuple = indices des groupes en TEST set.
    """
    if k_test >= n_groups:
        raise ValueError(f"k_test ({k_test}) >= n_groups ({n_groups})")
    return list(combinations(range(n_groups), k_test))


def sharpe_distribution_cpcv(
    trades_df: pd.DataFrame,
    n_groups: int = 10,
    k_test: int = 2,
    date_col: str = "date",
    pnl_col: str = "pnl",
) -> np.ndarray:
    """
    Calcule la distribution des Sharpe sur tous les paths CPCV.

    Pour chaque combo de k_test groupes test :
        - Aggrège PnL daily sur les groupes test
        - Compute Sharpe
        - Stocke

    Parameters
    ----------
    trades_df : pd.DataFrame
        Doit contenir colonnes `date` (str ou datetime) et `pnl`.
    n_groups : int
        Nombre de groupes temporels.
    k_test : int
        Taille du test set (en groupes).

    Returns
    -------
    np.ndarray
        Array de Sharpe OOS sur chaque path.
    """
    df = trades_df.copy()
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.sort_values(date_col)

    # Agrégation daily
    daily = df.groupby(df[date_col].dt.date)[pnl_col].sum().reset_index()
    daily.columns = [date_col, "daily_pnl"]
    daily = daily.sort_values(date_col).reset_index(drop=True)

    n_days = len(daily)
    if n_days < n_groups + 1:
        return np.array([])

    # Split en n_groups groupes contigus
    group_indices = np.array_split(np.arange(n_days), n_groups)

    paths = generate_cpcv_paths(n_groups, k_test)
    sharpes = []
    for test_groups in paths:
        test_idx = np.concatenate([group_indices[g] for g in test_groups])
        test_pnl = daily.iloc[test_idx]["daily_pnl"].to_numpy()
        if len(test_pnl) < 5 or np.std(test_pnl, ddof=1) == 0:
            continue
        sharpe = float(np.mean(test_pnl) / np.std(test_pnl, ddof=1) * np.sqrt(252))
        sharpes.append(sharpe)

    return np.array(sharpes)
