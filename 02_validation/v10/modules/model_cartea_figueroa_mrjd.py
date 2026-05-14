"""
Cartea-Figueroa Mean-Reverting Jump-Diffusion (Cartea & Figueroa 2005).

Modèle stochastique pour les séries mean-reverting avec sauts :

    dS_t = theta*(mu - S_t)*dt + sigma*dW_t + J_t*dN_t

avec :
    theta  : vitesse de mean reversion
    mu     : moyenne long-terme
    sigma  : volatilité diffusive
    W_t    : mouvement brownien
    N_t    : processus de Poisson d'intensité lambda
    J_t    : taille du jump ~ N(eta, delta^2)

Reference: Cartea, A. & Figueroa, M.G. (2005). "Pricing in Electricity Markets:
A Mean Reverting Jump Diffusion Model", Applied Mathematical Finance 12(4).

Usage dans v10 : calibration sur les résidus du Hurst_MR (price - rolling_mean)
+ détection des jumps dans le résidu → kill-switch MR complémentaire à
Lee-Mykland qui opère sur les returns.

Méthode de calibration (hybride OLS + outlier detection) :
    1. OLS sur X_{t+1} = alpha + beta*X_t + eps_t (forme discrète AR(1))
    2. theta = -log(beta) / dt
    3. mu = alpha / (1 - beta)
    4. Détection jumps : |eps_t| > k*sd(eps_t)  (k via Gumbel asymptote LM)
    5. Re-estime sigma sur eps_t hors jumps, lambda = #jumps/N, eta = mean
       des jumps, delta = std des jumps.
"""
from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd


_MIN_OBS = 30


def _estimate_jump_threshold(n: int, alpha: float) -> float:
    """Seuil critique asymptotique Gumbel pour |z| sous H0 (pas de jump)."""
    log_n = np.log(max(n, 2))
    a_n = 1.0 / np.sqrt(2.0 * log_n)
    b_n = np.sqrt(2.0 * log_n) - (np.log(np.pi) + np.log(log_n)) / (
        2.0 * np.sqrt(2.0 * log_n)
    )
    beta_alpha = -np.log(-np.log(1.0 - alpha))
    return a_n * beta_alpha + b_n


def calibrate_mrjd_params(
    residuals: pd.Series,
    dt: float = 1.0,
    alpha: float = 0.01,
) -> Dict[str, float]:
    """
    Calibre les paramètres MRJD sur une série de résidus mean-reverting.

    Parameters
    ----------
    residuals : pd.Series
        Série temporelle (typiquement résidus price - rolling_mean).
    dt : float, default 1.0
        Pas de temps entre observations.
    alpha : float, default 0.01
        Niveau de significativité pour la détection des jumps via OLS residuals.

    Returns
    -------
    dict
        - theta  : vitesse mean reversion
        - mu     : moyenne long-terme
        - sigma  : volatilité diffusive (sans jumps)
        - lambda : intensité Poisson (jumps par unité de temps)
        - eta    : moyenne taille des jumps
        - delta  : std taille des jumps
    """
    if len(residuals) < _MIN_OBS:
        raise ValueError(f"Au moins {_MIN_OBS} obs requises, reçu {len(residuals)}")
    if not (0.0 < alpha < 1.0):
        raise ValueError(f"alpha doit être dans (0, 1), reçu {alpha}")

    x = residuals.to_numpy(dtype=float)
    x = x[~np.isnan(x)]
    n = len(x)
    if n < _MIN_OBS:
        raise ValueError(f"Trop peu d'obs valides après nan-drop : {n}")

    # ── 1. OLS X_{t+1} = alpha_ + beta * X_t + eps_t ──────
    X_t = x[:-1]
    X_tp1 = x[1:]
    design = np.column_stack([np.ones(len(X_t)), X_t])
    coeffs, *_ = np.linalg.lstsq(design, X_tp1, rcond=None)
    alpha_ols, beta_ols = coeffs

    # Clipper beta dans (1e-6, 0.9999) pour log défini
    beta_safe = float(np.clip(beta_ols, 1e-6, 0.9999))

    # ── 2. Conversion vers paramètres continus ────────────
    theta = -np.log(beta_safe) / dt
    mu = alpha_ols / (1.0 - beta_safe) if abs(1 - beta_safe) > 1e-9 else 0.0

    # ── 3. Résidus eps_t ──────────────────────────────────
    eps = X_tp1 - (alpha_ols + beta_ols * X_t)
    sd_eps = float(np.std(eps, ddof=1)) if len(eps) > 1 else 0.0

    # ── 4. Détection jumps via seuil Gumbel ──────────────
    if sd_eps > 0:
        z_eps = eps / sd_eps
        threshold = _estimate_jump_threshold(len(eps), alpha)
        jump_mask = np.abs(z_eps) > threshold
    else:
        jump_mask = np.zeros_like(eps, dtype=bool)

    n_jumps = int(jump_mask.sum())
    n_eff = len(eps)

    # ── 5. Estimation des params jump et diffusion ───────
    lambda_ = n_jumps / (n_eff * dt) if n_eff > 0 else 0.0

    if n_jumps > 0:
        jumps = eps[jump_mask]
        eta = float(np.mean(jumps))
        delta = float(np.std(jumps, ddof=1)) if n_jumps > 1 else 0.0
    else:
        eta = 0.0
        delta = 0.0

    # Sigma diffusive estimé sur résidus HORS jumps
    diff_eps = eps[~jump_mask]
    if len(diff_eps) > 1:
        sd_diff = float(np.std(diff_eps, ddof=1))
    else:
        sd_diff = sd_eps
    # Conversion OU : sigma = sd_eps * sqrt(2*theta / (1 - beta^2))
    denom = (1.0 - beta_safe ** 2)
    sigma = sd_diff * np.sqrt(2.0 * theta / denom) if denom > 1e-9 and theta > 0 else sd_diff

    return {
        "theta": float(theta),
        "mu": float(mu),
        "sigma": float(sigma),
        "lambda": float(lambda_),
        "eta": float(eta),
        "delta": float(delta),
    }


def detect_jumps_in_residuals(
    residuals: pd.Series,
    alpha: float = 0.01,
) -> pd.Series:
    """
    Détecte les jumps dans une série de résidus via OLS + seuil Gumbel.

    Méthode :
        1. Fit AR(1) sur la série : X_{t+1} = a + b*X_t + eps_t
        2. Standardise eps_t / sd(eps_t)
        3. Flag bar i si |z_eps_i| > seuil_Gumbel(n, alpha)

    Returns
    -------
    pd.Series
        Bool series même longueur que residuals, True si jump détecté.
        Premier point = False par convention (besoin de X_{t-1}).
    """
    if not (0.0 < alpha < 1.0):
        raise ValueError(f"alpha doit être dans (0, 1), reçu {alpha}")
    n = len(residuals)
    flags = pd.Series(False, index=residuals.index, dtype=bool)
    if n < _MIN_OBS:
        return flags

    x = residuals.to_numpy(dtype=float)
    valid_mask = ~np.isnan(x)
    if valid_mask.sum() < _MIN_OBS:
        return flags

    X_t = x[:-1]
    X_tp1 = x[1:]
    design = np.column_stack([np.ones(len(X_t)), X_t])
    coeffs, *_ = np.linalg.lstsq(design, X_tp1, rcond=None)
    a_ols, b_ols = coeffs

    eps = X_tp1 - (a_ols + b_ols * X_t)
    sd_eps = float(np.std(eps, ddof=1)) if len(eps) > 1 else 0.0
    if sd_eps <= 0:
        return flags

    z = eps / sd_eps
    threshold = _estimate_jump_threshold(len(eps), alpha)
    jump_bool = np.abs(z) > threshold

    # eps[i] = residual_change from index i to i+1, so flag index i+1
    flags.iloc[1:] = jump_bool
    return flags
