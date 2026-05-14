"""Simulation cycle PA — le meilleur variant survit-il à un compte PA EOD continu ?

Le walk-forward et le stress test regardent des fenêtres. Le cycle PA regarde le compte
en CONTINU sur tout l'historique : un seul PaAccount, jour après jour. Trois questions :
  - survie     : le compte touche-t-il jamais le seuil DD EOD ? (touché = mort définitive)
  - lock       : atteint-il le plafond figé $50,100 ? (= une clôture journalière >= $52,100)
  - inactivité : respecte-t-il la règle Apex >= 2 jours à >= $50 net / 30 jours glissants ?
                 Un edge "rares gros gains" peut survivre ET se faire fermer pour inactivité.

run_variant est INJECTÉ (cf. plan §"Le contrat run_variant").
"""
from __future__ import annotations

import pandas as pd

from gauntlet.pa_rules import (
    ACCOUNT_SIZE, EOD_DD, EOD_THRESHOLD_LOCK,
    INACTIVITY_MIN_GREEN_DAYS, INACTIVITY_GREEN_THRESHOLD, INACTIVITY_WINDOW_DAYS,
)

# Plus haute clôture journalière qui déclenche le lock du seuil :
# seuil = min(highest_close - 2000, 50_100) == 50_100  <=>  highest_close >= 52_100.
_LOCK_CLOSE = EOD_THRESHOLD_LOCK + EOD_DD          # 52_100.0


def _daily_net_pnl(daily_history: list) -> list:
    """[(date, eod_close, tier), ...] -> [(date, net_pnl_du_jour), ...].

    net du jour 0 = clôture - ACCOUNT_SIZE ; net du jour i = clôture i - clôture i-1.
    """
    out = []
    prev = ACCOUNT_SIZE
    for date, eod_close, _tier in daily_history:
        out.append((date, eod_close - prev))
        prev = eod_close
    return out


def _inactivity_check(daily_history: list):
    """Vérifie la règle d'inactivité Apex sur toutes les fenêtres glissantes de 30 jours.

    Pour chaque jour de trading d dont la fenêtre [d, d+30j) est ENTIÈREMENT couverte par
    l'historique : compte les jours "verts" (net >= $50). Si une fenêtre a < 2 verts ->
    violation. Les fenêtres en fin d'historique (pas encore 30j de recul) ne sont pas
    jugées — pas assez de données pour conclure.

    Returns: (safe: bool, first_violation_date: date | None).
    """
    nets = _daily_net_pnl(daily_history)
    if not nets:
        return True, None
    dates = [pd.Timestamp(d) for d, _ in nets]
    green = [pd.Timestamp(d) for d, net in nets if net >= INACTIVITY_GREEN_THRESHOLD]
    last_date = dates[-1]
    window = pd.Timedelta(days=INACTIVITY_WINDOW_DAYS)
    for d in dates:
        if d + window > last_date:
            break                                  # fenêtre incomplète -> on s'arrête
        n_green = sum(1 for g in green if d <= g < d + window)
        if n_green < INACTIVITY_MIN_GREEN_DAYS:
            return False, d.date()
    return True, None


def analyze_pa_cycle(account) -> dict:
    """Analyse un PaAccount après un run complet sur l'historique.

    Args:
        account: PaAccount déjà avancé par backtest_pa sur tout l'historique.

    Returns:
        dict(survived, reached_lock, days_to_lock, final_balance, n_trading_days,
             inactivity_safe, inactivity_first_violation).
    """
    survived = account.status != "dead_eod"
    history = account.daily_history

    # Lock : 1er jour où la plus haute clôture cumulée atteint $52,100.
    reached_lock, days_to_lock = False, None
    running_max = ACCOUNT_SIZE
    for i, (_date, eod_close, _tier) in enumerate(history):
        if eod_close > running_max:
            running_max = eod_close
        if running_max >= _LOCK_CLOSE:
            reached_lock, days_to_lock = True, i + 1
            break

    final_balance = history[-1][1] if history else account.balance
    inactivity_safe, first_violation = _inactivity_check(history)

    return dict(
        survived=survived,
        reached_lock=reached_lock,
        days_to_lock=days_to_lock,
        final_balance=final_balance,
        n_trading_days=len(history),
        inactivity_safe=inactivity_safe,
        inactivity_first_violation=first_violation,
    )


def run_pa_cycle(df, best_params, run_variant) -> dict:
    """Rejoue le meilleur variant sur tout l'historique (un seul PaAccount continu),
    puis analyse le compte.

    Args:
        df: DataFrame préparé couvrant l'historique de simulation (Train+Valid).
        best_params: param dict du meilleur variant.
        run_variant: callable(df, params) -> (trades_df, account). Injecté.

    Returns:
        analyze_pa_cycle(account) enrichi de 'n_trades'.
    """
    trades, account = run_variant(df, best_params)
    result = analyze_pa_cycle(account)
    result["n_trades"] = len(trades)
    return result
