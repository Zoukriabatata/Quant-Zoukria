# Gauntlet — Plan 3 : Verdict + orchestration + calibration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Boucler le gauntlet de validation : l'agrégateur de verdict GO/NO-GO/CONDITIONAL, l'orchestrateur `run_gauntlet(hypothesis) -> Verdict` qui assemble les 5 blocs, et les 2 hypothèses de calibration known-answer (v9 HurstMR + EOD reversal) qui DOIVENT ressortir NO-GO — le test que la machine juge correctement.

**Architecture:** `verdict.py` applique les seuils de la checklist pré-déploiement Apex aux sorties des Blocs 3-4. `run_gauntlet.py` enchaîne Bloc 1 (préparation : load → resample → features → splits), Bloc 2 (le `run_variant` concret = signal_fn + `backtest_pa`), Blocs 3-4 (la batterie Plan 2), Bloc 5 (verdict). `report.py` écrit le rapport markdown + CSVs. Les 2 hypothèses de calibration sont des objets `Hypothesis` enfichables. Tests pytest sur données **synthétiques** (rapides, CI-safe) ; la calibration sur les vraies données 5 ans est un **script** que BB lance (décision BB — comme le sprint exit notebook).

**Tech Stack:** Python 3.10+, pandas, numpy, scipy, pytest. Réutilise tout le socle Plan 1 + la batterie Plan 2 + `01_research/src/` (data_loader, features, signals, hurst, backtest).

**Spec de référence:** `docs/superpowers/specs/2026-05-14-gauntlet-validation-design.md` (Blocs 1, 2, 5 + section Calibration).

**Plans précédents:** `2026-05-14-gauntlet-plan1-backtest-core.md` + `2026-05-14-gauntlet-plan2-stat-battery.md` (mergés dans `main`).

---

## Note pédagogique (préférence BB — apprendre au fil du projet)

BB veut **comprendre** ce qui est codé. Chaque task inclut un **"Pourquoi"** : le concept quant ou le choix de design. L'implémenteur DOIT garder ces explications dans les rapports.

---

## Décisions actées avec BB avant ce plan

1. **Seuil DSR.** Le spec et CLAUDE.md disent "DSR > 0", mais `deflated_sharpe_ratio` renvoie une probabilité ∈ (0,1) — toujours > 0. Décision BB : **DSR > 0.95** (convention déjà dans le repo, cf. `run_final_validation.py`). `DSR ≤ 0.95` = hard-fail → NO-GO.
2. **Exécution de la calibration.** Faire tourner v9 + EOD reversal dans `run_gauntlet` sur les vraies données = charger le CSV Databento 5 ans + Hurst rolling + walk-forward → plusieurs minutes, dépend d'un fichier local. Décision BB : **pytest sur synthétique + script sur vraies données**. Les tests pytest tournent sur une hypothèse synthétique injectée ; un script `02_validation/notebooks/03_gauntlet_calibration.py` lance les 2 vrais contrôles sur les 5 ans, écrit les rapports, et `assert` les 2 NO-GO. BB le lance.

## Choix de design documentés (à valider en review)

- **`Hypothesis` gagne un champ `prepare_features`.** Les features sont hypothèse-spécifiques (z-score pour MR, + Hurst rolling pour v9). Plan 1 a figé `Hypothesis` à 6 champs. On ajoute un 7e champ **optionnel** `prepare_features: Callable | None = None` — backward-compatible (les tests Plan 1 construisent sans, le défaut `None` les garde verts). Calculé **une fois** sur le df de session complet avant le découpage en splits — les features sont backward-looking (rolling), donc les calculer puis slicer ne fuit rien et évite de recomputer le Hurst (coûteux) par tranche.
- **Encodage des 2 contrôles de calibration.** Le gauntlet impose ses propres mécaniques (`backtest_pa` : SL `1.5×std` wick-aware, force-flat 15:55, friction obligatoire) — un contrôle "v9" jugé par le gauntlet n'est donc PAS le v9 NT8 à l'identique, c'est "l'ENTRÉE v9 jugée par les mécaniques honnêtes du gauntlet". C'est voulu : v9 est déjà mort en NT8 SA (PF 1.02), il doit l'être aussi ici. v9 = `signal_mr_zscore(entry_threshold=2.75)` gaté par `hurst < 0.58` (LB=19, HW=50), exit `exit_logic_mr_zscore`. EOD reversal = `signal_mr_zscore(entry_threshold=2.0, allowed_hours={15})`, exit `exit_logic_mr_zscore` (config C0/C1/C2 de mini-val #4). Les deux : MNQ 5min.
- **Le "meilleur variant"** est sélectionné sur **Train** par Sharpe (spec : "le meilleur variant de la grille, sélectionné sur Train"). Le walk-forward fait sa propre sélection par fenêtre — c'est indépendant.
- **PBO** exige ≥ 2 variants. Grille à 1 variant → critère PBO marqué N/A (pas un échec).
- **Holdout** : ouvert **une seule fois** en toute fin, un seul `backtest_pa` du meilleur variant, reporté comme confirmation à **confiance dégradée** (contaminé) — jamais un critère GO.

---

## Le contrat `run_variant` (rappel Plan 2)

`run_variant(df, params) -> (trades_df, account)`. Plan 2 a construit `walk_forward` / `stress_test` / `pa_cycle` autour de ce callable injecté. Plan 3 livre le `run_variant` **concret** (`make_run_variant`) : il applique la `signal_fn` de l'hypothèse puis `backtest_pa` sur un `PaAccount` neuf.

---

## File Structure

| Fichier | Responsabilité | Task |
|---|---|---|
| `02_validation/gauntlet/hypothesis.py` | **MODIFIÉ** — ajoute le champ `prepare_features` | 1 |
| `02_validation/gauntlet/verdict.py` | **NEW** — `CriterionResult`, `Verdict`, `build_verdict` + seuils | 2 |
| `02_validation/gauntlet/run_gauntlet.py` | **NEW** — Bloc 1 prep + `make_run_variant` (T3), helpers grille (T4), `run_gauntlet` (T5) | 3-5 |
| `02_validation/gauntlet/report.py` | **NEW** — `write_gauntlet_report` : markdown + CSVs | 6 |
| `02_validation/gauntlet/calibration/__init__.py` | marqueur de package (vide) | 7 |
| `02_validation/gauntlet/calibration/hyp_eod_reversal.py` | **NEW** — hypothèse contrôle EOD reversal | 7 |
| `02_validation/gauntlet/calibration/hyp_v9_hurstmr.py` | **NEW** — hypothèse contrôle v9 HurstMR | 7 |
| `02_validation/notebooks/03_gauntlet_calibration.py` | **NEW** — script de calibration sur vraies données (BB le lance) | 8 |
| `02_validation/gauntlet/tests/test_*.py` | tests unitaires par module | 1-7 |

**Aucune modification de `pyproject.toml`** : `02_validation/gauntlet/tests` est déjà dans `testpaths`. Le notebook de calibration n'est pas un test pytest.

---

### Task 1 : `hypothesis.py` — ajoute le champ `prepare_features`

**Files:**
- Modify: `02_validation/gauntlet/hypothesis.py`
- Modify: `02_validation/gauntlet/tests/test_hypothesis.py`

**Pourquoi :** le gauntlet doit calculer les features dont la `signal_fn` a besoin avant de générer les signaux. Ces features sont **hypothèse-spécifiques** : un MR z-score veut `mid/std/zscore`, le v9 veut en plus une colonne `hurst` rolling. Plan 1 a figé `Hypothesis` à 6 champs. On ajoute un 7e champ **optionnel** `prepare_features` (défaut `None`) : un callable `df -> df` appliqué **une fois** sur le df de session complet, avant le découpage en splits. Optionnel et avec défaut → les tests Plan 1 (qui construisent `Hypothesis` sans ce champ) restent verts.

- [ ] **Step 1: Écrire les tests qui échouent**

Add to `02_validation/gauntlet/tests/test_hypothesis.py` (à la fin du fichier) :

```python
def test_hypothesis_prepare_features_default_none():
    h = Hypothesis(
        name="dummy", description="", instrument="MNQ", timeframe="5min",
        build_variant=_dummy_build_variant, param_grid=[{"timeout_bars": 12}],
    )
    assert h.prepare_features is None


def test_hypothesis_prepare_features_accepts_callable():
    def _prep(df):
        return df
    h = Hypothesis(
        name="dummy", description="", instrument="MNQ", timeframe="5min",
        build_variant=_dummy_build_variant, param_grid=[{"timeout_bars": 12}],
        prepare_features=_prep,
    )
    assert h.prepare_features is _prep


def test_hypothesis_prepare_features_non_callable_leve_erreur():
    with pytest.raises(TypeError):
        Hypothesis(
            name="bad", description="", instrument="MNQ", timeframe="5min",
            build_variant=_dummy_build_variant, param_grid=[{"timeout_bars": 12}],
            prepare_features="pas une fonction",
        )
```

- [ ] **Step 2: Lancer les tests — ils doivent ÉCHOUER**

Run: `python -m pytest 02_validation/gauntlet/tests/test_hypothesis.py -v`
Expected: FAIL — les 3 nouveaux tests échouent (`TypeError: __init__() got an unexpected keyword argument 'prepare_features'` et `AttributeError`). Les 3 tests existants passent encore.

- [ ] **Step 3: Implémenter le champ**

Replace the ENTIRE content of `02_validation/gauntlet/hypothesis.py` with :

```python
"""L'interface Hypothesis : l'objet enfichable que le gauntlet juge."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional


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
        prepare_features : callable(df) -> df OPTIONNEL. Calcule les features dont la
                         signal_fn a besoin (mid/std/zscore, Hurst rolling…). Appliqué
                         UNE fois sur le df de session complet avant le découpage en
                         splits — les features sont backward-looking, donc les calculer
                         puis slicer ne fuit rien. None -> df de session utilisé tel quel.
    """
    name: str
    description: str
    instrument: str
    timeframe: str
    build_variant: Callable
    param_grid: list
    prepare_features: Optional[Callable] = None

    def __post_init__(self):
        if not self.param_grid:
            raise ValueError(f"Hypothesis '{self.name}': param_grid est vide")
        if not callable(self.build_variant):
            raise TypeError(f"Hypothesis '{self.name}': build_variant doit être callable")
        if self.prepare_features is not None and not callable(self.prepare_features):
            raise TypeError(
                f"Hypothesis '{self.name}': prepare_features doit être callable ou None"
            )

    @property
    def n_trials(self) -> int:
        """Nombre de variants testés — alimente la pénalité du Deflated Sharpe."""
        return len(self.param_grid)
```

- [ ] **Step 4: Lancer les tests — ils doivent PASSER**

Run: `python -m pytest 02_validation/gauntlet/tests/test_hypothesis.py -v`
Expected: PASS — 6 tests passés (3 originaux + 3 nouveaux).

- [ ] **Step 5: Lancer toute la suite gauntlet (non-régression)**

Run: `python -m pytest 02_validation/gauntlet/tests/ -q`
Expected: PASS — 83 passés (80 d'avant + 3 nouveaux).

- [ ] **Step 6: Commit**

```bash
git add 02_validation/gauntlet/hypothesis.py 02_validation/gauntlet/tests/test_hypothesis.py
git commit -m "feat(gauntlet): hypothesis - champ optionnel prepare_features"
```

---

### Task 2 : `verdict.py` — l'agrégateur GO / NO-GO / CONDITIONAL

**Files:**
- Create: `02_validation/gauntlet/verdict.py`
- Create: `02_validation/gauntlet/tests/test_verdict.py`

**Pourquoi :** c'est le Bloc 5 — il transforme les chiffres de la batterie en une **décision traçable**. Il applique les seuils de la checklist pré-déploiement Apex (CLAUDE.md). La logique : certains critères sont **éliminatoires** (hard fail) — compte mort, DSR ≤ 0.95, Monte Carlo p ≥ 0.05, stress test échoué — n'importe lequel échoué = **NO-GO**. Si aucun hard fail mais qu'un critère mou échoue (walk-forward marginal, PBO, max DD, cycle PA) = **CONDITIONAL** (cœur OK, caveats). Tout passe = **GO**. Le verdict liste aussi les next steps non-automatisables (cross-validation NT8, sim live) et le caveat holdout. `verdict.py` est une fonction pure — il ne lance aucun backtest, il juge des dicts.

- [ ] **Step 1: Écrire les tests qui échouent**

Create `02_validation/gauntlet/tests/test_verdict.py` :

```python
"""Tests de l'agrégateur de verdict GO / NO-GO / CONDITIONAL."""
from gauntlet.verdict import build_verdict, Verdict, CriterionResult


def _passing_kwargs():
    """Jeu d'arguments où TOUS les critères passent -> GO."""
    return dict(
        hypothesis_name="hyp_test",
        account_survived=True,
        wf_summary={"n_windows": 4, "pct_oos_profitable": 0.80},
        mc={"p_value": 0.01},
        dsr=0.99,
        pbo=0.20,
        full_max_dd=-600.0,
        stress_passed=True,
        reached_lock=True,
        inactivity_safe=True,
        holdout_note="Holdout : PF 1.5 (confiance dégradée).",
    )


def test_all_pass_gives_go():
    v = build_verdict(**_passing_kwargs())
    assert isinstance(v, Verdict)
    assert v.verdict == "GO"
    assert len(v.criteria) == 8
    assert all(c.passed for c in v.criteria)
    assert any("NinjaTrader" in s for s in v.next_steps)


def test_dead_account_is_hard_fail_nogo():
    kw = _passing_kwargs()
    kw["account_survived"] = False
    v = build_verdict(**kw)
    assert v.verdict == "NO-GO"
    assert any(c.name == "account_alive" and c.is_hard_fail for c in v.criteria)


def test_dsr_below_threshold_is_hard_fail_nogo():
    kw = _passing_kwargs()
    kw["dsr"] = 0.93                       # < 0.95
    v = build_verdict(**kw)
    assert v.verdict == "NO-GO"
    assert any(c.name == "deflated_sharpe" and c.is_hard_fail for c in v.criteria)


def test_mc_pvalue_high_is_hard_fail_nogo():
    kw = _passing_kwargs()
    kw["mc"] = {"p_value": 0.20}           # >= 0.05
    v = build_verdict(**kw)
    assert v.verdict == "NO-GO"
    assert any(c.name == "monte_carlo" and c.is_hard_fail for c in v.criteria)


def test_stress_fail_is_hard_fail_nogo():
    kw = _passing_kwargs()
    kw["stress_passed"] = False
    v = build_verdict(**kw)
    assert v.verdict == "NO-GO"
    assert any(c.name == "stress_test" and c.is_hard_fail for c in v.criteria)


def test_soft_fail_only_gives_conditional():
    # walk-forward marginal (mou) mais aucun hard fail -> CONDITIONAL
    kw = _passing_kwargs()
    kw["wf_summary"] = {"n_windows": 4, "pct_oos_profitable": 0.50}   # < 0.70
    v = build_verdict(**kw)
    assert v.verdict == "CONDITIONAL"
    wf = next(c for c in v.criteria if c.name == "walk_forward")
    assert wf.passed is False
    assert wf.hard_fail is False


def test_max_dd_too_large_is_soft_fail_conditional():
    kw = _passing_kwargs()
    kw["full_max_dd"] = -1500.0            # |DD| > 1000
    v = build_verdict(**kw)
    assert v.verdict == "CONDITIONAL"


def test_pbo_none_marks_criterion_na_and_passes():
    kw = _passing_kwargs()
    kw["pbo"] = None                       # grille à 1 variant
    v = build_verdict(**kw)
    pbo_c = next(c for c in v.criteria if c.name == "pbo")
    assert pbo_c.passed is True
    assert pbo_c.value == "N/A"
    assert v.verdict == "GO"


def test_caveats_include_holdout_note():
    kw = _passing_kwargs()
    v = build_verdict(**kw)
    assert any("Holdout" in c for c in v.caveats)


def test_nogo_next_steps_say_not_deployable():
    kw = _passing_kwargs()
    kw["account_survived"] = False
    v = build_verdict(**kw)
    assert any("ne PAS déployer" in s or "non validé" in s for s in v.next_steps)


def test_hard_fails_property_lists_failed_eliminatory_criteria():
    kw = _passing_kwargs()
    kw["dsr"] = 0.10
    kw["mc"] = {"p_value": 0.9}
    v = build_verdict(**kw)
    names = {c.name for c in v.hard_fails}
    assert names == {"deflated_sharpe", "monte_carlo"}
```

- [ ] **Step 2: Lancer les tests — ils doivent ÉCHOUER**

Run: `python -m pytest 02_validation/gauntlet/tests/test_verdict.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'gauntlet.verdict'`

- [ ] **Step 3: Implémenter `verdict.py`**

Create `02_validation/gauntlet/verdict.py` :

```python
"""Bloc 5 du gauntlet — l'agrégateur GO / NO-GO / CONDITIONAL.

Prend les sorties des Blocs 3-4 (walk-forward, Monte Carlo, DSR, PBO, stress test, cycle
PA) et applique les seuils de la checklist pré-déploiement Apex de CLAUDE.md. Sort un
Verdict chiffré, traçable critère par critère.

Logique :
  - HARD FAIL (n'importe lequel -> NO-GO) : compte mort, DSR <= seuil, Monte Carlo
    p >= 0.05, stress test échoué. Les fautes éliminatoires.
  - tous les critères passent -> GO.
  - aucun hard fail mais >= 1 critère mou échoué -> CONDITIONAL (cœur OK, caveats).

Fonction pure : verdict.py ne lance aucun backtest, il juge des dicts.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# ── Seuils (checklist pré-déploiement Apex, CLAUDE.md) ──────────────
DSR_GO_THRESHOLD = 0.95      # convention repo (run_final_validation.py "95% confidence")
MAX_DD_LIMIT = 1_000.0       # 50% du DD EOD Apex ($2,000)
WF_MIN_WINDOWS = 3
WF_MIN_PROFITABLE = 0.70     # fraction min de fenêtres OOS rentables
MC_PVALUE_MAX = 0.05
PBO_MAX = 0.5


@dataclass
class CriterionResult:
    """Résultat d'un critère du verdict."""
    name: str
    passed: bool
    value: object        # valeur mesurée (float / bool / str)
    threshold: object    # seuil de référence (pour le rapport)
    hard_fail: bool      # True : échouer ce critère = NO-GO immédiat
    detail: str          # explication lisible

    @property
    def is_hard_fail(self) -> bool:
        """True si ce critère est éliminatoire ET échoué."""
        return self.hard_fail and not self.passed


@dataclass
class Verdict:
    """Verdict global du gauntlet pour une hypothèse."""
    hypothesis_name: str
    verdict: str                       # "GO" | "NO-GO" | "CONDITIONAL"
    criteria: list                     # list[CriterionResult]
    caveats: list = field(default_factory=list)
    next_steps: list = field(default_factory=list)

    @property
    def hard_fails(self) -> list:
        """Les critères éliminatoires échoués."""
        return [c for c in self.criteria if c.is_hard_fail]


def build_verdict(
    hypothesis_name: str,
    account_survived: bool,
    wf_summary: dict,
    mc: dict,
    dsr: float,
    pbo,                       # float | None (None si grille < 2 variants)
    full_max_dd: float,
    stress_passed: bool,
    reached_lock: bool,
    inactivity_safe: bool,
    holdout_note: str,
    dsr_threshold: float = DSR_GO_THRESHOLD,
) -> Verdict:
    """Agrège les outputs des blocs en un Verdict chiffré.

    Args:
        hypothesis_name : nom de l'hypothèse jugée.
        account_survived: le compte survit au run plein Train+Valid (status != dead_eod).
        wf_summary      : sortie de walk_forward_summary (clés n_windows, pct_oos_profitable).
        mc              : sortie de permutation_test_sharpe (clé p_value).
        dsr             : Deflated Sharpe Ratio (probabilité dans (0,1)).
        pbo             : Probability of Backtest Overfitting, ou None si grille < 2 variants.
        full_max_dd     : max_dd ($, <= 0) du run plein Train+Valid (compute_trade_metrics).
        stress_passed   : stress_test_passed — le compte survit à toutes les périodes rouges.
        reached_lock    : le cycle PA atteint le lock $50,100.
        inactivity_safe : le cycle PA respecte la règle d'inactivité.
        holdout_note    : texte de caveat sur le holdout contaminé.
        dsr_threshold   : seuil GO du DSR (défaut 0.95).

    Returns:
        Verdict.
    """
    criteria = []

    # 1. Compte vivant — HARD FAIL
    criteria.append(CriterionResult(
        name="account_alive", passed=bool(account_survived),
        value=bool(account_survived), threshold=True, hard_fail=True,
        detail=("Le compte survit au run plein Train+Valid (jamais de touche du seuil "
                "DD EOD).") if account_survived else
               ("Le compte a touché le seuil DD EOD pendant le run Train+Valid — mort "
                "définitive."),
    ))

    # 2. Walk-forward — MOU
    n_win = wf_summary.get("n_windows", 0)
    pct = wf_summary.get("pct_oos_profitable", 0.0)
    wf_passed = n_win >= WF_MIN_WINDOWS and pct >= WF_MIN_PROFITABLE
    criteria.append(CriterionResult(
        name="walk_forward", passed=wf_passed,
        value=f"{n_win} fenêtres, {pct:.0%} OOS rentables",
        threshold=f">= {WF_MIN_WINDOWS} fenêtres ET >= {WF_MIN_PROFITABLE:.0%} rentables",
        hard_fail=False,
        detail=f"{n_win} fenêtres OOS, {pct:.0%} rentables (min {WF_MIN_PROFITABLE:.0%}).",
    ))

    # 3. Monte Carlo permutation — HARD FAIL
    p = mc.get("p_value", 1.0)
    criteria.append(CriterionResult(
        name="monte_carlo", passed=p < MC_PVALUE_MAX,
        value=p, threshold=f"< {MC_PVALUE_MAX}", hard_fail=True,
        detail=f"p-value Sharpe sous H0 = {p:.4f} "
               f"({'edge significatif' if p < MC_PVALUE_MAX else 'indistinguable du hasard'}).",
    ))

    # 4. Deflated Sharpe Ratio — HARD FAIL
    criteria.append(CriterionResult(
        name="deflated_sharpe", passed=dsr > dsr_threshold,
        value=dsr, threshold=f"> {dsr_threshold}", hard_fail=True,
        detail=f"DSR = {dsr:.4f} (seuil {dsr_threshold} — corrige le multi-testing sur "
               f"la grille).",
    ))

    # 5. PBO — MOU (N/A si grille < 2 variants)
    if pbo is None:
        criteria.append(CriterionResult(
            name="pbo", passed=True, value="N/A", threshold=f"< {PBO_MAX}",
            hard_fail=False,
            detail="PBO non calculé : grille à 1 variant (PBO exige >= 2 configs).",
        ))
    else:
        criteria.append(CriterionResult(
            name="pbo", passed=pbo < PBO_MAX, value=pbo, threshold=f"< {PBO_MAX}",
            hard_fail=False,
            detail=f"PBO = {pbo:.3f} (proba que le meilleur IS tombe dans la moitié "
                   f"basse OOS).",
        ))

    # 6. Max DD simulé — MOU
    dd_ok = abs(full_max_dd) < MAX_DD_LIMIT
    criteria.append(CriterionResult(
        name="max_dd", passed=dd_ok,
        value=full_max_dd, threshold=f"|DD| < ${MAX_DD_LIMIT:.0f}", hard_fail=False,
        detail=f"Max DD séquence de trades = ${full_max_dd:.0f} "
               f"(limite ${MAX_DD_LIMIT:.0f} = 50% du DD EOD Apex).",
    ))

    # 7. Stress test — HARD FAIL
    criteria.append(CriterionResult(
        name="stress_test", passed=bool(stress_passed),
        value=bool(stress_passed), threshold=True, hard_fail=True,
        detail=("Le compte survit à toutes les périodes rouges.") if stress_passed else
               ("Le compte touche le seuil DD EOD sur au moins une période rouge."),
    ))

    # 8. Cycle PA — lock + inactivité — MOU
    cycle_ok = bool(reached_lock and inactivity_safe)
    criteria.append(CriterionResult(
        name="pa_cycle", passed=cycle_ok,
        value=f"lock={reached_lock}, inactivity_safe={inactivity_safe}",
        threshold="lock atteint ET inactivity-safe", hard_fail=False,
        detail=f"Cycle PA continu : lock $50,100 "
               f"{'atteint' if reached_lock else 'NON atteint'}, règle d'inactivité "
               f"{'respectée' if inactivity_safe else 'VIOLÉE'}.",
    ))

    # ── Logique de verdict ──────────────────────────────────────
    hard_fails = [c for c in criteria if c.is_hard_fail]
    all_passed = all(c.passed for c in criteria)
    if hard_fails:
        verdict_str = "NO-GO"
    elif all_passed:
        verdict_str = "GO"
    else:
        verdict_str = "CONDITIONAL"

    # ── Caveats : critères mous échoués + note holdout ──────────
    caveats = [c.detail for c in criteria if not c.passed and not c.hard_fail]
    caveats.append(holdout_note)

    # ── Next steps ──────────────────────────────────────────────
    if verdict_str == "GO":
        next_steps = [
            "Cross-validation NinjaTrader 8 Strategy Analyzer (écart P&L < 10% vs Python).",
            "Sim live >= 2 semaines sur compte démo NinjaTrader.",
            "Spec écrite à jour + plan de coupure défini avant tout passage Apex.",
        ]
    else:
        next_steps = [
            "Edge non validé par le gauntlet — ne PAS déployer.",
            "Revoir l'hypothèse à la lumière des critères échoués, ou pivoter.",
        ]

    return Verdict(
        hypothesis_name=hypothesis_name, verdict=verdict_str, criteria=criteria,
        caveats=caveats, next_steps=next_steps,
    )
```

- [ ] **Step 4: Lancer les tests — ils doivent PASSER**

Run: `python -m pytest 02_validation/gauntlet/tests/test_verdict.py -v`
Expected: PASS — 11 tests passés.

- [ ] **Step 5: Commit**

```bash
git add 02_validation/gauntlet/verdict.py 02_validation/gauntlet/tests/test_verdict.py
git commit -m "feat(gauntlet): verdict - agrégateur GO/NO-GO/CONDITIONAL + seuils checklist Apex"
```

---

### Task 3 : `run_gauntlet.py` (1/3) — Bloc 1 préparation + `make_run_variant`

**Files:**
- Create: `02_validation/gauntlet/run_gauntlet.py`
- Create: `02_validation/gauntlet/tests/test_run_gauntlet_prep.py`

**Pourquoi :** Bloc 1 du spec — la préparation. `prepare_data` charge l'instrument, resample au TF, ajoute les colonnes temporelles, filtre la session NY, applique `prepare_features`, découpe en Train/Valid/Holdout. `_prepare_splits` isole la partie sans I/O (features + splits) pour la tester sur synthétique. `make_run_variant` construit le **`run_variant` concret** : le callable que toute la batterie Plan 2 attend — il applique la `signal_fn` de l'hypothèse puis `backtest_pa` sur un `PaAccount` neuf. `prepare_data` lit un vrai fichier Databento — il n'est pas testé en pytest (couvert par le script de calibration Task 8) ; `_prepare_splits` et `make_run_variant`, eux, sont testables sur synthétique.

- [ ] **Step 1: Écrire les tests qui échouent**

Create `02_validation/gauntlet/tests/test_run_gauntlet_prep.py` :

```python
"""Tests Bloc 1 — préparation des données + make_run_variant."""
import numpy as np
import pandas as pd

from gauntlet.hypothesis import Hypothesis
from gauntlet.pa_account import PaAccount
from gauntlet.run_gauntlet import _prepare_splits, make_run_variant


def _session_df():
    """DataFrame de session synthétique couvrant Train/Valid/Holdout (2021-05 -> 2026-05)."""
    idx = pd.date_range("2021-05-13", "2026-05-12", freq="1D", tz="UTC")
    return pd.DataFrame({"close": np.arange(len(idx), dtype=float)}, index=idx)


def test_prepare_splits_borne_les_3_splits():
    df = _session_df()
    hyp = Hypothesis(name="h", description="", instrument="MNQ", timeframe="1D",
                     build_variant=lambda p: (lambda d: d, lambda *a: (False, 0.0, ""), {}),
                     param_grid=[{}])
    splits = _prepare_splits(df, hyp, embargo_bars=0)
    assert set(splits) == {"train", "valid", "holdout", "full_tv"}
    assert splits["train"].index.max() < pd.Timestamp("2024-05-13", tz="UTC")
    assert splits["valid"].index.min() >= pd.Timestamp("2024-05-13", tz="UTC")
    assert splits["holdout"].index.min() >= pd.Timestamp("2025-05-13", tz="UTC")
    # full_tv = Train+Valid contigu
    assert splits["full_tv"].index.min() >= pd.Timestamp("2021-05-13", tz="UTC")
    assert splits["full_tv"].index.max() < pd.Timestamp("2025-05-13", tz="UTC")


def test_prepare_splits_applique_prepare_features():
    df = _session_df()
    def _prep(d):
        out = d.copy()
        out["feat"] = out["close"] * 2.0
        return out
    hyp = Hypothesis(name="h", description="", instrument="MNQ", timeframe="1D",
                     build_variant=lambda p: (lambda d: d, lambda *a: (False, 0.0, ""), {}),
                     param_grid=[{}], prepare_features=_prep)
    splits = _prepare_splits(df, hyp, embargo_bars=0)
    assert "feat" in splits["train"].columns
    assert "feat" in splits["full_tv"].columns


def test_prepare_splits_sans_prepare_features_passe_le_df_tel_quel():
    df = _session_df()
    hyp = Hypothesis(name="h", description="", instrument="MNQ", timeframe="1D",
                     build_variant=lambda p: (lambda d: d, lambda *a: (False, 0.0, ""), {}),
                     param_grid=[{}], prepare_features=None)
    splits = _prepare_splits(df, hyp, embargo_bars=0)
    assert list(splits["train"].columns) == ["close"]


def test_make_run_variant_retourne_trades_et_account():
    # hypothèse triviale : LONG si close > mid, exit si close revient sous mid
    def _build(params):
        def signal_fn(df):
            out = df.copy()
            out["signal"] = 0
            out.loc[out["close"] > out["mid"], "signal"] = 1
            return out
        def exit_logic(d, i, j, direction, entry_price, std_i, mid_i,
                       or_high, or_low, or_range, sl_pts):
            if direction == 1 and d.at[j, "close"] <= d.at[j, "mid"]:
                return True, d.at[j, "close"], "TP"
            return False, 0.0, ""
        return signal_fn, exit_logic, {"bar_size_min": 5, "timeout_bars": params["timeout_bars"]}

    hyp = Hypothesis(name="h", description="", instrument="MNQ", timeframe="5min",
                     build_variant=_build, param_grid=[{"timeout_bars": 3}])
    run_variant = make_run_variant(hyp)

    idx = pd.date_range("2026-01-02 14:30", periods=6, freq="5min", tz="America/New_York")
    df = pd.DataFrame({
        "close": [101.0, 99.0, 102.0, 99.0, 101.0, 99.0],
        "high": [101.5, 99.5, 102.5, 99.5, 101.5, 99.5],
        "low": [100.5, 98.5, 101.5, 98.5, 100.5, 98.5],
        "std": 4.0, "mid": 100.0,
    }, index=idx)
    df["hour_ny"] = df.index.hour
    df["min_ny"] = df.index.minute
    df["date"] = df.index.date

    trades, account = run_variant(df, {"timeout_bars": 3})
    assert isinstance(account, PaAccount)
    assert "pnl_usd" in trades.columns
    assert len(trades) > 0
```

- [ ] **Step 2: Lancer les tests — ils doivent ÉCHOUER**

Run: `python -m pytest 02_validation/gauntlet/tests/test_run_gauntlet_prep.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'gauntlet.run_gauntlet'`

- [ ] **Step 3: Créer `run_gauntlet.py` avec le Bloc 1**

Create `02_validation/gauntlet/run_gauntlet.py` :

```python
"""run_gauntlet — l'orchestrateur du gauntlet : run_gauntlet(hypothesis) -> Verdict.

Enchaîne les 5 blocs du spec :
  Bloc 1 — Préparation     : load -> resample -> features -> splits Train/Valid/Holdout.
  Bloc 2 — Backtest PA     : le run_variant concret (signal_fn + backtest_pa sur PaAccount).
  Bloc 3 — Batterie stat   : walk-forward, CPCV, Deflated Sharpe, PBO, Monte Carlo.
  Bloc 4 — Robustesse      : stress test périodes rouges, cycle PA continu.
  Bloc 5 — Verdict         : agrégation GO/NO-GO/CONDITIONAL.

Ce fichier est construit en 3 tasks : préparation (T3), helpers grille (T4), run_gauntlet (T5).
"""
from __future__ import annotations

import pandas as pd

from src.config import TRAIN_START, VALID_END
from src.instruments import INSTRUMENTS
from src.data_loader import (load_continuous, resample_ohlcv,
                             add_temporal_columns, filter_session_ny)

from gauntlet.pa_account import PaAccount
from gauntlet.backtest import backtest_pa
from gauntlet.splits import split_train, split_valid, split_holdout


# ════════════════════════════════════════════════════════════════════
# Bloc 1 — Préparation
# ════════════════════════════════════════════════════════════════════

def _prepare_splits(df_sess: pd.DataFrame, hypothesis, embargo_bars: int) -> dict:
    """Applique prepare_features puis découpe en Train / Valid / Holdout + full_tv.

    Args:
        df_sess: DataFrame de session NY (sortie de filter_session_ny), indexé tz-aware UTC.
        hypothesis: l'Hypothesis (pour prepare_features).
        embargo_bars: barres de purge jetées en fin de Train et de Valid.

    Returns:
        dict(train, valid, holdout, full_tv). full_tv = Train+Valid contigu — la batterie
        tourne dessus ; le holdout n'est ouvert qu'une fois en toute fin de run_gauntlet.

    Note : prepare_features est appliqué AVANT le découpage. Les features (rolling mean/std,
    Hurst) sont backward-looking — les calculer sur le df complet puis slicer ne fuit rien,
    et évite de recomputer le Hurst (coûteux) pour chaque tranche.
    """
    df_feat = hypothesis.prepare_features(df_sess) if hypothesis.prepare_features else df_sess
    train = split_train(df_feat, embargo_bars=embargo_bars)
    valid = split_valid(df_feat, embargo_bars=embargo_bars)
    holdout = split_holdout(df_feat)
    full_tv = df_feat.loc[
        (df_feat.index >= TRAIN_START) & (df_feat.index < VALID_END)
    ].copy()
    return dict(train=train, valid=valid, holdout=holdout, full_tv=full_tv)


def prepare_data(hypothesis, embargo_bars: int) -> dict:
    """Bloc 1 complet : charge l'instrument, resample, colonnes temporelles, session NY,
    features, splits.

    I/O : lit le CSV Databento de INSTRUMENTS[hypothesis.instrument]['path']. Non testé
    en pytest (dépend d'un fichier local) — couvert par le script de calibration.
    """
    specs = INSTRUMENTS[hypothesis.instrument]
    df_m1 = load_continuous(specs["path"], specs["root"])
    df_tf = resample_ohlcv(df_m1, hypothesis.timeframe)
    df_tf = add_temporal_columns(df_tf)
    df_sess = filter_session_ny(df_tf)
    return _prepare_splits(df_sess, hypothesis, embargo_bars)


# ════════════════════════════════════════════════════════════════════
# Bloc 2 — Le run_variant concret
# ════════════════════════════════════════════════════════════════════

def make_run_variant(hypothesis):
    """Construit le run_variant concret de l'hypothèse.

    run_variant(df, params) -> (trades_df, account) : applique la signal_fn de l'hypothèse
    puis backtest_pa sur un PaAccount NEUF. C'est le callable injecté dans walk_forward /
    stress_test / pa_cycle (cf. plan Plan 2 §"Le contrat run_variant").
    """
    specs = INSTRUMENTS[hypothesis.instrument]

    def run_variant(df, params):
        signal_fn, exit_logic, bt_kwargs = hypothesis.build_variant(params)
        df_sig = signal_fn(df)
        account = PaAccount()
        trades = backtest_pa(df_sig, exit_logic, specs, account, **bt_kwargs)
        return trades, account

    return run_variant
```

- [ ] **Step 4: Lancer les tests — ils doivent PASSER**

Run: `python -m pytest 02_validation/gauntlet/tests/test_run_gauntlet_prep.py -v`
Expected: PASS — 4 tests passés.

- [ ] **Step 5: Commit**

```bash
git add 02_validation/gauntlet/run_gauntlet.py 02_validation/gauntlet/tests/test_run_gauntlet_prep.py
git commit -m "feat(gauntlet): run_gauntlet 1/3 - Bloc 1 préparation + make_run_variant"
```

---

### Task 4 : `run_gauntlet.py` (2/3) — helpers de grille

**Files:**
- Modify: `02_validation/gauntlet/run_gauntlet.py` (append)
- Create: `02_validation/gauntlet/tests/test_run_gauntlet_grid.py`

**Pourquoi :** quatre helpers que l'orchestrateur enchaîne. `_extract_embargo` : la purge entre splits = la durée max d'un trade (le plus grand `timeout_bars` de la grille) — un trade ne peut pas déborder plus loin que ça. `_run_grid_on` : lance chaque variant de la grille sur un df, renvoie trades + account + métriques par variant — réutilisé sur Train (sélection) et sur full_tv (run plein + PBO). `_select_best_on_train` : choisit le variant au plus haut Sharpe sur Train (le spec : "meilleur variant sélectionné sur Train") et renvoie aussi les Sharpes (pour le `sr_variance` du Deflated Sharpe). `_compute_pbo` : assemble la matrice (jours × variants) des PnL journaliers et calcule le PBO — renvoie `None` si grille < 2 variants (PBO indéfini) ou historique trop court.

- [ ] **Step 1: Écrire les tests qui échouent**

Create `02_validation/gauntlet/tests/test_run_gauntlet_grid.py` :

```python
"""Tests des helpers de grille de run_gauntlet."""
import numpy as np
import pandas as pd

from gauntlet.hypothesis import Hypothesis
from gauntlet.run_gauntlet import (
    _extract_embargo, _run_grid_on, _select_best_on_train, _compute_pbo,
)


def _hyp(grid, timeouts=None):
    """Hypothèse factice. timeouts : timeout_bars par variant (défaut 10)."""
    timeouts = timeouts or [10] * len(grid)

    def build_variant(params):
        idx = grid.index(params)
        return (lambda d: d, lambda *a: (False, 0.0, ""),
                {"bar_size_min": 5, "timeout_bars": timeouts[idx]})

    return Hypothesis(name="h", description="", instrument="MNQ", timeframe="5min",
                      build_variant=build_variant, param_grid=grid)


def _fake_run_variant_factory():
    """run_variant factice : PnL dépend du param 'edge' (True -> positif, False -> négatif).
    Génère des trades sur 12 dates distinctes pour nourrir le PBO."""
    def run_variant(df, params):
        base = 100.0 if params["edge"] else -100.0
        trades = pd.DataFrame({
            "pnl_usd": [base + i for i in range(12)],
            "date": pd.date_range("2022-01-03", periods=12, freq="D"),
        })
        return trades, None
    return run_variant


def test_extract_embargo_prend_le_max_timeout():
    grid = [{"edge": True}, {"edge": False}]
    hyp = _hyp(grid, timeouts=[12, 120])
    assert _extract_embargo(hyp) == 120


def test_run_grid_on_aligne_sur_la_grille():
    grid = [{"edge": True}, {"edge": False}]
    hyp = _hyp(grid)
    rv = _fake_run_variant_factory()
    results = _run_grid_on(pd.DataFrame({"close": [1.0]}), hyp, rv)
    assert len(results) == 2
    assert results[0]["params"] == {"edge": True}
    assert results[1]["params"] == {"edge": False}
    assert results[0]["metrics"]["trades"] == 12
    assert "account" in results[0] and "trades" in results[0]


def test_select_best_on_train_prend_le_meilleur_sharpe():
    grid = [{"edge": False}, {"edge": True}]
    hyp = _hyp(grid)
    rv = _fake_run_variant_factory()
    results = _run_grid_on(pd.DataFrame({"close": [1.0]}), hyp, rv)
    best_params, best_idx, sharpes = _select_best_on_train(results)
    assert best_params == {"edge": True}        # Sharpe positif
    assert best_idx == 1
    assert len(sharpes) == 2


def test_compute_pbo_none_si_grille_un_variant():
    grid = [{"edge": True}]
    hyp = _hyp(grid)
    rv = _fake_run_variant_factory()
    results = _run_grid_on(pd.DataFrame({"close": [1.0]}), hyp, rv)
    assert _compute_pbo(results, n_splits=4) is None


def test_compute_pbo_renvoie_un_float_dans_unit_interval():
    grid = [{"edge": True}, {"edge": False}]
    hyp = _hyp(grid)
    rv = _fake_run_variant_factory()
    results = _run_grid_on(pd.DataFrame({"close": [1.0]}), hyp, rv)
    pbo = _compute_pbo(results, n_splits=4)
    assert pbo is not None
    assert 0.0 <= pbo <= 1.0


def test_compute_pbo_none_si_matrice_trop_courte():
    # n_splits plus grand que le nombre de jours -> None
    grid = [{"edge": True}, {"edge": False}]
    hyp = _hyp(grid)
    rv = _fake_run_variant_factory()        # 12 jours
    results = _run_grid_on(pd.DataFrame({"close": [1.0]}), hyp, rv)
    assert _compute_pbo(results, n_splits=50) is None
```

- [ ] **Step 2: Lancer les tests — ils doivent ÉCHOUER**

Run: `python -m pytest 02_validation/gauntlet/tests/test_run_gauntlet_grid.py -v`
Expected: FAIL — `ImportError: cannot import name '_extract_embargo' from 'gauntlet.run_gauntlet'`

- [ ] **Step 3: Ajouter les helpers à `run_gauntlet.py`**

Append to `02_validation/gauntlet/run_gauntlet.py` (after `make_run_variant`). First, add to the imports block at the top of the file — change the import section so it also imports numpy and `compute_trade_metrics` and `probability_backtest_overfitting`. The top imports become :

```python
from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import TRAIN_START, VALID_END
from src.instruments import INSTRUMENTS
from src.data_loader import (load_continuous, resample_ohlcv,
                             add_temporal_columns, filter_session_ny)
from src.backtest import compute_trade_metrics

from gauntlet.pa_account import PaAccount
from gauntlet.backtest import backtest_pa
from gauntlet.splits import split_train, split_valid, split_holdout
from gauntlet.deflated_sharpe import probability_backtest_overfitting
```

Then append at the end of the file :

```python
# ════════════════════════════════════════════════════════════════════
# Helpers de grille
# ════════════════════════════════════════════════════════════════════

def _extract_embargo(hypothesis) -> int:
    """Embargo (barres) = le plus grand timeout_bars de la grille.

    Un trade dure au plus timeout_bars barres ; on purge donc cette durée entre les splits
    pour qu'aucun trade ouvert en fin de fenêtre ne déborde sur la suivante.
    """
    timeouts = []
    for params in hypothesis.param_grid:
        _, _, bt_kwargs = hypothesis.build_variant(params)
        timeouts.append(int(bt_kwargs.get("timeout_bars", 0)))
    return max(timeouts) if timeouts else 0


def _run_grid_on(df: pd.DataFrame, hypothesis, run_variant) -> list:
    """Lance chaque variant de la grille sur df.

    Returns:
        list alignée sur param_grid : [{params, trades, account, metrics}, ...].
    """
    results = []
    for params in hypothesis.param_grid:
        trades, account = run_variant(df, params)
        results.append({
            "params": params, "trades": trades, "account": account,
            "metrics": compute_trade_metrics(trades),
        })
    return results


def _select_best_on_train(train_results: list) -> tuple:
    """Sélectionne le meilleur variant par Sharpe sur Train.

    Args:
        train_results: sortie de _run_grid_on sur le split Train.

    Returns:
        (best_params, best_index, train_sharpes). train_sharpes alimente le sr_variance
        du Deflated Sharpe. Un variant sans trade marque -inf (jamais sélectionné sauf si
        tous vides — auquel cas le premier gagne).
    """
    sharpes = [r["metrics"]["sharpe"] if r["metrics"]["trades"] > 0 else float("-inf")
               for r in train_results]
    best_index = int(np.argmax(sharpes))
    return train_results[best_index]["params"], best_index, sharpes


def _compute_pbo(fulltv_results: list, n_splits: int = 10):
    """PBO sur la matrice (jours × variants) des PnL journaliers des variants sur full_tv.

    Args:
        fulltv_results: sortie de _run_grid_on sur full_tv.
        n_splits: nombre de blocs temporels du PBO combinatoire.

    Returns:
        float PBO, ou None si < 2 variants (PBO indéfini) ou matrice plus courte que n_splits.
    """
    if len(fulltv_results) < 2:
        return None
    daily_panel = {}
    for i, r in enumerate(fulltv_results):
        tr = r["trades"]
        if len(tr) == 0:
            daily_panel[i] = pd.Series(dtype=float)
        else:
            daily_panel[i] = tr.groupby("date")["pnl_usd"].sum()
    pnl_matrix_df = pd.DataFrame(daily_panel).fillna(0.0)
    if len(pnl_matrix_df) < n_splits:
        return None
    return float(probability_backtest_overfitting(pnl_matrix_df.to_numpy(), n_splits=n_splits))
```

- [ ] **Step 4: Lancer les tests — ils doivent PASSER**

Run: `python -m pytest 02_validation/gauntlet/tests/test_run_gauntlet_grid.py 02_validation/gauntlet/tests/test_run_gauntlet_prep.py -v`
Expected: PASS — 6 + 4 = 10 tests passés (les tests prep ne régressent pas avec les imports ajoutés).

- [ ] **Step 5: Commit**

```bash
git add 02_validation/gauntlet/run_gauntlet.py 02_validation/gauntlet/tests/test_run_gauntlet_grid.py
git commit -m "feat(gauntlet): run_gauntlet 2/3 - helpers de grille (embargo, grid run, sélection, PBO)"
```

---

### Task 5 : `run_gauntlet.py` (3/3) — l'orchestrateur `run_gauntlet`

**Files:**
- Modify: `02_validation/gauntlet/run_gauntlet.py` (append)
- Create: `02_validation/gauntlet/tests/test_run_gauntlet_e2e.py`

**Pourquoi :** la fonction qui assemble tout. Elle enchaîne : sélection du meilleur variant sur Train → walk-forward sur Train+Valid → run plein du meilleur variant (qui nourrit Monte Carlo, CPCV, Deflated Sharpe, max DD, cycle PA) → PBO sur la grille → stress test → ouverture unique du holdout → verdict. L'argument `splits` est un **point d'injection** : si fourni, on saute `prepare_data` (donc tout le I/O fichier) — c'est ce qui rend `run_gauntlet` testable de bout en bout sur des données synthétiques. Le `sr_variance` du Deflated Sharpe est calculé honnêtement à partir de la variance des Sharpes de la grille sur Train (à défaut, fallback documenté). Le test de bout en bout reprend le fixture oversold-MR éprouvé du Plan 2.

- [ ] **Step 1: Écrire le test de bout en bout qui échoue**

Create `02_validation/gauntlet/tests/test_run_gauntlet_e2e.py` :

```python
"""Intégration : run_gauntlet de bout en bout sur une hypothèse synthétique injectée."""
import numpy as np
import pandas as pd

from gauntlet.hypothesis import Hypothesis
from gauntlet.verdict import Verdict
from gauntlet.run_gauntlet import run_gauntlet


def _feature_complete_df(n_days: int) -> pd.DataFrame:
    """n_days jours ouvrés, 12 barres 5min/jour. Barres paires sous mid (signal LONG MR
    oversold), impaires au-dessus (exit). Amplitude jour-à-jour variable -> PnL journalier
    non dégénéré. Fixture éprouvé en Plan 2 (test_integration_plan2)."""
    rng = np.random.default_rng(2026)
    days = pd.bdate_range("2022-01-03", periods=n_days)
    rows = []
    for d in days:
        amp = 1.0 + abs(rng.normal(0.0, 0.5))
        base = pd.Timestamp(d.year, d.month, d.day, 14, 30, tz="America/New_York")
        for b in range(12):
            ts = base + pd.Timedelta(minutes=5 * b)
            close = 100.0 - amp if b % 2 == 0 else 100.0 + amp
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


def _build_variant(params):
    def signal_fn(df):
        out = df.copy()
        out["signal"] = 0
        out.loc[out["close"] < out["mid"], "signal"] = 1
        return out

    def exit_logic(d, i, j, direction, entry_price, std_i, mid_i,
                   or_high, or_low, or_range, sl_pts):
        if direction == 1 and d.at[j, "close"] >= d.at[j, "mid"]:
            return True, d.at[j, "close"], "TP_back_to_mid"
        return False, 0.0, ""

    return signal_fn, exit_logic, {"bar_size_min": 5, "timeout_bars": params["timeout_bars"]}


def test_run_gauntlet_e2e_synthetique():
    df = _feature_complete_df(n_days=40)
    # Splits manuels (l'injection `splits` court-circuite prepare_data et ses dates réelles).
    n = len(df)
    splits = {
        "train": df.iloc[: int(n * 0.45)],
        "valid": df.iloc[int(n * 0.45): int(n * 0.65)],
        "holdout": df.iloc[int(n * 0.65): int(n * 0.85)],
        "full_tv": df.iloc[: int(n * 0.65)],
    }
    hyp = Hypothesis(
        name="synth_mr", description="MR oversold synthétique — test e2e",
        instrument="MNQ", timeframe="5min", build_variant=_build_variant,
        param_grid=[{"timeout_bars": 2}, {"timeout_bars": 4}],
    )
    verdict = run_gauntlet(hyp, splits=splits, out_dir=None, mc_iter=300, seed=0,
                           n_windows=3, cpcv_n_groups=5, pbo_n_splits=4)

    assert isinstance(verdict, Verdict)
    assert verdict.verdict in {"GO", "NO-GO", "CONDITIONAL"}
    assert verdict.hypothesis_name == "synth_mr"
    assert len(verdict.criteria) == 8                       # les 8 critères du spec
    assert any("Holdout" in c for c in verdict.caveats)     # holdout reporté
    assert len(verdict.next_steps) > 0
```

- [ ] **Step 2: Lancer le test — il doit ÉCHOUER**

Run: `python -m pytest 02_validation/gauntlet/tests/test_run_gauntlet_e2e.py -v`
Expected: FAIL — `ImportError: cannot import name 'run_gauntlet' from 'gauntlet.run_gauntlet'`

- [ ] **Step 3: Ajouter `run_gauntlet` à `run_gauntlet.py`**

First, extend the imports block at the top of `02_validation/gauntlet/run_gauntlet.py` — add these lines to the gauntlet imports group (after `from gauntlet.deflated_sharpe import probability_backtest_overfitting`) :

```python
from gauntlet.walk_forward import purged_walk_forward, walk_forward_summary
from gauntlet.monte_carlo import permutation_test_sharpe, dd_distribution_shuffle
from gauntlet.cpcv import sharpe_distribution_cpcv
from gauntlet.deflated_sharpe import deflated_sharpe_ratio
from gauntlet.stress_test import run_stress_test, stress_test_passed
from gauntlet.pa_cycle import analyze_pa_cycle
from gauntlet.verdict import build_verdict, DSR_GO_THRESHOLD
```

Then append at the end of the file :

```python
# ════════════════════════════════════════════════════════════════════
# L'orchestrateur
# ════════════════════════════════════════════════════════════════════

# Fallback du sr_variance du Deflated Sharpe quand la grille a < 2 variants exploitables.
# 0.09 = 0.3^2, convention héritée de run_final_validation.py.
_SR_VARIANCE_FALLBACK = 0.09


def run_gauntlet(hypothesis, splits: dict = None, out_dir=None,
                 mc_iter: int = 10_000, seed: int = 0,
                 n_windows: int = 4, cpcv_n_groups: int = 10,
                 pbo_n_splits: int = 10):
    """Exécute le gauntlet complet sur une hypothèse -> Verdict.

    Args:
        hypothesis: l'Hypothesis à juger.
        splits: dict(train, valid, holdout, full_tv) DÉJÀ préparé. None -> prepare_data
                charge les vraies données (I/O fichier). L'injection sert aux tests.
        out_dir: dossier où écrire le rapport (None -> pas de rapport écrit).
        mc_iter: itérations Monte Carlo.
        seed: graine RNG (Monte Carlo).
        n_windows: fenêtres du walk-forward.
        cpcv_n_groups: groupes du CPCV.
        pbo_n_splits: blocs temporels du PBO.

    Returns:
        Verdict.
    """
    run_variant = make_run_variant(hypothesis)
    embargo = _extract_embargo(hypothesis)
    if splits is None:
        splits = prepare_data(hypothesis, embargo_bars=embargo)
    train, full_tv, holdout = splits["train"], splits["full_tv"], splits["holdout"]

    # ── Sélection du meilleur variant sur Train ─────────────────
    train_results = _run_grid_on(train, hypothesis, run_variant)
    best_params, _best_idx, train_sharpes = _select_best_on_train(train_results)

    # ── Bloc 3a — Walk-forward purgé sur Train+Valid ────────────
    wf = purged_walk_forward(full_tv, hypothesis.param_grid, run_variant,
                             n_windows=n_windows, embargo_bars=embargo)
    wf_sum = walk_forward_summary(wf)

    # ── Run plein Train+Valid + grille complète sur full_tv ─────
    fulltv_results = _run_grid_on(full_tv, hypothesis, run_variant)
    best_on_fulltv = next(r for r in fulltv_results if r["params"] == best_params)
    full_trades = best_on_fulltv["trades"]
    full_account = best_on_fulltv["account"]
    full_metrics = best_on_fulltv["metrics"]

    # ── Bloc 3b — Monte Carlo + CPCV + Deflated Sharpe + PBO ────
    pnl = full_trades["pnl_usd"].to_numpy() if len(full_trades) else np.array([])
    mc = permutation_test_sharpe(pnl, n_iter=mc_iter, seed=seed)
    dd = dd_distribution_shuffle(pnl, n_iter=mc_iter, seed=seed)
    cpcv = (sharpe_distribution_cpcv(full_trades, n_groups=cpcv_n_groups, k_test=2,
                                     date_col="date", pnl_col="pnl_usd")
            if len(full_trades) else np.array([]))
    daily = (full_trades.groupby("date")["pnl_usd"].sum().to_numpy()
             if len(full_trades) else np.array([]))
    finite_sharpes = [s for s in train_sharpes if np.isfinite(s)]
    sr_variance = (max(float(np.var(finite_sharpes, ddof=1)), 1e-4)
                   if len(finite_sharpes) >= 2 else _SR_VARIANCE_FALLBACK)
    dsr = (float(deflated_sharpe_ratio(daily, n_trials=hypothesis.n_trials,
                                       sr_variance=sr_variance))
           if len(daily) >= 5 else 0.0)
    pbo = _compute_pbo(fulltv_results, n_splits=pbo_n_splits)

    # ── Bloc 4 — Stress test + cycle PA ─────────────────────────
    stress = run_stress_test(full_tv, best_params, run_variant)
    cycle = analyze_pa_cycle(full_account)
    cycle["n_trades"] = len(full_trades)

    # ── Holdout — ouvert UNE seule fois, confiance dégradée ─────
    holdout_trades, _holdout_account = run_variant(holdout, best_params)
    holdout_metrics = compute_trade_metrics(holdout_trades)
    holdout_note = (
        f"Holdout 2025-05->2026-05 (confiance DÉGRADÉE — partiellement contaminé par le "
        f"grid-search dual-config) : {holdout_metrics['trades']} trades, "
        f"PF {holdout_metrics['pf']:.2f}, Sharpe {holdout_metrics['sharpe']:.2f}, "
        f"PnL ${holdout_metrics['pnl']:.0f}. Confirmation indicative, pas un critère GO."
    )

    # ── Bloc 5 — Verdict ────────────────────────────────────────
    verdict = build_verdict(
        hypothesis_name=hypothesis.name,
        account_survived=(full_account.status != "dead_eod"),
        wf_summary=wf_sum, mc=mc, dsr=dsr, pbo=pbo,
        full_max_dd=full_metrics["max_dd"],
        stress_passed=stress_test_passed(stress),
        reached_lock=cycle["reached_lock"],
        inactivity_safe=cycle["inactivity_safe"],
        holdout_note=holdout_note, dsr_threshold=DSR_GO_THRESHOLD,
    )

    # ── Rapport (import paresseux : report.py n'existe qu'à partir de Task 6) ──
    if out_dir is not None:
        from gauntlet.report import write_gauntlet_report
        write_gauntlet_report(verdict, dict(
            hypothesis=hypothesis, wf=wf, wf_summary=wf_sum, mc=mc, dd=dd,
            cpcv=cpcv, dsr=dsr, sr_variance=sr_variance, pbo=pbo,
            full_metrics=full_metrics, full_account=full_account,
            stress=stress, cycle=cycle, holdout_metrics=holdout_metrics,
            fulltv_results=fulltv_results, best_params=best_params,
        ), out_dir)

    return verdict
```

- [ ] **Step 4: Lancer le test — il doit PASSER**

Run: `python -m pytest 02_validation/gauntlet/tests/test_run_gauntlet_e2e.py -v`
Expected: PASS — 1 test passé. (Si un module de la batterie râle sur une forme de données, c'est un vrai bug de câblage — investiguer, ne pas affaiblir le test.)

- [ ] **Step 5: Lancer toute la suite gauntlet**

Run: `python -m pytest 02_validation/gauntlet/tests/ -q`
Expected: PASS — toute la suite gauntlet verte.

- [ ] **Step 6: Commit**

```bash
git add 02_validation/gauntlet/run_gauntlet.py 02_validation/gauntlet/tests/test_run_gauntlet_e2e.py
git commit -m "feat(gauntlet): run_gauntlet 3/3 - l'orchestrateur des 5 blocs"
```

---

### Task 6 : `report.py` — rapport markdown + CSVs

**Files:**
- Create: `02_validation/gauntlet/report.py`
- Create: `02_validation/gauntlet/tests/test_report.py`

**Pourquoi :** un verdict qui ne s'écrit nulle part ne sert à rien. `write_gauntlet_report` matérialise les outputs du spec dans `02_validation/outputs/gauntlet/<nom>/` : `gauntlet_report.md` (le verdict + stats par bloc, lisible par BB), `ranking.csv` (métriques par variant), `pa_account_trace.csv` (clôtures journalières + tier + seuil DD reconstruit), `walk_forward.csv`, `cpcv_distribution.csv`, `run_log.txt`. Le seuil DD EOD n'est pas stocké jour par jour par `PaAccount` — on le **reconstruit** depuis les clôtures (`seuil = min(plus_haute_clôture − 2000, 50100)`), c'est déterministe.

- [ ] **Step 1: Écrire les tests qui échouent**

Create `02_validation/gauntlet/tests/test_report.py` :

```python
"""Tests de l'écriture du rapport gauntlet."""
import numpy as np
import pandas as pd

from gauntlet.pa_account import PaAccount
from gauntlet.hypothesis import Hypothesis
from gauntlet.verdict import build_verdict
from gauntlet.report import write_gauntlet_report, _reconstruct_threshold_trace


def _verdict_and_outputs():
    hyp = Hypothesis(name="hyp_rep", description="hypothèse de test rapport",
                     instrument="MNQ", timeframe="5min",
                     build_variant=lambda p: (lambda d: d, lambda *a: (False, 0.0, ""), {}),
                     param_grid=[{"x": 1}, {"x": 2}])
    verdict = build_verdict(
        hypothesis_name="hyp_rep", account_survived=True,
        wf_summary={"n_windows": 4, "pct_oos_profitable": 0.80},
        mc={"p_value": 0.01}, dsr=0.99, pbo=0.2, full_max_dd=-500.0,
        stress_passed=True, reached_lock=True, inactivity_safe=True,
        holdout_note="Holdout : PF 1.2 (confiance dégradée).",
    )
    acc = PaAccount()
    acc.daily_history = [("2022-01-03", 50_300.0, 1), ("2022-01-04", 50_100.0, 1),
                         ("2022-01-05", 52_500.0, 3)]
    outputs = dict(
        hypothesis=hyp,
        wf=pd.DataFrame({"window": [0, 1], "oos_sharpe": [1.2, 0.9],
                         "oos_pnl": [500.0, 300.0], "oos_profitable": [True, True]}),
        wf_summary={"n_windows": 4, "pct_oos_profitable": 0.80, "oos_sharpe_mean": 1.0},
        mc={"observed_sharpe": 2.1, "p_value": 0.01, "n_iter": 500},
        dd={"observed_max_dd": -500.0, "dd_p95": -800.0, "dd_worst": -1200.0},
        cpcv=np.array([0.5, 1.1, 0.8, 1.3]),
        dsr=0.99, sr_variance=0.05, pbo=0.2,
        full_metrics={"trades": 120, "pf": 1.6, "sharpe": 1.4, "max_dd": -500.0,
                      "wr": 0.45, "pnl": 3200.0, "avg_trade": 26.7},
        full_account=acc,
        stress=pd.DataFrame({"period": ["bear_2022"], "n_trades": [20], "pnl": [150.0],
                             "trade_seq_max_dd": [-300.0], "survived": [True]}),
        cycle={"survived": True, "reached_lock": True, "trading_days_to_lock": 3,
               "final_balance": 52_500.0, "n_trading_days": 3, "inactivity_safe": True,
               "inactivity_first_violation": None, "inactivity_unchecked_tail_days": 0,
               "n_trades": 120},
        holdout_metrics={"trades": 30, "pf": 1.2, "sharpe": 0.6, "max_dd": -400.0,
                         "wr": 0.4, "pnl": 600.0, "avg_trade": 20.0},
        fulltv_results=[
            {"params": {"x": 1}, "trades": pd.DataFrame(), "account": PaAccount(),
             "metrics": {"trades": 120, "pf": 1.6, "sharpe": 1.4, "max_dd": -500.0,
                         "wr": 0.45, "pnl": 3200.0, "avg_trade": 26.7}},
            {"params": {"x": 2}, "trades": pd.DataFrame(), "account": PaAccount(),
             "metrics": {"trades": 90, "pf": 1.1, "sharpe": 0.4, "max_dd": -700.0,
                         "wr": 0.4, "pnl": 400.0, "avg_trade": 4.4}},
        ],
        best_params={"x": 1},
    )
    return verdict, outputs


def test_reconstruct_threshold_trace():
    # clôtures 50_300 / 50_100 / 52_500
    # seuils : min(50_300-2000, 50_100)=48_300 ; min(50_300-2000, ...)=48_300 ; min(52_500-2000,50_100)=50_100
    hist = [("2022-01-03", 50_300.0, 1), ("2022-01-04", 50_100.0, 1),
            ("2022-01-05", 52_500.0, 3)]
    trace = _reconstruct_threshold_trace(hist)
    assert list(trace["eod_threshold"]) == [48_300.0, 48_300.0, 50_100.0]


def test_write_gauntlet_report_ecrit_les_6_fichiers(tmp_path):
    verdict, outputs = _verdict_and_outputs()
    out_dir = tmp_path / "hyp_rep"
    write_gauntlet_report(verdict, outputs, str(out_dir))
    for fname in ["gauntlet_report.md", "ranking.csv", "pa_account_trace.csv",
                  "walk_forward.csv", "cpcv_distribution.csv", "run_log.txt"]:
        assert (out_dir / fname).exists(), f"{fname} manquant"


def test_report_md_contient_le_verdict(tmp_path):
    verdict, outputs = _verdict_and_outputs()
    out_dir = tmp_path / "hyp_rep"
    write_gauntlet_report(verdict, outputs, str(out_dir))
    md = (out_dir / "gauntlet_report.md").read_text(encoding="utf-8")
    assert "GO" in md
    assert "hyp_rep" in md
    assert "account_alive" in md            # la table des critères
    assert "Holdout" in md                  # le caveat holdout


def test_ranking_csv_une_ligne_par_variant(tmp_path):
    verdict, outputs = _verdict_and_outputs()
    out_dir = tmp_path / "hyp_rep"
    write_gauntlet_report(verdict, outputs, str(out_dir))
    ranking = pd.read_csv(out_dir / "ranking.csv")
    assert len(ranking) == 2                # 2 variants dans la grille
    assert "is_best" in ranking.columns
    assert int(ranking["is_best"].sum()) == 1


def test_run_gauntlet_ecrit_le_rapport_avec_out_dir(tmp_path):
    # run_gauntlet avec out_dir non-None doit produire le dossier de rapport
    import numpy as np
    from gauntlet.run_gauntlet import run_gauntlet

    rng = np.random.default_rng(7)
    days = pd.bdate_range("2022-01-03", periods=40)
    rows = []
    for d in days:
        amp = 1.0 + abs(rng.normal(0.0, 0.5))
        base = pd.Timestamp(d.year, d.month, d.day, 14, 30, tz="America/New_York")
        for b in range(12):
            ts = base + pd.Timedelta(minutes=5 * b)
            rows.append((ts, 100.0 - amp if b % 2 == 0 else 100.0 + amp))
    idx = pd.DatetimeIndex([r[0] for r in rows])
    closes = np.array([r[1] for r in rows])
    df = pd.DataFrame({"close": closes, "high": closes + 0.5, "low": closes - 0.5,
                       "std": 4.0, "mid": 100.0}, index=idx)
    df["hour_ny"] = df.index.hour
    df["min_ny"] = df.index.minute
    df["date"] = df.index.date
    n = len(df)
    splits = {"train": df.iloc[:int(n * 0.45)], "valid": df.iloc[int(n * 0.45):int(n * 0.65)],
              "holdout": df.iloc[int(n * 0.65):int(n * 0.85)], "full_tv": df.iloc[:int(n * 0.65)]}

    def _build(params):
        def signal_fn(d):
            out = d.copy()
            out["signal"] = 0
            out.loc[out["close"] < out["mid"], "signal"] = 1
            return out
        def exit_logic(d, i, j, direction, ep, std_i, mid_i, oh, ol, orr, slp):
            if direction == 1 and d.at[j, "close"] >= d.at[j, "mid"]:
                return True, d.at[j, "close"], "TP"
            return False, 0.0, ""
        return signal_fn, exit_logic, {"bar_size_min": 5, "timeout_bars": params["timeout_bars"]}

    hyp = Hypothesis(name="hyp_outdir", description="", instrument="MNQ", timeframe="5min",
                     build_variant=_build, param_grid=[{"timeout_bars": 2}])
    out_dir = tmp_path / "hyp_outdir"
    run_gauntlet(hyp, splits=splits, out_dir=str(out_dir), mc_iter=200, seed=0,
                 n_windows=3, cpcv_n_groups=5, pbo_n_splits=4)
    assert (out_dir / "gauntlet_report.md").exists()
```

- [ ] **Step 2: Lancer les tests — ils doivent ÉCHOUER**

Run: `python -m pytest 02_validation/gauntlet/tests/test_report.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'gauntlet.report'`

- [ ] **Step 3: Implémenter `report.py`**

Create `02_validation/gauntlet/report.py` :

```python
"""Écriture du rapport gauntlet : markdown lisible + CSVs traçables.

Outputs dans <out_dir>/ :
  gauntlet_report.md    — le verdict + stats par bloc, pour BB.
  ranking.csv           — métriques par variant de la grille.
  pa_account_trace.csv  — clôtures journalières + tier + seuil DD EOD reconstruit.
  walk_forward.csv      — la table walk-forward brute.
  cpcv_distribution.csv — la distribution des Sharpe OOS du CPCV.
  run_log.txt           — résumé une-ligne du run.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from gauntlet.pa_rules import ACCOUNT_SIZE, EOD_DD, EOD_THRESHOLD_LOCK


def _reconstruct_threshold_trace(daily_history: list) -> pd.DataFrame:
    """Reconstruit la trajectoire du seuil DD EOD depuis les clôtures journalières.

    seuil[i] = min(plus_haute_clôture_jusqu'à_i - EOD_DD, EOD_THRESHOLD_LOCK). Le PaAccount
    ne stocke pas le seuil jour par jour, mais il est déterministe à partir des clôtures.

    Args:
        daily_history: [(date, eod_close_balance, tier), ...] de PaAccount.

    Returns:
        DataFrame [date, eod_close_balance, tier, eod_threshold].
    """
    rows = []
    running_max = ACCOUNT_SIZE
    for date, eod_close, tier in daily_history:
        running_max = max(running_max, eod_close)
        threshold = min(running_max - EOD_DD, EOD_THRESHOLD_LOCK)
        rows.append({"date": date, "eod_close_balance": eod_close, "tier": tier,
                     "eod_threshold": threshold})
    return pd.DataFrame(rows)


def _format_report_md(verdict, outputs: dict) -> str:
    """Construit le corps markdown du rapport."""
    hyp = outputs["hypothesis"]
    fm = outputs["full_metrics"]
    mc = outputs["mc"]
    dd = outputs["dd"]
    cycle = outputs["cycle"]
    hm = outputs["holdout_metrics"]
    cpcv = outputs["cpcv"]

    lines = []
    lines.append(f"# Gauntlet — Verdict : {verdict.verdict}")
    lines.append("")
    lines.append(f"**Hypothèse** : `{hyp.name}` — {hyp.description}  ")
    lines.append(f"**Instrument / TF** : {hyp.instrument} / {hyp.timeframe}  ")
    lines.append(f"**Variants testés (n_trials)** : {hyp.n_trials}  ")
    lines.append(f"**Meilleur variant (sélectionné sur Train)** : `{outputs['best_params']}`")
    lines.append("")

    # ── Table des critères ──────────────────────────────────────
    lines.append("## Critères")
    lines.append("")
    lines.append("| Critère | Valeur | Seuil | Passé | Éliminatoire |")
    lines.append("|---|---|---|:---:|:---:|")
    for c in verdict.criteria:
        val = f"{c.value:.4f}" if isinstance(c.value, float) else str(c.value)
        ok = "✅" if c.passed else "❌"
        hard = "🔴" if c.hard_fail else ""
        lines.append(f"| {c.name} | {val} | {c.threshold} | {ok} | {hard} |")
    lines.append("")
    for c in verdict.criteria:
        lines.append(f"- **{c.name}** : {c.detail}")
    lines.append("")

    # ── Stats par bloc ──────────────────────────────────────────
    lines.append("## Détail par bloc")
    lines.append("")
    lines.append(f"- **Run plein Train+Valid** : {fm['trades']} trades, PF {fm['pf']:.2f}, "
                 f"Sharpe {fm['sharpe']:.2f}, max DD ${fm['max_dd']:.0f}, "
                 f"WR {fm['wr']:.1%}, PnL ${fm['pnl']:.0f}.")
    lines.append(f"- **Walk-forward** : {outputs['wf_summary'].get('n_windows', 0)} fenêtres, "
                 f"{outputs['wf_summary'].get('pct_oos_profitable', 0):.0%} OOS rentables, "
                 f"Sharpe OOS moyen {outputs['wf_summary'].get('oos_sharpe_mean', 0):.2f}.")
    lines.append(f"- **Monte Carlo** : Sharpe observé {mc.get('observed_sharpe', 0):.2f}, "
                 f"p-value {mc.get('p_value', 1):.4f} ({mc.get('n_iter', 0)} permutations).")
    lines.append(f"- **Distribution Max DD** (order-shuffle) : observé "
                 f"${dd.get('observed_max_dd', 0):.0f}, p95 ${dd.get('dd_p95', 0):.0f}, "
                 f"pire ${dd.get('dd_worst', 0):.0f}.")
    if len(cpcv) > 0:
        lines.append(f"- **CPCV** : {len(cpcv)} chemins, Sharpe OOS moyen "
                     f"{float(np.mean(cpcv)):.2f} (écart-type {float(np.std(cpcv)):.2f}).")
    else:
        lines.append("- **CPCV** : pas assez de jours de trading pour générer des chemins.")
    lines.append(f"- **Deflated Sharpe Ratio** : {outputs['dsr']:.4f} "
                 f"(sr_variance {outputs['sr_variance']:.4f}, n_trials {hyp.n_trials}).")
    pbo = outputs["pbo"]
    lines.append(f"- **PBO** : {'N/A (grille à 1 variant)' if pbo is None else f'{pbo:.3f}'}.")
    lines.append(f"- **Cycle PA** : compte {'vivant' if cycle['survived'] else 'MORT'}, "
                 f"lock {'atteint' if cycle['reached_lock'] else 'NON atteint'} "
                 f"(en {cycle['trading_days_to_lock']} jours de trading), "
                 f"inactivité {'OK' if cycle['inactivity_safe'] else 'VIOLÉE'}, "
                 f"balance finale ${cycle['final_balance']:.0f}.")
    lines.append("")

    # ── Stress test ─────────────────────────────────────────────
    lines.append("## Stress test — périodes rouges")
    lines.append("")
    lines.append(outputs["stress"].to_markdown(index=False))
    lines.append("")

    # ── Caveats + next steps ────────────────────────────────────
    lines.append("## Caveats")
    lines.append("")
    for cav in verdict.caveats:
        lines.append(f"- {cav}")
    lines.append("")
    lines.append("## Next steps")
    lines.append("")
    for step in verdict.next_steps:
        lines.append(f"- {step}")
    lines.append("")
    lines.append(f"_Holdout : {hm['trades']} trades, PF {hm['pf']:.2f}, "
                 f"Sharpe {hm['sharpe']:.2f}, PnL ${hm['pnl']:.0f} — confiance dégradée._")
    lines.append("")
    return "\n".join(lines)


def write_gauntlet_report(verdict, outputs: dict, out_dir: str) -> None:
    """Écrit le rapport markdown + les 5 CSVs/logs dans out_dir.

    Args:
        verdict: le Verdict (sortie de build_verdict).
        outputs: dict bundlé par run_gauntlet (hypothesis, wf, mc, dd, cpcv, dsr, pbo,
                 full_metrics, full_account, stress, cycle, holdout_metrics,
                 fulltv_results, best_params, sr_variance, wf_summary).
        out_dir: dossier de destination (créé si absent).
    """
    os.makedirs(out_dir, exist_ok=True)

    # gauntlet_report.md
    md = _format_report_md(verdict, outputs)
    with open(os.path.join(out_dir, "gauntlet_report.md"), "w", encoding="utf-8") as f:
        f.write(md)

    # ranking.csv — une ligne par variant
    ranking_rows = []
    for r in outputs["fulltv_results"]:
        m = r["metrics"]
        ranking_rows.append({
            "params": str(r["params"]),
            "trades": m["trades"], "pf": m["pf"], "sharpe": m["sharpe"],
            "max_dd": m["max_dd"], "wr": m["wr"], "pnl": m["pnl"],
            "avg_trade": m["avg_trade"],
            "is_best": r["params"] == outputs["best_params"],
        })
    pd.DataFrame(ranking_rows).to_csv(os.path.join(out_dir, "ranking.csv"), index=False)

    # pa_account_trace.csv — clôtures + tier + seuil DD reconstruit
    trace = _reconstruct_threshold_trace(outputs["full_account"].daily_history)
    trace.to_csv(os.path.join(out_dir, "pa_account_trace.csv"), index=False)

    # walk_forward.csv
    outputs["wf"].to_csv(os.path.join(out_dir, "walk_forward.csv"), index=False)

    # cpcv_distribution.csv
    pd.DataFrame({"oos_sharpe": np.asarray(outputs["cpcv"], dtype=float)}).to_csv(
        os.path.join(out_dir, "cpcv_distribution.csv"), index=False)

    # run_log.txt
    acc = outputs["full_account"]
    with open(os.path.join(out_dir, "run_log.txt"), "w", encoding="utf-8") as f:
        f.write(f"hypothesis    : {outputs['hypothesis'].name}\n")
        f.write(f"verdict       : {verdict.verdict}\n")
        f.write(f"best_params   : {outputs['best_params']}\n")
        f.write(f"account status: {acc.status}\n")
        f.write(f"hard fails    : {[c.name for c in verdict.hard_fails]}\n")
        f.write(f"n criteria    : {len(verdict.criteria)}\n")
```

- [ ] **Step 4: Lancer les tests — ils doivent PASSER**

Run: `python -m pytest 02_validation/gauntlet/tests/test_report.py -v`
Expected: PASS — 5 tests passés.

- [ ] **Step 5: Commit**

```bash
git add 02_validation/gauntlet/report.py 02_validation/gauntlet/tests/test_report.py
git commit -m "feat(gauntlet): report - rapport markdown + CSVs traçables"
```

---

### Task 7 : `calibration/` — les 2 hypothèses contrôle

**Files:**
- Create: `02_validation/gauntlet/calibration/__init__.py`
- Create: `02_validation/gauntlet/calibration/hyp_eod_reversal.py`
- Create: `02_validation/gauntlet/calibration/hyp_v9_hurstmr.py`
- Create: `02_validation/gauntlet/tests/test_calibration_hyps.py`

**Pourquoi :** la calibration known-answer. Le gauntlet doit prouver qu'il rejette des stratégies connues-mortes — sinon aucun verdict n'est fiable. Deux hypothèses contrôle, encodées comme objets `Hypothesis` enfichables. **EOD reversal** : MR z-score sur la pocket 15h NY (mini-val #4 — PF 0.80 Train, 0/61 mois), grille sur le z-score d'exit (C0/C1/C2). **v9 HurstMR** : MR z-score k=2.75 gaté par Hurst < 0.58 (NT8 SA : PF 1.02, DD -$22k). Les deux réutilisent les générateurs de `01_research/src/` tels quels — l'`Hypothesis` les wrappe. Rappel (cf. choix de design en tête de plan) : le gauntlet impose ses propres SL/force-flat/friction, donc ces contrôles ne reproduisent pas le backtest NT8 à l'identique — ils encodent l'**entrée** de v9 / EOD reversal jugée par les mécaniques honnêtes du gauntlet, et doivent ressortir NO-GO.

- [ ] **Step 1: Écrire les tests qui échouent**

Create `02_validation/gauntlet/tests/test_calibration_hyps.py` :

```python
"""Tests des 2 hypothèses de calibration (objets Hypothesis bien formés)."""
from gauntlet.hypothesis import Hypothesis
from gauntlet.calibration.hyp_eod_reversal import HYP_EOD_REVERSAL
from gauntlet.calibration.hyp_v9_hurstmr import HYP_V9_HURSTMR


def _check_well_formed(hyp):
    assert isinstance(hyp, Hypothesis)
    assert hyp.instrument in {"MNQ"}
    assert hyp.timeframe == "5min"
    assert callable(hyp.prepare_features)
    assert len(hyp.param_grid) >= 1
    # build_variant produit le triplet (signal_fn, exit_logic, backtest_kwargs)
    for params in hyp.param_grid:
        signal_fn, exit_logic, bt_kwargs = hyp.build_variant(params)
        assert callable(signal_fn)
        assert callable(exit_logic)
        assert "bar_size_min" in bt_kwargs and "timeout_bars" in bt_kwargs


def test_eod_reversal_hypothesis_well_formed():
    _check_well_formed(HYP_EOD_REVERSAL)
    assert HYP_EOD_REVERSAL.name == "eod_reversal_control"
    assert HYP_EOD_REVERSAL.n_trials == 3


def test_v9_hurstmr_hypothesis_well_formed():
    _check_well_formed(HYP_V9_HURSTMR)
    assert HYP_V9_HURSTMR.name == "v9_hurstmr_control"
    assert HYP_V9_HURSTMR.n_trials == 3


def test_prepare_features_ajoute_les_colonnes_attendues():
    import numpy as np
    import pandas as pd
    # df de session minimal : 3 jours, 80 barres/jour, colonnes OHLC + temporelles
    rows = []
    for d in pd.bdate_range("2022-01-03", periods=3):
        base = pd.Timestamp(d.year, d.month, d.day, 9, 30, tz="UTC")
        for b in range(80):
            rows.append((base + pd.Timedelta(minutes=5 * b), 100.0 + np.sin(b / 5)))
    idx = pd.DatetimeIndex([r[0] for r in rows])
    df = pd.DataFrame({"close": [r[1] for r in rows]}, index=idx)
    df["high"] = df["close"] + 0.5
    df["low"] = df["close"] - 0.5
    df["date"] = df.index.date
    df["hour_ny"] = df.index.hour
    df["min_ny"] = df.index.minute

    eod_feat = HYP_EOD_REVERSAL.prepare_features(df)
    assert {"mid", "std", "zscore"}.issubset(eod_feat.columns)

    v9_feat = HYP_V9_HURSTMR.prepare_features(df)
    assert {"mid", "std", "zscore", "hurst"}.issubset(v9_feat.columns)
```

- [ ] **Step 2: Lancer les tests — ils doivent ÉCHOUER**

Run: `python -m pytest 02_validation/gauntlet/tests/test_calibration_hyps.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'gauntlet.calibration'`

- [ ] **Step 3: Créer le package + les 2 hypothèses**

Create `02_validation/gauntlet/calibration/__init__.py` (fichier vide, 0 octet).

Create `02_validation/gauntlet/calibration/hyp_eod_reversal.py` :

```python
"""Hypothèse contrôle de calibration — EOD Reversal MNQ 5min.

KNOWN-ANSWER : doit ressortir NO-GO. Mini-validation #4 : PF 0.80 Train Apex-compliant,
0/61 mois passés. L'edge EOD reversal se complète après 16:00 NY (close auction) — Apex
verrouille le trader dehors. Encode l'ENTRÉE EOD reversal (MR z-score sur la pocket 15h NY)
jugée par les mécaniques du gauntlet ; la grille balaie le z-score d'exit (configs C0/C1/C2
du sprint re-engineering exit).
"""
from __future__ import annotations

from functools import partial

from src.config import ENTRY_CUTOFF_NY_MIN
from src.features import compute_signal_features
from src.signals import signal_mr_zscore
from src.backtest import exit_logic_mr_zscore

from gauntlet.hypothesis import Hypothesis

_BAR_MIN = 5
_LOOKBACK = 20          # lookback z-score (mini-val #4)
_TIMEOUT_BARS = 12      # 5min : timeout = 12 barres (mini-val #4)


def _prepare_features(df):
    """Features MR z-score (mid / std / zscore rolling)."""
    return compute_signal_features(df, lookback=_LOOKBACK)


def _build_variant(params):
    """params: {'zscore_exit': float}. Entrée z>2 pocket 15h NY, exit z-score."""
    def signal_fn(df):
        return signal_mr_zscore(
            df, entry_threshold=2.0, allowed_hours={15},
            entry_cutoff_ny_min=ENTRY_CUTOFF_NY_MIN, bar_size_min=_BAR_MIN,
        )
    exit_logic = partial(exit_logic_mr_zscore, zscore_exit=params["zscore_exit"])
    return signal_fn, exit_logic, {"bar_size_min": _BAR_MIN, "timeout_bars": _TIMEOUT_BARS}


HYP_EOD_REVERSAL = Hypothesis(
    name="eod_reversal_control",
    description="EOD Reversal MNQ 5min — MR z>2 pocket 15h NY, exit z-score — contrôle known-NO-GO",
    instrument="MNQ",
    timeframe="5min",
    build_variant=_build_variant,
    param_grid=[{"zscore_exit": 0.5}, {"zscore_exit": 1.0}, {"zscore_exit": 1.5}],
    prepare_features=_prepare_features,
)
```

Create `02_validation/gauntlet/calibration/hyp_v9_hurstmr.py` :

```python
"""Hypothèse contrôle de calibration — v9 HurstMR MNQ 5min.

KNOWN-ANSWER : doit ressortir NO-GO. Backtest NT8 Strategy Analyzer tick-realistic
(5 ans MNQ) : PF 1.02, max DD -$22,748, Sharpe 0.05 — pas d'edge, bust Apex garanti.
Encode l'ENTRÉE v9 (MR z-score k=2.75 gaté par Hurst < 0.58, LB=19, HW=50) jugée par les
mécaniques honnêtes du gauntlet (backtest_pa impose son propre SL 1.5×std wick-aware, le
force-flat 15:55 et la friction obligatoire — donc ce contrôle n'est PAS le v9 NT8 à
l'identique, c'est voulu). La grille balaie band_k et le seuil Hurst.

Note : la "skip 14h UTC" du v9 Python était l'un des 5 défauts structurels documentés
(archétype python_backtest_illusion) — on ne la reproduit pas, le contrôle trade toute
la session.
"""
from __future__ import annotations

from functools import partial

from src.config import ENTRY_CUTOFF_NY_MIN, HURST_WINDOW, LOOKBACK
from src.features import compute_signal_features
from src.hurst import compute_rolling_hurst_by_session
from src.signals import signal_mr_zscore
from src.backtest import exit_logic_mr_zscore

from gauntlet.hypothesis import Hypothesis

_BAR_MIN = 5
_TIMEOUT_BARS = 120     # v9 : timeout 120 barres (config figée)


def _prepare_features(df):
    """Features MR z-score (LB=19) + colonne Hurst rolling par session (HW=50)."""
    out = compute_signal_features(df, lookback=LOOKBACK)          # LOOKBACK = 19
    out["hurst"] = compute_rolling_hurst_by_session(out, hwin=HURST_WINDOW)  # HURST_WINDOW = 50
    return out


def _build_variant(params):
    """params: {'band_k': float, 'hurst_threshold': float}. MR z-score gaté Hurst."""
    def signal_fn(df):
        sigs = signal_mr_zscore(
            df, entry_threshold=params["band_k"],
            entry_cutoff_ny_min=ENTRY_CUTOFF_NY_MIN, bar_size_min=_BAR_MIN,
        )
        # Gate Hurst : v9 ne trade le MR que si H < seuil (régime mean-reverting).
        # Hurst NaN (warmup de session) -> pas de trade.
        block = sigs["hurst"].isna() | (sigs["hurst"] >= params["hurst_threshold"])
        sigs.loc[block, "signal"] = 0
        return sigs
    exit_logic = partial(exit_logic_mr_zscore, zscore_exit=0.5)
    return signal_fn, exit_logic, {"bar_size_min": _BAR_MIN, "timeout_bars": _TIMEOUT_BARS}


HYP_V9_HURSTMR = Hypothesis(
    name="v9_hurstmr_control",
    description="v9 HurstMR MNQ 5min — MR z k=2.75 gaté Hurst<0.58 — contrôle known-NO-GO",
    instrument="MNQ",
    timeframe="5min",
    build_variant=_build_variant,
    param_grid=[
        {"band_k": 2.75, "hurst_threshold": 0.58},
        {"band_k": 2.50, "hurst_threshold": 0.58},
        {"band_k": 2.75, "hurst_threshold": 0.55},
    ],
    prepare_features=_prepare_features,
)
```

- [ ] **Step 4: Lancer les tests — ils doivent PASSER**

Run: `python -m pytest 02_validation/gauntlet/tests/test_calibration_hyps.py -v`
Expected: PASS — 3 tests passés.

- [ ] **Step 5: Commit**

```bash
git add 02_validation/gauntlet/calibration/ 02_validation/gauntlet/tests/test_calibration_hyps.py
git commit -m "feat(gauntlet): calibration - hypothèses contrôle EOD reversal + v9 HurstMR"
```

---

### Task 8 : `03_gauntlet_calibration.py` — le script de calibration sur vraies données

**Files:**
- Create: `02_validation/notebooks/03_gauntlet_calibration.py`

**Pourquoi :** le test d'intégration final du gauntlet — sur les **vraies données**. Le spec : "les 2 hypothèses de calibration sont le test d'intégration de bout en bout, elles DOIVENT ressortir NO-GO". Ce script lance `run_gauntlet` sur les 2 contrôles (chargement réel du CSV Databento 5 ans), écrit les rapports dans `02_validation/outputs/gauntlet/`, et **`assert`** que les 2 verdicts sont NO-GO. Si l'un sort GO ou CONDITIONAL → le gauntlet est cassé ou mal calibré, STOP, investiguer. C'est un **script** (pas un test pytest) : il dépend d'un fichier local de ~1.7M lignes et tourne en plusieurs minutes (décision BB) — structuré comme `01_research/notebooks/02_sprint_exit_reengineering.py`.

- [ ] **Step 1: Créer le script de calibration**

Create `02_validation/notebooks/03_gauntlet_calibration.py` :

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
# # Gauntlet — Calibration known-answer
#
# Lance le gauntlet complet (`run_gauntlet`) sur les 2 hypothèses contrôle :
# **v9 HurstMR** et **EOD reversal**. Les deux sont connues-mortes — elles DOIVENT
# ressortir **NO-GO**. Si l'une sort GO ou CONDITIONAL, le gauntlet est cassé ou mal
# calibré : STOP, investiguer avant de faire confiance à un verdict.
#
# Spec : `docs/superpowers/specs/2026-05-14-gauntlet-validation-design.md` (section Calibration).
#
# **Exécuter depuis la racine du repo** (`python 02_validation/notebooks/03_gauntlet_calibration.py`).
# Charge le CSV Databento MNQ 5 ans (~1.7M lignes) + Hurst rolling — compter plusieurs minutes.

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
from gauntlet.calibration.hyp_eod_reversal import HYP_EOD_REVERSAL
from gauntlet.calibration.hyp_v9_hurstmr import HYP_V9_HURSTMR

OUT_BASE = _VALIDATION / "outputs" / "gauntlet"
OUT_BASE.mkdir(parents=True, exist_ok=True)

# %% [markdown]
# ## Lancement du gauntlet sur les 2 contrôles
#
# `run_gauntlet` charge les vraies données, prépare les splits, lance la batterie complète
# (walk-forward, CPCV, DSR, PBO, Monte Carlo, stress test, cycle PA) et agrège le verdict.

# %%
CONTROLS = [HYP_V9_HURSTMR, HYP_EOD_REVERSAL]
verdicts = {}

for hyp in CONTROLS:
    print("=" * 72)
    print(f"GAUNTLET — {hyp.name}")
    print("=" * 72)
    out_dir = OUT_BASE / hyp.name
    verdict = run_gauntlet(hyp, splits=None, out_dir=str(out_dir))
    verdicts[hyp.name] = verdict
    print(f"  verdict     : {verdict.verdict}")
    print(f"  hard fails  : {[c.name for c in verdict.hard_fails]}")
    for c in verdict.criteria:
        mark = "OK " if c.passed else "FAIL"
        print(f"    [{mark}] {c.name:18} = {c.value}")
    print(f"  rapport     : {out_dir / 'gauntlet_report.md'}")
    print()

# %% [markdown]
# ## Vérification known-answer
#
# Les 2 contrôles DOIVENT ressortir NO-GO. C'est le test d'intégration du build.

# %%
for name, verdict in verdicts.items():
    assert verdict.verdict == "NO-GO", (
        f"CALIBRATION ÉCHOUÉE : {name} ressort {verdict.verdict}, attendu NO-GO. "
        f"Le gauntlet est cassé ou mal calibré — investiguer avant de faire confiance "
        f"à un verdict. Hard fails détectés : {[c.name for c in verdict.hard_fails]}"
    )
    print(f"OK — {name} : NO-GO (calibration confirmée)")

print()
print("=" * 72)
print("GAUNTLET CALIBRÉ — les 2 contrôles known-dead ressortent bien NO-GO.")
print("Le gauntlet est prêt à juger une vraie hypothèse de recherche (cycle suivant).")
print("=" * 72)
```

- [ ] **Step 2: Vérifier que le script s'importe et se compile**

Run: `python -c "import ast; ast.parse(open('02_validation/notebooks/03_gauntlet_calibration.py', encoding='utf-8').read()); print('syntaxe OK')"`
Expected: `syntaxe OK`

Then verify the gauntlet imports the script relies on all resolve, from the repo root:
Run: `python -c "import sys; sys.path.insert(0, '02_validation'); sys.path.insert(0, '01_research'); from gauntlet.run_gauntlet import run_gauntlet; from gauntlet.calibration.hyp_eod_reversal import HYP_EOD_REVERSAL; from gauntlet.calibration.hyp_v9_hurstmr import HYP_V9_HURSTMR; print('imports OK')"`
Expected: `imports OK`

- [ ] **Step 3: Lancer le script de calibration sur les vraies données**

Run: `python 02_validation/notebooks/03_gauntlet_calibration.py`
Expected: le script tourne (plusieurs minutes — chargement Databento + Hurst rolling), écrit les rapports dans `02_validation/outputs/gauntlet/`, et imprime `GAUNTLET CALIBRÉ` après avoir confirmé les 2 NO-GO.

**Si le fichier de données est absent** (`INSTRUMENTS['MNQ']['path']` introuvable) ou si le run dépasse un budget de temps raisonnable : rapporter **DONE_WITH_CONCERNS** — le script est écrit et les imports résolvent, mais le run réel est à lancer par BB. Ne PAS commit un script qui ne se compile pas / dont les imports cassent.

**Si un contrôle ressort GO ou CONDITIONAL** : l'`assert` casse. NE PAS affaiblir l'`assert`. Rapporter **BLOCKED** avec le verdict obtenu, les hard fails, et le `gauntlet_report.md` correspondant — soit le gauntlet a un bug, soit l'encodage du contrôle n'est pas assez fidèle. Le contrôleur tranchera.

- [ ] **Step 4: Commit**

```bash
git add 02_validation/notebooks/03_gauntlet_calibration.py
git commit -m "feat(gauntlet): script de calibration - v9 + EOD reversal doivent ressortir NO-GO"
```

(Si les rapports `02_validation/outputs/gauntlet/` ont été générés et que BB veut les versionner, les ajouter dans un commit séparé — sinon `02_validation/outputs/` peut rester non versionné comme `01_research/outputs/`.)

---

## Self-Review (effectuée à l'écriture du plan)

**1. Couverture spec** — Plan 3 couvre les blocs restants du spec :
- Bloc 1 (Préparation) ✓ — `prepare_data` + `_prepare_splits` (Task 3).
- Bloc 2 (le run_variant concret PA-réaliste) ✓ — `make_run_variant` (Task 3) ; le `backtest_pa` lui-même est Plan 1.
- Bloc 3 (batterie statistique) ✓ — orchestré dans `run_gauntlet` (Task 5), modules Plan 2.
- Bloc 4 (robustesse) ✓ — `run_stress_test` + `analyze_pa_cycle` orchestrés dans `run_gauntlet` (Task 5).
- Bloc 5 (Verdict) ✓ — `verdict.py` (Task 2).
- Architecture `run_gauntlet.py` + `verdict.py` + `calibration/` ✓ (Tasks 2-7).
- Outputs `02_validation/outputs/gauntlet/<nom>/` (gauntlet_report.md, ranking.csv, pa_account_trace.csv, walk_forward.csv, cpcv_distribution.csv, run_log.txt) ✓ — `report.py` (Task 6).
- Calibration : 2 hypothèses contrôle known-NO-GO ✓ (Task 7) + le test d'intégration de bout en bout ✓ — script de calibration (Task 8) + le test pytest synthétique e2e (Task 5).
- Réutilisé tel quel : `signals.py` / `exit_logic_*` / `data_loader.py` / `features.py` / `hurst.py` de `01_research/src/` — wrappés par les `Hypothesis` et `prepare_data`.

**Écarts assumés vs le texte du spec** (tous documentés en tête de plan) : (a) `Hypothesis` gagne un champ `prepare_features` — le spec ne le mentionnait pas mais les features sont hypothèse-spécifiques ; champ optionnel, backward-compatible. (b) Seuil DSR fixé à 0.95 (le spec disait "> 0", impossible avec le code consolidé) — décision BB. (c) Calibration en script + pytest synthétique plutôt qu'un seul test pytest — décision BB.

**2. Placeholders** — aucun TBD/TODO ; tout le code est complet et exécutable. Le script de calibration (Task 8) n'est pas du TDD red-green (c'est un script avec `assert` intégrés) — c'est explicite et justifié (dépend d'un fichier local lourd, décision BB).

**3. Cohérence des types** — le contrat `run_variant(df, params) -> (trades_df, account)` est identique partout (`make_run_variant`, les helpers, les modules Plan 2). `Hypothesis` a bien 7 champs après Task 1, et Tasks 3-7 utilisent `prepare_features` / `build_variant` / `param_grid` / `n_trials` de façon cohérente. `build_verdict` (Task 2) reçoit exactement les clés que `run_gauntlet` (Task 5) lui passe : `account_survived`, `wf_summary`, `mc`, `dsr`, `pbo`, `full_max_dd`, `stress_passed`, `reached_lock`, `inactivity_safe`, `holdout_note`. Le dict `outputs` passé à `write_gauntlet_report` (Task 6) contient exactement les clés que `_format_report_md` et `write_gauntlet_report` lisent : `hypothesis, wf, wf_summary, mc, dd, cpcv, dsr, sr_variance, pbo, full_metrics, full_account, stress, cycle, holdout_metrics, fulltv_results, best_params`. Les sorties des modules Plan 2 sont consommées sous leurs noms RÉELS post-fix (vérifié sur le code mergé) : `walk_forward_summary` → `n_windows`/`pct_oos_profitable`/`oos_sharpe_mean` ; `analyze_pa_cycle` → `survived`/`reached_lock`/`trading_days_to_lock`/`inactivity_safe`/`final_balance`/`n_trading_days` ; `run_stress_test` → colonne `trade_seq_max_dd` (pas `max_dd`) ; `permutation_test_sharpe` → `observed_sharpe`/`p_value`/`n_iter` ; `dd_distribution_shuffle` → `observed_max_dd`/`dd_p95`/`dd_worst`. `compute_trade_metrics` → `trades`/`pf`/`sharpe`/`max_dd`/`wr`/`pnl`/`avg_trade`.

**4. Risque connu** — `prepare_data` (le seul code à I/O fichier) n'a pas de test pytest direct : il est couvert par le script de calibration (Task 8) qui le fait tourner sur les vraies données. C'est assumé (décision BB sur la structure calibration). Le risque résiduel : un bug dans le chaînage `load_continuous → resample → add_temporal_columns → filter_session_ny → _prepare_splits` ne se verrait qu'au run de calibration — mais `_prepare_splits` (la partie features+splits) EST testée, et `load_continuous`/`resample_ohlcv`/`add_temporal_columns`/`filter_session_ny` sont du code recherche existant déjà éprouvé par le sprint exit. L'autre risque : l'encodage des contrôles de calibration pas assez fidèle → un contrôle ressort ≠ NO-GO. C'est exactement ce que le script de calibration détecte (l'`assert`), et le plan dit explicitement de remonter ça en BLOCKED plutôt que d'affaiblir l'`assert`.
