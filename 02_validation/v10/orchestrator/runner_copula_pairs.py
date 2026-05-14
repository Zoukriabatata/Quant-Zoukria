"""
Backtest engine pour Copula Pairs ES/NQ (Sprint 3.3).

Stratégie simple :
    1. Charge ES et NQ continuous front-month, aligne sur ts_event commun
    2. Resample à 5-min (réduit le bruit micro et accélère le backtest)
    3. À chaque bar, calcule signal copule sur lookback rolling
    4. Entry quand conditional_prob > p_high (short ES, long NQ) ou < p_low (long ES, short NQ)
    5. Exit quand conditional_prob revient dans [exit_low, exit_high]
       OU stop_loss en points sur le spread
    6. Position size : 1 contrat ES vs N contrats NQ (hedge ratio par OLS rolling)

Notation :
    point_value ES = $50/pt, MES = $5/pt, NQ = $20/pt, MNQ = $2/pt
    Pour limiter le risque : trade MES + MNQ (micros) au lieu de ES + NQ.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from quant_v10.modules.copula_pairs_es_nq import (
    compute_mispricing_signal,
    fit_gaussian_copula,
    empirical_cdf_transform,
)
from quant_v10.utils.databento_loader import build_continuous_front_month


@dataclass
class CopulaPairsConfig:
    es_path: str
    nq_path: str
    resample: str = "5min"
    lookback: int = 500            # 500 × 5min ≈ 1.5 jours trading
    p_high: float = 0.95
    p_low: float = 0.05
    exit_neutral_band: float = 0.10  # exit quand |p - 0.5| < band
    max_hold_bars: int = 60        # cap holding period (5h)
    sl_spread_pts: float = 30.0    # SL en points de spread (MES x 1 - MNQ x ?)
    point_value_x: float = 5.0     # MES = $5/pt
    point_value_y: float = 2.0     # MNQ = $2/pt
    hedge_ratio: Optional[float] = None  # None = OLS rolling, sinon fixe
    capital: float = 50_000


def _align_and_resample(es: pd.DataFrame, nq: pd.DataFrame,
                         freq: str) -> pd.DataFrame:
    """
    Aligne ES et NQ sur ts_event commun, resample à freq donnée.
    Output : DataFrame avec colonnes 'es_close' et 'nq_close'.
    """
    es_r = es.set_index("ts_event")[["close"]].rename(columns={"close": "es_close"})
    nq_r = nq.set_index("ts_event")[["close"]].rename(columns={"close": "nq_close"})
    es_r = es_r.resample(freq).last().dropna()
    nq_r = nq_r.resample(freq).last().dropna()
    # Restreint à index commun
    joined = es_r.join(nq_r, how="inner").dropna()
    return joined


def run_copula_pairs_backtest(cfg: CopulaPairsConfig,
                                max_days: Optional[int] = None) -> dict:
    """
    Lance le backtest complet et retourne un dict de métriques + trades.
    """
    print("[copula] Loading ES & NQ continuous front-month ...")
    es = build_continuous_front_month(cfg.es_path, "ES", exclude_rollover_days=True)
    nq = build_continuous_front_month(cfg.nq_path, "NQ", exclude_rollover_days=True)
    print(f"[copula] ES {len(es):,} rows, NQ {len(nq):,} rows")

    df = _align_and_resample(es, nq, cfg.resample)
    print(f"[copula] Aligned {len(df):,} bars at {cfg.resample}")

    if max_days is not None:
        bars_per_day = pd.Timedelta("1D") / pd.Timedelta(cfg.resample)
        df = df.iloc[: int(max_days * bars_per_day)]
        print(f"[copula] Subset to {len(df):,} bars (max_days={max_days})")

    if len(df) < cfg.lookback + 50:
        raise ValueError(f"Trop peu de bars : {len(df)} < lookback+50")

    # Travailler sur log-prices (stationnaire en différences)
    log_x = np.log(df["es_close"])
    log_y = np.log(df["nq_close"])

    # Hedge ratio : OLS rolling ou fixe
    if cfg.hedge_ratio is None:
        # OLS rolling : log_x = a + beta * log_y
        beta_series = log_x.rolling(cfg.lookback).cov(log_y) / log_y.rolling(cfg.lookback).var()
        beta_series = beta_series.fillna(method="ffill").fillna(1.0)
    else:
        beta_series = pd.Series(cfg.hedge_ratio, index=df.index)

    # Spread
    spread = log_x - beta_series * log_y
    spread.name = "spread"

    # Compute signaux copule sur la SÉRIE DE SPREAD vs log_y (mispricing X vs Y)
    print("[copula] Computing copula signals (rolling) ...")
    sig = compute_mispricing_signal(
        log_x, log_y,
        lookback=cfg.lookback,
        p_high=cfg.p_high, p_low=cfg.p_low,
    )

    # ── Backtest core ─────────────────────────────────────
    trades = []
    pos = 0           # 0 = flat, +1 = long spread, -1 = short spread
    entry_bar = None
    entry_spread = 0.0
    entry_beta = 0.0
    pnl_total = 0.0

    log_x_arr = log_x.to_numpy()
    log_y_arr = log_y.to_numpy()
    spread_arr = spread.to_numpy()
    beta_arr = beta_series.to_numpy()
    cond_arr = sig["conditional_prob"].to_numpy()
    sig_arr = sig["signal"].to_numpy()
    idx = df.index

    for i in range(cfg.lookback, len(df)):
        p = cond_arr[i]
        if np.isnan(p):
            continue

        if pos == 0:
            # Entry
            if sig_arr[i] == 1:
                # X (ES) sous-évalué -> LONG spread = LONG ES, SHORT NQ
                pos = 1
                entry_bar = i
                entry_spread = spread_arr[i]
                entry_beta = beta_arr[i]
            elif sig_arr[i] == -1:
                # X (ES) surévalué -> SHORT spread = SHORT ES, LONG NQ
                pos = -1
                entry_bar = i
                entry_spread = spread_arr[i]
                entry_beta = beta_arr[i]
        else:
            # Check exit
            hold = i - entry_bar
            spread_now = spread_arr[i]
            spread_chg = spread_now - entry_spread
            # PnL : log_x change - beta_entry * log_y change → en log-units
            # Convertir en $$ : exp(log_x_t) * (exp(spread_chg) - 1) approximé
            # Simplification : pnl_pts = pos * (spread_chg * 10000)  (basis points)
            # Plus rigoureusement : pos * (log_x_chg - beta * log_y_chg) * price_avg
            log_x_chg = log_x_arr[i] - log_x_arr[entry_bar]
            log_y_chg = log_y_arr[i] - log_y_arr[entry_bar]
            # PnL en $ : pos * (X * exp(log_x_chg) - X) - pos * beta * (Y * exp(log_y_chg) - Y)
            # Mais X et Y en points, point_value différent
            x_price_entry = np.exp(log_x_arr[entry_bar])
            y_price_entry = np.exp(log_y_arr[entry_bar])
            x_pnl_pts = x_price_entry * (np.exp(log_x_chg) - 1.0)
            y_pnl_pts = y_price_entry * (np.exp(log_y_chg) - 1.0)
            pnl_dollars = pos * (
                x_pnl_pts * cfg.point_value_x
                - entry_beta * y_pnl_pts * cfg.point_value_y
            )

            # Exit conditions
            exit_now = False
            reason = None
            # 1. Conditional prob neutralise
            if abs(p - 0.5) < cfg.exit_neutral_band:
                exit_now = True
                reason = "neutral"
            # 2. Max holding
            elif hold >= cfg.max_hold_bars:
                exit_now = True
                reason = "timeout"
            # 3. SL spread (basis points absolus)
            elif abs(spread_chg) > cfg.sl_spread_pts / 10000.0:
                # En log-units, sl_spread_pts en bps : sl_log = sl_pts/10000
                if pos * spread_chg < -cfg.sl_spread_pts / 10000.0:
                    exit_now = True
                    reason = "sl"

            if exit_now:
                pnl_total += pnl_dollars
                trades.append(dict(
                    entry_ts=idx[entry_bar], exit_ts=idx[i],
                    pos=pos, hold_bars=hold,
                    pnl_dollars=pnl_dollars, exit_reason=reason,
                    entry_spread=entry_spread, exit_spread=spread_now,
                    entry_cond_prob=cond_arr[entry_bar],
                    exit_cond_prob=p,
                ))
                pos = 0
                entry_bar = None

    trades_df = pd.DataFrame(trades)

    # ── Metrics ──────────────────────────────────────────
    n_trades = len(trades_df)
    if n_trades == 0:
        return dict(n_trades=0, pnl=0.0, error="no trades")

    pnl = float(trades_df["pnl_dollars"].sum())
    wins = trades_df.loc[trades_df["pnl_dollars"] > 0, "pnl_dollars"].sum()
    losses = abs(trades_df.loc[trades_df["pnl_dollars"] < 0, "pnl_dollars"].sum())
    pf = float(wins / max(losses, 0.01))
    wr = float((trades_df["pnl_dollars"] > 0).mean() * 100)

    # Daily aggregation for Sharpe
    trades_df["date"] = pd.to_datetime(trades_df["exit_ts"]).dt.date
    daily = trades_df.groupby("date")["pnl_dollars"].sum()
    sharpe = float(daily.mean() / daily.std() * np.sqrt(252)) if daily.std() > 0 else 0.0

    # DD
    eq = np.concatenate([[cfg.capital], cfg.capital + np.cumsum(trades_df["pnl_dollars"].values)])
    peak = np.maximum.accumulate(eq)
    dd = peak - eq
    dd_max = float(dd.max())

    print(f"[copula] DONE — {n_trades} trades, PnL ${pnl:.0f}, "
          f"PF {pf:.2f}, Sharpe {sharpe:.2f}, DD ${dd_max:.0f}")

    return dict(
        n_trades=n_trades,
        pnl=pnl,
        pf=pf,
        wr=wr,
        sharpe=sharpe,
        dd_max=dd_max,
        calmar=float(pnl / dd_max) if dd_max > 0 else 0.0,
        trades_df=trades_df,
    )


if __name__ == "__main__":
    import sys
    cfg = CopulaPairsConfig(
        es_path=r"C:\Users\ryadb\OneDrive\QUANT MATHS\ES 5ANS DATA\glbx-mdp3-20210513-20260512.ohlcv-1m.csv.zst",
        nq_path=r"C:\Users\ryadb\OneDrive\QUANT MATHS\NQ 5ANS DATA\glbx-mdp3-20210513-20260512.ohlcv-1m.csv.zst",
    )
    max_days = int(sys.argv[1]) if len(sys.argv) > 1 else None
    res = run_copula_pairs_backtest(cfg, max_days=max_days)
    print("\n=== COPULA PAIRS BACKTEST RESULTS ===")
    for k, v in res.items():
        if k != "trades_df":
            print(f"  {k}: {v}")
