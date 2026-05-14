# Gauntlet de validation d'edge — Design

**Date** : 2026-05-14
**Auteur** : BB + Claude
**Statut** : design validé (Sections A/B/C), prêt pour review BB puis plan d'implémentation
**Couche** : 2 — Validation (`02_validation/gauntlet/`)

---

## Contexte & objectif

Tout ce qui a été tenté jusqu'ici a échoué : v9 HurstMR (PF 1.02, pas d'edge), momentum (PF 0.37), MR cross-asset ES (dégradé), EOD reversal (edge réel mais non capturable sous contrainte Apex), dual-config HurstMR (overfit + holdout contaminé + buste le compte). Le pattern : de la pêche statistique dans de l'OHLCV, validée à l'arrache, qui tombe en marche.

Plutôt que de parier sur une nouvelle hypothèse, on construit d'abord **la machine qui juge les hypothèses proprement** : un gauntlet de validation qui applique la discipline López de Prado + le réalisme du compte Apex, et sort un verdict **GO / NO-GO / CONDITIONAL** fiable. L'overfitting est contrôlé *by design* — le gauntlet ne cherche pas, il *juge*.

**Ce que ce spec livre** : la machine + la preuve qu'elle marche (via 2 hypothèses de calibration known-answer). **Pas** une nouvelle recherche d'edge — ça, c'est le cycle suivant.

### Contexte compte — Apex $50K PA EOD

BB est passé de l'Eval au **Performance Account EOD** le 2026-05-14. Règles structurantes (cf. CLAUDE.md §"Règles Apex" + mémoire `reference_apex_rules`) :

- **DD EOD $2,000** : `seuil = min(plus_haute_clôture_EOD − 2000, 50100)`, seuil initial $48,000, monotone croissant, recalculé à chaque clôture journalière. Enforced en temps réel intraday sur la balance (PnL non réalisé inclus) — touché = **compte fermé définitivement**.
- **Tiers (50K)** : L1 balance $50,000-51,499 (2 contrats std, DLL $1,000) · L2 $51,500-52,999 (3 ctr, $1,000) · L3 $53,000-55,999 (4 ctr, $2,000) · L4 $56,000+ (4 ctr, $3,000). Tier calculé sur la balance EOD de la veille, figé pour la session.
- **DLL tier-based** : touchée en intraday (equity totale) → journée stoppée, **compte survit**.
- **Contrats** : micro, 10 micros = 1 standard → L1 = 20 MNQ, L2 = 30, L3/L4 = 40.
- **Force-flat 15:55 NY** (`America/New_York`, gère le DST) — règle perso BB.
- **Pas de profit target, pas de limite de temps.**
- **Inactivité** : ≥ 2 jours à ≥ $50 net / 30 jours glissants, sinon fermeture.
- **Hedging interdit** · **stratégies high-risk interdites** (TP minuscule / SL énorme) · **automatisation interdite** (ticket Apex en attente — n'affecte pas ce spec, le gauntlet est execution-agnostic).

---

## A. Le concept + l'interface Hypothèse

Le gauntlet est une fonction `run_gauntlet(hypothèse) → Verdict`. On lui passe **une** hypothèse, il la fait passer par tout le pipeline, il sort un verdict chiffré. Il **n'optimise pas** : la grille de params est décidée par l'auteur de l'hypothèse (petite, délibérée), et le gauntlet compte honnêtement chaque point de grille pour le Deflated Sharpe.

Une **Hypothèse** est un objet enfichable (dataclass) :

| Champ | Type | Rôle |
|---|---|---|
| `name` | `str` | identifiant court (sert au nom du dossier d'output) |
| `description` | `str` | l'énoncé de l'hypothèse en une phrase |
| `instrument` | `str` | clé dans `INSTRUMENTS` (ex. `'MNQ'`) |
| `timeframe` | `str` | règle de resampling (ex. `'5min'`) |
| `build_variant` | `Callable[[dict], tuple]` | `params → (signal_fn, exit_logic, backtest_kwargs)` |
| `param_grid` | `list[dict]` | liste **petite et délibérée** de jeux de params ; `n_trials = len(param_grid)` |

`signal_fn` et `exit_logic` suivent les conventions existantes de `01_research/src/signals.py` et `src/backtest.py` (les `exit_logic_*`). Une hypothèse réutilise donc le harnais existant — elle ne réinvente rien.

---

## B. Le pipeline — 5 blocs

`run_gauntlet(hypothèse)` exécute, dans l'ordre :

### Bloc 1 — Préparation
Charge l'instrument, resample au TF, calcule les features. Splits López de Prado (figés dans `01_research/src/config.py`) :
- **Train** : 2021-05-13 → 2024-05-13
- **Valid** : 2024-05-13 → 2025-05-13
- **Holdout** : 2025-05-13 → 2026-05-13

Purge + embargo entre les splits (évite le leakage de labels chevauchants). Le gauntlet opère sur **Train + Valid**. Le **Holdout est contaminé** — BB a grid-searché le dual-config HurstMR sur 2026. Il est ouvert **une seule fois en toute fin**, et le verdict signale explicitement la confiance dégradée dessus.

### Bloc 2 — Backtest PA-réaliste *(le composant le plus lourd — quasi-réécriture)*
Un vrai **simulateur de compte PA EOD**, pas un simple backtester de trades. Deux modules :

- **`pa_account.py`** — l'état du compte PA EOD : balance, equity intraday (PnL non réalisé inclus), seuil DD EOD, tier courant, DLL du jour, statut (vivant / mort par DD EOD / journée stoppée par DLL). Recalcule le seuil et le tier à chaque clôture journalière. Expose les checks intraday : "ce trade est-il autorisé (contrats, DLL, compte vivant) ?" et "l'equity touche-t-elle le seuil EOD ?".
- **`backtest.py`** — la boucle event-driven qui tourne **sur** `pa_account` : génère les signaux via la `signal_fn` de l'hypothèse, ouvre/gère/ferme les trades via l'`exit_logic`, applique friction **obligatoire** (commission + slippage, aucun switch "off" — MNQ : `commission_rt` $1.10 + slippage 1 tick), SL wick-aware, **force-flat 15:55 NY**. À chaque barre : met à jour l'equity du `pa_account`, vérifie le seuil EOD (touché → compte mort, backtest stoppé), vérifie la DLL (touchée → journée stoppée). Sizing : au max des contrats du tier courant (le sizing fin — Kelly ou fixe — est un `backtest_kwarg` de l'hypothèse, plafonné par le tier).

Produit : courbe d'equity, liste de trades, P&L journalier, historique des tiers, et si/quand le compte est mort.

### Bloc 3 — Batterie statistique López de Prado
Sur le meilleur variant de la grille (sélectionné sur Train) :
- **Walk-forward purgé** (`walk_forward.py`, NEW) : ≥ 3 fenêtres sur Train+Valid, params optimisés in-sample, testés OOS, purge/embargo entre IS et OOS. Sortie : % fenêtres OOS rentables, Sharpe OOS par fenêtre.
- **CPCV** (`cpcv.py`, consolidé depuis `v10/validation/`) : distribution des Sharpe OOS sur tous les paths combinatoires.
- **Deflated Sharpe Ratio** (`deflated_sharpe.py`, consolidé) : DSR avec `n_trials = len(param_grid)` honnête.
- **PBO** (`deflated_sharpe.py`, consolidé) : Probability of Backtest Overfitting sur la matrice PnL des variants.
- **Monte Carlo permutation** (`monte_carlo.py`, NEW) : permute les returns des trades N fois → distribution du Sharpe sous H0 (pas d'edge) → p-value du Sharpe observé.

### Bloc 4 — Robustesse
- **Stress test** (`stress_test.py`, NEW) : rejoue le meilleur variant sur les périodes rouges *dans la plage de données dispo* (bear 2022, unwind août 2024, selloff tarifs avril 2025 — Mar 2020 / Oct 2018 hors plage). Vérifie que le seuil DD EOD n'est jamais touché sur ces fenêtres.
- **Simulation cycle PA** (`pa_cycle.py`, NEW) : rejoue le meilleur variant sur tout l'historique via le `pa_account`. Sort : le compte survit-il ? atteint-il le lock ($52,100 en clôture → seuil figé $50,100) ? en combien de jours ? respecte-t-il la règle d'inactivité (≥ 2 jours verts ≥ $50 / 30 j glissants) ?

### Bloc 5 — Verdict
**`verdict.py`** agrège tous les outputs et applique les seuils de la checklist pré-déploiement CLAUDE.md :

| Critère | Seuil GO |
|---|---|
| Compte vivant | survit sur Train+Valid — jamais de touche du seuil DD EOD en intraday |
| Walk-forward | ≥ 3 fenêtres, ≥ 70% OOS rentables |
| Monte Carlo permutation | p < 0.05 |
| Deflated Sharpe Ratio | DSR > 0 |
| PBO | < 0.5 |
| Max DD simulé | < $1,000 (50% du DD EOD $2,000) |
| Stress test | seuil EOD jamais touché sur les périodes rouges |
| Cycle PA | survit + atteint le lock + inactivity-safe |

**GO** : tous les critères passent. **NO-GO** : ≥ 1 hard fail (compte mort, DSR ≤ 0, MC p ≥ 0.05, stress test échoué). **CONDITIONAL** : critères cœur OK mais avec caveats (ex. WF marginal, confiance holdout dégradée). Le verdict liste aussi les **next steps si GO** non automatisables en Python : cross-validation NT8 Strategy Analyzer, sim live ≥ 2 semaines.

---

## C. Architecture & fichiers

```
02_validation/gauntlet/
├── __init__.py
├── pa_rules.py          — constantes PA EOD 50K (seuil DD, tiers, DLL, lock, force-flat 15:55)
├── hypothesis.py        — dataclass Hypothesis (l'interface enfichable)
├── splits.py            — splits Train/Valid/Holdout + purge/embargo LdP
├── pa_account.py        — ★ simulateur de compte PA EOD (DD EOD, tiers, DLL) — bloc 2
├── backtest.py          — backtest event-driven sur pa_account (friction, wick SL, force-flat)
├── walk_forward.py      — orchestration walk-forward purgé (NEW)
├── cpcv.py              — consolidé depuis 02_validation/v10/validation/
├── deflated_sharpe.py   — consolidé depuis 02_validation/v10/validation/ (PSR/DSR/PBO)
├── monte_carlo.py       — Monte Carlo permutation (NEW)
├── stress_test.py       — runner stress périodes rouges (NEW)
├── pa_cycle.py          — simulation cycle PA : survie / lock / inactivité (NEW)
├── verdict.py           — agrégateur GO/NO-GO + seuils checklist CLAUDE.md (NEW)
├── run_gauntlet.py      — orchestrateur : run_gauntlet(hypothesis) -> Verdict (NEW)
├── calibration/
│   ├── hyp_v9_hurstmr.py     — hypothèse contrôle v9 (doit ressortir NO-GO)
│   └── hyp_eod_reversal.py   — hypothèse contrôle EOD reversal (doit ressortir NO-GO)
└── tests/
    ├── test_pa_account.py    — le plus critique
    ├── test_splits.py
    ├── test_backtest.py
    ├── test_walk_forward.py
    ├── test_monte_carlo.py
    ├── test_stress_test.py
    ├── test_pa_cycle.py
    └── test_verdict.py
```

**Réutilisé / consolidé** :
- `cpcv.py` + `deflated_sharpe.py` sont **déplacés** depuis `02_validation/v10/validation/` vers `gauntlet/` ; les imports de `v10/validation/run_final_validation.py` sont corrigés en conséquence.
- Les générateurs de signaux (`01_research/src/signals.py`) et les `exit_logic_*` (`01_research/src/backtest.py`) sont **importés tels quels** — fonctions pures, l'interface Hypothesis les wrappe.
- Les splits LdP sont lus depuis `01_research/src/config.py` (`TRAIN_START` … `HOLDOUT_END`).

**Séparation des couches** : `01_research/src/backtest.py:backtest_apex` reste pour la recherche (Couche 1, plus léger, modèle Eval-ish). Le gauntlet a sa version PA-correcte validation-grade dans `gauntlet/`. Les deux ne fusionnent pas.

**Outputs** : `02_validation/outputs/gauntlet/<nom_hypothèse>/` — `gauntlet_report.md` (le verdict + stats par bloc), `ranking.csv` (métriques par variant), `pa_account_trace.csv` (equity, tier, seuil DD, jour de mort), `walk_forward.csv`, `cpcv_distribution.csv`, `run_log.txt`.

### Calibration — l'auto-test du gauntlet
Deux hypothèses contrôle known-answer : **v9 HurstMR** et **EOD reversal**. Les deux DOIVENT ressortir **NO-GO**. C'est le "C0" du gauntlet — s'il sort GO sur une stratégie connue-morte, le gauntlet est cassé et on ne fait confiance à aucun verdict. C'est le test d'intégration du build.

### Tests
Chaque composant a ses tests unitaires sur données synthétiques (TDD strict, comme le sprint exit). `pa_account.py` en priorité absolue — c'est le cœur, c'est une quasi-réécriture, et une erreur dans la logique DD EOD / tiers / DLL empoisonne tout verdict. Les 2 hypothèses de calibration sont le test d'intégration de bout en bout.

### Périmètre — HORS scope (YAGNI)
- Génération / recherche automatique d'hypothèses (choix acté : gauntlet-seul).
- Moteur d'exécution live + décision auto-vs-manuel (en attente du ticket Apex ; le gauntlet est execution-agnostic).
- Cross-validation NT8 Strategy Analyzer + sim live (étapes manuelles APRÈS un GO Python — le verdict les liste comme next steps).
- Acquisition de nouvelles données (utilise le Databento OHLCV-1m existant).
- Portfolio / combinaison multi-stratégies.
- **La première vraie hypothèse de recherche** à faire passer dans le gauntlet — cycle spec→plan séparé, après que le gauntlet existe et est calibré.

---

## Risques & limites connus

1. **`pa_account.py` est une quasi-réécriture, pas un durcissement.** Le `backtest_apex` existant modélise le schéma Eval. Le PA EOD (DD sur clôtures, tiers, DLL-pause-journée) est substantiellement différent. C'est le plus gros risque de bug du build — d'où la priorité tests sur ce module et les 2 calibrations en garde-fou.
2. **Holdout contaminé.** Le grid-search dual-config a touché 2026. Le gauntlet opère Train+Valid ; le holdout n'est qu'une confirmation finale à confiance dégradée. Ce n'est pas réparable — c'est documenté, pas masqué.
3. **`01_research/src/config.py` contient encore les constantes Apex Eval périmées** (`APEX_PROFIT_TARGET`, `APEX_TRAILING_DD`, `ENTRY_CUTOFF_NY_MIN`…). Le gauntlet définit ses propres constantes PA dans `pa_rules.py` et n'utilise PAS celles de `config.py`. Le nettoyage de `config.py` est hors scope ici (la Couche 1 recherche les utilise encore) — à traiter séparément.
4. **Heure exacte du cutoff Apex non confirmée**, mais BB fixe sa coupure perso à 15:55 NY (plus conservateur) — le gauntlet utilise 15:55 NY, point résolu pour le design.
5. **Périodes rouges limitées** : les données vont de 2021-05 à 2026-05 — pas de COVID (Mar 2020) ni de Q4 2018 pour le stress test. On stresse sur ce qu'on a (bear 2022, août 2024, avril 2025) ; le verdict le signale comme une couverture stress partielle.
6. **Convention Sharpe** : per-trade × √252 (convention repo, cohérente avec les mini-vals et le sprint). À garder en tête pour toute comparaison externe.
