"""Tests de signal_opening_drive_failure — données synthétiques avec features injectées."""
import numpy as np
import pandas as pd

from src.signals import signal_opening_drive_failure


def _df_with_features(rows):
    """rows : liste de dicts avec gap_z, spike_magnitude, rejection_body, vol_regime,
    relvol_open, hour_ny, min_ny. Construit un df indexé temps."""
    idx = pd.date_range("2022-01-03 14:30", periods=len(rows), freq="1min", tz="UTC")
    return pd.DataFrame(rows, index=idx)


def _long_row():
    """Une ligne où les 5 conditions LONG sont remplies (down-spike à fader)."""
    return dict(gap_z=-1.0, spike_magnitude=-20.0, rejection_body=0.8,
                vol_regime=True, relvol_open=1.5, hour_ny=9, min_ny=45)


def _short_row():
    """Une ligne où les 5 conditions SHORT sont remplies (up-spike à fader)."""
    return dict(gap_z=1.0, spike_magnitude=20.0, rejection_body=0.2,
                vol_regime=True, relvol_open=1.5, hour_ny=9, min_ny=45)


def test_long_signal_quand_les_5_conditions_alignees():
    out = signal_opening_drive_failure(_df_with_features([_long_row()]),
                                       window_end_min=630, gap_threshold=0.5,
                                       spike_min=15.0, rejet_seuil=0.66, relvol_seuil=1.0)
    assert out["signal"].iloc[0] == 1


def test_short_signal_symetrique():
    out = signal_opening_drive_failure(_df_with_features([_short_row()]),
                                       window_end_min=630, gap_threshold=0.5,
                                       spike_min=15.0, rejet_seuil=0.66, relvol_seuil=1.0)
    assert out["signal"].iloc[0] == -1


def test_pas_de_signal_si_gap_trop_faible():
    row = _long_row()
    row["gap_z"] = -0.2                              # < gap_threshold 0.5
    out = signal_opening_drive_failure(_df_with_features([row]), window_end_min=630,
                                       gap_threshold=0.5, spike_min=15.0,
                                       rejet_seuil=0.66, relvol_seuil=1.0)
    assert out["signal"].iloc[0] == 0


def test_pas_de_signal_hors_fenetre():
    row = _long_row()
    row["hour_ny"], row["min_ny"] = 11, 0            # 11:00, hors fenêtre 9:30-10:30
    out = signal_opening_drive_failure(_df_with_features([row]), window_end_min=630,
                                       gap_threshold=0.5, spike_min=15.0,
                                       rejet_seuil=0.66, relvol_seuil=1.0)
    assert out["signal"].iloc[0] == 0


def test_pas_de_signal_si_vol_regime_faux():
    row = _long_row()
    row["vol_regime"] = False
    out = signal_opening_drive_failure(_df_with_features([row]), window_end_min=630,
                                       gap_threshold=0.5, spike_min=15.0,
                                       rejet_seuil=0.66, relvol_seuil=1.0)
    assert out["signal"].iloc[0] == 0


def test_nan_feature_ne_declenche_pas():
    row = _long_row()
    row["gap_z"] = np.nan                            # warmup -> pas de trade
    out = signal_opening_drive_failure(_df_with_features([row]), window_end_min=630,
                                       gap_threshold=0.5, spike_min=15.0,
                                       rejet_seuil=0.66, relvol_seuil=1.0)
    assert out["signal"].iloc[0] == 0


def test_window_end_min_resserre_la_fenetre():
    # 10:15 NY : dans la fenêtre 9:30-10:30 (630) mais hors 9:30-10:00 (600)
    row = _long_row()
    row["hour_ny"], row["min_ny"] = 10, 15
    out_large = signal_opening_drive_failure(_df_with_features([row]), window_end_min=630,
                                             gap_threshold=0.5, spike_min=15.0,
                                             rejet_seuil=0.66, relvol_seuil=1.0)
    out_tight = signal_opening_drive_failure(_df_with_features([row]), window_end_min=600,
                                             gap_threshold=0.5, spike_min=15.0,
                                             rejet_seuil=0.66, relvol_seuil=1.0)
    assert out_large["signal"].iloc[0] == 1
    assert out_tight["signal"].iloc[0] == 0
