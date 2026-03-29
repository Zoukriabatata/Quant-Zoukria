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

**Equation 1 — Le modele** (comment l'etat EVOLUE) :

$$x_t = F \cdot x_{t-1} + B \cdot u + w_t \quad ,\quad w_t \sim \mathcal{N}(0, Q)$$

**Equation 2 — L'observation** (ce qu'on MESURE) :

$$z_t = H \cdot x_t + v_t \quad ,\quad v_t \sim \mathcal{N}(0, R)$$

- $x_t$ = etat vrai (ce qu'on cherche)
- $F$ = dynamique du modele
- $z_t$ = observation (le tick, le prix)
- $Q$ = bruit du processus, $R$ = bruit de mesure

## Les 2 etapes du Kalman Filter

A CHAQUE nouveau point de donnee, tu fais :

**ETAPE 1 : PREDICTION** (le modele parle)

$$\hat{x}_{pred} = F \cdot x_{prev} + B \cdot u$$
$$P_{pred} = F^2 \cdot P_{prev} + Q$$

> "Voici ou je PENSE que l'etat est, et voici mon INCERTITUDE"

**ETAPE 2 : CORRECTION** (les donnees parlent)

$$\text{Innovation} = z - \hat{x}_{pred}$$
$$K = \frac{P_{pred}}{P_{pred} + R}$$
$$\hat{x}_{new} = \hat{x}_{pred} + K \cdot \text{Innovation}$$
$$P_{new} = (1 - K) \cdot P_{pred}$$

> "Je corrige ma prediction avec les donnees. Mon incertitude a DIMINUE"

## Le KALMAN GAIN (K) — la cle de tout

$$\boxed{K = \frac{P_{pred}}{P_{pred} + R}}$$

- $P_{pred}$ = incertitude du **MODELE**
- $R$ = incertitude de la **MESURE** (bruit des donnees)
- $K$ est toujours entre 0 et 1

| Situation | $K$ | Comportement |
|---|---|---|
| $P$ grand (modele incertain) | $K \to 1$ | Suit les **donnees** |
| $R$ grand (donnees bruitees) | $K \to 0$ | Suit le **modele** |
| $P = R$ | $K = 0.5$ | Equilibre |

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

**MODELE :** le VIX suit un processus OU (mean reversion)

$$x_t = e^{-\kappa \Delta t} \cdot x_{t-1} + \theta(1 - e^{-\kappa \Delta t})$$

En AR(1) : $x_t = \phi \cdot x_{t-1} + b$

| Parametre | Valeur | Role |
|---|---|---|
| $\kappa$ | $25.4$ | Vitesse de reversion |
| $\theta$ | $15.5$ | Moyenne long terme |
| $\sigma$ | $43.1$ | Volatilite de la vol |

**OBSERVATION :** le VIX quote $= x_{vrai} + \text{bruit de mesure}$

**KALMAN FILTER :**
1. PREDICTION : "Mon modele dit $\hat{x}_{pred} = 18.3$"
2. OBSERVATION : "Le marche quote $z = 21.5$"
3. GAIN : $K = 0.7$
4. ESTIMATION : $18.3 + 0.7 \times (21.5 - 18.3) = 18.3 + 2.24 = 20.54$
5. "Mon meilleur guess du VRAI VIX $= 20.54$"

## Dual Filter : detecter les regime changes

**PROBLEME :** si le regime change (ex: crash), le modele predit mal. L'innovation $(z - \hat{x}_{pred})$ devient ENORME.

**SOLUTION** (Adaptive / Dual Kalman) : si $|\text{innovation}| > 3 \sqrt{P_{pred} + R}$ :
- "Alerte ! Quelque chose a change !"
- On augmente $P$ (= on ne fait plus confiance au modele)
- $K$ monte vers 1 (= on suit les donnees)
- Le filtre s'ADAPTE au nouveau regime

```
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

Setup : $F = 1$ (random walk), $Q = 1$, $R = 4$ (donnees $4\times$ plus bruitees), $x_0 = 10$, $P_0 = 1$

**TICK 1 :** observation $z = 12$

Prediction : $\hat{x}_{pred} = 1 \times 10 = 10$, $P_{pred} = 1^2 \times 1 + 1 = 2$

Correction :

$$\text{Innovation} = 12 - 10 = 2 \qquad K = \frac{2}{2 + 4} = 0.333$$
$$\hat{x}_{new} = 10 + 0.333 \times 2 = 10.67 \qquad P_{new} = (1 - 0.333) \times 2 = 1.333$$

Le filtre dit $10.67$ (pas $12$, car $R$ est grand = donnees bruitees).

**TICK 2 :** observation $z = 13$

Prediction : $\hat{x}_{pred} = 10.67$, $P_{pred} = 1.333 + 1 = 2.333$

Correction :

$$\text{Innovation} = 13 - 10.67 = 2.33 \qquad K = \frac{2.333}{2.333 + 4} = 0.368$$
$$\hat{x}_{new} = 10.67 + 0.368 \times 2.33 = 11.53 \qquad P_{new} = (1 - 0.368) \times 2.333 = 1.474$$

Monte doucement vers les observations.

## Exercice 2 : Impact de R

Meme donnees, TICK 1 $z = 12$, $P_{pred} = 2$ :

| $R$ | $K = \frac{P_{pred}}{P_{pred}+R}$ | $\hat{x}_{new}$ | Comportement |
|---|---|---|---|
| $0.5$ | $0.80$ | $11.6$ | Proche de $z$ |
| $4$ | $0.333$ | $10.67$ | Proche du modele |
| $100$ | $0.02$ | $10.04$ | Ignore l'observation |

**LECON :** $R$ controle "a quel point tu fais confiance aux donnees"
- Petit $R$ = suit les donnees (reactif mais bruite)
- Grand $R$ = suit le modele (lisse mais en retard)
- A toi de trouver le bon $R$ pour ton signal

## Exercice 3 : Detecter un regime change

Ton filtre tourne tranquillement : $\hat{x}_{pred} = 100$, $P_{pred} = 2$, $R = 4$

Soudain : $z = 85$ (crash !)

$$\text{Innovation} = 85 - 100 = -15$$
$$\text{Seuil } 3\sigma = 3 \sqrt{P_{pred} + R} = 3 \times 2.45 = 7.35$$

$|\text{innovation}| = 15 > 7.35$ $\Rightarrow$ **ALERTE REGIME CHANGE !**

Action : inflate $P$ : $P_{pred} = 2 + 150 = 152$

$$K = \frac{152}{152 + 4} = 0.974 \qquad \hat{x}_{new} = 100 + 0.974 \times (-15) = 85.4$$

Le filtre **SAUTE** vers la nouvelle realite au lieu de trainer pendant 20 ticks.

---

# ============================================
# RESUME — Fiche de revision
# ============================================

**KALMAN FILTER :** combine MODELE + DONNEES pour estimer l'etat vrai.

**2 ETAPES** (a chaque tick) :

1. **PREDICTION :**

$$\hat{x}_{pred} = F \cdot x_{prev} + B \cdot u \qquad P_{pred} = F^2 \cdot P_{prev} + Q$$

2. **CORRECTION :**

$$\boxed{K = \frac{P_{pred}}{P_{pred} + R}} \qquad \hat{x}_{new} = \hat{x}_{pred} + K \cdot (z - \hat{x}_{pred}) \qquad P_{new} = (1-K) \cdot P_{pred}$$

**KALMAN GAIN** ($K$) :
- $K \to 1$ = suit les donnees (modele incertain)
- $K \to 0$ = suit le modele (donnees bruitees)

**PARAMETRES CLES :**

| Parametre | Role | Si grand |
|---|---|---|
| $Q$ | Bruit du modele (processus) | $K$ monte, suit les donnees |
| $R$ | Bruit de mesure (observations) | $K$ baisse, suit le modele |
| $F$ | Dynamique du modele | |

**DUAL FILTER** (regime change) : si $|\text{innovation}| > 3\sqrt{P+R}$ $\Rightarrow$ inflate $P$ $\Rightarrow$ $K$ monte $\Rightarrow$ s'adapte vite

**POUR TON TRADING :**
- Signal d'absorption brut $\to$ Kalman $\to$ signal propre
- $R$ = "combien de bruit dans mes donnees d'orderflow ?"
- $Q$ = "a quelle vitesse le vrai signal change ?"
- Petit $R$ = reactif (bon pour signaux rapides)
- Grand $R$ = lisse (bon pour tendances lentes)
- **COMBINE AVEC :** GARCH $\to$ ajuste $Q$ dynamiquement ; HMM $\to$ detecte le regime pour ajuster $R$

**LETTRES ET SYMBOLES :**

| Lettre | Nom | Signification |
|--------|-----|---------------|
| $\hat{x}_{pred}$ | x chapeau pred | L'etat predit AVANT de voir la nouvelle observation |
| $\hat{x}_{new}$ | x chapeau new | L'etat estime APRES avoir vu la nouvelle observation |
| $F$ | F (matrice de transition) | Comment l'etat evolue d'un pas a l'autre (modele de physique) |
| $P_{pred}$ | P pred | Incertitude sur la prediction (avant observation) |
| $P_{new}$ | P new | Incertitude mise a jour (apres observation) |
| $K$ | K (Kalman gain) | Poids donne aux donnees vs au modele (entre 0 et 1) |
| $Q$ | Q (bruit processus) | Combien le vrai etat peut changer entre deux pas |
| $R$ | R (bruit mesure) | Combien les observations sont bruitees / peu fiables |
| $z$ | z | La nouvelle observation (le prix observe) |
| $z - \hat{x}_{pred}$ | Innovation | La surprise : difference entre ce qu'on observait et ce qu'on attendait |
