# 02b — Asymptotics (Statistics)
# "Ce qui se passe quand n devient grand"

---

# ============================================
# APPRENTISSAGE — C'est quoi ? Pourquoi ?
# ============================================

## Le probleme

Tu as 50 trades. Ta moyenne est +12$/trade.
Mais est-ce que cette moyenne est FIABLE ?

Avec 500 trades, ta moyenne serait-elle la meme ?
Avec 5000 ? Avec l'infini ?

**L'asymptotique repond a cette question :**
"Que se passe-t-il quand j'ai de plus en plus de donnees ?"

## Pourquoi c'est vital pour le trading

Tout ce que tu calcules sur tes trades (moyenne, sharpe, winrate)
ce sont des ESTIMATIONS basees sur un echantillon limite.

```
TES DONNEES :
  50 trades --> estimation BRUYANTE (peut etre tres fausse)
  500 trades --> estimation CORRECTE (commence a etre fiable)
  5000 trades --> estimation PRECISE (tu peux faire confiance)

L'asymptotique te dit :
  1. Est-ce que ton estimateur CONVERGE vers la vraie valeur ?
  2. A QUELLE VITESSE il converge ?
  3. QUELLE FORME prend l'erreur ?
```

## Analogie : viser une cible

```
Avec 10 tirs :           Avec 1000 tirs :
    .                         .
  .   .  .                 .. ...
    .  .                  .......
  .                       ........
    .                      .......
                            .. ..
                              .
Tu vois un nuage           Tu vois clairement
tu sais pas trop            ou tu vises
ou est le centre            le centre apparait

L'asymptotique = "plus tu tires, plus le centre apparait"
```

## Les 3 grands resultats asymptotiques

```
1. LOI DES GRANDS NOMBRES (LGN)
   "La moyenne converge vers l'esperance"
   --> ton estimation CONVERGE

2. THEOREME CENTRAL LIMITE (CLT)
   "L'erreur suit une gaussienne"
   --> tu peux QUANTIFIER l'incertitude

3. METHODE DU DELTA
   "Si f(X) est lisse, f(X_bar) converge aussi"
   --> tu peux transformer tes estimations
```

---

# ============================================
# MODEL — Les maths
# ============================================

## 1. Types de convergence

Il y a plusieurs facons de dire "ca converge" en stats.
Du plus faible au plus fort :

```
CONVERGENCE EN DISTRIBUTION (la plus faible)
  Xn -->d X
  "La FORME de la distribution converge"

  Exemple : le CLT
  La distribution de la moyenne --> gaussienne
  (les valeurs individuelles n'ont pas besoin de converger)


CONVERGENCE EN PROBABILITE (plus fort)
  Xn -->p X
  "La VALEUR converge, les gros ecarts deviennent rares"

  Pour tout epsilon > 0 :
  P(|Xn - X| > epsilon) --> 0 quand n --> infini

  En francais : la proba d'etre "loin" de X tend vers 0


CONVERGENCE PRESQUE SURE (le plus fort)
  Xn -->ps X
  "La VALEUR converge pour de vrai, pas juste en proba"

  P(Xn --> X) = 1

  En francais : avec probabilite 1, les valeurs convergent
```

Visuellement :

```
n petit :     Xn peut etre n'importe ou

  <----[=====X=====]---->
       tres large

n moyen :     Xn se rapproche

  <------[==X==]-------->
         plus serre

n grand :     Xn est colle

  <--------[X]---------->
          precis

n = infini :  Xn = X
```

## 2. Loi des Grands Nombres (LGN)

C'est LE resultat fondamental.

```
ENONCE :

  Soit X1, X2, ..., Xn des variables i.i.d.
  avec E[Xi] = mu

  Alors :
  X_bar = (X1 + X2 + ... + Xn) / n  -->p  mu

  "La moyenne empirique converge vers la vraie moyenne"
```

Application au trading :

```
Tes trades : X1, X2, ..., Xn (P&L de chaque trade)
  Chaque trade a une esperance E[Xi] = mu (ton edge)

Moyenne empirique = (somme des P&L) / n

LGN dit : quand n grandit, ta moyenne empirique --> mu

  n = 10   : moyenne = +25$ (mais mu = +8$, ecart = 17$)
  n = 100  : moyenne = +11$ (ecart = 3$)
  n = 1000 : moyenne = +8.3$ (ecart = 0.3$)
  n = inf  : moyenne = +8$ = mu exactement
```

**Condition importante : i.i.d.**
(independant et identiquement distribue)

```
i.i.d. en trading = chaque trade est :
  - INDEPENDANT du precedent (pas de correlation)
  - MEME DISTRIBUTION (meme strategie, meme conditions)

Est-ce vrai en pratique ? PAS TOUJOURS.
  - Tes trades apres un drawdown sont-ils independants ? (tilt?)
  - Le marche de lundi est-il identique a celui de vendredi ?
  - Ton edge change-t-il avec le temps ? (regime change)

Quand i.i.d. est viole, la convergence est PLUS LENTE.
C'est pour ca que le HMM et le GARCH sont importants :
ils modelisent les violations de i.i.d.
```

## 3. Vitesse de convergence

La LGN dit "ca converge". Mais A QUELLE VITESSE ?

```
VITESSE : 1 / sqrt(n)

  Erreur typique de la moyenne = sigma / sqrt(n)

  sigma = ecart-type de tes trades
  n = nombre de trades

  n = 25   --> erreur ~ sigma/5
  n = 100  --> erreur ~ sigma/10
  n = 400  --> erreur ~ sigma/20
  n = 10000 --> erreur ~ sigma/100

Pour DIVISER l'erreur par 2, il faut 4x PLUS de trades.
Pour DIVISER l'erreur par 10, il faut 100x PLUS de trades.

C'est la "racine de n" -- lente mais sure.
```

Visuellement :

```
Erreur
  |
  |*
  | *
  |  *
  |   **
  |     ***
  |        ******
  |              **************
  +---------------------------------> n
  0   100   400   1000   5000

La courbe descend vite au debut, puis de plus en plus lentement.
Les premiers trades reduisent beaucoup l'incertitude.
Apres ~500 trades, les gains de precision sont marginaux.
```

## 4. Theoreme Central Limite (rappel + extension)

Le CLT dit QUELLE FORME prend l'erreur :

```
sqrt(n) * (X_bar - mu) / sigma  -->d  Normal(0, 1)

En reorganisant :
X_bar ~ Normal(mu, sigma^2/n) pour n grand

Cela permet de construire des INTERVALLES DE CONFIANCE :
  IC 95% = [X_bar - 1.96*sigma/sqrt(n), X_bar + 1.96*sigma/sqrt(n)]
```

## 5. Consistance d'un estimateur

Un estimateur est CONSISTANT s'il converge vers la vraie valeur.

```
CONSISTANT :
  Plus tu as de donnees, plus c'est precis.
  Exemple : la moyenne empirique est consistante pour mu.

NON CONSISTANT :
  Meme avec l'infini de donnees, ca ne converge pas.
  Exemple : utiliser le PREMIER trade comme estimateur.
  X1 ne change jamais, peu importe combien tu trades apres.
```

Estimateurs courants en trading et leur consistance :

```
ESTIMATEUR          CONSISTANT ?    VITESSE
----------------------------------------------
Moyenne (edge)      OUI             1/sqrt(n)
Variance            OUI             1/sqrt(n)
Sharpe ratio        OUI             1/sqrt(n)  (mais biaise pour petit n)
Win rate            OUI             1/sqrt(n)
Max drawdown        NON (*)         log(n)/n
Ratio gain/perte    OUI             1/sqrt(n)

(*) Le max drawdown est BIAISE : plus tu trades longtemps,
    plus le max drawdown sera grand.
    C'est un estimateur qui ne converge PAS vers une valeur fixe.
```

## 6. Methode du Delta

Si tu connais le comportement asymptotique de X_bar,
tu peux en deduire celui de f(X_bar) pour toute fonction f lisse.

```
METHODE DU DELTA :

  Si sqrt(n) * (X_bar - mu) -->d Normal(0, sigma^2)

  Alors :
  sqrt(n) * (f(X_bar) - f(mu)) -->d Normal(0, sigma^2 * [f'(mu)]^2)

En francais :
  Si tu transformes ta moyenne avec une fonction,
  la variance est multipliee par [derivee]^2.
```

Application : le Sharpe Ratio

```
Sharpe = X_bar / S    (moyenne / ecart-type)

C'est une FONCTION de deux estimateurs.
La methode du delta dit que :

  Var(Sharpe) ~ (1 + Sharpe^2/2) / n

  Pour Sharpe = 1.0 et n = 100 :
  Var ~ (1 + 0.5) / 100 = 0.015
  Ecart-type du Sharpe ~ 0.12

  IC 95% = [1.0 - 0.24, 1.0 + 0.24] = [0.76, 1.24]

  Ton Sharpe de 1.0 pourrait en realite etre entre 0.76 et 1.24.
  Avec 400 trades : IC = [0.88, 1.12] -- plus precis.
```

## 7. Biais vs Consistance

```
BIAIS = erreur SYSTEMATIQUE (meme direction a chaque fois)

  Estimateur BIAISE mais CONSISTANT :
  Le biais disparait quand n grandit.

  Exemple : variance empirique avec 1/n au lieu de 1/(n-1)
    Biais = -sigma^2/n --> 0 quand n grandit
    Consistant quand meme.

  Estimateur NON BIAISE mais NON CONSISTANT :
  Pas d'erreur systematique mais ne converge pas.

  Exemple : X1 (le premier trade) comme estimateur de mu.
    E[X1] = mu (pas de biais)
    Mais ne s'ameliore jamais avec plus de donnees.

POUR LE TRADING :
  Le Sharpe ratio sur petit echantillon est BIAISE vers le haut.
  Formule de correction : Sharpe_corrige = Sharpe * sqrt((n-1)/n)
  Mais c'est consistant : avec assez de trades, ca converge.
```

---

# ============================================
# LECON — Exercices pratiques
# ============================================

## Exercice 1 : Convergence de la moyenne

```
Tu trades avec un edge reel de mu = +5$ et sigma = 80$.

Calcule l'erreur standard pour differents n :

  n = 25  : SE = 80/sqrt(25)  = 80/5   = ?
  n = 100 : SE = 80/sqrt(100) = 80/10  = ?
  n = 400 : SE = 80/sqrt(400) = 80/20  = ?
  n = 2500: SE = 80/sqrt(2500)= 80/50  = ?

Reponses :
  n = 25  : SE = 16$   (ta moyenne peut etre entre -27$ et +37$)
  n = 100 : SE = 8$    (ta moyenne peut etre entre -11$ et +21$)
  n = 400 : SE = 4$    (ta moyenne peut etre entre -3$ et +13$)
  n = 2500: SE = 1.6$  (ta moyenne peut etre entre +1.8$ et +8.2$)
```

## Exercice 2 : Combien de trades pour confirmer un Sharpe ?

```
Tu mesures un Sharpe de 1.5 sur 50 trades.

Ecart-type du Sharpe = sqrt((1 + Sharpe^2/2) / n)
  = sqrt((1 + 1.125) / 50)
  = sqrt(2.125 / 50)
  = sqrt(0.0425)
  = 0.206

IC 95% = [1.5 - 2*0.206, 1.5 + 2*0.206] = [1.09, 1.91]

Question : est-ce que ton Sharpe pourrait etre < 0.5 ?
Non, 0.5 est en dehors de l'IC. Bon signe.

Mais avec seulement 20 trades :
  SE = sqrt(2.125/20) = 0.326
  IC = [0.85, 2.15]

  Le Sharpe reel pourrait etre aussi bas que 0.85.
  Beaucoup moins impressionnant.
```

## Exercice 3 : La LGN en action

```
Tu lances un de 6 faces. E[X] = 3.5

Simule mentalement :
  10 lancers  : 4, 1, 6, 3, 2, 5, 6, 1, 4, 3  --> moyenne = 3.5 (chanceux!)

Typiquement :
  10 lancers  : moyenne entre 2.5 et 4.5  (large)
  100 lancers : moyenne entre 3.2 et 3.8  (plus serre)
  1000 lancers: moyenne entre 3.4 et 3.6  (precis)

Calcule l'IC 95% :
  sigma du de = sqrt(35/12) = 1.71

  n=10  : IC = [3.5 +/- 2*1.71/sqrt(10)]  = [3.5 +/- 1.08] = [2.42, 4.58]
  n=100 : IC = [3.5 +/- 2*1.71/sqrt(100)] = [3.5 +/- 0.34] = [3.16, 3.84]
  n=1000: IC = [3.5 +/- 2*1.71/sqrt(1000)]= [3.5 +/- 0.11] = [3.39, 3.61]
```

## Exercice 4 : Biais du max drawdown

```
Pourquoi le max drawdown est un MAUVAIS estimateur :

  Tu trades 100 jours : max DD = -500$
  Tu trades 200 jours : max DD = -700$ (probablement pire)
  Tu trades 1000 jours: max DD = -1200$ (encore pire)

  Le max drawdown GRANDIT avec le nombre de trades.
  Il ne converge pas vers une valeur fixe.

  C'est pour ca qu'il faut normaliser :
  Max DD / sigma / sqrt(n) est un meilleur indicateur.

  Ou utiliser des drawdowns MOYENS plutot que le MAX.
```

## Exercice 5 : Methode du delta pour le win rate

```
Ton win rate observe = 58% sur 200 trades.

Le win rate est une moyenne de Bernoulli :
  sigma = sqrt(p*(1-p)) = sqrt(0.58*0.42) = 0.494

Erreur standard = sigma / sqrt(n) = 0.494 / sqrt(200) = 0.035

IC 95% = [0.58 - 2*0.035, 0.58 + 2*0.035] = [0.51, 0.65]

Ton vrai win rate est probablement entre 51% et 65%.

Si tu veux etre sur que c'est > 50% :
  Il faut que 0.50 soit en dehors de l'IC.
  0.50 < 0.51 --> c'est (de justesse) en dehors.
  Ton winrate > 50% est confirme a ~95%.

Avec 50 trades seulement :
  SE = 0.494/sqrt(50) = 0.070
  IC = [0.44, 0.72]
  0.50 est DEDANS --> tu ne peux PAS confirmer.
```

---

# ============================================
# RESUME — Fiche de revision
# ============================================

```
ASYMPTOTIQUE = "que se passe-t-il quand n --> infini ?"

3 TYPES DE CONVERGENCE (du plus faible au plus fort) :
  En distribution : la forme converge (CLT)
  En probabilite  : la valeur converge (LGN)
  Presque sure    : la valeur converge pour de vrai

LOI DES GRANDS NOMBRES :
  X_bar -->  mu quand n grandit
  "La moyenne empirique converge vers la vraie moyenne"

VITESSE DE CONVERGENCE :
  Erreur ~ sigma / sqrt(n)
  Pour diviser l'erreur par 2 --> 4x plus de donnees
  Pour diviser par 10 --> 100x plus de donnees

CLT (extension) :
  X_bar ~ Normal(mu, sigma^2/n)
  Permet de construire des intervalles de confiance

CONSISTANCE :
  Un estimateur est consistant s'il converge vers la verite
  Moyenne, variance, Sharpe, win rate = consistants
  Max drawdown = NON consistant (grandit avec n)

METHODE DU DELTA :
  Var(f(X_bar)) ~ [f'(mu)]^2 * sigma^2 / n
  Utile pour Sharpe, ratios, transformations

BIAIS vs CONSISTANCE :
  Biais = erreur systematique (direction fixe)
  Consistance = convergence vers la verite
  On peut etre biaise ET consistant (biais disparait)

POUR TON TRADING :
  - N'evalue JAMAIS ta strategie sur < 100 trades
  - Le Sharpe est biaise vers le haut sur petit echantillon
  - Le max drawdown n'est PAS un bon benchmark (grandit avec n)
  - Win rate de 55% sur 50 trades = probablement du bruit
  - Win rate de 55% sur 500 trades = probablement reel
  - Toujours calculer l'IC avant de conclure
  - i.i.d. rarement vrai en trading --> convergence plus lente
  - GARCH et HMM modelisent les violations de i.i.d.
```
