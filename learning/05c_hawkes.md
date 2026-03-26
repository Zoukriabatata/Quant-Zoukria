# 05c — Hawkes Processes
# "Microstructure : valider l'absorption"

> **Video :** [Hawkes Processes for Quant Finance — Roman Paolucci](https://youtu.be/BotPHbWFRUA)

---

# ============================================
# APPRENTISSAGE — C'est quoi ? Pourquoi ?
# ============================================

## Le probleme

Tu vois une absorption sur l'orderflow.
Mais est-ce REELLE ou un FAUX SIGNAL ?

```
ABSORPTION SEULE :
  "Il y a du volume au bid"
  --> Peut-etre que quelqu'un absorbe
  --> Peut-etre juste du bruit normal

ABSORPTION + HAWKES :
  "Il y a du volume au bid ET l'intensite des ordres
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

TON ORDERFLOW :
  1. Gros ordre au bid (absorption)
  2. D'autres voient le support --> ajoutent des ordres
  3. Plus d'ordres --> plus de confiance
  4. CLUSTER d'ordres = absorption CONFIRMEE

  Sans Hawkes : tu vois un gros ordre (maybe noise)
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

```
lambda(t) = mu + SUM sur tous les events passes ti < t de : alpha * e^(-beta*(t-ti))

  mu    = taux de base (background rate)
  alpha = excitation par event (combien l'intensite MONTE)
  beta  = vitesse de declin (combien vite l'excitation RETOMBE)
  ti    = temps de chaque event passe

En francais :
  "L'intensite = un taux de base
   + une contribution de CHAQUE event passe
   qui decroit exponentiellement avec le temps"
```

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

```
mu (baseline) :
  Taux d'arrivee "normal" des events
  Sans excitation, lambda(t) = mu
  Petit mu = marche calme
  Grand mu = marche actif

alpha (excitation) :
  Combien l'intensite SAUTE apres un event
  Grand alpha = forte auto-excitation = gros clusters
  Petit alpha = faible excitation = events presque independants

beta (decay) :
  Vitesse de retour au baseline apres un spike
  Grand beta = retour rapide (memoire courte)
  Petit beta = retour lent (memoire longue)

CONDITION DE STABILITE : alpha / beta < 1
  Si alpha/beta >= 1 : l'intensite EXPLOSE (instable)
  Typiquement : alpha/beta = 0.3 a 0.7
```

## 4. Simulation discrete

```
A chaque pas de temps dt :

  1. Tire le nombre d'events : dN = Poisson(lambda * dt)
  2. Met a jour l'intensite :
     lambda_new = mu + (lambda_old - mu) * e^(-beta*dt) + alpha * dN

C'est la recursion du notebook #94 :
  lambdas = mu_base + (lambdas - mu_base) * exp(-beta*dt) + alpha * increments
```

## 5. Pourquoi ca change tout pour l'absorption

```
SANS HAWKES :
  Tu vois 1 gros ordre au bid --> signal ?
  Tu vois 3 ordres en 10 secondes --> signal ?
  Tu ne sais pas si c'est du clustering ou du hasard.

AVEC HAWKES :
  Tu modelises l'intensite des ordres d'achat.
  Si lambda(t) est en train de SPIKE (bien au-dessus de mu) :
  --> les ordres CLUSTERISENT = auto-excitation
  --> l'absorption est REELLE

  Si lambda(t) est stable autour de mu :
  --> les ordres arrivent normalement
  --> le "gros ordre" est probablement du bruit

DECISION :
  lambda(t) >> mu + seuil  --> absorption VALIDEE --> trade
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
Observations sur 10 ticks (nombre d'ordres d'achat) :
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
  --> Si c'est des ordres d'achat = absorption VALIDEE
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

POUR TON ABSORPTION :
  Modelise l'intensite des ordres d'achat/vente
  lambda(t) spike --> cluster d'ordres = absorption REELLE
  lambda(t) stable --> bruit normal = FAUX signal

  absorption + Hawkes cluster --> TRADE
  absorption SANS Hawkes      --> NO TRADE

PIPELINE :
  Regime OK (Markov Switching)
  + Vol OK (GARCH)
  + Cluster valide (Hawkes)
  + Direction propre (Kalman)
  + Absorption visible
  = ENTRY
```
