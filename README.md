# Quant Trading — MNQ Apex Trader Funding $50K Eval

> Système de recherche et de trading systématique sur **MNQ** (Micro Nasdaq futures CME) pour le compte d'évaluation **Apex Trader Funding $50K**.

**Statut au 2026-05-14** : Phase de recherche d'edge **close**. Stratégie `HURST_MR v9` figée comme référence repo mais **NON déployable Apex** en l'état (NT8 Strategy Analyzer = PF 1.02 / DD -$22K — voir `03_spec/hurst_mr_v9_spec.md`). Pas de stratégie validée live actuellement.

---

## Architecture 3 couches

```
┌─────────────────────────────────────────────┐
│  COUCHE 1 — RECHERCHE & ÉTUDE                │
│  Python + JupyterLab + VectorBT              │
│  → Trouver ce qui marche                     │
│  ➤  01_research/                             │
└──────────────────────┬──────────────────────┘
                       ↓
┌─────────────────────────────────────────────┐
│  COUCHE 2 — VALIDATION                       │
│  Python (backtrader) + NinjaScript SA       │
│  → Vérifier que ça tiendra en réel           │
│  ➤  02_validation/                           │
└──────────────────────┬──────────────────────┘
                       ↓
┌─────────────────────────────────────────────┐
│  COUCHE 3 — LIVE FULL AUTO                   │
│  C# / NinjaScript sur NinjaTrader + Rithmic │
│  → Exécution réelle sur Apex                 │
│  ➤  03_live/                                 │
└─────────────────────────────────────────────┘
```

## Structure du repo

```
.
├── 01_research/                  # COUCHE 1
│   ├── notebooks/                # Jupyter (.ipynb)
│   ├── src/                      # Fonctions réutilisables (source de vérité)
│   │   ├── config.py             # Splits LdP + Apex rules + params v9
│   │   ├── instruments.py        # Specs MNQ/NQ/ES
│   │   ├── data_loader.py        # Loader Databento .csv.zst
│   │   ├── hurst.py              # Exposant Hurst R/S
│   │   ├── features.py           # Z-score, RSI, ORB, GARCH
│   │   ├── signals.py            # MR/RSI/ORB signals (Apex-compliant)
│   │   └── backtest.py           # Backtester + simulate_apex_cycle
│   ├── data/raw/                 # CSV/Parquet (gitignored)
│   ├── outputs/                  # Artefacts recherche (CSV, PNG, logs)
│   └── run_*.py                  # Scripts mini-validations (phase recherche)
│
├── 02_validation/                # COUCHE 2
│   ├── notebooks/                # Backtrader event-driven (TODO)
│   ├── src/                      # Backtester Python NT8-compatible (TODO)
│   ├── reports/                  # Rapports QuantStats + LdP checks
│   └── v10/                      # Sprint v10 (Lee-Mykland, HAR-RV, GZ, MRJD, MF-DFA)
│
├── 03_live/                      # COUCHE 3
│   ├── ninjascript/              # HurstMR_Apex.cs (champion v9), v10, RithmicBridge
│   └── quantower/                # Port Quantower
│
├── 03_spec/                      # Specs écrites
│   ├── hurst_mr_v9_spec.md       # Config champion v9 figée
│   ├── strategy_diagnosis_v9_csharp.md   # 5 mismatchs Python vs NT8 SA
│   └── baselines/                # Baselines historiques
│
├── docs/                         # Documentation pédagogique
│   ├── 04_garch.md, 05_HMM, 06_Kalman, 25_hurst_mr.md, etc.
│   └── archive/                  # Anciens markdowns
│
├── ES 5ANS DATA/, NQ 5ANS DATA/  # Data Databento (gitignored, ~100GB)
│
├── AUDIT_REPORT.md               # Cartographie initiale du repo (réf historique)
├── CLAUDE.md                     # Contexte projet pour Claude Code
├── README.md                     # Ce fichier
├── requirements.txt              # Dépendances runtime
├── requirements-dev.txt          # + Dépendances dev (pytest, black, ruff, jupyter)
├── pyproject.toml                # Config black + ruff + pytest
└── .gitignore
```

## Setup

### Prérequis
- Python ≥ 3.10 (testé sur Python 3.14.2)
- NinjaTrader 8 (pour Couche 3)
- Compte Databento (pour récupérer les CSV 1-minute MNQ/NQ/ES — déjà téléchargés localement)

### Installation Python
```bash
# Production (runtime recherche + validation)
pip install -r requirements.txt

# Dev (avec Jupyter + tests + formatting)
pip install -r requirements-dev.txt
```

### Vérification import
```bash
cd 01_research
python -c "
from src.hurst import hurst_rs
from src.data_loader import load_continuous
from src.signals import signal_mr_zscore
from src.backtest import backtest_apex
print('OK')
"
```

### Lancement Jupyter
```bash
jupyter lab
# Naviguer vers 01_research/notebooks/
```

## Workflow standard

1. **Recherche (Couche 1)** : exploration dans Jupyter, utilisation des modules `01_research/src/`. Hypothèses, features engineering, signaux candidats.
2. **Validation (Couche 2)** : backtester tick-realistic dans `02_validation/src/` (wicks intra-bar obligatoire), méthodologie López de Prado (CPCV + DSR + PBO via `02_validation/v10/validation/`).
3. **Spec écrite (`03_spec/`)** : config figée, chiffres réels, hypothèses, checklist validation.
4. **Implémentation NinjaScript (`03_live/ninjascript/`)** : port C# de la config validée.
5. **Backtest NT8 Strategy Analyzer** : cross-validation Python ↔ NT8 SA, écart < 15% obligatoire.
6. **Sim live démo NT8** : minimum 2 semaines avant tout déploiement Apex.
7. **Live Apex** : seulement si tous les checks passent (cf. `CLAUDE.md` Checklist pré-déploiement).

## Règles Apex Eval $50K (cf. `CLAUDE.md` §"Règles Apex")

| Règle | Valeur |
|-------|--------|
| Profit Target | $3,000 |
| Trailing DD | $2,000 |
| Daily Loss Limit | $1,000 |
| Max contrats mini (NQ, ES, etc.) | 10 |
| Max contrats micro (MNQ, MES, etc.) | 40 |
| Flat obligatoire | avant 16h NY (chaque jour) |
| Durée max challenge | 1 mois |

Tout backtester doit simuler ces contraintes intra-day (force-flat 15:59 NY + daily limit + trailing DD).

## Historique récent

- **2026-05-14** : Restructuration repo 3 couches. Suppression Streamlit. Spec v9 figée. Phase recherche d'edge close.
- **2026-05-13** : Backtest NT8 SA réel sur HurstMR_Apex.cs → PF 1.02 / DD -$22K → v9 non déployable Apex. Pivot vers recherche d'edge alternatif (échec, voir `AUDIT_REPORT.md` + `01_research/outputs/`).
- **2026-05-12** : Config "champion v9" Hurst_MR figée (chiffres Python invalidés depuis).
- **2026-04-15** : Migration de 4PropTrader vers Apex Trader Funding.

## Documentation

- `CLAUDE.md` : contexte complet pour Claude Code (assistant IA), inclut profil opérateur, règles Apex, anti-patterns, références acceptées.
- `03_spec/hurst_mr_v9_spec.md` : spec officielle config champion v9.
- `03_spec/strategy_diagnosis_v9_csharp.md` : diagnostic des écarts Python ↔ NT8 SA.
- `AUDIT_REPORT.md` : cartographie initiale du repo (référence historique pré-restructuration).
- `docs/` : markdowns pédagogiques (Hurst, HMM, Kalman, GARCH, Kelly, trading metrics) basés sur Quant Guild Library de Roman Paolucci.
