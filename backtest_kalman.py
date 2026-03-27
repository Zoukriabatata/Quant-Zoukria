"""
Backtest Kalman OU Mean Reversion — MNQ
Databento tick data → GARCH regime → Kalman fair value → OU bands
→ Entry quand prix hors bande → TP = retour au fair value → SL = ATR
→ 1 trade/session max → Kelly sizing → Apex protection
"""

import glob
import os
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ── Theme ────────────────────────────────────────────────────────────
DARK = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(17,17,17,1)",
    font=dict(color="#e0e0e0", size=13),
    margin=dict(t=50, b=40, l=50, r=30),
)
CYAN, MAGENTA, GREEN, RED = "#00e5ff", "#ff00e5", "#00ff88", "#ff3366"
YELLOW, ORANGE = "#ffd600", "#ff9100"

st.set_page_config(page_title="Backtest Kalman OU", page_icon="KO", layout="wide")
st.title("Backtest Kalman OU Mean Reversion — MNQ")

# ── Sidebar ──────────────────────────────────────────────────────────
st.sidebar.header("Donnees")
data_dir = st.sidebar.text_input(
    "Dossier CSV Databento",
    value=r"C:\Users\ryadb\Downloads\GLBX-20260327-P8LBCQVG8R"
)
bar_seconds = st.sidebar.selectbox("Barre (secondes)", [30, 60, 120, 300], index=1)

st.sidebar.markdown("---")
st.sidebar.header("Kalman OU")
kalman_lookback = st.sidebar.number_input("Lookback calibration (barres)", value=120, min_value=30, step=10)
band_k = st.sidebar.number_input("Bande k (x sigma_stat)", value=1.0, min_value=0.3, max_value=3.0, step=0.1,
                                  help="Entry quand prix depasse fair_value ± k × sigma_stat")
kalman_R_mult = st.sidebar.number_input("Kalman R multiplier", value=5.0, min_value=0.5, step=0.5,
                                         help="Confiance modele vs data. Plus haut = plus lisse")

st.sidebar.markdown("---")
st.sidebar.header("GARCH Regime")
garch_alpha1 = st.sidebar.number_input("GARCH alpha1", value=0.12, step=0.01, format="%.2f")
garch_beta1 = st.sidebar.number_input("GARCH beta1", value=0.85, step=0.01, format="%.2f")

st.sidebar.markdown("---")
st.sidebar.header("Risk (ATR)")
atr_sl_mult = st.sidebar.number_input("SL = ATR x", value=1.5, step=0.1)
max_sl_pts = st.sidebar.number_input("SL max (pts)", value=15.0, step=1.0)
min_sl_pts = st.sidebar.number_input("SL min (pts)", value=5.0, step=0.5)

st.sidebar.markdown("---")
st.sidebar.header("Realisme")
slippage_ticks = st.sidebar.number_input("Slippage (ticks)", value=2, min_value=0, step=1)

st.sidebar.markdown("---")
st.sidebar.header("Session")
session_start_h = st.sidebar.number_input("Debut (h UTC)", value=14, min_value=0, max_value=23)
session_start_m = st.sidebar.number_input("Debut (min)", value=30, min_value=0, max_value=59)
session_end_h = st.sidebar.number_input("Fin (h UTC)", value=21, min_value=0, max_value=23)
session_end_m = st.sidebar.number_input("Fin (min)", value=0, min_value=0, max_value=59)

st.sidebar.markdown("---")
st.sidebar.header("Challenge Apex")
capital_initial = st.sidebar.number_input("Capital ($)", value=50000, step=1000)
max_drawdown_dollars = st.sidebar.number_input("Max DD Apex ($)", value=2000, step=100)
daily_loss_limit = st.sidebar.number_input("Perte max/jour ($)", value=400, step=50)
max_contracts = st.sidebar.number_input("Contracts max", value=2, min_value=1, step=1)
risk_pct = st.sidebar.number_input("Risque/trade (%)", value=0.5, min_value=0.1, step=0.1)
dd_safety_pct = st.sidebar.number_input("Stop trading a X% du DD max", value=75, min_value=50, step=5)

TICK_VALUE = 0.50
TICK_SIZE = 0.25
DOLLAR_PER_PT = TICK_VALUE / TICK_SIZE  # $2/pt MNQ
DD_SAFETY_LIMIT = max_drawdown_dollars * (dd_safety_pct / 100)


# ══════════════════════════════════════════════════════════════════════
# ENGINE
# ══════════════════════════════════════════════════════════════════════

def load_single_day(filepath, start_h, start_m, end_h, end_m):
    """Charge un fichier, filtre session."""
    df = pd.read_csv(filepath, usecols=["ts_event", "side", "price", "size"])
    df["ts"] = pd.to_datetime(df["ts_event"], utc=True)
    df["price"] = df["price"].astype(float)
    df["size"] = df["size"].astype(int)
    df.drop(columns=["ts_event"], inplace=True)
    t_min = df["ts"].dt.hour * 60 + df["ts"].dt.minute
    mask = (t_min >= start_h * 60 + start_m) & (t_min < end_h * 60 + end_m)
    return df[mask].sort_values("ts").reset_index(drop=True)


def build_bars(df, freq_seconds):
    """Ticks → barres OHLCV + ATR + delta."""
    df = df.copy()
    df["bar"] = df["ts"].dt.floor(f"{freq_seconds}s")
    df["buy_vol"] = np.where(df["side"] == "B", df["size"], 0)
    df["sell_vol"] = np.where(df["side"] == "A", df["size"], 0)

    bars = df.groupby("bar").agg(
        open=("price", "first"),
        high=("price", "max"),
        low=("price", "min"),
        close=("price", "last"),
        volume=("size", "sum"),
        buy_volume=("buy_vol", "sum"),
        sell_volume=("sell_vol", "sum"),
    ).reset_index()

    bars["delta"] = bars["buy_volume"] - bars["sell_volume"]
    bars["cvd"] = bars["delta"].cumsum()
    bars["tr"] = np.maximum(
        bars["high"] - bars["low"],
        np.maximum(
            abs(bars["high"] - bars["close"].shift(1)),
            abs(bars["low"] - bars["close"].shift(1))
        )
    )
    bars["atr_14"] = bars["tr"].rolling(14, min_periods=1).mean()
    bars["returns"] = bars["close"].pct_change().fillna(0)
    bars["date"] = bars["bar"].dt.date
    return bars


def compute_garch_vol(returns, alpha1=0.12, beta1=0.85):
    """GARCH(1,1) volatility."""
    alpha0 = 0.00001
    n = len(returns)
    sigma2 = np.zeros(n)
    sigma2[0] = alpha0 / max(1 - alpha1 - beta1, 0.01)
    for t in range(1, n):
        sigma2[t] = alpha0 + alpha1 * returns[t - 1] ** 2 + beta1 * sigma2[t - 1]
    return np.sqrt(sigma2)


def classify_regime(garch_vol, window=60):
    """LOW / MED / HIGH vol regime."""
    regimes = np.full(len(garch_vol), 1)
    for i in range(window, len(garch_vol)):
        history = garch_vol[max(0, i - window):i]
        p33 = np.percentile(history, 33)
        p67 = np.percentile(history, 67)
        if garch_vol[i] < p33:
            regimes[i] = 0
        elif garch_vol[i] > p67:
            regimes[i] = 2
        else:
            regimes[i] = 1
    return regimes


def kalman_ou_filter(prices, lookback, R_mult=5.0):
    """
    Kalman filter sur un modele OU (Ornstein-Uhlenbeck).
    Ref: Quant Guild #92 + #95

    Retourne pour chaque barre:
    - fair_value: estimation Kalman du prix moyen
    - sigma_stat: deviation stationnaire (bandes de reversion)
    - kalman_gain: K du filtre
    """
    n = len(prices)
    fair_values = np.full(n, np.nan)
    sigma_stats = np.full(n, np.nan)
    kalman_gains = np.full(n, np.nan)

    for i in range(lookback, n):
        window = prices[max(0, i - lookback):i]

        # Calibration AR(1): X_t = phi * X_{t-1} + c + eps
        x_prev = window[:-1]
        x_curr = window[1:]
        m = len(x_prev)

        if np.std(x_prev) < 1e-10 or m < 10:
            fair_values[i] = prices[i]
            sigma_stats[i] = 5.0
            kalman_gains[i] = 0.5
            continue

        sx = np.sum(x_prev)
        sy = np.sum(x_curr)
        sxx = np.sum(x_prev ** 2)
        sxy = np.sum(x_prev * x_curr)
        denom = m * sxx - sx * sx

        if abs(denom) < 1e-10:
            fair_values[i] = prices[i]
            sigma_stats[i] = 5.0
            kalman_gains[i] = 0.5
            continue

        phi = np.clip((m * sxy - sx * sy) / denom, 0.5, 0.999)
        c = (sy - phi * sx) / m
        mu = c / (1 - phi) if abs(1 - phi) > 1e-6 else np.mean(window)
        residuals = x_curr - (phi * x_prev + c)
        sigma = np.std(residuals)
        if sigma < 1e-10:
            sigma = 1.0

        # Sigma stationnaire
        sigma_stat = sigma / np.sqrt(max(2 * (1 - phi), 0.001))

        # Kalman filter
        Q = sigma ** 2 * (1 - phi ** 2)
        R = sigma ** 2 * R_mult

        x_est = window[0]
        P = sigma_stat ** 2

        for obs in window:
            x_pred = phi * x_est + (1 - phi) * mu
            P_pred = phi ** 2 * P + Q
            K = P_pred / (P_pred + R)
            x_est = x_pred + K * (obs - x_pred)
            P = (1 - K) * P_pred

        fair_values[i] = x_est
        sigma_stats[i] = sigma_stat
        kalman_gains[i] = K

    return fair_values, sigma_stats, kalman_gains


def find_signals(bars, fair_values, sigma_stats, regimes, band_k):
    """
    Genere les signaux d'entree:
    - LONG  quand close < fair_value - k * sigma_stat (prix trop bas)
    - SHORT quand close > fair_value + k * sigma_stat (prix trop haut)
    - Pas de signal en regime HIGH vol
    - 1 signal max par session (le premier qui declenche)
    """
    n = len(bars)
    signals = []
    traded_today = set()

    for i in range(n):
        if np.isnan(fair_values[i]) or np.isnan(sigma_stats[i]):
            continue

        date = bars.iloc[i]["date"]
        if date in traded_today:
            continue

        # Pas de trade en HIGH vol
        if regimes[i] == 2:
            continue

        close = bars.iloc[i]["close"]
        fv = fair_values[i]
        ss = sigma_stats[i]
        upper = fv + band_k * ss
        lower = fv - band_k * ss

        direction = None
        if close > upper:
            direction = "short"  # prix trop haut, va revenir
        elif close < lower:
            direction = "long"   # prix trop bas, va revenir

        if direction:
            traded_today.add(date)
            signals.append({
                "bar_idx": i,
                "date": date,
                "bar": bars.iloc[i]["bar"],
                "price": close,
                "fair_value": fv,
                "sigma_stat": ss,
                "direction": direction,
                "deviation": abs(close - fv) / ss,  # combien de sigma hors bande
                "regime": regimes[i],
            })

    return signals


def simulate_trade(bars, entry_idx, entry_price, direction, sl_pts, tp_price, slip_pts):
    """
    Simule un trade:
    - Entry au prix avec slippage
    - TP = retour au fair value Kalman
    - SL = ATR-based
    - Max 120 barres
    """
    if direction == "long":
        real_entry = entry_price + slip_pts
        sl_price = real_entry - sl_pts
    else:
        real_entry = entry_price - slip_pts
        sl_price = real_entry + sl_pts

    for i in range(entry_idx + 1, min(entry_idx + 120, len(bars))):
        bar = bars.iloc[i]

        if direction == "long":
            if bar["low"] <= sl_price:
                return -(sl_pts + slip_pts)  # SL touche
            if bar["high"] >= tp_price:
                return (tp_price - slip_pts) - real_entry  # TP touche
        else:
            if bar["high"] >= sl_price:
                return -(sl_pts + slip_pts)
            if bar["low"] <= tp_price:
                return real_entry - (tp_price + slip_pts)

    # Timeout → close at market
    last = bars.iloc[min(entry_idx + 119, len(bars) - 1)]["close"]
    if direction == "long":
        return (last - slip_pts) - real_entry
    else:
        return real_entry - (last + slip_pts)


def kelly_fraction(results):
    """Kelly et demi-Kelly."""
    wins = results[results > 0]
    losses = results[results < 0]
    if len(wins) == 0 or len(losses) == 0:
        return 0, 0
    p = len(wins) / len(results)
    b = wins.mean() / abs(losses.mean())
    k = (p * b - (1 - p)) / b
    return max(0, k), max(0, k / 2)


# ══════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════

if st.sidebar.button("Lancer le Backtest", type="primary"):
    files = sorted(glob.glob(os.path.join(data_dir, "*.trades.csv")))
    if not files:
        st.error("Aucun fichier .trades.csv trouve.")
        st.stop()

    st.info(f"{len(files)} fichiers. Pipeline: GARCH regime → Kalman OU → Bandes → 1 trade/session")
    progress = st.progress(0)

    all_trades = []
    all_daily_stats = []
    skipped_high_vol = 0
    skipped_no_signal = 0
    skipped_dd = 0
    running_equity = capital_initial
    running_peak = capital_initial
    challenge_busted = False
    slip = slippage_ticks * TICK_SIZE

    for file_idx, filepath in enumerate(files):
        progress.progress((file_idx + 1) / len(files),
                          text=f"Jour {file_idx + 1}/{len(files)}")

        # Protection DD
        running_dd = running_peak - running_equity
        if running_dd >= max_drawdown_dollars:
            challenge_busted = True
            break
        if running_dd >= DD_SAFETY_LIMIT:
            skipped_dd += 1
            continue

        # 1. Charger
        ticks = load_single_day(filepath, session_start_h, session_start_m,
                                session_end_h, session_end_m)
        if len(ticks) < 100:
            skipped_no_signal += 1
            continue

        # 2. Barres
        bars = build_bars(ticks, bar_seconds)
        del ticks
        if len(bars) < kalman_lookback + 20:
            skipped_no_signal += 1
            continue

        # 3. GARCH regime
        garch_vol = compute_garch_vol(bars["returns"].values, garch_alpha1, garch_beta1)
        regimes = classify_regime(garch_vol)

        # Regime dominant
        regime_counts = np.bincount(regimes, minlength=3)
        dominant_regime = regime_counts.argmax()
        if dominant_regime == 2:
            skipped_high_vol += 1
            all_daily_stats.append({
                "date": bars.iloc[0]["date"], "regime": "HIGH",
                "action": "SKIP", "reason": "Regime HIGH vol",
            })
            continue

        # 4. Kalman OU filter
        prices = bars["close"].values
        fair_values, sigma_stats, k_gains = kalman_ou_filter(
            prices, kalman_lookback, kalman_R_mult
        )

        # 5. Signaux
        signals = find_signals(bars, fair_values, sigma_stats, regimes, band_k)

        if not signals:
            skipped_no_signal += 1
            all_daily_stats.append({
                "date": bars.iloc[0]["date"],
                "regime": ["LOW", "MED", "HIGH"][dominant_regime],
                "action": "SKIP", "reason": "Pas de signal (prix dans les bandes)",
            })
            continue

        # 6. Prendre le premier signal (1 trade/session)
        sig = signals[0]
        bar_idx = sig["bar_idx"]

        # 7. SL dynamique ATR
        atr = bars.iloc[bar_idx]["atr_14"]
        if np.isnan(atr) or atr <= 0:
            atr = bars["tr"].mean()
        if np.isnan(atr) or atr <= 0:
            atr = 8.0
        sl_pts = np.clip(atr * atr_sl_mult, min_sl_pts, max_sl_pts)

        # 8. TP = retour au fair value Kalman
        tp_price = sig["fair_value"]

        # 9. Sizing Apex-safe
        regime_mult = 0.75 if sig["regime"] == 0 else 1.0
        risk_dollars = capital_initial * (risk_pct / 100) * regime_mult
        contracts = max(1, int(risk_dollars / (sl_pts * DOLLAR_PER_PT)))
        contracts = min(contracts, max_contracts)

        loss_if_sl = sl_pts * DOLLAR_PER_PT * contracts
        if loss_if_sl > daily_loss_limit:
            contracts = max(1, int(daily_loss_limit / (sl_pts * DOLLAR_PER_PT)))
        remaining_dd = max_drawdown_dollars - running_dd
        if loss_if_sl > remaining_dd * 0.5:
            contracts = 1

        # 10. Simuler
        result_pts = simulate_trade(bars, bar_idx, sig["price"],
                                     sig["direction"], sl_pts, tp_price, slip)

        pnl_dollars = result_pts * DOLLAR_PER_PT * contracts
        running_equity += pnl_dollars
        if running_equity > running_peak:
            running_peak = running_equity

        tp_pts = abs(sig["fair_value"] - sig["price"])
        rr_target = tp_pts / sl_pts if sl_pts > 0 else 0

        trade = {
            "date": sig["date"],
            "time": sig["bar"],
            "price": round(sig["price"], 2),
            "fair_value": round(sig["fair_value"], 2),
            "sigma_stat": round(sig["sigma_stat"], 2),
            "deviation": round(sig["deviation"], 2),
            "direction": sig["direction"],
            "regime": ["LOW", "MED", "HIGH"][sig["regime"]],
            "sl_pts": round(sl_pts, 2),
            "tp_pts": round(tp_pts, 2),
            "rr_target": round(rr_target, 1),
            "result_pts": round(result_pts, 2),
            "contracts": contracts,
            "pnl_dollars": round(pnl_dollars, 2),
            "win": result_pts > 0,
            "equity": round(running_equity, 2),
            "dd_from_peak": round(running_peak - running_equity, 2),
        }
        all_trades.append(trade)

        all_daily_stats.append({
            "date": sig["date"],
            "regime": trade["regime"],
            "action": "TRADE",
            "reason": f"{sig['direction']} @ {sig['price']:.2f}, "
                      f"FV={sig['fair_value']:.2f}, dev={sig['deviation']:.1f}σ",
        })

    progress.empty()

    # ══════════════════════════════════════════════════════════════════
    # RESULTATS
    # ══════════════════════════════════════════════════════════════════

    if not all_trades:
        st.warning("Aucun trade. Baisse k (bande) ou le lookback.")
        st.stop()

    trades_df = pd.DataFrame(all_trades)
    daily_df = pd.DataFrame(all_daily_stats)

    # Challenge Apex
    st.markdown("---")
    if challenge_busted:
        st.error(f"**CHALLENGE BUST** — DD >= ${max_drawdown_dollars}")
    else:
        max_dd_actual = trades_df["dd_from_peak"].max()
        dd_pct = max_dd_actual / max_drawdown_dollars * 100
        st.subheader("Challenge Apex")
        ca1, ca2, ca3, ca4 = st.columns(4)
        ca1.metric("DD max autorise", f"${max_drawdown_dollars:,}")
        ca2.metric("DD max atteint", f"${max_dd_actual:,.0f}", delta=f"{dd_pct:.0f}% du max")
        ca3.metric("Marge restante", f"${max_drawdown_dollars - max_dd_actual:,.0f}")
        ca4.metric("Skip protection DD", skipped_dd)
        if dd_pct < 50:
            st.success(f"DD sous controle ({dd_pct:.0f}%)")
        elif dd_pct < 75:
            st.warning(f"DD a surveiller ({dd_pct:.0f}%)")
        else:
            st.error(f"DD dangereux ({dd_pct:.0f}%)")

    # Pipeline
    st.markdown("---")
    st.subheader("Pipeline")
    c1, c2, c3 = st.columns(3)
    c1.metric("Jours analyses", len(files))
    c2.metric("Skip HIGH vol", skipped_high_vol)
    c3.metric("Skip pas de signal", skipped_no_signal)
    st.success(f"**{len(trades_df)} trades** sur {len(files)} jours "
               f"(Kalman OU, k={band_k}, 1/session)")

    # Metriques
    st.markdown("---")
    st.subheader("Resultats")
    results = trades_df["result_pts"].values
    pnl = trades_df["pnl_dollars"].values
    wins = results[results > 0]
    losses = results[results < 0]
    n_total = len(results)
    n_wins = len(wins)
    winrate = n_wins / n_total if n_total > 0 else 0
    avg_win = wins.mean() if len(wins) > 0 else 0
    avg_loss = abs(losses.mean()) if len(losses) > 0 else 0
    expectancy = (winrate * avg_win) - ((1 - winrate) * avg_loss)
    gross_profit = wins.sum() if len(wins) > 0 else 0
    gross_loss = abs(losses.sum()) if len(losses) > 0 else 1
    profit_factor = gross_profit / gross_loss
    kelly_full, kelly_half = kelly_fraction(results)

    equity = capital_initial + np.cumsum(pnl)
    equity = np.insert(equity, 0, capital_initial)
    peak = np.maximum.accumulate(equity)
    drawdown = (equity - peak) / peak * 100
    max_dd = drawdown.min()
    total_return = (equity[-1] - capital_initial) / capital_initial * 100

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Trades", n_total)
    c1.metric("W / L", f"{n_wins} / {len(losses)}")
    c2.metric("Winrate", f"{winrate:.1%}")
    c2.metric("Profit Factor", f"{profit_factor:.2f}")
    c3.metric("Esperance", f"{expectancy:.1f} pts")
    c3.metric("R:R moyen", f"{trades_df['rr_target'].mean():.1f}")
    c4.metric("Gain moyen", f"{avg_win:.1f} pts")
    c4.metric("Perte moy.", f"{avg_loss:.1f} pts")
    c5.metric("Max Drawdown", f"{max_dd:.1f}%")
    c5.metric("P&L total", f"${pnl.sum():,.0f}")

    # Kelly
    st.markdown("---")
    ck1, ck2 = st.columns(2)
    with ck1:
        st.markdown("### Kelly Criterion")
        st.metric("Kelly optimal", f"{kelly_full:.1%}")
        st.metric("Demi-Kelly", f"{kelly_half:.1%}")
        avg_sl = trades_df["sl_pts"].mean()
        kc = max(1, int(capital_initial * kelly_half / (avg_sl * DOLLAR_PER_PT))) if kelly_half > 0 else 1
        st.metric("Contracts (1/2 Kelly)", kc)

    with ck2:
        if kelly_full > 0:
            p = winrate
            b_r = avg_win / avg_loss if avg_loss > 0 else 1
            f_range = np.linspace(0, min(1, kelly_full * 3), 200)
            g = p * np.log(1 + b_r * f_range) + (1 - p) * np.log(np.maximum(1 - f_range, 1e-10))
            fig_k = go.Figure()
            fig_k.add_trace(go.Scatter(x=f_range, y=g, mode="lines", line=dict(color=CYAN, width=2)))
            g_k = p * np.log(1 + b_r * kelly_full) + (1 - p) * np.log(max(1 - kelly_full, 1e-10))
            fig_k.add_trace(go.Scatter(x=[kelly_full], y=[g_k], mode="markers",
                                       marker=dict(color=GREEN, size=12), name=f"K={kelly_full:.1%}"))
            fig_k.add_trace(go.Scatter(
                x=[kelly_half],
                y=[p * np.log(1 + b_r * kelly_half) + (1 - p) * np.log(max(1 - kelly_half, 1e-10))],
                mode="markers", marker=dict(color=YELLOW, size=12), name=f"½K={kelly_half:.1%}"))
            fig_k.update_layout(title="Kelly Curve", height=300, xaxis_title="f",
                                yaxis_title="g(f)", **DARK)
            st.plotly_chart(fig_k, use_container_width=True)

    # Equity curve
    st.markdown("---")
    fig_eq = make_subplots(rows=2, cols=1, shared_xaxes=True,
                            row_heights=[0.7, 0.3],
                            subplot_titles=["Equity ($)", "Drawdown (%)"])
    fig_eq.add_trace(go.Scatter(
        x=trades_df["date"].astype(str).tolist(),
        y=equity[1:], mode="lines+markers",
        line=dict(color=CYAN, width=2),
        marker=dict(size=5, color=[GREEN if w else RED for w in trades_df["win"]]),
        text=[f"{'W' if w else 'L'} {r:+.1f}pts | FV={fv:.0f}" for w, r, fv
              in zip(trades_df["win"], results, trades_df["fair_value"])],
        hovertemplate="%{x}<br>%{text}<br>$%{y:,.0f}<extra></extra>"
    ), row=1, col=1)
    fig_eq.add_trace(go.Scatter(
        x=trades_df["date"].astype(str).tolist(),
        y=drawdown[1:], mode="lines",
        line=dict(color=RED, width=1.5),
        fill="tozeroy", fillcolor="rgba(255,51,102,0.12)"
    ), row=2, col=1)
    fig_eq.update_layout(height=500, showlegend=False, **DARK)
    fig_eq.update_yaxes(title_text="$", row=1, col=1)
    fig_eq.update_yaxes(title_text="%", row=2, col=1)
    st.plotly_chart(fig_eq, use_container_width=True)

    # Distribution P&L
    st.markdown("### Distribution P&L")
    colors = [GREEN if r > 0 else RED for r in results]
    fig_d = go.Figure()
    fig_d.add_trace(go.Bar(
        x=trades_df["date"].astype(str).tolist(), y=results,
        marker_color=colors, text=[f"{r:+.1f}" for r in results],
        textposition="outside", textfont=dict(size=9)
    ))
    fig_d.add_hline(y=0, line_dash="dash", line_color="white", opacity=0.3)
    fig_d.add_hline(y=expectancy, line_dash="dot", line_color=CYAN,
                    annotation_text=f"Esperance = {expectancy:.1f} pts")
    fig_d.update_layout(height=350, xaxis_title="Date", yaxis_title="Points", **DARK)
    st.plotly_chart(fig_d, use_container_width=True)

    # Stats par regime
    st.markdown("---")
    st.subheader("Performance par regime")
    for rname in ["LOW", "MED"]:
        sub = trades_df[trades_df["regime"] == rname]
        if len(sub) == 0:
            continue
        r = sub["result_pts"].values
        w = r[r > 0]
        l = r[r < 0]
        wr = len(w) / len(r)
        avg_w = w.mean() if len(w) > 0 else 0
        avg_l = abs(l.mean()) if len(l) > 0 else 0
        exp = (wr * avg_w) - ((1 - wr) * avg_l)
        st.markdown(f"**{rname} vol** — {len(r)} trades, WR {wr:.1%}, "
                    f"Esperance {exp:.1f} pts, Total {r.sum():.1f} pts")

    # Stats par deviation
    st.markdown("---")
    st.subheader("Performance par deviation (sigma)")
    bins = [(1.0, 1.5), (1.5, 2.0), (2.0, 3.0), (3.0, 10.0)]
    dev_stats = []
    for lo, hi in bins:
        sub = trades_df[(trades_df["deviation"] >= lo) & (trades_df["deviation"] < hi)]
        if len(sub) == 0:
            continue
        r = sub["result_pts"].values
        w = r[r > 0]
        l = r[r < 0]
        wr = len(w) / len(r)
        avg_w = w.mean() if len(w) > 0 else 0
        avg_l = abs(l.mean()) if len(l) > 0 else 0
        exp = (wr * avg_w) - ((1 - wr) * avg_l)
        dev_stats.append({
            "Deviation": f"{lo}-{hi}σ", "Trades": len(r),
            "Winrate": f"{wr:.1%}", "Esperance": f"{exp:.1f} pts",
            "Total": f"{r.sum():.1f} pts",
        })
    if dev_stats:
        st.dataframe(pd.DataFrame(dev_stats), use_container_width=True, hide_index=True)

    # Journal
    st.markdown("---")
    st.subheader("Journal des trades")
    display = trades_df.copy()
    display["win"] = display["win"].map({True: "TP", False: "SL"})
    st.dataframe(display, use_container_width=True, hide_index=True)
    csv = display.to_csv(index=False)
    st.download_button("Telecharger CSV", csv, "backtest_kalman.csv", "text/csv")

    # Log journalier
    st.markdown("---")
    st.subheader("Log journalier")
    st.dataframe(daily_df, use_container_width=True, hide_index=True)

    # Verdict
    st.markdown("---")
    st.subheader("Verdict")
    if expectancy > 0 and profit_factor > 1.5:
        st.success(
            f"**EDGE CONFIRME** — {winrate:.1%} WR, {expectancy:.1f} pts/trade, "
            f"PF {profit_factor:.2f}, Kelly {kelly_full:.1%}\n\n"
            f"Signal: Kalman OU (k={band_k}σ) | TP = retour fair value | SL = ATR\n\n"
            f"Return: **{total_return:+.1f}%** | Max DD: **{max_dd:.1f}%** | "
            f"Demi-Kelly: **{kelly_half:.1%}** = {kc} contracts"
        )
    elif expectancy > 0 and profit_factor > 1.0:
        st.warning(
            f"**Edge marginal** — {winrate:.1%} WR, {expectancy:.1f} pts/trade, "
            f"PF {profit_factor:.2f}\n\n"
            f"Essaie: augmenter k (bande plus large) ou ajuster le lookback."
        )
    else:
        st.error(
            f"**Pas d'edge** — {winrate:.1%} WR, {expectancy:.1f} pts/trade, "
            f"PF {profit_factor:.2f}\n\n"
            f"Ajuste: k, lookback, ou parametres GARCH."
        )