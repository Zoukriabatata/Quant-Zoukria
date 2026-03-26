# 06b — Trading Mean Reversion with Kalman Filters
# "Appliquer le Kalman Filter au trading reel"

> **Video :** [Trading Mean Reversion with Kalman Filters — Roman Paolucci](https://youtu.be/BuPil7nXvMU)
> **Paper :** [Recipes for Simulating Stochastic Processes (SSRN)](https://gaussiancookbook.com/)
> **Code :** [Quant Guild Library #95](https://github.com/romanmichaelpaolucci/Quant-Guild-Library/tree/main/2026%20Video%20Lectures/95.%20Trading%20Mean%20Reversion%20with%20Kalman%20Filters)

---

# ============================================
# APPRENTISSAGE — C'est quoi ? Pourquoi ?
# ============================================

## Le probleme

Tu as appris le Kalman Filter (module 06). Maintenant :
comment l'utiliser pour TRADER du mean reversion ?

Le mean reversion c'est simple en theorie :

```
Le prix est AU-DESSUS de sa "juste valeur" --> VEND
Le prix est EN-DESSOUS de sa "juste valeur" --> ACHETE
Le prix REVIENT a sa juste valeur --> FERME

Facile non ?

SAUF QUE :
  1. C'est quoi la "juste valeur" ? (personne ne sait)
  2. Elle CHANGE dans le temps (pas fixe)
  3. Tu te bases sur un ESTIMATEUR bruite
  4. Si ton estimation est biaisee, tu PERDS lentement
```

## Le piege du mean reversion (lecon #1 du notebook)

Roman Paolucci montre le "Mean Reversion Trap" :

```
Tu estimes la moyenne avec 30 points.
Ta moyenne estimee = 103.5 (biaisee vers le haut)
La VRAIE moyenne = 100.0

Tu trades sur ta mauvaise estimation :
  - Tu shortes a 104 (au-dessus de TON estimation)
  - Le prix revient a 100 (la VRAIE moyenne)
  - Mais ta bande basse est a 102 (tu ne fermes pas)
  - Le prix repart a 100 et tu perds lentement

RESULTAT : equity curve qui DESCEND
C'est le "structural bias bleed"
```

## Pourquoi le Kalman Filter resout ca

Le Kalman Filter estime la "juste valeur" en TEMPS REEL :

```
SANS Kalman (moyenne fixe) :
  Tu calcules une moyenne une fois
  Tu trades dessus pendant 400 barres
  Si ta moyenne est fausse --> tu perds TOUT le temps

AVEC Kalman (moyenne adaptative) :
  A chaque nouveau tick, le filtre MET A JOUR la moyenne
  Si le marche change, le filtre S'ADAPTE
  Tu trades sur une estimation VIVANTE, pas morte
```

## Le processus Ornstein-Uhlenbeck (OU)

Le modele mathematique du mean reversion :

$$dX_t = \theta(\mu - X_t)\,dt + \sigma\,dW_t$$

- $X_t$ = le prix actuel
- $\mu$ = la moyenne long-terme (ou le prix revient)
- $\theta$ = la **vitesse** de retour (plus $\theta$ est grand, plus vite)
- $\sigma$ = la volatilite
- $dW_t$ = bruit aleatoire (mouvement brownien)

**En francais :** le prix est tire vers $\mu$ comme un elastique. Plus il est loin, plus la force de rappel est forte.

Visuellement :

```
Prix
  |
  |    /\      /\
  |   /  \    /  \     /\
  |  /    \  /    \   /  \
  | /      \/      \ /    \
  |         mu       \      <-- le prix oscille autour de mu
  |                    \  /
  |                     \/
  +-------------------------> temps
```

## Le Kalman + OU = combo parfait

```
1. MODELE OU : "le prix DEVRAIT revenir vers mu"
   C'est le F (dynamique) du Kalman Filter

2. OBSERVATION : "le tick actuel dit prix = 101.5"
   C'est le z (mesure)

3. KALMAN : combine les deux
   "Mon modele dit 100.3, le tick dit 101.5"
   K = 0.6
   Estimation = 100.3 + 0.6 * (101.5 - 100.3) = 101.02

4. CETTE estimation (101.02) = ta "juste valeur" actuelle
   Prix > 101.02 + bande --> short
   Prix < 101.02 - bande --> long
```

---

# ============================================
# MODEL — Les maths
# ============================================

## 1. Le processus OU en discret (AR(1))

En pratique on travaille en discret (barres) :

```
X(t+1) = phi * X(t) + (1 - phi) * mu + sigma * epsilon

  phi = e^(-theta * dt) = "combien le prix oublie" (entre 0 et 1)
  mu  = moyenne long-terme
  sigma = volatilite des residus
  epsilon ~ Normal(0, 1)

Si phi = 0.95 : le prix est FORTEMENT persistant (lent a revenir)
Si phi = 0.50 : le prix revient VITE vers mu
```

## 2. Calibration AR(1) depuis les donnees

```
On a N barres de prix : X1, X2, ..., XN

Regression lineaire :
  X(t) = c + phi * X(t-1) + erreur

  phi = coefficient de regression
  c   = constante
  mu  = c / (1 - phi) = moyenne implicite
  sigma = ecart-type des residus

Code Python (du notebook #95) :
  y = closes[1:]
  x_lag = closes[:-1]
  X = [ones, x_lag]
  beta = least_squares(X, y)
  c, phi = beta[0], beta[1]
  mu = mean(closes)
  sigma = std(residus)
```

## 3. Le Kalman Filter pour OU

```
ETAT : x = le niveau moyen estime (fair value)

PREDICTION (etape 1) :
  x_pred = phi * x_prev + (1 - phi) * mu
  P_pred = phi^2 * P_prev + Q

  Q = sigma^2 * (1 - phi^2) = bruit du processus OU

MISE A JOUR (etape 2) :
  K = P_pred / (P_pred + R)
  x_new = x_pred + K * (prix_observe - x_pred)
  P_new = (1 - K) * P_pred
```

## 4. Le "noise lever" (levier de confiance)

```
R = observation noise = "combien les prix sont bruitees"

  R petit  --> K grand --> suit les prix (reactif)
  R grand  --> K petit --> suit le modele OU (lisse)

Le "noise lever" de l'app kts.py :
  0%   = Trust Prices (R = 0.1 * sigma^2)
  50%  = Equilibre    (R = 5 * sigma^2)
  100% = Trust OU     (R = 10^8, K = 0, ignore les prix)
```

## 5. Bandes de trading

Distribution stationnaire du OU :

$$X \sim \mathcal{N}\left(\mu,\; \frac{\sigma^2}{2\theta}\right) \quad \Rightarrow \quad \sigma_{stat} = \frac{\sigma}{\sqrt{2\theta}}$$

Bandes de trading :

$$\text{Upper} = \hat{x}_{kalman} + k \cdot \sigma_{stat}$$
$$\text{Lower} = \hat{x}_{kalman} - k \cdot \sigma_{stat}$$

avec $k$ entre 0.8 et 1.5 selon l'agressivite.

| Condition | Action |
|---|---|
| Prix $>$ Upper | **SHORT** |
| Prix $<$ Lower | **LONG** |
| Prix $\approx \hat{x}_{kalman}$ | **FERMER** |

## 6. Le forecast OU

```
Prediction a h barres dans le futur :

  X_hat(h) = mu + phi^h * (x_current - mu)

  Le prix converge vers mu de maniere exponentielle.

  h = 1 : X_hat = mu + phi * (x - mu)
  h = 5 : X_hat = mu + phi^5 * (x - mu)
  h = 20: X_hat = mu + phi^20 * (x - mu) ≈ mu

  Si phi = 0.95 :
    phi^5  = 0.77  --> encore 77% de l'ecart
    phi^20 = 0.36  --> plus que 36%
    phi^50 = 0.08  --> presque revenu a mu
```

## 7. Le piege : estimation biaisee

```
PROBLEME CRITIQUE (lecon du notebook #95) :

  Si tu estimes mu avec trop peu de donnees (N=30),
  ton estimation est biaisee.

  Rappel du CLT :
    SE = sigma / sqrt(N)
    N = 30, sigma = 4 --> SE = 0.73
    IC 95% = [mu_hat - 1.46, mu_hat + 1.46]

  Si la vraie mu = 100 et ton estimation = 103.5,
  TOUS tes shorts sont trop haut, TOUS tes longs trop haut.
  Tu perds systematiquement.

SOLUTION :
  1. Utiliser le Kalman Filter (mu s'adapte)
  2. Recalibrer regulierement (online_params)
  3. Avoir assez de donnees (N > 60 minimum)
```

---

# ============================================
# LECON — Exercices pratiques
# ============================================

## Exercice 1 : Calibration OU a la main

```
Donnees (5 barres) : 100, 101, 100.5, 99.8, 100.3

Regression AR(1) :
  X_lag = [100, 101, 100.5, 99.8]
  X_cur = [101, 100.5, 99.8, 100.3]

  Approximation simple :
  phi ≈ correlation(X_cur, X_lag)

  Diff : [+1, -0.5, -0.7, +0.5]
  Le prix revient vers une moyenne ~100.3

  mu ≈ mean = (100+101+100.5+99.8+100.3)/5 = 100.32
  sigma ≈ std des residus ≈ 0.7
```

## Exercice 2 : Kalman Filter OU

```
Parametres : phi=0.95, mu=100, sigma=1.0
Initial : x=100, P=1.0
Q = 1.0^2 * (1 - 0.95^2) = 0.0975
R = 2.0

Tick 1 : prix = 102

  Prediction :
    x_pred = 0.95 * 100 + 0.05 * 100 = 100
    P_pred = 0.95^2 * 1.0 + 0.0975 = 0.9025 + 0.0975 = 1.0

  Mise a jour :
    K = 1.0 / (1.0 + 2.0) = 0.333
    x_new = 100 + 0.333 * (102 - 100) = 100.667
    P_new = (1 - 0.333) * 1.0 = 0.667

  --> Fair value estimee = 100.667
  --> Le prix (102) est au-dessus : potentiellement a shorter
```

## Exercice 3 : Decision de trading

```
x_kalman = 100.667
sigma_stat = 1.0 / sqrt(2 * 0.05) = 1.0 / 0.316 = 3.16
bande (k=0.8) = 0.8 * 3.16 = 2.53

Upper = 100.667 + 2.53 = 103.19
Lower = 100.667 - 2.53 = 98.14

Prix actuel = 102

102 < 103.19 --> PAS de short (pas assez haut)
102 > 98.14  --> PAS de long (pas assez bas)

Decision : NO TRADE (attendre)

Si le prix montait a 103.5 :
  103.5 > 103.19 --> SHORT
  Target = x_kalman = 100.667 (profit potentiel = ~2.83)
```

## Exercice 4 : Le piege de l'estimation biaisee

```
Scenario A : mu estimee = 103.5, vraie mu = 100
  Tu shortes quand prix > 104.5
  Tu fermes quand prix = 103.5
  Mais le prix gravite autour de 100, pas 103.5
  --> Tes shorts sont fermes TROP HAUT
  --> Tu perds la difference (3.5 points de biais)

Scenario B : Kalman adaptatif
  Apres 50 barres, le Kalman a ajuste :
  x_kalman = 100.8 (proche de la realite)
  Tes bandes sont maintenant correctes
  --> Tes trades sont BIEN centres
  --> Tu profites du vrai mean reversion

LECON : le Kalman te protege contre le biais d'estimation
```

---

# ============================================
# RESUME — Fiche de revision
# ============================================

```
MEAN REVERSION = le prix revient a une "juste valeur"

PROCESSUS OU :
  dX = theta * (mu - X) * dt + sigma * dW
  Discret : X(t+1) = phi * X(t) + (1-phi) * mu + sigma * epsilon
  Distribution : X ~ Normal(mu, sigma^2 / (2*theta))

CALIBRATION AR(1) :
  Regression X(t) sur X(t-1) --> phi, c
  mu = mean(closes) ou c/(1-phi)
  sigma = std(residus)

KALMAN FILTER + OU :
  Prediction : x_pred = phi * x + (1-phi) * mu
  Mise a jour : K = P/(P+R), x = x_pred + K*(prix - x_pred)
  Q = sigma^2 * (1-phi^2)
  R = confiance dans les prix vs le modele

NOISE LEVER :
  R petit = suit les prix (reactif, bruite)
  R grand = suit le modele OU (lisse, en retard)

BANDES DE TRADING :
  sigma_stat = sigma / sqrt(2*theta)
  Upper = x_kalman + k * sigma_stat
  Lower = x_kalman - k * sigma_stat
  k typique = 0.8 a 1.5

REGLES :
  Prix > Upper --> SHORT
  Prix < Lower --> LONG
  Prix ~ x_kalman --> FERMER

FORECAST OU :
  X_hat(h) = mu + phi^h * (x - mu)
  Le prix converge vers mu exponentiellement

LE PIEGE :
  Estimer mu avec trop peu de donnees = BIAIS
  Biais = perte SYSTEMATIQUE (structural bleed)
  Solution : Kalman adaptatif + recalibration

POUR TON TRADING :
  1. Calibre OU sur tes donnees MNQ (AR(1) regression)
  2. Initialise le Kalman avec phi, mu, sigma
  3. A chaque tick : update le Kalman
  4. x_kalman = ta fair value en temps reel
  5. Si absorption detectee (module 06) + prix hors bande :
     --> signal fort de mean reversion
  6. Combine avec HMM (module 05) : ne trade QUE en low/med vol
  7. Combine avec GARCH (module 04) : ajuste la taille selon la vol

APP KTS.PY :
  - Se connecte a IBKR en live
  - Calibre OU automatiquement
  - Kalman Filter temps reel sur chaque tick
  - Noise lever : slider trust prices vs trust OU
  - Forecast OU (points violets)
  - Trading Long/Short/Close
```
