# Multi-Timeframe MR — MNQ 5min & 15min (Mini-validation #1)

**Date** : 2026-05-14
**Branche** : `restructure-v1`
**Script** : `01_research/run_exploration_MR_MNQ_multi_TF.py`
**Source data** : `C:\Users\ryadb\Downloads\MNQ 5ANS DATA\glbx-mdp3-20210513-20260512.ohlcv-1m.csv.zst`

---

## 1. Setup

Signal MR identique à l'exploration M1 (entry Z>2, exit z-score dynamique [-0.5, +0.5], SL 1.5×std bordé [5, 10] pts, wicks intra-bar, commissions $1.10 RT, slippage 1 tick au SL). Resampling OHLCV depuis M1.

| TF | Hurst Window | Timeout | Bars total | Bars session NY |
|---:|-------------:|--------:|-----------:|----------------:|
| 5min | 30 | 12 bars (1h) | 344,493 | 96,336 |
| 15min | 20 | 4 bars (1h) | 114,831 | 32,112 |

Splits Train (3 ans) / Valid (1 an) / Holdout (1 an intouché) identiques à l'analyse M1.

---

## 2. Résultats Hurst global

| TF | H mean | H median | H std | Bars TV avec H |
|---:|------:|---------:|------:|---------------:|
| **M1** (référence) | 0.6158 | 0.6168 | 0.0870 | 334,665 |
| **5min** | 0.6308 | 0.6323 | 0.1149 | 46,893 |
| **15min** | 0.6383 | 0.6420 | 0.1585 | 5,808 |

→ **H augmente avec le TF** : 0.62 (M1) → 0.63 (5min) → 0.64 (15min). Le marché MNQ devient **plus persistant à fréquence plus basse**. Cohérent avec littérature (DAX : 0.54 sur 1-day vs 0.82 sur 50-day).

**Aucune poche MR identifiée par critère statistique** (H<0.45 ET p<0.01) sur 5min ni 15min, identique au M1.

---

## 3. Backtest MR par heure NY (Train)

### 5min (Train, force-trade signal MR Z>2)

| Heure NY | Trades | PF | Sharpe | Max DD | WR | PnL |
|---------:|-------:|----:|-------:|-------:|---:|----:|
| **15h** | 737 | **2.03** | **+2.57** | -$607 | 26.5% | **+$11,996** |
| 12h | 454 | 0.97 | -0.14 | -$1,545 | 23.8% | -$194 |
| 14h | 669 | 0.95 | -0.30 | -$1,211 | 24.5% | -$562 |
| 10h | 358 | 0.87 | -0.80 | -$1,559 | 16.2% | -$875 |
| 9h | 1053 | 0.83 | -0.98 | -$5,261 | 12.8% | -$3,450 |
| 13h | 611 | 0.73 | -1.75 | -$2,994 | 19.8% | -$2,815 |
| 11h | 365 | 0.73 | -1.93 | -$2,095 | 20.8% | -$1,692 |

### 15min (Train, force-trade signal MR Z>2)

| Heure NY | Trades | PF | Sharpe | Max DD | WR | PnL |
|---------:|-------:|----:|-------:|-------:|---:|----:|
| **15h** | 269 | **2.68** | **+3.79** | -$367 | 20.8% | **+$7,749** |
| 12h | 69 | 1.09 | +0.44 | -$373 | 20.3% | +$103 |
| 9h | 449 | 0.91 | -0.45 | -$1,637 | 11.6% | -$810 |
| 14h | 157 | 0.75 | -1.14 | -$1,144 | 10.8% | -$758 |
| 11h | 184 | 0.73 | -1.81 | -$1,208 | 15.8% | -$906 |
| 10h | 511 | 0.55 | -2.87 | -$4,373 | 10.8% | -$4,395 |
| 13h | 57 | 0.53 | -3.85 | -$542 | 14.0% | -$496 |

→ **Une seule heure profitable sur les deux TF : 15h NY locale** (= 15h-16h NY = dernière heure equity session, close auction).

---

## 4. Validation Out-Of-Sample sur Valid (poche {15})

| TF | Train PF | Train Sharpe | Valid PF | Valid Sharpe | Valid DD | Valid trades | Valid PnL |
|---:|---------:|-------------:|---------:|-------------:|---------:|-------------:|----------:|
| **5min** | 2.03 | 2.57 | **2.02** | **+2.77** | -$408 | 248 | **+$4,136** |
| **15min** | 2.68 | 3.79 | **3.65** | **+4.60** | -$180 | 62 | **+$2,809** |

→ **Out-Of-Sample TIENT** sur les deux TF. Les métriques Valid sont **équivalentes ou meilleures** que Train. Pas de signe d'overfit.

### Comparaison consolidée

| Setup | TF | Heure | PF Train | Sharpe Train | PF Valid | Sharpe Valid | WR | Notes |
|-------|---:|------:|---------:|-------------:|---------:|-------------:|---:|-------|
| MR strict | M1 | 15h | 1.30 | 1.08 | (non testé Valid sur cette poche) | — | 38% | seuils KO |
| MR strict | 5min | 15h | 2.03 | 2.57 | 2.02 | 2.77 | 26% | **PROMOTION OK** |
| MR strict | 15min | 15h | 2.68 | 3.79 | 3.65 | 4.60 | 21% | **PROMOTION OK** |

---

## 5. Caractéristiques du payoff

WR 20-26% mais Sharpe >2 et PF >2 → **profil asymétrique** :
- Avg trade 5min : +$16.27 par trade
- Avg trade 15min : +$28.81 par trade (Train), +$45.31 (Valid)
- Win/loss ratio ~3-4× (cohérent avec MR + SL serré)

→ Profil "rare big wins" attendu pour MR de close auction : peu d'entrées, mais quand la fair value mean-reverse, le retour est complet (limit TP au z-score=0.5).

---

## 6. Cohérence académique

Le finding "edge MR fin de journée NY" est **documenté dans la littérature peer-reviewed** :

- **Baltussen, Da, Soebhag (2024) — "End-of-Day Reversal"** (EFMA Lisbon)
- **Della Corte & Kosowski — "Overnight-Intraday Reversal Everywhere"** (Sharpe 2-5× supérieur)
- **Lou, Polk, Skouras — "A Tug of War"** (LSE, last 30-min explicite)
- **Ndame Yoda — "Hedging Demand and Market Intraday Momentum"** (JFE 2021)

Mécanisme causal probable :
- Gamma hedging des option market makers (long gamma → contre-mouvement → pinning)
- MOC orders flux → convergence settlement price
- 0DTE options accentuent l'effet depuis 2022

---

## 7. Précautions

1. **WR 20% asymétrique** : la stratégie est sensible aux régimes. Une période de marché trending fort sans reversal peut produire un long streak de SL → Sharpe rolling instable. **Stress test recommandé** par régime VIX et par phase macro.
2. **Faible nombre de trades sur 15min Valid** (62 trades sur 1 an) : statistiquement limite. Le 5min (248 trades Valid) est plus solide.
3. **Pas encore validé** : Deflated Sharpe Ratio (DSR), Combinatorial Purged CV (CPCV), Monte Carlo permutation. À faire en Étape 2.
4. **Asymétrie LONG/SHORT non analysée** : décomposition à faire (NDX a bias long structurel — un SHORT MR en fin de journée pourrait être systématiquement perdant ou inversement).
5. **Holdout 2025-05 → 2026-05 INTOUCHÉ** — à ouvrir UNIQUEMENT après finalisation Étape 2.

---

## 8. Verdict mini-validation #1

🟢 **EDGE MR FIN DE JOURNÉE NY confirmé sur MNQ multi-TF (5min, 15min)** :
- Train PF > 2.0 ET Sharpe > 2.0 sur les deux TF
- Validation OOS sur Valid sans dégradation (PF et Sharpe stables ou supérieurs)
- Aucune autre heure ne donne d'edge robuste

**Promotion conditionnelle Étape 2** sous réserve :
- Mini-validation #2 (ES) **confirme** ou non le caractère cross-asset
- Validation rigoureuse López de Prado (DSR, CPCV, Monte Carlo)
- Stress test régime + décomposition LONG/SHORT

**Fichiers de référence** :
- `h_by_hour_5min.csv`, `h_by_hour_15min.csv` : distribution Hurst
- `results_hour_train_5min.csv`, `results_hour_train_15min.csv` : backtest par heure
- `run_log.txt` : log d'exécution complet
