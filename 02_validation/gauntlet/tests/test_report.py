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
