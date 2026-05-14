"""
run_exploration_MR_MNQ.py — Script d'exécution extrait de 01_exploration_MR_MNQ.ipynb

Objectif identique au notebook : exploration MR sur MNQ 5 ans tick-realistic,
identifier des poches d'edge par heure NY / mois / jour. Cf. notebook .ipynb
pour la documentation détaillée.

Sortie : 01_research/outputs/ (CSV des tables clefs + PNG des plots + log).

Lancement :
    python 01_research/run_exploration_MR_MNQ.py > 01_research/outputs/run_log.txt 2>&1
"""
from __future__ import annotations

# Backend non-interactif pour savefig sans display (server / pas de GUI)
import matplotlib
matplotlib.use('Agg')

import traceback
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from scipy import stats
import matplotlib.pyplot as plt

pd.set_option('display.max_rows', 50)
pd.set_option('display.float_format', '{:.4f}'.format)
np.set_printoptions(precision=4, suppress=True)

print('=' * 70)
print('### ENVIRONNEMENT ###')
print('=' * 70)
print(f'numpy   {np.__version__}')
print(f'pandas  {pd.__version__}')
print(f'scipy   {stats.__name__} ok')

# ════════════════════════════════════════════════════════════════════
# CONSTANTES (mirror cell-03-constants du notebook)
# ════════════════════════════════════════════════════════════════════

CSV_PATH = Path(r'C:\Users\ryadb\Downloads\MNQ 5ANS DATA\glbx-mdp3-20210513-20260512.ohlcv-1m.csv.zst')
OUT_DIR  = Path('01_research/outputs')
OUT_DIR.mkdir(parents=True, exist_ok=True)

TRAIN_START   = pd.Timestamp('2021-05-13', tz='UTC')
TRAIN_END     = pd.Timestamp('2024-05-13', tz='UTC')
VALID_START   = TRAIN_END
VALID_END     = pd.Timestamp('2025-05-13', tz='UTC')
HOLDOUT_START = VALID_END
HOLDOUT_END   = pd.Timestamp('2026-05-13', tz='UTC')

COMMISSION_RT   = 1.10
SLIPPAGE_TICKS  = 1
TICK_VALUE_MNQ  = 0.50
POINT_VALUE_MNQ = 2.00
TICK_SIZE_MNQ   = 0.25

HURST_WINDOW    = 50
HURST_MR_THR    = 0.45
ZSCORE_LOOKBACK = 20
ZSCORE_ENTRY    = 2.0
ZSCORE_EXIT     = 0.5

STOP_STD_MULT   = 1.5
STOP_FLOOR_PTS  = 5.0
STOP_CAP_PTS    = 10.0

TIMEOUT_BARS    = 60

print()
print(f'Train   : {TRAIN_START.date()} -> {TRAIN_END.date()}')
print(f'Valid   : {VALID_START.date()} -> {VALID_END.date()}')
print(f'Holdout : {HOLDOUT_START.date()} -> {HOLDOUT_END.date()}  (INTOUCHABLE)')
print()

# ════════════════════════════════════════════════════════════════════
# FONCTIONS PURES
# ════════════════════════════════════════════════════════════════════

def hurst_rs(ts: np.ndarray) -> float:
    """R/S Hurst exponent. Verbatim from pages/5_Backtest.py:150-179."""
    ts = np.asarray(ts, dtype=float)
    n  = len(ts)
    if n < 20:
        return 0.5
    lags = np.unique(np.round(
        np.exp(np.linspace(np.log(4), np.log(min(n // 2, 50)), 12))
    ).astype(int))
    lags = lags[lags >= 4]
    rs_vals = []
    for lag in lags:
        lag = int(lag)
        n_chunks = n // lag
        if n_chunks < 2:
            continue
        mat  = ts[:n_chunks * lag].reshape(n_chunks, lag)
        mean = mat.mean(axis=1, keepdims=True)
        devs = np.cumsum(mat - mean, axis=1)
        R    = devs.max(axis=1) - devs.min(axis=1)
        S    = mat.std(axis=1, ddof=0)
        mask = S > 0
        if mask.sum() == 0:
            continue
        rs_vals.append(float((R[mask] / S[mask]).mean()))
    if len(rs_vals) < 3:
        return 0.5
    try:
        return float(np.clip(
            np.polyfit(np.log(lags[:len(rs_vals)]), np.log(rs_vals), 1)[0],
            0.0, 1.0,
        ))
    except Exception:
        return 0.5


def load_mnq_continuous(path: Path) -> pd.DataFrame:
    """Charge MNQ 5 ans, filtre rollover, retourne DataFrame OHLCV + datetime UTC."""
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
        include_groups=False,
    ).reset_index()
    day_sym.columns = ['date','dominant']
    day_sym['prev'] = day_sym['dominant'].shift(1)
    day_sym['roll'] = (day_sym['dominant'] != day_sym['prev']) & day_sym['prev'].notna()
    day_sym['roll'] = (day_sym['roll'] | day_sym['roll'].shift(-1)).fillna(False).astype(bool)
    roll_dates = set(day_sym.loc[day_sym['roll'], 'date'].astype(str))
    df['is_roll'] = df['date'].astype(str).isin(roll_dates)
    df = df[~df['is_roll']].drop(columns=['is_roll','symbol']).reset_index(drop=True)
    df = df.set_index('bar').sort_index()
    return df[['open','high','low','close','volume']]


def compute_rolling_hurst_by_session(df: pd.DataFrame, hwin: int = HURST_WINDOW) -> pd.Series:
    """Hurst rolling par session (sans look-ahead), reset chaque jour."""
    out = np.full(len(df), np.nan)
    closes = df['close'].values.astype(float)
    dates  = df['date'].values
    day_starts = np.where(np.concatenate([[True], dates[1:] != dates[:-1]]))[0]
    day_starts = np.append(day_starts, len(df))
    for k in range(len(day_starts) - 1):
        a, b = day_starts[k], day_starts[k+1]
        if b - a < hwin + 2:
            continue
        sess_close = closes[a:b]
        sess_rets  = np.diff(np.log(np.maximum(sess_close, 1e-9)))
        sess_rets  = np.concatenate([[0.0], sess_rets])
        for i in range(hwin, b - a):
            out[a + i] = hurst_rs(sess_rets[i - hwin: i])
    return pd.Series(out, index=df.index, name='hurst')


def compute_signal_features(df: pd.DataFrame, lookback: int = ZSCORE_LOOKBACK) -> pd.DataFrame:
    """Calcule z-score sur fenetre lookback rolling. PAS d'ATR."""
    out = df.copy()
    closes = out['close']
    out['mid']    = closes.rolling(lookback).mean()
    out['std']    = closes.rolling(lookback).std(ddof=0)
    out['zscore'] = (closes - out['mid']) / out['std'].replace(0, np.nan)
    return out


def generate_mr_signals(df: pd.DataFrame, zscore_entry: float = ZSCORE_ENTRY,
                        allowed_hours: Optional[set] = None) -> pd.DataFrame:
    """Genere les barres de signal MR minimal."""
    out = df.copy()
    out['signal'] = 0
    in_pocket = (out['hour_ny'].isin(allowed_hours)) if allowed_hours else True
    valid = out['zscore'].notna() & out['std'].notna() & (out['std'] > 0) & in_pocket
    out.loc[valid & (out['zscore'] >  zscore_entry), 'signal'] = -1
    out.loc[valid & (out['zscore'] < -zscore_entry), 'signal'] = +1
    return out


def backtest_tick_realistic(df_signals: pd.DataFrame,
                            stop_std_mult: float = STOP_STD_MULT,
                            stop_floor_pts: float = STOP_FLOOR_PTS,
                            stop_cap_pts: float = STOP_CAP_PTS,
                            zscore_exit: float = ZSCORE_EXIT,
                            slippage_ticks: int = SLIPPAGE_TICKS,
                            commission_rt: float = COMMISSION_RT,
                            timeout_bars: int = TIMEOUT_BARS) -> pd.DataFrame:
    """Backtest event-driven : SL sur wicks high/low, TP dynamique sur z-score."""
    df = df_signals.reset_index().copy()
    n  = len(df)
    trades = []
    i = 0
    while i < n - 1:
        sig = df.at[i, 'signal']
        if sig == 0 or pd.isna(df.at[i, 'std']) or df.at[i, 'std'] <= 0 or pd.isna(df.at[i, 'mid']):
            i += 1
            continue
        direction   = int(sig)
        entry_price = df.at[i, 'close']
        std_i       = df.at[i, 'std']
        sl_pts   = max(stop_floor_pts, min(stop_cap_pts, stop_std_mult * std_i))
        sl_price = entry_price - direction * sl_pts
        slip_pts = slippage_ticks * TICK_SIZE_MNQ
        result_pts = 0.0
        exit_reason = 'timeout'
        exit_idx = min(i + timeout_bars, n - 1)
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
            z_j = df.at[j, 'zscore']
            if pd.notna(z_j):
                tp_touched = (direction == 1 and z_j >= -zscore_exit) or \
                             (direction == -1 and z_j <= zscore_exit)
                if tp_touched:
                    exit_price = df.at[j, 'close']
                    result_pts = direction * (exit_price - entry_price)
                    exit_reason = 'TP_zscore'
                    exit_idx = j
                    break
        else:
            exit_price = df.at[exit_idx, 'close']
            result_pts = direction * (exit_price - entry_price)
        pnl_usd = result_pts * POINT_VALUE_MNQ - commission_rt
        trades.append({
            'entry_time':   df.at[i, 'bar'],
            'exit_time':    df.at[exit_idx, 'bar'],
            'direction':    'LONG' if direction == 1 else 'SHORT',
            'entry_price':  entry_price,
            'exit_price':   exit_price,
            'sl_price':     sl_price,
            'sl_pts':       sl_pts,
            'std_i':        std_i,
            'pts':          result_pts,
            'pnl_usd':      pnl_usd,
            'exit_reason':  exit_reason,
            'bars_held':    exit_idx - i,
            'hour_ny':      df.at[i, 'hour_ny'],
            'month':        df.at[i, 'month'],
            'dow':          df.at[i, 'dow'],
        })
        i = exit_idx + 1
    return pd.DataFrame(trades)


def compute_trade_metrics(trades: pd.DataFrame) -> dict:
    """Metriques agregees d'un ensemble de trades."""
    if len(trades) == 0:
        return dict(trades=0, pf=0.0, sharpe=0.0, max_dd=0.0, wr=0.0, pnl=0.0, avg_trade=0.0)
    pnl = trades['pnl_usd']
    pos = pnl[pnl > 0].sum()
    neg = abs(pnl[pnl < 0].sum())
    pf  = pos / neg if neg > 0 else np.inf
    wr  = (pnl > 0).mean()
    eq  = pnl.cumsum()
    peak = eq.cummax()
    dd  = (eq - peak)
    max_dd = float(dd.min())
    sharpe = pnl.mean() / pnl.std() * np.sqrt(252) if pnl.std() > 0 else 0
    return dict(
        trades=len(trades), pf=pf, sharpe=sharpe, max_dd=max_dd,
        wr=wr, pnl=pnl.sum(), avg_trade=pnl.mean(),
    )


def emit_verdict(pocket_hours: set, train_metrics: dict, valid_metrics: dict,
                 max_dd_6m_usd: float, valid_trades: int) -> None:
    """A appeler manuellement apres lecture des resultats (BB tranche en dernier)."""
    print('=' * 70)
    print('VERDICT EXPLORATION MR-MNQ')
    print('=' * 70)
    print(f'Poche identifiee : heures NY {sorted(pocket_hours)}')
    print()
    print(f'Train  : PF {train_metrics.get("pf", 0):.2f} · Sharpe {train_metrics.get("sharpe", 0):.2f} '
          f'· MaxDD ${train_metrics.get("max_dd", 0):,.0f} · WR {train_metrics.get("wr", 0)*100:.1f}% '
          f'· {train_metrics.get("trades", 0)} trades')
    print(f'Valid  : PF {valid_metrics.get("pf", 0):.2f} · Sharpe {valid_metrics.get("sharpe", 0):.2f} '
          f'· MaxDD ${valid_metrics.get("max_dd", 0):,.0f} · WR {valid_metrics.get("wr", 0)*100:.1f}% '
          f'· {valid_metrics.get("trades", 0)} trades')
    print()
    ok_pf      = valid_metrics.get('pf', 0) > 1.5
    ok_sharpe  = valid_metrics.get('sharpe', 0) > 1.0
    ok_dd      = abs(max_dd_6m_usd) < 1500
    ok_trades  = valid_trades >= 100
    print(f'  PF > 1.5         : {"OK" if ok_pf else "KO"} (Valid {valid_metrics.get("pf", 0):.2f})')
    print(f'  Sharpe > 1       : {"OK" if ok_sharpe else "KO"} (Valid {valid_metrics.get("sharpe", 0):.2f})')
    print(f'  DD 6m < $1500    : {"OK" if ok_dd else "KO"} (max ${max_dd_6m_usd:,.0f})')
    print(f'  Trades Valid >=100: {"OK" if ok_trades else "KO"} ({valid_trades})')
    print()
    if ok_pf and ok_sharpe and ok_dd and ok_trades:
        print('>>> PROMOTION VERS ETAPE 2 — Construction backtester Python NT8-compatible')
    else:
        print('>>> PAS DEDGE — Pivoter : autre instrument ? Autre famille de strategie ?')
    print('=' * 70)


# ════════════════════════════════════════════════════════════════════
# SECTION 1 — CHARGEMENT DONNEES
# ════════════════════════════════════════════════════════════════════

df_session = None
print('=' * 70)
print('### SECTION 1 — CHARGEMENT DONNEES MNQ 5 ans ###')
print('=' * 70)
try:
    df_mnq = load_mnq_continuous(CSV_PATH)
    print(f'Bars charges : {len(df_mnq):,}')
    print(f'Periode     : {df_mnq.index[0]} -> {df_mnq.index[-1]}')

    # Colonnes temporelles + filtre session NY 9h30-16h
    df_mnq['ts_ny']   = df_mnq.index.tz_convert('America/New_York')
    df_mnq['hour_ny'] = df_mnq['ts_ny'].dt.hour
    df_mnq['min_ny']  = df_mnq['ts_ny'].dt.minute
    df_mnq['month']   = df_mnq.index.month
    df_mnq['dow']     = df_mnq.index.dayofweek
    df_mnq['date']    = df_mnq.index.date

    t_ny = df_mnq['hour_ny'] * 60 + df_mnq['min_ny']
    session_mask = (t_ny >= 9*60+30) & (t_ny < 16*60)
    df_session = df_mnq[session_mask].copy()
    print(f'Bars en session NY 9h30-16h : {len(df_session):,}')
except Exception as e:
    print(f'[ERROR SECTION 1] {type(e).__name__}: {e}')
    traceback.print_exc()


# ════════════════════════════════════════════════════════════════════
# SECTION 2 — HURST ROLLING
# ════════════════════════════════════════════════════════════════════

print()
print('=' * 70)
print('### SECTION 2 — HURST ROLLING (5-15 min attendus) ###')
print('=' * 70)
try:
    if df_session is None:
        raise RuntimeError('df_session non disponible (section 1 a echoue)')
    print(f'Lancement compute_rolling_hurst_by_session(hwin={HURST_WINDOW}) sur {len(df_session):,} bars...')
    import time
    t0 = time.time()
    df_session['hurst'] = compute_rolling_hurst_by_session(df_session, HURST_WINDOW)
    elapsed = time.time() - t0
    valid_h = df_session['hurst'].notna().sum()
    print(f'Termine en {elapsed:.1f}s ({elapsed/60:.1f} min). H calcule pour {valid_h:,} / {len(df_session):,} bars.')
    print()
    print('Statistiques globales H :')
    print(df_session['hurst'].describe())
except Exception as e:
    print(f'[ERROR SECTION 2] {type(e).__name__}: {e}')
    traceback.print_exc()


# ════════════════════════════════════════════════════════════════════
# SECTION 3 — DISTRIBUTION H PAR DIMENSION
# ════════════════════════════════════════════════════════════════════

h_by_hour = h_by_month = h_by_dow = None
df_tv = None
print()
print('=' * 70)
print('### SECTION 3 — DISTRIBUTION H PAR HEURE/MOIS/JOUR ###')
print('=' * 70)
try:
    mask_tv = (df_session.index >= TRAIN_START) & (df_session.index < HOLDOUT_START)
    df_tv = df_session.loc[mask_tv & df_session['hurst'].notna()].copy()
    print(f'Bars Train+Valid avec H : {len(df_tv):,}')
    print(f'Bars Holdout (reserves) : {(df_session.index >= HOLDOUT_START).sum():,}')

    def hurst_summary_by(group_col: str, label: str) -> pd.DataFrame:
        g = df_tv.groupby(group_col)['hurst']
        summary = g.agg(['mean', 'std', 'count']).copy()
        summary['t_stat'] = (summary['mean'] - 0.5) / (summary['std'] / np.sqrt(summary['count']))
        summary['p_value'] = 2 * (1 - stats.norm.cdf(np.abs(summary['t_stat'])))
        summary['mr_significant'] = (summary['mean'] < HURST_MR_THR) & (summary['p_value'] < 0.01)
        summary.index.name = label
        return summary

    # 3.1 par heure NY
    h_by_hour = hurst_summary_by('hour_ny', 'hour_ny').sort_index()
    print()
    print('--- Hurst par heure NY (Train+Valid) ---')
    print(h_by_hour)
    h_by_hour.to_csv(OUT_DIR / 'h_by_hour.csv')
    print(f'-> sauvegarde {OUT_DIR / "h_by_hour.csv"}')

    # 3.2 par mois
    h_by_month = hurst_summary_by('month', 'month')
    print()
    print('--- Hurst par mois calendaire (Train+Valid) ---')
    print(h_by_month)
    h_by_month.to_csv(OUT_DIR / 'h_by_month.csv')
    print(f'-> sauvegarde {OUT_DIR / "h_by_month.csv"}')

    # 3.3 par jour de semaine
    h_by_dow = hurst_summary_by('dow', 'dow')
    dow_labels = {0:'Lundi', 1:'Mardi', 2:'Mercredi', 3:'Jeudi', 4:'Vendredi'}
    h_by_dow.index = [dow_labels.get(i, str(i)) for i in h_by_dow.index]
    print()
    print('--- Hurst par jour de semaine (Train+Valid) ---')
    print(h_by_dow)
    h_by_dow.to_csv(OUT_DIR / 'h_by_dow.csv')
    print(f'-> sauvegarde {OUT_DIR / "h_by_dow.csv"}')

    # Plots
    fig, axes = plt.subplots(1, 3, figsize=(18, 4))
    axes[0].bar(h_by_hour.index, h_by_hour['mean'], yerr=h_by_hour['std']/np.sqrt(h_by_hour['count']))
    axes[0].axhline(0.5, color='red', linestyle='--', label='H=0.5 (random walk)')
    axes[0].axhline(HURST_MR_THR, color='green', linestyle='--', label=f'H={HURST_MR_THR} (seuil MR exploitable)')
    axes[0].set_title('Hurst moyen par heure NY')
    axes[0].set_xlabel('Heure NY locale'); axes[0].set_ylabel('H')
    axes[0].legend()

    axes[1].bar(h_by_month.index, h_by_month['mean'], yerr=h_by_month['std']/np.sqrt(h_by_month['count']))
    axes[1].axhline(0.5, color='red', linestyle='--')
    axes[1].axhline(HURST_MR_THR, color='green', linestyle='--')
    axes[1].set_title('Hurst moyen par mois calendaire')
    axes[1].set_xlabel('Mois'); axes[1].set_ylabel('H')

    axes[2].bar(range(len(h_by_dow)), h_by_dow['mean'], yerr=h_by_dow['std']/np.sqrt(h_by_dow['count']))
    axes[2].set_xticks(range(len(h_by_dow))); axes[2].set_xticklabels(h_by_dow.index)
    axes[2].axhline(0.5, color='red', linestyle='--')
    axes[2].axhline(HURST_MR_THR, color='green', linestyle='--')
    axes[2].set_title('Hurst moyen par jour de semaine')
    axes[2].set_ylabel('H')

    plt.tight_layout()
    plt.savefig(OUT_DIR / 'hurst_distribution.png', dpi=150, bbox_inches='tight')
    plt.close()
    print(f'-> sauvegarde {OUT_DIR / "hurst_distribution.png"}')
except Exception as e:
    print(f'[ERROR SECTION 3] {type(e).__name__}: {e}')
    traceback.print_exc()


# ════════════════════════════════════════════════════════════════════
# SECTION 4 — POCHES MR EXPLOITABLES (H < 0.45 ET p < 0.01)
# ════════════════════════════════════════════════════════════════════

print()
print('=' * 70)
print(f'### SECTION 4 — POCHES MR EXPLOITABLES (H<{HURST_MR_THR}, p<0.01) ###')
print('=' * 70)
try:
    if h_by_hour is None:
        raise RuntimeError('h_by_hour non disponible (section 3 a echoue)')
    print()
    print('--- Heures MR significatives ---')
    pockets_hour = h_by_hour[h_by_hour['mr_significant']].sort_values('mean')
    print(pockets_hour if len(pockets_hour) else '(aucune)')
    print()
    print('--- Mois MR significatifs ---')
    pockets_month = h_by_month[h_by_month['mr_significant']].sort_values('mean')
    print(pockets_month if len(pockets_month) else '(aucun)')
    print()
    print('--- Jours MR significatifs ---')
    pockets_dow = h_by_dow[h_by_dow['mr_significant']].sort_values('mean')
    print(pockets_dow if len(pockets_dow) else '(aucun)')
except Exception as e:
    print(f'[ERROR SECTION 4] {type(e).__name__}: {e}')
    traceback.print_exc()


# ════════════════════════════════════════════════════════════════════
# SECTION 5 — SPLITS TRAIN/VALID/HOLDOUT + FEATURES SIGNAL
# ════════════════════════════════════════════════════════════════════

df_train = df_valid = df_holdout = None
print()
print('=' * 70)
print('### SECTION 5 — SPLITS + FEATURES SIGNAL ###')
print('=' * 70)
try:
    df_sig = compute_signal_features(df_session.copy())
    mask_train   = (df_sig.index >= TRAIN_START)   & (df_sig.index < TRAIN_END)
    mask_valid   = (df_sig.index >= VALID_START)   & (df_sig.index < VALID_END)
    mask_holdout = (df_sig.index >= HOLDOUT_START) & (df_sig.index < HOLDOUT_END)
    df_train   = df_sig.loc[mask_train].copy()
    df_valid   = df_sig.loc[mask_valid].copy()
    df_holdout = df_sig.loc[mask_holdout].copy()
    print(f'Train   : {len(df_train):,} bars  · {df_train.index[0]} -> {df_train.index[-1]}')
    print(f'Valid   : {len(df_valid):,} bars  · {df_valid.index[0]} -> {df_valid.index[-1]}')
    print(f'Holdout : {len(df_holdout):,} bars  · INTOUCHABLE')
except Exception as e:
    print(f'[ERROR SECTION 5] {type(e).__name__}: {e}')
    traceback.print_exc()


# ════════════════════════════════════════════════════════════════════
# SECTION 6 — BACKTEST PAR HEURE NY (Train)
# ════════════════════════════════════════════════════════════════════

results_hour_df = None
print()
print('=' * 70)
print('### SECTION 6 — BACKTEST PAR HEURE NY (Train uniquement) ###')
print('=' * 70)
try:
    if df_train is None:
        raise RuntimeError('df_train non disponible (section 5 a echoue)')
    results_hour = []
    for h in sorted(df_train['hour_ny'].dropna().unique()):
        sigs = generate_mr_signals(df_train, allowed_hours={int(h)})
        trades = backtest_tick_realistic(sigs)
        m = compute_trade_metrics(trades)
        m['hour'] = int(h)
        results_hour.append(m)
        print(f'  hour={int(h):2d} : trades={m["trades"]:>5} | PF={m["pf"]:.2f} | Sharpe={m["sharpe"]:.2f} | DD=${m["max_dd"]:,.0f} | WR={m["wr"]*100:.1f}% | PnL=${m["pnl"]:+,.0f}')
    results_hour_df = pd.DataFrame(results_hour).sort_values('pf', ascending=False)
    print()
    print('--- Resultats par heure (tries par PF decroissant) ---')
    print(results_hour_df[['hour','trades','pf','sharpe','max_dd','wr','pnl','avg_trade']])
    results_hour_df.to_csv(OUT_DIR / 'results_hour_train.csv', index=False)
    print(f'-> sauvegarde {OUT_DIR / "results_hour_train.csv"}')
except Exception as e:
    print(f'[ERROR SECTION 6] {type(e).__name__}: {e}')
    traceback.print_exc()


# ════════════════════════════════════════════════════════════════════
# SECTION 7 — BACKTEST PAR MOIS CALENDAIRE (Train)
# ════════════════════════════════════════════════════════════════════

results_month_df = None
print()
print('=' * 70)
print('### SECTION 7 — BACKTEST PAR MOIS CALENDAIRE (Train uniquement) ###')
print('=' * 70)
try:
    if df_train is None:
        raise RuntimeError('df_train non disponible')
    results_month = []
    for m_num in range(1, 13):
        sigs = generate_mr_signals(df_train, allowed_hours=None)
        sigs_m = sigs[sigs['month'] == m_num].copy()
        trades = backtest_tick_realistic(sigs_m)
        m_metrics = compute_trade_metrics(trades)
        m_metrics['month'] = m_num
        results_month.append(m_metrics)
        print(f'  mois={m_num:2d} : trades={m_metrics["trades"]:>5} | PF={m_metrics["pf"]:.2f} | Sharpe={m_metrics["sharpe"]:.2f} | DD=${m_metrics["max_dd"]:,.0f} | WR={m_metrics["wr"]*100:.1f}% | PnL=${m_metrics["pnl"]:+,.0f}')
    results_month_df = pd.DataFrame(results_month).sort_values('pf', ascending=False)
    print()
    print('--- Resultats par mois (tries par PF decroissant) ---')
    print(results_month_df[['month','trades','pf','sharpe','max_dd','wr','pnl','avg_trade']])
    results_month_df.to_csv(OUT_DIR / 'results_month_train.csv', index=False)
    print(f'-> sauvegarde {OUT_DIR / "results_month_train.csv"}')
except Exception as e:
    print(f'[ERROR SECTION 7] {type(e).__name__}: {e}')
    traceback.print_exc()


# ════════════════════════════════════════════════════════════════════
# SECTION 8 — IDENTIFICATION HEURES PROMETTEUSES + VALIDATION SUR VALID
# ════════════════════════════════════════════════════════════════════

print()
print('=' * 70)
print('### SECTION 8 — PROMOTION HEURES + VALIDATION VALID ###')
print('=' * 70)
try:
    if results_hour_df is None or df_valid is None:
        raise RuntimeError('results_hour_df ou df_valid non disponible')
    TRAIN_PF_THR     = 1.5
    TRAIN_SHARPE_THR = 1.0
    TRAIN_MIN_TRADES = 100
    promising = results_hour_df[
        (results_hour_df['pf'] > TRAIN_PF_THR)
        & (results_hour_df['sharpe'] > TRAIN_SHARPE_THR)
        & (results_hour_df['trades'] >= TRAIN_MIN_TRADES)
    ].copy()
    print(f'Seuils Train : PF>{TRAIN_PF_THR} ET Sharpe>{TRAIN_SHARPE_THR} ET trades>={TRAIN_MIN_TRADES}')
    print(f'Heures prometteuses sur Train : {len(promising)}')
    if len(promising) > 0:
        print(promising[['hour','trades','pf','sharpe','max_dd','wr','pnl']])
        promising.to_csv(OUT_DIR / 'promising_hours_train.csv', index=False)
        print(f'-> sauvegarde {OUT_DIR / "promising_hours_train.csv"}')

        pocket_hours = set(promising['hour'].astype(int).tolist())
        print()
        print(f'Validation poche {sorted(pocket_hours)} sur Valid...')
        sigs_v = generate_mr_signals(df_valid, allowed_hours=pocket_hours)
        trades_v = backtest_tick_realistic(sigs_v)
        m_v = compute_trade_metrics(trades_v)
        print(f'Valid : trades={m_v["trades"]} | PF={m_v["pf"]:.2f} | Sharpe={m_v["sharpe"]:.2f} | DD=${m_v["max_dd"]:,.0f} | WR={m_v["wr"]*100:.1f}% | PnL=${m_v["pnl"]:+,.0f}')
        if len(trades_v) > 0:
            trades_v.to_csv(OUT_DIR / 'trades_valid.csv', index=False)
            print(f'-> sauvegarde {OUT_DIR / "trades_valid.csv"}')
    else:
        print('Aucune heure prometteuse sur Train — pas de validation a faire.')
        pocket_hours = set()
        m_v = compute_trade_metrics(pd.DataFrame())
except Exception as e:
    print(f'[ERROR SECTION 8] {type(e).__name__}: {e}')
    traceback.print_exc()


# ════════════════════════════════════════════════════════════════════
# VERDICT FINAL — non appele automatiquement (BB tranche apres lecture)
# ════════════════════════════════════════════════════════════════════

print()
print('=' * 70)
print('### FIN EXECUTION — verdict NON appele (a faire manuellement apres lecture) ###')
print('=' * 70)
print()
print('Pour appeler le verdict :')
print('    emit_verdict(pocket_hours, train_metrics_consolidated, m_v, max_dd_6m_usd, valid_trades=m_v["trades"])')
print()
print('Fichiers generes dans 01_research/outputs/ :')
for p in sorted(OUT_DIR.iterdir()):
    print(f'  - {p.name}')
print()
print('=' * 70)
