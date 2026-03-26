# 04b — Why Trading Metrics are Misleading
# "Mesurer ton edge"

> **Video :** [Why Trading Metrics are Misleading (Unless This is True) — Roman Paolucci](https://youtu.be/xziwmju7x2s)

---

# ============================================
# APPRENTISSAGE — C'est quoi ? Pourquoi ?
# ============================================

## Le probleme

Tu as un Sharpe de 2.5 sur ton backtest.
Tu as un winrate de 65%.
Tu fais +3000 dollars/mois.

EST-CE QUE CA VEUT DIRE QUE TA STRATEGIE MARCHE ?

**NON.** Pas necessairement.

## Les metriques "inutiles" (seules)

```
EXPECTED RETURN :
  "J'ai fait +15% cette annee"
  --> Ca dit ce qui S'EST PASSE, pas ce qui VA se passer
  --> Sur quelle periode ? 1 semaine ? 1 an ?
  --> Resultat completement different selon la fenetre

WIN RATE :
  "J'ai 100% de winrate"
  --> Je peux te donner une strategie a 100% winrate :
      Vends de l'assurance tremblement de terre.
      Tu gagnes 99 fois. La 100eme te ruine.
  --> 40% winrate avec bon ratio gain/perte > 100% winrate

CASH :
  "Je fais 3000$/mois"
  --> Sur un compte de 1M$ c'est 0.3%/mois = TERRIBLE
  --> Sur un compte de 10k$ c'est 30%/mois = INCROYABLE
  --> Sans contexte de capital, ca ne veut rien dire
```

## Les metriques "moins inutiles"

```
SHARPE RATIO :
  Sharpe = E[R - Rf] / sigma(R)
  "Rendement ajuste par le risque"
  --> Un Sharpe de 1 = pour chaque unite de risque, 1 unite de rendement
  --> Sharpe > 2 = tres bon (mais attention au biais)

SORTINO RATIO :
  Sortino = E[R - Rf] / sigma_downside
  "Comme le Sharpe mais ne penalise que les BAISSES"
  --> Meilleur car la volatilite haussiere n'est pas du "risque"

MAX DRAWDOWN :
  MaxDD = max(pic - creux) / pic
  "La pire perte depuis le plus haut"
  --> Rappel module 02b : MaxDD n'est PAS consistant
      (il grandit avec le temps)
```

## Le vrai message de Roman Paolucci

```
"Performance metrics are NECESSARY but NOT SUFFICIENT"

  NECESSAIRE : si tes metriques sont mauvaises, ta strategie est mauvaise
  PAS SUFFISANT : meme si tes metriques sont bonnes, ca ne prouve rien

  CE QUI COMPTE VRAIMENT = STABILITE

  Un Sharpe de 10 en backtest qui tombe a -1 en live = INUTILE
  Un Sharpe de 1.2 en backtest et 1.0 en live = VALUABLE
```

---

# ============================================
# MODEL — Les maths
# ============================================

## 1. Sharpe Ratio

$$\text{Sharpe} = \sqrt{252} \cdot \frac{E[R - R_f]}{\sigma(R)}$$

- $\sqrt{252}$ = annualisation (252 jours de trading)
- $E[R - R_f]$ = rendement moyen en exces du taux sans risque

| Sharpe | Interpretation |
|---|---|
| 0.5 | Faible |
| 1.0 | Acceptable |
| 2.0 | Tres bon |
| 3.0+ | **Suspicieux** (overfitting probable) |

**Biais :** le Sharpe sur petit echantillon est biaise vers le haut. Sur 50 trades, un Sharpe de 2 pourrait etre 1.2 en realite (voir module 02b).

## 2. Sortino Ratio

$$\text{Sortino} = \sqrt{252} \cdot \frac{E[R - R_f]}{\sigma_{downside}}$$

$\sigma_{downside}$ = ecart-type des rendements **NEGATIFS** seulement. Mieux que le Sharpe car la volatilite haussiere n'est pas du "risque".

## 3. Max Drawdown

$$\text{MaxDD} = \max_t \left(\frac{\text{pic}(t) - \text{valeur}(t)}{\text{pic}(t)}\right)$$

| MaxDD | Interpretation |
|---|---|
| 10% | Tres bon controle |
| 25% | Acceptable |
| 50%+ | Dangereux ($+100\%$ pour recuperer) |

**Attention :** le MaxDD est **NON CONSISTANT** — il grandit avec le temps (voir module 02b).

## 4. Le test de stabilite (la cle de tout)

```
METHODE :
  1. Calcule tes metriques sur le BACKTEST (periode 1)
  2. Calcule les MEMES metriques en LIVE (periode 2)
  3. Compare :

  STABLE (bon signe) :
    Backtest Sharpe = 1.5, Live Sharpe = 1.3
    --> Legere degradation mais MEME direction

  INSTABLE (mauvais signe) :
    Backtest Sharpe = 2.5, Live Sharpe = -0.3
    --> Effondrement total = pas de vrai edge

  RAISONS DE DEGRADATION :
  - Exposition a un regime favorable qui a change
  - Alpha qui s'est fait crowder (trop de gens le tradent)
  - Overfitting du backtest sur du bruit
  - Le systeme est dynamique : l'edge peut revenir
```

## 5. Le piege du random walk (du notebook #48)

```
Roman Paolucci montre :
  1000 random walks (EV = 0, aucun edge)
  Prend le MEILLEUR parcours
  --> Return +80%, Sharpe 1.5, Sortino 2.0

  "Wow quel trader incroyable !"

  SAUF QUE : c'est du PUR HASARD.
  Si tu continues le meme parcours dans le futur :
  --> il revient a 0 (mean reversion vers EV=0)

  C'est EXACTEMENT ce qui arrive quand tu backtestes
  1000 strategies et tu gardes la meilleure.
  C'est du SELECTION BIAS, pas de l'alpha.
```

---

# ============================================
# LECON — Exercices pratiques
# ============================================

## Exercice 1 : Calcul du Sharpe

```
Tes 100 derniers trades :
  Rendement moyen = +0.15% par trade
  Ecart-type = 0.8% par trade
  Rf = 0 (ignore)

  Sharpe (par trade) = 0.15 / 0.8 = 0.1875
  Sharpe annualise (si 1 trade/jour) = 0.1875 * sqrt(252) = 2.97

  Ca semble bon ! Mais avec seulement 100 trades :
  SE du Sharpe = sqrt((1 + 2.97^2/2) / 100) = sqrt(5.41/100) = 0.233
  IC 95% = [2.97 - 0.47, 2.97 + 0.47] = [2.50, 3.44]

  Le Sharpe reel est probablement entre 2.5 et 3.4
  C'est encore bon. Mais attends 400 trades pour confirmer.
```

## Exercice 2 : Win rate trompeur

```
Strategie A : 95% winrate
  Gain moyen quand win = +20$
  Perte moyenne quand loss = -500$

  EV = 0.95 * 20 + 0.05 * (-500) = 19 - 25 = -6$ par trade
  --> PERDANTE malgre 95% winrate !

Strategie B : 40% winrate
  Gain moyen quand win = +300$
  Perte moyenne quand loss = -80$

  EV = 0.40 * 300 + 0.60 * (-80) = 120 - 48 = +72$ par trade
  --> GAGNANTE malgre 40% winrate !

LECON : winrate seul = inutile. C'est EV qui compte.
```

## Exercice 3 : Test de stabilite

```
Tes metriques sur 3 periodes :

  Periode 1 (backtest) : Sharpe=1.8, MaxDD=8%
  Periode 2 (paper)    : Sharpe=1.4, MaxDD=12%
  Periode 3 (live)     : Sharpe=1.2, MaxDD=15%

  Analyse :
  - Degradation legere mais CONSTANTE
  - Le Sharpe reste > 1 en live
  - Le MaxDD augmente mais reste gerable
  --> STABLE : tu as probablement un vrai edge

  Compare avec :
  Periode 1 (backtest) : Sharpe=3.5, MaxDD=3%
  Periode 2 (paper)    : Sharpe=0.8, MaxDD=25%
  Periode 3 (live)     : Sharpe=-0.5, MaxDD=40%

  --> INSTABLE : effondrement = pas de vrai edge
      Probablement du overfitting ou du regime fitting
```

---

# ============================================
# RESUME — Fiche de revision
# ============================================

```
METRIQUES INUTILES (seules) :
  Expected Return : backward-looking, depend de la fenetre
  Win Rate : 100% winrate peut etre perdant
  Cash : sans contexte de capital = vide de sens

METRIQUES MOINS INUTILES :
  Sharpe = E[R-Rf] / sigma (risk-adjusted)
  Sortino = E[R-Rf] / sigma_downside (meilleur)
  MaxDD = pire perte pic-a-creux (non consistant)

TOUTES SONT : NECESSAIRES mais PAS SUFFISANTES

CE QUI COMPTE VRAIMENT = STABILITE
  Backtest Sharpe ~ Live Sharpe --> vrai edge
  Backtest Sharpe >> Live Sharpe --> pas d'edge (overfitting)

PIEGES :
  - Selectionner le meilleur backtest parmi 1000 = selection bias
  - Sharpe > 3 = suspicieux (overfitting probable)
  - MaxDD grandit avec le temps (non consistant)
  - Win rate sans ratio gain/perte = inutile

POUR TON TRADING :
  1. Calcule Sharpe, Sortino, MaxDD sur tes periodes
  2. Compare backtest vs paper vs live
  3. Si les metriques sont STABLES --> edge probable
  4. Si elles s'effondrent en live --> pas d'edge reel
  5. Recalcule regulierement (les edges meurent et reviennent)
  6. Un Sharpe modeste mais stable > Sharpe enorme instable
```
