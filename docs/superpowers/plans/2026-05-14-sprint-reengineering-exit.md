# Sprint Re-engineering Exit — EOD Reversal MNQ — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tester si l'edge EOD Reversal MNQ se capture avec un exit qui se résout avant le force-flat Apex 16:00, via une grille délibérée de 8 configs d'exit mesurées Apex-compliant sur 5min et 15min.

**Architecture:** 4 nouvelles fonctions `exit_logic_*` réutilisables ajoutées à `01_research/src/backtest.py` (TDD strict, tests unitaires sur données synthétiques). Orchestration dans un fichier jupytext percent-format `01_research/notebooks/02_sprint_exit_reengineering.py` (runnable en `python` ET ouvrable comme notebook), converti en `.ipynb` en fin de sprint. Le notebook ne contient aucune logique réutilisable — il consomme `src/`.

**Tech Stack:** Python 3.10+, pandas, numpy, pytest, jupytext. Réutilise les modules existants `src/data_loader.py`, `src/features.py`, `src/signals.py`, `src/backtest.py`, `src/instruments.py`, `src/config.py`.

**Spec de référence:** `docs/superpowers/specs/2026-05-14-sprint-reengineering-eod-reversal-design.md`

---

## Contexte vérifié pendant la planification

Équivalence confirmée entre les modules `src/` et le pipeline inline de mini-validation #4
(`01_research/run_exploration_MR_MNQ_apex_compliant.py`) — la config-contrôle C0 doit donc
reproduire les chiffres de mini-val #4 :

| Module `src/` | Équivalent mini-val #4 |
|---|---|
| `data_loader.load_continuous(path, 'MNQ')` | `load_mnq_continuous` (verbatim) |
| `data_loader.resample_ohlcv` | `resample_ohlcv` (verbatim) |
| `data_loader.add_temporal_columns` + `filter_session_ny` | colonnes temporelles + filtre session inline |
| `features.compute_signal_features(df, lookback=20)` | `compute_signal_features` (verbatim) |
| `signals.signal_mr_zscore` | `generate_mr_signals` (logique identique) |
| `backtest.backtest_apex` + `exit_logic_mr_zscore` | `backtest_apex_compliant` (z-score exit, logique identique) |

Specs MNQ (`src/instruments.py`) : `point_value=2.00`, `tick_size=0.25`, `commission_rt=1.10`,
`sl_floor_pts=5.0`, `sl_cap_pts=10.0`. Constantes Apex (`src/config.py`) :
`ENTRY_CUTOFF_NY_MIN=955`, `EXIT_FORCE_NY_MIN=959`. Toutes cohérentes avec mini-val #4.

**Chiffres de référence mini-val #4 (Train, Apex-compliant)** — pour l'assertion C0 :
- 5min : `trades=632`, `PF=0.8009`
- 15min : `trades=180`, `PF=0.7664`

**Paramètres par timeframe** (identiques à mini-val #4) :
- 5min : `rule='5min'`, `bar_size_min=5`, `timeout_bars=12`
- 15min : `rule='15min'`, `bar_size_min=15`, `timeout_bars=4`

---

## File Structure

| Fichier | Responsabilité | Action |
|---|---|---|
| `01_research/src/backtest.py` | + 4 fonctions `exit_logic_*` réutilisables | Modify |
| `01_research/conftest.py` | Ajoute `01_research/` à `sys.path` pour pytest | Create |
| `01_research/tests/test_exit_logics.py` | Tests unitaires des 4 exit logics (données synthétiques) | Create |
| `pyproject.toml` | Ajoute `01_research/tests` à `testpaths` | Modify |
| `requirements-dev.txt` | Ajoute `jupytext` | Modify |
| `01_research/notebooks/02_sprint_exit_reengineering.py` | Orchestration jupytext percent-format (runnable standalone) | Create |
| `01_research/notebooks/02_sprint_exit_reengineering.ipynb` | Notebook généré depuis le `.py` | Create (Task 10) |
| `01_research/outputs/sprint_exit/ranking.csv` | Métriques de toutes les configs × TF, Train + Valid | Généré au run |
| `01_research/outputs/sprint_exit/sprint_exit_report.md` | Verdict, n_trials, interprétation, recommandation | Généré au run |
| `01_research/outputs/sprint_exit/run_log.txt` | Log d'exécution complet | Généré au run |

---

## Les 8 configs d'exit

| Nom | Fonction | Paramètres |
|---|---|---|
| `C0_zscore_0.5` | `exit_logic_mr_zscore` (existant) | `zscore_exit=0.5` — **contrôle harness** |
| `C1_zscore_1.0` | `exit_logic_mr_zscore` (existant) | `zscore_exit=1.0` |
| `C2_zscore_1.5` | `exit_logic_mr_zscore` (existant) | `zscore_exit=1.5` |
| `C3_fixed_0.75std` | `exit_logic_fixed_tp_std` (Task 2) | `tp_std_mult=0.75` |
| `C4_fixed_0.40std` | `exit_logic_fixed_tp_std` (Task 2) | `tp_std_mult=0.40` |
| `C5_time_stop` | `exit_logic_time_stop` (Task 3) | `exit_ny_min` = 955 (5min) / 945 (15min) |
| `C6_trail_1.0std` | `exit_logic_trailing_std` (Task 4) | `trail_std_mult=1.0` |
| `C7_hybrid` | `exit_logic_hybrid_zscore_time` (Task 5) | `zscore_exit=1.0`, `exit_ny_min` = 955/945 |

`exit_ny_min` est calibré une barre avant le force-flat Apex (959) : pour 5min la barre
15:50→15:55 a `close_min_ny=955` ; pour 15min la barre 15:30→15:45 a `close_min_ny=945`.
À granularité de barre, "exit 15:58" n'existe pas — `exit_ny_min` réalise l'intention de la
spec ("exit près du close, avant le force-flat") de façon correcte.

**n_trials = 16** (8 configs × 2 TF) — loggé dans le rapport pour le budget DSR de l'Étape 2.

---

### Task 1: Infrastructure pytest pour `01_research/`

**Files:**
- Create: `01_research/conftest.py`
- Create: `01_research/tests/test_exit_logics.py` (squelette vide pour cette task)
- Modify: `pyproject.toml:55-60`

- [ ] **Step 1: Créer le conftest qui expose `src/` à pytest**

Create `01_research/conftest.py` :

```python
"""Ajoute 01_research/ à sys.path pour que les tests puissent faire `from src... import ...`."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
```

- [ ] **Step 2: Créer le fichier de tests avec un test sentinelle**

Create `01_research/tests/test_exit_logics.py` :

```python
"""Tests unitaires des exit logics du sprint re-engineering — données synthétiques."""
import pandas as pd

from src.backtest import (
    exit_logic_fixed_tp_std,
    exit_logic_time_stop,
    exit_logic_trailing_std,
    exit_logic_hybrid_zscore_time,
)


def test_imports_ok():
    """Sentinelle : les 4 exit logics sont importables."""
    assert callable(exit_logic_fixed_tp_std)
    assert callable(exit_logic_time_stop)
    assert callable(exit_logic_trailing_std)
    assert callable(exit_logic_hybrid_zscore_time)
```

- [ ] **Step 3: Ajouter `01_research/tests` à testpaths**

Modify `pyproject.toml`, section `[tool.pytest.ini_options]` — remplacer la ligne `testpaths` :

```toml
testpaths = ["01_research/tests", "02_validation/v10/tests", "tests"]
```

- [ ] **Step 4: Lancer le test sentinelle — il doit ÉCHOUER**

Run: `python -m pytest 01_research/tests/test_exit_logics.py -v`
Expected: FAIL — `ImportError: cannot import name 'exit_logic_fixed_tp_std' from 'src.backtest'`

- [ ] **Step 5: Commit**

```bash
git add 01_research/conftest.py 01_research/tests/test_exit_logics.py pyproject.toml
git commit -m "test: infra pytest 01_research + squelette tests exit logics"
```

---

### Task 2: `exit_logic_fixed_tp_std` (configs C3, C4)

**Files:**
- Modify: `01_research/src/backtest.py` (ajout en fin de fichier, après `exit_logic_orb`)
- Test: `01_research/tests/test_exit_logics.py`

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à `01_research/tests/test_exit_logics.py` :

```python
def test_fixed_tp_std_long_hit():
    # entry 100, std 8, tp_std_mult 0.5 -> TP long = 100 + 1*0.5*8 = 104
    df = pd.DataFrame({'high': [100.0, 104.0], 'low': [100.0, 99.0], 'close': [100.0, 103.0]})
    touched, price, reason = exit_logic_fixed_tp_std(
        df, i=0, j=1, direction=1, entry_price=100.0, std_i=8.0, mid_i=100.0,
        or_high=float('nan'), or_low=float('nan'), or_range=float('nan'), sl_pts=7.5,
        tp_std_mult=0.5)
    assert touched is True
    assert price == 104.0
    assert reason == 'TP_fixed_std'


def test_fixed_tp_std_short_hit():
    # short: TP = 100 + (-1)*0.5*8 = 96
    df = pd.DataFrame({'high': [100.0, 101.0], 'low': [100.0, 95.0], 'close': [100.0, 97.0]})
    touched, price, reason = exit_logic_fixed_tp_std(
        df, i=0, j=1, direction=-1, entry_price=100.0, std_i=8.0, mid_i=100.0,
        or_high=float('nan'), or_low=float('nan'), or_range=float('nan'), sl_pts=7.5,
        tp_std_mult=0.5)
    assert touched is True
    assert price == 96.0
    assert reason == 'TP_fixed_std'


def test_fixed_tp_std_no_hit():
    # TP long = 104, high[1]=102 < 104 -> pas touché
    df = pd.DataFrame({'high': [100.0, 102.0], 'low': [100.0, 99.0], 'close': [100.0, 101.0]})
    touched, price, reason = exit_logic_fixed_tp_std(
        df, i=0, j=1, direction=1, entry_price=100.0, std_i=8.0, mid_i=100.0,
        or_high=float('nan'), or_low=float('nan'), or_range=float('nan'), sl_pts=7.5,
        tp_std_mult=0.5)
    assert touched is False
```

- [ ] **Step 2: Lancer les tests — ils doivent ÉCHOUER**

Run: `python -m pytest 01_research/tests/test_exit_logics.py -k fixed_tp_std -v`
Expected: FAIL — `ImportError: cannot import name 'exit_logic_fixed_tp_std'`

- [ ] **Step 3: Implémenter la fonction**

Ajouter à la fin de `01_research/src/backtest.py` :

```python
def exit_logic_fixed_tp_std(df, i, j, direction, entry_price, std_i, mid_i,
                            or_high, or_low, or_range, sl_pts,
                            tp_std_mult: float = 0.75):
    """TP fixe : entry +/- tp_std_mult * std_i, vérifié sur wicks (high/low).

    TP de type limit order : fill au prix exact, pas de slippage (cf. exit_logic_orb).
    Configs C3 (tp_std_mult=0.75) et C4 (0.40) du sprint re-engineering exit.
    """
    tp_price = entry_price + direction * tp_std_mult * std_i
    hj = df.at[j, 'high']
    lj = df.at[j, 'low']
    tp_touched = (direction == 1 and hj >= tp_price) or (direction == -1 and lj <= tp_price)
    if tp_touched:
        return True, tp_price, 'TP_fixed_std'
    return False, 0.0, ''
```

- [ ] **Step 4: Lancer les tests — ils doivent PASSER**

Run: `python -m pytest 01_research/tests/test_exit_logics.py -k fixed_tp_std -v`
Expected: PASS — 3 tests passés

- [ ] **Step 5: Commit**

```bash
git add 01_research/src/backtest.py 01_research/tests/test_exit_logics.py
git commit -m "feat: exit_logic_fixed_tp_std (configs C3/C4 sprint exit)"
```

---

### Task 3: `exit_logic_time_stop` (config C5)

**Files:**
- Modify: `01_research/src/backtest.py` (ajout après `exit_logic_fixed_tp_std`)
- Test: `01_research/tests/test_exit_logics.py`

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à `01_research/tests/test_exit_logics.py` :

```python
def test_time_stop_fires_at_cutoff():
    # j=1 : close_min_ny = 15*60 + 50 + 5 = 955 >= 955 -> exit MTM au close
    df = pd.DataFrame({'hour_ny': [15, 15], 'min_ny': [45, 50], 'close': [100.0, 101.0]})
    touched, price, reason = exit_logic_time_stop(
        df, i=0, j=1, direction=1, entry_price=100.0, std_i=5.0, mid_i=100.0,
        or_high=float('nan'), or_low=float('nan'), or_range=float('nan'), sl_pts=7.5,
        exit_ny_min=955, bar_size_min=5)
    assert touched is True
    assert price == 101.0
    assert reason == 'time_stop'


def test_time_stop_silent_before_cutoff():
    # j=1 : close_min_ny = 15*60 + 40 + 5 = 945 < 955 -> pas d'exit
    df = pd.DataFrame({'hour_ny': [15, 15], 'min_ny': [30, 40], 'close': [100.0, 101.0]})
    touched, price, reason = exit_logic_time_stop(
        df, i=0, j=1, direction=1, entry_price=100.0, std_i=5.0, mid_i=100.0,
        or_high=float('nan'), or_low=float('nan'), or_range=float('nan'), sl_pts=7.5,
        exit_ny_min=955, bar_size_min=5)
    assert touched is False


def test_time_stop_15min_cutoff_945():
    # 15min : close_min_ny = 15*60 + 30 + 15 = 945 >= 945 -> exit
    df = pd.DataFrame({'hour_ny': [15, 15], 'min_ny': [15, 30], 'close': [100.0, 102.0]})
    touched, price, reason = exit_logic_time_stop(
        df, i=0, j=1, direction=-1, entry_price=100.0, std_i=5.0, mid_i=100.0,
        or_high=float('nan'), or_low=float('nan'), or_range=float('nan'), sl_pts=7.5,
        exit_ny_min=945, bar_size_min=15)
    assert touched is True
    assert price == 102.0
    assert reason == 'time_stop'
```

- [ ] **Step 2: Lancer les tests — ils doivent ÉCHOUER**

Run: `python -m pytest 01_research/tests/test_exit_logics.py -k time_stop -v`
Expected: FAIL — `ImportError: cannot import name 'exit_logic_time_stop'`

- [ ] **Step 3: Implémenter la fonction**

Ajouter à la fin de `01_research/src/backtest.py` :

```python
def exit_logic_time_stop(df, i, j, direction, entry_price, std_i, mid_i,
                         or_high, or_low, or_range, sl_pts,
                         exit_ny_min: int = 955, bar_size_min: int = 5):
    """Exit temps fixe : flat MTM au close de la 1ère barre dont close >= exit_ny_min NY.

    exit_ny_min est calibré une barre avant le force-flat Apex (959) :
    5min -> 955 (barre 15:50->15:55), 15min -> 945 (barre 15:30->15:45).
    Ignore le z-score : teste si le drift entrée->close paie seul. Config C5 du sprint.
    """
    close_min_ny = df.at[j, 'hour_ny'] * 60 + df.at[j, 'min_ny'] + bar_size_min
    if close_min_ny >= exit_ny_min:
        return True, df.at[j, 'close'], 'time_stop'
    return False, 0.0, ''
```

- [ ] **Step 4: Lancer les tests — ils doivent PASSER**

Run: `python -m pytest 01_research/tests/test_exit_logics.py -k time_stop -v`
Expected: PASS — 3 tests passés

- [ ] **Step 5: Commit**

```bash
git add 01_research/src/backtest.py 01_research/tests/test_exit_logics.py
git commit -m "feat: exit_logic_time_stop (config C5 sprint exit)"
```

---

### Task 4: `exit_logic_trailing_std` (config C6)

**Files:**
- Modify: `01_research/src/backtest.py` (ajout après `exit_logic_time_stop`)
- Test: `01_research/tests/test_exit_logics.py`

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à `01_research/tests/test_exit_logics.py` :

```python
def test_trailing_std_long_retrace_hits():
    # bars 1..3 : excursion favorable max high = max(108,112,111) = 112
    # trail_dist = 1.0 * 5 = 5 -> trail_price = 107 ; low[3]=106 <= 107 -> hit
    # fill = 107 - trail_slip_pts(0.25) = 106.75
    df = pd.DataFrame({
        'high':  [100.0, 108.0, 112.0, 111.0],
        'low':   [100.0, 104.0, 109.0, 106.0],
        'close': [100.0, 107.0, 111.0, 107.0],
    })
    touched, price, reason = exit_logic_trailing_std(
        df, i=0, j=3, direction=1, entry_price=100.0, std_i=5.0, mid_i=100.0,
        or_high=float('nan'), or_low=float('nan'), or_range=float('nan'), sl_pts=7.5,
        trail_std_mult=1.0)
    assert touched is True
    assert price == 106.75
    assert reason == 'trail'


def test_trailing_std_long_no_hit():
    # excursion max high = 113 -> trail_price = 108 ; low[3]=110 > 108 -> pas de hit
    df = pd.DataFrame({
        'high':  [100.0, 108.0, 112.0, 113.0],
        'low':   [100.0, 104.0, 109.0, 110.0],
        'close': [100.0, 107.0, 111.0, 112.0],
    })
    touched, price, reason = exit_logic_trailing_std(
        df, i=0, j=3, direction=1, entry_price=100.0, std_i=5.0, mid_i=100.0,
        or_high=float('nan'), or_low=float('nan'), or_range=float('nan'), sl_pts=7.5,
        trail_std_mult=1.0)
    assert touched is False


def test_trailing_std_short_retrace_hits():
    # short : excursion favorable min low = min(92,88,89) = 88
    # trail_dist = 5 -> trail_price = 93 ; high[3]=94 >= 93 -> hit
    # fill = 93 + trail_slip_pts(0.25) = 93.25
    df = pd.DataFrame({
        'high':  [100.0, 96.0, 91.0, 94.0],
        'low':   [100.0, 92.0, 88.0, 89.0],
        'close': [100.0, 93.0, 89.0, 93.0],
    })
    touched, price, reason = exit_logic_trailing_std(
        df, i=0, j=3, direction=-1, entry_price=100.0, std_i=5.0, mid_i=100.0,
        or_high=float('nan'), or_low=float('nan'), or_range=float('nan'), sl_pts=7.5,
        trail_std_mult=1.0)
    assert touched is True
    assert price == 93.25
    assert reason == 'trail'
```

- [ ] **Step 2: Lancer les tests — ils doivent ÉCHOUER**

Run: `python -m pytest 01_research/tests/test_exit_logics.py -k trailing_std -v`
Expected: FAIL — `ImportError: cannot import name 'exit_logic_trailing_std'`

- [ ] **Step 3: Implémenter la fonction**

Ajouter à la fin de `01_research/src/backtest.py` :

```python
def exit_logic_trailing_std(df, i, j, direction, entry_price, std_i, mid_i,
                            or_high, or_low, or_range, sl_pts,
                            trail_std_mult: float = 1.0, trail_slip_pts: float = 0.25):
    """Trailing stop : trail_std_mult * std_i derrière l'excursion favorable.

    Excursion favorable = plus haut high (long) / plus bas low (short) sur les barres
    i+1..j. Vérifié sur wicks. Stop order -> fill avec 1 tick de slippage défavorable
    (trail_slip_pts, défaut 0.25 = 1 tick MNQ). Recalcule l'excursion à chaque appel
    (O(n) par bar, acceptable pour la grille du sprint). Config C6 du sprint.
    """
    trail_dist = trail_std_mult * std_i
    if direction == 1:
        max_fav = df['high'].iloc[i + 1:j + 1].max()
        trail_price = max_fav - trail_dist
        if df.at[j, 'low'] <= trail_price:
            return True, trail_price - trail_slip_pts, 'trail'
    else:
        min_fav = df['low'].iloc[i + 1:j + 1].min()
        trail_price = min_fav + trail_dist
        if df.at[j, 'high'] >= trail_price:
            return True, trail_price + trail_slip_pts, 'trail'
    return False, 0.0, ''
```

- [ ] **Step 4: Lancer les tests — ils doivent PASSER**

Run: `python -m pytest 01_research/tests/test_exit_logics.py -k trailing_std -v`
Expected: PASS — 3 tests passés

- [ ] **Step 5: Commit**

```bash
git add 01_research/src/backtest.py 01_research/tests/test_exit_logics.py
git commit -m "feat: exit_logic_trailing_std (config C6 sprint exit)"
```

---

### Task 5: `exit_logic_hybrid_zscore_time` (config C7)

**Files:**
- Modify: `01_research/src/backtest.py` (ajout après `exit_logic_trailing_std`)
- Test: `01_research/tests/test_exit_logics.py`

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à `01_research/tests/test_exit_logics.py` :

```python
def test_hybrid_zscore_fires_first():
    # short trade (entré sur z>2). j=1 : z=0.8 <= zscore_exit=1.0 -> TP_zscore au close
    df = pd.DataFrame({
        'zscore': [2.5, 0.8], 'hour_ny': [15, 15], 'min_ny': [10, 15], 'close': [100.0, 99.0],
    })
    touched, price, reason = exit_logic_hybrid_zscore_time(
        df, i=0, j=1, direction=-1, entry_price=100.0, std_i=5.0, mid_i=100.0,
        or_high=float('nan'), or_low=float('nan'), or_range=float('nan'), sl_pts=7.5,
        zscore_exit=1.0, exit_ny_min=955, bar_size_min=5)
    assert touched is True
    assert price == 99.0
    assert reason == 'TP_zscore'


def test_hybrid_time_fires_when_zscore_silent():
    # short trade. j=1 : z=1.8 > 1.0 -> pas de TP z. close_min_ny=15*60+50+5=955 -> time_stop
    df = pd.DataFrame({
        'zscore': [2.5, 1.8], 'hour_ny': [15, 15], 'min_ny': [45, 50], 'close': [100.0, 99.5],
    })
    touched, price, reason = exit_logic_hybrid_zscore_time(
        df, i=0, j=1, direction=-1, entry_price=100.0, std_i=5.0, mid_i=100.0,
        or_high=float('nan'), or_low=float('nan'), or_range=float('nan'), sl_pts=7.5,
        zscore_exit=1.0, exit_ny_min=955, bar_size_min=5)
    assert touched is True
    assert price == 99.5
    assert reason == 'time_stop'


def test_hybrid_no_exit_when_both_silent():
    # j=1 : z=1.8 > 1.0 (pas de TP z) ET close_min_ny=15*60+10+5=915 < 955 -> rien
    df = pd.DataFrame({
        'zscore': [2.5, 1.8], 'hour_ny': [15, 15], 'min_ny': [5, 10], 'close': [100.0, 99.5],
    })
    touched, price, reason = exit_logic_hybrid_zscore_time(
        df, i=0, j=1, direction=-1, entry_price=100.0, std_i=5.0, mid_i=100.0,
        or_high=float('nan'), or_low=float('nan'), or_range=float('nan'), sl_pts=7.5,
        zscore_exit=1.0, exit_ny_min=955, bar_size_min=5)
    assert touched is False
```

- [ ] **Step 2: Lancer les tests — ils doivent ÉCHOUER**

Run: `python -m pytest 01_research/tests/test_exit_logics.py -k hybrid -v`
Expected: FAIL — `ImportError: cannot import name 'exit_logic_hybrid_zscore_time'`

- [ ] **Step 3: Implémenter la fonction**

Ajouter à la fin de `01_research/src/backtest.py` :

```python
def exit_logic_hybrid_zscore_time(df, i, j, direction, entry_price, std_i, mid_i,
                                  or_high, or_low, or_range, sl_pts,
                                  zscore_exit: float = 1.0,
                                  exit_ny_min: int = 955, bar_size_min: int = 5):
    """Hybride : TP z-score serré OU exit temps fixe, le premier touché.

    Combine un TP rapide (z revient dans [-zscore_exit, +zscore_exit]) avec un hard
    time stop une barre avant le force-flat Apex. Config C7 du sprint.
    """
    z_j = df.at[j, 'zscore'] if 'zscore' in df.columns else float('nan')
    if pd.notna(z_j):
        tp = (direction == 1 and z_j >= -zscore_exit) or (direction == -1 and z_j <= zscore_exit)
        if tp:
            return True, df.at[j, 'close'], 'TP_zscore'
    close_min_ny = df.at[j, 'hour_ny'] * 60 + df.at[j, 'min_ny'] + bar_size_min
    if close_min_ny >= exit_ny_min:
        return True, df.at[j, 'close'], 'time_stop'
    return False, 0.0, ''
```

- [ ] **Step 4: Lancer toute la suite — tout doit PASSER**

Run: `python -m pytest 01_research/tests/test_exit_logics.py -v`
Expected: PASS — 13 tests passés (1 sentinelle + 3 + 3 + 3 + 3)

- [ ] **Step 5: Commit**

```bash
git add 01_research/src/backtest.py 01_research/tests/test_exit_logics.py
git commit -m "feat: exit_logic_hybrid_zscore_time (config C7 sprint exit)"
```

---

### Task 6: Dépendance jupytext + squelette de l'orchestration

**Files:**
- Modify: `requirements-dev.txt`
- Create: `01_research/notebooks/02_sprint_exit_reengineering.py` (jupytext percent-format, partiel)

- [ ] **Step 1: Ajouter jupytext aux deps dev**

Ajouter une ligne à `requirements-dev.txt` (dans la section jupyter, à la suite des outils notebook existants) :

```
jupytext
```

- [ ] **Step 2: Installer jupytext**

Run: `pip install jupytext`
Expected: `Successfully installed jupytext-...`

- [ ] **Step 3: Créer le squelette de l'orchestration (header + imports + data prep + registre configs)**

Create `01_research/notebooks/02_sprint_exit_reengineering.py` :

```python
# ---
# jupyter:
#   jupytext:
#     formats: py:percent,ipynb
#     text_representation:
#       extension: .py
#       format_name: percent
# ---

# %% [markdown]
# # Sprint Re-engineering Exit — EOD Reversal MNQ
#
# Teste si l'edge EOD Reversal MNQ (entry z>2, 15:00-15:55 NY) se capture avec un exit
# qui se résout avant le force-flat Apex 16:00. Grille de 8 configs d'exit × 2 TF,
# tout mesuré Apex-compliant.
#
# Spec : `docs/superpowers/specs/2026-05-14-sprint-reengineering-eod-reversal-design.md`

# %%
import sys
from functools import partial
from pathlib import Path

import pandas as pd

# 01_research/ sur le path pour `import src...`
sys.path.insert(0, str(Path.cwd().parents[0] if Path.cwd().name == 'notebooks' else Path.cwd()))

from src.config import (TRAIN_START, TRAIN_END, VALID_START, VALID_END,
                        ENTRY_CUTOFF_NY_MIN)
from src.instruments import INSTRUMENTS
from src.data_loader import (load_continuous, resample_ohlcv, add_temporal_columns,
                             filter_session_ny)
from src.features import compute_signal_features
from src.signals import signal_mr_zscore
from src.backtest import (backtest_apex, compute_trade_metrics, simulate_apex_cycle,
                          exit_logic_mr_zscore, exit_logic_fixed_tp_std,
                          exit_logic_time_stop, exit_logic_trailing_std,
                          exit_logic_hybrid_zscore_time)

OUT_DIR = Path('01_research/outputs/sprint_exit')
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Coût round-trip MNQ : commission 1.10 + slippage 1 tick (0.25 pt * 2.00 $ = 0.50)
RT_COST = INSTRUMENTS['MNQ']['commission_rt'] + 0.25 * INSTRUMENTS['MNQ']['point_value']

# Paramètres par timeframe (identiques à mini-val #4)
TF_PARAMS = {
    '5min':  dict(rule='5min',  bar_size_min=5,  timeout_bars=12, exit_ny_min=955),
    '15min': dict(rule='15min', bar_size_min=15, timeout_bars=4,  exit_ny_min=945),
}

# Chiffres de référence mini-val #4 (Train, Apex-compliant) pour le contrôle C0
MINIVAL4 = {
    '5min':  dict(trades=632, pf=0.8009),
    '15min': dict(trades=180, pf=0.7664),
}

# %%
def prepare_tf(rule: str) -> pd.DataFrame:
    """Charge MNQ M1, resample au TF, ajoute colonnes temporelles, filtre session NY,
    calcule mid/std/zscore. Pipeline identique à mini-val #4."""
    df_m1 = load_continuous(INSTRUMENTS['MNQ']['path'], 'MNQ')
    df_tf = resample_ohlcv(df_m1, rule)
    df_tf = add_temporal_columns(df_tf)
    df_sess = filter_session_ny(df_tf)
    df_feat = compute_signal_features(df_sess, lookback=20)
    return df_feat


def build_exit_configs(bar_size_min: int, exit_ny_min: int) -> dict:
    """Retourne {config_name: exit_logic callable} pour un TF donné."""
    return {
        'C0_zscore_0.5':    partial(exit_logic_mr_zscore, zscore_exit=0.5),
        'C1_zscore_1.0':    partial(exit_logic_mr_zscore, zscore_exit=1.0),
        'C2_zscore_1.5':    partial(exit_logic_mr_zscore, zscore_exit=1.5),
        'C3_fixed_0.75std': partial(exit_logic_fixed_tp_std, tp_std_mult=0.75),
        'C4_fixed_0.40std': partial(exit_logic_fixed_tp_std, tp_std_mult=0.40),
        'C5_time_stop':     partial(exit_logic_time_stop, exit_ny_min=exit_ny_min,
                                    bar_size_min=bar_size_min),
        'C6_trail_1.0std':  partial(exit_logic_trailing_std, trail_std_mult=1.0),
        'C7_hybrid':        partial(exit_logic_hybrid_zscore_time, zscore_exit=1.0,
                                    exit_ny_min=exit_ny_min, bar_size_min=bar_size_min),
    }


def run_config(df_split: pd.DataFrame, exit_logic, bar_size_min: int, timeout_bars: int):
    """Génère les signaux MR 15h NY Apex-compliant, backtest, retourne (métriques, trades)."""
    sigs = signal_mr_zscore(df_split, entry_threshold=2.0, allowed_hours={15},
                            entry_cutoff_ny_min=ENTRY_CUTOFF_NY_MIN,
                            bar_size_min=bar_size_min)
    trades = backtest_apex(sigs, exit_logic=exit_logic,
                           instrument_specs=INSTRUMENTS['MNQ'],
                           bar_size_min=bar_size_min, timeout_bars=timeout_bars,
                           apex_constraints=True)
    return compute_trade_metrics(trades), trades
```

- [ ] **Step 4: Vérifier que le squelette s'exécute sans erreur**

Run: `python 01_research/notebooks/02_sprint_exit_reengineering.py`
Expected: aucune sortie, exit code 0 (les fonctions sont définies mais pas encore appelées)

- [ ] **Step 5: Commit**

```bash
git add requirements-dev.txt 01_research/notebooks/02_sprint_exit_reengineering.py
git commit -m "feat: squelette orchestration sprint exit (data prep + registre configs)"
```

---

### Task 7: Contrôle harness C0 — doit reproduire mini-val #4

**Files:**
- Modify: `01_research/notebooks/02_sprint_exit_reengineering.py` (ajout cellule)

- [ ] **Step 1: Ajouter la cellule de contrôle C0 avec assertions**

Ajouter à la fin de `01_research/notebooks/02_sprint_exit_reengineering.py` :

```python
# %% [markdown]
# ## Contrôle C0 — fidélité du harness
#
# La config C0 (exit z-score ±0.5) doit reproduire les chiffres Apex-compliant de
# mini-validation #4. Si l'assertion échoue, le harness `src/` a divergé du pipeline
# inline de mini-val #4 — STOP, investiguer avant de faire confiance à C1-C7.

# %%
# Cache des DataFrames préparés par TF (réutilisés par la grille complète)
_PREPARED = {tf: prepare_tf(TF_PARAMS[tf]['rule']) for tf in TF_PARAMS}


def split_train(df):
    return df.loc[(df.index >= TRAIN_START) & (df.index < TRAIN_END)].copy()


def split_valid(df):
    return df.loc[(df.index >= VALID_START) & (df.index < VALID_END)].copy()


for tf, p in TF_PARAMS.items():
    df_train = split_train(_PREPARED[tf])
    configs = build_exit_configs(p['bar_size_min'], p['exit_ny_min'])
    m, _ = run_config(df_train, configs['C0_zscore_0.5'], p['bar_size_min'], p['timeout_bars'])
    ref = MINIVAL4[tf]
    assert m['trades'] == ref['trades'], (
        f"C0 {tf} : {m['trades']} trades vs mini-val #4 {ref['trades']} — HARNESS DIVERGÉ")
    assert abs(m['pf'] - ref['pf']) / ref['pf'] < 0.02, (
        f"C0 {tf} : PF {m['pf']:.4f} vs mini-val #4 {ref['pf']} — HARNESS DIVERGÉ")
    print(f"C0 {tf} OK : {m['trades']} trades, PF {m['pf']:.4f} (réf {ref['pf']})")
```

- [ ] **Step 2: Exécuter et vérifier que C0 passe**

Run: `python 01_research/notebooks/02_sprint_exit_reengineering.py`
Expected: deux lignes affichées —
```
C0 5min OK : 632 trades, PF 0.80... (réf 0.8009)
C0 15min OK : 180 trades, PF 0.76... (réf 0.7664)
```
Si une assertion échoue : NE PAS continuer le plan. Le harness `src/` ne reproduit pas
mini-val #4 — diagnostiquer l'écart (data loading, features, ou backtester) avant Task 8.

- [ ] **Step 3: Commit**

```bash
git add 01_research/notebooks/02_sprint_exit_reengineering.py
git commit -m "feat: contrôle harness C0 (reproduit mini-val #4)"
```

---

### Task 8: Grille complète + ranking CSV

**Files:**
- Modify: `01_research/notebooks/02_sprint_exit_reengineering.py` (ajout cellule)

- [ ] **Step 1: Ajouter la cellule de run de la grille complète**

Ajouter à la fin de `01_research/notebooks/02_sprint_exit_reengineering.py` :

```python
# %% [markdown]
# ## Grille complète — 8 configs × 2 TF (16 trials)
#
# Chaque config backtestée sur Train. Gate de promotion : PF > 1.5 ET Sharpe > 1.0 ET
# avg_trade > coût round-trip, sur Train Apex-compliant. Les configs qui passent le gate
# Train sont re-backtestées sur Valid (walk-forward).

# %%
N_TRIALS = 0
rows = []
trades_by_key = {}

for tf, p in TF_PARAMS.items():
    df_train = split_train(_PREPARED[tf])
    df_valid = split_valid(_PREPARED[tf])
    configs = build_exit_configs(p['bar_size_min'], p['exit_ny_min'])
    for name, exit_logic in configs.items():
        N_TRIALS += 1
        m_tr, tr_tr = run_config(df_train, exit_logic, p['bar_size_min'], p['timeout_bars'])
        gate_train = (m_tr['pf'] > 1.5 and m_tr['sharpe'] > 1.0
                      and m_tr['avg_trade'] > RT_COST)
        row = {
            'config': name, 'tf': tf,
            'train_trades': m_tr['trades'], 'train_pf': m_tr['pf'],
            'train_sharpe': m_tr['sharpe'], 'train_max_dd': m_tr['max_dd'],
            'train_wr': m_tr['wr'], 'train_pnl': m_tr['pnl'],
            'train_avg_trade': m_tr['avg_trade'], 'gate_train': gate_train,
        }
        trades_by_key[(name, tf, 'train')] = tr_tr
        if gate_train:
            m_va, tr_va = run_config(df_valid, exit_logic, p['bar_size_min'], p['timeout_bars'])
            row.update({
                'valid_trades': m_va['trades'], 'valid_pf': m_va['pf'],
                'valid_sharpe': m_va['sharpe'], 'valid_max_dd': m_va['max_dd'],
                'valid_wr': m_va['wr'], 'valid_pnl': m_va['pnl'],
                'valid_avg_trade': m_va['avg_trade'],
                'promoted': (m_va['pf'] >= 1.3 and m_va['sharpe'] > 0),
            })
            trades_by_key[(name, tf, 'valid')] = tr_va
        else:
            row.update({
                'valid_trades': None, 'valid_pf': None, 'valid_sharpe': None,
                'valid_max_dd': None, 'valid_wr': None, 'valid_pnl': None,
                'valid_avg_trade': None, 'promoted': False,
            })
        rows.append(row)
        print(f"{name:18} {tf:5} | Train PF {m_tr['pf']:.2f} Sharpe {m_tr['sharpe']:+.2f} "
              f"avg ${m_tr['avg_trade']:+.2f} | gate={gate_train} promoted={row['promoted']}")

ranking = pd.DataFrame(rows).sort_values(
    ['promoted', 'train_pf'], ascending=[False, False]).reset_index(drop=True)
ranking.to_csv(OUT_DIR / 'ranking.csv', index=False)
print(f"\nn_trials = {N_TRIALS} | ranking.csv écrit ({len(ranking)} lignes)")
```

- [ ] **Step 2: Exécuter la grille complète**

Run: `python 01_research/notebooks/02_sprint_exit_reengineering.py`
Expected: 16 lignes affichées (une par config × TF), puis `n_trials = 16 | ranking.csv écrit (16 lignes)`. Le fichier `01_research/outputs/sprint_exit/ranking.csv` existe avec 16 lignes. Note : les valeurs de PF/Sharpe de C1-C7 sont le résultat du sprint — pas de valeur attendue prédéfinie. Seul C0 est connu (PF ≈ 0.80 / 0.77).

- [ ] **Step 3: Commit**

```bash
git add 01_research/notebooks/02_sprint_exit_reengineering.py 01_research/outputs/sprint_exit/ranking.csv
git commit -m "feat: grille complète sprint exit + ranking.csv (16 trials)"
```

---

### Task 9: Simulation cycle Apex (contexte) + rapport

**Files:**
- Modify: `01_research/notebooks/02_sprint_exit_reengineering.py` (ajout cellule)

- [ ] **Step 1: Ajouter la cellule cycle Apex + génération du rapport**

Ajouter à la fin de `01_research/notebooks/02_sprint_exit_reengineering.py` :

```python
# %% [markdown]
# ## Cycle Apex (contexte) + rapport
#
# `simulate_apex_cycle` sur les trades Train+Valid des configs promues — affiché pour
# contexte, n'entre PAS dans le gate (pass rate sizing-dépendant). Puis génération du
# rapport markdown.

# %%
promoted = ranking[ranking['promoted'] == True]  # noqa: E712

cycle_summaries = {}
for _, r in promoted.iterrows():
    name, tf = r['config'], r['tf']
    p = TF_PARAMS[tf]
    df_all = _PREPARED[tf]
    df_tv = df_all.loc[(df_all.index >= TRAIN_START) & (df_all.index < VALID_END)].copy()
    configs = build_exit_configs(p['bar_size_min'], p['exit_ny_min'])
    _, trades_tv = run_config(df_tv, configs[name], p['bar_size_min'], p['timeout_bars'])
    cycle = simulate_apex_cycle(trades_tv)
    if len(cycle) > 0:
        cycle_summaries[(name, tf)] = {
            'months': len(cycle),
            'pass_rate': (cycle['status'] == 'PASSED').mean() * 100,
            'bust_dd_rate': (cycle['status'] == 'BUSTED_DD').mean() * 100,
            'avg_pnl_month': cycle['final_pnl'].mean(),
        }

# %%
lines = []
lines.append('# Sprint Re-engineering Exit — Rapport\n')
lines.append(f'**Date** : 2026-05-14  ')
lines.append(f'**n_trials** : {N_TRIALS} (8 configs × 2 TF) — budget overfitting pour le DSR Étape 2\n')
lines.append('## Verdict\n')
if len(promoted) == 0:
    lines.append('🔴 **Aucune config ne passe le gate.** Le gate exige PF > 1.5 ∧ Sharpe > 1.0 '
                 '∧ avg_trade > coût RT sur Train Apex-compliant, ET PF ≥ 1.3 sur Valid.\n')
    lines.append('L\'edge EOD Reversal n\'est pas capturable avant le force-flat 16:00 par le '
                 'seul levier exit. **Recommandation : acter l\'edge EOD Apex-mort, Étape 2 '
                 'pivote sur une nouvelle hypothèse.**\n')
else:
    lines.append(f'🟢 **{len(promoted)} config(s) passe(nt) le gate :**\n')
    for _, r in promoted.iterrows():
        lines.append(f"- `{r['config']}` ({r['tf']}) — Train PF {r['train_pf']:.2f} / "
                     f"Sharpe {r['train_sharpe']:.2f} ; Valid PF {r['valid_pf']:.2f} / "
                     f"Sharpe {r['valid_sharpe']:.2f}")
    lines.append('\n**Recommandation : promouvoir la config la plus robuste (cohérence '
                 'Train/Valid) vers une vraie Étape 2** — backtester NT8-compatible, '
                 'DSR/CPCV/Monte Carlo, décomposition LONG/SHORT, stress test régime.\n')

lines.append('## Classement complet\n')
cols = ['config', 'tf', 'train_trades', 'train_pf', 'train_sharpe', 'train_avg_trade',
        'gate_train', 'valid_pf', 'valid_sharpe', 'promoted']
lines.append(ranking[cols].to_markdown(index=False, floatfmt='.2f'))
lines.append('')

if cycle_summaries:
    lines.append('## Cycle Apex (contexte — hors gate)\n')
    for (name, tf), s in cycle_summaries.items():
        lines.append(f"- `{name}` ({tf}) : {s['months']} mois — pass {s['pass_rate']:.1f}% / "
                     f"bust DD {s['bust_dd_rate']:.1f}% / PnL moyen ${s['avg_pnl_month']:.0f}/mois "
                     f"(1 contrat)")
    lines.append('')

lines.append('## Limites connues\n')
lines.append('- `backtest_apex` non audité — le contrôle C0 ne couvre qu\'un bug non-commun '
             'à mini-val #4 et au sprint.')
lines.append('- Trailing stop (C6) : fill modélisé avec 1 tick de slippage ; pas de modélisation '
             'de gap intra-tick. À durcir en Étape 2.')
lines.append('- Sharpe = per-trade × √252 (convention repo, cohérente avec mini-vals #1-4).')
lines.append('- Holdout 2025-05→2026-05 INTOUCHÉ.')

report = '\n'.join(lines)
(OUT_DIR / 'sprint_exit_report.md').write_text(report, encoding='utf-8')
print(report)
print(f"\nRapport écrit : {OUT_DIR / 'sprint_exit_report.md'}")
```

- [ ] **Step 2: Exécuter et vérifier le rapport**

Run: `python 01_research/notebooks/02_sprint_exit_reengineering.py`
Expected: la grille tourne, le rapport s'affiche puis `Rapport écrit : 01_research/outputs/sprint_exit/sprint_exit_report.md`. Le fichier existe et contient un verdict (🟢 ou 🔴), le classement des 16 trials, et les limites connues.

- [ ] **Step 3: Commit**

```bash
git add 01_research/notebooks/02_sprint_exit_reengineering.py 01_research/outputs/sprint_exit/
git commit -m "feat: cycle Apex contexte + rapport sprint exit"
```

---

### Task 10: Conversion en notebook + run log + finalisation

**Files:**
- Create: `01_research/notebooks/02_sprint_exit_reengineering.ipynb`
- Create: `01_research/outputs/sprint_exit/run_log.txt`

- [ ] **Step 1: Générer le run log**

Run: `python 01_research/notebooks/02_sprint_exit_reengineering.py > 01_research/outputs/sprint_exit/run_log.txt 2>&1`
Expected: exit code 0, fichier `run_log.txt` créé avec toute la sortie console (C0, grille, rapport).

- [ ] **Step 2: Convertir le `.py` percent en notebook**

Run: `jupytext --to notebook 01_research/notebooks/02_sprint_exit_reengineering.py`
Expected: `[jupytext] Writing 01_research/notebooks/02_sprint_exit_reengineering.ipynb`

- [ ] **Step 3: Exécuter le notebook pour peupler les sorties de cellules**

Run: `jupyter nbconvert --to notebook --execute --inplace 01_research/notebooks/02_sprint_exit_reengineering.ipynb`
Expected: `[NbConvertApp] Writing ... to 01_research/notebooks/02_sprint_exit_reengineering.ipynb` — aucune erreur (les assertions C0 passent).

- [ ] **Step 4: Vérifier la suite de tests complète**

Run: `python -m pytest 01_research/tests/ -v`
Expected: PASS — 13 tests passés.

- [ ] **Step 5: Commit final**

```bash
git add 01_research/notebooks/02_sprint_exit_reengineering.ipynb 01_research/outputs/sprint_exit/run_log.txt
git commit -m "feat: notebook sprint exit généré + run log"
```

---

## Self-Review (effectuée à l'écriture du plan)

**1. Couverture spec :**
- §Architecture (exit logics dans `src/`, notebook orchestration) → Tasks 2-5, 6-9 ✓
- §Grille 8 configs C0-C7 → registre `build_exit_configs` Task 6, exécutée Task 8 ✓
- §Protocole : C0 d'abord → Task 7 ; tout Apex-compliant (`apex_constraints=True`) → `run_config` Task 6 ; Train→Valid → Task 8 ; cycle Apex contexte → Task 9 ✓
- §Gate de promotion (PF>1.5 ∧ Sharpe>1.0 ∧ avg_trade>coût Train ; PF≥1.3 Valid) → Task 8 `gate_train` / `promoted` ✓
- §Outputs (ranking.csv, sprint_exit_report.md, run_log.txt) → Tasks 8, 9, 10 ✓
- §Anti-overfit (n_trials loggé, Holdout intouché) → `N_TRIALS` Task 8, rapport Task 9 ; aucun split holdout dans le code ✓

**2. Placeholders :** aucun TBD/TODO ; tout le code est complet et exécutable.

**3. Cohérence des types :** signature `exit_logic(df, i, j, direction, entry_price, std_i, mid_i, or_high, or_low, or_range, sl_pts, **kwargs)` identique dans les 4 fonctions et compatible avec l'appel de `backtest_apex` (11 args positionnels). `build_exit_configs` utilise `partial` pour fixer les kwargs spécifiques. Noms de fonctions cohérents entre Tasks 2-5 (définition), Task 1 (import test), Task 6 (import notebook).

**4. Risque résiduel :** si C0 échoue à Task 7, le plan s'arrête là — c'est le comportement voulu (gate de fidélité harness). L'engineer doit alors diagnostiquer l'écart `src/` vs mini-val #4 avant de reprendre.
