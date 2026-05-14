# Diagnostic v9 — Résultats réels NT8 Strategy Analyzer

**Date** : 2026-05-14
**Source** : Backtest manuel BB dans NT8 Strategy Analyzer
**Stratégie** : `ninjatrader/HurstMR_Apex.cs` (commit `b64d2c9`, branche `restructure-v1`)
**Instrument** : MNQ (CME Micro Nasdaq futures)
**Période** : 13/05/2021 → 13/05/2026 (5 ans calendaires)

---

## 1. Performance Summary (NT8 Strategy Analyzer)

| Métrique | Valeur |
|----------|-------:|
| Total Net Profit | **+$12,169** |
| Gross Profit | $738,550 |
| Gross Loss | -$726,381 |
| Profit Factor | **1.02** |
| Max Drawdown | **-$22,748** |
| Sharpe Ratio | 0.05 |
| Sortino Ratio | 0.08 |
| Total Trades | **6,531** (3,421 longs / 3,110 shorts) |
| % Profitable | **23.93%** |
| Avg Trade | $1.86 |
| Avg Win / Avg Loss | 3.23 |
| Max Consecutive Losers | **32** |
| Profit per Month | $203 |
| Max Time to Recover | **1,137 jours** |

---

## 2. Verdict acté

**v9 n'a pas d'edge réel en conditions tick-realistic.** PF 1.02 = bruit statistique. DD -$22,748 = 11.4× le DD Apex limit ($2,000) → bust catastrophique garanti. Stratégie **non déployable Apex**.

---

## 3. Analyse des stats

### 3.1 PF 1.02 — Pas d'edge significatif

- Gross Profit ($738k) ≈ Gross Loss ($726k) → P&L ≈ zero-sum sur 5 ans
- Net +$12k sur 5 ans = $200/mois ≈ **inférieur au coût de slippage + commissions** sur 6,531 trades
  - Commission Apex/CME MNQ ≈ $1.10/round-trip × 6,531 = $7,184
  - Slippage 1 tick ($0.50) × 6,531 = $3,266
  - **Total coûts ≈ $10,450** vs Net Profit $12,169 → ratio coûts/profit = 86%
- L'algo gagne effectivement quelque chose, mais c'est noyé dans les coûts d'exécution

### 3.2 WR 23.93% — Anormalement bas pour MR

- Une stratégie MR pure devrait avoir un **WR 40-50%** (entrer sur extension extrême, revenir à la moyenne)
- 23.93% suggère que **76% du temps, le SL est touché avant le retour à la fair value**
- Avec ratio win/loss = 3.23, le profil ressemble à : "petits gains nombreux + grosses pertes occasionnelles" → **inverse du profil MR attendu**
- Hypothèse : en NT8 tick-realistic, les wicks intra-bar déclenchent le SL avant que la barre ne ferme retour FV. En Python close-only, ces mêmes barres clôturaient près de FV → SL "manqué", TP atteint → WR Python gonflé artificiellement.

### 3.3 32 pertes consécutives — Anomalie de clustering

- P(32 losses consécutives | WR=24%) = 0.76³² ≈ 0.026% → événement quasi-impossible si i.i.d.
- Présence d'un **cluster persistant** : probablement une période de régime trending pendant lequel la stratégie MR a saigné en boucle
- Hypothèse : le filtre Hurst (H<0.58) ne suffit pas à éviter les régimes trending soutenus. Probable nécessité d'un filtre régime additionnel (volatility, momentum, ou HMM).

### 3.4 Max DD -$22,748 — Bust Apex catastrophique

- $22,748 = 11.4× le DD limit Apex ($2,000)
- Compte $50k EOD aurait été bust **plusieurs fois** sur les 5 ans
- Aucune itération de challenge ne survivrait → 0/N evaluations passées

### 3.5 1,137 jours pour recover — Stratégie inutilisable

- Sur 5 ans = ~1,260 jours de trading, max time to recover = 1,137 jours = **90% de la période en drawdown**
- Une stratégie utilisable a une time-to-recover < 60 jours typiquement
- Confirme l'absence d'edge structurel

### 3.6 Avg Trade $1.86 — Sous le coût d'exécution

- 0.93 pts MNQ × $2/pt = 0.93 pt net
- Coût aller-retour : slippage 1 tick = 0.25 pt + commission $1.10 = 0.55 pt → **~0.80 pt**
- Marge nette par trade ≈ 0.13 pt → presque rien
- À l'échelle de la variance des trades, cette marge est **statistiquement indétectable**

---

## 4. Pourquoi divergence vs chiffres Python annoncés ?

Cinq mismatchs identifiés en audit (cf. `AUDIT_REPORT.md` §1, 3, 4) entre `pages/5_Backtest.py` et `ninjatrader/HurstMR_Apex.cs`.

### 4.1 🔴 Close-only execution Python ↔ Tick-realistic NT8 (MISMATCH CRITIQUE)

`pages/5_Backtest.py:362-410` :
```python
for j in range(i+1, min(n, i+timeout_bars)):
    c = closes[j]                               # ← LE BUG : utilise CLOSE uniquement
    if direction == "long":
        if c <= price - sl_pts:                 # SL touché ?
            result_pts = -sl_pts - slip; ...
```

→ Si la barre `j` fait un wick `low[j] = price - sl_pts - 2` mais `close[j] = price`, le SL **n'est pas déclenché** en Python. En NT8 SA mode "On Each Tick", le SL est déclenché par les ticks intra-barre → touché systématiquement.

**Conséquence empirique** : les "trades qui finissent au TP" en Python sont en réalité des trades qui ont tap le SL puis sont revenus — donc en live ils sont des **pertes au SL**, pas des gains au TP. Cela explique simultanément :
- Le PF gonflé en Python (2.29 vs 1.02 réel)
- Le WR gonflé en Python (42.64% vs 23.93% réel)
- Le DD masqué en Python (2.49% vs 45.5% réel sur $50k)

### 4.2 Fenêtre session UTC vs NY local

- Python `pages/5_Backtest.py:471` : `filter_session(csv, s_h=9, s_m=30, e_h=16, e_m=0)` appliqué sur `dt.hour` UTC (cf. `load_csv:203` qui fait `pd.to_datetime(ts_event, utc=True)`)
- C# `HurstMR_Apex.cs:329` : `inSession = (nowParis.Hour > 15 || (==15 && Min >= 30)) && (nowParis.Hour < 22)` → 15h30-22h Paris = 9h30-16h NY local
- Fenêtres **quasi disjointes** (1h overlap)

### 4.3 Skip 14h UTC ≠ "afternoon hole" NY

- Python : `skip_hours=(14,)` sur dt.hour UTC = 10h NY EDT (post-open hole)
- C# : aucun skip — trade toutes les heures de session NY incluant 14h NY (vrai "afternoon hole")

### 4.4 std_min=1.0 Python only

- Python `pages/5_Backtest.py:326` : `if std < std_min: continue`
- C# : `if (std < 1e-9) return;` — laxiste
- Python rejette des setups en faible vol, C# les prend → différence sur le pool de trades

### 4.5 Commissions et slippage

- Python : `slip=0.5pt` modélisé, **zéro commission**
- NT8 SA : slippage par défaut + commissions Apex/CME MNQ ≈ $1.10/RT activés

---

## 5. Leçons actées

1. **Backtest Python close-only = fiction.** Tout backtest qui ne simule pas les wicks high/low est **invalide** pour MNQ tick-realistic. La règle est désormais : **wicks obligatoires**, pas de close-only.

2. **NT8 Strategy Analyzer = seule source de vérité** pour mesurer l'edge réel sur MNQ. Si écart Python ↔ NT8 SA > 15% sur PF/DD/trades, le backtest Python est rejeté.

3. **Validation mécanique avant promotion d'un edge** : tout nouveau backtest Python doit être cross-validé contre NT8 SA sur ≥ 5 configs avec écart < 15%.

4. **Les paramètres v9 ne sont pas mauvais en soi.** Ils sont tirés d'un backtest fictif (close-only) mais la configuration paramétrique (H<0.58 / HW=50 / LB=19 / etc.) pourrait avoir un edge dans certaines fenêtres temporelles précises non encore explorées. C'est l'objet de la phase recherche.

5. **Anti-pattern à ajouter dans `CLAUDE.md`** (déjà présent en spirit, à renforcer) : ❌ "Backtest sans simulation des wicks intra-bar pour stratégie touche-stop". 6 ans de travail Python sur MNQ ont été biaisés par cette omission.

---

## 6. Décisions actées

| # | Décision | Statut |
|---|----------|--------|
| 1 | v9 **NON déployable** Apex | Acté |
| 2 | `pages/5_Backtest.py` **invalide** pour décision live (jusqu'à refonte avec wicks) | Acté |
| 3 | `CLAUDE.md` mis à jour avec vrais chiffres + warning | ✅ 2026-05-14 |
| 4 | Phase recherche d'edge ouverte (Étape 1 exploration Jupyter) | En cours |
| 5 | Backtester Python NT8-compatible | Conditionnel (Étape 2, ssi Étape 1 trouve un edge) |
| 6 | Restructuration Phase 2/3 (cf. `AUDIT_REPORT.md`) | **En pause** jusqu'à clarification de la stratégie cible |
| 7 | `etape0_repro_v9.py` (script baseline Python) | **Obsolète** — ne pas exécuter |

---

## 7. Métriques cibles pour validation d'un futur edge

Pour qu'une nouvelle config soit considérée comme un edge réel et passe à l'Étape 2 :

- ✅ **PF > 1.5** sur Train + Valid (combinés)
- ✅ **Sharpe > 1** sur Train + Valid
- ✅ **Max DD < $1,500** sur 6 mois glissants (= 75% du DD Apex)
- ✅ **WR cohérent** avec ratio win/loss (Kelly stable)
- ✅ Cross-validé contre **NT8 SA réel** (écart < 15% sur PF/DD/trades)
- ✅ **Holdout intouchable** confirmé après validation finale

Une seule de ces conditions non remplie = config rejetée.
