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

$$r_t = \mu + \varepsilon_t$$

- $\mu$ = rendement moyen (souvent $\approx 0$ en intraday)
- $\varepsilon_t = \sigma_t \cdot z_t$
- $z_t \sim \mathcal{N}(0, 1)$ = bruit standard
- $\sigma_t$ = volatilite qui CHANGE dans le temps -- c'est ca qu'on cherche

## Etape 2 : ARCH(1) — Engle 1982

**ARCH = AutoRegressive Conditional Heteroskedasticity**

$$\sigma_t^2 = \alpha_0 + \alpha_1 \cdot \varepsilon_{t-1}^2$$

- $\alpha_0$ = "plancher" de volatilite (toujours $> 0$)
- $\alpha_1$ = "reaction" aux chocs recents

En francais : la volatilite d'aujourd'hui depend de la **TAILLE** du mouvement d'hier (au carre).

**Exemple numerique :** hier le prix a bouge de $+3\%$ (gros choc), $\varepsilon^2 = (0.03)^2 = 0.0009$

$$\sigma^2_{aujourd'hui} = 0.00001 + 0.25 \times 0.0009 = 0.00001 + 0.000225 = 0.000235 \quad \Rightarrow \quad \sigma = 1.53\%$$

Vs un jour calme ou hier $= +0.5\%$ :

$$\sigma^2 = 0.00001 + 0.25 \times (0.005)^2 = 0.00001 + 0.00000625 = 0.00001625 \quad \Rightarrow \quad \sigma = 0.40\%$$

| Contexte | $\sigma$ |
|---|---|
| Apres un gros choc | $1.53\%$ |
| Apres un jour calme | $0.40\%$ |

La vol s'adapte automatiquement !

## Etape 3 : GARCH(1,1) — Bollerslev 1986

**GARCH ajoute la MEMOIRE :**

$$\sigma_t^2 = \alpha_0 + \alpha_1 \cdot \varepsilon_{t-1}^2 + \beta_1 \cdot \sigma_{t-1}^2$$

- $\alpha_0$ = plancher
- $\alpha_1 \cdot \varepsilon_{t-1}^2$ = reaction au choc d'hier
- $\beta_1 \cdot \sigma_{t-1}^2$ = **MEMOIRE** (la vol d'hier persiste)

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

$$\alpha_1 + \beta_1 < 1 \quad \text{(sinon la vol explose)}$$

| Parametre | Valeur typique | Role |
|---|---|---|
| $\alpha_1$ | 0.05 - 0.15 | Reaction aux chocs |
| $\beta_1$ | 0.80 - 0.95 | Persistance |
| $\alpha_1 + \beta_1$ | 0.90 - 0.99 | Plus c'est proche de 1 = plus la vol persiste |

## Volatilite long terme (inconditionnelle)

$$\sigma_{LT}^2 = \frac{\alpha_0}{1 - \alpha_1 - \beta_1}$$

**Exemple :** $\alpha_0 = 0.00001$, $\alpha_1 = 0.1$, $\beta_1 = 0.85$

$$\sigma_{LT}^2 = \frac{0.00001}{1 - 0.1 - 0.85} = \frac{0.00001}{0.05} = 0.0002 \quad \Rightarrow \quad \sigma_{LT} = 1.41\%/\text{jour} = 22.4\%/\text{an}$$

## Application : Value at Risk (VaR)

VaR = "Quelle est ma perte maximale avec $95\%$ de confiance ?"

**VaR NAIVE** (vol constante) : $VaR = \sigma_{fixe} \times 1.645$ -- utilise la meme vol tout le temps, SOUS-ESTIME le risque en periode de crise.

**VaR GARCH** : $VaR_t = \sigma_{GARCH}(t) \times 1.645$ -- s'adapte au regime de vol actuel, beaucoup plus fiable.

| Methode | Exceedances | Cible |
|---|---|---|
| VaR naive | $40.65\%$ | $5\%$ !!! |
| VaR GARCH | $9.74\%$ | $5\%$ (bien meilleur) |

---

# ============================================
# LECON — Exercices pratiques
# ============================================

## Exercice 1 : GARCH(1,1) a la main

Parametres : $\alpha_0 = 0.00001$, $\alpha_1 = 0.10$, $\beta_1 = 0.85$. Jour 0 : $\sigma^2 = 0.0002$, $\varepsilon = +2\% = 0.02$

**Jour 1 :**

$$\sigma_1^2 = 0.00001 + 0.10 \times (0.02)^2 + 0.85 \times 0.0002 = 0.00001 + 0.00004 + 0.00017 = 0.00022$$
$$\sigma_1 = \sqrt{0.00022} = 1.48\%$$

Jour 1 a un mouvement de $-4\%$ (gros choc).

**Jour 2 :**

$$\sigma_2^2 = 0.00001 + 0.10 \times (0.04)^2 + 0.85 \times 0.00022 = 0.00001 + 0.00016 + 0.000187 = 0.000357$$
$$\sigma_2 = \sqrt{0.000357} = 1.89\%$$

La vol a **MONTE** de $1.48\%$ a $1.89\%$ apres le choc de $-4\%$.

## Exercice 2 : Persistance

Apres le choc, supposons des jours calmes ($\varepsilon = 0$) :

**Jour 3** ($\varepsilon=0$) : $\sigma_3^2 = 0.00001 + 0.10 \times 0 + 0.85 \times 0.000357 = 0.000313$ $\Rightarrow$ $\sigma_3 = 1.77\%$

**Jour 4** ($\varepsilon=0$) : $\sigma_4^2 = 0.00001 + 0 + 0.85 \times 0.000313 = 0.000276$ $\Rightarrow$ $\sigma_4 = 1.66\%$

| Jour | $\sigma$ |
|---|---|
| Jour 2 (choc) | $1.89\%$ |
| Jour 3 | $1.77\%$ |
| Jour 4 | $1.66\%$ |
| Jour 5 | $1.57\%$ |
| Jour 10 | $\sim 1.30\%$ |

La vol DESCEND lentement = **mean reversion**. Il faut $\sim 15$-$20$ jours pour revenir au niveau normal. C'est le **CLUSTERING** capture par $\beta_1$.

## Exercice 3 : Impact sur le sizing

Capital $= 10\,000$, risque max $1\% = 100$ par trade, stop loss $= 10$ points MNQ $= 50$

| Regime | $\sigma_{GARCH}$ | Contrats | Raison |
|---|---|---|---|
| LOW vol | petit | $100/50 = 2$ | Conditions normales |
| HIGH vol | double | $1$ | Stop atteint plus souvent, REDUIRE |

**GARCH te dit QUAND ajuster ta taille.**

---

# ============================================
# RESUME — Fiche de revision
# ============================================

**ARCH :**

$$\sigma_t^2 = \alpha_0 + \alpha_1 \cdot \varepsilon_{t-1}^2$$

La vol depend du choc d'hier.

**GARCH :**

$$\boxed{\sigma_t^2 = \alpha_0 + \alpha_1 \cdot \varepsilon_{t-1}^2 + \beta_1 \cdot \sigma_{t-1}^2}$$

La vol depend du choc d'hier ET de la vol d'hier. Capture le CLUSTERING (la vol persiste).

**PARAMETRES TYPIQUES :**

| Parametre | Valeur | Role |
|---|---|---|
| $\alpha_1$ | $0.05$-$0.15$ | Reaction aux chocs |
| $\beta_1$ | $0.80$-$0.95$ | Persistance |
| $\alpha_1 + \beta_1$ | $< 1$ | Stabilite |

**CAPTURE 3 PHENOMENES :**
1. Clustering : gros mouvements $\to$ gros mouvements
2. Mean reversion : la vol revient toujours a la moyenne
3. Fat tails : plus de valeurs extremes que la normale

**VOL LONG TERME :**

$$\sigma_{LT}^2 = \frac{\alpha_0}{1 - \alpha_1 - \beta_1}$$

**VaR GARCH >> VaR naive :** naive sous-estime massivement le risque ($40\%$ exceedances vs $5\%$ cible), GARCH bien meilleur ($10\%$ exceedances).

**LETTRES ET SYMBOLES :**

| Lettre | Nom | Signification |
|--------|-----|---------------|
| $\sigma_t^2$ | Sigma carre au temps t | Variance (volatilite au carre) aujourd'hui |
| $\sigma_t$ | Sigma t | Volatilite aujourd'hui (racine de la variance) |
| $\varepsilon_{t-1}$ | Epsilon t-1 | Le choc (surprise) d'hier = prix reel - prix prevu |
| $\varepsilon_{t-1}^2$ | Epsilon carre | Le choc d'hier au carre (toujours positif) |
| $\alpha_0$ | Alpha zero | Plancher de volatilite (vol minimale meme quand tout est calme) |
| $\alpha_1$ | Alpha un | Poids du choc recent (reaction aux nouvelles) |
| $\beta_1$ | Beta un | Poids de la vol passee (memoire/persistance) |
| $\sigma_{LT}^2$ | Sigma LT carre | Variance de long terme (ou la vol revient toujours) |

**POUR TON TRADING :**
- GARCH te donne la vol ACTUELLE (pas une moyenne fixe)
- En high vol : REDUIS ta taille de position
- En low vol : tu peux etre plus agressif
- Combine avec HMM : GARCH = "quelle vol ?", HMM = "quel regime ?"
