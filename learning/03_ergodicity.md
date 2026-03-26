# 03 — Ergodicity
# "Pourquoi la plupart des traders perdent"

> **Video :** [Why Most Traders Lose — Ergodicity for Quant Trading — Roman Paolucci](https://youtu.be/dryV1qJYUw8)

---

# ============================================
# APPRENTISSAGE — C'est quoi ? Pourquoi ?
# ============================================

## Le probleme qui tue les traders

Un jeu te propose :
- 50% de chance de GAGNER 50%
- 50% de chance de PERDRE 40%

La valeur attendue (expected value) :

```
EV = 0.5 * (+50%) + 0.5 * (-40%) = +5%

EV positif ! Super deal non ?
```

**FAUX.** Ce jeu va te RUINER.

## L'illusion de la moyenne d'ensemble

Le probleme : la valeur attendue calcule la moyenne
sur TOUS les univers paralleles. Pas sur TON parcours.

```
MOYENNE D'ENSEMBLE (ce que dit l'EV) :

  Univers 1 : +50% +50% +50% = RICHE
  Univers 2 : +50% -40% +50% = ok
  Univers 3 : -40% +50% -40% = pauvre
  Univers 4 : -40% -40% +50% = tres pauvre
  Univers 5 : -40% -40% -40% = ruine

  Moyenne des 5 = positive (grace a l'univers 1)

  MAIS : la PLUPART des univers perdent de l'argent !
```

## Le vrai calcul : la MOYENNE TEMPORELLE

Toi tu vis dans UN SEUL univers. Tu joues encore et encore.
Ce qui compte c'est la croissance geometrique :

```
MOYENNE TEMPORELLE (ce que TU vis) :

  Tu commences avec 1000$
  Tour 1 : +50% --> 1500$
  Tour 2 : -40% --> 900$    <-- tu as PERDU 100$ !
  Tour 3 : +50% --> 1350$
  Tour 4 : -40% --> 810$    <-- encore moins !

  Le TAUX DE CROISSANCE GEOMETRIQUE :
  g = sqrt(1.5 * 0.6) - 1 = sqrt(0.9) - 1 = -0.051 = -5.1%

  Tu PERDS 5.1% a chaque cycle, malgre un EV de +5% !
```

## Pourquoi ? La difference fondamentale

```
ERGODICITE = quand la moyenne d'ensemble = la moyenne temporelle

  Systeme ERGODIQUE :     Systeme NON-ERGODIQUE :
  (la moyenne marche)     (la moyenne ment)

  Exemple : lancer        Exemple : ton capital
  un de 1000 fois         de trading

  La moyenne des          La moyenne des
  1000 lancers            "univers paralleles"
  = la moyenne            =/= TON parcours
  theorique (3.5)         reel

  Pourquoi ?              Pourquoi ?
  Chaque lancer est       Les gains/pertes sont
  INDEPENDANT             MULTIPLICATIFS
                          (tu joues avec ce qui reste)
```

## L'intuition visuelle

```
ADDITIF (ergodique) :
  +10, -10, +10, -10 ...

  Solde : 1000, 1010, 1000, 1010, 1000
  --> oscille autour de 1000, stable

MULTIPLICATIF (NON ergodique) :
  +50%, -40%, +50%, -40% ...

  Solde : 1000, 1500, 900, 1350, 810, 1215, 729 ...
  --> DESCEND malgre l'EV positif !

  1000$ ----___    ___
               \__/   \___     ___
                          \___/   \___   --> 0
```

**Le trading est MULTIPLICATIF = NON-ERGODIQUE**

---

# ============================================
# MODEL — Les maths
# ============================================

## Croissance geometrique vs arithmetique

**Moyenne arithmetique** (ce qu'on calcule navement) :

$$E[r] = \frac{r_1 + r_2 + \cdots + r_n}{n}$$

**Moyenne geometrique** (ce que tu VIS reellement) :

$$g = \left(\prod_{i=1}^n (1+r_i)\right)^{1/n} - 1$$

**LA formule la plus importante de ce cours :**

$$\boxed{g = E[r] - \frac{\sigma^2}{2}}$$

| | $E[r]$ | $\sigma$ | $g$ (croissance reelle) |
|---|---|---|---|
| Bon | 5% | 10% | $5\% - 0.5\% = +4.5\%$ |
| Moyen | 5% | 30% | $5\% - 4.5\% = +0.5\%$ |
| **Mort** | 5% | 40% | $5\% - 8\% = -3\%$ |

Avec $\sigma = 40\%$, ton edge de 5% est **negatif** en realite !

## Le Kelly Criterion

Kelly repond a : "Quelle taille de position maximise $g$ ?"

$$f^* = \frac{p \cdot b - q}{b}$$

- $f^*$ = fraction optimale de ton capital a risquer
- $p$ = probabilite de gagner
- $q = 1 - p$ = probabilite de perdre
- $b$ = ratio gain/perte

**Exemple :** $p = 0.6$, gain $= +2R$, perte $= -1R$, donc $b = 2$

$$f^* = \frac{0.6 \times 2 - 0.4}{2} = \frac{0.8}{2} = 0.40 = 40\%$$

En pratique on utilise **demi-Kelly** ($20\%$) car :
1. On connait mal les vrais $p$ et $b$
2. La variance est douloureuse psychologiquement

## Visualisation de l'impact du sizing

```
SOUS-KELLY (safe) :
  Croissance lente mais SURE
  ----____-----_____------______------  --> monte doucement

KELLY OPTIMAL :
  Croissance maximale mais VIOLENTE
  --__----____--______---___________--- --> monte plus vite
  (drawdowns importants mais tu survis)

SUR-KELLY (danger) :
  Perte CERTAINE a long terme
  ----____    ____
            \/    \___        --> 0 (ruine)
                      \____

IMPORTANT : la RUINE est irreversible.
  0 * n'importe quoi = 0
  Si tu perds tout, aucun edge ne te sauve.
```

---

# ============================================
# LECON — Exercices pratiques
# ============================================

## Exercice 1 : Le jeu du casino

```
Jeu : tu mises 10% de ton capital a chaque tour
  - 60% de chance de doubler ta mise (+10%)
  - 40% de chance de perdre ta mise (-10%)

EV par tour = 0.6*(+10%) + 0.4*(-10%) = +2%

Croissance geometrique :
g = E[r] - sigma^2/2

sigma^2 de ce jeu = 0.6*(0.1)^2 + 0.4*(-0.1)^2 - (0.02)^2
                  = 0.6*0.01 + 0.4*0.01 - 0.0004
                  = 0.01 - 0.0004 = 0.0096

g = 0.02 - 0.0096/2 = 0.02 - 0.0048 = +1.52%

--> g > 0, donc ce jeu est VIABLE.
    Tu grandis de ~1.52% par tour en realite.
```

## Exercice 2 : A quel point la volatilite tue ?

```
Ton edge = +1% par trade (apres commissions)

Calcule ta croissance reelle pour differentes volatilites :

  sigma = 5%  : g = 1% - (5%)^2/2  = 1% - 0.125% = +0.875%
  sigma = 10% : g = 1% - (10%)^2/2 = 1% - 0.5%   = +0.5%
  sigma = 15% : g = 1% - (15%)^2/2 = 1% - 1.125% = -0.125%  PERTE !
  sigma = 20% : g = 1% - (20%)^2/2 = 1% - 2%     = -1%      RUINE !

LECON : avec un edge de 1%, tu ne peux PAS te permettre
        une volatilite > ~14% par trade.

C'est pour ca que le POSITION SIZING est vital.
```

## Exercice 3 : Kelly pour ton trading

```
Suppose tes stats reelles :
  Win rate = 55% (p = 0.55)
  Avg win = 150$
  Avg loss = 100$
  b = 150/100 = 1.5

  f* = (0.55 * 1.5 - 0.45) / 1.5
     = (0.825 - 0.45) / 1.5
     = 0.375 / 1.5
     = 0.25 = 25%

  Kelly dit 25%. En pratique utilise demi-Kelly = 12.5%.

  Si ton compte = 10 000$ :
  Risque max par trade = 10000 * 0.125 = 1 250$
```

---

# ============================================
# RESUME — Fiche de revision
# ============================================

```
ERGODICITY : la moyenne d'ensemble =/= ta realite

  Le trading est MULTIPLICATIF = NON-ERGODIQUE
  --> l'EV peut etre positif et tu peux quand meme perdre

FORMULE CLE :
  g = E[r] - sigma^2 / 2

  g = croissance geometrique (ce que tu VIS)
  E[r] = ton edge moyen
  sigma^2/2 = penalite de volatilite (TOUJOURS negative)

CONSEQUENCES :
  1. La volatilite DETRUIT la richesse
  2. Un edge positif ne suffit PAS si la variance est trop grande
  3. La RUINE est irreversible (0 * quoi que ce soit = 0)
  4. Le sizing est AUSSI important que l'edge

KELLY CRITERION :
  f* = (p*b - q) / b
  En pratique : utilise DEMI-KELLY

POUR TON TRADING :
  - Ton edge d'absorption est ton E[r]
  - Ta volatilite de P&L est ton sigma
  - Si sigma est trop grand, REDUIS ta taille
  - Mieux vaut un petit edge avec peu de variance
    qu'un gros edge avec beaucoup de variance
  - JAMAIS all-in. La survie d'abord. Les profits ensuite.
```
