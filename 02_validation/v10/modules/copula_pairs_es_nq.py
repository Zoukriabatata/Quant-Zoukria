"""
Copula Pairs Trading — Gaussian copula MVP pour ES/NQ.

Méthode (Hudson & Thames / Sklar's theorem) :
    1. Transformer chaque série en uniforme via CDF empirique
    2. Fit Gaussian copula : rho = corr(Phi^-1(u), Phi^-1(v))
    3. Calculer P(U <= u | V = v) via formule conditionnelle Gaussienne
    4. Signal :  P_high  → X surévalué, SHORT spread
                P_low   → X sous-évalué, LONG spread

Conditional CDF Gaussien :
    P(U <= u | V = v) = Phi((Phi^-1(u) - rho * Phi^-1(v)) / sqrt(1 - rho^2))

Reference: Liew & Wu (2013), "Pairs Trading: A Copula Approach".
Hudson & Thames, "Copula Pairs Trading Overview".
"""
from __future__ import annotations

from typing import Tuple

import numpy as np
import pandas as pd
from scipy.stats import norm


def empirical_cdf_transform(series: pd.Series) -> pd.Series:
    """
    Transforme une série en pseudo-uniformes via la CDF empirique.

    u_i = rank(x_i) / (n + 1)   (formule "Hazen" pour éviter 0 et 1 exacts)

    Returns
    -------
    pd.Series
        Uniformes dans (0, 1).
    """
    ranks = series.rank(method="average")
    n = len(series)
    u = ranks / (n + 1)
    u.name = "u"
    return u


def fit_gaussian_copula(x: pd.Series, y: pd.Series) -> float:
    """
    Estime le paramètre rho d'une copule Gaussienne.

    rho = Pearson correlation(Phi^-1(u), Phi^-1(v))
    où u, v sont les transformées CDF empiriques de x, y.
    """
    u = empirical_cdf_transform(x).to_numpy()
    v = empirical_cdf_transform(y).to_numpy()
    z_u = norm.ppf(u)
    z_v = norm.ppf(v)
    # Pearson sur les Z
    rho = float(np.corrcoef(z_u, z_v)[0, 1])
    # Clip pour éviter rho = ±1 exact
    return float(np.clip(rho, -0.999, 0.999))


def conditional_probability(u: float, v: float, rho: float) -> float:
    """
    Calcule P(U <= u | V = v) pour copule Gaussienne.

    P(U <= u | V = v) = Phi((Phi^-1(u) - rho * Phi^-1(v)) / sqrt(1 - rho^2))

    Returns
    -------
    float
        Probabilité conditionnelle dans [0, 1].
    """
    if not (-1.0 < rho < 1.0):
        raise ValueError(f"rho doit être dans (-1, 1), reçu {rho}")
    if not (0.0 < u < 1.0):
        raise ValueError(f"u doit être dans (0, 1), reçu {u}")
    if not (0.0 < v < 1.0):
        raise ValueError(f"v doit être dans (0, 1), reçu {v}")

    z_u = norm.ppf(u)
    z_v = norm.ppf(v)
    denom = np.sqrt(1.0 - rho ** 2)
    z_cond = (z_u - rho * z_v) / denom
    return float(norm.cdf(z_cond))


def compute_mispricing_signal(
    x: pd.Series,
    y: pd.Series,
    lookback: int = 500,
    p_high: float = 0.95,
    p_low: float = 0.05,
) -> pd.DataFrame:
    """
    Calcule la série de signaux de mispricing entre X et Y via copule Gaussienne.

    Pour chaque date t :
        1. Fit copule sur x[t-lookback:t], y[t-lookback:t]
        2. Compute u_t = F_X(x_t), v_t = F_Y(y_t)
        3. Compute p_t = P(U <= u_t | V = v_t)
        4. Signal : -1 si p_t > p_high (X surévalué)
                    +1 si p_t < p_low (X sous-évalué)
                     0 sinon

    Returns
    -------
    pd.DataFrame
        Colonnes :
        - 'rho' : rho calibré rolling
        - 'conditional_prob' : P(U_t <= u_t | V_t = v_t)
        - 'signal' : -1 / 0 / +1
    """
    if len(x) != len(y):
        raise ValueError(f"x ({len(x)}) et y ({len(y)}) doivent avoir même longueur")
    n = len(x)

    out = pd.DataFrame(
        index=x.index,
        data={"rho": np.nan, "conditional_prob": np.nan, "signal": 0},
    )
    out["signal"] = out["signal"].astype(int)

    if n <= lookback:
        return out

    x_arr = x.to_numpy()
    y_arr = y.to_numpy()

    for t in range(lookback, n):
        win_x = pd.Series(x_arr[t - lookback: t])
        win_y = pd.Series(y_arr[t - lookback: t])

        try:
            rho = fit_gaussian_copula(win_x, win_y)
        except Exception:
            continue

        # Position courante : rank de x_t et y_t dans la fenêtre étendue
        ext_x = np.append(x_arr[t - lookback: t], x_arr[t])
        ext_y = np.append(y_arr[t - lookback: t], y_arr[t])
        rank_x = pd.Series(ext_x).rank(method="average").iloc[-1]
        rank_y = pd.Series(ext_y).rank(method="average").iloc[-1]
        u = float(rank_x / (lookback + 2))
        v = float(rank_y / (lookback + 2))
        # Clip pour éviter exact 0/1
        u = float(np.clip(u, 0.001, 0.999))
        v = float(np.clip(v, 0.001, 0.999))

        try:
            p = conditional_probability(u, v, rho)
        except Exception:
            continue

        out.iloc[t, out.columns.get_loc("rho")] = rho
        out.iloc[t, out.columns.get_loc("conditional_prob")] = p
        if p > p_high:
            out.iloc[t, out.columns.get_loc("signal")] = -1
        elif p < p_low:
            out.iloc[t, out.columns.get_loc("signal")] = 1
        else:
            out.iloc[t, out.columns.get_loc("signal")] = 0

    return out
