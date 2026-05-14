"""
Tests Copula Pairs ES/NQ (Gaussian copula MVP).

Math :
    - Empirical CDF marginales : F_X, F_Y
    - Uniformes : u = F_X(x), v = F_Y(y)
    - Gaussian copula : C(u,v) = Phi_2(Phi^-1(u), Phi^-1(v); rho)
    - Conditional CDF : P(U <= u | V = v) = Phi((Phi^-1(u) - rho*Phi^-1(v)) / sqrt(1-rho^2))
    - Signal mispricing : si conditional > 0.95 ou < 0.05, entry trade
"""
import numpy as np
import pandas as pd
import pytest

from quant_v10.modules.copula_pairs_es_nq import (
    empirical_cdf_transform,
    fit_gaussian_copula,
    conditional_probability,
    compute_mispricing_signal,
)


# ───────────────────────────────────────────────────────────
# Fixtures
# ───────────────────────────────────────────────────────────
@pytest.fixture
def correlated_returns():
    """Génère 2 séries de returns corrélés (rho=0.85) — proxy ES/NQ."""
    rng = np.random.default_rng(seed=42)
    n = 2000
    # Génère bivariate normal corrélé
    rho = 0.85
    z1 = rng.normal(0, 1, n)
    z2 = rho * z1 + np.sqrt(1 - rho ** 2) * rng.normal(0, 1, n)
    return pd.Series(z1, name="ES"), pd.Series(z2, name="NQ"), rho


# ───────────────────────────────────────────────────────────
# 1. empirical_cdf_transform
# ───────────────────────────────────────────────────────────
def test_cdf_transform_returns_uniforms():
    """Sortie de empirical_cdf doit être dans (0, 1)."""
    rng = np.random.default_rng(0)
    x = pd.Series(rng.normal(0, 1, 500))
    u = empirical_cdf_transform(x)
    assert isinstance(u, pd.Series)
    assert (u > 0).all()
    assert (u < 1).all()


def test_cdf_transform_preserves_order():
    """Rang de x = rang de u (monotonicité)."""
    x = pd.Series([3.0, 1.0, 2.0, 5.0, 4.0])
    u = empirical_cdf_transform(x)
    assert list(x.rank()) == list(u.rank())


def test_cdf_transform_uniform_distribution():
    """La transformation doit donner ~uniformes : mean ≈ 0.5, std ≈ 1/sqrt(12)."""
    rng = np.random.default_rng(7)
    x = pd.Series(rng.normal(0, 1, 5000))
    u = empirical_cdf_transform(x)
    assert 0.45 < u.mean() < 0.55
    assert 0.25 < u.std() < 0.32  # std uniform = 1/sqrt(12) ≈ 0.289


# ───────────────────────────────────────────────────────────
# 2. fit_gaussian_copula
# ───────────────────────────────────────────────────────────
def test_fit_returns_correlation_in_range(correlated_returns):
    x, y, _ = correlated_returns
    rho = fit_gaussian_copula(x, y)
    assert -1.0 <= rho <= 1.0


def test_fit_recovers_true_correlation(correlated_returns):
    """Si vraie correlation = 0.85, calibration doit donner valeur proche."""
    x, y, true_rho = correlated_returns
    rho_hat = fit_gaussian_copula(x, y)
    assert abs(rho_hat - true_rho) < 0.10


def test_fit_independent_series_gives_low_correlation():
    """Séries indépendantes → rho ≈ 0."""
    rng = np.random.default_rng(11)
    x = pd.Series(rng.normal(0, 1, 1000))
    y = pd.Series(rng.normal(0, 1, 1000))
    rho = fit_gaussian_copula(x, y)
    assert abs(rho) < 0.15


# ───────────────────────────────────────────────────────────
# 3. conditional_probability
# ───────────────────────────────────────────────────────────
def test_conditional_returns_value_in_unit_interval():
    p = conditional_probability(u=0.5, v=0.5, rho=0.7)
    assert 0.0 <= p <= 1.0


def test_conditional_symmetric_at_median():
    """À u=0.5, v=0.5, rho quelconque : conditionnelle = 0.5."""
    p = conditional_probability(u=0.5, v=0.5, rho=0.85)
    assert abs(p - 0.5) < 1e-9


def test_conditional_independence_returns_u():
    """Avec rho=0, P(U<=u | V=v) = u (indépendance)."""
    p = conditional_probability(u=0.3, v=0.7, rho=0.0)
    assert abs(p - 0.3) < 1e-9


# ───────────────────────────────────────────────────────────
# 4. compute_mispricing_signal
# ───────────────────────────────────────────────────────────
def test_signal_returns_dataframe(correlated_returns):
    """Output : DataFrame avec colonnes conditional_prob, signal."""
    x, y, _ = correlated_returns
    sig = compute_mispricing_signal(x, y, lookback=500)
    assert isinstance(sig, pd.DataFrame)
    assert {"conditional_prob", "signal"}.issubset(sig.columns)


def test_signal_values_in_set(correlated_returns):
    """Signal must be in {-1, 0, +1}."""
    x, y, _ = correlated_returns
    sig = compute_mispricing_signal(x, y, lookback=500, p_high=0.95, p_low=0.05)
    valid = sig["signal"].dropna()
    assert set(valid.unique()).issubset({-1, 0, 1})


def test_signal_fires_on_extreme_deviation():
    """Construit un cas où X >> Y nominal : signal doit fire négatif (X surévalué)."""
    rng = np.random.default_rng(99)
    n = 600
    z = rng.normal(0, 1, n)
    # Y suit Z, X suit Z mais avec spike à la fin
    x = pd.Series(z.copy())
    y = pd.Series(z.copy())
    x.iloc[-1] = 5.0  # Spike X (5 sigma)
    sig = compute_mispricing_signal(x, y, lookback=500, p_high=0.95, p_low=0.05)
    # Le dernier signal doit être non-zero (mispricing détecté)
    last_signal = sig["signal"].iloc[-1]
    assert last_signal != 0
