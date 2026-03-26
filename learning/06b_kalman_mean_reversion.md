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

1. **MODELE OU :** "le prix DEVRAIT revenir vers $\mu$" -- c'est le $F$ (dynamique) du Kalman Filter
2. **OBSERVATION :** "le tick actuel dit prix $= 101.5$" -- c'est le $z$ (mesure)
3. **KALMAN :** combine les deux. "Mon modele dit $100.3$, le tick dit $101.5$"

$$K = 0.6 \qquad \text{Estimation} = 100.3 + 0.6 \times (101.5 - 100.3) = 101.02$$

4. Cette estimation ($101.02$) = ta "juste valeur" actuelle. Prix $> 101.02 + \text{bande}$ $\to$ short ; Prix $< 101.02 - \text{bande}$ $\to$ long

---

# ============================================
# MODEL — Les maths
# ============================================

## 1. Le processus OU en discret (AR(1))

En pratique on travaille en discret (barres) :

$$X_{t+1} = \phi \cdot X_t + (1 - \phi) \cdot \mu + \sigma \cdot \varepsilon_t \quad ,\quad \varepsilon_t \sim \mathcal{N}(0,1)$$

- $\phi = e^{-\theta \Delta t}$ = "combien le prix oublie" (entre 0 et 1)
- $\mu$ = moyenne long-terme
- $\sigma$ = volatilite des residus

| $\phi$ | Comportement |
|---|---|
| $0.95$ | FORTEMENT persistant (lent a revenir) |
| $0.50$ | Revient VITE vers $\mu$ |

## 2. Calibration AR(1) depuis les donnees

On a $N$ barres de prix : $X_1, X_2, \ldots, X_N$. Regression lineaire :

$$X_t = c + \phi \cdot X_{t-1} + \varepsilon_t$$

- $\phi$ = coefficient de regression
- $c$ = constante
- $\mu = \frac{c}{1 - \phi}$ = moyenne implicite
- $\sigma = \text{std}(\text{residus})$

Code Python (du notebook #95) :
```
y = closes[1:]
x_lag = closes[:-1]
X = [ones, x_lag]
beta = least_squares(X, y)
c, phi = beta[0], beta[1]
mu = mean(closes)
sigma = std(residus)
```

## 3. Le Kalman Filter pour OU

ETAT : $x$ = le niveau moyen estime (fair value)

**PREDICTION** (etape 1) :

$$\hat{x}_{pred} = \phi \cdot x_{prev} + (1 - \phi) \cdot \mu$$
$$P_{pred} = \phi^2 \cdot P_{prev} + Q \quad \text{ou} \quad Q = \sigma^2(1 - \phi^2)$$

**MISE A JOUR** (etape 2) :

$$K = \frac{P_{pred}}{P_{pred} + R} \qquad \hat{x}_{new} = \hat{x}_{pred} + K \cdot (z_{obs} - \hat{x}_{pred}) \qquad P_{new} = (1 - K) \cdot P_{pred}$$

## 4. Le "noise lever" (levier de confiance)

$R$ = observation noise = "combien les prix sont bruitees"

| $R$ | $K$ | Comportement |
|---|---|---|
| Petit | Grand | Suit les prix (reactif) |
| Grand | Petit | Suit le modele OU (lisse) |

Le "noise lever" de l'app kts.py :

| Slider | $R$ | Effet |
|---|---|---|
| $0\%$ (Trust Prices) | $0.1 \cdot \sigma^2$ | $K$ grand |
| $50\%$ (Equilibre) | $5 \cdot \sigma^2$ | Balance |
| $100\%$ (Trust OU) | $10^8$ | $K \approx 0$, ignore les prix |

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

Prediction a $h$ barres dans le futur :

$$\boxed{\hat{X}(h) = \mu + \phi^h \cdot (x_{current} - \mu)}$$

Le prix converge vers $\mu$ de maniere exponentielle.

| $h$ | $\hat{X}(h)$ | Si $\phi = 0.95$ |
|---|---|---|
| $1$ | $\mu + \phi(x - \mu)$ | $95\%$ de l'ecart |
| $5$ | $\mu + \phi^5(x - \mu)$ | $77\%$ de l'ecart |
| $20$ | $\mu + \phi^{20}(x - \mu)$ | $36\%$ de l'ecart |
| $50$ | $\mu + \phi^{50}(x - \mu)$ | $8\%$ -- presque revenu a $\mu$ |

## 7. Le piege : estimation biaisee

**PROBLEME CRITIQUE** (lecon du notebook #95) : si tu estimes $\mu$ avec trop peu de donnees ($N=30$), ton estimation est biaisee.

Rappel du CLT :

$$SE = \frac{\sigma}{\sqrt{N}} \quad \Rightarrow \quad N = 30,\; \sigma = 4 \quad \Rightarrow \quad SE = 0.73$$
$$IC_{95\%} = [\hat{\mu} - 1.46,\; \hat{\mu} + 1.46]$$

Si la vraie $\mu = 100$ et ton estimation $= 103.5$, TOUS tes shorts sont trop haut, TOUS tes longs trop haut. Tu perds systematiquement.

**SOLUTION :**
1. Utiliser le Kalman Filter ($\mu$ s'adapte)
2. Recalibrer regulierement (online_params)
3. Avoir assez de donnees ($N > 60$ minimum)

---

# ============================================
# LECON — Exercices pratiques
# ============================================

## Exercice 1 : Calibration OU a la main

Donnees (5 barres) : $100, 101, 100.5, 99.8, 100.3$

Regression AR(1) : $X_{lag} = [100, 101, 100.5, 99.8]$, $X_{cur} = [101, 100.5, 99.8, 100.3]$

Approximation simple : $\phi \approx \text{corr}(X_{cur}, X_{lag})$

Diff : $[+1, -0.5, -0.7, +0.5]$ -- le prix revient vers une moyenne $\sim 100.3$

$$\mu \approx \bar{X} = \frac{100+101+100.5+99.8+100.3}{5} = 100.32 \qquad \sigma \approx \text{std}(\text{residus}) \approx 0.7$$

## Exercice 2 : Kalman Filter OU

Parametres : $\phi=0.95$, $\mu=100$, $\sigma=1.0$, $x_0=100$, $P_0=1.0$

$$Q = \sigma^2(1 - \phi^2) = 1.0^2 \times (1 - 0.95^2) = 0.0975 \qquad R = 2.0$$

**Tick 1 :** prix $= 102$

Prediction : $\hat{x}_{pred} = 0.95 \times 100 + 0.05 \times 100 = 100$, $P_{pred} = 0.95^2 \times 1.0 + 0.0975 = 1.0$

Mise a jour :

$$K = \frac{1.0}{1.0 + 2.0} = 0.333 \qquad \hat{x}_{new} = 100 + 0.333 \times (102 - 100) = 100.667 \qquad P_{new} = 0.667$$

Fair value estimee $= 100.667$. Le prix ($102$) est au-dessus : potentiellement a shorter.

## Exercice 3 : Decision de trading

$$\hat{x}_{kalman} = 100.667 \qquad \sigma_{stat} = \frac{1.0}{\sqrt{2 \times 0.05}} = \frac{1.0}{0.316} = 3.16$$
$$\text{Bande } (k=0.8) = 0.8 \times 3.16 = 2.53$$
$$\text{Upper} = 100.667 + 2.53 = 103.19 \qquad \text{Lower} = 100.667 - 2.53 = 98.14$$

Prix actuel $= 102$ :

| Test | Resultat | Action |
|---|---|---|
| $102 < 103.19$ | Pas assez haut | PAS de short |
| $102 > 98.14$ | Pas assez bas | PAS de long |

**Decision : NO TRADE** (attendre)

Si le prix montait a $103.5$ : $103.5 > 103.19$ $\Rightarrow$ **SHORT**, target $= \hat{x}_{kalman} = 100.667$ (profit potentiel $\approx 2.83$)

## Exercice 4 : Le piege de l'estimation biaisee

**Scenario A :** $\hat{\mu} = 103.5$, vraie $\mu = 100$
- Tu shortes quand prix $> 104.5$
- Tu fermes quand prix $= 103.5$
- Mais le prix gravite autour de $100$, pas $103.5$
- Tes shorts sont fermes TROP HAUT, tu perds la difference ($3.5$ points de biais)

**Scenario B :** Kalman adaptatif
- Apres 50 barres, le Kalman a ajuste : $\hat{x}_{kalman} = 100.8$ (proche de la realite)
- Tes bandes sont maintenant correctes
- Tes trades sont BIEN centres, tu profites du vrai mean reversion

**LECON :** le Kalman te protege contre le biais d'estimation.

---

# ============================================
# RESUME — Fiche de revision
# ============================================

**MEAN REVERSION** = le prix revient a une "juste valeur"

**PROCESSUS OU :**

$$dX_t = \theta(\mu - X_t)\,dt + \sigma\,dW_t$$

Discret : $X_{t+1} = \phi \cdot X_t + (1-\phi) \cdot \mu + \sigma \cdot \varepsilon$

Distribution : $X \sim \mathcal{N}\!\left(\mu,\; \frac{\sigma^2}{2\theta}\right)$

**CALIBRATION AR(1) :** regression $X_t$ sur $X_{t-1}$ $\to$ $\phi$, $c$, puis $\mu = \frac{c}{1-\phi}$, $\sigma = \text{std}(\text{residus})$

**KALMAN FILTER + OU :**

$$\hat{x}_{pred} = \phi \cdot x + (1-\phi) \cdot \mu \qquad K = \frac{P}{P+R} \qquad \hat{x}_{new} = \hat{x}_{pred} + K \cdot (z - \hat{x}_{pred})$$
$$Q = \sigma^2(1-\phi^2) \qquad R = \text{confiance prix vs modele}$$

**NOISE LEVER :** $R$ petit = suit les prix (reactif, bruite) ; $R$ grand = suit le modele OU (lisse, en retard)

**BANDES DE TRADING :**

$$\sigma_{stat} = \frac{\sigma}{\sqrt{2\theta}} \qquad \text{Upper} = \hat{x}_{kalman} + k \cdot \sigma_{stat} \qquad \text{Lower} = \hat{x}_{kalman} - k \cdot \sigma_{stat}$$

$k$ typique $= 0.8$ a $1.5$

| Condition | Action |
|---|---|
| Prix $>$ Upper | **SHORT** |
| Prix $<$ Lower | **LONG** |
| Prix $\approx \hat{x}_{kalman}$ | **FERMER** |

**FORECAST OU :**

$$\boxed{\hat{X}(h) = \mu + \phi^h \cdot (x - \mu)}$$

Le prix converge vers $\mu$ exponentiellement.

**LE PIEGE :** estimer $\mu$ avec trop peu de donnees $=$ BIAIS $=$ perte SYSTEMATIQUE (structural bleed). Solution : Kalman adaptatif + recalibration.

**POUR TON TRADING :**
1. Calibre OU sur tes donnees MNQ (AR(1) regression)
2. Initialise le Kalman avec $\phi$, $\mu$, $\sigma$
3. A chaque tick : update le Kalman
4. $\hat{x}_{kalman}$ = ta fair value en temps reel
5. Si absorption detectee (module 06) + prix hors bande $\to$ signal fort de mean reversion
6. Combine avec HMM (module 05) : ne trade QUE en low/med vol
7. Combine avec GARCH (module 04) : ajuste la taille selon la vol

**APP KTS.PY :** IBKR live, calibre OU auto, Kalman temps reel, noise lever slider, forecast OU, trading Long/Short/Close
