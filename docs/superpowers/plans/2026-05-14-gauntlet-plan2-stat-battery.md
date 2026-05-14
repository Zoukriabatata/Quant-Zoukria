# Gauntlet — Plan 2 : La batterie statistique + robustesse — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construire les Blocs 3 et 4 du gauntlet — la batterie statistique López de Prado (walk-forward purgé, CPCV, Deflated Sharpe, PBO, Monte Carlo permutation) et la robustesse (stress test périodes rouges, cycle PA continu) — qui transforment « ce backtest a l'air bien » en « cet edge est statistiquement réel, ou pas ».

**Architecture:** Six modules dans `02_validation/gauntlet/`. Deux sont **consolidés** depuis `02_validation/v10/validation/` (code mort : il importe un package `quant_v10` qui ne résout pas) : `cpcv.py` et `deflated_sharpe.py`. Quatre sont **neufs** : `monte_carlo.py`, `walk_forward.py`, `stress_test.py`, `pa_cycle.py`. Les modules qui doivent rejouer des backtests (`walk_forward`, `stress_test`, `pa_cycle`) ne chargent **pas** les données eux-mêmes : ils reçoivent un callable `run_variant` injecté (voir §"Le contrat `run_variant`"). Ça les garde purs et testables sur données synthétiques ; le `run_variant` concret (data-load + features + signal + `backtest_pa`) est câblé en Plan 3. TDD strict.

**Tech Stack:** Python 3.10+, pandas, numpy, scipy, pytest. Réutilise le socle Plan 1 (`pa_account`, `backtest_pa`) et `compute_trade_metrics` de `01_research/src/backtest.py` (déjà sur le `sys.path` via `gauntlet/conftest.py`).

**Spec de référence:** `docs/superpowers/specs/2026-05-14-gauntlet-validation-design.md` (Blocs 3 et 4).

**Plan précédent:** `docs/superpowers/plans/2026-05-14-gauntlet-plan1-backtest-core.md` (socle mergé dans `main`).

---

## Note pédagogique (préférence BB — apprendre au fil du projet)

BB veut **comprendre** ce qui est codé. Chaque task inclut une explication **"Pourquoi"** : le concept quant ou le choix de design derrière le code. L'implémenteur DOIT garder ces explications dans les messages de rapport.

---

## Décisions actées avec BB avant ce plan

1. **Monte Carlo permutation** — le spec dit « permute les returns des trades → distribution du Sharpe ». Problème : le Sharpe (moyenne / écart-type) est **insensible à l'ordre** des trades — permuter l'ordre ne produit aucune distribution. Décision BB : **sign-flip + shuffle DD**. `monte_carlo.py` fait donc *deux* tests distincts — sign-flip du signe de chaque trade pour la p-value du Sharpe, et shuffle de l'ordre pour la distribution du Max DD (le DD, lui, dépend de l'ordre).
2. **`02_validation/v10/validation/`** — contient `cpcv.py` + `deflated_sharpe.py` (à déplacer vers `gauntlet/` selon le spec) mais aussi `run_final_validation.py` + le test `v10/tests/test_validation.py`, tous deux important `quant_v10.*` qui **ne résout pas** (vérifié : `ModuleNotFoundError`, collection error). Décision BB : **tout consolider, supprimer le mort**. On déplace `cpcv.py`/`deflated_sharpe.py`, on ressuscite les tests dans `gauntlet/tests/`, on supprime `run_final_validation.py` + `v10/validation/` + `v10/tests/test_validation.py`.

---

## Le contrat `run_variant`

Trois des six modules (`walk_forward`, `stress_test`, `pa_cycle`) doivent **rejouer un backtest** sur des sous-ensembles de données. Ils ne chargent pas les données eux-mêmes — ils reçoivent un callable injecté :

```
run_variant(df: pd.DataFrame, params: dict) -> tuple[trades_df: pd.DataFrame, account: PaAccount]
```

- `df` : un DataFrame **préparé** (features calculées, indexé par `DatetimeIndex` tz-aware) — ou une **tranche** de celui-ci. Le module appelant slice `df` par dates (fenêtres walk-forward, périodes rouges) et passe la tranche.
- `params` : un jeu de params issu de `Hypothesis.param_grid`.
- retourne : `(trades_df, account)` — la sortie de `backtest_pa` (Plan 1) **et** le `PaAccount` après le run. `walk_forward` et `stress_test` n'utilisent que ce qu'il leur faut (`stress_test` lit `account.status` pour la survie).

**Pourquoi l'injection plutôt que charger les données dans le module :** ça garde `walk_forward`/`stress_test`/`pa_cycle` **purs** — aucune I/O, testables sur données synthétiques avec un `run_variant` factice. Le `run_variant` concret (qui charge l'instrument, resample, calcule les features, applique la `signal_fn` de l'hypothèse, lance `backtest_pa` sur un `PaAccount` neuf) appartient à l'orchestrateur `run_gauntlet.py` — c'est du Plan 3. Plan 2 livre la machinerie statistique ; Plan 3 la câble aux vraies données.

---

## File Structure

| Fichier | Responsabilité | Task |
|---|---|---|
| `02_validation/gauntlet/cpcv.py` | **déplacé** de `v10/validation/` — paths CPCV + distribution Sharpe OOS | 1 |
| `02_validation/gauntlet/deflated_sharpe.py` | **déplacé** de `v10/validation/` — PSR + DSR + PBO | 1 |
| `02_validation/gauntlet/tests/test_cpcv.py` | tests CPCV ressuscités (imports corrigés) | 1 |
| `02_validation/gauntlet/tests/test_deflated_sharpe.py` | tests PSR/DSR/PBO ressuscités | 1 |
| `02_validation/gauntlet/monte_carlo.py` | **NEW** — sign-flip (p-value Sharpe) + order-shuffle (distribution Max DD) | 2 |
| `02_validation/gauntlet/walk_forward.py` | **NEW** — walk-forward purgé à fenêtres ancrées | 3 |
| `02_validation/gauntlet/stress_test.py` | **NEW** — rejoue le meilleur variant sur les périodes rouges | 4 |
| `02_validation/gauntlet/pa_cycle.py` | **NEW** — analyse d'un cycle PA continu (survie / lock / inactivité) | 5 |
| `02_validation/gauntlet/tests/test_*.py` | tests unitaires par module | 2-6 |
| `02_validation/gauntlet/tests/test_integration_plan2.py` | intégration : la batterie tourne de bout en bout | 6 |
| `02_validation/v10/validation/` (dossier) | **SUPPRIMÉ** — code mort consolidé | 1 |
| `02_validation/v10/tests/test_validation.py` | **SUPPRIMÉ** — ressuscité dans `gauntlet/tests/` | 1 |

**Aucune modification de `pyproject.toml`** : `02_validation/gauntlet/tests` est déjà dans `testpaths` (Plan 1). `02_validation/v10/tests` y reste pour les autres tests v10.

---

### Task 1 : Consolider `cpcv.py` + `deflated_sharpe.py` dans `gauntlet/`, supprimer le mort

**Files:**
- Create: `02_validation/gauntlet/tests/test_cpcv.py`
- Create: `02_validation/gauntlet/tests/test_deflated_sharpe.py`
- Move: `02_validation/v10/validation/cpcv.py` → `02_validation/gauntlet/cpcv.py`
- Move: `02_validation/v10/validation/deflated_sharpe.py` → `02_validation/gauntlet/deflated_sharpe.py`
- Delete: `02_validation/v10/validation/run_final_validation.py`, `02_validation/v10/validation/__init__.py`, `02_validation/v10/tests/test_validation.py`

**Pourquoi :** le spec demande de réutiliser CPCV / Deflated Sharpe / PBO plutôt que de les réécrire — ils sont corrects (références Bailey & López de Prado 2014). Mais ils vivent dans `v10/validation/` et n'y sont **plus accessibles** : `run_final_validation.py` et `test_validation.py` importent un package `quant_v10` qui n'existe pas (vérifié — `ModuleNotFoundError`). Ce sont des **fichiers purs** (numpy/scipy/pandas, aucun import interne du projet) : les déplacer = un simple `git mv`, le code ne change pas. On ressuscite au passage les tests (qui ne tournaient plus) en corrigeant leurs imports vers `gauntlet.*`, et on supprime l'orchestrateur v10 mort. Rappel des concepts : **CPCV** (Combinatorial Purged CV) génère plein de chemins OOS en combinant des groupes temporels → distribution de Sharpe au lieu d'un point unique. **PSR/DSR** (Probabilistic / Deflated Sharpe) : la proba que le vrai Sharpe soit positif, le DSR pénalisant pour le nombre de configs testées (plus tu testes, plus tu trouves un edge par hasard). **PBO** (Probability of Backtest Overfitting) : sur une matrice de PnL multi-configs, la fraction des découpages où la "meilleure" config in-sample finit dans la moitié basse out-of-sample.

- [ ] **Step 1: Écrire les tests qui échouent (CPCV)**

Create `02_validation/gauntlet/tests/test_cpcv.py` :

```python
"""Tests de cpcv : génération de paths CPCV + distribution de Sharpe OOS.

Consolidé depuis 02_validation/v10/validation/tests (où il était mort — l'import
quant_v10 ne résolvait pas). Imports corrigés vers gauntlet.cpcv.
"""
import numpy as np
import pandas as pd
import pytest

from gauntlet.cpcv import generate_cpcv_paths, sharpe_distribution_cpcv


@pytest.fixture
def good_trades():
    """Série de trades avec edge réel (moyenne positive)."""
    rng = np.random.default_rng(42)
    pnl = rng.normal(loc=50.0, scale=200.0, size=1000)
    dates = pd.date_range("2022-01-01", periods=1000, freq="D")
    return pd.DataFrame({"date": dates, "pnl": pnl})


def test_generate_paths_count():
    """CPCV(N=8, K=2) doit générer C(8,2)=28 paths."""
    paths = generate_cpcv_paths(n_groups=8, k_test=2)
    assert len(paths) == 28


def test_each_path_test_size_is_k():
    paths = generate_cpcv_paths(n_groups=6, k_test=2)
    for test_indices in paths:
        assert len(test_indices) == 2


def test_paths_are_unique():
    paths = generate_cpcv_paths(n_groups=6, k_test=2)
    seen = {tuple(sorted(path)) for path in paths}
    assert len(seen) == len(paths)


def test_sharpe_distribution_cpcv(good_trades):
    """Pour des trades avec edge, la distribution Sharpe doit avoir une moyenne > 0."""
    sharpes = sharpe_distribution_cpcv(good_trades, n_groups=10, k_test=2)
    assert len(sharpes) > 0
    assert np.mean(sharpes) > 0.0
```

- [ ] **Step 2: Écrire les tests qui échouent (Deflated Sharpe + PBO)**

Create `02_validation/gauntlet/tests/test_deflated_sharpe.py` :

```python
"""Tests de deflated_sharpe : PSR + DSR + PBO.

Consolidé depuis 02_validation/v10/validation/tests (où il était mort — l'import
quant_v10 ne résolvait pas). Imports corrigés vers gauntlet.deflated_sharpe.
"""
import numpy as np
import pandas as pd
import pytest

from gauntlet.deflated_sharpe import (
    probabilistic_sharpe_ratio,
    deflated_sharpe_ratio,
    probability_backtest_overfitting,
)


@pytest.fixture
def good_trades():
    """Série de trades avec edge réel (moyenne positive)."""
    rng = np.random.default_rng(42)
    pnl = rng.normal(loc=50.0, scale=200.0, size=1000)
    dates = pd.date_range("2022-01-01", periods=1000, freq="D")
    return pd.DataFrame({"date": dates, "pnl": pnl})


@pytest.fixture
def noise_trades():
    """Pas d'edge (moyenne = 0)."""
    rng = np.random.default_rng(1)
    pnl = rng.normal(loc=0.0, scale=200.0, size=1000)
    dates = pd.date_range("2022-01-01", periods=1000, freq="D")
    return pd.DataFrame({"date": dates, "pnl": pnl})


def test_psr_in_unit_interval(good_trades):
    """PSR(SR) doit être dans [0, 1] (c'est une probabilité)."""
    psr = probabilistic_sharpe_ratio(good_trades["pnl"].values, sr_benchmark=0.0)
    assert 0.0 <= psr <= 1.0


def test_psr_higher_for_better_edge(good_trades, noise_trades):
    """PSR sur edge > PSR sur noise."""
    psr_edge = probabilistic_sharpe_ratio(good_trades["pnl"].values, sr_benchmark=0.0)
    psr_noise = probabilistic_sharpe_ratio(noise_trades["pnl"].values, sr_benchmark=0.0)
    assert psr_edge > psr_noise


def test_dsr_corrects_for_multiple_testing(good_trades):
    """DSR avec n_trials élevé <= PSR (correction type Bonferroni)."""
    pnl = good_trades["pnl"].values
    psr = probabilistic_sharpe_ratio(pnl, sr_benchmark=0.0)
    dsr = deflated_sharpe_ratio(pnl, n_trials=100, sr_variance=0.5 ** 2)
    assert dsr <= psr


def test_dsr_in_unit_interval(good_trades):
    dsr = deflated_sharpe_ratio(
        good_trades["pnl"].values, n_trials=10, sr_variance=0.3 ** 2,
    )
    assert 0.0 <= dsr <= 1.0


def test_pbo_in_unit_interval():
    """PBO doit être dans [0, 1]."""
    rng = np.random.default_rng(0)
    matrix = rng.normal(0, 1, size=(200, 10))
    pbo = probability_backtest_overfitting(matrix, n_splits=8)
    assert 0.0 <= pbo <= 1.0


def test_pbo_high_for_pure_noise():
    """Sur des PnL pur bruit, le PBO doit converger vers ~0.5 (ranking aléatoire)."""
    rng = np.random.default_rng(2024)
    matrix = rng.normal(0, 1, size=(500, 20))
    pbo = probability_backtest_overfitting(matrix, n_splits=10)
    assert 0.3 < pbo < 0.7
```

- [ ] **Step 3: Lancer les tests — ils doivent ÉCHOUER**

Run: `cd "C:/Users/ryadb/OneDrive/QUANT MATHS"; python -m pytest 02_validation/gauntlet/tests/test_cpcv.py 02_validation/gauntlet/tests/test_deflated_sharpe.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'gauntlet.cpcv'` (et `gauntlet.deflated_sharpe`).

- [ ] **Step 4: Déplacer les deux modules dans `gauntlet/`**

Run:
```bash
cd "C:/Users/ryadb/OneDrive/QUANT MATHS"
git mv 02_validation/v10/validation/cpcv.py 02_validation/gauntlet/cpcv.py
git mv 02_validation/v10/validation/deflated_sharpe.py 02_validation/gauntlet/deflated_sharpe.py
```
Aucune édition du contenu : les deux fichiers sont purs (numpy / scipy / pandas / itertools, zéro import interne du projet). Le `git mv` suffit.

- [ ] **Step 5: Lancer les tests — ils doivent PASSER**

Run: `cd "C:/Users/ryadb/OneDrive/QUANT MATHS"; python -m pytest 02_validation/gauntlet/tests/test_cpcv.py 02_validation/gauntlet/tests/test_deflated_sharpe.py -v`
Expected: PASS — 4 tests CPCV + 6 tests Deflated Sharpe = 10 tests passés.

- [ ] **Step 6: Supprimer le code mort**

Run:
```bash
cd "C:/Users/ryadb/OneDrive/QUANT MATHS"
git rm 02_validation/v10/validation/run_final_validation.py
git rm 02_validation/v10/validation/__init__.py
git rm 02_validation/v10/tests/test_validation.py
```
`run_final_validation.py` et `test_validation.py` importent `quant_v10.*` qui ne résout pas (vérifié : collection error) — code mort. Le dossier `02_validation/v10/validation/` est maintenant vide ; `git rm` l'a déréférencé. Si un dossier vide subsiste sur le disque, le supprimer : `Remove-Item 02_validation/v10/validation -Recurse -Force` (PowerShell).

- [ ] **Step 7: Vérifier qu'aucune autre référence ne casse**

Run: `cd "C:/Users/ryadb/OneDrive/QUANT MATHS"; python -m pytest 02_validation/gauntlet/tests/ 02_validation/v10/tests/ -q`
Expected: PASS — tous les tests `gauntlet/` (Plan 1 + les 10 nouveaux) + tous les tests `v10/tests/` restants passent ou collectent sans erreur. **Aucune** `ModuleNotFoundError` liée à `validation`. (Note : d'autres tests v10 peuvent rester rouges pour des raisons préexistantes — ce qui compte ici, c'est qu'aucune régression ne vienne de cette task. Si un test v10 échoue, vérifier via `git stash` qu'il échouait déjà avant.)

- [ ] **Step 8: Commit**

```bash
git add -A 02_validation/gauntlet/ 02_validation/v10/
git commit -m "refactor(gauntlet): consolide cpcv + deflated_sharpe, supprime v10/validation mort"
```

---

### Task 2 : `monte_carlo.py` — sign-flip (p-value Sharpe) + order-shuffle (distribution Max DD)

**Files:**
- Create: `02_validation/gauntlet/monte_carlo.py`
- Create: `02_validation/gauntlet/tests/test_monte_carlo.py`

**Pourquoi :** deux tests de permutation, parce que le Sharpe et le Max DD ne réagissent **pas pareil** à une permutation. Le **Sharpe** = moyenne / écart-type : insensible à l'ordre des trades — permuter l'ordre ne donne aucune distribution. Pour obtenir une vraie distribution sous H0, on permute le **signe** de chaque PnL (×±1 aléatoire) : H0 = « chaque trade est un pile ou face sur sa magnitude, aucun edge directionnel ». La p-value = fraction des Sharpes permutés ≥ Sharpe observé ; `p < 0.05` ⇒ l'edge n'est pas un coup de chance. Le **Max DD**, lui, dépend complètement de l'ordre (des pertes groupées creusent plus qu'éparpillées) : on permute l'**ordre** des trades et on mesure le Max DD de chaque courbe d'equity → distribution des DD plausibles. Sur un compte Apex où toucher le seuil = mort définitive, savoir que « 99% des ordres restent au-dessus de -$X » vaut de l'or.

- [ ] **Step 1: Écrire les tests qui échouent**

Create `02_validation/gauntlet/tests/test_monte_carlo.py` :

```python
"""Tests de monte_carlo : permutation sign-flip (Sharpe) + order-shuffle (Max DD)."""
import numpy as np

from gauntlet.monte_carlo import (
    permutation_test_sharpe,
    dd_distribution_shuffle,
    _sharpe,
    _max_drawdown,
)


def test_max_drawdown_hand_calc():
    # pnl chronologique [+100, -300, +100, -300, +100]
    # equity = [100, -200, -100, -400, -300] ; peak = [100,100,100,100,100]
    # dd = [0, -300, -200, -500, -200] ; max dd = -500
    pnl = np.array([100.0, -300.0, 100.0, -300.0, 100.0])
    assert _max_drawdown(pnl) == -500.0


def test_max_drawdown_all_positive_is_zero():
    assert _max_drawdown(np.array([10.0, 20.0, 5.0])) == 0.0


def test_sharpe_matches_repo_convention():
    # convention repo : moyenne / std(ddof=1) * sqrt(252) — cf. compute_trade_metrics
    pnl = np.array([100.0, -50.0, 75.0, -25.0, 60.0])
    expected = np.mean(pnl) / np.std(pnl, ddof=1) * np.sqrt(252)
    assert abs(_sharpe(pnl) - expected) < 1e-9


def test_permutation_strong_edge_low_pvalue():
    # 200 trades, edge franc (moyenne très > 0) -> p-value proche de 0
    rng = np.random.default_rng(7)
    pnl = rng.normal(loc=120.0, scale=150.0, size=200)
    res = permutation_test_sharpe(pnl, n_iter=2000, seed=0)
    assert res["observed_sharpe"] > 0
    assert res["p_value"] < 0.01


def test_permutation_pure_noise_pvalue_near_half():
    # PnL recentré sur 0 -> Sharpe observé = 0, pile au centre de la distribution sign-flip
    rng = np.random.default_rng(11)
    pnl = rng.normal(loc=0.0, scale=150.0, size=300)
    pnl = pnl - pnl.mean()
    res = permutation_test_sharpe(pnl, n_iter=4000, seed=0)
    assert abs(res["observed_sharpe"]) < 1e-9
    assert 0.40 < res["p_value"] < 0.60


def test_permutation_reproducible():
    rng = np.random.default_rng(3)
    pnl = rng.normal(loc=30.0, scale=100.0, size=100)
    r1 = permutation_test_sharpe(pnl, n_iter=500, seed=42)
    r2 = permutation_test_sharpe(pnl, n_iter=500, seed=42)
    assert r1["p_value"] == r2["p_value"]


def test_dd_distribution_observed_is_chronological():
    # observed_max_dd doit être le Max DD dans l'ordre RÉEL fourni
    pnl = np.array([100.0, -300.0, 100.0, -300.0, 100.0])
    res = dd_distribution_shuffle(pnl, n_iter=500, seed=0)
    assert res["observed_max_dd"] == -500.0


def test_dd_distribution_percentiles_ordered():
    rng = np.random.default_rng(5)
    pnl = rng.normal(loc=-5.0, scale=200.0, size=150)
    res = dd_distribution_shuffle(pnl, n_iter=3000, seed=0)
    # tous les DD <= 0 ; p50 (le moins profond) >= p95 >= p99 >= worst (le plus profond)
    assert res["dd_p50"] <= 0.0
    assert res["dd_p50"] >= res["dd_p95"] >= res["dd_p99"] >= res["dd_worst"]


def test_dd_distribution_reproducible():
    rng = np.random.default_rng(9)
    pnl = rng.normal(loc=10.0, scale=120.0, size=120)
    r1 = dd_distribution_shuffle(pnl, n_iter=500, seed=1)
    r2 = dd_distribution_shuffle(pnl, n_iter=500, seed=1)
    assert r1 == r2
```

- [ ] **Step 2: Lancer les tests — ils doivent ÉCHOUER**

Run: `cd "C:/Users/ryadb/OneDrive/QUANT MATHS"; python -m pytest 02_validation/gauntlet/tests/test_monte_carlo.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'gauntlet.monte_carlo'`

- [ ] **Step 3: Implémenter `monte_carlo.py`**

Create `02_validation/gauntlet/monte_carlo.py` :

```python
"""Monte Carlo permutation — p-value du Sharpe + distribution du Max Drawdown.

Deux tests distincts, parce que le Sharpe et le Max DD ne réagissent PAS pareil à une
permutation :

  - permutation_test_sharpe : SIGN-FLIP. Le Sharpe (moyenne / écart-type) est insensible
    à l'ORDRE des trades — permuter l'ordre ne donne aucune distribution. On permute donc
    le SIGNE de chaque PnL de trade (x +/-1 aléatoire). H0 = "chaque trade est un pile ou
    face sur sa magnitude" (aucun edge directionnel). p-value = fraction des Sharpes
    permutés >= Sharpe observé. p < 0.05 => l'edge n'est pas un coup de chance.

  - dd_distribution_shuffle : ORDER-SHUFFLE. Le Max DD, lui, dépend complètement de
    l'ordre (des pertes groupées creusent plus qu'éparpillées). On permute l'ORDRE des
    trades et on mesure le Max DD de chaque courbe d'equity -> distribution des DD
    plausibles avec ce jeu de trades. Critique pour un compte Apex où le DD = la mort.

Décision BB (2026-05-14) : le spec disait "permute les returns des trades" ; comme ça ne
produit pas de distribution de Sharpe (order-invariant), on fait sign-flip + shuffle DD.
"""
from __future__ import annotations

import numpy as np

_ANN = np.sqrt(252.0)  # annualisation per-trade (convention repo, cf. compute_trade_metrics)


def _sharpe(pnl: np.ndarray) -> float:
    """Sharpe per-trade annualisé sqrt(252) — convention src.backtest.compute_trade_metrics."""
    if len(pnl) < 2:
        return 0.0
    sd = np.std(pnl, ddof=1)
    if sd == 0:
        return 0.0
    return float(np.mean(pnl) / sd * _ANN)


def _max_drawdown(pnl: np.ndarray) -> float:
    """Max Drawdown ($) d'une séquence de PnL de trades, dans l'ordre donné.

    Equity = cumsum du PnL ; DD = equity - plus-haut-glissant ; Max DD = le minimum (<= 0).
    """
    if len(pnl) == 0:
        return 0.0
    equity = np.cumsum(pnl)
    running_peak = np.maximum.accumulate(equity)
    return float(np.min(equity - running_peak))


def permutation_test_sharpe(pnl, n_iter: int = 10_000, seed: int = 0) -> dict:
    """Test de permutation sign-flip : p-value du Sharpe observé sous H0 "pas d'edge".

    Args:
        pnl: séquence de PnL par trade ($). L'ordre est indifférent (le Sharpe l'ignore).
        n_iter: nombre de permutations sign-flip.
        seed: graine RNG (reproductibilité).

    Returns:
        dict(observed_sharpe, p_value, perm_mean, perm_std, n_iter).
        p_value = (1 + #{perm >= observed}) / (1 + n_iter) — estimateur non biaisé,
        jamais exactement 0.
    """
    pnl = np.asarray(pnl, dtype=float)
    pnl = pnl[~np.isnan(pnl)]
    observed = _sharpe(pnl)
    if len(pnl) < 2:
        return dict(observed_sharpe=observed, p_value=1.0,
                    perm_mean=0.0, perm_std=0.0, n_iter=n_iter)
    rng = np.random.default_rng(seed)
    perms = np.empty(n_iter, dtype=float)
    for k in range(n_iter):
        signs = rng.choice((-1.0, 1.0), size=len(pnl))
        perms[k] = _sharpe(pnl * signs)
    p_value = float((1 + np.sum(perms >= observed)) / (1 + n_iter))
    return dict(
        observed_sharpe=observed,
        p_value=p_value,
        perm_mean=float(np.mean(perms)),
        perm_std=float(np.std(perms, ddof=1)),
        n_iter=n_iter,
    )


def dd_distribution_shuffle(pnl, n_iter: int = 10_000, seed: int = 0) -> dict:
    """Distribution du Max Drawdown par permutation de l'ORDRE des trades.

    Args:
        pnl: séquence de PnL par trade ($), dans l'ordre CHRONOLOGIQUE réel.
        n_iter: nombre de permutations d'ordre.
        seed: graine RNG.

    Returns:
        dict(observed_max_dd, dd_p50, dd_p95, dd_p99, dd_worst, n_iter).
        Tous les DD sont <= 0 ($). observed_max_dd = Max DD dans l'ordre réel.
        dd_p95 = le DD tel que 95% des ordres font MIEUX (moins profond) — donc le 5e
        percentile de la distribution. dd_worst = le pire DD sur toutes les permutations.
    """
    pnl = np.asarray(pnl, dtype=float)
    pnl = pnl[~np.isnan(pnl)]
    observed = _max_drawdown(pnl)
    if len(pnl) < 2:
        return dict(observed_max_dd=observed, dd_p50=observed, dd_p95=observed,
                    dd_p99=observed, dd_worst=observed, n_iter=n_iter)
    rng = np.random.default_rng(seed)
    dds = np.empty(n_iter, dtype=float)
    for k in range(n_iter):
        dds[k] = _max_drawdown(rng.permutation(pnl))
    return dict(
        observed_max_dd=observed,
        dd_p50=float(np.percentile(dds, 50)),
        dd_p95=float(np.percentile(dds, 5)),    # 5% des ordres font pire
        dd_p99=float(np.percentile(dds, 1)),    # 1% des ordres font pire
        dd_worst=float(np.min(dds)),
        n_iter=n_iter,
    )
```

- [ ] **Step 4: Lancer les tests — ils doivent PASSER**

Run: `cd "C:/Users/ryadb/OneDrive/QUANT MATHS"; python -m pytest 02_validation/gauntlet/tests/test_monte_carlo.py -v`
Expected: PASS — 9 tests passés.

- [ ] **Step 5: Commit**

```bash
git add 02_validation/gauntlet/monte_carlo.py 02_validation/gauntlet/tests/test_monte_carlo.py
git commit -m "feat(gauntlet): monte_carlo - sign-flip p-value Sharpe + order-shuffle distribution DD"
```

---

### Task 3 : `walk_forward.py` — walk-forward purgé à fenêtres ancrées

**Files:**
- Create: `02_validation/gauntlet/walk_forward.py`
- Create: `02_validation/gauntlet/tests/test_walk_forward.py`

**Pourquoi :** López de Prado, règle nº1 — **on ne juge jamais une stratégie sur les données qui ont servi à la régler**. Le walk-forward découpe l'historique en fenêtres successives ; sur chaque fenêtre on **optimise** les params en in-sample (IS) puis on les **teste** en out-of-sample (OOS) sur des données que l'optimisation n'a jamais vues. La **purge** (embargo) jette les dernières barres de l'IS : un trade ouvert tout en fin d'IS dure plusieurs barres et "déborderait" sur l'OOS — l'embargo coupe ce chevauchement, sinon l'OOS est contaminé. On fait des fenêtres **ancrées** (expanding) : l'IS grossit à chaque fenêtre (tranches `[0..k]`), l'OOS est toujours la tranche suivante — ça simule un trader qui ré-optimise périodiquement avec tout l'historique disponible. La sortie alimente le critère verdict du spec : « ≥ 3 fenêtres, ≥ 70% OOS rentables ».

- [ ] **Step 1: Écrire les tests qui échouent**

Create `02_validation/gauntlet/tests/test_walk_forward.py` :

```python
"""Tests du walk-forward purgé à fenêtres ancrées."""
import numpy as np
import pandas as pd
import pytest

from gauntlet.walk_forward import purged_walk_forward, walk_forward_summary


def _make_df(n_bars: int) -> pd.DataFrame:
    """DataFrame minimal indexé temps — le contenu n'importe pas (run_variant est factice)."""
    idx = pd.date_range("2022-01-01", periods=n_bars, freq="1h", tz="UTC")
    return pd.DataFrame({"close": np.arange(n_bars, dtype=float)}, index=idx)


def _fake_run_variant_factory(call_log):
    """Construit un run_variant factice qui :
      - journalise (len(df), params) à chaque appel dans call_log ;
      - retourne des trades dont le PnL dépend du param 'edge' :
          edge=True  -> 10 trades positifs  (Sharpe > 0)
          edge=False -> 10 trades négatifs  (Sharpe < 0)
    """
    def run_variant(df_slice, params):
        call_log.append((len(df_slice), dict(params)))
        base = 100.0 if params["edge"] else -100.0
        trades = pd.DataFrame({
            "pnl_usd": [base + i for i in range(10)],   # +i -> écart-type != 0
            "date": pd.date_range("2022-06-01", periods=10, freq="D"),
        })
        return trades, None
    return run_variant


def test_wf_produces_n_windows():
    df = _make_df(220)
    rv = _fake_run_variant_factory([])
    wf = purged_walk_forward(df, [{"edge": True}], rv, n_windows=4, embargo_bars=5)
    assert len(wf) == 4
    assert list(wf["window"]) == [0, 1, 2, 3]


def test_wf_selects_best_param_on_is():
    df = _make_df(220)
    rv = _fake_run_variant_factory([])
    grid = [{"edge": False}, {"edge": True}]
    wf = purged_walk_forward(df, grid, rv, n_windows=3, embargo_bars=5)
    # edge=True donne un Sharpe positif -> sélectionné sur CHAQUE fenêtre
    assert all(p == {"edge": True} for p in wf["best_params"])
    assert wf["oos_profitable"].all()


def test_wf_embargo_trims_is():
    df = _make_df(220)
    log = []
    rv = _fake_run_variant_factory(log)
    purged_walk_forward(df, [{"edge": True}], rv, n_windows=4, embargo_bars=7)
    # 5 tranches de 44 barres. Fenêtre 0 : IS ancré = tranche 0 = 44 barres, moins
    # embargo 7 -> 37. Premier appel journalisé = IS de la fenêtre 0.
    assert log[0][0] == 44 - 7


def test_wf_all_params_tried_on_is():
    df = _make_df(220)
    log = []
    rv = _fake_run_variant_factory(log)
    grid = [{"edge": False}, {"edge": True}]
    purged_walk_forward(df, grid, rv, n_windows=3, embargo_bars=5)
    # par fenêtre : 2 appels IS (un par param) + 1 appel OOS = 3. 3 fenêtres -> 9 appels.
    assert len(log) == 9


def test_wf_summary_aggregates():
    df = _make_df(220)
    rv = _fake_run_variant_factory([])
    wf = purged_walk_forward(df, [{"edge": True}], rv, n_windows=4, embargo_bars=5)
    s = walk_forward_summary(wf)
    assert s["n_windows"] == 4
    assert s["pct_oos_profitable"] == 1.0
    assert s["all_profitable"] is True
    assert s["oos_sharpe_mean"] > 0


def test_wf_rejects_too_short_df():
    df = _make_df(3)
    rv = _fake_run_variant_factory([])
    with pytest.raises(ValueError):
        purged_walk_forward(df, [{"edge": True}], rv, n_windows=5, embargo_bars=1)
```

- [ ] **Step 2: Lancer les tests — ils doivent ÉCHOUER**

Run: `cd "C:/Users/ryadb/OneDrive/QUANT MATHS"; python -m pytest 02_validation/gauntlet/tests/test_walk_forward.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'gauntlet.walk_forward'`

- [ ] **Step 3: Implémenter `walk_forward.py`**

Create `02_validation/gauntlet/walk_forward.py` :

```python
"""Walk-forward purgé à fenêtres ancrées (expanding).

López de Prado : on ne juge jamais une stratégie sur les données qui ont servi à la
régler. Le walk-forward découpe l'historique en fenêtres successives ; sur chaque fenêtre
on OPTIMISE les params en in-sample (IS) puis on les TESTE en out-of-sample (OOS), sur des
données que l'optimisation n'a jamais vues. La PURGE (embargo) jette les dernières barres
de l'IS : un trade ouvert en fin d'IS dure plusieurs barres et "déborderait" sur l'OOS —
l'embargo coupe ce chevauchement.

Fenêtres ANCRÉES (expanding) : l'IS grossit à chaque fenêtre (tranches[0..k]), l'OOS est
toujours la tranche suivante. C'est le walk-forward classique — un trader qui ré-optimise
périodiquement avec tout l'historique disponible.

run_variant est INJECTÉ (cf. plan §"Le contrat run_variant") : signature
run_variant(df_slice, params) -> (trades_df, account). Le walk-forward n'utilise que
trades_df.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.backtest import compute_trade_metrics


def purged_walk_forward(df, param_grid, run_variant, n_windows: int = 4,
                        embargo_bars: int = 10) -> pd.DataFrame:
    """Walk-forward purgé à fenêtres ancrées.

    Args:
        df: DataFrame préparé (features calculées), indexé par DatetimeIndex tz-aware.
        param_grid: list[dict] — la grille de params de l'hypothèse.
        run_variant: callable(df_slice, params) -> (trades_df, account). Injecté.
        n_windows: nombre de fenêtres OOS (>= 3 recommandé, cf. spec).
        embargo_bars: barres jetées en fin d'IS (purge IS/OOS).

    Returns:
        DataFrame, une ligne par fenêtre :
        [window, is_start, is_end, oos_start, oos_end, best_params,
         oos_trades, oos_sharpe, oos_pf, oos_pnl, oos_max_dd, oos_profitable].

    Découpe df en n_windows+1 tranches contiguës. Fenêtre k (0-indexée) :
      IS  = df.iloc[0 : fin_tranche_k]  moins les embargo_bars dernières barres
      OOS = tranche k+1
    """
    n = len(df)
    if n_windows < 1:
        raise ValueError(f"n_windows >= 1 requis, reçu {n_windows}")
    if n < n_windows + 1:
        raise ValueError(f"df trop court ({n} barres) pour {n_windows} fenêtres")

    slices = np.array_split(np.arange(n), n_windows + 1)
    rows = []
    for k in range(n_windows):
        is_end_pos = int(slices[k][-1]) + 1            # fin exclusive de l'IS ancré
        is_df = df.iloc[:is_end_pos]
        if embargo_bars > 0:
            is_df = is_df.iloc[:-embargo_bars] if embargo_bars < len(is_df) else is_df.iloc[:0]
        oos_pos = slices[k + 1]
        oos_df = df.iloc[int(oos_pos[0]):int(oos_pos[-1]) + 1]

        # ── Optimisation in-sample : meilleur param par Sharpe ──
        best_params, best_score = None, -np.inf
        for params in param_grid:
            is_trades, _ = run_variant(is_df, params)
            score = compute_trade_metrics(is_trades)["sharpe"] if len(is_trades) else -np.inf
            if score > best_score:
                best_score, best_params = score, params

        # ── Test out-of-sample avec le meilleur param ──
        oos_trades, _ = run_variant(oos_df, best_params)
        m = compute_trade_metrics(oos_trades)
        rows.append({
            "window": k,
            "is_start": is_df.index[0] if len(is_df) else None,
            "is_end": is_df.index[-1] if len(is_df) else None,
            "oos_start": oos_df.index[0] if len(oos_df) else None,
            "oos_end": oos_df.index[-1] if len(oos_df) else None,
            "best_params": best_params,
            "oos_trades": m["trades"],
            "oos_sharpe": m["sharpe"],
            "oos_pf": m["pf"],
            "oos_pnl": m["pnl"],
            "oos_max_dd": m["max_dd"],
            "oos_profitable": m["pnl"] > 0,
        })
    return pd.DataFrame(rows)


def walk_forward_summary(wf_df: pd.DataFrame) -> dict:
    """Agrège un résultat de purged_walk_forward en métriques de verdict.

    Returns:
        dict(n_windows, pct_oos_profitable, oos_sharpe_mean, oos_sharpe_min,
             oos_pf_mean, all_profitable).
        pct_oos_profitable alimente le critère verdict "≥ 70% fenêtres OOS rentables".
    """
    if len(wf_df) == 0:
        return dict(n_windows=0, pct_oos_profitable=0.0, oos_sharpe_mean=0.0,
                    oos_sharpe_min=0.0, oos_pf_mean=0.0, all_profitable=False)
    return dict(
        n_windows=len(wf_df),
        pct_oos_profitable=float(wf_df["oos_profitable"].mean()),
        oos_sharpe_mean=float(wf_df["oos_sharpe"].mean()),
        oos_sharpe_min=float(wf_df["oos_sharpe"].min()),
        oos_pf_mean=float(wf_df["oos_pf"].replace([np.inf, -np.inf], np.nan).mean()),
        all_profitable=bool(wf_df["oos_profitable"].all()),
    )
```

- [ ] **Step 4: Lancer les tests — ils doivent PASSER**

Run: `cd "C:/Users/ryadb/OneDrive/QUANT MATHS"; python -m pytest 02_validation/gauntlet/tests/test_walk_forward.py -v`
Expected: PASS — 6 tests passés.

- [ ] **Step 5: Commit**

```bash
git add 02_validation/gauntlet/walk_forward.py 02_validation/gauntlet/tests/test_walk_forward.py
git commit -m "feat(gauntlet): walk_forward - walk-forward purgé à fenêtres ancrées"
```

---

### Task 4 : `stress_test.py` — rejoue le meilleur variant sur les périodes rouges

**Files:**
- Create: `02_validation/gauntlet/stress_test.py`
- Create: `02_validation/gauntlet/tests/test_stress_test.py`

**Pourquoi :** une stratégie peut afficher un beau Sharpe moyen et **mourir quand même** sur une fenêtre hostile. Le stress test rejoue le meilleur variant sur les krachs présents dans les données (2021-05 → 2026-05) et vérifie le critère **existentiel** Apex : le seuil DD EOD n'est **jamais touché** (sinon le compte est mort définitivement). Périodes retenues, dans la plage de données : bear 2022, dénouement du carry yen d'août 2024, selloff tarifs d'avril 2025. COVID (mars 2020) et Q4 2018 sont hors plage — le verdict (Plan 3) signalera la couverture stress comme partielle. `run_variant` est injecté ; `stress_test` lit `account.status` pour savoir si le compte a survécu à chaque période.

- [ ] **Step 1: Écrire les tests qui échouent**

Create `02_validation/gauntlet/tests/test_stress_test.py` :

```python
"""Tests du stress test sur périodes rouges."""
import numpy as np
import pandas as pd

from gauntlet.stress_test import run_stress_test, stress_test_passed, RED_PERIODS
from gauntlet.pa_account import PaAccount


def _make_df():
    """DataFrame couvrant 2021-2026 (1 barre/jour) — contenu indifférent (run_variant factice)."""
    idx = pd.date_range("2021-06-01", "2026-04-01", freq="1D", tz="UTC")
    return pd.DataFrame({"close": np.arange(len(idx), dtype=float)}, index=idx)


def _trades(pnl_list):
    return pd.DataFrame({
        "pnl_usd": pnl_list,
        "date": pd.date_range("2022-01-03", periods=len(pnl_list), freq="D"),
    })


def test_stress_runs_all_periods():
    df = _make_df()

    def rv(sub, params):
        return _trades([10.0, -5.0, 8.0]), PaAccount()   # compte vivant

    res = run_stress_test(df, {"x": 1}, rv)
    assert len(res) == len(RED_PERIODS)
    assert set(res["period"]) == set(RED_PERIODS.keys())


def test_stress_flags_dead_account():
    df = _make_df()

    def rv(sub, params):
        acc = PaAccount()
        # période bear_2022 : on simule un compte tué par le seuil EOD
        if sub.index[0] < pd.Timestamp("2023-01-01", tz="UTC"):
            acc.status = "dead_eod"
        return _trades([-500.0, -600.0]), acc

    res = run_stress_test(df, {"x": 1}, rv).set_index("period")
    assert not res.loc["bear_2022", "survived"]
    assert res.loc["yen_unwind_aug2024", "survived"]
    assert stress_test_passed(res.reset_index()) is False


def test_stress_empty_period_handled():
    # df qui ne couvre AUCUNE période rouge -> toutes les lignes vides, survived=True
    idx = pd.date_range("2027-01-01", "2027-02-01", freq="1D", tz="UTC")
    df = pd.DataFrame({"close": np.arange(len(idx), dtype=float)}, index=idx)

    def rv(sub, params):
        raise AssertionError("run_variant ne doit pas être appelé sur une période vide")

    res = run_stress_test(df, {"x": 1}, rv)
    assert (res["n_trades"] == 0).all()
    assert res["survived"].all()


def test_stress_custom_periods():
    df = _make_df()
    custom = {"my_crash": (pd.Timestamp("2023-03-01", tz="UTC"),
                           pd.Timestamp("2023-03-31", tz="UTC"))}

    def rv(sub, params):
        return _trades([1.0, 2.0]), PaAccount()

    res = run_stress_test(df, {"x": 1}, rv, red_periods=custom)
    assert list(res["period"]) == ["my_crash"]


def test_stress_test_passed_all_survive():
    df = _make_df()

    def rv(sub, params):
        return _trades([5.0, 6.0]), PaAccount()

    res = run_stress_test(df, {"x": 1}, rv)
    assert stress_test_passed(res) is True
```

- [ ] **Step 2: Lancer les tests — ils doivent ÉCHOUER**

Run: `cd "C:/Users/ryadb/OneDrive/QUANT MATHS"; python -m pytest 02_validation/gauntlet/tests/test_stress_test.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'gauntlet.stress_test'`

- [ ] **Step 3: Implémenter `stress_test.py`**

Create `02_validation/gauntlet/stress_test.py` :

```python
"""Stress test — rejoue le meilleur variant sur les périodes rouges historiques.

Une stratégie peut avoir un beau Sharpe moyen et mourir quand même sur une fenêtre
hostile. Le stress test rejoue le variant sur les krachs disponibles dans les données
(2021-05 -> 2026-05) et vérifie le critère existentiel Apex : le seuil DD EOD n'est
JAMAIS touché (sinon compte mort définitif).

Périodes COVID (mars 2020) et Q4 2018 hors plage de données -> couverture stress
partielle, le verdict (Plan 3) le signalera.

run_variant est INJECTÉ (cf. plan §"Le contrat run_variant").
"""
from __future__ import annotations

import pandas as pd

from src.backtest import compute_trade_metrics

# Périodes rouges dans la plage de données (index df attendu en UTC, cf. src/config.py).
# Bornes [start, end).
RED_PERIODS = {
    "bear_2022": (
        pd.Timestamp("2022-01-03", tz="UTC"), pd.Timestamp("2022-10-14", tz="UTC")),
    "yen_unwind_aug2024": (
        pd.Timestamp("2024-07-29", tz="UTC"), pd.Timestamp("2024-08-09", tz="UTC")),
    "tariff_selloff_apr2025": (
        pd.Timestamp("2025-04-01", tz="UTC"), pd.Timestamp("2025-04-30", tz="UTC")),
}


def run_stress_test(df, best_params, run_variant, red_periods: dict = RED_PERIODS) -> pd.DataFrame:
    """Rejoue le meilleur variant sur chaque période rouge.

    Args:
        df: DataFrame préparé, indexé DatetimeIndex tz-aware.
        best_params: le param dict du meilleur variant (sélectionné par le walk-forward).
        run_variant: callable(df_slice, params) -> (trades_df, account). Injecté.
        red_periods: dict {nom: (start, end)} — bornes [start, end).

    Returns:
        DataFrame, une ligne par période :
        [period, start, end, n_trades, pnl, max_dd, survived].
        survived = le compte n'a PAS touché le seuil DD EOD (account.status != 'dead_eod').
        Période hors plage de données -> n_trades=0, pnl=0, max_dd=0, survived=True
        (vacuité : pas de trading, pas de mort).
    """
    rows = []
    for name, (start, end) in red_periods.items():
        sub = df.loc[(df.index >= start) & (df.index < end)]
        if len(sub) == 0:
            rows.append({"period": name, "start": start, "end": end,
                         "n_trades": 0, "pnl": 0.0, "max_dd": 0.0, "survived": True})
            continue
        trades, account = run_variant(sub, best_params)
        m = compute_trade_metrics(trades)
        survived = account is None or account.status != "dead_eod"
        rows.append({
            "period": name, "start": start, "end": end,
            "n_trades": m["trades"], "pnl": m["pnl"], "max_dd": m["max_dd"],
            "survived": survived,
        })
    return pd.DataFrame(rows)


def stress_test_passed(stress_df: pd.DataFrame) -> bool:
    """True si le compte a survécu à TOUTES les périodes rouges (critère verdict)."""
    if len(stress_df) == 0:
        return False
    return bool(stress_df["survived"].all())
```

- [ ] **Step 4: Lancer les tests — ils doivent PASSER**

Run: `cd "C:/Users/ryadb/OneDrive/QUANT MATHS"; python -m pytest 02_validation/gauntlet/tests/test_stress_test.py -v`
Expected: PASS — 5 tests passés.

- [ ] **Step 5: Commit**

```bash
git add 02_validation/gauntlet/stress_test.py 02_validation/gauntlet/tests/test_stress_test.py
git commit -m "feat(gauntlet): stress_test - rejoue le meilleur variant sur les périodes rouges"
```

---

### Task 5 : `pa_cycle.py` — analyse d'un cycle PA continu

**Files:**
- Create: `02_validation/gauntlet/pa_cycle.py`
- Create: `02_validation/gauntlet/tests/test_pa_cycle.py`

**Pourquoi :** le walk-forward et le stress test regardent des **fenêtres**. Le cycle PA regarde le compte **en continu** : un seul `PaAccount`, jour après jour, sur tout l'historique de simulation (Train+Valid). Trois questions auxquelles seul un run continu répond. **Survie** : le compte touche-t-il jamais le seuil DD EOD ? (touché = mort définitive). **Lock** : atteint-il le plafond figé $50,100 ? — ce qui arrive quand une **clôture journalière** dépasse $52,100 (`seuil = min(plus_haute_clôture − 2000, 50100)` ⇒ figé dès `plus_haute_clôture ≥ 52100`). **Inactivité** : respecte-t-il la règle Apex « ≥ 2 jours à ≥ $50 net / 30 jours glissants » ? — un edge "rares gros gains" peut survivre **et** se faire fermer le compte pour inactivité. Le module sépare `analyze_pa_cycle(account)` (analyse pure d'un compte déjà avancé — tout le contenu testable est là) et `run_pa_cycle(...)` (wrapper mince qui appelle `run_variant` puis analyse).

- [ ] **Step 1: Écrire les tests qui échouent**

Create `02_validation/gauntlet/tests/test_pa_cycle.py` :

```python
"""Tests de la simulation cycle PA."""
import pandas as pd

from gauntlet.pa_account import PaAccount
from gauntlet.pa_cycle import analyze_pa_cycle, run_pa_cycle, _daily_net_pnl


def _account_with_history(history, status="alive"):
    """PaAccount avec un daily_history injecté à la main (teste l'analyse seule)."""
    acc = PaAccount()
    acc.daily_history = history
    acc.status = status
    if history:
        acc.balance = history[-1][1]
    return acc


def test_analyze_survived_account():
    hist = [("2026-01-02", 50_300.0, 1), ("2026-01-03", 50_500.0, 1)]
    res = analyze_pa_cycle(_account_with_history(hist))
    assert res["survived"] is True
    assert res["n_trading_days"] == 2
    assert res["final_balance"] == 50_500.0


def test_analyze_dead_account():
    hist = [("2026-01-02", 49_000.0, 1)]
    res = analyze_pa_cycle(_account_with_history(hist, status="dead_eod"))
    assert res["survived"] is False


def test_analyze_reached_lock_and_days():
    # la clôture franchit 52_100 au 3e jour -> reached_lock=True, days_to_lock=3
    hist = [
        ("2026-01-02", 51_000.0, 1),
        ("2026-01-05", 51_800.0, 2),
        ("2026-01-06", 52_300.0, 3),
        ("2026-01-07", 52_000.0, 3),
    ]
    res = analyze_pa_cycle(_account_with_history(hist))
    assert res["reached_lock"] is True
    assert res["days_to_lock"] == 3


def test_analyze_never_locks():
    hist = [("2026-01-02", 50_500.0, 1), ("2026-01-05", 51_000.0, 1)]
    res = analyze_pa_cycle(_account_with_history(hist))
    assert res["reached_lock"] is False
    assert res["days_to_lock"] is None


def test_daily_net_pnl():
    hist = [("2026-01-02", 50_300.0, 1), ("2026-01-05", 50_100.0, 1)]
    nets = _daily_net_pnl(hist)
    assert nets[0] == ("2026-01-02", 300.0)     # 50_300 - 50_000 (ACCOUNT_SIZE)
    assert nets[1] == ("2026-01-05", -200.0)    # 50_100 - 50_300


def test_analyze_inactivity_safe():
    # 90 jours, +$100 net chaque jour -> chaque fenêtre 30j a >> 2 jours verts
    hist = []
    bal = 50_000.0
    for d in pd.date_range("2026-01-01", periods=90, freq="D"):
        bal += 100.0
        hist.append((d.date(), bal, 1))
    res = analyze_pa_cycle(_account_with_history(hist))
    assert res["inactivity_safe"] is True
    assert res["inactivity_first_violation"] is None


def test_analyze_inactivity_violation():
    # 90 jours : 1 seul jour vert au début, puis 89 jours plats ($0 net) -> une fenêtre
    # 30j sans 2 jours verts -> violation
    hist = []
    dates = pd.date_range("2026-01-01", periods=90, freq="D")
    bal = 50_000.0 + 100.0                       # jour 0 : vert
    hist.append((dates[0].date(), bal, 1))
    for d in dates[1:]:                          # jours 1..89 : plats
        hist.append((d.date(), bal, 1))
    res = analyze_pa_cycle(_account_with_history(hist))
    assert res["inactivity_safe"] is False
    assert res["inactivity_first_violation"] is not None


def test_run_pa_cycle_wrapper():
    df = pd.DataFrame({"close": [1.0, 2.0, 3.0]},
                      index=pd.date_range("2026-01-01", periods=3, freq="D", tz="UTC"))
    hist = [("2026-01-02", 50_400.0, 1), ("2026-01-03", 50_800.0, 1)]

    def rv(d, params):
        trades = pd.DataFrame({"pnl_usd": [400.0, 400.0]})
        return trades, _account_with_history(hist)

    res = run_pa_cycle(df, {"x": 1}, rv)
    assert res["n_trades"] == 2
    assert res["n_trading_days"] == 2
    assert res["survived"] is True
```

- [ ] **Step 2: Lancer les tests — ils doivent ÉCHOUER**

Run: `cd "C:/Users/ryadb/OneDrive/QUANT MATHS"; python -m pytest 02_validation/gauntlet/tests/test_pa_cycle.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'gauntlet.pa_cycle'`

- [ ] **Step 3: Implémenter `pa_cycle.py`**

Create `02_validation/gauntlet/pa_cycle.py` :

```python
"""Simulation cycle PA — le meilleur variant survit-il à un compte PA EOD continu ?

Le walk-forward et le stress test regardent des fenêtres. Le cycle PA regarde le compte
en CONTINU sur tout l'historique : un seul PaAccount, jour après jour. Trois questions :
  - survie     : le compte touche-t-il jamais le seuil DD EOD ? (touché = mort définitive)
  - lock       : atteint-il le plafond figé $50,100 ? (= une clôture journalière >= $52,100)
  - inactivité : respecte-t-il la règle Apex >= 2 jours à >= $50 net / 30 jours glissants ?
                 Un edge "rares gros gains" peut survivre ET se faire fermer pour inactivité.

run_variant est INJECTÉ (cf. plan §"Le contrat run_variant").
"""
from __future__ import annotations

import pandas as pd

from gauntlet.pa_rules import (
    ACCOUNT_SIZE, EOD_DD, EOD_THRESHOLD_LOCK,
    INACTIVITY_MIN_GREEN_DAYS, INACTIVITY_GREEN_THRESHOLD, INACTIVITY_WINDOW_DAYS,
)

# Plus haute clôture journalière qui déclenche le lock du seuil :
# seuil = min(highest_close - 2000, 50_100) == 50_100  <=>  highest_close >= 52_100.
_LOCK_CLOSE = EOD_THRESHOLD_LOCK + EOD_DD          # 52_100.0


def _daily_net_pnl(daily_history: list) -> list:
    """[(date, eod_close, tier), ...] -> [(date, net_pnl_du_jour), ...].

    net du jour 0 = clôture - ACCOUNT_SIZE ; net du jour i = clôture i - clôture i-1.
    """
    out = []
    prev = ACCOUNT_SIZE
    for date, eod_close, _tier in daily_history:
        out.append((date, eod_close - prev))
        prev = eod_close
    return out


def _inactivity_check(daily_history: list):
    """Vérifie la règle d'inactivité Apex sur toutes les fenêtres glissantes de 30 jours.

    Pour chaque jour de trading d dont la fenêtre [d, d+30j) est ENTIÈREMENT couverte par
    l'historique : compte les jours "verts" (net >= $50). Si une fenêtre a < 2 verts ->
    violation. Les fenêtres en fin d'historique (pas encore 30j de recul) ne sont pas
    jugées — pas assez de données pour conclure.

    Returns: (safe: bool, first_violation_date: date | None).
    """
    nets = _daily_net_pnl(daily_history)
    if not nets:
        return True, None
    dates = [pd.Timestamp(d) for d, _ in nets]
    green = [pd.Timestamp(d) for d, net in nets if net >= INACTIVITY_GREEN_THRESHOLD]
    last_date = dates[-1]
    window = pd.Timedelta(days=INACTIVITY_WINDOW_DAYS)
    for d in dates:
        if d + window > last_date:
            break                                  # fenêtre incomplète -> on s'arrête
        n_green = sum(1 for g in green if d <= g < d + window)
        if n_green < INACTIVITY_MIN_GREEN_DAYS:
            return False, d.date()
    return True, None


def analyze_pa_cycle(account) -> dict:
    """Analyse un PaAccount après un run complet sur l'historique.

    Args:
        account: PaAccount déjà avancé par backtest_pa sur tout l'historique.

    Returns:
        dict(survived, reached_lock, days_to_lock, final_balance, n_trading_days,
             inactivity_safe, inactivity_first_violation).
    """
    survived = account.status != "dead_eod"
    history = account.daily_history

    # Lock : 1er jour où la plus haute clôture cumulée atteint $52,100.
    reached_lock, days_to_lock = False, None
    running_max = ACCOUNT_SIZE
    for i, (_date, eod_close, _tier) in enumerate(history):
        if eod_close > running_max:
            running_max = eod_close
        if running_max >= _LOCK_CLOSE:
            reached_lock, days_to_lock = True, i + 1
            break

    final_balance = history[-1][1] if history else account.balance
    inactivity_safe, first_violation = _inactivity_check(history)

    return dict(
        survived=survived,
        reached_lock=reached_lock,
        days_to_lock=days_to_lock,
        final_balance=final_balance,
        n_trading_days=len(history),
        inactivity_safe=inactivity_safe,
        inactivity_first_violation=first_violation,
    )


def run_pa_cycle(df, best_params, run_variant) -> dict:
    """Rejoue le meilleur variant sur tout l'historique (un seul PaAccount continu),
    puis analyse le compte.

    Args:
        df: DataFrame préparé couvrant l'historique de simulation (Train+Valid).
        best_params: param dict du meilleur variant.
        run_variant: callable(df, params) -> (trades_df, account). Injecté.

    Returns:
        analyze_pa_cycle(account) enrichi de 'n_trades'.
    """
    trades, account = run_variant(df, best_params)
    result = analyze_pa_cycle(account)
    result["n_trades"] = len(trades)
    return result
```

- [ ] **Step 4: Lancer les tests — ils doivent PASSER**

Run: `cd "C:/Users/ryadb/OneDrive/QUANT MATHS"; python -m pytest 02_validation/gauntlet/tests/test_pa_cycle.py -v`
Expected: PASS — 8 tests passés.

- [ ] **Step 5: Commit**

```bash
git add 02_validation/gauntlet/pa_cycle.py 02_validation/gauntlet/tests/test_pa_cycle.py
git commit -m "feat(gauntlet): pa_cycle - analyse cycle PA continu (survie / lock / inactivité)"
```

---

### Task 6 : Test d'intégration de bout en bout — la batterie tourne

**Files:**
- Create: `02_validation/gauntlet/tests/test_integration_plan2.py`

**Pourquoi :** les tasks 1-5 testent chaque module isolément avec un `run_variant` factice. Cette task vérifie que les six modules **s'assemblent sur un vrai `run_variant`** — construit ici à partir du socle Plan 1 (`backtest_pa` + `PaAccount` + une `signal_fn` triviale). On enchaîne walk-forward → sélection du meilleur param → Monte Carlo → CPCV → DSR → stress test → cycle PA. C'est le test de câblage de la batterie : si ça passe, Plan 2 est fonctionnel et Plan 3 (verdict + orchestration `run_gauntlet`) peut se brancher dessus. Le `run_variant` réel de Plan 2 prouve aussi que le contrat (`df, params) -> (trades_df, account)` tient sur le `backtest_pa` du Plan 1.

- [ ] **Step 1: Écrire le test d'intégration**

Create `02_validation/gauntlet/tests/test_integration_plan2.py` :

```python
"""Intégration Plan 2 : la batterie statistique tourne de bout en bout.

Construit un run_variant RÉEL (signal trivial + backtest_pa sur PaAccount), puis fait
tourner les six modules : walk-forward, CPCV, DSR, Monte Carlo, stress test, cycle PA.
Si ça passe, Plan 2 est fonctionnel et Plan 3 (verdict + orchestration) peut se brancher.
"""
import numpy as np
import pandas as pd

from gauntlet.pa_account import PaAccount
from gauntlet.backtest import backtest_pa
from gauntlet.walk_forward import purged_walk_forward, walk_forward_summary
from gauntlet.monte_carlo import permutation_test_sharpe, dd_distribution_shuffle
from gauntlet.cpcv import sharpe_distribution_cpcv
from gauntlet.deflated_sharpe import deflated_sharpe_ratio
from gauntlet.stress_test import run_stress_test, stress_test_passed
from gauntlet.pa_cycle import run_pa_cycle

MNQ_SPECS = {
    "point_value": 2.00, "tick_size": 0.25, "commission_rt": 1.10,
    "sl_floor_pts": 5.0, "sl_cap_pts": 10.0,
}


def _prepared_df(n_days: int = 60) -> pd.DataFrame:
    """n_days jours ouvrés, 12 barres 5min/jour (14:30->15:25 NY), prix oscillant autour
    de mid=100 avec un léger drift jour-à-jour (pour que le PnL journalier varie -> les
    Sharpe CPCV ne sont pas tous dégénérés)."""
    rng = np.random.default_rng(2026)
    days = pd.bdate_range("2022-01-03", periods=n_days)
    rows = []
    for d in days:
        day_drift = rng.normal(0.0, 1.0)
        base = pd.Timestamp(d.year, d.month, d.day, 14, 30, tz="America/New_York")
        for b in range(12):
            ts = base + pd.Timedelta(minutes=5 * b)
            close = 100.0 + (3.0 if b % 2 == 0 else -3.0) + day_drift
            rows.append((ts, close))
    idx = pd.DatetimeIndex([r[0] for r in rows])
    closes = np.array([r[1] for r in rows])
    df = pd.DataFrame({
        "close": closes, "high": closes + 0.5, "low": closes - 0.5,
        "std": 4.0, "mid": 100.0,
    }, index=idx)
    df["hour_ny"] = df.index.hour
    df["min_ny"] = df.index.minute
    df["date"] = df.index.date
    return df


def _run_variant(df, params):
    """run_variant RÉEL : signal MR trivial (LONG si close>mid) + backtest_pa sur un
    PaAccount neuf. Conforme au contrat (df, params) -> (trades_df, account)."""
    out = df.copy()
    out["signal"] = 0
    out.loc[out["close"] > out["mid"], "signal"] = 1

    def exit_logic(d, i, j, direction, entry_price, std_i, mid_i,
                   or_high, or_low, or_range, sl_pts):
        if direction == 1 and d.at[j, "close"] <= d.at[j, "mid"]:
            return True, d.at[j, "close"], "TP_back_to_mid"
        return False, 0.0, ""

    acc = PaAccount()
    trades = backtest_pa(out, exit_logic, MNQ_SPECS, acc,
                         bar_size_min=5, timeout_bars=params["timeout_bars"])
    return trades, acc


def test_plan2_battery_runs_end_to_end():
    df = _prepared_df(n_days=60)
    grid = [{"timeout_bars": 2}, {"timeout_bars": 4}]

    # ── Walk-forward purgé ───────────────────────────────────────
    wf = purged_walk_forward(df, grid, _run_variant, n_windows=3, embargo_bars=5)
    assert len(wf) == 3
    wf_sum = walk_forward_summary(wf)
    assert 0.0 <= wf_sum["pct_oos_profitable"] <= 1.0
    best_params = wf.iloc[-1]["best_params"]
    assert best_params in grid

    # ── Un run plein pour alimenter les tests sur trades ─────────
    trades, account = _run_variant(df, best_params)
    assert len(trades) > 0
    pnl = trades["pnl_usd"].to_numpy()

    # ── Monte Carlo : sign-flip (Sharpe) + order-shuffle (DD) ────
    mc = permutation_test_sharpe(pnl, n_iter=500, seed=0)
    assert 0.0 <= mc["p_value"] <= 1.0
    dd = dd_distribution_shuffle(pnl, n_iter=500, seed=0)
    assert dd["dd_p50"] >= dd["dd_worst"]

    # ── CPCV + Deflated Sharpe ───────────────────────────────────
    cpcv = sharpe_distribution_cpcv(trades, n_groups=5, k_test=2,
                                    date_col="date", pnl_col="pnl_usd")
    assert len(cpcv) > 0
    daily = trades.groupby("date")["pnl_usd"].sum().to_numpy()
    dsr = deflated_sharpe_ratio(daily, n_trials=len(grid), sr_variance=0.3 ** 2)
    assert 0.0 <= dsr <= 1.0

    # ── Stress test (période custom dans la plage synthétique) ───
    custom_red = {
        "synthetic_crash": (pd.Timestamp("2022-02-01", tz="America/New_York"),
                            pd.Timestamp("2022-02-15", tz="America/New_York")),
    }
    stress = run_stress_test(df, best_params, _run_variant, red_periods=custom_red)
    assert len(stress) == 1
    assert isinstance(stress_test_passed(stress), bool)

    # ── Cycle PA ─────────────────────────────────────────────────
    cycle = run_pa_cycle(df, best_params, _run_variant)
    assert "survived" in cycle
    assert cycle["n_trading_days"] >= 1
    assert cycle["n_trades"] == len(trades)
```

- [ ] **Step 2: Lancer le test — il doit PASSER**

Run: `cd "C:/Users/ryadb/OneDrive/QUANT MATHS"; python -m pytest 02_validation/gauntlet/tests/test_integration_plan2.py -v`
Expected: PASS — 1 test passé. (Toutes les briques sont déjà implémentées — ce test ne fait que les assembler sur un vrai `run_variant`.)

- [ ] **Step 3: Lancer toute la suite gauntlet**

Run: `cd "C:/Users/ryadb/OneDrive/QUANT MATHS"; python -m pytest 02_validation/gauntlet/tests/ -v`
Expected: PASS — toute la suite gauntlet (Plan 1 : smoke + pa_rules + hypothesis + splits + pa_account + backtest + integration_plan1 ; Plan 2 : cpcv + deflated_sharpe + monte_carlo + walk_forward + stress_test + pa_cycle + integration_plan2).

- [ ] **Step 4: Commit**

```bash
git add 02_validation/gauntlet/tests/test_integration_plan2.py
git commit -m "test(gauntlet): integration Plan 2 - la batterie statistique tourne de bout en bout"
```

---

## Self-Review (effectuée à l'écriture du plan)

**1. Couverture spec** — Plan 2 couvre les Blocs 3 et 4 du spec :
- Bloc 3 — Batterie statistique : walk-forward purgé ✓ (Task 3), CPCV ✓ (Task 1, consolidé), Deflated Sharpe Ratio ✓ (Task 1, consolidé), PBO ✓ (Task 1, consolidé), Monte Carlo permutation ✓ (Task 2).
- Bloc 4 — Robustesse : stress test périodes rouges ✓ (Task 4), simulation cycle PA ✓ (Task 5).
- Le Bloc 5 (`verdict.py`), l'orchestrateur `run_gauntlet.py` et les hypothèses de calibration sont **explicitement reportés à Plan 3** — c'est la décomposition annoncée à BB.
- Écart assumé vs le texte du spec : « Monte Carlo permutation : permute les returns des trades » est techniquement faux (le Sharpe est order-invariant). Remplacé par sign-flip + shuffle DD — **décision BB actée** (documentée en tête de plan et dans la docstring de `monte_carlo.py`).
- Écart assumé vs le texte du spec : le spec dit « les imports de `run_final_validation.py` sont corrigés ». En réalité ce fichier est déjà mort (importe `quant_v10` qui ne résout pas) — **décision BB actée** : supprimé plutôt que réparé.

**2. Placeholders** — aucun TBD/TODO ; tout le code est complet et exécutable. Les périodes rouges sont des dates concrètes. Le `run_variant` concret (data-load réel) est marqué Plan 3, ce n'est pas un placeholder mais une frontière de plan explicite.

**3. Cohérence des types** — le contrat `run_variant(df, params) -> (trades_df, account)` est identique dans `walk_forward`, `stress_test`, `pa_cycle`, leurs tests, et l'intégration Task 6. `compute_trade_metrics` (importé de `src.backtest`) retourne `dict(trades, pf, sharpe, max_dd, wr, pnl, avg_trade)` — les clés utilisées (`sharpe`, `pf`, `pnl`, `max_dd`, `trades`) existent toutes. `PaAccount` : attributs lus (`status`, `daily_history`, `balance`) cohérents avec Plan 1. `analyze_pa_cycle` retourne les mêmes clés entre la def (Task 5) et les assertions des tests. La sortie `backtest_pa` (colonnes `pnl_usd`, `date`) est cohérente avec ce que `compute_trade_metrics`, `sharpe_distribution_cpcv` (`pnl_col="pnl_usd"`, `date_col="date"`) et le Monte Carlo consomment. Le Sharpe est partout en convention repo (per-trade × √252).

**4. Risque connu** — `cpcv.py` et `deflated_sharpe.py` sont consolidés sans relecture ligne à ligne de leur logique (ils ont leurs tests, ressuscités en Task 1 — c'est le filet). Si un test CPCV/DSR échoue après le `git mv`, c'est soit un bug latent préexistant, soit un problème de path : investiguer, ne pas affaiblir l'assertion. Pour `walk_forward`/`stress_test`/`pa_cycle`, le risque est dans le contrat `run_variant` — d'où l'intégration Task 6 qui le valide sur un vrai `backtest_pa`.
