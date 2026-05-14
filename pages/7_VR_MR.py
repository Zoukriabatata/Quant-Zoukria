"""
VR_MR Deep Analysis — Hurst + Variance Ratio Test Lo-MacKinlay (1988)
Page dédiée à l'optimisation fine des paramètres pour maximiser l'edge.
"""

import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from config import MNQ_CSV

from styles import inject as _inj; _inj()

# ═══════════════════════════════════════════════════════════════════════════
# THEME
# ═══════════════════════════════════════════════════════════════════════════
DARK = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="#050505",
    font=dict(color="#94a3b8", size=11,
              family="'JetBrains Mono','Space Grotesk',monospace"),
    margin=dict(t=48, b=40, l=52, r=24),
    hoverlabel=dict(bgcolor="#0a0a0a", bordercolor="rgba(59,130,246,0.4)",
                    font=dict(size=12, family="JetBrains Mono", color="#f1f5f9")),
)
TEAL = "#06b6d4"; GREEN = "#10b981"; RED = "#ef4444"
YELLOW = "#f59e0b"; BLUE = "#3b82f6"; ORANGE = "#f97316"
PURPLE = "#8b5cf6"; CYAN = "#22d3ee"

st.markdown("""
<style>
.block-container{padding-top:1.2rem;max-width:1400px}
.page-tag{font-family:'JetBrains Mono',monospace;font-size:.65rem;letter-spacing:.2em;
    color:#ca8a04;text-transform:uppercase}
.page-title{font-size:1.8rem;font-weight:700;color:#fff;letter-spacing:-.02em;margin:.3rem 0 0}
.section-label{font-family:'JetBrains Mono',monospace;font-size:.6rem;font-weight:700;
    letter-spacing:.2em;color:#ca8a04;text-transform:uppercase;margin:1.6rem 0 .6rem}
.metric-box{background:rgba(15,23,42,.8);border:1px solid rgba(202,138,4,.25);
    border-radius:8px;padding:.8rem 1rem;font-family:'JetBrains Mono',monospace;font-size:.82rem}
.badge{font-size:1.6rem;font-weight:700;text-align:center;padding:.4rem}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div>
  <div class="page-tag">VR_MR · DEEP ANALYSIS · HURST + VARIANCE RATIO</div>
  <div class="page-title">VR_MR — Optimisation Fine des Paramètres</div>
</div>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════
# FONCTIONS CORE
# ═══════════════════════════════════════════════════════════════════════════

def hurst_exponent(prices):
    p = np.asarray(prices, dtype=float)
    p = p[np.isfinite(p)]
    if len(p) < 20: return 0.5
    max_lag = min(len(p) // 4, 64)
    lags = sorted(set(int(round(2**x)) for x in
                  np.linspace(1, np.log2(max(max_lag, 2)), 8)))
    lags = [l for l in lags if 2 <= l < len(p)]
    if len(lags) < 3: return 0.5
    ll, lt = [], []
    for lag in lags:
        std = np.std(p[lag:] - p[:-lag])
        if std > 0:
            ll.append(np.log(lag)); lt.append(np.log(std))
    if len(ll) < 3: return 0.5
    return float(np.clip(np.polyfit(ll, lt, 1)[0], 0.05, 0.95))


def variance_ratio(returns, q, vr_thresh=0.90):
    """VR(q) = Var(q-returns) / (q × Var(1-return)). Returns (vr, ok)."""
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    if len(r) < max(q * 4, 20): return 1.0, False
    var1 = float(np.var(r, ddof=1))
    if var1 < 1e-15: return 1.0, False
    rq = np.array([r[i:i+q].sum() for i in range(0, len(r)-q+1, q)])
    if len(rq) < 4: return 1.0, False
    vr = float(np.var(rq, ddof=1)) / (q * var1)
    return vr, bool(vr < vr_thresh)


def filter_session(df, sh, sm, eh, em):
    t = df["bar"].dt.hour * 60 + df["bar"].dt.minute
    return df[(t >= sh*60+sm) & (t < eh*60+em)].reset_index(drop=True)


@st.cache_data(show_spinner=False)
def load_csv(csv_path, years_back=5):
    try:
        df = pd.read_csv(csv_path,
                         usecols=["ts_event","open","high","low","close","volume","symbol"])
    except Exception as e:
        return None, str(e)
    df = df[df["symbol"].str.startswith("MNQ") &
            ~df["symbol"].str.contains("-", na=False)].copy()
    if df.empty: return None, "Aucun symbole MNQ"
    df = (df.sort_values("volume", ascending=False)
            .groupby("ts_event", sort=False).first().reset_index())
    df["bar"] = pd.to_datetime(df["ts_event"], utc=True)
    df = df[["bar","open","high","low","close","volume","symbol"]].copy()
    df[["open","high","low","close"]] = df[["open","high","low","close"]].astype(float)
    df["volume"] = df["volume"].fillna(0).astype(int)
    df.sort_values("bar", inplace=True)
    df.drop_duplicates(subset=["bar"], inplace=True)
    df.reset_index(drop=True, inplace=True)
    end_dt = df["bar"].max()
    df = df[df["bar"] >= end_dt - pd.DateOffset(years=years_back)].reset_index(drop=True)
    df["date"] = df["bar"].dt.date
    df["tr"] = np.maximum(df["high"]-df["low"],
               np.maximum(abs(df["high"]-df["close"].shift(1)),
                          abs(df["low"] -df["close"].shift(1))))
    # rollover detection
    day_sym = (df.groupby("date")
                 .apply(lambda g: g.loc[g["volume"].idxmax(),"symbol"] if len(g)>0 else None)
                 .reset_index())
    day_sym.columns = ["date","dominant"]
    day_sym["prev"] = day_sym["dominant"].shift(1)
    day_sym["is_rollover"] = ((day_sym["dominant"] != day_sym["prev"]) &
                               day_sym["prev"].notna())
    day_sym["is_rollover"] = (day_sym["is_rollover"] |
                               day_sym["is_rollover"].shift(-1).fillna(False))
    rollover_dates = set(day_sym.loc[day_sym["is_rollover"],"date"].astype(str))
    df["is_rollover_day"] = df["date"].astype(str).isin(rollover_dates)
    return df, None


def build_cache(full_df, sh, sm, eh, em):
    cache = {}
    for day_key in sorted(full_df["date"].unique()):
        day_df = full_df[full_df["date"] == day_key].copy()
        if day_df["is_rollover_day"].any(): continue
        bars = filter_session(day_df, sh, sm, eh, em)
        if len(bars) < 30: continue
        closes  = bars["close"].values
        returns = np.concatenate([[0], np.diff(np.log(np.maximum(closes, 1e-9)))])
        cache[str(day_key)] = {
            "bars":    bars,
            "closes":  closes,
            "returns": returns,
            "hurst":   hurst_exponent(closes),
        }
    return cache


def simulate_trade(bars, entry_idx, entry_price, direction, sl_pts, tp_price, slip_pts):
    if direction == "long":
        real_entry = entry_price + slip_pts
        sl_price   = real_entry - sl_pts
    else:
        real_entry = entry_price - slip_pts
        sl_price   = real_entry + sl_pts
    for i in range(entry_idx+1, min(entry_idx+120, len(bars))):
        bar = bars.iloc[i]
        if direction == "long":
            if bar["low"]  <= sl_price: return -(sl_pts + slip_pts), i
            if bar["high"] >= tp_price: return (tp_price - slip_pts) - real_entry, i
        else:
            if bar["high"] >= sl_price: return -(sl_pts + slip_pts), i
            if bar["low"]  <= tp_price: return real_entry - (tp_price + slip_pts), i
    exit_idx = min(entry_idx+119, len(bars)-1)
    last = bars.iloc[exit_idx]["close"]
    return ((last - slip_pts) - real_entry if direction == "long"
            else real_entry - (last + slip_pts)), exit_idx


def run_vr_backtest(day_cache, hurst_thr, vr_q, vr_thr, lookback, band_k,
                    sl_mult, tp_ratio, slip_pts, max_td, skip_open, skip_close,
                    risk_pct=0.10, capital=50_000, max_dd=2_000,
                    daily_loss=1_000, profit_target=3_000):
    """Backtest complet VR_MR avec suivi mensuel Apex EOD."""
    all_trades = []
    monthly    = []
    equity     = capital
    peak       = capital
    cur_month  = None
    m_trades   = []
    m_passed   = m_busted = False

    for day_key in sorted(day_cache.keys()):
        month = day_key[:7]
        if month != cur_month:
            if cur_month is not None:
                nw = sum(1 for t in m_trades if t["win"])
                nt = len(m_trades)
                monthly.append({"mois": cur_month,
                                 "pnl":     equity - capital,
                                 "trades":  nt,
                                 "winrate": nw/nt*100 if nt>0 else 0,
                                 "passed":  m_passed,
                                 "busted":  m_busted})
                equity = capital; peak = capital
                m_passed = m_busted = False; m_trades = []
            cur_month = month

        if m_passed or m_busted: continue
        if peak - equity >= max_dd: m_busted = True; continue
        if equity - capital >= profit_target: m_passed = True

        c = day_cache[day_key]
        if c["hurst"] >= hurst_thr: continue
        vr_val, vr_ok = variance_ratio(c["returns"], vr_q, vr_thr)
        if not vr_ok: continue

        bars        = c["bars"]
        closes      = c["closes"]
        n           = len(closes)
        last_exit   = -1
        daily_pnl   = 0.0
        day_td      = 0

        for i in range(lookback, n - skip_close):
            if i < skip_open: continue
            if day_td >= max_td or daily_pnl <= -daily_loss: continue
            if i <= last_exit: continue

            win   = closes[i - lookback: i]
            mid   = float(win.mean())
            std   = float(win.std())
            if std == 0: continue
            price = closes[i]
            z     = (price - mid) / std
            if abs(z) < band_k: continue

            direction = "short" if z > 0 else "long"
            sl_pts    = max(3.0, sl_mult * std)
            sl_pts    = min(sl_pts, 20.0)
            tp_price  = price + tp_ratio * (mid - price)

            dd_used     = max(0.0, peak - equity)
            dd_rem      = max(0.0, max_dd - dd_used)
            risk        = max(50.0, min(risk_pct * dd_rem, daily_loss * 0.40))
            loss_ctr    = sl_pts * 2.0
            if loss_ctr <= 0: continue
            contracts   = max(1, min(60, int(risk / loss_ctr)))
            if contracts * loss_ctr > max(0.0, daily_loss + daily_pnl):
                contracts = max(1, int(max(0.0, daily_loss + daily_pnl) / loss_ctr))
            if contracts <= 0: continue

            result_pts, exit_bar = simulate_trade(
                bars, i, price, direction, sl_pts, tp_price, slip_pts)
            last_exit  = exit_bar
            pnl        = result_pts * 2.0 * contracts
            equity    += pnl
            daily_pnl += pnl
            day_td    += 1
            if equity > peak: peak = equity
            win_trade = pnl > 0
            all_trades.append({"date": str(c["bars"].iloc[i]["date"]),
                                "win": win_trade, "pnl": pnl,
                                "pts": result_pts, "z": z,
                                "contracts": contracts, "direction": direction,
                                "vr": vr_val, "hurst": c["hurst"]})
            m_trades.append({"win": win_trade, "pnl": pnl})

    if len(all_trades) < 10: return None

    df       = pd.DataFrame(all_trades)
    n_tr     = len(df)
    wr       = float(df["win"].mean())
    pos_pnl  = df[df["pnl"]>0]["pnl"].sum()
    neg_pnl  = abs(df[df["pnl"]<0]["pnl"].sum())
    pf       = pos_pnl / max(neg_pnl, 0.01)
    total    = df["pnl"].sum()

    daily_s  = df.groupby("date")["pnl"].sum()
    daily_s.index = pd.to_datetime(daily_s.index)
    bdays    = pd.bdate_range(daily_s.index.min(), daily_s.index.max())
    daily_r  = daily_s.reindex(bdays, fill_value=0) / capital
    sharpe   = float(daily_r.mean()/daily_r.std()*np.sqrt(252)) if daily_r.std()>0 else 0

    max_dd_pct = 0.0
    for m in monthly:
        mdf = df[df["date"].str.startswith(m["mois"])]
        if len(mdf)==0: continue
        eq_m = np.concatenate([[capital], np.cumsum(mdf["pnl"].values)+capital])
        pk_m = np.maximum.accumulate(eq_m)
        max_dd_pct = max(max_dd_pct, float((pk_m-eq_m).max()/capital*100))

    n_months  = len(monthly)
    n_pass    = sum(1 for m in monthly if m["passed"])
    n_bust    = sum(1 for m in monthly if m["busted"])

    return {
        "n_trades":      n_tr,
        "winrate":       round(wr*100, 1),
        "profit_factor": round(pf, 3),
        "sharpe":        round(sharpe, 3),
        "total_pnl":     round(total, 0),
        "max_dd_pct":    round(max_dd_pct, 2),
        "pass_rate":     round(n_pass/max(n_months,1)*100, 0),
        "bust_rate":     round(n_bust/max(n_months,1)*100, 0),
        "avg_win":       round(df[df["pnl"]>0]["pnl"].mean() if df["pnl"].gt(0).any() else 0, 1),
        "avg_loss":      round(abs(df[df["pnl"]<0]["pnl"].mean()) if df["pnl"].lt(0).any() else 0, 1),
        "avg_vr":        round(float(df["vr"].mean()), 3),
        "avg_hurst":     round(float(df["hurst"].mean()), 3),
        "trades_per_day": round(n_tr/max(len(bdays),1), 2),
        "_df":           df,
        "_monthly":      monthly,
    }


def composite_score(r):
    """Score composite pour le classement de l'optimisation."""
    if r is None: return -999.0
    pf_sc   = min(max(r["profit_factor"] - 1.0, 0) / 2.0, 1.0) * 0.35
    sh_sc   = min(max(r["sharpe"], 0) / 2.5, 1.0) * 0.25
    wr_sc   = min(max(r["winrate"] - 30, 0) / 30, 1.0) * 0.15
    ps_sc   = min(r["pass_rate"] / 60.0, 1.0) * 0.15
    fr_sc   = min(r["trades_per_day"] / 0.5, 1.0) * 0.10
    dd_pen  = -0.50 if r["max_dd_pct"] > 5.0 else 0.0
    pf_pen  = -0.35 if r["profit_factor"] < 1.3 else 0.0
    tr_pen  = -0.20 if r["n_trades"] < 30 else 0.0
    return round(pf_sc + sh_sc + wr_sc + ps_sc + fr_sc + dd_pen + pf_pen + tr_pen, 4)


def edge_badge(r):
    c = {
        "PF ≥ 1.9":    r["profit_factor"] >= 1.9,
        "Sharpe ≥ 1.9": r["sharpe"]        >= 1.9,
        "WR ≥ 30%":    r["winrate"]        >= 30,
        "DD < 5%":     r["max_dd_pct"]     <  5.0,
        "Trades OK":   96 <= r["n_trades"] <= 720,
    }
    n = sum(c.values())
    details = " · ".join(f"{'✓' if v else '✗'} {k}" for k,v in c.items())
    badge = ("🏆 EDGE PARFAIT" if n==5 else "🌟 EDGE FORT" if n>=4
             else "✅ EDGE PARTIEL" if n>=3 else "❌ PAS D'EDGE")
    return badge, details


# ═══════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════

st.sidebar.markdown("## VR_MR — Paramètres fins")

st.sidebar.markdown("### Données")
years_back  = st.sidebar.slider("Années de données", 1, 5, 5)
session_sh  = st.sidebar.number_input("Session début (heure UTC)", value=14)
session_sm  = st.sidebar.number_input("Session début (min)", value=30)
session_eh  = st.sidebar.number_input("Session fin (heure UTC)", value=21)
session_em  = st.sidebar.number_input("Session fin (min)", value=0)
skip_open   = st.sidebar.number_input("Skip barres ouverture", value=15, step=5)
skip_close  = st.sidebar.number_input("Skip barres clôture", value=15, step=5)

st.sidebar.markdown("### Couche 1 — Hurst Gate")
hurst_thr = st.sidebar.slider("Hurst threshold", 0.40, 0.52, 0.45, 0.01,
    help="H < seuil → session MR active. 0.45 = filtre strict, 0.50 = large.")

st.sidebar.markdown("### Couche 1b — VR Gate")
vr_q   = st.sidebar.slider("VR q (horizon barres)", 2, 20, 8, 1,
    help="Horizon temporel du test. q=8 = 8 min sur M1.")
vr_thr = st.sidebar.slider("VR threshold (seuil max)", 0.70, 0.99, 0.90, 0.01,
    help="VR < threshold → anti-persistance confirmée. 0.90 = strict, 0.99 = large.")

st.sidebar.markdown("### Couche 2+3 — Signal")
lookback = st.sidebar.slider("Lookback rolling mean (barres)", 10, 100, 30, 5,
    help="Fenêtre pour calculer μ et σ. Court = rapide, Long = stable.")
band_k   = st.sidebar.slider("Band k (Z-score entrée)", 1.0, 4.0, 2.0, 0.25,
    help="Nombre de σ minimum pour entrer. Haut = rares mais fiables.")

st.sidebar.markdown("### Risk Management")
sl_mult    = st.sidebar.slider("SL = k × σ", 0.5, 3.0, 1.25, 0.25)
tp_ratio   = st.sidebar.slider("TP ratio", 0.3, 1.0, 0.7, 0.1)
risk_pct   = st.sidebar.slider("Risk % DD / trade", 0.05, 0.30, 0.10, 0.05)
max_td     = st.sidebar.number_input("Max trades/jour", 1, 5, 2)

st.sidebar.markdown("### Grid Search")
grid_mode  = st.sidebar.selectbox("Axes heatmap",
    ["band_k × vr_q", "band_k × lookback", "vr_q × lookback",
     "hurst_thr × band_k", "vr_thr × band_k"])
grid_metric = st.sidebar.selectbox("Métrique heatmap", ["profit_factor","sharpe","winrate","pass_rate"])

run_single = st.sidebar.button("▶ Lancer l'analyse",      type="primary", use_container_width=True)
run_grid   = st.sidebar.button("🔲 Grid Search",                          use_container_width=True)
run_wf     = st.sidebar.button("🔁 Walk-Forward",                         use_container_width=True)
run_optim  = st.sidebar.button("🔥 Optimisation complète",                use_container_width=True)
run_phase2 = st.sidebar.button("🧬 Phase 2 — Combo Hurst",                use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════════
# DATA LOADING
# ═══════════════════════════════════════════════════════════════════════════

if not (run_single or run_grid or run_wf or run_optim or run_phase2):
    st.info("Configure les paramètres à gauche, puis clique **Lancer l'analyse**.")
    st.markdown("""
<div style='background:rgba(202,138,4,.08);border:1px solid rgba(202,138,4,.3);
     border-radius:8px;padding:1rem 1.3rem;font-family:monospace;font-size:.85rem;line-height:2'>
<b>Architecture VR_MR :</b><br/>
Couche 1 → Hurst &lt; threshold &nbsp;&nbsp;→ session anti-persistante (filtre journée)<br/>
Couche 1b → VR(q) &lt; vr_threshold → confirmé statistiquement (Lo-MacKinlay)<br/>
Couche 2 → rolling mean(lookback) &nbsp;→ fair value estimée<br/>
Couche 3 → |Z| &gt; band_k &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;→ prix assez étiré pour entrer<br/>
EXIT &nbsp;&nbsp; → retour à la mean &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;→ Z ≈ 0<br/>
STOP &nbsp;&nbsp; → SL = sl_mult × σ &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;→ invalidation du signal
</div>
""", unsafe_allow_html=True)
    st.stop()

with st.spinner("Chargement des données MNQ…"):
    full_df, err = load_csv(MNQ_CSV, years_back)

if err:
    st.error(f"Erreur chargement : {err}")
    st.stop()

with st.spinner("Calcul cache journalier (Hurst + returns)…"):
    day_cache = build_cache(full_df, session_sh, session_sm, session_eh, session_em)

n_days = len(day_cache)
slip   = 0.25

tab_analyse, tab_grid, tab_wf, tab_trades, tab_optim, tab_phase2 = st.tabs(
    ["📊 Analyse", "🔲 Grid Search", "🔁 Walk-Forward", "📋 Trades",
     "🔥 Optimisation", "🧬 Phase 2 — Hurst Combo"])

# ═══════════════════════════════════════════════════════════════════════════
# TAB 1 — ANALYSE SINGLE RUN
# ═══════════════════════════════════════════════════════════════════════════

with tab_analyse:
    if not (run_single or run_grid or run_wf):
        st.info("Lance une analyse via la sidebar.")
    else:
        with st.spinner("Backtest VR_MR en cours…"):
            res = run_vr_backtest(
                day_cache, hurst_thr, vr_q, vr_thr, lookback, band_k,
                sl_mult, tp_ratio, slip, max_td, skip_open, skip_close, risk_pct)

        if res is None:
            st.error("Moins de 10 trades — paramètres trop restrictifs, élargis les seuils.")
            st.stop()

        badge, details = edge_badge(res)
        st.markdown(f"<div class='badge'>{badge}</div>", unsafe_allow_html=True)
        st.caption(details)

        # Métriques principales
        st.markdown("<p class='section-label'>Métriques de performance</p>",
                    unsafe_allow_html=True)
        c1,c2,c3,c4,c5 = st.columns(5)
        c1.metric("Trades total",  res["n_trades"])
        c2.metric("Profit Factor", f"{res['profit_factor']:.3f}",
                  delta="✓" if res["profit_factor"]>=1.9 else "✗ < 1.9",
                  delta_color="normal" if res["profit_factor"]>=1.9 else "inverse")
        c3.metric("Sharpe Ratio",  f"{res['sharpe']:.3f}",
                  delta="✓" if res["sharpe"]>=1.9 else "✗ < 1.9",
                  delta_color="normal" if res["sharpe"]>=1.9 else "inverse")
        c4.metric("Win Rate",      f"{res['winrate']:.1f}%")
        c5.metric("Max DD",        f"{res['max_dd_pct']:.2f}%",
                  delta_color="inverse" if res["max_dd_pct"]>=5 else "off")

        c1b,c2b,c3b,c4b,c5b = st.columns(5)
        c1b.metric("P&L total",    f"${res['total_pnl']:+,.0f}")
        c2b.metric("Pass rate",    f"{res['pass_rate']:.0f}%")
        c3b.metric("Bust rate",    f"{res['bust_rate']:.0f}%")
        c4b.metric("H moyen trade",f"{res['avg_hurst']:.3f}")
        c5b.metric("VR moyen",     f"{res['avg_vr']:.3f}")

        # Equity curve
        st.markdown("<p class='section-label'>Equity curve</p>", unsafe_allow_html=True)
        df_t  = res["_df"]
        eq    = np.concatenate([[50_000], np.cumsum(df_t["pnl"].values)+50_000])
        pk    = np.maximum.accumulate(eq)
        dd_eq = eq - pk

        fig_eq = make_subplots(rows=2, cols=1, row_heights=[0.72, 0.28],
                               shared_xaxes=True, vertical_spacing=0.04)
        fig_eq.add_trace(go.Scatter(y=eq, mode="lines", name="Equity",
                                    line=dict(color=CYAN, width=2)), row=1, col=1)
        fig_eq.add_trace(go.Scatter(y=pk, mode="lines", name="Peak",
                                    line=dict(color=GREEN, width=1, dash="dot"),
                                    opacity=0.5), row=1, col=1)
        fig_eq.add_hline(y=53_000, line_color=GREEN, line_dash="dash",
                         opacity=0.4, annotation_text="Target +$3K", row=1, col=1)
        fig_eq.add_hline(y=48_000, line_color=RED, line_dash="dash",
                         opacity=0.4, annotation_text="Bust -$2K", row=1, col=1)
        fig_eq.add_trace(go.Scatter(y=dd_eq, mode="lines", name="Drawdown",
                                    line=dict(color=RED, width=1),
                                    fill="tozeroy", opacity=0.4), row=2, col=1)
        fig_eq.update_layout(height=480, showlegend=True,
                              yaxis_title="Équité ($)", yaxis2_title="DD ($)", **DARK)
        st.plotly_chart(fig_eq, use_container_width=True)

        # Monthly P&L bar
        st.markdown("<p class='section-label'>P&L mensuel</p>", unsafe_allow_html=True)
        mon_df = pd.DataFrame(res["_monthly"])
        if len(mon_df) > 0:
            colors_m = [GREEN if p>0 else RED for p in mon_df["pnl"]]
            fig_m = go.Figure(go.Bar(
                x=mon_df["mois"], y=mon_df["pnl"],
                marker_color=colors_m, text=mon_df["pnl"].apply(lambda x: f"${x:+,.0f}"),
                textposition="outside"))
            fig_m.add_hline(y=3000, line_color=GREEN, line_dash="dash",
                            annotation_text="Target $3K")
            fig_m.add_hline(y=-2000, line_color=RED, line_dash="dash",
                            annotation_text="Bust -$2K")
            fig_m.update_layout(title="P&L par mois (simulation Apex EOD)",
                                 height=350, showlegend=False, **DARK)
            st.plotly_chart(fig_m, use_container_width=True)

        # Diagnostique
        st.markdown("<p class='section-label'>Diagnostique</p>", unsafe_allow_html=True)
        diags = []
        if res["profit_factor"] < 1.9:
            diags.append(("⚠", f"PF {res['profit_factor']:.3f} — "
                          f"cible 1.9 · manque {1.9-res['profit_factor']:.3f} points"))
        if res["sharpe"] < 1.9:
            diags.append(("⚠", f"Sharpe {res['sharpe']:.3f} — "
                          f"cible 1.9 · manque {1.9-res['sharpe']:.3f}"))
        if res["pass_rate"] == 0:
            avg_m = res["total_pnl"] / max(len(res["_monthly"]),1)
            diags.append(("🔴", f"Pass rate 0% — P&L moyen {avg_m:+.0f}$/mois "
                          f"(cible $3,000) · sizing trop bas pour passer Apex"))
        if res["n_trades"] < 96:
            diags.append(("⚠", f"Trades {res['n_trades']}/an — trop peu (cible ≥ 96)"))
        if res["n_trades"] > 720:
            diags.append(("⚠", f"Trades {res['n_trades']}/an — trop (filtre trop lâche)"))
        if not diags:
            st.success("✓ Tous les critères sont dans les cibles.")
        for icon, msg in diags:
            if "🔴" in icon: st.error(f"{icon} {msg}")
            else:            st.warning(f"{icon} {msg}")

        # Sizing pour passer Apex
        avg_monthly = res["total_pnl"] / max(len(res["_monthly"]),1)
        if avg_monthly > 0 and res["profit_factor"] > 1.0:
            needed_scale = 3000 / avg_monthly
            needed_risk  = risk_pct * needed_scale
            st.markdown("<p class='section-label'>Sizing pour viser Apex $3K/mois</p>",
                        unsafe_allow_html=True)
            sz_rows = []
            for rp in [0.05, 0.10, 0.15, 0.20, 0.25, 0.30]:
                scale    = rp / max(risk_pct, 0.01)
                est_pnl  = avg_monthly * scale
                est_bust = min(0.95, res["bust_rate"]/100 * scale**1.4)
                viable   = ("✅" if est_pnl >= 3000 and est_bust < 0.30
                            else "⚠" if est_pnl >= 1500 else "❌")
                sz_rows.append({
                    "Risk %/trade": f"{rp*100:.0f}%",
                    "P&L est./mois": f"${est_pnl:+,.0f}",
                    "Bust est.":     f"{est_bust*100:.0f}%",
                    "Viable Apex":   viable,
                })
            st.dataframe(pd.DataFrame(sz_rows), use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════════════════
# TAB 2 — GRID SEARCH
# ═══════════════════════════════════════════════════════════════════════════

with tab_grid:
    if not run_grid:
        st.info("Clique **Lancer le Grid Search** dans la sidebar.")
        st.markdown("""
<div class='metric-box'>
<b>Comment ça marche :</b><br/>
Le Grid Search teste toutes les combinaisons des 2 paramètres sélectionnés<br/>
en maintenant les autres fixes (valeurs sidebar).<br/>
Résultat : heatmap interactive — trouve les zones optimales.
</div>""", unsafe_allow_html=True)
    else:
        # Define grids per axis choice
        grids = {
            "band_k × vr_q":      (np.arange(1.0, 4.0, 0.25), range(2, 18, 2),   "band_k", "vr_q"),
            "band_k × lookback":  (np.arange(1.0, 4.0, 0.25), range(10, 101, 10),"band_k","lookback"),
            "vr_q × lookback":    (range(2, 18, 2), range(10, 101, 10),           "vr_q",  "lookback"),
            "hurst_thr × band_k": (np.arange(0.40, 0.52, 0.01), np.arange(1.0, 4.0, 0.25),
                                   "hurst_thr","band_k"),
            "vr_thr × band_k":    (np.arange(0.70, 1.00, 0.03), np.arange(1.0, 4.0, 0.25),
                                   "vr_thr","band_k"),
        }
        x_vals, y_vals, x_name, y_name = grids[grid_mode]
        x_vals = list(x_vals); y_vals = list(y_vals)
        total  = len(x_vals) * len(y_vals)

        prog = st.progress(0, text=f"Grid Search {grid_mode} — 0/{total}")
        matrix   = np.full((len(y_vals), len(x_vals)), np.nan)
        n_matrix = np.full((len(y_vals), len(x_vals)), 0)
        done = 0

        param_defaults = dict(
            hurst_thr=hurst_thr, vr_q=vr_q, vr_thr=vr_thr,
            lookback=lookback, band_k=band_k)

        for xi, xv in enumerate(x_vals):
            for yi, yv in enumerate(y_vals):
                p = dict(param_defaults)
                p[x_name] = float(xv)
                p[y_name] = float(yv)
                r = run_vr_backtest(
                    day_cache,
                    p["hurst_thr"], int(p["vr_q"]) if "vr_q"==x_name or "vr_q"==y_name
                                    else p["vr_q"],
                    p["vr_thr"], int(p["lookback"]), p["band_k"],
                    sl_mult, tp_ratio, slip, max_td, skip_open, skip_close, risk_pct)
                if r:
                    matrix[yi, xi]   = r[grid_metric]
                    n_matrix[yi, xi] = r["n_trades"]
                done += 1
                prog.progress(done/total, text=f"Grid {x_name}={xv:.2f} {y_name}={yv:.2f} ({done}/{total})")

        prog.empty()

        # Heatmap
        st.markdown(f"<p class='section-label'>Heatmap — {grid_metric} ({grid_mode})</p>",
                    unsafe_allow_html=True)
        x_labels = [f"{v:.2f}" for v in x_vals]
        y_labels = [f"{v:.2f}" for v in y_vals]
        fig_hm = go.Figure(go.Heatmap(
            z=matrix, x=x_labels, y=y_labels,
            colorscale="RdYlGn", text=np.round(matrix, 2),
            texttemplate="%{text}", textfont=dict(size=9),
            hovertemplate=f"{x_name}=%{{x}}<br>{y_name}=%{{y}}<br>{grid_metric}=%{{z:.3f}}<extra></extra>",
            colorbar=dict(title=grid_metric),
        ))
        # Overlay best cell
        best_idx = np.unravel_index(np.nanargmax(matrix), matrix.shape)
        fig_hm.add_trace(go.Scatter(
            x=[x_labels[best_idx[1]]], y=[y_labels[best_idx[0]]],
            mode="markers", marker=dict(symbol="star", size=16, color=YELLOW),
            name=f"Best {grid_metric}={matrix[best_idx]:.3f}"))
        fig_hm.update_layout(
            title=f"Heatmap {grid_metric} — {grid_mode}",
            xaxis_title=x_name, yaxis_title=y_name, height=500, **DARK)
        st.plotly_chart(fig_hm, use_container_width=True)

        # Best params
        bx = float(x_vals[best_idx[1]])
        by = float(y_vals[best_idx[0]])
        best_val = matrix[best_idx]
        st.success(
            f"**Meilleur {grid_metric} : {best_val:.3f}**  \n"
            f"`{x_name} = {bx:.2f}` · `{y_name} = {by:.2f}`  \n"
            f"Trades : {n_matrix[best_idx]}")

        # Top 10 combos table
        st.markdown("<p class='section-label'>Top 10 combinaisons</p>",
                    unsafe_allow_html=True)
        rows = []
        for xi, xv in enumerate(x_vals):
            for yi, yv in enumerate(y_vals):
                if not np.isnan(matrix[yi, xi]):
                    rows.append({x_name: round(float(xv),2), y_name: round(float(yv),2),
                                 grid_metric: round(matrix[yi,xi],3),
                                 "Trades": n_matrix[yi,xi]})
        top10 = pd.DataFrame(rows).sort_values(grid_metric, ascending=False).head(10)
        st.dataframe(top10, use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════════════════
# TAB 3 — WALK-FORWARD
# ═══════════════════════════════════════════════════════════════════════════

with tab_wf:
    if not run_wf:
        st.info("Clique **Walk-Forward** dans la sidebar.")
        st.markdown("""
<div class='metric-box'>
<b>Walk-Forward Test — validation OOS :</b><br/>
Train : premières années → trouve les meilleurs paramètres (in-sample)<br/>
Test  : dernières années → applique ces params sur données jamais vues (out-of-sample)<br/>
Si le Test ≈ Train → l'edge est RÉEL. Si Test &lt;&lt; Train → overfit.
</div>""", unsafe_allow_html=True)
    else:
        # Split cache in two halves
        all_days = sorted(day_cache.keys())
        n_d      = len(all_days)
        split_n  = int(n_d * 0.60)  # 60% train, 40% test
        train_keys = all_days[:split_n]
        test_keys  = all_days[split_n:]
        train_cache = {k: day_cache[k] for k in train_keys}
        test_cache  = {k: day_cache[k] for k in test_keys}

        st.markdown(
            f"Train : **{train_keys[0]} → {train_keys[-1]}** ({len(train_keys)} jours)  \n"
            f"Test  : **{test_keys[0]} → {test_keys[-1]}** ({len(test_keys)} jours)",
        )

        # Grid search on TRAIN
        st.markdown("<p class='section-label'>1. Grid Search sur Train (60%)</p>",
                    unsafe_allow_html=True)
        band_k_vals  = [1.5, 1.75, 2.0, 2.25, 2.5, 2.75, 3.0]
        vr_q_vals    = [4, 6, 8, 10, 12]
        lookback_vals= [20, 30, 40, 60]
        total_wf     = len(band_k_vals) * len(vr_q_vals) * len(lookback_vals)
        prog_wf = st.progress(0, text=f"Train grid 0/{total_wf}…")
        best_train = None; best_score = -9999; done_wf = 0

        for bk in band_k_vals:
            for vq in vr_q_vals:
                for lb in lookback_vals:
                    r = run_vr_backtest(
                        train_cache, hurst_thr, vq, vr_thr, lb, bk,
                        sl_mult, tp_ratio, slip, max_td, skip_open, skip_close, risk_pct)
                    done_wf += 1
                    prog_wf.progress(done_wf/total_wf,
                                     text=f"Train bk={bk} q={vq} lb={lb} ({done_wf}/{total_wf})")
                    if r is None: continue
                    sc = (0.4*min(max(r["profit_factor"]-1,0)/2,1) +
                          0.3*min(max(r["sharpe"],0)/2.5,1) +
                          0.3*min(r["winrate"]/60,1))
                    if sc > best_score:
                        best_score = sc
                        best_train = r
                        best_params_wf = {"band_k": bk, "vr_q": vq, "lookback": lb}

        prog_wf.empty()

        if best_train is None:
            st.error("Aucun résultat sur le train — paramètres trop restrictifs.")
        else:
            st.success(
                f"Meilleurs params TRAIN : `band_k={best_params_wf['band_k']}` · "
                f"`vr_q={best_params_wf['vr_q']}` · `lookback={best_params_wf['lookback']}`  \n"
                f"PF={best_train['profit_factor']:.3f} · Sharpe={best_train['sharpe']:.3f} · "
                f"WR={best_train['winrate']:.1f}%")

            # Apply to TEST
            st.markdown("<p class='section-label'>2. Application sur Test OOS (40%)</p>",
                        unsafe_allow_html=True)
            res_test = run_vr_backtest(
                test_cache, hurst_thr,
                best_params_wf["vr_q"], vr_thr,
                best_params_wf["lookback"], best_params_wf["band_k"],
                sl_mult, tp_ratio, slip, max_td, skip_open, skip_close, risk_pct)

            if res_test is None:
                st.warning("Pas assez de trades sur la période de test OOS.")
            else:
                badge_train, _ = edge_badge(best_train)
                badge_test, _  = edge_badge(res_test)

                col_tr, col_te = st.columns(2)
                with col_tr:
                    st.markdown(f"**TRAIN (IS)** — {badge_train}")
                    st.metric("PF",     f"{best_train['profit_factor']:.3f}")
                    st.metric("Sharpe", f"{best_train['sharpe']:.3f}")
                    st.metric("WR",     f"{best_train['winrate']:.1f}%")
                    st.metric("Trades", best_train["n_trades"])
                with col_te:
                    st.markdown(f"**TEST (OOS)** — {badge_test}")
                    delta_pf = res_test["profit_factor"] - best_train["profit_factor"]
                    st.metric("PF",     f"{res_test['profit_factor']:.3f}",
                              delta=f"{delta_pf:+.3f}",
                              delta_color="normal" if delta_pf >= -0.15 else "inverse")
                    delta_sh = res_test["sharpe"] - best_train["sharpe"]
                    st.metric("Sharpe", f"{res_test['sharpe']:.3f}",
                              delta=f"{delta_sh:+.3f}",
                              delta_color="normal" if delta_sh >= -0.3 else "inverse")
                    st.metric("WR",     f"{res_test['winrate']:.1f}%")
                    st.metric("Trades", res_test["n_trades"])

                # Verdict
                decay_pf = best_train["profit_factor"] - res_test["profit_factor"]
                if decay_pf < 0.15:
                    st.success("✅ **Edge ROBUSTE** — La dégradation OOS est faible (< 0.15 PF). "
                               "L'edge est réel et non curve-fitted.")
                elif decay_pf < 0.35:
                    st.warning("⚠ **Edge PARTIEL** — Dégradation modérée OOS. "
                               "L'edge existe mais est sensible aux paramètres.")
                else:
                    st.error("❌ **Overfit probable** — Forte dégradation OOS. "
                             "L'edge train-sample ne tient pas sur données non vues.")


# ═══════════════════════════════════════════════════════════════════════════
# TAB 4 — TRADES ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════

with tab_trades:
    if not (run_single or run_grid or run_wf):
        st.info("Lance une analyse d'abord.")
    else:
        # Use single run result if available, else recompute
        _r = None
        if run_single and "res" in dir() and res is not None: _r = res
        if _r is None:
            with st.spinner("Calcul pour l'analyse des trades…"):
                _r = run_vr_backtest(
                    day_cache, hurst_thr, vr_q, vr_thr, lookback, band_k,
                    sl_mult, tp_ratio, slip, max_td, skip_open, skip_close, risk_pct)

        if _r is None:
            st.error("Pas assez de trades.")
        else:
            df_t = _r["_df"]

            st.markdown("<p class='section-label'>Distribution des P&L par trade</p>",
                        unsafe_allow_html=True)
            fig_hist = go.Figure()
            wins  = df_t[df_t["win"]]["pnl"]
            loses = df_t[~df_t["win"]]["pnl"]
            fig_hist.add_trace(go.Histogram(x=wins, name="Gagnants",
                                            marker_color=GREEN, opacity=0.7, nbinsx=40))
            fig_hist.add_trace(go.Histogram(x=loses, name="Perdants",
                                            marker_color=RED, opacity=0.7, nbinsx=40))
            fig_hist.update_layout(barmode="overlay", title="Distribution P&L/trade",
                                   height=320, **DARK)
            st.plotly_chart(fig_hist, use_container_width=True)

            # Z-score at entry vs outcome
            st.markdown("<p class='section-label'>Z-score d'entrée vs résultat</p>",
                        unsafe_allow_html=True)
            fig_z = go.Figure()
            fig_z.add_trace(go.Scatter(
                x=df_t["z"].abs(), y=df_t["pnl"], mode="markers",
                marker=dict(color=[GREEN if w else RED for w in df_t["win"]],
                            size=4, opacity=0.6),
                name="Trades"))
            fig_z.add_hline(y=0, line_color="#444")
            fig_z.update_layout(title="|Z-score entrée| vs P&L trade",
                                 xaxis_title="|Z-score|", yaxis_title="P&L ($)",
                                 height=320, **DARK)
            st.plotly_chart(fig_z, use_container_width=True)

            # VR distribution on trading days
            st.markdown("<p class='section-label'>Distribution du VR(q) sur les jours tradés</p>",
                        unsafe_allow_html=True)
            fig_vr = go.Figure()
            fig_vr.add_trace(go.Histogram(
                x=df_t["vr"], nbinsx=30, marker_color=CYAN, opacity=0.8, name="VR"))
            fig_vr.add_vline(x=vr_thr, line_color=YELLOW, line_dash="dash",
                             annotation_text=f"seuil {vr_thr}")
            fig_vr.update_layout(title=f"VR(q={vr_q}) sur les jours tradés",
                                  xaxis_title="VR", height=280, **DARK)
            st.plotly_chart(fig_vr, use_container_width=True)

            # Long vs Short stats
            st.markdown("<p class='section-label'>Long vs Short</p>",
                        unsafe_allow_html=True)
            ls_rows = []
            for side in ["long", "short"]:
                sub = df_t[df_t["direction"]==side]
                if len(sub)==0: continue
                ls_rows.append({
                    "Direction":  side.upper(),
                    "Trades":     len(sub),
                    "WR %":       round(sub["win"].mean()*100, 1),
                    "PF":         round(sub[sub["pnl"]>0]["pnl"].sum() /
                                        max(abs(sub[sub["pnl"]<0]["pnl"].sum()), 0.01), 2),
                    "P&L total":  f"${sub['pnl'].sum():+,.0f}",
                    "Moy/trade":  f"${sub['pnl'].mean():+.0f}",
                })
            st.dataframe(pd.DataFrame(ls_rows), use_container_width=True, hide_index=True)

            # Hurst distribution on trading days
            st.markdown("<p class='section-label'>Hurst au moment du trade</p>",
                        unsafe_allow_html=True)
            fig_h = go.Figure()
            fig_h.add_trace(go.Histogram(
                x=df_t["hurst"], nbinsx=25, marker_color=PURPLE, opacity=0.8))
            fig_h.add_vline(x=hurst_thr, line_color=RED, line_dash="dash",
                            annotation_text=f"seuil {hurst_thr}")
            fig_h.update_layout(title="Distribution Hurst — jours tradés",
                                  xaxis_title="H", height=280, **DARK)
            st.plotly_chart(fig_h, use_container_width=True)

            # Raw trades table
            with st.expander("Voir tous les trades"):
                st.dataframe(df_t[["date","direction","pnl","pts","z","contracts",
                                    "vr","hurst","win"]].style.applymap(
                    lambda v: "color:#10b981" if v is True else
                              ("color:#ef4444" if v is False else ""),
                    subset=["win"]), use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════
# TAB 5 — OPTIMISATION COMPLÈTE (tous les angles)
# ═══════════════════════════════════════════════════════════════════════════

with tab_optim:
    st.markdown("<p class='section-label'>Optimisation exhaustive — signal + risk management</p>",
                unsafe_allow_html=True)
    st.markdown("""
<div class='metric-box'>
Teste <b>toutes les combinaisons</b> des paramètres signal et risk en parallèle.<br/>
Hurst threshold = valeur fixée dans la sidebar (appliqué à toutes les combos).<br/>
Phase 2 ajoute ensuite le sweep Hurst sur les meilleurs résultats trouvés ici.
</div>""", unsafe_allow_html=True)

    # ── Sélection des valeurs à tester ──────────────────────────────────────
    st.markdown("<p class='section-label'>Valeurs à tester par paramètre</p>",
                unsafe_allow_html=True)
    oc1, oc2 = st.columns(2)
    with oc1:
        st.markdown("**Signal**")
        opt_vr_q   = st.multiselect("VR q",        [2,4,6,8,10,12,16],
                                     default=[4,6,8,10,12])
        opt_vr_thr = st.multiselect("VR threshold", [0.80,0.85,0.88,0.90,0.93,0.95,0.99],
                                     default=[0.85,0.90,0.95])
        opt_lb     = st.multiselect("Lookback",     [10,15,20,25,30,40,50,60],
                                     default=[15,20,30,40])
        opt_bk     = st.multiselect("Band k",       [1.0,1.25,1.5,1.75,2.0,2.25,2.5,2.75,3.0,3.5],
                                     default=[1.5,1.75,2.0,2.25,2.5,3.0])
    with oc2:
        st.markdown("**Risk Management**")
        opt_sl     = st.multiselect("SL mult",      [0.5,0.75,1.0,1.25,1.5,1.75,2.0],
                                     default=[0.75,1.0,1.25,1.5])
        opt_tp     = st.multiselect("TP ratio",     [0.4,0.5,0.6,0.7,0.8,0.9,1.0],
                                     default=[0.5,0.6,0.7,0.8,0.9])
        opt_rp     = st.multiselect("Risk % DD",    [0.05,0.10,0.15,0.20,0.25,0.30],
                                     default=[0.10,0.15,0.20])
        opt_mtd    = st.multiselect("Max trades/j", [1,2,3],
                                     default=[1,2])

    n_combos = (len(opt_vr_q)*len(opt_vr_thr)*len(opt_lb)*len(opt_bk)*
                len(opt_sl)*len(opt_tp)*len(opt_rp)*len(opt_mtd))
    t_est    = n_combos * 0.12 / 60
    col_info, col_start = st.columns([3,1])
    col_info.info(
        f"**{n_combos:,} combinaisons** — temps estimé : ~{t_est:.0f} min  \n"
        f"Hurst fixé à **{hurst_thr}** (sidebar) pour toutes les combos.")

    if not run_optim:
        st.info("Ajuste les valeurs ci-dessus puis clique **Optimisation complète** dans la sidebar.")
    elif n_combos == 0:
        st.error("Sélectionne au moins une valeur par paramètre.")
    else:
        import itertools

        prog_o = st.progress(0, text="Initialisation…")
        status_o = st.empty()
        all_opt  = []
        done_o   = 0

        for vq, vt, lb, bk, sl, tp, rp, mtd in itertools.product(
                opt_vr_q, opt_vr_thr, opt_lb, opt_bk,
                opt_sl, opt_tp, opt_rp, opt_mtd):
            r = run_vr_backtest(
                day_cache, hurst_thr, int(vq), float(vt), int(lb), float(bk),
                float(sl), float(tp), slip, int(mtd),
                int(skip_open), int(skip_close), float(rp))
            done_o += 1
            if r:
                sc = composite_score(r)
                all_opt.append({
                    "vr_q":       vq,   "vr_thr":  round(vt,2),
                    "lookback":   lb,   "band_k":  bk,
                    "sl_mult":    sl,   "tp_ratio": tp,
                    "risk_pct":   rp,   "max_td":  mtd,
                    "score":      sc,
                    "PF":         r["profit_factor"],
                    "Sharpe":     r["sharpe"],
                    "WR %":       r["winrate"],
                    "Max DD %":   r["max_dd_pct"],
                    "Trades":     r["n_trades"],
                    "Pass %":     r["pass_rate"],
                    "P&L ($)":    r["total_pnl"],
                })
            if done_o % 20 == 0 or done_o == n_combos:
                prog_o.progress(done_o/n_combos,
                    text=f"{done_o}/{n_combos} — vr_q={vq} bk={bk} sl={sl} tp={tp}")

        prog_o.empty(); status_o.empty()

        if not all_opt:
            st.error("Aucun résultat — critères trop restrictifs.")
        else:
            df_opt = pd.DataFrame(all_opt).sort_values("score", ascending=False)

            # Sauvegarde pour Phase 2
            st.session_state["optim_top"] = df_opt.head(20).to_dict("records")
            st.session_state["optim_best"] = df_opt.iloc[0].to_dict()

            best_o = df_opt.iloc[0]
            badge_o, _ = edge_badge({
                "profit_factor": best_o["PF"], "sharpe": best_o["Sharpe"],
                "winrate": best_o["WR %"], "max_dd_pct": best_o["Max DD %"],
                "n_trades": best_o["Trades"]})
            st.markdown(f"<div class='badge'>{badge_o}</div>", unsafe_allow_html=True)
            st.success(
                f"**Meilleur combo (score {best_o['score']:.4f}) :**  \n"
                f"vr_q=**{int(best_o['vr_q'])}** · vr_thr=**{best_o['vr_thr']}** · "
                f"lookback=**{int(best_o['lookback'])}** · band_k=**{best_o['band_k']}**  \n"
                f"sl=**{best_o['sl_mult']}** · tp=**{best_o['tp_ratio']}** · "
                f"risk=**{best_o['risk_pct']*100:.0f}%** · max_td=**{int(best_o['max_td'])}**  \n"
                f"→ PF **{best_o['PF']:.3f}** · Sharpe **{best_o['Sharpe']:.3f}** · "
                f"WR **{best_o['WR %']:.1f}%** · DD **{best_o['Max DD %']:.2f}%** · "
                f"Trades **{int(best_o['Trades'])}**"
            )

            # Scatter PF vs Sharpe coloré par score
            st.markdown("<p class='section-label'>Nuage PF × Sharpe — toutes les combos valides</p>",
                        unsafe_allow_html=True)
            fig_sc = go.Figure(go.Scatter(
                x=df_opt["PF"], y=df_opt["Sharpe"],
                mode="markers",
                marker=dict(
                    color=df_opt["score"], colorscale="RdYlGn",
                    size=5, opacity=0.7, showscale=True,
                    colorbar=dict(title="Score"),
                    cmin=df_opt["score"].quantile(0.05),
                    cmax=df_opt["score"].quantile(0.95),
                ),
                text=[f"bk={r['band_k']} vr_q={r['vr_q']} lb={r['lookback']}<br>"
                      f"sl={r['sl_mult']} tp={r['tp_ratio']} risk={r['risk_pct']}"
                      for _, r in df_opt.iterrows()],
                hovertemplate="PF=%{x:.3f} Sharpe=%{y:.3f}<br>%{text}<extra></extra>",
            ))
            fig_sc.add_vline(x=1.9, line_color=GREEN, line_dash="dash", opacity=0.5,
                             annotation_text="PF 1.9")
            fig_sc.add_hline(y=1.9, line_color=GREEN, line_dash="dash", opacity=0.5,
                             annotation_text="Sharpe 1.9")
            fig_sc.update_layout(title=f"{len(df_opt)} combos valides sur {n_combos} testées",
                                  xaxis_title="Profit Factor", yaxis_title="Sharpe",
                                  height=420, **DARK)
            st.plotly_chart(fig_sc, use_container_width=True)

            # Heatmap PF moyen par (band_k × vr_q)
            st.markdown("<p class='section-label'>Heatmap PF moyen — band_k × vr_q</p>",
                        unsafe_allow_html=True)
            pivot = (df_opt.groupby(["band_k","vr_q"])["PF"]
                           .mean().reset_index()
                           .pivot(index="band_k", columns="vr_q", values="PF"))
            fig_pv = go.Figure(go.Heatmap(
                z=pivot.values, x=[str(c) for c in pivot.columns],
                y=[str(i) for i in pivot.index],
                colorscale="RdYlGn", texttemplate="%.2f",
                text=np.round(pivot.values,2),
                hovertemplate="band_k=%{y} vr_q=%{x}<br>PF moy=%{z:.3f}<extra></extra>",
                colorbar=dict(title="PF moy"),
            ))
            fig_pv.update_layout(xaxis_title="vr_q", yaxis_title="band_k",
                                  height=350, **DARK)
            st.plotly_chart(fig_pv, use_container_width=True)

            # Heatmap Sharpe moyen par (sl_mult × tp_ratio)
            st.markdown("<p class='section-label'>Heatmap Sharpe moyen — SL × TP</p>",
                        unsafe_allow_html=True)
            pivot2 = (df_opt.groupby(["sl_mult","tp_ratio"])["Sharpe"]
                            .mean().reset_index()
                            .pivot(index="sl_mult", columns="tp_ratio", values="Sharpe"))
            fig_pv2 = go.Figure(go.Heatmap(
                z=pivot2.values, x=[str(c) for c in pivot2.columns],
                y=[str(i) for i in pivot2.index],
                colorscale="RdYlGn", texttemplate="%.2f",
                text=np.round(pivot2.values,2),
                colorbar=dict(title="Sharpe moy"),
            ))
            fig_pv2.update_layout(xaxis_title="tp_ratio", yaxis_title="sl_mult",
                                   height=320, **DARK)
            st.plotly_chart(fig_pv2, use_container_width=True)

            # Top 30 table
            st.markdown("<p class='section-label'>Top 30 combinaisons</p>",
                        unsafe_allow_html=True)
            top30_cols = ["score","vr_q","vr_thr","lookback","band_k",
                          "sl_mult","tp_ratio","risk_pct","max_td",
                          "PF","Sharpe","WR %","Max DD %","Trades","Pass %","P&L ($)"]
            st.dataframe(df_opt[top30_cols].head(30), use_container_width=True, hide_index=True)

            # Export CSV
            csv_data = df_opt.to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇ Exporter tous les résultats CSV",
                data=csv_data, file_name="vr_mr_optim.csv", mime="text/csv",
                use_container_width=True)

            st.info("Lance maintenant **Phase 2 — Hurst Combo** pour ajouter le filtre Hurst sur ce meilleur paramétrage.")


# ═══════════════════════════════════════════════════════════════════════════
# TAB 6 — PHASE 2 : VALEUR AJOUTÉE DU FILTRE HURST
# ═══════════════════════════════════════════════════════════════════════════

with tab_phase2:
    st.markdown("<p class='section-label'>Phase 2 — Valeur ajoutée du filtre Hurst sur le meilleur paramétrage</p>",
                unsafe_allow_html=True)
    st.markdown("""
<div class='metric-box'>
<b>Objectif :</b> prendre le meilleur paramétrage trouvé en Phase 1 (ou sidebar)<br/>
et tester l'impact du filtre Hurst à différents niveaux de sévérité.<br/>
<br/>
Sans Hurst → baseline. Avec Hurst de 0.52 à 0.40 → filtre de plus en plus strict.<br/>
Résultat : trouver le seuil Hurst optimal qui maximise PF/Sharpe sans trop réduire les trades.
</div>""", unsafe_allow_html=True)

    # Source des params : optimisation ou sidebar
    has_optim = "optim_best" in st.session_state
    p2_source = st.radio(
        "Paramètres à utiliser",
        ["Meilleur de l'optimisation (Phase 1)" if has_optim else "Optimisation non lancée → sidebar",
         "Paramètres sidebar (manuel)"],
        horizontal=True)

    if "optim_best" in st.session_state and "Phase 1" in p2_source:
        bp = st.session_state["optim_best"]
        p2_vr_q    = int(bp["vr_q"])
        p2_vr_thr  = float(bp["vr_thr"])
        p2_lb      = int(bp["lookback"])
        p2_bk      = float(bp["band_k"])
        p2_sl      = float(bp["sl_mult"])
        p2_tp      = float(bp["tp_ratio"])
        p2_rp      = float(bp["risk_pct"])
        p2_mtd     = int(bp["max_td"])
        st.success(
            f"Params Phase 1 : vr_q={p2_vr_q} · vr_thr={p2_vr_thr} · "
            f"lb={p2_lb} · bk={p2_bk} · sl={p2_sl} · tp={p2_tp} · "
            f"risk={p2_rp*100:.0f}% · max_td={p2_mtd}")
    else:
        p2_vr_q   = vr_q; p2_vr_thr = vr_thr; p2_lb = lookback
        p2_bk     = band_k; p2_sl = sl_mult; p2_tp = tp_ratio
        p2_rp     = risk_pct; p2_mtd = max_td
        st.info(f"Utilisation des paramètres sidebar.")

    # Niveaux Hurst à tester
    hurst_levels = [None, 0.52, 0.50, 0.48, 0.47, 0.46, 0.45, 0.44, 0.43, 0.42, 0.40]
    hurst_labels = ["Sans Hurst" if h is None else f"H < {h}" for h in hurst_levels]

    if not run_phase2:
        st.info("Clique **Phase 2 — Hurst Combo** dans la sidebar pour lancer l'analyse.")
    else:
        prog_p2  = st.progress(0, text="Phase 2 en cours…")
        p2_rows  = []

        for idx, (h_val, h_lbl) in enumerate(zip(hurst_levels, hurst_labels)):
            # Pour "Sans Hurst" on force threshold = 1.0 (passe tout)
            h_use = h_val if h_val is not None else 1.0
            r = run_vr_backtest(
                day_cache, h_use, p2_vr_q, p2_vr_thr, p2_lb, p2_bk,
                p2_sl, p2_tp, slip, p2_mtd,
                int(skip_open), int(skip_close), p2_rp)
            prog_p2.progress((idx+1)/len(hurst_levels), text=f"{h_lbl}…")

            if r:
                badge, _ = edge_badge(r)
                sc = composite_score(r)
                p2_rows.append({
                    "Hurst gate":  h_lbl,
                    "Score":       sc,
                    "PF":          r["profit_factor"],
                    "Sharpe":      r["sharpe"],
                    "WR %":        r["winrate"],
                    "Max DD %":    r["max_dd_pct"],
                    "Trades":      r["n_trades"],
                    "Pass %":      r["pass_rate"],
                    "P&L ($)":     r["total_pnl"],
                    "Edge":        badge,
                    "_h":          h_val if h_val is not None else 1.0,
                })
            else:
                p2_rows.append({
                    "Hurst gate": h_lbl, "Score": None,
                    "PF": None, "Sharpe": None, "WR %": None,
                    "Max DD %": None, "Trades": 0, "Pass %": None,
                    "P&L ($)": None, "Edge": "❌ Trop peu de trades",
                    "_h": h_val if h_val is not None else 1.0,
                })

        prog_p2.empty()
        df_p2 = pd.DataFrame(p2_rows)
        df_valid = df_p2.dropna(subset=["PF"])

        # Tableau comparatif
        st.markdown("<p class='section-label'>Impact du seuil Hurst — comparatif</p>",
                    unsafe_allow_html=True)
        display_cols = ["Hurst gate","Score","PF","Sharpe","WR %","Max DD %","Trades","Pass %","P&L ($)","Edge"]
        st.dataframe(df_p2[display_cols], use_container_width=True, hide_index=True)

        if len(df_valid) >= 2:
            # Chart évolution PF / Sharpe / Trades vs Hurst threshold
            st.markdown("<p class='section-label'>Évolution des métriques selon le seuil Hurst</p>",
                        unsafe_allow_html=True)
            fig_p2 = make_subplots(rows=2, cols=2,
                subplot_titles=["Profit Factor", "Sharpe Ratio",
                                 "Nombre de trades", "Max Drawdown %"],
                vertical_spacing=0.14, horizontal_spacing=0.10)

            x_vals = df_valid["Hurst gate"].tolist()
            fig_p2.add_trace(go.Scatter(x=x_vals, y=df_valid["PF"], mode="lines+markers",
                line=dict(color=GREEN,  width=2), marker=dict(size=7), name="PF"), row=1, col=1)
            fig_p2.add_trace(go.Scatter(x=x_vals, y=df_valid["Sharpe"], mode="lines+markers",
                line=dict(color=CYAN,   width=2), marker=dict(size=7), name="Sharpe"), row=1, col=2)
            fig_p2.add_trace(go.Bar(x=x_vals, y=df_valid["Trades"],
                marker_color=BLUE, opacity=0.8, name="Trades"), row=2, col=1)
            fig_p2.add_trace(go.Scatter(x=x_vals, y=df_valid["Max DD %"], mode="lines+markers",
                line=dict(color=RED,    width=2), marker=dict(size=7), name="DD%"), row=2, col=2)

            # Lignes cibles
            fig_p2.add_hline(y=1.9, line_color=GREEN, line_dash="dash", opacity=0.4, row=1, col=1)
            fig_p2.add_hline(y=1.9, line_color=GREEN, line_dash="dash", opacity=0.4, row=1, col=2)
            fig_p2.add_hline(y=5.0, line_color=RED,   line_dash="dash", opacity=0.4, row=2, col=2)

            fig_p2.update_layout(height=520, showlegend=False, **DARK)
            st.plotly_chart(fig_p2, use_container_width=True)

            # Meilleur seuil Hurst selon le score
            best_p2 = df_valid.loc[df_valid["Score"].idxmax()]
            baseline = df_p2[df_p2["Hurst gate"] == "Sans Hurst"].iloc[0]

            st.markdown("<p class='section-label'>Verdict Phase 2</p>",
                        unsafe_allow_html=True)

            gain_pf = (best_p2["PF"] - baseline["PF"]) if baseline["PF"] else 0
            gain_sh = (best_p2["Sharpe"] - baseline["Sharpe"]) if baseline["Sharpe"] else 0
            trade_loss = best_p2["Trades"] - baseline["Trades"] if baseline["Trades"] else 0

            if best_p2["Hurst gate"] == "Sans Hurst":
                st.warning(
                    "Le filtre Hurst ne semble pas améliorer ce paramétrage.  \n"
                    "Le signal VR seul est déjà suffisamment sélectif sur ces données.")
            else:
                badge_p2, _ = edge_badge({
                    "profit_factor": best_p2["PF"], "sharpe": best_p2["Sharpe"],
                    "winrate": best_p2["WR %"], "max_dd_pct": best_p2["Max DD %"],
                    "n_trades": best_p2["Trades"]})
                st.markdown(f"<div class='badge'>{badge_p2}</div>", unsafe_allow_html=True)
                st.success(
                    f"**Seuil Hurst optimal : {best_p2['Hurst gate']}** (score {best_p2['Score']:.4f})  \n"
                    f"PF : {baseline['PF']:.3f} → **{best_p2['PF']:.3f}** "
                    f"({'+'if gain_pf>=0 else ''}{gain_pf:.3f})  \n"
                    f"Sharpe : {baseline['Sharpe']:.3f} → **{best_p2['Sharpe']:.3f}** "
                    f"({'+'if gain_sh>=0 else ''}{gain_sh:.3f})  \n"
                    f"Trades : {int(baseline['Trades'])} → **{int(best_p2['Trades'])}** "
                    f"({trade_loss:+d}) — le filtre Hurst élimine les sessions douteuses")

                if gain_pf > 0.05 or gain_sh > 0.1:
                    st.info(
                        "**Conclusion :** le filtre Hurst apporte une valeur ajoutée significative.  \n"
                        f"Combine **{best_p2['Hurst gate']}** + VR + ces params → configuration finale recommandée.")
                else:
                    st.info(
                        "**Conclusion :** le filtre Hurst améliore légèrement l'edge.  \n"
                        "Si PF toujours < 1.9, élargis band_k ou réduis le lookback pour concentrer les entrées.")

            # Sauvegarde config finale
            if best_p2["Hurst gate"] != "Sans Hurst":
                final_config = {
                    "hurst_threshold": best_p2["_h"],
                    "vr_q":      p2_vr_q, "vr_thr":  p2_vr_thr,
                    "lookback":  p2_lb,   "band_k":  p2_bk,
                    "sl_mult":   p2_sl,   "tp_ratio": p2_tp,
                    "risk_pct":  p2_rp,
                }
                st.session_state["final_config"] = final_config
                st.markdown("<p class='section-label'>Configuration finale recommandée</p>",
                            unsafe_allow_html=True)
                st.code(str(final_config), language="python")


st.caption(
    f"VR_MR Deep Analysis · MNQ {years_back}Y · "
    f"Lo & MacKinlay (1988) Review of Financial Studies · "
    f"Source données : Databento GLBX"
)
