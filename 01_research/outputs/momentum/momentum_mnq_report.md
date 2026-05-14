# MOMENTUM MNQ — Test stratégie breakout (Mini-validation #3)

**Date** : 2026-05-14
**Branche** : `restructure-v1`
**Script** : `01_research/run_exploration_MOMENTUM_MNQ.py`
**Hypothèse testée** : si H=0.62 en moyenne (persistant), une stratégie momentum / breakout devrait avoir un edge.

---

## 1. Setup signal momentum

- **LONG** : `close[i] > rolling_max(close, 20)[i-1]` — breakout au-dessus du max des 20 dernières bars (exclu barre courante)
- **SHORT** : `close[i] < rolling_min(close, 20)[i-1]` — breakdown sous le min des 20 dernières bars
- **SL hard** : entry ± 2 × std_lookback(20) FIXÉ à l'entrée, bordé [5, 15] pts, wick check
- **Trail stop dynamique** : max/min favorable ± 1 × std_lookback(20) RECALCULÉ chaque barre, bordé [3, 12] pts, wick check
- **Règle pessimiste** : si SL hard ET trail touchés dans même barre → exit au pire prix
- Timeout 60 bars (1h)
- 1 contrat MNQ fixe, slippage 1 tick au touche, commission $1.10 RT
- Session NY 9h30-16h locale, splits Train (3 ans) / Valid (1 an) / Holdout (1 an intouché)

---

## 2. Résultats globaux Train (toutes heures)

| Métrique | Valeur |
|----------|-------:|
| Signaux générés | 67,429 |
| Trades exécutés | **37,347** |
| Profit Factor | **0.37** |
| Sharpe | **-4.85** |
| Max DD | **-$215,617** |
| Win Rate | 27.2% |
| Avg Trade | **-$5.77** |
| PnL total | **-$215,601** |

→ **Catastrophe absolue**. Plus de 37k trades exécutés sur 3 ans = ~50/jour. Chaque trade perd en moyenne $5.77. Le DD dépasse les $200k sur un compte $50k — bust × 100.

---

## 3. Backtest par heure NY (Train)

| Heure NY | Trades | PF | Sharpe | Max DD | WR | PnL |
|---------:|-------:|----:|-------:|-------:|---:|----:|
| **15h** (meilleure) | 6,121 | 0.57 | -1.93 | -$24,899 | 26.6% | -$23,747 |
| 9h | 3,418 | 0.39 | -5.97 | -$24,982 | 31.9% | -$24,892 |
| 14h | 5,695 | 0.35 | -5.78 | -$30,942 | 26.2% | -$30,940 |
| 10h | 6,001 | 0.34 | -6.72 | -$41,450 | 29.6% | -$41,442 |
| 13h | 5,424 | 0.32 | -6.74 | -$30,229 | 26.3% | -$30,248 |
| 12h | 5,524 | 0.30 | -6.61 | -$31,282 | 25.1% | -$31,283 |
| 11h | 5,699 | 0.29 | -7.46 | -$37,213 | 26.4% | -$37,221 |

→ **TOUTES les heures perdent**. Aucune n'approche PF 1.0. La "meilleure" (15h) est encore à PF 0.57.

---

## 4. Backtest par mois calendaire (Train)

Tous les mois perdants. Le moins pire est janvier (PF 0.75, Sharpe -0.22). Le pire est août (PF 0.29, Sharpe -6.97). **Pas un seul mois profitable.**

---

## 5. Heures prometteuses (PF>1.5, Sharpe>1.0, trades≥100) : **0**

Pas de validation OOS effectuée (aucune heure ne passe le filtre Train).

---

## 6. Analyse — Pourquoi le momentum perd autant ?

### Hypothèse 1 : confusion "H>0.5 statistique" ≠ "breakout profitable"

H = 0.62 sur les returns M1 signifie une autocorrélation **positive faible** des returns aux différents lags. C'est un **drift léger continu**, pas un effet "breakout à N=20 marche". L'inférence "trending → momentum profitable" est trop naïve :

- L'edge momentum théorique est sur des **timeframes plus longs** (multi-day, weekly)
- En intraday M1, les "breakouts" sont majoritairement des **whipsaws** : false breakouts qui attirent les stops puis retournent. Connu en microstructure.
- Le filtre 20 bars est arbitraire — des seuils différents (Donchian 60, ATR breakout, volume-confirmed) donneraient probablement d'autres résultats. Mais la version brute = catastrophe.

### Hypothèse 2 : trail stop trop serré (1×std dynamique)

Avec std MNQ M1 ~3-5 pts en session NY, le trail à 1σ = 3-5 pts derrière le max favorable. Un wick rétractant de 5 pts (= 1 fois le HL range moyen) suffit à toucher le trail. **Beaucoup de sorties prématurées juste après l'entrée**.

Le SL hard à 2σ (~10 pts) est plus large mais le trail kick presque toujours avant — d'où :
- 37k trades pour 67k signaux : ~44% des signaux exécutés (les autres en cooldown post-exit)
- Avg trade -$5.77 ≈ -3 pts MNQ ≈ slippage + commission + petit perte

→ Le trail dynamique mange systématiquement le profit AVANT que le mouvement momentum ne se développe.

### Hypothèse 3 : coûts d'exécution écrasent le micro-edge

Coûts par trade (round-trip) :
- Slippage 1 tick au SL/trail : 0.25 pt × $2 = $0.50
- Commission Apex/CME : $1.10
- Total ≈ $1.60 / trade

Sur 37,347 trades : **$59,755 de coûts cumulés** (~28% du DD total). Le signal devrait gagner au minimum $1.60/trade NET pour breakeven. En réalité il perd $5.77/trade.

### Hypothèse 4 : breakouts intraday MNQ = anti-edge

C'est un **résultat connu** en microstructure equity index futures : les breakouts à court terme sur indices sont systématiquement des fades. Les MM exploitent les stops placés autour des range highs/lows en pousant le prix au-delà puis en le ramenant — c'est l'opposé de l'effet momentum théorique.

→ Le résultat **renforce paradoxalement le finding MR fin de journée** : sur la dernière heure, c'est exactement ce comportement de "fade des extensions" qui produit l'edge MR Z>2.

---

## 7. Note méthodologique

Cette implémentation est volontairement minimale (breakout 20 bars + trail 1σ). Une étude momentum sérieuse aurait besoin de :
- Filtres trend-following multi-indicateurs (ADX, EMA cross, regime filter)
- Trailing stops plus sophistiqués (Chandelier, Parabolic, breakeven+lock-in)
- Position sizing volatility-adjusted (pas 1 contrat fixe)
- Tests sur timeframes plus longs (M5, M15, H1) — l'effet momentum est mieux capturé en TF supérieur

Le test ici sert juste à **invalider l'hypothèse naïve** "H>0.5 ⇒ momentum profitable" — invalidée.

---

## 8. Verdict mini-validation #3

🔴 **MOMENTUM minimaliste sur MNQ M1 = NO EDGE**. PF 0.37 global, toutes heures et tous mois perdants, DD -$215k sur 3 ans. **Pas une question d'optimisation, c'est structurel** : les breakouts M1 sur indices sont des anti-edges historiques.

Implications :
- **Pivot complet vers momentum sur MNQ M1 = exclu**
- L'hypothèse "marché trending donc momentum marche" est **invalidée empiriquement**
- Cohérent avec littérature : le momentum sur indices est un effet **multi-day / multi-week**, pas intraday M1
- Le résultat renforce la lecture microstructure : **fade des extensions intraday** est le profil dominant, qui supporte notre finding MR fin de journée NY

**Fichiers de référence** :
- `results_hour_train_momentum.csv`
- `results_month_train_momentum.csv`
- `run_log.txt`
