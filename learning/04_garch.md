# 04 — ARCH & GARCH
# "Filtre de volatilite"

> **Video :** [Master Volatility with ARCH & GARCH Models — Roman Paolucci](https://youtu.be/iImtlBRcczA)

---

# ============================================
# APPRENTISSAGE — C'est quoi ? Pourquoi ?
# ============================================

## Le probleme

La volatilite n'est PAS constante. Tout le monde le sait.
Mais comment la MESURER en temps reel ?

```
Marche calme :                 Marche agite :
  _-_-_-_-_-_-_-              _/\  /\_
                                  \/    \/\  /
                                            \/

  Petits mouvements             Gros mouvements
  sigma = petit                 sigma = grand
```

**Le probleme :** si tu utilises une volatilite FIXE,
tu vas :
1. Sous-estimer le risque en regime HIGH vol
2. Sur-estimer le risque en regime LOW vol
3. Prendre des positions trop grosses au pire moment

## Pourquoi GARCH ?

GARCH capture 3 phenomenes reels du marche :

```
1. VOLATILITY CLUSTERING (regroupement)
   "Les gros mouvements suivent les gros mouvements"

   ___      ___/\/\/\___      ___
      \____/            \____/

   calme   agite        calme   <-- la vol vient en vagues

2. MEAN REVERSION (retour a la moyenne)
   "La vol extreme ne dure pas eternellement"

   La vol spike apres un choc, puis retourne a la normale.

        /\
       /  \
      /    \___
     /         \___
    /              -------- <-- niveau normal

3. LEVERAGE EFFECT (effet de levier)
   "Le marche qui baisse = vol qui monte"

   Les baisses generent PLUS de volatilite que les hausses.
```

## Analogie

```
VOLATILITE FIXE = conduire a 50 km/h tout le temps
  --> trop lent sur autoroute, trop vite dans une ruelle

GARCH = ajuster ta vitesse selon la route
  --> autoroute = vite, ruelle = lent
  --> et si tu viens de freiner d'urgence,
      tu restes prudent pendant un moment (clustering)
```

---

# ============================================
# MODEL — Les maths
# ============================================

## Etape 1 : Le modele de base

Le prix suit :
```
rendement(t) = mu + erreur(t)

  mu = rendement moyen (souvent ~0 en intraday)
  erreur(t) = sigma(t) * z(t)
  z(t) = bruit standard (normal 0,1)
  sigma(t) = volatilite qui CHANGE dans le temps  <-- c'est ca qu'on cherche
```

## Etape 2 : ARCH(1) — Engle 1982

**ARCH = AutoRegressive Conditional Heteroskedasticity**
(Hetero = different, skedasticity = variance)

```
sigma^2(t) = alpha0 + alpha1 * erreur^2(t-1)

  alpha0 = "plancher" de volatilite (toujours > 0)
  alpha1 = "reaction" aux chocs recents

En francais :
  La volatilite d'aujourd'hui depend de
  la TAILLE du mouvement d'hier (au carre).
```

Visuellement :

```
  Hier le prix a bouge de +3% (gros choc)
  erreur^2 = (0.03)^2 = 0.0009

  sigma^2(aujourd'hui) = 0.00001 + 0.25 * 0.0009
                        = 0.00001 + 0.000225
                        = 0.000235
  sigma = sqrt(0.000235) = 1.53%

  Vs un jour calme ou hier = +0.5% :
  sigma^2 = 0.00001 + 0.25 * (0.005)^2
          = 0.00001 + 0.00000625
          = 0.00001625
  sigma = 0.40%

  Apres un gros choc : sigma = 1.53%
  Apres un jour calme : sigma = 0.40%
  --> la vol s'adapte automatiquement !
```

## Etape 3 : GARCH(1,1) — Bollerslev 1986

**GARCH ajoute la MEMOIRE :**

```
sigma^2(t) = alpha0 + alpha1 * erreur^2(t-1) + beta1 * sigma^2(t-1)

                ^           ^                        ^
                |           |                        |
             plancher    reaction au              MEMOIRE
                         choc d'hier          (vol d'hier persiste)
```

**Le truc genial :** le terme `beta1 * sigma^2(t-1)` fait que
la volatilite d'hier INFLUENCE celle d'aujourd'hui.

```
Sans GARCH (ARCH seul) :
  Un choc fait monter la vol
  Mais si demain est calme, la vol retombe direct

  vol:    |
          |  *         <-- spike
          |     *      <-- retombe vite
          | *     * *
          +---------->  temps

Avec GARCH :
  Un choc fait monter la vol
  Et elle RESTE elevee pendant un moment (clustering !)

  vol:    |
          |  * * *     <-- spike + persistance
          |        * *
          | *          * * *
          +---------->  temps
```

## Conditions importantes

```
alpha1 + beta1 < 1   (sinon la vol explose a l'infini)

Typiquement on trouve :
  alpha1 = 0.05 a 0.15  (faible reaction aux chocs)
  beta1  = 0.80 a 0.95  (forte persistance)
  alpha1 + beta1 = 0.90 a 0.99

Plus alpha1+beta1 est proche de 1 = plus la vol persiste longtemps
```

## Volatilite long terme (inconditionnelle)

```
sigma^2_LT = alpha0 / (1 - alpha1 - beta1)

Exemple :
  alpha0 = 0.00001, alpha1 = 0.1, beta1 = 0.85
  sigma^2_LT = 0.00001 / (1 - 0.1 - 0.85) = 0.00001 / 0.05 = 0.0002
  sigma_LT = sqrt(0.0002) = 1.41% par jour
  sigma_LT annualisee = 1.41% * sqrt(252) = 22.4%
```

## Application : Value at Risk (VaR)

```
VaR = "Quelle est ma perte maximale avec 95% de confiance ?"

VaR NAIVE (vol constante) :
  VaR = sigma_fixe * 1.645
  --> utilise la meme vol tout le temps
  --> SOUS-ESTIME le risque en periode de crise

VaR GARCH :
  VaR(t) = sigma_GARCH(t) * 1.645
  --> s'adapte au regime de vol actuel
  --> beaucoup plus fiable

Resultats du notebook (AAPL) :
  VaR naive : 40.65% d'exceedances (devrait etre 5%)  !!!
  VaR GARCH : 9.74% d'exceedances (bien meilleur)
```

---

# ============================================
# LECON — Exercices pratiques
# ============================================

## Exercice 1 : GARCH(1,1) a la main

```
Parametres : alpha0 = 0.00001, alpha1 = 0.10, beta1 = 0.85
Jour 0 : sigma^2 = 0.0002, erreur = +2% = 0.02

Jour 1 :
  sigma^2(1) = 0.00001 + 0.10 * (0.02)^2 + 0.85 * 0.0002
             = 0.00001 + 0.10 * 0.0004 + 0.85 * 0.0002
             = 0.00001 + 0.00004 + 0.00017
             = 0.00022
  sigma(1) = sqrt(0.00022) = 1.48%

Maintenant jour 1 a un mouvement de -4% (gros choc) :

Jour 2 :
  sigma^2(2) = 0.00001 + 0.10 * (0.04)^2 + 0.85 * 0.00022
             = 0.00001 + 0.10 * 0.0016 + 0.85 * 0.00022
             = 0.00001 + 0.00016 + 0.000187
             = 0.000357
  sigma(2) = sqrt(0.000357) = 1.89%

  --> La vol a MONTE de 1.48% a 1.89% apres le choc de -4%.
```

## Exercice 2 : Persistance

```
Apres le choc, supposons des jours calmes (erreur = 0) :

Jour 3 (erreur=0) :
  sigma^2(3) = 0.00001 + 0.10 * 0 + 0.85 * 0.000357
             = 0.00001 + 0 + 0.000303 = 0.000313
  sigma(3) = 1.77%

Jour 4 (erreur=0) :
  sigma^2(4) = 0.00001 + 0 + 0.85 * 0.000313 = 0.000276
  sigma(4) = 1.66%

Jour 5 :
  sigma(5) = 1.57%

Jour 10 :
  sigma(10) = ~1.30%

  --> La vol DESCEND lentement = mean reversion
  --> Il faut ~15-20 jours pour revenir au niveau normal
  --> C'est le CLUSTERING capture par beta1
```

## Exercice 3 : Impact sur le sizing

```
Ton capital = 10 000$
Tu risques max 1% = 100$ par trade
Stop loss = 10 points MNQ = 50$

En regime LOW vol (sigma GARCH = petit) :
  Tu peux prendre 2 contrats (100$/50$ = 2)

En regime HIGH vol (sigma GARCH double) :
  Le stop de 10 points est atteint PLUS souvent
  Tu devrais REDUIRE a 1 contrat

GARCH te dit QUAND ajuster ta taille.
```

---

# ============================================
# RESUME — Fiche de revision
# ============================================

```
ARCH : sigma^2(t) = alpha0 + alpha1 * erreur^2(t-1)
  --> la vol depend du choc d'hier

GARCH : sigma^2(t) = alpha0 + alpha1 * erreur^2(t-1) + beta1 * sigma^2(t-1)
  --> la vol depend du choc d'hier ET de la vol d'hier
  --> capture le CLUSTERING (la vol persiste)

PARAMETRES TYPIQUES :
  alpha1 = 0.05-0.15 (reaction aux chocs)
  beta1  = 0.80-0.95 (persistance)
  alpha1 + beta1 < 1  (stabilite)

CAPTURE 3 PHENOMENES :
  1. Clustering : gros mouvements --> gros mouvements
  2. Mean reversion : la vol revient toujours a la moyenne
  3. Fat tails : plus de valeurs extremes que la normale

VOL LONG TERME :
  sigma^2_LT = alpha0 / (1 - alpha1 - beta1)

VaR GARCH >> VaR naive :
  Naive sous-estime massivement le risque (40% exceedances vs 5% cible)
  GARCH bien meilleur (10% exceedances)

POUR TON TRADING :
  - GARCH te donne la vol ACTUELLE (pas une moyenne fixe)
  - En high vol : REDUIS ta taille de position
  - En low vol : tu peux etre plus agressif
  - Combine avec HMM : GARCH = "quelle vol ?"
                        HMM = "quel regime ?"
```
