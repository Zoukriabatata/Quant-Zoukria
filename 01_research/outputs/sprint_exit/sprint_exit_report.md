# Sprint Re-engineering Exit — Rapport

**Date** : 2026-05-14  
**n_trials** : 16 (8 configs × 2 TF) — budget overfitting pour le DSR Étape 2

## Verdict

🔴 **Aucune config ne passe le gate.** Le gate exige PF > 1.5 ∧ Sharpe > 1.0 ∧ avg_trade > coût RT sur Train Apex-compliant, ET PF ≥ 1.3 sur Valid.

L'edge EOD Reversal n'est pas capturable avant le force-flat 16:00 par le seul levier exit. **Recommandation : acter l'edge EOD Apex-mort, Étape 2 pivote sur une nouvelle hypothèse.**

## Classement complet

| config           | tf    |   train_trades |   train_pf |   train_sharpe |   train_avg_trade | gate_train   | valid_pf   | valid_sharpe   | promoted   |
|:-----------------|:------|---------------:|-----------:|---------------:|------------------:|:-------------|:-----------|:---------------|:-----------|
| C5_time_stop     | 5min  |            604 |       0.87 |          -0.72 |             -2.19 | False        |            |                | False      |
| C0_zscore_0.5    | 5min  |            632 |       0.80 |          -1.41 |             -3.15 | False        |            |                | False      |
| C0_zscore_0.5    | 15min |            180 |       0.77 |          -1.50 |             -4.07 | False        |            |                | False      |
| C1_zscore_1.0    | 15min |            180 |       0.71 |          -2.01 |             -5.10 | False        |            |                | False      |
| C1_zscore_1.0    | 5min  |            634 |       0.70 |          -2.35 |             -4.56 | False        |            |                | False      |
| C7_hybrid        | 5min  |            634 |       0.70 |          -2.43 |             -4.65 | False        |            |                | False      |
| C2_zscore_1.5    | 5min  |            644 |       0.68 |          -2.65 |             -4.55 | False        |            |                | False      |
| C3_fixed_0.75std | 15min |            183 |       0.67 |          -2.74 |             -5.45 | False        |            |                | False      |
| C2_zscore_1.5    | 15min |            180 |       0.65 |          -2.80 |             -5.92 | False        |            |                | False      |
| C5_time_stop     | 15min |            180 |       0.64 |          -2.97 |             -5.85 | False        |            |                | False      |
| C7_hybrid        | 15min |            180 |       0.62 |          -3.23 |             -6.18 | False        |            |                | False      |
| C3_fixed_0.75std | 5min  |            656 |       0.59 |          -3.94 |             -5.67 | False        |            |                | False      |
| C4_fixed_0.40std | 5min  |            679 |       0.45 |          -5.95 |             -6.61 | False        |            |                | False      |
| C4_fixed_0.40std | 15min |            184 |       0.40 |          -6.93 |             -9.51 | False        |            |                | False      |
| C6_trail_1.0std  | 15min |            183 |       0.34 |          -7.26 |            -11.06 | False        |            |                | False      |
| C6_trail_1.0std  | 5min  |            666 |       0.30 |          -8.19 |             -9.93 | False        |            |                | False      |

## Limites connues

- `backtest_apex` non audité — le contrôle C0 ne couvre qu'un bug non-commun à mini-val #4 et au sprint.
- Trailing stop (C6) : fill modélisé avec 1 tick de slippage ; pas de modélisation de gap intra-tick. À durcir en Étape 2.
- Sharpe = per-trade × √252 (convention repo, cohérente avec mini-vals #1-4).
- Holdout 2025-05→2026-05 INTOUCHÉ.