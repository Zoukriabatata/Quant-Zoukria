# 06 — Kalman Filter
# "Signal propre"

> **Video :** [Kalman Filter for Quant Finance — Roman Paolucci](https://youtu.be/zVJY_oaVh-0)

---

# ============================================
# APPRENTISSAGE — C'est quoi ? Pourquoi ?
# ============================================

## Le probleme

Ton signal d'absorption est BRUITE.
A chaque tick tu recois des donnees, mais elles contiennent :
- Du vrai signal (quelqu'un absorbe reellement)
- Du bruit (fluctuations aleatoires, faux signaux)

```
CE QUE TU VOIS (signal bruite) :

  *  *      *    *
    *  *  *   *    *  *
  *      *  *        *   *
         ^
         |
  Est-ce un vrai signal ou du bruit ???

CE QUE TU VEUX (signal filtre) :

      ______
     /      \
    /        \________
   /
  Ca c'est le VRAI signal. Clean.
```

## C'est quoi le Kalman Filter ?

C'est un algorithme qui combine 2 sources d'info :

```
SOURCE 1 : TON MODELE (ce que tu PENSES qu'il va se passer)
  "Le VIX a tendance a revenir vers 15"
  "Le prix va probablement rester pres de sa position actuelle"

SOURCE 2 : LES DONNEES (ce que tu OBSERVES)
  "Le dernier tick dit VIX = 22"
  "Le prix vient de bouger de +1%"

KALMAN FILTER :
  "Ok, mon modele dit 15, le marche dit 22.
   Je fais confiance au marche a 60% et a mon modele a 40%.
   Mon estimation = 0.6 * 22 + 0.4 * 15 = 19.2"
```

## L'analogie du GPS

```
Ton GPS utilise un Kalman Filter !

  MODELE : "Tu roulais a 50km/h vers le nord.
            Donc tu devrais etre ICI" (prediction)

  SATELLITE : "Le signal dit que tu es LA" (observation)
              (mais le signal est bruite de quelques metres)

  KALMAN : combine les deux pour donner ta position EXACTE

  Si le signal satellite est bon (peu bruite) :
    --> fait confiance au satellite

  Si le signal satellite est mauvais (tunnel, immeuble) :
    --> fait confiance au modele (continue sur la trajectoire)
```

## Pourquoi c'est genial pour le trading ?

```
SANS Kalman (signal brut) :
  Tick 1 : absorption = 150  --> signal ?
  Tick 2 : absorption = 50   --> faux signal ?
  Tick 3 : absorption = 200  --> signal !
  Tick 4 : absorption = 80   --> bruit ?

  Tu ne sais jamais si c'est reel ou du bruit.
  Tu entres trop tot ou trop tard.

AVEC Kalman (signal filtre) :
  Estimation lissee : 90, 95, 110, 115, 130, 140...

  Tu vois clairement la TENDANCE monter.
  Tu entres au bon moment.
```

---

# ============================================
# MODEL — Les maths
# ============================================

## Le cadre : 2 equations

```
EQUATION 1 — Le modele (comment l'etat EVOLUE) :
  x(t) = F * x(t-1) + B * u + w(t)

  x(t)   = etat vrai (ce qu'on cherche)
  F      = comment l'etat se transforme (dynamique)
  B * u  = force externe (ex: retour a la moyenne)
  w(t)   = bruit du modele ~ Normal(0, Q)

EQUATION 2 — L'observation (ce qu'on MESURE) :
  z(t) = H * x(t) + v(t)

  z(t)   = ce qu'on observe (le tick, le prix)
  H      = comment l'etat se traduit en observation
  v(t)   = bruit de mesure ~ Normal(0, R)
```

## Les 2 etapes du Kalman Filter

A CHAQUE nouveau point de donnee, tu fais :

```
+=============================================+
|  ETAPE 1 : PREDICTION (le modele parle)     |
|                                              |
|  x_pred = F * x_prev + B * u                |
|  P_pred = F^2 * P_prev + Q                  |
|                                              |
|  "Voici ou je PENSE que l'etat est"         |
|  "Et voici mon INCERTITUDE"                 |
+=============================================+
              |
              v
+=============================================+
|  ETAPE 2 : CORRECTION (les donnees parlent) |
|                                              |
|  Innovation = z - x_pred                     |
|  K = P_pred / (P_pred + R)                  |
|  x_new = x_pred + K * Innovation            |
|  P_new = (1 - K) * P_pred                   |
|                                              |
|  "Je corrige ma prediction avec les donnees" |
|  "Mon incertitude a DIMINUE"                |
+=============================================+
```

## Le KALMAN GAIN (K) — la cle de tout

```
K = P_pred / (P_pred + R)

  P_pred = incertitude du MODELE
  R = incertitude de la MESURE (bruit des donnees)
  K = entre 0 et 1

SI P_pred est GRAND (modele incertain) :
  K --> proche de 1
  --> "Je ne fais pas confiance a mon modele"
  --> "Je suis les donnees"

SI R est GRAND (donnees bruitees) :
  K --> proche de 0
  --> "Les donnees sont pourries"
  --> "Je fais confiance a mon modele"
```

Visuellement :

```
K = 0.9 (fait confiance aux donnees) :
  Le filtre SUIT les observations de pres

  Observations :  * *  *  *    *
  Filtre :        *_*__*__*____*    <-- colle aux donnees

K = 0.1 (fait confiance au modele) :
  Le filtre est LISSE, ignore le bruit

  Observations :  * *  *  *    *
  Filtre :        _______________   <-- ligne lisse

K = 0.5 (equilibre) :
  Observations :  * *  *  *    *
  Filtre :        _-_-_--__-__-_    <-- compromis
```

## Application au VIX (exemple du notebook #92)

```
MODELE : le VIX suit un processus OU (mean reversion)
  x(t) = e^(-kappa*dt) * x(t-1) + theta*(1-e^(-kappa*dt))

  En AR(1) : x(t) = phi * x(t-1) + b

  Calibration sur donnees historiques :
    kappa = 25.4 (vitesse de reversion)
    theta = 15.5 (moyenne long terme)
    sigma = 43.1 (volatilite de la vol)

OBSERVATION : le VIX quote = x_vrai + bruit de mesure

KALMAN FILTER :
  1. PREDICTION : "Mon modele dit que le VIX devrait etre a 18.3"
  2. OBSERVATION : "Le marche quote 21.5"
  3. GAIN : K = 0.7
  4. ESTIMATION : 18.3 + 0.7 * (21.5 - 18.3) = 18.3 + 2.24 = 20.54
  5. "Mon meilleur guess du VRAI VIX = 20.54"
```

## Dual Filter : detecter les regime changes

```
PROBLEME :
  Si le regime change (ex: crash), le modele predit mal.
  L'innovation (z - x_pred) devient ENORME.

SOLUTION (Adaptive / Dual Kalman) :
  Si |innovation| > 3 * sqrt(P_pred + R) :
    --> "Alerte ! Quelque chose a change !"
    --> On augmente P (= on ne fait plus confiance au modele)
    --> K monte vers 1 (= on suit les donnees)
    --> Le filtre s'ADAPTE au nouveau regime

SANS adaptation :                AVEC adaptation :
  Regime change ici               Regime change ici
         |                               |
  -------|______                  -------|
         |      \______                  |\_____
         |             \____             |      -----
         |                               |
  Le filtre est LENT              Le filtre REAGIT vite
  a s'adapter                     grace au spike de K
```

---

# ============================================
# LECON — Exercices pratiques
# ============================================

## Exercice 1 : Kalman Filter a la main

```
Setup :
  F = 1 (random walk : x(t) = x(t-1) + bruit)
  Q = 1 (bruit du modele)
  R = 4 (bruit de mesure : les donnees sont 4x plus bruitees)
  x(0) = 10 (estimation initiale)
  P(0) = 1 (incertitude initiale)

TICK 1 : observation z = 12

  Prediction :
    x_pred = 1 * 10 = 10
    P_pred = 1^2 * 1 + 1 = 2

  Correction :
    Innovation = 12 - 10 = 2
    K = 2 / (2 + 4) = 2/6 = 0.333
    x_new = 10 + 0.333 * 2 = 10.67
    P_new = (1 - 0.333) * 2 = 1.333

  --> Le filtre dit 10.67 (pas 12, car R est grand = donnees bruitees)

TICK 2 : observation z = 13

  Prediction :
    x_pred = 10.67
    P_pred = 1.333 + 1 = 2.333

  Correction :
    Innovation = 13 - 10.67 = 2.33
    K = 2.333 / (2.333 + 4) = 0.368
    x_new = 10.67 + 0.368 * 2.33 = 11.53
    P_new = (1 - 0.368) * 2.333 = 1.474

  --> Monte doucement vers les observations
```

## Exercice 2 : Impact de R

```
Meme donnees, mais R = 0.5 (donnees precises) :

TICK 1 : z = 12
  K = 2 / (2 + 0.5) = 0.80
  x_new = 10 + 0.80 * 2 = 11.6   (proche de 12)

Vs R = 4 (donnees bruitees) :
  K = 0.333
  x_new = 10.67                    (reste proche du modele)

Vs R = 100 (donnees tres bruitees) :
  K = 2 / (2 + 100) = 0.02
  x_new = 10 + 0.02 * 2 = 10.04   (ignore presque l'observation)

LECON : R controle "a quel point tu fais confiance aux donnees"
  - Petit R = suit les donnees (reactif mais bruite)
  - Grand R = suit le modele (lisse mais en retard)
  - A toi de trouver le bon R pour ton signal
```

## Exercice 3 : Detecter un regime change

```
Ton filtre tourne tranquillement :
  x_pred = 100, P_pred = 2, R = 4

Soudain : z = 85 (crash !)

  Innovation = 85 - 100 = -15
  Seuil 3-sigma = 3 * sqrt(2 + 4) = 3 * 2.45 = 7.35

  |innovation| = 15 > 7.35 --> ALERTE REGIME CHANGE !

  Action : inflate P
  P_pred = 2 + 150 = 152
  K = 152 / (152 + 4) = 0.974

  x_new = 100 + 0.974 * (-15) = 85.4

  --> Le filtre SAUTE vers la nouvelle realite
      au lieu de trainer pendant 20 ticks
```

---

# ============================================
# RESUME — Fiche de revision
# ============================================

```
KALMAN FILTER : combine MODELE + DONNEES pour estimer l'etat vrai

2 ETAPES (a chaque tick) :
  1. PREDICTION : x_pred = F * x_prev + B*u
                  P_pred = F^2 * P_prev + Q
  2. CORRECTION : K = P_pred / (P_pred + R)
                  x_new = x_pred + K * (z - x_pred)
                  P_new = (1-K) * P_pred

KALMAN GAIN (K) :
  K proche de 1 = suit les donnees (modele incertain)
  K proche de 0 = suit le modele (donnees bruitees)
  K = P / (P + R)

PARAMETRES CLES :
  Q = bruit du modele (processus)
  R = bruit de mesure (observations)
  F = dynamique du modele

  Grand Q = modele instable = K monte = suit les donnees
  Grand R = mesures bruitees = K baisse = suit le modele

DUAL FILTER (regime change) :
  Si |innovation| > 3 * sqrt(P+R) :
  --> inflate P --> K monte --> s'adapte vite

POUR TON TRADING :
  Signal d'absorption brut --> Kalman --> signal propre

  R = "combien de bruit dans mes donnees d'orderflow ?"
  Q = "a quelle vitesse le vrai signal change ?"

  Petit R = reactif (bon pour signaux rapides)
  Grand R = lisse (bon pour tendances lentes)

  COMBINE AVEC :
  GARCH --> ajuste Q dynamiquement (vol change)
  HMM   --> detecte le regime pour ajuster R
```
