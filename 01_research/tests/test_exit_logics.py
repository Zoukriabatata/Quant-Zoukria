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


def test_time_stop_fires_at_cutoff():
    # j=1 : close_min_ny = 15*60 + 50 + 5 = 955 >= 955 -> exit MTM au close
    df = pd.DataFrame({'hour_ny': [15, 15], 'min_ny': [45, 50], 'close': [100.0, 101.0]})
    touched, price, reason = exit_logic_time_stop(
        df, i=0, j=1, direction=1, entry_price=100.0, std_i=5.0, mid_i=100.0,
        or_high=float('nan'), or_low=float('nan'), or_range=float('nan'), sl_pts=7.5,
        exit_ny_min=955, bar_size_min=5)
    assert touched is True
    assert price == 101.0
    assert reason == 'time_stop'


def test_time_stop_silent_before_cutoff():
    # j=1 : close_min_ny = 15*60 + 40 + 5 = 945 < 955 -> pas d'exit
    df = pd.DataFrame({'hour_ny': [15, 15], 'min_ny': [30, 40], 'close': [100.0, 101.0]})
    touched, price, reason = exit_logic_time_stop(
        df, i=0, j=1, direction=1, entry_price=100.0, std_i=5.0, mid_i=100.0,
        or_high=float('nan'), or_low=float('nan'), or_range=float('nan'), sl_pts=7.5,
        exit_ny_min=955, bar_size_min=5)
    assert touched is False


def test_time_stop_15min_cutoff_945():
    # 15min : close_min_ny = 15*60 + 30 + 15 = 945 >= 945 -> exit
    df = pd.DataFrame({'hour_ny': [15, 15], 'min_ny': [15, 30], 'close': [100.0, 102.0]})
    touched, price, reason = exit_logic_time_stop(
        df, i=0, j=1, direction=-1, entry_price=100.0, std_i=5.0, mid_i=100.0,
        or_high=float('nan'), or_low=float('nan'), or_range=float('nan'), sl_pts=7.5,
        exit_ny_min=945, bar_size_min=15)
    assert touched is True
    assert price == 102.0
    assert reason == 'time_stop'


def test_trailing_std_long_retrace_hits():
    # bars 1..3 : excursion favorable max high = max(108,112,111) = 112
    # trail_dist = 1.0 * 5 = 5 -> trail_price = 107 ; low[3]=106 <= 107 -> hit
    # fill = 107 - trail_slip_pts(0.25) = 106.75
    df = pd.DataFrame({
        'high':  [100.0, 108.0, 112.0, 111.0],
        'low':   [100.0, 104.0, 109.0, 106.0],
        'close': [100.0, 107.0, 111.0, 107.0],
    })
    touched, price, reason = exit_logic_trailing_std(
        df, i=0, j=3, direction=1, entry_price=100.0, std_i=5.0, mid_i=100.0,
        or_high=float('nan'), or_low=float('nan'), or_range=float('nan'), sl_pts=7.5,
        trail_std_mult=1.0)
    assert touched is True
    assert price == 106.75
    assert reason == 'trail'


def test_trailing_std_long_no_hit():
    # excursion max high = 113 -> trail_price = 108 ; low[3]=110 > 108 -> pas de hit
    df = pd.DataFrame({
        'high':  [100.0, 108.0, 112.0, 113.0],
        'low':   [100.0, 104.0, 109.0, 110.0],
        'close': [100.0, 107.0, 111.0, 112.0],
    })
    touched, price, reason = exit_logic_trailing_std(
        df, i=0, j=3, direction=1, entry_price=100.0, std_i=5.0, mid_i=100.0,
        or_high=float('nan'), or_low=float('nan'), or_range=float('nan'), sl_pts=7.5,
        trail_std_mult=1.0)
    assert touched is False


def test_trailing_std_short_retrace_hits():
    # short : excursion favorable min low = min(92,88,89) = 88
    # trail_dist = 5 -> trail_price = 93 ; high[3]=94 >= 93 -> hit
    # fill = 93 + trail_slip_pts(0.25) = 93.25
    df = pd.DataFrame({
        'high':  [100.0, 96.0, 91.0, 94.0],
        'low':   [100.0, 92.0, 88.0, 89.0],
        'close': [100.0, 93.0, 89.0, 93.0],
    })
    touched, price, reason = exit_logic_trailing_std(
        df, i=0, j=3, direction=-1, entry_price=100.0, std_i=5.0, mid_i=100.0,
        or_high=float('nan'), or_low=float('nan'), or_range=float('nan'), sl_pts=7.5,
        trail_std_mult=1.0)
    assert touched is True
    assert price == 93.25
    assert reason == 'trail'


def test_trailing_std_short_no_hit():
    # short : excursion favorable min low = min(92,88,87) = 87 -> trail_price = 92
    # high[3]=90 < 92 -> pas de hit
    df = pd.DataFrame({
        'high':  [100.0, 96.0, 92.0, 90.0],
        'low':   [100.0, 92.0, 88.0, 87.0],
        'close': [100.0, 93.0, 89.0, 88.0],
    })
    touched, price, reason = exit_logic_trailing_std(
        df, i=0, j=3, direction=-1, entry_price=100.0, std_i=5.0, mid_i=100.0,
        or_high=float('nan'), or_low=float('nan'), or_range=float('nan'), sl_pts=7.5,
        trail_std_mult=1.0)
    assert touched is False


def test_hybrid_zscore_fires_first():
    # short trade (entré sur z>2). j=1 : z=0.8 <= zscore_exit=1.0 -> TP_zscore au close
    df = pd.DataFrame({
        'zscore': [2.5, 0.8], 'hour_ny': [15, 15], 'min_ny': [10, 15], 'close': [100.0, 99.0],
    })
    touched, price, reason = exit_logic_hybrid_zscore_time(
        df, i=0, j=1, direction=-1, entry_price=100.0, std_i=5.0, mid_i=100.0,
        or_high=float('nan'), or_low=float('nan'), or_range=float('nan'), sl_pts=7.5,
        zscore_exit=1.0, exit_ny_min=955, bar_size_min=5)
    assert touched is True
    assert price == 99.0
    assert reason == 'TP_zscore'


def test_hybrid_time_fires_when_zscore_silent():
    # short trade. j=1 : z=1.8 > 1.0 -> pas de TP z. close_min_ny=15*60+50+5=955 -> time_stop
    df = pd.DataFrame({
        'zscore': [2.5, 1.8], 'hour_ny': [15, 15], 'min_ny': [45, 50], 'close': [100.0, 99.5],
    })
    touched, price, reason = exit_logic_hybrid_zscore_time(
        df, i=0, j=1, direction=-1, entry_price=100.0, std_i=5.0, mid_i=100.0,
        or_high=float('nan'), or_low=float('nan'), or_range=float('nan'), sl_pts=7.5,
        zscore_exit=1.0, exit_ny_min=955, bar_size_min=5)
    assert touched is True
    assert price == 99.5
    assert reason == 'time_stop'


def test_hybrid_no_exit_when_both_silent():
    # j=1 : z=1.8 > 1.0 (pas de TP z) ET close_min_ny=15*60+10+5=915 < 955 -> rien
    df = pd.DataFrame({
        'zscore': [2.5, 1.8], 'hour_ny': [15, 15], 'min_ny': [5, 10], 'close': [100.0, 99.5],
    })
    touched, price, reason = exit_logic_hybrid_zscore_time(
        df, i=0, j=1, direction=-1, entry_price=100.0, std_i=5.0, mid_i=100.0,
        or_high=float('nan'), or_low=float('nan'), or_range=float('nan'), sl_pts=7.5,
        zscore_exit=1.0, exit_ny_min=955, bar_size_min=5)
    assert touched is False
