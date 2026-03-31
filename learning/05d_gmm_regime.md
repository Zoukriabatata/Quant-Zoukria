# 05d — GMM Sticky Regime : Identification des vrais régimes
# "Remplacer GARCH+percentile par un modele qui apprend les regimes"

> **Video :** [Hidden Markov Models — Roman Paolucci](https://youtu.be/Bru4Mkr601Q)
> **Video :** [Markov Regime Switching Bot Part 1 — Roman Paolucci](https://youtu.be/mais1dsB_1g)
> **Ref :** Quant Guild #51 + #72/74
> **Code :** backtest_kalman.py → `classify_regime_gmm()`

---

# ============================================
# APPRENTISSAGE — C'est quoi ? Pourquoi ?
# ============================================

## Le probleme avec GARCH + percentile

L'ancienne methode :
1. Calcule la volatilite GARCH(1,1)
2. Compare au 33e/67e percentile des 60 dernieres barres
3. Classifie LOW / MED / HIGH

**Probleme :** les seuils changent constamment. Un jour "normal" peut etre classe HIGH juste parce que les 60 dernieres barres etaient calmes. Le modele ne **comprend pas** les regimes — il compare juste des chiffres.

---

## La solution : GMM (Gaussian Mixture Model)

**Idee :** les |returns| ne suivent pas une seule distribution. Ils suivent un **melange** de 3 distributions :

```
Regime LOW  → petits |returns|  → distribution etroite
Regime MED  → |returns| moyens  → distribution moyenne
Regime HIGH → grands |returns|  → distribution large
```

Le GMM **apprend ces 3 distributions directement des donnees**. Pas de seuils arbitraires.

---

## Sticky transitions (memoire)

**Probleme du GMM pur :** il peut osciller rapidement entre regimes (LOW → MED → LOW → MED en quelques barres).

**Solution sticky** (inspiree du HMM — Lec 51) :

> Une fois en regime LOW, on reste en LOW jusqu'a ce qu'on soit hors LOW pendant **N barres consecutives**.

C'est la propriete de **memoire** du Hidden Markov Model — les regimes sont "collants".

```
Sticky window = 5 barres :
  Bar 1: LOW ✓
  Bar 2: MED → force LOW (1 barre hors LOW)
  Bar 3: MED → force LOW (2 barres hors LOW)
  Bar 4: LOW → reset compteur
  Bar 5: MED → force LOW (1 barre hors LOW)
  ...
  Bar 10: 5 barres consecutives MED → quitte LOW
```

---

# ============================================
# COMPRENDRE — Comment ca marche ?
# ============================================

## Dans le code

```python
from sklearn.mixture import GaussianMixture

# Entraine le GMM sur |returns|
X = np.abs(returns).reshape(-1, 1)
gmm = GaussianMixture(n_components=3, covariance_type="full",
                      n_init=5, random_state=42)
gmm.fit(X)

# Labels bruts : 0, 1, 2 (ordre arbitraire)
raw_labels = gmm.predict(X)

# Re-mapper par volatilite croissante : 0=LOW, 1=MED, 2=HIGH
means = gmm.means_.flatten()
order = np.argsort(means)
remap = {order[i]: i for i in range(3)}
regimes = np.array([remap[l] for l in raw_labels])
```

## Sticky

```python
# Reste en LOW jusqu'a sticky_window barres consecutives non-LOW
for i in range(1, n):
    if smoothed[i-1] == 0:        # etais en LOW
        if regimes[i] != 0:
            non_low_streak += 1
            if non_low_streak < sticky_window:
                smoothed[i] = 0   # force LOW
```

---

# ============================================
# FORMULES A RETENIR
# ============================================

**GMM likelihood :**
$$p(x) = \sum_{k=1}^{3} \pi_k \cdot \mathcal{N}(x \mid \mu_k, \sigma_k^2)$$

- $\pi_k$ = poids de chaque composante (probabilite d'etre dans ce regime)
- $\mu_k$ = volatilite moyenne du regime k
- $\sigma_k^2$ = variance du regime k

**Sticky threshold :**
$$\text{quitter LOW} \iff \sum_{t=i-N}^{i} \mathbf{1}[\text{regime}_t \neq \text{LOW}] \geq N$$

---

# ============================================
# PRATIQUE — Comment l'utiliser
# ============================================

## Quand trader ?

- **LOW** → conditions ideales pour le mean reversion → TRADER
- **MED** → signal possible mais moins fiable → EVITER (toggle "LOW uniquement")
- **HIGH** → volatilite trop forte → TOUJOURS SKIP

## Sidebar backtest

- **GMM Sticky Regime** : ON
- **Sticky window** : 5 barres (defaut) — augmente pour etre plus conservatif

## Dans le live

Le signal affiche maintenant le regime : `Regime LOW ✓` ou `Regime MED ✗`
Si MED ou HIGH → signal passe a **ATTENDRE** meme si le prix est hors bande.