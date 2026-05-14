"""
Tests Grossman-Zhou DD-constrained sizing (Grossman & Zhou 1993, Math Finance).

Mathématique :
    pi*(t) = (mu - r) / (gamma * sigma^2) * (W_t - alpha * M_t) / W_t

où W_t = equity courant, M_t = high-water mark, alpha = floor relatif au HWM.
La fraction (W_t - alpha*M_t) / W_t shrink la taille à zéro à l'approche du floor.

Contrainte Apex trailing DD $2k : floor = M_t - 2000 (en $) soit alpha = (M_t-2000)/M_t.
"""
import numpy as np
import pytest

from quant_v10.modules.sizing_grossman_zhou import (
    apex_floor_alpha,
    grossman_zhou_fraction,
    grossman_zhou_contracts,
)


# ───────────────────────────────────────────────────────────
# 1. apex_floor_alpha : conversion DD absolu -> alpha relatif
# ───────────────────────────────────────────────────────────
def test_floor_alpha_at_initial_capital():
    """Au début, W_t = M_t = 50_000 et DD floor = $2k => alpha = 48000/50000 = 0.96."""
    alpha = apex_floor_alpha(hwm=50_000, max_dd_dollars=2_000)
    assert abs(alpha - 0.96) < 1e-9


def test_floor_alpha_grows_with_hwm():
    """Quand HWM monte (trailing locked), le floor monte aussi mais alpha augmente."""
    alpha_low = apex_floor_alpha(hwm=50_000, max_dd_dollars=2_000)
    alpha_high = apex_floor_alpha(hwm=53_000, max_dd_dollars=2_000)
    assert alpha_high > alpha_low
    assert abs(alpha_high - 51_000 / 53_000) < 1e-9


# ───────────────────────────────────────────────────────────
# 2. grossman_zhou_fraction : la formule core
# ───────────────────────────────────────────────────────────
def test_fraction_zero_at_floor():
    """À l'approche du floor (W_t = alpha * M_t), pi* doit être zéro."""
    alpha = 0.96
    M_t = 50_000
    W_t = alpha * M_t   # exactement au floor
    pi = grossman_zhou_fraction(
        equity=W_t, hwm=M_t, alpha=alpha,
        mu_excess=0.001, sigma2=0.01 ** 2, gamma=2.0,
    )
    assert pi == pytest.approx(0.0, abs=1e-9)


def test_fraction_negative_below_floor_clipped_to_zero():
    """Si W_t < alpha * M_t (drawdown dépassé), la formule donne négatif → clip à 0."""
    pi = grossman_zhou_fraction(
        equity=47_000, hwm=50_000, alpha=0.96,
        mu_excess=0.001, sigma2=0.01 ** 2, gamma=2.0,
    )
    assert pi == pytest.approx(0.0, abs=1e-9)


def test_fraction_maximum_at_hwm():
    """Quand W_t = M_t (au peak), la fraction est maximale = (1-alpha) * (mu-r)/(gamma*sigma^2)."""
    M_t = 50_000
    alpha = 0.96
    mu = 0.001
    sigma2 = 0.01 ** 2
    gamma = 2.0
    pi = grossman_zhou_fraction(
        equity=M_t, hwm=M_t, alpha=alpha,
        mu_excess=mu, sigma2=sigma2, gamma=gamma,
    )
    expected = mu / (gamma * sigma2) * (1.0 - alpha)
    assert pi == pytest.approx(expected, rel=1e-9)


def test_fraction_decreases_as_equity_drops_toward_floor():
    """La fraction doit être strictement décroissante quand W_t baisse vers le floor."""
    M_t = 50_000
    alpha = 0.96
    args = dict(hwm=M_t, alpha=alpha, mu_excess=0.001, sigma2=1e-4, gamma=2.0)
    pi_50k = grossman_zhou_fraction(equity=50_000, **args)
    pi_49k = grossman_zhou_fraction(equity=49_000, **args)
    pi_48k = grossman_zhou_fraction(equity=48_500, **args)
    assert pi_50k > pi_49k > pi_48k > 0


def test_fraction_scales_inversely_with_variance():
    """Pi doit scaler 1/sigma^2 (sizing baissé en haute vol)."""
    args = dict(equity=50_000, hwm=50_000, alpha=0.96, mu_excess=0.001, gamma=2.0)
    pi_low_vol = grossman_zhou_fraction(sigma2=1e-4, **args)
    pi_high_vol = grossman_zhou_fraction(sigma2=4e-4, **args)
    # 4x variance → 1/4 fraction
    assert pi_low_vol == pytest.approx(4.0 * pi_high_vol, rel=1e-9)


def test_fraction_raises_on_negative_sigma2():
    with pytest.raises(ValueError, match="sigma2"):
        grossman_zhou_fraction(
            equity=50_000, hwm=50_000, alpha=0.96,
            mu_excess=0.001, sigma2=-1.0, gamma=2.0,
        )


def test_fraction_raises_on_zero_gamma():
    with pytest.raises(ValueError, match="gamma"):
        grossman_zhou_fraction(
            equity=50_000, hwm=50_000, alpha=0.96,
            mu_excess=0.001, sigma2=1e-4, gamma=0.0,
        )


# ───────────────────────────────────────────────────────────
# 3. grossman_zhou_contracts : conversion fraction -> contracts MNQ
# ───────────────────────────────────────────────────────────
def test_contracts_zero_at_floor():
    """Au floor, 0 contracts."""
    n = grossman_zhou_contracts(
        equity=48_000, hwm=50_000, max_dd_dollars=2_000,
        mu_excess=0.001, sigma2=1e-4, gamma=2.0,
        point_value=2.0, sl_points=10.0, max_contracts=12,
    )
    assert n == 0


def test_contracts_is_integer():
    n = grossman_zhou_contracts(
        equity=50_000, hwm=50_000, max_dd_dollars=2_000,
        mu_excess=0.001, sigma2=1e-4, gamma=2.0,
        point_value=2.0, sl_points=10.0, max_contracts=12,
    )
    assert isinstance(n, int)


def test_contracts_respects_max_cap():
    """Avec mu_excess énorme et sigma2 minuscule, la fraction explose → doit clipper à max_contracts."""
    n = grossman_zhou_contracts(
        equity=50_000, hwm=50_000, max_dd_dollars=2_000,
        mu_excess=0.5, sigma2=1e-8, gamma=1.0,
        point_value=2.0, sl_points=10.0, max_contracts=12,
    )
    assert n == 12


def test_contracts_increase_with_dd_buffer():
    """Plus on est loin du floor (buffer grand), plus on size."""
    base_args = dict(
        hwm=50_000, max_dd_dollars=2_000,
        mu_excess=0.001, sigma2=1e-4, gamma=2.0,
        point_value=2.0, sl_points=10.0, max_contracts=60,
    )
    n_far = grossman_zhou_contracts(equity=50_000, **base_args)
    n_near = grossman_zhou_contracts(equity=48_500, **base_args)
    assert n_far >= n_near
