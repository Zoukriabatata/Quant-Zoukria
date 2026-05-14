"""
Tests MF-DFA (Multifractal Detrended Fluctuation Analysis).

Reference: Kantelhardt, J.W. et al. (2002). "Multifractal detrended fluctuation
analysis of nonstationary time series", Physica A 316.

Pour fBm mono-fractal : H(q) ≈ constant.
Pour multi-fractal : H(q) décroît avec q.
"""
import numpy as np
import pandas as pd
import pytest

from quant_v10.modules.hurst_multifractal_mfdfa import (
    compute_mfdfa,
    compute_multifractality_width,
)


def _white_noise(n=2048, seed=42):
    """Bruit blanc Gaussien standard. h(2) attendu = 0.5 via MF-DFA."""
    rng = np.random.default_rng(seed)
    return pd.Series(rng.normal(0, 1, n))


def _random_walk(n=2048, seed=42):
    """Marche aléatoire (cumsum bruit blanc). h(2) attendu = 1.5 via MF-DFA."""
    rng = np.random.default_rng(seed)
    return pd.Series(np.cumsum(rng.normal(0, 1, n)))


def _fbm_synthetic(n=2048, H=0.7, seed=42):
    """Compat ancien nom — retourne un random walk (h(2)=1.5)."""
    return _random_walk(n=n, seed=seed)


def _multifractal_cascade(n=2048, p=0.6, seed=1):
    """
    Cascade binomiale multifractale : à chaque niveau, scinde la mesure en 2
    avec poids p et 1-p. Donne un spectre H(q) non-trivial.
    """
    rng = np.random.default_rng(seed)
    # log2(n) levels
    levels = int(np.log2(n))
    measure = np.ones(2 ** levels)
    for level in range(levels):
        size = 2 ** (level + 1)
        # Pour chaque paire de mesures à ce niveau, multiplie par p et 1-p
        for i in range(0, 2 ** levels, 2 ** (levels - level)):
            half = 2 ** (levels - level - 1)
            if rng.random() < 0.5:
                measure[i: i + half] *= p
                measure[i + half: i + 2 * half] *= (1 - p)
            else:
                measure[i: i + half] *= (1 - p)
                measure[i + half: i + 2 * half] *= p
    return pd.Series(np.cumsum(measure))


# ───────────────────────────────────────────────────────────
# 1. compute_mfdfa
# ───────────────────────────────────────────────────────────
def test_compute_mfdfa_returns_dict():
    series = _fbm_synthetic(n=1024)
    result = compute_mfdfa(series, q_values=[-5, -1, 1, 2, 5])
    assert isinstance(result, dict)
    assert set(result.keys()) == {-5, -1, 1, 2, 5}


def test_h_q_values_in_valid_range():
    """H(q) doit être dans [0, 2] pour des séries financières."""
    series = _fbm_synthetic(n=1024)
    result = compute_mfdfa(series, q_values=[-5, -1, 1, 2, 5])
    for q, h in result.items():
        assert 0.0 <= h <= 2.0, f"H({q}) = {h} hors fourchette"


def test_h_at_q2_close_to_classical_hurst():
    """
    Sur bruit blanc (input = returns), MF-DFA fait cumsum interne → h(2) ≈ 0.5
    (= Hurst classique des returns indépendants).
    """
    series = _white_noise(n=2048)
    result = compute_mfdfa(series, q_values=[2])
    assert 0.3 < result[2] < 0.7, f"H(2) = {result[2]:.3f} hors fourchette pour bruit blanc"


def test_monofractal_has_flat_hq_spectrum():
    """Sur cumsum bruit blanc (mono-fractal), H(q) doit être quasi-constant."""
    series = _fbm_synthetic(n=2048, H=0.5)
    result = compute_mfdfa(series, q_values=[-3, -1, 1, 3])
    h_values = list(result.values())
    spread = max(h_values) - min(h_values)
    assert spread < 0.30, f"H(q) spread {spread:.3f} > 0.30 sur série mono-fractale"


def test_too_short_series_raises():
    series = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    with pytest.raises(ValueError, match="courte"):
        compute_mfdfa(series, q_values=[2])


def test_empty_q_values_raises():
    series = _fbm_synthetic(n=512)
    with pytest.raises(ValueError, match="q_values"):
        compute_mfdfa(series, q_values=[])


# ───────────────────────────────────────────────────────────
# 2. compute_multifractality_width
# ───────────────────────────────────────────────────────────
def test_width_is_float():
    series = _fbm_synthetic(n=1024)
    width = compute_multifractality_width(series)
    assert isinstance(width, float)


def test_width_is_non_negative():
    """Width = max(H(q)) - min(H(q)) >= 0 par construction."""
    series = _fbm_synthetic(n=1024)
    width = compute_multifractality_width(series)
    assert width >= 0.0


def test_width_smaller_on_monofractal_than_multifractal():
    """Cascade multifractale doit avoir width > série mono-fractale."""
    mono = _fbm_synthetic(n=2048, H=0.5)
    multi = _multifractal_cascade(n=2048, p=0.7)
    w_mono = compute_multifractality_width(mono)
    w_multi = compute_multifractality_width(multi)
    assert w_multi > w_mono, (
        f"Width multi ({w_multi:.3f}) doit être > mono ({w_mono:.3f})"
    )
