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
