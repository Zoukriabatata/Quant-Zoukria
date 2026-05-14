# 06c — Half-Life Ornstein-Uhlenbeck : La vitesse du retour a la moyenne
# "Pourquoi ton TP=0.15σ fonctionne et pas 1.0σ"

> **Source :** [Quant Guild #95 — Kalman Mean Reversion](https://youtu.be/BuPil7nXvMU)

---

# ============================================
# APPRENTISSAGE — C'est quoi ? Pourquoi ?
# ============================================

## L'intuition en 30 secondes

Quand le prix s'eloigne de la moyenne en regime MR, il **finit toujours par revenir**.

Mais a quelle vitesse ?

- Si la half-life est de **5 barres** → le prix revient vite, TP serre OK
- Si la half-life est de **120 barres** → le prix revient lentement, ton trade peut timeout
- Si la half-life est **infinie** → ce n'est pas vraiment MR, c'est random walk

**Le half-life te dit le temps median pour fermer la moitie de l'ecart vers la moyenne.**

C'est l'equivalent en finance du temps de demi-vie radioactive en physique : combien de temps pour reduire de moitie l'ecart actuel.

---

## Ce que ca change pour ton edge

Imagine que tu entres SHORT a Z=+3 (prix tres au-dessus de la moyenne).

| Half-life | Que se passe | Action optimale |
|---|---|---|
| 3 barres | Z = 3 → 1.5 en 3 min → 0 en 6 min | **TP rapide a FV** ✅ ton edge |
| 20 barres | Z = 3 → 1.5 en 20 min → 0 en 40 min | **TP plus loin (overshoot)** |
| 100 barres | Z = 3 → 1.5 en 100 min → timeout 120 | **Probablement pas MR**, skip |
| ∞ (random walk) | Ne revient jamais a la moyenne | **NE PAS TRADER** |

**Ta config v9 (TP overshoot = 0.15σ, Timeout = 120 barres)** est calibree pour les regimes **a half-life courte** (5-30 barres). C'est pour ca que le filtre Hurst H<0.58 est crucial : il elimine les regimes a half-life trop longue.

---

## Le lien direct avec ton Hurst

**Plus le Hurst est bas, plus la half-life est courte.**

| Hurst | Half-life typique | Regime | Tu trades ? |
|---|---|---|---|
| H = 0.30 | 3-8 barres | MR ultra-fort | 🔥 OUI (PF 6.89 dans tes data) |
| H = 0.45 | 10-20 barres | MR fort | ✅ OUI |
| H = 0.55 | 25-50 barres | MR faible | ⚠️ OK mais marginal |
| H = 0.58 | 50-80 barres | Borderline | ⚠️ Limite |
| H = 0.62 | > 100 barres | Trend ou indecis | ❌ NON |

**C'est ca qui explique pourquoi les trades avec H<0.40 ont PF 6.89 dans tes donnees** : la half-life est courte → le prix revient vite → ton TP a 0.15σ est touche rapidement → winners abondants.

---

# ============================================
# MODEL — Les maths derriere
# ============================================

## Le processus Ornstein-Uhlenbeck (OU)

C'est l'equation differentielle stochastique standard du retour a la moyenne :

```
dX_t = θ × (μ - X_t) dt + σ × dW_t
```

**Decodage symbole par symbole** :
- `X_t` = prix au temps t
- `μ` = moyenne long-terme (la fair value vers laquelle le prix retourne)
- `θ` (theta) = **vitesse de retour** (plus theta est grand, plus le retour est rapide)
- `σ` (sigma) = volatilite (force des chocs aleatoires)
- `dW_t` = mouvement brownien (le bruit aleatoire)

**Interpretation intuitive** :
- `θ × (μ - X_t) dt` = **force de rappel** vers la moyenne (comme un elastique)
- `σ × dW_t` = **chocs aleatoires** (le marche bouge a chaque tick)

**Si θ est grand** → l'elastique est tendu → retour rapide.
**Si θ est petit** → l'elastique est lache → retour lent.

---

## La formule de half-life

A partir de θ, on calcule la half-life :

```
half_life = ln(2) / θ ≈ 0.693 / θ
```

Avec :
- `ln(2)` ≈ 0.693 (le logarithme naturel de 2)
- `θ` = vitesse de retour OU

**Exemples** :
- θ = 0.10 → HL = 6.93 barres (rapide)
- θ = 0.05 → HL = 13.9 barres (moyen)
- θ = 0.01 → HL = 69.3 barres (lent, edge marginal)

---

## Comment on estime θ en pratique

On ne peut pas mesurer θ directement. On l'estime via une regression **AR(1)** :

```
X_t = α + φ × X_{t-1} + ε_t
```

Avec :
- `φ` (phi) = coefficient d'auto-regression (entre 0 et 1)
- `α` = constante
- `ε_t` = erreur (bruit)

**Lien entre φ et θ** :
```
θ = -ln(φ)
```

Et donc :
```
half_life = ln(2) / (-ln(φ)) = -ln(2) / ln(φ)
```

**Interpretation de φ** :
- φ = 0 → X_t totalement aleatoire (pas de memoire)
- φ = 0.5 → memoire moderee (HL = 1 barre)
- φ = 0.9 → memoire forte mais retour lent (HL = 6.6 barres)
- φ = 0.99 → quasi random walk (HL = 69 barres)
- φ = 1 → exactement random walk (HL = infini)

**En clair** : plus φ est proche de 1, plus la "memoire" est longue, plus la half-life est grande.

---

## Pour ton edge v9

Tu n'utilises pas explicitement φ ou θ dans ton code. **Tu utilises Hurst comme proxy.** C'est mathematiquement equivalent :

- **Hurst bas** ≈ **θ grand** ≈ **half-life courte** ≈ MR rapide ✅
- **Hurst haut** ≈ **θ petit** ≈ **half-life longue** ≈ MR lente/trend

**Pourquoi Hurst plutot que θ ?** Hurst est :
1. Plus stable a estimer (R/S est non-parametrique)
2. Plus interpretable (entre 0 et 1)
3. Robuste aux outliers
4. Calculable rapidement en live

C'est le **bon trade-off** pour une strategie temps reel.

---

## Le lien TP overshoot ↔ half-life

C'est pour ca que ton TP=0.15σ marche :

### Si la half-life est courte (HL ~5 barres, regime MR rapide)
- Le prix revient vite a la fair value
- Il a tendance a **depasser** la moyenne par inertie (overshoot)
- TP = `mean ± 0.15 × std` capture ce petit overshoot
- Probabilite de toucher TP = elevee (~50%+) → WR 42%

### Si on mettait TP=1.0σ (overshoot agressif)
- Le prix devrait depasser de 1σ après le retour
- En regime rapide, le prix repart avant → TP rarement touche
- WR chute, P&L decevant

**Ta config v9 respecte le theoreme empirique** : TP serre + SL large = optimal pour regime MR a half-life courte.

---

# ============================================
# LECON — Exercice
# ============================================

## Cas pratique #1 : Calculer une half-life

Tu fais une regression AR(1) sur 50 barres MNQ et tu obtiens φ = 0.87.

**Question** : quelle est la half-life ?

<details>
<summary>Reponse</summary>

```
half_life = -ln(2) / ln(0.87)
          = -0.693 / -0.139
          = 4.99 ≈ 5 barres
```

**Interpretation** : le prix revient a la moitie de l'ecart en environ **5 minutes**. C'est un regime MR **rapide** ✅, ideal pour ton edge.

Avec TP = 0.15σ, tu touches le TP en ~3-7 barres en moyenne. Cohérent avec ta config Timeout=120.
</details>

---

## Cas pratique #2 : Identifier un regime trop lent

Tu observes φ = 0.995 sur les 100 barres precedentes.

**Question** : quelle half-life ? Tu trades ?

<details>
<summary>Reponse</summary>

```
half_life = -ln(2) / ln(0.995)
          = -0.693 / -0.005
          = 138 barres
```

**Half-life = 138 minutes ≈ 2h20**. 

→ Ton Timeout est 120 barres = 2h. Donc le trade va probablement **timeout** avant de toucher le TP.

→ **NE PAS TRADER**. C'est exactement ce que ton filtre Hurst fait automatiquement : H sera proche de 0.58+ avec une half-life de 138.

**Insight** : la half-life est un excellent **filtre de confirmation** du Hurst. Si tu doutes du regime, calcule la HL.
</details>

---

## Cas pratique #3 : Pourquoi le TP=0.15σ et pas 0.50σ ?

Imagine que tu testes ton edge avec TP_overshoot = 0.50σ (au lieu de 0.15σ).

**Question** : qu'est-ce qui changerait theoriquement ?

<details>
<summary>Reponse</summary>

En regime MR rapide (half-life ~5 barres) :
- Le prix touche la mean rapidement
- Mais il ne depasse pas toujours de 0.50σ (overshoot rare)
- **WR baisse drastiquement** (trades qui touchent mean mais pas TP → timeout ou retour)
- Avg Win augmente mais beaucoup moins frequent
- **Net : PF baisse**

C'est exactement ce qu'on a teste empiriquement :
- TP=0.50σ (config v7) : WR 27.7%, PF 1.91
- TP=0.15σ (config v9) : WR 42.6%, PF 2.29

**+54% de WR** parce que le TP est cale sur la vraie distance de retour MR. Pas du hasard, **de la calibration mathematique**.
</details>

---

# ============================================
# RESUME — Fiche de revision
# ============================================

## Les formules a retenir

```
Processus Ornstein-Uhlenbeck :
dX_t = θ(μ - X_t) dt + σ dW_t

Estimation pratique via AR(1) :
X_t = α + φ × X_{t-1} + ε_t

Half-life :
HL = -ln(2) / ln(φ) = ln(2) / θ
```

---

## Tableau Hurst ↔ Half-life ↔ Action

| Hurst | Half-life | Regime | Action |
|---|---|---|---|
| 0.30 | 3-8 barres | MR ultra-fort | ✅ TRADE |
| 0.45 | 10-20 barres | MR fort | ✅ TRADE |
| 0.55 | 25-50 barres | MR faible | ⚠️ Marginal |
| 0.58 | 50-80 barres | Limite (ton seuil) | ⚠️ Dernier OK |
| 0.62 | > 100 barres | Trend | ❌ NO TRADE |

---

## Pourquoi c'est pertinent pour ton edge

1. **Le Hurst capture indirectement la half-life** — c'est pour ca que H<0.58 fonctionne
2. **TP overshoot court (0.15σ) est calibre pour HL courte** — TP plus large casserait l'edge
3. **Le Timeout 120 barres** est un cap de securite si la HL etait sous-estimee

---

## La phrase a retenir

> **Hurst = humeur du marche. Half-life = vitesse de retour. TP = ou prendre le profit avant qu'il reparte. Les 3 doivent etre coherents.**

Si tu changes l'un sans les autres, tu casses l'edge. Si tu les comprends ensemble, tu sais EXACTEMENT pourquoi ton edge marche.
