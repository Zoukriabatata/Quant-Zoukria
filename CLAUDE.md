# CLAUDE.md — Contexte Quant Trading (Myriam / BB)

## Profil opérateur

- Trader systématique sur **MNQ** (Micro Nasdaq futures)
- Compte **Apex Trader Funding $50K Eval** — règles complètes en §"Règles Apex"
- **Je ne code pas.** Je dirige la conception, Claude implémente. Quand je décris une logique, traduis-la en code propre sans me demander d'écrire les bouts.
- Stack technique :
  - **Python** (recherche, backtest, signaux) — JupyterLab principal, Streamlit pour interfaces finales uniquement
  - **SQLite** (journal de trades, persistance)
  - **NinjaTrader 8 + Rithmic** (exécution)
  - **C# / NinjaScript** (stratégies live full auto + bridge `rithmic_bridge.cs` mode semi-auto)
- Application actuelle : 14 pages Streamlit (journal, backtester, live signal MNQ, alertes, crypto swing, SOL live, etc.)

## Appellation

Tu peux m'appeler **BB**.

## Statut actuel — Recherche d'edge en cours (NO LIVE)

> ⚠️ **v9 NON déployable Apex — PF 1.02 · DD -$22,748 mesurés en NT8 Strategy Analyzer tick-realistic.** Aucune stratégie validée pour live actuellement. Phase de recherche d'edge ouverte sur MNQ.

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

### Phase de recherche d'edge en cours

- **Étape 1** — Exploration Jupyter `01_research/notebooks/01_exploration_MR_MNQ.ipynb` : identifier si un edge MR existe dans des "poches" temporelles (heure NY locale, mois, jour de semaine) sur MNQ tick-realistic. Méthodologie López de Prado stricte (Train 2021-05→2024-05 / Valid 2024-05→2025-05 / Holdout 2025-05→2026-05 intouchable).
- **Étape 2** (conditionnelle) — Construction d'un backtester Python NT8-compatible (wicks intra-bar, commissions $1.10/RT, slippage 1 tick, bracket orders) pour grid search massive **uniquement si Étape 1 trouve une poche avec PF>1.5, Sharpe>1, DD<$1.5k sur 6 mois glissants**. Validation fidélité Python ↔ NT8 obligatoire sur 5+ configs (écart < 15%) avant tout usage.

## Données

- Source : à préciser/confirmer à chaque nouveau backtest
- Timezone : à confirmer (UTC vs NY) — **critique pour Hurst rolling et heure de skip 14h NY**
- Granularité : bars (préciser le timeframe à chaque session)
- Format attendu : OHLCV + timestamp, indexé pandas DatetimeIndex tz-aware

## Règles Apex à intégrer dans TOUT backtest

### Apex Trader Funding — $50K Evaluation (config officielle 2026)

| Règle | Valeur | Note |
|-------|--------|------|
| **Profit Target** | **$3,000** | À atteindre pour passer en Performance Account (PA) |
| **Trailing DD (SL max)** | **$2,000** | Plafond cumulé en intraday, simulé en temps réel |
| **Daily Loss Limit** | **$1,000** | Stop trading le jour si atteint |
| **Contrats max mini** | **10** | ES, NQ, CL, GC, ZN, etc. |
| **Contrats max micro** | **40** | MNQ, MES, MCL, MGC, MNG, M2K, MYM, etc. |
| **Flat obligatoire** | **avant 16h NY** | Aucune position ne peut être ouverte après 16h00 NY locale |
| **Durée max challenge** | **1 mois** | Si target $3,000 pas atteint en 1 mois → challenge échoué |

### Impact sur la conception du backtester

1. **Trailing DD intra-journalier** simulé en temps réel (pas en EOD seulement). Un backtest qui ne le simule pas est **invalide** pour décision Apex.
2. **Force-flat 15h59 NY** : tout trade ouvert à 15h59 NY doit être liquidé MTM. Pas de position carry-over jusqu'à 16h.
3. **Pas d'entrée après 15h55 NY** (marge de sécurité 4 min pour fermer proprement).
4. **Time-to-target** : sur 21-22 jours de trading dans le mois, le P&L moyen requis est ~$140-$150/jour à 1 contrat. Sizing Kelly indispensable pour atteindre $3K en 1 mois.
5. **News blackout** (FOMC, NFP, CPI) : filtre recommandé, pas obligatoire Apex mais bonnes pratiques.

### À vérifier (non-confirmé dans la spec ci-dessus)

- **Consistency rule** : applicable en Eval ou seulement en Performance Account ? (Règle : meilleur jour ≤ X% du profit total — Apex PA = 50%, Eval potentiellement libre). À confirmer Apex docs.
- **Mix mini + micro** : Apex permet généralement les deux en équivalent (1 mini = 4 micros). À confirmer avant tout sizing combiné.

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
- ❌ Backtest sans simulation du trailing DD Apex en temps réel
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
- [ ] Max DD simulé < 50% du trailing DD Apex ($1,000 sur $2,000)
- [ ] Stress test sur les périodes rouges historiques (Oct 2018, Mar 2020, Sep 2022, Oct historique)
- [ ] Re-backtest dans NinjaTrader Strategy Analyzer cohérent avec backtest Python (écart P&L < 10%)
- [ ] Sim live ≥ 2 semaines sur compte démo NinjaTrader, cohérent avec backtest
- [ ] Spec écrite à jour dans `04_live/strategy_spec_vX.md`
- [ ] Plan de coupure défini : à quel DD je coupe la strat ? Quel jour de la semaine je relance ?

## Règle absolue

Le but n'est **pas** de maximiser le P&L théorique. Le but est de **passer Apex puis rester funded** sur la durée. Toute décision technique passe par ce filtre.