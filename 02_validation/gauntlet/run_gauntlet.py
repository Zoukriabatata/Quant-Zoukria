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
from gauntlet.walk_forward import purged_walk_forward, walk_forward_summary
from gauntlet.monte_carlo import permutation_test_sharpe, dd_distribution_shuffle
from gauntlet.cpcv import sharpe_distribution_cpcv
from gauntlet.deflated_sharpe import deflated_sharpe_ratio
from gauntlet.stress_test import run_stress_test, stress_test_passed
from gauntlet.pa_cycle import analyze_pa_cycle
from gauntlet.verdict import build_verdict, DSR_GO_THRESHOLD


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


# ════════════════════════════════════════════════════════════════════
# L'orchestrateur
# ════════════════════════════════════════════════════════════════════

# Fallback du sr_variance du Deflated Sharpe quand la grille a < 2 variants exploitables.
# 0.09 = 0.3^2, convention héritée de run_final_validation.py.
_SR_VARIANCE_FALLBACK = 0.09


def run_gauntlet(hypothesis, splits: dict = None, out_dir=None,
                 mc_iter: int = 10_000, seed: int = 0,
                 n_windows: int = 4, cpcv_n_groups: int = 10,
                 pbo_n_splits: int = 10):
    """Exécute le gauntlet complet sur une hypothèse -> Verdict.

    Args:
        hypothesis: l'Hypothesis à juger.
        splits: dict(train, valid, holdout, full_tv) DÉJÀ préparé. None -> prepare_data
                charge les vraies données (I/O fichier). L'injection sert aux tests.
        out_dir: dossier où écrire le rapport (None -> pas de rapport écrit).
        mc_iter: itérations Monte Carlo.
        seed: graine RNG (Monte Carlo).
        n_windows: fenêtres du walk-forward.
        cpcv_n_groups: groupes du CPCV.
        pbo_n_splits: blocs temporels du PBO.

    Returns:
        Verdict.
    """
    run_variant = make_run_variant(hypothesis)
    embargo = _extract_embargo(hypothesis)
    if splits is None:
        splits = prepare_data(hypothesis, embargo_bars=embargo)
    train, full_tv, holdout = splits["train"], splits["full_tv"], splits["holdout"]

    # ── Sélection du meilleur variant sur Train ─────────────────
    train_results = _run_grid_on(train, hypothesis, run_variant)
    best_params, _best_idx, train_sharpes = _select_best_on_train(train_results)

    # ── Bloc 3a — Walk-forward purgé sur Train+Valid ────────────
    wf = purged_walk_forward(full_tv, hypothesis.param_grid, run_variant,
                             n_windows=n_windows, embargo_bars=embargo)
    wf_sum = walk_forward_summary(wf)

    # ── Run plein Train+Valid + grille complète sur full_tv ─────
    fulltv_results = _run_grid_on(full_tv, hypothesis, run_variant)
    best_on_fulltv = next(r for r in fulltv_results if r["params"] == best_params)
    full_trades = best_on_fulltv["trades"]
    full_account = best_on_fulltv["account"]
    full_metrics = best_on_fulltv["metrics"]

    # ── Bloc 3b — Monte Carlo + CPCV + Deflated Sharpe + PBO ────
    pnl = full_trades["pnl_usd"].to_numpy() if len(full_trades) else np.array([])
    mc = permutation_test_sharpe(pnl, n_iter=mc_iter, seed=seed)
    dd = dd_distribution_shuffle(pnl, n_iter=mc_iter, seed=seed)
    cpcv = (sharpe_distribution_cpcv(full_trades, n_groups=cpcv_n_groups, k_test=2,
                                     date_col="date", pnl_col="pnl_usd")
            if len(full_trades) else np.array([]))
    daily = (full_trades.groupby("date")["pnl_usd"].sum().to_numpy()
             if len(full_trades) else np.array([]))
    finite_sharpes = [s for s in train_sharpes if np.isfinite(s)]
    sr_variance = (max(float(np.var(finite_sharpes, ddof=1)), 1e-4)
                   if len(finite_sharpes) >= 2 else _SR_VARIANCE_FALLBACK)
    dsr = (float(deflated_sharpe_ratio(daily, n_trials=hypothesis.n_trials,
                                       sr_variance=sr_variance))
           if len(daily) >= 5 else 0.0)
    pbo = _compute_pbo(fulltv_results, n_splits=pbo_n_splits)

    # ── Bloc 4 — Stress test + cycle PA ─────────────────────────
    stress = run_stress_test(full_tv, best_params, run_variant)
    cycle = analyze_pa_cycle(full_account)
    cycle["n_trades"] = len(full_trades)

    # ── Holdout — ouvert UNE seule fois, confiance dégradée ─────
    holdout_trades, _holdout_account = run_variant(holdout, best_params)
    holdout_metrics = compute_trade_metrics(holdout_trades)
    holdout_note = (
        f"Holdout 2025-05->2026-05 (confiance DÉGRADÉE — partiellement contaminé par le "
        f"grid-search dual-config) : {holdout_metrics['trades']} trades, "
        f"PF {holdout_metrics['pf']:.2f}, Sharpe {holdout_metrics['sharpe']:.2f}, "
        f"PnL ${holdout_metrics['pnl']:.0f}. Confirmation indicative, pas un critère GO."
    )

    # ── Bloc 5 — Verdict ────────────────────────────────────────
    verdict = build_verdict(
        hypothesis_name=hypothesis.name,
        account_survived=(full_account.status != "dead_eod"),
        wf_summary=wf_sum, mc=mc, dsr=dsr, pbo=pbo,
        full_max_dd=full_metrics["max_dd"],
        stress_passed=stress_test_passed(stress),
        reached_lock=cycle["reached_lock"],
        inactivity_safe=cycle["inactivity_safe"],
        holdout_note=holdout_note, dsr_threshold=DSR_GO_THRESHOLD,
    )

    # ── Rapport (import paresseux : report.py n'existe qu'à partir de Task 6) ──
    if out_dir is not None:
        from gauntlet.report import write_gauntlet_report
        write_gauntlet_report(verdict, dict(
            hypothesis=hypothesis, wf=wf, wf_summary=wf_sum, mc=mc, dd=dd,
            cpcv=cpcv, dsr=dsr, sr_variance=sr_variance, pbo=pbo,
            full_metrics=full_metrics, full_account=full_account,
            stress=stress, cycle=cycle, holdout_metrics=holdout_metrics,
            fulltv_results=fulltv_results, best_params=best_params,
        ), out_dir)

    return verdict
