# Opening Drive Failure Fade — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Encoder l'hypothèse de recherche « Opening Drive Failure Fade » en objet `Hypothesis` enfichable, prêt à passer dans `run_gauntlet()`.

**Architecture:** Trois fonctions pures neuves dans `01_research/src/` (une feature, un signal, un exit_logic), suivant les patterns existants du repo. Un objet `Hypothesis` dans `02_validation/gauntlet/hypotheses/` qui les wrappe. Un script runner dans `02_validation/notebooks/`. Le gauntlet (Plans 1-3, déjà mergé) fait tout le reste — backtest PA-réaliste, batterie statistique, verdict.

**Tech Stack:** Python 3.10+, pandas, numpy, pytest. Réutilise `01_research/src/` (data_loader, features, backtest) et `02_validation/gauntlet/`.

**Spec de référence:** `docs/superpowers/specs/2026-05-15-opening-drive-failure-fade-design.md`

---

## Note pédagogique (préférence BB — apprendre au fil du projet)

BB veut **comprendre** ce qui est codé. Chaque task inclut un **"Pourquoi"** : le concept quant ou le choix de design. L'implémenteur DOIT garder ces explications dans les rapports.

## Contexte technique pour l'implémenteur

- `01_research/conftest.py` met `01_research/` sur `sys.path` → les tests de `01_research/tests/` font `from src.X import ...`.
- `02_validation/gauntlet/conftest.py` met `02_validation/` ET `01_research/` sur `sys.path` → `from gauntlet.X import ...` et `from src.X import ...` marchent depuis `02_validation/gauntlet/tests/`.
- **Le gauntlet `backtest_pa` exige les colonnes `std` et `mid`** dans le df (pour le calcul du SL et passé à `exit_logic`). C'est pourquoi `prepare_features` chaîne `compute_signal_features` (qui produit `std`/`mid`) AVANT `compute_features_opening_drive`.
- Signature `exit_logic` standard du repo : `(df, i, j, direction, entry_price, std_i, mid_i, or_high, or_low, or_range, sl_pts) -> (touched: bool, price: float, reason: str)`. Le gauntlet passe `or_high/or_low/or_range` à `nan`.
- Pas de modification de `pyproject.toml` : `01_research/tests` et `02_validation/gauntlet/tests` sont déjà dans `testpaths`.
- Lancer pytest : `python -m pytest <chemin> -v`. Sur Windows, lancer git sans préfixe `cd`.

---

## File Structure

| Fichier | Responsabilité | Task |
|---|---|---|
| `01_research/src/features.py` | **MODIFIÉ** — ajoute `compute_features_opening_drive` | 1 |
| `01_research/tests/test_features_opening_drive.py` | tests de la feature | 1 |
| `01_research/src/signals.py` | **MODIFIÉ** — ajoute `signal_opening_drive_failure` | 2 |
| `01_research/tests/test_signal_opening_drive.py` | tests du signal | 2 |
| `01_research/src/backtest.py` | **MODIFIÉ** — ajoute `exit_logic_return_to_open` | 3 |
| `01_research/tests/test_exit_return_to_open.py` | tests de l'exit | 3 |
| `02_validation/gauntlet/hypotheses/__init__.py` | marqueur de package (vide) | 4 |
| `02_validation/gauntlet/hypotheses/hyp_opening_drive_failure.py` | l'objet `Hypothesis` | 4 |
| `02_validation/gauntlet/tests/test_hyp_opening_drive_failure.py` | tests de l'hypothèse | 4 |
| `02_validation/notebooks/04_run_opening_drive_failure.py` | script runner (BB le lance) | 5 |

---

### Task 1 : `compute_features_opening_drive` — les features littérature-grounded

**Files:**
- Modify: `01_research/src/features.py` (append une fonction)
- Create: `01_research/tests/test_features_opening_drive.py`

**Pourquoi :** la feature est le cœur littérature-grounded de l'hypothèse. Elle calcule, sur le df de session RTH complet : `open_ref` (le « corps », l'open 9:30 du jour), `prev_close` (close RTH de la veille), `gap_z` (le gap overnight normalisé — **le prédicteur central** de la littérature overnight-intraday reversal), `spike_magnitude` (déplacement du prix vs l'open), `rejection_body` (le ratio de mèche — l'exhaustion, validé par Osler/Heston), `vol_regime` (régime de volatilité — l'effet est ~2× plus fort en haute vol), `relvol_open` (volume relatif). Calculée AVANT le découpage en splits car les features sont backward-looking — pas de leakage, et le gap/vol nécessitent du contexte inter-journées.

- [ ] **Step 1: Écrire les tests qui échouent**

Create `01_research/tests/test_features_opening_drive.py` :

```python
"""Tests de compute_features_opening_drive — données synthétiques déterministes."""
import numpy as np
import pandas as pd

from src.features import compute_features_opening_drive


def _session_df():
    """3 jours de session RTH synthétique, 3 barres 1-min/jour (9:30, 9:31, 9:32).

    Jour 1 (2022-01-03) : open 9:30 = 100 ; closes [100, 101, 99] ; last close 99.
    Jour 2 (2022-01-04) : open 9:30 = 102 ; closes [102, 103, 101] ; last close 101.
    Jour 3 (2022-01-05) : open 9:30 = 98  ; closes [98,  97,  99].
    """
    rows = []
    spec = {
        "2022-01-03": (100.0, [100.0, 101.0, 99.0]),
        "2022-01-04": (102.0, [102.0, 103.0, 101.0]),
        "2022-01-05": (98.0, [98.0, 97.0, 99.0]),
    }
    for day, (op, closes) in spec.items():
        for b, c in enumerate(closes):
            ts = pd.Timestamp(f"{day} 09:3{b}", tz="America/New_York").tz_convert("UTC")
            o = op if b == 0 else closes[b - 1]
            rows.append({
                "bar": ts, "open": o, "high": max(o, c) + 1.0, "low": min(o, c) - 1.0,
                "close": c, "volume": 1000.0 + 100.0 * b,
            })
    df = pd.DataFrame(rows).set_index("bar")
    df["date"] = df.index.tz_convert("America/New_York").date
    df["hour_ny"] = 9
    df["min_ny"] = [0, 1, 2] * 3
    df["min_ny"] = [30, 31, 32] * 3
    return df


def test_open_ref_constant_par_jour():
    out = compute_features_opening_drive(_session_df())
    d1 = out[out["date"] == pd.Timestamp("2022-01-03").date()]
    assert (d1["open_ref"] == 100.0).all()
    d3 = out[out["date"] == pd.Timestamp("2022-01-05").date()]
    assert (d3["open_ref"] == 98.0).all()


def test_prev_close_est_la_cloture_de_la_veille():
    out = compute_features_opening_drive(_session_df())
    d1 = out[out["date"] == pd.Timestamp("2022-01-03").date()]
    assert d1["prev_close"].isna().all()                     # pas de veille
    d2 = out[out["date"] == pd.Timestamp("2022-01-04").date()]
    assert (d2["prev_close"] == 99.0).all()                  # last close jour 1
    d3 = out[out["date"] == pd.Timestamp("2022-01-05").date()]
    assert (d3["prev_close"] == 101.0).all()                 # last close jour 2


def test_spike_magnitude_est_close_moins_open_ref():
    out = compute_features_opening_drive(_session_df())
    d3 = out[out["date"] == pd.Timestamp("2022-01-05").date()]
    # closes jour 3 = [98, 97, 99], open_ref = 98 -> spike = [0, -1, 1]
    assert list(d3["spike_magnitude"]) == [0.0, -1.0, 1.0]


def test_rejection_body_formule():
    # bougie : open 98, close 97 -> high = max(98,97)+1 = 99, low = min(98,97)-1 = 96
    # rejection_body = (close - low) / (high - low) = (97 - 96) / (99 - 96) = 1/3
    out = compute_features_opening_drive(_session_df())
    d3 = out[out["date"] == pd.Timestamp("2022-01-05").date()]
    assert abs(d3["rejection_body"].iloc[1] - (1.0 / 3.0)) < 1e-9


def test_gap_z_signe_correct():
    # jour 3 : open 98, prev_close 101 -> gap overnight = -3 (baissier) -> gap_z < 0
    out = compute_features_opening_drive(_session_df(), gap_std_window=2)
    d3 = out[out["date"] == pd.Timestamp("2022-01-05").date()]
    assert d3["gap_z"].notna().all()
    assert (d3["gap_z"] < 0).all()


def test_vol_regime_est_booleen_sans_nan():
    out = compute_features_opening_drive(_session_df(), vol_regime_window=2)
    assert out["vol_regime"].dtype == bool
    assert not out["vol_regime"].isna().any()


def test_colonnes_produites():
    out = compute_features_opening_drive(_session_df())
    for col in ["open_ref", "prev_close", "gap_z", "spike_magnitude",
                "rejection_body", "vol_regime", "relvol_open"]:
        assert col in out.columns
```

- [ ] **Step 2: Lancer les tests — ils doivent ÉCHOUER**

Run: `python -m pytest 01_research/tests/test_features_opening_drive.py -v`
Expected: FAIL — `ImportError: cannot import name 'compute_features_opening_drive' from 'src.features'`

- [ ] **Step 3: Implémenter `compute_features_opening_drive`**

Append à la fin de `01_research/src/features.py` :

```python
def compute_features_opening_drive(df: pd.DataFrame,
                                   gap_std_window: int = 20,
                                   vol_regime_window: int = 60,
                                   relvol_window: int = 20) -> pd.DataFrame:
    """Features de l'hypothèse Opening Drive Failure Fade (cf. spec 2026-05-15).

    Calculée sur le df de session RTH COMPLET (toutes les journées) — les features
    gap/vol nécessitent du contexte inter-journées. Backward-looking : pas de leakage.

    Nécessite les colonnes : open, high, low, close, volume, date, hour_ny, min_ny.

    Args:
        gap_std_window: fenêtre rolling (jours) de l'écart-type des gaps overnight.
        vol_regime_window: fenêtre rolling (jours) de la médiane de vol réalisée.
        relvol_window: fenêtre rolling (jours) de la moyenne de volume par tranche horaire.

    Returns: copy de df + colonnes
        ['open_ref', 'prev_close', 'gap_z', 'spike_magnitude', 'rejection_body',
         'vol_regime', 'relvol_open'].
    """
    out = df.copy()

    # open_ref : open de la 1re bougie de chaque journée (le "corps", constant/jour).
    out['open_ref'] = out.groupby('date')['open'].transform('first')

    # prev_close : close de la dernière bougie de la session RTH précédente.
    daily_last_close = out.groupby('date')['close'].last()
    prev_close_by_date = daily_last_close.shift(1)
    out['prev_close'] = out['date'].map(prev_close_by_date)

    # gap_z : gap overnight (open du jour - close veille) normalisé par l'écart-type
    # rolling des gaps. Le prédicteur central (littérature overnight-intraday reversal).
    daily_open = out.groupby('date')['open'].first()
    daily_gap = daily_open - prev_close_by_date
    gap_std = daily_gap.rolling(gap_std_window).std()
    gap_z_by_date = daily_gap / gap_std.replace(0.0, np.nan)
    out['gap_z'] = out['date'].map(gap_z_by_date)

    # spike_magnitude : déplacement signé du close vs open_ref (en points).
    out['spike_magnitude'] = out['close'] - out['open_ref']

    # rejection_body : position de la clôture dans le range de la bougie.
    # ~1 = clôture en haut du range (rejet d'un down-spike) ; ~0 = rejet d'un up-spike.
    rng = out['high'] - out['low']
    out['rejection_body'] = np.where(rng > 0, (out['close'] - out['low']) / rng, 0.5)

    # vol_regime : vol réalisée intraday du jour > médiane rolling. L'effet reversal
    # est ~2x plus fort en régime de volatilité élevée.
    daily_rv = out.groupby('date')['close'].apply(lambda s: s.pct_change().std())
    rv_median = daily_rv.rolling(vol_regime_window).median()
    vol_regime_by_date = (daily_rv > rv_median)
    out['vol_regime'] = out['date'].map(vol_regime_by_date).fillna(False).astype(bool)

    # relvol_open : volume / moyenne rolling du volume à la même tranche horaire.
    tod = out['hour_ny'] * 60 + out['min_ny']
    vol_mean_tod = out.groupby(tod)['volume'].transform(
        lambda s: s.rolling(relvol_window).mean()
    )
    out['relvol_open'] = out['volume'] / vol_mean_tod.replace(0.0, np.nan)

    return out
```

- [ ] **Step 4: Lancer les tests — ils doivent PASSER**

Run: `python -m pytest 01_research/tests/test_features_opening_drive.py -v`
Expected: PASS — 7 tests passés.

- [ ] **Step 5: Commit**

```bash
git add 01_research/src/features.py 01_research/tests/test_features_opening_drive.py
git commit -m "feat(research): compute_features_opening_drive - features littérature-grounded"
```

---

### Task 2 : `signal_opening_drive_failure` — le signal conditionné

**Files:**
- Modify: `01_research/src/signals.py` (append une fonction)
- Create: `01_research/tests/test_signal_opening_drive.py`

**Pourquoi :** le signal applique les **5 conditions** du spec : gap overnight significatif (`gap_z`), spike notable (`spike_magnitude`), rejet de bougie (`rejection_body`), régime haute volatilité (`vol_regime`), confirmation volume (`relvol_open`). Down-spike → LONG, up-spike → SHORT, symétrique. C'est le « ciblage » qui distingue cette hypothèse du MR vanille mort : on ne fade pas n'importe quel extrême, on fade le faux move de l'open *quand toute la poche conditionnée s'aligne*. Les comparaisons avec des NaN (warmup des features) donnent `False` → signal reste 0, pas de trade sur données incomplètes.

- [ ] **Step 1: Écrire les tests qui échouent**

Create `01_research/tests/test_signal_opening_drive.py` :

```python
"""Tests de signal_opening_drive_failure — données synthétiques avec features injectées."""
import numpy as np
import pandas as pd

from src.signals import signal_opening_drive_failure


def _df_with_features(rows):
    """rows : liste de dicts avec gap_z, spike_magnitude, rejection_body, vol_regime,
    relvol_open, hour_ny, min_ny. Construit un df indexé temps."""
    idx = pd.date_range("2022-01-03 14:30", periods=len(rows), freq="1min", tz="UTC")
    return pd.DataFrame(rows, index=idx)


def _long_row():
    """Une ligne où les 5 conditions LONG sont remplies (down-spike à fader)."""
    return dict(gap_z=-1.0, spike_magnitude=-20.0, rejection_body=0.8,
                vol_regime=True, relvol_open=1.5, hour_ny=9, min_ny=45)


def _short_row():
    """Une ligne où les 5 conditions SHORT sont remplies (up-spike à fader)."""
    return dict(gap_z=1.0, spike_magnitude=20.0, rejection_body=0.2,
                vol_regime=True, relvol_open=1.5, hour_ny=9, min_ny=45)


def test_long_signal_quand_les_5_conditions_alignees():
    out = signal_opening_drive_failure(_df_with_features([_long_row()]),
                                       window_end_min=630, gap_threshold=0.5,
                                       spike_min=15.0, rejet_seuil=0.66, relvol_seuil=1.0)
    assert out["signal"].iloc[0] == 1


def test_short_signal_symetrique():
    out = signal_opening_drive_failure(_df_with_features([_short_row()]),
                                       window_end_min=630, gap_threshold=0.5,
                                       spike_min=15.0, rejet_seuil=0.66, relvol_seuil=1.0)
    assert out["signal"].iloc[0] == -1


def test_pas_de_signal_si_gap_trop_faible():
    row = _long_row()
    row["gap_z"] = -0.2                              # < gap_threshold 0.5
    out = signal_opening_drive_failure(_df_with_features([row]), window_end_min=630,
                                       gap_threshold=0.5, spike_min=15.0,
                                       rejet_seuil=0.66, relvol_seuil=1.0)
    assert out["signal"].iloc[0] == 0


def test_pas_de_signal_hors_fenetre():
    row = _long_row()
    row["hour_ny"], row["min_ny"] = 11, 0            # 11:00, hors fenêtre 9:30-10:30
    out = signal_opening_drive_failure(_df_with_features([row]), window_end_min=630,
                                       gap_threshold=0.5, spike_min=15.0,
                                       rejet_seuil=0.66, relvol_seuil=1.0)
    assert out["signal"].iloc[0] == 0


def test_pas_de_signal_si_vol_regime_faux():
    row = _long_row()
    row["vol_regime"] = False
    out = signal_opening_drive_failure(_df_with_features([row]), window_end_min=630,
                                       gap_threshold=0.5, spike_min=15.0,
                                       rejet_seuil=0.66, relvol_seuil=1.0)
    assert out["signal"].iloc[0] == 0


def test_nan_feature_ne_declenche_pas():
    row = _long_row()
    row["gap_z"] = np.nan                            # warmup -> pas de trade
    out = signal_opening_drive_failure(_df_with_features([row]), window_end_min=630,
                                       gap_threshold=0.5, spike_min=15.0,
                                       rejet_seuil=0.66, relvol_seuil=1.0)
    assert out["signal"].iloc[0] == 0


def test_window_end_min_resserre_la_fenetre():
    # 10:15 NY : dans la fenêtre 9:30-10:30 (630) mais hors 9:30-10:00 (600)
    row = _long_row()
    row["hour_ny"], row["min_ny"] = 10, 15
    out_large = signal_opening_drive_failure(_df_with_features([row]), window_end_min=630,
                                             gap_threshold=0.5, spike_min=15.0,
                                             rejet_seuil=0.66, relvol_seuil=1.0)
    out_tight = signal_opening_drive_failure(_df_with_features([row]), window_end_min=600,
                                             gap_threshold=0.5, spike_min=15.0,
                                             rejet_seuil=0.66, relvol_seuil=1.0)
    assert out_large["signal"].iloc[0] == 1
    assert out_tight["signal"].iloc[0] == 0
```

- [ ] **Step 2: Lancer les tests — ils doivent ÉCHOUER**

Run: `python -m pytest 01_research/tests/test_signal_opening_drive.py -v`
Expected: FAIL — `ImportError: cannot import name 'signal_opening_drive_failure' from 'src.signals'`

- [ ] **Step 3: Implémenter `signal_opening_drive_failure`**

Append à la fin de `01_research/src/signals.py` :

```python
def signal_opening_drive_failure(df: pd.DataFrame,
                                 window_end_min: int = 630,
                                 gap_threshold: float = 0.5,
                                 spike_min: float = 15.0,
                                 rejet_seuil: float = 0.66,
                                 relvol_seuil: float = 1.0) -> pd.DataFrame:
    """Signal Opening Drive Failure Fade : fade le faux spike d'open (cf. spec 2026-05-15).

    Down-spike -> LONG, up-spike -> SHORT, déclenché quand 5 conditions s'alignent :
    gap overnight significatif, spike notable, rejet de bougie (exhaustion), régime de
    volatilité élevé, confirmation volume. Comparaisons avec NaN -> False -> signal 0.

    Nécessite les colonnes (via compute_features_opening_drive) : gap_z,
    spike_magnitude, rejection_body, vol_regime, relvol_open, hour_ny, min_ny.

    Args:
        window_end_min: fin de la fenêtre en minutes NY locales (600 = 10:00, 630 = 10:30).
        gap_threshold: |gap_z| minimum (en σ) pour un setup valide.
        spike_min: déplacement minimum (points) du close vs open_ref.
        rejet_seuil: rejection_body minimum pour un rejet de down-spike (LONG).
        relvol_seuil: relvol_open minimum (confirmation volume).

    Returns: copy de df + colonne 'signal' (+1 LONG, -1 SHORT, 0 none).
    """
    out = df.copy()
    out['signal'] = 0
    ny_min = out['hour_ny'] * 60 + out['min_ny']
    in_window = (ny_min >= 9 * 60 + 30) & (ny_min < window_end_min)

    long_cond = (
        in_window
        & (out['gap_z'] <= -gap_threshold)
        & (out['spike_magnitude'] <= -spike_min)
        & (out['rejection_body'] >= rejet_seuil)
        & (out['vol_regime'])
        & (out['relvol_open'] >= relvol_seuil)
    )
    short_cond = (
        in_window
        & (out['gap_z'] >= gap_threshold)
        & (out['spike_magnitude'] >= spike_min)
        & (out['rejection_body'] <= 1.0 - rejet_seuil)
        & (out['vol_regime'])
        & (out['relvol_open'] >= relvol_seuil)
    )
    out.loc[long_cond, 'signal'] = 1
    out.loc[short_cond, 'signal'] = -1
    return out
```

- [ ] **Step 4: Lancer les tests — ils doivent PASSER**

Run: `python -m pytest 01_research/tests/test_signal_opening_drive.py -v`
Expected: PASS — 7 tests passés.

- [ ] **Step 5: Commit**

```bash
git add 01_research/src/signals.py 01_research/tests/test_signal_opening_drive.py
git commit -m "feat(research): signal_opening_drive_failure - fade conditionné du spike d'open"
```

---

### Task 3 : `exit_logic_return_to_open` — la sortie « retour au corps »

**Files:**
- Modify: `01_research/src/backtest.py` (append une fonction dans la section exit logics)
- Create: `01_research/tests/test_exit_return_to_open.py`

**Pourquoi :** la thèse dit que le faux spike est une *mèche* et que le prix revient vers le *corps* — l'`open_ref` du jour. L'exit vise donc le retour à `open_ref`. Pour un LONG (on a fadé un down-spike, entrée sous l'open), le TP est `open_ref` au-dessus → touché quand le `high` de la bougie l'atteint. Symétrique pour un SHORT. Fill au prix exact (limit order, pas de slippage — comme `exit_logic_orb` et `exit_logic_fixed_tp_std` existants). Le SL wick-aware, le timeout et le force-flat sont imposés par `backtest_pa` du gauntlet — cet `exit_logic` ne fait que le TP.

- [ ] **Step 1: Écrire les tests qui échouent**

Create `01_research/tests/test_exit_return_to_open.py` :

```python
"""Tests de exit_logic_return_to_open — données synthétiques."""
import numpy as np
import pandas as pd

from src.backtest import exit_logic_return_to_open

# Signature exit_logic : (df, i, j, direction, entry_price, std_i, mid_i,
#                         or_high, or_low, or_range, sl_pts)
_NAN = float("nan")


def _df(open_ref, high, low):
    """df 2 barres : barre 0 = entrée, barre 1 = barre testée (j=1)."""
    return pd.DataFrame({
        "open_ref": [open_ref, open_ref],
        "high": [high, high],
        "low": [low, low],
    })


def test_long_tp_touche_quand_high_atteint_open_ref():
    # LONG : entrée à 95 (down-spike), open_ref = 100. high de la barre = 101 >= 100 -> TP.
    df = _df(open_ref=100.0, high=101.0, low=99.0)
    touched, price, reason = exit_logic_return_to_open(
        df, 0, 1, 1, 95.0, 4.0, 95.0, _NAN, _NAN, _NAN, 6.0)
    assert touched is True
    assert price == 100.0
    assert reason == "TP_return_to_open"


def test_long_tp_pas_touche_si_high_sous_open_ref():
    # LONG, high = 99 < open_ref 100 -> pas de TP.
    df = _df(open_ref=100.0, high=99.0, low=97.0)
    touched, price, reason = exit_logic_return_to_open(
        df, 0, 1, 1, 95.0, 4.0, 95.0, _NAN, _NAN, _NAN, 6.0)
    assert touched is False


def test_short_tp_touche_quand_low_atteint_open_ref():
    # SHORT : entrée à 105 (up-spike), open_ref = 100. low de la barre = 99 <= 100 -> TP.
    df = _df(open_ref=100.0, high=106.0, low=99.0)
    touched, price, reason = exit_logic_return_to_open(
        df, 0, 1, -1, 105.0, 4.0, 105.0, _NAN, _NAN, _NAN, 6.0)
    assert touched is True
    assert price == 100.0
    assert reason == "TP_return_to_open"


def test_short_tp_pas_touche_si_low_au_dessus_open_ref():
    # SHORT, low = 101 > open_ref 100 -> pas de TP.
    df = _df(open_ref=100.0, high=104.0, low=101.0)
    touched, price, reason = exit_logic_return_to_open(
        df, 0, 1, -1, 105.0, 4.0, 105.0, _NAN, _NAN, _NAN, 6.0)
    assert touched is False


def test_open_ref_nan_pas_de_tp():
    df = _df(open_ref=np.nan, high=101.0, low=99.0)
    touched, price, reason = exit_logic_return_to_open(
        df, 0, 1, 1, 95.0, 4.0, 95.0, _NAN, _NAN, _NAN, 6.0)
    assert touched is False
```

- [ ] **Step 2: Lancer les tests — ils doivent ÉCHOUER**

Run: `python -m pytest 01_research/tests/test_exit_return_to_open.py -v`
Expected: FAIL — `ImportError: cannot import name 'exit_logic_return_to_open' from 'src.backtest'`

- [ ] **Step 3: Implémenter `exit_logic_return_to_open`**

Append à la fin de `01_research/src/backtest.py` (après les autres `exit_logic_*`) :

```python
def exit_logic_return_to_open(df, i, j, direction, entry_price, std_i, mid_i,
                              or_high, or_low, or_range, sl_pts):
    """TP Opening Drive Failure : retour au prix d'open du jour (le 'corps').

    Le faux spike est censé revenir vers open_ref. TP = open_ref, vérifié sur wicks
    (high/low de la bougie). Fill au prix exact — limit order, pas de slippage (comme
    exit_logic_orb / exit_logic_fixed_tp_std).

    Nécessite la colonne 'open_ref' dans df (via compute_features_opening_drive).
    """
    tp_price = df.at[j, 'open_ref'] if 'open_ref' in df.columns else np.nan
    if pd.isna(tp_price):
        return False, 0.0, ''
    hj = df.at[j, 'high']
    lj = df.at[j, 'low']
    tp_touched = (direction == 1 and hj >= tp_price) or (direction == -1 and lj <= tp_price)
    if tp_touched:
        return True, tp_price, 'TP_return_to_open'
    return False, 0.0, ''
```

- [ ] **Step 4: Lancer les tests — ils doivent PASSER**

Run: `python -m pytest 01_research/tests/test_exit_return_to_open.py -v`
Expected: PASS — 5 tests passés.

- [ ] **Step 5: Commit**

```bash
git add 01_research/src/backtest.py 01_research/tests/test_exit_return_to_open.py
git commit -m "feat(research): exit_logic_return_to_open - TP au retour au prix d'open"
```

---

### Task 4 : `hyp_opening_drive_failure.py` — l'objet `Hypothesis` enfichable

**Files:**
- Create: `02_validation/gauntlet/hypotheses/__init__.py` (vide)
- Create: `02_validation/gauntlet/hypotheses/hyp_opening_drive_failure.py`
- Create: `02_validation/gauntlet/tests/test_hyp_opening_drive_failure.py`

**Pourquoi :** l'objet `Hypothesis` est l'interface enfichable que `run_gauntlet()` consomme (cf. Plan 1/3). Il wrappe les 3 fonctions des Tasks 1-3 : `prepare_features` chaîne `compute_signal_features` (pour `std`/`mid` exigés par `backtest_pa`) puis `compute_features_opening_drive` ; `build_variant(params)` retourne `(signal_fn, exit_logic, backtest_kwargs)` pour un jeu de params ; `param_grid` est la **grille délibérée de 4 trials** (`window_end_min` × `gap_threshold`). `instrument='MNQ'`, `timeframe='1min'`. Le dossier `hypotheses/` est parallèle à `calibration/` — les vraies hypothèses de recherche y vivront.

- [ ] **Step 1: Écrire les tests qui échouent**

Create `02_validation/gauntlet/tests/test_hyp_opening_drive_failure.py` :

```python
"""Tests de l'hypothèse Opening Drive Failure Fade (objet Hypothesis bien formé)."""
import numpy as np
import pandas as pd

from gauntlet.hypothesis import Hypothesis
from gauntlet.hypotheses.hyp_opening_drive_failure import HYP_OPENING_DRIVE_FAILURE


def test_hypothesis_bien_formee():
    h = HYP_OPENING_DRIVE_FAILURE
    assert isinstance(h, Hypothesis)
    assert h.name == "opening_drive_failure"
    assert h.instrument == "MNQ"
    assert h.timeframe == "1min"
    assert h.n_trials == 4
    assert callable(h.prepare_features)


def test_build_variant_retourne_le_triplet():
    h = HYP_OPENING_DRIVE_FAILURE
    for params in h.param_grid:
        signal_fn, exit_logic, bt_kwargs = h.build_variant(params)
        assert callable(signal_fn)
        assert callable(exit_logic)
        assert bt_kwargs["bar_size_min"] == 1
        assert "timeout_bars" in bt_kwargs


def test_param_grid_est_window_x_gap():
    grid = HYP_OPENING_DRIVE_FAILURE.param_grid
    windows = {p["window_end_min"] for p in grid}
    gaps = {p["gap_threshold"] for p in grid}
    assert windows == {600, 630}              # 9:30-10:00 et 9:30-10:30
    assert gaps == {0.5, 1.0}
    assert len(grid) == 4


def test_prepare_features_ajoute_les_colonnes_attendues():
    # df de session synthétique : 2 jours, 5 barres/jour autour de 9:30 NY
    rows = []
    for day in ["2022-01-03", "2022-01-04"]:
        for b in range(5):
            ts = pd.Timestamp(f"{day} 09:3{b}", tz="America/New_York").tz_convert("UTC")
            rows.append({"bar": ts, "open": 100.0 + b, "high": 102.0 + b,
                         "low": 98.0 + b, "close": 100.5 + b, "volume": 1000.0})
    df = pd.DataFrame(rows).set_index("bar")
    df["date"] = df.index.tz_convert("America/New_York").date
    df["hour_ny"] = 9
    df["min_ny"] = [30, 31, 32, 33, 34] * 2

    feat = HYP_OPENING_DRIVE_FAILURE.prepare_features(df)
    # std + mid (via compute_signal_features, exigés par backtest_pa)
    assert {"std", "mid"}.issubset(feat.columns)
    # features opening drive
    assert {"open_ref", "gap_z", "spike_magnitude", "rejection_body",
            "vol_regime", "relvol_open"}.issubset(feat.columns)


def test_build_variant_signal_fn_produit_une_colonne_signal():
    # le signal_fn doit tourner sur un df qui a les features et produire 'signal'
    h = HYP_OPENING_DRIVE_FAILURE
    signal_fn, _, _ = h.build_variant(h.param_grid[0])
    df = pd.DataFrame({
        "gap_z": [np.nan], "spike_magnitude": [0.0], "rejection_body": [0.5],
        "vol_regime": [False], "relvol_open": [np.nan], "hour_ny": [9], "min_ny": [45],
    })
    out = signal_fn(df)
    assert "signal" in out.columns
    assert out["signal"].iloc[0] == 0          # features dégénérées -> pas de signal
```

- [ ] **Step 2: Lancer les tests — ils doivent ÉCHOUER**

Run: `python -m pytest 02_validation/gauntlet/tests/test_hyp_opening_drive_failure.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'gauntlet.hypotheses'`

- [ ] **Step 3: Créer le package + l'hypothèse**

Create `02_validation/gauntlet/hypotheses/__init__.py` (fichier vide, 0 octet).

Create `02_validation/gauntlet/hypotheses/hyp_opening_drive_failure.py` :

```python
"""Hypothèse de recherche #1 — Opening Drive Failure Fade (MNQ).

Première vraie hypothèse de recherche passée dans le gauntlet. Le 1er move de l'open
MNQ est un faux spike (mèche, pas corps) ; on le fade, entrée sur exhaustion conditionnée
(gap overnight significatif + rejet de bougie + régime haute vol + volume), exit = retour
au prix d'open. Feature set littérature-grounded.

Spec : docs/superpowers/specs/2026-05-15-opening-drive-failure-fade-design.md
"""
from __future__ import annotations

from src.features import compute_signal_features, compute_features_opening_drive
from src.signals import signal_opening_drive_failure
from src.backtest import exit_logic_return_to_open

from gauntlet.hypothesis import Hypothesis

# ── Constantes figées (cf. spec — "défauts sensés", non grillés) ────
_BAR_MIN = 1
_TIMEOUT_BARS = 15      # ~15 min : l'observation dit que le faux move se résout vite
_LOOKBACK = 20          # lookback de compute_signal_features (std / mid pour backtest_pa)
_SPIKE_MIN = 15.0       # déplacement minimum du spike (points)
_REJET_SEUIL = 0.66     # rejection_body minimum
_RELVOL_SEUIL = 1.0     # confirmation volume


def _prepare_features(df):
    """Chaîne compute_signal_features (std/mid pour backtest_pa) puis les features
    Opening Drive (gap_z, spike_magnitude, rejection_body, vol_regime, relvol_open)."""
    df = compute_signal_features(df, lookback=_LOOKBACK)
    df = compute_features_opening_drive(df)
    return df


def _build_variant(params):
    """params: {'window_end_min': int, 'gap_threshold': float}.
    Retourne (signal_fn, exit_logic, backtest_kwargs)."""
    window_end_min = params["window_end_min"]
    gap_threshold = params["gap_threshold"]

    def signal_fn(df):
        return signal_opening_drive_failure(
            df, window_end_min=window_end_min, gap_threshold=gap_threshold,
            spike_min=_SPIKE_MIN, rejet_seuil=_REJET_SEUIL, relvol_seuil=_RELVOL_SEUIL,
        )

    return signal_fn, exit_logic_return_to_open, {
        "bar_size_min": _BAR_MIN, "timeout_bars": _TIMEOUT_BARS,
    }


HYP_OPENING_DRIVE_FAILURE = Hypothesis(
    name="opening_drive_failure",
    description=("Opening Drive Failure Fade MNQ 1min — fade le faux spike d'open, "
                 "conditionné gap overnight + rejet + régime haute vol, exit retour open"),
    instrument="MNQ",
    timeframe="1min",
    build_variant=_build_variant,
    param_grid=[
        {"window_end_min": 600, "gap_threshold": 0.5},   # 9:30-10:00, gap 0.5σ
        {"window_end_min": 600, "gap_threshold": 1.0},   # 9:30-10:00, gap 1.0σ
        {"window_end_min": 630, "gap_threshold": 0.5},   # 9:30-10:30, gap 0.5σ
        {"window_end_min": 630, "gap_threshold": 1.0},   # 9:30-10:30, gap 1.0σ
    ],
    prepare_features=_prepare_features,
)
```

- [ ] **Step 4: Lancer les tests — ils doivent PASSER**

Run: `python -m pytest 02_validation/gauntlet/tests/test_hyp_opening_drive_failure.py -v`
Expected: PASS — 5 tests passés.

- [ ] **Step 5: Lancer toute la suite (non-régression)**

Run: `python -m pytest 01_research/tests/ 02_validation/gauntlet/tests/ -q`
Expected: PASS — toute la suite verte (les tests existants + les nouveaux des Tasks 1-4).

- [ ] **Step 6: Commit**

```bash
git add 02_validation/gauntlet/hypotheses/ 02_validation/gauntlet/tests/test_hyp_opening_drive_failure.py
git commit -m "feat(gauntlet): hyp_opening_drive_failure - hypothèse de recherche #1 enfichable"
```

---

### Task 5 : `04_run_opening_drive_failure.py` — le script runner

**Files:**
- Create: `02_validation/notebooks/04_run_opening_drive_failure.py`

**Pourquoi :** lancer l'hypothèse dans le gauntlet sur les vraies données = charger le CSV Databento MNQ 5 ans + features + batterie complète → plusieurs minutes. C'est un **script** (pas un test pytest), parallèle à `03_gauntlet_calibration.py`, que BB lance. Contrairement à la calibration, **pas d'`assert`** sur le verdict : on ne connaît pas la réponse — c'est tout l'intérêt. Le script lance `run_gauntlet`, écrit le rapport, imprime le verdict + les 8 critères.

- [ ] **Step 1: Créer le script runner**

Create `02_validation/notebooks/04_run_opening_drive_failure.py` :

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
# # Gauntlet — Hypothèse #1 : Opening Drive Failure Fade (MNQ)
#
# Lance le gauntlet complet (`run_gauntlet`) sur la première vraie hypothèse de
# recherche d'edge. Contrairement à la calibration, on NE connaît PAS la réponse —
# le gauntlet tranche GO / NO-GO / CONDITIONAL.
#
# Spec : `docs/superpowers/specs/2026-05-15-opening-drive-failure-fade-design.md`
#
# **Exécuter depuis la racine du repo** (`python 02_validation/notebooks/04_run_opening_drive_failure.py`).
# Charge le CSV Databento MNQ 5 ans (~1.7M lignes) — compter plusieurs minutes.

# %%
from __future__ import annotations

import sys
from pathlib import Path

# Console Windows cp1252 ne peut pas imprimer les emojis — forcer UTF-8.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Ce script tourne depuis la racine du repo. 02_validation/ et 01_research/ sur le path.
_REPO_ROOT = Path(".").resolve()
_VALIDATION = _REPO_ROOT / "02_validation"
_RESEARCH = _REPO_ROOT / "01_research"
if not _VALIDATION.is_dir() or not _RESEARCH.is_dir():
    raise RuntimeError(
        f"02_validation/ ou 01_research/ introuvable depuis {_REPO_ROOT}. "
        "Lancer ce script depuis la racine du repo."
    )
for p in (str(_VALIDATION), str(_RESEARCH)):
    if p not in sys.path:
        sys.path.insert(0, p)

from gauntlet.run_gauntlet import run_gauntlet
from gauntlet.hypotheses.hyp_opening_drive_failure import HYP_OPENING_DRIVE_FAILURE

OUT_DIR = _VALIDATION / "outputs" / "gauntlet" / HYP_OPENING_DRIVE_FAILURE.name
OUT_DIR.mkdir(parents=True, exist_ok=True)

# %% [markdown]
# ## Lancement du gauntlet
#
# `run_gauntlet` charge les vraies données MNQ, prépare les splits, lance la batterie
# (walk-forward, CPCV, DSR, PBO, Monte Carlo, stress test, cycle PA) et agrège le verdict.

# %%
print("=" * 72)
print(f"GAUNTLET — {HYP_OPENING_DRIVE_FAILURE.name}")
print("=" * 72)

verdict = run_gauntlet(HYP_OPENING_DRIVE_FAILURE, splits=None, out_dir=str(OUT_DIR))

print(f"\n  VERDICT     : {verdict.verdict}")
print(f"  hard fails  : {[c.name for c in verdict.hard_fails]}")
print("\n  Critères :")
for c in verdict.criteria:
    mark = "OK  " if c.passed else "FAIL"
    print(f"    [{mark}] {c.name:18} = {c.value}")
print("\n  Caveats :")
for cav in verdict.caveats:
    print(f"    - {cav}")
print("\n  Next steps :")
for step in verdict.next_steps:
    print(f"    - {step}")
print(f"\n  Rapport complet : {OUT_DIR / 'gauntlet_report.md'}")

# %% [markdown]
# ## Lecture du verdict
#
# - **GO** → cross-validation NT8 Strategy Analyzer + sim live ≥ 2 semaines (next steps).
# - **NO-GO / CONDITIONAL** → résultat honnête. Relire les critères échoués, décider :
#   raffiner (ex. news blackout contre le momentum-flip) ou pivoter sur une autre thèse.
#   Vu la prudence de la littérature, un NO-GO est un résultat probable — et c'est le
#   process qui marche, pas un échec.

# %%
print("\nRun terminé. Verdict ci-dessus, rapport détaillé dans le dossier outputs.")
```

- [ ] **Step 2: Vérifier la syntaxe et les imports**

Run: `python -c "import ast; ast.parse(open('02_validation/notebooks/04_run_opening_drive_failure.py', encoding='utf-8').read()); print('syntaxe OK')"`
Expected: `syntaxe OK`

Run: `python -c "import sys; sys.path.insert(0, '02_validation'); sys.path.insert(0, '01_research'); from gauntlet.run_gauntlet import run_gauntlet; from gauntlet.hypotheses.hyp_opening_drive_failure import HYP_OPENING_DRIVE_FAILURE; print('imports OK')"`
Expected: `imports OK`

- [ ] **Step 3: Commit**

```bash
git add 02_validation/notebooks/04_run_opening_drive_failure.py
git commit -m "feat(gauntlet): script runner hypothèse #1 Opening Drive Failure Fade"
```

- [ ] **Step 4: (BB) Lancer le gauntlet sur les vraies données**

Le run réel est à lancer par BB (vraies données, plusieurs minutes) :
Run: `python 02_validation/notebooks/04_run_opening_drive_failure.py`
Le verdict GO / NO-GO / CONDITIONAL s'imprime, le rapport atterrit dans `02_validation/outputs/gauntlet/opening_drive_failure/`. **Pas de réponse attendue connue** — c'est le gauntlet qui tranche.

---

## Self-Review (effectuée à l'écriture du plan)

**1. Couverture spec** — chaque pièce du spec a sa task :
- Features littérature-grounded (`gap_z`, `spike_magnitude`, `rejection_body`, `vol_regime`, `relvol_open`, `open_ref`, `prev_close`) → Task 1.
- Signal conditionné 5 conditions → Task 2.
- Exit retour à l'open → Task 3.
- Objet `Hypothesis` (instrument MNQ, timeframe 1min, grille 4 trials window × gap_threshold, `prepare_features` chaînant std/mid + opening drive) → Task 4.
- Script runner → Task 5.
- Le gauntlet lui-même (batterie, verdict, report) est réutilisé tel quel — déjà mergé Plans 1-3, hors scope de ce plan.

**2. Placeholders** — aucun TBD/TODO. Tout le code est complet et exécutable. Les params « figés à des défauts sensés » du spec sont matérialisés en constantes nommées dans `hyp_opening_drive_failure.py` (`_SPIKE_MIN`, `_REJET_SEUIL`, `_RELVOL_SEUIL`, `_TIMEOUT_BARS`) — ce sont des valeurs concrètes, pas des placeholders.

**3. Cohérence des types** — vérifiée bout en bout :
- `compute_features_opening_drive` produit `open_ref, prev_close, gap_z, spike_magnitude, rejection_body, vol_regime, relvol_open` (Task 1) — exactement les colonnes que `signal_opening_drive_failure` consomme (Task 2) et que `exit_logic_return_to_open` lit (`open_ref`, Task 3).
- `signal_opening_drive_failure` signature `(df, window_end_min, gap_threshold, spike_min, rejet_seuil, relvol_seuil)` — appelée avec exactement ces kwargs par `_build_variant` (Task 4).
- `exit_logic_return_to_open` suit la signature `exit_logic` standard à 11 args positionnels — compatible avec `backtest_pa` du gauntlet.
- `_prepare_features` chaîne `compute_signal_features` (→ `std`, `mid`) puis `compute_features_opening_drive` — `backtest_pa` exige `std`/`mid`, c'est couvert.
- `param_grid` : dicts `{window_end_min, gap_threshold}` — `_build_variant` lit exactement ces deux clés.
- `Hypothesis` construit avec les 7 champs (name, description, instrument, timeframe, build_variant, param_grid, prepare_features) — conforme à la dataclass de Plan 3.
