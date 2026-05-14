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
from __future__ import annotations

import sys
from functools import partial
from pathlib import Path

import pandas as pd

# Ce script s'exécute depuis la racine du repo. 01_research/ sur le path pour `import src...`.
_RESEARCH_ROOT = Path('01_research').resolve()
if not _RESEARCH_ROOT.is_dir():
    raise RuntimeError(
        f"01_research/ introuvable ({_RESEARCH_ROOT}). "
        "Lancer ce script / JupyterLab depuis la racine du repo."
    )
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

OUT_DIR = _RESEARCH_ROOT / 'outputs' / 'sprint_exit'
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
def prepare_tf(rule: str, lookback: int = 20, df_m1: pd.DataFrame | None = None) -> pd.DataFrame:
    """Charge MNQ M1, resample au TF, ajoute colonnes temporelles, filtre session NY,
    calcule mid/std/zscore. Pipeline identique à mini-val #4 (lookback=20).

    Si df_m1 est fourni, le réutilise au lieu de recharger le CSV (évite des lectures
    répétées du fichier ~1.7M lignes quand on prépare plusieurs TF)."""
    if df_m1 is None:
        df_m1 = load_continuous(INSTRUMENTS['MNQ']['path'], 'MNQ')
    df_tf = resample_ohlcv(df_m1, rule)
    df_tf = add_temporal_columns(df_tf)
    df_sess = filter_session_ny(df_tf)
    df_feat = compute_signal_features(df_sess, lookback=lookback)
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


# %% [markdown]
# ## Contrôle C0 — fidélité du harness
#
# La config C0 (exit z-score ±0.5) doit reproduire les chiffres Apex-compliant de
# mini-validation #4. Si l'assertion échoue, le harness `src/` a divergé du pipeline
# inline de mini-val #4 — STOP, investiguer avant de faire confiance à C1-C7.

# %%
def split_train(df: pd.DataFrame) -> pd.DataFrame:
    """Slice le split Train (TRAIN_START <= index < TRAIN_END)."""
    return df.loc[(df.index >= TRAIN_START) & (df.index < TRAIN_END)].copy()


def split_valid(df: pd.DataFrame) -> pd.DataFrame:
    """Slice le split Valid (VALID_START <= index < VALID_END)."""
    return df.loc[(df.index >= VALID_START) & (df.index < VALID_END)].copy()


# M1 chargé une seule fois, partagé entre les TF (évite 2 lectures du CSV ~1.7M lignes)
_M1 = load_continuous(INSTRUMENTS['MNQ']['path'], 'MNQ')
# Cache des DataFrames préparés par TF (réutilisés par la grille complète)
_PREPARED = {tf: prepare_tf(TF_PARAMS[tf]['rule'], df_m1=_M1) for tf in TF_PARAMS}


for tf, p in TF_PARAMS.items():
    df_train = split_train(_PREPARED[tf])
    configs = build_exit_configs(p['bar_size_min'], p['exit_ny_min'])
    m, _ = run_config(df_train, configs['C0_zscore_0.5'], p['bar_size_min'], p['timeout_bars'])
    ref = MINIVAL4[tf]
    assert m['trades'] == ref['trades'], (
        f"C0 {tf} : {m['trades']} trades vs mini-val #4 {ref['trades']} — HARNESS DIVERGÉ")
    # 2% : marge float, tolérance intentionnelle — tout écart > 0 doit être investigué
    assert abs(m['pf'] - ref['pf']) / ref['pf'] < 0.02, (
        f"C0 {tf} : PF {m['pf']:.4f} vs mini-val #4 {ref['pf']} — HARNESS DIVERGÉ")
    print(f"C0 {tf} OK : {m['trades']} trades, PF {m['pf']:.4f} (réf {ref['pf']})")

# %% [markdown]
# ## Grille complète — 8 configs × 2 TF (16 trials)
#
# Chaque config backtestée sur Train. Gate de promotion : PF > 1.5 ET Sharpe > 1.0 ET
# avg_trade > coût round-trip, sur Train Apex-compliant. Les configs qui passent le gate
# Train sont re-backtestées sur Valid (walk-forward).

# %%
N_TRIALS = 0
rows = []
trades_by_key = {}

for tf, p in TF_PARAMS.items():
    df_train = split_train(_PREPARED[tf])
    df_valid = split_valid(_PREPARED[tf])
    configs = build_exit_configs(p['bar_size_min'], p['exit_ny_min'])
    for name, exit_logic in configs.items():
        N_TRIALS += 1
        m_tr, tr_tr = run_config(df_train, exit_logic, p['bar_size_min'], p['timeout_bars'])
        gate_train = (m_tr['pf'] > 1.5 and m_tr['sharpe'] > 1.0
                      and m_tr['avg_trade'] > RT_COST)
        row = {
            'config': name, 'tf': tf,
            'train_trades': m_tr['trades'], 'train_pf': m_tr['pf'],
            'train_sharpe': m_tr['sharpe'], 'train_max_dd': m_tr['max_dd'],
            'train_wr': m_tr['wr'], 'train_pnl': m_tr['pnl'],
            'train_avg_trade': m_tr['avg_trade'], 'gate_train': gate_train,
        }
        trades_by_key[(name, tf, 'train')] = tr_tr
        if gate_train:
            m_va, tr_va = run_config(df_valid, exit_logic, p['bar_size_min'], p['timeout_bars'])
            row.update({
                'valid_trades': m_va['trades'], 'valid_pf': m_va['pf'],
                'valid_sharpe': m_va['sharpe'], 'valid_max_dd': m_va['max_dd'],
                'valid_wr': m_va['wr'], 'valid_pnl': m_va['pnl'],
                'valid_avg_trade': m_va['avg_trade'],
                'promoted': (m_va['pf'] >= 1.3 and m_va['sharpe'] > 0),
            })
            trades_by_key[(name, tf, 'valid')] = tr_va
        else:
            row.update({
                'valid_trades': None, 'valid_pf': None, 'valid_sharpe': None,
                'valid_max_dd': None, 'valid_wr': None, 'valid_pnl': None,
                'valid_avg_trade': None, 'promoted': False,
            })
        rows.append(row)
        print(f"{name:18} {tf:5} | Train PF {m_tr['pf']:.2f} Sharpe {m_tr['sharpe']:+.2f} "
              f"avg ${m_tr['avg_trade']:+.2f} | gate={gate_train} promoted={row['promoted']}")

ranking = pd.DataFrame(rows).sort_values(
    ['promoted', 'train_pf'], ascending=[False, False]).reset_index(drop=True)
ranking.to_csv(OUT_DIR / 'ranking.csv', index=False)
print(f"\nn_trials = {N_TRIALS} | ranking.csv écrit ({len(ranking)} lignes)")
