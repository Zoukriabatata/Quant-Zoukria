"""
Sprint 4.3 — Validation finale des Top configs v10.

Pipeline :
    1. Re-run les 8 configs Sprint 2 sur 5y et capture les trades_df de chacune
    2. Pour chaque config : compute CPCV Sharpe distribution + PSR + DSR
    3. Compute PBO global sur la matrice (T, N) des PnL des 8 configs
    4. Output : reports/v10_champion_validated.md avec verdict final

Critères de validation :
    - DSR > 0.95 → strategy real à 95% confidence (anti-multiple-testing)
    - PBO < 0.50 → ensemble non-overfit
    - CPCV Sharpe mean > 0 ET CPCV Sharpe stdev raisonnable
"""
from __future__ import annotations

import os
import json
import time

import numpy as np
import pandas as pd

from quant_v10.orchestrator.runner_v10 import (
    build_day_cache, enrich_day_cache, run_backtest_v10,
    build_sprint2_full_configs, compute_metrics,
)
from quant_v10.validation.cpcv import sharpe_distribution_cpcv
from quant_v10.validation.deflated_sharpe import (
    probabilistic_sharpe_ratio,
    deflated_sharpe_ratio,
    probability_backtest_overfitting,
)


def run_final_validation(csv_path: str) -> dict:
    print("=" * 70)
    print("SPRINT 4.3 — VALIDATION FINALE")
    print("=" * 70)

    t0 = time.time()
    print(f"\n[1/4] Loading day_cache from {csv_path} ...")
    day_cache_base = build_day_cache(csv_path, sh=9, sm=30, eh=16, em=0, hwin=50)
    print(f"      {len(day_cache_base)} jours chargés en {time.time()-t0:.1f}s")

    configs = build_sprint2_full_configs()
    print(f"\n[2/4] Running {len(configs)} configs + capturing trades ...")

    all_trades = {}
    all_metrics = {}
    for cfg in configs:
        print(f"  - {cfg.name} ...", end=" ", flush=True)
        ts = time.time()
        day_cache = {k: dict(v) for k, v in day_cache_base.items()}
        day_cache = enrich_day_cache(day_cache, cfg)
        trades_df, monthly_df = run_backtest_v10(day_cache, cfg)
        metrics = compute_metrics(trades_df, monthly_df, capital=cfg.capital)
        all_trades[cfg.name] = trades_df
        all_metrics[cfg.name] = metrics
        print(f"{len(trades_df)} trades, PnL ${metrics['pnl']:.0f}, "
              f"Sharpe {metrics['sharpe']:.2f}  ({time.time()-ts:.1f}s)")

    # ── [3/4] Validation par config ───────────────────────
    print(f"\n[3/4] CPCV + PSR + DSR par config ...")
    validation_rows = []
    for name, trades_df in all_trades.items():
        if trades_df.empty:
            continue
        # CPCV : 10 groupes, 2 en test (45 paths)
        cpcv_sharpes = sharpe_distribution_cpcv(
            trades_df, n_groups=10, k_test=2,
            date_col="date", pnl_col="pnl",
        )
        # Aggrégation daily PnL pour PSR/DSR
        daily = trades_df.groupby("date")["pnl"].sum().values
        psr = probabilistic_sharpe_ratio(daily, sr_benchmark=0.0)
        # DSR avec n_trials = nombre de configs testées
        dsr = deflated_sharpe_ratio(daily, n_trials=len(configs), sr_variance=0.3 ** 2)

        validation_rows.append(dict(
            config=name,
            sharpe_full=all_metrics[name]["sharpe"],
            pnl=all_metrics[name]["pnl"],
            n_busted=all_metrics[name]["n_busted_months"],
            n_passed=all_metrics[name]["n_passed_months"],
            cpcv_mean=float(np.mean(cpcv_sharpes)) if len(cpcv_sharpes) > 0 else np.nan,
            cpcv_std=float(np.std(cpcv_sharpes)) if len(cpcv_sharpes) > 0 else np.nan,
            cpcv_n_paths=len(cpcv_sharpes),
            psr=float(psr),
            dsr=float(dsr),
        ))

    val_df = pd.DataFrame(validation_rows).set_index("config")

    # ── [4/4] PBO sur la matrice de PnL daily ─────────────
    print(f"\n[4/4] PBO global sur matrice PnL daily ...")
    # Construit matrice (T_days, N_configs) avec daily PnL
    daily_panel = {}
    for name, trades_df in all_trades.items():
        if trades_df.empty:
            continue
        daily = trades_df.groupby("date")["pnl"].sum()
        daily_panel[name] = daily

    pnl_matrix_df = pd.DataFrame(daily_panel).fillna(0.0)
    pnl_matrix = pnl_matrix_df.values  # (T, N)
    print(f"      Matrix shape: {pnl_matrix.shape}")

    pbo = probability_backtest_overfitting(pnl_matrix, n_splits=10)
    print(f"      PBO global = {pbo:.3f} ({'OVERFIT' if pbo > 0.5 else 'OK'})")

    # ── Verdict champion ──────────────────────────────────
    print("\n" + "=" * 70)
    print("VERDICT")
    print("=" * 70)
    val_df_sorted = val_df.sort_values("dsr", ascending=False)
    print(val_df_sorted.to_string())

    print(f"\nPBO global = {pbo:.3f}")
    if pbo < 0.5:
        # Le champion = meilleur DSR
        champion = val_df_sorted.index[0]
        print(f"\n🏆 CHAMPION v10 = {champion}")
        print(f"   Sharpe full = {val_df_sorted.loc[champion, 'sharpe_full']:.2f}")
        print(f"   PnL = ${val_df_sorted.loc[champion, 'pnl']:.0f}")
        print(f"   DSR = {val_df_sorted.loc[champion, 'dsr']:.3f}")
        print(f"   Bustés = {val_df_sorted.loc[champion, 'n_busted']}")
        print(f"   Passés = {val_df_sorted.loc[champion, 'n_passed']}")
    else:
        print(f"\n⚠️  PBO > 0.5 → ensemble suspect d'overfit. Pas de champion certifié.")
        champion = None

    return dict(
        validation_df=val_df_sorted,
        pbo=pbo,
        champion=champion,
        all_metrics=all_metrics,
    )


if __name__ == "__main__":
    csv = r"C:\Users\ryadb\Downloads\5 ANS DATA MNQ OHLCV M1\glbx-mdp3-20210405-20260404.ohlcv-1m.csv"
    res = run_final_validation(csv)
    # Save report
    out_path = "quant_v10/reports/v10_champion_validated.md"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("# V10 Champion Validation Report\n\n")
        f.write(f"**Date**: 2026-05-13\n")
        f.write(f"**Source data**: MNQ M1 Databento 5y\n\n")
        f.write("## Validation Metrics (per config)\n\n")
        f.write(res["validation_df"].to_markdown())
        f.write(f"\n\n## PBO global = {res['pbo']:.3f}\n")
        if res["champion"]:
            f.write(f"\n## 🏆 CHAMPION = {res['champion']}\n")
        else:
            f.write(f"\n## ⚠️ Pas de champion certifié (PBO > 0.5)\n")
    print(f"\nReport saved to {out_path}")

    # CSV/JSON version
    res["validation_df"].to_csv("quant_v10/reports/v10_validation_summary.csv")
