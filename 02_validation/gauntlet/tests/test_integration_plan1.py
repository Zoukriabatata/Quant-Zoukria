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
    # end_session est appelé aux 2 changements de date ; la dernière journée n'est pas
    # clôturée par le backtest (pas de date suivante).
    assert len(acc.daily_history) >= 2
    # n_trials de l'hypothèse est cohérent
    assert hyp.n_trials == 1
