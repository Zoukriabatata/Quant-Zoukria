"""
Runner v10 — orchestre le backtest Hurst_MR v9 avec 3 hooks Sprint 1.

Hooks injectables (chaque flag activable indépendamment) :
    1. use_jump_filter   -> module jump_detection_lee_mykland
    2. use_har_rv_sizing -> module vol_forecast_har_rv (vol forecast pour sizing)
    3. use_gz_sizing     -> module sizing_grossman_zhou (DD-constrained)

Architecture : on FORK les fonctions pures du v9 (load_csv, build_study_cache,
hurst_rs) pour éviter d'importer backtest_hurst.py (dépendances Streamlit
au top-level). v9 reste 100% intact.

Validation : avec tous les flags OFF (config C0), le résultat doit reproduire
fidèlement le baseline v9.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from quant_v10.modules.jump_detection_lee_mykland import detect_jumps
from quant_v10.modules.vol_forecast_har_rv import (
    compute_realized_volatility,
    forecast_har_rv,
)
from quant_v10.modules.sizing_grossman_zhou import (
    apply_gz_shrinkage,
    grossman_zhou_contracts,
)
from quant_v10.modules.model_cartea_figueroa_mrjd import (
    detect_jumps_in_residuals,
)
from quant_v10.modules.hurst_multifractal_mfdfa import (
    compute_multifractality_width,
)


# ═══════════════════════════════════════════════════════════════════════
# FORK des fonctions pures v9 (sans Streamlit, sans cache)
# Source : backtest_hurst.py (Hurst_MR v9 champion validé 2026-05-12)
# ═══════════════════════════════════════════════════════════════════════

def hurst_rs(ts):
    """Hurst exponent via R/S analysis (fork v9)."""
    ts = np.asarray(ts, dtype=float)
    n = len(ts)
    if n < 20:
        return 0.5
    lags = np.unique(np.round(
        np.exp(np.linspace(np.log(4), np.log(min(n // 2, 50)), 12))
    ).astype(int))
    lags = lags[lags >= 4]
    rs_vals = []
    for lag in lags:
        lag = int(lag)
        n_chunks = n // lag
        if n_chunks < 2:
            continue
        mat = ts[:n_chunks * lag].reshape(n_chunks, lag)
        mean = mat.mean(axis=1, keepdims=True)
        devs = np.cumsum(mat - mean, axis=1)
        R = devs.max(axis=1) - devs.min(axis=1)
        S = mat.std(axis=1, ddof=0)
        mask = S > 0
        if mask.sum() == 0:
            continue
        rs_vals.append(float((R[mask] / S[mask]).mean()))
    if len(rs_vals) < 3:
        return 0.5
    try:
        return float(np.clip(
            np.polyfit(np.log(lags[:len(rs_vals)]), np.log(rs_vals), 1)[0],
            0.0, 1.0,
        ))
    except Exception:
        return 0.5


def load_csv_mnq(path: str):
    """Charge MNQ CSV format Databento (fork v9, sans @st.cache_data)."""
    df = pd.read_csv(path, usecols=["ts_event", "open", "high", "low", "close", "volume", "symbol"])
    df = df[df["symbol"].str.startswith("MNQ") & ~df["symbol"].str.contains("-", na=False)].copy()
    if df.empty:
        raise ValueError("Aucun symbole MNQ trouvé dans le CSV")
    df = df.sort_values("volume", ascending=False).groupby("ts_event", sort=False).first().reset_index()
    df["bar"] = pd.to_datetime(df["ts_event"], utc=True)
    df[["open", "high", "low", "close"]] = df[["open", "high", "low", "close"]].astype(float)
    df["volume"] = df["volume"].fillna(0).astype(int)
    df.sort_values("bar", inplace=True)
    df.drop_duplicates(subset=["bar"], inplace=True)
    df.reset_index(drop=True, inplace=True)
    df["date"] = df["bar"].dt.date
    # Rollover detection (jours de bascule contract front)
    day_sym = df.groupby("date").apply(
        lambda g: g.loc[g["volume"].idxmax(), "symbol"] if len(g) > 0 else None,
        include_groups=False,
    ).reset_index()
    day_sym.columns = ["date", "dominant"]
    day_sym["prev"] = day_sym["dominant"].shift(1)
    day_sym["roll"] = (day_sym["dominant"] != day_sym["prev"]) & day_sym["prev"].notna()
    day_sym["roll"] = (day_sym["roll"] | day_sym["roll"].shift(-1)).fillna(False).astype(bool)
    roll_dates = set(day_sym.loc[day_sym["roll"], "date"].astype(str))
    df["is_roll"] = df["date"].astype(str).isin(roll_dates)
    return df


def _filter_session(df, sh, sm, eh, em):
    t = df["bar"].dt.hour * 60 + df["bar"].dt.minute
    return df[(t >= sh * 60 + sm) & (t < eh * 60 + em)].reset_index(drop=True)


def _resample_bars(bars: pd.DataFrame, freq_minutes: int) -> pd.DataFrame:
    """Resample bars 1-min vers freq_minutes (OHLC aggregation)."""
    if freq_minutes <= 1:
        return bars
    df = bars.copy().set_index("bar")
    agg = df.resample(f"{freq_minutes}min", label="right", closed="right").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last",
         "volume": "sum", "symbol": "last", "date": "last", "is_roll": "any"}
    ).dropna(subset=["close"])
    agg = agg.reset_index()
    return agg


def build_day_cache(csv_path: str, sh=9, sm=30, eh=16, em=0, hwin=50,
                    max_days: Optional[int] = None, freq_minutes: int = 1):
    """
    Construit le cache jour-par-jour avec Hurst rolling pré-calculé.

    Default session : NY 9:30 → 16:00. hwin=50 (HW v9 champion).
    `max_days` : limite optionnelle (utile pour smoke tests).
    `freq_minutes` : 1 pour bars 1-min (default), 5 pour bars 5-min, etc.
    """
    df = load_csv_mnq(csv_path)
    days = {}
    all_days = sorted(df["date"].unique())
    if max_days is not None:
        all_days = all_days[:max_days]
    for day in all_days:
        day_df = df[df["date"] == day]
        if day_df["is_roll"].any():
            continue
        bars = _filter_session(day_df, sh, sm, eh, em)
        if len(bars) < 50:
            continue
        # Resample si demande (e.g. 5-min)
        if freq_minutes > 1:
            bars = _resample_bars(bars, freq_minutes)
            if len(bars) < 20:  # apres resample, on a moins de bars
                continue
        closes = bars["close"].values.astype(float)
        highs = bars["high"].values.astype(float)
        lows = bars["low"].values.astype(float)
        rets = np.diff(np.log(np.maximum(closes, 1e-9)))
        rets = np.concatenate([[0], rets])
        n = len(closes)
        h_full = hurst_rs(closes)
        hurst_arr = np.full(n, np.nan)
        # Sur 5-min, hwin=50 est trop : on a ~78 bars/jour sur 1-min, donc ~16 sur 5-min
        effective_hwin = min(hwin, max(20, n // 3))
        for _i in range(effective_hwin, n):
            hurst_arr[_i] = hurst_rs(rets[_i - effective_hwin: _i])
        days[str(day)] = dict(
            bars=bars, closes=closes, highs=highs, lows=lows,
            rets=rets, hurst=h_full, hurst_arr=hurst_arr,
        )
    return days


# ═══════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class V10Config:
    """Config v10 = config v9 + flags pour les 3 modules Sprint 1."""
    # Params v9 champion (defaults = champion config v9)
    ht: float = 0.58           # Hurst threshold
    hwin: int = 50             # Hurst window
    lb: int = 19               # Lookback bandes
    bk: float = 2.75           # Band k
    sl_m: float = 0.65         # SL multiplier (× std)
    tp_overshoot: float = 0.15 # TP overshoot
    slip: float = 0.5          # Slippage points
    max_td: int = 20           # Max trades / jour (aligne sur NT defaut)
    skip_o: int = 0            # Skip open bars
    skip_c: int = 14           # Skip close bars (14h NY filter)
    halt_monthly_on_bust: bool = False  # NT-aligned : pas de halt mensuel (continuous execution)
    sl_min_pts: float = 5.0    # SL min en points (théorème Leung)
    use_trail: bool = True
    trail_h_thresh: float = 0.51

    # Apex parameters
    capital: float = 50_000
    max_dd: float = 2_000
    daily_lim: float = 1_000
    profit_target: float = 3_000
    risk_pct: float = 0.12     # Kelly v9
    max_contracts: int = 12

    # Session
    sh: int = 9
    sm: int = 30
    eh: int = 16
    em: int = 0

    # ── Hooks v10 ─────────────────────────────────────────
    use_jump_filter: bool = False
    jump_window: int = 156
    jump_alpha: float = 0.01

    use_har_rv_sizing: bool = False
    har_lookback: int = 252

    use_gz_sizing: bool = False
    gz_gamma: float = 2.0
    gz_mu_excess: float = 0.001  # 0.1% par trade (à calibrer)

    # NEW Sprint 2.1 : GZ adaptatif (multiplicateur shrinkage du sizing v9)
    use_gz_adaptive: bool = False

    # NEW Sprint 2.2 : MRJD jump filter sur résidus
    use_mrjd_filter: bool = False
    mrjd_alpha: float = 0.01

    # NEW Sprint 2.3 : MF-DFA multifractality filter (per-day skip si width trop élevé)
    use_mfdfa_filter: bool = False
    mfdfa_width_threshold: float = 0.50  # skip jour si h(-5)-h(5) > seuil

    # === NEW : Mode realiste comme NinjaTrader ===
    use_intrabar_sl_tp: bool = True   # SL/TP declenches sur high/low intra-bar (comme NT)
    commission_rt_per_contract: float = 3.0  # $ round-trip par contrat (Apex/Rithmic MNQ)

    name: str = "C0_baseline"


# ═══════════════════════════════════════════════════════════════════════
# PRÉ-PROCESSING : injecte les outputs des modules dans le day_cache
# ═══════════════════════════════════════════════════════════════════════

def enrich_day_cache(day_cache: dict, cfg: V10Config) -> dict:
    """
    Pour chaque jour, calcule et stocke :
      - jump_flags : array bool de même longueur que closes (Lee-Mykland)
      - har_rv_forecast : float (vol forecast pour le jour, agrège la session)

    Si les flags sont OFF, ces champs restent None (et le runner les ignore).
    """
    # 1. Jump flags : par jour, on calcule LM sur les closes intraday
    if cfg.use_jump_filter:
        for day_key, d in day_cache.items():
            closes_series = pd.Series(d["closes"])
            lm_result = detect_jumps(
                closes_series,
                window=min(cfg.jump_window, max(3, len(closes_series) // 2)),
                alpha=cfg.jump_alpha,
            )
            d["jump_flags"] = lm_result["jump_flag"].to_numpy(dtype=bool)
    else:
        for d in day_cache.values():
            d["jump_flags"] = None

    # 2bis. MF-DFA per-day : on calcule le width multifractality une fois par jour
    if cfg.use_mfdfa_filter:
        for day_key, d in day_cache.items():
            closes_series = pd.Series(d["closes"])
            try:
                width = compute_multifractality_width(
                    closes_series, q_min=-5.0, q_max=5.0, q_step=2.0,
                    s_min=8, s_max=min(len(closes_series) // 4, 80),
                )
            except (ValueError, np.linalg.LinAlgError):
                width = 0.0
            d["mfdfa_width"] = float(width)
            d["mfdfa_skip_day"] = width > cfg.mfdfa_width_threshold
    else:
        for d in day_cache.values():
            d["mfdfa_skip_day"] = False
            d["mfdfa_width"] = None

    # 3. HAR-RV : on a besoin de la time-série de RV quotidienne sur tout l'historique
    if cfg.use_har_rv_sizing or cfg.use_gz_sizing:
        # Construit la série de RV quotidienne à partir des returns intraday
        daily_rv = {}
        for day_key, d in day_cache.items():
            r = d["rets"]
            daily_rv[day_key] = float(np.sum(r[1:] ** 2))  # exclut le premier qui est 0
        rv_series = pd.Series(daily_rv)
        rv_series.index = pd.to_datetime(rv_series.index)
        rv_series = rv_series.sort_index()

        if cfg.use_har_rv_sizing:
            forecast = forecast_har_rv(rv_series, lookback=cfg.har_lookback)
            # On indexe par day_key string pour merge
            forecast.index = forecast.index.strftime("%Y-%m-%d")
            for day_key, d in day_cache.items():
                if day_key in forecast.index:
                    d["har_rv_forecast"] = float(forecast.loc[day_key]) if pd.notna(forecast.loc[day_key]) else None
                else:
                    d["har_rv_forecast"] = None
        else:
            for d in day_cache.values():
                d["har_rv_forecast"] = None
    else:
        for d in day_cache.values():
            d["har_rv_forecast"] = None

    return day_cache


# ═══════════════════════════════════════════════════════════════════════
# BACKTEST CORE (fork v9 + hooks)
# ═══════════════════════════════════════════════════════════════════════

def run_backtest_v10(day_cache: dict, cfg: V10Config):
    """
    Backtest Hurst_MR v9 + hooks v10.
    Source : backtest_hurst.py:run_hurst_backtest (forked unchanged for C0).
    """
    trades = []
    monthly = []
    running = cfg.capital
    peak = cfg.capital
    cur_month = None
    m_trades = []
    busted = passed = False
    days_el = 0

    for day_key in sorted(day_cache):
        dm = day_key[:7]
        if dm != cur_month:
            if cur_month:
                nw = sum(1 for t in m_trades if t["win"])
                nt = len(m_trades)
                monthly.append(dict(
                    mois=cur_month, pnl=running - cfg.capital,
                    trades=nt, wr=nw / nt * 100 if nt else 0,
                    passed=passed, busted=busted,
                ))
                running = cfg.capital
                peak = cfg.capital
                busted = passed = False
                m_trades = []
                days_el = 0
            cur_month = dm

        # NT-aligned : on track bust/pass mais on NE skip PAS le mois (sauf si halt_monthly_on_bust)
        if cfg.halt_monthly_on_bust and (passed or busted):
            continue
        dd_used = max(0., peak - running)
        if dd_used >= cfg.max_dd:
            busted = True
            if cfg.halt_monthly_on_bust:
                continue
        if (running - cfg.capital) >= cfg.profit_target:
            passed = True
        days_el += 1

        d = day_cache[day_key]

        # ── HOOK MF-DFA : skip jour entier si trop multifractal ──
        if cfg.use_mfdfa_filter and d.get("mfdfa_skip_day", False):
            continue

        closes = d["closes"]
        highs  = d["highs"]
        lows   = d["lows"]
        hurst_arr = d["hurst_arr"]
        bars = d["bars"]
        jump_flags = d.get("jump_flags")
        har_forecast = d.get("har_rv_forecast")
        n = len(closes)

        last_exit = -1
        daily_pnl = 0.
        day_td = 0

        for i in range(cfg.lb + cfg.skip_o, n - cfg.skip_c):
            if day_td >= cfg.max_td or daily_pnl <= -cfg.daily_lim:
                break
            if i <= last_exit:
                continue

            # ── HOOK #1 : Jump filter Lee-Mykland ─────────
            if cfg.use_jump_filter and jump_flags is not None and jump_flags[i]:
                continue

            h_bar = hurst_arr[i] if i < len(hurst_arr) else np.nan
            if np.isnan(h_bar) or h_bar >= cfg.ht:
                continue

            w = closes[i - cfg.lb: i]
            mid = w.mean()
            std = w.std()
            if std == 0:
                continue
            price = closes[i]
            z = (price - mid) / std
            if abs(z) < cfg.bk:
                continue

            # ── HOOK MRJD : skip si jump détecté dans la série des résidus ──
            if cfg.use_mrjd_filter and i >= cfg.lb + 30:
                # Construit série de résidus locaux : r[j] = close[j] - mean(close[j-lb:j])
                # sur fenêtre récente [i-30, i-1] (30 résidus pour AR(1) calibration)
                residual_history = np.array([
                    closes[j] - closes[j - cfg.lb: j].mean()
                    for j in range(i - 30, i)
                ])
                try:
                    flags = detect_jumps_in_residuals(
                        pd.Series(residual_history), alpha=cfg.mrjd_alpha,
                    )
                    if bool(flags.iloc[-1]):
                        continue
                except Exception:
                    pass

            direction = "short" if z > 0 else "long"
            sl_pts = max(cfg.sl_min_pts, cfg.sl_m * std)
            sl_pts = min(sl_pts, 20.0)
            tp_price = mid + cfg.tp_overshoot * std if direction == "long" else mid - cfg.tp_overshoot * std

            # ── HOOK #2/#3 : Sizing ────────────────────────
            if cfg.use_gz_sizing:
                # Grossman-Zhou avec sigma2 = HAR forecast si dispo, sinon std²
                sigma2 = har_forecast if (cfg.use_har_rv_sizing and har_forecast is not None) else (std / price) ** 2
                if sigma2 is None or sigma2 <= 0:
                    sigma2 = max((std / price) ** 2, 1e-8)
                contracts = grossman_zhou_contracts(
                    equity=running, hwm=peak, max_dd_dollars=cfg.max_dd,
                    mu_excess=cfg.gz_mu_excess, sigma2=sigma2, gamma=cfg.gz_gamma,
                    point_value=2.0, sl_points=sl_pts, max_contracts=cfg.max_contracts,
                )
            else:
                # Sizing v9 original (Kelly DD-restant)
                dd_rem = max(0., cfg.max_dd - dd_used)
                risk = max(50., min(cfg.risk_pct * dd_rem, cfg.daily_lim * 0.40))
                lpc = sl_pts * 2.0
                if lpc <= 0:
                    continue
                contracts = min(cfg.max_contracts, int(risk / lpc))
                budget_rem = max(0., cfg.daily_lim + daily_pnl)
                contracts = min(contracts, int(budget_rem / lpc))

            # ── HOOK #3bis : GZ adaptatif (shrinkage multiplicatif) ──
            if cfg.use_gz_adaptive:
                contracts = apply_gz_shrinkage(
                    baseline_contracts=contracts,
                    equity=running, hwm=peak,
                    max_dd_dollars=cfg.max_dd,
                )

            if contracts <= 0:
                continue

            # ── Simulation trade (MODE INTRABAR realiste comme NinjaTrader) ──
            result_pts = 0.0
            exit_bar = i
            hit = False
            trail_active = False
            trail_stop = None
            # En mode intrabar : SL/TP triggered par high/low de la bar
            # En mode close : ancien comportement (Python original)
            for j in range(i + 1, min(n, i + 120)):
                c = closes[j]
                hi = highs[j] if cfg.use_intrabar_sl_tp else c
                lo = lows[j]  if cfg.use_intrabar_sl_tp else c
                if cfg.use_trail and j >= cfg.lb:
                    w_j = closes[j - cfg.lb: j]
                    mid_j = w_j.mean()
                    std_j = w_j.std() if w_j.std() > 1e-9 else std
                    h_j = hurst_arr[j] if j < len(hurst_arr) else np.nan
                else:
                    mid_j = mid
                    std_j = std
                    h_j = np.nan

                if not trail_active:
                    # SL : declenche sur LOW (long) ou HIGH (short) en intrabar
                    if direction == "long":
                        sl_price_lvl = price - sl_pts
                        if lo <= sl_price_lvl:
                            result_pts = -sl_pts - cfg.slip
                            exit_bar = j
                            hit = True
                            break
                    else:
                        sl_price_lvl = price + sl_pts
                        if hi >= sl_price_lvl:
                            result_pts = -sl_pts - cfg.slip
                            exit_bar = j
                            hit = True
                            break

                    if cfg.use_trail:
                        fv_crossed = (direction == "long" and c > mid_j) or \
                                     (direction == "short" and c < mid_j)
                        h_trend = not np.isnan(h_j) and h_j > cfg.trail_h_thresh
                        if fv_crossed and h_trend:
                            trail_active = True
                            trail_stop = mid_j
                        else:
                            # TP : declenche sur HIGH (long) ou LOW (short) en intrabar
                            if direction == "long" and hi >= tp_price:
                                result_pts = (tp_price - price) - cfg.slip
                                exit_bar = j
                                hit = True
                                break
                            elif direction == "short" and lo <= tp_price:
                                result_pts = (price - tp_price) - cfg.slip
                                exit_bar = j
                                hit = True
                                break
                    else:
                        if direction == "long" and hi >= tp_price:
                            result_pts = (tp_price - price) - cfg.slip
                            exit_bar = j
                            hit = True
                            break
                        elif direction == "short" and lo <= tp_price:
                            result_pts = (price - tp_price) - cfg.slip
                            exit_bar = j
                            hit = True
                            break
                else:  # trail actif
                    z_j = (c - mid_j) / std_j if std_j > 0 else 0.0
                    if direction == "long":
                        if mid_j > trail_stop:
                            trail_stop = mid_j
                        # Trail stop : declenche sur LOW intrabar (comme NT)
                        if lo <= trail_stop:
                            result_pts = (trail_stop - price) - cfg.slip
                            exit_bar = j
                            hit = True
                            break
                        if z_j >= 3.0:
                            result_pts = (c - price) - cfg.slip
                            exit_bar = j
                            hit = True
                            break
                        if not np.isnan(h_j) and h_j > cfg.ht and z_j >= 2.5:
                            result_pts = (c - price) - cfg.slip
                            exit_bar = j
                            hit = True
                            break
                    else:
                        if mid_j < trail_stop:
                            trail_stop = mid_j
                        # Trail stop : declenche sur HIGH intrabar (comme NT)
                        if hi >= trail_stop:
                            result_pts = (price - trail_stop) - cfg.slip
                            exit_bar = j
                            hit = True
                            break
                        if z_j <= -3.0:
                            result_pts = (price - c) - cfg.slip
                            exit_bar = j
                            hit = True
                            break
                        if not np.isnan(h_j) and h_j > cfg.ht and z_j <= -2.5:
                            result_pts = (price - c) - cfg.slip
                            exit_bar = j
                            hit = True
                            break

            if not hit:
                exit_bar = min(n - 1, i + 120)
                c_exit = closes[exit_bar]
                if direction == "long":
                    if trail_active and trail_stop is not None:
                        result_pts = (trail_stop - price) - cfg.slip
                    else:
                        result_pts = (c_exit - price) - cfg.slip
                else:
                    if trail_active and trail_stop is not None:
                        result_pts = (price - trail_stop) - cfg.slip
                    else:
                        result_pts = (price - c_exit) - cfg.slip

            # PnL avec commission (round-trip par contrat) — comme NT realiste
            pnl_brut = result_pts * 2.0 * contracts
            commission = cfg.commission_rt_per_contract * contracts
            pnl = pnl_brut - commission
            running += pnl
            daily_pnl += pnl
            day_td += 1
            if running > peak:
                peak = running
            last_exit = exit_bar
            win = pnl > 0

            hour = bars["bar"].iloc[i].hour
            dow = bars["bar"].iloc[i].dayofweek
            trades.append(dict(
                date=str(day_key), win=win, pnl=pnl, pnl_brut=pnl_brut, commission=commission,
                pts=result_pts, contracts=contracts,
                z=z, std=std, price=price, mid=mid,
                direction=direction, hurst=float(h_bar),
                hour=hour, dow=dow,
            ))
            m_trades.append(dict(win=win, pnl=pnl))

    # Flush dernier mois
    if cur_month and m_trades:
        nw = sum(1 for t in m_trades if t["win"])
        nt = len(m_trades)
        monthly.append(dict(
            mois=cur_month, pnl=running - cfg.capital,
            trades=nt, wr=nw / nt * 100 if nt else 0,
            passed=passed, busted=busted,
        ))

    return pd.DataFrame(trades), pd.DataFrame(monthly)


# ═══════════════════════════════════════════════════════════════════════
# METRICS
# ═══════════════════════════════════════════════════════════════════════

def compute_metrics(trades_df: pd.DataFrame, monthly_df: pd.DataFrame,
                    capital: float = 50_000.0) -> dict:
    """
    Métriques alignées EXACTEMENT sur la définition v9 (backtest_hurst.py:430-442) :
      - Sharpe sur PnL agrégé QUOTIDIENNEMENT (pas per-trade)
      - DD global en % du capital initial
      - PF, WR identiques v9

    Ajoute métriques Apex-spécifiques :
      - dd_max_intramonth_dollars : pire DD intra-mois (ce que Apex surveille)
      - n_busted_months : nombre de mois ayant atteint $2k DD
      - n_passed_months : nombre de mois ayant atteint le target $3k
    """
    if trades_df.empty:
        return dict(
            pnl=0.0, n_trades=0, wr=0.0, pf=0.0, sharpe=0.0,
            dd_max_dollars=0.0, dd_max_pct=0.0, calmar=0.0,
            dd_max_intramonth_dollars=0.0,
            n_months=0, pct_months_pos=0.0,
            n_busted_months=0, n_passed_months=0,
        )

    # ── Métriques globales (v9 formulae) ───────────────────
    pnl = float(trades_df["pnl"].sum())
    n = len(trades_df)
    wr = float((trades_df["pnl"] > 0).mean() * 100)

    wins = trades_df.loc[trades_df["pnl"] > 0, "pnl"].sum()
    losses = abs(trades_df.loc[trades_df["pnl"] < 0, "pnl"].sum())
    pf = float(wins / max(losses, 0.01))

    # Sharpe : DAILY aggregation (v9 line 441-442)
    daily = trades_df.groupby("date")["pnl"].sum()
    sharpe = float(daily.mean() / daily.std() * np.sqrt(252)) if daily.std() > 0 else 0.0

    # Drawdown global sur equity continue (v9 line 437-440)
    eq = np.concatenate([[capital], np.cumsum(trades_df["pnl"].values) + capital])
    peak = np.maximum.accumulate(eq)
    dd_dollars = peak - eq
    dd_max_dollars = float(dd_dollars.max())
    dd_max_pct = float((dd_dollars / capital * 100).max())
    calmar = float(pnl / dd_max_dollars) if dd_max_dollars > 0 else 0.0

    # ── DD intra-mois (vrai métrique Apex) ─────────────────
    # Pour chaque mois, recompute equity intra-mois et son DD
    trades_df = trades_df.copy()
    trades_df["month"] = trades_df["date"].str[:7]
    intramonth_dds = []
    for month, grp in trades_df.groupby("month"):
        eq_m = np.concatenate([[capital], capital + np.cumsum(grp["pnl"].values)])
        peak_m = np.maximum.accumulate(eq_m)
        dd_m = (peak_m - eq_m).max()
        intramonth_dds.append(dd_m)
    dd_max_intramonth = float(max(intramonth_dds)) if intramonth_dds else 0.0

    # ── Métriques mensuelles ───────────────────────────────
    n_months = len(monthly_df) if not monthly_df.empty else 0
    pct_months_pos = float((monthly_df["pnl"] > 0).mean() * 100) if n_months > 0 else 0.0
    n_busted = int(monthly_df["busted"].sum()) if "busted" in monthly_df.columns else 0
    n_passed = int(monthly_df["passed"].sum()) if "passed" in monthly_df.columns else 0

    return dict(
        pnl=pnl, n_trades=n, wr=wr, pf=pf, sharpe=sharpe,
        dd_max_dollars=dd_max_dollars, dd_max_pct=dd_max_pct,
        dd_max_intramonth_dollars=dd_max_intramonth,
        calmar=calmar,
        n_months=n_months, pct_months_pos=pct_months_pos,
        n_busted_months=n_busted, n_passed_months=n_passed,
    )


# ═══════════════════════════════════════════════════════════════════════
# CONFIG MATRIX SPRINT 1
# ═══════════════════════════════════════════════════════════════════════

def build_sprint1_configs():
    """7 configs : C0 baseline + 4 mono-hooks + 2 combos + full."""
    return [
        V10Config(name="C0_baseline"),
        V10Config(name="C1_jump_filter", use_jump_filter=True),
        V10Config(name="C2_har_sizing", use_har_rv_sizing=True, use_gz_sizing=True),
        V10Config(name="C3_gz_only", use_gz_sizing=True),
        V10Config(name="C6_jump_plus_har_gz",
                  use_jump_filter=True, use_har_rv_sizing=True, use_gz_sizing=True),
        V10Config(name="C7_jump_plus_gz",
                  use_jump_filter=True, use_gz_sizing=True),
        V10Config(name="C_S1_full",
                  use_jump_filter=True, use_har_rv_sizing=True, use_gz_sizing=True),
    ]


def build_sprint2_configs():
    """Sprint 2 configs : focus GZ adaptatif + combos avec jump filter."""
    return [
        V10Config(name="C0_baseline"),
        V10Config(name="C1_jump_filter", use_jump_filter=True),     # rappel S1 winner
        V10Config(name="C_GZadapt_only", use_gz_adaptive=True),
        V10Config(name="C_jump_GZadapt",
                  use_jump_filter=True, use_gz_adaptive=True),
    ]


def build_sprint2_full_configs():
    """Sprint 2 matrix complète : 8 configs incluant MRJD et MF-DFA."""
    return [
        V10Config(name="C0_baseline"),
        V10Config(name="C1_jump_LM", use_jump_filter=True),
        V10Config(name="C_GZadapt", use_gz_adaptive=True),
        V10Config(name="C_MRJD", use_mrjd_filter=True),
        V10Config(name="C_MFDFA", use_mfdfa_filter=True),
        V10Config(name="C_jump_GZadapt",
                  use_jump_filter=True, use_gz_adaptive=True),
        V10Config(name="C_jump_MRJD",
                  use_jump_filter=True, use_mrjd_filter=True),
        V10Config(name="C_S2_ALL",
                  use_jump_filter=True, use_gz_adaptive=True,
                  use_mrjd_filter=True, use_mfdfa_filter=True),
    ]


def run_sprint1_matrix(csv_path: str, configs: Optional[list] = None,
                       max_days: Optional[int] = None,
                       freq_minutes: int = 1) -> pd.DataFrame:
    """Lance toutes les configs Sprint 1 sur le MNQ CSV et retourne une table de ranking.

    `max_days` : utile pour smoke test sur sous-échantillon (ex: 30 derniers jours).
    `freq_minutes` : 1 (default) ou 5 pour bars 5-min (moins de wicks).
    """
    if configs is None:
        configs = build_sprint1_configs()

    # Construit le day_cache UNE SEULE FOIS (partagé entre configs)
    print(f"[runner_v10] Loading & building day_cache from {csv_path} (freq={freq_minutes}min) ...")
    day_cache_base = build_day_cache(
        csv_path, sh=9, sm=30, eh=16, em=0, hwin=50, max_days=max_days,
        freq_minutes=freq_minutes,
    )
    print(f"[runner_v10] {len(day_cache_base)} jours dans le cache.")

    rows = []
    for cfg in configs:
        print(f"[runner_v10] Running config: {cfg.name} ...")
        # Deep-copy minimal du cache (on n'écrit que des champs nouveaux)
        day_cache = {k: dict(v) for k, v in day_cache_base.items()}
        day_cache = enrich_day_cache(day_cache, cfg)
        trades_df, monthly_df = run_backtest_v10(day_cache, cfg)
        metrics = compute_metrics(trades_df, monthly_df, capital=cfg.capital)
        metrics["config"] = cfg.name
        rows.append(metrics)
        print(f"  -> {cfg.name}: PnL=${metrics['pnl']:.0f} PF={metrics['pf']:.2f} "
              f"Sharpe={metrics['sharpe']:.2f} DD_glob=${metrics['dd_max_dollars']:.0f} "
              f"DD_intramonth=${metrics['dd_max_intramonth_dollars']:.0f} "
              f"Trades={metrics['n_trades']} %M+={metrics['pct_months_pos']:.1f}% "
              f"Bust={metrics['n_busted_months']} Pass={metrics['n_passed_months']}")

    return pd.DataFrame(rows).set_index("config")


if __name__ == "__main__":
    import sys
    csv_path = sys.argv[1] if len(sys.argv) > 1 else os.environ.get(
        "MNQ_CSV",
        r"C:\Users\ryadb\Downloads\5 ANS DATA MNQ OHLCV M1\glbx-mdp3-20210405-20260404.ohlcv-1m.csv",
    )
    df = run_sprint1_matrix(csv_path)
    print("\n=== Sprint 1 Multi-Backtest Ranking ===")
    print(df.to_string())
