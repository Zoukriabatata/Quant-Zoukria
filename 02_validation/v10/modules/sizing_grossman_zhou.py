"""
Grossman-Zhou Drawdown-Constrained Optimal Investment (Grossman & Zhou 1993).

Sizing optimal sous contrainte de drawdown maximal — CRITIQUE pour respecter
le trailing DD de $2,000 sur Apex 50k Eval. La fraction optimale converge
vers zéro à mesure que l'equity approche du floor (M_t - DD_max).

Mathématique :
    pi*(t) = (mu - r) / (gamma * sigma^2) * (W_t - alpha * M_t) / W_t

où :
    W_t   = equity courant
    M_t   = high-water mark (max equity vu)
    alpha = fraction du HWM en dessous de laquelle on ne descend pas
    mu-r  = excess return attendu par trade
    gamma = coefficient d'aversion au risque CRRA
    sigma^2 = variance forecast (input HAR-RV)

Le facteur (W_t - alpha M_t) / W_t = "buffer relatif" capture la marge
restante avant de toucher le floor. À equity = alpha*M_t, ce facteur est 0
=> pi* = 0 (interdit de prendre du risque).

Reference: Grossman, S.J. & Zhou, Z. (1993). "Optimal Investment Strategies
for Controlling Drawdowns", Mathematical Finance 3(3), 241-276.
"""
from __future__ import annotations


def apex_floor_alpha(hwm: float, max_dd_dollars: float) -> float:
    """
    Convertit un trailing DD absolu en alpha relatif au HWM courant.

    floor_$ = HWM - max_dd_dollars
    alpha = floor_$ / HWM = 1 - max_dd_dollars / HWM

    Parameters
    ----------
    hwm : float
        High-water mark courant (en $).
    max_dd_dollars : float
        Trailing drawdown maximal autorisé (en $). Ex: 2000 pour Apex 50k.

    Returns
    -------
    float
        alpha dans (0, 1).
    """
    if hwm <= 0:
        raise ValueError(f"hwm doit être > 0, reçu {hwm}")
    if max_dd_dollars <= 0:
        raise ValueError(f"max_dd_dollars doit être > 0, reçu {max_dd_dollars}")
    if max_dd_dollars >= hwm:
        raise ValueError(
            f"max_dd_dollars ({max_dd_dollars}) >= hwm ({hwm}) : floor négatif impossible"
        )
    return 1.0 - max_dd_dollars / hwm


def grossman_zhou_fraction(
    equity: float,
    hwm: float,
    alpha: float,
    mu_excess: float,
    sigma2: float,
    gamma: float,
) -> float:
    """
    Calcule la fraction optimale Grossman-Zhou de richesse à allouer.

    Parameters
    ----------
    equity : float
        Equity courant W_t.
    hwm : float
        High-water mark M_t.
    alpha : float
        Fraction du HWM constituant le floor (alpha * M_t).
    mu_excess : float
        Excess return attendu par trade (mu - r).
    sigma2 : float
        Variance forecast (doit être > 0).
    gamma : float
        Coefficient d'aversion au risque CRRA (doit être > 0).

    Returns
    -------
    float
        pi* >= 0. Clipped à 0 si le calcul donne négatif (sous le floor).
    """
    if sigma2 <= 0:
        raise ValueError(f"sigma2 doit être > 0, reçu {sigma2}")
    if gamma <= 0:
        raise ValueError(f"gamma doit être > 0, reçu {gamma}")
    if equity <= 0:
        return 0.0

    buffer_rel = (equity - alpha * hwm) / equity
    if buffer_rel <= 0:
        return 0.0

    return (mu_excess / (gamma * sigma2)) * buffer_rel


def gz_shrinkage_factor(
    equity: float,
    hwm: float,
    max_dd_dollars: float,
) -> float:
    """
    Forme ADAPTATIVE de Grossman-Zhou : facteur de shrinkage multiplicatif.

    shrinkage = (W_t - alpha*M_t) / ((1 - alpha) * M_t)
              = (W_t - (M_t - DD_max)) / DD_max
              = buffer_dollars / max_dd_dollars

    Interprétation :
        1.0 → W_t au peak (full buffer)
        0.5 → W_t à mi-chemin entre peak et floor
        0.0 → W_t au floor (DD max atteint, plus de risque)

    Cette forme évite les pathologies du GZ pur (mu/(gamma*sigma²) explosif)
    en agissant uniquement comme garde DD multiplicative sur un sizing baseline
    (typiquement le sizing Kelly v9).

    Parameters
    ----------
    equity : float
        Equity courant W_t.
    hwm : float
        High-water mark M_t.
    max_dd_dollars : float
        Trailing DD maximum autorisé (= floor sous le HWM).

    Returns
    -------
    float
        Shrinkage factor dans [0, 1].
    """
    if hwm <= 0:
        return 0.0
    if max_dd_dollars <= 0:
        raise ValueError(f"max_dd_dollars doit être > 0, reçu {max_dd_dollars}")

    floor_dollars = hwm - max_dd_dollars
    buffer_dollars = equity - floor_dollars
    if buffer_dollars <= 0:
        return 0.0
    raw = buffer_dollars / max_dd_dollars
    return min(1.0, raw)


def apply_gz_shrinkage(
    baseline_contracts: int,
    equity: float,
    hwm: float,
    max_dd_dollars: float,
) -> int:
    """
    Applique le shrinkage GZ à un nombre de contrats baseline (typiquement
    issus du sizing Kelly v9). Garantit que le résultat n'EXCÈDE JAMAIS
    le baseline (uniquement réduit ou égal).

    Returns
    -------
    int
        floor(baseline * shrinkage), dans [0, baseline].
    """
    if baseline_contracts <= 0:
        return 0
    s = gz_shrinkage_factor(equity=equity, hwm=hwm, max_dd_dollars=max_dd_dollars)
    return int(baseline_contracts * s)


def grossman_zhou_contracts(
    equity: float,
    hwm: float,
    max_dd_dollars: float,
    mu_excess: float,
    sigma2: float,
    gamma: float,
    point_value: float,
    sl_points: float,
    max_contracts: int = 12,
) -> int:
    """
    Traduit la fraction Grossman-Zhou en nombre entier de contrats.

    Logique : dollar_risk_par_contrat = sl_points * point_value
              dollar_alloue = pi* * equity
              n_contracts = floor(dollar_alloue / dollar_risk_par_contrat)

    Parameters
    ----------
    equity, hwm : float
        Equity et HWM courants.
    max_dd_dollars : float
        Trailing DD autorisé (Apex = 2000).
    mu_excess, sigma2, gamma : float
        Inputs Grossman-Zhou.
    point_value : float
        Valeur d'un point sur l'instrument (MNQ = $2, NQ = $20, MES = $5, ES = $50).
    sl_points : float
        Stop-loss en points (utilisé pour convertir fraction en contracts).
    max_contracts : int, default 12
        Cap absolu (= plafond du v9 Apex).

    Returns
    -------
    int
        Nombre de contrats à trader, dans [0, max_contracts].
    """
    if point_value <= 0:
        raise ValueError(f"point_value doit être > 0, reçu {point_value}")
    if sl_points <= 0:
        raise ValueError(f"sl_points doit être > 0, reçu {sl_points}")
    if max_contracts < 0:
        raise ValueError(f"max_contracts doit être >= 0, reçu {max_contracts}")

    alpha = apex_floor_alpha(hwm=hwm, max_dd_dollars=max_dd_dollars)
    pi = grossman_zhou_fraction(
        equity=equity, hwm=hwm, alpha=alpha,
        mu_excess=mu_excess, sigma2=sigma2, gamma=gamma,
    )

    dollar_risk_per_contract = sl_points * point_value
    dollar_allocated = pi * equity
    n = int(dollar_allocated / dollar_risk_per_contract)
    return max(0, min(n, max_contracts))
