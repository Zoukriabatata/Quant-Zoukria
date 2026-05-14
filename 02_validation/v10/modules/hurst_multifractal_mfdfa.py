"""
MF-DFA — Multifractal Detrended Fluctuation Analysis (Kantelhardt 2002).

Reference: Kantelhardt, J.W., Zschiegner, S.A., Koscielny-Bunde, E.,
Bunde, A., Havlin, S., & Stanley, H.E. (2002). "Multifractal detrended
fluctuation analysis of nonstationary time series", Physica A 316.

Algorithme :
    1. Profil Y(i) = sum_{k=1}^{i} (x_k - <x>)
    2. Pour chaque échelle s ∈ [s_min, s_max], divise Y en N_s = N//s
       segments de longueur s (deux fois : depuis le début et depuis la fin
       pour ne pas perdre les bars qui ne rentrent pas exactement).
    3. Pour chaque segment v, calcule la tendance par polynôme degré m
       et la variance F²(s, v) = (1/s) * sum_{i=1}^{s} (Y_v(i) - p_v(i))²
    4. Fonction de fluctuation d'ordre q :
       F_q(s) = [(1/(2*N_s)) * sum F²(s,v)^(q/2)]^(1/q)  pour q != 0
       log F_0(s) = (1/(2*N_s)) * sum log F²(s,v) / 2     (limit q -> 0)
    5. Si série multifractale : F_q(s) ~ s^h(q)
       → régression linéaire log(F_q(s)) vs log(s) donne h(q)

Pour q=2 : h(2) = exposant de Hurst classique (DFA).
Pour mono-fractal (fBm) : h(q) ≈ constante.
Pour multi-fractal : h(q) décroît avec q.

Usage v10 :
    - h(2) remplace l'estimateur Hurst R/S du v9 (DFA est plus robuste)
    - width = h(q_min) - h(q_max) = indice de multifractalité
    - Filter idea : si width > seuil, le régime est trop complexe → skip MR
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd


_MIN_LENGTH = 64
_POLY_ORDER = 1  # tendance linéaire par segment (DFA classique)


def compute_mfdfa(
    series: pd.Series,
    q_values: List[float],
    s_min: int = 8,
    s_max: Optional[int] = None,
    n_scales: int = 12,
) -> Dict[float, float]:
    """
    Calcule h(q) pour chaque q via MF-DFA.

    Parameters
    ----------
    series : pd.Series
        Série temporelle (typiquement log-prices ou prix bruts).
    q_values : list of float
        Valeurs de q à évaluer. q=2 → Hurst classique.
    s_min : int, default 8
        Plus petite échelle (en bars).
    s_max : int, default N//4
        Plus grande échelle.
    n_scales : int, default 12
        Nombre d'échelles log-espacées entre s_min et s_max.

    Returns
    -------
    dict[float, float]
        Mapping q -> h(q).
    """
    if not q_values:
        raise ValueError("q_values ne peut pas être vide")
    x = series.to_numpy(dtype=float)
    x = x[~np.isnan(x)]
    N = len(x)
    if N < _MIN_LENGTH:
        raise ValueError(f"Série trop courte : {N} < {_MIN_LENGTH}")

    if s_max is None:
        s_max = N // 4
    s_max = min(s_max, N // 4)
    if s_max < s_min:
        raise ValueError(f"s_max ({s_max}) < s_min ({s_min})")

    # ── Profil cumulatif ──────────────────────────────────
    Y = np.cumsum(x - x.mean())

    # ── Échelles log-espacées ─────────────────────────────
    scales = np.unique(
        np.round(np.exp(np.linspace(np.log(s_min), np.log(s_max), n_scales))).astype(int)
    )
    scales = scales[(scales >= s_min) & (scales <= s_max)]

    # ── Fonction de fluctuation pour chaque échelle ───────
    F_q_s = {q: [] for q in q_values}
    for s in scales:
        Ns = N // s
        # Segments depuis le début ET depuis la fin (2*Ns)
        F2 = np.zeros(2 * Ns)
        x_axis = np.arange(s)
        for v in range(Ns):
            seg_start = Y[v * s: (v + 1) * s]
            seg_end = Y[N - (v + 1) * s: N - v * s]
            for idx, seg in enumerate([seg_start, seg_end]):
                # Detrend : polyfit + résidu
                p = np.polyfit(x_axis, seg, _POLY_ORDER)
                trend = np.polyval(p, x_axis)
                F2[v + idx * Ns] = np.mean((seg - trend) ** 2)

        # F_q(s) pour chaque q
        F2 = np.maximum(F2, 1e-20)  # éviter log(0)
        for q in q_values:
            if abs(q) < 1e-6:
                # Cas q=0 : moyenne géométrique
                Fq = np.exp(0.25 * np.mean(np.log(F2)))
            else:
                Fq = (np.mean(F2 ** (q / 2.0))) ** (1.0 / q)
            F_q_s[q].append(Fq)

    # ── Régression log F_q(s) vs log(s) → h(q) ───────────
    log_s = np.log(scales)
    h_q = {}
    for q in q_values:
        log_Fq = np.log(F_q_s[q])
        slope, _ = np.polyfit(log_s, log_Fq, 1)
        h_q[q] = float(np.clip(slope, 0.0, 2.0))

    return h_q


def compute_multifractality_width(
    series: pd.Series,
    q_min: float = -5.0,
    q_max: float = 5.0,
    q_step: float = 1.0,
    s_min: int = 8,
    s_max: Optional[int] = None,
) -> float:
    """
    Calcule l'indice de multifractalité = h(q_min) - h(q_max).

    Une série mono-fractale (fBm) donne width ≈ 0 (h(q) constant).
    Une série multifractale (cascade, hétéroskédasticité forte) donne width > 0.
    """
    q_values = list(np.arange(q_min, q_max + q_step / 2, q_step))
    h_q = compute_mfdfa(series, q_values=q_values, s_min=s_min, s_max=s_max)
    h_values = list(h_q.values())
    return float(max(h_values) - min(h_values))
