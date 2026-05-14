"""Tests de la simulation cycle PA."""
import pandas as pd
import pytest

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
    # la clôture franchit 52_100 au 3e jour -> reached_lock=True, trading_days_to_lock=3
    hist = [
        ("2026-01-02", 51_000.0, 1),
        ("2026-01-05", 51_800.0, 2),
        ("2026-01-06", 52_300.0, 3),
        ("2026-01-07", 52_000.0, 3),
    ]
    res = analyze_pa_cycle(_account_with_history(hist))
    assert res["reached_lock"] is True
    assert res["trading_days_to_lock"] == 3


def test_analyze_never_locks():
    hist = [("2026-01-02", 50_500.0, 1), ("2026-01-05", 51_000.0, 1)]
    res = analyze_pa_cycle(_account_with_history(hist))
    assert res["reached_lock"] is False
    assert res["trading_days_to_lock"] is None


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
    # les ~30 derniers anchors ne sont pas jugeables (fenêtre 30j incomplète)
    assert res["inactivity_unchecked_tail_days"] > 0


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


def test_analyze_inactivity_borderline_two_green():
    # jours verts tous les 15 jours -> chaque fenêtre 30j glissante en attrape exactement 2.
    # pinne la frontière >= 2 (un code avec > 2 échouerait).
    hist = []
    bal = 50_000.0
    for i, d in enumerate(pd.date_range("2026-01-01", periods=65, freq="D")):
        if i % 15 == 0:
            bal += 100.0                         # jour vert
        hist.append((d.date(), bal, 1))
    res = analyze_pa_cycle(_account_with_history(hist))
    assert res["inactivity_safe"] is True
    assert res["inactivity_first_violation"] is None


def test_analyze_empty_history():
    # compte mort avant toute clôture -> daily_history vide, fallback sur account.balance
    acc = PaAccount()
    acc.status = "dead_eod"
    res = analyze_pa_cycle(acc)
    assert res["survived"] is False
    assert res["n_trading_days"] == 0
    assert res["final_balance"] == 50_000.0
    assert res["reached_lock"] is False
    assert res["trading_days_to_lock"] is None
    assert res["inactivity_safe"] is True
    assert res["inactivity_unchecked_tail_days"] == 0


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


def test_run_pa_cycle_raises_on_none_account():
    # run_variant qui viole le contrat (account=None) -> ValueError, pas un AttributeError
    df = pd.DataFrame({"close": [1.0]},
                      index=pd.date_range("2026-01-01", periods=1, freq="D", tz="UTC"))

    def rv_bad(d, params):
        return pd.DataFrame({"pnl_usd": [1.0]}), None

    with pytest.raises(ValueError):
        run_pa_cycle(df, {"x": 1}, rv_bad)
