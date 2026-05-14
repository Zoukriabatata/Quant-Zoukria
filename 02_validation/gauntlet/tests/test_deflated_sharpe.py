"""Tests de deflated_sharpe : PSR + DSR + PBO.

Consolidé depuis 02_validation/v10/validation/tests (où il était mort — l'import
quant_v10 ne résolvait pas). Imports corrigés vers gauntlet.deflated_sharpe.
"""
import numpy as np
import pandas as pd
import pytest

from gauntlet.deflated_sharpe import (
    probabilistic_sharpe_ratio,
    deflated_sharpe_ratio,
    probability_backtest_overfitting,
)


@pytest.fixture
def good_trades():
    """Série de trades avec edge réel (moyenne positive)."""
    rng = np.random.default_rng(42)
    pnl = rng.normal(loc=50.0, scale=200.0, size=1000)
    dates = pd.date_range("2022-01-01", periods=1000, freq="D")
    return pd.DataFrame({"date": dates, "pnl": pnl})


@pytest.fixture
def noise_trades():
    """Pas d'edge (moyenne = 0)."""
    rng = np.random.default_rng(1)
    pnl = rng.normal(loc=0.0, scale=200.0, size=1000)
    dates = pd.date_range("2022-01-01", periods=1000, freq="D")
    return pd.DataFrame({"date": dates, "pnl": pnl})


def test_psr_in_unit_interval(good_trades):
    """PSR(SR) doit être dans [0, 1] (c'est une probabilité)."""
    psr = probabilistic_sharpe_ratio(good_trades["pnl"].values, sr_benchmark=0.0)
    assert 0.0 <= psr <= 1.0


def test_psr_higher_for_better_edge(good_trades, noise_trades):
    """PSR sur edge > PSR sur noise."""
    psr_edge = probabilistic_sharpe_ratio(good_trades["pnl"].values, sr_benchmark=0.0)
    psr_noise = probabilistic_sharpe_ratio(noise_trades["pnl"].values, sr_benchmark=0.0)
    assert psr_edge > psr_noise


def test_dsr_corrects_for_multiple_testing(good_trades):
    """DSR avec n_trials élevé <= PSR (correction type Bonferroni)."""
    pnl = good_trades["pnl"].values
    psr = probabilistic_sharpe_ratio(pnl, sr_benchmark=0.0)
    dsr = deflated_sharpe_ratio(pnl, n_trials=100, sr_variance=0.5 ** 2)
    assert dsr <= psr


def test_dsr_in_unit_interval(good_trades):
    dsr = deflated_sharpe_ratio(
        good_trades["pnl"].values, n_trials=10, sr_variance=0.3 ** 2,
    )
    assert 0.0 <= dsr <= 1.0


def test_pbo_in_unit_interval():
    """PBO doit être dans [0, 1]."""
    rng = np.random.default_rng(0)
    matrix = rng.normal(0, 1, size=(200, 10))
    pbo = probability_backtest_overfitting(matrix, n_splits=8)
    assert 0.0 <= pbo <= 1.0


def test_pbo_high_for_pure_noise():
    """Sur des PnL pur bruit, le PBO doit converger vers ~0.5 (ranking aléatoire)."""
    rng = np.random.default_rng(2024)
    matrix = rng.normal(0, 1, size=(500, 20))
    pbo = probability_backtest_overfitting(matrix, n_splits=10)
    assert 0.3 < pbo < 0.7
