"""run_gauntlet — l'orchestrateur du gauntlet : run_gauntlet(hypothesis) -> Verdict.

Enchaîne les 5 blocs du spec :
  Bloc 1 — Préparation     : load -> resample -> features -> splits Train/Valid/Holdout.
  Bloc 2 — Backtest PA     : le run_variant concret (signal_fn + backtest_pa sur PaAccount).
  Bloc 3 — Batterie stat   : walk-forward, CPCV, Deflated Sharpe, PBO, Monte Carlo.
  Bloc 4 — Robustesse      : stress test périodes rouges, cycle PA continu.
  Bloc 5 — Verdict         : agrégation GO/NO-GO/CONDITIONAL.

Ce fichier est construit en 3 tasks : préparation (T3), helpers grille (T4), run_gauntlet (T5).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import TRAIN_START, VALID_END
from src.instruments import INSTRUMENTS
from src.data_loader import (load_continuous, resample_ohlcv,
                             add_temporal_columns, filter_session_ny)
from src.backtest import compute_trade_metrics

from gauntlet.pa_account import PaAccount
from gauntlet.backtest import backtest_pa
from gauntlet.splits import split_train, split_valid, split_holdout
from gauntlet.deflated_sharpe import probability_backtest_overfitting


# ════════════════════════════════════════════════════════════════════
# Bloc 1 — Préparation
# ════════════════════════════════════════════════════════════════════

def _prepare_splits(df_sess: pd.DataFrame, hypothesis, embargo_bars: int) -> dict:
    """Applique prepare_features puis découpe en Train / Valid / Holdout + full_tv.

    Args:
        df_sess: DataFrame de session NY (sortie de filter_session_ny), indexé tz-aware UTC.
        hypothesis: l'Hypothesis (pour prepare_features).
        embargo_bars: barres de purge jetées en fin de Train et de Valid.

    Returns:
        dict(train, valid, holdout, full_tv). full_tv = Train+Valid contigu — la batterie
        tourne dessus ; le holdout n'est ouvert qu'une fois en toute fin de run_gauntlet.

    Note : prepare_features est appliqué AVANT le découpage. Les features (rolling mean/std,
    Hurst) sont backward-looking — les calculer sur le df complet puis slicer ne fuit rien,
    et évite de recomputer le Hurst (coûteux) pour chaque tranche.
    """
    df_feat = (hypothesis.prepare_features(df_sess)
               if hypothesis.prepare_features is not None else df_sess)
    train = split_train(df_feat, embargo_bars=embargo_bars)
    valid = split_valid(df_feat, embargo_bars=embargo_bars)
    holdout = split_holdout(df_feat)
    full_tv = df_feat.loc[
        (df_feat.index >= TRAIN_START) & (df_feat.index < VALID_END)
    ].copy()
    return dict(train=train, valid=valid, holdout=holdout, full_tv=full_tv)


def prepare_data(hypothesis, embargo_bars: int) -> dict:
    """Bloc 1 complet : charge l'instrument, resample, colonnes temporelles, session NY,
    features, splits.

    I/O : lit le CSV Databento de INSTRUMENTS[hypothesis.instrument]['path']. Non testé
    en pytest (dépend d'un fichier local) — couvert par le script de calibration.
    """
    specs = INSTRUMENTS[hypothesis.instrument]
    df_m1 = load_continuous(specs["path"], specs["root"])
    df_tf = resample_ohlcv(df_m1, hypothesis.timeframe)
    df_tf = add_temporal_columns(df_tf)
    df_sess = filter_session_ny(df_tf)
    return _prepare_splits(df_sess, hypothesis, embargo_bars)


# ════════════════════════════════════════════════════════════════════
# Bloc 2 — Le run_variant concret
# ════════════════════════════════════════════════════════════════════

def make_run_variant(hypothesis):
    """Construit le run_variant concret de l'hypothèse.

    run_variant(df, params) -> (trades_df, account) : applique la signal_fn de l'hypothèse
    puis backtest_pa sur un PaAccount NEUF. C'est le callable injecté dans walk_forward /
    stress_test / pa_cycle (cf. plan Plan 2 §"Le contrat run_variant").

    build_variant(params) est appelé à CHAQUE invocation (et non mis en cache) : c'est
    voulu — walk_forward appelle run_variant avec des params différents par fenêtre, il
    faut reconstruire (signal_fn, exit_logic, bt_kwargs) à chaque fois.
    """
    specs = INSTRUMENTS[hypothesis.instrument]

    def run_variant(df, params):
        signal_fn, exit_logic, bt_kwargs = hypothesis.build_variant(params)
        df_sig = signal_fn(df)
        account = PaAccount()
        trades = backtest_pa(df_sig, exit_logic, specs, account, **bt_kwargs)
        return trades, account

    return run_variant


# ════════════════════════════════════════════════════════════════════
# Helpers de grille
# ════════════════════════════════════════════════════════════════════

def _extract_embargo(hypothesis) -> int:
    """Embargo (barres) = le plus grand timeout_bars de la grille.

    Un trade dure au plus timeout_bars barres ; on purge donc cette durée entre les splits
    pour qu'aucun trade ouvert en fin de fenêtre ne déborde sur la suivante.
    """
    timeouts = []
    for params in hypothesis.param_grid:
        _, _, bt_kwargs = hypothesis.build_variant(params)
        timeouts.append(int(bt_kwargs.get("timeout_bars", 0)))
    return max(timeouts) if timeouts else 0


def _run_grid_on(df: pd.DataFrame, hypothesis, run_variant) -> list:
    """Lance chaque variant de la grille sur df.

    Returns:
        list alignée sur param_grid : [{params, trades, account, metrics}, ...].
    """
    results = []
    for params in hypothesis.param_grid:
        trades, account = run_variant(df, params)
        results.append({
            "params": params, "trades": trades, "account": account,
            "metrics": compute_trade_metrics(trades),
        })
    return results


def _select_best_on_train(train_results: list) -> tuple:
    """Sélectionne le meilleur variant par Sharpe sur Train.

    Args:
        train_results: sortie de _run_grid_on sur le split Train.

    Returns:
        (best_params, best_index, train_sharpes). train_sharpes alimente le sr_variance
        du Deflated Sharpe. Un variant sans trade marque -inf (jamais sélectionné sauf si
        tous vides — auquel cas le premier gagne).
    """
    sharpes = [r["metrics"]["sharpe"] if r["metrics"]["trades"] > 0 else float("-inf")
               for r in train_results]
    best_index = int(np.argmax(sharpes))
    return train_results[best_index]["params"], best_index, sharpes


def _compute_pbo(fulltv_results: list, n_splits: int = 10):
    """PBO sur la matrice (jours × variants) des PnL journaliers des variants sur full_tv.

    Args:
        fulltv_results: sortie de _run_grid_on sur full_tv.
        n_splits: nombre de blocs temporels du PBO combinatoire.

    Returns:
        float PBO, ou None si < 2 variants (PBO indéfini) ou matrice plus courte que n_splits.
    """
    if len(fulltv_results) < 2:
        return None
    daily_panel = {}
    for i, r in enumerate(fulltv_results):
        tr = r["trades"]
        if len(tr) == 0:
            daily_panel[i] = pd.Series(dtype=float)
        else:
            daily_panel[i] = tr.groupby("date")["pnl_usd"].sum()
    pnl_matrix_df = pd.DataFrame(daily_panel).fillna(0.0)
    if len(pnl_matrix_df) < n_splits:
        return None
    return float(probability_backtest_overfitting(pnl_matrix_df.to_numpy(), n_splits=n_splits))
