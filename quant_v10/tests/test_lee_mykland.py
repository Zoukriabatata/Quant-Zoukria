"""
Tests Lee-Mykland jump detection (Lee & Mykland 2008, RFS).

Math :
- r_i = log(P_i) - log(P_{i-1})
- sigma_hat_i^2 = (pi/2) * (1/(K-2)) * sum_{j=i-K+2}^{i-1} |r_{j-1}| * |r_j|
- L_i = r_i / sigma_hat_i
- Rejet H_0 si |L_i| > seuil asymptotique Gumbel
"""
import numpy as np
import pandas as pd
import pytest

from quant_v10.modules.jump_detection_lee_mykland import detect_jumps


# ───────────────────────────────────────────────────────────
# Fixtures déterministes
# ───────────────────────────────────────────────────────────
@pytest.fixture
def pure_brownian():
    """Pure GBM, sigma=1%, n=2000 bars, AUCUN jump inséré."""
    rng = np.random.default_rng(seed=42)
    n = 2000
    sigma = 0.01
    rets = rng.normal(loc=0.0, scale=sigma, size=n)
    log_prices = np.cumsum(rets) + np.log(100.0)  # start at price 100
    prices = np.exp(log_prices)
    idx = pd.date_range("2024-01-01", periods=n, freq="5min")
    return pd.Series(prices, index=idx, name="price")


@pytest.fixture
def brownian_with_known_jump():
    """GBM + 1 gros jump de +10*sigma au bar 1000."""
    rng = np.random.default_rng(seed=123)
    n = 2000
    sigma = 0.01
    rets = rng.normal(loc=0.0, scale=sigma, size=n)
    rets[1000] += 10.0 * sigma  # jump connu
    log_prices = np.cumsum(rets) + np.log(100.0)
    prices = np.exp(log_prices)
    idx = pd.date_range("2024-01-01", periods=n, freq="5min")
    return pd.Series(prices, index=idx, name="price"), 1000  # retourne aussi l'index du jump


# ───────────────────────────────────────────────────────────
# 1. API & schema
# ───────────────────────────────────────────────────────────
def test_returns_dataframe_with_required_columns(pure_brownian):
    """Output schema : DataFrame avec colonnes ['L_stat', 'sigma_hat', 'jump_flag']."""
    result = detect_jumps(pure_brownian, window=156, alpha=0.01)
    assert isinstance(result, pd.DataFrame)
    assert set(result.columns) >= {"L_stat", "sigma_hat", "jump_flag"}
    assert len(result) == len(pure_brownian)


def test_jump_flag_is_boolean(pure_brownian):
    result = detect_jumps(pure_brownian, window=156, alpha=0.01)
    assert result["jump_flag"].dtype == bool


def test_index_preserved(pure_brownian):
    """L'index temporel doit être préservé pour le merge avec le backtest."""
    result = detect_jumps(pure_brownian, window=156, alpha=0.01)
    pd.testing.assert_index_equal(result.index, pure_brownian.index)


# ───────────────────────────────────────────────────────────
# 2. Comportement statistique
# ───────────────────────────────────────────────────────────
def test_pure_brownian_has_few_false_positives(pure_brownian):
    """
    Sur un GBM pur sans jump, le taux de faux positifs à alpha=1%
    doit rester < 5% (tolérance pour seuil pointwise vs global).
    """
    result = detect_jumps(pure_brownian, window=156, alpha=0.01)
    # On exclut la zone de warm-up où sigma_hat n'est pas défini
    valid = result.dropna(subset=["sigma_hat"])
    fp_rate = valid["jump_flag"].mean()
    assert fp_rate < 0.05, f"Taux faux positif {fp_rate:.2%} > 5% sur GBM pur"


def test_detects_known_inserted_jump(brownian_with_known_jump):
    """Un jump inséré de +10*sigma doit être détecté."""
    prices, jump_idx = brownian_with_known_jump
    result = detect_jumps(prices, window=156, alpha=0.01)
    assert result["jump_flag"].iloc[jump_idx], (
        f"Jump connu au bar {jump_idx} non détecté. "
        f"L_stat = {result['L_stat'].iloc[jump_idx]:.2f}"
    )


def test_L_stat_at_jump_exceeds_4(brownian_with_known_jump):
    """Pour un jump de 10*sigma, |L_stat| doit être très grand (>> 4)."""
    prices, jump_idx = brownian_with_known_jump
    result = detect_jumps(prices, window=156, alpha=0.01)
    assert abs(result["L_stat"].iloc[jump_idx]) > 4.0


# ───────────────────────────────────────────────────────────
# 3. Edge cases & validation
# ───────────────────────────────────────────────────────────
def test_warmup_period_returns_nan_or_false():
    """Les premiers `window` bars ne peuvent pas avoir de sigma_hat estimé."""
    rng = np.random.default_rng(0)
    prices = pd.Series(100 + np.cumsum(rng.normal(0, 0.01, 500)))
    result = detect_jumps(prices, window=156, alpha=0.01)
    # Pendant warm-up : jump_flag = False (ou NaN -> False)
    assert not result["jump_flag"].iloc[:156].any()


def test_window_too_small_raises():
    """Window < 3 impossible (besoin de K-2 produits non-vides)."""
    prices = pd.Series([100, 101, 102, 103, 104])
    with pytest.raises(ValueError, match="window"):
        detect_jumps(prices, window=2, alpha=0.01)


def test_alpha_out_of_range_raises():
    prices = pd.Series([100] * 200)
    with pytest.raises(ValueError, match="alpha"):
        detect_jumps(prices, window=50, alpha=1.5)
    with pytest.raises(ValueError, match="alpha"):
        detect_jumps(prices, window=50, alpha=-0.1)


def test_constant_price_no_jumps():
    """Prix strictement constant → returns nuls → pas de jumps détectables."""
    prices = pd.Series([100.0] * 500)
    result = detect_jumps(prices, window=156, alpha=0.01)
    # Aucun jump ne peut être flag sur prix plat (numérateur r_i = 0)
    assert not result["jump_flag"].any()
