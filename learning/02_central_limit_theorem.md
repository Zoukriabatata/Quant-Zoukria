# 02 — Central Limit Theorem (CLT)
# "Pourquoi les statistiques marchent"

> **Video :** [Central Limit Theorem for Quant Finance — Roman Paolucci](https://youtu.be/q2era-4pnic)

---

# ============================================
# APPRENTISSAGE — C'est quoi ? Pourquoi ?
# ============================================

## Le probleme

Tu prends 50 trades. Tu fais +2.3% en moyenne.
Est-ce que c'est ton edge ? Ou est-ce que c'est de la chance ?

Le CLT repond a cette question.

## C'est quoi le CLT ?

En francais simple :

```
Si tu prends BEAUCOUP de mesures de n'importe quoi,
la MOYENNE de ces mesures suit TOUJOURS
une distribution normale (courbe en cloche).

Meme si les mesures individuelles ne sont PAS normales.
```

## Analogie : le casino

```
1 lancer de de : resultat = 1, 2, 3, 4, 5 ou 6
  --> distribution PLATE (chaque face a 1/6 de chance)
  --> pas du tout une cloche

  |  |  |  |  |  |
  1  2  3  4  5  6

Mais si tu lances 100 des et tu fais la MOYENNE :
  --> la moyenne tourne toujours autour de 3.5
  --> et la distribution des moyennes = une CLOCHE

         ___
        /   \
       /     \
      /       \
     /         \
    2.5  3.5  4.5
```

**C'est ca le CLT :** peu importe la distribution d'origine,
la moyenne converge vers une gaussienne.

## Pourquoi c'est crucial pour le trading ?

```
Tes trades individuels = CHAOS
  +50, -30, +120, -80, +10, -60, +200, -40

Mais ta MOYENNE sur 100 trades :
  --> si tu as un edge, la moyenne sera > 0
  --> et tu PEUX le prouver statistiquement grace au CLT
```

Le CLT te dit :
1. **Combien de trades** il faut pour confirmer ton edge
2. **Quelle confiance** tu peux avoir dans ta moyenne
3. **Quand** un drawdown est "normal" vs "ton edge a disparu"

---

# ============================================
# MODEL — Les maths
# ============================================

## La formule du CLT

```
Soit X1, X2, ..., Xn des variables aleatoires
  avec moyenne mu et ecart-type sigma

Alors la moyenne X_bar = (X1 + X2 + ... + Xn) / n

suit approximativement :

  X_bar ~ Normal( mu, sigma / sqrt(n) )

          ^         ^        ^
          |         |        |
    distribution   centre   largeur
    en cloche      = mu     RETRECIT avec n
```

## Le truc magique : sigma / sqrt(n)

```
sigma = volatilite de tes trades individuels
n = nombre de trades

sigma / sqrt(n) = precision de ta moyenne

Exemple :
  sigma = 100$ par trade
  n = 25 trades  -->  100/sqrt(25) = 100/5  = 20$
  n = 100 trades -->  100/sqrt(100)= 100/10 = 10$
  n = 400 trades -->  100/sqrt(400)= 100/20 = 5$

Plus tu as de trades, plus ta moyenne est PRECISE.
```

Visuellement :

```
25 trades :
     ____
    /    \        <-- large, incertain
   /      \
  /________\
  -40  0  +40

100 trades :
      __
     /  \         <-- plus serre
    /    \
   /______\
   -20 0 +20

400 trades :
       _
      / \         <-- tres precis
     /   \
    /_____\
    -10 0 +10
```

## La regle des 68-95-99.7 (empirical rule)

```
Pour une distribution normale :

  68%  des valeurs sont dans [mu - 1*sigma, mu + 1*sigma]
  95%  des valeurs sont dans [mu - 2*sigma, mu + 2*sigma]
  99.7% des valeurs sont dans [mu - 3*sigma, mu + 3*sigma]

         99.7%
      |---------|
       95%
      |-------|
        68%
       |----|

        _____
      /|  |  |\
     / |  |  | \
    /  |  |  |  \
   /   |  |  |   \
  -3s -2s -1s 0 +1s +2s +3s
```

## Application : "Est-ce que j'ai un edge ?"

```
Tes 100 derniers trades :
  Moyenne (X_bar) = +15$ par trade
  Ecart-type (sigma) = 80$ par trade

Erreur standard = sigma / sqrt(n) = 80 / sqrt(100) = 8$

Intervalle de confiance a 95% :
  [15 - 2*8, 15 + 2*8] = [-1$, +31$]

Comme 0$ est DANS l'intervalle --> pas assez de preuves
Tu as PEUT-ETRE un edge, mais 100 trades ne suffisent pas.

Apres 400 trades (si la moyenne reste a +15$) :
  Erreur standard = 80 / sqrt(400) = 4$
  IC 95% = [15 - 8, 15 + 8] = [+7$, +23$]

Maintenant 0$ est EN DEHORS --> ton edge est REEL (95% confiance)
```

---

# ============================================
# LECON — Exercices pratiques
# ============================================

## Exercice 1 : Lancer de des

```
Tu lances 1 de : E[X] = (1+2+3+4+5+6)/6 = 3.5

Tu lances 2 des et tu fais la moyenne :
  Moyenne possible : (1+1)/2=1 ... (6+6)/2=6
  Mais la plupart des moyennes seront proches de 3.5

Question : pourquoi la moyenne de 2 des a MOINS de chance
de tomber sur 1 que 1 seul de ?

Reponse : pour avoir une moyenne de 1 avec 2 des,
il faut que les DEUX tombent sur 1.
Proba = 1/6 * 1/6 = 1/36 (au lieu de 1/6)
Les extremes deviennent RARES quand on moyenne.
```

## Exercice 2 : Ton trading

```
Suppose tes stats sur 200 trades :
  Moyenne = +8$ par trade
  Ecart-type = 60$ par trade

1. Calcule l'erreur standard :
   SE = 60 / sqrt(200) = 60 / 14.14 = ?

2. Calcule l'IC a 95% :
   [8 - 2*SE, 8 + 2*SE] = ?

3. Est-ce que ton edge est statistiquement significatif ?
   (= est-ce que 0 est en dehors de l'IC ?)

Reponses :
1. SE = 4.24$
2. IC = [8 - 8.48, 8 + 8.48] = [-0.48$, +16.48$]
3. NON, 0 est encore dans l'IC (de justesse)
   Il faut plus de trades pour confirmer.
```

## Exercice 3 : Combien de trades pour prouver ton edge ?

```
Formule : n > (2 * sigma / mu)^2

Avec mu = +8$, sigma = 60$ :
  n > (2 * 60 / 8)^2 = (15)^2 = 225 trades

Il te faut AU MINIMUM 225 trades pour confirmer
un edge de 8$ moyen avec 60$ de volatilite.
```

---

# ============================================
# RESUME — Fiche de revision
# ============================================

```
CLT : La moyenne de N observations --> distribution normale
      Peu importe la distribution d'origine

FORMULE CLE :
  Moyenne ~ Normal( mu, sigma/sqrt(n) )

  sigma/sqrt(n) = PRECISION de ta moyenne
  Plus n augmente, plus c'est precis

REGLE 68-95-99.7 :
  68% dans +-1 sigma
  95% dans +-2 sigma
  99.7% dans +-3 sigma

POUR PROUVER UN EDGE :
  1. Calcule ta moyenne (mu) et ecart-type (sigma)
  2. Erreur standard = sigma / sqrt(n)
  3. IC 95% = [mu - 2*SE, mu + 2*SE]
  4. Si 0 est EN DEHORS --> edge confirme
  5. Si 0 est DEDANS --> pas assez de donnees

NOMBRE MIN DE TRADES :
  n > (2 * sigma / mu)^2

POUR TON TRADING :
  - Ne tire JAMAIS de conclusion avec < 100 trades
  - Un bon mois ne prouve rien (trop peu de donnees)
  - Le CLT te dit QUAND tu peux faire confiance a tes stats
  - Plus ton edge est petit par rapport a la volatilite,
    plus il faut de trades pour le prouver
```
