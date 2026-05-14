"""Tests unitaires des exit logics du sprint re-engineering — données synthétiques."""
import pandas as pd

from src.backtest import (
    exit_logic_fixed_tp_std,
    exit_logic_time_stop,
    exit_logic_trailing_std,
    exit_logic_hybrid_zscore_time,
)


def test_imports_ok():
    """Sentinelle : les 4 exit logics sont importables."""
    assert callable(exit_logic_fixed_tp_std)
    assert callable(exit_logic_time_stop)
    assert callable(exit_logic_trailing_std)
    assert callable(exit_logic_hybrid_zscore_time)


def test_fixed_tp_std_long_hit():
    # entry 100, std 8, tp_std_mult 0.5 -> TP long = 100 + 1*0.5*8 = 104
    df = pd.DataFrame({'high': [100.0, 104.0], 'low': [100.0, 99.0], 'close': [100.0, 103.0]})
    touched, price, reason = exit_logic_fixed_tp_std(
        df, i=0, j=1, direction=1, entry_price=100.0, std_i=8.0, mid_i=100.0,
        or_high=float('nan'), or_low=float('nan'), or_range=float('nan'), sl_pts=7.5,
        tp_std_mult=0.5)
    assert touched is True
    assert price == 104.0
    assert reason == 'TP_fixed_std'


def test_fixed_tp_std_short_hit():
    # short: TP = 100 + (-1)*0.5*8 = 96
    df = pd.DataFrame({'high': [100.0, 101.0], 'low': [100.0, 95.0], 'close': [100.0, 97.0]})
    touched, price, reason = exit_logic_fixed_tp_std(
        df, i=0, j=1, direction=-1, entry_price=100.0, std_i=8.0, mid_i=100.0,
        or_high=float('nan'), or_low=float('nan'), or_range=float('nan'), sl_pts=7.5,
        tp_std_mult=0.5)
    assert touched is True
    assert price == 96.0
    assert reason == 'TP_fixed_std'


def test_fixed_tp_std_no_hit():
    # TP long = 104, high[1]=102 < 104 -> pas touché
    df = pd.DataFrame({'high': [100.0, 102.0], 'low': [100.0, 99.0], 'close': [100.0, 101.0]})
    touched, price, reason = exit_logic_fixed_tp_std(
        df, i=0, j=1, direction=1, entry_price=100.0, std_i=8.0, mid_i=100.0,
        or_high=float('nan'), or_low=float('nan'), or_range=float('nan'), sl_pts=7.5,
        tp_std_mult=0.5)
    assert touched is False
