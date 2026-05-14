"""
run_grid_screen_apex.py — Grid screen exploratoire Apex-compliant.

Scope : 3 instruments (MNQ, NQ, ES) x 3 signaux (MR Z, RSI extreme, ORB) x 2 TF (5min, 15min)
      = 18 configurations testees en Apex-compliant strict (force-flat 15:59, no entry apres 15:55,
        daily $1K hard-stop, trailing DD $2K hard-stop, 1 contrat fixe).

Pour chaque config : backtest Train + Valid + simulation cycle Apex (60 mois).
Output : grid_results.csv + grid_results.md (recap markdown).

Duree estimee : 30-45 min selon la machine.
"""
from __future__ import annotations
import matplotlib
matplotlib.use('Agg')

import traceback
import time
from pathlib import Path
from typing import Optional, Callable

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

pd.set_option('display.max_rows', 80)
pd.set_option('display.float_format', '{:.4f}'.format)
pd.set_option('display.max_columns', 20)
pd.set_option('display.width', 200)

OUT_DIR = Path('01_research/outputs/grid_screen')
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Splits Lopez de Prado ────────────────────────────────────────────
TRAIN_START   = pd.Timestamp('2021-05-13', tz='UTC')
TRAIN_END     = pd.Timestamp('2024-05-13', tz='UTC')
VALID_START   = TRAIN_END
VALID_END     = pd.Timestamp('2025-05-13', tz='UTC')
HOLDOUT_START = VALID_END
HOLDOUT_END   = pd.Timestamp('2026-05-13', tz='UTC')

# ── Contraintes Apex Eval $50K ───────────────────────────────────────
APEX_CAPITAL       = 50_000
APEX_PROFIT_TARGET = 3_000
APEX_TRAILING_DD   = 2_000
APEX_DAILY_LIMIT   = 1_000
ENTRY_CUTOFF_NY_MIN = 15 * 60 + 55   # 15:55 NY
EXIT_FORCE_NY_MIN   = 15 * 60 + 59   # 15:59 NY

# ── Specs instruments ────────────────────────────────────────────────
INSTRUMENTS = {
    'MNQ': {
        'path': r'C:\Users\ryadb\Downloads\MNQ 5ANS DATA\glbx-mdp3-20210513-20260512.ohlcv-1m.csv.zst',
        'root': 'MNQ',
        'point_value': 2.00,
        'tick_size':   0.25,
        'commission_rt': 1.10,
        'max_contracts': 40,
        'sl_floor_pts': 5.0,    # SL minimum en points
        'sl_cap_pts':   10.0,
    },
    'NQ': {
        'path': r'NQ 5ANS DATA\glbx-mdp3-20210513-20260512.ohlcv-1m.csv.zst',
        'root': 'NQ',
        'point_value': 20.00,
        'tick_size':   0.25,
        'commission_rt': 4.50,
        'max_contracts': 10,
        'sl_floor_pts': 5.0,
        'sl_cap_pts':   10.0,
    },
    'ES': {
        'path': r'ES 5ANS DATA\glbx-mdp3-20210513-20260512.ohlcv-1m.csv.zst',
        'root': 'ES',
        'point_value': 50.00,
        'tick_size':   0.25,
        'commission_rt': 4.50,
        'max_contracts': 10,
        'sl_floor_pts': 1.0,    # ES bouge ~3x moins en pts qu'NQ
        'sl_cap_pts':   2.0,
    },
}


# ════════════════════════════════════════════════════════════════════
# LOADERS
# ════════════════════════════════════════════════════════════════════

def load_continuous(path, root):
    """Charge un fichier Databento .csv.zst, filtre par symbol root, exclut spreads et rollover."""
    df = pd.read_csv(path, usecols=['ts_event','open','high','low','close','volume','symbol'])
    df = df[df['symbol'].str.startswith(root) & ~df['symbol'].str.contains('-', na=False)].copy()
    df = df.sort_values('volume', ascending=False).groupby('ts_event', sort=False).first().reset_index()
    df['bar'] = pd.to_datetime(df['ts_event'], utc=True)
    df[['open','high','low','close']] = df[['open','high','low','close']].astype(float)
    df['volume'] = df['volume'].fillna(0).astype(int)
    df.sort_values('bar', inplace=True)
    df.drop_duplicates(subset=['bar'], inplace=True)
    df.reset_index(drop=True, inplace=True)
    df['date'] = df['bar'].dt.date
    day_sym = df.groupby('date').apply(
        lambda g: g.loc[g['volume'].idxmax(), 'symbol'] if len(g) > 0 else None,
        include_groups=False).reset_index()
    day_sym.columns = ['date','dominant']
    day_sym['prev'] = day_sym['dominant'].shift(1)
    day_sym['roll'] = (day_sym['dominant'] != day_sym['prev']) & day_sym['prev'].notna()
    day_sym['roll'] = (day_sym['roll'] | day_sym['roll'].shift(-1)).fillna(False).astype(bool)
    roll_dates = set(day_sym.loc[day_sym['roll'], 'date'].astype(str))
    df['is_roll'] = df['date'].astype(str).isin(roll_dates)
    df = df[~df['is_roll']].drop(columns=['is_roll','symbol']).reset_index(drop=True)
    df = df.set_index('bar').sort_index()
    return df[['open','high','low','close','volume']]


def resample_ohlcv(df, rule):
    out = df.resample(rule).agg({
        'open': 'first', 'high': 'max', 'low': 'min',
        'close': 'last', 'volume': 'sum'
    }).dropna(subset=['close'])
    return out


def add_temporal_columns(df):
    out = df.copy()
    out['ts_ny']   = out.index.tz_convert('America/New_York')
    out['hour_ny'] = out['ts_ny'].dt.hour
    out['min_ny']  = out['ts_ny'].dt.minute
    out['month']   = out.index.month
    out['dow']     = out.index.dayofweek
    out['date']    = out.index.date
    return out


def filter_session_ny(df):
    t_ny = df['hour_ny'] * 60 + df['min_ny']
    return df[(t_ny >= 9*60+30) & (t_ny < 16*60)].copy()


# ════════════════════════════════════════════════════════════════════
# SIGNAUX
# ════════════════════════════════════════════════════════════════════

def add_features_mr_zscore(df, lookback=20):
    """MR Z-score : entry quand |z|>2, exit quand z dans [-0.5, +0.5]."""
    out = df.copy()
    closes = out['close']
    out['mid']    = closes.rolling(lookback).mean()
    out['std']    = closes.rolling(lookback).std(ddof=0)
    out['zscore'] = (closes - out['mid']) / out['std'].replace(0, np.nan)
    return out


def signal_mr_zscore(df, entry_threshold=2.0, bar_size_min=1):
    """Signaux MR Z-score Apex-compliant (entry cutoff applique)."""
    out = df.copy()
    out['signal'] = 0
    close_min_ny = out['hour_ny'] * 60 + out['min_ny'] + bar_size_min
    valid = out['zscore'].notna() & out['std'].notna() & (out['std'] > 0) & (close_min_ny <= ENTRY_CUTOFF_NY_MIN)
    out.loc[valid & (out['zscore'] >  entry_threshold), 'signal'] = -1   # SHORT
    out.loc[valid & (out['zscore'] < -entry_threshold), 'signal'] = +1   # LONG
    return out


def add_features_rsi(df, period=14):
    """RSI standard."""
    out = df.copy()
    close = out['close']
    delta = close.diff()
    gain  = delta.where(delta > 0, 0.0).rolling(period).mean()
    loss  = (-delta.where(delta < 0, 0.0)).rolling(period).mean()
    rs    = gain / loss.replace(0, np.nan)
    out['rsi'] = 100 - (100 / (1 + rs))
    # std lookback pour SL (même que MR Z-score)
    out['std'] = close.rolling(20).std(ddof=0)
    out['mid'] = close.rolling(20).mean()
    return out


def signal_rsi_extreme(df, low_threshold=30, high_threshold=70, bar_size_min=1):
    """Signaux RSI extreme : LONG si RSI<30, SHORT si RSI>70."""
    out = df.copy()
    out['signal'] = 0
    close_min_ny = out['hour_ny'] * 60 + out['min_ny'] + bar_size_min
    valid = out['rsi'].notna() & out['std'].notna() & (out['std'] > 0) & (close_min_ny <= ENTRY_CUTOFF_NY_MIN)
    out.loc[valid & (out['rsi'] < low_threshold), 'signal']  = +1   # LONG (oversold)
    out.loc[valid & (out['rsi'] > high_threshold), 'signal'] = -1   # SHORT (overbought)
    return out


def add_features_orb(df, or_minutes=30, bar_size_min=1):
    """ORB : Opening Range = bars dans les 'or_minutes' premieres min de session.

    Pour chaque jour, calcule or_high = max(high) sur OR, or_low = min(low) sur OR.
    Genere des features or_high/or_low/or_range disponibles a partir de la 1ere bar APRES l'OR.
    """
    out = df.copy()
    # Marque les bars dans l'OR : close_min_ny <= 9:30 + or_minutes
    close_min_ny = out['hour_ny'] * 60 + out['min_ny'] + bar_size_min
    or_end = 9 * 60 + 30 + or_minutes
    out['in_or'] = (close_min_ny > 9*60+30) & (close_min_ny <= or_end)
    # Pour chaque jour, calculer or_high/or_low (max/min sur les bars de l'OR uniquement)
    daily_or = out[out['in_or']].groupby('date').agg(or_high=('high','max'), or_low=('low','min'))
    daily_or['or_range'] = daily_or['or_high'] - daily_or['or_low']
    # Merge back
    out = out.reset_index().merge(daily_or, on='date', how='left').set_index('bar')
    # Bars apres l'OR uniquement (= close_min_ny > or_end)
    out['post_or'] = close_min_ny > or_end
    # std for SL
    out['std'] = out['close'].rolling(20).std(ddof=0)
    out['mid'] = out['close'].rolling(20).mean()
    return out


def signal_orb(df, bar_size_min=1):
    """Signaux ORB : LONG si close break or_high, SHORT si close break or_low. Apex-compliant.

    Une entry par jour par direction max (handled implicitly by cooldown post-exit in backtest).
    """
    out = df.copy()
    out['signal'] = 0
    close_min_ny = out['hour_ny'] * 60 + out['min_ny'] + bar_size_min
    valid = out['post_or'] & out['or_high'].notna() & out['or_low'].notna() & (close_min_ny <= ENTRY_CUTOFF_NY_MIN)
    out.loc[valid & (out['close'] > out['or_high']), 'signal'] = +1   # LONG breakout
    out.loc[valid & (out['close'] < out['or_low']),  'signal'] = -1   # SHORT breakdown
    return out


# ════════════════════════════════════════════════════════════════════
# BACKTEST GENERIQUE APEX-COMPLIANT
# ════════════════════════════════════════════════════════════════════

def backtest_apex(df_signals, exit_logic, instrument_specs, bar_size_min, timeout_bars,
                  contracts=1, slippage_ticks=1):
    """Backtest event-driven Apex-compliant.

    exit_logic : callable(df, i, j, direction, entry_price, std_i, mid_i, or_data, sl_pts)
                 -> (tp_touched: bool, tp_price: float, exit_reason: str)
                 retourne True si TP/exit-condition touche sur bar j, sinon False.
    """
    df = df_signals.reset_index().copy()
    n  = len(df)
    trades = []
    i = 0
    tick_size = instrument_specs['tick_size']
    point_value = instrument_specs['point_value']
    commission_rt = instrument_specs['commission_rt']
    sl_floor = instrument_specs['sl_floor_pts']
    sl_cap   = instrument_specs['sl_cap_pts']
    while i < n - 1:
        sig = df.at[i, 'signal']
        if sig == 0 or pd.isna(df.at[i, 'std']) or df.at[i, 'std'] <= 0:
            i += 1; continue
        direction = int(sig)
        entry_price = df.at[i, 'close']
        std_i = df.at[i, 'std']
        mid_i = df.at[i, 'mid'] if pd.notna(df.at[i, 'mid']) else entry_price
        # OR data si dispo
        or_high = df.at[i, 'or_high'] if 'or_high' in df.columns else np.nan
        or_low  = df.at[i, 'or_low']  if 'or_low'  in df.columns else np.nan
        or_range = df.at[i, 'or_range'] if 'or_range' in df.columns else np.nan
        # SL : 1.5 x std, bordé [floor, cap]
        sl_pts = max(sl_floor, min(sl_cap, 1.5 * std_i))
        sl_price = entry_price - direction * sl_pts
        slip_pts = slippage_ticks * tick_size
        result_pts = 0.0
        exit_reason = 'timeout'
        exit_idx = min(i + timeout_bars, n - 1)
        entry_date = df.at[i, 'date']
        for j in range(i + 1, min(n, i + timeout_bars + 1)):
            hj = df.at[j, 'high']; lj = df.at[j, 'low']
            # SL wick check (pessimiste)
            sl_touched = (direction == 1 and lj <= sl_price) or (direction == -1 and hj >= sl_price)
            if sl_touched:
                exit_price = sl_price - direction * slip_pts
                result_pts = direction * (exit_price - entry_price)
                exit_reason = 'SL'; exit_idx = j; break
            # Exit logic specifique au signal
            tp_touched, tp_price, tp_reason = exit_logic(df, i, j, direction, entry_price,
                                                         std_i, mid_i, or_high, or_low, or_range, sl_pts)
            if tp_touched:
                exit_price = tp_price
                result_pts = direction * (exit_price - entry_price)
                exit_reason = tp_reason; exit_idx = j; break
            # Apex force-flat 15:59 NY
            close_min_ny = df.at[j, 'hour_ny'] * 60 + df.at[j, 'min_ny'] + bar_size_min
            if df.at[j, 'date'] == entry_date and close_min_ny > EXIT_FORCE_NY_MIN:
                exit_price = df.at[j, 'close']
                result_pts = direction * (exit_price - entry_price)
                exit_reason = 'apex_force_flat'; exit_idx = j; break
        else:
            exit_price = df.at[exit_idx, 'close']
            result_pts = direction * (exit_price - entry_price)
        pnl_usd = result_pts * point_value * contracts - commission_rt * contracts
        trades.append({
            'entry_time': df.at[i, 'bar'], 'exit_time': df.at[exit_idx, 'bar'],
            'direction': 'LONG' if direction == 1 else 'SHORT',
            'entry_price': entry_price, 'exit_price': exit_price,
            'sl_pts': sl_pts, 'pts': result_pts, 'pnl_usd': pnl_usd,
            'exit_reason': exit_reason, 'bars_held': exit_idx - i,
            'hour_ny': df.at[i, 'hour_ny'], 'date': df.at[i, 'date'],
            'month': df.at[i, 'month'], 'dow': df.at[i, 'dow'],
        })
        i = exit_idx + 1
    return pd.DataFrame(trades)


# ════════════════════════════════════════════════════════════════════
# EXIT LOGICS PAR SIGNAL
# ════════════════════════════════════════════════════════════════════

def exit_logic_mr_zscore(df, i, j, direction, entry_price, std_i, mid_i, or_high, or_low, or_range, sl_pts):
    """TP MR : z revient dans [-0.5, +0.5]."""
    z_j = df.at[j, 'zscore'] if 'zscore' in df.columns else np.nan
    if pd.notna(z_j):
        tp = (direction == 1 and z_j >= -0.5) or (direction == -1 and z_j <= 0.5)
        if tp:
            return True, df.at[j, 'close'], 'TP_zscore'
    return False, 0.0, ''


def exit_logic_rsi(df, i, j, direction, entry_price, std_i, mid_i, or_high, or_low, or_range, sl_pts):
    """TP RSI : RSI revient vers 50."""
    rsi_j = df.at[j, 'rsi'] if 'rsi' in df.columns else np.nan
    if pd.notna(rsi_j):
        tp = (direction == 1 and rsi_j >= 50) or (direction == -1 and rsi_j <= 50)
        if tp:
            return True, df.at[j, 'close'], 'TP_rsi50'
    return False, 0.0, ''


def exit_logic_orb(df, i, j, direction, entry_price, std_i, mid_i, or_high, or_low, or_range, sl_pts):
    """TP ORB : 1x or_range au-dela de l'entry, ou wick haut/bas selon direction.

    LONG  : TP = entry + or_range (touche sur high[j])
    SHORT : TP = entry - or_range (touche sur low[j])
    """
    if pd.isna(or_range) or or_range <= 0:
        return False, 0.0, ''
    tp_price = entry_price + direction * or_range
    hj = df.at[j, 'high']; lj = df.at[j, 'low']
    tp_touched = (direction == 1 and hj >= tp_price) or (direction == -1 and lj <= tp_price)
    if tp_touched:
        return True, tp_price, 'TP_orb_1R'
    return False, 0.0, ''


# ════════════════════════════════════════════════════════════════════
# METRICS & APEX CYCLE
# ════════════════════════════════════════════════════════════════════

def compute_trade_metrics(trades):
    if len(trades) == 0:
        return dict(trades=0, pf=0.0, sharpe=0.0, max_dd=0.0, wr=0.0, pnl=0.0, avg_trade=0.0)
    pnl = trades['pnl_usd']
    pos = pnl[pnl > 0].sum(); neg = abs(pnl[pnl < 0].sum())
    pf = pos / neg if neg > 0 else np.inf
    wr = (pnl > 0).mean()
    eq = pnl.cumsum(); peak = eq.cummax(); dd = (eq - peak)
    max_dd = float(dd.min())
    sharpe = pnl.mean() / pnl.std() * np.sqrt(252) if pnl.std() > 0 else 0
    return dict(trades=len(trades), pf=pf, sharpe=sharpe, max_dd=max_dd,
                wr=wr, pnl=pnl.sum(), avg_trade=pnl.mean())


def simulate_apex_cycle(trades_df, target=APEX_PROFIT_TARGET, dd_limit=APEX_TRAILING_DD,
                        daily_limit=APEX_DAILY_LIMIT):
    if len(trades_df) == 0:
        return pd.DataFrame()
    trades_df = trades_df.sort_values('entry_time').copy()
    trades_df['ym'] = trades_df['entry_time'].dt.strftime('%Y-%m')
    months = sorted(trades_df['ym'].unique())
    results = []
    for ym in months:
        m_trades = trades_df[trades_df['ym'] == ym].copy()
        running_pnl = 0.0; hwm = 0.0; status = 'NO_TARGET'
        daily_pnl = {}; busted_today = set()
        trades_taken = 0
        for _, t in m_trades.iterrows():
            d = t['date']
            if d in busted_today: continue
            if status == 'BUSTED_DD': continue
            pnl = t['pnl_usd']
            running_pnl += pnl
            daily_pnl[d] = daily_pnl.get(d, 0.0) + pnl
            trades_taken += 1
            if running_pnl > hwm: hwm = running_pnl
            if (hwm - running_pnl) >= dd_limit:
                status = 'BUSTED_DD'; continue
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
# CONFIGS GRID
# ════════════════════════════════════════════════════════════════════

# (signal_name, add_features_fn, signal_fn, exit_logic_fn, feature_kwargs)
SIGNAUX = [
    ('mr_zscore', add_features_mr_zscore, signal_mr_zscore, exit_logic_mr_zscore, {'lookback': 20}),
    ('rsi_ext',   add_features_rsi,       signal_rsi_extreme, exit_logic_rsi,    {'period': 14}),
    ('orb',       add_features_orb,       signal_orb,        exit_logic_orb,    {'or_minutes': 30}),
]

# (tf_str, resample_rule, bar_size_min, timeout_bars)
TFS = [
    ('5min',  '5min',  5,  12),    # timeout 1h
    ('15min', '15min', 15, 4),     # timeout 1h
]


# ════════════════════════════════════════════════════════════════════
# MAIN LOOP
# ════════════════════════════════════════════════════════════════════

def main():
    grid_results = []

    for inst_name, specs in INSTRUMENTS.items():
        print('=' * 70)
        print(f'### CHARGEMENT {inst_name} ###')
        print('=' * 70)
        t0 = time.time()
        try:
            df_raw = load_continuous(specs['path'], specs['root'])
        except Exception as e:
            print(f'[ERROR LOAD {inst_name}] {type(e).__name__}: {e}')
            continue
        print(f'{inst_name} bars chargees : {len(df_raw):,} en {time.time()-t0:.1f}s')

        for tf_str, resample_rule, bar_size_min, timeout_bars in TFS:
            print(f'\n  Resample -> {tf_str}...')
            df_tf = resample_ohlcv(df_raw, resample_rule)
            df_tf = add_temporal_columns(df_tf)
            df_tf_sess = filter_session_ny(df_tf)
            print(f'  Bars {inst_name} {tf_str} session NY : {len(df_tf_sess):,}')

            for sig_name, add_feat_fn, sig_fn, exit_fn, feat_kwargs in SIGNAUX:
                t1 = time.time()
                print(f'\n  >> {inst_name} | {sig_name} | {tf_str}')
                # Features
                feat_kwargs_runtime = dict(feat_kwargs)
                if sig_name == 'orb':
                    feat_kwargs_runtime['bar_size_min'] = bar_size_min
                df_feat = add_feat_fn(df_tf_sess, **feat_kwargs_runtime)
                # Signaux
                df_sig = sig_fn(df_feat, bar_size_min=bar_size_min)
                n_sig = (df_sig['signal'] != 0).sum()
                # Splits
                df_train = df_sig.loc[(df_sig.index >= TRAIN_START) & (df_sig.index < TRAIN_END)].copy()
                df_valid = df_sig.loc[(df_sig.index >= VALID_START) & (df_sig.index < VALID_END)].copy()
                # Backtests
                trades_train = backtest_apex(df_train, exit_fn, specs, bar_size_min, timeout_bars)
                trades_valid = backtest_apex(df_valid, exit_fn, specs, bar_size_min, timeout_bars)
                m_train = compute_trade_metrics(trades_train)
                m_valid = compute_trade_metrics(trades_valid)
                # Apex cycle sur Train+Valid combine (5 ans = 60 mois)
                all_trades = pd.concat([trades_train, trades_valid], ignore_index=True)
                cycle = simulate_apex_cycle(all_trades)
                if len(cycle) > 0:
                    pass_rate = (cycle['status'] == 'PASSED').mean() * 100
                    bust_rate = (cycle['status'] == 'BUSTED_DD').mean() * 100
                    no_target = (cycle['status'] == 'NO_TARGET').mean() * 100
                    avg_pnl_month = cycle['final_pnl'].mean()
                    n_months = len(cycle)
                else:
                    pass_rate = bust_rate = no_target = 0.0
                    avg_pnl_month = 0.0
                    n_months = 0
                # Save trades + cycle CSV
                tag = f'{inst_name}_{sig_name}_{tf_str}'
                if len(all_trades) > 0:
                    all_trades.to_csv(OUT_DIR / f'trades_{tag}.csv', index=False)
                if len(cycle) > 0:
                    cycle.to_csv(OUT_DIR / f'apex_cycle_{tag}.csv', index=False)
                # Log
                print(f'     signaux={n_sig} | Train trades={m_train["trades"]} PF={m_train["pf"]:.2f} Sharpe={m_train["sharpe"]:.2f}')
                print(f'     Valid trades={m_valid["trades"]} PF={m_valid["pf"]:.2f} Sharpe={m_valid["sharpe"]:.2f}')
                print(f'     Apex cycle ({n_months} mois): PASSED {pass_rate:.1f}% | BUSTED_DD {bust_rate:.1f}% | NO_TARGET {no_target:.1f}% | PnL/mois ${avg_pnl_month:.0f}')
                print(f'     Duree : {time.time()-t1:.1f}s')

                grid_results.append({
                    'instrument': inst_name,
                    'signal': sig_name,
                    'tf': tf_str,
                    'n_signals': n_sig,
                    'train_trades': m_train['trades'],
                    'train_pf': m_train['pf'],
                    'train_sharpe': m_train['sharpe'],
                    'train_max_dd': m_train['max_dd'],
                    'train_wr': m_train['wr'],
                    'train_pnl': m_train['pnl'],
                    'valid_trades': m_valid['trades'],
                    'valid_pf': m_valid['pf'],
                    'valid_sharpe': m_valid['sharpe'],
                    'valid_max_dd': m_valid['max_dd'],
                    'valid_wr': m_valid['wr'],
                    'valid_pnl': m_valid['pnl'],
                    'apex_months': n_months,
                    'apex_pass_rate': pass_rate,
                    'apex_bust_rate': bust_rate,
                    'apex_no_target_rate': no_target,
                    'apex_avg_pnl_month': avg_pnl_month,
                })

    # ─── Tableau recapitulatif final ───
    print()
    print('=' * 70)
    print('### TABLEAU RECAPITULATIF FINAL — GRID SCREEN APEX ###')
    print('=' * 70)
    grid_df = pd.DataFrame(grid_results)
    if len(grid_df) > 0:
        grid_df.to_csv(OUT_DIR / 'grid_results.csv', index=False)
        # Trier par apex_pass_rate desc, puis valid_sharpe desc
        grid_df_sorted = grid_df.sort_values(['apex_pass_rate', 'valid_sharpe'], ascending=[False, False])
        cols_print = ['instrument', 'signal', 'tf', 'train_trades', 'train_pf', 'train_sharpe',
                      'valid_trades', 'valid_pf', 'valid_sharpe', 'apex_pass_rate', 'apex_avg_pnl_month']
        print()
        print(grid_df_sorted[cols_print].to_string(index=False))
        print()
        # Highlight les configs qui passent au moins 1 mois sur 60
        promising = grid_df_sorted[grid_df_sorted['apex_pass_rate'] > 0]
        if len(promising) > 0:
            print(f'\n[!] Configs avec pass_rate > 0 : {len(promising)}')
            print(promising[cols_print].to_string(index=False))
        else:
            print('\n[!] AUCUNE config ne passe Apex (pass_rate 0% partout)')

    print()
    print('=' * 70)
    print('### FIN GRID SCREEN ###')
    print('=' * 70)
    print(f'Fichiers dans {OUT_DIR}/ :')
    for p in sorted(OUT_DIR.iterdir()):
        print(f'  - {p.name}')


if __name__ == '__main__':
    main()
