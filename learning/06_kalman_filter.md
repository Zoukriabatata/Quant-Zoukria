# 06 — Kalman Filter : Nettoyer le signal du bruit
# "L'algorithme NASA qui aide a estimer la vraie fair value"

> **Source :** [Quant Guild #92 Kalman](https://youtu.be/zVJY_oaVh-0) + [#95 Kalman Mean Reversion](https://youtu.be/BuPil7nXvMU)

---

# ============================================
# APPRENTISSAGE — C'est quoi ? Pourquoi ?
# ============================================

## L'histoire impressionnante

Le **Kalman Filter** a ete invente par Rudolf Kalman en 1960. Premiere application celebre : **la NASA l'a utilise dans Apollo 11** pour guider la fusee jusqu'a la Lune malgre les mesures imparfaites des capteurs.

Le principe : **combiner intelligemment plusieurs sources d'information bruitees** pour obtenir une meilleure estimation que chacune individuellement.

---

## L'intuition en 30 secondes

Imagine que tu veux connaitre la vraie "fair value" du MNQ a chaque instant. Tu as 2 sources :
1. **Le prix observe** (instantane, mais tres bruite par les ticks aleatoires)
2. **Ton estimation precedente + un modele** (lisse, mais peut deriver)

Le Kalman te dit comment **combiner ces 2 sources optimalement** :
- Si le prix observe est tres bruite → fais confiance a ton modele
- Si ton modele est mauvais → fais confiance au prix
- En general : **moyenne ponderee dynamique** des deux

C'est ca, le **gain de Kalman** : un facteur qui ajuste automatiquement la confiance dans chaque source.

---

## Pourquoi c'est pertinent pour ton edge

Ton code n'utilise pas Kalman explicitement. **Mais le concept est partout** :

| Concept Kalman | Equivalent dans ton edge |
|---|---|
| Fair value (etat cache) | `mean = moyenne des 19 dernieres barres` |
| Prix observe | Close[i] courant |
| Bruit d'observation | Slippage, ticks aleatoires |
| Mise a jour optimale | Z-score = (close - mean) / std |

**Ton rolling mean(19) est une version simplifiee de Kalman**. Le vrai Kalman serait :
- Plus precis (s'adapte a la vol)
- Plus complexe a implementer
- Probablement ~5% meilleur en backtest

→ **Le rolling mean est suffisant pour ton timeframe M1.** Mais comprendre Kalman t'aide a comprendre POURQUOI ton mean(19) marche.

---

## L'analogie du GPS

Imagine que tu utilises un GPS dans un canyon avec mauvaise reception :
- Le GPS te donne ta position toutes les 5 secondes (bruite)
- Tu connais ta vitesse approximative (modele)

Sans Kalman :
- Soit tu fais 100% confiance au GPS (zigzag erratique)
- Soit tu fais 100% confiance au modele (derive lente)

Avec Kalman :
- Le filtre combine intelligemment les deux
- Si le GPS est tres bruite → poids modele augmente
- Si le modele divergerait → poids GPS augmente

**Resultat : trajectoire lisse et precise.**

---

# ============================================
# MODEL — Les maths derriere
# ============================================

## Les 2 phases de Kalman

### Phase 1 : Prediction
On predit l'etat (fair value) au temps t a partir de t-1 :

```
x_pred[t] = F × x_est[t-1]            ← prediction de l'etat
P_pred[t] = F × P_est[t-1] × Fᵀ + Q   ← incertitude predite
```

Avec :
- `F` = matrice de transition (comment l'etat evolue naturellement)
- `Q` = bruit du modele (incertitude par pas de temps)
- `P` = covariance (mesure de l'incertitude)

### Phase 2 : Mise a jour (correction)
On corrige la prediction avec l'observation reelle :

```
K[t] = P_pred[t] × Hᵀ / (H × P_pred[t] × Hᵀ + R)   ← gain de Kalman
x_est[t] = x_pred[t] + K[t] × (z[t] - H × x_pred[t])  ← estimation corrigee
P_est[t] = (I - K[t] × H) × P_pred[t]                  ← nouvelle covariance
```

Avec :
- `z[t]` = observation a l'instant t (le prix observe)
- `R` = bruit de mesure (vol des ticks)
- `H` = matrice d'observation
- `K[t]` = **gain de Kalman** (le facteur magique)

---

## Le gain de Kalman expliqué simplement

```
K = P_pred / (P_pred + R)
```

Lecture intuitive :
- Si `R >> P_pred` (mesure tres bruitee) → K → 0 → on ignore l'observation
- Si `R << P_pred` (mesure tres precise) → K → 1 → on prend l'observation telle quelle
- En general : 0 < K < 1, ponderation optimale

C'est **mathematiquement prouve optimal** sous des hypotheses gaussiennes.

---

## Kalman pour Mean Reversion (variante)

Pour le mean reversion specifiquement, on suppose que la fair value suit un processus OU :

```
fair_value[t] = (1-θ) × fair_value[t-1] + θ × price[t]
```

Avec `θ` (theta) = vitesse de retour a la moyenne (lien avec half-life du module 06c).

**C'est exactement** ce que ton `rolling mean(19)` calcule approximativement, mais avec poids egaux au lieu d'exponentiels.

### Equivalence approximative

Pour une window de 19 barres :
- Rolling mean(19) ≈ EWMA avec α ≈ 1/19 = 0.053
- Kalman OU avec θ = 0.05 → equivalent EWMA α ≈ 0.05

**Ta config Lookback = 19 correspond a un Kalman avec θ ≈ 0.05** → adapte aux regimes MR a half-life ~14 barres (cohérent avec ton Hurst threshold).

---

## Pourquoi ne pas implementer Kalman explicite ?

Trade-offs :

| Aspect | Rolling mean(19) | Kalman OU |
|---|---|---|
| Complexite code | 1 ligne | 50+ lignes |
| Performance backtest | Reference | +3-5% (marginal) |
| Robustesse a l'overfitting | Tres robuste | Modere |
| Calcul live | Trivial | ~10× plus lent |
| Sensible au choix de Q, R | Non | Tres sensible |

→ **Le rolling mean(19) est un trade-off optimal pour ton timeframe M1.** Kalman explicite serait pertinent pour un timeframe daily ou intraday > 30min.

---

# ============================================
# LECON — Exercice (court)
# ============================================

## Cas pratique : Quand Kalman vaudrait le coup

Tu testes un nouvel edge sur le **timeframe daily** sur ES futures. Tes signaux dependent fortement de la fair value.

**Question** : utiliser rolling mean ou Kalman ?

<details>
<summary>Reponse</summary>

**Kalman.** Pourquoi ?

- **Timeframe daily** = peu de barres par jour, chaque observation est precieuse
- **Pas de probleme de latence** (1 calcul/jour)
- **Sensibilite aux changements de regime** elevee (Kalman s'adapte mieux)
- **Robustesse** : Kalman gere mieux les outliers (gaps, news)

A l'inverse pour le **M1 MNQ** :
- 1440 barres/jour → rolling mean est suffisant
- Latence calcul critique
- Overfitting plus probable avec Kalman a tuner

**Regle d'or** : Kalman pour timeframes longs, rolling mean pour scalping/intraday rapide.
</details>

---

# ============================================
# RESUME — Fiche de revision
# ============================================

## Ce qu'il faut retenir

| Concept | Definition |
|---|---|
| **Kalman Filter** | Combine optimalement modele + observation |
| **Gain de Kalman (K)** | Ponderation dynamique de la confiance |
| **Bruit modele (Q)** | Incertitude de l'evolution naturelle |
| **Bruit mesure (R)** | Incertitude des observations |
| **Kalman OU** | Variante pour mean reversion |

---

## Pour ton edge

- **Tu utilises rolling mean(19)** = Kalman simplifie
- C'est suffisant pour le M1 (trade-off complexite/perf optimal)
- Si jamais tu changes de timeframe → reconsidererait Kalman

---

## La phrase a retenir

> **Kalman = comment combiner intelligemment plusieurs sources d'info bruitees. Pour ton M1, le rolling mean fait le job a 95% pour 1% de la complexite.**
