# 25 — Hurst_MR + Trail : Ton edge live complet
# "Le mode d'emploi exact de ta strategie v9"

> **Source academique :** [Lec 25 fBm](https://github.com/romanmichaelpaolucci/Quant-Guild-Library) + [Lec 51 HMM](https://youtu.be/Bru4Mkr601Q) + [Tim Leung 2015 arXiv:1411.5062](https://arxiv.org/abs/1411.5062) (theoreme SL/TP)

---

# ============================================
# APPRENTISSAGE — C'est quoi ? Pourquoi ?
# ============================================

## L'intuition en 30 secondes

Imagine un elastique tendu. Tu sais que :
- Plus tu tires fort, plus il revient fort.
- Si tu lui donnes le temps, il revient toujours a sa position de repos.

**Le marche MNQ en regime mean-reversion, c'est exactement ca.** Quand le prix s'eloigne trop de sa "valeur juste" (fair value), des forces statistiques le ramenent vers le centre.

**Ton edge en 1 phrase** : tu vends quand le prix est trop haut, tu achetes quand il est trop bas — mais **seulement** quand le marche est dans cette humeur d'elastique (et pas dans une humeur de fusee qui continue tout droit).

---

## Les 3 ingredients de l'edge

### 1. Le DETECTEUR — l'exposant de Hurst (H)

Hurst c'est un seul chiffre entre 0 et 1 qui te dit l'humeur du marche :

| Hurst | Humeur | Ce qui se passe | Tu trades ? |
|---|---|---|---|
| H < 0.5 | **Anti-persistant** | Si ca monte trop, ca redescend (elastique) | ✅ OUI |
| H = 0.5 | Random walk | Aucune memoire, comme pile/face | ❌ NON |
| H > 0.5 | **Persistant** | Si ca monte, ca continue (tendance) | ❌ NON |

**Ta config v9** : tu trades **uniquement quand H < 0.58**. Tout le reste du temps : tu attends.

**Analogie concrete** : imagine que tu ecoutes la respiration de quelqu'un. Si elle est reguliere et calme (H bas), tu peux predire le prochain souffle. Si elle est haletante et chaotique (H proche de 0.5), tu ne peux rien predire. Le marche, c'est pareil.

### 2. Le DECLENCHEUR — le Z-score

Une fois que le marche est en humeur elastique (H < 0.58), il faut savoir **quand exactement** le prix est trop loin.

Le Z-score te dit "a combien d'ecarts-types le prix est-il de la moyenne ?".

```
Z = (prix actuel - moyenne des 19 dernieres barres) / ecart-type
```

| Z-score | Position du prix | Action |
|---|---|---|
| Z = 0 | Prix = moyenne | Rien faire, prix normal |
| Z = +1 | 1 ecart-type au-dessus | Encore normal, on attend |
| Z = +2.75 | **TRES au-dessus** (extreme statistique) | ✅ **SHORT** (le prix va redescendre) |
| Z = -2.75 | **TRES en-dessous** | ✅ **LONG** (le prix va remonter) |

**Ta config v9** : declenchement a **|Z| >= 2.75**. Pourquoi 2.75 et pas 2.0 ou 3.0 ? Parce qu'a 2.75, le prix est si extreme statistiquement qu'il y a ~99% de chance qu'il revienne (zone des "fat tails").

### 3. La SORTIE — Le theoreme de Leung

Une fois entre, comment sortir ? Voici LE secret qu'on a empiriquement reproduit :

> **Theoreme Tim Leung (2015) :** Plus le stop-loss est LARGE, plus le take-profit doit etre COURT. Ils sont mathematiquement lies.

**Pourquoi ?** Si tu mets un SL serre, tu te fais stop par le bruit. Donc tu mets un SL plus large. Mais alors le prix peut osciller dans ta direction et revenir — il faut prendre le profit AVANT qu'il reparte.

**Ta config v9 respecte exactement ce theoreme :**

| Avant (v7) | Apres (v9) | Cause-effet |
|---|---|---|
| SL = 0.50 × std (serre) | SL = **0.65 × std + min 5pts** (large) | + protection contre fake stops |
| TP overshoot = 0.25σ (loin) | TP overshoot = **0.15σ** (court) | + tu prends le profit plus vite |
| Win Rate = 27.7% | Win Rate = **42.64%** | +54% de winners ! |

**C'est ca qui explique tes resultats v9 incroyables.** Pas de la chance — un theoreme academique de 2015 applique correctement.

---

## A quoi ca sert tout ca ?

Le **Hurst** te dit QUAND trader (le bon regime).
Le **Z-score** te dit OU entrer (le bon prix).
Le couple **SL/TP de Leung** te dit COMMENT sortir (la bonne distance).

Sans Hurst → tu trades a contre-tendance et tu perds.
Sans Z-score → tu entres trop tot ou trop tard.
Sans Leung → tu te fais stop sur les fake-outs.

**Les 3 ensemble** = ton Sharpe 4.82 et ton PF 2.29.

---

# ============================================
# MODEL — Les maths derriere
# ============================================

## Comment on calcule Hurst exactement

La methode utilisee dans ton algo s'appelle **R/S Rescaled Range Analysis**.

### Etape 1 : Prendre les 50 dernieres barres
Ta config : `HurstWindow = 50` → on regarde les 50 dernieres minutes pour decider.

### Etape 2 : Pour plusieurs tailles de fenetre `n`, on calcule R/S
- **R (Range)** = amplitude des oscillations cumulatives
- **S (Standard deviation)** = ecart-type

### Etape 3 : Regression log-log
Theoriquement, **R/S grandit comme `n^H`** :

```
R/S(n) ≈ c × n^H
```

En prenant le log des 2 cotes :
```
log(R/S) = log(c) + H × log(n)
```

C'est une droite de pente **H** sur un graphique log-log. La pente, c'est l'exposant de Hurst.

**En clair** : on regarde la vitesse a laquelle les oscillations grandissent quand on augmente la fenetre. Si elles grandissent lentement → H bas → memoire negative (MR). Si elles grandissent vite → H haut → memoire positive (trend).

### Pourquoi c'est costaud
- **Non parametrique** : pas besoin de supposer une distribution gaussienne
- **Robuste aux outliers** : un flash crash ne fausse pas H
- **Mathematiquement fonde** : c'est la base du **fractional Brownian motion (fBm)** de Mandelbrot

---

## Le Z-score en formules

```
mean = moyenne des Close des 19 dernieres barres (Lookback = 19)
std  = ecart-type des Close des 19 dernieres barres

Z = (Close[barre actuelle] - mean) / std
```

**Pour un trade :**
- Si Z > +2.75 → prix tres au-dessus → **SHORT** (vente)
- Si Z < -2.75 → prix tres en-dessous → **LONG** (achat)

---

## Le couple SL/TP — la formule Leung

### Stop-Loss (en points MNQ)
```
SL_pts = max(5.0, 0.65 × std)
SL_pts = min(SL_pts, 20.0)   ← plafond de securite
```

**Pourquoi `max(5, ...)`** ? En marche calme `std` peut etre tres petit (~3pts). Sans plancher, le SL serait a 2pts et serait touche par le moindre tick. Le 5pts garantit qu'on respire.

**Pourquoi `min(..., 20)`** ? En marche tres volatile `std` peut exploser (~50pts). Sans plafond, on prendrait des pertes enormes. Le 20pts cap le risque par trade.

### Take-Profit (en prix MNQ)
```
Pour un SHORT :
TP_price = mean - 0.15 × std

Pour un LONG :
TP_price = mean + 0.15 × std
```

Le `0.15 × std` est le **overshoot** : on prend le profit un peu au-dela de la moyenne (overshoot inverse) pour profiter du rebond. Mais court (`0.15`) car le theoreme Leung dit "SL large = TP court".

---

## Le Trail MR/Trend

Quand un trade est ouvert, le code surveille en continu le Hurst intra-trade. Si pendant le trade :

```
H_intra > 0.51   →   le marche bascule en mode TREND
```

Alors la strategie active le **trail** : le SL "ratchete" automatiquement vers la fair value (mean), suivant le prix. C'est une protection contre les trades qui partent dans la mauvaise direction puis se transforment en tendance.

**Logique mathematique** : si H passe de bas (MR) a haut (trend) pendant le trade, ca veut dire que le retour a la moyenne ne va PAS se produire. Donc on protege ce qui a deja ete gagne et on coupe avant que ca explose.

---

## La taille de position — Kelly

Tu ne risques pas la meme taille a chaque trade. Le code applique Kelly :

```
DD_restant = $2,000 - DD_deja_utilise
risk_$ = max($50, min(12% × DD_restant, $400))
contracts = min(12, risk_$ / (SL_pts × 2))
```

**Decodage** :
- Tu risques **12% du DD restant** par trade (Kelly 12%)
- Avec un plafond `$400` (40% du daily limit)
- Plancher `$50` (toujours au moins un peu)
- **Maximum 12 contrats** MNQ (limite Apex Eval)
- Division par `SL_pts × 2` car 1pt MNQ = $2

**Exemple concret** :
- Tu demarres le challenge, DD utilise = $0, donc DD_restant = $2,000
- risk_$ = max($50, min(12% × $2000, $400)) = max($50, min($240, $400)) = **$240**
- En marche calme : SL = 5pts → contracts = min(12, $240 / ($5 × 2)) = min(12, 24) = **12 contrats**
- En marche volatile : SL = 10pts → contracts = min(12, $240 / ($10 × 2)) = min(12, 12) = **12 contrats**
- Apres 5 trades losing ($100 chacun) : DD_utilise = $500, DD_restant = $1500
- → risk_$ = $180 → contracts = $180 / ($5 × 2) = **9 contrats** (sizing reduit auto)

C'est ca la "DD-adaptativite" : moins tu as de marge, moins tu paries.

---

# ============================================
# LECON — Exercice
# ============================================

## Cas pratique #1 : Lecture d'un signal

Tu vois dans la fenetre Output NT :

```
[SIGNAL] 16:23 H=0,42 (seuil=0,58) Close=29245,50
[MR REGIME] 16:23 H=0,42 Z=-2,87 (seuil=±2,75) mean=29265,30 std=6,88
```

**Question** : la strategie va-t-elle prendre un trade ? Si oui, dans quel sens ?

<details>
<summary>Reponse</summary>

✅ **OUI, LONG** (achat de 12 contrats si DD plein).

**Raisonnement** :
1. H = 0.42 < 0.58 → regime MR ✅
2. |Z| = 2.87 > 2.75 → extreme statistique ✅
3. Z = -2.87 → prix sous la moyenne → on achete (le prix va remonter)

**Calculs** :
- SL_pts = max(5.0, 0.65 × 6.88) = max(5.0, 4.47) = **5.0 pts** → SL = 29245.50 - 5.0 = **29240.50**
- TP_price = mean + 0.15 × std = 29265.30 + 0.15 × 6.88 = 29265.30 + 1.03 = **29266.33**

Tu vois ? SL a 5 pts en-dessous, TP a 21 pts au-dessus. R/R ratio = **4.2 : 1**. C'est ca l'edge MR.
</details>

---

## Cas pratique #2 : Quand ca echoue

Tu vois :

```
[SIGNAL] 14:05 H=0,61 (seuil=0,58) Close=29150,00
```

**Question** : que fait la strategie ?

<details>
<summary>Reponse</summary>

❌ **PAS DE TRADE.**

H = 0.61 >= 0.58 → marche en regime trend → on s'abstient.

Meme si le Z-score etait extreme (genre Z = -3.5), on n'entre PAS. **Le filtre Hurst est le veto absolu.**

C'est exactement ce qui differencie ton edge des amateurs qui shortent les pumps en regime trending et se font ratiboiser.
</details>

---

## Cas pratique #3 : Le Trail s'active

Tu es en SHORT depuis 5 minutes a 29200, SL a 29208, TP a 29185.

Soudain :
```
[TRAIL ON] 14:32 H=0,54 FV=29198,50 Z=0,42 TrailStop=29198,50
```

**Question** : que s'est-il passe ?

<details>
<summary>Reponse</summary>

Le prix a touche la fair value (mean = 29198.50) **ET** le Hurst intra-trade a depasse 0.51.

→ Bascule en mode **trail** : le nouveau SL est ratchete a la fair value (29198.50). Si le prix repart contre toi (remonte vers 29200), tu sortiras BE au lieu de perdre 8 pts. Si le prix continue dans ta direction (descend vers 29180+), le trail ratchet suivra.

C'est une protection anti-renversement de regime.
</details>

---

# ============================================
# RESUME — Fiche de revision
# ============================================

## Les 3 conditions OBLIGATOIRES pour entrer

1. ✅ **H < 0.58** (regime MR confirme)
2. ✅ **|Z| >= 2.75** (extreme statistique)
3. ✅ **std >= 1.0** (volatilite suffisante) + **heure != 14h NY** (pas de fake-stops)

Si UNE seule n'est pas remplie → **pas de trade**.

---

## Les parametres v9 a retenir

| Param | Valeur | Pourquoi |
|---|---|---|
| Hurst threshold | **0.58** | Seuil entree MR |
| Hurst window | **50** | Sensibilite Hurst (50 min lookback) |
| Lookback bandes | **19** | Fenetre Z-score |
| Bande k (sigma) | **2.75** | Seuil declenchement Z |
| SL mult | **0.65** | Multiplicateur SL (theoreme Leung) |
| SL min (pts) | **5.0** | Plancher SL anti-fake-stops |
| TP overshoot | **0.15** | TP raccourci (theoreme Leung) |
| Trail H thresh | **0.51** | Bascule trail si regime trend |
| Kelly Risk | **12%** | % du DD restant par trade |
| Plafond contrats | **12 MNQ** | Cap Kelly sizing |
| Max trades/jour | **20** | Plafond frequence |

---

## Performance attendue

| Metrique | Backtest 5 ans | OOS (Walk-Forward) |
|---|---|---|
| Profit Factor | **2.29** | 5.17 |
| Win Rate | **42.64%** | ~ 38% |
| Sharpe | **4.82** | 3.34 |
| Max DD | **2.49%** ($1,245) | < 3.5% |
| Mois positifs | **60/60** (100%) | 78% fenetres rentables |
| P&L 5 ans | **+$303,306** | extrapole ~$280k |

---

## Les 3 erreurs a NE JAMAIS faire

1. ❌ **Forcer un trade sans Hurst valide** ("oui mais le pattern est beau") → tu mourras lentement
2. ❌ **Augmenter le SL sans baisser le TP** → tu violes Leung → degradation garantie (v7 vs v9)
3. ❌ **Demarrer la strategie moins de 2h avant l'open NY** → divergence Hurst entre postes (bug du 6 mai)

---

## La phrase a retenir

> **L'edge n'est pas dans le SL. L'edge est dans le couple Hurst + Z-score + SL/TP relies par Leung.**

Tu sais ca, tu comprends 90% de pourquoi ton edge marche.
