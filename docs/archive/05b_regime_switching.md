# 05b — Markov Regime Switching
# "QUAND trader (version avancee)"

> **Video Part 1 :** [Markov Chain Regime Switching Bot (IBKR) — Roman Paolucci](https://youtu.be/mais1dsB_1g)
> **Video Part 2 :** [Markov Chain Regime Switching Bot Part 2 — Roman Paolucci](https://youtu.be/CkXljL6eI5A)

---

# ============================================
# APPRENTISSAGE — C'est quoi ? Pourquoi ?
# ============================================

## Pourquoi upgrade le HMM ?

Le HMM du module 05 est une bonne base theorique.
Le Regime Switching est la VERSION PRATIQUE :

| | HMM (module 05) | Regime Switching (ce module) |
|---|-----------------|----------------------------|
| Approche | Theorie : Forward/Backward, Baum-Welch | Filtrage bayesien EN TEMPS REEL |
| Calibration | Offline sur donnees historiques | Sur barres IBKR live |
| Temps reel | Non | Oui, coloration du chart par regime |
| Decision | Pas directe | Trading immediate |

## Comment ca marche

**3 ETATS :** LOW vol (vert), MED vol (orange), HIGH vol (rouge)

**CLASSIFICATION :**
1. Calcule la volatilite de chaque barre : $\text{vol} = (\text{high} - \text{low}) / \text{close}$
2. Trie les volatilites historiques en 3 buckets (percentiles 33/67)
3. Chaque bucket = un regime avec sa propre distribution

**FILTRAGE BAYESIEN** (a chaque nouvelle barre) :
1. **PREDICTION :** $P(\text{regime}_t) = A^\top \cdot P(\text{regime}_{t-1})$
2. **LIKELIHOOD :** $P(\text{vol} \mid \text{regime}) = \text{gaussienne}$
3. **POSTERIOR :** $P(\text{regime} \mid \text{vol}) = \text{prediction} \times \text{likelihood}$
4. **NORMALISE :** divise par la somme
5. **REGIME** $= \arg\max(\text{posterior})$

## L'app IBKR (final_product.py)

```
L'app se connecte a IBKR et fait tout en live :

  1. CONNEXION : host:port vers TWS/Gateway
  2. CALIBRATION : demande 300 secondes de barres historiques
     --> estime les 3 distributions + matrice de transition
  3. STREAMING : chaque 5 secondes, nouvelle barre
     --> filtre bayesien --> regime actuel
  4. CHART : OHLC candles avec FOND COLORE par regime
     vert = low vol, orange = med vol, rouge = high vol
  5. RECALIBRATION : bouton pour recalibrer a tout moment
```

---

# ============================================
# MODEL — Les maths
# ============================================

## 1. Volatilite par barre

$$\boxed{\text{vol}(\text{barre}) = \frac{\text{high} - \text{low}}{\text{close}}}$$

C'est le range normalise. Simple, robuste, pas besoin de returns.

## 2. Classification en 3 regimes

Sur un historique de 60 barres de vol :

$$P_{33} = \text{percentile } 33\%, \quad P_{67} = \text{percentile } 67\%$$

| Condition | Regime |
|-----------|--------|
| $\text{vol} < P_{33}$ | LOW |
| $P_{33} < \text{vol} < P_{67}$ | MED |
| $\text{vol} > P_{67}$ | HIGH |

Pour chaque regime : $\mu_r = \text{mean}(\text{vols du regime } r)$, $\sigma_r = \text{std}(\text{vols du regime } r)$.

## 3. Matrice de transition

Compte les transitions observees, normalise chaque ligne (+ lissage Laplace $+0.1$) :

$$A = \begin{pmatrix} 0.93 & 0.06 & 0.01 \\ 0.15 & 0.77 & 0.08 \\ 0.01 & 0.17 & 0.82 \end{pmatrix}$$

Les diagonales sont GRANDES = les regimes persistent.

## 4. Filtrage bayesien en temps reel

A chaque nouvelle barre :

**1. PREDICTION (prior) :**

$$\text{prior} = A^\top \cdot \text{posterior}_{\text{precedent}}$$

**2. LIKELIHOOD :**

$$L(r) = \frac{1}{\sigma_r \sqrt{2\pi}} \exp\!\left(-\frac{(\text{vol} - \mu_r)^2}{2\sigma_r^2}\right)$$

**3. POSTERIOR :**

$$\text{posterior}(r) = \frac{\text{prior}(r) \cdot L(r)}{\sum_{r'} \text{prior}(r') \cdot L(r')}$$

**4. REGIME :**

$$\text{regime} = \arg\max_r \;\text{posterior}(r)$$

Exemple : $\text{posterior} = [0.82,\; 0.15,\; 0.03]$, $\arg\max = 0 \to$ LOW vol $\to$ fond du chart = VERT $\to$ tu peux trader normalement.

## 5. Integration avec ton pipeline

| Regime | Kalman | GARCH / Taille | Action |
|--------|--------|----------------|--------|
| LOW vol | $R$ grand (lisse) | Vol basse = taille normale | TRADE si signal present |
| MED vol | $R$ moyen | Taille reduite | TRADE demi-taille si signal fort |
| HIGH vol | $R$ petit (reactif) | Vol haute = tres petite taille | PAS DE TRADE (sauf exception) |

---

# ============================================
# LECON — Exercices pratiques
# ============================================

## Exercice 1 : Classification

Volatilites de 10 barres : 0.2, 0.3, 0.8, 0.1, 0.5, 0.9, 0.2, 0.4, 0.7, 0.3

Trie : 0.1, 0.2, 0.2, 0.3, 0.3, 0.4, 0.5, 0.7, 0.8, 0.9

$P_{33} = 0.23$, $P_{67} = 0.6$

| Vol | Regime |
|-----|--------|
| 0.2 | LOW |
| 0.3 | MED |
| 0.8 | HIGH |
| 0.1 | LOW |
| 0.5 | MED |
| 0.9 | HIGH |
| 0.2 | LOW |
| 0.4 | MED |
| 0.7 | HIGH |
| 0.3 | MED |

Sequence des regimes : L, M, H, L, M, H, L, M, H, M

## Exercice 2 : Filtrage bayesien

Prior apres prediction : $[0.6,\; 0.3,\; 0.1]$

Nouvelle barre : $\text{vol} = 0.15$ (tres basse)

Likelihood :
- $L(\text{LOW} \mid 0.15) = \mathcal{N}(0.15;\; \mu=0.18,\; \sigma=0.05) = 0.88$
- $L(\text{MED} \mid 0.15) = \mathcal{N}(0.15;\; \mu=0.45,\; \sigma=0.10) = 0.003$
- $L(\text{HIGH} \mid 0.15) = \mathcal{N}(0.15;\; \mu=0.80,\; \sigma=0.15) \approx 0$

Posterior (non normalise) :
$[0.6 \times 0.88,\; 0.3 \times 0.003,\; 0.1 \times 0] = [0.528,\; 0.0009,\; 0]$

Normalise : $[0.998,\; 0.002,\; 0.000]$

Regime = LOW (99.8% de confiance) $\to$ fond VERT, tu peux trader.

---

# ============================================
# RESUME — Fiche de revision
# ============================================

**REGIME SWITCHING** = HMM en TEMPS REEL pour le trading.

**3 ETATS :** LOW vol (vert), MED vol (orange), HIGH vol (rouge).

**CLASSIFICATION :** $\text{vol} = (\text{high} - \text{low}) / \text{close}$, 3 buckets par percentiles (33/67), chaque bucket = $\mathcal{N}(\mu, \sigma)$.

**MATRICE DE TRANSITION :** Compte les changements observes, normalise + lissage Laplace. Diagonales grandes = regimes persistent.

**FILTRAGE BAYESIEN** (chaque barre) :

$$\text{prior} = A^\top \cdot \text{posterior} \quad\longrightarrow\quad \text{likelihood} = \mathcal{N}(\text{vol} \mid \text{regime}) \quad\longrightarrow\quad \text{posterior} \propto \text{prior} \times \text{likelihood} \quad\longrightarrow\quad \text{regime} = \arg\max$$

**APP IBKR :** Connexion live, barres 5s, chart OHLC colore par regime, recalibration a la demande.

**LETTRES ET SYMBOLES :**

| Lettre | Nom | Signification |
|--------|-----|---------------|
| $\mu$ | Mu | Volatilite moyenne d'un regime (ex: LOW vol = 0.18%) |
| $\sigma$ | Sigma | Dispersion de la vol dans un regime (etendue du bucket) |
| $\mathcal{N}(\mu, \sigma)$ | Loi normale | Distribution de la vol dans chaque etat |
| $A$ | Matrice de transition | Probabilite de passer d'un regime a un autre |
| $P(\text{regime})$ | Probabilite du regime | La confiance qu'on est en LOW / MED / HIGH |
| prior | Prior | Estimation du regime AVANT d'observer la nouvelle barre |
| likelihood | Vraisemblance | Proba d'observer cette vol SI on etait dans ce regime |
| posterior | Posterior | Estimation du regime APRES avoir observe la nouvelle barre |
| $\propto$ | Proportionnel | "proportionnel a" — on normalise apres |
| $\arg\max$ | ArgMax | "l'etat qui donne la probabilite la plus grande" |

**POUR TON TRADING :**

| Regime | Action |
|--------|--------|
| LOW | Trade normalement (signal fiable) |
| MED | Demi-taille (prudence) |
| HIGH | No trade (survie d'abord) |
