"""Tests du backtest event-driven sur PaAccount."""
import pandas as pd

from gauntlet.backtest import backtest_pa
from gauntlet.pa_account import PaAccount

# Specs MNQ minimales (cf. 01_research/src/instruments.py)
MNQ_SPECS = {
    "point_value": 2.00, "tick_size": 0.25, "commission_rt": 1.10,
    "sl_floor_pts": 5.0, "sl_cap_pts": 10.0,
}


def _exit_never(df, i, j, direction, entry_price, std_i, mid_i,
                or_high, or_low, or_range, sl_pts):
    """Exit logic qui ne déclenche jamais de TP — le trade sort par SL/force-flat/timeout."""
    return False, 0.0, ""


def _make_df(rows):
    """rows : list de dicts. Construit un df_signals indexé temps avec les colonnes requises."""
    idx = pd.date_range("2026-01-02 14:30", periods=len(rows), freq="5min", tz="America/New_York")
    df = pd.DataFrame(rows, index=idx)
    df["hour_ny"] = df.index.hour
    df["min_ny"] = df.index.minute
    df["date"] = df.index.date
    return df


def test_un_trade_long_gagnant_par_timeout():
    # signal LONG à la barre 0, le prix monte, sortie par timeout à la barre 2
    df = _make_df([
        {"signal": 1, "close": 100.0, "high": 100.5, "low": 99.5, "std": 4.0, "mid": 100.0},
        {"signal": 0, "close": 103.0, "high": 103.5, "low": 102.5, "std": 4.0, "mid": 100.0},
        {"signal": 0, "close": 105.0, "high": 105.5, "low": 104.5, "std": 4.0, "mid": 100.0},
    ])
    acc = PaAccount()
    trades = backtest_pa(df, _exit_never, MNQ_SPECS, acc, bar_size_min=5, timeout_bars=2)
    assert len(trades) == 1
    t = trades.iloc[0]
    assert t["direction"] == "LONG"
    assert t["exit_reason"] == "timeout"
    # gain brut = (105 - 100) * 2.00 * 20 contrats = 200 ; moins commission 1.10*20 = 22
    assert t["pnl_usd"] == 5.0 * 2.00 * 20 - 1.10 * 20
    assert acc.balance == 50_000.0 + t["pnl_usd"]


def test_sl_touche_sur_le_wick():
    # signal LONG ; std 4 -> sl_pts = max(5, min(10, 1.5*4)) = 6 -> sl_price = 94
    # barre 1 : low = 93.5 <= 94 -> SL touché sur le wick
    df = _make_df([
        {"signal": 1, "close": 100.0, "high": 100.5, "low": 99.5, "std": 4.0, "mid": 100.0},
        {"signal": 0, "close": 96.0, "high": 100.0, "low": 93.5, "std": 4.0, "mid": 100.0},
        {"signal": 0, "close": 96.0, "high": 96.5, "low": 95.5, "std": 4.0, "mid": 100.0},
    ])
    acc = PaAccount()
    trades = backtest_pa(df, _exit_never, MNQ_SPECS, acc, bar_size_min=5, timeout_bars=5)
    assert len(trades) == 1
    assert trades.iloc[0]["exit_reason"] == "SL"
    # exit_price = sl_price - slippage = 94 - 0.25 = 93.75 ; perte = (93.75-100)*2*20 - 1.10*20
    assert trades.iloc[0]["pnl_usd"] == (93.75 - 100.0) * 2.00 * 20 - 1.10 * 20


def test_force_flat_a_1555_ny():
    # entrée à 15:50 NY ; la barre de 15:55 close à 16:00 -> au-delà du cutoff -> force-flat
    idx = pd.to_datetime([
        "2026-01-02 15:50", "2026-01-02 15:55",
    ]).tz_localize("America/New_York")
    df = pd.DataFrame({
        "signal": [1, 0], "close": [100.0, 102.0], "high": [100.5, 102.5],
        "low": [99.5, 101.5], "std": [4.0, 4.0], "mid": [100.0, 100.0],
    }, index=idx)
    df["hour_ny"] = df.index.hour
    df["min_ny"] = df.index.minute
    df["date"] = df.index.date
    acc = PaAccount()
    trades = backtest_pa(df, _exit_never, MNQ_SPECS, acc, bar_size_min=5, timeout_bars=10)
    assert len(trades) == 1
    assert trades.iloc[0]["exit_reason"] == "force_flat"


def test_compte_mort_si_seuil_eod_touche():
    # signal LONG, 20 contrats MNQ. Le prix s'effondre : un mouvement adverse de 50 pts
    # = 50 * 2.00 * 20 = 2_000 de perte non réalisée -> equity 48_000 = seuil EOD initial.
    df = _make_df([
        {"signal": 1, "close": 100.0, "high": 100.5, "low": 99.5, "std": 4.0, "mid": 100.0},
        {"signal": 0, "close": 60.0, "high": 100.0, "low": 50.0, "std": 4.0, "mid": 100.0},
        {"signal": 0, "close": 60.0, "high": 60.5, "low": 59.5, "std": 4.0, "mid": 100.0},
    ])
    acc = PaAccount()
    trades = backtest_pa(df, _exit_never, MNQ_SPECS, acc, bar_size_min=5, timeout_bars=10)
    assert acc.status == "dead_eod"
    # le backtest s'arrête : le trade est liquidé, pas de trade après
    assert len(trades) == 1
    assert trades.iloc[0]["exit_reason"] == "account_dead"


def test_pas_de_trade_si_signal_apres_le_cutoff():
    # signal à 16:00 NY (barre qui close à 16:05) -> au-delà du cutoff -> aucune entrée
    idx = pd.to_datetime(["2026-01-02 16:00"]).tz_localize("America/New_York")
    df = pd.DataFrame({
        "signal": [1], "close": [100.0], "high": [100.5], "low": [99.5],
        "std": [4.0], "mid": [100.0],
    }, index=idx)
    df["hour_ny"] = df.index.hour
    df["min_ny"] = df.index.minute
    df["date"] = df.index.date
    acc = PaAccount()
    trades = backtest_pa(df, _exit_never, MNQ_SPECS, acc, bar_size_min=5, timeout_bars=10)
    assert len(trades) == 0
