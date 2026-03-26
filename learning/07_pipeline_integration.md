# 07 — Pipeline Integration
# "Connecter tout a ton edge"

---

# ============================================
# APPRENTISSAGE — Pourquoi combiner ?
# ============================================

## Chaque outil seul ne suffit pas

```
GARCH seul : "La vol est haute"
  --> ok, mais est-ce bullish ou bearish ?

HMM seul : "On est en regime bear"
  --> ok, mais mon signal d'absorption est-il fiable la ?

Kalman seul : "Le signal filtre dit d'acheter"
  --> ok, mais si on est en high vol, c'est dangereux

ENSEMBLE :
  GARCH dit "vol haute" +
  HMM dit "regime bear" +
  Kalman dit "signal d'absorption detecte"

  ==> "Il y a de l'absorption mais en regime bear high-vol.
       Soit je passe, soit je reduis ma taille."
```

## Le pipeline OPTIMAL (upgrade)

```
DONNEES BRUTES (prix, volume, orderflow MNQ)
         |
         v
+---------------------------+
| 1. REGIME SWITCHING       |  "QUAND trader ?"
| Markov bayesien (#72/74)  |  --> LOW/MED/HIGH vol
+---------------------------+
         |
         v
+---------------------------+
| 2. GARCH(1,1)             |  "SI je dois trader ?"
| Filtre de volatilite (#47)|  --> sigma_garch
| Ni trop mort, ni chaos    |  --> zone exploitable
+---------------------------+
         |
         v
+---------------------------+
| 3. HAWKES PROCESS         |  "Le cluster est-il REEL ?"
| Microstructure (#94)      |  --> lambda(t) >> mu ?
| Valide l'absorption       |  --> cluster confirme
+---------------------------+
         |
         v
+---------------------------+
| 4. KALMAN AVANCE          |  "Quelle DIRECTION ?"
| OU mean reversion (#95)   |  --> fair value adaptative
| x_filtered = ... |  --> signal d'absorption propre
| (R ajuste par     |     (R depend du regime HMM)
|  regime HMM)      |     (Q depend de sigma GARCH)
+------------------+
         |
         v
+------------------+
| DECISION          |
| TRADING            |
+------------------+
```

---

# ============================================
# MODEL — Comment ca s'emboite
# ============================================

## Etape 1 : GARCH calcule la vol actuelle

```
Input : rendements recents du MNQ
Output : sigma_garch(t)

sigma^2(t) = alpha0 + alpha1 * r^2(t-1) + beta1 * sigma^2(t-1)

Ce sigma alimente :
  1. Le Kalman Filter (ajuste Q = bruit du processus)
  2. Le position sizing (plus sigma est grand = plus petit)
```

## Etape 2 : HMM detecte le regime

```
Input : rendements + sigma_garch
Output : P(etat=Low), P(etat=Med), P(etat=High)

Le regime alimente :
  1. Le Kalman Filter (ajuste R selon le regime)
  2. Le decision engine (filtre les trades)

REGLES SIMPLES :
  Si P(High-vol) > 0.7 :
    --> R plus petit (signal change vite, suit les donnees)
    --> Taille reduite ou no trade

  Si P(Low-vol) > 0.7 :
    --> R plus grand (signal stable, lisse davantage)
    --> Taille normale
```

## Etape 3 : Kalman filtre le signal d'absorption

```
Input : signal brut d'absorption + Q(GARCH) + R(HMM)
Output : signal_filtered(t)

Le filtre s'adapte au contexte :
  - High vol = Q augmente (le vrai signal bouge vite)
  - Low vol  = Q diminue (le vrai signal est stable)
  - High vol = R diminue (suit les donnees de pres)
  - Low vol  = R augmente (lisse davantage)
```

## Etape 4 : Decision de trading

```
ENTREES :
  1. signal_filtered > seuil_absorption ?
  2. regime = compatible avec absorption ?
  3. sigma_garch = acceptable pour ma taille ?

MATRICE DE DECISION :

  Regime     | Signal Fort | Signal Faible
  -----------+-------------+--------------
  Low vol    | TRADE (100%)| PAS DE TRADE
  Med vol    | TRADE (50%) | PAS DE TRADE
  High vol   | PAS DE TRADE| PAS DE TRADE

  "100%" et "50%" = pourcentage de ta taille normale
```

---

# ============================================
# LECON — Mise en pratique
# ============================================

## Exercice 1 : Scenario complet

```
Matin du lundi. Tu ouvres ton dashboard.

GARCH : sigma = 1.8% (au-dessus de la moyenne de 1.2%)
HMM : P(Low)=0.15, P(Med)=0.55, P(High)=0.30
Kalman : signal d'absorption = 0.73 (seuil = 0.60)

Analyse :
  1. Vol elevee (1.8% vs 1.2% moyenne) --> prudence
  2. Regime mixte (55% Med, 30% High) --> incertain
  3. Signal d'absorption > seuil --> signal present

Decision ?
  Le signal est la mais le contexte est risque.
  --> Trade avec DEMI-TAILLE (50%)
  --> Stop plus serre que d'habitude
  --> Objectif plus petit (prendre le profit vite)
```

## Exercice 2 : Quand NE PAS trader

```
GARCH : sigma = 3.2% (tres haute, crise)
HMM : P(Low)=0.05, P(Med)=0.15, P(High)=0.80
Kalman : signal d'absorption = 0.85 (tres fort !)

Le signal est FORT. Mais :
  - Vol extreme (3.2%)
  - 80% de chance d'etre en HIGH vol
  - Le signal fort peut etre un FAUX POSITIF
    (en high vol, tout semble fort car les mouvements sont gros)

Decision : PAS DE TRADE
  Meme si le signal est tentant.
  Rappelle-toi l'ergodicity :
  un trade monstrueux en high vol peut te ruiner.
  La SURVIE d'abord.
```

## Exercice 3 : Le trade ideal

```
GARCH : sigma = 0.8% (faible, marche calme)
HMM : P(Low)=0.82, P(Med)=0.15, P(High)=0.03
Kalman : signal d'absorption = 0.71 (au-dessus du seuil 0.60)

Analyse :
  1. Vol basse --> conditions ideales
  2. Regime clairement Low vol (82%)
  3. Signal propre et au-dessus du seuil

Decision : TRADE TAILLE PLEINE
  - C'est le setup ideal
  - Absorption detectee en marche calme
  - Stop normal, target normal
  - C'est ICI que tu fais ton argent
```

---

# ============================================
# RESUME — Fiche de revision
# ============================================

```
PIPELINE :
  Donnees --> GARCH --> sigma(t)     "Quelle vol ?"
  Donnees --> HMM   --> regime(t)    "Quel marche ?"
  Signal  --> Kalman --> clean(t)    "Quel signal vrai ?"

  sigma + regime + clean --> DECISION

INTERCONNEXIONS :
  GARCH alimente Kalman (Q = f(sigma))
  HMM alimente Kalman (R = f(regime))
  Les 3 alimentent la decision finale

DECISION MATRIX :
  Low vol  + Signal : TRADE 100%
  Med vol  + Signal : TRADE 50%
  High vol          : PAS DE TRADE (meme avec signal)
  Pas de signal     : PAS DE TRADE (quel que soit le regime)

PHILOSOPHIE :
  - Le SIGNAL dit "quoi" (absorption detectee)
  - Le REGIME dit "quand" (conditions favorables)
  - La VOL dit "combien" (taille de position)

  Les 3 doivent etre alignes pour trader.

RAPPEL ERGODICITY :
  g = E[r] - sigma^2/2

  Si sigma est trop grand, ton edge est NEGATIF.
  Le GARCH te dit quand sigma est trop grand.
  Le HMM te dit quand le regime rend ton edge moins fiable.
  Le Kalman te donne un signal propre pour eviter les faux signaux.

  SURVIE > PROFIT
  PATIENCE > ACTION
  SIGNAL + CONTEXTE > SIGNAL SEUL
```
