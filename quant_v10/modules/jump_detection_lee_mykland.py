"""
Lee-Mykland Jump Detection (Lee & Mykland 2008, RFS 21(6)).

Test non-paramétrique de détection de jumps intra-day sur séries de prix
haute fréquence. Filtre OBLIGATOIRE pour stratégies mean-reversion :
le MR ne fonctionne PAS pendant les jumps, donc on désactive le signal
sur les bars détectés comme jumps.

Mathématique :
    r_i = log(P_i) - log(P_{i-1})
    sigma_hat_i^2 = (pi/2) * (1/(K-2)) * sum_{j=i-K+2}^{i-1} |r_{j-1}| * |r_j|
    L_i = r_i / sigma_hat_i

Sous H_0 (pas de jump dans la fenêtre), avec n observations :
    (max_i |L_i| - b_n) / a_n  ->  Gumbel(0, 1)
    a_n = (2 log n)^{-1/2}
    b_n = (2 log n)^{1/2} - (log(pi) + log(log n)) / (2 (2 log n)^{1/2})

Rejet H_0 à seuil alpha si :
    |L_i| > a_n * beta_alpha + b_n,  beta_alpha = -log(-log(1 - alpha))

Pour alpha = 1% : beta_alpha ≈ 4.6
Pour alpha = 0.1% : beta_alpha ≈ 6.9

Reference: Lee, S.S. & Mykland, P.A. (2008).
"Jumps in Financial Markets: A New Nonparametric Test and Jump Dynamics",
Review of Financial Studies, 21(6), 2535-2563.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


_BIPOWER_BIAS_CORRECTION = np.pi / 2.0  # E[|N(0,1)| * |N(0,1)|] = 2/pi


def detect_jumps(
    prices: pd.Series,
    window: int = 156,
    alpha: float = 0.01,
) -> pd.DataFrame:
    """
    Détecte les jumps Lee-Mykland sur une série de prix.

    Parameters
    ----------
    prices : pd.Series
        Série de prix (niveaux, pas returns) indexée par datetime.
    window : int, default 156
        Taille K de la fenêtre de bipower variation locale.
        Recommandé : 270 pour bars 5min (Lee-Mykland 2008),
        156 pour bars 5min sur session NY (~13h).
        Doit être >= 3.
    alpha : float, default 0.01
        Niveau de significativité du test (Type-I error).
        Doit être dans (0, 1).

    Returns
    -------
    pd.DataFrame
        Colonnes :
        - 'L_stat'    : statistique de test L_i = r_i / sigma_hat_i
        - 'sigma_hat' : volatilité locale estimée (bipower)
        - 'jump_flag' : bool, True si bar i détecté comme jump
        - 'threshold' : seuil critique appliqué (constant pour alpha donné)
        Index identique à `prices`.
    """
    # ── Validation ─────────────────────────────────────────
    if window < 3:
        raise ValueError(f"window doit être >= 3, reçu {window}")
    if not (0.0 < alpha < 1.0):
        raise ValueError(f"alpha doit être dans (0, 1), reçu {alpha}")

    n = len(prices)
    out = pd.DataFrame(
        index=prices.index,
        data={
            "L_stat": np.nan,
            "sigma_hat": np.nan,
            "jump_flag": False,
            "threshold": np.nan,
        },
    )

    if n < window + 1:
        return out

    # ── Log-returns ────────────────────────────────────────
    log_prices = np.log(prices.to_numpy(dtype=float))
    log_rets = np.diff(log_prices, prepend=np.nan)  # r_1 = NaN par convention

    # ── Bipower variation locale (fenêtre glissante de taille K-2) ──
    # BV_i = (1/(K-2)) * sum_{j=i-K+2}^{i-1} |r_{j-1}| * |r_j|
    # On calcule |r_{j-1}| * |r_j| à chaque j, puis somme rolling K-2.
    abs_rets = np.abs(log_rets)
    bipower_products = abs_rets[:-1] * abs_rets[1:]  # |r_{j-1}| * |r_j| à position j
    bipower_products = np.concatenate([[np.nan], bipower_products])  # align à index j

    # Rolling sum sur K-2 termes finissant à i-1 (donc exclut r_i)
    bp_series = pd.Series(bipower_products, index=prices.index)
    rolling_bp = bp_series.rolling(window=window - 2, min_periods=window - 2).sum()
    # Shift d'1 pour exclure r_i de la somme (sigma_hat_i utilise r_{i-K+2}..r_{i-1})
    rolling_bp = rolling_bp.shift(1)

    sigma2_hat = _BIPOWER_BIAS_CORRECTION * rolling_bp / (window - 2)
    sigma_hat = np.sqrt(sigma2_hat)

    # ── Statistique L_i ────────────────────────────────────
    L_stat = pd.Series(log_rets, index=prices.index) / sigma_hat

    # ── Seuil critique asymptotique (Gumbel) ───────────────
    # On utilise n_eff = nombre de bars valides post-warmup
    n_eff = max(int((~sigma_hat.isna()).sum()), 2)
    log_n = np.log(n_eff)
    a_n = 1.0 / np.sqrt(2.0 * log_n)
    b_n = np.sqrt(2.0 * log_n) - (np.log(np.pi) + np.log(log_n)) / (
        2.0 * np.sqrt(2.0 * log_n)
    )
    beta_alpha = -np.log(-np.log(1.0 - alpha))
    threshold = a_n * beta_alpha + b_n

    # ── Flag jumps ─────────────────────────────────────────
    jump_flag = L_stat.abs() > threshold
    # NaN -> False (warm-up period)
    jump_flag = jump_flag.fillna(False).astype(bool)

    out["L_stat"] = L_stat
    out["sigma_hat"] = sigma_hat
    out["jump_flag"] = jump_flag
    out["threshold"] = threshold

    return out
