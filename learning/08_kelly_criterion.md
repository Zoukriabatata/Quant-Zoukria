# 08 — Kelly Criterion & Half-Kelly
# "Combien risquer par trade ?"

> **Video :** [How to Trade with the Kelly Criterion — Roman Paolucci](https://www.youtube.com/watch?v=https://github.com/romanmichaelpaolucci/Quant-Guild-Library/tree/main/2025%20Video%20Lectures/36.%20How%20to%20Trade%20with%20the%20Kelly%20Criterion)
> **Code :** [Quant Guild Library #36](https://github.com/romanmichaelpaolucci/Quant-Guild-Library/tree/main/2025%20Video%20Lectures/36.%20How%20to%20Trade%20with%20the%20Kelly%20Criterion)

---

# ============================================
# APPRENTISSAGE — C'est quoi ? Pourquoi ?
# ============================================

## Le problème du sizing

Tu as un edge. Bonne nouvelle.

Mais COMBIEN tu risques par trade ?

```
Trop peu  → tu gagnes, mais très lentement
Trop fort → un drawdown te détruit avant que l'edge paie

EXEMPLE :
  - Edge : 55% WR, R:R 1:1
  - Risquer 50% du capital par trade
  - Série de 5 losses = -97% (fini)

  - Risquer 5% du capital par trade
  - Série de 5 losses = -23% (tu survives)
```

C'est exactement le problème que Kelly résout : **la fraction OPTIMALE à risquer pour maximiser la croissance à long terme.**

## L'intuition de Kelly

Imagine un pari répété à l'infini :
- Tu gagnes +100% si pile
- Tu perds -100% si face
- Probabilité de gagner : 60%

Si tu mises 100% → une seule défaite te détruit (ruin)
Si tu mises 0% → tu ne gagnes rien
Si tu mises 20% → ça pousse la croissance géométrique au maximum

Kelly trouve ce 20% **mathématiquement**.

## Le lien avec l'ergodicity (module 03)

Kelly et ergodicity parlent du même problème :
- La **moyenne arithmétique** (E[gain]) est trompeuse
- Ce qui compte c'est la **croissance géométrique** (taux composé)
- Kelly maximise exactement la croissance géométrique

```
Sans Kelly : tu optimises E[gain] → RUIN possible
Avec Kelly : tu optimises log(richesse) → croissance stable
```

---

# ============================================
# MODEL — Les maths
# ============================================

## 1. La formule de Kelly (cas discret)

Pour un pari binaire (gagner b:1 ou perdre 1) :

$$f^* = \frac{p \cdot b - (1-p)}{b}$$

- $f^*$ = fraction optimale du capital à risquer
- $p$ = probabilité de gagner
- $b$ = ratio gain/perte (R:R)
- $1-p$ = probabilité de perdre

**Exemple :** WR = 55%, R:R = 2:1 (gagner 2, perdre 1)

$$f^* = \frac{0.55 \times 2 - 0.45}{2} = \frac{1.10 - 0.45}{2} = \frac{0.65}{2} = 0.325$$

Kelly dit : risquer **32.5%** du capital.

## 2. Cas général (Kelly continu)

Pour des rendements continus :

$$f^* = \frac{\mu}{\sigma^2}$$

- $\mu$ = rendement moyen espéré par trade
- $\sigma^2$ = variance des rendements

C'est le ratio de Sharpe au carré, normalisé.

## 3. Overbet = destruction

La croissance géométrique en fonction de $f$ :

$$g(f) = p \cdot \ln(1 + f \cdot b) + (1-p) \cdot \ln(1 - f)$$

| $f$ | Croissance | Commentaire |
|-----|-----------|-------------|
| 0 | 0% | Tu ne joues pas |
| $f^*$ | **maximum** | Kelly optimal |
| $2f^*$ | 0% | tu stagues en moyenne |
| $> 2f^*$ | **négatif** | tu te ruines lentement |

**OVERBET = PIRE que ne pas jouer.**

## 4. Half-Kelly — pourquoi on l'utilise

En pratique, $f^*$ est dangereux pour 2 raisons :
1. **L'estimation de $p$ et $b$ est imprécise** → ton Kelly est biaisé
2. **La variance du portefeuille est trop haute** → psychologiquement insoutenable

**Half-Kelly = $f^* / 2$**

| Indicateur | Full Kelly | Half-Kelly |
|-----------|-----------|-----------|
| Croissance | 100% du max | ~75% du max |
| Volatilité portefeuille | haute | 2× moins haute |
| Drawdown moyen | ~50% | ~25% |
| Risque de ruin | faible | très faible |

75% de la croissance pour 50% des drawdowns : **le deal est rentable.**

## 5. Kelly en trading de futures (contrats)

Adapter Kelly pour les contrats MNQ :

$$\text{Contrats} = \frac{f^* \cdot \text{Capital}}{SL\_pts \times \$2/pt}$$

Avec Half-Kelly :

$$\text{Contrats} = \frac{f^*/2 \cdot \text{Capital}}{SL\_pts \times \$2/pt}$$

**Exemple Apex 50K :**
- Capital = $50,000
- $f^* = 10\%$ (Half-Kelly estimé = 5%)
- SL = 8 pts, $2/pt = $16/contrat

$$\text{Contrats} = \frac{0.05 \times 50000}{8 \times 2} = \frac{2500}{16} = 156 \text{ (limité à 40 par Apex)}$$

## 6. Kelly dynamique par phase (dans le backtest)

Le backtest implémente un Kelly dynamique selon les phases :

| Phase | Condition | Fraction risque | Commentaire |
|-------|-----------|-----------------|-------------|
| PRUDENTE | Capital < $47,000 | 4% | Protéger le compte |
| STANDARD | $47,000 ≤ Capital ≤ $49,000 | 10% | Mode normal |
| SECURITE | Capital > $49,000 | 4% | Protéger le profit target |

```python
PHASE_RISK = {"PRUDENTE": 0.04, "STANDARD": 0.10, "SECURITE": 0.04}
RISK_MIN_DOLLARS = 200
RISK_MAX_DOLLARS = 800
```

Le risque en dollars est clipé entre $200 et $800 par trade.

---

# ============================================
# LECON — Exercices pratiques
# ============================================

## Exercice 1 : Kelly de base

Ton edge sur MNQ :
- WR = 50%, R:R = 2:1 (tu gagnes 2 fois ce que tu risques)
- $b = 2$, $p = 0.50$

$$f^* = \frac{p \cdot b - (1-p)}{b} = \frac{0.50 \times 2 - 0.50}{2} = \frac{0.50}{2} = 0.25$$

Kelly = 25% du capital. Half-Kelly = **12.5%**

## Exercice 2 : Calculer les contrats

Données :
- Capital : $50,000
- Half-Kelly : 5%
- SL : 6 pts (= $12/contrat MNQ)

$$\text{Contrats} = \frac{0.05 \times 50000}{6 \times 2} = \frac{2500}{12} \approx 208$$

Apex limite à 40 contrats PA → **40 contrats** (contrainte binding).

## Exercice 3 : Danger du overbet

Tu penses que ton edge est 60% WR, R:R 1:1.
Kelly = $\frac{0.60 - 0.40}{1} = 20\%$

Mais ton vrai WR est 52% (tu surestimes ton edge).
Vrai Kelly = $\frac{0.52 - 0.48}{1} = 4\%$

Tu misais 5× Kelly → growth négatif → tu perds lentement.

**LECON :** Toujours sous-estimer ton edge. Half-Kelly te protège contre ce biais.

---

# ============================================
# RESUME — Fiche de revision
# ============================================

**KELLY CRITERION** = la fraction optimale du capital à risquer pour maximiser la croissance géométrique.

**FORMULE :**

$$f^* = \frac{p \cdot b - (1-p)}{b} \qquad \text{(discret)}$$

$$f^* = \frac{\mu}{\sigma^2} \qquad \text{(continu)}$$

**HALF-KELLY :** $f = f^*/2$ — 75% de la croissance, 2× moins de drawdown. Toujours utiliser en trading réel.

**CONTRATS MNQ :**

$$\text{Contrats} = \frac{f \cdot \text{Capital}}{SL_{pts} \times \$2}$$

**PHASES (dans le backtest) :**
| Phase | Fraction |
|-------|---------|
| PRUDENTE | 4% |
| STANDARD | 10% |
| SECURITE | 4% |

**LES 3 REGLES :**
1. Surestimer son edge = overbet = ruin lente
2. Half-Kelly suffit (75% du max pour 50% du risque)
3. Apex te limite (40 contrats PA, 60 eval) → la contrainte prime sur Kelly

**LIEN AVEC L'ERGODICITY :** Kelly maximise la même chose que l'ergodicity — la croissance géométrique, pas la moyenne arithmétique.

**LETTRES ET SYMBOLES :**

| Lettre | Nom | Signification |
|--------|-----|---------------|
| $f^*$ | f étoile | Fraction Kelly optimale du capital à risquer |
| $p$ | p | Probabilité de gagner un trade (WR) |
| $b$ | b | Ratio gain/perte (R:R) |
| $g(f)$ | g de f | Croissance géométrique en fonction de la fraction risquée |
| $\mu$ | Mu | Rendement moyen espéré |
| $\sigma^2$ | Sigma carré | Variance des rendements |
