# 09b — Profitable vs Tradable
# "Pourquoi les stratégies meurent en live"

> **Video :** [Profitable vs Tradable — Why Most Strategies Fail Live — Roman Paolucci](https://github.com/romanmichaelpaolucci/Quant-Guild-Library/tree/main/2025%20Video%20Lectures/77.%20Profitable%20vs%20Tradable%20-%20Why%20Most%20Strategies%20Fail%20Live)
> **Code :** [Quant Guild Library #77](https://github.com/romanmichaelpaolucci/Quant-Guild-Library/tree/main/2025%20Video%20Lectures/77.%20Profitable%20vs%20Tradable%20-%20Why%20Most%20Strategies%20Fail%20Live)

---

# ============================================
# APPRENTISSAGE — C'est quoi ? Pourquoi ?
# ============================================

## La distinction critique

```
PROFITABLE = le backtest montre un profit

TRADABLE   = la stratégie RESTE profitable
             en conditions réelles, sur le long terme
```

Ce sont deux choses différentes. La plupart des stratégies qui paraissent "profitable" en backtest ne sont **pas tradables** en live.

## Pourquoi elles meurent en live

Roman identifie les causes principales :

```
1. SLIPPAGE : tu n'entres pas au prix que tu vois
              → Chaque trade coûte plus que prévu

2. REGIME CHANGE : le marché change de comportement
                   → Ta stratégie calibrée sur le passé n'est plus valide

3. PSYCHOLOGIE : tu ne suis pas les règles en live
                 → Tu coupe les winners trop tôt, tu laisse les losers courir

4. CAPACITÉ : la stratégie est profitable avec 1 contrat
              mais le slippage s'aggrave avec 40 contrats

5. FRÉQUENCE RÉELLE : moins de trades que prévu en live
                      → Statistiques moins stables
```

## Le test "tradable"

Une stratégie est **tradable** si elle satisfait ces critères :

```
a) Robustesse des paramètres
   → Si tu changes band_k de 1.5 à 1.3 ou 1.7, les résultats sont similaires

b) Survie aux coûts réels
   → Slippage + commissions inclus, le Sharpe reste > 0.5

c) Out-of-sample positif
   → La dernière période (pas utilisée pour calibrer) est profitable

d) Drawdown psychologiquement supportable
   → Tu peux tenir 10 losses de suite sans changer la stratégie

e) Volume réaliste
   → Apex limite 40 contrats PA → le sizing est exécutable
```

---

# ============================================
# MODEL — Les maths
# ============================================

## 1. Slippage — l'impact réel

**Slippage** = différence entre le prix théorique (backtest) et le prix réel (live)

Pour MNQ avec slippage de 2 ticks = 0.5 pts :

$$\text{Coût réel} = \text{Coût backtest} + 2 \times 0.5 \times \$2 = \text{Coût} + \$2$$

Sur 200 trades/an × $2 = **$400/an en slippage seul.**

Sur 40 contrats : **$400 × 40 = $16,000/an** en friction.

**Impact sur le Sharpe :**

$$\text{Sharpe}_{live} \approx \text{Sharpe}_{backtest} - \frac{\text{Coût friction annuel}}{\sigma_{P\&L}}$$

Avec backtest Sharpe = 1.2 et friction = $16k sur $50k de capital :

$$\text{Sharpe}_{live} \approx 1.2 - \frac{16000}{?} \quad \text{(depends on P\&L vol)}$$

**Règle pratique :** tester avec slippage × 2 dans le backtest. Si la stratégie reste profitable, elle est robuste.

## 2. Robustesse des paramètres

Une stratégie tradable est **peu sensible** aux paramètres.

Test de sensibilité pour `band_k` :

| `band_k` | Trades/an | Net P&L | Sharpe |
|---------|----------|---------|-------|
| 1.2 | 320 | $6,200 | 0.9 |
| **1.5** | **220** | **$7,800** | **1.1** |
| 1.8 | 140 | $5,100 | 0.85 |
| 2.0 | 90 | $3,500 | 0.7 |

Si la stratégie est robuste → tous les Sharpe restent positifs, la variation est graduelle.
Si la stratégie est fragile → elle s'effondre hors d'un range étroit de `band_k`.

## 3. Regime change — le problème principal

Le marché change de régime. Le modèle OU calibré sur 2024 peut être invalide en 2026.

**Indicateurs de changement de régime :**

| Indicateur | Formule | Signal d'alerte |
|-----------|---------|-----------------|
| Hit rate glissant (30j) | WR sur les 30 derniers jours | < 35% pendant 2 semaines |
| σ_stat | Volatilité stationnaire OU | > 2× la moyenne historique |
| Drawdown consécutif | Nombre de trades consécutifs perdants | > 7 |
| P&L moyen par trade | Moyenne glissante | Négative sur 20 trades |

**Réponse au régime change :**

```
Si WR < 35% sur 30j → ARRÊTER et recalibrer
Si σ_stat > 2× normale → ARRÊTER (marché trending, OU invalide)
Recalibrer l'OU sur données récentes
Ne jamais "forcer" la stratégie quand le régime change
```

## 4. La règle de Paolucci — "Dead Strategy Walking"

Roman identifie une pattern classique :

```
Semaine 1 : perte 5 trades
Décision A : "C'est normal, je continue"  ← correct si dans la distribution attendue
Décision B : "Je double la taille pour rattraper" ← ERREUR (martingale)
Décision C : "Je change les paramètres" ← ERREUR (overfitting en temps réel)

La bonne réponse :
→ Vérifier si la perte est DANS la distribution simulée du backtest
→ Si oui : continuer mécaniquement
→ Si non (anomalie statistique) : stopper et diagnostiquer
```

## 5. Test statistique : la perte est-elle "normale" ?

Le backtest Monte Carlo donne la distribution des drawdowns attendus.

$$P(\text{drawdown} > D_{observed}) > 5\% \rightarrow \text{Normal, continuer}$$
$$P(\text{drawdown} > D_{observed}) < 1\% \rightarrow \text{Anomalie, stopper}$$

**Dans le backtest :** la simulation Monte Carlo calcule la distribution de l'equity curve.
Si le drawdown live dépasse le percentile 99% du Monte Carlo → stratégie potentiellement cassée.

## 6. Capacity — le problème de scalabilité

La stratégie backtest avec $N$ contrats. En live avec $M$ contrats, le slippage augmente.

$$\text{Slippage}(M) = \text{Slippage}(1) \times \sqrt{M}$$

(empirique — le slippage scale pas linéairement pour les petits contrats MNQ)

Pour MNQ (marché très liquide), l'impact est minimal jusqu'à ~200 contrats. Apex limite à 40-60 → pas de problème de capacité.

---

# ============================================
# LECON — Exercices pratiques
# ============================================

## Exercice 1 : Test de robustesse

Ton backtest avec `band_k=1.5` donne Sharpe 1.1.

Tu testes `band_k=1.2` → Sharpe 0.9. Et `band_k=1.8` → Sharpe 0.85.

**Question :** La stratégie est-elle robuste ?

**Réponse :** Oui. La dégradation est graduelle (pas d'effondrement). Les Sharpe restent positifs dans la plage testée. La stratégie est robuste à ce paramètre.

## Exercice 2 : Diagnostiquer un live qui sous-performe

Live : 3 semaines, 45 trades, WR = 38%, P&L = -$800.

Backtest attendu : WR = 52%, P&L = +$1,200 sur 45 trades.

**Checklist :**
- [ ] Slippage réel > 2 ticks en moyenne ?
- [ ] σ_stat actuel > 2× la moyenne backtest ?
- [ ] Régime de marché = forte tendance (Kalman OU invalide) ?
- [ ] Le signal confirme bien avant entrée ?
- [ ] Look-ahead bias dans le live code ?

## Exercice 3 : La décision "stopper ou continuer"

Backtest Monte Carlo 5th percentile equity curve : -$1,800 à 45 trades.
Live equity : -$800.

**Question :** Est-ce une anomalie ?

**Réponse :** Non. -$800 est MIEUX que le 5th percentile (-$1,800). C'est dans la distribution normale. Continuer mécaniquement.

---

# ============================================
# RESUME — Fiche de revision
# ============================================

**PROFITABLE ≠ TRADABLE**

| | Profitable | Tradable |
|--|-----------|---------|
| Backtest | ✓ | ✓ |
| Avec slippage réel | ? | ✓ |
| Paramètres robustes | ? | ✓ |
| Out-of-sample | ? | ✓ |
| Psychologiquement tenable | ? | ✓ |

**5 CAUSES D'ÉCHEC EN LIVE :**
1. Slippage → inclure dans le backtest (2+ ticks MNQ)
2. Regime change → surveiller WR glissant 30j
3. Psychologie → suivre les règles mécaniquement
4. Overfitting → test de robustesse des paramètres
5. Capacité → OK pour MNQ jusqu'à 200+ contrats

**TEST DE TRADABILITÉ :**
- Sharpe > 0.5 avec slippage × 2 ?
- OOS positif (20% des données) ?
- Sensibilité paramètres : changement ±20% → performance encore positive ?
- Drawdown live dans le 95th percentile Monte Carlo ?

**RÈGLE D'OR :**
```
Perte dans la distribution simulée → CONTINUER
Perte hors distribution → STOPPER, diagnostiquer, ne jamais changer
les paramètres en live pour "rattraper"
```

**DANS TON SYSTÈME :**
- `slippage_ticks = 2` dans le backtest → réaliste
- Monte Carlo → donne la distribution des drawdowns attendus
- `max_trades_per_day = 2` → limite le drawdown quotidien (DLL Apex)
- Mode Funded PA `max_contracts = 40` → sizing exécutable en live

**LETTRES ET SYMBOLES :**

| Terme | Signification |
|-------|---------------|
| OOS | Out-of-sample : données non utilisées pour calibrer |
| WR glissant | Win rate calculé sur les N derniers trades (dérive de régime) |
| Slippage | Écart entre prix théorique et prix réel d'exécution |
| Regime change | Le marché change de comportement statistique |
| Monte Carlo | Simulation de milliers de chemins pour estimer les risques |
| DLL | Daily Loss Limit — limite de perte quotidienne Apex |
