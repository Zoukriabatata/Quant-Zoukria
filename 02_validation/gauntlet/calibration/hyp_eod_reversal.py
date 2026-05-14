"""Hypothèse contrôle de calibration — EOD Reversal MNQ 5min.

KNOWN-ANSWER : doit ressortir NO-GO. Mini-validation #4 : PF 0.80 Train Apex-compliant,
0/61 mois passés. L'edge EOD reversal se complète après 16:00 NY (close auction) — Apex
verrouille le trader dehors. Encode l'ENTRÉE EOD reversal (MR z-score sur la pocket 15h NY)
jugée par les mécaniques du gauntlet ; la grille balaie le z-score d'exit (configs C0/C1/C2
du sprint re-engineering exit).
"""
from __future__ import annotations

from functools import partial

from src.config import ENTRY_CUTOFF_NY_MIN
from src.features import compute_signal_features
from src.signals import signal_mr_zscore
from src.backtest import exit_logic_mr_zscore

from gauntlet.hypothesis import Hypothesis

_BAR_MIN = 5
_LOOKBACK = 20          # lookback z-score (mini-val #4)
_TIMEOUT_BARS = 12      # 5min : timeout = 12 barres (mini-val #4)


def _prepare_features(df):
    """Features MR z-score (mid / std / zscore rolling)."""
    return compute_signal_features(df, lookback=_LOOKBACK)


def _build_variant(params):
    """params: {'zscore_exit': float}. Entrée z>2 pocket 15h NY, exit z-score."""
    def signal_fn(df):
        return signal_mr_zscore(
            df, entry_threshold=2.0, allowed_hours={15},
            entry_cutoff_ny_min=ENTRY_CUTOFF_NY_MIN, bar_size_min=_BAR_MIN,
        )
    exit_logic = partial(exit_logic_mr_zscore, zscore_exit=params["zscore_exit"])
    return signal_fn, exit_logic, {"bar_size_min": _BAR_MIN, "timeout_bars": _TIMEOUT_BARS}


HYP_EOD_REVERSAL = Hypothesis(
    name="eod_reversal_control",
    description="EOD Reversal MNQ 5min — MR z>2 pocket 15h NY, exit z-score — contrôle known-NO-GO",
    instrument="MNQ",
    timeframe="5min",
    build_variant=_build_variant,
    param_grid=[{"zscore_exit": 0.5}, {"zscore_exit": 1.0}, {"zscore_exit": 1.5}],
    prepare_features=_prepare_features,
)
