"""backtest_pa — backtest event-driven sur un compte PA EOD.

Fait avancer un PaAccount jour par jour en simulant les trades d'une hypothèse.
Friction obligatoire, SL wick-aware, force-flat 15:55 NY, enforcement DD EOD + DLL.
"""
from __future__ import annotations

import pandas as pd

from gauntlet.pa_rules import FORCE_FLAT_NY, MICROS_PER_STANDARD


def backtest_pa(df_signals, exit_logic, instrument_specs, account,
                bar_size_min, timeout_bars, slippage_ticks=1, force_flat_ny=FORCE_FLAT_NY):
    """Backtest event-driven sur un compte PA EOD.

    Args:
        df_signals: DataFrame indexé temps, colonnes requises :
            signal (+1/-1/0), close, high, low, std, mid, hour_ny, min_ny, date.
        exit_logic: callable(df, i, j, direction, entry_price, std_i, mid_i,
                             or_high, or_low, or_range, sl_pts) -> (touched, price, reason).
        instrument_specs: dict avec point_value, tick_size, commission_rt,
                          sl_floor_pts, sl_cap_pts.
        account: PaAccount — simulé EN PLACE (modifié).
        bar_size_min: taille de barre en minutes.
        timeout_bars: liquidation MTM après N barres si ni SL ni TP.
        slippage_ticks: ticks de slippage défavorable au SL.
        force_flat_ny: (heure, minute) NY du force-flat.

    Returns:
        DataFrame de trades. Colonnes : entry_time, exit_time, direction, entry_price,
        exit_price, contracts, sl_pts, pts, pnl_usd, exit_reason, bars_held, date.
    """
    df = df_signals.reset_index().copy()
    n = len(df)
    bar_col = df.columns[0]  # nom de la colonne d'index temps après reset_index()

    point_value = instrument_specs["point_value"]
    tick_size = instrument_specs["tick_size"]
    commission_rt = instrument_specs["commission_rt"]
    sl_floor = instrument_specs["sl_floor_pts"]
    sl_cap = instrument_specs["sl_cap_pts"]
    slip_pts = slippage_ticks * tick_size
    force_flat_min = force_flat_ny[0] * 60 + force_flat_ny[1]

    trades = []
    if n == 0:
        return pd.DataFrame(trades)

    current_date = df.at[0, "date"]
    account.start_session(current_date)
    i = 0
    while i < n:
        # ── Frontière de journée ────────────────────────────────────
        if df.at[i, "date"] != current_date:
            account.end_session(current_date)
            if account.status == "dead_eod":
                break
            current_date = df.at[i, "date"]
            account.start_session(current_date)

        if not account.can_trade():
            i += 1
            continue

        sig = df.at[i, "signal"]
        std_i = df.at[i, "std"]
        if sig == 0 or pd.isna(std_i) or std_i <= 0:
            i += 1
            continue

        # Pas d'entrée si la barre close au-delà du cutoff force-flat.
        close_min_ny = df.at[i, "hour_ny"] * 60 + df.at[i, "min_ny"] + bar_size_min
        if close_min_ny > force_flat_min:
            i += 1
            continue

        direction = int(sig)
        entry_price = df.at[i, "close"]
        mid_i = df.at[i, "mid"] if pd.notna(df.at[i, "mid"]) else entry_price
        sl_pts = max(sl_floor, min(sl_cap, 1.5 * std_i))
        sl_price = entry_price - direction * sl_pts
        contracts = account.max_contracts_std * MICROS_PER_STANDARD

        exit_idx = min(i + timeout_bars, n - 1)
        exit_price = df.at[exit_idx, "close"]
        exit_reason = "timeout"

        for j in range(i + 1, min(n, i + timeout_bars + 1)):
            hj, lj, cj = df.at[j, "high"], df.at[j, "low"], df.at[j, "close"]

            # ── Enforcement PA : equity au wick DÉFAVORABLE (conservateur) ──
            adverse = lj if direction == 1 else hj
            unreal_worst = direction * (adverse - entry_price) * point_value * contracts
            state = account.check_intraday(account.balance + unreal_worst)
            if state == "dead":
                exit_price, exit_idx, exit_reason = cj, j, "account_dead"
                break
            if state == "day_paused":
                exit_price, exit_idx, exit_reason = cj, j, "dll_paused"
                break

            # ── SL wick-aware ───────────────────────────────────────
            sl_touched = (direction == 1 and lj <= sl_price) or (direction == -1 and hj >= sl_price)
            if sl_touched:
                exit_price = sl_price - direction * slip_pts
                exit_idx, exit_reason = j, "SL"
                break

            # ── Take-profit de l'hypothèse ──────────────────────────
            tp_touched, tp_price, tp_reason = exit_logic(
                df, i, j, direction, entry_price, std_i, mid_i,
                float("nan"), float("nan"), float("nan"), sl_pts,
            )
            if tp_touched:
                exit_price, exit_idx, exit_reason = tp_price, j, tp_reason
                break

            # ── Force-flat 15:55 NY ─────────────────────────────────
            close_min_j = df.at[j, "hour_ny"] * 60 + df.at[j, "min_ny"] + bar_size_min
            if df.at[j, "date"] == current_date and close_min_j > force_flat_min:
                exit_price, exit_idx, exit_reason = cj, j, "force_flat"
                break

        pts = direction * (exit_price - entry_price)
        pnl_usd = pts * point_value * contracts - commission_rt * contracts
        account.record_trade(pnl_usd)
        trades.append({
            "entry_time": df.at[i, bar_col], "exit_time": df.at[exit_idx, bar_col],
            "direction": "LONG" if direction == 1 else "SHORT",
            "entry_price": entry_price, "exit_price": exit_price, "contracts": contracts,
            "sl_pts": sl_pts, "pts": pts, "pnl_usd": pnl_usd, "exit_reason": exit_reason,
            "bars_held": exit_idx - i, "date": df.at[i, "date"],
        })

        if account.status == "dead_eod":
            break
        i = exit_idx + 1

    return pd.DataFrame(trades)
