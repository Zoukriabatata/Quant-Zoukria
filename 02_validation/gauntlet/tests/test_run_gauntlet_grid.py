"""Tests des helpers de grille de run_gauntlet."""
import numpy as np
import pandas as pd

from gauntlet.hypothesis import Hypothesis
from gauntlet.run_gauntlet import (
    _extract_embargo, _run_grid_on, _select_best_on_train, _compute_pbo,
)


def _hyp(grid, timeouts=None):
    """Hypothèse factice. timeouts : timeout_bars par variant (défaut 10)."""
    timeouts = timeouts or [10] * len(grid)

    def build_variant(params):
        idx = grid.index(params)
        return (lambda d: d, lambda *a: (False, 0.0, ""),
                {"bar_size_min": 5, "timeout_bars": timeouts[idx]})

    return Hypothesis(name="h", description="", instrument="MNQ", timeframe="5min",
                      build_variant=build_variant, param_grid=grid)


def _fake_run_variant_factory():
    """run_variant factice : PnL dépend du param 'edge' (True -> positif, False -> négatif).
    Génère des trades sur 12 dates distinctes pour nourrir le PBO."""
    def run_variant(df, params):
        base = 100.0 if params["edge"] else -100.0
        trades = pd.DataFrame({
            "pnl_usd": [base + i for i in range(12)],
            "date": pd.date_range("2022-01-03", periods=12, freq="D"),
        })
        return trades, None
    return run_variant


def test_extract_embargo_prend_le_max_timeout():
    grid = [{"edge": True}, {"edge": False}]
    hyp = _hyp(grid, timeouts=[12, 120])
    assert _extract_embargo(hyp) == 120


def test_run_grid_on_aligne_sur_la_grille():
    grid = [{"edge": True}, {"edge": False}]
    hyp = _hyp(grid)
    rv = _fake_run_variant_factory()
    results = _run_grid_on(pd.DataFrame({"close": [1.0]}), hyp, rv)
    assert len(results) == 2
    assert results[0]["params"] == {"edge": True}
    assert results[1]["params"] == {"edge": False}
    assert results[0]["metrics"]["trades"] == 12
    assert "account" in results[0] and "trades" in results[0]


def test_select_best_on_train_prend_le_meilleur_sharpe():
    grid = [{"edge": False}, {"edge": True}]
    hyp = _hyp(grid)
    rv = _fake_run_variant_factory()
    results = _run_grid_on(pd.DataFrame({"close": [1.0]}), hyp, rv)
    best_params, best_idx, sharpes = _select_best_on_train(results)
    assert best_params == {"edge": True}
    assert best_idx == 1
    assert len(sharpes) == 2


def test_compute_pbo_none_si_grille_un_variant():
    grid = [{"edge": True}]
    hyp = _hyp(grid)
    rv = _fake_run_variant_factory()
    results = _run_grid_on(pd.DataFrame({"close": [1.0]}), hyp, rv)
    assert _compute_pbo(results, n_splits=4) is None


def test_compute_pbo_renvoie_un_float_dans_unit_interval():
    grid = [{"edge": True}, {"edge": False}]
    hyp = _hyp(grid)
    rv = _fake_run_variant_factory()
    results = _run_grid_on(pd.DataFrame({"close": [1.0]}), hyp, rv)
    pbo = _compute_pbo(results, n_splits=4)
    assert pbo is not None
    assert 0.0 <= pbo <= 1.0


def test_compute_pbo_none_si_matrice_trop_courte():
    grid = [{"edge": True}, {"edge": False}]
    hyp = _hyp(grid)
    rv = _fake_run_variant_factory()        # 12 jours
    results = _run_grid_on(pd.DataFrame({"close": [1.0]}), hyp, rv)
    assert _compute_pbo(results, n_splits=50) is None
