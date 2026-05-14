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
    kw["dsr"] = 0.93
    v = build_verdict(**kw)
    assert v.verdict == "NO-GO"
    assert any(c.name == "deflated_sharpe" and c.is_hard_fail for c in v.criteria)


def test_mc_pvalue_high_is_hard_fail_nogo():
    kw = _passing_kwargs()
    kw["mc"] = {"p_value": 0.20}
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
    kw = _passing_kwargs()
    kw["wf_summary"] = {"n_windows": 4, "pct_oos_profitable": 0.50}
    v = build_verdict(**kw)
    assert v.verdict == "CONDITIONAL"
    wf = next(c for c in v.criteria if c.name == "walk_forward")
    assert wf.passed is False
    assert wf.hard_fail is False


def test_max_dd_too_large_is_soft_fail_conditional():
    kw = _passing_kwargs()
    kw["full_max_dd"] = -1500.0
    v = build_verdict(**kw)
    assert v.verdict == "CONDITIONAL"


def test_pbo_none_marks_criterion_na_and_passes():
    kw = _passing_kwargs()
    kw["pbo"] = None
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


def test_dsr_exact_boundary_095_is_nogo():
    # DSR == 0.95 doit ÉCHOUER (le code utilise dsr > 0.95, strict — décision BB).
    # Ce test verrouille la frontière : un passage à `>=` serait détecté.
    kw = _passing_kwargs()
    kw["dsr"] = 0.95
    v = build_verdict(**kw)
    assert v.verdict == "NO-GO"
    dsr_c = next(c for c in v.criteria if c.name == "deflated_sharpe")
    assert dsr_c.passed is False
    assert dsr_c.is_hard_fail is True


def test_pa_cycle_soft_fail_gives_conditional():
    # reached_lock=False (critère mou pa_cycle échoué), aucun hard fail -> CONDITIONAL.
    kw = _passing_kwargs()
    kw["reached_lock"] = False
    v = build_verdict(**kw)
    assert v.verdict == "CONDITIONAL"
    cycle_c = next(c for c in v.criteria if c.name == "pa_cycle")
    assert cycle_c.passed is False
    assert cycle_c.hard_fail is False
