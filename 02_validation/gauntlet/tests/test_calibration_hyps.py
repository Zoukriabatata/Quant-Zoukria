"""Tests des 2 hypothèses de calibration (objets Hypothesis bien formés)."""
from gauntlet.hypothesis import Hypothesis
from gauntlet.calibration.hyp_eod_reversal import HYP_EOD_REVERSAL
from gauntlet.calibration.hyp_v9_hurstmr import HYP_V9_HURSTMR


def _check_well_formed(hyp):
    assert isinstance(hyp, Hypothesis)
    assert hyp.instrument in {"MNQ"}
    assert hyp.timeframe == "5min"
    assert callable(hyp.prepare_features)
    assert len(hyp.param_grid) >= 1
    # build_variant produit le triplet (signal_fn, exit_logic, backtest_kwargs)
    for params in hyp.param_grid:
        signal_fn, exit_logic, bt_kwargs = hyp.build_variant(params)
        assert callable(signal_fn)
        assert callable(exit_logic)
        assert "bar_size_min" in bt_kwargs and "timeout_bars" in bt_kwargs


def test_eod_reversal_hypothesis_well_formed():
    _check_well_formed(HYP_EOD_REVERSAL)
    assert HYP_EOD_REVERSAL.name == "eod_reversal_control"
    assert HYP_EOD_REVERSAL.n_trials == 3


def test_v9_hurstmr_hypothesis_well_formed():
    _check_well_formed(HYP_V9_HURSTMR)
    assert HYP_V9_HURSTMR.name == "v9_hurstmr_control"
    assert HYP_V9_HURSTMR.n_trials == 3


def test_prepare_features_ajoute_les_colonnes_attendues():
    import numpy as np
    import pandas as pd
    # df de session minimal : 3 jours, 80 barres/jour, colonnes OHLC + temporelles
    rows = []
    for d in pd.bdate_range("2022-01-03", periods=3):
        base = pd.Timestamp(d.year, d.month, d.day, 9, 30, tz="UTC")
        for b in range(80):
            rows.append((base + pd.Timedelta(minutes=5 * b), 100.0 + np.sin(b / 5)))
    idx = pd.DatetimeIndex([r[0] for r in rows])
    df = pd.DataFrame({"close": [r[1] for r in rows]}, index=idx)
    df["high"] = df["close"] + 0.5
    df["low"] = df["close"] - 0.5
    df["date"] = df.index.date
    df["hour_ny"] = df.index.hour
    df["min_ny"] = df.index.minute

    eod_feat = HYP_EOD_REVERSAL.prepare_features(df)
    assert {"mid", "std", "zscore"}.issubset(eod_feat.columns)

    v9_feat = HYP_V9_HURSTMR.prepare_features(df)
    assert {"mid", "std", "zscore", "hurst"}.issubset(v9_feat.columns)
