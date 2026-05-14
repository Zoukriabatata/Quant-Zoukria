# ES Hurst & MR — Cross-asset validation (Mini-validation #2)

**Date** : 2026-05-14
**Branche** : `restructure-v1`
**Script** : `01_research/run_exploration_MR_ES.py`
**Source data** : `ES 5ANS DATA\glbx-mdp3-20210513-20260512.ohlcv-1m.csv.zst` (82 MB)

---

## 1. Setup ES (différences vs MNQ)

Mêmes paramètres signal (Hurst window 50, lookback 20, Z entry 2, Z exit 0.5, SL std 1.5×, timeout 60 bars). **Specs contrat différentes** :

| Param | MNQ | ES |
|-------|----:|---:|
| Point value | $2.00 | **$50.00** |
| Commission RT | $1.10 | **$4.00** |
| Tick size | 0.25 | 0.25 |
| SL floor | 5 pts | **1 pt** ($50) |
| SL cap | 10 pts | **2 pts** ($100) |

ES étant ~25× plus capital-intensive que MNQ, les bornes SL sont réduites en points pour rester comparables en risque dollar.

---

## 2. Données chargées

- **1,733,959 bars** ES M1 (rollovers exclus)
- **485,188 bars** en session NY 9h30-16h locale
- Période 2021-05-13 → 2026-05-12
- Filtre symbole : `ES*` (front month dominant par volume, exclu spreads)

---

## 3. Hurst global ES

| Stat | ES | MNQ (référence) |
|------|----:|----:|
| **H mean** | **0.6090** | 0.6158 |
| H median | 0.6100 | 0.6168 |
| H std | 0.0883 | 0.0870 |
| H min | 0.0000 | 0.0266 |
| H max | 0.9652 | 0.9687 |

→ **ES légèrement moins persistant que MNQ** (H mean 0.609 vs 0.616) mais toujours **>0.5 = persistant**. Pas de différence statistique significative cross-asset au niveau global.

### Distribution H par heure NY (ES)

| Heure | H mean | t-stat | p-value | mr_significant |
|------:|------:|-------:|--------:|---------------:|
| 10h | 0.6136 | 258.0 | 0.0000 | ❌ |
| 11h | 0.6117 | 317.3 | 0.0000 | ❌ |
| 12h | 0.6074 | 299.7 | 0.0000 | ❌ |
| 13h | 0.6106 | 304.3 | 0.0000 | ❌ |
| 14h | 0.6081 | 294.4 | 0.0000 | ❌ |
| **15h** | **0.6057** | 293.4 | 0.0000 | ❌ |

**Aucune poche MR statistique** sur ES non plus (H<0.45 jamais atteint). Même profil que MNQ : H descend marginalement vers 0.61 sur les heures plus tardives, mais reste loin du seuil MR exploitable.

---

## 4. Backtest MR ES par heure NY (Train, force-trade)

| Heure NY | Trades | PF | Sharpe | Max DD | WR | PnL |
|---------:|-------:|----:|-------:|-------:|---:|----:|
| **15h** | 3228 | **1.15** | **+0.63** | -$15,240 | 34.6% | **+$34,987** |
| 12h | 2828 | 0.93 | -0.45 | -$18,639 | 40.5% | -$12,792 |
| 11h | 2778 | 0.88 | -0.86 | -$24,305 | 37.1% | -$23,528 |
| 14h | 3017 | 0.83 | -1.13 | -$34,069 | 36.7% | -$34,114 |
| 10h | 2878 | 0.80 | -1.49 | -$46,383 | 30.5% | -$44,644 |
| 13h | 2825 | 0.80 | -1.47 | -$38,501 | 37.6% | -$37,836 |
| 9h | 1590 | 0.73 | -1.92 | -$40,459 | 21.7% | -$39,285 |

⚠️ **Drawdowns énormes** sur les heures perdantes (~-$24k à -$46k sur 3 ans Train) — conséquence du point value ES = $50/pt × cap SL 2 pts = $100 par trade SL × WR perdant ~63-67%.

---

## 5. Validation OOS (Valid) — ES poche {15}

**KO sur critères promotion** :
- Train : PF 1.15 ✗ (< 1.5), Sharpe **0.63** ✗ (< 1.0), 3228 trades ✓
- Heures prometteuses ES (PF>1.5 ET Sharpe>1.0 ET trades≥100) : **0**

Pas de validation Valid effectuée (aucune poche ne passe le filtre Train).

---

## 6. Comparaison directe ES vs MNQ — Heure 15h NY (M1)

| Métrique | MNQ M1 | ES M1 | Ratio ES/MNQ |
|----------|-------:|------:|-------------:|
| Trades | 3,024 | 3,228 | 1.07× |
| PF | **1.30** | 1.15 | 0.88× |
| Sharpe | **1.08** | 0.63 | 0.58× |
| Max DD | -$1,729 | -$15,240 | 8.8× ⚠️ |
| WR | 38.4% | 34.6% | 0.90× |
| Avg trade | $3.60 | $10.84 | 3.0× |
| PnL total Train | +$10,895 | +$34,987 | 3.2× |
| PnL / trade | $3.60 | $10.84 | 3.0× |
| PnL / $DD risk | $6.30 / $ DD | $2.30 / $ DD | **0.36×** |

→ **L'edge 15h NY est PLUS FAIBLE sur ES qu'sur MNQ** en termes de qualité (Sharpe ratio, PnL/DD). En valeur absolue, ES rapporte 3× plus (logique vu $50/pt vs $2/pt) mais avec un DD 8.8× plus grand → ratio risk-adjusted dégradé.

### Pourquoi cette différence ?

Hypothèses à creuser :
1. **MNQ = retail-driven**, ES = institutionnel-driven. Le close auction MNQ est dominé par les ordres retail (DCA, MOC retail), plus prédictible. ES dominé par MOC institutionnels + 0DTE flow → moins de pattern reproductible.
2. **Ratio NQ vs SPX** : NQ a une vol intraday plus élevée que SPX → extensions de Z>2 plus fréquentes en MNQ → plus de setups MR exploitables.
3. **0DTE concentration** : le marché 0DTE SPX (XSP/SPX) est massif depuis 2022, peut casser les patterns historiques ES. NDX 0DTE est plus jeune et plus petit → l'edge MNQ MR est moins "arbitragé".
4. **SL cap différent** : 2 pts ES = $100 / 10 pts MNQ = $20 par trade. Risk-per-trade dollar incomparable.

---

## 7. Verdict mini-validation #2

🟡 **L'edge MR fin de journée NY existe sur ES MAIS dégradé** :
- 15h NY = seule heure positive en absolu, +$34,987 sur 3 ans Train
- MAIS Sharpe 0.63 **sous le seuil de promotion 1.0**
- MAIS DD -$15,240 = 7.6× le DD limit Apex ($2,000) → bust garanti à 1 contrat ES

→ **Robustesse cross-asset LIMITÉE**. Le finding "15h NY MR" est **principalement spécifique à MNQ** (l'edge est plus net) et l'écart MNQ/ES est cohérent avec une lecture microstructure (NDX retail/0DTE-light vs SPX institutionnel/0DTE-heavy).

**Implications pour la suite** :
- Le finding MNQ reste **valide** comme piste prioritaire
- ES est **NOT une fallback** propre — pas de cross-asset robustness
- Étape 2 devra **focus exclusif MNQ** + analyse fine du gamma hedging NDX (corrélation avec open interest 0DTE NQ)
- Tester ES sur 5min/15min n'a pas été fait — c'est une investigation possible mais probablement décevante vu les chiffres M1

**Fichiers de référence** :
- `h_by_hour_es.csv`, `h_by_month_es.csv`, `h_by_dow_es.csv`
- `results_hour_train_es.csv`
- `hurst_distribution_es.png`
- `run_log.txt`
