"""Tests de exit_logic_return_to_open — données synthétiques."""
import numpy as np
import pandas as pd

from src.backtest import exit_logic_return_to_open

# Signature exit_logic : (df, i, j, direction, entry_price, std_i, mid_i,
#                         or_high, or_low, or_range, sl_pts)
_NAN = float("nan")


def _df(open_ref, high, low):
    """df 2 barres : barre 0 = entrée, barre 1 = barre testée (j=1)."""
    return pd.DataFrame({
        "open_ref": [open_ref, open_ref],
        "high": [high, high],
        "low": [low, low],
    })


def test_long_tp_touche_quand_high_atteint_open_ref():
    # LONG : entrée à 95 (down-spike), open_ref = 100. high de la barre = 101 >= 100 -> TP.
    df = _df(open_ref=100.0, high=101.0, low=99.0)
    touched, price, reason = exit_logic_return_to_open(
        df, 0, 1, 1, 95.0, 4.0, 95.0, _NAN, _NAN, _NAN, 6.0)
    assert touched is True
    assert price == 100.0
    assert reason == "TP_return_to_open"


def test_long_tp_pas_touche_si_high_sous_open_ref():
    # LONG, high = 99 < open_ref 100 -> pas de TP.
    df = _df(open_ref=100.0, high=99.0, low=97.0)
    touched, price, reason = exit_logic_return_to_open(
        df, 0, 1, 1, 95.0, 4.0, 95.0, _NAN, _NAN, _NAN, 6.0)
    assert touched is False


def test_short_tp_touche_quand_low_atteint_open_ref():
    # SHORT : entrée à 105 (up-spike), open_ref = 100. low de la barre = 99 <= 100 -> TP.
    df = _df(open_ref=100.0, high=106.0, low=99.0)
    touched, price, reason = exit_logic_return_to_open(
        df, 0, 1, -1, 105.0, 4.0, 105.0, _NAN, _NAN, _NAN, 6.0)
    assert touched is True
    assert price == 100.0
    assert reason == "TP_return_to_open"


def test_short_tp_pas_touche_si_low_au_dessus_open_ref():
    # SHORT, low = 101 > open_ref 100 -> pas de TP.
    df = _df(open_ref=100.0, high=104.0, low=101.0)
    touched, price, reason = exit_logic_return_to_open(
        df, 0, 1, -1, 105.0, 4.0, 105.0, _NAN, _NAN, _NAN, 6.0)
    assert touched is False


def test_open_ref_nan_pas_de_tp():
    df = _df(open_ref=np.nan, high=101.0, low=99.0)
    touched, price, reason = exit_logic_return_to_open(
        df, 0, 1, 1, 95.0, 4.0, 95.0, _NAN, _NAN, _NAN, 6.0)
    assert touched is False
