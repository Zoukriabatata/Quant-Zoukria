# 00c — Notation Mathematique
# "Les symboles qu'on voit partout en quant"

---

# ============================================
# POURQUOI APPRENDRE CA ?
# ============================================

Tu vas lire des formules dans tous les modules.
Si tu connais pas les symboles, tu bloques avant meme de comprendre l'idee.

Ce module = dictionnaire de reference. Reviens ici quand tu vois un symbole inconnu.

---

# ============================================
# LES LETTRES GRECQUES
# ============================================

## σ — Sigma (minuscule)
**= ecart-type = dispersion = risque**

```
σ = combien les valeurs s'eloignent de la moyenne
```

- σ petit → les valeurs sont serrees → marche calme
- σ grand → les valeurs sont dispersees → marche volatile

Exemple concret :
```
MNQ bouge en moyenne 5 pts/min  →  σ = 5 pts
```

---

## Σ — Sigma (majuscule)
**= somme = additionner tous les elements**

$$
\Sigma_{i=1}^{n} x_i = x_1 + x_2 + x_3 + ... + x_n
$$

Exemple :
```
Sigma de 5 trades de P&L [+10, -5, +8, +3, -2]
= 10 + (-5) + 8 + 3 + (-2) = 14 pts
```

---

## μ — Mu
**= moyenne = fair value = valeur centrale**

$$
\mu = \frac{1}{n} \Sigma x_i
$$

Dans le Kalman OU :
```
μ = le "vrai prix" vers lequel MNQ revient toujours
  = ce qu'on appelle Fair Value
```

---

## ε — Epsilon
**= erreur = bruit = ce qu'on n'a pas prevu**

```
prix_reel = prix_prevu + ε_t
```

- `ε_t` = la surprise au temps t
- Si `ε_t = 0` → le modele etait parfait (impossible en pratique)
- Plus `ε_t` est grand → plus le marche est impredictible

---

## φ — Phi
**= persistance = memoire du processus**

Dans le Kalman OU :
```
x_t = φ · x_{t-1} + c + ε_t
```

- `φ = 0.95` → le prix "se souvient" a 95% de la barre precedente
- `φ proche de 1` → serie tres persistante (tendance)
- `φ proche de 0` → serie tres mean-reverting (retour rapide)

---

## α, β — Alpha, Beta
**Alpha** = rendement superieur au marche (ton edge)
**Beta** = sensibilite au marche

```
Si ton systeme fait +15% quand le marche fait +10%  →  alpha = +5%
```

En GARCH :
```
α = poids du choc recent sur la volatilite
β = poids de la volatilite passee
```

---

## λ — Lambda
**= taux de decay = vitesse d'oubli**

```
λ grand → on oublie vite le passe (reactivite)
λ petit → on garde longtemps la memoire (stabilite)
```

---

## θ — Theta
**= parametre inconnu a estimer**

Quand tu lis "estimer θ" → on cherche la valeur qui explique le mieux les donnees.

---

# ============================================
# LES NOTATIONS COMMUNES
# ============================================

## ~ (tilde)
**= "suit la distribution"**

```
Z_t ~ N(0, 1)   →   Z au temps t suit une loi normale de moyenne 0, ecart-type 1
ε ~ N(0, σ²)    →   l'erreur suit une normale de variance σ²
```

---

## E[ ] — Esperance
**= moyenne theorique = ce qu'on attend en moyenne**

$$
E[X] = \text{moyenne de X sur un tres grand nombre d'essais}
$$

Exemple trading :
```
E[P&L] = (probabilite win × gain moyen) - (probabilite loss × perte moyenne)
       = (0.468 × 20.5) - (0.532 × 5.9)
       = +9.6 pts par trade  ← ton esperance positive
```

---

## Var[ ] et Cov[ ]
**Var = variance = sigma au carre**
**Cov = covariance = comment deux variables bougent ensemble**

```
Var[X] = σ²
Cov[X, Y] = comment X et Y bougent ensemble
           > 0 → meme direction
           < 0 → directions opposees
           = 0 → independants
```

---

## ∂ — Derivee partielle
**= "comment ca change si je change un seul parametre"**

```
∂f/∂x = combien f change si x change de 1, tout le reste fixe
```

---

## → et ∞
**→ = "tend vers"**
**∞ = infini**

```
n → ∞   →   quand n devient tres grand
x → 0   →   quand x s'approche de zero
```

---

# ============================================
# LES SOMMES — DETAIL
# ============================================

## Somme simple
$$
\Sigma_{i=1}^{n} x_i
$$

Lire : "somme de x_i pour i allant de 1 a n"

Exemple avec n=4 :
```
Sigma x_i = x_1 + x_2 + x_3 + x_4
          = 10 + (-5) + 8 + 3 = 16
```

---

## Somme geometrique
**Chaque terme = terme precedent × meme ratio r**

$$
\Sigma_{k=0}^{n} r^k = 1 + r + r^2 + r^3 + ... + r^n
$$

Exemple avec r=0.9 :
```
1 + 0.9 + 0.81 + 0.729 + ...
```

**Pourquoi c'est important en trading ?**
```
Le GARCH utilise une somme geometrique de chocs passes :
σ²_t = ω + α·ε²_{t-1} + β·σ²_{t-1}

= les chocs recents comptent plus que les anciens
= poids qui decroissent geometriquement
```

Si β = 0.9 :
```
Barre d'hier   → poids 0.9
Barre avant    → poids 0.9² = 0.81
Il y a 3 jours → poids 0.9³ = 0.73
...
```

---

## Produit Π (Pi majuscule)
**= multiplication de tous les elements**

$$
\Pi_{i=1}^{n} x_i = x_1 \times x_2 \times x_3 \times ... \times x_n
$$

---

# ============================================
# RECAP RAPIDE — LE CHEATSHEET
# ============================================

| Symbole | Nom | Signification |
|---|---|---|
| σ | sigma | ecart-type / volatilite |
| Σ | Sigma | somme |
| μ | mu | moyenne / fair value |
| ε | epsilon | erreur / bruit |
| φ | phi | persistance / memoire |
| α | alpha | edge / poids choc GARCH |
| β | beta | sensibilite marche / poids vol GARCH |
| λ | lambda | taux de decay |
| ~ | tilde | "suit la distribution" |
| E[ ] | esperance | moyenne theorique |
| Var[ ] | variance | σ au carre |
| ∂ | del | derivee partielle |
| ∞ | infini | tres grand nombre |
| Z_t | z au temps t | valeur de Z a l'instant t |
| x_t | x indice t | valeur de x a l'instant t |

---

> **A retenir** : quand tu vois un symbole inconnu, reviens ici.
> Le plus important pour ton systeme : **σ (volatilite)**, **μ (fair value)**, **φ (persistance)**, **ε (bruit)**.