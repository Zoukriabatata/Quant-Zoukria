"""Tests de l'hypothèse Opening Drive Failure Fade (objet Hypothesis bien formé)."""
import numpy as np
import pandas as pd

from gauntlet.hypothesis import Hypothesis
from gauntlet.hypotheses.hyp_opening_drive_failure import HYP_OPENING_DRIVE_FAILURE


def test_hypothesis_bien_formee():
    h = HYP_OPENING_DRIVE_FAILURE
    assert isinstance(h, Hypothesis)
    assert h.name == "opening_drive_failure"
    assert h.instrument == "MNQ"
    assert h.timeframe == "1min"
    assert h.n_trials == 4
    assert callable(h.prepare_features)


def test_build_variant_retourne_le_triplet():
    h = HYP_OPENING_DRIVE_FAILURE
    for params in h.param_grid:
        signal_fn, exit_logic, bt_kwargs = h.build_variant(params)
        assert callable(signal_fn)
        assert callable(exit_logic)
        assert bt_kwargs["bar_size_min"] == 1
        assert "timeout_bars" in bt_kwargs


def test_param_grid_est_window_x_gap():
    grid = HYP_OPENING_DRIVE_FAILURE.param_grid
    windows = {p["window_end_min"] for p in grid}
    gaps = {p["gap_threshold"] for p in grid}
    assert windows == {600, 630}              # 9:30-10:00 et 9:30-10:30
    assert gaps == {0.5, 1.0}
    assert len(grid) == 4


def test_prepare_features_ajoute_les_colonnes_attendues():
    # df de session synthétique : 2 jours, 5 barres/jour autour de 9:30 NY
    rows = []
    for day in ["2022-01-03", "2022-01-04"]:
        for b in range(5):
            ts = pd.Timestamp(f"{day} 09:3{b}", tz="America/New_York").tz_convert("UTC")
            rows.append({"bar": ts, "open": 100.0 + b, "high": 102.0 + b,
                         "low": 98.0 + b, "close": 100.5 + b, "volume": 1000.0})
    df = pd.DataFrame(rows).set_index("bar")
    df["date"] = df.index.tz_convert("America/New_York").date
    df["hour_ny"] = 9
    df["min_ny"] = [30, 31, 32, 33, 34] * 2

    feat = HYP_OPENING_DRIVE_FAILURE.prepare_features(df)
    # std + mid (via compute_signal_features, exigés par backtest_pa)
    assert {"std", "mid"}.issubset(feat.columns)
    # features opening drive
    assert {"open_ref", "gap_z", "spike_magnitude", "rejection_body",
            "vol_regime", "relvol_open"}.issubset(feat.columns)


def test_build_variant_signal_fn_produit_une_colonne_signal():
    # le signal_fn doit tourner sur un df qui a les features et produire 'signal'
    h = HYP_OPENING_DRIVE_FAILURE
    signal_fn, _, _ = h.build_variant(h.param_grid[0])
    df = pd.DataFrame({
        "gap_z": [np.nan], "spike_magnitude": [0.0], "rejection_body": [0.5],
        "vol_regime": [False], "relvol_open": [np.nan], "hour_ny": [9], "min_ny": [45],
    })
    out = signal_fn(df)
    assert "signal" in out.columns
    assert out["signal"].iloc[0] == 0          # features dégénérées -> pas de signal
