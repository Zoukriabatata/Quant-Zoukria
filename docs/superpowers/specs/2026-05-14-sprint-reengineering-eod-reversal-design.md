# Sprint Re-engineering Exit — EOD Reversal MNQ

**Date** : 2026-05-14
**Auteur** : BB + Claude
**Statut** : design validé, prêt pour plan d'implémentation
**Contexte** : Étape 2 recadrée — voir §"Pourquoi ce sprint"

---

## Pourquoi ce sprint

La phase d'exploration d'edge (Étape 1) a sorti un candidat : MR fin de journée NY
(entry z>2 sur la fenêtre 15:00-15:55 NY locale) sur MNQ 5min/15min, qui tenait OOS
sur le split Valid en **baseline** (sans contraintes Apex) — PF 2.03→2.02 OOS (5min),
PF 2.68→3.65 OOS (15min).

**Mini-validation #4** (`01_research/outputs/apex_compliant/`) a appliqué les
contraintes Apex (force-flat 15:59 NY + pas d'entrée après 15:55) et l'edge s'effondre :

| | Baseline (sans Apex) | Apex-compliant |
|---|---|---|
| 5min Train | PF 2.03 · Sharpe 2.57 · +$11,996 | **PF 0.80 · Sharpe -1.41 · -$1,992** |
| 5min Valid | PF 2.02 · Sharpe 2.77 · +$4,136 | PF 1.11 · Sharpe 0.58 · +$376 |
| 15min Train | PF 2.68 · Sharpe 3.79 · +$7,749 | **PF 0.77 · Sharpe -1.50 · -$733** |
| 15min Valid | PF 3.65 · Sharpe 4.60 · +$2,809 | PF 1.08 · Sharpe 0.39 · +$47 |
| Cycle Apex 1-mois | — | **0/61 mois passés · 100% NO_TARGET** |

**Diagnostic** : le backtester baseline (`run_exploration_MR_MNQ_multi_TF.py`) n'a
aucun force-flat — timeout 12 bars (1h). Un trade entré à 15:30 NY tourne jusqu'à
16:30. L'edge End-of-Day Reversal se complète **dans / après le close auction de
16:00 NY**. MNQ futures tradent quasi 24h donc le backtest baseline capture ce
retour post-close. Apex oblige flat à 16:00 → la queue profitable est coupée.
Cohérent avec la littérature (Baltussen et al. — le reversal complète au close
auction).

**Question du sprint** : l'edge EOD Reversal se capture-t-il avec un exit qui se
résout **avant** le force-flat 16:00 ? Ou vit-il structurellement dans une fenêtre
où Apex verrouille le trader dehors ?

Le sprint est conçu pour pouvoir **tuer l'idée à pas cher** — conclure "non"
proprement est une issue probable et acceptable.

---

## Objectif

Produire une config d'exit qui tient un edge **avec contraintes Apex bakées dès le
départ**, ou conclure proprement que l'edge EOD Reversal est non-capturable sur Apex.

Issue terminale du sprint, l'une des trois :
1. **Une config passe le gate** → elle part en vraie Étape 2 (backtester
   NT8-compatible + DSR/CPCV/Monte Carlo).
2. **Plusieurs passent** → on promeut la plus **robuste** (meilleure cohérence
   Train/Valid), pas la plus performante en PF brut.
3. **Aucune ne passe** → edge EOD acté Apex-mort, CLAUDE.md mis à jour, Étape 2
   pivote sur une nouvelle hypothèse de recherche.

---

## Périmètre

### Dans le scope
- Re-engineering du **seul levier exit**. 8 configs d'exit délibérées.
- 2 timeframes : 5min et 15min.
- Mesure systématiquement **Apex-compliant** (force-flat 15:59 + cutoff entrée 15:55).
- Walk-forward Train → Valid.

### Hors scope (figé au baseline, non touché)
- Fenêtre d'entrée : 15:00-15:55 NY locale (`hour_ny == 15`, cutoff 15:55).
- Seuil d'entrée : z-score > 2.0.
- Stop loss : 1.5×std borné [5, 10] pts, wick check.
- Coûts : slippage 1 tick, commission $1.10 RT.
- M1 : exclu (baseline déjà faible — PF 1.30 @ 15h, sous les seuils).
- Sizing Kelly : hors scope, vient après l'Étape 2.
- Holdout 2025-05 → 2026-05 : **INTOUCHÉ**.

---

## Architecture

| Composant | Emplacement | Rôle |
|---|---|---|
| Exit logics réutilisables | `01_research/src/backtest.py` | Nouveaux callables `exit_logic_*`, deviennent des assets pour l'Étape 2 |
| Orchestration + analyse + plots | `01_research/notebooks/02_sprint_exit_reengineering.ipynb` | Consomme `src/`, boucle la grille, produit les outputs |
| Outputs | `01_research/outputs/sprint_exit/` | `ranking.csv`, `sprint_exit_report.md`, `run_log.txt` |
| Backtester | `backtest_apex` (existant, `src/backtest.py`) | Déjà doté du force-flat 15:59 ; `apex_constraints=True` |
| Simulation cycle | `simulate_apex_cycle` (existant) | Contexte mensuel des configs promues — **pas un gate** |

Le notebook ne contient **aucune logique réutilisable** — uniquement l'orchestration
et l'analyse. Toute fonction réutilisable vit dans `src/`. Outputs de cellules
nettoyés avant commit pour limiter le bruit de diff.

### Compatibilité signature `exit_logic`

Les exit logics suivent la signature existante de `backtest_apex` :
```
exit_logic(df, i, j, direction, entry_price, std_i, mid_i,
           or_high, or_low, or_range, sl_pts) -> (tp_touched: bool, tp_price: float, exit_reason: str)
```
- Exit temps fixe : teste `df.at[j,'hour_ny']`, `df.at[j,'min_ny']`.
- Trailing : recalcule l'excursion favorable depuis `df['high'/'low'][i:j]` à chaque
  appel (O(n²) par trade, acceptable pour une grille de cette taille).

---

## La grille d'exit — 8 configs × 2 TF = 16 trials

L'exit baseline actuel = "z-score revient dans [-0.5, +0.5]" — lent, se résout
souvent post-16:00. Chaque config ci-dessous est motivée physiquement.

| # | Config exit | Rationale |
|---|---|---|
| **C0** | z-score ±0.5 (exit de mini-val #4) | **Contrôle harness**. Doit reproduire PF 0.80 Train 5min / 0.77 Train 15min |
| C1 | z-score ±1.0 | Prend le reversal partiel plus vite |
| C2 | z-score ±1.5 | Prend juste la 1ʳᵉ jambe du reversal |
| C3 | TP points fixes 0.75×std (au touche, wick check) | Win plafonné court, MR-style (théorème de Leung) |
| C4 | TP points fixes 0.4×std (au touche, wick check) | Scalp le reversal |
| C5 | Exit temps fixe 15:58 NY (flat MTM) | Ignore z — teste si le drift d'entrée→close paie seul |
| C6 | Trailing 1×std sur excursion favorable | Lock l'excursion favorable |
| C7 | Hybride : z-score ±1.0 OU temps 15:58 (premier touché) | TP rapide + hard time stop |

`n_trials = 16` est loggé explicitement dans le rapport — c'est le budget
d'overfitting que l'Étape 2 devra compenser via le Deflated Sharpe Ratio.

---

## Protocole de mesure

1. **Tout Apex-compliant** : chaque backtest tourne avec `backtest_apex(...,
   apex_constraints=True)` — force-flat 15:59 NY, pas d'entrée après 15:55.
2. **C0 d'abord (gate de fidélité harness)** : si les métriques Train de C0 ne
   reproduisent pas mini-val #4 à moins de 2% près → **STOP**. Le harness a divergé,
   on investigue avant de faire confiance aux configs C1-C7.
3. **Train** : chaque config × TF backtestée sur Train 2021-05→2024-05 → PF, Sharpe,
   max_dd ($), WR, PnL, avg_trade, breakdown des exit-reasons.
4. **Valid (walk-forward)** : les configs qui passent le gate Train sont re-backtestées
   sur Valid 2024-05→2025-05. C'est l'OOS interne du sprint.
5. **Cycle Apex (contexte)** : `simulate_apex_cycle` tourné sur chaque config promue
   — month-by-month status. Reporté pour information, **n'entre pas dans le gate**
   (pass rate sizing-dépendant, non pertinent à 1 contrat fixe).

### Convention Sharpe
`compute_trade_metrics` calcule un Sharpe per-trade × √252 (convention du repo,
identique aux mini-vals #1-4). Conservée telle quelle pour que les chiffres se
comparent directement à mini-val #4.

---

## Gate de promotion

Une config promeut vers une vraie Étape 2 si **toutes** ces conditions sont remplies :

**Sur Train Apex-compliant :**
- PF > 1.5
- Sharpe > 1.0
- avg_trade > coût round-trip (~$1.60 : slippage 1 tick + commission $1.10)

**ET sur Valid Apex-compliant :**
- PF ≥ ~1.3
- Pas d'effondrement : Sharpe reste positif, max_dd ne s'envole pas

`max_dd` est **reporté pour information** mais n'est pas un critère bloquant du
gate (le contrôle DD strict relève de l'Étape 2 + sizing).

En cas de plusieurs configs promues : sélection par **robustesse** (cohérence
Train/Valid la plus forte), pas par PF brut le plus élevé.

---

## Outputs

### `01_research/outputs/sprint_exit/ranking.csv`
Toutes les configs × TF avec métriques complètes Train + Valid (PF, Sharpe, max_dd,
WR, PnL, avg_trade, n_trades, breakdown exit-reasons).

### `01_research/outputs/sprint_exit/sprint_exit_report.md`
- Verdict : quelle(s) config(s) passe(nt) le gate, ou aucune.
- `n_trials = 16` loggé pour le budget DSR de l'Étape 2.
- Interprétation mécanisme : pourquoi telle config marche / ne marche pas, où vit
  l'edge dans le temps.
- Recommandation : vraie Étape 2 sur config X, ou edge EOD acté Apex-mort.

### `01_research/outputs/sprint_exit/run_log.txt`
Log d'exécution complet (encoding UTF-8 — éviter le crash `cp1252` sur caractères
non-ASCII observé dans mini-val #4).

### Notebook
Plots conservés : equity curves des configs promues, distributions des exit-reasons
par config.

---

## Discipline anti-overfit

- **Holdout jamais touché** dans le sprint.
- **Train → Valid** = walk-forward, l'OOS propre du sprint.
- **C0 contrôle** = garde-fou contre l'illusion harness (cf. `python_backtest_illusion`).
- **n_trials = 16 loggé** = budget d'overfitting transmis à l'Étape 2 pour le DSR.
- Grille **délibérée** (8 configs raisonnées) et non grid search massif — conforme
  aux anti-patterns CLAUDE.md ("paramètre optimal sans walk-forward", "robustesse >
  performance brute").

---

## Risques & limites connus

1. **L'edge peut être structurellement post-16:00.** Issue probable : aucune config
   ne passe. Le sprint est conçu pour conclure "non" proprement — ce n'est pas un échec.
2. **`backtest_apex` non audité.** BB a choisi de ne pas auditer le force-flat avant
   le sprint. La config-contrôle C0 mitige : si C0 ne reproduit pas mini-val #4, le
   sprint s'arrête. Mais un bug commun aux deux (mini-val #4 et le sprint) resterait
   invisible. Audit complet du force-flat repoussé à l'Étape 2 si une config promeut.
3. **Trailing O(n²).** Acceptable pour 16 trials ; à vectoriser si réutilisé en
   Étape 2 sur grid plus large.
4. **Convention Sharpe non standard** (per-trade × √252). Cohérente avec l'historique
   du repo mais à garder en tête pour toute comparaison externe.
