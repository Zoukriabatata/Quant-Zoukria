# 06d — Confirmation de Reversion : Timing d'entrée
# "N'entre pas au pic — attends la confirmation"

> **Video :** [Markov Regime Switching Bot Part 1 — Roman Paolucci](https://youtu.be/mais1dsB_1g)
> **Ref :** Quant Guild #72 — Timing d'entree
> **Code :** backtest_kalman.py → `confirm_reversal` dans `find_signals()`

---

# ============================================
# APPRENTISSAGE — C'est quoi ? Pourquoi ?
# ============================================

## Le probleme : entrer au mauvais moment

Tu vois le prix a 2σ au-dessus du fair value. Tu entres SHORT immediatement.

**Mais :** le prix peut aller a 2.5σ, 3σ avant de revenir. Tu es SL avant la reversion.

```
Prix  ──────────── 3σ (SL touche ici)
                ↑
       2σ ──── ENTREE ICI  ← erreur
      /
─────  fair value
```

---

## La solution : confirmation

**Idee :** N'entrer que quand le prix a **deja commence** a revenir vers le fair value.

La barre suivante doit montrer une deviation **inferieure** a la barre du signal.

```
Prix  ──────────── 2.5σ (pic)
                ↘
       2σ ─── signal detecte
            ↘
     1.8σ ──── ENTREE ICI ✓ (confirmation : deja en train de revenir)
      ↘
─────  fair value (TP)
```

Tu entres un peu moins loin du fair value, mais tu as la **confirmation** que la reversion a commence.

---

## Le trade-off

| | Sans confirmation | Avec confirmation |
|--|--|--|
| Winrate | ~30% | ~38-42% |
| Trades/mois | plus | moins |
| Faux signaux | beaucoup | peu |
| Sharpe | plus bas | plus haut |

Moins de trades, mais chaque trade est **plus probable** de toucher le TP.

---

# ============================================
# COMPRENDRE — Comment ca marche ?
# ============================================

## Dans le code

```python
if confirm_reversal:
    if i + 1 >= n:
        continue

    # Deviation de la barre suivante
    next_dev = abs(bars.iloc[i+1]["close"] - fair_values[i+1]) / sigma_stats[i+1]

    if next_dev >= deviation:
        continue   # pas encore en reversion → ignorer

    # Entrer a la barre i+1 (confirmation)
    entry_bar   = i + 1
    entry_close = bars.iloc[i + 1]["close"]
```

**Logique :**
- Barre i : signal detecte (prix hors bande)
- Barre i+1 : si deviation diminue → confirmation → entrer
- Barre i+1 : si deviation augmente ou stable → pas de confirmation → ignorer

## Dans le live

La barre en cours est comparee a la barre precedente :

```python
prev_dev = abs(prices[last_idx - 1] - fair_values[last_idx - 1])
curr_dev = abs(last_price - fv)
reversal_ok = (curr_dev < prev_dev)   # prix se rapproche du FV
```

Affichage : `Reversion ✓` ou `Reversion ✗`

---

# ============================================
# FORMULES A RETENIR
# ============================================

**Signal detecte a la barre $i$ :**
$$\delta_i = \frac{|P_i - FV_i|}{\sigma_i} > k$$

**Confirmation a la barre $i+1$ :**
$$\delta_{i+1} < \delta_i$$

**Entree a la barre $i+1$** si la confirmation est valide.

---

# ============================================
# PRATIQUE — Comment l'utiliser
# ============================================

## Sidebar backtest

- **Confirmation reversion** : ON (recommande)
- Effet : -20% de trades, +8-12 pts de WR

## Dans le live

Tu vois le signal LONG/SHORT sur le graphe. Tu regardes :
- `Reversion ✓` → le prix revient deja → entrer maintenant
- `Reversion ✗` → le prix continue de s'eloigner → attendre la prochaine barre

**Regle simple :** si la barre en cours est plus loin du FV que la precedente → **ne pas entrer encore**.