# 05 — Hidden Markov Models (HMM)
# "Detecter le regime de marche"

> **Video :** [Hidden Markov Models for Quant Finance — Roman Paolucci](https://youtu.be/Bru4Mkr601Q)

---

# ============================================
# APPRENTISSAGE — C'est quoi ? Pourquoi ?
# ============================================

## Le probleme

Le marche n'est pas toujours pareil. Certains jours c'est calme,
d'autres c'est le chaos. Ton edge d'absorption ne marche pas
pareil dans les deux cas.

```
REGIME 1 (calme) :          REGIME 2 (volatile) :
  ___---___---___            /\    /\
                              \  /  \/\  /\
                               \/       \/

  Ton absorption              Ton absorption
  marche bien ici             peut se faire
                              ecraser ici
```

**Le probleme :** tu ne VOIS PAS directement le regime.
Tu vois juste le prix. Le regime est CACHE (hidden).

## L'idee du HMM

Le marche a des "etats caches" qui influencent ce que tu observes.

```
ETATS CACHES (que tu ne vois pas) :
  [Bull]  [Bear]  [Sideways]

  Ces etats determinent les REGLES du jeu :
  - En Bull : rendements positifs, vol moderee
  - En Bear : rendements negatifs, vol elevee
  - En Sideways : rendements ~0, vol faible

OBSERVATIONS (ce que tu vois) :
  +0.5%, -0.2%, +0.8%, -3.2%, -1.5%, +0.1%, ...

LE DEFI :
  A partir des observations (rendements),
  deviner dans quel etat cache on est.
```

## Analogie : la meteo interieure

```
Tu es dans un bureau SANS FENETRE.
Tu ne vois PAS le temps qu'il fait (= etat cache).

Mais tu observes les gens qui arrivent :
  - Parapluie ? --> probablement qu'il pleut
  - Lunettes de soleil ? --> probablement beau temps
  - Veste ? --> probablement nuageux

L'HMM fait pareil :
  Il observe les RENDEMENTS (= parapluies)
  Et deduit le REGIME (= meteo) le plus probable.
```

---

# ============================================
# MODEL — Les maths
# ============================================

## Etape 1 : Chaines de Markov (les fondations)

**Propriete de Markov :**
"L'etat de demain depend UNIQUEMENT de l'etat d'aujourd'hui"
(pas d'hier, pas d'avant-hier)

```
Aujourd'hui = Bull

  Demain ?
  +---> Bull (85% de chance)     <-- le regime persiste souvent
  +---> Bear (10% de chance)     <-- changement rare
  +---> Sideways (5% de chance)  <-- changement rare
```

On ecrit ca dans une **matrice de transition** :

```
              Vers:
              Bull   Bear   Side
Depuis: Bull [ 0.85   0.10   0.05 ]
        Bear [ 0.10   0.80   0.10 ]
        Side [ 0.15   0.10   0.75 ]

Lecture : "Si on est en Bull, on a 85% de chance
           de rester en Bull demain"

REMARQUE IMPORTANTE :
  Les diagonales sont GRANDES (0.75-0.85)
  --> les regimes PERSISTENT (ils ne changent pas tout le temps)
  --> c'est realiste : un marche bullish ne devient pas
      bearish en 1 jour
```

## Etape 2 : Les distributions conditionnelles

Chaque etat a sa propre distribution de rendements :

```
ETAT BULL :
  Rendements ~ Normal(+0.1%, 1.5%)

      ___
     / | \
    /  |  \       <-- centree sur +0.1% (positif)
   /   |   \          ecart-type petit (calme)
  /____|____\
  -3%  0  +3%

ETAT BEAR :
  Rendements ~ Normal(-0.5%, 3.0%)

    ___
   / | \
  /  |  \         <-- centree sur -0.5% (negatif)
 /   |   \            ecart-type GRAND (volatile)
/____|________\
-8% -3%  0  +3%

ETAT SIDEWAYS :
  Rendements ~ Normal(0%, 1.0%)

       _
      /|\
     / | \        <-- centree sur 0% (pas de direction)
    /  |  \           ecart-type tres petit (calme)
   /___|___\
   -2% 0  +2%
```

## Etape 3 : Le HMM complet

Le HMM a 3 composantes :

```
1. pi = probabilites initiales
   [0.33, 0.33, 0.33]  (on ne sait pas ou on commence)

2. A = matrice de transition (comment les etats changent)
   [0.85 0.10 0.05]
   [0.10 0.80 0.10]
   [0.15 0.10 0.75]

3. B = distributions d'emission (quoi observer dans chaque etat)
   Bull:     N(mu=+0.1%, sigma=1.5%)
   Bear:     N(mu=-0.5%, sigma=3.0%)
   Sideways: N(mu=0.0%,  sigma=1.0%)
```

## Etape 4 : L'algorithme de Baum-Welch

**C'est l'algorithme qui APPREND les parametres (pi, A, B) a partir des donnees.**

Il fonctionne en 2 etapes repetees (comme EM = Expectation-Maximization) :

```
ETAPE E (Expectation) : "Deviner les etats"
  Avec les parametres actuels, calcule la probabilite
  d'etre dans chaque etat a chaque instant.

  temps:    t1     t2     t3     t4
  P(Bull):  0.8    0.7    0.3    0.1
  P(Bear):  0.1    0.2    0.6    0.8
  P(Side):  0.1    0.1    0.1    0.1

ETAPE M (Maximization) : "Mettre a jour les parametres"
  Avec les etats devines, recalcule :
  - La matrice de transition A
  - Les moyennes et ecarts-types de chaque etat
  - Les probabilites initiales pi

REPETER jusqu'a convergence (les parametres ne bougent plus)
```

### Forward Algorithm (calcul vers l'avant)

```
alpha(t, j) = P(observer O1...Ot ET etre dans l'etat j a t)

Initialisation :
  alpha(1, j) = pi(j) * P(O1 | etat j)

Recursion :
  alpha(t+1, j) = P(Ot+1 | etat j) * SUM_i[ alpha(t,i) * A(i,j) ]

  En francais :
  "La proba d'etre en j a t+1" =
    "proba d'observer Ot+1 si on est en j"
    * "somme sur tous les etats possibles a t
       de (proba d'y etre * proba de transiter vers j)"
```

### Backward Algorithm (calcul vers l'arriere)

```
beta(t, i) = P(observer Ot+1...OT | etre dans l'etat i a t)

Initialisation :
  beta(T, i) = 1

Recursion :
  beta(t, i) = SUM_j[ A(i,j) * P(Ot+1 | etat j) * beta(t+1, j) ]
```

### Combinaison : probabilite d'etre dans chaque etat

```
gamma(t, i) = P(etat = i a temps t | toutes les observations)

            = alpha(t,i) * beta(t,i) / P(O)

C'est la REPONSE FINALE :
  gamma(t, Bull) = 0.8 --> "80% de chance qu'on soit en Bull"
```

---

# ============================================
# LECON — Exercices pratiques
# ============================================

## Exercice 1 : Matrice de transition a la main

```
Donnes : 20 jours de regime (tu les connais) :
  L L L L H H H L L L M M M M L L L L H H

  L = Low vol, M = Medium vol, H = High vol

Compte les transitions :
  L->L : 8 fois
  L->H : 2 fois
  L->M : 1 fois
  H->H : 2 fois
  H->L : 2 fois
  H->M : 0 fois
  M->M : 2 fois
  M->L : 1 fois
  M->H : 0 fois

Total depuis L : 11 transitions
Total depuis H : 4 transitions
Total depuis M : 3 transitions (le dernier M n'a pas de "vers")

Matrice :
         L      H      M
  L  [ 8/11   2/11   1/11 ] = [0.73  0.18  0.09]
  H  [ 2/4    2/4    0/4  ] = [0.50  0.50  0.00]
  M  [ 1/3    0/3    2/3  ] = [0.33  0.00  0.67]

Interpretation :
  - Low vol est PERSISTANT (73% de rester)
  - High vol retourne souvent en Low (50%)
  - Medium vol est aussi persistant (67%)
```

## Exercice 2 : Dans quel regime suis-je ?

```
Tu observes les rendements suivants :
  +0.2%, +0.1%, -0.1%, +0.3%, +0.2%

Tu connais les distributions :
  Bull : N(+0.15%, 0.5%)
  Bear : N(-0.3%, 1.5%)

Pour le premier rendement (+0.2%) :
  P(+0.2% | Bull) = eleve (proche de la moyenne Bull)
  P(+0.2% | Bear) = faible (loin de la moyenne Bear)

Pour une serie de 5 rendements tous proches de +0.15% :
  --> presque certainement en regime BULL

Si soudain : -2.5%, -1.8%, -3.1%
  --> probablement bascule en regime BEAR
```

## Exercice 3 : Application a ton trading

```
Question : Comment utiliser le HMM pour ton absorption ?

1. Calibre un HMM 3-etats sur les rendements MNQ
   --> tu obtiens : Low-vol, Medium-vol, High-vol

2. Chaque matin, calcule gamma(aujourd'hui) :
   P(Low)=0.7, P(Med)=0.2, P(High)=0.1

3. Adapte ta strategie :
   - Low vol : absorption fiable, taille normale
   - Med vol : absorption ok, reduis un peu
   - High vol : absorption moins fiable, petite taille ou pas de trade

C'est ton FILTRE DE REGIME.
```

---

# ============================================
# RESUME — Fiche de revision
# ============================================

```
HMM = Hidden Markov Model
  "Deviner l'etat cache a partir de ce qu'on observe"

3 COMPOSANTES :
  1. pi   = ou on commence (probabilites initiales)
  2. A    = comment les etats changent (matrice de transition)
  3. B    = ce qu'on observe dans chaque etat (distributions)

PROPRIETE DE MARKOV :
  Le futur depend UNIQUEMENT du present (pas du passe)

BAUM-WELCH (apprentissage) :
  Etape E : deviner les etats (forward + backward)
  Etape M : mettre a jour les parametres
  Repeter jusqu'a convergence

RESULTATS TYPIQUES (3 etats) :
  Etat 1 : mean=+0.2%, std=1.5%  (calme, haussier)
  Etat 2 : mean=-0.7%, std=4.5%  (volatile, baissier)
  Etat 3 : mean=+0.1%, std=2.5%  (intermediaire)

MATRICE DE TRANSITION : les diagonales sont grandes
  --> les regimes PERSISTENT (changent rarement)

ATTENTION :
  - On peut OVERFITTER (trop d'etats = bruit)
  - 2-3 etats suffisent generalement
  - Toujours valider OUT OF SAMPLE
  - Les etats ne sont pas forcement interpretables

POUR TON TRADING :
  HMM = FILTRE DE REGIME
  "Dans quel type de marche suis-je aujourd'hui ?"

  Pipeline :
  Donnees --> HMM --> regime --> adapte ta taille/strategie

  Low vol  = absorption fiable = taille normale
  High vol = absorption risquee = petite taille / no trade
```
