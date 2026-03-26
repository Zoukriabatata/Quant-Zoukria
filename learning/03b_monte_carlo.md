# 03b — Why Monte Carlo Simulation Works
# "Comprendre la stabilite"

> **Video :** [Why Monte Carlo Simulation Works — Roman Paolucci](https://youtu.be/-4sf43SLL3A)

---

# ============================================
# APPRENTISSAGE — C'est quoi ? Pourquoi ?
# ============================================

## Le probleme

Tu as un jeu complexe. Tu ne connais pas la formule exacte
pour calculer tes gains moyens. Comment faire ?

**Reponse : tu simules des milliers de parties.**

C'est ca le Monte Carlo : remplacer les maths par la simulation.

## C'est quoi le Monte Carlo ?

```
IDEE SIMPLE :
  Si tu ne PEUX PAS calculer une reponse analytiquement,
  tu peux la SIMULER en repetant l'experience des milliers de fois.

  La Loi des Grands Nombres (LGN) garantit que
  la moyenne de tes simulations CONVERGE vers la vraie valeur.
```

## Analogie : le de

```
Theorie : E[de] = 3.5
  Tu ne peux pas obtenir 3.5 en un lancer.

Monte Carlo : lance le de 10 000 fois
  Moyenne des 10 000 lancers --> 3.502
  C'est TRES proche de 3.5

  Plus tu lances, plus c'est precis.
```

## Pourquoi c'est important pour ton trading ?

```
1. ESTIMER TA MOYENNE DE P&L
   Tu ne connais pas ton "vrai" edge.
   Mais tu peux simuler 10 000 seances de trading
   et voir ou converge ta moyenne.

2. ESTIMER DES PROBABILITES
   "Quelle proba de ruine si je risque 2% par trade ?"
   Simule 10 000 parcours --> compte combien finissent a 0.

3. TESTER LA STABILITE
   "Mon edge tient-il si les conditions changent ?"
   Simule avec differents parametres et observe.

4. PRICING
   Les options sont pricees par Monte Carlo
   (quand Black-Scholes ne suffit pas).
```

---

# ============================================
# MODEL — Les maths
# ============================================

## 1. La LGN comme fondation

```
Monte Carlo repose ENTIEREMENT sur la LGN :

  X1, X2, ..., Xn  tires de la meme distribution D

  Moyenne = (X1 + X2 + ... + Xn) / n  -->  E[X]  quand n --> infini

  Peu importe que D soit complique, bizarre, asymetrique...
  La moyenne converge TOUJOURS.
```

## 2. Estimer des statistiques

```
Avec n simulations tu peux estimer :

  Moyenne :    E[X] = (1/n) * SUM(Xi)
  Variance :   Var[X] = (1/(n-1)) * SUM((Xi - Xbar)^2)
  Proba :      P(X > seuil) = (nb de Xi > seuil) / n

  Precision = sigma / sqrt(n)
  Pour diviser l'erreur par 2 --> 4x plus de simulations
```

## 3. Exemple : le jeu du casino (du notebook #33)

```
REGLES :
  1. Lance un de a 6 faces
  2. Si IMPAIR (1,3,5) : piece biaisee (60% face)
     - Face = gagner 1000$
     - Pile = perdre 500$
  3. Si PAIR (2,4,6) : piece equilibree (50%)
     - Face = perdre 500$
     - Pile = gagner 1000$

CALCUL ANALYTIQUE :
  EV = P(impair)*[0.6*1000 + 0.4*(-500)]
     + P(pair)*[0.5*(-500) + 0.5*1000]
  EV = 0.5*[600-200] + 0.5*[-250+500]
  EV = 0.5*400 + 0.5*250
  EV = 200 + 125 = 325$

MONTE CARLO (10 000 parties) :
  Moyenne simulee --> 324.8$  (tres proche de 325$)
```

## 4. Estimer des probabilites

```
Question : "Quelle proba de gagner a ce jeu ?"

Monte Carlo :
  1. Simule 10 000 parties
  2. Compte combien donnent un gain > 0
  3. P(gagner) = nb_gains / 10 000

Resultat : P(gagner) = 55%

C'est un Bernoulli : Xi = 1 si gain, 0 sinon
La LGN dit : moyenne des Xi --> P(gagner)
```

## 5. Wealth paths et ruine

```
Question : "Si je joue 100 fois en payant 325$ l'entree,
            quelle proba d'atteindre 15 000$ depuis 10 000$ ?"

Monte Carlo :
  1. Simule 1000 parcours de richesse
  2. Chaque parcours : 100 parties, depart = 10 000$
  3. Compte combien atteignent 15 000$

Resultat du notebook : P(target) = ~10%

Les parcours verts = atteignent le target
Les parcours rouges = font faillite avant
```

## 6. Le defi en finance : la distribution CHANGE

```
PROBLEME :
  Monte Carlo suppose une distribution FIXE.
  En finance, la distribution des rendements CHANGE.

  Janvier : rendements ~ Normal(+0.1%, 1%)
  Mars (crise) : rendements ~ Normal(-0.5%, 3%)

  Si tu simules avec les parametres de janvier,
  ta simulation est FAUSSE pour mars.

SOLUTIONS :
  1. HMM pour detecter le regime --> simule par regime
  2. GARCH pour capturer la vol changeante
  3. Recalibrer regulierement les parametres
  4. Stress testing : simule avec des parametres extremes
```

---

# ============================================
# LECON — Exercices pratiques
# ============================================

## Exercice 1 : Monte Carlo du de

```
Lance un de 10 fois (mentalement ou avec des vrais des) :
  Resultats : 3, 5, 1, 6, 2, 4, 3, 5, 1, 4

  Moyenne = (3+5+1+6+2+4+3+5+1+4)/10 = 34/10 = 3.4
  Theorie = 3.5
  Erreur = |3.4 - 3.5| = 0.1

  Avec 100 lancers, l'erreur serait ~0.03
  Avec 10 000 lancers, l'erreur serait ~0.003
```

## Exercice 2 : Ton edge par Monte Carlo

```
Tes stats (suppose) : winrate=55%, gain moyen=+150$, perte=-100$

Simule 1 trade :
  tire un nombre aleatoire entre 0 et 1
  si < 0.55 : P&L = +150
  sinon : P&L = -100

Simule 10 000 trades, calcule la moyenne :
  EV = 0.55*150 + 0.45*(-100) = 82.5 - 45 = +37.5$ par trade

Monte Carlo confirmera ~37.5$ avec assez de simulations.
```

## Exercice 3 : Proba de ruine

```
Capital = 10 000$, risque 200$ par trade, edge = 37.5$/trade

Question : quelle proba de toucher 0$ avant 20 000$ ?

Monte Carlo :
  1. Depart = 10 000
  2. Chaque trade : +150 (55%) ou -100 (45%) * 2 contrats
  3. Stop si capital = 0 ou 20 000
  4. Repete 10 000 fois
  5. P(ruine) = nb de fois capital=0 / 10 000

Si P(ruine) < 1% : ton sizing est ok
Si P(ruine) > 5% : REDUIS ta taille
```

## Exercice 4 : Stabilite de ton edge

```
Simule 10 000 trades avec ton edge (37.5$).
Maintenant re-simule avec un edge REDUIT (20$).
Et encore avec edge = 0$ (pas d'edge).

Compare les 3 equity curves :
  Edge 37.5$ : monte regulierement
  Edge 20$   : monte lentement, plus de variance
  Edge 0$    : random walk (pas de direction)

Si ta courbe REELLE ressemble au 3e cas :
  --> tu n'as probablement pas d'edge
  --> ou ton edge a disparu (regime change)
```

---

# ============================================
# RESUME — Fiche de revision
# ============================================

```
MONTE CARLO = simuler des milliers de fois pour estimer

FONDATION : Loi des Grands Nombres
  Moyenne des n simulations --> vraie valeur
  Precision = sigma / sqrt(n)

3 USAGES PRINCIPAUX :
  1. Estimer des STATISTIQUES (moyenne, variance)
  2. Estimer des PROBABILITES (proba de ruine, de gain)
  3. Estimer des PRIX (options, produits derives)

RECETTE :
  1. Definir le modele (distribution, regles du jeu)
  2. Tirer n echantillons aleatoires
  3. Calculer la statistique d'interet
  4. La LGN garantit la convergence

PRECISION :
  n = 100    --> erreur ~ sigma/10
  n = 10 000 --> erreur ~ sigma/100
  4x plus de sims = erreur / 2

DEFI EN FINANCE :
  La distribution CHANGE dans le temps
  Monte Carlo suppose une distribution FIXE
  Solution : recalibrer, HMM, GARCH, stress tests

POUR TON TRADING :
  - Simule 10 000 seances pour estimer ton vrai edge
  - Calcule la proba de ruine avec ton sizing actuel
  - Teste la stabilite : change les parametres et observe
  - Si tes resultats reels sont HORS de l'IC simule :
    --> soit tu as plus d'edge que prevu (rare)
    --> soit ton modele est faux (plus probable)
```
