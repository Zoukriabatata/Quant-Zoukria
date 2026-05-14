# HURST_MR v9 — Spécification "best edge" (snapshot 2026-05-12)

**Date du snapshot** : 2026-05-12 (timezone Europe/Paris)
**Date de figeage spec** : 2026-05-14
**Statut** : Configuration de référence, code en place dans `ninjatrader/HurstMR_Apex.cs` et defaults sliders `pages/5_Backtest.py`.
**Compte cible** : Apex Trader Funding $50K Evaluation

---

## 1. Résumé (TL;DR)

- **H (Hurst)** : 0.58 — seuil entrée régime MR (H < 0.58)
- **Fenêtre H (HW)** : 50 barres
- **Lookback (LB)** : 19 barres (mean/std rolling pour Z-score)
- **Band / K** : 2.75 σ — seuil |z-score| pour entrée
- **Stop-loss** : `SL = 0.65 × σ` (multiplicateur), **SL min = 5.0 pts MNQ**, **SL max = 20.0 pts**
- **SL adaptatif ATR** : OFF
- **Take-profit overshoot** : 0.15 σ au-delà de la fair value (théorème Leung)
- **Max trades / jour** : 20
- **Daily loss limit** : $1,000
- **DD autorisé (rappel Apex)** : $2,000
- **Trailing MR/Trend** : ON, activé quand **H > 0.51** (régime trending)
- **Anti fake-stops (STD filter)** : 1.00 pt minimum
- **Time filter** : skip 14:00 UTC = ON (= 10h NY EDT — voir caveat §3)
- **Sizing** : Auto Kelly fractionnel
- **DD-adaptatif (plafond contrats max)** : 12 MNQ
- **Risk % / trade** : 12% du DD restant

---

## 2. Paramètres détaillés

| Bloc | Paramètre | Valeur | Unité | Source code |
|------|-----------|--------|-------|-------------|
| **Signal** | H (Hurst threshold) | 0.58 | sans dim. | `HurstMR_Apex.cs:200`, `pages/5_Backtest.py:68` |
| Signal | HW (Hurst window) | 50 | barres M1 | `HurstMR_Apex.cs:201`, `:71` |
| Signal | LB (lookback Z-score) | 19 | barres M1 | `HurstMR_Apex.cs:202`, `:73` |
| **Bandes** | K (Z-score entry) | 2.75 | σ | `HurstMR_Apex.cs:203`, `:75` |
| **Risk** | SL multiplicateur | 0.65 | × std | `HurstMR_Apex.cs:204`, `:79` |
| Risk | SL minimum | 5.0 | **points MNQ** ($10 par contrat) | `HurstMR_Apex.cs:419`, `:81` |
| Risk | SL maximum (cap) | 20.0 | **points MNQ** | `HurstMR_Apex.cs:420` |
| Risk | SL adaptatif ATR | OFF | bool | `pages/5_Backtest.py:83` |
| **Exit** | TP overshoot | 0.15 | σ au-delà FV (côté opposé) | `HurstMR_Apex.cs:205`, `:85` |
| Exit | Timeout | 120 | barres M1 | `HurstMR_Apex.cs:206`, `:101` |
| **Filtres** | STD filter (anti fake-stops) | 1.00 | points (std min lookback 20) | `pages/5_Backtest.py:119` |
| Filtres | Skip 14h | ON | filtre time-of-day | `pages/5_Backtest.py:121` |
| **Trail** | Trail MR/Trend | ON | bool | `HurstMR_Apex.cs:208`, `:112` |
| Trail | Activation trail (seuil H) | **0.51** | **H > seuil → trail actif** | `HurstMR_Apex.cs:209`, `:114` |
| **Limits** | Max trades / jour | 20 | trades | `HurstMR_Apex.cs:221` |
| Limits | Daily loss limit | 1000 | dollars Apex | `HurstMR_Apex.cs:222` |
| Limits | DD autorisé | 2000 | dollars Apex Trailing DD | `HurstMR_Apex.cs:223` |
| Limits | Safety buffer DD | 150 | dollars (arrêt si DD-buffer < 150) | `HurstMR_Apex.cs:224` |
| **Sizing** | Méthode | Auto Kelly | fractionnel adaptatif | `HurstMR_Apex.cs:104`, `ComputeKellyContracts()` |
| Sizing | Plafond contrats max (Eval) | 12 | MNQ | `HurstMR_Apex.cs:213` |
| Sizing | Plafond contrats max (PA) | 4 | MNQ | `HurstMR_Apex.cs:214` |
| Sizing | Risk % / trade | 0.12 | 12% du DD restant | `HurstMR_Apex.cs:212` |
| Sizing | Plancher risk (min) | 50 | dollars | `HurstMR_Apex.cs:266` |
| **Session** | Début session (live, Paris) | 15:30 | Paris (= 9:30 NY local) | `HurstMR_Apex.cs:329` |
| Session | Fin session (live, Paris) | 22:00 | Paris (= 16:00 NY local) | `HurstMR_Apex.cs:330` |
| Session | Flat forcé (live) | 21:59 | Paris (= 15:59 NY local) | `HurstMR_Apex.cs:336-337` |
| Session | Stop nouvelle entrée (live) | 21:55 | Paris (= 15:55 NY local) | `HurstMR_Apex.cs:351` |

---

## 3. Caveats & ambiguïtés documentés

### 3.1 "Skip 14h NY" — interprétation effective

Le toggle Python `pages/5_Backtest.py:121` s'appelle "Skip 14h NY (afternoon hole)" mais l'implémentation `pages/5_Backtest.py:316-317` filtre sur `dt.hour` qui est en **UTC** (timezone du CSV Databento). Concrètement :

- **Backtest Python** : skip les bars dont l'heure UTC est 14 → = **10h NY EDT** (= 09h NY EST). C'est l'heure du "post-open consolidation" NY equity.
- **Live NT8 (HurstMR_Apex.cs)** : la session est en heure Paris locale (15h30-22h Paris = 9h30-16h NY local). **Pas de skip explicite d'heure intraday** dans le code C# — toute heure dans 15h30-21h55 Paris est tradable.

→ **Asymétrie backtest Python ↔ live C#**. À harmoniser en Phase 2 si besoin de cohérence stricte.

### 3.2 Session backtest Python vs live C#

- **Backtest Python** : session 9h30-16h **UTC** (sliders defaults), couvre 5h30-12h NY EDT (= pré-marché + open NY + 2.5h matin).
- **Live C#** : session 15h30-22h **Paris** = 9h30-16h NY local (= vraie session equity NY classique).

→ Le live C# trade une fenêtre temporelle ~7-8h plus tard que celle utilisée pour calibrer les paramètres en Python. C'est une **divergence majeure** documentée mais non résolue.

### 3.3 Trail H > 0.51

Trail activé quand `hurst > TrailHThresh` (= H > 0.51). Logique : si pendant la position le marché bascule en régime trending (H monte), on ratchete le SL à la fair value mobile pour ne pas couper trop tôt un mouvement directionnel. Sortie explicite si |z| ≥ 3.0 ou (H > 0.51 ET |z| ≥ 2.5).

---

## 4. État réel mesuré (chiffres à jour 2026-05-14)

⚠️ **Cette section distingue le backtest Python du backtest NT8 Strategy Analyzer. Les écarts sont importants et documentés.**

### 4.1 Backtest Python `pages/5_Backtest.py` (close-only, SL/TP checked sur closes)

| Métrique | Valeur 5 ans |
|----------|-------------:|
| Profit Factor | 2.29 |
| Win Rate | 42.64% |
| Sharpe (annualisé) | 4.82 |
| Max DD (%) | 2.49% |
| Max DD ($) | $1,245 |
| Trades | 3,030 |
| P&L total | +$303,306 |
| Walk-Forward OOS PF | 5.17 |
| Walk-Forward OOS Sharpe | 3.34 |
| % mois positifs | 100% (60/60) |

### 4.2 Backtest NT8 Strategy Analyzer (tick-realistic, SL/TP sur ticks intra-bar) — source de vérité live-realistic

| Métrique | Valeur 5 ans (13/05/2021 → 13/05/2026) |
|----------|---------------------------------------:|
| Profit Factor | **1.02** |
| Win Rate | 23.93% |
| Sharpe | 0.05 |
| Max DD | **-$22,748** |
| Trades | 6,531 |
| P&L total | +$12,169 |
| Max consec losers | 32 |
| Avg trade | $1.86 |

### 4.3 Explication de la divergence

Cf. `03_spec/strategy_diagnosis_v9_csharp.md` (diagnostic complet) :

1. **Close-only Python** rate les SL touchés intra-bar par les wicks → SL "miraculeusement évités" en backtest, déclenchés en réalité
2. **Asymétrie fenêtre session** (UTC vs NY local) + skip 14h appliqué uniquement Python
3. **Pas de commissions Apex/CME modélisées** en Python (~$1.10/RT × 6,531 trades = $7,184 absorbés)

→ **PF Python 2.29 n'est pas représentatif du live**. Le PF NT8 SA 1.02 est la mesure live-réaliste de référence.

---

## 5. Hypothèses & unités confirmées

- **SL min = 5.0 points MNQ** ✓
- **Daily loss limit / DD autorisé** = dollars Apex $50K Evaluation ✓
- **σ (sigma)** = std rolling 20 barres sur **closes** (M1) ✓
- **STD filter 1.00** = std minimum **en points** sur lookback 20 ✓
- **Timeframe** = M1 (1-minute bars Databento GLBX.MDP.3) ✓

---

## 6. Checklist de validation "edge incroyable"

- [x] **Sur-échantillonnage / leakage** : Walk-forward + OOS effectués (résultats Python, cohérence avec NT8 SA NON validée)
- [ ] **Robustesse** : perturber HW/LB/K/SL de ±5-20% et vérifier que l'edge tient — **À FAIRE**
- [x] **Coûts réels** : commissions + slippage + latence — modélisés en NT8 SA, **NON modélisés en Python**. Conséquence : PF Python invalide.
- [ ] **Stress test** : journées news, jours trend forts, gaps — **À FAIRE** (FOMC, NFP, CPI blackout pas implémenté)
- [ ] **Risk of ruin** vs **Risk%/trade = 12** + **DD 2k** : à calculer formellement (Kelly fractionnel agressif sur compte $2K DD = risque non négligeable de bust intra-mois)

---

## 7. Statut de déploiement

| Composant | Statut |
|-----------|--------|
| Code C# NinjaScript (`ninjatrader/HurstMR_Apex.cs`) | ✅ En place, defaults champion v9 hardcodés |
| Code Python backtest (`pages/5_Backtest.py`) | ✅ En place, defaults sliders = config champion |
| Spec écrite | ✅ Ce document |
| Backtest Python | ⚠️ Chiffres invalidés par NT8 SA (close-only bug) |
| Backtest NT8 SA | ✅ Mesuré 2026-05-14 : **PF 1.02, DD -$22k → NON déployable Apex** |
| Sim live démo NT8 | ❌ Pas encore effectué (recommandation : 2 semaines avant tout live) |
| Live Apex | ❌ **PAS déployable en l'état** — voir caveat §4 |

---

## 8. Décisions actées

1. **v9 reste la configuration de référence du repo** — aucune modification de paramètres prévue tant que pas de nouveau backtest réaliste démontrant amélioration.
2. **Le code C# `HurstMR_Apex.cs` est la source de vérité live**. Le code Python sert pour recherche/visualisation, pas pour décision Apex.
3. **Pas de déploiement live Apex tant que** : (a) backtest Python n'est pas réécrit avec wicks intra-bar, (b) sim démo NT8 ≥ 2 semaines, (c) cross-validation Python ↔ NT8 SA écart < 15%.
4. **La phase de recherche d'edge (2026-05-13/14) est close**. Phase 2 restructuration repo reprend (cf. `AUDIT_REPORT.md`).

---

*Document figé 2026-05-14 — révision uniquement sur nouveau backtest tick-realistic démontrant une amélioration significative et reproductible.*
