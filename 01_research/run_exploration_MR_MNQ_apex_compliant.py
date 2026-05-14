"""
run_exploration_MR_MNQ_apex_compliant.py — Mini-validation #4 : finding 15h NY MR
sous contraintes Apex Eval $50K strictes.

Contraintes appliquées :
  1. Force-flat MTM au close du dernier bar dont close <= 15:59 NY
  2. No entry après 15:55 NY (last bar close <= 15:55 NY)
  3. Daily loss hard-stop : si daily_pnl <= -$1,000 → arrêt jour
  4. Trailing DD intra-month : HWM cumulé du P&L mensuel, si DD utilisé >= $2,000 → bust mois

Comparaison : avec contraintes vs sans contraintes (= replay mini-val #1)
Cycle Apex : 60 mois simulés sur 5 ans, calcul pass rate $3K target.

Outputs : 01_research/outputs/apex_compliant/
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
from scipy import stats
import matplotlib.pyplot as plt

pd.set_option('display.max_rows', 80)
pd.set_option('display.float_format', '{:.4f}'.format)

CSV_PATH = Path(r'C:\Users\ryadb\Downloads\MNQ 5ANS DATA\glbx-mdp3-20210513-20260512.ohlcv-1m.csv.zst')
OUT_DIR  = Path('01_research/outputs/apex_compliant')
OUT_DIR.mkdir(parents=True, exist_ok=True)

TRAIN_START   = pd.Timestamp('2021-05-13', tz='UTC')
TRAIN_END     = pd.Timestamp('2024-05-13', tz='UTC')
VALID_START   = TRAIN_END
VALID_END     = pd.Timestamp('2025-05-13', tz='UTC')
HOLDOUT_START = VALID_END
HOLDOUT_END   = pd.Timestamp('2026-05-13', tz='UTC')

COMMISSION_RT   = 1.10
SLIPPAGE_TICKS  = 1
POINT_VALUE_MNQ = 2.00
TICK_SIZE_MNQ   = 0.25

ZSCORE_LOOKBACK = 20
ZSCORE_ENTRY    = 2.0
ZSCORE_EXIT     = 0.5

STOP_STD_MULT   = 1.5
STOP_FLOOR_PTS  = 5.0
STOP_CAP_PTS    = 10.0

# ── Contraintes Apex $50K Eval ───────────────────────────────────────
APEX_CAPITAL          = 50_000
APEX_PROFIT_TARGET    = 3_000
APEX_TRAILING_DD      = 2_000
APEX_DAILY_LIMIT      = 1_000
APEX_MAX_CONTRACTS    = 40         # MNQ micros
ENTRY_CUTOFF_NY_MIN   = 15 * 60 + 55   # entry interdite si close > 15:55 NY (= 955 min depuis minuit)
EXIT_FORCE_NY_MIN     = 15 * 60 + 59   # force exit MTM au close <= 15:59 NY

# Sizing simple pour mini-val : 1 contrat fixe (comme mini-val #1)
# Sizing Kelly testé séparément si besoin
FIXED_CONTRACTS = 1


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


def resample_ohlcv(df, rule):
    out = df.resample(rule).agg({
        'open': 'first', 'high': 'max', 'low': 'min',
        'close': 'last', 'volume': 'sum'
    }).dropna(subset=['close'])
    return out


def compute_signal_features(df, lookback=ZSCORE_LOOKBACK):
    out = df.copy()
    closes = out['close']
    out['mid'] = closes.rolling(lookback).mean()
    out['std'] = closes.rolling(lookback).std(ddof=0)
    out['zscore'] = (closes - out['mid']) / out['std'].replace(0, np.nan)
    return out


def generate_mr_signals(df, zscore_entry=ZSCORE_ENTRY, allowed_hours=None,
                       entry_cutoff_ny_min=None, bar_size_min=1):
    """Génère signaux MR. Si entry_cutoff_ny_min set : pas de signal si la barre
    close après ce cutoff (en min NY locale)."""
    out = df.copy()
    out['signal'] = 0
    in_pocket = (out['hour_ny'].isin(allowed_hours)) if allowed_hours else True
    valid = out['zscore'].notna() & out['std'].notna() & (out['std'] > 0) & in_pocket
    if entry_cutoff_ny_min is not None:
        # close_min_ny = minute_ny + bar_size_min (la barre close à start_min + bar_size)
        close_min_ny = out['hour_ny'] * 60 + out['min_ny'] + bar_size_min
        valid = valid & (close_min_ny <= entry_cutoff_ny_min)
    out.loc[valid & (out['zscore'] > zscore_entry), 'signal'] = -1
    out.loc[valid & (out['zscore'] < -zscore_entry), 'signal'] = +1
    return out


def backtest_apex_compliant(df_signals, contracts=FIXED_CONTRACTS,
                            stop_std_mult=STOP_STD_MULT,
                            stop_floor_pts=STOP_FLOOR_PTS, stop_cap_pts=STOP_CAP_PTS,
                            zscore_exit=ZSCORE_EXIT, slippage_ticks=SLIPPAGE_TICKS,
                            commission_rt=COMMISSION_RT, timeout_bars=60,
                            bar_size_min=1, apex_constraints=True,
                            exit_force_ny_min=EXIT_FORCE_NY_MIN):
    """Backtest event-driven avec option contraintes Apex.

    Si apex_constraints=True :
      - Force exit MTM au close <= exit_force_ny_min (15:59 NY default)
      - Entry cutoff appliqué via generate_mr_signals upstream
      - daily_limit / trailing DD appliqués en post-process (cf. simulate_apex_cycle)
    """
    df = df_signals.reset_index().copy()
    n = len(df); trades = []; i = 0
    while i < n - 1:
        sig = df.at[i, 'signal']
        if sig == 0 or pd.isna(df.at[i, 'std']) or df.at[i, 'std'] <= 0 or pd.isna(df.at[i, 'mid']):
            i += 1; continue
        direction = int(sig); entry_price = df.at[i, 'close']; std_i = df.at[i, 'std']
        sl_pts = max(stop_floor_pts, min(stop_cap_pts, stop_std_mult * std_i))
        sl_price = entry_price - direction * sl_pts
        slip_pts = slippage_ticks * TICK_SIZE_MNQ
        result_pts = 0.0; exit_reason = 'timeout'; exit_idx = min(i + timeout_bars, n - 1)
        # Date de l'entrée (pour limite force-flat intra-day)
        entry_date = df.at[i, 'date']
        for j in range(i + 1, min(n, i + timeout_bars + 1)):
            hj = df.at[j, 'high']; lj = df.at[j, 'low']
            sl_touched = (direction == 1 and lj <= sl_price) or (direction == -1 and hj >= sl_price)
            if sl_touched:
                exit_price = sl_price - direction * slip_pts
                result_pts = direction * (exit_price - entry_price)
                exit_reason = 'SL'; exit_idx = j; break
            z_j = df.at[j, 'zscore']
            if pd.notna(z_j):
                tp_touched = (direction == 1 and z_j >= -zscore_exit) or \
                             (direction == -1 and z_j <= zscore_exit)
                if tp_touched:
                    exit_price = df.at[j, 'close']
                    result_pts = direction * (exit_price - entry_price)
                    exit_reason = 'TP_zscore'; exit_idx = j; break
            # CONTRAINTE APEX : force-flat MTM si on s'approche de 16h NY ce jour-là
            if apex_constraints:
                close_min_ny = df.at[j, 'hour_ny'] * 60 + df.at[j, 'min_ny'] + bar_size_min
                # même jour ET close > exit_force_ny_min → force exit au close de cette barre
                same_day = df.at[j, 'date'] == entry_date
                if same_day and close_min_ny > exit_force_ny_min:
                    exit_price = df.at[j, 'close']
                    result_pts = direction * (exit_price - entry_price)
                    exit_reason = 'apex_force_flat'
                    exit_idx = j; break
                # Si on est sur un autre jour → c'est que la session NY ne contient pas
                # l'heure d'exit force (ne devrait jamais arriver sur session 9h30-16h)
        else:
            exit_price = df.at[exit_idx, 'close']
            result_pts = direction * (exit_price - entry_price)
        pnl_usd = result_pts * POINT_VALUE_MNQ * contracts - commission_rt * contracts
        trades.append({
            'entry_time': df.at[i, 'bar'], 'exit_time': df.at[exit_idx, 'bar'],
            'direction': 'LONG' if direction == 1 else 'SHORT',
            'entry_price': entry_price, 'exit_price': exit_price,
            'sl_price': sl_price, 'sl_pts': sl_pts, 'std_i': std_i,
            'pts': result_pts, 'pnl_usd': pnl_usd, 'exit_reason': exit_reason,
            'bars_held': exit_idx - i, 'hour_ny': df.at[i, 'hour_ny'],
            'min_ny': df.at[i, 'min_ny'],
            'date': df.at[i, 'date'],
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


def simulate_apex_cycle(trades_df, contracts=FIXED_CONTRACTS,
                        target=APEX_PROFIT_TARGET, dd_limit=APEX_TRAILING_DD,
                        daily_limit=APEX_DAILY_LIMIT):
    """Simule un challenge Apex Eval 1-mois indépendant pour chaque mois calendaire.

    Pour chaque mois :
      - démarre avec running_pnl=0, hwm=0
      - itère les trades chronologiquement
      - applique : daily limit, trailing DD intra-month, target
      - retourne le statut : 'PASSED' / 'BUSTED_DD' / 'BUSTED_DAILY' / 'NO_TARGET'

    Le daily limit ne bust pas le mois — il stop juste le jour (les trades suivants
    du même jour sont skippés). Le DD limit bust le mois (aucun trade après).
    """
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
        trades_taken = 0; trades_skipped_daily = 0; trades_skipped_dd = 0
        for _, t in m_trades.iterrows():
            d = t['date']
            # Skip si déjà busted aujourd'hui (daily limit atteint)
            if d in busted_today:
                trades_skipped_daily += 1
                continue
            # Skip si DD limit déjà atteint ce mois (bust mois)
            if status == 'BUSTED_DD':
                trades_skipped_dd += 1
                continue
            # Exécute le trade
            pnl = t['pnl_usd']
            running_pnl += pnl
            daily_pnl[d] = daily_pnl.get(d, 0.0) + pnl
            trades_taken += 1
            # Update HWM
            if running_pnl > hwm: hwm = running_pnl
            # Check DD
            dd_used = hwm - running_pnl
            if dd_used >= dd_limit:
                status = 'BUSTED_DD'
                continue
            # Check target
            if running_pnl >= target and status == 'NO_TARGET':
                status = 'PASSED'
            # Check daily limit
            if daily_pnl[d] <= -daily_limit:
                busted_today.add(d)
        results.append({
            'month': ym,
            'status': status,
            'final_pnl': running_pnl,
            'hwm': hwm,
            'max_dd_intra_month': hwm - running_pnl if status != 'BUSTED_DD' else dd_limit,
            'trades_taken': trades_taken,
            'trades_skipped_daily': trades_skipped_daily,
            'trades_skipped_dd': trades_skipped_dd,
            'n_days_busted': len(busted_today),
        })
    return pd.DataFrame(results)


# ════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════

print('=' * 70)
print('### CHARGEMENT MNQ M1 ###')
print('=' * 70)
df_mnq = load_mnq_continuous(CSV_PATH)
print(f'Bars M1 (rollovers exclus) : {len(df_mnq):,}')


def run_apex_check_for_tf(tf_str, resample_rule, bar_size_min, timeout_bars):
    print()
    print('=' * 70)
    print(f'### TF {tf_str} @ 15h NY — APEX COMPLIANCE CHECK ###')
    print('=' * 70)
    df_tf = resample_ohlcv(df_mnq, resample_rule)
    df_tf['ts_ny']   = df_tf.index.tz_convert('America/New_York')
    df_tf['hour_ny'] = df_tf['ts_ny'].dt.hour
    df_tf['min_ny']  = df_tf['ts_ny'].dt.minute
    df_tf['month']   = df_tf.index.month
    df_tf['dow']     = df_tf.index.dayofweek
    df_tf['date']    = df_tf.index.date
    t_ny = df_tf['hour_ny'] * 60 + df_tf['min_ny']
    df_tf_sess = df_tf[(t_ny >= 9*60+30) & (t_ny < 16*60)].copy()
    df_sig = compute_signal_features(df_tf_sess)

    df_train = df_sig.loc[(df_sig.index >= TRAIN_START) & (df_sig.index < TRAIN_END)].copy()
    df_valid = df_sig.loc[(df_sig.index >= VALID_START) & (df_sig.index < VALID_END)].copy()
    print(f'Train : {len(df_train):,} bars | Valid : {len(df_valid):,} bars')

    # ─── A) Baseline (mini-val #1 replay) : sans contraintes ───
    print()
    print(f'--- {tf_str} A) BASELINE (sans contraintes Apex) ---')
    sigs_train_baseline = generate_mr_signals(df_train, allowed_hours={15},
                                              entry_cutoff_ny_min=None,
                                              bar_size_min=bar_size_min)
    n_sig_baseline = (sigs_train_baseline['signal'] != 0).sum()
    print(f'Signaux Train baseline : {n_sig_baseline}')
    trades_train_baseline = backtest_apex_compliant(sigs_train_baseline,
                                                    timeout_bars=timeout_bars,
                                                    bar_size_min=bar_size_min,
                                                    apex_constraints=False)
    m_train_baseline = compute_trade_metrics(trades_train_baseline)
    print(f'Train baseline : {m_train_baseline}')

    sigs_valid_baseline = generate_mr_signals(df_valid, allowed_hours={15},
                                              entry_cutoff_ny_min=None,
                                              bar_size_min=bar_size_min)
    trades_valid_baseline = backtest_apex_compliant(sigs_valid_baseline,
                                                    timeout_bars=timeout_bars,
                                                    bar_size_min=bar_size_min,
                                                    apex_constraints=False)
    m_valid_baseline = compute_trade_metrics(trades_valid_baseline)
    print(f'Valid baseline : {m_valid_baseline}')

    # ─── B) Apex compliant : contraintes per-trade ───
    print()
    print(f'--- {tf_str} B) APEX-COMPLIANT (force-flat 15:59 + no entry après 15:55) ---')
    sigs_train_apex = generate_mr_signals(df_train, allowed_hours={15},
                                          entry_cutoff_ny_min=ENTRY_CUTOFF_NY_MIN,
                                          bar_size_min=bar_size_min)
    n_sig_apex = (sigs_train_apex['signal'] != 0).sum()
    print(f'Signaux Train apex-compliant : {n_sig_apex} (vs baseline {n_sig_baseline}, -{n_sig_baseline-n_sig_apex})')
    trades_train_apex = backtest_apex_compliant(sigs_train_apex,
                                                timeout_bars=timeout_bars,
                                                bar_size_min=bar_size_min,
                                                apex_constraints=True)
    m_train_apex = compute_trade_metrics(trades_train_apex)
    print(f'Train apex : {m_train_apex}')
    # Comptage des exit_reason
    if len(trades_train_apex) > 0:
        print(f'Train exit reasons : {trades_train_apex["exit_reason"].value_counts().to_dict()}')

    sigs_valid_apex = generate_mr_signals(df_valid, allowed_hours={15},
                                          entry_cutoff_ny_min=ENTRY_CUTOFF_NY_MIN,
                                          bar_size_min=bar_size_min)
    trades_valid_apex = backtest_apex_compliant(sigs_valid_apex,
                                                timeout_bars=timeout_bars,
                                                bar_size_min=bar_size_min,
                                                apex_constraints=True)
    m_valid_apex = compute_trade_metrics(trades_valid_apex)
    print(f'Valid apex : {m_valid_apex}')
    if len(trades_valid_apex) > 0:
        print(f'Valid exit reasons : {trades_valid_apex["exit_reason"].value_counts().to_dict()}')

    # ─── C) Simulation cycle Apex mensuel (Train + Valid combinés) ───
    print()
    print(f'--- {tf_str} C) SIMULATION CYCLE APEX 1-MOIS (60 mois sur 5 ans) ---')
    # Trades apex-compliant sur Train+Valid (5 ans), 1 contrat fixe
    all_signals = generate_mr_signals(df_sig, allowed_hours={15},
                                      entry_cutoff_ny_min=ENTRY_CUTOFF_NY_MIN,
                                      bar_size_min=bar_size_min)
    all_trades = backtest_apex_compliant(all_signals,
                                         timeout_bars=timeout_bars,
                                         bar_size_min=bar_size_min,
                                         apex_constraints=True)
    print(f'Trades total {tf_str} apex-compliant (5 ans) : {len(all_trades)}')
    cycle = simulate_apex_cycle(all_trades, contracts=1)
    if len(cycle) > 0:
        print(f'Mois simulés : {len(cycle)}')
        status_counts = cycle['status'].value_counts().to_dict()
        print(f'Status : {status_counts}')
        pass_rate = (cycle['status'] == 'PASSED').mean() * 100
        bust_rate = (cycle['status'] == 'BUSTED_DD').mean() * 100
        no_target_rate = (cycle['status'] == 'NO_TARGET').mean() * 100
        avg_pnl_per_month = cycle['final_pnl'].mean()
        print(f'Pass rate : {pass_rate:.1f}%')
        print(f'Bust DD rate : {bust_rate:.1f}%')
        print(f'No target end month : {no_target_rate:.1f}%')
        print(f'PnL moyen par mois (1 contrat) : ${avg_pnl_per_month:.0f}')
        print()
        print(f'Détail mois (1 contrat MNQ fixe) :')
        print(cycle.to_string(index=False))
        cycle.to_csv(OUT_DIR / f'apex_cycle_{tf_str}.csv', index=False)
        all_trades.to_csv(OUT_DIR / f'trades_apex_{tf_str}.csv', index=False)
    else:
        print('Pas de trades générés.')

    return dict(
        tf=tf_str,
        train_baseline=m_train_baseline,
        train_apex=m_train_apex,
        valid_baseline=m_valid_baseline,
        valid_apex=m_valid_apex,
        cycle=cycle if len(cycle) > 0 else None,
    )


try:
    res_5min = run_apex_check_for_tf('5min', '5min', bar_size_min=5, timeout_bars=12)
    res_15min = run_apex_check_for_tf('15min', '15min', bar_size_min=15, timeout_bars=4)

    # ─── Tableau comparatif final ───
    print()
    print('=' * 70)
    print('### TABLEAU COMPARATIF FINAL ###')
    print('=' * 70)
    print()
    print('| TF       | Bench Train PF | Apex Train PF | Δ PF | Bench Valid PF | Apex Valid PF | Δ PF |')
    print('|----------|----------------|----------------|------|----------------|----------------|------|')
    for r in [res_5min, res_15min]:
        tb = r['train_baseline']; ta = r['train_apex']
        vb = r['valid_baseline']; va = r['valid_apex']
        d_train = (ta['pf'] - tb['pf']) / max(tb['pf'], 0.01) * 100
        d_valid = (va['pf'] - vb['pf']) / max(vb['pf'], 0.01) * 100
        print(f"| {r['tf']:<8} | {tb['pf']:14.2f} | {ta['pf']:14.2f} | {d_train:+5.1f}% | {vb['pf']:14.2f} | {va['pf']:14.2f} | {d_valid:+5.1f}% |")
    print()
    print('Sharpe :')
    for r in [res_5min, res_15min]:
        tb = r['train_baseline']; ta = r['train_apex']
        vb = r['valid_baseline']; va = r['valid_apex']
        print(f"  {r['tf']:<6} Train: {tb['sharpe']:.2f} -> {ta['sharpe']:.2f}  ({ta['sharpe']-tb['sharpe']:+.2f}) | Valid: {vb['sharpe']:.2f} -> {va['sharpe']:.2f}  ({va['sharpe']-vb['sharpe']:+.2f})")

except Exception as e:
    print(f'[ERROR] {type(e).__name__}: {e}')
    traceback.print_exc()

print()
print('=' * 70)
print('### FIN MINI-VAL #4 ###')
print('=' * 70)
print(f'Fichiers dans {OUT_DIR}/ :')
for p in sorted(OUT_DIR.iterdir()):
    print(f'  - {p.name}')
