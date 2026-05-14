"""
Tests HAR-RV (Heterogeneous Autoregressive Realized Volatility) — Corsi 2009.

Math :
    RV_{t+1} = c + beta_d * RV_t + beta_w * RV_t^{(w)} + beta_m * RV_t^{(m)}
    avec RV_t^{(w)} = moyenne RV sur 5 derniers jours
         RV_t^{(m)} = moyenne RV sur 22 derniers jours
"""
import numpy as np
import pandas as pd
import pytest

from quant_v10.modules.vol_forecast_har_rv import (
    compute_realized_volatility,
    fit_har_rv,
    forecast_har_rv,
)


# ───────────────────────────────────────────────────────────
# Fixtures
# ───────────────────────────────────────────────────────────
@pytest.fixture
def intraday_returns_gbm():
    """
    Returns intraday simulés : 500 jours ouvrés × 78 bars (5-min session NYSE 6.5h).
    Sigma quotidien réaliste ~1% pour MNQ-like.
    Index = vrais timestamps respectant les sessions (pas un continuum 24/7).
    """
    rng = np.random.default_rng(seed=7)
    n_days = 500
    bars_per_day = 78
    daily_sigma = 0.01
    sigma_per_bar = daily_sigma / np.sqrt(bars_per_day)
    rets = rng.normal(0.0, sigma_per_bar, size=n_days * bars_per_day)
    # Construire l'index : pour chaque jour ouvré, 78 bars 5-min à partir de 09:30
    days = pd.date_range("2022-01-03", periods=n_days, freq="B")
    offsets = pd.timedelta_range("09:30:00", periods=bars_per_day, freq="5min")
    idx = pd.DatetimeIndex(
        (days.values[:, None] + offsets.values[None, :]).ravel()
    )
    return pd.Series(rets, index=idx, name="ret")


@pytest.fixture
def realized_vol_daily():
    """RV quotidienne synthétique, niveau ~ (0.01)^2 = 0.0001 avec persistance."""
    rng = np.random.default_rng(seed=11)
    n = 500
    # AR(1) sur log-RV pour persistance réaliste
    log_rv = np.zeros(n)
    log_rv[0] = np.log(1e-4)
    for t in range(1, n):
        log_rv[t] = 0.85 * log_rv[t - 1] + 0.15 * np.log(1e-4) + rng.normal(0, 0.3)
    rv = np.exp(log_rv)
    idx = pd.date_range("2022-01-03", periods=n, freq="B")
    return pd.Series(rv, index=idx, name="rv")


# ───────────────────────────────────────────────────────────
# 1. compute_realized_volatility
# ───────────────────────────────────────────────────────────
def test_realized_vol_returns_daily_series(intraday_returns_gbm):
    """RV quotidienne agrégée à partir de returns intraday."""
    rv = compute_realized_volatility(intraday_returns_gbm)
    assert isinstance(rv, pd.Series)
    # 500 jours attendus
    assert len(rv) == 500


def test_realized_vol_is_positive(intraday_returns_gbm):
    rv = compute_realized_volatility(intraday_returns_gbm)
    assert (rv > 0).all()


def test_realized_vol_consistency(intraday_returns_gbm):
    """
    Pour GBM avec sigma intraday = 1%/sqrt(78) par bar,
    RV quotidienne attendue ~ (0.01)^2 = 1e-4. Tolérance large car
    distribution chi^2.
    """
    rv = compute_realized_volatility(intraday_returns_gbm)
    mean_rv = rv.mean()
    expected = 0.01 ** 2
    # Tolerance ±50% car chi^2 a forte variance
    assert 0.5 * expected < mean_rv < 1.5 * expected


# ───────────────────────────────────────────────────────────
# 2. fit_har_rv
# ───────────────────────────────────────────────────────────
def test_fit_returns_coefficients(realized_vol_daily):
    """fit_har_rv renvoie dict avec c, beta_d, beta_w, beta_m, r2."""
    result = fit_har_rv(realized_vol_daily)
    assert isinstance(result, dict)
    assert set(result.keys()) >= {"c", "beta_d", "beta_w", "beta_m", "r2"}


def test_fit_coefficients_are_finite(realized_vol_daily):
    result = fit_har_rv(realized_vol_daily)
    for k in ("c", "beta_d", "beta_w", "beta_m"):
        assert np.isfinite(result[k]), f"Coefficient {k} non fini : {result[k]}"


def test_fit_r2_in_valid_range(realized_vol_daily):
    """R² doit être dans [0, 1] et positif sur série persistante."""
    result = fit_har_rv(realized_vol_daily)
    assert 0.0 <= result["r2"] <= 1.0
    # Avec persistance AR(1) phi=0.85, R² devrait être > 30%
    assert result["r2"] > 0.30


def test_fit_beta_d_positive_for_persistent_series(realized_vol_daily):
    """
    Sur une série de vol persistante, le coefficient daily (beta_d) doit être
    positif et significatif (la vol d'hier prédit positivement celle de demain).
    """
    result = fit_har_rv(realized_vol_daily)
    assert result["beta_d"] > 0


def test_fit_too_few_observations_raises():
    """Moins de 22+1 obs = impossible (besoin lag mensuel)."""
    rv = pd.Series([1e-4] * 20)
    with pytest.raises(ValueError, match="observations"):
        fit_har_rv(rv)


# ───────────────────────────────────────────────────────────
# 3. forecast_har_rv (rolling)
# ───────────────────────────────────────────────────────────
def test_forecast_returns_series_aligned(realized_vol_daily):
    """Le forecast doit avoir le même index que la série d'entrée."""
    fc = forecast_har_rv(realized_vol_daily, lookback=252)
    assert isinstance(fc, pd.Series)
    pd.testing.assert_index_equal(fc.index, realized_vol_daily.index)


def test_forecast_warmup_is_nan(realized_vol_daily):
    """Les premières (lookback + 22) obs ne peuvent pas avoir de forecast."""
    fc = forecast_har_rv(realized_vol_daily, lookback=252)
    warmup = 252 + 22
    assert fc.iloc[:warmup].isna().all()


def test_forecast_post_warmup_is_positive(realized_vol_daily):
    """Une vol forecast doit être strictement positive (clip à 0 si négatif)."""
    fc = forecast_har_rv(realized_vol_daily, lookback=252)
    fc_valid = fc.dropna()
    assert (fc_valid > 0).all()


def test_forecast_correlates_with_realized(realized_vol_daily):
    """
    Sur une série persistante, le forecast HAR-RV doit corréler positivement
    avec la RV réalisée du jour suivant (rho > 0.3 minimum).
    """
    fc = forecast_har_rv(realized_vol_daily, lookback=252)
    # forecast[t] prédit RV[t+1] ; on aligne
    target = realized_vol_daily.shift(-1)
    valid = pd.concat([fc, target], axis=1).dropna()
    corr = valid.iloc[:, 0].corr(valid.iloc[:, 1])
    assert corr > 0.30, f"Correlation forecast/realized {corr:.3f} trop basse"
