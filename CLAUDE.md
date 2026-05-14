# CLAUDE.md — Contexte Quant Trading (Myriam / BB)

## Profil opérateur

- Trader systématique sur **MNQ** (Micro Nasdaq futures)
- Compte **Apex Trader Funding $50K PA EOD** (Performance Account, Simulated Funded) — règles complètes en §"Règles Apex". ⚠️ Migré de l'Eval vers un PA EOD le 2026-05-14 — les anciennes règles Eval ne s'appliquent plus.
- **Je ne code pas.** Je dirige la conception, Claude implémente. Quand je décris une logique, traduis-la en code propre sans me demander d'écrire les bouts.
- Stack technique (architecture 3 couches, depuis restructuration 2026-05-14) :
  - **Couche 1 — Recherche** : Python + JupyterLab + VectorBT (`01_research/`)
  - **Couche 2 — Validation** : Python (backtrader) + NinjaScript Strategy Analyzer (`02_validation/`)
  - **Couche 3 — Live** : C# / NinjaScript sur NinjaTrader + Rithmic (`03_live/`) — ⚠️ le "full auto" est en question : Apex interdit l'automatisation (Prohibited Activities), clarification envoyée à Apex le 2026-05-14, réponse en attente
  - **Plus de Streamlit** — supprimé pour passer en pro Jupyter/notebooks

## Appellation

Tu peux m'appeler **BB**.

## Statut actuel — Sprint re-engineering exit en cours (NO LIVE)

> ⚠️ **v9 NON déployable Apex — PF 1.02 · DD -$22,748 mesurés en NT8 Strategy Analyzer tick-realistic.** Aucune stratégie validée pour live actuellement. Exploration d'edge **close** : un candidat baseline identifié (MR fin de journée NY sur MNQ) mais **il meurt sous contraintes Apex** (mini-val #4 — PF 0.80 Train, 0/61 mois passés). Sprint de re-engineering exit en cours pour déterminer si l'edge se capture avant le force-flat 16:00 NY.

### Backtest réaliste NT8 Strategy Analyzer — `HurstMR_Apex.cs` (5 ans MNQ, 13/05/2021 → 13/05/2026)

| Métrique | Valeur | Verdict |
|----------|-------:|---------|
| Total Net Profit | +$12,169 | ≈ bruit |
| Profit Factor | **1.02** | 🔴 Pas d'edge (cible >1.5) |
| Max Drawdown | **-$22,748** | 🔴 Bust Apex garanti (limit $2,000) |
| Sharpe Ratio | 0.05 | 🔴 Sharpe ~0 |
| Sortino Ratio | 0.08 | 🔴 |
| Total Trades | 6,531 (3,421 L / 3,110 S) | ~3.4 trades/jour |
| % Profitable | **23.93%** | 🔴 Trop bas pour MR (cible 40-50%) |
| Avg Trade | $1.86 | Ne couvre pas slippage + commissions |
| Avg Win / Avg Loss | 3.23 | OK isolément (Leung) |
| Max Consec Losers | **32** | 🔴 Catastrophique |
| Profit / mois | $203 | Loin du target $3,000 |
| Max Time to Recover | **1,137 jours** | 🔴 ~3 ans |

**Source** : backtest manuel BB · 2026-05-14 · diagnostic complet dans `03_spec/strategy_diagnosis_v9_csharp.md`.

### Pourquoi divergence vs chiffres Python annoncés avant

Le backtest Python `pages/5_Backtest.py` qui annonçait PF 2.29 / Sharpe 4.82 / DD 2.49% / +$303k souffrait de **5 défauts structurels** (cf. `AUDIT_REPORT.md` + `03_spec/strategy_diagnosis_v9_csharp.md`) :

1. **Close-only execution** : SL/TP vérifiés sur `closes[j]` au lieu de `highs[j]`/`lows[j]` → SL "manqués" simulés en backtest, déclenchés systématiquement en live tick
2. **Fenêtre session UTC** au lieu de NY local (label sidebar "Session NY" trompeur)
3. **Skip 14h UTC** (= 10h NY EDT) au lieu du vrai "afternoon hole" 14h NY (= 18h UTC EDT)
4. **Filtre `std_min=1.0`** présent en Python, absent du C#
5. **Commissions zéro** et slippage trop optimiste en Python

→ Archétype de la `python_backtest_illusion` actée en mémoire projet. **Le code Python n'est pas malhonnête, il est incomplet.**

### Historique des claims Python (caveat documenté — invalides pour décision Apex)

Chiffres circulés dans le repo avant 2026-05-14 — **invalidés** par le backtest NT8 SA :

- ~~PF 2.29 · WR 42.64% · Sharpe 4.82 · DD 2.49% · 3 030 trades · +$303,306~~
- ~~Walk-Forward OOS : PF 5.17 · Sharpe 3.34 · Calmar 95.50 · 78% fenêtres rentables · 220 trades OOS~~
- ~~60/60 mois positifs (100%) · 52/60 mois passed target~~
- ~~Saisonnalité : Mai/Décembre 100% positifs · Octobre rouge structurel~~

Conservés ici comme **historique uniquement**. Ne pas s'y référer pour décision live.

### Configuration v9 (figée — non déployable mais base de référence du code existant)

Les paramètres v9 restent figés dans `ninjatrader/HurstMR_Apex.cs` et `pages/5_Backtest.py` :

H<0.58 · HW=50 · LB=19 · k=2.75σ · SL=0.65×std (min 5 pts, max 20 pts) · TP overshoot=0.15σ · Timeout=120 bars · Trail ON @ H>0.51 · std_min=1.0 (Python only) · Skip 14h UTC (Python only) · Kelly 12%, plafond 12 MNQ.

### Phase d'exploration d'edge — CLOSE (2026-05-14)

**Étape 1 terminée.** Quatre mini-validations menées sur 5 ans MNQ/ES tick-realistic (wicks intra-bar, commissions $1.10/RT, slippage 1 tick, splits LdP Train 2021-05→2024-05 / Valid 2024-05→2025-05 / Holdout intouché). Résultats complets dans `01_research/outputs/` :

| Mini-validation | Verdict | Détail |
|---|---|---|
| #1 Multi-TF MNQ (`outputs/multi_tf/`) | 🟢 Candidat **baseline** | MR 15h NY locale — 5min PF 2.03→2.02 OOS ; 15min PF 2.68→3.65 OOS. **Mesuré sans contraintes Apex.** |
| #2 ES cross-asset (`outputs/es/`) | 🟡 Dégradé | Edge 15h NY existe sur ES mais Sharpe 0.63 < seuil, DD -$15k. Edge **MNQ-spécifique**, pas de robustesse cross-asset. |
| #3 Momentum MNQ (`outputs/momentum/`) | 🔴 No edge | PF 0.37, toutes heures et tous mois perdants. Hypothèse "H>0.5 ⇒ momentum intraday profitable" invalidée empiriquement. |
| #4 Apex-compliance (`outputs/apex_compliant/`) | 🔴 **Candidat KO sous Apex** | Force-flat 15:59 + cutoff entrée 15:55 appliqués → 5min Train PF 2.03→**0.80**, 15min Train PF 2.68→**0.77**. Cycle Apex : **0/61 mois passés**. L'edge se complète après 16:00 NY (close auction) — Apex verrouille le trader dehors. |

**Statut du candidat MR 15h NY** : edge réel en **baseline** (cohérent littérature — End-of-Day Reversal, gamma hedging des MM, flux MOC) mais **non capturable en l'état sous contraintes Apex**. Le backtester baseline laissait les trades tourner après 16:00 NY ; Apex l'interdit. L'exit actuel (z-score revient à ±0.5) est trop lent.

**Étape 2 — Sprint re-engineering exit (EN COURS)** : avant toute validation lourde, déterminer si l'edge se capture avec un exit qui se résout **avant** le force-flat 16:00. Spec : `docs/superpowers/specs/2026-05-14-sprint-reengineering-eod-reversal-design.md`.
- Grille délibérée de 8 configs d'exit (z-score serré, TP points fixes, exit temps fixe, trailing, hybride) × {5min, 15min} = 16 trials
- Tout mesuré **Apex-compliant dès le départ** ; config-contrôle C0 qui doit reproduire mini-val #4
- Gate de promotion : PF > 1.5 ∧ Sharpe > 1.0 sur Train Apex-compliant, tient sur Valid
- Issue : config promue → vraie validation LdP (DSR/CPCV/Monte Carlo, backtester NT8-compatible, décomposition LONG/SHORT, stress test régime) ; ou aucune → edge EOD acté Apex-mort, nouvelle hypothèse
- Holdout 2025-05→2026-05 **INTOUCHÉ** jusqu'à la fin de la validation rigoureuse

## Données

- Source : à préciser/confirmer à chaque nouveau backtest
- Timezone : à confirmer (UTC vs NY) — **critique pour Hurst rolling et heure de skip 14h NY**
- Granularité : bars (préciser le timeframe à chaque session)
- Format attendu : OHLCV + timestamp, indexé pandas DatetimeIndex tz-aware

## Règles Apex à intégrer dans TOUT backtest

### Apex Trader Funding — $50K Performance Account EOD (règles officielles, vérifiées depuis le help-center Apex 2026-05-14)

> Compte **PA EOD** (Performance Account, Simulated Funded) — **plus l'Eval**. Pas de profit target, pas de limite de temps. Le compte vit tant qu'on ne touche pas le seuil EOD et qu'on respecte la règle d'inactivité.

| Règle | Valeur PA EOD 50K | Note |
|-------|-------------------|------|
| **Drawdown EOD** | **$2,000** | Seuil calculé 1×/jour à la clôture (16:59:59 ET) sur la balance de clôture. Trail les **clôtures journalières** les plus hautes, ne descend JAMAIS. **Enforced en temps réel intraday** : si la balance (PnL non réalisé inclus) touche le seuil à tout moment → liquidation + **PA fermé définitivement**. Seuil initial = $48,000. |
| **Lock du seuil EOD** | **$50,100** | Une fois qu'une clôture journalière atteint ≥ $52,100, le seuil se fige à $50,100 **à vie**. Objectif stratégique nº1 : verrouiller ce plancher au plus vite. |
| **Daily Loss Limit (DLL)** | **tier-based** | $1,000 (L1/L2) · $2,000 (L3) · $3,000 (L4). Fixe pour la session, monitored intraday sur l'equity totale (réalisé + non réalisé). Touché = positions liquidées + journée stoppée, **compte survit**, reprise session suivante (reset 18h ET). |
| **Contrats max** | **tier-based** | 2 / 3 / 4 / 4 contrats standard = **20 / 30 / 40 / 40 MNQ** (10 micros = 1 standard). Ordre au-delà = rejeté sans pénalité. Limite sur l'exposition totale tous instruments confondus. |
| **Scaling tiers (50K)** | balance EOD → tier | L1 $0-1,499 (2 ctr · DLL $1k) · L2 $1,500-2,999 (3 ctr · DLL $1k) · L3 $3,000-5,999 (4 ctr · DLL $2k) · L4 $6,000+ (4 ctr · DLL $3k). Tier figé 1×/jour à la clôture sur la balance EOD, vaut pour la session suivante. Plancher L1, plafond L4. |
| **Profit target** | **aucun** | Compte funded — pas de cible à atteindre. |
| **Limite de temps** | **aucune** | Confirmé. |
| **Inactivité** | **≥ 2 jours à ≥ $50 net / 30 j glissants** | Sinon dormant à 15 j, fermeture définitive à 30 j. La strat doit produire des journées vertes régulières — un edge "rare big wins" pur risque la fermeture pour inactivité. |
| **Flat à la clôture** | **15:55 NY** | Règle perso BB (= 21:55 Paris), plus conservateur que le hard rule Apex "before market close" (~16:59:59 ET). Aucune position ouverte après **15:55 America/New_York** — force-flat MTM de toute position à 15:55 NY, aucune entrée qui resterait ouverte au-delà. |
| **Hedging** | **interdit** | Long + short simultané même instrument OU corrélé = prohibé. Un dual-config LONG/SHORT doit être **mutuellement exclusif** (machine à états, jamais les deux ouverts). |
| **Stratégies high-risk** | **interdit** | "Small TP + disproportionately large SL" (ex. 5 ticks TP / 150 ticks SL) = prohibé. ⚠️ Tension directe avec le théorème de Leung — le ratio risk:reward ne doit pas tomber dans la zone prohibée. |
| **Automatisation** | **interdite** | "No Automation or Algorithm Usage allowed" (Prohibited Activities). ⚠️ **Contredit frontalement "Couche 3 — Live full auto".** Ticket de clarification envoyé à Apex le 2026-05-14 — **réponse en attente**. Tant que non tranché : ne pas présumer que le full-auto est déployable. |

### Impact sur la conception du backtester

1. **DD EOD, pas intraday** : le seuil ne bouge que sur les **clôtures** journalières. Les swings intraday sont "gratuits" tant qu'on ne touche pas le seuil. Bien plus tolérant que le trailing intraday de l'Eval — mais le seuil reste "collé en haut" après un repli (il ne suit pas la balance vers le bas). Modéliser : `seuil = min(plus_haute_clôture_EOD − 2000, 50100)`, monotone croissant.
2. **DLL + contrats tier-based** : le backtester doit recalculer le tier chaque jour sur la balance EOD de la veille, et appliquer la DLL + le plafond contrats du tier sur la session.
3. **DLL ≠ fin de compte** : DLL touchée = journée stoppée, compte vivant. Seuil EOD touché = compte mort. Deux mécaniques distinctes à simuler.
4. **Force-flat à 15:55 NY** (règle perso BB, fuseau `America/New_York` — gère le DST automatiquement) : toute position liquidée MTM à 15:55 NY, aucune entrée qui resterait ouverte au-delà.
5. **Pas de hedging** : si la stratégie a un volet LONG et un volet SHORT, ils doivent être mutuellement exclusifs.
6. **Ratio risk:reward** : éviter la zone "high-risk strategy" prohibée (TP minuscule / SL énorme).
7. **News blackout** (FOMC, NFP, CPI) : recommandé. Le news-trading "qui chase le marché" est prohibé ; une stratégie systématique normale pendant les news est autorisée.

### À confirmer

- **Automatisation** : ticket envoyé à Apex le 2026-05-14, réponse en attente. Détermine si le livrable final est un algo full-auto ou un edge systématique à exécution manuelle.

> Force-flat **résolu** (2026-05-14) : BB fixe sa propre coupure à **15:55 NY** — plus conservateur que le cutoff Apex. Le sprint EOD reversal ("Apex-mort", force-flat 15:55-15:59) reste donc valide, son verdict ne change pas avec le passage en PA EOD.

## Workflow standard

```
Recherche Python (Jupyter)  →  Backtest massif (vectorbt)  →  
Validation event-driven (backtrader)  →  Rapport (QuantStats + López de Prado checks)  →  
Spec écrite (.md)  →  Implémentation NinjaScript (C#)  →  
Backtest NinjaTrader Strategy Analyzer  →  Sim live 2-4 semaines  →  Live Apex
```

**Aucune étape ne se saute.** Surtout pas le sim live avant Apex.

## Comment je veux que tu m'aides

- **Critique frontalement** : si une stratégie sent l'overfit, dis-le. Pas de validation de complaisance.
- **Robustesse > performance brute** : un Sharpe 2 stable vaut mieux qu'un Sharpe 4 fragile.
- **Walk-forward et OOS par défaut** : aucune optim sans validation hors-échantillon.
- **Méthodes López de Prado** : Purged K-Fold CV, Combinatorial Purged CV, Deflated Sharpe Ratio, fractional differentiation quand pertinent.
- **Code Python vectorisé** : NumPy/Pandas, pas de boucles `for` sur les bars sauf nécessité absolue. Préfère `numba` ou `vectorbt` pour les calculs lourds.
- **Code NinjaScript** : conventions NT8 strictes, `OnBarUpdate()` propre, gestion d'état explicite, pas de magic numbers.
- **Quand tu suggères une amélioration, fournis le test pour la valider**, pas juste l'idée.
- **Si tu ne sais pas, dis-le.** Pas de bullshit confident. En quant, une fausse certitude peut coûter un compte.

## Anti-patterns interdits

- ❌ Stratégie qui n'a pas survécu à un Monte Carlo permutation des trades
- ❌ Paramètre "optimal" trouvé sans walk-forward
- ❌ Optimisation sur l'historique complet sans holdout préservé
- ❌ "Ça marche en backtest donc on déploie" — sim live obligatoire avant Apex
- ❌ Sharpe brut sans Deflated Sharpe quand on a testé plusieurs configs
- ❌ Backtest sans modélisation du slippage et des commissions futures (CME $4-5 aller-retour)
- ❌ Backtest sans simulation du DD EOD Apex (seuil sur clôtures journalières, enforced intraday) ni de la DLL tier-based
- ❌ Stop loss serré + take profit lointain sur stratégie MR (théorème de Leung : MR demande SL large + TP court)
- ❌ Pine Script TradingView comme source de validation finale
- ❌ Streamlit pour de la recherche lourde (utiliser Jupyter)

## Références acceptées (par ordre de priorité)

1. **Marcos López de Prado** — *Advances in Financial Machine Learning* (2018), *Machine Learning for Asset Managers* (2020), papers SSRN. Référence #1 absolue sur l'overfitting, le CV financier, le Deflated Sharpe, le meta-labeling.
2. **Papers peer-reviewed (WebFetch / WebSearch autorisés)** :
   - **SSRN** (Quantitative Finance, Financial Economics Network)
   - **ArXiv** q-fin (Quantitative Finance), stat.ML, math.ST
   - **ISSN journals** : Journal of Finance, Journal of Financial Economics, Journal of Portfolio Management, Journal of Financial Markets, Review of Financial Studies, Mathematical Finance, Quantitative Finance, Journal of Empirical Finance, Journal of Futures Markets
3. **Ernest Chan** — *Algorithmic Trading* (2013), *Machine Trading* (2017). Très appliqué retail/prop, excellent sur mean reversion et cointégration.
4. **Robert Carver** — *Systematic Trading* (2015), *Leveraged Trading* (2019). Référence sur le sizing systématique et la robustesse.
5. **Andrew Lo** — papers sur l'Adaptive Markets Hypothesis, microstructure
6. **Roman Michael Paolucci — Quant Guild Library** : [github.com/romanmichaelpaolucci/Quant-Guild-Library](https://github.com/romanmichaelpaolucci/Quant-Guild-Library) — Colombia University Quant. Lectures 25 (fBm), 28 (Gambler's Ruin), 34, 36 (Kelly), 44 (Time Series), 47/51/72/74 (HMM/Régimes), 48 (Trading Metrics), 49 référencées dans `SYSTEM_PLAN.md` et `learning/25_hurst_mr.md`. **Autorisé pour citations et code de référence.**
7. **Documentation officielle** : QuantLib, vectorbt, backtrader, statsmodels, NinjaTrader 8 NinjaScript reference
8. **Quantpedia** pour stratégies publiées avec références académiques
9. **Hudson & Thames** (mlfinlab) — implémentation propre des méthodes López de Prado

**Sources exclues :** réseaux sociaux, YouTube non académique, blogs non vérifiés, forums grand public, "gourous" trading, signaux Discord/Telegram, indicateurs TradingView non documentés.

## Style de communication

- **Français**, tutoiement, ton direct
- **Dense**, pas de remplissage, pas de paraphrase de la question
- Pas d'introduction du genre "Excellente question !" — entre dans le sujet directement
- Quand je pose une question floue, demande **une** clarification précise plutôt que de partir dans tous les sens
- Quand tu donnes du code, **explique les choix non triviaux** (pourquoi cette méthode et pas une autre)
- Pas de name-dropping pédagogique gratuit
- Tu peux m'appeler **BB**

## Checklist pré-déploiement Apex

Avant qu'une stratégie passe sur mon compte live Apex, valide chacun de ces points :

- [ ] Walk-forward sur ≥ 3 fenêtres avec ≥ 70% de fenêtres OOS rentables
- [ ] Monte Carlo permutation : p-value < 0.05 sur le Sharpe vs aléatoire
- [ ] Deflated Sharpe Ratio > 0 (compense le nombre de configs testées)
- [ ] Max DD simulé < 50% du DD EOD Apex ($1,000 sur $2,000) — et aucune journée ne touche le seuil EOD en intraday
- [ ] Stress test sur les périodes rouges historiques (Oct 2018, Mar 2020, Sep 2022, Oct historique)
- [ ] Re-backtest dans NinjaTrader Strategy Analyzer cohérent avec backtest Python (écart P&L < 10%)
- [ ] Sim live ≥ 2 semaines sur compte démo NinjaTrader, cohérent avec backtest
- [ ] Spec écrite à jour dans `04_live/strategy_spec_vX.md`
- [ ] Plan de coupure défini : à quel DD je coupe la strat ? Quel jour de la semaine je relance ?

## Règle absolue

Le but n'est **pas** de maximiser le P&L théorique. Le but est de **passer Apex puis rester funded** sur la durée. Toute décision technique passe par ce filtre.