# 05c — Hawkes Processes
# "Microstructure : valider un cluster de signaux"

> **Video :** [Hawkes Processes for Quant Finance — Roman Paolucci](https://youtu.be/BotPHbWFRUA)

---

# ============================================
# APPRENTISSAGE — C'est quoi ? Pourquoi ?
# ============================================

## Le probleme

Tu vois un signal de trading.
Mais est-ce REEL ou un FAUX SIGNAL ?

```
SIGNAL SEUL :
  "Le prix s'est eloigne de la fair value"
  --> Peut-etre une vraie opportunite
  --> Peut-etre juste du bruit normal

SIGNAL + HAWKES :
  "Le prix s'eloigne ET l'intensite des mouvements
   est en train de CLUSTERISER dans cette zone"
  --> Beaucoup plus probable que c'est reel
```

## C'est quoi un processus de Hawkes ?

Un processus ou **les evenements PROVOQUENT d'autres evenements**.

```
POISSON SIMPLE (module 03b Monte Carlo) :
  Les evenements arrivent au HASARD
  Chaque evenement est INDEPENDANT
  Pas de clustering

  |  *     *        *    *       *     *   |
  temps -->

HAWKES (ce module) :
  Un evenement AUGMENTE la proba du suivant
  Les evenements arrivent en CLUSTERS
  C'est SELF-EXCITING (auto-excitant)

  |  * **  *    * *** **   *     * ** ***  |
  temps -->
       ^clusters^              ^clusters^
```

## L'analogie du marche

```
CRASH BOURSIER :
  1. Grosse vente --> panique
  2. Panique --> plus de ventes
  3. Plus de ventes --> encore plus de panique
  4. etc.

  Chaque vente AUGMENTE la probabilite de la prochaine vente.
  C'est exactement un Hawkes.

TON TRADING :
  1. Fort mouvement de prix (signal potentiel)
  2. D'autres participants reagissent dans la meme zone
  3. Plus de reactions --> plus de confiance
  4. CLUSTER de mouvements = signal CONFIRME

  Sans Hawkes : tu vois un mouvement isole (maybe noise)
  Avec Hawkes : tu vois un CLUSTER qui s'auto-renforce
```

---

# ============================================
# MODEL — Les maths
# ============================================

## 1. Rappel : Poisson

```
Poisson : N(t) compte les evenements jusqu'a temps t
  Intensite = lambda (constante)
  P(1 event dans dt) = lambda * dt

  Les events sont INDEPENDANTS --> pas de clustering
```

## 2. Hawkes : intensite auto-excitante

$$\lambda(t) = \mu + \sum_{t_i < t} \alpha \cdot e^{-\beta(t - t_i)}$$

- $\mu$ = taux de base (background rate)
- $\alpha$ = excitation par event (combien l'intensite **MONTE**)
- $\beta$ = vitesse de declin (combien vite l'excitation **RETOMBE**)
- $t_i$ = temps de chaque event passe

Visuellement :

```
lambda(t)
  |
  |     *                    <-- event 1 : spike
  |    / \     *             <-- event 2 : spike sur spike
  |   /   \   /\   *        <-- event 3 : encore plus
  |  /     \ /  \ / \
  | /       X    X   \___   <-- decay exponentiel
  |/                      \_____  mu (baseline)
  +-------------------------------> temps
```

## 3. Les 3 parametres

| Parametre | Role | Petit | Grand |
|---|---|---|---|
| $\mu$ (baseline) | Taux normal d'arrivee | Marche calme | Marche actif |
| $\alpha$ (excitation) | Saut d'intensite par event | Events independants | Gros clusters |
| $\beta$ (decay) | Vitesse de retour au baseline | Memoire longue | Memoire courte |

**Condition de stabilite :**

$$\frac{\alpha}{\beta} < 1 \quad \text{(sinon l'intensite explose)}$$

Typiquement $\alpha/\beta$ entre 0.3 et 0.7.

## 4. Simulation discrete

```
A chaque pas de temps dt :

  1. Tire le nombre d'events : dN = Poisson(lambda * dt)
  2. Met a jour l'intensite :
     lambda_new = mu + (lambda_old - mu) * e^(-beta*dt) + alpha * dN

C'est la recursion du notebook #94 :
  lambdas = mu_base + (lambdas - mu_base) * exp(-beta*dt) + alpha * increments
```

## 5. Pourquoi ca change tout pour ton signal

```
SANS HAWKES :
  Tu vois 1 fort mouvement --> signal ?
  Tu vois 3 mouvements en 10 secondes --> signal ?
  Tu ne sais pas si c'est du clustering ou du hasard.

AVEC HAWKES :
  Tu modelises l'intensite des mouvements de prix.
  Si lambda(t) est en train de SPIKE (bien au-dessus de mu) :
  --> les mouvements CLUSTERISENT = auto-excitation
  --> le signal est REEL

  Si lambda(t) est stable autour de mu :
  --> les mouvements arrivent normalement
  --> le "fort mouvement" est probablement du bruit

DECISION :
  lambda(t) >> mu + seuil  --> signal VALIDE --> trade
  lambda(t) ~ mu           --> bruit normal --> no trade
```

## 6. Hawkes Jump Diffusion (du notebook)

```
Le notebook montre que remplacer Poisson par Hawkes
dans un modele de jumps change tout :

  STANDARD (Poisson) :
    Jumps independants, pas de clustering
    Kurtosis moderee

  HAWKES :
    Jumps en clusters, auto-excitation
    Kurtosis BEAUCOUP plus elevee (fat tails)
    MIEUX capture la realite des marches

  Resultat Monte Carlo (1000 paths) :
    Standard : kurtosis ~ 2.5
    Hawkes   : kurtosis ~ 5.5
    --> Hawkes capture 2x mieux les tails extremes
```

---

# ============================================
# LECON — Exercices pratiques
# ============================================

## Exercice 1 : Intensite a la main

```
mu = 0.2, alpha = 0.4, beta = 0.8, dt = 1

Temps 0 : lambda = 0.2 (baseline), 0 event
Temps 1 : lambda = 0.2 + (0.2-0.2)*e^(-0.8) + 0 = 0.2, 1 event arrive
Temps 2 : lambda = 0.2 + (0.2+0.4-0.2)*e^(-0.8) + 0
         = 0.2 + 0.4*0.449 = 0.2 + 0.18 = 0.38

  L'intensite a MONTE de 0.2 a 0.38 a cause de l'event.

Temps 3 (pas d'event) :
  lambda = 0.2 + (0.38-0.2)*e^(-0.8) = 0.2 + 0.18*0.449 = 0.28

  L'intensite RETOMBE vers mu (decay).
```

## Exercice 2 : Detecter un cluster

```
Observations sur 10 ticks (nombre de mouvements de prix) :
  0, 0, 1, 0, 3, 5, 4, 2, 1, 0

Calcule lambda(t) avec mu=0.5, alpha=0.3, beta=0.5 :
  t0: lambda=0.5
  t1: lambda=0.5 (0 event)
  t2: lambda=0.5 + 0.3*1 = 0.80 (1 event!)
  t3: lambda=0.5 + 0.30*e^(-0.5) = 0.68 (decay, 0 event)
  t4: lambda~0.61 + 0.3*3 = 1.51 (3 events! SPIKE)
  t5: lambda~1.11 + 0.3*5 = 2.61 (5 events! CLUSTER)

  A t5, lambda = 2.61 >> mu = 0.5
  C'est 5x le baseline --> CLUSTER CONFIRME
  --> CLUSTER VALIDE = signal reel
```

## Exercice 3 : Seuil de validation

```
Regle simple :
  Si lambda(t) > mu + 2*sigma_lambda --> cluster detecte

Avec mu=0.5, sigma_lambda estimee = 0.3 :
  Seuil = 0.5 + 2*0.3 = 1.1

  lambda = 2.61 > 1.1 --> CLUSTER VALIDE
  lambda = 0.68 < 1.1 --> pas de cluster (bruit)
```

---

# ============================================
# RESUME — Fiche de revision
# ============================================

```
HAWKES = processus SELF-EXCITING (auto-excitant)
  "Les events provoquent d'autres events"

INTENSITE :
  lambda(t) = mu + SUM alpha * e^(-beta*(t-ti))

  mu    = baseline (taux normal)
  alpha = excitation par event
  beta  = vitesse de decay
  alpha/beta < 1 pour la stabilite

SIMULATION :
  lambda_new = mu + (lambda_old - mu)*e^(-beta*dt) + alpha*dN

CLUSTERS :
  lambda >> mu = cluster d'events = auto-excitation
  lambda ~ mu  = arrivals normales = pas de cluster

POUR TON TRADING :
  Modelise l'intensite des mouvements de prix
  lambda(t) spike --> cluster de mouvements = signal REEL
  lambda(t) stable --> bruit normal = FAUX signal

  Signal + Hawkes cluster --> TRADE
  Signal SANS Hawkes      --> NO TRADE

PIPELINE :
  Regime OK (Markov Switching)
  + Vol OK (GARCH)
  + Cluster valide (Hawkes)
  + Direction propre (Kalman)
  = ENTRY
```

**LETTRES ET SYMBOLES :**

| Lettre | Nom | Signification |
|--------|-----|---------------|
| $\lambda(t)$ | Lambda t | Intensite instantanee = taux d'arrivee des evenements a l'instant t |
| $\mu$ | Mu | Baseline = taux d'arrivee normal quand aucun event recent |
| $\alpha$ | Alpha | Force d'excitation = combien chaque event fait monter lambda |
| $\beta$ | Beta | Vitesse de decay = a quelle vitesse l'excitation retombe |
| $e^{-\beta(t-t_i)}$ | Exponentielle | Decroissance : l'impact de l'event $i$ s'estompe avec le temps |
| $t_i$ | Temps ti | Moment ou l'event $i$ s'est produit |
| $\alpha/\beta$ | Ratio stabilite | Doit etre $< 1$ sinon le processus explose (trop auto-excitant) |
| $dN$ | dN | 1 si un nouvel event arrive maintenant, 0 sinon |
| $\lambda \gg \mu$ | Lambda >> Mu | Cluster detecte : beaucoup plus d'events que la normale |
