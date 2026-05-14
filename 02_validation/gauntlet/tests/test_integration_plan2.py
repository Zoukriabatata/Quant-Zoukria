"""Intégration Plan 2 : la batterie statistique tourne de bout en bout.

Construit un run_variant RÉEL (signal MR trivial + backtest_pa sur PaAccount), puis fait
tourner les six modules : walk-forward, CPCV, DSR, Monte Carlo, stress test, cycle PA.
Si ça passe, Plan 2 est fonctionnel et Plan 3 (verdict + orchestration) peut se brancher.

Portée : ce test vérifie le CÂBLAGE (les six modules s'assemblent et produisent une
sortie bien formée sur un vrai run_variant). La fixture est volontairement tout-profit
(le compte doit survivre 60 jours pour que CPCV ait assez de jours) — du coup les chemins
drawdown / survie / mort de compte ne sont exercés que trivialement ici. Leurs cas non
triviaux (trades perdants, compte qui meurt) sont couverts par les tests unitaires de
test_monte_carlo.py / test_pa_account.py / test_pa_cycle.py.
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
    """n_days jours ouvrés, 12 barres 5min/jour (14:30->15:25 NY).

    Les barres PAIRES sont sous mid (close = 100 - amp -> déclenchent le signal LONG MR
    "oversold"), les barres IMPAIRES repassent au-dessus de mid (close = 100 + amp ->
    déclenchent l'exit "retour au mid"). Chaque trade achète bas / sort haut -> profitable
    -> le compte survit les 60 jours, donc CPCV obtient assez de jours de trading.
    L'amplitude `amp` varie jour à jour -> le PnL journalier varie -> les Sharpe CPCV ne
    sont pas dégénérés (écart-type non nul).
    """
    rng = np.random.default_rng(2026)
    days = pd.bdate_range("2022-01-03", periods=n_days)
    rows = []
    for d in days:
        amp = 1.0 + abs(rng.normal(0.0, 0.5))     # amplitude jour-à-jour, toujours > 0
        base = pd.Timestamp(d.year, d.month, d.day, 14, 30, tz="America/New_York")
        for b in range(12):
            ts = base + pd.Timedelta(minutes=5 * b)
            # barres paires sous mid (oversold -> LONG), impaires au-dessus (exit)
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


def _run_variant(df, params):
    """run_variant RÉEL : signal MR trivial (LONG si close < mid, "oversold") + backtest_pa
    sur un PaAccount neuf. Conforme au contrat (df, params) -> (trades_df, account)."""
    out = df.copy()
    out["signal"] = 0
    out.loc[out["close"] < out["mid"], "signal"] = 1

    def exit_logic(d, i, j, direction, entry_price, std_i, mid_i,
                   or_high, or_low, or_range, sl_pts):
        if direction == 1 and d.at[j, "close"] >= d.at[j, "mid"]:
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
    assert not wf["oos_no_signal"].any()        # le signal se déclenche dans chaque fenêtre
    wf_sum = walk_forward_summary(wf)
    assert 0.0 <= wf_sum["pct_oos_profitable"] <= 1.0
    # convention : meilleur param de la DERNIÈRE fenêtre OOS — Plan 3 peut choisir autrement
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
    # fixture tout-profit -> equity monotone -> tous les DD sont nuls. Le chemin DD non
    # trivial (trades perdants) est couvert par test_monte_carlo.py.
    assert dd["dd_worst"] <= 0.0
    assert dd["observed_max_dd"] == 0.0

    # ── CPCV + Deflated Sharpe ───────────────────────────────────
    cpcv = sharpe_distribution_cpcv(trades, n_groups=5, k_test=2,
                                    date_col="date", pnl_col="pnl_usd")
    assert len(cpcv) > 0
    daily = trades.groupby("date")["pnl_usd"].sum().to_numpy()
    dsr = deflated_sharpe_ratio(daily, n_trials=len(grid), sr_variance=0.3 ** 2)
    # fixture à fort edge synthétique (60 jours profitables) -> DSR doit être proche de 1.
    # > 0.95 attrape une entrée mal mise à l'échelle (ex. PnL per-trade au lieu de daily).
    assert 0.95 < dsr <= 1.0

    # ── Stress test (période custom dans la plage synthétique) ───
    custom_red = {
        "synthetic_crash": (pd.Timestamp("2022-02-01", tz="America/New_York"),
                            pd.Timestamp("2022-02-15", tz="America/New_York")),
    }
    stress = run_stress_test(df, best_params, _run_variant, red_periods=custom_red)
    assert len(stress) == 1
    # fixture tout-profit : aucune journée ne meurt -> survie garantie
    assert stress_test_passed(stress) is True

    # ── Cycle PA ─────────────────────────────────────────────────
    cycle = run_pa_cycle(df, best_params, _run_variant)
    assert "survived" in cycle
    assert cycle["n_trading_days"] >= 1
    # deux runs indépendants sur df entier (fresh PaAccount) -> même n_trades tant que
    # le compte survit
    assert cycle["n_trades"] == len(trades)
