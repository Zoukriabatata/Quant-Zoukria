"""
Tests Cartea-Figueroa Mean-Reverting Jump-Diffusion (Cartea & Figueroa 2005).

Modèle :
    dS_t = theta*(mu - S_t)*dt + sigma*dW_t + J_t*dN_t
avec J_t ~ N(eta, delta^2), N_t ~ Poisson(lambda).

Usage : calibration sur résidus Hurst_MR + détection des jumps dans le résidu.
"""
import numpy as np
import pandas as pd
import pytest

from quant_v10.modules.model_cartea_figueroa_mrjd import (
    calibrate_mrjd_params,
    detect_jumps_in_residuals,
)


# ───────────────────────────────────────────────────────────
# Fixtures
# ───────────────────────────────────────────────────────────
def _simulate_ou(n=1000, theta=0.1, mu=0.0, sigma=1.0, x0=0.0, seed=42):
    """Simule un OU discret : X_{t+1} = X_t*exp(-theta*dt) + mu*(1-exp(-theta*dt)) + noise."""
    rng = np.random.default_rng(seed)
    dt = 1.0
    beta = np.exp(-theta * dt)
    sd_eps = sigma * np.sqrt((1 - beta ** 2) / (2 * theta)) if theta > 0 else sigma
    x = np.zeros(n)
    x[0] = x0
    for t in range(1, n):
        x[t] = beta * x[t - 1] + mu * (1 - beta) + rng.normal(0, sd_eps)
    return pd.Series(x)


@pytest.fixture
def pure_ou_residuals():
    """Résidus suivant un OU pur, theta=0.1, sigma=1.0."""
    return _simulate_ou(n=1000, theta=0.1, mu=0.0, sigma=1.0, seed=42)


@pytest.fixture
def ou_with_known_jumps():
    """OU + 5 jumps connus à des positions précises."""
    x = _simulate_ou(n=1000, theta=0.1, mu=0.0, sigma=1.0, seed=99).copy()
    jump_positions = [200, 400, 600, 800, 950]
    jump_size = 10.0  # 10*sigma
    for pos in jump_positions:
        x.iloc[pos:] += jump_size  # jump permanent
    return x, jump_positions


# ───────────────────────────────────────────────────────────
# 1. calibrate_mrjd_params
# ───────────────────────────────────────────────────────────
def test_calibrate_returns_required_keys(pure_ou_residuals):
    """API : dict avec theta, mu, sigma, lambda, eta, delta."""
    params = calibrate_mrjd_params(pure_ou_residuals)
    assert set(params.keys()) >= {"theta", "mu", "sigma", "lambda", "eta", "delta"}


def test_calibrate_finite_outputs(pure_ou_residuals):
    params = calibrate_mrjd_params(pure_ou_residuals)
    for k in ("theta", "mu", "sigma", "lambda"):
        assert np.isfinite(params[k]), f"Param {k} non fini : {params[k]}"


def test_theta_positive_on_mean_reverting(pure_ou_residuals):
    """OU avec theta=0.1 → estimation doit donner theta > 0."""
    params = calibrate_mrjd_params(pure_ou_residuals)
    assert params["theta"] > 0, f"theta estimé = {params['theta']}, devrait être > 0"


def test_calibration_recovers_theta_approximately(pure_ou_residuals):
    """Theta vrai = 0.1, calibration doit donner valeur dans (0.03, 0.30)."""
    params = calibrate_mrjd_params(pure_ou_residuals)
    assert 0.03 < params["theta"] < 0.30, f"theta {params['theta']:.3f} hors fourchette"


def test_lambda_zero_on_pure_diffusion(pure_ou_residuals):
    """Sur OU pur sans jumps, lambda (jump rate) doit être ≈ 0 (< 5%)."""
    params = calibrate_mrjd_params(pure_ou_residuals)
    assert params["lambda"] < 0.05, f"lambda {params['lambda']:.3f} trop élevé sur OU pur"


def test_lambda_positive_with_jumps(ou_with_known_jumps):
    """Avec 5 jumps sur 1000 bars, lambda doit être > 0."""
    residuals, _ = ou_with_known_jumps
    params = calibrate_mrjd_params(residuals)
    assert params["lambda"] > 0.0


# ───────────────────────────────────────────────────────────
# 2. detect_jumps_in_residuals
# ───────────────────────────────────────────────────────────
def test_detect_returns_bool_array_same_length(pure_ou_residuals):
    flags = detect_jumps_in_residuals(pure_ou_residuals)
    assert isinstance(flags, pd.Series)
    assert flags.dtype == bool
    assert len(flags) == len(pure_ou_residuals)


def test_detect_few_false_positives_on_pure_ou(pure_ou_residuals):
    """Sur OU pur, taux de faux positifs doit rester < 5%."""
    flags = detect_jumps_in_residuals(pure_ou_residuals, alpha=0.01)
    fp_rate = flags.mean()
    assert fp_rate < 0.05, f"FP rate {fp_rate:.2%} > 5% sur OU pur"


def test_detect_finds_known_jumps(ou_with_known_jumps):
    """Sur OU + jumps, on doit détecter au moins 50% des jumps connus."""
    residuals, positions = ou_with_known_jumps
    flags = detect_jumps_in_residuals(residuals, alpha=0.01)
    detected = sum(1 for p in positions if flags.iloc[p])
    assert detected >= len(positions) // 2, (
        f"Seulement {detected}/{len(positions)} jumps détectés"
    )


def test_detect_invalid_alpha_raises():
    residuals = pd.Series(np.zeros(100))
    with pytest.raises(ValueError, match="alpha"):
        detect_jumps_in_residuals(residuals, alpha=1.5)
