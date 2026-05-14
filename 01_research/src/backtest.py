"""Backtester event-driven Apex-compliant + simulation cycle Apex 1-mois.

NOTE : ce backtester reste 'close-only' sur le check TP indicateur (z-score, RSI).
Le SL est vérifié sur wicks high/low (correct). Pour une validation 100% tick-realistic
(TP wick-aware), un nouveau backtester sera écrit dans 02_validation/src/.
"""
from __future__ import annotations
from typing import Callable

import numpy as np
import pandas as pd

from .config import (APEX_PROFIT_TARGET, APEX_TRAILING_DD, APEX_DAILY_LIMIT,
                     EXIT_FORCE_NY_MIN)


def backtest_apex(df_signals: pd.DataFrame,
                  exit_logic: Callable,
                  instrument_specs: dict,
                  bar_size_min: int,
                  timeout_bars: int,
                  contracts: int = 1,
                  slippage_ticks: int = 1,
                  apex_constraints: bool = True,
                  exit_force_ny_min: int = EXIT_FORCE_NY_MIN) -> pd.DataFrame:
    """Backtest event-driven générique Apex-compliant.

    SL : entry +/- max(floor, min(cap, 1.5 * std)) — WICK check (low/high de chaque bar).
    Exit-logic spécifique au signal : callable retournant (tp_touched, tp_price, exit_reason).
    Apex constraint : force-flat MTM au close <= exit_force_ny_min (15:59 NY default).

    Args:
        df_signals: DataFrame avec colonnes ['signal', 'close', 'high', 'low', 'std', 'mid',
                                              'hour_ny', 'min_ny', 'date', 'month', 'dow'].
        exit_logic: callable(df, i, j, direction, entry_price, std_i, mid_i,
                              or_high, or_low, or_range, sl_pts)
                    -> (bool, float, str)
        instrument_specs: dict de instruments.INSTRUMENTS[name].
        bar_size_min: taille bar en min (5 pour 5min, 15 pour 15min, etc.).
        timeout_bars: liquidation MTM après N bars si ni SL ni TP touché.
        contracts: nombre de contrats fixe par trade (sizing externe).
        slippage_ticks: ticks défavorables au touche SL.
        apex_constraints: active force-flat 15:59 NY si True.

    Returns:
        DataFrame de trades avec colonnes
        [entry_time, exit_time, direction, entry_price, exit_price, sl_pts, pts,
         pnl_usd, exit_reason, bars_held, hour_ny, date, month, dow].
    """
    df = df_signals.reset_index().copy()
    n = len(df)
    trades = []
    i = 0
    tick_size = instrument_specs['tick_size']
    point_value = instrument_specs['point_value']
    commission_rt = instrument_specs['commission_rt']
    sl_floor = instrument_specs['sl_floor_pts']
    sl_cap = instrument_specs['sl_cap_pts']
    while i < n - 1:
        sig = df.at[i, 'signal']
        if sig == 0 or pd.isna(df.at[i, 'std']) or df.at[i, 'std'] <= 0:
            i += 1
            continue
        direction = int(sig)
        entry_price = df.at[i, 'close']
        std_i = df.at[i, 'std']
        mid_i = df.at[i, 'mid'] if pd.notna(df.at[i, 'mid']) else entry_price
        or_high = df.at[i, 'or_high'] if 'or_high' in df.columns else np.nan
        or_low = df.at[i, 'or_low'] if 'or_low' in df.columns else np.nan
        or_range = df.at[i, 'or_range'] if 'or_range' in df.columns else np.nan
        sl_pts = max(sl_floor, min(sl_cap, 1.5 * std_i))
        sl_price = entry_price - direction * sl_pts
        slip_pts = slippage_ticks * tick_size
        result_pts = 0.0
        exit_reason = 'timeout'
        exit_idx = min(i + timeout_bars, n - 1)
        entry_date = df.at[i, 'date']
        for j in range(i + 1, min(n, i + timeout_bars + 1)):
            hj = df.at[j, 'high']
            lj = df.at[j, 'low']
            sl_touched = (direction == 1 and lj <= sl_price) or (direction == -1 and hj >= sl_price)
            if sl_touched:
                exit_price = sl_price - direction * slip_pts
                result_pts = direction * (exit_price - entry_price)
                exit_reason = 'SL'
                exit_idx = j
                break
            tp_touched, tp_price, tp_reason = exit_logic(
                df, i, j, direction, entry_price, std_i, mid_i,
                or_high, or_low, or_range, sl_pts,
            )
            if tp_touched:
                exit_price = tp_price
                result_pts = direction * (exit_price - entry_price)
                exit_reason = tp_reason
                exit_idx = j
                break
            if apex_constraints:
                close_min_ny = df.at[j, 'hour_ny'] * 60 + df.at[j, 'min_ny'] + bar_size_min
                if df.at[j, 'date'] == entry_date and close_min_ny > exit_force_ny_min:
                    exit_price = df.at[j, 'close']
                    result_pts = direction * (exit_price - entry_price)
                    exit_reason = 'apex_force_flat'
                    exit_idx = j
                    break
        else:
            exit_price = df.at[exit_idx, 'close']
            result_pts = direction * (exit_price - entry_price)
        pnl_usd = result_pts * point_value * contracts - commission_rt * contracts
        trades.append({
            'entry_time': df.at[i, 'bar'],
            'exit_time': df.at[exit_idx, 'bar'],
            'direction': 'LONG' if direction == 1 else 'SHORT',
            'entry_price': entry_price,
            'exit_price': exit_price,
            'sl_pts': sl_pts,
            'pts': result_pts,
            'pnl_usd': pnl_usd,
            'exit_reason': exit_reason,
            'bars_held': exit_idx - i,
            'hour_ny': df.at[i, 'hour_ny'],
            'date': df.at[i, 'date'],
            'month': df.at[i, 'month'],
            'dow': df.at[i, 'dow'],
        })
        i = exit_idx + 1
    return pd.DataFrame(trades)


def compute_trade_metrics(trades: pd.DataFrame) -> dict:
    """Métriques agrégées d'un ensemble de trades.

    Returns dict avec : trades, pf, sharpe (annualisé sqrt(252)), max_dd ($), wr, pnl, avg_trade.
    """
    if len(trades) == 0:
        return dict(trades=0, pf=0.0, sharpe=0.0, max_dd=0.0, wr=0.0, pnl=0.0, avg_trade=0.0)
    pnl = trades['pnl_usd']
    pos = pnl[pnl > 0].sum()
    neg = abs(pnl[pnl < 0].sum())
    pf = pos / neg if neg > 0 else np.inf
    wr = (pnl > 0).mean()
    eq = pnl.cumsum()
    peak = eq.cummax()
    dd = (eq - peak)
    max_dd = float(dd.min())
    sharpe = pnl.mean() / pnl.std() * np.sqrt(252) if pnl.std() > 0 else 0
    return dict(
        trades=len(trades), pf=pf, sharpe=sharpe, max_dd=max_dd,
        wr=wr, pnl=pnl.sum(), avg_trade=pnl.mean(),
    )


def simulate_apex_cycle(trades_df: pd.DataFrame,
                        target: float = APEX_PROFIT_TARGET,
                        dd_limit: float = APEX_TRAILING_DD,
                        daily_limit: float = APEX_DAILY_LIMIT) -> pd.DataFrame:
    """Simule un challenge Apex Eval 1-mois indépendant pour chaque mois calendaire.

    Pour chaque mois :
        - running_pnl démarre à 0, hwm à 0
        - applique daily limit (skip jour si daily_pnl <= -daily_limit)
        - applique trailing DD (BUSTED_DD si hwm - running_pnl >= dd_limit)
        - applique target ($3K) : PASSED dès qu'atteint

    Returns:
        DataFrame avec colonnes [month, status, final_pnl, hwm, trades_taken].
        status ∈ {'PASSED', 'BUSTED_DD', 'NO_TARGET'}.
    """
    if len(trades_df) == 0:
        return pd.DataFrame()
    trades_df = trades_df.sort_values('entry_time').copy()
    trades_df['ym'] = trades_df['entry_time'].dt.strftime('%Y-%m')
    months = sorted(trades_df['ym'].unique())
    results = []
    for ym in months:
        m_trades = trades_df[trades_df['ym'] == ym].copy()
        running_pnl = 0.0
        hwm = 0.0
        status = 'NO_TARGET'
        daily_pnl: dict = {}
        busted_today: set = set()
        trades_taken = 0
        for _, t in m_trades.iterrows():
            d = t['date']
            if d in busted_today:
                continue
            if status == 'BUSTED_DD':
                continue
            pnl = t['pnl_usd']
            running_pnl += pnl
            daily_pnl[d] = daily_pnl.get(d, 0.0) + pnl
            trades_taken += 1
            if running_pnl > hwm:
                hwm = running_pnl
            if (hwm - running_pnl) >= dd_limit:
                status = 'BUSTED_DD'
                continue
            if running_pnl >= target and status == 'NO_TARGET':
                status = 'PASSED'
            if daily_pnl[d] <= -daily_limit:
                busted_today.add(d)
        results.append({
            'month': ym, 'status': status, 'final_pnl': running_pnl, 'hwm': hwm,
            'trades_taken': trades_taken,
        })
    return pd.DataFrame(results)


# ════════════════════════════════════════════════════════════════════
# Exit logics par famille de signal
# ════════════════════════════════════════════════════════════════════

def exit_logic_mr_zscore(df, i, j, direction, entry_price, std_i, mid_i,
                         or_high, or_low, or_range, sl_pts,
                         zscore_exit: float = 0.5):
    """TP MR : z revient dans [-zscore_exit, +zscore_exit]."""
    z_j = df.at[j, 'zscore'] if 'zscore' in df.columns else np.nan
    if pd.notna(z_j):
        tp = (direction == 1 and z_j >= -zscore_exit) or (direction == -1 and z_j <= zscore_exit)
        if tp:
            return True, df.at[j, 'close'], 'TP_zscore'
    return False, 0.0, ''


def exit_logic_rsi(df, i, j, direction, entry_price, std_i, mid_i,
                   or_high, or_low, or_range, sl_pts,
                   rsi_exit: float = 50):
    """TP RSI : RSI revient vers mid (50)."""
    rsi_j = df.at[j, 'rsi'] if 'rsi' in df.columns else np.nan
    if pd.notna(rsi_j):
        tp = (direction == 1 and rsi_j >= rsi_exit) or (direction == -1 and rsi_j <= rsi_exit)
        if tp:
            return True, df.at[j, 'close'], 'TP_rsi50'
    return False, 0.0, ''


def exit_logic_orb(df, i, j, direction, entry_price, std_i, mid_i,
                   or_high, or_low, or_range, sl_pts):
    """TP ORB : 1× or_range au-delà de l'entry (wick check)."""
    if pd.isna(or_range) or or_range <= 0:
        return False, 0.0, ''
    tp_price = entry_price + direction * or_range
    hj = df.at[j, 'high']
    lj = df.at[j, 'low']
    tp_touched = (direction == 1 and hj >= tp_price) or (direction == -1 and lj <= tp_price)
    if tp_touched:
        return True, tp_price, 'TP_orb_1R'
    return False, 0.0, ''


def exit_logic_fixed_tp_std(df, i, j, direction, entry_price, std_i, mid_i,
                            or_high, or_low, or_range, sl_pts,
                            tp_std_mult: float = 0.75):
    """TP fixe : entry +/- tp_std_mult * std_i, vérifié sur wicks (high/low).

    TP de type limit order : fill au prix exact, pas de slippage (cf. exit_logic_orb).
    Configs C3 (tp_std_mult=0.75) et C4 (0.40) du sprint re-engineering exit.
    """
    tp_price = entry_price + direction * tp_std_mult * std_i
    hj = df.at[j, 'high']
    lj = df.at[j, 'low']
    tp_touched = (direction == 1 and hj >= tp_price) or (direction == -1 and lj <= tp_price)
    if tp_touched:
        return True, tp_price, 'TP_fixed_std'
    return False, 0.0, ''


def exit_logic_time_stop(df, i, j, direction, entry_price, std_i, mid_i,
                         or_high, or_low, or_range, sl_pts,
                         exit_ny_min: int = 955, bar_size_min: int = 5):
    """Exit temps fixe : flat MTM au close de la 1ère barre dont close >= exit_ny_min NY.

    exit_ny_min est calibré une barre avant le force-flat Apex (959) :
    5min -> 955 (barre 15:50->15:55), 15min -> 945 (barre 15:30->15:45).
    Ignore le z-score : teste si le drift entrée->close paie seul. Config C5 du sprint.
    """
    close_min_ny = df.at[j, 'hour_ny'] * 60 + df.at[j, 'min_ny'] + bar_size_min
    if close_min_ny >= exit_ny_min:
        return True, df.at[j, 'close'], 'time_stop'
    return False, 0.0, ''


def exit_logic_trailing_std(df, i, j, direction, entry_price, std_i, mid_i,
                            or_high, or_low, or_range, sl_pts,
                            **kwargs):
    """Stub — Task 4. Pas encore implémenté."""
    raise NotImplementedError("exit_logic_trailing_std: Task 4 non encore implémentée")


def exit_logic_hybrid_zscore_time(df, i, j, direction, entry_price, std_i, mid_i,
                                  or_high, or_low, or_range, sl_pts,
                                  **kwargs):
    """Stub — Task 5. Pas encore implémenté."""
    raise NotImplementedError("exit_logic_hybrid_zscore_time: Task 5 non encore implémentée")
