# ---
# jupyter:
#   jupytext:
#     formats: py:percent,ipynb
#     text_representation:
#       extension: .py
#       format_name: percent
# ---

# %% [markdown]
# # Sprint Re-engineering Exit — EOD Reversal MNQ
#
# Teste si l'edge EOD Reversal MNQ (entry z>2, 15:00-15:55 NY) se capture avec un exit
# qui se résout avant le force-flat Apex 16:00. Grille de 8 configs d'exit × 2 TF,
# tout mesuré Apex-compliant.
#
# Spec : `docs/superpowers/specs/2026-05-14-sprint-reengineering-eod-reversal-design.md`
#
# **Exécuter depuis la racine du repo** (`python 01_research/notebooks/02_sprint_exit_reengineering.py`,
# ou lancer JupyterLab depuis la racine du repo).

# %%
import sys
from functools import partial
from pathlib import Path

import pandas as pd

# Ce script s'exécute depuis la racine du repo. 01_research/ sur le path pour `import src...`.
_RESEARCH_ROOT = Path('01_research').resolve()
if str(_RESEARCH_ROOT) not in sys.path:
    sys.path.insert(0, str(_RESEARCH_ROOT))

from src.config import (TRAIN_START, TRAIN_END, VALID_START, VALID_END,
                        ENTRY_CUTOFF_NY_MIN)
from src.instruments import INSTRUMENTS
from src.data_loader import (load_continuous, resample_ohlcv, add_temporal_columns,
                             filter_session_ny)
from src.features import compute_signal_features
from src.signals import signal_mr_zscore
from src.backtest import (backtest_apex, compute_trade_metrics, simulate_apex_cycle,
                          exit_logic_mr_zscore, exit_logic_fixed_tp_std,
                          exit_logic_time_stop, exit_logic_trailing_std,
                          exit_logic_hybrid_zscore_time)

OUT_DIR = Path('01_research/outputs/sprint_exit')
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Coût round-trip MNQ : commission 1.10 + slippage 1 tick (0.25 pt * 2.00 $ = 0.50)
RT_COST = INSTRUMENTS['MNQ']['commission_rt'] + 0.25 * INSTRUMENTS['MNQ']['point_value']

# Paramètres par timeframe (identiques à mini-val #4)
TF_PARAMS = {
    '5min':  dict(rule='5min',  bar_size_min=5,  timeout_bars=12, exit_ny_min=955),
    '15min': dict(rule='15min', bar_size_min=15, timeout_bars=4,  exit_ny_min=945),
}

# Chiffres de référence mini-val #4 (Train, Apex-compliant) pour le contrôle C0
MINIVAL4 = {
    '5min':  dict(trades=632, pf=0.8009),
    '15min': dict(trades=180, pf=0.7664),
}

# %%
def prepare_tf(rule: str) -> pd.DataFrame:
    """Charge MNQ M1, resample au TF, ajoute colonnes temporelles, filtre session NY,
    calcule mid/std/zscore. Pipeline identique à mini-val #4."""
    df_m1 = load_continuous(INSTRUMENTS['MNQ']['path'], 'MNQ')
    df_tf = resample_ohlcv(df_m1, rule)
    df_tf = add_temporal_columns(df_tf)
    df_sess = filter_session_ny(df_tf)
    df_feat = compute_signal_features(df_sess, lookback=20)
    return df_feat


def build_exit_configs(bar_size_min: int, exit_ny_min: int) -> dict:
    """Retourne {config_name: exit_logic callable} pour un TF donné."""
    return {
        'C0_zscore_0.5':    partial(exit_logic_mr_zscore, zscore_exit=0.5),
        'C1_zscore_1.0':    partial(exit_logic_mr_zscore, zscore_exit=1.0),
        'C2_zscore_1.5':    partial(exit_logic_mr_zscore, zscore_exit=1.5),
        'C3_fixed_0.75std': partial(exit_logic_fixed_tp_std, tp_std_mult=0.75),
        'C4_fixed_0.40std': partial(exit_logic_fixed_tp_std, tp_std_mult=0.40),
        'C5_time_stop':     partial(exit_logic_time_stop, exit_ny_min=exit_ny_min,
                                    bar_size_min=bar_size_min),
        'C6_trail_1.0std':  partial(exit_logic_trailing_std, trail_std_mult=1.0),
        'C7_hybrid':        partial(exit_logic_hybrid_zscore_time, zscore_exit=1.0,
                                    exit_ny_min=exit_ny_min, bar_size_min=bar_size_min),
    }


def run_config(df_split: pd.DataFrame, exit_logic, bar_size_min: int, timeout_bars: int):
    """Génère les signaux MR 15h NY Apex-compliant, backtest, retourne (métriques, trades)."""
    sigs = signal_mr_zscore(df_split, entry_threshold=2.0, allowed_hours={15},
                            entry_cutoff_ny_min=ENTRY_CUTOFF_NY_MIN,
                            bar_size_min=bar_size_min)
    trades = backtest_apex(sigs, exit_logic=exit_logic,
                           instrument_specs=INSTRUMENTS['MNQ'],
                           bar_size_min=bar_size_min, timeout_bars=timeout_bars,
                           apex_constraints=True)
    return compute_trade_metrics(trades), trades
