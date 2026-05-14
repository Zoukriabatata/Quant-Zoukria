# Gauntlet — Plan 1 : Le cœur backtest PA EOD — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construire le socle du gauntlet de validation : un simulateur de compte Apex $50K PA EOD fidèle, et un backtest event-driven qui tourne dessus.

**Architecture:** Un package `02_validation/gauntlet/`. Les constantes PA EOD (`pa_rules`), l'interface enfichable `Hypothesis`, les splits López de Prado (`splits`), le simulateur de compte stateful (`pa_account` — DD EOD trailing, tiers, DLL), et le backtest event-driven (`backtest`) qui fait avancer le compte jour par jour en simulant les trades. TDD strict, données synthétiques.

**Tech Stack:** Python 3.10+, pandas, numpy, pytest. Réutilise `01_research/src/` (specs instruments, splits) mais le simulateur de compte et le backtest sont neufs (PA-correct, ≠ le `backtest_apex` Eval-ish de la Couche 1).

**Spec de référence:** `docs/superpowers/specs/2026-05-14-gauntlet-validation-design.md`

---

## Note pédagogique (préférence BB — apprendre au fil du projet)

BB veut **comprendre** ce qui est codé, pas juste recevoir un livrable. Chaque task de ce plan inclut une courte **explication "Pourquoi"** : le concept quant ou le choix de design derrière le code. L'implémenteur DOIT garder ces explications dans les messages de rapport (ne pas les supprimer comme du commentaire superflu).

---

## File Structure

| Fichier | Responsabilité | Task |
|---|---|---|
| `02_validation/gauntlet/__init__.py` | marqueur de package (vide) | 1 |
| `02_validation/gauntlet/conftest.py` | met `02_validation/` et `01_research/` sur `sys.path` pour pytest | 1 |
| `02_validation/gauntlet/tests/__init__.py` | marqueur (vide) | 1 |
| `pyproject.toml` | ajoute `02_validation/gauntlet/tests` à `testpaths` | 1 |
| `02_validation/gauntlet/pa_rules.py` | constantes PA EOD 50K + `tier_for_balance()` | 2 |
| `02_validation/gauntlet/hypothesis.py` | dataclass `Hypothesis` (interface enfichable) | 3 |
| `02_validation/gauntlet/splits.py` | splits Train/Valid/Holdout + embargo | 4 |
| `02_validation/gauntlet/pa_account.py` | `PaAccount` — simulateur de compte PA EOD stateful | 5 |
| `02_validation/gauntlet/backtest.py` | `backtest_pa()` — backtest event-driven sur `PaAccount` | 6 |
| `02_validation/gauntlet/tests/test_*.py` | tests unitaires par module | 2-7 |

---

### Task 1 : Infrastructure pytest du package `gauntlet`

**Files:**
- Create: `02_validation/gauntlet/__init__.py`
- Create: `02_validation/gauntlet/tests/__init__.py`
- Create: `02_validation/gauntlet/conftest.py`
- Create: `02_validation/gauntlet/tests/test_smoke.py`
- Modify: `pyproject.toml` (section `[tool.pytest.ini_options]`)

**Pourquoi :** le gauntlet est un package Python. Pour que `import gauntlet.pa_rules` marche depuis les tests, `02_validation/` doit être sur le `sys.path` ; et le gauntlet importe aussi `01_research/src/`, donc `01_research/` aussi. Le `conftest.py` fait ça. C'est de la plomberie — une fois en place on n'y touche plus.

- [ ] **Step 1: Créer le marqueur de package**

Create `02_validation/gauntlet/__init__.py` (fichier vide, 0 octet).

- [ ] **Step 2: Créer le marqueur du dossier de tests**

Create `02_validation/gauntlet/tests/__init__.py` (fichier vide, 0 octet).

- [ ] **Step 3: Créer le conftest qui configure sys.path**

Create `02_validation/gauntlet/conftest.py` :

```python
"""Met 02_validation/ et 01_research/ sur sys.path pour les imports du gauntlet.

- 02_validation/ sur le path  -> `import gauntlet.pa_rules` etc.
- 01_research/ sur le path    -> `import src.instruments`, `import src.config` etc.
"""
import sys
from pathlib import Path

_GAUNTLET = Path(__file__).resolve().parent           # 02_validation/gauntlet
sys.path.insert(0, str(_GAUNTLET.parent))             # 02_validation/
sys.path.insert(0, str(_GAUNTLET.parents[1] / "01_research"))  # 01_research/
```

- [ ] **Step 4: Créer un test sentinelle**

Create `02_validation/gauntlet/tests/test_smoke.py` :

```python
"""Sentinelle : le package gauntlet et la config 01_research sont importables."""


def test_gauntlet_package_importable():
    import gauntlet  # noqa: F401


def test_research_config_importable():
    from src.config import TRAIN_START, HOLDOUT_END  # noqa: F401
```

- [ ] **Step 5: Ajouter le dossier de tests à pytest**

Modify `pyproject.toml`, section `[tool.pytest.ini_options]` — remplacer la ligne `testpaths` (actuellement `testpaths = ["01_research/tests", "02_validation/v10/tests", "tests"]`) par :

```toml
testpaths = ["01_research/tests", "02_validation/gauntlet/tests", "02_validation/v10/tests", "tests"]
```

- [ ] **Step 6: Lancer le test sentinelle — il doit PASSER**

Run: `cd "C:/Users/ryadb/OneDrive/QUANT MATHS"; python -m pytest 02_validation/gauntlet/tests/test_smoke.py -v`
Expected: PASS — 2 tests passés. (Si `import gauntlet` ou `from src.config` échoue, le `sys.path` du conftest est mal configuré.)

- [ ] **Step 7: Commit**

```bash
git add 02_validation/gauntlet/__init__.py 02_validation/gauntlet/tests/__init__.py 02_validation/gauntlet/conftest.py 02_validation/gauntlet/tests/test_smoke.py pyproject.toml
git commit -m "feat(gauntlet): infra pytest du package gauntlet"
```

---

### Task 2 : `pa_rules.py` — constantes PA EOD + `tier_for_balance`

**Files:**
- Create: `02_validation/gauntlet/pa_rules.py`
- Create: `02_validation/gauntlet/tests/test_pa_rules.py`

**Pourquoi :** un compte Apex $50K PA EOD a des règles chiffrées précises (DD EOD $2,000, lock à $50,100, tiers de scaling). On les centralise dans un module de constantes — une seule source de vérité. `tier_for_balance` traduit une balance EOD en (niveau, contrats max, daily loss limit) : c'est le système de "scaling" d'Apex — plus le compte grossit, plus on peut trader gros. Le `01_research/src/config.py` a encore les vieilles constantes Eval (périmées) — le gauntlet n'utilise QUE `pa_rules`.

- [ ] **Step 1: Écrire les tests qui échouent**

Create `02_validation/gauntlet/tests/test_pa_rules.py` :

```python
"""Tests de pa_rules : constantes PA EOD 50K + tier_for_balance."""
from gauntlet.pa_rules import (
    ACCOUNT_SIZE, EOD_DD, EOD_THRESHOLD_INITIAL, EOD_THRESHOLD_LOCK,
    tier_for_balance,
)


def test_constantes_de_base():
    assert ACCOUNT_SIZE == 50_000.0
    assert EOD_DD == 2_000.0
    assert EOD_THRESHOLD_INITIAL == 48_000.0   # 50_000 - 2_000
    assert EOD_THRESHOLD_LOCK == 50_100.0      # 50_000 + 100


def test_tier_l1_balance_de_depart():
    # balance 50_000 -> Level 1 : 2 contrats std, DLL $1_000
    level, max_ctr, dll = tier_for_balance(50_000.0)
    assert level == 1
    assert max_ctr == 2
    assert dll == 1_000.0


def test_tier_l1_floor_sous_50k():
    # sous 50_000 -> plancher L1 (le tier ne descend jamais sous L1)
    level, max_ctr, dll = tier_for_balance(48_500.0)
    assert (level, max_ctr, dll) == (1, 2, 1_000.0)


def test_tier_l2():
    # balance 51_500 (profit +1_500) -> Level 2 : 3 contrats, DLL $1_000
    assert tier_for_balance(51_500.0) == (2, 3, 1_000.0)


def test_tier_l3():
    # balance 53_000 (profit +3_000) -> Level 3 : 4 contrats, DLL $2_000
    assert tier_for_balance(53_000.0) == (3, 4, 2_000.0)


def test_tier_l4():
    # balance 56_000 (profit +6_000) -> Level 4 : 4 contrats, DLL $3_000
    assert tier_for_balance(56_000.0) == (4, 4, 3_000.0)


def test_tier_frontiere_l1_l2():
    # 51_499 -> encore L1 ; 51_500 -> L2
    assert tier_for_balance(51_499.0)[0] == 1
    assert tier_for_balance(51_500.0)[0] == 2
```

- [ ] **Step 2: Lancer les tests — ils doivent ÉCHOUER**

Run: `cd "C:/Users/ryadb/OneDrive/QUANT MATHS"; python -m pytest 02_validation/gauntlet/tests/test_pa_rules.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'gauntlet.pa_rules'`

- [ ] **Step 3: Implémenter `pa_rules.py`**

Create `02_validation/gauntlet/pa_rules.py` :

```python
"""Constantes du compte Apex $50K PA EOD. Source : help-center Apex, vérifié 2026-05-14.

Remplace les constantes Apex Eval périmées de 01_research/src/config.py (qui restent
pour la Couche 1 recherche). Le gauntlet utilise UNIQUEMENT pa_rules.
"""
from __future__ import annotations

# ── Compte ──────────────────────────────────────────────────────────
ACCOUNT_SIZE = 50_000.0
EOD_DD = 2_000.0                                # drawdown EOD max
EOD_THRESHOLD_INITIAL = ACCOUNT_SIZE - EOD_DD   # 48_000.0 — seuil au jour 1
EOD_THRESHOLD_LOCK = ACCOUNT_SIZE + 100.0       # 50_100.0 — seuil figé une fois atteint

# ── Tiers de scaling ────────────────────────────────────────────────
# (seuil_balance_EOD, contrats_std_max, daily_loss_limit). Le tier d'une balance =
# le plus haut tier dont le seuil est <= balance. Plancher L1 (jamais en dessous).
TIERS = [
    (50_000.0, 2, 1_000.0),   # L1 : balance >= 50_000
    (51_500.0, 3, 1_000.0),   # L2 : balance >= 51_500
    (53_000.0, 4, 2_000.0),   # L3 : balance >= 53_000
    (56_000.0, 4, 3_000.0),   # L4 : balance >= 56_000
]

# ── Contrats ────────────────────────────────────────────────────────
MICROS_PER_STANDARD = 10        # 10 contrats micro (MNQ) = 1 contrat standard (NQ)

# ── Force-flat (règle perso BB) ─────────────────────────────────────
FORCE_FLAT_NY = (15, 55)        # (heure, minute) America/New_York

# ── Inactivité ──────────────────────────────────────────────────────
INACTIVITY_MIN_GREEN_DAYS = 2       # jours à >= seuil de profit, par fenêtre glissante
INACTIVITY_GREEN_THRESHOLD = 50.0   # $ net pour qu'un jour "compte"
INACTIVITY_WINDOW_DAYS = 30         # fenêtre glissante (jours calendaires)


def tier_for_balance(balance: float) -> tuple[int, int, float]:
    """Retourne (level, contrats_std_max, daily_loss_limit) pour une balance EOD.

    Plancher L1 : une balance sous 50_000 reste au Level 1.
    """
    level, max_ctr, dll = 1, TIERS[0][1], TIERS[0][2]
    for i, (threshold, ctr, d) in enumerate(TIERS, start=1):
        if balance >= threshold:
            level, max_ctr, dll = i, ctr, d
        else:
            break
    return level, max_ctr, dll
```

- [ ] **Step 4: Lancer les tests — ils doivent PASSER**

Run: `cd "C:/Users/ryadb/OneDrive/QUANT MATHS"; python -m pytest 02_validation/gauntlet/tests/test_pa_rules.py -v`
Expected: PASS — 7 tests passés.

- [ ] **Step 5: Commit**

```bash
git add 02_validation/gauntlet/pa_rules.py 02_validation/gauntlet/tests/test_pa_rules.py
git commit -m "feat(gauntlet): pa_rules - constantes PA EOD 50K + tier_for_balance"
```

---

### Task 3 : `hypothesis.py` — l'interface `Hypothesis`

**Files:**
- Create: `02_validation/gauntlet/hypothesis.py`
- Create: `02_validation/gauntlet/tests/test_hypothesis.py`

**Pourquoi :** le gauntlet juge des hypothèses. Une "hypothèse" doit être un objet standardisé et enfichable, sinon chaque test serait du code ad hoc (le piège dans lequel on est tombé jusqu'ici). La dataclass `Hypothesis` bundle : un nom, un instrument/timeframe, une fonction `build_variant(params)` qui produit le couple (signal, exit) pour un jeu de params, et une `param_grid` — la **petite grille délibérée** de params à tester. `n_trials = len(param_grid)` : ce compte sert plus tard au Deflated Sharpe (plus on teste de configs, plus on risque de trouver un edge par hasard — le DSR pénalise pour ça).

- [ ] **Step 1: Écrire les tests qui échouent**

Create `02_validation/gauntlet/tests/test_hypothesis.py` :

```python
"""Tests de l'interface Hypothesis."""
import pytest

from gauntlet.hypothesis import Hypothesis


def _dummy_build_variant(params):
    """build_variant minimal : retourne (signal_fn, exit_logic, backtest_kwargs)."""
    def signal_fn(df):
        return df
    def exit_logic(*args, **kwargs):
        return False, 0.0, ""
    return signal_fn, exit_logic, {"timeout_bars": params["timeout_bars"]}


def test_hypothesis_construction_et_n_trials():
    h = Hypothesis(
        name="dummy",
        description="hypothèse de test",
        instrument="MNQ",
        timeframe="5min",
        build_variant=_dummy_build_variant,
        param_grid=[{"timeout_bars": 12}, {"timeout_bars": 24}],
    )
    assert h.name == "dummy"
    assert h.instrument == "MNQ"
    assert h.n_trials == 2


def test_hypothesis_param_grid_vide_leve_erreur():
    with pytest.raises(ValueError):
        Hypothesis(
            name="vide", description="", instrument="MNQ", timeframe="5min",
            build_variant=_dummy_build_variant, param_grid=[],
        )


def test_hypothesis_build_variant_non_callable_leve_erreur():
    with pytest.raises(TypeError):
        Hypothesis(
            name="bad", description="", instrument="MNQ", timeframe="5min",
            build_variant="pas une fonction", param_grid=[{"timeout_bars": 12}],
        )
```

- [ ] **Step 2: Lancer les tests — ils doivent ÉCHOUER**

Run: `cd "C:/Users/ryadb/OneDrive/QUANT MATHS"; python -m pytest 02_validation/gauntlet/tests/test_hypothesis.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'gauntlet.hypothesis'`

- [ ] **Step 3: Implémenter `hypothesis.py`**

Create `02_validation/gauntlet/hypothesis.py` :

```python
"""L'interface Hypothesis : l'objet enfichable que le gauntlet juge."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass
class Hypothesis:
    """Une hypothèse de stratégie, prête à passer dans le gauntlet.

    Champs :
        name           : identifiant court (sert au nom du dossier d'output).
        description    : l'énoncé de l'hypothèse en une phrase.
        instrument     : clé dans INSTRUMENTS (ex. 'MNQ').
        timeframe      : règle de resampling pandas (ex. '5min').
        build_variant  : callable(params: dict) -> (signal_fn, exit_logic, backtest_kwargs).
                         Produit le couple signal/exit pour UN jeu de params.
        param_grid     : list[dict] — la petite grille délibérée de params à tester.
                         n_trials = len(param_grid), utilisé pour le Deflated Sharpe.
    """
    name: str
    description: str
    instrument: str
    timeframe: str
    build_variant: Callable
    param_grid: list

    def __post_init__(self):
        if not self.param_grid:
            raise ValueError(f"Hypothesis '{self.name}': param_grid est vide")
        if not callable(self.build_variant):
            raise TypeError(f"Hypothesis '{self.name}': build_variant doit être callable")

    @property
    def n_trials(self) -> int:
        """Nombre de variants testés — alimente la pénalité du Deflated Sharpe."""
        return len(self.param_grid)
```

- [ ] **Step 4: Lancer les tests — ils doivent PASSER**

Run: `cd "C:/Users/ryadb/OneDrive/QUANT MATHS"; python -m pytest 02_validation/gauntlet/tests/test_hypothesis.py -v`
Expected: PASS — 3 tests passés.

- [ ] **Step 5: Commit**

```bash
git add 02_validation/gauntlet/hypothesis.py 02_validation/gauntlet/tests/test_hypothesis.py
git commit -m "feat(gauntlet): hypothesis - interface Hypothesis enfichable"
```

---

### Task 4 : `splits.py` — splits Train/Valid/Holdout + embargo

**Files:**
- Create: `02_validation/gauntlet/splits.py`
- Create: `02_validation/gauntlet/tests/test_splits.py`

**Pourquoi :** en quant, on ne juge JAMAIS une stratégie sur les données qui ont servi à la régler — c'est de l'overfitting garanti. López de Prado impose de découper l'historique : **Train** (on règle dessus), **Valid** (on valide dessus, jamais vu pendant le réglage), **Holdout** (intouchable jusqu'au verdict final). L'**embargo** : on jette les dernières barres de chaque fenêtre, pour qu'un trade ouvert tout en fin de Train ne "fuite" pas son résultat dans le Valid (un trade dure plusieurs barres — sans embargo, sa fenêtre de vie chevauche la frontière). Les dates des splits sont déjà figées dans `01_research/src/config.py`.

- [ ] **Step 1: Écrire les tests qui échouent**

Create `02_validation/gauntlet/tests/test_splits.py` :

```python
"""Tests des splits Train/Valid/Holdout + embargo."""
import pandas as pd

from gauntlet.splits import split_train, split_valid, split_holdout


def _synthetic_df():
    """DataFrame horaire couvrant Train, Valid et Holdout (2021-05 -> 2026-05)."""
    idx = pd.date_range("2021-05-13", "2026-05-13", freq="1D", tz="UTC")
    return pd.DataFrame({"close": range(len(idx))}, index=idx)


def test_split_train_borne_les_dates():
    df = _synthetic_df()
    tr = split_train(df)
    assert tr.index.min() >= pd.Timestamp("2021-05-13", tz="UTC")
    assert tr.index.max() < pd.Timestamp("2024-05-13", tz="UTC")


def test_split_valid_borne_les_dates():
    df = _synthetic_df()
    va = split_valid(df)
    assert va.index.min() >= pd.Timestamp("2024-05-13", tz="UTC")
    assert va.index.max() < pd.Timestamp("2025-05-13", tz="UTC")


def test_split_holdout_borne_les_dates():
    df = _synthetic_df()
    ho = split_holdout(df)
    assert ho.index.min() >= pd.Timestamp("2025-05-13", tz="UTC")
    assert ho.index.max() < pd.Timestamp("2026-05-13", tz="UTC")


def test_splits_ne_se_chevauchent_pas():
    df = _synthetic_df()
    tr, va, ho = split_train(df), split_valid(df), split_holdout(df)
    assert tr.index.max() < va.index.min()
    assert va.index.max() < ho.index.min()


def test_embargo_jette_les_dernieres_barres():
    df = _synthetic_df()
    tr_full = split_train(df)
    tr_embargo = split_train(df, embargo_bars=5)
    assert len(tr_embargo) == len(tr_full) - 5
    assert tr_embargo.index.max() < tr_full.index.max()
```

- [ ] **Step 2: Lancer les tests — ils doivent ÉCHOUER**

Run: `cd "C:/Users/ryadb/OneDrive/QUANT MATHS"; python -m pytest 02_validation/gauntlet/tests/test_splits.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'gauntlet.splits'`

- [ ] **Step 3: Implémenter `splits.py`**

Create `02_validation/gauntlet/splits.py` :

```python
"""Splits López de Prado : Train / Valid / Holdout, avec embargo.

Les dates sont figées dans 01_research/src/config.py. L'embargo jette les dernières
barres d'une fenêtre pour éviter qu'un trade ouvert près de la frontière "fuite" son
résultat dans la fenêtre suivante.
"""
from __future__ import annotations

import pandas as pd

from src.config import (
    TRAIN_START, TRAIN_END, VALID_START, VALID_END, HOLDOUT_START, HOLDOUT_END,
)


def _slice(df: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp,
           embargo_bars: int) -> pd.DataFrame:
    """Slice [start, end) puis jette les `embargo_bars` dernières barres."""
    s = df.loc[(df.index >= start) & (df.index < end)]
    if embargo_bars > 0:
        s = s.iloc[:-embargo_bars]
    return s.copy()


def split_train(df: pd.DataFrame, embargo_bars: int = 0) -> pd.DataFrame:
    """Fenêtre Train (2021-05-13 -> 2024-05-13)."""
    return _slice(df, TRAIN_START, TRAIN_END, embargo_bars)


def split_valid(df: pd.DataFrame, embargo_bars: int = 0) -> pd.DataFrame:
    """Fenêtre Valid (2024-05-13 -> 2025-05-13)."""
    return _slice(df, VALID_START, VALID_END, embargo_bars)


def split_holdout(df: pd.DataFrame, embargo_bars: int = 0) -> pd.DataFrame:
    """Fenêtre Holdout (2025-05-13 -> 2026-05-13) — intouchable jusqu'au verdict final.

    Note : partiellement contaminée par le grid-search du dual-config HurstMR (2026-05-14).
    """
    return _slice(df, HOLDOUT_START, HOLDOUT_END, embargo_bars)
```

- [ ] **Step 4: Lancer les tests — ils doivent PASSER**

Run: `cd "C:/Users/ryadb/OneDrive/QUANT MATHS"; python -m pytest 02_validation/gauntlet/tests/test_splits.py -v`
Expected: PASS — 5 tests passés.

- [ ] **Step 5: Commit**

```bash
git add 02_validation/gauntlet/splits.py 02_validation/gauntlet/tests/test_splits.py
git commit -m "feat(gauntlet): splits - Train/Valid/Holdout + embargo LdP"
```

---

### Task 5 : `pa_account.py` — le simulateur de compte PA EOD

**Files:**
- Create: `02_validation/gauntlet/pa_account.py`
- Create: `02_validation/gauntlet/tests/test_pa_account.py`

**Pourquoi :** c'est le **cœur du gauntlet** — un backtest qui ne simule pas les vraies règles du compte ne sert à rien (c'est ce qui a planté à chaque fois). `PaAccount` est une **machine à états** qui modélise le compte PA EOD :

- **Le seuil DD EOD** : le seuil de drawdown est recalculé à chaque clôture journalière comme `min(plus_haute_clôture − 2000, 50100)`. Il **monte** quand on fait des nouveaux plus-hauts en clôture, ne **descend jamais**, et se **fige à $50,100** une fois atteint. Si l'equity (PnL non réalisé inclus) **touche** ce seuil en intraday → compte **mort définitivement**.
- **Le tier** : recalculé à chaque clôture sur la balance ; fixe les contrats max et la DLL de la session suivante.
- **La DLL (Daily Loss Limit)** : si la perte du jour atteint la DLL du tier → journée stoppée, mais le **compte survit** et reprend le lendemain. C'est une mécanique **distincte** de la mort par seuil EOD.

`PaAccount` ne fait pas de backtest — il tient l'état du compte. Le `backtest.py` (Task 6) le fait avancer.

- [ ] **Step 1: Écrire les tests qui échouent**

Create `02_validation/gauntlet/tests/test_pa_account.py` :

```python
"""Tests du simulateur de compte PA EOD."""
from gauntlet.pa_account import PaAccount


def test_etat_initial():
    acc = PaAccount()
    assert acc.balance == 50_000.0
    assert acc.eod_threshold == 48_000.0       # 50_000 - 2_000
    assert acc.status == "alive"
    assert acc.tier == 1
    assert acc.max_contracts_std == 2
    assert acc.dll == 1_000.0
    assert acc.threshold_locked is False


def test_record_trade_met_a_jour_la_balance():
    acc = PaAccount()
    acc.record_trade(150.0)
    acc.record_trade(-50.0)
    assert acc.balance == 50_100.0


def test_end_session_fait_monter_le_seuil_sur_nouveau_plus_haut():
    acc = PaAccount()
    acc.record_trade(1_000.0)                  # balance 51_000
    acc.end_session("2026-01-02")
    # seuil = min(51_000 - 2_000, 50_100) = 49_000
    assert acc.eod_threshold == 49_000.0
    assert acc.highest_eod_close == 51_000.0


def test_end_session_seuil_ne_descend_jamais():
    acc = PaAccount()
    acc.record_trade(1_000.0); acc.end_session("2026-01-02")   # seuil 49_000
    acc.record_trade(-500.0); acc.end_session("2026-01-03")    # balance 50_500, clôture plus basse
    # le seuil reste à 49_000 (ne descend pas)
    assert acc.eod_threshold == 49_000.0
    assert acc.highest_eod_close == 51_000.0


def test_seuil_se_fige_a_50100():
    acc = PaAccount()
    acc.record_trade(2_100.0)                  # balance 52_100
    acc.end_session("2026-01-02")
    # min(52_100 - 2_000, 50_100) = 50_100 -> figé
    assert acc.eod_threshold == 50_100.0
    assert acc.threshold_locked is True
    # même après un gros gain, le seuil reste figé
    acc.record_trade(5_000.0); acc.end_session("2026-01-03")
    assert acc.eod_threshold == 50_100.0


def test_check_intraday_mort_si_equity_touche_le_seuil():
    acc = PaAccount()
    # seuil initial 48_000. equity (balance + PnL non réalisé) tombe à 48_000.
    res = acc.check_intraday(48_000.0)
    assert res == "dead"
    assert acc.status == "dead_eod"


def test_check_intraday_ok_si_equity_au_dessus():
    acc = PaAccount()
    assert acc.check_intraday(49_500.0) == "ok"
    assert acc.status == "alive"


def test_check_intraday_dll_pause_la_journee():
    acc = PaAccount()                          # DLL L1 = 1_000
    acc.start_session("2026-01-02")            # session_start_balance = 50_000
    # perte intraday de 1_000 -> equity 49_000 -> DLL touchée
    res = acc.check_intraday(49_000.0)
    assert res == "day_paused"
    assert acc.day_paused is True
    assert acc.status == "alive"               # le compte SURVIT
    assert acc.can_trade() is False


def test_dll_se_reset_a_la_session_suivante():
    acc = PaAccount()
    acc.start_session("2026-01-02")
    acc.check_intraday(49_000.0)               # DLL touchée
    assert acc.can_trade() is False
    acc.end_session("2026-01-02")
    acc.start_session("2026-01-03")            # nouvelle session
    assert acc.day_paused is False
    assert acc.can_trade() is True


def test_tier_monte_apres_une_bonne_cloture():
    acc = PaAccount()
    acc.record_trade(1_600.0)                  # balance 51_600 -> L2 au prochain tier-update
    acc.end_session("2026-01-02")
    assert acc.tier == 2
    assert acc.max_contracts_std == 3
    assert acc.dll == 1_000.0


def test_daily_history_enregistre_les_clotures():
    acc = PaAccount()
    acc.record_trade(300.0); acc.end_session("2026-01-02")
    acc.record_trade(-100.0); acc.end_session("2026-01-03")
    assert len(acc.daily_history) == 2
    assert acc.daily_history[0] == ("2026-01-02", 50_300.0, 1)
    assert acc.daily_history[1] == ("2026-01-03", 50_200.0, 1)
```

- [ ] **Step 2: Lancer les tests — ils doivent ÉCHOUER**

Run: `cd "C:/Users/ryadb/OneDrive/QUANT MATHS"; python -m pytest 02_validation/gauntlet/tests/test_pa_account.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'gauntlet.pa_account'`

- [ ] **Step 3: Implémenter `pa_account.py`**

Create `02_validation/gauntlet/pa_account.py` :

```python
"""PaAccount — simulateur de compte Apex $50K PA EOD (machine à états).

Deux mécaniques de risque DISTINCTES :
  - Seuil DD EOD : touché en intraday -> compte MORT (status 'dead_eod').
  - DLL          : touchée en intraday -> journée STOPPÉE, compte vivant.

PaAccount tient l'état ; il ne fait pas de backtest. Le backtest (backtest.py) le fait
avancer : record_trade() à chaque trade clos, check_intraday() à chaque barre,
start_session()/end_session() aux frontières de journée.
"""
from __future__ import annotations

from gauntlet.pa_rules import (
    ACCOUNT_SIZE, EOD_DD, EOD_THRESHOLD_INITIAL, EOD_THRESHOLD_LOCK, tier_for_balance,
)


class PaAccount:
    """État d'un compte PA EOD 50K, simulé dans le temps."""

    def __init__(self):
        self.balance: float = ACCOUNT_SIZE
        self.highest_eod_close: float = ACCOUNT_SIZE
        self.eod_threshold: float = EOD_THRESHOLD_INITIAL
        self.status: str = "alive"               # 'alive' | 'dead_eod'
        self.day_paused: bool = False            # DLL touchée dans la session courante
        self.session_start_balance: float = ACCOUNT_SIZE
        level, max_ctr, dll = tier_for_balance(self.balance)
        self.tier: int = level
        self.max_contracts_std: int = max_ctr
        self.dll: float = dll
        self.daily_history: list = []            # [(date, eod_close_balance, tier), ...]

    @property
    def threshold_locked(self) -> bool:
        """Le seuil EOD a-t-il atteint son plafond figé ($50,100) ?"""
        return self.eod_threshold >= EOD_THRESHOLD_LOCK

    def start_session(self, date) -> None:
        """Ouverture d'une journée de trading : reset l'état journalier."""
        if self.status == "alive":
            self.day_paused = False
        self.session_start_balance = self.balance

    def can_trade(self) -> bool:
        """True si on peut ouvrir un nouveau trade (compte vivant ET journée non stoppée)."""
        return self.status == "alive" and not self.day_paused

    def check_intraday(self, equity: float) -> str:
        """Vérifie les limites à partir de l'equity courante (balance + PnL non réalisé).

        Retourne 'dead' (seuil EOD touché -> compte mort), 'day_paused' (DLL touchée),
        ou 'ok'.
        """
        if self.status == "dead_eod":
            return "dead"
        # 1) Seuil DD EOD — touché = mort définitive
        if equity <= self.eod_threshold:
            self.status = "dead_eod"
            return "dead"
        # 2) Déjà en pause journée -> rien de plus à faire
        if self.day_paused:
            return "day_paused"
        # 3) Daily Loss Limit — perte du jour vs balance d'ouverture de session
        if (equity - self.session_start_balance) <= -self.dll:
            self.day_paused = True
            return "day_paused"
        return "ok"

    def record_trade(self, pnl: float) -> None:
        """Enregistre le P&L réalisé d'un trade clos."""
        self.balance += pnl

    def end_session(self, date) -> None:
        """Clôture d'une journée : met à jour le seuil EOD, le tier, l'historique.

        À appeler APRÈS le force-flat (toutes les positions sont closes -> balance = equity).
        """
        eod_close = self.balance
        if eod_close > self.highest_eod_close:
            self.highest_eod_close = eod_close
        # Le seuil trail la plus haute clôture, plafonné au lock. Monotone croissant car
        # highest_eod_close ne fait que monter -> le seuil "ne descend jamais".
        self.eod_threshold = min(self.highest_eod_close - EOD_DD, EOD_THRESHOLD_LOCK)
        # Tier pour la session suivante, calculé sur la balance de clôture.
        level, max_ctr, dll = tier_for_balance(eod_close)
        self.tier, self.max_contracts_std, self.dll = level, max_ctr, dll
        self.daily_history.append((date, eod_close, level))
```

- [ ] **Step 4: Lancer les tests — ils doivent PASSER**

Run: `cd "C:/Users/ryadb/OneDrive/QUANT MATHS"; python -m pytest 02_validation/gauntlet/tests/test_pa_account.py -v`
Expected: PASS — 11 tests passés.

- [ ] **Step 5: Commit**

```bash
git add 02_validation/gauntlet/pa_account.py 02_validation/gauntlet/tests/test_pa_account.py
git commit -m "feat(gauntlet): pa_account - simulateur de compte PA EOD (DD EOD, tiers, DLL)"
```

---

### Task 6 : `backtest.py` — le backtest event-driven sur `PaAccount`

**Files:**
- Create: `02_validation/gauntlet/backtest.py`
- Create: `02_validation/gauntlet/tests/test_backtest.py`

**Pourquoi :** `backtest_pa()` est la boucle qui simule le trading bar par bar et fait avancer le `PaAccount`. Différences clés vs un backtest naïf :

- **Friction obligatoire** : commission ($1.10 round-trip MNQ) + slippage (1 tick au SL) — toujours appliquées, aucun switch "off". Un backtest sans friction ment.
- **SL wick-aware** : le stop est vérifié sur le `low`/`high` de la barre (le wick), pas sur le `close` — sinon on "rate" des stops qui en réel se déclenchent.
- **Force-flat 15:55 NY** : aucune position ouverte au-delà.
- **Frontières de journée** : à chaque changement de date, `end_session()` puis `start_session()` — c'est là que le seuil EOD et le tier se recalculent.
- **Enforcement PA** : à chaque barre pendant un trade ouvert, on calcule l'equity intraday (balance + PnL non réalisé au **wick défavorable**, donc conservateur) et on appelle `check_intraday()`. Si 'dead' → trade liquidé, backtest STOPPÉ (compte mort). Si 'day_paused' → trade liquidé, journée finie.
- **Sizing tier** : le nombre de contrats = `max_contracts_std * 10` (MNQ micros). Pas de sizing fin pour l'instant (YAGNI — un `sizing_fn` configurable viendra si besoin).

L'`exit_logic` suit la convention existante de `01_research/src/backtest.py` (les `exit_logic_*` du sprint) : `(df, i, j, direction, entry_price, std_i, mid_i, or_high, or_low, or_range, sl_pts) -> (touched, price, reason)`.

- [ ] **Step 1: Écrire les tests qui échouent**

Create `02_validation/gauntlet/tests/test_backtest.py` :

```python
"""Tests du backtest event-driven sur PaAccount."""
import pandas as pd

from gauntlet.backtest import backtest_pa
from gauntlet.pa_account import PaAccount

# Specs MNQ minimales (cf. 01_research/src/instruments.py)
MNQ_SPECS = {
    "point_value": 2.00, "tick_size": 0.25, "commission_rt": 1.10,
    "sl_floor_pts": 5.0, "sl_cap_pts": 10.0,
}


def _exit_never(df, i, j, direction, entry_price, std_i, mid_i,
                or_high, or_low, or_range, sl_pts):
    """Exit logic qui ne déclenche jamais de TP — le trade sort par SL/force-flat/timeout."""
    return False, 0.0, ""


def _make_df(rows):
    """rows : list de dicts. Construit un df_signals indexé temps avec les colonnes requises."""
    idx = pd.date_range("2026-01-02 14:30", periods=len(rows), freq="5min", tz="America/New_York")
    df = pd.DataFrame(rows, index=idx)
    df["hour_ny"] = df.index.hour
    df["min_ny"] = df.index.minute
    df["date"] = df.index.date
    return df


def test_un_trade_long_gagnant_par_timeout():
    # signal LONG à la barre 0, le prix monte, sortie par timeout à la barre 2
    df = _make_df([
        {"signal": 1, "close": 100.0, "high": 100.5, "low": 99.5, "std": 4.0, "mid": 100.0},
        {"signal": 0, "close": 103.0, "high": 103.5, "low": 102.5, "std": 4.0, "mid": 100.0},
        {"signal": 0, "close": 105.0, "high": 105.5, "low": 104.5, "std": 4.0, "mid": 100.0},
    ])
    acc = PaAccount()
    trades = backtest_pa(df, _exit_never, MNQ_SPECS, acc, bar_size_min=5, timeout_bars=2)
    assert len(trades) == 1
    t = trades.iloc[0]
    assert t["direction"] == "LONG"
    assert t["exit_reason"] == "timeout"
    # gain brut = (105 - 100) * 2.00 * 20 contrats = 200 ; moins commission 1.10*20 = 22
    assert t["pnl_usd"] == 5.0 * 2.00 * 20 - 1.10 * 20
    assert acc.balance == 50_000.0 + t["pnl_usd"]


def test_sl_touche_sur_le_wick():
    # signal LONG ; std 4 -> sl_pts = max(5, min(10, 1.5*4)) = 6 -> sl_price = 94
    # barre 1 : low = 93.5 <= 94 -> SL touché sur le wick
    df = _make_df([
        {"signal": 1, "close": 100.0, "high": 100.5, "low": 99.5, "std": 4.0, "mid": 100.0},
        {"signal": 0, "close": 96.0, "high": 100.0, "low": 93.5, "std": 4.0, "mid": 100.0},
        {"signal": 0, "close": 96.0, "high": 96.5, "low": 95.5, "std": 4.0, "mid": 100.0},
    ])
    acc = PaAccount()
    trades = backtest_pa(df, _exit_never, MNQ_SPECS, acc, bar_size_min=5, timeout_bars=5)
    assert len(trades) == 1
    assert trades.iloc[0]["exit_reason"] == "SL"
    # exit_price = sl_price - slippage = 94 - 0.25 = 93.75 ; perte = (93.75-100)*2*20 - 1.10*20
    assert trades.iloc[0]["pnl_usd"] == (93.75 - 100.0) * 2.00 * 20 - 1.10 * 20


def test_force_flat_a_1555_ny():
    # entrée à 15:50 NY ; la barre de 15:55 close à 16:00 -> au-delà du cutoff -> force-flat
    idx = pd.to_datetime([
        "2026-01-02 15:50", "2026-01-02 15:55",
    ]).tz_localize("America/New_York")
    df = pd.DataFrame({
        "signal": [1, 0], "close": [100.0, 102.0], "high": [100.5, 102.5],
        "low": [99.5, 101.5], "std": [4.0, 4.0], "mid": [100.0, 100.0],
    }, index=idx)
    df["hour_ny"] = df.index.hour
    df["min_ny"] = df.index.minute
    df["date"] = df.index.date
    acc = PaAccount()
    trades = backtest_pa(df, _exit_never, MNQ_SPECS, acc, bar_size_min=5, timeout_bars=10)
    assert len(trades) == 1
    assert trades.iloc[0]["exit_reason"] == "force_flat"


def test_compte_mort_si_seuil_eod_touche():
    # signal LONG, 20 contrats MNQ. Le prix s'effondre : un mouvement adverse de 50 pts
    # = 50 * 2.00 * 20 = 2_000 de perte non réalisée -> equity 48_000 = seuil EOD initial.
    df = _make_df([
        {"signal": 1, "close": 100.0, "high": 100.5, "low": 99.5, "std": 4.0, "mid": 100.0},
        {"signal": 0, "close": 60.0, "high": 100.0, "low": 50.0, "std": 4.0, "mid": 100.0},
        {"signal": 0, "close": 60.0, "high": 60.5, "low": 59.5, "std": 4.0, "mid": 100.0},
    ])
    acc = PaAccount()
    trades = backtest_pa(df, _exit_never, MNQ_SPECS, acc, bar_size_min=5, timeout_bars=10)
    assert acc.status == "dead_eod"
    # le backtest s'arrête : le trade est liquidé, pas de trade après
    assert len(trades) == 1
    assert trades.iloc[0]["exit_reason"] == "account_dead"


def test_pas_de_trade_si_signal_apres_le_cutoff():
    # signal à 16:00 NY (barre qui close à 16:05) -> au-delà du cutoff -> aucune entrée
    idx = pd.to_datetime(["2026-01-02 16:00"]).tz_localize("America/New_York")
    df = pd.DataFrame({
        "signal": [1], "close": [100.0], "high": [100.5], "low": [99.5],
        "std": [4.0], "mid": [100.0],
    }, index=idx)
    df["hour_ny"] = df.index.hour
    df["min_ny"] = df.index.minute
    df["date"] = df.index.date
    acc = PaAccount()
    trades = backtest_pa(df, _exit_never, MNQ_SPECS, acc, bar_size_min=5, timeout_bars=10)
    assert len(trades) == 0
```

- [ ] **Step 2: Lancer les tests — ils doivent ÉCHOUER**

Run: `cd "C:/Users/ryadb/OneDrive/QUANT MATHS"; python -m pytest 02_validation/gauntlet/tests/test_backtest.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'gauntlet.backtest'`

- [ ] **Step 3: Implémenter `backtest.py`**

Create `02_validation/gauntlet/backtest.py` :

```python
"""backtest_pa — backtest event-driven sur un compte PA EOD.

Fait avancer un PaAccount jour par jour en simulant les trades d'une hypothèse.
Friction obligatoire, SL wick-aware, force-flat 15:55 NY, enforcement DD EOD + DLL.
"""
from __future__ import annotations

import pandas as pd

from gauntlet.pa_rules import FORCE_FLAT_NY, MICROS_PER_STANDARD


def backtest_pa(df_signals, exit_logic, instrument_specs, account,
                bar_size_min, timeout_bars, slippage_ticks=1, force_flat_ny=FORCE_FLAT_NY):
    """Backtest event-driven sur un compte PA EOD.

    Args:
        df_signals: DataFrame indexé temps, colonnes requises :
            signal (+1/-1/0), close, high, low, std, mid, hour_ny, min_ny, date.
        exit_logic: callable(df, i, j, direction, entry_price, std_i, mid_i,
                             or_high, or_low, or_range, sl_pts) -> (touched, price, reason).
        instrument_specs: dict avec point_value, tick_size, commission_rt,
                          sl_floor_pts, sl_cap_pts.
        account: PaAccount — simulé EN PLACE (modifié).
        bar_size_min: taille de barre en minutes.
        timeout_bars: liquidation MTM après N barres si ni SL ni TP.
        slippage_ticks: ticks de slippage défavorable au SL.
        force_flat_ny: (heure, minute) NY du force-flat.

    Returns:
        DataFrame de trades. Colonnes : entry_time, exit_time, direction, entry_price,
        exit_price, contracts, sl_pts, pts, pnl_usd, exit_reason, bars_held, date.
    """
    df = df_signals.reset_index().copy()
    n = len(df)
    bar_col = df.columns[0]  # nom de la colonne d'index temps après reset_index()

    point_value = instrument_specs["point_value"]
    tick_size = instrument_specs["tick_size"]
    commission_rt = instrument_specs["commission_rt"]
    sl_floor = instrument_specs["sl_floor_pts"]
    sl_cap = instrument_specs["sl_cap_pts"]
    slip_pts = slippage_ticks * tick_size
    force_flat_min = force_flat_ny[0] * 60 + force_flat_ny[1]

    trades = []
    if n == 0:
        return pd.DataFrame(trades)

    current_date = df.at[0, "date"]
    account.start_session(current_date)
    i = 0
    while i < n:
        # ── Frontière de journée ────────────────────────────────────
        if df.at[i, "date"] != current_date:
            account.end_session(current_date)
            if account.status == "dead_eod":
                break
            current_date = df.at[i, "date"]
            account.start_session(current_date)

        if not account.can_trade():
            i += 1
            continue

        sig = df.at[i, "signal"]
        std_i = df.at[i, "std"]
        if sig == 0 or pd.isna(std_i) or std_i <= 0:
            i += 1
            continue

        # Pas d'entrée si la barre close au-delà du cutoff force-flat.
        close_min_ny = df.at[i, "hour_ny"] * 60 + df.at[i, "min_ny"] + bar_size_min
        if close_min_ny > force_flat_min:
            i += 1
            continue

        direction = int(sig)
        entry_price = df.at[i, "close"]
        mid_i = df.at[i, "mid"] if pd.notna(df.at[i, "mid"]) else entry_price
        sl_pts = max(sl_floor, min(sl_cap, 1.5 * std_i))
        sl_price = entry_price - direction * sl_pts
        contracts = account.max_contracts_std * MICROS_PER_STANDARD

        exit_idx = min(i + timeout_bars, n - 1)
        exit_price = df.at[exit_idx, "close"]
        exit_reason = "timeout"

        for j in range(i + 1, min(n, i + timeout_bars + 1)):
            hj, lj, cj = df.at[j, "high"], df.at[j, "low"], df.at[j, "close"]

            # ── Enforcement PA : equity au wick DÉFAVORABLE (conservateur) ──
            adverse = lj if direction == 1 else hj
            unreal_worst = direction * (adverse - entry_price) * point_value * contracts
            state = account.check_intraday(account.balance + unreal_worst)
            if state == "dead":
                exit_price, exit_idx, exit_reason = cj, j, "account_dead"
                break
            if state == "day_paused":
                exit_price, exit_idx, exit_reason = cj, j, "dll_paused"
                break

            # ── SL wick-aware ───────────────────────────────────────
            sl_touched = (direction == 1 and lj <= sl_price) or (direction == -1 and hj >= sl_price)
            if sl_touched:
                exit_price = sl_price - direction * slip_pts
                exit_idx, exit_reason = j, "SL"
                break

            # ── Take-profit de l'hypothèse ──────────────────────────
            tp_touched, tp_price, tp_reason = exit_logic(
                df, i, j, direction, entry_price, std_i, mid_i,
                float("nan"), float("nan"), float("nan"), sl_pts,
            )
            if tp_touched:
                exit_price, exit_idx, exit_reason = tp_price, j, tp_reason
                break

            # ── Force-flat 15:55 NY ─────────────────────────────────
            close_min_j = df.at[j, "hour_ny"] * 60 + df.at[j, "min_ny"] + bar_size_min
            if df.at[j, "date"] == current_date and close_min_j > force_flat_min:
                exit_price, exit_idx, exit_reason = cj, j, "force_flat"
                break

        pts = direction * (exit_price - entry_price)
        pnl_usd = pts * point_value * contracts - commission_rt * contracts
        account.record_trade(pnl_usd)
        trades.append({
            "entry_time": df.at[i, bar_col], "exit_time": df.at[exit_idx, bar_col],
            "direction": "LONG" if direction == 1 else "SHORT",
            "entry_price": entry_price, "exit_price": exit_price, "contracts": contracts,
            "sl_pts": sl_pts, "pts": pts, "pnl_usd": pnl_usd, "exit_reason": exit_reason,
            "bars_held": exit_idx - i, "date": df.at[i, "date"],
        })

        if account.status == "dead_eod":
            break
        i = exit_idx + 1

    return pd.DataFrame(trades)
```

- [ ] **Step 4: Lancer les tests — ils doivent PASSER**

Run: `cd "C:/Users/ryadb/OneDrive/QUANT MATHS"; python -m pytest 02_validation/gauntlet/tests/test_backtest.py -v`
Expected: PASS — 5 tests passés.

- [ ] **Step 5: Commit**

```bash
git add 02_validation/gauntlet/backtest.py 02_validation/gauntlet/tests/test_backtest.py
git commit -m "feat(gauntlet): backtest_pa - backtest event-driven sur PaAccount"
```

---

### Task 7 : Test d'intégration de bout en bout

**Files:**
- Create: `02_validation/gauntlet/tests/test_integration_plan1.py`

**Pourquoi :** les tasks 2-6 testent chaque brique isolément. Cette task vérifie qu'elles **s'assemblent** : on construit une `Hypothesis` synthétique triviale, on génère ses signaux, on backtest sur un `PaAccount` neuf, et on vérifie que le compte a bien avancé sur plusieurs jours (frontières de journée, `daily_history`, tier). C'est le test de câblage du socle — si ça passe, Plan 1 est fonctionnel et Plan 2 peut se brancher dessus.

- [ ] **Step 1: Écrire le test d'intégration**

Create `02_validation/gauntlet/tests/test_integration_plan1.py` :

```python
"""Intégration Plan 1 : Hypothesis + backtest_pa + PaAccount s'assemblent et avancent."""
import pandas as pd

from gauntlet.hypothesis import Hypothesis
from gauntlet.backtest import backtest_pa
from gauntlet.pa_account import PaAccount

MNQ_SPECS = {
    "point_value": 2.00, "tick_size": 0.25, "commission_rt": 1.10,
    "sl_floor_pts": 5.0, "sl_cap_pts": 10.0,
}


def _build_variant(params):
    """Hypothèse triviale : LONG quand close > mid, exit quand close revient sous mid."""
    def signal_fn(df):
        out = df.copy()
        out["signal"] = 0
        out.loc[out["close"] > out["mid"], "signal"] = 1
        return out

    def exit_logic(df, i, j, direction, entry_price, std_i, mid_i,
                   or_high, or_low, or_range, sl_pts):
        if direction == 1 and df.at[j, "close"] <= df.at[j, "mid"]:
            return True, df.at[j, "close"], "TP_back_to_mid"
        return False, 0.0, ""

    return signal_fn, exit_logic, {"timeout_bars": params["timeout_bars"]}


def test_socle_plan1_sassemble_et_avance_sur_plusieurs_jours():
    # 3 jours de 4 barres en session NY, prix qui oscille autour de mid=100
    idx = pd.to_datetime([
        "2026-01-02 14:30", "2026-01-02 14:35", "2026-01-02 14:40", "2026-01-02 14:45",
        "2026-01-05 14:30", "2026-01-05 14:35", "2026-01-05 14:40", "2026-01-05 14:45",
        "2026-01-06 14:30", "2026-01-06 14:35", "2026-01-06 14:40", "2026-01-06 14:45",
    ]).tz_localize("America/New_York")
    closes = [101.0, 99.0, 102.0, 99.0, 101.0, 99.0, 103.0, 99.0, 101.0, 99.0, 102.0, 99.0]
    df = pd.DataFrame({
        "close": closes,
        "high": [c + 0.5 for c in closes],
        "low": [c - 0.5 for c in closes],
        "std": [4.0] * 12,
        "mid": [100.0] * 12,
    }, index=idx)
    df["hour_ny"] = df.index.hour
    df["min_ny"] = df.index.minute
    df["date"] = df.index.date

    hyp = Hypothesis(
        name="trivial_mr", description="LONG si close>mid, exit si close<=mid",
        instrument="MNQ", timeframe="5min", build_variant=_build_variant,
        param_grid=[{"timeout_bars": 3}],
    )
    signal_fn, exit_logic, bt_kwargs = hyp.build_variant(hyp.param_grid[0])
    df_sig = signal_fn(df)
    acc = PaAccount()
    trades = backtest_pa(df_sig, exit_logic, MNQ_SPECS, acc,
                         bar_size_min=5, timeout_bars=bt_kwargs["timeout_bars"])

    # Le socle a produit des trades et le compte a avancé sur les 3 journées.
    assert len(trades) > 0
    assert acc.status == "alive"
    # end_session est appelé aux 2 changements de date (J2->J3 du backtest interne) ;
    # la dernière journée n'est pas clôturée par le backtest (pas de date suivante).
    assert len(acc.daily_history) >= 2
    # n_trials de l'hypothèse est cohérent
    assert hyp.n_trials == 1
```

- [ ] **Step 2: Lancer le test — il doit PASSER**

Run: `cd "C:/Users/ryadb/OneDrive/QUANT MATHS"; python -m pytest 02_validation/gauntlet/tests/test_integration_plan1.py -v`
Expected: PASS — 1 test passé. (Toutes les briques du Plan 1 sont déjà implémentées — ce test ne fait que les assembler, il doit passer directement.)

- [ ] **Step 3: Lancer toute la suite gauntlet**

Run: `cd "C:/Users/ryadb/OneDrive/QUANT MATHS"; python -m pytest 02_validation/gauntlet/tests/ -v`
Expected: PASS — tous les tests du package gauntlet (smoke + pa_rules + hypothesis + splits + pa_account + backtest + integration).

- [ ] **Step 4: Commit**

```bash
git add 02_validation/gauntlet/tests/test_integration_plan1.py
git commit -m "test(gauntlet): integration Plan 1 - le socle backtest PA EOD s'assemble"
```

---

## Self-Review (effectuée à l'écriture du plan)

**1. Couverture spec** — Plan 1 couvre la partie "socle" du spec : interface Hypothesis (§A) ✓, splits LdP (Bloc 1) ✓, simulateur compte PA EOD + backtest réaliste (Bloc 2) ✓. Les Blocs 3-5 (batterie statistique, robustesse, verdict) sont explicitement reportés aux Plans 2-3 — c'est la décomposition annoncée.

**2. Placeholders** — aucun TBD/TODO ; tout le code est complet et exécutable. Le `sizing_fn` configurable est explicitement marqué YAGNI (hors Plan 1), pas un placeholder.

**3. Cohérence des types** — `Hypothesis.build_variant` retourne `(signal_fn, exit_logic, backtest_kwargs)` partout (Task 3 def, Task 7 usage). `PaAccount` : méthodes `start_session/end_session/check_intraday/can_trade/record_trade` + attributs `balance/status/eod_threshold/tier/max_contracts_std/dll/day_paused/daily_history/threshold_locked` cohérents entre Task 5 (def) et Task 6 (usage dans `backtest_pa`). La signature `exit_logic` (11 args positionnels) est identique entre Task 6, le test Task 6 et le test Task 7, et conforme à la convention `01_research/src/backtest.py`. `backtest_pa` retourne un DataFrame avec les colonnes listées — cohérent entre def et tests.

**4. Risque connu** — `pa_account.py` + `backtest.py` sont une quasi-réécriture (le spec le signalait). C'est pour ça que `test_pa_account.py` (11 tests) et `test_backtest.py` (5 tests) couvrent chaque mécanique séparément, et que Task 7 valide le câblage. Si un test de Task 5/6 résiste, ne pas affaiblir l'assertion — c'est un vrai bug du simulateur, à corriger.
