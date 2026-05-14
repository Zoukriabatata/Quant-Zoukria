"""
A/B Test : v9 baseline (C0) vs v10 (C_GZadapt) sur les 6 derniers mois MNQ.

But : valider que le port C# NinjaTrader ne dérive pas de la simulation Python.

Output :
    1. Tableau comparatif des métriques (PnL, PF, Sharpe, DD, mois bustés)
    2. Liste trade-par-trade des divergences (v9 a tradé / v10 a skippé)
    3. Distribution du shrinkage GZ par mois (à quel point GZ a réduit le sizing)
    4. Rapport markdown : quant_v10/reports/ab_compare_v9_vs_v10.md

Usage :
    python -m quant_v10.orchestrator.ab_compare_v9_v10 [--max-days N]
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import timedelta

import numpy as np
import pandas as pd

from quant_v10.orchestrator.runner_v10 import (
    V10Config, build_day_cache, enrich_day_cache,
    run_backtest_v10, compute_metrics,
)


def run_ab_comparison(csv_path: str, last_n_days: int = 126):
    """
    Lance v9 (C0_baseline) vs v10 (C_GZadapt) sur les `last_n_days` derniers
    jours du CSV et compare ligne par ligne.

    `last_n_days = 126` ≈ 6 mois trading (252 jours / 2).
    """
    print("=" * 70)
    print(f"A/B TEST v9 (C0) vs v10 (C_GZadapt) — {last_n_days} derniers jours")
    print("=" * 70)

    t0 = time.time()
    print(f"\n[1/3] Loading day_cache from {csv_path} ...")
    # On charge TOUT pour récupérer le dernier segment de l'historique
    day_cache_full = build_day_cache(csv_path, sh=9, sm=30, eh=16, em=0, hwin=50)
    print(f"      {len(day_cache_full)} jours total chargés en {time.time()-t0:.1f}s")

    # Garde uniquement les `last_n_days` derniers jours
    sorted_keys = sorted(day_cache_full.keys())
    keep_keys = sorted_keys[-last_n_days:]
    day_cache_base = {k: day_cache_full[k] for k in keep_keys}
    print(f"      Echantillon final : {len(day_cache_base)} jours "
          f"({keep_keys[0]} -> {keep_keys[-1]})")

    # ── [2/3] Run v9 baseline + v10 GZ adaptatif ──────────
    print(f"\n[2/3] Backtests v9 et v10 sur même echantillon ...")

    configs = [
        V10Config(name="v9_baseline"),
        V10Config(name="v10_GZadapt", use_gz_adaptive=True),
    ]

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
              f"Sharpe {metrics['sharpe']:.2f}, DD intra ${metrics['dd_max_intramonth_dollars']:.0f}, "
              f"bust {metrics['n_busted_months']} ({time.time()-ts:.1f}s)")

    # ── [3/3] Analyse comparative ─────────────────────────
    print(f"\n[3/3] Analyse comparative ...")

    v9 = all_trades["v9_baseline"]
    v10 = all_trades["v10_GZadapt"]

    # 3.1 Comparaison sizing trade-par-trade
    # Match les trades par (date, hour, direction) pour identifier ceux communs
    if not v9.empty and not v10.empty:
        v9_key = v9[["date", "hour", "direction"]].apply(
            lambda r: f"{r['date']}|{r['hour']}|{r['direction']}", axis=1
        )
        v10_key = v10[["date", "hour", "direction"]].apply(
            lambda r: f"{r['date']}|{r['hour']}|{r['direction']}", axis=1
        )
        v9["key"] = v9_key
        v10["key"] = v10_key

        common = set(v9["key"]) & set(v10["key"])
        only_v9 = set(v9["key"]) - set(v10["key"])
        only_v10 = set(v10["key"]) - set(v9["key"])

        print(f"\nTrade matching :")
        print(f"  Trades communs (mêmes timing) : {len(common)}")
        print(f"  v9 seul (v10 a skip)           : {len(only_v9)}")
        print(f"  v10 seul (v9 a skip)           : {len(only_v10)}")

        # 3.2 Sur les trades communs : compare le sizing (contracts)
        if common:
            v9_sub = v9[v9["key"].isin(common)].set_index("key")
            v10_sub = v10[v10["key"].isin(common)].set_index("key")
            joined = v9_sub.join(v10_sub, rsuffix="_v10")
            # Trades où v10 a réduit le sizing vs v9
            joined["size_diff"] = joined["contracts_v10"] - joined["contracts"]
            shrink_count = (joined["size_diff"] < 0).sum()
            same_count = (joined["size_diff"] == 0).sum()
            avg_shrink_ratio = (joined["contracts_v10"] / joined["contracts"].clip(lower=1)).mean()
            print(f"\nSizing comparison (sur trades communs) :")
            print(f"  v10 < v9 (shrink active)  : {shrink_count} ({shrink_count/len(common)*100:.1f}%)")
            print(f"  v10 = v9 (peak / no DD)   : {same_count} ({same_count/len(common)*100:.1f}%)")
            print(f"  Ratio moyen contracts v10/v9 : {avg_shrink_ratio:.3f}")

    # ── Comparaison métriques ─────────────────────────────
    print(f"\n{'='*70}")
    print("METRIQUES COMPAREES")
    print("=" * 70)
    comp_df = pd.DataFrame({
        "v9_baseline": all_metrics["v9_baseline"],
        "v10_GZadapt": all_metrics["v10_GZadapt"],
    }).T
    # Calcule deltas v10 vs v9
    delta_pnl = (all_metrics["v10_GZadapt"]["pnl"] / max(abs(all_metrics["v9_baseline"]["pnl"]), 1e-6) - 1) * 100
    delta_dd = (all_metrics["v10_GZadapt"]["dd_max_intramonth_dollars"]
                / max(all_metrics["v9_baseline"]["dd_max_intramonth_dollars"], 1e-6) - 1) * 100
    delta_sharpe = all_metrics["v10_GZadapt"]["sharpe"] - all_metrics["v9_baseline"]["sharpe"]
    delta_busted = all_metrics["v10_GZadapt"]["n_busted_months"] - all_metrics["v9_baseline"]["n_busted_months"]

    print(comp_df.to_string())
    print(f"\nDeltas v10 vs v9 :")
    print(f"  PnL          : {delta_pnl:+.1f}%")
    print(f"  DD intra-mois: {delta_dd:+.1f}%")
    print(f"  Sharpe       : {delta_sharpe:+.2f}")
    print(f"  Busted months: {delta_busted:+d}")

    # ── Génère rapport markdown ──────────────────────────
    out_path = "quant_v10/reports/ab_compare_v9_vs_v10.md"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"# A/B Test v9 vs v10 (GZ adaptatif)\n\n")
        f.write(f"**Date** : {time.strftime('%Y-%m-%d')}\n")
        f.write(f"**Echantillon** : {len(day_cache_base)} jours "
                f"({keep_keys[0]} -> {keep_keys[-1]})\n\n")
        f.write(f"## Metriques comparees\n\n")
        f.write(comp_df.to_markdown())
        f.write(f"\n\n## Deltas v10 vs v9\n\n")
        f.write(f"| Metrique | v9 | v10 | Delta |\n")
        f.write(f"|----------|------|------|-------|\n")
        f.write(f"| PnL | ${all_metrics['v9_baseline']['pnl']:.0f} | "
                f"${all_metrics['v10_GZadapt']['pnl']:.0f} | {delta_pnl:+.1f}% |\n")
        f.write(f"| DD intra-mois | ${all_metrics['v9_baseline']['dd_max_intramonth_dollars']:.0f} | "
                f"${all_metrics['v10_GZadapt']['dd_max_intramonth_dollars']:.0f} | {delta_dd:+.1f}% |\n")
        f.write(f"| Sharpe | {all_metrics['v9_baseline']['sharpe']:.2f} | "
                f"{all_metrics['v10_GZadapt']['sharpe']:.2f} | {delta_sharpe:+.2f} |\n")
        f.write(f"| Mois bustes | {all_metrics['v9_baseline']['n_busted_months']} | "
                f"{all_metrics['v10_GZadapt']['n_busted_months']} | {delta_busted:+d} |\n")
        f.write(f"| Mois passes | {all_metrics['v9_baseline']['n_passed_months']} | "
                f"{all_metrics['v10_GZadapt']['n_passed_months']} | "
                f"{all_metrics['v10_GZadapt']['n_passed_months'] - all_metrics['v9_baseline']['n_passed_months']:+d} |\n")
        f.write(f"\n## Verdict\n\n")
        if delta_busted < 0:
            f.write(f"✅ v10 REDUIT le nombre de mois bustes ({delta_busted:+d}) — "
                    f"objectif Apex compliance ATTEINT.\n")
        elif delta_busted == 0:
            if all_metrics["v9_baseline"]["n_busted_months"] == 0:
                f.write(f"⚖️ Aucun bust sur la periode pour les 2 configs — "
                        f"echantillon trop court pour differencier.\n")
            else:
                f.write(f"⚠️ Meme nombre de mois bustes ({delta_busted}) — "
                        f"l'echantillon ne montre pas la valeur ajoutee de v10.\n")
        else:
            f.write(f"❌ v10 a PLUS de busts que v9 — investigation requise.\n")

    print(f"\nRapport sauvegarde : {out_path}")

    return dict(
        v9_metrics=all_metrics["v9_baseline"],
        v10_metrics=all_metrics["v10_GZadapt"],
        v9_trades=all_trades["v9_baseline"],
        v10_trades=all_trades["v10_GZadapt"],
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-days", type=int, default=126,
                        help="Nombre de jours recents a tester (default 126 = 6 mois)")
    parser.add_argument("--csv", type=str,
                        default=r"C:\Users\ryadb\Downloads\5 ANS DATA MNQ OHLCV M1\glbx-mdp3-20210405-20260404.ohlcv-1m.csv",
                        help="Chemin du CSV MNQ")
    args = parser.parse_args()
    run_ab_comparison(args.csv, last_n_days=args.max_days)
