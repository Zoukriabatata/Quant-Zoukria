# 05 — HMM : Detecter le regime de marche cache
# "Pourquoi le marche change d'humeur sans prevenir"

> **Source :** [Quant Guild #51 — Hidden Markov Models](https://youtu.be/Bru4Mkr601Q)

---

# ============================================
# APPRENTISSAGE — C'est quoi ? Pourquoi ?
# ============================================

## L'intuition en 30 secondes

Le marche a des **humeurs cachees** que tu ne peux pas voir directement :
- **Bull regime** : prix qui monte regulierement, vol basse
- **Bear regime** : prix qui baisse, vol elevee
- **Sideways/Range** : prix qui oscille, vol moderee
- **Crash** : chute violente, vol explosee

Ces humeurs sont **cachees** (hidden) — tu ne peux les observer que via leurs **consequences** (prix, vol).

**HMM (Hidden Markov Model)** = methode mathematique pour deviner l'humeur cachee actuelle a partir des observations.

---

## Comment ca relie a ton edge

Ton edge HURST_MR fait deja une **detection de regime simplifiee** :
- Hurst < 0.58 → regime "MR" (humeur favorable a ta strategie)
- Hurst >= 0.58 → regime "non-MR" (humeur defavorable)

C'est un HMM **a 2 etats** (MR/pas-MR) avec Hurst comme observation. **Simple mais efficace.**

Un HMM complet pourrait avoir 4-5 etats (Bull-MR, Bull-Trend, Bear-MR, Bear-Trend, Crash) avec des transitions probabilistes entre eux. **Plus complexe mais pas necessairement meilleur**.

---

## La propriete de Markov (concept central)

> **L'avenir ne depend que du present, pas du passe.**

En clair : pour predire l'humeur de demain, tu n'as besoin que de l'humeur d'aujourd'hui. Pas besoin de remonter a la semaine derniere.

Cette propriete est **fausse en general** sur les marches (l'historique compte). Mais elle est **suffisamment vraie a court terme** (heure/jour) pour que HMM marche.

---

## Pourquoi c'est revolutionnaire

Avant HMM, on supposait que les parametres du marche (vol, retours) etaient **constants**. Erreur fondamentale : le marche change de regime.

HMM permet :
1. **Detecter automatiquement** quand le regime change
2. **Adapter la strategie** au regime detecte
3. **Anticiper** la duree probable du regime actuel

---

# ============================================
# MODEL — Les maths derriere (simplifie)
# ============================================

## Les 3 elements d'un HMM

### 1. Les etats caches (S)
Exemple a 3 etats : `S = {Bull, Bear, Range}`

### 2. La matrice de transition (A)
Probabilites de passer d'un etat a un autre :

```
        Bull   Bear   Range
Bull  [ 0.85   0.05   0.10 ]    ← Si on est en Bull, 85% on reste Bull
Bear  [ 0.05   0.85   0.10 ]    ← Si on est en Bear, 85% on reste Bear
Range [ 0.15   0.15   0.70 ]    ← Range moins "collant"
```

**Lecture** : un regime tend a **persister** (diagonale dominante). C'est le pendant du "volatility clustering" pour les regimes.

### 3. Les emissions (B)
Pour chaque etat, distribution des observations (returns, vol, volume).

Exemple :
- Bull : returns moyens +0.05%/h, vol 8 pts
- Bear : returns moyens -0.05%/h, vol 15 pts (vol plus forte en bear)
- Range : returns 0, vol 4 pts

---

## L'algorithme de Viterbi (en intuition)

Pour deviner la sequence d'etats caches la plus probable etant donne tes observations :

```
1. Initialisation : on suppose chaque etat possible au depart, avec une proba
2. Pour chaque nouvelle observation (chaque barre M1) :
   - On calcule la proba de chaque etat etant donne l'observation
   - On met a jour : nouvelle_proba = ancienne × P(observation|etat) × P(transition)
3. A la fin : on prend la sequence d'etats avec la proba maximum
```

C'est **dynamic programming** avec une complexite O(N × T) ou N = nb etats, T = nb barres.

---

## Pourquoi tu n'utilises pas HMM explicite

Ton edge utilise **Hurst** comme proxy. C'est mathematiquement equivalent a un HMM a 2 etats mais :
- ✅ Plus rapide a calculer (10ms vs 100ms)
- ✅ Plus stable (moins d'overfitting)
- ✅ Plus interpretable (1 chiffre vs matrice 3x3)
- ❌ Moins precis pour distinguer Bull-MR vs Bear-MR

**Pour ton timeframe M1, ce trade-off est correct.** Si tu tradais le daily, HMM apporterait plus.

---

# ============================================
# LECON — Exercice (court)
# ============================================

## Cas pratique : Pourquoi le marche change brusquement ?

Tu observes : sur 30 min de session, le marche etait tres MR (Hurst ~0.4). Puis brusquement, en 10 minutes, le marche se met a trender fort (Hurst monte a 0.62).

**Question** : c'est un bug ou un phenomene reel ?

<details>
<summary>Reponse</summary>

**Phenomene reel** completement modelise par HMM.

**Hypothese HMM** : le marche est passe de l'etat **"Range MR"** a l'etat **"Trend"**. La matrice de transition modelise exactement ces sauts probabilistes.

Causes possibles cote macro :
- Annonce news (CPI, Fed)
- Gros ordre institutionnel
- Cassure technique d'un niveau cle

Reponse de ton edge : ton **Trail MR/Trend** s'active automatiquement (H_intra > 0.51 → bascule en mode trail). C'est exactement la logique HMM appliquee : **detecter le changement d'etat et adapter l'execution**.

C'est pour ca que le Trail v9 marche : c'est un mini-HMM en temps reel.
</details>

---

# ============================================
# RESUME — Fiche de revision
# ============================================

## Ce que tu dois retenir

| Concept | Definition simple |
|---|---|
| **Etat cache** | L'humeur invisible du marche (Bull/Bear/Range/MR/Trend) |
| **Observation** | Ce que tu vois (prix, vol, returns, Hurst) |
| **Matrice transition** | Probabilites de changer d'etat |
| **Emission** | Distribution des observations par etat |
| **Viterbi** | Algorithme pour deviner les etats passes |

---

## Lien direct avec ton edge

- **Ton Hurst** = HMM simplifie a 2 etats
- **Ton Trail** = detection en live du changement d'etat MR→Trend
- **Pas besoin d'implementer HMM complet** : Hurst suffit pour le timeframe M1

---

## La phrase a retenir

> **Le marche a des humeurs cachees. Hurst en detecte UNE (MR vs pas-MR). Pour ton edge, c'est suffisant. HMM complet = overkill pour le M1.**
