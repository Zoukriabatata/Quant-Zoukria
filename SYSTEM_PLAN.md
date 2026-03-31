# SYSTÈME QUANT — PLAN COMPLET
## Objectif : Sharpe 1.2 → 1.5 · Edge pur · Robuste

> Sources : Quant Guild Library (Roman Paolucci) — Lectures 28, 34, 36, 47, 48, 49, 51, 72, 74
> Architecture actuelle : Kalman OU · GARCH · Half-Kelly · QQQ→MNQ · Apex 50K EOD

---

## 0. POURQUOI 1.2–1.5 ET PAS PLUS

```
Lecture 48 — "Trading Metrics are Misleading"

Le Sharpe est une VARIABLE ALEATOIRE.
Avec 250 trades, l'intervalle de confiance à 95% = ±0.6 Sharpe.
→ Un Sharpe backtest de 2.0 peut etre 1.0 en live.
→ Un Sharpe cible de 1.2–1.5 = edge REEL, pas overfitting.

Sharpe > 2.0 sur 3 mois = faux signal (trop peu de trades).
Sharpe 1.2–1.5 stable sur 4-5 mois = edge prouvé.

Formule :
  Sharpe = (μ_trades × √N_annuel) / σ_trades
  où N_annuel = trades/an × jours de trading

  Pour 1 trade/jour × 250 jours → N = 250
  Sharpe 1.3 nécessite μ/σ = 1.3 / √250 = 0.082
  → chaque trade doit gagner 8.2% de son écart-type
```

---

## 1. ARCHITECTURE GLOBALE DU SYSTÈME

```
┌─────────────────────────────────────────────────────────┐
│                    COUCHE DONNÉES                        │
│  QQQ 1-min (yfinance) → clean_spikes → barres OHLCV     │
└───────────────────────────┬─────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────┐
│                  COUCHE RÉGIME (FILTRE)                  │
│                                                          │
│  GARCH(1,1) → variance conditionnelle σ²_t              │
│       +                                                  │
│  HMM 3 états → régime {LOW / MED / HIGH}                │
│                                                          │
│  Règle : trade UNIQUEMENT en LOW et MED                  │
│  Règle : taille réduite en MED vs LOW                    │
└───────────────────────────┬─────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────┐
│                  COUCHE SIGNAL                           │
│                                                          │
│  Kalman OU → fair_value + sigma_stat                     │
│  Signal LONG  : close < FV - k × σ_stat                 │
│  Signal SHORT : close > FV + k × σ_stat                 │
│                                                          │
│  Filtre qualité : k_min=1.5σ, k_max=4.0σ                │
│  (1.0σ → trop de bruit, 4.0σ → bad tick)                │
└───────────────────────────┬─────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────┐
│                  COUCHE SIZING (KELLY)                   │
│                                                          │
│  f* = (b×p - q) / b    [Kelly complet]                  │
│  Half-Kelly = f*/2     [utilisé en pratique]             │
│                                                          │
│  Sizing par régime :                                     │
│  LOW   → 10% du DD restant (Half-Kelly standard)        │
│  MED   →  6% du DD restant (dégradé)                    │
│  PUSH  → 15% du DD restant (si <80% objectif, fin mois) │
│  SÉCURITÉ → 4% du DD restant (si >80% objectif)         │
└───────────────────────────┬─────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────┐
│                  COUCHE RISK MANAGEMENT                  │
│                                                          │
│  SL = ATR(14) × 1.5 [max 15 pts, min 5 pts]             │
│  TP = retour au fair value Kalman                        │
│  Daily loss stop = 80% du daily limit Apex              │
│  Gambler's Ruin stop : 2 pertes consec → pause           │
│  EOD flat : 21h45 UTC obligatoire                        │
└─────────────────────────────────────────────────────────┘
```

---

## 2. UPGRADE RÉGIME — GARCH + HMM (Lecture 47, 51, 72)

### Pourquoi l'upgrade

```
Problème GARCH seul :
  GARCH classe la volatilité ABSOLUE.
  Mais le marché a des régimes LATENTS (cachés).
  Un jour MED avec tendance ≠ un jour MED en range.
  HMM capte les ÉTATS, pas juste la volatilité.

Roman (Lecture 72) :
  "Our regime model uses 3 latent states.
   The transition matrix is STICKY : 90% de rester dans le même état."
  Sticky = stable, pas de faux flips.
```

### Paramètres HMM validés par Roman (Lecture 74)

```python
# Matrice de transition (sticky states)
TRANSITION = np.array([
    [0.90, 0.08, 0.02],   # LOW  → LOW=90%, MED=8%, HIGH=2%
    [0.10, 0.80, 0.10],   # MED  → LOW=10%, MED=80%, HIGH=10%
    [0.05, 0.05, 0.90],   # HIGH → LOW=5%,  MED=5%,  HIGH=90%
])

# Distributions d'émission (volatilité bar = (H-L)/C)
EMIT_MEAN = [0.0015, 0.0035, 0.0080]   # LOW, MED, HIGH
EMIT_STD  = [0.0008, 0.0015, 0.0030]

# Mise à jour Bayésienne (filtre en temps réel)
def update_regime(prior, obs_vol, transition, emit_mean, emit_std):
    # 1. Prédiction : appliquer matrice de transition
    predicted = transition.T @ prior
    # 2. Vraisemblance : P(obs | état)
    likelihood = np.array([
        norm.pdf(obs_vol, emit_mean[s], emit_std[s]) for s in range(3)
    ])
    # 3. Update Bayésien (Bayes' Rule)
    posterior = predicted * likelihood
    return posterior / posterior.sum()   # normaliser
```

### Règle de trading par régime

```
HMM régime LOW  → signal actif, sizing STANDARD (10% DD)
HMM régime MED  → signal actif, sizing PRUDENT  (6% DD)
HMM régime HIGH → PAS DE TRADE, attendre retour MED/LOW
```

---

## 3. SIGNAL — CALIBRATION KALMAN (Lecture 44)

### Problème actuel : k=1.0σ

```
Lecture 44 — Time Series :
  "Filtering = reducing noise using past and current data"
  Un seuil trop bas (k=1.0) → entre dans le BRUIT, pas le signal.
  Le prix est NATURELLEMENT dans les bandes 68% du temps (1σ).
  À k=1.0, on trade donc 32% des barres → trop fréquent.

Optimal pour MNQ mean reversion :
  k = 1.5σ → 13% des barres = signal rare = signal réel
  k = 2.0σ →  5% des barres = signal fort
  k_max = 4.0σ → au-dessus = bad tick, ne pas trader
```

### Paramètres cibles

```
band_k     = 1.5     (signal = prix > 1.5σ de la FV)
band_k_max = 4.0     (filtre bad ticks)
lookback   = 150     (barres, au lieu de 120)
R_mult     = 5.0     (inchangé)

Pourquoi 150 vs 120 :
  Plus long lookback → estimation OU plus stable
  Mais trop long (>200) → slow to adapt
  150 = compromis optimal pour 1-min QQQ
```

---

## 4. KELLY CRITERION — CALIBRATION CORRECTE (Lecture 36)

### Formule complète

```
f* = (b × p - q) / b

Paramètres depuis le backtest :
  p = 0.42        (win rate 42%)
  b = 2.75        (ratio win/loss moyen)
  q = 1 - 0.42 = 0.58

f* = (2.75 × 0.42 - 0.58) / 2.75
f* = (1.155 - 0.58) / 2.75
f* = 0.575 / 2.75
f* = 0.209  →  20.9% du capital

Half-Kelly = f*/2 = 10.5%  ≈ 10% du DD restant ✓

L'implémentation actuelle est CORRECTE.
```

### Kelly par régime (amélioration)

```
Lecture 36 : "Kelly suppose des rendements stables.
  En pratique : utilise une Kelly CONDITIONNELLE au régime."

LOW regime  : p_low ≈ 0.47, b_low ≈ 2.8  → f* = 21% → half = 10.5%
MED regime  : p_med ≈ 0.38, b_med ≈ 2.5  → f* = 13% → half = 6.5%
(HIGH skippé)

→ Sizing automatiquement plus petit en MED
  sans avoir à le coder manuellement.
```

---

## 5. GAMBLER'S RUIN — PROTECTION (Lecture 28)

```
P(ruin) = [1 - (p/q)^i] / [1 - (p/q)^N]

Avec :
  p = 0.42, q = 0.58
  p/q = 0.724
  i = DD restant en unités de risque/trade
  N = DD max en unités de risque/trade

Pour Apex 50K EOD :
  DD max = $2,000
  Risque/trade = $200 (10% × $2,000)
  i = 10 unités, N = 10 unités

  P(ruin depuis zéro) = [1 - 0.724^10] / [1 - 0.724^10]
  → Si on part de ZÉRO DD → P(ruin) = 100% statistiquement

SOLUTION (Lecture 28) :
  Ne JAMAIS utiliser 100% du budget de risque.
  Garder un buffer de 20% minimum.
  → DD utilisable = 80% × $2,000 = $1,600
  → Stop AVANT $1,600 (implémenté : PRUDENT si DD > 50%)

Règle pratique :
  DD < 30% utilisé : taille normale
  DD 30–50%        : taille réduite (-30%)
  DD > 50%         : taille mini, objectif survie
  DD > 80%         : STOP, ne plus trader ce mois
```

---

## 6. FILTRE TEMPOREL — TIME-OF-DAY

```
Lecture 34 — "How to Trade with an Edge" :
  L'edge est concentré dans certaines fenêtres.
  Les premières et dernières barres = bruit institutionnel (MM rebalancing).

Filtres à appliquer :
  NE PAS trader 09h30–10h00 ET   (open = bruit, spread large)
  NE PAS trader 15h30–16h00 ET   (close = bruit, EOD positioning)

  FENÊTRE OPTIMALE MNQ : 10h00–15h30 ET (16h00–21h30 UTC)

Traduction en UTC :
  session_start : 15h00 UTC (au lieu de 14h30)
  session_end   : 21h00 UTC (au lieu de 21h00)
  Exclusion open : ignorer les 30 premières barres de la session

En barres 1-min : skip les 30 premières barres après l'open
```

---

## 7. CONSISTENCY RULE — ÉVITER LES JOURS "JACKPOT"

```
Lecture 51 (HMM) + Apex PA Rule :
  Aucun jour > 50% du profit total du mois.
  Raison : un jour "jackpot" = outlier, pas l'edge.
  Si tu retires ce jour, l'edge doit toujours fonctionner.

Implémentation :
  Après chaque trade : vérifier si pnl_aujourd'hui > 50% × pnl_total_challenge
  Si oui : STOP pour aujourd'hui (même si le signal dit GO)
  Résultat : distribution des P&L plus régulière = Sharpe plus stable
```

---

## 8. MÉTRIQUES DE VALIDATION — SAVOIR SI L'EDGE EST RÉEL

```
Lecture 48 — "Why Trading Metrics are Misleading" :
  Les métriques sont des variables aléatoires.
  Il faut N trades suffisants pour les considérer significatives.

  Sharpe significatif à 95% : N > 36 / Sharpe²
  → Pour Sharpe cible 1.3 : N > 36 / 1.69 = 21 trades minimum
  → Pour Sharpe cible 1.2 : N > 36 / 1.44 = 25 trades minimum

MÉTRIQUES À SURVEILLER :

  1. Sharpe (annualisé)
     Cible : 1.2 – 1.5
     Alarme : < 0.8 sur 30 trades → recalibrer

  2. Profit Factor = ΣGains / ΣPertes
     Cible : 1.8 – 2.5
     Alarme : < 1.3 → edge dégradé

  3. Win Rate
     Cible : 38% – 48%
     !! Ne pas optimiser le WR isolément !!
     Un WR élevé avec petit b = Kelly négatif

  4. Recovery Factor = P&L total / Max DD
     Cible : > 2.0
     Alarme : < 1.0 → risque/reward mal calibré

  5. Stabilité du Sharpe (rolling 20 trades)
     Cible : Sharpe rolling dans [0.8, 2.5]
     Alarme : Sharpe rolling < 0 sur 10 trades → stop trading

  6. Calmar Ratio = Return annualisé / Max DD
     Cible : > 1.0
     Mesure la qualité du rendement par unité de risque
```

---

## 9. RÈGLES D'ADAPTATION — QUAND RECALIBRER

```
Lecture 58 — "Why Quant Models Break" :
  Les modèles se dégradent quand :
  1. Le régime change durablement (nouveau régime macro)
  2. La volatilité de la volatilité augmente (vol of vol)
  3. Le signal est crowdé (trop de gens font pareil)

SIGNAUX D'ALERTE :
  - Sharpe rolling 20 trades < 0.5  → recalibrer k et lookback
  - Win Rate sur 20 trades < 30%   → recalibrer ou pauser
  - Max DD > 60% du budget Apex    → stop immédiat, attendre
  - 3 jours de perte consécutifs   → pause 2 jours
  - ATR(14) × 3 > ATR moyen 20j   → vol extreme, skip

RECALIBRATION :
  Tous les 20 trades : re-estimer p, b, Kelly
  Tous les mois      : re-fitter GARCH + HMM sur données récentes
  Tous les 3 mois    : réévaluer lookback Kalman (peut dériver)
```

---

## 10. PLAN D'IMPLÉMENTATION PAR PRIORITÉ

```
PRIORITÉ 1 (Sharpe +0.2 estimé) — Filtre signal k=1.5σ
  Modifier band_k default de 1.0 → 1.5
  Plus rare mais plus propre

PRIORITÉ 2 (Sharpe +0.15) — Filtre horaire
  Skip les 30 premières barres post-open
  Skip les 30 dernières barres pre-close

PRIORITÉ 3 (Sharpe +0.1) — HMM upgrade
  Remplacer GARCH seul par GARCH + HMM Bayésien
  Utiliser la matrice de transition sticky de Roman

PRIORITÉ 4 (Sharpe +0.1) — Kelly conditionnel par régime
  6% en MED, 10% en LOW (au lieu de 10% fixe)
  Réduction automatique du risque en MED

PRIORITÉ 5 (Sharpe +0.05) — Consistency rule
  Ajouter stop si pnl_aujourd'hui > 50% × pnl_challenge

TOTAL estimé : Sharpe backtest 0.9 → 1.3–1.5
```

---

## 11. TABLEAU DE BORD — CE QU'ON DOIT VOIR EN LIVE

```
METRICS (mise à jour à chaque trade) :
  Sharpe rolling 20 trades    [vert >1.0 | orange 0.5-1.0 | rouge <0.5]
  Profit Factor               [vert >1.8 | orange 1.3-1.8 | rouge <1.3]
  Win Rate 20 trades          [vert 38-48% | orange hors range | rouge <30%]
  Kelly fraction actuelle     [afficher f* calculé dynamiquement]
  Régime HMM actuel           [LOW/MED/HIGH + probabilités]
  DD utilisé %                [barre de progression]
  Status GO/STOP              [basé sur toutes les règles]

ALERTES SONS :
  Signal entré → beep 440Hz (LONG) ou 880Hz (SHORT)
  Stop journalier atteint → beep triple grave
  Sharpe rolling < 0.5 → alerte orange
```

---

## 12. RÉSUMÉ PARAMÈTRES CIBLES

```
SIGNAL :
  band_k          = 1.5 σ      (était 1.0)
  band_k_max      = 4.0 σ      (était 5.0)
  lookback        = 150 barres (était 120)
  R_mult          = 5.0        (inchangé)

RÉGIME :
  GARCH alpha1    = 0.12       (inchangé)
  GARCH beta1     = 0.85       (inchangé)
  HMM transition  = sticky 90/80/90
  Trade si régime ∈ {LOW, MED}

SIZING :
  LOW  → 10% du DD restant (Half-Kelly)
  MED  →  6% du DD restant
  PUSH → 15% du DD restant
  SÉCURITÉ → 4% du DD restant
  Plancher : $80 / Plafond : $600

RISK :
  SL = ATR(14) × 1.5 [min 5 pts, max 15 pts]
  TP = fair value Kalman
  Daily loss stop = 80% × $1,000 = $800
  EOD flat : 21h45 UTC
  Consec losses : 2 → stop jour

SESSIONS :
  Début : 15h00 UTC (open + 30 min)
  Fin   : 21h00 UTC (close - 30 min)

VALIDATION :
  Sharpe cible   : 1.2 – 1.5
  Profit Factor  : 1.8 – 2.5
  Recovery Factor: > 2.0
  N min trades   : 25 pour Sharpe significatif
```

---

*Sources : Quant Guild Library 2025 — Lectures 28, 34, 36, 44, 47, 48, 49, 51, 72, 74*
*Roman Paolucci — Columbia University Quant*
