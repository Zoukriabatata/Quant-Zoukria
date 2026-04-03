# 25 — Exposant de Hurst & Mean Reversion (fBm)
# "Detecter les sessions anti-persistantes — Ton edge live"

> **Videos :** [Lec 25 — Fractional Brownian Motion](https://github.com/romanmichaelpaolucci/Quant-Guild-Library/tree/main) + [Lec 51 — HMM Filtre regime](https://youtu.be/Bru4Mkr601Q)

---

# ============================================
# APPRENTISSAGE — C'est quoi ? Pourquoi ?
# ============================================

## Le probleme fondamental

Le marche bouge de deux facons opposees selon la session.
Regarde les deux cas ci-dessous — ils expliquent tout :

<!-- CHART:hurst_session_visual -->

Si tu entres SHORT quand ca monte trop fort en **session TRENDING**, tu te fais ecraser.
La meme entree en **session MEAN-REVERTING** est rentable.

**La question : comment savoir AVANT de trader dans quelle session on est ?**

**Reponse : l'Exposant de Hurst H.**

---

## Le spectre de H

<!-- CHART:hurst_regime_spectrum -->

**3 regimes :**

| Valeur H | Nom | Signal pour ton trading |
|----------|-----|------------------------|
| **H < 0.45** | Anti-persistant | MR valide — **TRADE** |
| H = 0.5 | Aleatoire | Random walk — pas d'edge |
| H > 0.45 | Persistant | Trend — **NE PAS TRADER en MR** |

**Ton seuil : H < 0.45** — conservateur, pour etre certain que c'est vraiment MR.

---

## La memoire du marche

La cle mathematique : l'**autocorrelation des increments** (variation barre-a-barre).

$$\rho(1) = 2^{2H-1} - 1$$

| H | $\rho(1)$ | Ce que ca veut dire |
|---|----------|---------------------|
| 0.2 | $-0.36$ | Barre suivante tend a aller dans **l'autre sens** |
| 0.5 | $0$ | Independant — random walk |
| 0.7 | $+0.32$ | Barre suivante tend a **continuer** |

C'est cette autocorrelation **negative** (H < 0.5) qui cree ton edge MR.

---

## Visualisation — 3 series avec H differents

Le graphique montre 3 series simulees : verte (H=0.2 MR), jaune (H=0.5 RW), rouge (H=0.7 trend).
Observe que la serie verte **revient toujours vers sa moyenne** apres chaque ecart.

<!-- CHART:hurst_fbm_paths -->

---

## Ton strategy Hurst_MR en 3 etapes

**Etape 1** — Debut de session (15h30 Paris) : calcule H sur les 30 premieres barres.

**Etape 2** — Si H < 0.45 : attends que le prix sorte de ±2.5σ.

**Etape 3** — Entre contre la direction, TP = retour a la moyenne, SL = ±1.25σ.

---

# ============================================
# MODEL — Les maths
# ============================================

## Le Mouvement Brownien Fractionnel (fBm)

Le fBm est une generalisation du Mouvement Brownien Standard (H = 0.5).

**Covariance (Mandelbrot & Van Ness, 1968) :**

$$\text{Cov}[B_H(t), B_H(s)] = \frac{1}{2}\left(|t|^{2H} + |s|^{2H} - |t-s|^{2H}\right)$$

**Variance — insight cle :**

$$\text{Var}[B_H(t)] = t^{2H}$$

Quand H < 0.5, la variance croit **moins vite** que lineairement → le prix se freine et revient.

**Autocovariance des increments (fGn) :**

$$\gamma(k) = \frac{1}{2}\left(|k+1|^{2H} - 2|k|^{2H} + |k-1|^{2H}\right)$$

Quand H < 0.5 : $\gamma(1) < 0$ → increments **negativement** correles → MR.

**Validation — Empirical vs Theoretical Covariance**

Le graphique ci-dessous montre que la simulation Davies-Harte reproduit exactement
la structure de covariance theorique de la formule (RMSE tres proche de 0).
C'est la validation que le modele fBm est correct.

<!-- CHART:hurst_covariance_heatmap -->

---

## Calculer H : la methode R/S

Pour chaque fenetre de taille $\tau$ :

$$R(\tau) = \max(D_t) - \min(D_t) \quad \text{ou} \quad D_t = \sum_{s=1}^t (r_s - \bar{r})$$

$$S(\tau) = \text{ecart-type des } r_t \qquad RS(\tau) = \frac{R(\tau)}{S(\tau)}$$

**La pente du log-log = H :**

$$\boxed{H = \text{pente de } \log(RS) \text{ vs } \log(\tau)}$$

Le graphique ci-dessous montre les 3 droites pour H = 0.2, 0.5, 0.7.
**Plus la pente est faible, plus le marche est mean-reverting.**

<!-- CHART:hurst_rs_analysis -->

---

## Ton code Python — hurst_exponent()

```python
def hurst_exponent(ts):
    lags = range(2, min(len(ts) // 2, 50))
    rs_vals = []
    for lag in lags:
        chunks = [ts[i:i+lag] for i in range(0, len(ts) - lag + 1, lag)]
        rs_chunk = []
        for c in chunks:
            std = c.std()
            if std > 0:
                devs = np.cumsum(c - c.mean())
                rs_chunk.append((devs.max() - devs.min()) / std)
        if rs_chunk:
            rs_vals.append(np.mean(rs_chunk))
    h = np.polyfit(np.log(list(lags)[:len(rs_vals)]),
                   np.log(rs_vals), 1)[0]
    return float(np.clip(h, 0.0, 1.0))
```

---

## Les bandes de mean reversion

Rolling 30 barres M1 :

$$\mu_t = \frac{1}{30} \sum_{i=t-29}^{t} C_i \qquad \sigma_t = \text{std}(C_{t-29} \ldots C_t) \qquad z_t = \frac{C_t - \mu_t}{\sigma_t}$$

| Condition | Direction | TP | SL |
|-----------|-----------|----|----|
| $z_t > +2.5$ | SHORT | $\mu_t$ | $+1.25\sigma_t$ |
| $z_t < -2.5$ | LONG | $\mu_t$ | $-1.25\sigma_t$ |

---

## Le filtre HMM (Lec 51)

Meme en session MR, certaines barres sont trending.

```python
def hmm_proxy_state(closes):
    rets = np.abs(np.diff(np.log(closes)))
    cur  = rets[-1]
    if cur <= np.nanpercentile(rets, 33): return 0   # CALME
    if cur >= np.nanpercentile(rets, 67): return 2   # TRENDING → SKIP
    return 1                                           # NORMAL
```

**Regle :** HMM state = 2 → pas de trade sur cette barre.

---

# ============================================
# LECON — Exercices pratiques
# ============================================

## Exercice 1 : Identifier le regime a l'oeil

**Serie A :** 24 000 → 24 010 → 24 005 → 24 008 → 24 003

Variations : +10, −5, +3, −5 → **alternent +/−** → autocorrelation negative → **H < 0.5 → MR**

**Serie B :** 24 000 → 24 015 → 24 030 → 24 048 → 24 070

Variations : +15, +15, +18, +22 → **toutes positives et croissantes** → **H > 0.5 → Trend**

Quelle serie tu trades en MR ? **Serie A.**

---

## Exercice 2 : Calcul R/S simplifie a la main

Fenetre $\tau = 3$ sur la serie : +2%, −1%, +2%

| Etape | Calcul | Resultat |
|-------|--------|---------|
| Moyenne | $(2-1+2)/3$ | $\bar{r} = 1\%$ |
| Deviations cumulatives | $D_1=+1$, $D_2=-1$, $D_3=0$ | |
| Range | $\max(1,-1,0) - \min(1,-1,0)$ | $R = 2$ |
| Std | $\sqrt{(1+4+1)/3}$ | $S \approx 1.41$ |
| **R/S** | $2 / 1.41$ | **$\approx 1.42$** |

Repetes pour $\tau = 5, 9$ → traces $\log(RS)$ vs $\log(\tau)$ → la pente = H.

---

## Exercice 3 : Lire le dashboard et agir

Dashboard Live Signal a 15h30 Paris :

| Indicateur | Valeur | Interpretation |
|-----------|--------|----------------|
| Hurst H | **0.38** | < 0.45 → **Session MR validee** |
| HMM state | 1 | NORMAL → trade autorise |
| Z-score | **−2.7** | < −2.5 → **Signal LONG** |
| Prix | 24 180 NQ | MNQ = 2 418.0 |
| Fair Value | 24 225 NQ | Cible TP |
| SL guide | ±18 pts NQ | Stop = 24 162 |

**R:R = 18 pts risques / 45 pts vises = 2.5**

---

## La strategie en action — simulation

<!-- CHART:hurst_mr_strategy -->

---

## Exercice 4 : Quand NE PAS trader

Dashboard : Hurst H = **0.52** → > 0.45 → Session TRENDING.

**Regle absolue : tu fermes et tu attends demain.**

L'edge n'existe QUE quand H < 0.45. Forcer un trade en session trending = jouer contre les probabilites.

---

# ============================================
# RESUME — Fiche de revision
# ============================================

## Le spectre H — rappel visuel

<!-- CHART:hurst_regime_spectrum -->

---

## Tes parametres live (valides sur MNQ M1 Databento)

| Parametre | Valeur | Role |
|-----------|--------|------|
| `HURST_THRESHOLD` | **0.45** | Seuil session MR |
| `LOOKBACK` | **30 barres M1** | Fenetre rolling |
| `BAND_K` | **2.5σ** | Distance d'entree |
| `HMM state` | **≠ 2** | Filtre barre trending |
| `SL_MULT` | **1.25σ** | Stop loss |
| `TP` | **μ** (fair value) | Cible = retour a la moyenne |

---

## Formules cles

**Pente R/S = H :**

$$H = \text{pente de } \log\!\left(\frac{R(\tau)}{S(\tau)}\right) \text{ vs } \log(\tau)$$

**Autocorrelation lag-1 des increments :**

$$\rho(1) = 2^{2H-1} - 1 \quad \Rightarrow \quad \text{negative si H} < 0.5$$

---

## Le pipeline de decision

<div style="font-family:'JetBrains Mono',monospace; font-size:0.82rem; line-height:2.2; background:#080808; border:1px solid #1a1a1a; border-radius:10px; padding:1.4rem 1.8rem; margin:1rem 0;">
<div style="color:#3CC4B7; font-size:0.65rem; letter-spacing:0.2em; text-transform:uppercase; margin-bottom:0.8rem;">Pipeline de decision — chaque session</div>
<div style="color:#888;">15h30 Paris (9h30 NY) — Ouverture session</div>
<div style="color:#555; padding-left:1.2rem;">↓</div>
<div style="color:#fff;">Calcule <b>H</b> sur les 30 premieres barres</div>
<div style="color:#555; padding-left:1.2rem;">↓</div>
<div style="display:flex; gap:2rem; margin:0.4rem 0;">
  <div style="flex:1; background:#2a0a10; border:1px solid #ff3366; border-radius:8px; padding:0.7rem 1rem;">
    <div style="color:#ff3366; font-weight:700;">H ≥ 0.45 — TRENDING</div>
    <div style="color:#555; font-size:0.78rem; margin-top:0.3rem;">Pas de trade MR aujourd'hui<br>Attends demain</div>
  </div>
  <div style="flex:1; background:#0a2a1a; border:1px solid #00ff88; border-radius:8px; padding:0.7rem 1rem;">
    <div style="color:#00ff88; font-weight:700;">H &lt; 0.45 — MODE ACTIF</div>
    <div style="color:#555; font-size:0.78rem; margin-top:0.3rem;">Session MR validee<br>Attends le signal</div>
  </div>
</div>
<div style="color:#555; padding-left:1.2rem;">↓ (si H &lt; 0.45)</div>
<div style="color:#fff;">Chaque barre M1 : calcule <b>Z = (prix − μ) / σ</b></div>
<div style="color:#555; padding-left:1.2rem;">↓</div>
<div style="display:flex; gap:1rem; margin:0.4rem 0; flex-wrap:wrap;">
  <div style="background:#111; border:1px solid #1a1a1a; border-radius:6px; padding:0.5rem 0.8rem; color:#555; font-size:0.78rem;">
    <span style="color:#ff3366;">HMM = 2</span> → barre trending → <b>SKIP</b>
  </div>
  <div style="background:#0a2a1a; border:1px solid #00ff88; border-radius:6px; padding:0.5rem 0.8rem; color:#aaa; font-size:0.78rem;">
    <span style="color:#00ff88;">Z &lt; −2.5</span> → Signal <b>LONG</b> · TP=μ · SL=−1.25σ
  </div>
  <div style="background:#2a0a10; border:1px solid #ff3366; border-radius:6px; padding:0.5rem 0.8rem; color:#aaa; font-size:0.78rem;">
    <span style="color:#ff3366;">Z &gt; +2.5</span> → Signal <b>SHORT</b> · TP=μ · SL=+1.25σ
  </div>
</div>
</div>

---

## Lettres et symboles

| Lettre | Nom | Signification |
|--------|-----|---------------|
| $H$ | Hurst | Exposant de persistance (0 < H < 1) |
| $\rho(1)$ | Rho lag-1 | Autocorrelation increment suivant = $2^{2H-1}-1$ |
| $\gamma(k)$ | Gamma | Autocovariance des increments a lag k |
| $R(\tau)$ | Range | Etendue des deviations cumulatives |
| $S(\tau)$ | Std | Ecart-type de la fenetre $\tau$ |
| $\mu_t$ | Mu rolling | Moyenne 30 barres = fair value = cible TP |
| $\sigma_t$ | Sigma rolling | Ecart-type 30 barres = volatilite |
| $z_t$ | Z-score | Distance du prix a la moyenne en nombre de sigma |

---

## Limites a connaitre

- H est **instable** : recalcule chaque session
- H < 0.45 ne garantit pas que chaque trade est gagnant — c'est un **edge statistique** sur 20+ trades
- En RTH (15h30-22h00 Paris), H est plus stable qu'en overnight
- Backtest valide sur MNQ M1 CSV Databento — toujours versionner et revalider
