# 09 — 3 Backtesting Pitfalls
# "Pourquoi ton backtest ment"

> **Video :** [3 Backtesting Pitfalls That Ruin Your Strategy — Roman Paolucci](https://github.com/romanmichaelpaolucci/Quant-Guild-Library/tree/main/2026%20Video%20Lectures/97.%203%20Backtesting%20Pitfalls%20That%20Ruin%20Your%20Strategy)
> **Code :** [Quant Guild Library #97](https://github.com/romanmichaelpaolucci/Quant-Guild-Library/tree/main/2026%20Video%20Lectures/97.%203%20Backtesting%20Pitfalls%20That%20Ruin%20Your%20Strategy)

---

# ============================================
# APPRENTISSAGE — C'est quoi ? Pourquoi ?
# ============================================

## Le problème

Ton backtest dit : **+$8,000 de profit, 58% WR, Sharpe 1.4.**

Tu passes en live. Résultat : **-$1,200** les deux premières semaines.

Qu'est-ce qui s'est passé ?

```
Ton backtest était FAUX.
Pas parce que tu as mal codé.
Parce que tu as fait des erreurs classiques
que TOUT LE MONDE fait.
```

Ces erreurs s'appellent les "backtesting pitfalls" (pièges du backtesting).

## Les 3 pièges principaux

```
PIEGE 1 : Look-ahead bias
           Tu utilises des données du FUTUR pour décider MAINTENANT

PIEGE 2 : Survivorship bias
           Tes données ne montrent que les actifs qui ont "survécu"
           (les losers ont été retirés)

PIEGE 3 : Overfitting
           Ta stratégie est optimisée pour le PASSE
           mais ne généralise pas au FUTUR
```

---

# ============================================
# MODEL — Les maths
# ============================================

## PIEGE 1 : Look-ahead bias

**Definition :** utiliser des informations qui n'étaient pas disponibles au moment de la décision.

**Exemple classique :**

```python
# FAUX — utilise la clôture FINALE de la barre pour décider d'ENTRER
signal = df["close"] > df["close"].rolling(20).mean()
entry  = df["close"][signal]  # FAUX : la clôture n'est connue qu'APRES

# CORRECT — décider sur la barre i, entrer sur la barre i+1
signal = df["close"].shift(1) > df["close"].shift(1).rolling(20).mean()
entry  = df["open"][signal]   # on entre à l'OUVERTURE du bar suivant
```

**Dans le backtest Kalman :**
- Signal calculé sur la barre $i$ (OK)
- Option `confirm_reversal` : entrée à la barre $i+1$ seulement si elle confirme (encore mieux)
- `skip_open_bars = 15` : évite d'utiliser la volatilité d'ouverture qu'on ne pouvait pas anticiper

**Mesure de l'impact :**
Le look-ahead bias peut multiplier le Sharpe par 3 à 10× artificiellement. Un backtest avec look-ahead bias est **inutile**.

## PIEGE 2 : Survivorship bias

**Definition :** tes données ne contiennent que les actifs qui existent encore aujourd'hui. Les actifs qui ont fait faillite ou ont été retirés du marché ont disparu de tes données.

**Impact sur MNQ :**
Pour les futures, le biais de survivorship se manifeste autrement :
- **Roll bias :** chaque contrat expire. Si tu prends le "front month" sans roll correctement, tu as des gaps artificiels
- **Databento** : le CSV utilise le front-month par volume à chaque barre → roll propre

```python
# Dans load_mnq_csv() du backtest :
# Sélectionne le contrat avec le plus grand volume à chaque barre
# → évite le roll bias (pas de gap artificiel à la date de roll)
```

**Pour les stocks :**
- Backtest sur S&P 500 "actuel" → biais car les stocks qui ont chuté sont sortis
- Solution : utiliser les données "point-in-time" (S&P 500 tel qu'il existait à chaque date)

## PIEGE 3 : Overfitting (sur-ajustement)

**Definition :** ta stratégie a trop de paramètres, ajustés pour maximiser la performance **sur les données d'entraînement** mais qui ne généralisent pas.

**Symptôme :**

```
Sur la période d'entraînement : Sharpe 2.1, WR 65%
Sur la période de test :        Sharpe 0.3, WR 48%

Écart → overfitting
```

**Mesure de l'overfitting :**

$$\text{Ratio de généralisation} = \frac{\text{Sharpe}_{out-of-sample}}{\text{Sharpe}_{in-sample}}$$

- Ratio > 0.7 → bon signe (peu d'overfitting)
- Ratio < 0.4 → forte overfitting

**Dans le backtest Kalman :**
Le risque d'overfitting vient de l'optimisation des paramètres :

| Paramètre | Valeur backtestée | Risque |
|-----------|------------------|--------|
| `band_k` | 1.5 σ | Moyen : ajusté sur 2 ans |
| `lookback` | 120 barres | Faible : logique économique claire |
| `noise_scale` | 5.0 | Moyen : empirique |
| `sl_sigma_mult` | 0.75 | Moyen : basé sur R:R cible |
| `session` | 14h30-21h UTC | Faible : heures de marché réelles |

**Règles anti-overfitting :**

1. **Moins de paramètres libres** → plus robuste
2. **Paramètres avec justification économique** → plus robuste (ex: `lookback=120` = 2h car c'est un cycle de marché connu)
3. **Walk-forward** : calibrer sur $T_1$, valider sur $T_2$, jamais toucher $T_2$ avant la fin
4. **Out-of-sample final** : garder 20% des données intouchées jusqu'à la fin

## Méthode walk-forward (anti-overfitting)

$$T = T_{train} + T_{oos}$$

```
DATA : |──────────────────────────|
        Train (80%)    OOS (20%)
        jan2024-oct2025  nov2025-mars2026

Règle : tu optimises band_k, noise_scale sur TRAIN uniquement.
        Tu regardes OOS UNE SEULE FOIS à la fin.
```

Si performance OOS ≈ performance TRAIN → stratégie robuste
Si OOS << TRAIN → overfitting

## Le nombre de "trades libres" (complexité)

Degré de liberté = nombre de paramètres ajustables

$$\text{Paramètres libres} = k \qquad \text{Trades} = N$$

Règle empirique : $N > 50 \times k$ pour des estimations fiables.

Avec 6 paramètres ajustables, il faut **300+ trades** dans le backtest avant de faire confiance aux résultats.

---

# ============================================
# LECON — Exercices pratiques
# ============================================

## Exercice 1 : Identifier le look-ahead

```python
# Lequel est correct ?

# A)
signal_A = (df["close"] > df["close"].rolling(10).mean())
entry_A  = df["close"].where(signal_A)

# B)
signal_B = (df["close"] > df["close"].rolling(10).mean())
entry_B  = df["open"].shift(-1).where(signal_B)
```

**Réponse :** B est correct. On signale sur la clôture, on entre à l'ouverture du bar SUIVANT. A utilise la clôture du même bar pour entrer → look-ahead.

## Exercice 2 : Tester la robustesse

Backtest 1 (jan2024-jan2025) : Sharpe = 1.8
Backtest 2 (jan2025-jan2026) : Sharpe = 0.9

Ratio = 0.9/1.8 = **50%** → limite acceptable (>40%)

Si Backtest 2 donnait Sharpe = 0.2 → ratio 11% → fort overfitting → stratégie à revoir.

## Exercice 3 : Compter les paramètres

Dans le backtest Kalman, combien de paramètres sont LIBRES (optimisés) ?
- `band_k` ✓ libre
- `band_k_max` ✓ libre
- `noise_scale` ✓ libre
- `sl_sigma_mult` ✓ libre
- `tp_ratio` ✓ libre
- `lookback` ✓ libre (mais justifié)

= 6 paramètres libres → besoin de **300+ trades** pour être significatif.

---

# ============================================
# RESUME — Fiche de revision
# ============================================

**LES 3 PIÈGES DU BACKTESTING :**

**1. LOOK-AHEAD BIAS**
Utiliser des données futures pour décider maintenant.
- Detection : le signal utilise `close[i]` pour entrer à `close[i]` (même barre)
- Fix : entrer à `open[i+1]` ou utiliser `shift(1)` sur le signal

**2. SURVIVORSHIP BIAS**
Tes données ne montrent que les "gagnants" (actifs existant encore).
- Pour MNQ : s'assurer que le roll CSV est propre (front-month par volume)
- Databento gère ça automatiquement

**3. OVERFITTING**
Trop de paramètres ajustés → ne généralise pas.
- Mesure : $Sharpe_{OOS} / Sharpe_{IS}$ > 0.7
- Fix : walk-forward, moins de paramètres, justification économique

**RÈGLES PRATIQUES :**

| Règle | Pourquoi |
|-------|---------|
| Signal sur barre $i$, entrée sur barre $i+1$ | Évite look-ahead |
| Walk-forward : OOS 20% intouché | Mesure vraie généralisation |
| $N_{trades} > 50 \times k_{params}$ | Significativité statistique |
| Chaque paramètre doit avoir une raison économique | Évite overfitting |

**DANS TON BACKTEST KALMAN :**
- `confirm_reversal` : évite le look-ahead (attend confirmation i+1)
- `skip_open_bars / skip_close_bars` : évite les données non-représentatives
- 2 ans de données avec ~$N$ trades → vérifier que $N > 300$ pour 6 paramètres
- Comparer performances 2024 vs 2025 → ratio de généralisation

**LETTRES ET SYMBOLES :**

| Terme | Signification |
|-------|---------------|
| OOS | Out-of-sample : données non utilisées pour calibrer |
| IS | In-sample : données utilisées pour calibrer |
| Look-ahead | Utiliser des données futures (interdit) |
| Walk-forward | Calibration glissante sur fenêtres temporelles |
| $k$ params | Nombre de paramètres libres dans la stratégie |
| Roll bias | Gap artificiel dû à l'expiration des contrats futures |
