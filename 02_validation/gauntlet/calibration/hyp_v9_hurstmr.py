"""Hypothèse contrôle de calibration — v9 HurstMR MNQ 5min.

KNOWN-ANSWER : doit ressortir NO-GO. Backtest NT8 Strategy Analyzer tick-realistic
(5 ans MNQ) : PF 1.02, max DD -$22,748, Sharpe 0.05 — pas d'edge, bust Apex garanti.
Encode l'ENTRÉE v9 (MR z-score k=2.75 gaté par Hurst < 0.58, LB=19, HW=50) jugée par les
mécaniques honnêtes du gauntlet (backtest_pa impose son propre SL 1.5×std wick-aware, le
force-flat 15:55 et la friction obligatoire — donc ce contrôle n'est PAS le v9 NT8 à
l'identique, c'est voulu). La grille balaie band_k et le seuil Hurst.

Note : la "skip 14h UTC" du v9 Python était l'un des 5 défauts structurels documentés
(archétype python_backtest_illusion) — on ne la reproduit pas, le contrôle trade toute
la session.
"""
from __future__ import annotations

from functools import partial

from src.config import ENTRY_CUTOFF_NY_MIN, HURST_WINDOW, LOOKBACK
from src.features import compute_signal_features
from src.hurst import compute_rolling_hurst_by_session
from src.signals import signal_mr_zscore
from src.backtest import exit_logic_mr_zscore

from gauntlet.hypothesis import Hypothesis

_BAR_MIN = 5
_TIMEOUT_BARS = 120     # v9 : timeout 120 barres (config figée)


def _prepare_features(df):
    """Features MR z-score (LB=19) + colonne Hurst rolling par session (HW=50)."""
    out = compute_signal_features(df, lookback=LOOKBACK)          # LOOKBACK = 19
    out["hurst"] = compute_rolling_hurst_by_session(out, hwin=HURST_WINDOW)  # HURST_WINDOW = 50
    return out


def _build_variant(params):
    """params: {'band_k': float, 'hurst_threshold': float}. MR z-score gaté Hurst."""
    def signal_fn(df):
        sigs = signal_mr_zscore(
            df, entry_threshold=params["band_k"],
            entry_cutoff_ny_min=ENTRY_CUTOFF_NY_MIN, bar_size_min=_BAR_MIN,
        )
        # Gate Hurst : v9 ne trade le MR que si H < seuil (régime mean-reverting).
        # Hurst NaN (warmup de session) -> pas de trade.
        block = sigs["hurst"].isna() | (sigs["hurst"] >= params["hurst_threshold"])
        sigs.loc[block, "signal"] = 0
        return sigs
    exit_logic = partial(exit_logic_mr_zscore, zscore_exit=0.5)
    return signal_fn, exit_logic, {"bar_size_min": _BAR_MIN, "timeout_bars": _TIMEOUT_BARS}


HYP_V9_HURSTMR = Hypothesis(
    name="v9_hurstmr_control",
    description="v9 HurstMR MNQ 5min — MR z k=2.75 gaté Hurst<0.58 — contrôle known-NO-GO",
    instrument="MNQ",
    timeframe="5min",
    build_variant=_build_variant,
    param_grid=[
        {"band_k": 2.75, "hurst_threshold": 0.58},
        {"band_k": 2.50, "hurst_threshold": 0.58},
        {"band_k": 2.75, "hurst_threshold": 0.55},
    ],
    prepare_features=_prepare_features,
)
