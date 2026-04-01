# QUANT MATHS — Roadmap d'Apprentissage

## Objectif
Maitriser les outils mathematiques pour le trading systematique.
Chaque module suit la meme structure :

```
APPRENTISSAGE  -->  ce que c'est, pourquoi ca existe
MODEL          -->  les maths, les formules, comment ca marche
LECON          -->  exercices pratiques, code, exemples
RESUME         -->  fiche de revision rapide
```

---

## Ordre d'apprentissage (du plus fondamental au plus avance)

```
NIVEAU 1 — Les fondations
+--------------------------------------------------+
|  01. Time Series Analysis (#44)                   |
|      "Comprendre les donnees"                     |
|      Trend, bruit, saisonnalite, filtrage         |
+--------------------------------------------------+
|  02. Central Limit Theorem (#61)                  |
|      "Pourquoi les stats marchent"                |
|      Moyennes, convergence, loi des grands nbres  |
+--------------------------------------------------+
|  03. Ergodicity (#81)                             |
|      "Pourquoi la plupart des traders perdent"    |
|      Ensemble vs temps, Kelly, survie             |
+--------------------------------------------------+

NIVEAU 2 — Les outils de combat
+--------------------------------------------------+
|  04. GARCH (#47)                                  |
|      "Filtre de volatilite"                       |
|      ARCH, GARCH, clustering, VaR                 |
+--------------------------------------------------+
|  05. Hidden Markov Models (#51)                   |
|      "Regime de marche"                           |
|      Etats latents, Baum-Welch, transitions       |
+--------------------------------------------------+

NIVEAU 3 — Le signal propre
+--------------------------------------------------+
|  06. Kalman Filter (#92)                          |
|      "Filtre de signal"                           |
|      Prediction, correction, Kalman Gain          |
+--------------------------------------------------+

NIVEAU 4 — Live trading
+--------------------------------------------------+
|  07. Pipeline complet                             |
|      GARCH --> HMM --> Kalman --> Signal           |
+--------------------------------------------------+
|  08. Kelly Criterion (#36)                        |
|      "Combien risquer par trade"                  |
|      Half-Kelly, sizing dynamique, phases Apex    |
+--------------------------------------------------+
|  09. Backtesting Pitfalls (#97)                   |
|      "Pourquoi ton backtest ment"                 |
|      Look-ahead, survivorship, overfitting        |
+--------------------------------------------------+
|  09b. Profitable vs Tradable (#77)                |
|       "Pourquoi ca meurt en live"                 |
|       Slippage, regime change, robustesse         |
+--------------------------------------------------+
```

---

## Comment utiliser ce systeme

1. Lis chaque module dans l'ordre
2. Fais les exercices de la section LECON
3. Relis le RESUME avant de passer au suivant
4. Le module 07 connecte tout a ton edge

---

## Temps estime par module

| Module | Difficulte | Temps |
|--------|-----------|-------|
| 01 Time Series | Facile | 1-2h |
| 02 CLT | Facile | 1h |
| 03 Ergodicity | Moyen | 1-2h |
| 04 GARCH | Moyen | 2-3h |
| 05 HMM | Difficile | 3-4h |
| 06 Kalman | Difficile | 3-4h |
| 07 Pipeline | Application | 2-3h |
| 08 Kelly | Moyen | 1-2h |
| 09 Pitfalls | Moyen | 1-2h |
| 09b Live | Moyen | 1-2h |
