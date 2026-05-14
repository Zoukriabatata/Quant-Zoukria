"""Tests du walk-forward purgé à fenêtres ancrées."""
import numpy as np
import pandas as pd
import pytest

from gauntlet.walk_forward import purged_walk_forward, walk_forward_summary


def _make_df(n_bars: int) -> pd.DataFrame:
    """DataFrame minimal indexé temps — le contenu n'importe pas (run_variant est factice)."""
    idx = pd.date_range("2022-01-01", periods=n_bars, freq="1h", tz="UTC")
    return pd.DataFrame({"close": np.arange(n_bars, dtype=float)}, index=idx)


def _fake_run_variant_factory(call_log):
    """Construit un run_variant factice qui :
      - journalise (len(df), params) à chaque appel dans call_log ;
      - retourne des trades dont le PnL dépend du param 'edge' :
          edge=True  -> 10 trades positifs  (Sharpe > 0)
          edge=False -> 10 trades négatifs  (Sharpe < 0)
    """
    def run_variant(df_slice, params):
        call_log.append((len(df_slice), dict(params)))
        base = 100.0 if params["edge"] else -100.0
        trades = pd.DataFrame({
            "pnl_usd": [base + i for i in range(10)],   # +i -> écart-type != 0
            "date": pd.date_range("2022-06-01", periods=10, freq="D"),
        })
        return trades, None
    return run_variant


def test_wf_produces_n_windows():
    df = _make_df(220)
    rv = _fake_run_variant_factory([])
    wf = purged_walk_forward(df, [{"edge": True}], rv, n_windows=4, embargo_bars=5)
    assert len(wf) == 4
    assert list(wf["window"]) == [0, 1, 2, 3]


def test_wf_selects_best_param_on_is():
    df = _make_df(220)
    rv = _fake_run_variant_factory([])
    grid = [{"edge": False}, {"edge": True}]
    wf = purged_walk_forward(df, grid, rv, n_windows=3, embargo_bars=5)
    # edge=True donne un Sharpe positif -> sélectionné sur CHAQUE fenêtre
    assert all(p == {"edge": True} for p in wf["best_params"])
    assert wf["oos_profitable"].all()


def test_wf_embargo_trims_is():
    df = _make_df(220)
    log = []
    rv = _fake_run_variant_factory(log)
    purged_walk_forward(df, [{"edge": True}], rv, n_windows=4, embargo_bars=7)
    # 5 tranches de 44 barres. Fenêtre 0 : IS ancré = tranche 0 = 44 barres, moins
    # embargo 7 -> 37. Premier appel journalisé = IS de la fenêtre 0.
    assert log[0][0] == 44 - 7


def test_wf_all_params_tried_on_is():
    df = _make_df(220)
    log = []
    rv = _fake_run_variant_factory(log)
    grid = [{"edge": False}, {"edge": True}]
    purged_walk_forward(df, grid, rv, n_windows=3, embargo_bars=5)
    # par fenêtre : 2 appels IS (un par param) + 1 appel OOS = 3. 3 fenêtres -> 9 appels.
    assert len(log) == 9


def test_wf_summary_aggregates():
    df = _make_df(220)
    rv = _fake_run_variant_factory([])
    wf = purged_walk_forward(df, [{"edge": True}], rv, n_windows=4, embargo_bars=5)
    s = walk_forward_summary(wf)
    assert s["n_windows"] == 4
    assert s["pct_oos_profitable"] == 1.0
    assert s["all_profitable"] is True
    assert s["oos_sharpe_mean"] > 0


def test_wf_rejects_too_short_df():
    df = _make_df(3)
    rv = _fake_run_variant_factory([])
    with pytest.raises(ValueError):
        purged_walk_forward(df, [{"edge": True}], rv, n_windows=5, embargo_bars=1)
