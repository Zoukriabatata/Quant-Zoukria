# Opening Drive Failure Fade — Design (hypothèse de recherche #1)

**Date** : 2026-05-15
**Auteur** : BB + Claude
**Statut** : design validé en brainstorming, prêt pour review BB puis plan d'implémentation
**Couche** : hypothèse de recherche, jugée par le gauntlet (`02_validation/gauntlet/`)

---

## Contexte & objectif

Le gauntlet de validation d'edge (Plans 1-3) est construit, mergé dans `main`, et **calibré** : les 2 contrôles known-dead (v9 HurstMR, EOD reversal) ressortent NO-GO — la machine juge correctement. Tout ce qui a été tenté jusqu'ici est mort ou Apex-mort (v9, v10, momentum, ES cross-asset, EOD reversal). C'est la **première vraie hypothèse de recherche d'edge** — la première fois qu'on amène au gauntlet un candidat qu'on *espère vivant*.

L'hypothèse vient d'une **observation marché brute de BB** : à l'open MNQ, le premier mouvement directionnel est souvent un faux signal — un spike (« mèche ») qui ne tient pas, suivi d'un retournement. *« MNQ a besoin de cumuler avant de prendre la vraie direction. »*

**Ce que ce spec livre** : la définition complète et testable de l'hypothèse — features, signal, exit, grille de params — prête à être encodée en objet `Hypothesis` et passée dans `run_gauntlet()`. **Pas** une garantie d'edge : le gauntlet tranchera GO / NO-GO / CONDITIONAL, et un NO-GO est un résultat honnête.

## La thèse d'edge

**Opening Drive Failure Fade.** À l'open de la session NY (9:30), le premier mouvement directionnel de MNQ est fréquemment un **faux spike** : le prix s'écarte vite de son prix d'ouverture, puis échoue et revient. On **fade** ce faux mouvement — down-spike → on achète, up-spike → on vend.

**Mécanisme** (le *pourquoi* — ce qui manquait à v9/momentum) : à l'open, plusieurs forces produisent un mouvement non-informatif — débouclage des positions overnight, FOMO retail au coup de cloche, balayage des stops accumulés sur les niveaux overnight (liquidity sweep). Ce premier impulse « ment » : il prend la liquidité avant que la vraie direction (s'il y en a une) ne s'établisse. Phénomène de microstructure documenté (*opening drive failure*).

**Pourquoi ça pourrait survivre à Apex** : l'edge vit le matin (9:30-10:30). Un trade entré vers 9:40 et résolu en quelques minutes laisse **5h+ de marge avant le force-flat 15:55**. C'est l'opposé du problème de l'EOD reversal (qui se complétait après 16:00). L'open est le moment de la journée le plus compatible avec les contraintes Apex.

**Honnêteté** : c'est une stratégie de **mean-reversion** — la famille que BB a déjà testée et vue échouer. Le pari de cette hypothèse, c'est que trois leviers la distinguent du MR vanille mort :
1. **Ciblage** — on ne fade pas n'importe quel extrême n'importe quand ; uniquement le faux move de l'open.
2. **Mécanisme** — le MR vanille n'avait pas de *pourquoi* ; celui-ci en a un.
3. **Entrée sur exhaustion** — on n'entre pas sur un extrême statique (z-score > seuil) mais sur une *dynamique* d'épuisement.

Si ces trois leviers ne suffisent pas, le gauntlet le dira.

## L'approche — ancrée sur le prix d'open

Trois encodages ont été considérés : (1) signal bougie unique, (2) séquence multi-bougies spike→rejet, (3) ancrée sur le prix d'open. **Retenu : (3).**

Le **prix d'open du jour (9:30) est la référence du « corps »**. Toute la thèse s'exprime par rapport à ce niveau : un faux spike = un écart de l'open ; un rejet = un retour vers l'open ; la sortie = le retour à l'open. C'est le choix qui rend « mèche vs corps » concret, qui donne l'exit gratuitement, et qui a la plus petite grille de params (le plus résistant à l'overfit).

## La mécanique

### Features (`prepare_features`)
Calculées sur les bougies 1-min de la session, sur MNQ :
- **`open_ref`** — le prix d'open du jour : l'`open` de la première bougie de session (9:30). C'est le niveau « corps ». Constant sur la journée.
- **`dist_open`** — écart signé `close − open_ref` (en points). « De combien on s'est éloigné du corps. »
- **`rejet`** — position de la clôture dans le range de la bougie : `(close − low) / (high − low)`. Proche de 1 = clôture près du haut (rejet d'un down-spike) ; proche de 0 = clôture près du bas (rejet d'un up-spike). Indéfini si `high == low` → traité comme neutre (0.5).
- **`vol_ratio`** — volume de la bougie rapporté à sa moyenne mobile récente (SMA 20 par défaut). Sert à détecter le climax de volume puis sa contraction.

### Signal (`signal_fn`)
Pour une bougie `i` dans la fenêtre `[9:30, fin_fenêtre]`, le signal se déclenche quand les **trois** conditions s'alignent.

**Down-spike → LONG :**
1. **Spike** : `dist_open[i] ≤ −spike_min_pts` — le prix s'est éloigné d'au moins `spike_min_pts` sous l'open.
2. **Rejet (B)** : `rejet[i] ≥ rejet_seuil` — la bougie a spiké bas mais clôture dans le haut de son range (rejet de la mèche).
3. **Contraction volume (C)** : le volume a culminé pendant le spike et reflue sur la bougie de rejet — opérationnalisé comme : `vol_ratio` a dépassé un seuil de climax sur les bougies récentes **ET** `vol_ratio[i]` est en repli par rapport à ce climax.

**Up-spike → SHORT :** strictement symétrique — `dist_open[i] ≥ +spike_min_pts`, `rejet[i] ≤ 1 − rejet_seuil`, même logique volume.

Entrée à la clôture de la bougie de rejet. Mutuellement exclusif (jamais long et short en même temps — `backtest_pa` gère une position à la fois de toute façon).

### Exit (`exit_logic`)
**Retour au prix d'open.** Le TP est le niveau `open_ref` du jour — le « corps » vers lequel le prix est censé revenir. Par-dessus s'appliquent les mécaniques imposées par `backtest_pa` du gauntlet : SL wick-aware (`1.5 × std`, borné floor/cap), **timeout court** (l'observation dit que ça se résout en minutes — ordre de grandeur 10-20 min, valeur exacte figée dans le plan), et le force-flat 15:55 (non-contraignant ici, on est le matin).

## Param grid

On grille **uniquement** les dimensions sur lesquelles l'incertitude est légitime ; le reste est figé à des défauts sensés (valeurs exactes réglées dans le plan). Grille délibérée et petite — `n_trials` alimente la pénalité du Deflated Sharpe.

| Param | Valeurs | Grillé / figé — pourquoi |
|---|---|---|
| `window` | {9:30-10:00, 9:30-10:30} | **Grillé** — incertitude réelle sur l'extension de l'edge au-delà de l'open pur |
| `spike_min_pts` | {15, 30} | **Grillé** — BB observe 5-50 pts ; 15-30 = la chair, 5 = bruit, 50 = rare |
| `rejet_seuil` | figé (~0.66) | Pas d'incertitude forte — un défaut sensé suffit |
| seuils volume (climax / contraction) | figés (défauts) | Idem |
| `timeout` exit | figé (court, ~10-20 min) | L'observation contraint déjà l'ordre de grandeur |

→ **4 trials** (2 × 2). Très petit — le DSR sera à peine pénalisé.

## Architecture & fichiers

**Code nouveau, suivant les patterns existants de `01_research/src/`** :
- `01_research/src/features.py` — une fonction `compute_features_opening_drive` : `open_ref`, `dist_open`, `rejet`, `vol_ratio`.
- `01_research/src/signals.py` — un générateur `signal_opening_drive_failure` : la logique des 3 conditions, symétrique.
- `01_research/src/backtest.py` — un `exit_logic_return_to_open` : TP = `open_ref` (signature `exit_logic` standard du repo).
- `02_validation/gauntlet/hypotheses/hyp_opening_drive_failure.py` — l'objet `Hypothesis` (parallèle à `calibration/`) : `name`, `description`, `instrument='MNQ'`, `timeframe='1min'`, `build_variant`, `param_grid`, `prepare_features`.
- `02_validation/gauntlet/hypotheses/__init__.py` — marqueur de package.

**Réutilisé tel quel** : tout le gauntlet (`run_gauntlet`, la batterie statistique, le verdict, le report), `data_loader.py`, `backtest_pa`. L'hypothèse est un objet enfichable — elle ne réinvente rien.

**Exécution** : un script `02_validation/notebooks/04_run_opening_drive_failure.py` (parallèle à `03_gauntlet_calibration.py`) charge l'hypothèse, lance `run_gauntlet`, écrit le rapport dans `02_validation/outputs/gauntlet/opening_drive_failure/`. BB le lance (vraies données, plusieurs minutes).

## Critères de succès

Le gauntlet décide — pas BB, pas Claude. Le verdict applique les 8 critères de la checklist pré-déploiement Apex (compte survit, walk-forward ≥ 70% OOS rentables, Monte Carlo p < 0.05, DSR > 0.95, PBO < 0.5, max DD < $1000, stress test survit, cycle PA).

**GO** → next steps listés par le verdict : cross-validation NT8 Strategy Analyzer, sim live ≥ 2 semaines. **NO-GO / CONDITIONAL** → résultat honnête ; on relit les critères échoués, on pivote ou on raffine. Un NO-GO n'est pas un échec du process — c'est le process qui marche.

## Risques & limites connus

1. **Sub-minute** — BB observe le phénomène à 15-30 sec ; on teste en 1-min (granularité plancher des données). Si l'edge est réellement sub-minute, le 1-min le capturera mal. En cas de NO-GO, hypothèse de sortie explicite — non testable en l'état sans données plus fines.
2. **Famille mean-reversion** — BB a un historique d'échecs en MR sur MNQ. Le pari repose sur ciblage + mécanisme + entrée sur exhaustion. Si le gauntlet sort NO-GO, distinguer « le MR est mort sur MNQ » de « cet encodage précis est mauvais ».
3. **Opérationnalisation de l'exhaustion** — « mèche vs corps » et « la vente se calme » sont des intuitions ; leur traduction OHLCV (`rejet`, `vol_ratio`) est une *proxy*. La proxy peut perdre une partie de l'edge réel. Risque assumé, documenté.
4. **Extension >10:30** — l'hypothèse est ancrée sur l'open ; l'observation de BB de spikes jusqu'à 11:30 est *un autre phénomène potentiel*, à tester en hypothèse séparée (un mécanisme = une hypothèse).
5. **Holdout contaminé** — comme pour toute hypothèse passée dans le gauntlet, le holdout 2025-05→2026-05 est partiellement contaminé ; le verdict le signalera, confiance dégradée.
