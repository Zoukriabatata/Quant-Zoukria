# 05b — Markov Regime Switching
# "QUAND trader (version avancee)"

> **Video Part 1 :** [Markov Chain Regime Switching Bot (IBKR) — Roman Paolucci](https://youtu.be/mais1dsB_1g)
> **Video Part 2 :** [Markov Chain Regime Switching Bot Part 2 — Roman Paolucci](https://youtu.be/CkXljL6eI5A)

---

# ============================================
# APPRENTISSAGE — C'est quoi ? Pourquoi ?
# ============================================

## Pourquoi upgrade le HMM ?

Le HMM du module 05 est une bonne base theorique.
Le Regime Switching est la VERSION PRATIQUE :

```
HMM (module 05) :
  - Theorie : Forward/Backward, Baum-Welch
  - Calibration offline sur donnees historiques
  - Pas de temps reel

REGIME SWITCHING (ce module) :
  - Filtrage bayesien EN TEMPS REEL
  - Calibration sur barres IBKR live
  - Coloration du chart par regime
  - Decision de trading immediate
```

## Comment ca marche

```
3 ETATS :
  LOW vol  = marche calme   (vert)
  MED vol  = transition     (orange)
  HIGH vol = marche agite   (rouge)

CLASSIFICATION :
  1. Calcule la volatilite de chaque barre : vol = (high - low) / close
  2. Trie les volatilites historiques en 3 buckets (33/67 percentiles)
  3. Chaque bucket = un regime avec sa propre distribution

FILTRAGE BAYESIEN (a chaque nouvelle barre) :
  1. PREDICTION : P(regime_t) = Transition^T @ P(regime_t-1)
  2. LIKELIHOOD : P(vol | regime) = gaussienne
  3. POSTERIOR : P(regime | vol) = prediction * likelihood
  4. NORMALISE : divise par la somme
  5. REGIME = argmax(posterior)
```

## L'app IBKR (final_product.py)

```
L'app se connecte a IBKR et fait tout en live :

  1. CONNEXION : host:port vers TWS/Gateway
  2. CALIBRATION : demande 300 secondes de barres historiques
     --> estime les 3 distributions + matrice de transition
  3. STREAMING : chaque 5 secondes, nouvelle barre
     --> filtre bayesien --> regime actuel
  4. CHART : OHLC candles avec FOND COLORE par regime
     vert = low vol, orange = med vol, rouge = high vol
  5. RECALIBRATION : bouton pour recalibrer a tout moment
```

---

# ============================================
# MODEL — Les maths
# ============================================

## 1. Volatilite par barre

```
vol(barre) = (high - low) / close

  C'est le range normalise.
  Simple, robuste, pas besoin de returns.
```

## 2. Classification en 3 regimes

```
Historique : 60 barres de vol
  Trie : vol_sorted = sort(vols)
  P33 = percentile 33%
  P67 = percentile 67%

  vol < P33  --> LOW
  P33 < vol < P67 --> MED
  vol > P67  --> HIGH

Pour chaque regime :
  mu_regime = mean(vols dans ce regime)
  sigma_regime = std(vols dans ce regime)
```

## 3. Matrice de transition

```
Compte les transitions observees :
  LOW->LOW : 45, LOW->MED : 3, LOW->HIGH : 0
  MED->LOW : 4, MED->MED : 20, MED->HIGH : 2
  HIGH->LOW : 0, HIGH->MED : 3, HIGH->HIGH : 15

Normalise chaque ligne (+ lissage Laplace +0.1) :
  T = [[0.93, 0.06, 0.01],
       [0.15, 0.77, 0.08],
       [0.01, 0.17, 0.82]]

Les diagonales sont GRANDES = les regimes persistent.
```

## 4. Filtrage bayesien en temps reel

```
A chaque nouvelle barre :

  1. PREDICTION (prior) :
     prior = T^T @ posterior_precedent

  2. LIKELIHOOD :
     Pour chaque regime r :
       L(r) = gaussienne(vol_actuel | mu_r, sigma_r)

  3. POSTERIOR :
     posterior(r) = prior(r) * L(r)
     posterior = posterior / sum(posterior)  <-- normalisation

  4. REGIME :
     regime_actuel = argmax(posterior)

Exemple :
  posterior = [0.82, 0.15, 0.03]
  argmax = 0 --> LOW vol
  --> fond du chart = VERT
  --> tu peux trader normalement
```

## 5. Integration avec ton pipeline

```
Le regime alimente TOUT le reste :

  LOW vol  --> Kalman : R grand (lisse)
            --> GARCH : vol basse = taille normale
            --> TRADE si signal d'absorption

  MED vol  --> Kalman : R moyen
            --> GARCH : taille reduite
            --> TRADE demi-taille si signal fort

  HIGH vol --> Kalman : R petit (reactif)
            --> GARCH : vol haute = tres petite taille
            --> PAS DE TRADE (sauf exception)
```

---

# ============================================
# LECON — Exercices pratiques
# ============================================

## Exercice 1 : Classification

```
Volatilites de 10 barres : 0.2, 0.3, 0.8, 0.1, 0.5, 0.9, 0.2, 0.4, 0.7, 0.3

Trie : 0.1, 0.2, 0.2, 0.3, 0.3, 0.4, 0.5, 0.7, 0.8, 0.9
P33 = 0.23 (entre le 3e et 4e)
P67 = 0.6 (entre le 7e et 8e)

Classification :
  0.2 = LOW, 0.3 = MED, 0.8 = HIGH, 0.1 = LOW
  0.5 = MED, 0.9 = HIGH, 0.2 = LOW, 0.4 = MED
  0.7 = HIGH, 0.3 = MED

Regimes : L, M, H, L, M, H, L, M, H, M
```

## Exercice 2 : Filtrage bayesien

```
Prior apres prediction = [0.6, 0.3, 0.1]
Nouvelle barre : vol = 0.15 (tres basse)

Likelihood :
  L(LOW | vol=0.15)  = gauss(0.15, mu=0.18, sigma=0.05) = 0.88
  L(MED | vol=0.15)  = gauss(0.15, mu=0.45, sigma=0.10) = 0.003
  L(HIGH | vol=0.15) = gauss(0.15, mu=0.80, sigma=0.15) = ~0

Posterior (non normalise) :
  [0.6*0.88, 0.3*0.003, 0.1*0] = [0.528, 0.0009, 0]

Normalise : [0.998, 0.002, 0.000]

Regime = LOW (99.8% de confiance)
--> fond VERT, tu peux trader
```

---

# ============================================
# RESUME — Fiche de revision
# ============================================

```
REGIME SWITCHING = HMM en TEMPS REEL pour le trading

3 ETATS : LOW vol (vert), MED vol (orange), HIGH vol (rouge)

CLASSIFICATION :
  vol = (high - low) / close
  3 buckets par percentiles (33/67)
  Chaque bucket = gaussienne(mu, sigma)

MATRICE DE TRANSITION :
  Compte les changements observes
  Normalise + lissage Laplace
  Diagonales grandes = regimes persistent

FILTRAGE BAYESIEN (chaque barre) :
  1. prior = T^T @ posterior
  2. likelihood = gauss(vol | regime)
  3. posterior = prior * likelihood (normalise)
  4. regime = argmax(posterior)

APP IBKR :
  Connexion live, barres 5s, chart OHLC colore par regime
  Recalibration a la demande

POUR TON TRADING :
  LOW  = trade normalement (absorption fiable)
  MED  = demi-taille (prudence)
  HIGH = no trade (survie d'abord)
```
