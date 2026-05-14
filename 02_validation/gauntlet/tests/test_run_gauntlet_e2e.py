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
