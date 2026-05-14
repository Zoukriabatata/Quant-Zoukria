# Opening Drive Failure Fade — Design (hypothèse de recherche #1)

**Date** : 2026-05-15
**Auteur** : BB + Claude
**Statut** : design validé en brainstorming + revue littérature approfondie, prêt pour review BB puis plan d'implémentation
**Couche** : hypothèse de recherche, jugée par le gauntlet (`02_validation/gauntlet/`)

---

## Contexte & objectif

Le gauntlet de validation d'edge (Plans 1-3) est construit, mergé dans `main`, et **calibré** : les 2 contrôles known-dead (v9 HurstMR, EOD reversal) ressortent NO-GO — la machine juge correctement. Tout ce qui a été tenté jusqu'ici est mort ou Apex-mort (v9, v10, momentum, ES cross-asset, EOD reversal). C'est la **première vraie hypothèse de recherche d'edge** — la première fois qu'on amène au gauntlet un candidat qu'on *espère vivant*.

L'hypothèse vient d'une **observation marché brute de BB** : à l'open MNQ, le premier mouvement directionnel est souvent un faux signal — un spike (« mèche ») qui ne tient pas, suivi d'un retournement. *« MNQ a besoin de cumuler avant de prendre la vraie direction. »*

Cette observation a ensuite été **adossée à la littérature peer-reviewed** (revue approfondie SSRN / ArXiv q-fin / journals — voir §"Ancrage littérature"). La revue a confirmé que le phénomène est documenté, **mais a aussi surfacé de vraies fragilités** (effet affaibli post-2010, rarement confirmé net-of-costs, danger du momentum-flip). Le feature set a été refait à partir des modèles publiés ; les fragilités sont des risques explicites, pas masqués.

**Ce que ce spec livre** : la définition complète et testable de l'hypothèse — features littérature-grounded, signal conditionné, exit, grille de params — prête à être encodée en objet `Hypothesis` et passée dans `run_gauntlet()`. **Pas** une garantie d'edge : la littérature elle-même dit « marginal ». Le gauntlet tranchera GO / NO-GO / CONDITIONAL, et un NO-GO sera un résultat honnête — une vraie tentative grounded, pas de la pêche.

## La thèse d'edge

**Opening Drive Failure Fade.** À l'open de la session NY (9:30), le premier mouvement directionnel de MNQ est fréquemment un **faux spike** : le prix prolonge le gap overnight, échoue, et se retourne. On **fade** ce faux mouvement — down-spike → on achète, up-spike → on vend.

**Mécanisme** (le *pourquoi* — ce qui manquait à v9/momentum) : à l'open, plusieurs forces produisent un mouvement non-informatif — débouclage des positions overnight, FOMO retail au coup de cloche, balayage des stops accumulés sur les niveaux overnight (*liquidity sweep*, Osler 2005). Ce premier impulse « ment » : il prend la liquidité avant que la vraie direction (s'il y en a une) ne s'établisse. Phénomène de microstructure documenté.

**Pourquoi ça pourrait survivre à Apex** : l'edge vit le matin (9:30-10:30). Un trade entré vers 9:40 et résolu en quelques minutes laisse **5h+ de marge avant le force-flat 15:55**. C'est l'opposé du problème de l'EOD reversal (qui se complétait après 16:00). L'open est le moment de la journée le plus compatible avec les contraintes Apex.

**Honnêteté** : c'est une stratégie de **mean-reversion** — la famille que BB a déjà testée et vue échouer. Le pari, c'est que trois leviers la distinguent du MR vanille mort :
1. **Ciblage** — on ne fade pas n'importe quel extrême ; uniquement le faux move de l'open, conditionné sur un gap overnight significatif.
2. **Mécanisme** — le MR vanille n'avait pas de *pourquoi* ; celui-ci en a un, documenté.
3. **Entrée sur exhaustion + conditioning** — on entre sur une dynamique d'épuisement (rejet de bougie + contraction volume), uniquement en régime de volatilité élevée (la poche où l'effet est ~2× plus fort).

Si ces trois leviers ne suffisent pas, le gauntlet le dira.

## Ancrage littérature

Le phénomène est soutenu par plusieurs strands peer-reviewed — mais la littérature est aussi explicitement nuancée.

**Soutiennent la thèse :**
- **Liu, Liu, Wang, Zhou, Zhu — "Overnight-Intraday Reversal Everywhere"** (SSRN 2730304) : le rendement overnight se reverse en intraday sur 35 futures CME (indices actions inclus) ; Sharpe 2-5× supérieur au reversal daily classique.
- **"Intraday Time Series Reversal"** (SSRN 5807282) : le rendement overnight prédit la **première demi-heure** de la session US avec **signe inverse** ; effet **plus fort en haute volatilité**.
- **Stoll & Whaley — "Stock Market Structure and Volatility"** (RFS 1990) : l'ouverture génère structurellement du bruit qui se reverse — propriété stable sur 30+ ans.
- **Osler — "Stop-Loss Orders and Price Cascades"** (JIMF 2005) : les clusters de stops amplifient un mouvement puis provoquent un reversal — le mécanisme microstructure du « fake spike ».

**Nuancent / contredisent (intégrés en §"Risques") :**
- **Gao, Han, Li, Zhou — "Market Intraday Momentum"** (JFE 2018) : la 1re demi-heure prédit la **dernière** demi-heure avec le **même signe** (momentum). Une spike *informative* continue au lieu de reverser.
- La littérature note que l'effet reversal s'est **affaibli post-2010** et est **rarement confirmé net-of-costs** ; la plupart des résultats sont **cross-sectionnels** (long-short entre actifs), pas time-series single-asset.

## L'approche — ancrée sur le prix d'open, conditionnée sur le gap overnight

Trois encodages ont été considérés : (1) signal bougie unique, (2) séquence multi-bougies spike→rejet, (3) ancrée sur le prix d'open. **Retenu : (3)**, enrichi par la littérature.

Le **prix d'open du jour (9:30) est la référence du « corps »** : un faux spike = un écart de l'open, un rejet = un retour vers l'open, la sortie = le retour à l'open. Mais la littérature ajoute une couche : le prédicteur le plus fort du reversal n'est pas l'écart intraday, c'est le **gap overnight**. L'encodage final conditionne donc le fade sur la présence d'un gap overnight significatif — on ne fade pas n'importe quel spike, on fade un spike qui prolonge un gap que la littérature dit réversible.

## La mécanique

### Features (`prepare_features`)
Calculées sur les bougies 1-min de la session RTH, sur MNQ. `prepare_features` reçoit le df de session complet (toutes les journées, 9:30-16:00) — il peut donc calculer les références inter-journées.

| Feature | Construction | Fondement |
|---|---|---|
| **`open_ref`** | `open` de la première bougie de session (9:30). Niveau « corps », constant sur la journée. | Thèse BB |
| **`prev_close`** | `close` de la dernière bougie de la session RTH précédente. Niveau pré-gap. | Liu et al. (CO-OC) |
| **`gap_z`** | `(open_ref − prev_close)` normalisé par l'écart-type rolling 20j des gaps overnight. Signé : `gap_z < 0` = gap baissier. **Le prédicteur central.** | Liu et al. ; Intraday Time Series Reversal |
| **`spike_magnitude`** | Déplacement signé du prix depuis `open_ref` (en points ; normalisation ATR possible — à figer dans le plan). « De combien le faux move a spiké. » | Chang et al. (OR size) |
| **`rejection_body`** | Ratio de mèche de la bougie courante. Down-spike : `(close − low) / (high − low)` (proche de 1 = clôture en haut du range = rejet du bas). Up-spike : symétrique. `high == low` → neutre (0.5). | Osler 2005 ; Heston et al. 2010 |
| **`vol_regime`** | Booléen : régime de volatilité réalisée élevé (ex. vol réalisée 20j > médiane 252j). | Intraday Time Series Reversal (effet ~2× plus fort en haute vol) |
| **`relvol_open`** | Volume de la bougie / moyenne 20j pour la même tranche horaire. **Note** : sur index futures, volume élevé = *plus* de reversal (inverse des actions). | Zarattini et al. ; étude ORB NQ |

### Signal (`signal_fn`)
Pour une bougie `i` dans la fenêtre `[9:30, fin_fenêtre]`, le signal se déclenche quand **toutes** les conditions s'alignent.

**Down-spike → LONG** (on fade un faux mouvement baissier) :
1. **Gap** : `gap_z ≤ −gap_threshold` — gap overnight baissier significatif (le gap que la littérature dit réversible).
2. **Spike** : `spike_magnitude ≤ −spike_min` — le prix a prolongé le mouvement baissier d'au moins `spike_min` sous l'open.
3. **Rejet (exhaustion)** : `rejection_body ≥ rejet_seuil` — la bougie courante rejette le bas.
4. **Régime** : `vol_regime` élevé — on n'opère que dans la poche de volatilité haute.
5. **Volume** : `relvol_open ≥ relvol_seuil` — confirmation.

**Up-spike → SHORT** : strictement symétrique (`gap_z ≥ +gap_threshold`, `spike_magnitude ≥ +spike_min`, `rejection_body ≤ 1 − rejet_seuil`, mêmes conditions régime/volume).

Entrée à la clôture de la bougie de rejet. Mutuellement exclusif (`backtest_pa` gère une position à la fois de toute façon).

### Exit (`exit_logic`)
**Retour au prix d'open.** Le TP est le niveau `open_ref` du jour — le « corps » vers lequel le prix est censé revenir. Par-dessus s'appliquent les mécaniques imposées par `backtest_pa` du gauntlet : SL wick-aware (`1.5 × std`, borné floor/cap), **timeout court** (l'observation dit que ça se résout en minutes — ordre de grandeur 10-20 min, valeur exacte figée dans le plan), et le force-flat 15:55 (non-contraignant ici, on est le matin).

*Refinement possible (hors v1)* : viser le retour vers `prev_close` (clôture complète du gap) plutôt que `open_ref`. Gardé pour une itération future — v1 reste sur le target conservateur.

## Param grid

On grille **uniquement** les dimensions sur lesquelles l'incertitude est légitime ; le reste est figé à des défauts sensés (valeurs exactes réglées dans le plan). Grille délibérée et petite — `n_trials` alimente la pénalité du Deflated Sharpe.

| Param | Valeurs | Grillé / figé — pourquoi |
|---|---|---|
| `window` | {9:30-10:00, 9:30-10:30} | **Grillé** — incertitude réelle sur l'extension de l'edge au-delà de l'open pur |
| `gap_threshold` | {0.5σ, 1.0σ} | **Grillé** — `gap_z` est le prédicteur central de la littérature ; vaut le coup de tester 2 niveaux d'exigence |
| `spike_min` | figé (~15 pts) | `gap_z` + `rejection_body` + `vol_regime` portent le conditioning ; le spike a juste besoin d'être « notable » |
| `rejet_seuil`, `relvol_seuil`, seuil `vol_regime`, `timeout` | figés (défauts) | Pas d'incertitude forte — des défauts sensés suffisent |

→ **4 trials** (2 × 2). Très petit — le DSR sera à peine pénalisé.

## Architecture & fichiers

**Code nouveau, suivant les patterns existants de `01_research/src/`** :
- `01_research/src/features.py` — `compute_features_opening_drive` : `open_ref`, `prev_close`, `gap_z`, `spike_magnitude`, `rejection_body`, `vol_regime`, `relvol_open`.
- `01_research/src/signals.py` — `signal_opening_drive_failure` : la logique des 5 conditions, symétrique.
- `01_research/src/backtest.py` — `exit_logic_return_to_open` : TP = `open_ref` (signature `exit_logic` standard du repo).
- `02_validation/gauntlet/hypotheses/hyp_opening_drive_failure.py` — l'objet `Hypothesis` : `name`, `description`, `instrument='MNQ'`, `timeframe='1min'`, `build_variant`, `param_grid`, `prepare_features`.
- `02_validation/gauntlet/hypotheses/__init__.py` — marqueur de package.

**Réutilisé tel quel** : tout le gauntlet (`run_gauntlet`, la batterie statistique, le verdict, le report), `data_loader.py`, `backtest_pa`. L'hypothèse est un objet enfichable.

**Exécution** : un script `02_validation/notebooks/04_run_opening_drive_failure.py` (parallèle à `03_gauntlet_calibration.py`) charge l'hypothèse, lance `run_gauntlet`, écrit le rapport dans `02_validation/outputs/gauntlet/opening_drive_failure/`. BB le lance (vraies données, plusieurs minutes).

## Critères de succès

Le gauntlet décide — pas BB, pas Claude. Le verdict applique les 8 critères de la checklist pré-déploiement Apex (compte survit, walk-forward ≥ 70% OOS rentables, Monte Carlo p < 0.05, DSR > 0.95, PBO < 0.5, max DD < $1000, stress test survit, cycle PA).

**GO** → next steps listés par le verdict : cross-validation NT8 Strategy Analyzer, sim live ≥ 2 semaines. **NO-GO / CONDITIONAL** → résultat honnête ; on relit les critères échoués, on pivote ou on raffine. Vu la prudence de la littérature, un NO-GO est un résultat *probable* — et ce ne sera pas un échec du process, ce sera le process qui marche.

## Risques & limites connus

1. **Affaiblissement post-2010 (documenté)** — la littérature note explicitement que l'effet reversal s'est affaibli après 2010, quasi effacé sur plusieurs fenêtres post-Covid. Le gauntlet teste 2021-2025 — il révélera directement si l'edge existe encore sur la période récente. C'est le risque nº1.
2. **Cross-sectionnel → time-series single-asset** — les papiers fondateurs testent des portefeuilles long-short *entre* actifs ; nous avons un seul actif (MNQ), signal univarié bien plus bruité. Le conditioning serré (gap + vol regime + rejet) est la réponse — mais ça reste un saut que la littérature ne valide pas directement.
3. **Net-of-costs rarement confirmé** — la plupart des résultats publiés sont bruts de friction réaliste. Le gauntlet impose commission + slippage obligatoires ; sur un move MNQ de 3-5 points, $2.20 RT + slippage mange une part réelle. C'est exactement ce qu'on veut tester.
4. **Momentum-flip — danger nº1 non résolu** — Gao et al. (JFE 2018) : une spike *informative* (news macro, vrai catalyseur) **continue** au lieu de reverser, et le fade se prend le move dans le mauvais sens. Distinguer « fake spike » de « informative spike » en 1-min OHLCV n'est pas résolu par la littérature. Le conditioning `gap_z` + `vol_regime` cible la poche reversal mais ne l'élimine pas. **Refinement évident si v1 sature là-dessus** : ajouter un news blackout (FOMC/NFP/CPI) — hors v1 car ça casse la contrainte OHLCV-pur, mais documenté comme la prochaine itération.
5. **Microstructure futures ≠ actions** — MNQ trade 24h ; à 9:30 ET le gap est déjà partiellement arbitré dans les futures overnight, donc la « surprise » au cash open est réduite vs les actions cash que la littérature étudie souvent.
6. **Sub-minute** — BB observe le phénomène à 15-30 sec ; on teste en 1-min (granularité plancher des données). Si l'edge est réellement sub-minute, le 1-min le capturera mal — hypothèse de sortie explicite en cas de NO-GO.
7. **Famille mean-reversion** — BB a un historique d'échecs en MR sur MNQ. Si le gauntlet sort NO-GO, distinguer « le MR est mort sur MNQ » de « cet encodage précis est mauvais ».
8. **Holdout contaminé** — le holdout 2025-05→2026-05 est partiellement contaminé ; le verdict le signalera, confiance dégradée.
