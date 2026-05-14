"""
forensic_NQ_mr_zscore_15min.py — Analyse approfondie de la seule config "marginale"
du grid screen : NQ x MR Z-score x 15min (pass rate 10.2%, PnL/mois +$118 à 1 contrat).

3 angles :
  1. Décomposition par heure NY
  2. Décomposition LONG vs SHORT (test bias long NDX)
  3. Décomposition contexte (mois PASSED vs BUSTED, etc.)

Sortie : 01_research/outputs/forensic_NQ/forensic_report.md + CSV intermédiaires.
Lecture seule des CSV existants — pas de re-backtest.
"""
from __future__ import annotations
import matplotlib
matplotlib.use('Agg')

import traceback
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

pd.set_option('display.max_rows', 80)
pd.set_option('display.float_format', '{:.4f}'.format)
pd.set_option('display.width', 200)

TRADES_PATH = Path('01_research/outputs/grid_screen/trades_NQ_mr_zscore_15min.csv')
CYCLE_PATH  = Path('01_research/outputs/grid_screen/apex_cycle_NQ_mr_zscore_15min.csv')
OUT_DIR     = Path('01_research/outputs/forensic_NQ')
OUT_DIR.mkdir(parents=True, exist_ok=True)


def main():
    print('=' * 70)
    print('### FORENSIQUE NQ x MR Z-score x 15min ###')
    print('=' * 70)
    print(f'Source trades : {TRADES_PATH}')
    print(f'Source cycle  : {CYCLE_PATH}')
    print()

    trades = pd.read_csv(TRADES_PATH)
    cycle  = pd.read_csv(CYCLE_PATH)
    trades['entry_time'] = pd.to_datetime(trades['entry_time'])
    trades['exit_time']  = pd.to_datetime(trades['exit_time'])
    trades['ym'] = trades['entry_time'].dt.strftime('%Y-%m')

    print(f'Total trades : {len(trades):,}')
    print(f'Total mois   : {len(cycle)} ({cycle["status"].value_counts().to_dict()})')
    print()

    # ════════════════════════════════════════════════════════════════
    # ANGLE 1 — DÉCOMPOSITION PAR HEURE NY
    # ════════════════════════════════════════════════════════════════
    print('=' * 70)
    print('### ANGLE 1 — DÉCOMPOSITION PAR HEURE NY ###')
    print('=' * 70)
    by_hour = trades.groupby('hour_ny').agg(
        n_trades=('pnl_usd', 'count'),
        wr=('pnl_usd', lambda x: (x > 0).mean()),
        avg_pnl=('pnl_usd', 'mean'),
        total_pnl=('pnl_usd', 'sum'),
        wins=('pnl_usd', lambda x: (x > 0).sum()),
        losses=('pnl_usd', lambda x: (x <= 0).sum()),
    ).round(2)
    by_hour['pf'] = (
        trades[trades['pnl_usd'] > 0].groupby('hour_ny')['pnl_usd'].sum() /
        trades[trades['pnl_usd'] < 0].groupby('hour_ny')['pnl_usd'].sum().abs()
    ).fillna(0).round(3)
    print(by_hour.sort_values('total_pnl', ascending=False))
    by_hour.to_csv(OUT_DIR / 'by_hour.csv')
    print()

    # ════════════════════════════════════════════════════════════════
    # ANGLE 2 — DÉCOMPOSITION LONG vs SHORT
    # ════════════════════════════════════════════════════════════════
    print('=' * 70)
    print('### ANGLE 2 — DÉCOMPOSITION LONG vs SHORT (test bias long NDX) ###')
    print('=' * 70)
    by_dir = trades.groupby('direction').agg(
        n_trades=('pnl_usd', 'count'),
        wr=('pnl_usd', lambda x: (x > 0).mean()),
        avg_pnl=('pnl_usd', 'mean'),
        total_pnl=('pnl_usd', 'sum'),
        max_dd=('pnl_usd', lambda x: (x.cumsum() - x.cumsum().cummax()).min()),
    ).round(2)
    by_dir['pf'] = (
        trades[trades['pnl_usd'] > 0].groupby('direction')['pnl_usd'].sum() /
        trades[trades['pnl_usd'] < 0].groupby('direction')['pnl_usd'].sum().abs()
    ).fillna(0).round(3)
    print(by_dir)
    by_dir.to_csv(OUT_DIR / 'by_direction.csv')
    print()
    print(f'Total LONG  : {by_dir.loc["LONG", "n_trades"]} trades | PF {by_dir.loc["LONG","pf"]:.2f} | PnL ${by_dir.loc["LONG","total_pnl"]:,.0f}')
    print(f'Total SHORT : {by_dir.loc["SHORT", "n_trades"]} trades | PF {by_dir.loc["SHORT","pf"]:.2f} | PnL ${by_dir.loc["SHORT","total_pnl"]:,.0f}')

    # Cross : direction x heure NY
    print()
    print('--- Cross : direction x heure NY ---')
    by_dir_hour = trades.groupby(['direction', 'hour_ny'])['pnl_usd'].agg(
        n='count', total='sum', avg='mean', wr=lambda x: (x > 0).mean()
    ).round(2)
    print(by_dir_hour)
    by_dir_hour.to_csv(OUT_DIR / 'by_direction_hour.csv')
    print()

    # ════════════════════════════════════════════════════════════════
    # ANGLE 3 — DÉCOMPOSITION CONTEXTE (PASSED vs BUSTED vs NO_TARGET)
    # ════════════════════════════════════════════════════════════════
    print('=' * 70)
    print('### ANGLE 3 — MOIS PASSED vs BUSTED_DD vs NO_TARGET ###')
    print('=' * 70)
    # Joindre cycle (statut) aux trades par mois
    trades_with_status = trades.merge(cycle[['month', 'status']],
                                      left_on='ym', right_on='month', how='left')
    print(f'\nDistribution status :')
    print(cycle['status'].value_counts())
    print()
    print('--- Stats trades par statut mensuel ---')
    by_status = trades_with_status.groupby('status').agg(
        n_trades=('pnl_usd', 'count'),
        wr=('pnl_usd', lambda x: (x > 0).mean()),
        avg_pnl=('pnl_usd', 'mean'),
        total_pnl=('pnl_usd', 'sum'),
    ).round(2)
    by_status['pf'] = (
        trades_with_status[trades_with_status['pnl_usd'] > 0].groupby('status')['pnl_usd'].sum() /
        trades_with_status[trades_with_status['pnl_usd'] < 0].groupby('status')['pnl_usd'].sum().abs()
    ).fillna(0).round(3)
    print(by_status)
    print()

    # Mois PASSED en détail
    passed_months = cycle[cycle['status'] == 'PASSED'].copy()
    print(f'--- {len(passed_months)} mois PASSED ---')
    print(passed_months[['month', 'final_pnl', 'hwm', 'trades_taken']].to_string(index=False))
    print()

    # Mois BUSTED en détail
    busted = cycle[cycle['status'] == 'BUSTED_DD'].copy()
    print(f'--- {len(busted)} mois BUSTED_DD (top 10 par final_pnl ascendant) ---')
    print(busted[['month', 'final_pnl', 'hwm', 'trades_taken']].sort_values('final_pnl').head(10).to_string(index=False))
    print()

    # Heure NY des trades PASSED vs BUSTED
    print('--- Heure NY trades : PASSED vs BUSTED_DD ---')
    by_status_hour = trades_with_status[trades_with_status['status'].isin(['PASSED', 'BUSTED_DD'])].groupby(
        ['status', 'hour_ny'])['pnl_usd'].agg(
        n='count', total='sum', avg='mean', wr=lambda x: (x > 0).mean()
    ).round(2)
    print(by_status_hour)
    by_status_hour.to_csv(OUT_DIR / 'by_status_hour.csv')
    print()

    # Direction par status
    print('--- Direction par statut mensuel ---')
    by_status_dir = trades_with_status.groupby(['status', 'direction'])['pnl_usd'].agg(
        n='count', total='sum', avg='mean', wr=lambda x: (x > 0).mean()
    ).round(2)
    print(by_status_dir)
    by_status_dir.to_csv(OUT_DIR / 'by_status_direction.csv')
    print()

    # ════════════════════════════════════════════════════════════════
    # ANGLE 4 BONUS — Distribution exit reasons
    # ════════════════════════════════════════════════════════════════
    print('=' * 70)
    print('### BONUS — Exit reasons ###')
    print('=' * 70)
    by_exit = trades.groupby('exit_reason').agg(
        n_trades=('pnl_usd', 'count'),
        avg_pnl=('pnl_usd', 'mean'),
        total_pnl=('pnl_usd', 'sum'),
    ).round(2)
    print(by_exit.sort_values('n_trades', ascending=False))
    print()

    # ════════════════════════════════════════════════════════════════
    # SIMULATIONS WHAT-IF
    # ════════════════════════════════════════════════════════════════
    print('=' * 70)
    print('### SIMULATIONS WHAT-IF (filtres simples) ###')
    print('=' * 70)
    # Trier hours par PnL net descendant, garder top N
    by_hour_sorted = by_hour.sort_values('total_pnl', ascending=False)
    print('\n--- WHAT-IF : LONG-only ---')
    long_only = trades[trades['direction'] == 'LONG'].copy()
    if len(long_only) > 0:
        pnl_lo = long_only['pnl_usd']
        pf_lo = pnl_lo[pnl_lo > 0].sum() / max(abs(pnl_lo[pnl_lo < 0].sum()), 0.01)
        wr_lo = (pnl_lo > 0).mean()
        sharpe_lo = pnl_lo.mean() / pnl_lo.std() * np.sqrt(252) if pnl_lo.std() > 0 else 0
        print(f'  trades={len(long_only)} | PF={pf_lo:.3f} | WR={wr_lo*100:.1f}% | Sharpe={sharpe_lo:.2f} | PnL=${pnl_lo.sum():,.0f}')
    print('\n--- WHAT-IF : SHORT-only ---')
    short_only = trades[trades['direction'] == 'SHORT'].copy()
    if len(short_only) > 0:
        pnl_so = short_only['pnl_usd']
        pf_so = pnl_so[pnl_so > 0].sum() / max(abs(pnl_so[pnl_so < 0].sum()), 0.01)
        wr_so = (pnl_so > 0).mean()
        sharpe_so = pnl_so.mean() / pnl_so.std() * np.sqrt(252) if pnl_so.std() > 0 else 0
        print(f'  trades={len(short_only)} | PF={pf_so:.3f} | WR={wr_so*100:.1f}% | Sharpe={sharpe_so:.2f} | PnL=${pnl_so.sum():,.0f}')

    # Filtre heure : top 3 heures positives
    print('\n--- WHAT-IF : top heures positives uniquement ---')
    positive_hours = by_hour[by_hour['total_pnl'] > 0].index.tolist()
    print(f'Heures avec PnL net positif : {positive_hours}')
    filtered_h = trades[trades['hour_ny'].isin(positive_hours)].copy()
    if len(filtered_h) > 0:
        pnl_f = filtered_h['pnl_usd']
        pf_f = pnl_f[pnl_f > 0].sum() / max(abs(pnl_f[pnl_f < 0].sum()), 0.01)
        wr_f = (pnl_f > 0).mean()
        sharpe_f = pnl_f.mean() / pnl_f.std() * np.sqrt(252) if pnl_f.std() > 0 else 0
        print(f'  trades={len(filtered_h)} | PF={pf_f:.3f} | WR={wr_f*100:.1f}% | Sharpe={sharpe_f:.2f} | PnL=${pnl_f.sum():,.0f}')

    # Combo : LONG-only + top heures positives
    print('\n--- WHAT-IF : LONG-only + heures positives ---')
    filtered_combo = trades[(trades['direction'] == 'LONG') & (trades['hour_ny'].isin(positive_hours))].copy()
    if len(filtered_combo) > 0:
        pnl_c = filtered_combo['pnl_usd']
        pf_c = pnl_c[pnl_c > 0].sum() / max(abs(pnl_c[pnl_c < 0].sum()), 0.01)
        wr_c = (pnl_c > 0).mean()
        sharpe_c = pnl_c.mean() / pnl_c.std() * np.sqrt(252) if pnl_c.std() > 0 else 0
        # Distribution mensuelle
        filtered_combo['ym'] = filtered_combo['entry_time'].dt.strftime('%Y-%m')
        monthly_pnl_combo = filtered_combo.groupby('ym')['pnl_usd'].sum()
        n_months_3k = (monthly_pnl_combo >= 3000).sum()
        n_months_neg2k = (monthly_pnl_combo <= -2000).sum()
        n_months_pos = (monthly_pnl_combo > 0).sum()
        n_total_m = len(monthly_pnl_combo)
        print(f'  trades={len(filtered_combo)} | PF={pf_c:.3f} | WR={wr_c*100:.1f}% | Sharpe={sharpe_c:.2f} | PnL=${pnl_c.sum():,.0f}')
        print(f'  Mois : {n_total_m} total | positifs {n_months_pos} | >=$3K {n_months_3k} | <=-$2K {n_months_neg2k}')

    # Plot equity curves comparées
    print('\n--- Génération plot equity curves ---')
    fig, axes = plt.subplots(1, 2, figsize=(16, 5))
    axes[0].plot(trades['exit_time'], trades['pnl_usd'].cumsum(), label='Toutes directions', color='blue')
    axes[0].plot(long_only['exit_time'], long_only['pnl_usd'].cumsum(), label='LONG only', color='green')
    axes[0].plot(short_only['exit_time'], short_only['pnl_usd'].cumsum(), label='SHORT only', color='red')
    axes[0].set_title('Equity curve : LONG vs SHORT vs ALL')
    axes[0].set_xlabel('Temps'); axes[0].set_ylabel('PnL cumulé ($)')
    axes[0].legend(); axes[0].grid(alpha=0.3)
    axes[1].bar(by_hour.index, by_hour['total_pnl'],
                color=['green' if v > 0 else 'red' for v in by_hour['total_pnl']])
    axes[1].set_title('PnL net par heure NY locale')
    axes[1].set_xlabel('Heure NY'); axes[1].set_ylabel('PnL net ($)')
    axes[1].grid(alpha=0.3, axis='y')
    plt.tight_layout()
    plt.savefig(OUT_DIR / 'equity_long_short_by_hour.png', dpi=150, bbox_inches='tight')
    plt.close()
    print(f'-> {OUT_DIR / "equity_long_short_by_hour.png"}')

    print()
    print('=' * 70)
    print('### FIN FORENSIQUE ###')
    print('=' * 70)
    print(f'Fichiers générés dans {OUT_DIR}/ :')
    for p in sorted(OUT_DIR.iterdir()):
        print(f'  - {p.name}')


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f'[ERROR] {type(e).__name__}: {e}')
        traceback.print_exc()
