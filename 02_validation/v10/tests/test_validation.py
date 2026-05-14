"""
Tests pour le module de validation (CPCV + DSR + PBO).
"""
import numpy as np
import pandas as pd
import pytest

from quant_v10.validation.cpcv import (
    generate_cpcv_paths,
    sharpe_distribution_cpcv,
)
from quant_v10.validation.deflated_sharpe import (
    probabilistic_sharpe_ratio,
    deflated_sharpe_ratio,
    probability_backtest_overfitting,
)


# ───────────────────────────────────────────────────────────
# Fixtures
# ───────────────────────────────────────────────────────────
@pytest.fixture
def good_trades():
    """Série de trades avec edge réel (mean positive)."""
    rng = np.random.default_rng(42)
    pnl = rng.normal(loc=50.0, scale=200.0, size=1000)
    dates = pd.date_range("2022-01-01", periods=1000, freq="D")
    return pd.DataFrame({"date": dates, "pnl": pnl})


@pytest.fixture
def noise_trades():
    """Pas d'edge (mean = 0)."""
    rng = np.random.default_rng(1)
    pnl = rng.normal(loc=0.0, scale=200.0, size=1000)
    dates = pd.date_range("2022-01-01", periods=1000, freq="D")
    return pd.DataFrame({"date": dates, "pnl": pnl})


# ───────────────────────────────────────────────────────────
# 1. CPCV
# ───────────────────────────────────────────────────────────
def test_generate_paths_count():
    """CPCV(N=8, K=2) doit générer C(8,2)=28 paths."""
    paths = generate_cpcv_paths(n_groups=8, k_test=2)
    assert len(paths) == 28


def test_each_path_test_size_is_k():
    paths = generate_cpcv_paths(n_groups=6, k_test=2)
    for test_indices in paths:
        assert len(test_indices) == 2


def test_paths_are_unique():
    paths = generate_cpcv_paths(n_groups=6, k_test=2)
    seen = set()
    for path in paths:
        seen.add(tuple(sorted(path)))
    assert len(seen) == len(paths)


def test_sharpe_distribution_cpcv(good_trades):
    """Pour des trades avec edge, distribution Sharpe doit avoir mean > 0."""
    sharpes = sharpe_distribution_cpcv(good_trades, n_groups=10, k_test=2)
    assert len(sharpes) > 0
    assert np.mean(sharpes) > 0.0


# ───────────────────────────────────────────────────────────
# 2. Deflated Sharpe Ratio (PSR + DSR)
# ───────────────────────────────────────────────────────────
def test_psr_in_unit_interval(good_trades):
    """PSR(SR) doit être dans [0, 1] (probabilité)."""
    psr = probabilistic_sharpe_ratio(good_trades["pnl"].values, sr_benchmark=0.0)
    assert 0.0 <= psr <= 1.0


def test_psr_higher_for_better_edge(good_trades, noise_trades):
    """PSR sur edge > PSR sur noise."""
    psr_edge = probabilistic_sharpe_ratio(good_trades["pnl"].values, sr_benchmark=0.0)
    psr_noise = probabilistic_sharpe_ratio(noise_trades["pnl"].values, sr_benchmark=0.0)
    assert psr_edge > psr_noise


def test_dsr_corrects_for_multiple_testing(good_trades):
    """DSR avec n_trials élevé < PSR (correction Bonferroni-like)."""
    pnl = good_trades["pnl"].values
    psr = probabilistic_sharpe_ratio(pnl, sr_benchmark=0.0)
    dsr = deflated_sharpe_ratio(pnl, n_trials=100, sr_variance=0.5 ** 2)
    assert dsr <= psr


def test_dsr_in_unit_interval(good_trades):
    dsr = deflated_sharpe_ratio(
        good_trades["pnl"].values, n_trials=10, sr_variance=0.3 ** 2,
    )
    assert 0.0 <= dsr <= 1.0


# ───────────────────────────────────────────────────────────
# 3. PBO
# ───────────────────────────────────────────────────────────
def test_pbo_in_unit_interval():
    """PBO doit être dans [0, 1]."""
    rng = np.random.default_rng(0)
    n_configs = 10
    n_time = 200
    # Matrice (time, config) de PnLs aléatoires
    matrix = rng.normal(0, 1, size=(n_time, n_configs))
    pbo = probability_backtest_overfitting(matrix, n_splits=8)
    assert 0.0 <= pbo <= 1.0


def test_pbo_high_for_pure_noise():
    """Sur PnLs pure-noise, PBO doit être proche de 0.5 (random rank)."""
    rng = np.random.default_rng(2024)
    matrix = rng.normal(0, 1, size=(500, 20))
    pbo = probability_backtest_overfitting(matrix, n_splits=10)
    # Pour pure noise, PBO devrait converger autour de 0.5 (ranking aléatoire)
    assert 0.3 < pbo < 0.7
