# 02b — Asymptotics (Statistics)
# "Ce qui se passe quand n devient grand"

---

# ============================================
# APPRENTISSAGE — C'est quoi ? Pourquoi ?
# ============================================

## Le probleme

Tu as 50 trades. Ta moyenne est +12 dollars/trade.
Mais est-ce que cette moyenne est FIABLE ?

Avec 500 trades, ta moyenne serait-elle la meme ?
Avec 5000 ? Avec l'infini ?

**L'asymptotique repond a cette question :**
"Que se passe-t-il quand j'ai de plus en plus de donnees ?"

## Pourquoi c'est vital pour le trading

Tout ce que tu calcules sur tes trades (moyenne, sharpe, winrate)
ce sont des ESTIMATIONS basees sur un echantillon limite.

| Taille $n$ | Qualite de l'estimation |
|-----------|------------------------|
| 50 trades | BRUYANTE (peut etre tres fausse) |
| 500 trades | CORRECTE (commence a etre fiable) |
| 5000 trades | PRECISE (tu peux faire confiance) |

L'asymptotique te dit :
1. Est-ce que ton estimateur CONVERGE vers la vraie valeur ?
2. A QUELLE VITESSE il converge ?
3. QUELLE FORME prend l'erreur ?

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

1. **LOI DES GRANDS NOMBRES (LGN)** — "La moyenne converge vers l'esperance" — ton estimation CONVERGE
2. **THEOREME CENTRAL LIMITE (CLT)** — "L'erreur suit une gaussienne" — tu peux QUANTIFIER l'incertitude
3. **METHODE DU DELTA** — "Si $f(X)$ est lisse, $f(\bar{X})$ converge aussi" — tu peux transformer tes estimations

---

# ============================================
# MODEL — Les maths
# ============================================

## 1. Types de convergence

Il y a plusieurs facons de dire "ca converge" en stats.
Du plus faible au plus fort :

**CONVERGENCE EN DISTRIBUTION** (la plus faible)

$$X_n \xrightarrow{d} X$$

"La FORME de la distribution converge."
Exemple : le CLT — la distribution de la moyenne $\to$ gaussienne.

**CONVERGENCE EN PROBABILITE** (plus fort)

$$X_n \xrightarrow{p} X$$

"La VALEUR converge, les gros ecarts deviennent rares."

$$\forall \varepsilon > 0 : \quad P(|X_n - X| > \varepsilon) \to 0 \quad \text{quand } n \to \infty$$

En francais : la proba d'etre "loin" de $X$ tend vers 0.

**CONVERGENCE PRESQUE SURE** (le plus fort)

$$X_n \xrightarrow{p.s.} X$$

$$P(X_n \to X) = 1$$

En francais : avec probabilite 1, les valeurs convergent.

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

Soit $X_1, X_2, \ldots, X_n$ des variables i.i.d. avec $E[X_i] = \mu$.

$$\boxed{\bar{X} = \frac{X_1 + X_2 + \cdots + X_n}{n} \xrightarrow{p} \mu}$$

"La moyenne empirique converge vers la vraie moyenne."

Application au trading :

Tes trades : $X_1, X_2, \ldots, X_n$ (P&L de chaque trade).
Chaque trade a une esperance $E[X_i] = \mu$ (ton edge).

$$\text{Moyenne empirique} = \frac{\sum P\&L}{n}$$

LGN dit : quand $n$ grandit, ta moyenne empirique $\to \mu$

| $n$ | Moyenne observee | Ecart a $\mu = 8$ |
|-----|-----------------|---------------------|
| 10 | +25 | 17 |
| 100 | +11 | 3 |
| 1000 | +8.3 | 0.3 |
| $\infty$ | +8 | 0 |

**Condition importante : i.i.d.** (independant et identiquement distribue)

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

## 3. Vitesse de convergence

La LGN dit "ca converge". Mais A QUELLE VITESSE ?

$$\boxed{\text{Erreur standard} = \frac{\sigma}{\sqrt{n}}}$$

$\sigma$ = ecart-type de tes trades, $n$ = nombre de trades.

| $n$ | Erreur |
|-----|--------|
| 25 | $\sigma / 5$ |
| 100 | $\sigma / 10$ |
| 400 | $\sigma / 20$ |
| 10 000 | $\sigma / 100$ |

Pour DIVISER l'erreur par 2, il faut $4\times$ PLUS de trades.
Pour DIVISER l'erreur par 10, il faut $100\times$ PLUS de trades.

C'est la "racine de $n$" — lente mais sure.

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

$$\boxed{\frac{\sqrt{n}(\bar{X} - \mu)}{\sigma} \xrightarrow{d} \mathcal{N}(0, 1)}$$

En reorganisant :

$$\bar{X} \sim \mathcal{N}\!\left(\mu,\; \frac{\sigma^2}{n}\right) \quad \text{pour } n \text{ grand}$$

Cela permet de construire des **INTERVALLES DE CONFIANCE** :

$$IC_{95\%} = \left[\bar{X} - 1.96\,\frac{\sigma}{\sqrt{n}},\;\; \bar{X} + 1.96\,\frac{\sigma}{\sqrt{n}}\right]$$

## 5. Consistance d'un estimateur

Un estimateur est CONSISTANT s'il converge vers la vraie valeur.

- **CONSISTANT :** Plus tu as de donnees, plus c'est precis. Exemple : la moyenne empirique est consistante pour $\mu$.
- **NON CONSISTANT :** Meme avec l'infini de donnees, ca ne converge pas. Exemple : utiliser le PREMIER trade $X_1$ comme estimateur — il ne change jamais.

Estimateurs courants en trading et leur consistance :

| Estimateur | Consistant ? | Vitesse |
|-----------|-------------|---------|
| Moyenne (edge) | OUI | $1/\sqrt{n}$ |
| Variance | OUI | $1/\sqrt{n}$ |
| Sharpe ratio | OUI | $1/\sqrt{n}$ (biaise pour petit $n$) |
| Win rate | OUI | $1/\sqrt{n}$ |
| Max drawdown | NON (*) | $\log(n)/n$ |
| Ratio gain/perte | OUI | $1/\sqrt{n}$ |

(*) Le max drawdown est BIAISE : plus tu trades longtemps,
plus le max drawdown sera grand.
C'est un estimateur qui ne converge PAS vers une valeur fixe.

## 6. Methode du Delta

Si tu connais le comportement asymptotique de $\bar{X}$,
tu peux en deduire celui de $f(\bar{X})$ pour toute fonction $f$ lisse.

$$\text{Si } \sqrt{n}(\bar{X} - \mu) \xrightarrow{d} \mathcal{N}(0, \sigma^2)$$

$$\boxed{\sqrt{n}\big(f(\bar{X}) - f(\mu)\big) \xrightarrow{d} \mathcal{N}\!\left(0,\; \sigma^2 \cdot [f'(\mu)]^2\right)}$$

En francais : si tu transformes ta moyenne avec une fonction,
la variance est multipliee par $[f'(\mu)]^2$.

**Application : le Sharpe Ratio**

$$\text{Sharpe} = \frac{\bar{X}}{S}$$

C'est une FONCTION de deux estimateurs. La methode du delta dit que :

$$\text{Var}(\text{Sharpe}) \approx \frac{1 + \text{Sharpe}^2/2}{n}$$

Pour $\text{Sharpe} = 1.0$ et $n = 100$ :
- $\text{Var} \approx (1 + 0.5)/100 = 0.015$
- Ecart-type du Sharpe $\approx 0.12$
- $IC_{95\%} = [1.0 - 0.24,\; 1.0 + 0.24] = [0.76,\; 1.24]$

Ton Sharpe de 1.0 pourrait en realite etre entre 0.76 et 1.24.
Avec 400 trades : $IC = [0.88,\; 1.12]$ — plus precis.

## 7. Biais vs Consistance

**BIAIS** = erreur SYSTEMATIQUE (meme direction a chaque fois)

- **Estimateur BIAISE mais CONSISTANT :** Le biais disparait quand $n$ grandit.
  Exemple : variance empirique avec $1/n$ au lieu de $1/(n-1)$ — biais $= -\sigma^2/n \to 0$.

- **Estimateur NON BIAISE mais NON CONSISTANT :** Pas d'erreur systematique mais ne converge pas.
  Exemple : $X_1$ comme estimateur de $\mu$ — $E[X_1] = \mu$ (pas de biais) mais ne s'ameliore jamais.

**POUR LE TRADING :**
Le Sharpe ratio sur petit echantillon est BIAISE vers le haut.
Formule de correction : $\text{Sharpe}_{\text{corrige}} = \text{Sharpe} \times \sqrt{(n-1)/n}$
Mais c'est consistant : avec assez de trades, ca converge.

---

# ============================================
# LECON — Exercices pratiques
# ============================================

## Exercice 1 : Convergence de la moyenne

Tu trades avec un edge reel de $\mu = +5$ et $\sigma = 80$.

Calcule l'erreur standard pour differents $n$ :

| $n$ | $SE = \sigma / \sqrt{n}$ | IC 95% pour la moyenne |
|-----|-------------------------|----------------------|
| 25 | $80/5 = 16$ | $[-27,\; +37]$ |
| 100 | $80/10 = 8$ | $[-11,\; +21]$ |
| 400 | $80/20 = 4$ | $[-3,\; +13]$ |
| 2500 | $80/50 = 1.6$ | $[+1.8,\; +8.2]$ |

## Exercice 2 : Combien de trades pour confirmer un Sharpe ?

Tu mesures un Sharpe de 1.5 sur 50 trades.

$$SE_{\text{Sharpe}} = \sqrt{\frac{1 + \text{Sharpe}^2/2}{n}} = \sqrt{\frac{1 + 1.125}{50}} = \sqrt{\frac{2.125}{50}} = \sqrt{0.0425} = 0.206$$

$IC_{95\%} = [1.5 - 2 \times 0.206,\; 1.5 + 2 \times 0.206] = [1.09,\; 1.91]$

Question : est-ce que ton Sharpe pourrait etre < 0.5 ?
Non, 0.5 est en dehors de l'IC. Bon signe.

Mais avec seulement 20 trades :
- $SE = \sqrt{2.125/20} = 0.326$
- $IC = [0.85,\; 2.15]$
- Le Sharpe reel pourrait etre aussi bas que 0.85. Beaucoup moins impressionnant.

## Exercice 3 : La LGN en action

Tu lances un de 6 faces. $E[X] = 3.5$, $\sigma = \sqrt{35/12} = 1.71$.

| $n$ | IC 95% |
|-----|--------|
| 10 | $[3.5 \pm 2 \times 1.71/\sqrt{10}] = [3.5 \pm 1.08] = [2.42,\; 4.58]$ |
| 100 | $[3.5 \pm 2 \times 1.71/\sqrt{100}] = [3.5 \pm 0.34] = [3.16,\; 3.84]$ |
| 1000 | $[3.5 \pm 2 \times 1.71/\sqrt{1000}] = [3.5 \pm 0.11] = [3.39,\; 3.61]$ |

## Exercice 4 : Biais du max drawdown

Pourquoi le max drawdown est un MAUVAIS estimateur :

| Duree | Max DD |
|-------|--------|
| 100 jours | -500 |
| 200 jours | -700 (probablement pire) |
| 1000 jours | -1200 (encore pire) |

Le max drawdown GRANDIT avec le nombre de trades.
Il ne converge pas vers une valeur fixe.

C'est pour ca qu'il faut normaliser :
$\text{Max DD} / (\sigma \cdot \sqrt{n})$ est un meilleur indicateur.
Ou utiliser des drawdowns MOYENS plutot que le MAX.

## Exercice 5 : Methode du delta pour le win rate

Ton win rate observe = 58% sur 200 trades.

Le win rate est une moyenne de Bernoulli :

$$\sigma = \sqrt{p(1-p)} = \sqrt{0.58 \times 0.42} = 0.494$$

$$SE = \frac{\sigma}{\sqrt{n}} = \frac{0.494}{\sqrt{200}} = 0.035$$

$$IC_{95\%} = [0.58 - 2 \times 0.035,\; 0.58 + 2 \times 0.035] = [0.51,\; 0.65]$$

Ton vrai win rate est probablement entre 51% et 65%.

Si tu veux etre sur que c'est > 50% :
Il faut que 0.50 soit en dehors de l'IC.
$0.50 < 0.51$ — c'est (de justesse) en dehors. Ton winrate > 50% est confirme a ~95%.

Avec 50 trades seulement :
$SE = 0.494/\sqrt{50} = 0.070$, $IC = [0.44,\; 0.72]$.
0.50 est DEDANS — tu ne peux PAS confirmer.

---

# ============================================
# RESUME — Fiche de revision
# ============================================

**ASYMPTOTIQUE** = "que se passe-t-il quand $n \to \infty$ ?"

**3 TYPES DE CONVERGENCE** (du plus faible au plus fort) :

| Type | Notation | Signification |
|------|----------|--------------|
| En distribution | $X_n \xrightarrow{d} X$ | La forme converge (CLT) |
| En probabilite | $X_n \xrightarrow{p} X$ | La valeur converge (LGN) |
| Presque sure | $X_n \xrightarrow{p.s.} X$ | La valeur converge pour de vrai |

**LOI DES GRANDS NOMBRES :** $\bar{X} \to \mu$ quand $n$ grandit.

**VITESSE DE CONVERGENCE :** Erreur $\sim \sigma / \sqrt{n}$. Pour diviser l'erreur par 2 $\to$ $4\times$ plus de donnees.

**CLT :** $\bar{X} \sim \mathcal{N}(\mu, \sigma^2/n)$ — permet de construire des intervalles de confiance.

**CONSISTANCE :** Un estimateur est consistant s'il converge vers la verite.
Moyenne, variance, Sharpe, win rate = consistants. Max drawdown = NON consistant.

**METHODE DU DELTA :** $\text{Var}(f(\bar{X})) \approx [f'(\mu)]^2 \cdot \sigma^2 / n$

**BIAIS vs CONSISTANCE :** On peut etre biaise ET consistant (biais disparait).

**POUR TON TRADING :**
- N'evalue JAMAIS ta strategie sur < 100 trades
- Le Sharpe est biaise vers le haut sur petit echantillon
- Le max drawdown n'est PAS un bon benchmark (grandit avec $n$)
- Win rate de 55% sur 50 trades = probablement du bruit
- Win rate de 55% sur 500 trades = probablement reel
- Toujours calculer l'IC avant de conclure
- i.i.d. rarement vrai en trading $\to$ convergence plus lente
- GARCH et HMM modelisent les violations de i.i.d.
