"""
Backtest Absorption MNQ — Quant Pipeline
Databento tick data → Regime filter → Absorption detection → CVD confirmation
→ Dynamic SL (ATR) → Dynamic TP (VP levels) → Kelly sizing → 1 trade/session max
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

st.set_page_config(page_title="Backtest Absorption Quant", page_icon="BA", layout="wide")
st.title("Backtest Absorption MNQ — Pipeline Quant")

# ── Sidebar ──────────────────────────────────────────────────────────
st.sidebar.header("Donnees")
data_dir = st.sidebar.text_input(
    "Dossier CSV Databento",
    value=r"C:\Users\ryadb\Downloads\GLBX-20260327-P8LBCQVG8R"
)

st.sidebar.markdown("---")
st.sidebar.header("Absorption (config ATAS)")
abs_ratio = st.sidebar.number_input("Ratio", value=150, min_value=10, step=10)
abs_stacked = st.sidebar.number_input("Stacked levels", value=3, min_value=1, step=1)
abs_min_volume = st.sidebar.number_input("Minimum Volume", value=80, min_value=5, step=5)
bar_seconds = st.sidebar.selectbox("Barre (secondes)", [30, 60, 120, 300], index=1)

st.sidebar.markdown("---")
st.sidebar.header("Regime & Risk (Quant)")
garch_alpha1 = st.sidebar.number_input("GARCH alpha1", value=0.12, step=0.01, format="%.2f")
garch_beta1 = st.sidebar.number_input("GARCH beta1", value=0.85, step=0.01, format="%.2f")
atr_multiplier_sl = st.sidebar.number_input("SL = ATR x", value=1.5, step=0.1)
max_sl_pts = st.sidebar.number_input("SL max (pts)", value=15.0, step=1.0)
min_sl_pts = st.sidebar.number_input("SL min (pts)", value=5.0, step=0.5)

st.sidebar.markdown("---")
st.sidebar.header("Realisme")
slippage_ticks = st.sidebar.number_input("Slippage (ticks)", value=2, min_value=0, step=1,
                                          help="1-2 ticks = realiste pour MNQ")
trailing_active = st.sidebar.checkbox("Trailing stop (laisser courir)", value=False)
trail_atr_mult = st.sidebar.number_input("Trail = ATR x", value=3.0, step=0.1,
                                          help="Distance du trailing stop en ATR")

st.sidebar.markdown("---")
st.sidebar.header("Session")
session_start_h = st.sidebar.number_input("Debut (h UTC)", value=14, min_value=0, max_value=23)
session_start_m = st.sidebar.number_input("Debut (min)", value=30, min_value=0, max_value=59)
session_end_h = st.sidebar.number_input("Fin (h UTC)", value=21, min_value=0, max_value=23)
session_end_m = st.sidebar.number_input("Fin (min)", value=0, min_value=0, max_value=59)

st.sidebar.markdown("---")
st.sidebar.header("Challenge Apex")
capital_initial = st.sidebar.number_input("Capital ($)", value=50000, step=1000)
max_drawdown_dollars = st.sidebar.number_input("Max Drawdown Apex ($)", value=2000, step=100)
daily_loss_limit = st.sidebar.number_input("Perte max/jour ($)", value=400, step=50)
max_contracts = st.sidebar.number_input("Contracts max", value=2, min_value=1, step=1)
risk_pct = st.sidebar.number_input("Risque/trade (%)", value=0.5, min_value=0.1, step=0.1)
dd_safety_pct = st.sidebar.number_input("Stop trading a X% du DD max", value=75, min_value=50, step=5,
                                         help="Arrete de trader quand le DD atteint ce % du max autorise")

TICK_VALUE = 0.50
TICK_SIZE = 0.25
DOLLAR_PER_PT = TICK_VALUE / TICK_SIZE  # $2/pt MNQ
DD_SAFETY_LIMIT = max_drawdown_dollars * (dd_safety_pct / 100)  # $1500 par defaut


# ══════════════════════════════════════════════════════════════════════
# ENGINE
# ══════════════════════════════════════════════════════════════════════

def load_single_day(filepath, start_h, start_m, end_h, end_m):
    """Charge un fichier, filtre session, retourne ticks."""
    df = pd.read_csv(filepath, usecols=["ts_event", "side", "price", "size"])
    df["ts"] = pd.to_datetime(df["ts_event"], utc=True)
    df["price"] = df["price"].astype(float)
    df["size"] = df["size"].astype(int)
    df.drop(columns=["ts_event"], inplace=True)
    t_min = df["ts"].dt.hour * 60 + df["ts"].dt.minute
    mask = (t_min >= start_h * 60 + start_m) & (t_min < end_h * 60 + end_m)
    return df[mask].sort_values("ts").reset_index(drop=True)


def build_bars(df, freq_seconds):
    """Ticks → barres OHLCV + delta + ATR."""
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
    bars["date"] = bars["bar"].dt.date
    bars["returns"] = bars["close"].pct_change().fillna(0)
    return bars


def compute_garch_vol(returns, alpha0=0.00001, alpha1=0.12, beta1=0.85):
    """GARCH(1,1) volatility series."""
    n = len(returns)
    sigma2 = np.zeros(n)
    sigma2[0] = alpha0 / max(1 - alpha1 - beta1, 0.01)
    for t in range(1, n):
        sigma2[t] = alpha0 + alpha1 * returns[t - 1] ** 2 + beta1 * sigma2[t - 1]
    return np.sqrt(sigma2)


def classify_regime(garch_vol, window=60):
    """
    Regime bayesien simplifie: LOW / MED / HIGH vol.
    Basé sur les percentiles glissants de la vol GARCH.
    """
    regimes = np.full(len(garch_vol), 1)  # default MED
    for i in range(window, len(garch_vol)):
        history = garch_vol[max(0, i - window):i]
        p33 = np.percentile(history, 33)
        p67 = np.percentile(history, 67)
        if garch_vol[i] < p33:
            regimes[i] = 0  # LOW
        elif garch_vol[i] > p67:
            regimes[i] = 2  # HIGH
        else:
            regimes[i] = 1  # MED
    return regimes


def compute_session_vp(bars):
    """Volume Profile par session → POC, VAH, VAL."""
    vp = {}
    for date, grp in bars.groupby("date"):
        # Volume par prix arrondi au tick
        prices = (grp["close"] / TICK_SIZE).round() * TICK_SIZE
        price_vol = grp.groupby(prices)["volume"].sum()
        if len(price_vol) == 0:
            continue
        poc = price_vol.idxmax()
        total_vol = price_vol.sum()
        target = total_vol * 0.70
        sorted_pv = price_vol.sort_values(ascending=False)
        cumvol = 0
        va_prices = []
        for p, v in sorted_pv.items():
            cumvol += v
            va_prices.append(p)
            if cumvol >= target:
                break
        vp[date] = {"POC": poc, "VAH": max(va_prices), "VAL": min(va_prices)}
    return vp


def detect_absorption(ticks, ratio, stacked, min_volume, freq_seconds):
    """Detecte les niveaux d'absorption (ATAS-like)."""
    ticks = ticks.copy()
    ticks["bar"] = ticks["ts"].dt.floor(f"{freq_seconds}s")
    absorptions = []

    for bar_ts, group in ticks.groupby("bar"):
        pv = group.groupby(["price", "side"])["size"].sum().unstack(fill_value=0)
        if "A" not in pv.columns:
            pv["A"] = 0
        if "B" not in pv.columns:
            pv["B"] = 0
        pv["total"] = pv["A"] + pv["B"]
        pv = pv[pv["total"] >= min_volume].sort_index()
        if len(pv) == 0:
            continue

        for price_level, row in pv.iterrows():
            a, b_vol, total = row["A"], row["B"], row["total"]
            if a > 0 and b_vol > 0:
                if a >= b_vol * ratio / 100:
                    absorptions.append({"bar": bar_ts, "price": price_level,
                                        "type": "ask", "volume": total,
                                        "ask_vol": a, "bid_vol": b_vol})
                elif b_vol >= a * ratio / 100:
                    absorptions.append({"bar": bar_ts, "price": price_level,
                                        "type": "bid", "volume": total,
                                        "ask_vol": a, "bid_vol": b_vol})

    if not absorptions:
        return pd.DataFrame()

    abs_df = pd.DataFrame(absorptions)
    abs_df["bar"] = pd.to_datetime(abs_df["bar"], utc=True)

    # Filtre stacked
    if stacked > 1:
        filtered = []
        for bar_ts, grp in abs_df.groupby("bar"):
            for abs_type in ["ask", "bid"]:
                sub = grp[grp["type"] == abs_type].sort_values("price")
                if len(sub) < stacked:
                    continue
                prices = sub["price"].values
                diffs = np.diff(prices)
                consecutive = 1
                for i, d in enumerate(diffs):
                    if abs(d - TICK_SIZE) < 0.01:
                        consecutive += 1
                        if consecutive >= stacked:
                            start_idx = i + 2 - consecutive
                            for j in range(start_idx, i + 2):
                                filtered.append(sub.iloc[j].to_dict())
                    else:
                        consecutive = 1
        if filtered:
            abs_df = pd.DataFrame(filtered).drop_duplicates(subset=["bar", "price", "type"])
        else:
            return pd.DataFrame()

    # Cluster les niveaux proches
    abs_df["date"] = pd.to_datetime(abs_df["bar"]).dt.date
    levels = []
    for (date, abs_type), grp in abs_df.groupby(["date", "type"]):
        prices_sorted = grp.sort_values("price")["price"].values
        clusters = []
        current = [prices_sorted[0]]
        for p in prices_sorted[1:]:
            if p - current[-1] <= 2.0:
                current.append(p)
            else:
                clusters.append(current)
                current = [p]
        clusters.append(current)

        for cluster in clusters:
            cluster_rows = grp[grp["price"].isin(cluster)]
            levels.append({
                "date": date,
                "bar": cluster_rows["bar"].iloc[0],
                "price": np.mean(cluster),
                "type": abs_type,
                "volume": cluster_rows["volume"].sum(),
                "n_levels": len(cluster),
            })

    return pd.DataFrame(levels)


def check_cvd_divergence(bars, bar_idx, lookback=5):
    """CVD divergence: prix vs delta cumulatif."""
    if bar_idx < lookback:
        return False, None
    recent = bars.iloc[bar_idx - lookback:bar_idx + 1]
    price_chg = recent["close"].iloc[-1] - recent["close"].iloc[0]
    cvd_chg = recent["cvd"].iloc[-1] - recent["cvd"].iloc[0]
    if price_chg > 0 and cvd_chg < 0:
        return True, "bearish"
    elif price_chg < 0 and cvd_chg > 0:
        return True, "bullish"
    return False, None


def score_absorption(abso, bar_idx, bars, vp_levels, regime):
    """
    Score un signal d'absorption (0-100). Plus le score est haut, meilleur le signal.
    Criteres:
      - Volume (plus = mieux)                    0-25 pts
      - CVD divergence confirme                   0-25 pts
      - Sur niveau VP (POC/VAH/VAL)              0-25 pts
      - Regime favorable (LOW > MED > HIGH)      0-25 pts
    """
    score = 0

    # 1. Volume relatif (normalise sur la session)
    session_bars = bars[bars["date"] == abso["date"]]
    if len(session_bars) > 0:
        avg_vol = session_bars["volume"].mean()
        vol_ratio = abso["volume"] / max(avg_vol, 1)
        score += min(25, vol_ratio * 10)

    # 2. CVD divergence
    has_cvd, cvd_dir = check_cvd_divergence(bars, bar_idx)
    cvd_confirms = False
    if has_cvd:
        if abso["type"] == "ask" and cvd_dir == "bearish":
            cvd_confirms = True
        elif abso["type"] == "bid" and cvd_dir == "bullish":
            cvd_confirms = True
    if cvd_confirms:
        score += 25

    # 3. Proximite VP
    abs_date = abso["date"]
    on_vp = False
    vp_name = None
    if abs_date in vp_levels:
        vp = vp_levels[abs_date]
        for name in ["POC", "VAH", "VAL"]:
            if abs(abso["price"] - vp[name]) <= 5.0:
                on_vp = True
                vp_name = name
                break
    if on_vp:
        score += 25

    # 4. Regime
    if regime == 0:  # LOW vol
        score += 25
    elif regime == 1:  # MED vol
        score += 12
    # HIGH vol = 0 pts

    return score, cvd_confirms, on_vp, vp_name


def kalman_fair_value(bars, bar_idx, lookback=60):
    """
    Kalman Filter pour estimer le fair value en temps réel.
    Basé sur un modèle OU (Ornstein-Uhlenbeck) AR(1).

    Ref: Quant Guild #92 + #95 (Kalman Filter + Mean Reversion)
    Ref: app learning module 06b (kalman_mean_reversion)

    Retourne: (fair_value, sigma_stat, kalman_gain)
    - fair_value = prix estime par le Kalman
    - sigma_stat = deviation stationnaire (bandes de mean reversion)
    - kalman_gain = confiance du filtre (0 = suit le modele, 1 = suit le prix)
    """
    end = min(bar_idx + 1, len(bars))
    start = max(0, end - lookback)
    prices = bars.iloc[start:end]["close"].values

    if len(prices) < 10:
        return prices[-1], 5.0, 0.5

    # Calibration AR(1): X_t = phi * X_{t-1} + (1-phi) * mu + eps
    x_prev = prices[:-1]
    x_curr = prices[1:]
    if np.std(x_prev) < 1e-10:
        return prices[-1], 5.0, 0.5

    # Regression lineaire pour phi et mu
    n = len(x_prev)
    sx = np.sum(x_prev)
    sy = np.sum(x_curr)
    sxx = np.sum(x_prev ** 2)
    sxy = np.sum(x_prev * x_curr)

    denom = n * sxx - sx * sx
    if abs(denom) < 1e-10:
        return prices[-1], 5.0, 0.5

    phi = (n * sxy - sx * sy) / denom
    c = (sy - phi * sx) / n

    # Contraindre phi pour stabilite
    phi = np.clip(phi, 0.5, 0.999)

    # Mean implicite et sigma
    mu = c / (1 - phi) if abs(1 - phi) > 1e-6 else prices.mean()
    residuals = x_curr - (phi * x_prev + c)
    sigma = np.std(residuals)

    # Sigma stationnaire (bande de mean reversion)
    sigma_stat = sigma / np.sqrt(max(2 * (1 - phi), 0.001))

    # Kalman filter
    Q = sigma ** 2 * (1 - phi ** 2)  # process noise
    R = sigma ** 2 * 5.0  # observation noise (trust model more than data)

    x_est = prices[0]
    P = sigma_stat ** 2

    for obs in prices:
        # Predict
        x_pred = phi * x_est + (1 - phi) * mu
        P_pred = phi ** 2 * P + Q

        # Update
        K = P_pred / (P_pred + R)
        x_est = x_pred + K * (obs - x_pred)
        P = (1 - K) * P_pred

    return x_est, sigma_stat, K


def find_kalman_tp(entry_price, direction, bars, bar_idx, sl_pts):
    """
    TP = distance entre le prix d'entree et le fair value Kalman.
    L'absorption repousse le prix → le prix revient vers la moyenne Kalman.

    Logique:
    - Long  (absorption bid) : TP = fair_value (prix sous le fair value, va remonter)
    - Short (absorption ask) : TP = fair_value (prix au-dessus du fair value, va redescendre)

    Si le fair value est trop proche, utilise sigma_stat comme TP minimum.
    """
    fair_value, sigma_stat, K = kalman_fair_value(bars, bar_idx)

    if direction == "long":
        tp_pts = fair_value - entry_price
    else:
        tp_pts = entry_price - fair_value

    # Si le TP est negatif ou trop petit (prix deja au fair value),
    # utilise la bande de reversion (sigma_stat)
    if tp_pts < sl_pts * 1.0:
        tp_pts = sigma_stat * 0.8  # 80% de la bande stationnaire

    # TP minimum = 1.5x SL pour un R:R minimum
    tp_pts = max(tp_pts, sl_pts * 1.5)

    return tp_pts, fair_value, sigma_stat, K


def simulate_trade(bars, entry_idx, entry_price, direction, sl_pts, tp_pts,
                    use_trailing=False, trail_distance=10.0, slip_pts=0.5):
    """
    Simule un trade barre par barre avec:
    - Slippage a l'entree et sortie
    - Trailing stop optionnel
    - Max 120 barres (~2h)
    """
    # Slippage a l'entree (execution pire que prevu)
    if direction == "long":
        real_entry = entry_price + slip_pts
        sl_price = real_entry - sl_pts
        tp_price = real_entry + tp_pts
    else:
        real_entry = entry_price - slip_pts
        sl_price = real_entry + sl_pts
        tp_price = real_entry - tp_pts

    best_price = real_entry
    trailing_stop = sl_price

    for i in range(entry_idx + 1, min(entry_idx + 120, len(bars))):
        bar = bars.iloc[i]

        if direction == "long":
            # Mise a jour du trailing stop
            if use_trailing and bar["high"] > best_price:
                best_price = bar["high"]
                new_trail = best_price - trail_distance
                trailing_stop = max(trailing_stop, new_trail)

            stop = trailing_stop if use_trailing else sl_price

            # Check SL / trailing (avec slippage a la sortie)
            if bar["low"] <= stop:
                exit_price = stop - slip_pts
                return exit_price - real_entry

            # Check TP (avec slippage a la sortie)
            if bar["high"] >= tp_price:
                exit_price = tp_price - slip_pts
                return exit_price - real_entry

        else:  # short
            if use_trailing and bar["low"] < best_price:
                best_price = bar["low"]
                new_trail = best_price + trail_distance
                trailing_stop = min(trailing_stop, new_trail)

            stop = trailing_stop if use_trailing else sl_price

            if bar["high"] >= stop:
                exit_price = stop + slip_pts
                return real_entry - exit_price

            if bar["low"] <= tp_price:
                exit_price = tp_price + slip_pts
                return real_entry - exit_price

    # Timeout → close at market (avec slippage)
    last = bars.iloc[min(entry_idx + 119, len(bars) - 1)]["close"]
    if direction == "long":
        return (last - slip_pts) - real_entry
    else:
        return real_entry - (last + slip_pts)


def kelly_fraction(results):
    """Calcule Kelly et demi-Kelly a partir des resultats."""
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

    st.info(f"{len(files)} fichiers. Pipeline: Regime → Absorption → Score → Kalman TP → 1 trade/session")
    progress = st.progress(0)

    all_trades = []
    all_daily_stats = []
    skipped_high_vol = 0
    skipped_no_signal = 0
    skipped_low_score = 0
    skipped_dd_protection = 0
    running_equity = capital_initial
    running_peak = capital_initial
    challenge_busted = False

    for file_idx, filepath in enumerate(files):
        progress.progress((file_idx + 1) / len(files),
                          text=f"Jour {file_idx + 1}/{len(files)}")

        # ── 0. Protection DD Apex ────────────────────────────────────
        running_dd = running_peak - running_equity
        if running_dd >= max_drawdown_dollars:
            challenge_busted = True
            all_daily_stats.append({
                "date": "BUST",
                "regime": "-",
                "action": "BUST",
                "reason": f"DD ${running_dd:.0f} >= ${max_drawdown_dollars}",
                "n_absorptions": 0,
                "result_pts": 0,
            })
            break

        if running_dd >= DD_SAFETY_LIMIT:
            skipped_dd_protection += 1
            all_daily_stats.append({
                "date": os.path.basename(filepath).split(".")[0][-8:],
                "regime": "-",
                "action": "SKIP",
                "reason": f"Protection DD: ${running_dd:.0f} / ${max_drawdown_dollars}",
                "n_absorptions": 0,
                "result_pts": 0,
            })
            continue

        # ── 1. Charger le jour ───────────────────────────────────────
        ticks = load_single_day(filepath, session_start_h, session_start_m,
                                session_end_h, session_end_m)
        if len(ticks) < 100:
            skipped_no_signal += 1
            continue

        # ── 2. Barres + ATR ──────────────────────────────────────────
        bars = build_bars(ticks, bar_seconds)
        if len(bars) < 20:
            skipped_no_signal += 1
            continue

        # ── 3. GARCH regime ──────────────────────────────────────────
        garch_vol = compute_garch_vol(bars["returns"].values,
                                       alpha1=garch_alpha1, beta1=garch_beta1)
        regimes = classify_regime(garch_vol)

        # Regime dominant de la session
        regime_counts = np.bincount(regimes, minlength=3)
        dominant_regime = regime_counts.argmax()

        # Si majorite HIGH vol → pas de trade (SURVIE > PROFIT)
        if dominant_regime == 2:
            skipped_high_vol += 1
            all_daily_stats.append({
                "date": bars.iloc[0]["date"],
                "regime": "HIGH",
                "action": "SKIP",
                "reason": "Regime HIGH vol",
                "n_absorptions": 0,
                "result_pts": 0,
            })
            continue

        # ── 4. Volume Profile ────────────────────────────────────────
        vp_levels = compute_session_vp(bars)

        # ── 5. Detecter absorptions ──────────────────────────────────
        abs_levels = detect_absorption(ticks, abs_ratio,
                                        abs_stacked, abs_min_volume, bar_seconds)
        del ticks  # liberer memoire

        if len(abs_levels) == 0:
            skipped_no_signal += 1
            all_daily_stats.append({
                "date": bars.iloc[0]["date"],
                "regime": ["LOW", "MED", "HIGH"][dominant_regime],
                "action": "SKIP",
                "reason": "Aucune absorption",
                "n_absorptions": 0,
                "result_pts": 0,
            })
            continue

        # ── 6. Scorer chaque absorption ──────────────────────────────
        scored = []
        for _, abso in abs_levels.iterrows():
            bar_mask = bars["bar"] == abso["bar"]
            if not bar_mask.any():
                bar_idx = (bars["bar"] - abso["bar"]).abs().idxmin()
            else:
                bar_idx = bars[bar_mask].index[0]

            # Regime local de la barre
            local_regime = regimes[min(bar_idx, len(regimes) - 1)]

            # Skip si HIGH vol local
            if local_regime == 2:
                continue

            score, cvd_ok, vp_ok, vp_name = score_absorption(
                abso, bar_idx, bars, vp_levels, local_regime
            )

            scored.append({
                **abso.to_dict(),
                "bar_idx": bar_idx,
                "score": score,
                "cvd_confirms": cvd_ok,
                "on_vp": vp_ok,
                "vp_name": vp_name,
                "regime": local_regime,
            })

        if not scored:
            skipped_low_score += 1
            continue

        # ── 7. Prendre LE MEILLEUR signal (1 trade/session) ─────────
        scored_df = pd.DataFrame(scored).sort_values("score", ascending=False)
        best = scored_df.iloc[0]

        # Score minimum pour trader (au moins 2 criteres solides sur 4)
        if best["score"] < 50:
            skipped_low_score += 1
            all_daily_stats.append({
                "date": bars.iloc[0]["date"],
                "regime": ["LOW", "MED", "HIGH"][dominant_regime],
                "action": "SKIP",
                "reason": f"Score trop bas ({best['score']:.0f}/100)",
                "n_absorptions": len(abs_levels),
                "result_pts": 0,
            })
            continue

        # ── 8. SL dynamique = ATR x multiplier ──────────────────────
        bar_idx = int(best["bar_idx"])
        atr = bars.iloc[bar_idx]["atr_14"]
        if np.isnan(atr) or atr <= 0:
            atr = bars["tr"].mean()
        if np.isnan(atr) or atr <= 0:
            atr = 8.0  # fallback MNQ
        sl_pts = np.clip(atr * atr_multiplier_sl, min_sl_pts, max_sl_pts)

        # ── 9. TP Kalman mean reversion ──────────────────────────────
        direction = "short" if best["type"] == "ask" else "long"
        tp_pts, fair_val, sigma_stat, k_gain = find_kalman_tp(
            best["price"], direction, bars, bar_idx, sl_pts
        )

        # ── 10. Position sizing (Apex-safe) ─────────────────────────
        # Calcul: combien de contracts pour risquer X% du capital
        regime_mult = 0.75 if best["regime"] == 0 else 1.0
        risk_dollars = capital_initial * (risk_pct / 100) * regime_mult
        contracts = max(1, int(risk_dollars / (sl_pts * DOLLAR_PER_PT)))

        # CAP: ne jamais depasser max_contracts
        contracts = min(contracts, max_contracts)

        # Protection: si une perte toucherait la daily loss limit, reduire
        loss_if_sl = sl_pts * DOLLAR_PER_PT * contracts
        if loss_if_sl > daily_loss_limit:
            contracts = max(1, int(daily_loss_limit / (sl_pts * DOLLAR_PER_PT)))

        # Protection: si proche du DD max, reduire a 1 contract
        remaining_dd = max_drawdown_dollars - (running_peak - running_equity)
        if loss_if_sl > remaining_dd * 0.5:
            contracts = 1

        # ── 11. Simuler le trade (avec slippage + trailing) ────────
        slip = slippage_ticks * TICK_SIZE  # ex: 2 ticks * 0.25 = 0.5 pts
        trail_dist = atr * trail_atr_mult if trailing_active else 0
        result_pts = simulate_trade(bars, bar_idx, best["price"],
                                     direction, sl_pts, tp_pts,
                                     use_trailing=trailing_active,
                                     trail_distance=trail_dist,
                                     slip_pts=slip)

        rr_actual = abs(result_pts) / sl_pts if sl_pts > 0 else 0
        pnl_dollars = result_pts * DOLLAR_PER_PT * contracts

        # Mettre a jour l'equity running (pour protection DD)
        running_equity += pnl_dollars
        if running_equity > running_peak:
            running_peak = running_equity

        trade = {
            "date": best["date"],
            "time": best["bar"],
            "price": best["price"],
            "type": best["type"],
            "direction": direction,
            "score": best["score"],
            "regime": ["LOW", "MED", "HIGH"][int(best["regime"])],
            "cvd_confirms": best["cvd_confirms"],
            "on_vp": best["on_vp"],
            "vp_name": best["vp_name"],
            "fair_value": round(fair_val, 2),
            "sigma_stat": round(sigma_stat, 2),
            "kalman_K": round(k_gain, 3),
            "sl_pts": round(sl_pts, 2),
            "tp_pts": round(tp_pts, 2),
            "rr_target": round(tp_pts / sl_pts, 1),
            "result_pts": round(result_pts, 2),
            "rr_actual": round(rr_actual, 1),
            "contracts": contracts,
            "pnl_dollars": round(pnl_dollars, 2),
            "win": result_pts > 0,
            "equity": round(running_equity, 2),
            "dd_from_peak": round(running_peak - running_equity, 2),
            "n_absorptions_day": len(abs_levels),
        }
        all_trades.append(trade)

        all_daily_stats.append({
            "date": best["date"],
            "regime": trade["regime"],
            "action": "TRADE",
            "reason": f"Score {best['score']:.0f}, {direction} @ {best['price']:.2f}",
            "n_absorptions": len(abs_levels),
            "result_pts": result_pts,
        })

    progress.empty()

    # ══════════════════════════════════════════════════════════════════
    # RESULTATS
    # ══════════════════════════════════════════════════════════════════

    if not all_trades:
        st.warning("Aucun trade execute. Baisse le score minimum ou les parametres d'absorption.")
        st.stop()

    trades_df = pd.DataFrame(all_trades)
    daily_df = pd.DataFrame(all_daily_stats)

    # ── Challenge Apex Status ────────────────────────────────────────
    st.markdown("---")
    if challenge_busted:
        st.error(f"**CHALLENGE BUST** — Drawdown a depasse ${max_drawdown_dollars}")
    else:
        max_dd_actual = trades_df["dd_from_peak"].max() if "dd_from_peak" in trades_df.columns else 0
        dd_pct_of_max = max_dd_actual / max_drawdown_dollars * 100
        st.subheader("Challenge Apex")
        ca1, ca2, ca3, ca4 = st.columns(4)
        ca1.metric("DD max autorise", f"${max_drawdown_dollars:,}")
        ca2.metric("DD max atteint", f"${max_dd_actual:,.0f}",
                   delta=f"{dd_pct_of_max:.0f}% du max")
        ca3.metric("Marge restante", f"${max_drawdown_dollars - max_dd_actual:,.0f}")
        ca4.metric("Skip protection DD", skipped_dd_protection)

        if dd_pct_of_max < 50:
            st.success(f"DD sous controle ({dd_pct_of_max:.0f}% du max)")
        elif dd_pct_of_max < 75:
            st.warning(f"DD a surveiller ({dd_pct_of_max:.0f}% du max)")
        else:
            st.error(f"DD dangereux ({dd_pct_of_max:.0f}% du max)")

    # ── Resume pipeline ──────────────────────────────────────────────
    st.markdown("---")
    st.subheader("Pipeline")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Jours analyses", len(files))
    c2.metric("Skip HIGH vol", skipped_high_vol)
    c3.metric("Skip pas de signal", skipped_no_signal)
    c4.metric("Skip score bas", skipped_low_score)

    st.success(f"**{len(trades_df)} trades executes** sur {len(files)} jours "
               f"(1 trade/session max, filtre regime + score)")

    # ── Metriques globales ──────────────────��────────────────────────
    st.markdown("---")
    st.subheader("Resultats")

    results = trades_df["result_pts"].values
    pnl = trades_df["pnl_dollars"].values
    wins = results[results > 0]
    losses = results[results < 0]
    n_total = len(results)
    n_wins = len(wins)
    winrate = n_wins / n_total

    avg_win = wins.mean() if len(wins) > 0 else 0
    avg_loss = abs(losses.mean()) if len(losses) > 0 else 0
    expectancy = (winrate * avg_win) - ((1 - winrate) * avg_loss)

    gross_profit = wins.sum() if len(wins) > 0 else 0
    gross_loss = abs(losses.sum()) if len(losses) > 0 else 1
    profit_factor = gross_profit / gross_loss

    kelly_full, kelly_half = kelly_fraction(results)

    # Equity
    equity = capital_initial + np.cumsum(pnl)
    equity = np.insert(equity, 0, capital_initial)
    peak = np.maximum.accumulate(equity)
    drawdown = (equity - peak) / peak * 100
    max_dd = drawdown.min()

    # Avg R:R
    avg_rr = trades_df["rr_target"].mean()
    avg_rr_actual_win = trades_df[trades_df["win"]]["rr_actual"].mean() if n_wins > 0 else 0

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Trades", n_total)
    col1.metric("W / L", f"{n_wins} / {len(losses)}")
    col2.metric("Winrate", f"{winrate:.1%}")
    col2.metric("Profit Factor", f"{profit_factor:.2f}")
    col3.metric("Esperance", f"{expectancy:.1f} pts")
    col3.metric("R:R moyen cible", f"{avg_rr:.1f}")
    col4.metric("Gain moyen", f"{avg_win:.1f} pts")
    col4.metric("Perte moy.", f"{avg_loss:.1f} pts")
    col5.metric("Max Drawdown", f"{max_dd:.1f}%")
    col5.metric("P&L total", f"${pnl.sum():,.0f}")

    # ── Kelly ───────��────────────────────────────────────────────────
    st.markdown("---")
    ck1, ck2 = st.columns(2)
    with ck1:
        st.markdown("### Kelly Criterion")
        st.metric("Kelly optimal", f"{kelly_full:.1%}")
        st.metric("Demi-Kelly", f"{kelly_half:.1%}")
        avg_sl = trades_df["sl_pts"].mean()
        kelly_contracts = max(1, int(capital_initial * kelly_half / (avg_sl * DOLLAR_PER_PT)))
        st.metric("Contracts (1/2 Kelly)", kelly_contracts)

    with ck2:
        if kelly_full > 0:
            p = winrate
            b_ratio = avg_win / avg_loss if avg_loss > 0 else 1
            f_range = np.linspace(0, min(1, kelly_full * 3), 200)
            g = p * np.log(1 + b_ratio * f_range) + (1 - p) * np.log(
                np.maximum(1 - f_range, 1e-10))
            fig_k = go.Figure()
            fig_k.add_trace(go.Scatter(x=f_range, y=g, mode="lines",
                                       line=dict(color=CYAN, width=2)))
            g_k = p * np.log(1 + b_ratio * kelly_full) + (1 - p) * np.log(max(1 - kelly_full, 1e-10))
            fig_k.add_trace(go.Scatter(x=[kelly_full], y=[g_k], mode="markers",
                                       marker=dict(color=GREEN, size=12),
                                       name=f"Kelly={kelly_full:.1%}"))
            fig_k.add_trace(go.Scatter(
                x=[kelly_half],
                y=[p * np.log(1 + b_ratio * kelly_half) + (1 - p) * np.log(max(1 - kelly_half, 1e-10))],
                mode="markers", marker=dict(color=YELLOW, size=12),
                name=f"1/2K={kelly_half:.1%}"))
            fig_k.update_layout(title="Kelly Curve", height=300,
                                xaxis_title="f", yaxis_title="g(f)", **DARK)
            st.plotly_chart(fig_k, use_container_width=True)

    # ── Equity curve ─────────────────────────────────────────────────
    st.markdown("---")
    fig_eq = make_subplots(rows=2, cols=1, shared_xaxes=True,
                            row_heights=[0.7, 0.3],
                            subplot_titles=["Equity ($)", "Drawdown (%)"])
    fig_eq.add_trace(go.Scatter(
        x=trades_df["date"].astype(str).tolist(),
        y=equity[1:], mode="lines+markers",
        line=dict(color=CYAN, width=2),
        marker=dict(size=4, color=[GREEN if w else RED for w in trades_df["win"]]),
        text=[f"{'W' if w else 'L'} {r:+.1f}pts" for w, r in zip(trades_df["win"], results)],
        hovertemplate="%{x}<br>%{text}<br>Equity: $%{y:,.0f}<extra></extra>"
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

    # ── Distribution P&L ─────────────────────────────────────────────
    st.markdown("### Distribution P&L")
    colors = [GREEN if r > 0 else RED for r in results]
    fig_d = go.Figure()
    fig_d.add_trace(go.Bar(
        x=trades_df["date"].astype(str).tolist(), y=results,
        marker_color=colors,
        text=[f"{r:+.1f}" for r in results], textposition="outside",
        textfont=dict(size=9)
    ))
    fig_d.add_hline(y=0, line_dash="dash", line_color="white", opacity=0.3)
    fig_d.add_hline(y=expectancy, line_dash="dot", line_color=CYAN,
                    annotation_text=f"Esperance = {expectancy:.1f} pts")
    fig_d.update_layout(height=350, xaxis_title="Date", yaxis_title="Points", **DARK)
    st.plotly_chart(fig_d, use_container_width=True)

    # ── Stats par regime ─────────────────────────────────────────────
    st.markdown("---")
    st.subheader("Performance par regime")
    for regime_name in ["LOW", "MED"]:
        sub = trades_df[trades_df["regime"] == regime_name]
        if len(sub) == 0:
            continue
        r = sub["result_pts"].values
        w = r[r > 0]
        l = r[r < 0]
        wr = len(w) / len(r)
        avg_w = w.mean() if len(w) > 0 else 0
        avg_l = abs(l.mean()) if len(l) > 0 else 0
        exp = (wr * avg_w) - ((1 - wr) * avg_l)
        st.markdown(f"**{regime_name} vol** — {len(r)} trades, "
                    f"WR {wr:.1%}, Esperance {exp:.1f} pts, "
                    f"Total {r.sum():.1f} pts")

    # ── Stats par score ──────────────────────────────────────────────
    st.markdown("---")
    st.subheader("Performance par score")
    bins = [(37, 50), (50, 62), (62, 75), (75, 100)]
    score_stats = []
    for lo, hi in bins:
        sub = trades_df[(trades_df["score"] >= lo) & (trades_df["score"] < hi)]
        if len(sub) == 0:
            continue
        r = sub["result_pts"].values
        w = r[r > 0]
        l = r[r < 0]
        wr = len(w) / len(r)
        avg_w = w.mean() if len(w) > 0 else 0
        avg_l = abs(l.mean()) if len(l) > 0 else 0
        exp = (wr * avg_w) - ((1 - wr) * avg_l)
        score_stats.append({
            "Score": f"{lo}-{hi}",
            "Trades": len(r),
            "Winrate": f"{wr:.1%}",
            "Esperance": f"{exp:.1f} pts",
            "Total": f"{r.sum():.1f} pts",
        })
    if score_stats:
        st.dataframe(pd.DataFrame(score_stats), use_container_width=True, hide_index=True)

    # ── Journal ──────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("Journal des trades")
    display = trades_df.copy()
    display["win"] = display["win"].map({True: "TP", False: "SL"})
    display["cvd_confirms"] = display["cvd_confirms"].map({True: "Oui", False: "Non"})
    display["on_vp"] = display["on_vp"].map({True: "Oui", False: "Non"})
    st.dataframe(display, use_container_width=True, hide_index=True)
    csv = display.to_csv(index=False)
    st.download_button("Telecharger CSV", csv, "backtest_quant.csv", "text/csv")

    # ── Daily log ────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("Log journalier")
    st.dataframe(daily_df, use_container_width=True, hide_index=True)

    # ── Verdict ──────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("Verdict")
    # Verdict base sur l'esperance et le PF, pas le winrate seul
    # Un systeme sniper (20% WR, gros R:R) est valide si PF > 1.5 et esperance > 0
    total_return = (equity[-1] - capital_initial) / capital_initial * 100
    if expectancy > 0 and profit_factor > 1.5:
        st.success(
            f"**EDGE CONFIRME** — {winrate:.1%} WR, {expectancy:.1f} pts/trade, "
            f"PF {profit_factor:.2f}, Kelly {kelly_full:.1%}\n\n"
            f"Profil **sniper** : peu de wins mais gros R:R = rentable\n\n"
            f"Pipeline: Regime + Score ≥50 + SL ATR + TP VP → "
            f"**{n_total} trades / {len(files)} jours**\n\n"
            f"Return: **{total_return:+.1f}%** | Max DD: **{max_dd:.1f}%** | "
            f"Demi-Kelly: **{kelly_half:.1%}** = {kelly_contracts} contracts"
        )
    elif expectancy > 0 and profit_factor > 1.0:
        st.warning(
            f"**Edge marginal** — {winrate:.1%} WR, {expectancy:.1f} pts/trade, "
            f"PF {profit_factor:.2f}\n\n"
            f"Return: {total_return:+.1f}% | Ameliore le score minimum ou les filtres."
        )
    else:
        st.error(
            f"**Pas d'edge** — {winrate:.1%} WR, {expectancy:.1f} pts/trade, "
            f"PF {profit_factor:.2f}\n\n"
            f"Ajuste: ratio absorption, min volume, ou parametres regime."
        )