"""Tests de cpcv : génération de paths CPCV + distribution de Sharpe OOS.

Consolidé depuis 02_validation/v10/validation/tests (où il était mort — l'import
quant_v10 ne résolvait pas). Imports corrigés vers gauntlet.cpcv.
"""
import numpy as np
import pandas as pd
import pytest

from gauntlet.cpcv import generate_cpcv_paths, sharpe_distribution_cpcv


@pytest.fixture
def good_trades():
    """Série de trades avec edge réel (moyenne positive)."""
    rng = np.random.default_rng(42)
    pnl = rng.normal(loc=50.0, scale=200.0, size=1000)
    dates = pd.date_range("2022-01-01", periods=1000, freq="D")
    return pd.DataFrame({"date": dates, "pnl": pnl})


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
    seen = {tuple(sorted(path)) for path in paths}
    assert len(seen) == len(paths)


def test_sharpe_distribution_cpcv(good_trades):
    """Pour des trades avec edge, la distribution Sharpe doit avoir une moyenne > 0."""
    sharpes = sharpe_distribution_cpcv(good_trades, n_groups=10, k_test=2)
    assert len(sharpes) > 0
    assert np.mean(sharpes) > 0.0
