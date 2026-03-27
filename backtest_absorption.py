"""
Backtest Absorption MNQ — Databento tick data
Charge les trades Databento, detecte absorption/CVD/VP automatiquement,
backteste les entries/exits, calcule winrate, esperance, drawdown, Kelly.
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

st.set_page_config(page_title="Backtest Absorption", page_icon="BA", layout="wide")
st.title("Backtest Absorption MNQ")

# ── Sidebar ──────────────────────────────────────────────────────────
st.sidebar.header("Donnees Databento")
data_dir = st.sidebar.text_input(
    "Dossier des CSV Databento",
    value=r"C:\Users\ryadb\Downloads\GLBX-20260327-P8LBCQVG8R"
)

st.sidebar.markdown("---")
st.sidebar.header("Absorption (config ATAS)")
abs_ratio = st.sidebar.number_input("Ratio", value=150, min_value=10, step=10)
abs_stacked = st.sidebar.number_input("Stacked levels", value=3, min_value=1, step=1)
abs_min_volume = st.sidebar.number_input("Minimum Volume", value=80, min_value=5, step=5)
bar_seconds = st.sidebar.selectbox("Barre (secondes)", [30, 60, 120, 300], index=1)

st.sidebar.markdown("---")
st.sidebar.header("Trade Management")
sl_pts = st.sidebar.number_input("Stop Loss (pts)", value=10.0, min_value=0.25, step=0.25)
tp_mode = st.sidebar.selectbox("Take Profit", ["Fixe (pts)", "R:R ratio", "Trailing"])
if tp_mode == "Fixe (pts)":
    tp_pts = st.sidebar.number_input("TP (pts)", value=15.0, min_value=0.25, step=0.25)
elif tp_mode == "R:R ratio":
    rr_ratio = st.sidebar.number_input("R:R", value=2.0, min_value=0.5, step=0.5)
    tp_pts = sl_pts * rr_ratio
else:
    trail_pts = st.sidebar.number_input("Trail distance (pts)", value=10.0, min_value=0.25, step=0.25)
    tp_pts = None

capital_initial = st.sidebar.number_input("Capital initial ($)", value=50000, step=1000)
risk_pct = st.sidebar.number_input("Risque par trade (%)", value=1.0, min_value=0.1, step=0.1)
tick_value = 0.50  # MNQ
tick_size = 0.25   # MNQ

st.sidebar.markdown("---")
st.sidebar.header("Filtres")
use_cvd_filter = st.sidebar.checkbox("Filtre CVD divergence", value=True)
use_vp_filter = st.sidebar.checkbox("Filtre Volume Profile (POC/VAH/VAL)", value=False)
vp_tolerance = st.sidebar.number_input("VP tolerance (pts)", value=5.0, step=0.25)
session_start_h = st.sidebar.number_input("Session debut (heure UTC)", value=14, min_value=0, max_value=23)
session_start_m = st.sidebar.number_input("Session debut (min)", value=30, min_value=0, max_value=59)
session_end_h = st.sidebar.number_input("Session fin (heure UTC)", value=21, min_value=0, max_value=23)
session_end_m = st.sidebar.number_input("Session fin (min)", value=0, min_value=0, max_value=59)


# ══════════════════════════════════════════════════════════════════════
# ENGINE
# ══════════════════════════════════════════════════════════════════════

@st.cache_data(show_spinner="Chargement des ticks Databento...")
def load_databento(folder):
    """Charge tous les CSV trades Databento d'un dossier."""
    pattern = os.path.join(folder, "*.trades.csv")
    files = sorted(glob.glob(pattern))
    if not files:
        return None
    chunks = []
    for f in files:
        df = pd.read_csv(f, usecols=["ts_event", "side", "price", "size"])
        chunks.append(df)
    all_trades = pd.concat(chunks, ignore_index=True)
    all_trades["ts"] = pd.to_datetime(all_trades["ts_event"], utc=True)
    all_trades["price"] = all_trades["price"].astype(float)
    all_trades["size"] = all_trades["size"].astype(int)
    all_trades = all_trades.sort_values("ts").reset_index(drop=True)
    return all_trades


def filter_session(df, start_h, start_m, end_h, end_m):
    """Filtre les trades pour garder uniquement la session US."""
    t = df["ts"].dt
    start_minutes = start_h * 60 + start_m
    end_minutes = end_h * 60 + end_m
    trade_minutes = t.hour * 60 + t.minute
    mask = (trade_minutes >= start_minutes) & (trade_minutes < end_minutes)
    return df[mask].copy()


def build_bars(df, freq_seconds):
    """Agrege les ticks en barres OHLCV + delta."""
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
        n_trades=("size", "count"),
    ).reset_index()
    bars["delta"] = bars["buy_volume"] - bars["sell_volume"]
    bars["cvd"] = bars["delta"].cumsum()
    bars["date"] = bars["bar"].dt.date
    return bars


def detect_absorption(df_ticks, bars, ratio, stacked, min_volume, freq_seconds):
    """
    Detecte les absorptions : un niveau de prix ou les ordres passifs
    absorbent les ordres agressifs sans que le prix bouge.

    Absorption ASK (resistance) : gros volume ask (side=A) a un prix,
    mais le prix ne descend pas -> vendeurs passifs absorbent les acheteurs
    agressifs... Non, c'est l'inverse:

    Absorption BID (support) = gros volume d'achat agressif (side=B)
    absorbe par des vendeurs passifs au ask, prix ne monte pas.
    -> En fait: absorption = gros volume echange a un prix sans mouvement.

    Implementation ATAS-like:
    - Pour chaque barre, on regarde le volume par prix
    - Si a un prix donne, le volume total est >= min_volume
      ET le ratio dominant_side/minority_side >= ratio threshold
      ET il y a >= stacked niveaux consecutifs
    -> C'est une absorption.
    """
    df_ticks = df_ticks.copy()
    df_ticks["bar"] = df_ticks["ts"].dt.floor(f"{freq_seconds}s")

    absorptions = []

    for bar_ts, group in df_ticks.groupby("bar"):
        # Volume par prix et par side
        pv = group.groupby(["price", "side"])["size"].sum().unstack(fill_value=0)
        if "A" not in pv.columns:
            pv["A"] = 0
        if "B" not in pv.columns:
            pv["B"] = 0
        pv["total"] = pv["A"] + pv["B"]
        pv = pv[pv["total"] >= min_volume].sort_index()

        if len(pv) == 0:
            continue

        # Detecter le ratio et le type
        for price_level, row in pv.iterrows():
            ask_vol = row["A"]
            bid_vol = row["B"]
            total = row["total"]

            if total < min_volume:
                continue

            # Absorption ASK: gros volume sell (A) mais prix tient = support casse pas
            # -> les vendeurs agressifs sont absorbes par des acheteurs passifs
            # Le prix devrait descendre mais ne descend pas
            if bid_vol > 0 and ask_vol > 0:
                if ask_vol >= bid_vol * ratio / 100:
                    # Gros ask volume absorbe -> absorption bearish (resistance)
                    absorptions.append({
                        "bar": bar_ts, "price": price_level,
                        "type": "ask", "volume": total,
                        "ask_vol": ask_vol, "bid_vol": bid_vol,
                        "ratio_actual": ask_vol / max(bid_vol, 1)
                    })
                elif bid_vol >= ask_vol * ratio / 100:
                    # Gros bid volume absorbe -> absorption bullish (support)
                    absorptions.append({
                        "bar": bar_ts, "price": price_level,
                        "type": "bid", "volume": total,
                        "ask_vol": ask_vol, "bid_vol": bid_vol,
                        "ratio_actual": bid_vol / max(ask_vol, 1)
                    })

    if not absorptions:
        return pd.DataFrame()

    abs_df = pd.DataFrame(absorptions)
    abs_df["bar"] = pd.to_datetime(abs_df["bar"], utc=True)

    # Filtre stacked: garder seulement si >= N niveaux consecutifs dans la meme barre
    if stacked > 1:
        filtered = []
        for bar_ts, grp in abs_df.groupby("bar"):
            for abs_type in ["ask", "bid"]:
                sub = grp[grp["type"] == abs_type].sort_values("price")
                if len(sub) < stacked:
                    continue
                # Chercher des sequences consecutives (tick_size = 0.25)
                prices = sub["price"].values
                diffs = np.diff(prices)
                consecutive = 1
                best_start = 0
                for i, d in enumerate(diffs):
                    if abs(d - tick_size) < 0.01:
                        consecutive += 1
                        if consecutive >= stacked:
                            # Garder tout le groupe stacked
                            start_idx = i + 2 - consecutive
                            for j in range(start_idx, i + 2):
                                filtered.append(sub.iloc[j].to_dict())
                    else:
                        consecutive = 1
        if filtered:
            abs_df = pd.DataFrame(filtered).drop_duplicates(subset=["bar", "price", "type"])
        else:
            return pd.DataFrame()

    # Agreger par niveau: un niveau = prix moyen du groupe stacked
    levels = []
    abs_df["date"] = pd.to_datetime(abs_df["bar"]).dt.date
    for (date, abs_type), grp in abs_df.groupby(["date", "type"]):
        # Cluster les prix proches (dans 2 pts)
        prices_sorted = grp.sort_values("price")["price"].values
        clusters = []
        current_cluster = [prices_sorted[0]]
        for p in prices_sorted[1:]:
            if p - current_cluster[-1] <= 2.0:
                current_cluster.append(p)
            else:
                clusters.append(current_cluster)
                current_cluster = [p]
        clusters.append(current_cluster)

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


def compute_session_vp(bars):
    """Calcule le Volume Profile par session (date) -> POC, VAH, VAL."""
    vp_levels = {}
    for date, grp in bars.groupby("date"):
        # Volume par prix (utilise close comme approximation)
        price_vol = grp.groupby(grp["close"].round(2))["volume"].sum()
        poc = price_vol.idxmax()

        # Value Area (70% du volume)
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
        vah = max(va_prices)
        val = min(va_prices)
        vp_levels[date] = {"POC": poc, "VAH": vah, "VAL": val}
    return vp_levels


def check_cvd_divergence(bars, bar_idx, lookback=5):
    """
    Verifie la divergence CVD:
    - Prix monte mais CVD descend = divergence bearish
    - Prix descend mais CVD monte = divergence bullish
    """
    if bar_idx < lookback:
        return False, None
    recent = bars.iloc[bar_idx - lookback:bar_idx + 1]
    price_change = recent["close"].iloc[-1] - recent["close"].iloc[0]
    cvd_change = recent["cvd"].iloc[-1] - recent["cvd"].iloc[0]

    if price_change > 0 and cvd_change < 0:
        return True, "bearish"  # prix monte, CVD descend
    elif price_change < 0 and cvd_change > 0:
        return True, "bullish"  # prix descend, CVD monte
    return False, None


def simulate_trade(bars, entry_bar_idx, entry_price, direction, sl_pts, tp_pts_val,
                   tp_mode_str, trail_pts_val=None):
    """
    Simule un trade tick par tick (barre par barre) apres l'entree.
    direction: 'long' ou 'short'
    Retourne le resultat en points.
    """
    if direction == "long":
        sl_price = entry_price - sl_pts
        tp_price = entry_price + tp_pts_val if tp_pts_val else None
    else:
        sl_price = entry_price + sl_pts
        tp_price = entry_price - tp_pts_val if tp_pts_val else None

    trailing_stop = sl_price if tp_mode_str == "Trailing" else None
    best_price = entry_price

    for i in range(entry_bar_idx + 1, min(entry_bar_idx + 120, len(bars))):
        bar = bars.iloc[i]

        if direction == "long":
            # Trailing stop update
            if tp_mode_str == "Trailing" and bar["high"] > best_price:
                best_price = bar["high"]
                trailing_stop = best_price - trail_pts_val

            stop = trailing_stop if tp_mode_str == "Trailing" else sl_price

            # Check SL
            if bar["low"] <= stop:
                return stop - entry_price

            # Check TP
            if tp_price and bar["high"] >= tp_price:
                return tp_price - entry_price

        else:  # short
            if tp_mode_str == "Trailing" and bar["low"] < best_price:
                best_price = bar["low"]
                trailing_stop = best_price + trail_pts_val

            stop = trailing_stop if tp_mode_str == "Trailing" else sl_price

            if bar["high"] >= stop:
                return entry_price - stop

            if tp_price and bar["low"] <= tp_price:
                return entry_price - tp_price

    # Timeout: fermer au close de la derniere barre
    last_close = bars.iloc[min(entry_bar_idx + 119, len(bars) - 1)]["close"]
    if direction == "long":
        return last_close - entry_price
    else:
        return entry_price - last_close


# ══════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════

if st.sidebar.button("Lancer le Backtest", type="primary"):
    # 1. Charger les donnees
    ticks = load_databento(data_dir)
    if ticks is None or len(ticks) == 0:
        st.error("Aucun fichier .trades.csv trouve dans le dossier.")
        st.stop()

    st.success(f"{len(ticks):,} ticks charges ({ticks['ts'].dt.date.nunique()} jours)")

    # 2. Filtrer session US
    ticks_session = filter_session(ticks, session_start_h, session_start_m,
                                   session_end_h, session_end_m)
    st.info(f"{len(ticks_session):,} ticks en session ({session_start_h}:{session_start_m:02d}-{session_end_h}:{session_end_m:02d} UTC)")

    # 3. Construire les barres
    with st.spinner("Construction des barres..."):
        bars = build_bars(ticks_session, bar_seconds)
    st.info(f"{len(bars):,} barres de {bar_seconds}s construites")

    # 4. Detecter les absorptions
    with st.spinner("Detection des absorptions..."):
        abs_levels = detect_absorption(ticks_session, bars, abs_ratio,
                                       abs_stacked, abs_min_volume, bar_seconds)

    if len(abs_levels) == 0:
        st.warning("Aucune absorption detectee. Baisse le Ratio ou le Minimum Volume.")
        st.stop()

    n_days = ticks_session["ts"].dt.date.nunique()
    avg_per_day = len(abs_levels) / n_days if n_days > 0 else 0
    st.success(f"{len(abs_levels)} absorptions detectees sur {n_days} jours "
               f"(moyenne: {avg_per_day:.1f}/session)")

    # 5. Volume Profile par session
    vp_levels = compute_session_vp(bars)

    # 6. Backtester chaque absorption
    with st.spinner("Simulation des trades..."):
        trades = []
        for _, abso in abs_levels.iterrows():
            abs_date = abso["date"]
            abs_price = abso["price"]
            abs_type = abso["type"]
            abs_bar = abso["bar"]

            # Trouver la barre correspondante
            bar_mask = bars["bar"] == abs_bar
            if not bar_mask.any():
                # Chercher la barre la plus proche
                time_diffs = (bars["bar"] - abs_bar).abs()
                bar_idx = time_diffs.idxmin()
            else:
                bar_idx = bars[bar_mask].index[0]

            # Direction du trade
            if abs_type == "ask":
                direction = "short"  # resistance, on short
            else:
                direction = "long"   # support, on long

            # Filtre CVD divergence
            has_cvd_div, cvd_dir = check_cvd_divergence(bars, bar_idx)
            cvd_confirms = False
            if has_cvd_div:
                if abs_type == "ask" and cvd_dir == "bearish":
                    cvd_confirms = True
                elif abs_type == "bid" and cvd_dir == "bullish":
                    cvd_confirms = True

            # Filtre Volume Profile
            on_vp_level = False
            if abs_date in vp_levels:
                vp = vp_levels[abs_date]
                for level_name in ["POC", "VAH", "VAL"]:
                    if abs(abs_price - vp[level_name]) <= vp_tolerance:
                        on_vp_level = True
                        break

            # Simuler le trade
            trail_val = trail_pts if tp_mode == "Trailing" else None
            tp_val = tp_pts if tp_mode != "Trailing" else None
            result_pts = simulate_trade(bars, bar_idx, abs_price, direction,
                                        sl_pts, tp_val, tp_mode, trail_val)

            trades.append({
                "date": abs_date,
                "time": abs_bar,
                "price": abs_price,
                "type": abs_type,
                "direction": direction,
                "volume": abso["volume"],
                "cvd_div": cvd_confirms,
                "vp_level": on_vp_level,
                "result_pts": round(result_pts, 2),
                "win": result_pts > 0,
            })

    trades_df = pd.DataFrame(trades)

    # ── Affichage ────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("Resultats")

    # Tabs pour les differentes vues
    tab_all, tab_cvd, tab_vp, tab_combo, tab_details = st.tabs([
        "Tous les trades", "Absorption + CVD", "Absorption + VP",
        "Absorption + CVD + VP", "Detail des trades"
    ])

    def show_results(df_trades, tab, label):
        """Affiche les stats pour un ensemble de trades."""
        with tab:
            if len(df_trades) == 0:
                st.warning(f"Aucun trade pour: {label}")
                return

            results = df_trades["result_pts"].values
            wins = results[results > 0]
            losses = results[results < 0]
            n_total = len(results)
            n_wins = len(wins)
            n_losses = len(losses)
            winrate = n_wins / n_total

            avg_win = wins.mean() if len(wins) > 0 else 0
            avg_loss = abs(losses.mean()) if len(losses) > 0 else 0
            expectancy = (winrate * avg_win) - ((1 - winrate) * avg_loss)

            gross_profit = wins.sum() if len(wins) > 0 else 0
            gross_loss = abs(losses.sum()) if len(losses) > 0 else 1
            profit_factor = gross_profit / gross_loss

            # Kelly
            if avg_loss > 0 and avg_win > 0:
                b = avg_win / avg_loss
                p = winrate
                kelly = (p * b - (1 - p)) / b
                half_kelly = kelly / 2
            else:
                kelly, half_kelly, b, p = 0, 0, 1, 0.5

            # Equity
            pts_per_tick = 1 / tick_size
            dollar_per_pt = tick_value * pts_per_tick
            risk_per_trade = capital_initial * (risk_pct / 100)
            contracts = max(1, int(risk_per_trade / (sl_pts * dollar_per_pt)))
            pnl_dollars = results * dollar_per_pt * contracts
            equity = capital_initial + np.cumsum(pnl_dollars)
            equity = np.insert(equity, 0, capital_initial)
            peak = np.maximum.accumulate(equity)
            drawdown = (equity - peak) / peak * 100
            max_dd = drawdown.min()

            # Metriques
            st.markdown(f"### {label}")
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Trades", n_total)
            c1.metric("W / L", f"{n_wins} / {n_losses}")
            c2.metric("Winrate", f"{winrate:.1%}")
            c2.metric("Profit Factor", f"{profit_factor:.2f}")
            c3.metric("Esperance", f"{expectancy:.1f} pts")
            c3.metric("Gain moyen", f"{avg_win:.1f} pts")
            c4.metric("Perte moy.", f"{avg_loss:.1f} pts")
            c4.metric("Max DD", f"{max_dd:.1f}%")
            c5.metric("Kelly", f"{kelly:.1%}")
            c5.metric("1/2 Kelly", f"{half_kelly:.1%}")

            # Equity + Drawdown
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                                row_heights=[0.7, 0.3],
                                subplot_titles=["Equity Curve", "Drawdown (%)"])
            fig.add_trace(go.Scatter(
                y=equity, mode="lines", line=dict(color=CYAN, width=2),
                fill="tozeroy", fillcolor="rgba(0,229,255,0.08)", name="Equity"
            ), row=1, col=1)
            fig.add_trace(go.Scatter(
                y=drawdown, mode="lines", line=dict(color=RED, width=1.5),
                fill="tozeroy", fillcolor="rgba(255,51,102,0.12)", name="DD"
            ), row=2, col=1)
            fig.update_layout(height=450, showlegend=False, **DARK)
            fig.update_xaxes(title_text="Trade #", row=2, col=1)
            fig.update_yaxes(title_text="$", row=1, col=1)
            fig.update_yaxes(title_text="%", row=2, col=1)
            st.plotly_chart(fig, use_container_width=True)

            # Distribution P&L
            colors = [GREEN if r > 0 else RED for r in results]
            fig_d = go.Figure()
            fig_d.add_trace(go.Bar(
                x=list(range(1, n_total + 1)), y=results,
                marker_color=colors
            ))
            fig_d.add_hline(y=0, line_dash="dash", line_color="white", opacity=0.3)
            fig_d.add_hline(y=expectancy, line_dash="dot", line_color=CYAN,
                            annotation_text=f"Esperance = {expectancy:.1f} pts")
            fig_d.update_layout(height=300, xaxis_title="Trade #",
                                yaxis_title="Points", **DARK)
            st.plotly_chart(fig_d, use_container_width=True)

            # Kelly curve
            if kelly > 0:
                f_range = np.linspace(0, min(1, kelly * 3), 200)
                g = p * np.log(1 + b * f_range) + (1 - p) * np.log(
                    np.maximum(1 - f_range, 1e-10))
                fig_k = go.Figure()
                fig_k.add_trace(go.Scatter(
                    x=f_range, y=g, mode="lines",
                    line=dict(color=CYAN, width=2), name="Growth"
                ))
                g_k = p * np.log(1 + b * kelly) + (1 - p) * np.log(max(1 - kelly, 1e-10))
                fig_k.add_trace(go.Scatter(
                    x=[kelly], y=[g_k], mode="markers",
                    marker=dict(color=GREEN, size=12), name=f"Kelly={kelly:.1%}"
                ))
                fig_k.add_trace(go.Scatter(
                    x=[half_kelly],
                    y=[p * np.log(1 + b * half_kelly) + (1 - p) * np.log(max(1 - half_kelly, 1e-10))],
                    mode="markers",
                    marker=dict(color=YELLOW, size=12), name=f"1/2K={half_kelly:.1%}"
                ))
                fig_k.update_layout(title="Kelly Criterion", height=300,
                                    xaxis_title="Fraction", yaxis_title="g(f)", **DARK)
                st.plotly_chart(fig_k, use_container_width=True)

            # Verdict
            if expectancy > 0 and winrate > 0.50:
                st.success(f"Edge CONFIRME : {winrate:.1%} WR, {expectancy:.1f} pts/trade, "
                           f"Kelly={kelly:.1%}")
            elif expectancy > 0:
                st.warning(f"Edge marginal : {winrate:.1%} WR, {expectancy:.1f} pts/trade")
            else:
                st.error(f"Pas d'edge : {winrate:.1%} WR, {expectancy:.1f} pts/trade")

    # Tab 1: Tous les trades
    show_results(trades_df, tab_all, "Absorption seule")

    # Tab 2: Absorption + CVD
    show_results(trades_df[trades_df["cvd_div"]], tab_cvd, "Absorption + CVD divergence")

    # Tab 3: Absorption + VP
    show_results(trades_df[trades_df["vp_level"]], tab_vp, "Absorption + Volume Profile")

    # Tab 4: Absorption + CVD + VP
    show_results(trades_df[trades_df["cvd_div"] & trades_df["vp_level"]],
                 tab_combo, "Absorption + CVD + VP")

    # Tab 5: Detail
    with tab_details:
        st.markdown("### Tous les trades")
        display_df = trades_df.copy()
        display_df["result_pts"] = display_df["result_pts"].round(2)
        display_df["win"] = display_df["win"].map({True: "TP", False: "SL"})
        display_df["cvd_div"] = display_df["cvd_div"].map({True: "Oui", False: "Non"})
        display_df["vp_level"] = display_df["vp_level"].map({True: "Oui", False: "Non"})
        st.dataframe(display_df, use_container_width=True, hide_index=True)

        # Export CSV
        csv = display_df.to_csv(index=False)
        st.download_button("Telecharger CSV", csv, "backtest_results.csv", "text/csv")

    # ── Stats par session ────────────────────────────────────────────
    st.markdown("---")
    st.subheader("Absorptions par session")
    daily = trades_df.groupby("date").agg(
        n_trades=("result_pts", "count"),
        n_wins=("win", lambda x: (x == True).sum() if x.dtype == bool else (x == "TP").sum()),
        total_pts=("result_pts", "sum"),
    ).reset_index()
    daily["winrate"] = (daily["n_wins"] / daily["n_trades"] * 100).round(1)

    fig_daily = go.Figure()
    colors_daily = [GREEN if t > 0 else RED for t in daily["total_pts"]]
    fig_daily.add_trace(go.Bar(
        x=daily["date"].astype(str), y=daily["total_pts"],
        marker_color=colors_daily, text=daily["n_trades"],
        textposition="outside", textfont=dict(size=10)
    ))
    fig_daily.update_layout(
        title="P&L par session (nombre de trades au-dessus)",
        xaxis_title="Date", yaxis_title="Points",
        height=350, **DARK
    )
    st.plotly_chart(fig_daily, use_container_width=True)

    # Comparaison des combos
    st.markdown("---")
    st.subheader("Comparaison des filtres")
    combos = {
        "Absorption seule": trades_df,
        "Absorption + CVD": trades_df[trades_df["cvd_div"]],
        "Absorption + VP": trades_df[trades_df["vp_level"]],
        "Absorption + CVD + VP": trades_df[trades_df["cvd_div"] & trades_df["vp_level"]],
    }
    summary = []
    for name, sub in combos.items():
        if len(sub) == 0:
            continue
        r = sub["result_pts"].values
        w = r[r > 0]
        l = r[r < 0]
        wr = len(w) / len(r)
        avg_w = w.mean() if len(w) > 0 else 0
        avg_l = abs(l.mean()) if len(l) > 0 else 0
        exp = (wr * avg_w) - ((1 - wr) * avg_l)
        summary.append({
            "Strategie": name,
            "Trades": len(r),
            "Winrate": f"{wr:.1%}",
            "Gain moy": f"{avg_w:.1f}",
            "Perte moy": f"{avg_l:.1f}",
            "Esperance": f"{exp:.1f} pts",
            "Total": f"{r.sum():.1f} pts",
        })
    st.dataframe(pd.DataFrame(summary), use_container_width=True, hide_index=True)