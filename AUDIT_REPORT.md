# AUDIT_REPORT — Projet Quant MNQ

**Date** : 2026-05-13
**Branche** : `restructure-v1`
**Tag de sécurité** : `pre-restructure-stable` → `b64d2c9`
**Backup code** : `C:\tmp\quant_backup_pre_restructure_2026-05-13\` (112 fichiers, 4.14 MB)
**Données massives** (126 GB) : intactes, exclues du nouveau `.gitignore`

> Lecture seule. Aucune modification de code effectuée. Ce rapport sert d'entrée pour la Phase 2 (plan de migration).

---

## 0. TL;DR — Ce qu'il faut retenir avant tout

| # | Constat | Sévérité |
|---|---------|----------|
| 1 | **Aucun JSON baseline v9 sauvegardé** dans le projet — les chiffres champion (PF 2.29 / Sharpe 4.82 / +$303k / 3030 trades) n'existent qu'en mémoire (CLAUDE.md). Référence `params_20260512_2324` introuvable. | 🔴 CRITIQUE |
| 2 | `backtest_hurst.py` (racine, 1470 l.) et `pages/5_Backtest.py` (2823 l.) sont **deux versions divergentes** du même module : le premier porte les defaults **PRE-champion** (H=0.50, lb=30, k=2.0, sl=0.75, tp=0.50), le second les defaults **champion v9** (H=0.58, hw=50, lb=19, k=2.75, sl=0.65, tp=0.15, timeout=120). | 🔴 CRITIQUE |
| 3 | **Pas un seul test** ne couvre le code v9 (Hurst, backtest, live signal, NinjaScript). Les 9 tests existants ciblent exclusivement les modules v10 (`quant_v10/tests/`). | 🔴 CRITIQUE |
| 4 | **6 pages Streamlit utilisent `exec(open(...).read())`** au lieu d'imports propres — anti-pattern qui rend la migration risquée et le caching impossible. | 🟠 MAJEUR |
| 5 | **Sous-caching massif** : 20 `@st.cache_data` au total sur 6500+ lignes Streamlit critiques. `live_signal_dash.py` (1547 l.) a 1 seul cache, `backtest_models.py` (1888 l.) 1 seul. Cause probable du "Streamlit qui rame". | 🟠 MAJEUR |
| 6 | **Header docstring obsolète dans `ninjatrader/HurstMR_Apex.cs`** (lignes 12-44) référence un backtest 2026-04-20 / H=0.53 / PF=1.88, alors que les valeurs par défaut du code (ligne 195+) sont bien v9 champion 2026-05-12. Désynchronisation doc/code. | 🟡 MOYEN |
| 7 | **Fonction `hurst_rs()` dupliquée 3 fois** (`backtest_hurst.py:108`, `live_signal.py:68`, `live_signal_dash.py:222`) + 2 variantes (`hurst_exponent` dans `backtest_models.py`, `signal_hurst_mr` dans `crypto_swing_backtest.py`). Risque de drift entre Python recherche et Python live. | 🟡 MOYEN |
| 8 | **Aucune externalisation des paramètres v9** dans un `config.yaml`. Les 8 paramètres champion sont dispersés dans les defaults de sliders Streamlit, les commentaires C#, et la mémoire. | 🟡 MOYEN |
| 9 | `.streamlit/secrets.toml` contient `APP_PASSWORD = "Minecraftprime"` en clair. **Gitignoré** donc OK localement, mais auth très faible. | 🟢 MINEUR |
| 10 | `README.md` est **vide** (0 octet). | 🟢 MINEUR |

---

## 1. Inventaire complet

### 1.1 Vue d'ensemble par extension

| Extension | Nombre | Volume |
|-----------|-------:|-------:|
| `.py` | 58 | 1.17 MB |
| `.md` | 29 | 223 KB |
| `.json` | 10 (hors data dirs) | ~12 KB |
| `.cs` | 5 | 97 KB |
| `.txt` | 9 | 21 KB |
| `.ipynb` | 1 | 2.72 MB |
| `.toml` / `.yml` | 3 | 1.2 KB |

### 1.2 Structure top-level

```
QUANT MATHS/
├── CLAUDE.md              # Contexte projet (8.3 KB, à jour)
├── README.md              # VIDE (0 KB) — à créer
├── SYSTEM_PLAN.md         # Ancien plan GARCH+HMM+Kalman (15 KB) — pas v9
├── requirements.txt       # 11 deps, basique
├── .gitignore             # Réécrit en étape 3 (14 sections, 54 l.)
│
├── .github/workflows/     # GitHub Actions (sol_alert.yml)
├── .streamlit/            # config.toml + secrets.toml (gitignored)
├── .devcontainer/
├── .pytest_cache/
│
├── learning/              # Markdown pédagogiques
│   ├── 04_garch.md, 04b_trading_metrics.md, 05_HMM, 06_Kalman, 06c_halflife,
│   │   08_Kelly, 25_hurst_mr.md         (7 actifs)
│   └── archive/                          (16 archivés)
│
├── pages/                 # 14 pages Streamlit + _home.py
├── ninjatrader/           # 2 .cs (v9 + v10) — non versionné
├── quantower/             # 2 fichiers (bridge + port v9) — non versionné
├── quant_v10/             # 41 fichiers (modules, orchestrator, tests, validation, reports)
│
├── ES 5ANS DATA/          # ~50 GB — exclus .gitignore
├── NQ 5ANS DATA/          # ~75 GB — exclus .gitignore
└── time_series_analysis_for_quant_finance.ipynb   # 2.7 MB, seul .ipynb
```

### 1.3 Fichiers Python à la racine (rôle inféré)

| Fichier | Lignes | Rôle |
|---------|------:|------|
| `Accueil.py` | 48 | Page home Streamlit |
| `alert_cron.py` | 121 | Cron GitHub Actions — alerte signal SOL daily |
| `app_learning.py` | 30 | Router auth → `_home.py` |
| `auth.py` | 36 | Auth Streamlit (mot de passe simple + DEV_MODE) |
| `backtest_hurst.py` | **1470** | **Backtest Hurst_MR (version OBSOLÈTE, defaults pre-champion)** |
| `backtest_models.py` | **1888** | Multi-model backtest (Apex/TopStep/Alpha — MNQ/ES/MGC/MCL) |
| `btc_dca.py` | 473 | BTC DCA signal + alertes Telegram/Discord |
| `charts.py` | **2157** | Plotly charts pour app_learning (catalogue de 30+ figures) |
| `config.py` | 54 | Chemins centralisés (MNQ_CSV, etc.) |
| `crypto_live_sol.py` | **1314** | Dashboard SOL live + alertes |
| `crypto_swing_backtest.py` | **1668** | Crypto multi-model swing backtest |
| `live_signal.py` | 241 | Signal live Hurst_MR via DXFeed (script standalone) |
| `live_signal_dash.py` | **1547** | Dashboard Streamlit live signal Hurst_MR |
| `quantower_setup.py` | 289 | Page Streamlit setup Quantower |
| `styles.py` | **1269** | Design system Streamlit (CSS injecté) |

### 1.4 Fichiers `pages/` Streamlit (14 pages + helpers)

| Page | Lignes | Pattern | Source |
|------|------:|---------|--------|
| `_home.py` | 189 | Standalone | — |
| `1_Demarrage.py` | 289 | Standalone | — |
| `2_Session_Prep.py` | 322 | Standalone | — |
| `3_Live_Signal.py` | **2** | ⚠️ `exec(open(...))` | `live_signal_dash.py` |
| `4_Journal.py` | 568 | Standalone | — |
| `5_Backtest.py` | **2823** | Standalone (gros) | — |
| `6_Multi_Model.py` | **2** | ⚠️ `exec(open(...))` | `backtest_models.py` |
| `7_Etude.py` | 741 | Standalone | Lit `learning/*.md` + charts |
| `7_VR_MR.py` | 1113 | Standalone (NEW) | Variance Ratio + Hurst optim |
| `8_Library.py` | 331 | Standalone | Catalogue Quant Guild |
| `9_BTC_DCA.py` | **2** | ⚠️ `exec(open(...))` | `btc_dca.py` |
| `Apex_Rules.py` | 688 | Standalone | Dashboard compliance Apex |
| `Crypto_Live_SOL.py` | **2** | ⚠️ `exec(open(...))` | `crypto_live_sol.py` |
| `Crypto_Swing.py` | **2** | ⚠️ `exec(open(...))` | `crypto_swing_backtest.py` |
| `Quantower_Setup.py` | **2** | ⚠️ `exec(open(...))` | `quantower_setup.py` |

### 1.5 Fichiers C# (5)

| Fichier | KB | Rôle |
|---------|----|------|
| `RithmicBridge.cs` (racine) | 4.7 | Bridge semi-auto Rithmic (signaux Python → NT8) |
| `ninjatrader/HurstMR_Apex.cs` | 36.7 | **Stratégie full-auto champion v9 (defaults corrects, docstring obsolète)** |
| `ninjatrader/HurstMR_Apex_v10.cs` | 35.4 | v10 avec hooks Lee-Mykland / Grossman-Zhou |
| `quantower/QuantowerBridge.cs` | 3.4 | Bridge Quantower (analogue Rithmic) |
| `quantower/HurstMR_Apex_Quantower.cs` | 16.8 | Port Quantower de HurstMR_Apex |

### 1.6 quant_v10/ (sprint v10 — 41 fichiers)

```
quant_v10/
├── modules/         (6 modules : Lee-Mykland, HAR-RV, Grossman-Zhou, Cartea-Figueroa, MF-DFA, Copula)
├── orchestrator/    (3 fichiers : runner_v10, runner_copula_pairs, ab_compare_v9_v10)
├── tests/           (9 tests TDD — 97 cas, source académique citée par module)
├── utils/           (databento_loader.py — format GLBX.MDP.3 .csv.zst)
├── validation/      (3 fichiers : cpcv.py, deflated_sharpe.py, run_final_validation.py)
└── reports/         (5 JSON + 3 MD — rankings sprints 1/2 + v10 champion validated)
```

### 1.7 Markdown actifs / archivés

**Actifs** (7) : `04_garch.md`, `04b_trading_metrics.md`, `05_hidden_markov_models.md`, `06_kalman_filter.md`, `06c_halflife_ou.md`, `08_kelly_criterion.md`, `25_hurst_mr.md` (ce dernier documente Hurst_MR v9 avec les bons chiffres).

**Archivés** (16, dans `learning/archive/`) : roadmap, retail vs institutional, notation maths, time series, CLT, asymptotics, ergodicity, Monte Carlo, régime switching, Hawkes, GMM, Kalman MR, confirmation/reversal, pipeline integration, backtesting pitfalls, profitable vs tradable.

### 1.8 Rapports JSON

Tous dans `quant_v10/reports/` : sprint1 + sprint2 rankings, `h080_trail050_5y_ranking.json`, `sprint2_1_gz_adaptive_5y.json`, `v10_champion_validated.md`. **Aucun JSON pour le baseline v9 champion.**

---

## 2. Cartographie du code par fonction

### 2.1 Où vit la logique HURST_MR v9 ?

| Couche | Fichier | Statut |
|--------|---------|--------|
| **Backtest Python (production de fait)** | `pages/5_Backtest.py` (2823 l.) | ✅ Defaults champion v9 hardcodés dans sliders |
| **Backtest Python (legacy)** | `backtest_hurst.py` (1470 l., racine) | ⚠️ Defaults pre-champion — divergent |
| **Live signal Streamlit** | `live_signal_dash.py` (1547 l.) | ✅ Active en prod |
| **Live signal standalone** | `live_signal.py` (241 l.) | ✅ Script DXFeed |
| **Live full-auto C#** | `ninjatrader/HurstMR_Apex.cs` (37 KB) | ✅ Defaults v9, header docstring obsolète |
| **Variante v10 avec hooks** | `ninjatrader/HurstMR_Apex_v10.cs` | Defaults v9, hooks Lee-Mykland / Grossman-Zhou ajoutés |
| **Port Quantower** | `quantower/HurstMR_Apex_Quantower.cs` | Port récent (non versionné) |
| **Étude paramétrique** | `pages/7_VR_MR.py` (1113 l.) | Variance Ratio + optim |

### 2.2 Streamlit "qui rame" — diagnostic des coupables

| Fichier | Lignes | `@st.cache_*` | Verdict |
|---------|------:|:-:|---------|
| `pages/5_Backtest.py` | 2823 | 4 | Volumineux mais correctement caché sur load_csv + build_study_cache ; le reste (grids, MC) probablement non caché |
| `backtest_models.py` | 1888 | 1 | **Sous-caché** — un seul cache pour multi-model + multi-instrument |
| `crypto_swing_backtest.py` | 1668 | 2 | Sous-caché pour 7 modèles × N pairs |
| `live_signal_dash.py` | 1547 | 1 | **Sous-caché** — dashboard live qui recompute Hurst+bandes à chaque tick |
| `crypto_live_sol.py` | 1314 | 1 | Sous-caché |
| `styles.py` | 1269 | 0 | Pas de Python lourd, c'est du CSS |
| `pages/7_VR_MR.py` | 1113 | 1 | Sous-caché pour optim params |

**Cause probable du lag** : recalculs Hurst rolling sur fenêtre 50 × 5 ans × M1 à chaque rerun Streamlit, sans cache de l'array intermédiaire `hurst_arr`. `build_study_cache` cache le dict mais ses inputs (csv_path, session window, hwin) changent dès qu'un slider bouge.

### 2.3 RithmicBridge.cs

Bridge **semi-auto** existant (4.7 KB, racine). Lit signaux Python via fichier JSON / socket, exécute en manuel-confirmé sur NT8 + Rithmic. Compagnon de `quantower/QuantowerBridge.cs` (3.4 KB).

### 2.4 Stratégie NinjaScript full-auto

`ninjatrader/HurstMR_Apex.cs` (37 KB). 19 `[NinjaScriptProperty]` exposées. Champion v9 hardcodé en `OnStateChange` (ligne ~195+) avec note "Champion v9 2026-05-12 / PF 2.29 / WR 42.64% / Sharpe 4.82 / DD 2.49% / 3030 trades / +$303,306". ✅ **Code à jour, seul le commentaire-header (l. 12-44) référence l'ancien backtest 2026-04-20.**

---

## 3. Duplications identifiées

### 3.1 Fonction Hurst (5 implémentations)

| Fichier | Fonction | Méthode |
|---------|----------|---------|
| `backtest_hurst.py:108` | `hurst_rs(ts)` | R/S, 12 lags log-espacés [4..min(n/2,50)], chunks vectorisés, ddof=0 |
| `live_signal.py:68` | `hurst_rs(ts)` | Idem (probable copie) |
| `live_signal_dash.py:222` | `hurst_rs(ts)` | Idem (probable copie) |
| `backtest_models.py:272` | `hurst_exponent(prices)` | Variante (à vérifier signature) |
| `crypto_swing_backtest.py:233` | `signal_hurst_mr(close, window, ...)` | Wrapper crypto |
| `pages/5_Backtest.py` | inline | Probable copie de `backtest_hurst.py` |

**Risque** : si une implémentation est corrigée pour fix un edge case, les 4 autres restent buggées. Le live et le backtest peuvent diverger silencieusement.

### 3.2 Backtest Hurst : `backtest_hurst.py` vs `pages/5_Backtest.py`

Mêmes docstring d'en-tête (`"Étude Hurst_MR — Analyse complète Lec 25 (fBm) + Lec 51 (HMM)"`). Mais :
- Defaults sliders différents (pre-champion vs champion v9)
- `pages/5_Backtest.py` est 1.9× plus long → sections ajoutées (Walk-Forward, Apex Rules, sweep risk%, etc.)

**Conclusion** : `pages/5_Backtest.py` est l'évolution de `backtest_hurst.py`. Le second est une **copie figée** restée à la racine.

### 3.3 Rollover detection (`shift(-1)`)

Pattern dupliqué dans 6 fichiers (cf. §4.1).

### 3.4 Theme/CSS Plotly

Bloc `DARK = dict(template="plotly_dark", ...)` répété dans `backtest_hurst.py`, `pages/5_Backtest.py`, `quantower_setup.py`, probablement d'autres. Devrait vivre dans `styles.py` ou un module commun.

---

## 4. Risques identifiés

### 4.1 Look-ahead bias potentiels

Recherche : `shift(-`, `iloc[i+`, `center=True`, `.loc[..+1]`, `future_`.

| Fichier | Ligne | Pattern | Verdict |
|---------|------:|---------|---------|
| `backtest_hurst.py` | 176 | `day_sym["roll"] = (day_sym["roll"] \| day_sym["roll"].shift(-1))` | **Rollover skip** — marque le jour J si J+1 est rollover. Acceptable (les rollovers sont des dates calendaires connues à l'avance) MAIS doit être documenté. |
| `pages/5_Backtest.py` | 218 | Idem | Idem |
| `backtest_models.py` | 960 | Idem | Idem |
| `pages/7_VR_MR.py` | 127 | Idem | Idem |
| `quant_v10/orchestrator/runner_v10.py` | 105 | Idem | Idem |
| `quant_v10/utils/databento_loader.py` | 87 | Idem | Idem |
| `quant_v10/modules/vol_forecast_har_rv.py` | 68 | `df["target"] = df["rv"].shift(-1)` | **Correct** — création target HAR-RV (label futur pour fit). Pas un look-ahead. |
| `quant_v10/tests/test_har_rv.py` | 160 | Idem | Correct (test) |

**À investiguer** : sur `pages/7_VR_MR.py:127`, la chaîne `is_rollover.shift(-1).fillna(False)` n'est pas suivie du `|` OR avec la version non-shiftée comme dans les autres fichiers — formule potentiellement différente, à vérifier en Phase 2.

### 4.2 Paramètres v9 hardcodés (ou pas)

| Source | Type | Sécurité |
|--------|------|----------|
| `pages/5_Backtest.py` lignes 68-102 | Defaults Streamlit sliders | ⚠️ Modifiable par utilisateur d'un clic, sans warning |
| `backtest_hurst.py` lignes 66-103 | Defaults Streamlit sliders | ⚠️ Defaults **différents** (pre-champion) |
| `ninjatrader/HurstMR_Apex.cs` lignes 195+ | `OnStateChange` Initial state | Valeurs initialisées en code, modifiables UI NT8 |
| CLAUDE.md | Documentation | ✅ Source of truth officielle |
| **`config/strategies/hurst_mr_v9.yaml`** | **N'EXISTE PAS** | 🔴 Aucune externalisation |

### 4.3 Secrets en clair

| Fichier | Contenu | Statut |
|---------|---------|--------|
| `.streamlit/secrets.toml` | `APP_PASSWORD = "Minecraftprime"` | Gitignoré ✓ mais auth très faible |
| `.env` | Non présent (gitignoré) | OK |
| `live_signal.py:32` | `os.environ.get("DXFEED_PASSWORD", "")` | OK |
| `crypto_live_sol.py:41-42` | `st.secrets.get(...)` avec fallback | OK |
| `.github/workflows/sol_alert.yml` | `${{ secrets.SOL_NTFY_TOPIC }}` | OK |
| `btc_dca.py:361` | `st.text_input(type="password")` (Discord/Telegram) | OK (saisie runtime, pas persistée) |

**Pas de clé API hardcodée détectée.** Seul point sensible : `APP_PASSWORD` plain text dans secrets.toml local.

### 4.4 Imports cassés / dépendances obsolètes

`requirements.txt` actuel (11 deps) :
```
streamlit, plotly, numpy, scipy, pandas, yfinance, requests, pytz,
python-dotenv, streamlit-autorefresh, statsmodels
```

**Manquant** d'après imports détectés :
- `numba` (mentionné CLAUDE.md mais pas importé directement — OK si absent)
- `arch` (pour GARCH dans `04_garch.md` et `backtest_models.py`) → **à vérifier en Phase 2**
- `hmmlearn` (pour HMM) → **à vérifier**
- `pytest` (tests v10 existent) → **à ajouter en dev-requirements**
- `zstandard` (pour databento `.csv.zst`) → **à vérifier dans `databento_loader.py`**
- `joblib` / `numba` selon perf
- `black`, `ruff` (style)

**À faire en Phase 2** : générer un `pip freeze` du venv réel et confronter à `requirements.txt`.

### 4.5 Données sensibles dans le repo

- `sol_journal.db` : gitignoré ✓
- `ES 5ANS DATA/`, `NQ 5ANS DATA/` : gitignorés ✓ (nouveau .gitignore)
- `.streamlit/secrets.toml` : gitignoré ✓
- Aucune clé API hardcodée détectée

### 4.6 Baseline v9 NON sauvegardée

**Risque le plus critique du projet.**

Les chiffres PF 2.29 / Sharpe 4.82 / DD 2.49% / 3030 trades / +$303,306 ne sont **présents que dans** :
- `CLAUDE.md` (texte)
- `ninjatrader/HurstMR_Apex.cs` (commentaire ligne 195+)
- Aucun fichier JSON / Parquet / CSV

La référence `params_20260512_2324` (citée dans le `.cs`) ne correspond à aucun fichier dans le projet.

**Conséquence** : impossible de re-vérifier le backtest v9 sans :
1. Avoir la même version exacte du code Python (1 commit avant)
2. Avoir les mêmes données MNQ M1 (présentes dans `NQ 5ANS DATA/`)
3. Re-runner depuis `pages/5_Backtest.py` (dont les defaults sliders sont à jour)

**Action proposée en Phase 2** : **prioriser la création d'une baseline reproductible** avant toute autre étape de migration. Sans baseline, aucun test de non-régression n'est possible.

---

## 5. État du Streamlit — pourquoi ça rame

### 5.1 Cellules lourdes non cachées

| Fichier | Opération lourde probable | Caché ? |
|---------|--------------------------|---------|
| `live_signal_dash.py` | Recalcul rolling Hurst sur dernières N barres à chaque tick | Partiellement (1 cache total) |
| `backtest_models.py` | Multi-model × multi-instrument × M1 sur 1 an | 1 cache total — insuffisant |
| `pages/5_Backtest.py` | Sweep risk%, Monte Carlo, Walk-Forward | Caches sur load + build_study_cache, **MC et WF probablement non cachés** |
| `crypto_swing_backtest.py` | 7 modèles × N pairs × ressampling | 2 caches — insuffisant pour MultiModel |

### 5.2 Recalculs inutiles

Pattern observé : `hurst_rs` est appelé bar-par-bar dans `build_study_cache` (boucle `for _i in range(hwin, n)`). Pour 5 ans × 390 bars/jour × 1259 jours ≈ 491k barres × 50 lags × régression OLS, c'est massif. Le résultat est mis en cache via `@st.cache_data` mais **toute modification d'un slider** (capital, max_dd, max_td, risk_pct...) qui ne touche pas à `csv_path/sh/sm/eh/em/hwin` invalide-t-elle le cache ? À vérifier en Phase 2.

### 5.3 Chargements de données massifs

`load_csv()` lit le CSV MNQ M1 complet 5 ans (probablement >1 GB de raw). Cache `@st.cache_data` présent ✓. Mais :
- Format CSV (pas Parquet) → lecture ~10-30 s sans cache
- Pas de chunking
- Pas de support pour data > RAM

**Proposition Phase 2** : convertir le CSV master en Parquet (5-10× plus rapide), garder un loader unique côté `01_research/src/data.py`.

### 5.4 Anti-pattern exec()

6 pages chargent leur logique via `exec(open(...).read())`. Conséquences :
- Pas de tree-shaking, pas de cache module
- Impossible d'utiliser `@st.cache_data` correctement sur les fonctions du fichier exec'ed
- Imports résolus dans le scope global → conflits potentiels entre pages
- Stack traces illisibles

---

## 6. Couverture de tests

### 6.1 État actuel

| Localisation | Nombre de fichiers tests | Cibles |
|--------------|-------------------------:|--------|
| `quant_v10/tests/` | 9 | Modules v10 uniquement |
| Tout le reste | 0 | — |

**97 cas de test** documentés (cf. `v10_champion_validated.md`) couvrent : Lee-Mykland (10), HAR-RV (12), Grossman-Zhou (24), Cartea-Figueroa (10), MF-DFA (9), Copula (12), Databento loader (10), CPCV (4), Deflated Sharpe + PBO (6).

### 6.2 Trous critiques

| Module v9 | Tests ? |
|-----------|:-------:|
| `hurst_rs` (5 implémentations) | ❌ Aucun |
| `run_hurst_backtest` | ❌ Aucun |
| Apex DD trailing simulation | ❌ Aucun |
| NinjaScript C# | ❌ Aucun (NT8 Strategy Analyzer manuel uniquement) |
| Live signal pipeline | ❌ Aucun |
| Auth Streamlit | ❌ Aucun |
| Journal SQLite | ❌ Aucun |

### 6.3 Outils

- `.pytest_cache/` présent → pytest a déjà tourné au moins une fois sur `quant_v10/`
- `pytest` non listé dans `requirements.txt` → installé localement uniquement

---

## 7. SYSTEM_PLAN.md — clarification

**15 KB d'archive stratégique**. Décrit une stratégie **différente** de Hurst_MR v9 :
- Architecture GARCH + HMM 3-états + Kalman OU
- Sizing Half-Kelly par régime (LOW 10%, MED 6%)
- Cible Sharpe 1.2–1.5 (vs Sharpe 4.82 actuel)
- Sources : Quant Guild Library Lec 28/34/36/44/47/48/49/51/72/74

Ce n'est **ni la stratégie actuelle (Hurst_MR v9)** ni une roadmap v10 (qui est dans `quant_v10/reports/v10_champion_validated.md`). C'est un document de référence pédagogique / aspirational. À catégoriser : **document d'archive** (proposition Phase 2 : déplacer vers `03_spec/archive/strategy_garch_hmm_kalman_v0.md`).

---

## 8. Mapping vers l'architecture cible

Légende : **MOVE** = déplacer sans modifier · **REFACTOR** = déplacer + corriger imports · **SPLIT** = découper · **MERGE** = fusionner · **DELETE** = supprimer · **KEEP** = laisser à la racine.

### 8.1 Couche RESEARCH (`01_research/`)

| Source actuelle | Destination | Action |
|-----------------|-------------|--------|
| Notebooks à créer | `01_research/notebooks/` | Phase 3 (post-migration) |
| `hurst_rs` (5 copies) | `01_research/src/hurst.py` | **MERGE** en 1 seule fonction canonique |
| `garch_rolling` (`backtest_hurst.py:141`) | `01_research/src/garch.py` | MOVE |
| `time_series_analysis_for_quant_finance.ipynb` | `01_research/notebooks/` | MOVE |
| `ES 5ANS DATA/`, `NQ 5ANS DATA/` | `01_research/data/raw/` | MOVE (data dirs) ou symlink |

### 8.2 Couche BACKTEST (`02_backtest/`)

| Source actuelle | Destination | Action |
|-----------------|-------------|--------|
| `backtest_hurst.py` (legacy) | — | **DELETE** (après confirmation que `pages/5_Backtest.py` couvre tout) |
| `pages/5_Backtest.py` (logique) | `02_backtest/src/hurst_mr.py` + notebook | **SPLIT** : logique pure → src, UI → page Streamlit minimaliste |
| `backtest_models.py` | `02_backtest/src/multi_model.py` + notebook | SPLIT |
| `crypto_swing_backtest.py` | `02_backtest/src/crypto_swing.py` | REFACTOR |
| `pages/7_VR_MR.py` | `02_backtest/src/variance_ratio.py` | SPLIT |
| `quant_v10/` (modules + orchestrator + tests + validation) | `02_backtest/v10/` (préserver structure interne) | MOVE |
| `quant_v10/reports/` | `02_backtest/reports/` | MOVE |

### 8.3 Couche SPEC (`03_spec/`)

| Source actuelle | Destination | Action |
|-----------------|-------------|--------|
| **CRÉER** `hurst_mr_v9_spec.md` | `03_spec/hurst_mr_v9_spec.md` | **NEW** — codifier les 8 params champion + baseline JSON |
| **CRÉER** `config/strategies/hurst_mr_v9.yaml` | `03_spec/configs/hurst_mr_v9.yaml` | **NEW** — params externalisés |
| **CRÉER** baseline JSON | `03_spec/baselines/hurst_mr_v9_5y.json` | **NEW** — figer trades_df + metrics |
| `SYSTEM_PLAN.md` | `03_spec/archive/strategy_garch_hmm_kalman_v0.md` | MOVE (archive) |
| `learning/25_hurst_mr.md` | `03_spec/pedagogy/hurst_mr_v9.md` | MOVE (pédagogie) |

### 8.4 Couche LIVE (`04_live/`)

| Source actuelle | Destination | Action |
|-----------------|-------------|--------|
| `ninjatrader/HurstMR_Apex.cs` | `04_live/ninjascript/HurstMR_Apex.cs` | MOVE + **nettoyer header docstring** |
| `ninjatrader/HurstMR_Apex_v10.cs` | `04_live/ninjascript/HurstMR_Apex_v10.cs` | MOVE |
| `RithmicBridge.cs` (racine) | `04_live/ninjascript/RithmicBridge.cs` | MOVE |
| `quantower/HurstMR_Apex_Quantower.cs` | `04_live/quantower/HurstMR_Apex_Quantower.cs` | MOVE |
| `quantower/QuantowerBridge.cs` | `04_live/quantower/QuantowerBridge.cs` | MOVE |
| `live_signal.py` | `04_live/scripts/live_signal_dxfeed.py` | REFACTOR (dépend de Hurst module commun) |
| `live_signal_dash.py` | `04_live/streamlit/live_signal_dash.py` | **SPLIT** : logique → `04_live/src/`, UI → `05_app/pages/` |
| `alert_cron.py` | `04_live/cron/sol_alert.py` | MOVE |
| `.github/workflows/sol_alert.yml` | reste en `.github/workflows/` | KEEP |
| `quantower_setup.py` | `04_live/quantower/setup_page.py` | REFACTOR |

### 8.5 Couche APP (`05_app/`)

| Source actuelle | Destination | Action |
|-----------------|-------------|--------|
| `app_learning.py` | `05_app/app.py` | MOVE (renommer) |
| `Accueil.py` | `05_app/pages/0_Accueil.py` | MOVE |
| `auth.py` | `05_app/auth.py` | MOVE |
| `config.py` | `05_app/config.py` | MOVE (ou splitter en `config/paths.py` + `05_app/config.py`) |
| `styles.py` (1269 l.) | `05_app/styles.py` | KEEP en place, mais **envisager split** : `colors.py` / `typography.py` / `css.py` |
| `charts.py` (2157 l.) | `05_app/components/charts.py` | **SPLIT par thème** (hurst, regime, kelly, kalman...) |
| `pages/_home.py` | `05_app/pages/_home.py` | MOVE |
| `pages/1_Demarrage.py` à `pages/Apex_Rules.py` | `05_app/pages/` | MOVE + **transformer les 6 exec() en imports propres** |
| `pages/3_Live_Signal.py`, `pages/6_Multi_Model.py`, `pages/9_BTC_DCA.py`, `pages/Crypto_Live_SOL.py`, `pages/Crypto_Swing.py`, `pages/Quantower_Setup.py` | `05_app/pages/` | **REFACTOR — supprimer exec(), importer la logique des modules `02_backtest/` ou `04_live/`** |
| `btc_dca.py` | `02_backtest/src/btc_dca.py` (logique) + page mince | SPLIT |
| `crypto_live_sol.py` | `04_live/src/crypto_sol.py` (logique) + page mince | SPLIT |

### 8.6 Couche JOURNAL (`06_journal/`)

| Source actuelle | Destination | Action |
|-----------------|-------------|--------|
| `sol_journal.db` | `06_journal/db.sqlite` | MOVE (renommer) |
| `pages/4_Journal.py` (logique SQLite) | `06_journal/src/journal.py` + page mince dans `05_app/pages/` | SPLIT |
| **CRÉER** schémas SQL | `06_journal/schemas/` | NEW |

### 8.7 Tests (`tests/`)

| Source actuelle | Destination | Action |
|-----------------|-------------|--------|
| `quant_v10/tests/test_*.py` (9 fichiers) | `tests/v10/` (ou rester dans `02_backtest/v10/tests/`) | À DÉCIDER en Phase 2 — préserver liens imports |
| **CRÉER** `tests/test_hurst.py` | `tests/test_hurst.py` | **NEW** — couvre la fonction Hurst canonique |
| **CRÉER** `tests/test_apex_simulator.py` | `tests/test_apex_simulator.py` | **NEW** — trailing DD intra |
| **CRÉER** `tests/test_v9_regression.py` | `tests/test_v9_regression.py` | **NEW** — vérifie PF 2.29 ±0.01 etc. |

### 8.8 Configuration / build

| Source actuelle | Destination | Action |
|-----------------|-------------|--------|
| `requirements.txt` | racine | KEEP, **audit + compléter** en Phase 2 |
| **CRÉER** `requirements-dev.txt` | racine | NEW (pytest, black, ruff) |
| `.gitignore` | racine | KEEP (déjà mis à jour étape 3) |
| `.streamlit/` | racine | KEEP |
| `.github/` | racine | KEEP |
| `package.json`, `package-lock.json`, `node_modules/` | — | **VÉRIFIER usage** : présence d'un bridge JS DXFeed ? Si pas utilisé, DELETE. |
| `README.md` (vide) | racine | **CRÉER contenu** |
| **CRÉER** `pyproject.toml` (optionnel) | racine | Pour `black`/`ruff` config |

### 8.9 Suppressions candidates (à confirmer par BB)

| Fichier | Motif |
|---------|-------|
| `backtest_hurst.py` (racine, 1470 l.) | Doublon legacy de `pages/5_Backtest.py` avec defaults pre-champion |
| `.checklist.json`, `.progress.json`, `.watched.json` | State files vides ou quasi vides — utilité ? |
| `node_modules/` (si non utilisé) | Vérifier d'abord si `package.json` sert |
| `.devcontainer/` | Si pas utilisé activement |

---

## 9. Mémoire associée (`project_python_backtest_illusion.md`)

> **Attention** : ta memory mentionne *"Le backtest Python utilise close-only, manque les wicks 1-min. v9 et v10 = catastrophe en NT réaliste. Ne pas déployer en l'état."*

Cette alerte est cohérente avec le code observé : `run_hurst_backtest` (`backtest_hurst.py:218+`) prend `closes`, `highs`, `lows` en entrée — donc les wicks **sont** disponibles. Mais il faut vérifier en Phase 2 que la logique de TP/SL utilise bien `highs/lows` intra-bar et pas seulement `close[i]`. Si elle utilise close, ça expliquerait la divergence Python ↔ NT8 observée.

---

## 10. Checklist Phase 2 — points à valider avec BB avant de proposer le plan de migration

1. ❓ **Baseline v9 reproductible** : peux-tu re-générer un `hurst_mr_v9_5y.json` baseline depuis `pages/5_Backtest.py` avec les defaults actuels (sliders en position champion v9), pour servir de référence absolue ?
2. ❓ **`backtest_hurst.py` racine** : confirmer qu'il peut être supprimé (legacy) au profit de `pages/5_Backtest.py`.
3. ❓ **`SYSTEM_PLAN.md`** : archiver dans `03_spec/archive/` ou supprimer ?
4. ❓ **`charts.py` (2157 l.)** : split par module pédagogique ou laisser monolithique pour l'instant ?
5. ❓ **`styles.py` (1269 l.)** : idem, garder ou splitter ?
6. ❓ **node_modules + package.json** : utilisés (bridge JS DXFeed) ou héritage ?
7. ❓ **`learning/` actuel vs `03_spec/pedagogy/`** : tout le contenu pédagogique part en spec/pedagogy, ou on garde un dossier `learning/` distinct ?
8. ❓ **Tests v10** : laisser dans `02_backtest/v10/tests/` (auto-contenu) ou regrouper dans `tests/` racine ?
9. ❓ **Header docstring `HurstMR_Apex.cs`** : tu veux que je le mette à jour avec les chiffres champion 2026-05-12 dans une étape dédiée ?
10. ❓ **Look-ahead `shift(-1)` rollover** : on garde le pattern actuel (rollover skip avec lookahead 1 jour, acceptable car dates calendaires) ou on refactorise sans lookahead ?

---

## 11. Prochaines actions (Phase 2)

Une fois que tu valides ce rapport (et arbitre les 10 points §10), je rédige `MIGRATION_PLAN.md` avec :
- Plan d'exécution numéroté en ~25-40 étapes
- Pour chaque étape : action / fichiers / risque / test de non-régression
- **Étape 0 obligatoire** : générer `hurst_mr_v9_5y.json` baseline + figer test de régression
- Ordre : structure de dossiers → moves zéro impact → refactor imports → externalisation YAML → cleanup Streamlit → tests → finalisation
- Estimation de durée par étape
- Points de checkpoint utilisateur explicites

**STOP — j'attends ta validation de l'audit et tes réponses aux 10 points avant de produire le `MIGRATION_PLAN.md`.**
