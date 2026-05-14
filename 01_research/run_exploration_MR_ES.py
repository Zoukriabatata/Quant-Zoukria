"""
run_exploration_MR_ES.py — Hurst + signal MR sur ES M1 (E-mini S&P 500) 5 ans.

Mini-validation #2 : si MNQ M1 est trending (H~0.62), est-ce que ES (sous-jacent
différent) montre un comportement MR ?

Outputs : 01_research/outputs/es/
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

pd.set_option('display.max_rows', 50)
pd.set_option('display.float_format', '{:.4f}'.format)

ES_CSV_PATH = Path(r'ES 5ANS DATA\glbx-mdp3-20210513-20260512.ohlcv-1m.csv.zst')
OUT_DIR     = Path('01_research/outputs/es')
OUT_DIR.mkdir(parents=True, exist_ok=True)

TRAIN_START   = pd.Timestamp('2021-05-13', tz='UTC')
TRAIN_END     = pd.Timestamp('2024-05-13', tz='UTC')
VALID_START   = TRAIN_END
VALID_END     = pd.Timestamp('2025-05-13', tz='UTC')
HOLDOUT_START = VALID_END
HOLDOUT_END   = pd.Timestamp('2026-05-13', tz='UTC')

# ── ES contract specs (différents de MNQ) ────────────────────────────
COMMISSION_RT  = 4.00          # ~$4/round-trip ES retail (vs $1.10 MNQ)
SLIPPAGE_TICKS = 1
POINT_VALUE_ES = 50.00         # $50/pt ES (vs $2 MNQ)
TICK_SIZE_ES   = 0.25

# Mêmes paramètres signal qu'MNQ (cohérence)
HURST_WINDOW    = 50
HURST_MR_THR    = 0.45
ZSCORE_LOOKBACK = 20
ZSCORE_ENTRY    = 2.0
ZSCORE_EXIT     = 0.5

# SL en pts ES : 1.5 × std, floor 1 pt = $50, cap 2 pts = $100
# (ES bouge ~3x moins en points qu'MNQ — adapté aux specs ES)
STOP_STD_MULT  = 1.5
STOP_FLOOR_PTS = 1.0
STOP_CAP_PTS   = 2.0

TIMEOUT_BARS = 60


# ─── Fonctions ───
def hurst_rs(ts):
    ts = np.asarray(ts, dtype=float); n = len(ts)
    if n < 20: return 0.5
    lags = np.unique(np.round(np.exp(np.linspace(np.log(4), np.log(min(n // 2, 50)), 12))).astype(int))
    lags = lags[lags >= 4]
    rs_vals = []
    for lag in lags:
        lag = int(lag); n_chunks = n // lag
        if n_chunks < 2: continue
        mat = ts[:n_chunks * lag].reshape(n_chunks, lag)
        mean = mat.mean(axis=1, keepdims=True)
        devs = np.cumsum(mat - mean, axis=1)
        R = devs.max(axis=1) - devs.min(axis=1)
        S = mat.std(axis=1, ddof=0)
        mask = S > 0
        if mask.sum() == 0: continue
        rs_vals.append(float((R[mask] / S[mask]).mean()))
    if len(rs_vals) < 3: return 0.5
    try:
        return float(np.clip(np.polyfit(np.log(lags[:len(rs_vals)]), np.log(rs_vals), 1)[0], 0.0, 1.0))
    except Exception:
        return 0.5


def load_es_continuous(path):
    """Charge ES 5 ans, filtre rollover, retourne DataFrame OHLCV.

    Format Databento : symbole ESM1, ESU1, ESZ1, ESH2, etc. (M=mars, M=juin, U=sept, Z=déc, H=mars).
    """
    df = pd.read_csv(path, usecols=['ts_event','open','high','low','close','volume','symbol'])
    # ES contrats simples (pas de spreads, pas de MNQ)
    df = df[df['symbol'].str.startswith('ES') & ~df['symbol'].str.contains('-', na=False)].copy()
    # Volume max par timestamp = front month dominant
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


def compute_rolling_hurst_by_session(df, hwin):
    out = np.full(len(df), np.nan)
    closes = df['close'].values.astype(float); dates = df['date'].values
    day_starts = np.where(np.concatenate([[True], dates[1:] != dates[:-1]]))[0]
    day_starts = np.append(day_starts, len(df))
    for k in range(len(day_starts) - 1):
        a, b = day_starts[k], day_starts[k+1]
        if b - a < hwin + 2: continue
        sess_close = closes[a:b]
        sess_rets = np.diff(np.log(np.maximum(sess_close, 1e-9)))
        sess_rets = np.concatenate([[0.0], sess_rets])
        for i in range(hwin, b - a):
            out[a + i] = hurst_rs(sess_rets[i - hwin: i])
    return pd.Series(out, index=df.index, name='hurst')


def compute_signal_features(df, lookback=ZSCORE_LOOKBACK):
    out = df.copy()
    closes = out['close']
    out['mid'] = closes.rolling(lookback).mean()
    out['std'] = closes.rolling(lookback).std(ddof=0)
    out['zscore'] = (closes - out['mid']) / out['std'].replace(0, np.nan)
    return out


def generate_mr_signals(df, zscore_entry=ZSCORE_ENTRY, allowed_hours=None):
    out = df.copy()
    out['signal'] = 0
    in_pocket = (out['hour_ny'].isin(allowed_hours)) if allowed_hours else True
    valid = out['zscore'].notna() & out['std'].notna() & (out['std'] > 0) & in_pocket
    out.loc[valid & (out['zscore'] > zscore_entry), 'signal'] = -1
    out.loc[valid & (out['zscore'] < -zscore_entry), 'signal'] = +1
    return out


def backtest_tick_realistic_es(df_signals, stop_std_mult=STOP_STD_MULT,
                                stop_floor_pts=STOP_FLOOR_PTS, stop_cap_pts=STOP_CAP_PTS,
                                zscore_exit=ZSCORE_EXIT, slippage_ticks=SLIPPAGE_TICKS,
                                commission_rt=COMMISSION_RT, timeout_bars=TIMEOUT_BARS):
    df = df_signals.reset_index().copy()
    n = len(df); trades = []; i = 0
    while i < n - 1:
        sig = df.at[i, 'signal']
        if sig == 0 or pd.isna(df.at[i, 'std']) or df.at[i, 'std'] <= 0 or pd.isna(df.at[i, 'mid']):
            i += 1; continue
        direction = int(sig); entry_price = df.at[i, 'close']; std_i = df.at[i, 'std']
        sl_pts = max(stop_floor_pts, min(stop_cap_pts, stop_std_mult * std_i))
        sl_price = entry_price - direction * sl_pts
        slip_pts = slippage_ticks * TICK_SIZE_ES
        result_pts = 0.0; exit_reason = 'timeout'; exit_idx = min(i + timeout_bars, n - 1)
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
        else:
            exit_price = df.at[exit_idx, 'close']
            result_pts = direction * (exit_price - entry_price)
        pnl_usd = result_pts * POINT_VALUE_ES - commission_rt
        trades.append({
            'entry_time': df.at[i, 'bar'], 'exit_time': df.at[exit_idx, 'bar'],
            'direction': 'LONG' if direction == 1 else 'SHORT',
            'entry_price': entry_price, 'exit_price': exit_price,
            'sl_price': sl_price, 'sl_pts': sl_pts, 'std_i': std_i,
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
print('### CHARGEMENT ES M1 ###')
print('=' * 70)
print(f'Source : {ES_CSV_PATH}')
try:
    df_es = load_es_continuous(ES_CSV_PATH)
    print(f'Bars ES (rollovers exclus) : {len(df_es):,}')
    print(f'Periode : {df_es.index[0]} -> {df_es.index[-1]}')

    df_es['ts_ny']   = df_es.index.tz_convert('America/New_York')
    df_es['hour_ny'] = df_es['ts_ny'].dt.hour
    df_es['min_ny']  = df_es['ts_ny'].dt.minute
    df_es['month']   = df_es.index.month
    df_es['dow']     = df_es.index.dayofweek
    df_es['date']    = df_es.index.date
    t_ny = df_es['hour_ny'] * 60 + df_es['min_ny']
    df_session = df_es[(t_ny >= 9*60+30) & (t_ny < 16*60)].copy()
    print(f'Bars en session NY 9h30-16h : {len(df_session):,}')

    # Hurst rolling
    print()
    print('=' * 70)
    print(f'### HURST ROLLING ES (HW={HURST_WINDOW}) ###')
    print('=' * 70)
    t0 = time.time()
    df_session['hurst'] = compute_rolling_hurst_by_session(df_session, HURST_WINDOW)
    print(f'Termine en {time.time()-t0:.1f}s ({(time.time()-t0)/60:.1f} min)')
    print(f'H valide : {df_session["hurst"].notna().sum():,} / {len(df_session):,}')
    print('Stats H :', df_session['hurst'].describe().to_dict())

    # Distribution H Train+Valid
    print()
    print('=' * 70)
    print('### DISTRIBUTION H ES ###')
    print('=' * 70)
    mask_tv = (df_session.index >= TRAIN_START) & (df_session.index < HOLDOUT_START)
    df_tv = df_session.loc[mask_tv & df_session['hurst'].notna()].copy()
    print(f'Bars TV avec H : {len(df_tv):,}')

    def hsum(col):
        g = df_tv.groupby(col)['hurst']
        s = g.agg(['mean', 'std', 'count']).copy()
        s['t_stat'] = (s['mean'] - 0.5) / (s['std'] / np.sqrt(s['count']))
        s['p_value'] = 2 * (1 - stats.norm.cdf(np.abs(s['t_stat'])))
        s['mr_significant'] = (s['mean'] < HURST_MR_THR) & (s['p_value'] < 0.01)
        return s

    h_by_hour  = hsum('hour_ny').sort_index()
    h_by_month = hsum('month')
    h_by_dow   = hsum('dow')
    print('\n--- H par heure NY (ES) ---')
    print(h_by_hour)
    print('\n--- H par mois (ES) ---')
    print(h_by_month)
    print('\n--- H par jour de semaine (ES) ---')
    print(h_by_dow)
    h_by_hour.to_csv(OUT_DIR / 'h_by_hour_es.csv')
    h_by_month.to_csv(OUT_DIR / 'h_by_month_es.csv')
    h_by_dow.to_csv(OUT_DIR / 'h_by_dow_es.csv')

    print(f'\nPoches MR exploitables (H<{HURST_MR_THR}, p<0.01) :')
    pockets_h = h_by_hour[h_by_hour['mr_significant']]
    pockets_m = h_by_month[h_by_month['mr_significant']]
    pockets_d = h_by_dow[h_by_dow['mr_significant']]
    print(f'  heures : {len(pockets_h)} ({list(pockets_h.index)})')
    print(f'  mois   : {len(pockets_m)} ({list(pockets_m.index)})')
    print(f'  jours  : {len(pockets_d)} ({list(pockets_d.index)})')

    # Plot
    fig, axes = plt.subplots(1, 3, figsize=(18, 4))
    axes[0].bar(h_by_hour.index, h_by_hour['mean'], yerr=h_by_hour['std']/np.sqrt(h_by_hour['count']))
    axes[0].axhline(0.5, color='red', linestyle='--', label='H=0.5')
    axes[0].axhline(HURST_MR_THR, color='green', linestyle='--', label=f'H={HURST_MR_THR}')
    axes[0].set_title('ES — Hurst par heure NY'); axes[0].legend()
    axes[1].bar(h_by_month.index, h_by_month['mean'])
    axes[1].axhline(0.5, color='red', linestyle='--')
    axes[1].axhline(HURST_MR_THR, color='green', linestyle='--')
    axes[1].set_title('ES — Hurst par mois')
    axes[2].bar(range(len(h_by_dow)), h_by_dow['mean'])
    axes[2].set_xticks(range(len(h_by_dow))); axes[2].set_xticklabels(h_by_dow.index)
    axes[2].axhline(0.5, color='red', linestyle='--')
    axes[2].axhline(HURST_MR_THR, color='green', linestyle='--')
    axes[2].set_title('ES — Hurst par jour')
    plt.tight_layout()
    plt.savefig(OUT_DIR / 'hurst_distribution_es.png', dpi=150, bbox_inches='tight')
    plt.close()

    # Backtest par heure
    print()
    print('=' * 70)
    print('### BACKTEST ES PAR HEURE NY (Train) ###')
    print('=' * 70)
    df_sig = compute_signal_features(df_session.copy())
    df_train = df_sig.loc[(df_sig.index >= TRAIN_START) & (df_sig.index < TRAIN_END)].copy()
    df_valid = df_sig.loc[(df_sig.index >= VALID_START) & (df_sig.index < VALID_END)].copy()
    print(f'Train : {len(df_train):,} bars | Valid : {len(df_valid):,} bars')

    results_hour = []
    for h in sorted(df_train['hour_ny'].dropna().unique()):
        sigs = generate_mr_signals(df_train, allowed_hours={int(h)})
        trades = backtest_tick_realistic_es(sigs)
        m = compute_trade_metrics(trades)
        m['hour'] = int(h)
        results_hour.append(m)
        print(f'  hour={int(h):2d} : trades={m["trades"]:>5} | PF={m["pf"]:.2f} | Sharpe={m["sharpe"]:.2f} | DD=${m["max_dd"]:,.0f} | WR={m["wr"]*100:.1f}% | PnL=${m["pnl"]:+,.0f}')
    rh_df = pd.DataFrame(results_hour).sort_values('pf', ascending=False)
    print('\n--- Resultats ES par heure (tries par PF) ---')
    print(rh_df[['hour','trades','pf','sharpe','max_dd','wr','pnl','avg_trade']])
    rh_df.to_csv(OUT_DIR / 'results_hour_train_es.csv', index=False)

    # Promotion
    promising = rh_df[(rh_df['pf'] > 1.5) & (rh_df['sharpe'] > 1.0) & (rh_df['trades'] >= 100)]
    print(f'\nHeures prometteuses ES (PF>1.5, Sharpe>1.0, trades>=100) : {len(promising)}')
    if len(promising) > 0:
        print(promising[['hour','trades','pf','sharpe','max_dd','wr','pnl']])
        pocket_hours = set(promising['hour'].astype(int).tolist())
        sigs_v = generate_mr_signals(df_valid, allowed_hours=pocket_hours)
        trades_v = backtest_tick_realistic_es(sigs_v)
        m_v = compute_trade_metrics(trades_v)
        print(f'Valid ES pocket {sorted(pocket_hours)} : {m_v}')

except Exception as e:
    print(f'[ERROR] {type(e).__name__}: {e}')
    traceback.print_exc()

print()
print('=' * 70)
print('### FIN ES ###')
print('=' * 70)
print(f'Fichiers dans {OUT_DIR}/ :')
for p in sorted(OUT_DIR.iterdir()):
    print(f'  - {p.name}')
