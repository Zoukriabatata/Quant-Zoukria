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
