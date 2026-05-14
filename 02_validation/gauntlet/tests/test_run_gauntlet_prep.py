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

    # contrat : chaque appel produit un PaAccount NEUF (pas de state qui fuit entre appels)
    trades2, account2 = run_variant(df, {"timeout_bars": 3})
    assert account2 is not account
    assert isinstance(account2, PaAccount)
