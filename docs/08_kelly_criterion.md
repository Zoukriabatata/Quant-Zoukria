# 08 — Kelly Criterion : Combien risquer par trade
# "La formule mathematique de la taille optimale"

> **Source :** [Quant Guild #36 — How to Trade with the Kelly Criterion](https://github.com/romanmichaelpaolucci/Quant-Guild-Library/tree/main/2025%20Video%20Lectures/36.%20How%20to%20Trade%20with%20the%20Kelly%20Criterion)

---

# ============================================
# APPRENTISSAGE — C'est quoi ? Pourquoi ?
# ============================================

## L'intuition en 30 secondes

Tu as un edge (PF 2.29, WR 42%). **Combien doit etre la taille de ton pari** ?

- Trop petit → tu gagnes peu (sub-optimal)
- Trop grand → un seul gros mauvais run te ruine (over-leverage)
- **Juste bien** → tu maximises la croissance long-terme

**Le Kelly Criterion** est la formule mathematique qui te dit ce "juste bien".

C'est un theoreme de John Kelly Jr. (1956) prouve par Edward Thorp (le createur du comptage de cartes au blackjack et du premier hedge fund quantitatif).

---

## L'histoire vraie qui prouve que ca marche

Edward Thorp a fait ~$2 milliards de fortune en appliquant Kelly :

1. D'abord au blackjack (1962) — il a transforme Las Vegas
2. Puis a la bourse via Princeton Newport Partners — 28 ans de profits **consecutifs** sans une seule annee negative
3. Sharpe live moyen tres eleve sur certains fonds

Sa cle ? Il n'a JAMAIS pari trop gros, jamais trop petit. Toujours **fractional Kelly**.

---

## La logique simple

### Si tu paris 100% de ton capital
Un seul loser → bust definitif. Probabilite de bust = WR's complement.

### Si tu paris 1% de ton capital
Tu ne busts jamais, mais ta croissance est minuscule. Tu sous-exploites ton edge.

### Si tu paris Kelly
**Tu maximises la croissance long-terme** sans risque de ruine.

**Pour ton edge v9 (WR 42.64%, R/R 4.27)** : le Kelly optimal mathematique est environ **29%**. Tu utilises **12%** = **fractional Kelly (plus prudent)**. Pourquoi ? Voir plus bas.

---

## Pourquoi Kelly = la verite mathematique

Kelly maximise une chose unique : **l'esperance du log de la richesse finale**.

Pourquoi le log ? Parce qu'en trading, ce qui compte n'est pas la moyenne arithmetique des P&L (qui peut etre tiree par 1 jackpot) mais la **moyenne geometrique** (la croissance reelle compose).

**Exemple choc** :
- Trader A : +100% un jour, -50% le lendemain → richesse finale = inchangee (×2 ×0.5 = ×1)
- Trader B : +20% un jour, -10% le lendemain → richesse finale = +8% (×1.2 ×0.9 = ×1.08)

Trader A a une **meilleure moyenne arithmetique** (+25%) que Trader B (+5%). Mais Trader B a une **meilleure moyenne geometrique** (+8%). Kelly t'oblige a optimiser pour Trader B.

---

# ============================================
# MODEL — Les maths derriere
# ============================================

## La formule de base

Pour un pari binaire (win/lose simple), Kelly est :

```
f* = (p × b − q) / b
```

Avec :
- `f*` = fraction du capital a parier (le "Kelly")
- `p` = probabilite de gagner (Win Rate)
- `q` = 1 − p (probabilite de perdre)
- `b` = ratio recompense/risque (Avg Win / Avg Loss)

### Application a ton edge v9

Tes stats : WR = 42.64%, R/R ratio ~4.27

```
p = 0.4264
q = 0.5736
b = 4.27

f* = (0.4264 × 4.27 − 0.5736) / 4.27
f* = (1.8208 − 0.5736) / 4.27
f* = 1.2472 / 4.27
f* = 0.292 = 29.2%
```

**Kelly mathematique pur** = 29.2% du capital par trade.

Mais en pratique, personne ne joue le full Kelly. Pourquoi ?

---

## Pourquoi NE JAMAIS jouer le full Kelly

### Raison 1 — Tes stats sont incertaines
WR = 42.64% est une **estimation** basee sur 3030 trades passes. Le WR reel futur pourrait etre 38% ou 45%. Si tu paries pour 42.64% et que le vrai est 38%, tu over-leverages.

### Raison 2 — Le DD intermediaire est brutal
Meme avec Kelly, sur la trajectoire vers la richesse finale, tu peux passer par des DD de 40-50% intermediaires. Mathematiquement OK long-terme, mais **psychologiquement impossible** a tenir.

### Raison 3 — Pour Apex c'est interdit
Apex a un trailing DD strict ($2k sur $50k). Un DD intermediaire de 30% = bust direct.

---

## Le Fractional Kelly — la vraie solution

La regle pratique adoptee par 99% des quants : **half-Kelly** ou **quarter-Kelly**.

```
f_fractional = f* / 2   (half-Kelly)
ou
f_fractional = f* / 4   (quarter-Kelly)
```

**Avantages** :
- DD intermediaire divise par ~3
- Robustesse aux erreurs d'estimation de p et b
- Croissance long-terme = ~75% du Kelly full (acceptable)

**Pour ton edge v9** :
- Kelly pur = 29.2%
- Half-Kelly = 14.6%
- **Ta valeur = 12%** (entre quarter et half, plus proche de half)

C'est exactement le bon equilibre.

---

## Comment Kelly est implemente dans ton code

### Etape 1 : Calculer le risque par trade en $

```
DD_restant = ApexDdLimit - DD_deja_utilise
            = $2,000 - DD_consomme

risk_$ = max($50, min(KellyRiskPct × DD_restant, DailyLossLimit × 0.40))
       = max($50, min(0.12 × DD_restant, $400))
```

**Decodage** :
- `KellyRiskPct = 0.12` = ton 12% Kelly
- `× DD_restant` = on adapte au DD encore disponible
- `min(..., $400)` = on ne risque jamais plus de 40% du daily limit en un seul trade
- `max($50, ...)` = on garantit au moins $50 minimum (sinon contracts = 0)

### Etape 2 : Convertir le risque en nombre de contrats

```
loss_per_contract = SL_pts × $2/pt
                  = (par exemple) 5 × $2 = $10/contrat

contracts = risk_$ / loss_per_contract
          = $240 / $10 = 24 contrats

contracts = min(MaxContractsEval, contracts)
          = min(12, 24) = 12 contrats
```

---

## Le mecanisme DD-adaptatif

C'est ca qui rend Kelly different d'un fixed sizing :

| Etat du compte | DD utilise | DD restant | risk_$ a 12% | Contracts (SL 5pts) |
|---|---|---|---|---|
| Frais | $0 | $2,000 | $240 | **12** (plafond) |
| Apres 1 loser | $120 | $1,880 | $226 | 12 (plafond) |
| Apres 3 losers | $360 | $1,640 | $197 | **12** (plafond) |
| Apres 5 losers | $600 | $1,400 | $168 | 12 (plafond) |
| Apres 10 losers | $1,200 | $800 | $96 | **9 contrats** ↓ |
| Apres 13 losers | $1,560 | $440 | $53 | **5 contrats** ↓↓ |
| Apres 17 losers | $2,000 | $0 | $50 | **5 contrats min** |

**Plus tu consomes le DD, plus le sizing se reduit AUTOMATIQUEMENT.** C'est ca le "DD-adaptatif" : Kelly pur applique a un compte funded.

---

## Pourquoi 12% et pas 9% ou 15% ?

Tu as teste empiriquement :

| Risk % | DD backtest | P&L 5 ans | Mois bustes | Verdict |
|---|---|---|---|---|
| 9% (v7) | 3.3% | $277k | 2/60 | Bon |
| **12% (v9)** | **2.49%** | **$303k** | **2/60** | **Optimal** |
| 19% (v8 rejete) | 3.2% | $306k | 7/60 | DD acceptable mais 7 mois bustes |

**12% = sweet spot** car :
- Maximise le P&L sans exploser le DD
- 2/60 mois bustes (acceptable)
- Sharpe maximal (4.82)

---

# ============================================
# LECON — Exercice
# ============================================

## Cas pratique #1 : Calculer Kelly pour un nouvel edge

Tu testes une nouvelle strategie qui donne :
- WR = 55%
- Avg Win = $80
- Avg Loss = $60

**Question** : quel est le Kelly mathematique ? Quelle fraction utiliser en pratique ?

<details>
<summary>Reponse</summary>

```
p = 0.55
q = 0.45
b = 80 / 60 = 1.333

f* = (0.55 × 1.333 − 0.45) / 1.333
f* = (0.733 − 0.45) / 1.333
f* = 0.283 / 1.333
f* = 0.213 = 21.3%
```

**Kelly pur** = 21.3% du capital par trade.

**En pratique** : half-Kelly = 10.6% (recommande).
**Ultra-prudent** : quarter-Kelly = 5.3%.

Note : ce nouvel edge a un R/R seulement 1.33 (contre 4.27 pour ton Hurst_MR). Donc meme avec un meilleur WR (55% vs 42%), le Kelly est PLUS BAS (21% vs 29%). **Le R/R compte plus que le WR pour Kelly**.
</details>

---

## Cas pratique #2 : Sizing en cours de challenge

Tu es en plein challenge Apex. Etat actuel :
- Capital initial : $50,000
- Equity actuel : $51,200 (HWM = $51,500 il y a 1 heure)
- DD utilise = $51,500 - $51,200 = $300

**Question** : quel sizing pour le prochain trade (SL = 5pts) ?

<details>
<summary>Reponse</summary>

```
DD_restant = $2,000 - $300 = $1,700
risk_$ = max($50, min(0.12 × $1,700, $400))
       = max($50, min($204, $400))
       = $204

loss_per_contract = 5 × $2 = $10
contracts = $204 / $10 = 20.4 contrats theoriques
contracts = min(12, 20.4) = 12 contrats
```

**Tu prendrais 12 contrats** (plafond Apex). Le risque sur ce trade = 12 × $10 = $120.

Si le trade perd → DD utilise passe a $420 → DD_restant = $1,580 → prochain trade risk_$ = $190 → encore 12 contrats max.
</details>

---

## Cas pratique #3 : Quand reduire le risk %

Tu observes ton edge live et tu vois apres 100 trades reels :
- WR live = 28% (vs 42% backtest)
- PF live = 1.3 (vs 2.29 backtest)

**Question** : faut-il continuer a tradier a 12% Kelly ?

<details>
<summary>Reponse</summary>

**NON.** Tu dois reduire IMMEDIATEMENT le Kelly.

Pourquoi ? Si les stats live divergent de l'estimation, le 12% qui etait optimal pour WR=42% est trop agressif pour WR=28%.

**Recalcul rapide** avec nouvelles stats live :
```
Si WR live = 28% et R/R live = 1.3 :
p = 0.28, q = 0.72, b = 1.3
f* = (0.28 × 1.3 - 0.72) / 1.3 = -0.277 = -27.7%

Kelly negatif → arret de la strategie obligatoire !
```

**Action** : si stats live divergent significativement (Sharpe live < 2 ou WR < 25% sur 100+ trades), **arreter** et investiguer.

C'est pourquoi le monitoring live vs backtest est non-negociable.
</details>

---

# ============================================
# RESUME — Fiche de revision
# ============================================

## La formule a retenir

```
f* = (p × b − q) / b

Avec :
  p = Win Rate
  q = 1 − p (Loss Rate)
  b = Avg Win / Avg Loss (R/R ratio)

f* = Kelly pur (jamais utiliser directement)
f_pratique = f* / 2 ou f* / 4 (fractional Kelly)
```

---

## Pour ton edge v9

| Variable | Valeur |
|---|---|
| Win Rate (p) | 0.4264 |
| Loss Rate (q) | 0.5736 |
| R/R (b) | ~4.27 |
| **Kelly pur (f*)** | **29.2%** |
| **Ton choix v9 (~half Kelly)** | **12%** |

---

## Les regles d'or de Kelly

1. ✅ **Calcule TON Kelly base sur TES stats backtest** (jamais copier celui d'un autre)
2. ✅ **Utilise toujours half-Kelly ou quarter-Kelly** (jamais le full)
3. ✅ **Recalcule chaque trimestre** avec les vraies stats live
4. ✅ **DD-adaptatif obligatoire** sur compte funded (Apex, FTMO, etc.)
5. ❌ **Ne jamais augmenter le Kelly apres une perte** ("revenge sizing")
6. ❌ **Ne jamais jouer Kelly full** meme si tu es sur de ton edge

---

## La phrase a retenir

> **Kelly te dit COMBIEN parier. Hurst te dit QUAND parier. Z-score te dit OU entrer. Leung te dit COMMENT sortir.**

Les 4 ensemble = ton edge complet. Manque 1 → l'edge s'effondre.
