"""
run_exploration_MOMENTUM_MNQ.py — Test stratégie MOMENTUM minimaliste sur MNQ M1.

Mini-validation #3 : si MNQ M1 a H~0.62 (persistant), la stratégie inverse de MR
— le momentum — devrait avoir un edge. Test : breakout/breakdown 20 bars + trail stop.

Spec :
- LONG  : close[i] > rolling_max(close, N=20)[i-1]   (breakout au-dessus du max des 20 dernières)
- SHORT : close[i] < rolling_min(close, N=20)[i-1]   (breakdown sous le min des 20 dernières)
- SL hard : entry ± 2 × std_lookback(20) GELÉ à l'entrée — wick check
- Trail stop : max/min favorable ± 1 × std_lookback DYNAMIQUE (recalculé chaque barre)
  - LONG  : trail_stop_j = max(highs[i:j+1]) - 1 × std_j
  - SHORT : trail_stop_j = min(lows[i:j+1])  + 1 × std_j
- Timeout 60 bars
- 1 contrat MNQ fixe, slippage 1 tick au SL/trail, commission $1.10 RT
- Tests par heure NY sur Train 2021-2024

Outputs : 01_research/outputs/momentum/
"""
from __future__ import annotations
import matplotlib
matplotlib.use('Agg')

import traceback
import time
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

pd.set_option('display.max_rows', 50)
pd.set_option('display.float_format', '{:.4f}'.format)

CSV_PATH = Path(r'C:\Users\ryadb\Downloads\MNQ 5ANS DATA\glbx-mdp3-20210513-20260512.ohlcv-1m.csv.zst')
OUT_DIR  = Path('01_research/outputs/momentum')
OUT_DIR.mkdir(parents=True, exist_ok=True)

TRAIN_START   = pd.Timestamp('2021-05-13', tz='UTC')
TRAIN_END     = pd.Timestamp('2024-05-13', tz='UTC')
VALID_START   = TRAIN_END
VALID_END     = pd.Timestamp('2025-05-13', tz='UTC')

COMMISSION_RT   = 1.10
SLIPPAGE_TICKS  = 1
POINT_VALUE_MNQ = 2.00
TICK_SIZE_MNQ   = 0.25

# Signal momentum
BREAKOUT_LOOKBACK = 20         # max/min des 20 dernières bars
STOP_LOOKBACK     = 20         # std lookback (= breakout lookback)
SL_STD_MULT       = 2.0        # SL hard = 2 × std
TRAIL_STD_MULT    = 1.0        # trail stop = 1 × std en arrière du max/min
TIMEOUT_BARS      = 60

# SL plafonds (raisonnables MNQ)
SL_FLOOR_PTS = 5.0
SL_CAP_PTS   = 15.0
TRAIL_FLOOR_PTS = 3.0
TRAIL_CAP_PTS   = 12.0


# ─── Fonctions ───
def load_mnq_continuous(path):
    df = pd.read_csv(path, usecols=['ts_event','open','high','low','close','volume','symbol'])
    df = df[df['symbol'].str.startswith('MNQ') & ~df['symbol'].str.contains('-', na=False)].copy()
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


def compute_momentum_features(df, breakout_lookback=BREAKOUT_LOOKBACK,
                              stop_lookback=STOP_LOOKBACK):
    """Calcule rolling_max/min (breakout levels) et std (pour SL/trail).

    rolling_max(N)[i] = max(close[i-N+1:i+1]) → on shift(1) pour utiliser le max
    des N barres PRÉCÉDENTES (sans inclure la barre courante).
    """
    out = df.copy()
    closes = out['close']
    out['max_lookback'] = closes.rolling(breakout_lookback).max().shift(1)
    out['min_lookback'] = closes.rolling(breakout_lookback).min().shift(1)
    out['std'] = closes.rolling(stop_lookback).std(ddof=0)
    return out


def generate_momentum_signals(df, allowed_hours=None):
    """Signaux momentum : breakout = LONG, breakdown = SHORT, dans heure autorisée."""
    out = df.copy()
    out['signal'] = 0
    in_pocket = (out['hour_ny'].isin(allowed_hours)) if allowed_hours else True
    valid = out['max_lookback'].notna() & out['min_lookback'].notna() & out['std'].notna() & (out['std'] > 0) & in_pocket
    out.loc[valid & (out['close'] > out['max_lookback']), 'signal'] = +1   # LONG breakout
    out.loc[valid & (out['close'] < out['min_lookback']), 'signal'] = -1   # SHORT breakdown
    return out


def backtest_momentum_tick_realistic(df_signals,
                                     sl_std_mult=SL_STD_MULT,
                                     trail_std_mult=TRAIL_STD_MULT,
                                     sl_floor=SL_FLOOR_PTS, sl_cap=SL_CAP_PTS,
                                     trail_floor=TRAIL_FLOOR_PTS, trail_cap=TRAIL_CAP_PTS,
                                     slippage_ticks=SLIPPAGE_TICKS,
                                     commission_rt=COMMISSION_RT,
                                     timeout_bars=TIMEOUT_BARS):
    """Backtest momentum : breakout entry, SL hard + trail stop dynamique sur wicks."""
    df = df_signals.reset_index().copy()
    n = len(df); trades = []; i = 0
    while i < n - 1:
        sig = df.at[i, 'signal']
        if sig == 0 or pd.isna(df.at[i, 'std']) or df.at[i, 'std'] <= 0:
            i += 1; continue
        direction   = int(sig)
        entry_price = df.at[i, 'close']
        std_i       = df.at[i, 'std']
        # SL hard FIXE à l'entrée
        sl_hard_pts   = max(sl_floor, min(sl_cap, sl_std_mult * std_i))
        sl_hard_price = entry_price - direction * sl_hard_pts
        slip_pts = slippage_ticks * TICK_SIZE_MNQ
        # Trail tracking
        max_high = entry_price   # pour LONG
        min_low  = entry_price   # pour SHORT
        result_pts = 0.0
        exit_reason = 'timeout'
        exit_idx = min(i + timeout_bars, n - 1)
        for j in range(i + 1, min(n, i + timeout_bars + 1)):
            hj = df.at[j, 'high']; lj = df.at[j, 'low']
            # 1. SL hard wick check
            sl_hard_touched = (direction == 1 and lj <= sl_hard_price) or (direction == -1 and hj >= sl_hard_price)
            # 2. Trail stop dynamique : recalculer à chaque barre
            std_j = df.at[j, 'std'] if pd.notna(df.at[j, 'std']) and df.at[j, 'std'] > 0 else std_i
            trail_pts = max(trail_floor, min(trail_cap, trail_std_mult * std_j))
            if direction == 1:
                # LONG : update max_high avec le high de la barre j
                if hj > max_high: max_high = hj
                trail_stop = max_high - trail_pts
                trail_touched = lj <= trail_stop
            else:
                # SHORT : update min_low avec le low de la barre j
                if lj < min_low: min_low = lj
                trail_stop = min_low + trail_pts
                trail_touched = hj >= trail_stop
            # Règle pessimiste : si les deux touchés, prendre le plus défavorable
            if sl_hard_touched and trail_touched:
                # Comparer prix : pour LONG, le plus bas; pour SHORT, le plus haut
                if direction == 1:
                    worst_price = min(sl_hard_price, trail_stop)
                else:
                    worst_price = max(sl_hard_price, trail_stop)
                exit_price = worst_price - direction * slip_pts
                result_pts = direction * (exit_price - entry_price)
                exit_reason = 'SL_hard+trail'
                exit_idx = j; break
            elif sl_hard_touched:
                exit_price = sl_hard_price - direction * slip_pts
                result_pts = direction * (exit_price - entry_price)
                exit_reason = 'SL_hard'
                exit_idx = j; break
            elif trail_touched:
                exit_price = trail_stop - direction * slip_pts
                result_pts = direction * (exit_price - entry_price)
                exit_reason = 'trail'
                exit_idx = j; break
        else:
            exit_price = df.at[exit_idx, 'close']
            result_pts = direction * (exit_price - entry_price)
        pnl_usd = result_pts * POINT_VALUE_MNQ - commission_rt
        trades.append({
            'entry_time': df.at[i, 'bar'], 'exit_time': df.at[exit_idx, 'bar'],
            'direction': 'LONG' if direction == 1 else 'SHORT',
            'entry_price': entry_price, 'exit_price': exit_price,
            'sl_hard_price': sl_hard_price, 'sl_hard_pts': sl_hard_pts,
            'pts': result_pts, 'pnl_usd': pnl_usd, 'exit_reason': exit_reason,
            'bars_held': exit_idx - i, 'hour_ny': df.at[i, 'hour_ny'],
            'month': df.at[i, 'month'], 'dow': df.at[i, 'dow'],
        })
        i = exit_idx + 1
    return pd.DataFrame(trades)


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


# ════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════

print('=' * 70)
print('### CHARGEMENT MNQ M1 ###')
print('=' * 70)
try:
    df_mnq = load_mnq_continuous(CSV_PATH)
    print(f'Bars MNQ M1 (rollovers exclus) : {len(df_mnq):,}')

    # Colonnes temporelles + filtre session NY
    df_mnq['ts_ny']   = df_mnq.index.tz_convert('America/New_York')
    df_mnq['hour_ny'] = df_mnq['ts_ny'].dt.hour
    df_mnq['min_ny']  = df_mnq['ts_ny'].dt.minute
    df_mnq['month']   = df_mnq.index.month
    df_mnq['dow']     = df_mnq.index.dayofweek
    df_mnq['date']    = df_mnq.index.date
    t_ny = df_mnq['hour_ny'] * 60 + df_mnq['min_ny']
    df_session = df_mnq[(t_ny >= 9*60+30) & (t_ny < 16*60)].copy()
    print(f'Bars session NY 9h30-16h : {len(df_session):,}')

    print()
    print('=' * 70)
    print(f'### MOMENTUM FEATURES (N={BREAKOUT_LOOKBACK}) ###')
    print('=' * 70)
    t0 = time.time()
    df_feat = compute_momentum_features(df_session)
    print(f'Termine en {time.time()-t0:.1f}s')

    # Splits
    df_train = df_feat.loc[(df_feat.index >= TRAIN_START) & (df_feat.index < TRAIN_END)].copy()
    df_valid = df_feat.loc[(df_feat.index >= VALID_START) & (df_feat.index < VALID_END)].copy()
    print(f'Train : {len(df_train):,} bars | Valid : {len(df_valid):,} bars')

    # Backtest GLOBAL (toutes heures)
    print()
    print('=' * 70)
    print('### BACKTEST MOMENTUM GLOBAL (toutes heures, Train) ###')
    print('=' * 70)
    sigs_all = generate_momentum_signals(df_train, allowed_hours=None)
    n_signals = (sigs_all['signal'] != 0).sum()
    print(f'Signaux generes (Train) : {n_signals:,}')
    t0 = time.time()
    trades_all = backtest_momentum_tick_realistic(sigs_all)
    print(f'Backtest global termine en {time.time()-t0:.1f}s — {len(trades_all)} trades')
    m_all = compute_trade_metrics(trades_all)
    print(f'Global Train : {m_all}')

    # Backtest par heure NY (Train)
    print()
    print('=' * 70)
    print('### BACKTEST MOMENTUM PAR HEURE NY (Train) ###')
    print('=' * 70)
    results_hour = []
    for h in sorted(df_train['hour_ny'].dropna().unique()):
        sigs = generate_momentum_signals(df_train, allowed_hours={int(h)})
        trades = backtest_momentum_tick_realistic(sigs)
        m = compute_trade_metrics(trades)
        m['hour'] = int(h)
        results_hour.append(m)
        print(f'  hour={int(h):2d} : trades={m["trades"]:>5} | PF={m["pf"]:.2f} | Sharpe={m["sharpe"]:.2f} | DD=${m["max_dd"]:,.0f} | WR={m["wr"]*100:.1f}% | PnL=${m["pnl"]:+,.0f}')
    rh_df = pd.DataFrame(results_hour).sort_values('pf', ascending=False)
    print('\n--- Resultats momentum par heure (tries par PF) ---')
    print(rh_df[['hour','trades','pf','sharpe','max_dd','wr','pnl','avg_trade']])
    rh_df.to_csv(OUT_DIR / 'results_hour_train_momentum.csv', index=False)

    # Backtest par mois (Train, toutes heures)
    print()
    print('=' * 70)
    print('### BACKTEST MOMENTUM PAR MOIS (Train) ###')
    print('=' * 70)
    results_month = []
    for m_num in range(1, 13):
        sigs = generate_momentum_signals(df_train, allowed_hours=None)
        sigs_m = sigs[sigs['month'] == m_num].copy()
        trades = backtest_momentum_tick_realistic(sigs_m)
        m_metrics = compute_trade_metrics(trades)
        m_metrics['month'] = m_num
        results_month.append(m_metrics)
        print(f'  mois={m_num:2d} : trades={m_metrics["trades"]:>5} | PF={m_metrics["pf"]:.2f} | Sharpe={m_metrics["sharpe"]:.2f} | DD=${m_metrics["max_dd"]:,.0f} | WR={m_metrics["wr"]*100:.1f}% | PnL=${m_metrics["pnl"]:+,.0f}')
    rm_df = pd.DataFrame(results_month).sort_values('pf', ascending=False)
    print('\n--- Resultats momentum par mois (tries par PF) ---')
    print(rm_df[['month','trades','pf','sharpe','max_dd','wr','pnl','avg_trade']])
    rm_df.to_csv(OUT_DIR / 'results_month_train_momentum.csv', index=False)

    # Promotion : seuils PF>1.5, Sharpe>1.0, trades>=100
    promising = rh_df[(rh_df['pf'] > 1.5) & (rh_df['sharpe'] > 1.0) & (rh_df['trades'] >= 100)]
    print(f'\nHeures momentum prometteuses : {len(promising)}')
    if len(promising) > 0:
        print(promising[['hour','trades','pf','sharpe','max_dd','wr','pnl']])
        pocket_hours = set(promising['hour'].astype(int).tolist())
        sigs_v = generate_momentum_signals(df_valid, allowed_hours=pocket_hours)
        trades_v = backtest_momentum_tick_realistic(sigs_v)
        m_v = compute_trade_metrics(trades_v)
        print(f'Valid pocket momentum {sorted(pocket_hours)} : {m_v}')

except Exception as e:
    print(f'[ERROR] {type(e).__name__}: {e}')
    traceback.print_exc()

print()
print('=' * 70)
print('### FIN MOMENTUM ###')
print('=' * 70)
print(f'Fichiers dans {OUT_DIR}/ :')
for p in sorted(OUT_DIR.iterdir()):
    print(f'  - {p.name}')
