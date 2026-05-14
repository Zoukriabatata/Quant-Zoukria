"""Tests de compute_features_opening_drive — données synthétiques déterministes."""
import numpy as np
import pandas as pd

from src.features import compute_features_opening_drive


def _session_df():
    """3 jours de session RTH synthétique, 3 barres 1-min/jour (9:30, 9:31, 9:32).

    Jour 1 (2022-01-03) : open 9:30 = 100 ; closes [100, 101, 99] ; last close 99.
    Jour 2 (2022-01-04) : open 9:30 = 102 ; closes [102, 103, 101] ; last close 101.
    Jour 3 (2022-01-05) : open 9:30 = 98  ; closes [98,  97,  99].
    """
    rows = []
    spec = {
        "2022-01-03": (100.0, [100.0, 101.0, 99.0]),
        "2022-01-04": (102.0, [102.0, 103.0, 101.0]),
        "2022-01-05": (98.0, [98.0, 97.0, 99.0]),
    }
    for day, (op, closes) in spec.items():
        for b, c in enumerate(closes):
            ts = pd.Timestamp(f"{day} 09:3{b}", tz="America/New_York").tz_convert("UTC")
            o = op if b == 0 else closes[b - 1]
            rows.append({
                "bar": ts, "open": o, "high": max(o, c) + 1.0, "low": min(o, c) - 1.0,
                "close": c, "volume": 1000.0 + 100.0 * b,
            })
    df = pd.DataFrame(rows).set_index("bar")
    df["date"] = df.index.tz_convert("America/New_York").date
    df["hour_ny"] = 9
    df["min_ny"] = [0, 1, 2] * 3
    df["min_ny"] = [30, 31, 32] * 3
    return df


def test_open_ref_constant_par_jour():
    out = compute_features_opening_drive(_session_df())
    d1 = out[out["date"] == pd.Timestamp("2022-01-03").date()]
    assert (d1["open_ref"] == 100.0).all()
    d3 = out[out["date"] == pd.Timestamp("2022-01-05").date()]
    assert (d3["open_ref"] == 98.0).all()


def test_prev_close_est_la_cloture_de_la_veille():
    out = compute_features_opening_drive(_session_df())
    d1 = out[out["date"] == pd.Timestamp("2022-01-03").date()]
    assert d1["prev_close"].isna().all()                     # pas de veille
    d2 = out[out["date"] == pd.Timestamp("2022-01-04").date()]
    assert (d2["prev_close"] == 99.0).all()                  # last close jour 1
    d3 = out[out["date"] == pd.Timestamp("2022-01-05").date()]
    assert (d3["prev_close"] == 101.0).all()                 # last close jour 2


def test_spike_magnitude_est_close_moins_open_ref():
    out = compute_features_opening_drive(_session_df())
    d3 = out[out["date"] == pd.Timestamp("2022-01-05").date()]
    # closes jour 3 = [98, 97, 99], open_ref = 98 -> spike = [0, -1, 1]
    assert list(d3["spike_magnitude"]) == [0.0, -1.0, 1.0]


def test_rejection_body_formule():
    # bougie : open 98, close 97 -> high = max(98,97)+1 = 99, low = min(98,97)-1 = 96
    # rejection_body = (close - low) / (high - low) = (97 - 96) / (99 - 96) = 1/3
    out = compute_features_opening_drive(_session_df())
    d3 = out[out["date"] == pd.Timestamp("2022-01-05").date()]
    assert abs(d3["rejection_body"].iloc[1] - (1.0 / 3.0)) < 1e-9


def test_gap_z_signe_correct():
    # jour 3 : open 98, prev_close 101 -> gap overnight = -3 (baissier) -> gap_z < 0
    out = compute_features_opening_drive(_session_df(), gap_std_window=2)
    d3 = out[out["date"] == pd.Timestamp("2022-01-05").date()]
    assert d3["gap_z"].notna().all()
    assert (d3["gap_z"] < 0).all()


def test_vol_regime_est_booleen_sans_nan():
    out = compute_features_opening_drive(_session_df(), vol_regime_window=2)
    assert out["vol_regime"].dtype == bool
    assert not out["vol_regime"].isna().any()


def test_colonnes_produites():
    out = compute_features_opening_drive(_session_df())
    for col in ["open_ref", "prev_close", "gap_z", "spike_magnitude",
                "rejection_body", "vol_regime", "relvol_open"]:
        assert col in out.columns
