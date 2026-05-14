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

    # 8. Cycle PA — survie + lock + inactivité — MOU (spec : "survit + lock + inactivity-safe").
    # La survie est aussi le critère hard #1 ; on la garde ici pour que le critère pa_cycle
    # soit cohérent avec son énoncé (un compte mort ne "réussit" pas son cycle PA).
    cycle_ok = bool(account_survived and reached_lock and inactivity_safe)
    criteria.append(CriterionResult(
        name="pa_cycle", passed=cycle_ok,
        value=f"survived={account_survived}, lock={reached_lock}, "
              f"inactivity_safe={inactivity_safe}",
        threshold="compte survit ET lock atteint ET inactivity-safe", hard_fail=False,
        detail=f"Cycle PA continu : compte "
               f"{'vivant' if account_survived else 'MORT'}, lock $50,100 "
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
