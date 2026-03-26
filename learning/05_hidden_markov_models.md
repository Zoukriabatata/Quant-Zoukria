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

**ETATS CACHES** (que tu ne vois pas) : Bull, Bear, Sideways

Ces etats determinent les REGLES du jeu :
- En Bull : rendements positifs, vol moderee
- En Bear : rendements negatifs, vol elevee
- En Sideways : rendements $\sim 0$, vol faible

**OBSERVATIONS** (ce que tu vois) :
$+0.5\%,\; -0.2\%,\; +0.8\%,\; -3.2\%,\; -1.5\%,\; +0.1\%, \ldots$

**LE DEFI :** A partir des observations (rendements), deviner dans quel etat cache on est.

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

On ecrit ca dans une **matrice de transition** $A$ :

|  | $\to$ Bull | $\to$ Bear | $\to$ Side |
|---|-----------|-----------|-----------|
| **Bull** | 0.85 | 0.10 | 0.05 |
| **Bear** | 0.10 | 0.80 | 0.10 |
| **Side** | 0.15 | 0.10 | 0.75 |

Lecture : "Si on est en Bull, on a 85% de chance de rester en Bull demain."

**REMARQUE IMPORTANTE :**
Les diagonales sont GRANDES (0.75–0.85)
$\to$ les regimes PERSISTENT (ils ne changent pas tout le temps).
C'est realiste : un marche bullish ne devient pas bearish en 1 jour.

## Etape 2 : Les distributions conditionnelles

Chaque etat a sa propre distribution de rendements :

| Etat | Distribution | Interpretation |
|------|-------------|----------------|
| Bull | $\mathcal{N}(+0.1\%,\; 1.5\%)$ | Centree sur +0.1% (positif), vol petite (calme) |
| Bear | $\mathcal{N}(-0.5\%,\; 3.0\%)$ | Centree sur -0.5% (negatif), vol GRANDE (volatile) |
| Sideways | $\mathcal{N}(0\%,\; 1.0\%)$ | Centree sur 0% (pas de direction), vol tres petite |

```
ETAT BULL :
      ___
     / | \
    /  |  \       <-- centree sur +0.1% (positif)
   /   |   \          ecart-type petit (calme)
  /____|____\
  -3%  0  +3%

ETAT BEAR :
    ___
   / | \
  /  |  \         <-- centree sur -0.5% (negatif)
 /   |   \            ecart-type GRAND (volatile)
/____|________\
-8% -3%  0  +3%

ETAT SIDEWAYS :
       _
      /|\
     / | \        <-- centree sur 0% (pas de direction)
    /  |  \           ecart-type tres petit (calme)
   /___|___\
   -2% 0  +2%
```

## Etape 3 : Le HMM complet

Le HMM a 3 composantes :

1. $\boldsymbol{\pi}$ = probabilites initiales : $[0.33,\; 0.33,\; 0.33]$ (on ne sait pas ou on commence)

2. $A$ = matrice de transition (comment les etats changent) :

$$A = \begin{pmatrix} 0.85 & 0.10 & 0.05 \\ 0.10 & 0.80 & 0.10 \\ 0.15 & 0.10 & 0.75 \end{pmatrix}$$

3. $B$ = distributions d'emission (quoi observer dans chaque etat) :

| Etat | $\mu$ | $\sigma$ |
|------|-------|----------|
| Bull | +0.1% | 1.5% |
| Bear | -0.5% | 3.0% |
| Sideways | 0.0% | 1.0% |

## Etape 4 : L'algorithme de Baum-Welch

**C'est l'algorithme qui APPREND les parametres ($\pi$, $A$, $B$) a partir des donnees.**

Il fonctionne en 2 etapes repetees (comme EM = Expectation-Maximization) :

**ETAPE E (Expectation) : "Deviner les etats"**
Avec les parametres actuels, calcule la probabilite d'etre dans chaque etat a chaque instant.

| temps | $P(\text{Bull})$ | $P(\text{Bear})$ | $P(\text{Side})$ |
|-------|-----------------|-----------------|-----------------|
| $t_1$ | 0.8 | 0.1 | 0.1 |
| $t_2$ | 0.7 | 0.2 | 0.1 |
| $t_3$ | 0.3 | 0.6 | 0.1 |
| $t_4$ | 0.1 | 0.8 | 0.1 |

**ETAPE M (Maximization) : "Mettre a jour les parametres"**
Avec les etats devines, recalcule $A$, les $\mu$ et $\sigma$ de chaque etat, et $\pi$.

REPETER jusqu'a convergence (les parametres ne bougent plus).

### Forward Algorithm (calcul vers l'avant)

$$\alpha(t, j) = P(O_1 \ldots O_t \text{ ET etat } j \text{ a } t)$$

Initialisation :

$$\alpha(1, j) = \pi(j) \cdot P(O_1 \mid \text{etat } j)$$

Recursion :

$$\boxed{\alpha(t+1, j) = P(O_{t+1} \mid \text{etat } j) \cdot \sum_i \alpha(t, i) \cdot A(i, j)}$$

En francais : "La proba d'etre en $j$ a $t+1$" =
"proba d'observer $O_{t+1}$ si on est en $j$"
$\times$ "somme sur tous les etats possibles a $t$ de (proba d'y etre $\times$ proba de transiter vers $j$)"

### Backward Algorithm (calcul vers l'arriere)

$$\beta(t, i) = P(O_{t+1} \ldots O_T \mid \text{etat } i \text{ a } t)$$

Initialisation : $\beta(T, i) = 1$

Recursion :

$$\boxed{\beta(t, i) = \sum_j A(i, j) \cdot P(O_{t+1} \mid \text{etat } j) \cdot \beta(t+1, j)}$$

### Combinaison : probabilite d'etre dans chaque etat

$$\boxed{\gamma(t, i) = P(\text{etat} = i \text{ a } t \mid \text{toutes les observations}) = \frac{\alpha(t, i) \cdot \beta(t, i)}{P(O)}}$$

C'est la REPONSE FINALE : $\gamma(t, \text{Bull}) = 0.8$ $\to$ "80% de chance qu'on soit en Bull"

---

# ============================================
# LECON — Exercices pratiques
# ============================================

## Exercice 1 : Matrice de transition a la main

Donnes : 20 jours de regime (tu les connais) :
L L L L H H H L L L M M M M L L L L H H

(L = Low vol, M = Medium vol, H = High vol)

Compte les transitions :

| Transition | Compte |
|-----------|--------|
| L $\to$ L | 8 |
| L $\to$ H | 2 |
| L $\to$ M | 1 |
| H $\to$ H | 2 |
| H $\to$ L | 2 |
| H $\to$ M | 0 |
| M $\to$ M | 2 |
| M $\to$ L | 1 |
| M $\to$ H | 0 |

Total depuis L : 11 transitions. Total depuis H : 4. Total depuis M : 3.

Matrice :

|  | $\to$ L | $\to$ H | $\to$ M |
|---|---------|---------|---------|
| **L** | $8/11 = 0.73$ | $2/11 = 0.18$ | $1/11 = 0.09$ |
| **H** | $2/4 = 0.50$ | $2/4 = 0.50$ | $0/4 = 0.00$ |
| **M** | $1/3 = 0.33$ | $0/3 = 0.00$ | $2/3 = 0.67$ |

Interpretation :
- Low vol est PERSISTANT (73% de rester)
- High vol retourne souvent en Low (50%)
- Medium vol est aussi persistant (67%)

## Exercice 2 : Dans quel regime suis-je ?

Tu observes les rendements suivants : $+0.2\%,\; +0.1\%,\; -0.1\%,\; +0.3\%,\; +0.2\%$

Tu connais les distributions :
- Bull : $\mathcal{N}(+0.15\%,\; 0.5\%)$
- Bear : $\mathcal{N}(-0.3\%,\; 1.5\%)$

Pour le premier rendement ($+0.2\%$) :
- $P(+0.2\% \mid \text{Bull})$ = eleve (proche de la moyenne Bull)
- $P(+0.2\% \mid \text{Bear})$ = faible (loin de la moyenne Bear)

Pour une serie de 5 rendements tous proches de $+0.15\%$ :
$\to$ presque certainement en regime BULL

Si soudain : $-2.5\%,\; -1.8\%,\; -3.1\%$
$\to$ probablement bascule en regime BEAR

## Exercice 3 : Application a ton trading

Question : Comment utiliser le HMM pour ton absorption ?

1. Calibre un HMM 3-etats sur les rendements MNQ
   $\to$ tu obtiens : Low-vol, Medium-vol, High-vol

2. Chaque matin, calcule $\gamma(\text{aujourd'hui})$ :
   $P(\text{Low})=0.7$, $P(\text{Med})=0.2$, $P(\text{High})=0.1$

3. Adapte ta strategie :
   - Low vol : absorption fiable, taille normale
   - Med vol : absorption ok, reduis un peu
   - High vol : absorption moins fiable, petite taille ou pas de trade

C'est ton FILTRE DE REGIME.

---

# ============================================
# RESUME — Fiche de revision
# ============================================

**HMM** = Hidden Markov Model — "Deviner l'etat cache a partir de ce qu'on observe"

**3 COMPOSANTES :**

| Composante | Symbole | Role |
|-----------|---------|------|
| Probabilites initiales | $\pi$ | Ou on commence |
| Matrice de transition | $A$ | Comment les etats changent |
| Distributions d'emission | $B$ | Ce qu'on observe dans chaque etat |

**PROPRIETE DE MARKOV :** Le futur depend UNIQUEMENT du present (pas du passe).

**BAUM-WELCH (apprentissage) :**
- Etape E : deviner les etats (forward + backward)
- Etape M : mettre a jour les parametres
- Repeter jusqu'a convergence

**RESULTATS TYPIQUES (3 etats) :**

| Etat | $\mu$ | $\sigma$ | Interpretation |
|------|-------|----------|---------------|
| 1 | +0.2% | 1.5% | Calme, haussier |
| 2 | -0.7% | 4.5% | Volatile, baissier |
| 3 | +0.1% | 2.5% | Intermediaire |

**MATRICE DE TRANSITION :** les diagonales sont grandes $\to$ les regimes PERSISTENT.

**ATTENTION :**
- On peut OVERFITTER (trop d'etats = bruit)
- 2–3 etats suffisent generalement
- Toujours valider OUT OF SAMPLE
- Les etats ne sont pas forcement interpretables

**POUR TON TRADING :**

HMM = FILTRE DE REGIME : "Dans quel type de marche suis-je aujourd'hui ?"

Pipeline : Donnees $\to$ HMM $\to$ regime $\to$ adapte ta taille/strategie

| Regime | Action |
|--------|--------|
| Low vol | Absorption fiable = taille normale |
| High vol | Absorption risquee = petite taille / no trade |
