# 00b — Retail vs Institutional Trading
# "Comprendre le jeu AVANT d'y jouer"

> **Video :** [Quant Trader on Retail vs Institutional Trading — Roman Paolucci](https://youtu.be/j1XAcdEHzbU)

---

# ============================================
# APPRENTISSAGE — C'est quoi ? Pourquoi ?
# ============================================

## Pourquoi tu DOIS comprendre ca

Tu es un trader retail. Tu trades le MNQ.
Mais tu joues dans un monde ou des institutions
gerent des MILLIARDS avec des equipes de PhDs.

Si tu ne comprends pas la difference,
tu ne comprends pas CONTRE QUI tu joues.

## Le paysage

```
RETAIL (toi)                    INSTITUTIONAL
-----------                     -------------
1 personne                      Equipes de 50+ quants
Ton capital personnel           Milliards sous gestion
Interactive Brokers             Infrastructure dediee
Tu assumes TOUT le risque       Le risque est diversifie
Discretionnaire + algo          100% systematique

TON AVANTAGE :
  - Pas de bureaucratie
  - Tu peux etre agile (petites positions)
  - Pas de contraintes de taille
  - Tu choisis QUAND trader (pas d'obligation)

TON DESAVANTAGE :
  - Pas d'equipe pour optimiser
  - Pas de pipeline de recherche
  - Information asymetrique (ils en savent plus)
  - Infrastructure limitee
```

---

# ============================================
# MODEL — Le comment du pourquoi
# ============================================

## 1. Le Sell-Side : Market-Making

```
LE BUSINESS :
  Le market-maker quote un BID et un ASK.
  Il ne PREDIT pas la direction.
  Il COLLECTE le spread a chaque transaction.

  BID = 100.00    ASK = 100.20    Mid = 100.10
  Spread = 0.20

  Si quelqu'un achete (lift l'ask) : MM gagne 0.10
  Si quelqu'un vend (hit le bid) : MM gagne 0.10
  Il fait 0.10 a CHAQUE trade.

  Sur 10 000 trades par jour : 10 000 * 0.10 = 1000$/jour

POURQUOI C'EST POSSIBLE :
  Le MM a juste besoin que son MID PRICE soit CORRECT en moyenne.
  C'est exactement ce que font les modeles de time series.

  "Notre modele n'a pas besoin d'etre parfait.
   Il a juste besoin d'etre correct EN MOYENNE."
   --> CLT + LGN (modules 02 et 03b)

LES RISQUES DU MM :
  1. INVENTORY RISK : trop d'achats sans ventes (desequilibre)
  2. ADVERSE SELECTION : quelqu'un qui sait MIEUX que toi
     (un trader informe trade contre ton bid/ask)
  3. VOL EXTREME : pas le temps de hedger
  4. ERREUR TECHNIQUE : Knight Capital a perdu 400M$ en 1 heure
```

## 2. Le Buy-Side : Hedge Funds Quant

```
LE BUSINESS :
  Les hedge funds SPECULATIFS cherchent de l'ALPHA.
  Alpha = rendement qui ne vient pas du marche.

  Ils construisent des SIGNAUX :
  1. Trie les actifs par signal (buckets)
  2. Long les meilleurs, Short les pires
  3. Le spread Long/Short = alpha (si le signal est bon)

STRATEGIES :
  - Signal-based : selection d'actifs, horizon jour/semaine/mois
  - Statistical Arbitrage : mean reversion intraday
  - HFT : microstructure, latence, market-making algo
  - Vol Arbitrage : surface d'implied vol

CE QUI COMPTE :
  - L'ALPHA DECAY : combien de temps le signal reste bon
  - Le CROWDING : si trop de gens utilisent le meme signal
  - La STABILITE : les metriques tiennent-elles en live ?
    (module 04b)
```

## 3. Ce que Roman fait avec son argent

```
"Edge changes based on regimes, timing, administration"

  Roman Paolucci (quant, Columbia) :
  1. Trade discretionnaire QUAND ca lui convient
  2. Active ses algos QUAND les conditions sont bonnes
  3. Laisse son cash en S&P 500 QUAND rien ne marche

  C'est EXACTEMENT ce que ton pipeline fait :
  - Regime OK ? --> trade
  - Regime mauvais ? --> reste en cash
  - Edge degrade ? --> arrete et recalibre

SON YTD 2025 (rebase a 100k) :
  Les 60 premiers jours : drawdown significatif
  Apres jour 60 : belle reprise

  Lecon : MEME les quants pros ont des drawdowns.
  Le Sharpe change selon la fenetre.
  Les metriques sont des VARIABLES ALEATOIRES (module 04b).
```

## 4. Ce que tu dois eviter (PIEGE RETAIL)

```
Roman le dit clairement :

  EVITE :
  - Les plateformes qui "automatisent" pour toi
    --> elles veulent tes abonnements, pas ton edge
  - Les news et "tips"
    --> ils veulent ton attention
  - Les brokers qui rendent le trading "trop facile"
    --> ils veulent tes commissions

  FAIS :
  - Apprends les maths (c'est ce que tu fais la)
  - Prends des decisions quantitatives
  - Comprends ton edge AVANT de risquer ton capital
```

## 5. Portfolio = combinaison lineaire

```
Si tu as 3 strategies :
  D = Discretionnaire : E[R]=25%, sigma=12%
  A = Algo : E[R]=10%, sigma=5%
  M = Marche : E[R]=8%, sigma=15%

  Portefeuille = W_D * D + W_A * A + W_M * M

  Tu peux optimiser les poids (min variance, max Sharpe...)
  MAIS les rendements CHANGENT dans le temps.
  C'est PAS un probleme d'optimisation fixe.

  "Les statistiques ne convergent pas.
   L'optimisation de portefeuille est de l'overfitting."

  --> C'est pour ca que les regimes importent (module 05b)
  --> C'est pour ca que la stabilite > les metriques (module 04b)
```

---

# ============================================
# LECON — Exercices de reflexion
# ============================================

## Exercice 1 : Ou es-tu dans le paysage ?

```
Reponds honnetement :

1. Tu as combien de capital a risquer ? ____$
2. Tu peux perdre combien sans que ca impacte ta vie ? ____$
3. Tu as combien de temps par jour pour trader ? ____h
4. Tu as un edge PROUVE (stabilite confirmee) ? OUI / NON

Si NON au point 4 :
  --> Tu es en mode APPRENTISSAGE (pas en mode profit)
  --> Risque MINIMAL jusqu'a ce que tu prouves ton edge
  --> Module 04b : combien de trades pour confirmer ?
```

## Exercice 2 : Calcul du spread

```
Tu trades le MNQ. Le spread typique = 0.25 points.
1 point MNQ = 2$.

Si un market-maker capture le demi-spread a chaque trade :
  Gain/trade = 0.125 * 2$ = 0.25$
  1000 trades/jour = 250$/jour

TOI en comparaison :
  Tu fais 5 trades/jour
  Tu dois gagner en MOYENNE 50$/trade pour faire 250$/jour

  Est-ce que c'est realiste avec ton edge actuel ?
  Calcule : EV par trade = winrate * avg_win - (1-winrate) * avg_loss
```

## Exercice 3 : Adverse selection et toi

```
Quand tu trades avec ton signal :
  TU es le trader informe (tu vois le signal)
  Le market-maker est le pigeon (il ne voit que le flux)

  C'est l'ADVERSE SELECTION en ta faveur !

  MAIS : quand tu trades SANS signal clair :
  TU es le pigeon
  Les algos HFT sont les traders informes

  Lecon : NE TRADE QUE quand ton pipeline dit GO
  Sinon tu es le pigeon, pas le requin.
```

---

# ============================================
# RESUME — Fiche de revision
# ============================================

```
RETAIL vs INSTITUTIONAL :
  Retail : agile, pas de contraintes, mais seul
  Institutional : puissant, mais bureaucratique

SELL-SIDE (Market-Making) :
  Collecte le spread
  Besoin que le mid-price soit correct EN MOYENNE
  Risques : inventory, adverse selection, tech errors

BUY-SIDE (Hedge Funds) :
  Cherche l'alpha (rendement hors-marche)
  Signaux, long/short, stat arb
  Alpha decay + crowding = l'edge meurt

CE QUE ROMAN FAIT :
  Trade quand les conditions sont bonnes
  Reste en cash sinon
  Les metriques sont des variables aleatoires
  Meme les pros ont des drawdowns

PIEGES RETAIL :
  Plateformes automatiques = overfitting + abonnements
  News = bruit
  Brokers "faciles" = commissions

TON AVANTAGE REEL :
  Tu es AGILE (pas de bureaucratie)
  Tu peux CHOISIR quand trader
  Tu as un edge de MICROSTRUCTURE (Kalman + regime)
  Avec ton pipeline : regime + vol + hawkes + kalman
  --> tu es le trader INFORME, pas le pigeon

POUR TON TRADING :
  1. Comprends que tu joues contre des machines
  2. Ton edge = la ou les machines ne regardent PAS
     (signal = jugement discret + pipeline quantitatif)
  3. NE TRADE QUE quand le pipeline dit GO
  4. Sinon = cash = le meilleur trade c'est pas de trade
  5. Les metriques changent = recalibre regulierement
```
