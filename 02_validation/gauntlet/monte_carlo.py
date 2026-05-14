"""Monte Carlo permutation — p-value du Sharpe + distribution du Max Drawdown.

Deux tests distincts, parce que le Sharpe et le Max DD ne réagissent PAS pareil à une
permutation :

  - permutation_test_sharpe : SIGN-FLIP. Le Sharpe (moyenne / écart-type) est insensible
    à l'ORDRE des trades — permuter l'ordre ne donne aucune distribution. On permute donc
    le SIGNE de chaque PnL de trade (x +/-1 aléatoire). H0 = "chaque trade est un pile ou
    face sur sa magnitude" (aucun edge directionnel). p-value = fraction des Sharpes
    permutés >= Sharpe observé. p < 0.05 => l'edge n'est pas un coup de chance.

  - dd_distribution_shuffle : ORDER-SHUFFLE. Le Max DD, lui, dépend complètement de
    l'ordre (des pertes groupées creusent plus qu'éparpillées). On permute l'ORDRE des
    trades et on mesure le Max DD de chaque courbe d'equity -> distribution des DD
    plausibles avec ce jeu de trades. Critique pour un compte Apex où le DD = la mort.

Décision BB (2026-05-14) : le spec disait "permute les returns des trades" ; comme ça ne
produit pas de distribution de Sharpe (order-invariant), on fait sign-flip + shuffle DD.
"""
from __future__ import annotations

import numpy as np

_ANN = np.sqrt(252.0)  # annualisation per-trade (convention repo, cf. compute_trade_metrics)


def _sharpe(pnl: np.ndarray) -> float:
    """Sharpe per-trade annualisé sqrt(252) — convention src.backtest.compute_trade_metrics."""
    if len(pnl) < 2:
        return 0.0
    sd = np.std(pnl, ddof=1)
    if sd == 0:
        return 0.0
    return float(np.mean(pnl) / sd * _ANN)


def _max_drawdown(pnl: np.ndarray) -> float:
    """Max Drawdown ($) d'une séquence de PnL de trades, dans l'ordre donné.

    Equity = cumsum du PnL ; DD = equity - plus-haut-glissant ; Max DD = le minimum (<= 0).
    """
    if len(pnl) == 0:
        return 0.0
    equity = np.cumsum(pnl)
    running_peak = np.maximum.accumulate(equity)
    return float(np.min(equity - running_peak))


def permutation_test_sharpe(pnl, n_iter: int = 10_000, seed: int = 0) -> dict:
    """Test de permutation sign-flip : p-value du Sharpe observé sous H0 "pas d'edge".

    Args:
        pnl: séquence de PnL par trade ($). L'ordre est indifférent (le Sharpe l'ignore).
        n_iter: nombre de permutations sign-flip.
        seed: graine RNG (reproductibilité).

    Returns:
        dict(observed_sharpe, p_value, perm_mean, perm_std, n_iter).
        p_value = (1 + #{perm >= observed}) / (1 + n_iter) — estimateur non biaisé,
        jamais exactement 0.
    """
    pnl = np.asarray(pnl, dtype=float)
    pnl = pnl[~np.isnan(pnl)]
    observed = _sharpe(pnl)
    if len(pnl) < 2:
        return dict(observed_sharpe=observed, p_value=1.0,
                    perm_mean=0.0, perm_std=0.0, n_iter=n_iter)
    rng = np.random.default_rng(seed)
    perms = np.empty(n_iter, dtype=float)
    for k in range(n_iter):
        signs = rng.choice((-1.0, 1.0), size=len(pnl))
        perms[k] = _sharpe(pnl * signs)
    p_value = float((1 + np.sum(perms >= observed)) / (1 + n_iter))
    return dict(
        observed_sharpe=observed,
        p_value=p_value,
        perm_mean=float(np.mean(perms)),
        perm_std=float(np.std(perms, ddof=1)),
        n_iter=n_iter,
    )


def dd_distribution_shuffle(pnl, n_iter: int = 10_000, seed: int = 0) -> dict:
    """Distribution du Max Drawdown par permutation de l'ORDRE des trades.

    Args:
        pnl: séquence de PnL par trade ($), dans l'ordre CHRONOLOGIQUE réel.
        n_iter: nombre de permutations d'ordre.
        seed: graine RNG.

    Returns:
        dict(observed_max_dd, dd_p50, dd_p95, dd_p99, dd_worst, n_iter).
        Tous les DD sont <= 0 ($). observed_max_dd = Max DD dans l'ordre réel.
        dd_p95 = le DD tel que 95% des ordres font MIEUX (moins profond) — donc le 5e
        percentile de la distribution. dd_worst = le pire DD sur toutes les permutations.
    """
    pnl = np.asarray(pnl, dtype=float)
    pnl = pnl[~np.isnan(pnl)]
    observed = _max_drawdown(pnl)
    if len(pnl) < 2:
        return dict(observed_max_dd=observed, dd_p50=observed, dd_p95=observed,
                    dd_p99=observed, dd_worst=observed, n_iter=n_iter)
    rng = np.random.default_rng(seed)
    dds = np.empty(n_iter, dtype=float)
    for k in range(n_iter):
        dds[k] = _max_drawdown(rng.permutation(pnl))
    return dict(
        observed_max_dd=observed,
        dd_p50=float(np.percentile(dds, 50)),
        dd_p95=float(np.percentile(dds, 5)),    # 5% des ordres font pire
        dd_p99=float(np.percentile(dds, 1)),    # 1% des ordres font pire
        dd_worst=float(np.min(dds)),
        n_iter=n_iter,
    )
