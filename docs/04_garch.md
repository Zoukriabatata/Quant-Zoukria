# 04 — GARCH : Le clustering de volatilite
# "Pourquoi la volatilite a de la memoire"

> **Source :** [Quant Guild #47 — ARCH & GARCH](https://youtu.be/iImtlBRcczA)

---

# ============================================
# APPRENTISSAGE — C'est quoi ? Pourquoi ?
# ============================================

## L'intuition en 30 secondes

Regarde MNQ sur un mois quelconque. Tu vas remarquer :

- **Periodes calmes** : 3-5 jours de range etroit, ATR faible, peu de mouvement
- **Periodes volatiles** : 2-3 jours d'oscillations enormes, ATR triple, gros range

Et surtout : **les jours calmes sont voisins** des jours calmes, **les jours volatiles** sont voisins des jours volatils. Ce n'est pas aleatoire.

**GARCH (Generalized Auto-Regressive Conditional Heteroskedasticity)** est le modele mathematique qui formalise ce phenomene appele **volatility clustering**.

---

## Pourquoi c'est pertinent pour TOI

Tu n'utilises pas explicitement GARCH dans ton code. **Mais GARCH explique pourquoi** :

1. Ton edge ne marche pas en marche tres calme (std < 1.0 dans tes data → PF 1.13 mediocre)
2. Ton edge brille en marche moderement volatile (std 4-8 → PF 2.20)
3. Ton edge est variable en marche tres volatile (std > 20 → PF 3.86 mais peu de trades)

**Le clustering de vol** signifie que tu peux **anticiper le regime de volatilite** de la prochaine heure en regardant l'heure precedente. C'est ca qu'utilise ton **filtre std > 1.0**.

---

## L'analogie de la meteo

Pense a la meteo :
- Si aujourd'hui c'est tempête, demain a 80% chance d'etre encore tempête
- Si aujourd'hui c'est calme, demain a 80% chance d'etre encore calme
- Mais les transitions calme→tempête prennent quelques heures, pas instantanees

**Le marche est pareil pour la volatilite**. GARCH modelise ces persistances et transitions.

---

# ============================================
# MODEL — Les maths derriere (simplifie)
# ============================================

## L'equation GARCH(1,1)

C'est le modele GARCH le plus utilise en pratique :

```
σ²_t = ω + α × ε²_{t-1} + β × σ²_{t-1}
```

**Decodage** :
- `σ²_t` = variance (volatilite au carre) au temps t — ce qu'on veut predire
- `ω` (omega) = constante de base (vol minimum a long terme)
- `α` (alpha) = poids du dernier choc carre (~10%)
- `ε²_{t-1}` = carre du rendement precedent (le "choc" de la barre passee)
- `β` (beta) = poids de la vol passee (~85%)
- `σ²_{t-1}` = vol au carre de la barre precedente

**Lecture humaine** :
> "La vol d'aujourd'hui = un peu de bruit constant + un peu du choc d'hier + beaucoup de la vol d'hier."

C'est pour ca que la vol **persiste** : 85% de la vol d'aujourd'hui vient de hier.

---

## Pourquoi ton std × Lookback suffit

Tu n'as PAS besoin d'implementer GARCH explicite. Ton code calcule **std sur 19 dernieres barres** (Lookback). Cet std est en fait une **moyenne mobile de volatilite** — l'equivalent simplifie de GARCH.

Mathématiquement :
- GARCH(1,1) → estimation exponentielle pondérée
- Rolling std → estimation uniforme sur fenêtre
- Les deux convergent en pratique sur des fenetres > 15 barres

**Ton std(19 barres) capture 95% du signal GARCH** sans la complexite. C'est un trade-off rationnel.

---

## Quand GARCH explicite vaudrait le coup

Si tu voulais aller plus loin, GARCH te donnerait :
1. **Prediction explicite de la vol future** (pas juste l'actuelle)
2. **Asymmetrie** : les chocs negatifs (chutes) augmentent plus la vol que les chocs positifs (variante GJR-GARCH)
3. **Long-memory** : capture des effets sur 100+ barres (FIGARCH)

Mais pour ton timeframe M1, **rolling std reste suffisant**. La complexite GARCH apporterait < 5% d'amelioration au prix de 10× plus de code.

---

# ============================================
# LECON — Exercice (court)
# ============================================

## Cas pratique : Pourquoi std > 1.0 dans tes filtres ?

Tu regardes tes data : sur 3030 trades, ceux avec **std < 1.0** ont PF = 1.13 (mediocre) alors que ceux avec **std 4-6** ont PF = 2.20.

**Question** : que dit GARCH a ce sujet ?

<details>
<summary>Reponse</summary>

GARCH dit : "la vol persiste". Donc :

- **std actuel tres bas (<1.0)** → la vol va probablement rester basse pour les 5-15 prochaines barres
- Sur des barres a faible vol, **les mouvements sont minuscules** → ton TP a 0.15σ correspond a un mouvement de **0.15pts** (negligeable)
- Tes gains sont absorbes par le slippage et les frais
- → **PF 1.13** observe

A l'inverse, **std moyen (4-6)** → la vol persiste a ce niveau → mouvements MR de 1-3pts → TP atteignable et profitable → **PF 2.20**.

**C'est pour ca que std > 1.0 dans ton filtre fonctionne mathematiquement**. GARCH formalise ce que tu as decouvert empiriquement.
</details>

---

# ============================================
# RESUME — Fiche de revision
# ============================================

## L'idee a retenir en 3 lignes

> 1. **Volatility clustering** : la vol persiste (calme reste calme, volatile reste volatile)
> 2. **GARCH(1,1)** formalise ca : vol d'aujourd'hui = 85% de vol d'hier + 10% de choc + bruit
> 3. **Ton rolling std(19)** capture ce phenomene sans avoir besoin d'implementer GARCH

---

## Ce que tu DOIS retenir pour ton edge

- **std < 1.0** = marche mort → filtre tes setups (config v9 : std > 1.0 obligatoire)
- **std 4-8** = sweet spot → PF maximum
- **std > 20** = marche en panique → PF eleve mais peu de trades, attention au DD

---

## La phrase a retenir

> **La volatilite n'est pas aleatoire — elle a de la memoire. Ton filtre std > 1.0 exploite cette memoire pour eviter les setups morts.**
