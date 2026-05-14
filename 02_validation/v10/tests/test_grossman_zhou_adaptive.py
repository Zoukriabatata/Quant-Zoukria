"""
Tests pour la forme adaptative de Grossman-Zhou :
    contracts_adaptive = contracts_baseline * shrinkage_factor

où shrinkage_factor = (W_t - alpha*M_t) / ((1 - alpha) * M_t)
  = 1 quand W_t = M_t (au peak, pas de shrink)
  = 0 quand W_t = alpha*M_t (au floor, shrink complet)
  = clipped à [0, 1] dans tous les cas

Cette forme évite le problème du GZ pur où mu/(gamma*sigma²) explose
et où GZ recommande toujours max_contracts. La forme adaptative ne fait
que multiplier le sizing du v9 par un facteur de garde DD.
"""
import pytest

from quant_v10.modules.sizing_grossman_zhou import (
    gz_shrinkage_factor,
    apply_gz_shrinkage,
)


# ───────────────────────────────────────────────────────────
# 1. gz_shrinkage_factor
# ───────────────────────────────────────────────────────────
def test_shrinkage_one_at_peak():
    """W_t = M_t → shrinkage = 1 (pas de réduction)."""
    s = gz_shrinkage_factor(equity=50_000, hwm=50_000, max_dd_dollars=2_000)
    assert s == pytest.approx(1.0, abs=1e-9)


def test_shrinkage_zero_at_floor():
    """W_t = M_t - DD_max → shrinkage = 0 (pas de risque)."""
    s = gz_shrinkage_factor(equity=48_000, hwm=50_000, max_dd_dollars=2_000)
    assert s == pytest.approx(0.0, abs=1e-9)


def test_shrinkage_zero_below_floor():
    """W_t < floor → shrinkage clamped à 0 (déjà busté)."""
    s = gz_shrinkage_factor(equity=47_500, hwm=50_000, max_dd_dollars=2_000)
    assert s == 0.0


def test_shrinkage_linear_interpolation():
    """À mi-chemin entre floor et peak, shrinkage = 0.5."""
    s = gz_shrinkage_factor(equity=49_000, hwm=50_000, max_dd_dollars=2_000)
    # W_t - alpha*M_t = 49000 - 48000 = 1000
    # (1-alpha)*M_t = 2000
    # ratio = 1000/2000 = 0.5
    assert s == pytest.approx(0.5, abs=1e-9)


def test_shrinkage_capped_at_one():
    """Si W_t > M_t (impossible normalement), shrinkage cappé à 1."""
    s = gz_shrinkage_factor(equity=51_000, hwm=50_000, max_dd_dollars=2_000)
    assert s == 1.0


def test_shrinkage_monotonic_with_hwm():
    """Quand HWM monte (trailing locked higher), le floor monte aussi."""
    # Même equity courant, mais HWM plus haut → on est plus proche du floor
    s_low_hwm = gz_shrinkage_factor(equity=50_000, hwm=50_000, max_dd_dollars=2_000)
    s_high_hwm = gz_shrinkage_factor(equity=50_000, hwm=51_000, max_dd_dollars=2_000)
    assert s_high_hwm < s_low_hwm


# ───────────────────────────────────────────────────────────
# 2. apply_gz_shrinkage
# ───────────────────────────────────────────────────────────
def test_apply_unchanged_at_peak():
    """Au peak, contracts ne changent pas."""
    n = apply_gz_shrinkage(baseline_contracts=12, equity=50_000,
                            hwm=50_000, max_dd_dollars=2_000)
    assert n == 12


def test_apply_zero_at_floor():
    """Au floor, 0 contracts (pas de risque)."""
    n = apply_gz_shrinkage(baseline_contracts=12, equity=48_000,
                            hwm=50_000, max_dd_dollars=2_000)
    assert n == 0


def test_apply_floor_at_mid_buffer():
    """Au mid-buffer, contracts ≈ baseline/2 (floor int)."""
    n = apply_gz_shrinkage(baseline_contracts=12, equity=49_000,
                            hwm=50_000, max_dd_dollars=2_000)
    # 12 * 0.5 = 6
    assert n == 6


def test_apply_never_increases_baseline():
    """La fonction ne doit JAMAIS augmenter le baseline (uniquement réduire ou égal)."""
    for equity in [48_500, 49_000, 49_500, 50_000, 50_500]:
        n = apply_gz_shrinkage(baseline_contracts=10, equity=equity,
                                hwm=50_000, max_dd_dollars=2_000)
        assert n <= 10, f"À equity={equity}, contracts={n} > baseline=10"


def test_apply_zero_baseline_returns_zero():
    """Si baseline=0, output=0 quel que soit le buffer."""
    n = apply_gz_shrinkage(baseline_contracts=0, equity=50_000,
                            hwm=50_000, max_dd_dollars=2_000)
    assert n == 0
