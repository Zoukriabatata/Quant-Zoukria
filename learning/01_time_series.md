# 01 — Time Series Analysis
# "Comprendre les donnees avant de les modeliser"

> **Video :** [Time Series Analysis for Quant Finance — Roman Paolucci](https://youtu.be/JwqjuUnR8OY)

---

# ============================================
# APPRENTISSAGE — C'est quoi ? Pourquoi ?
# ============================================

## Le probleme

Tu regardes un graphique de prix. Tu vois des mouvements.
Mais est-ce du signal ou du bruit ?

Une time series (serie temporelle) c'est simplement :
**une suite de valeurs ordonnees dans le temps**

```
Prix MNQ a chaque seconde :
t1: 18450.25
t2: 18450.50
t3: 18449.75
t4: 18451.00
...
```

## Pourquoi c'est important pour toi

Tout ce que tu fais en trading = analyser des time series :
- Le prix = time series
- Le volume = time series
- L'orderflow = time series
- La volatilite = time series

Si tu ne comprends pas comment une time series se decompose,
tu ne peux pas separer le SIGNAL du BRUIT.

## Les 3 composantes d'une time series

Imagine le prix comme la somme de 3 forces :

```
PRIX = TREND + SAISONNALITE + BRUIT (choc)

Exemple visuel :

TREND (la direction generale)
    /
   /
  /          <-- le marche monte lentement
 /

SAISONNALITE (patterns qui se repetent)
 /\  /\  /\
/  \/  \/  \  <-- cycle regulier (ex: ouverture US chaque jour)

BRUIT (mouvements aleatoires)
 _/\_/\__/\   <-- imprevisible, c'est le "bruit de marche"
     \/

RESULTAT = tout combine :
   _/\
  /   \  /\
 /     \/  \_/\  <-- ce que tu vois sur ton ecran
/              \
```

## Analogie simple

Pense a la METEO :
- TREND = on va vers l'ete (temperature monte)
- SAISONNALITE = il fait plus chaud le jour que la nuit
- BRUIT = demain il peut pleuvoir meme en ete

Le marche c'est pareil. Sauf que :
- Les trends sont moins clairs
- La saisonnalite est moins reguliere
- Le bruit est BEAUCOUP plus fort

---

# ============================================
# MODEL — Comment ca marche mathematiquement
# ============================================

## 1. Filtrage (Filtering)

**But :** Estimer l'etat ACTUEL en eliminant le bruit

**Methode la plus simple : Moyenne Mobile (Moving Average)**

```
MA(n) = (prix[t] + prix[t-1] + ... + prix[t-n+1]) / n

Exemple avec MA(3) :
Prix:  10, 12, 11, 13, 12, 14
MA(3):  -, -,  11, 12, 12, 13
                ^
                (10+12+11)/3 = 11
```

**Probleme :** La MA est en RETARD. Plus n est grand, plus le retard est important.

```
n petit (MA 3)  = reactif mais bruite
  /\/\/\___/\/\

n grand (MA 20) = lisse mais en retard
      ___/------\___
```

## 2. Lissage (Smoothing)

**But :** Donner plus de poids aux donnees recentes

**Exponential Moving Average (EMA) :**

```
EMA(t) = alpha * prix(t) + (1 - alpha) * EMA(t-1)

alpha = facteur de lissage (entre 0 et 1)
  - alpha proche de 1 = reagit vite (suit le prix)
  - alpha proche de 0 = reagit lentement (lisse beaucoup)
```

```
alpha = 0.9 (reactif)     alpha = 0.1 (lisse)
  /\/\___/\                    ___/---\___
  suit le prix de pres         filtre le bruit
```

## 3. Prevision (Forecasting)

**But :** Estimer le FUTUR

**La verite brutale :** Les previsions de prix sont TOUJOURS fausses.

```
Pourquoi ? Parce que :

Le prix aujourd'hui             Le prix demain
     |                               |
     v                               v
  18450.00         -->           ????.??

Le marche peut :
1. Continuer (trend)
2. Reverser (mean reversion)
3. Exploser (choc/news)
4. Rester la (range)

PERSONNE ne sait lequel.
```

**Mais alors a quoi ca sert ?**

On ne predit pas le prix exact.
On estime une DISTRIBUTION de prix possibles.

```
           Probable
              |
         _____|_____
        /     |     \
       /      |      \     <-- distribution des prix possibles
      /       |       \
     /        |        \
   Baisse   Actuel   Hausse

On dit : "le prix sera PROBABLEMENT dans cette zone"
         avec X% de confiance
```

## 4. Le Random Walk (marche aleatoire)

Le modele de base en finance :

```
prix(t+1) = prix(t) + bruit_aleatoire

En gros : le meilleur predicateur du prix de demain
           c'est le prix d'aujourd'hui + du hasard
```

C'est dur a accepter mais c'est le point de depart.
Le but des modeles plus avances (GARCH, HMM, Kalman)
c'est de capturer ce que le random walk ne capture PAS.

---

# ============================================
# LECON — Exercices pratiques
# ============================================

## Exercice 1 : Decomposition mentale

Regarde un graphique MNQ de la derniere semaine.
Identifie visuellement :

```
1. Le TREND : le marche montait ou descendait globalement ?
2. La SAISONNALITE : tu vois un pattern a l'ouverture US ? (9h30)
3. Le BRUIT : les mouvements qui n'ont aucun sens
```

## Exercice 2 : Moving Average a la main

```
Prix MNQ (5 barres) : 100, 102, 101, 103, 104

Calcule MA(3) pour chaque point possible :
- Point 3 : (100 + 102 + 101) / 3 = ?
- Point 4 : (102 + 101 + 103) / 3 = ?
- Point 5 : (101 + 103 + 104) / 3 = ?

Reponse :
- Point 3 : 101.0
- Point 4 : 102.0
- Point 5 : 102.67
```

## Exercice 3 : EMA a la main

```
Prix : 100, 105, 103
Alpha = 0.5

EMA(1) = 100 (on demarre au premier prix)
EMA(2) = 0.5 * 105 + 0.5 * 100 = ?
EMA(3) = 0.5 * 103 + 0.5 * EMA(2) = ?

Reponse :
EMA(2) = 102.5
EMA(3) = 102.75
```

## Exercice 4 : Signal vs Bruit

```
Imagine 2 scenarios :

Scenario A : Prix fait +1, -1, +1, -1, +1, -1
  --> C'est du BRUIT (aucune direction)

Scenario B : Prix fait +3, +2, -1, +4, +1, +5
  --> Il y a du SIGNAL (trend haussier + bruit)

Comment differencier ?
Regarde la SOMME CUMULATIVE :
  A : +1, 0, +1, 0, +1, 0     --> oscille autour de 0
  B : +3, +5, +4, +8, +9, +14  --> monte clairement
```

---

# ============================================
# RESUME — Fiche de revision
# ============================================

```
TIME SERIES = valeurs ordonnees dans le temps
            = TREND + SAISONNALITE + BRUIT

3 TACHES :
  Filtrage   = estimer le present (MA, EMA)
  Lissage    = eliminer le bruit
  Prevision  = estimer le futur (toujours incertain)

MOVING AVERAGE : moyenne des n derniers points
  + simple
  - en retard

EMA : poids exponentiels (recent = plus important)
  + reactif
  - peut surreagir

RANDOM WALK : prix(t+1) = prix(t) + hasard
  --> meilleur predicateur naif = prix actuel

LECON CLE :
  Les previsions de prix EXACTES n'existent pas.
  On travaille avec des DISTRIBUTIONS (probabilites).
  Le but = filtrer le bruit pour voir le signal.

POUR TON TRADING :
  Ton signal d'absorption = une time series
  Tu dois le FILTRER (Kalman) pour enlever le bruit
  Et le CONTEXTUALISER (HMM/GARCH) par le regime
```
