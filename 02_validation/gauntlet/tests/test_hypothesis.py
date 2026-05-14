"""Tests de l'interface Hypothesis."""
import pytest

from gauntlet.hypothesis import Hypothesis


def _dummy_build_variant(params):
    """build_variant minimal : retourne (signal_fn, exit_logic, backtest_kwargs)."""
    def signal_fn(df):
        return df
    def exit_logic(*args, **kwargs):
        return False, 0.0, ""
    return signal_fn, exit_logic, {"timeout_bars": params["timeout_bars"]}


def test_hypothesis_construction_et_n_trials():
    h = Hypothesis(
        name="dummy",
        description="hypothèse de test",
        instrument="MNQ",
        timeframe="5min",
        build_variant=_dummy_build_variant,
        param_grid=[{"timeout_bars": 12}, {"timeout_bars": 24}],
    )
    assert h.name == "dummy"
    assert h.instrument == "MNQ"
    assert h.n_trials == 2


def test_hypothesis_param_grid_vide_leve_erreur():
    with pytest.raises(ValueError):
        Hypothesis(
            name="vide", description="", instrument="MNQ", timeframe="5min",
            build_variant=_dummy_build_variant, param_grid=[],
        )


def test_hypothesis_build_variant_non_callable_leve_erreur():
    with pytest.raises(TypeError):
        Hypothesis(
            name="bad", description="", instrument="MNQ", timeframe="5min",
            build_variant="pas une fonction", param_grid=[{"timeout_bars": 12}],
        )


def test_hypothesis_prepare_features_default_none():
    h = Hypothesis(
        name="dummy", description="", instrument="MNQ", timeframe="5min",
        build_variant=_dummy_build_variant, param_grid=[{"timeout_bars": 12}],
    )
    assert h.prepare_features is None


def test_hypothesis_prepare_features_accepts_callable():
    def _prep(df):
        return df
    h = Hypothesis(
        name="dummy", description="", instrument="MNQ", timeframe="5min",
        build_variant=_dummy_build_variant, param_grid=[{"timeout_bars": 12}],
        prepare_features=_prep,
    )
    assert h.prepare_features is _prep


def test_hypothesis_prepare_features_non_callable_leve_erreur():
    with pytest.raises(TypeError):
        Hypothesis(
            name="bad", description="", instrument="MNQ", timeframe="5min",
            build_variant=_dummy_build_variant, param_grid=[{"timeout_bars": 12}],
            prepare_features="pas une fonction",
        )
