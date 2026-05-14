"""Walk-forward purgé à fenêtres ancrées (expanding).

López de Prado : on ne juge jamais une stratégie sur les données qui ont servi à la
régler. Le walk-forward découpe l'historique en fenêtres successives ; sur chaque fenêtre
on OPTIMISE les params en in-sample (IS) puis on les TESTE en out-of-sample (OOS), sur des
données que l'optimisation n'a jamais vues. La PURGE (embargo) jette les dernières barres
de l'IS : un trade ouvert en fin d'IS dure plusieurs barres et "déborderait" sur l'OOS —
l'embargo coupe ce chevauchement.

Fenêtres ANCRÉES (expanding) : l'IS grossit à chaque fenêtre (tranches[0..k]), l'OOS est
toujours la tranche suivante. C'est le walk-forward classique — un trader qui ré-optimise
périodiquement avec tout l'historique disponible.

run_variant est INJECTÉ (cf. plan §"Le contrat run_variant") : signature
run_variant(df_slice, params) -> (trades_df, account). Le walk-forward n'utilise que
trades_df.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.backtest import compute_trade_metrics


def purged_walk_forward(df: pd.DataFrame, param_grid: list, run_variant,
                        n_windows: int = 4, embargo_bars: int = 10) -> pd.DataFrame:
    """Walk-forward purgé à fenêtres ancrées.

    Args:
        df: DataFrame préparé (features calculées), indexé par DatetimeIndex tz-aware.
        param_grid: list[dict] — la grille de params de l'hypothèse.
        run_variant: callable(df_slice, params) -> (trades_df, account). Injecté.
        n_windows: nombre de fenêtres OOS (>= 3 recommandé, cf. spec).
        embargo_bars: barres jetées en fin d'IS (purge IS/OOS).

    Returns:
        DataFrame, une ligne par fenêtre :
        [window, is_start, is_end, oos_start, oos_end, best_params,
         oos_trades, oos_sharpe, oos_pf, oos_pnl, oos_max_dd, oos_profitable,
         oos_no_signal].

    Découpe df en n_windows+1 tranches contiguës. Fenêtre k (0-indexée) :
      IS  = df.iloc[0 : fin_tranche_k]  moins les embargo_bars dernières barres
      OOS = tranche k+1
    """
    n = len(df)
    if n_windows < 1:
        raise ValueError(f"n_windows >= 1 requis, reçu {n_windows}")
    if n < n_windows + 1:
        raise ValueError(f"df trop court ({n} barres) pour {n_windows} fenêtres")

    slices = np.array_split(np.arange(n), n_windows + 1)
    rows = []
    for k in range(n_windows):
        is_end_pos = int(slices[k][-1]) + 1            # fin exclusive de l'IS ancré
        is_df = df.iloc[:is_end_pos]
        if embargo_bars > 0:
            is_df = is_df.iloc[:-embargo_bars] if embargo_bars < len(is_df) else is_df.iloc[:0]
        oos_pos = slices[k + 1]
        oos_df = df.iloc[int(oos_pos[0]):int(oos_pos[-1]) + 1]

        # ── Optimisation in-sample : meilleur param par Sharpe ──
        # -inf (et non 0) pour les variants sans trade IS : aucun trade = pire cas,
        # on ne promeut pas un param dont le signal ne se déclenche pas.
        best_params, best_score = None, -np.inf
        for params in param_grid:
            is_trades, _ = run_variant(is_df, params)
            score = compute_trade_metrics(is_trades)["sharpe"] if len(is_trades) else -np.inf
            if score > best_score:
                best_score, best_params = score, params

        # Aucun variant n'a produit de trade IS : pas de signal dans cette fenêtre.
        # On ne lance PAS de backtest OOS (run_variant(oos_df, None) planterait sur un
        # vrai run_variant qui indexe params) — la fenêtre est marquée no-signal.
        if best_params is None:
            rows.append({
                "window": k,
                "is_start": is_df.index[0] if len(is_df) else None,
                "is_end": is_df.index[-1] if len(is_df) else None,
                "oos_start": oos_df.index[0] if len(oos_df) else None,
                "oos_end": oos_df.index[-1] if len(oos_df) else None,
                "best_params": None,
                "oos_trades": 0, "oos_sharpe": 0.0, "oos_pf": 0.0,
                "oos_pnl": 0.0, "oos_max_dd": 0.0,
                "oos_profitable": False, "oos_no_signal": True,
            })
            continue

        # ── Test out-of-sample avec le meilleur param ──
        oos_trades, _ = run_variant(oos_df, best_params)
        m = compute_trade_metrics(oos_trades)
        rows.append({
            "window": k,
            "is_start": is_df.index[0] if len(is_df) else None,
            "is_end": is_df.index[-1] if len(is_df) else None,
            "oos_start": oos_df.index[0] if len(oos_df) else None,
            "oos_end": oos_df.index[-1] if len(oos_df) else None,
            "best_params": best_params,
            "oos_trades": m["trades"],
            "oos_sharpe": m["sharpe"],
            "oos_pf": m["pf"],
            "oos_pnl": m["pnl"],
            "oos_max_dd": m["max_dd"],
            "oos_profitable": m["pnl"] > 0,
            "oos_no_signal": m["trades"] == 0,
        })
    return pd.DataFrame(rows)


def walk_forward_summary(wf_df: pd.DataFrame) -> dict:
    """Agrège un résultat de purged_walk_forward en métriques de verdict.

    Returns:
        dict(n_windows, n_windows_no_signal, pct_oos_profitable, oos_sharpe_mean,
             oos_sharpe_min, oos_pf_mean, all_profitable).
        pct_oos_profitable alimente le critère verdict "≥ 70% fenêtres OOS rentables".
        n_windows_no_signal : fenêtres où le signal ne s'est jamais déclenché en IS.
    """
    if len(wf_df) == 0:
        return dict(n_windows=0, n_windows_no_signal=0, pct_oos_profitable=0.0,
                    oos_sharpe_mean=0.0, oos_sharpe_min=0.0, oos_pf_mean=0.0,
                    all_profitable=False)
    return dict(
        n_windows=len(wf_df),
        n_windows_no_signal=int((wf_df["oos_trades"] == 0).sum()),
        pct_oos_profitable=float(wf_df["oos_profitable"].mean()),
        oos_sharpe_mean=float(wf_df["oos_sharpe"].mean()),
        oos_sharpe_min=float(wf_df["oos_sharpe"].min()),
        oos_pf_mean=float(wf_df["oos_pf"].replace([np.inf, -np.inf], np.nan).mean()),
        all_profitable=bool(wf_df["oos_profitable"].all()),
    )
