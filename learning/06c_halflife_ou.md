# 06c — Demi-vie OU : Filtre de vitesse de reversion
# "Filtrer les signaux trop lents avant d'entrer"

> **Video :** [Trading Mean Reversion with Kalman Filters — Roman Paolucci](https://youtu.be/BuPil7nXvMU)
> **Ref :** Quant Guild #92/#95 — Kalman Filter + Mean Reversion
> **Code :** backtest_kalman.py → `half_lives` dans `kalman_ou_filter()`

---

# ============================================
# APPRENTISSAGE — C'est quoi ? Pourquoi ?
# ============================================

## Le probleme

Tu trouves un signal : le prix est 2σ au-dessus du fair value. Tu entres SHORT.

Mais... il met **3 jours** a revenir. La session se ferme. Tu es sorti en loss.

Le signal etait juste. Le **timing** etait mauvais.

**La demi-vie OU te dit : combien de temps va prendre la reversion.**

---

## Le modele OU (Ornstein-Uhlenbeck)

Le Kalman calibre un AR(1) sur chaque fenetre de barres :

$$X_t = \phi \cdot X_{t-1} + c + \varepsilon_t$$

- $\phi$ = persistance (entre 0.5 et 0.999)
- Plus $\phi$ est proche de **1** → prix revient **lentement**
- Plus $\phi$ est proche de **0.5** → prix revient **vite**

---

## La formule demi-vie

$$\text{half-life} = \frac{-\ln(2)}{\ln(\phi)}$$

**En barres 1m :**

| $\phi$ | Demi-vie | Interpretation |
|--------|----------|----------------|
| 0.99   | ~69 barres | ~1h10 — trop lent |
| 0.95   | ~14 barres | ~14 min — bon |
| 0.90   | ~7 barres  | ~7 min — excellent |
| 0.70   | ~2 barres  | trop rapide (bruit) |

**Regle pratique :** session = 420 barres. Si half-life > 60 barres → probabilite faible de revenir avant la cloture.

---

## Pourquoi ce filtre ameliore le Sharpe

Sans filtre : tu prends tous les signaux, meme ceux qui mettent 2h a revenir.
Resultat : beaucoup de timeouts au close → loss systematiques.

Avec filtre half-life < 60 barres :
- Tu gardes les setups ou la reversion est **rapide et probable**
- Moins de trades, mais WR plus haut
- Sharpe ameliore car moins de losses par timeout

---

# ============================================
# COMPRENDRE — Comment ca marche ?
# ============================================

## Dans le code

```python
# Dans kalman_ou_filter() — calcul du phi et demi-vie
phi = np.clip((m * sxy - sx * sy) / denom, 0.5, 0.999)
hl = -np.log(2) / np.log(phi)   # demi-vie en barres
```

```python
# Dans find_signals() — filtre
if max_half_life is not None and half_lives is not None:
    hl = half_lives[i]
    if np.isnan(hl) or hl > max_half_life:
        continue   # signal ignore — reversion trop lente
```

## Dans le live

Le live affiche maintenant :
- `Demi-vie 23b ✓` → reversion rapide, signal valide
- `Demi-vie 85b ✗` → trop lent, signal ATTENDRE

---

# ============================================
# FORMULES A RETENIR
# ============================================

$$\text{half-life} = \frac{-\ln(2)}{\ln(\phi)} \quad \text{(barres)}$$

$$\phi \approx 0.95 \Rightarrow \text{half-life} \approx 14 \text{ barres (14 min en 1m)}$$

**Regle :** N'entre que si `half-life < session_duration / 7`

---

# ============================================
# PRATIQUE — Comment l'utiliser
# ============================================

## Sidebar backtest

- **Filtre demi-vie OU** : ON
- **Demi-vie max (barres)** : 60 par defaut
  - Baisse a 30 pour etre plus selectif (moins de trades, WR plus haut)
  - Monte a 90 pour plus de trades (WR plus faible)

## Intuition

Avant d'entrer un trade, pose-toi la question :
> "A quelle vitesse ce marche revient-il normalement a sa valeur ?"

Si la reponse est "lentement" (phi proche de 1) → passe.
Si la reponse est "vite" (phi < 0.95) → signal potentiellement valide.