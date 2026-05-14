"""Tests de monte_carlo : permutation sign-flip (Sharpe) + order-shuffle (Max DD)."""
import numpy as np

from gauntlet.monte_carlo import (
    permutation_test_sharpe,
    dd_distribution_shuffle,
    _sharpe,
    _max_drawdown,
)


def test_max_drawdown_hand_calc():
    # pnl chronologique [+100, -300, +100, -300, +100]
    # equity = [100, -200, -100, -400, -300] ; peak = [100,100,100,100,100]
    # dd = [0, -300, -200, -500, -400] ; max dd = -500
    pnl = np.array([100.0, -300.0, 100.0, -300.0, 100.0])
    assert _max_drawdown(pnl) == -500.0


def test_max_drawdown_all_positive_is_zero():
    assert _max_drawdown(np.array([10.0, 20.0, 5.0])) == 0.0


def test_sharpe_matches_repo_convention():
    # convention repo : moyenne / std(ddof=1) * sqrt(252) — cf. compute_trade_metrics
    pnl = np.array([100.0, -50.0, 75.0, -25.0, 60.0])
    expected = np.mean(pnl) / np.std(pnl, ddof=1) * np.sqrt(252)
    assert abs(_sharpe(pnl) - expected) < 1e-9


def test_permutation_strong_edge_low_pvalue():
    # 200 trades, edge franc (moyenne très > 0) -> p-value proche de 0
    rng = np.random.default_rng(7)
    pnl = rng.normal(loc=120.0, scale=150.0, size=200)
    res = permutation_test_sharpe(pnl, n_iter=2000, seed=0)
    assert res["observed_sharpe"] > 0
    assert res["p_value"] < 0.01


def test_permutation_pure_noise_pvalue_near_half():
    # PnL recentré sur 0 -> Sharpe observé = 0, pile au centre de la distribution sign-flip
    rng = np.random.default_rng(11)
    pnl = rng.normal(loc=0.0, scale=150.0, size=300)
    pnl = pnl - pnl.mean()
    res = permutation_test_sharpe(pnl, n_iter=4000, seed=0)
    assert abs(res["observed_sharpe"]) < 1e-9
    assert 0.40 < res["p_value"] < 0.60


def test_permutation_reproducible():
    rng = np.random.default_rng(3)
    pnl = rng.normal(loc=30.0, scale=100.0, size=100)
    r1 = permutation_test_sharpe(pnl, n_iter=500, seed=42)
    r2 = permutation_test_sharpe(pnl, n_iter=500, seed=42)
    assert r1["p_value"] == r2["p_value"]


def test_permutation_zero_variance_pnl():
    # PnL dégénéré (tous identiques) -> Sharpe nul, aucun edge -> p_value = 1.0
    pnl = np.array([100.0, 100.0, 100.0, 100.0])
    res = permutation_test_sharpe(pnl, n_iter=500, seed=0)
    assert res["observed_sharpe"] == 0.0
    assert res["p_value"] == 1.0


def test_dd_distribution_observed_is_chronological():
    # observed_max_dd doit être le Max DD dans l'ordre RÉEL fourni
    pnl = np.array([100.0, -300.0, 100.0, -300.0, 100.0])
    res = dd_distribution_shuffle(pnl, n_iter=500, seed=0)
    assert res["observed_max_dd"] == -500.0


def test_dd_distribution_percentiles_ordered():
    rng = np.random.default_rng(5)
    pnl = rng.normal(loc=-5.0, scale=200.0, size=150)
    res = dd_distribution_shuffle(pnl, n_iter=3000, seed=0)
    # tous les DD <= 0 ; p50 (le moins profond) >= p95 >= p99 >= worst (le plus profond)
    assert res["dd_p50"] <= 0.0
    assert res["dd_p50"] >= res["dd_p95"] >= res["dd_p99"] >= res["dd_worst"]


def test_dd_distribution_reproducible():
    rng = np.random.default_rng(9)
    pnl = rng.normal(loc=10.0, scale=120.0, size=120)
    r1 = dd_distribution_shuffle(pnl, n_iter=500, seed=1)
    r2 = dd_distribution_shuffle(pnl, n_iter=500, seed=1)
    assert r1 == r2
