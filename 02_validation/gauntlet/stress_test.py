"""Stress test — rejoue le meilleur variant sur les périodes rouges historiques.

Une stratégie peut avoir un beau Sharpe moyen et mourir quand même sur une fenêtre
hostile. Le stress test rejoue le variant sur les krachs disponibles dans les données
(2021-05 -> 2026-05) et vérifie le critère existentiel Apex : le seuil DD EOD n'est
JAMAIS touché (sinon compte mort définitif).

Périodes COVID (mars 2020) et Q4 2018 hors plage de données -> couverture stress
partielle, le verdict (Plan 3) le signalera.

run_variant est INJECTÉ (cf. plan §"Le contrat run_variant").
"""
from __future__ import annotations

import pandas as pd

from src.backtest import compute_trade_metrics

# Périodes rouges dans la plage de données (index df attendu en UTC, cf. src/config.py).
# Bornes [start, end).
RED_PERIODS = {
    "bear_2022": (
        pd.Timestamp("2022-01-03", tz="UTC"), pd.Timestamp("2022-10-14", tz="UTC")),
    "yen_unwind_aug2024": (
        pd.Timestamp("2024-07-29", tz="UTC"), pd.Timestamp("2024-08-09", tz="UTC")),
    "tariff_selloff_apr2025": (
        pd.Timestamp("2025-04-01", tz="UTC"), pd.Timestamp("2025-04-30", tz="UTC")),
}


def run_stress_test(df, best_params, run_variant, red_periods: dict = RED_PERIODS) -> pd.DataFrame:
    """Rejoue le meilleur variant sur chaque période rouge.

    Args:
        df: DataFrame préparé, indexé DatetimeIndex tz-aware.
        best_params: le param dict du meilleur variant (sélectionné par le walk-forward).
        run_variant: callable(df_slice, params) -> (trades_df, account). Injecté.
        red_periods: dict {nom: (start, end)} — bornes [start, end).

    Returns:
        DataFrame, une ligne par période :
        [period, start, end, n_trades, pnl, trade_seq_max_dd, survived].
        survived = le compte n'a PAS touché le seuil DD EOD (account.status != 'dead_eod').
        trade_seq_max_dd = drawdown cumulé de la SÉQUENCE de trades ($, départ 0) — ce n'est
        PAS le drawdown de l'equity du compte vs le seuil Apex $2,000. Indicatif uniquement.
        Période hors plage de données -> n_trades=0, pnl=0, trade_seq_max_dd=0, survived=True
        (vacuité : pas de trading, pas de mort).

    Raises:
        ValueError: si run_variant retourne account=None (contrat run_variant violé —
            stress_test exige un PaAccount pour vérifier la survie).
    """
    rows = []
    for name, (start, end) in red_periods.items():
        sub = df.loc[(df.index >= start) & (df.index < end)]
        if len(sub) == 0:
            rows.append({"period": name, "start": start, "end": end,
                         "n_trades": 0, "pnl": 0.0, "trade_seq_max_dd": 0.0,
                         "survived": True})
            continue
        trades, account = run_variant(sub, best_params)
        if account is None:
            raise ValueError(
                f"run_variant a retourné account=None pour la période '{name}'. "
                "stress_test exige un PaAccount — utiliser un run_variant qui en retourne un."
            )
        m = compute_trade_metrics(trades)
        survived = account.status != "dead_eod"
        rows.append({
            "period": name, "start": start, "end": end,
            "n_trades": m["trades"], "pnl": m["pnl"], "trade_seq_max_dd": m["max_dd"],
            "survived": survived,
        })
    return pd.DataFrame(rows)


def stress_test_passed(stress_df: pd.DataFrame) -> bool:
    """True si le compte a survécu à TOUTES les périodes rouges (critère verdict)."""
    if len(stress_df) == 0:
        return False
    return bool(stress_df["survived"].all())
