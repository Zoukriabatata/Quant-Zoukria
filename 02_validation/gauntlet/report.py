"""Écriture du rapport gauntlet : markdown lisible + CSVs traçables.

Outputs dans <out_dir>/ :
  gauntlet_report.md    — le verdict + stats par bloc, pour BB.
  ranking.csv           — métriques par variant de la grille.
  pa_account_trace.csv  — clôtures journalières + tier + seuil DD EOD reconstruit.
  walk_forward.csv      — la table walk-forward brute.
  cpcv_distribution.csv — la distribution des Sharpe OOS du CPCV.
  run_log.txt           — résumé une-ligne du run.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from gauntlet.pa_rules import ACCOUNT_SIZE, EOD_DD, EOD_THRESHOLD_LOCK


def _reconstruct_threshold_trace(daily_history: list) -> pd.DataFrame:
    """Reconstruit la trajectoire du seuil DD EOD depuis les clôtures journalières.

    seuil[i] = min(plus_haute_clôture_jusqu'à_i - EOD_DD, EOD_THRESHOLD_LOCK). Le PaAccount
    ne stocke pas le seuil jour par jour, mais il est déterministe à partir des clôtures.

    Args:
        daily_history: [(date, eod_close_balance, tier), ...] de PaAccount.

    Returns:
        DataFrame [date, eod_close_balance, tier, eod_threshold].
    """
    rows = []
    running_max = ACCOUNT_SIZE
    for date, eod_close, tier in daily_history:
        running_max = max(running_max, eod_close)
        threshold = min(running_max - EOD_DD, EOD_THRESHOLD_LOCK)
        rows.append({"date": date, "eod_close_balance": eod_close, "tier": tier,
                     "eod_threshold": threshold})
    return pd.DataFrame(rows)


def _format_report_md(verdict, outputs: dict) -> str:
    """Construit le corps markdown du rapport."""
    hyp = outputs["hypothesis"]
    fm = outputs["full_metrics"]
    mc = outputs["mc"]
    dd = outputs["dd"]
    cycle = outputs["cycle"]
    hm = outputs["holdout_metrics"]
    cpcv = outputs["cpcv"]

    lines = []
    lines.append(f"# Gauntlet — Verdict : {verdict.verdict}")
    lines.append("")
    lines.append(f"**Hypothèse** : `{hyp.name}` — {hyp.description}  ")
    lines.append(f"**Instrument / TF** : {hyp.instrument} / {hyp.timeframe}  ")
    lines.append(f"**Variants testés (n_trials)** : {hyp.n_trials}  ")
    lines.append(f"**Meilleur variant (sélectionné sur Train)** : `{outputs['best_params']}`")
    lines.append("")

    # ── Table des critères ──────────────────────────────────────
    lines.append("## Critères")
    lines.append("")
    lines.append("| Critère | Valeur | Seuil | Passé | Éliminatoire |")
    lines.append("|---|---|---|:---:|:---:|")
    for c in verdict.criteria:
        val = f"{c.value:.4f}" if isinstance(c.value, float) else str(c.value)
        ok = "✅" if c.passed else "❌"
        hard = "🔴" if c.hard_fail else ""
        lines.append(f"| {c.name} | {val} | {c.threshold} | {ok} | {hard} |")
    lines.append("")
    for c in verdict.criteria:
        lines.append(f"- **{c.name}** : {c.detail}")
    lines.append("")

    # ── Stats par bloc ──────────────────────────────────────────
    lines.append("## Détail par bloc")
    lines.append("")
    lines.append(f"- **Run plein Train+Valid** : {fm['trades']} trades, PF {fm['pf']:.2f}, "
                 f"Sharpe {fm['sharpe']:.2f}, max DD ${fm['max_dd']:.0f}, "
                 f"WR {fm['wr']:.1%}, PnL ${fm['pnl']:.0f}.")
    lines.append(f"- **Walk-forward** : {outputs['wf_summary'].get('n_windows', 0)} fenêtres, "
                 f"{outputs['wf_summary'].get('pct_oos_profitable', 0):.0%} OOS rentables, "
                 f"Sharpe OOS moyen {outputs['wf_summary'].get('oos_sharpe_mean', 0):.2f}.")
    lines.append(f"- **Monte Carlo** : Sharpe observé {mc.get('observed_sharpe', 0):.2f}, "
                 f"p-value {mc.get('p_value', 1):.4f} ({mc.get('n_iter', 0)} permutations).")
    lines.append(f"- **Distribution Max DD** (order-shuffle) : observé "
                 f"${dd.get('observed_max_dd', 0):.0f}, p95 ${dd.get('dd_p95', 0):.0f}, "
                 f"pire ${dd.get('dd_worst', 0):.0f}.")
    if len(cpcv) > 0:
        lines.append(f"- **CPCV** : {len(cpcv)} chemins, Sharpe OOS moyen "
                     f"{float(np.mean(cpcv)):.2f} (écart-type {float(np.std(cpcv)):.2f}).")
    else:
        lines.append("- **CPCV** : pas assez de jours de trading pour générer des chemins.")
    lines.append(f"- **Deflated Sharpe Ratio** : {outputs['dsr']:.4f} "
                 f"(sr_variance {outputs['sr_variance']:.4f}, n_trials {hyp.n_trials}).")
    pbo = outputs["pbo"]
    lines.append(f"- **PBO** : {'N/A (grille à 1 variant)' if pbo is None else f'{pbo:.3f}'}.")
    lines.append(f"- **Cycle PA** : compte {'vivant' if cycle['survived'] else 'MORT'}, "
                 f"lock {'atteint' if cycle['reached_lock'] else 'NON atteint'} "
                 f"(en {cycle['trading_days_to_lock']} jours de trading), "
                 f"inactivité {'OK' if cycle['inactivity_safe'] else 'VIOLÉE'}, "
                 f"balance finale ${cycle['final_balance']:.0f}.")
    lines.append("")

    # ── Stress test ─────────────────────────────────────────────
    lines.append("## Stress test — périodes rouges")
    lines.append("")
    lines.append(outputs["stress"].to_markdown(index=False))
    lines.append("")

    # ── Caveats + next steps ────────────────────────────────────
    lines.append("## Caveats")
    lines.append("")
    for cav in verdict.caveats:
        lines.append(f"- {cav}")
    lines.append("")
    lines.append("## Next steps")
    lines.append("")
    for step in verdict.next_steps:
        lines.append(f"- {step}")
    lines.append("")
    lines.append(f"_Holdout : {hm['trades']} trades, PF {hm['pf']:.2f}, "
                 f"Sharpe {hm['sharpe']:.2f}, PnL ${hm['pnl']:.0f} — confiance dégradée._")
    lines.append("")
    return "\n".join(lines)


def write_gauntlet_report(verdict, outputs: dict, out_dir: str) -> None:
    """Écrit le rapport markdown + les 5 CSVs/logs dans out_dir.

    Args:
        verdict: le Verdict (sortie de build_verdict).
        outputs: dict bundlé par run_gauntlet (hypothesis, wf, mc, dd, cpcv, dsr, pbo,
                 full_metrics, full_account, stress, cycle, holdout_metrics,
                 fulltv_results, best_params, sr_variance, wf_summary).
        out_dir: dossier de destination (créé si absent).
    """
    os.makedirs(out_dir, exist_ok=True)

    # gauntlet_report.md
    md = _format_report_md(verdict, outputs)
    with open(os.path.join(out_dir, "gauntlet_report.md"), "w", encoding="utf-8") as f:
        f.write(md)

    # ranking.csv — une ligne par variant
    ranking_rows = []
    for r in outputs["fulltv_results"]:
        m = r["metrics"]
        ranking_rows.append({
            "params": str(r["params"]),
            "trades": m["trades"], "pf": m["pf"], "sharpe": m["sharpe"],
            "max_dd": m["max_dd"], "wr": m["wr"], "pnl": m["pnl"],
            "avg_trade": m["avg_trade"],
            "is_best": r["params"] == outputs["best_params"],
        })
    pd.DataFrame(ranking_rows).to_csv(os.path.join(out_dir, "ranking.csv"), index=False)

    # pa_account_trace.csv — clôtures + tier + seuil DD reconstruit
    trace = _reconstruct_threshold_trace(outputs["full_account"].daily_history)
    trace.to_csv(os.path.join(out_dir, "pa_account_trace.csv"), index=False)

    # walk_forward.csv
    outputs["wf"].to_csv(os.path.join(out_dir, "walk_forward.csv"), index=False)

    # cpcv_distribution.csv
    pd.DataFrame({"oos_sharpe": np.asarray(outputs["cpcv"], dtype=float)}).to_csv(
        os.path.join(out_dir, "cpcv_distribution.csv"), index=False)

    # run_log.txt
    acc = outputs["full_account"]
    with open(os.path.join(out_dir, "run_log.txt"), "w", encoding="utf-8") as f:
        f.write(f"hypothesis    : {outputs['hypothesis'].name}\n")
        f.write(f"verdict       : {verdict.verdict}\n")
        f.write(f"best_params   : {outputs['best_params']}\n")
        f.write(f"account status: {acc.status}\n")
        f.write(f"hard fails    : {[c.name for c in verdict.hard_fails]}\n")
        f.write(f"n criteria    : {len(verdict.criteria)}\n")
