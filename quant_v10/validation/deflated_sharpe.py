"""
Probabilistic Sharpe Ratio (PSR) + Deflated Sharpe Ratio (DSR) + PBO.

References :
    - Bailey, D.H. & Lopez de Prado, M. (2014). "The Deflated Sharpe Ratio:
      Correcting for Selection Bias, Backtest Overfitting and Non-Normality",
      Journal of Portfolio Management 40(5).
    - Bailey, D.H. & Lopez de Prado, M. (2014). "The Probability of Backtest
      Overfitting", arXiv:1505.06769.
"""
from __future__ import annotations

from itertools import combinations

import numpy as np
from scipy.stats import norm, skew, kurtosis


def _sample_sharpe(returns: np.ndarray) -> float:
    """Sharpe annualisé (daily-like, sqrt(252))."""
    if len(returns) < 2 or np.std(returns, ddof=1) == 0:
        return 0.0
    return float(np.mean(returns) / np.std(returns, ddof=1) * np.sqrt(252))


def probabilistic_sharpe_ratio(
    returns: np.ndarray,
    sr_benchmark: float = 0.0,
) -> float:
    """
    PSR(SR*) = P(SR_true > SR*) via Bailey-LdP 2014.

    PSR = Phi((SR_hat - SR*) * sqrt(T-1) / sqrt(1 - gamma3*SR_hat + (gamma4-1)/4*SR_hat^2))
    """
    returns = np.asarray(returns, dtype=float)
    returns = returns[~np.isnan(returns)]
    T = len(returns)
    if T < 5:
        return 0.0
    sr_hat = _sample_sharpe(returns)
    gamma3 = float(skew(returns))
    gamma4 = float(kurtosis(returns, fisher=False))
    denom = 1.0 - gamma3 * sr_hat + (gamma4 - 1.0) / 4.0 * sr_hat ** 2
    if denom <= 0:
        return 0.5
    z = (sr_hat - sr_benchmark) * np.sqrt(T - 1) / np.sqrt(denom)
    return float(norm.cdf(z))


def deflated_sharpe_ratio(
    returns: np.ndarray,
    n_trials: int,
    sr_variance: float,
) -> float:
    """
    DSR = PSR avec benchmark = SR* attendu sous H0 après N trials.

    SR_0 = sqrt(sr_variance) * (
        (1 - gamma_euler) * Phi^-1(1 - 1/N) + gamma_euler * Phi^-1(1 - 1/(N*e))
    )
    """
    if n_trials < 1:
        raise ValueError(f"n_trials >= 1 requis, reçu {n_trials}")
    gamma_euler = 0.5772156649
    inv_n = max(min(1.0 - 1.0 / n_trials, 1.0 - 1e-12), 1e-12)
    inv_n_e = max(min(1.0 - 1.0 / (n_trials * np.e), 1.0 - 1e-12), 1e-12)
    sr_0 = np.sqrt(sr_variance) * (
        (1.0 - gamma_euler) * norm.ppf(inv_n)
        + gamma_euler * norm.ppf(inv_n_e)
    )
    return probabilistic_sharpe_ratio(returns, sr_benchmark=float(sr_0))


def probability_backtest_overfitting(
    pnl_matrix: np.ndarray,
    n_splits: int = 16,
) -> float:
    """
    PBO via méthode combinatoire de Bailey-LdP.

    pnl_matrix : (T, N) où N = configs, T = time.
    PBO = fraction des combos où best IS rank tombe dans la moitié basse OOS.
    """
    pnl_matrix = np.asarray(pnl_matrix, dtype=float)
    T, N = pnl_matrix.shape
    if N < 2:
        raise ValueError("Au moins 2 configs requises")
    if n_splits < 2 or n_splits > T:
        raise ValueError(f"n_splits invalide : {n_splits}")
    if n_splits % 2 != 0:
        n_splits -= 1

    groups = np.array_split(np.arange(T), n_splits)
    logit_ranks = []
    half = n_splits // 2
    for is_indices in combinations(range(n_splits), half):
        is_set = set(is_indices)
        oos_set = [g for g in range(n_splits) if g not in is_set]
        is_idx = np.concatenate([groups[g] for g in is_indices])
        oos_idx = np.concatenate([groups[g] for g in oos_set])

        is_pnl = pnl_matrix[is_idx]
        oos_pnl = pnl_matrix[oos_idx]

        is_sharpe = np.array([_sample_sharpe(is_pnl[:, c]) for c in range(N)])
        oos_sharpe = np.array([_sample_sharpe(oos_pnl[:, c]) for c in range(N)])

        best_is = int(np.argmax(is_sharpe))
        oos_rank = float((np.argsort(np.argsort(oos_sharpe))[best_is] + 1) / N)
        rr = float(np.clip(oos_rank, 1e-6, 1 - 1e-6))
        logit_ranks.append(np.log(rr / (1.0 - rr)))

    return float(np.mean(np.array(logit_ranks) < 0))
