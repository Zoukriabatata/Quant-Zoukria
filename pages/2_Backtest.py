"""
Étude Hurst_MR — Analyse complète Lec 25 (fBm) + Lec 51 (HMM)
Instrument : MNQ M1 Databento CSV
"""

import os
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from config import MNQ_CSV

st.set_page_config(page_title="Backtest Hurst_MR", page_icon="📊", layout="wide")
from styles import inject as _inj; _inj()

# ═══════════════════════════════════════════════════════════════════════
# THEME
# ═══════════════════════════════════════════════════════════════════════
DARK = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="#0d1117",
    font=dict(color="#94a3b8", size=11,
              family="'JetBrains Mono','Space Grotesk',monospace"),
    margin=dict(t=48, b=40, l=52, r=24),
    legend=dict(bgcolor="rgba(13,17,23,0.85)",
                bordercolor="rgba(148,163,184,0.10)", borderwidth=1,
                font=dict(size=11, color="#94a3b8"), itemsizing="constant"),
    hoverlabel=dict(bgcolor="#161f2e", bordercolor="rgba(59,130,246,0.4)",
                    font=dict(size=12, family="JetBrains Mono", color="#f1f5f9")),
)
TEAL, GREEN, RED, YELLOW, CYAN, ORANGE, MAGENTA = (
    "#06b6d4", "#10b981", "#ef4444", "#f59e0b", "#06b6d4", "#f97316", "#8b5cf6"
)
BLUE = "#3b82f6"

def _css(raw):
    import re
    css = re.sub(r'/\*.*?\*/', '', raw, flags=re.DOTALL)
    st.markdown(f"<style>{' '.join(css.split())}</style>", unsafe_allow_html=True)

_css("""
.block-container{padding-top:1.2rem;max-width:1300px}
.stat-num{font-size:1.5rem;}
.info-box{
  background:var(--bg-surface);border:1px solid var(--border-default);
  border-radius:var(--r-md);padding:1rem 1.3rem;margin:.4rem 0;
  font-family:'JetBrains Mono',monospace;font-size:.82rem;line-height:2;
  box-shadow:var(--shadow-card);
}
""")

st.markdown("""
<div class="ph anim-fade-up">
  <div class="ph-tag">ÉTUDE · MNQ M1 CSV · LEC 25 + LEC 51</div>
  <div class="ph-title">Hurst_MR — Analyse Complète</div>
</div>""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.header("Données")
    csv_path = st.text_input("CSV MNQ M1", value=MNQ_CSV)
    st.markdown("---")
    st.header("Hurst_MR")
    hurst_threshold = st.slider("Seuil Hurst H <", 0.35, 0.60, 0.52, 0.01,
        help="H < seuil → session anti-persistante → MR valide")
    hurst_win = st.select_slider("Hurst window (returns)", [20, 30, 40, 50, 60, 80, 100], value=60,
        help="Fenêtre rolling R/S — paramètre le plus sensible du signal")
    lookback = st.select_slider("Lookback (barres)", [15, 20, 30, 45, 60, 90, 120], value=30)
    band_k   = st.slider("Bande k (σ)", 1.5, 4.0, 3.25, 0.25)
    st.markdown("---")
    st.header("Exécution")
    sl_mult      = st.slider("SL = k × σ", 0.5, 3.0, 0.75, 0.25)
    use_atr_sl   = st.toggle("SL adaptatif ATR(14)", value=False,
        help="ON : SL = sl_mult × max(std, ATR) — évite les whipsaws en période volatile")
    tp_overshoot = st.slider("TP overshoot (σ au-delà FV)", 0.0, 2.0, 0.0, 0.25,
        help="0 = fair value pure · 0.5 = FV + 0.5σ de l'autre côté · 1.5 = overshoot agressif")
    slip_pts  = st.number_input("Slippage (pts)", 0.0, 5.0, 0.5, 0.25)
    max_td    = st.number_input("Max trades/jour", 1, 10, 5, 1)
    daily_lim_ui = st.slider("Limite perte/jour ($)", 300, 1500, 600, 100,
        help="Stop trading le jour si cette perte est atteinte — clé pour contrôler le DD")
    st.markdown("---")
    st.header("Session NY")
    sh, sm = st.columns(2)
    with sh: s_h = st.number_input("Début h", 9, 15, 9)
    with sm: s_m = st.number_input("Début m", 0, 59, 30)
    eh, em = st.columns(2)
    with eh: e_h = st.number_input("Fin h", 12, 21, 16)
    with em: e_m = st.number_input("Fin m", 0, 59, 0)
    skip_o      = st.number_input("Skip open (barres)", 0, 30, 5)
    skip_c      = st.number_input("Skip close (barres)", 0, 30, 3)
    timeout_ui  = st.select_slider("Timeout trade (barres M1)", [15, 30, 60, 120, 240], value=120,
        help="Liquidation mark-to-market si ni TP ni SL touché · 120 = config validée")
    st.markdown("---")
    st.header("Challenge")
    capital_ui       = st.number_input("Capital ($)", 25_000, 200_000, 50_000, 5_000)
    max_dd_ui        = st.number_input("DD max autorisé ($)", 500, 10_000, 2_500, 250,
        help="4PropTrader = 2500 · Apex 50K = 2000 · TopStep = 3000")
    profit_target_ui = st.number_input("Profit target ($)", 500, 20_000, 3_000, 250,
        help="Montant à atteindre pour passer le challenge")
    st.markdown("---")
    st.header("Monte Carlo")
    mc_sims  = st.select_slider("Simulations", [500, 1000, 2000, 5000], value=1000)
    mc_days  = st.number_input("Jours / simulation", 20, 30, 22)
    mc_risk  = st.slider("Risk % DD / trade", 5, 30, 10, 1)
    st.markdown("---")
    run_btn = st.button("▶  Lancer l'étude", type="primary", use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════
# MATH
# ═══════════════════════════════════════════════════════════════════════

def hurst_rs(ts):
    ts = np.asarray(ts, dtype=float)
    n  = len(ts)
    if n < 20: return 0.5
    # 12 lags log-espacés entre 4 et n//2 (max 50) — même régression, mieux conditionnée
    lags = np.unique(np.round(
        np.exp(np.linspace(np.log(4), np.log(min(n // 2, 50)), 12))
    ).astype(int))
    lags = lags[lags >= 4]
    rs_vals = []
    for lag in lags:
        lag = int(lag)
        n_chunks = n // lag
        if n_chunks < 2: continue
        mat  = ts[:n_chunks * lag].reshape(n_chunks, lag)  # (chunks, lag) — vectorisé
        mean = mat.mean(axis=1, keepdims=True)
        devs = np.cumsum(mat - mean, axis=1)
        R    = devs.max(axis=1) - devs.min(axis=1)
        S    = mat.std(axis=1, ddof=0)
        mask = S > 0
        if mask.sum() == 0: continue
        rs_vals.append(float((R[mask] / S[mask]).mean()))
    if len(rs_vals) < 3: return 0.5
    try:
        return float(np.clip(
            np.polyfit(np.log(lags[:len(rs_vals)]), np.log(rs_vals), 1)[0],
            0.0, 1.0
        ))
    except Exception:
        return 0.5



def garch_rolling(rets, omega=1e-6, alpha=0.1, beta=0.85):
    n  = len(rets)
    vs = np.full(n, np.var(rets) if np.var(rets) > 0 else 1e-6)
    for i in range(1, n):
        vs[i] = omega + alpha * rets[i-1]**2 + beta * vs[i-1]
    return vs

# ═══════════════════════════════════════════════════════════════════════
# DATA LOADING
# ═══════════════════════════════════════════════════════════════════════

@st.cache_data(show_spinner=False)
def load_csv(path):
    try:
        df = pd.read_csv(path, usecols=["ts_event","open","high","low","close","volume","symbol"])
    except Exception as e:
        return None, str(e)
    df = df[df["symbol"].str.startswith("MNQ") & ~df["symbol"].str.contains("-", na=False)].copy()
    if df.empty: return None, "Aucun symbole MNQ"
    df = df.sort_values("volume", ascending=False).groupby("ts_event", sort=False).first().reset_index()
    df["bar"] = pd.to_datetime(df["ts_event"], utc=True)
    df[["open","high","low","close"]] = df[["open","high","low","close"]].astype(float)
    df["volume"] = df["volume"].fillna(0).astype(int)
    df.sort_values("bar", inplace=True)
    df.drop_duplicates(subset=["bar"], inplace=True)
    df.reset_index(drop=True, inplace=True)
    df["date"] = df["bar"].dt.date
    # Utilise toutes les données disponibles — pas de trim
    # Rollover
    day_sym = df.groupby("date").apply(
        lambda g: g.loc[g["volume"].idxmax(), "symbol"] if len(g) > 0 else None,
        include_groups=False,
    ).reset_index(); day_sym.columns = ["date","dominant"]
    day_sym["prev"] = day_sym["dominant"].shift(1)
    day_sym["roll"] = (day_sym["dominant"] != day_sym["prev"]) & day_sym["prev"].notna()
    day_sym["roll"] = (day_sym["roll"] | day_sym["roll"].shift(-1)).fillna(False).astype(bool)
    roll_dates = set(day_sym.loc[day_sym["roll"], "date"].astype(str))
    df["is_roll"] = df["date"].astype(str).isin(roll_dates)
    return df, None


def filter_session(df, sh, sm, eh, em):
    t = df["bar"].dt.hour * 60 + df["bar"].dt.minute
    return df[(t >= sh*60+sm) & (t < eh*60+em)].reset_index(drop=True)


@st.cache_data(show_spinner=False)
def build_study_cache(csv_path, sh, sm, eh, em, hwin=60):
    df, err = load_csv(csv_path)
    if err: return None, err
    days = {}
    for day in sorted(df["date"].unique()):
        day_df = df[df["date"] == day]
        if day_df["is_roll"].any(): continue
        bars = filter_session(day_df, sh, sm, eh, em)
        if len(bars) < 50: continue
        closes = bars["close"].values.astype(float)
        highs  = bars["high"].values.astype(float)
        lows   = bars["low"].values.astype(float)
        rets   = np.diff(np.log(np.maximum(closes, 1e-9)))
        rets   = np.concatenate([[0], rets])
        n      = len(closes)
        h_full    = hurst_rs(closes)   # session complète — affichage Tab 2 uniquement
        hurst_arr = np.full(n, np.nan)
        for _i in range(hwin, n):
            hurst_arr[_i] = hurst_rs(rets[_i - hwin: _i])  # returns, pas prix
        # ATR(14) vectorisé
        tr = np.maximum(
            highs[1:] - lows[1:],
            np.maximum(np.abs(highs[1:] - closes[:-1]),
                       np.abs(lows[1:]  - closes[:-1]))
        )
        tr = np.concatenate([[highs[0] - lows[0]], tr])
        atr_arr = pd.Series(tr).rolling(14).mean().values
        days[str(day)] = dict(
            bars=bars, closes=closes, highs=highs, lows=lows,
            rets=rets, hurst=h_full, hurst_arr=hurst_arr, atr_arr=atr_arr,
        )
    return days, None


# ═══════════════════════════════════════════════════════════════════════
# BACKTEST
# ═══════════════════════════════════════════════════════════════════════

def run_hurst_backtest(day_cache, ht, lb, bk, sl_m, tp_overshoot, slip,
                       max_td, skip_o, skip_c, timeout_bars=120,
                       capital=50_000, max_dd=2_000, daily_lim=1_000,
                       profit_target=3_000, risk_pct=0.10, atr_sl=False):
    trades = []
    monthly = []
    running = capital; peak = capital
    cur_month = None; m_trades = []; busted = passed = False; days_el = 0

    for day_key in sorted(day_cache):
        dm = day_key[:7]
        if dm != cur_month:
            if cur_month:
                nw = sum(1 for t in m_trades if t["win"])
                nt = len(m_trades)
                monthly.append(dict(mois=cur_month, pnl=running-capital,
                                    trades=nt, wr=nw/nt*100 if nt else 0,
                                    passed=passed, busted=busted))
                running = capital; peak = capital
                busted = passed = False; m_trades = []; days_el = 0
            cur_month = dm

        if passed or busted: continue
        dd_used = max(0., peak - running)
        if dd_used >= max_dd: busted = True; continue
        if (running - capital) >= profit_target: passed = True
        days_el += 1

        cached    = day_cache[day_key]
        closes    = cached["closes"]
        hurst_arr = cached["hurst_arr"]   # rolling H sans look-ahead
        atr_arr   = cached.get("atr_arr")
        bars      = cached["bars"]
        n         = len(closes)

        last_exit  = -1; daily_pnl = 0.; day_td = 0

        for i in range(lb + skip_o, n - skip_c):
            if day_td >= max_td or daily_pnl <= -daily_lim: break
            if i <= last_exit: continue
            # Filtre Hurst sans look-ahead : H calculé sur les 60 barres passées
            h_bar = hurst_arr[i] if i < len(hurst_arr) else np.nan
            if np.isnan(h_bar) or h_bar >= ht: continue

            w   = closes[i - lb: i]
            mid = w.mean(); std = w.std()
            if std == 0: continue
            price = closes[i]; z = (price - mid) / std
            if abs(z) < bk: continue

            direction = "short" if z > 0 else "long"
            if atr_sl and atr_arr is not None and i < len(atr_arr) and not np.isnan(atr_arr[i]):
                vol_base = max(std, atr_arr[i])   # ATR protège contre les whipsaws intraday
            else:
                vol_base = std
            sl_pts = max(3.0, sl_m * vol_base)
            sl_pts = min(sl_pts, 20.0)
            # TP = fair value + overshoot de l'autre côté
            # Long (price < mid) : TP au-dessus de mid
            # Short (price > mid): TP en-dessous de mid
            if direction == "long":
                tp_price = mid + tp_overshoot * std
            else:
                tp_price = mid - tp_overshoot * std

            dd_rem = max(0., max_dd - dd_used)
            risk   = max(50., min(risk_pct * dd_rem, daily_lim * 0.40))
            lpc    = sl_pts * 2.0
            if lpc <= 0: continue
            contracts = min(60, int(risk / lpc))
            # Plafonne au budget journalier restant — ne force jamais 1 contrat si budget épuisé
            budget_rem = max(0., daily_lim + daily_pnl)
            contracts  = min(contracts, int(budget_rem / lpc))
            if contracts <= 0: continue

            # Simulate trade
            result_pts = 0.0; exit_bar = i; hit = False
            for j in range(i+1, min(n, i+timeout_bars)):
                c = closes[j]
                if direction == "long":
                    if c <= price - sl_pts: result_pts = -sl_pts - slip; exit_bar = j; hit = True; break
                    if c >= tp_price:       result_pts = (tp_price - price) - slip; exit_bar = j; hit = True; break
                else:
                    if c >= price + sl_pts: result_pts = -sl_pts - slip; exit_bar = j; hit = True; break
                    if c <= tp_price:       result_pts = (price - tp_price) - slip; exit_bar = j; hit = True; break
            if not hit:
                # Timeout : mark-to-market au close de la barre de sortie
                exit_bar = min(n - 1, i + timeout_bars)
                c_exit = closes[exit_bar]
                if direction == "long":
                    result_pts = (c_exit - price) - slip
                else:
                    result_pts = (price - c_exit) - slip

            pnl = result_pts * 2.0 * contracts
            running += pnl; daily_pnl += pnl; day_td += 1
            if running > peak: peak = running
            last_exit = exit_bar
            win = pnl > 0

            hour = bars["bar"].iloc[i].hour
            dow  = bars["bar"].iloc[i].dayofweek
            trades.append(dict(
                date=str(day_key), win=win, pnl=pnl,
                pts=result_pts, contracts=contracts,
                z=z, std=std, price=price, mid=mid,
                direction=direction, hurst=float(h_bar),
                hour=hour, dow=dow,
            ))
            m_trades.append(dict(win=win, pnl=pnl))

    return pd.DataFrame(trades), pd.DataFrame(monthly)


# ═══════════════════════════════════════════════════════════════════════
# RUN
# ═══════════════════════════════════════════════════════════════════════

if run_btn:
    st.session_state["study_ready"] = True
if not st.session_state.get("study_ready", False):
    st.info("Configure les paramètres dans la sidebar puis clique **▶ Lancer l'étude**.")
    st.stop()

if not os.path.exists(csv_path):
    st.error(f"CSV introuvable : `{csv_path}`"); st.stop()

with st.spinner("Chargement et calcul Hurst par session…"):
    day_cache, err = build_study_cache(csv_path, s_h, s_m, e_h, e_m, hwin=hurst_win)

if err: st.error(err); st.stop()
if not day_cache: st.error("Aucune session valide."); st.stop()

with st.spinner("Backtest en cours…"):
    trades_df, monthly_df = run_hurst_backtest(
        day_cache, hurst_threshold, lookback, band_k,
        sl_mult, tp_overshoot, slip_pts, max_td, skip_o, skip_c,
        timeout_bars=timeout_ui,
        capital=capital_ui, max_dd=max_dd_ui, daily_lim=daily_lim_ui,
        profit_target=profit_target_ui, risk_pct=mc_risk/100,
        atr_sl=use_atr_sl,
    )

if len(trades_df) < 10:
    st.warning("Moins de 10 trades — paramètres trop restrictifs."); st.stop()

# ── Métriques globales ────────────────────────────────────────────────
n     = len(trades_df)
wr    = float(trades_df["win"].mean())
pos   = trades_df[trades_df["pnl"] > 0]["pnl"].sum()
neg   = abs(trades_df[trades_df["pnl"] < 0]["pnl"].sum())
pf    = pos / max(neg, 0.01)
total = trades_df["pnl"].sum()
eq    = np.concatenate([[capital_ui], np.cumsum(trades_df["pnl"].values) + capital_ui])
peak  = np.maximum.accumulate(eq)
dd_   = (peak - eq) / np.maximum(peak, capital_ui) * 100
max_dd_pct = float(dd_.max())
_daily = trades_df.groupby("date")["pnl"].sum()
sharpe = float(_daily.mean() / _daily.std() * np.sqrt(252)) if _daily.std() > 0 else 0

# Hurst study data
h_vals     = np.array([day_cache[d]["hurst"] for d in sorted(day_cache)])  # prix bruts — Tab 2 uniquement
total_days = len(h_vals)
mr_days    = int((h_vals < hurst_threshold).sum())   # pour Tab 2 (affichage sessions)
mr_pct     = mr_days / total_days * 100
# % de barres qui passent le filtre rolling H (returns) — cohérent avec le backtest
_bar_h_vals = np.concatenate([
    day_cache[d]["hurst_arr"][~np.isnan(day_cache[d]["hurst_arr"])]
    for d in sorted(day_cache)
])
mr_bars_pct = float((_bar_h_vals < hurst_threshold).mean() * 100) if len(_bar_h_vals) > 0 else 0.0

# ─── TABS ────────────────────────────────────────────────────────────
t1,t2,t3,t4,t5,t6,t7 = st.tabs([
    "📊 Résultats","🔬 Analyse Hurst","⏱ Signal & Timing",
    "🎲 Monte Carlo","🧪 Preuve d'Edge","🔧 Grid Search","🔄 Walk-Forward"
])

# ═══════════════════════════════════════════════════════════════════════
# TAB 1 — RÉSULTATS
# ═══════════════════════════════════════════════════════════════════════
with t1:
    def kpi(val, lbl, color="#fff"):
        return f'<div class="stat-cell"><div class="stat-num" style="color:{color}">{val}</div><div class="stat-lbl">{lbl}</div></div>'

    pf_col  = GREEN if pf >= 1.5 else YELLOW if pf >= 1.2 else RED
    wr_col  = GREEN if wr >= 0.5 else YELLOW if wr >= 0.45 else RED
    dd_col  = GREEN if max_dd_pct < 3 else YELLOW if max_dd_pct < 5 else RED
    pnl_col = GREEN if total > 0 else RED

    st.markdown(f"""<div class="stat-row">
        {kpi(f"{pf:.2f}", "Profit Factor", pf_col)}
        {kpi(f"{wr*100:.1f}%", "Win Rate", wr_col)}
        {kpi(f"{sharpe:.2f}", "Sharpe", GREEN if sharpe > 2 else YELLOW)}
        {kpi(f"{max_dd_pct:.1f}%", "Max DD", dd_col)}
        {kpi(n, "Trades", CYAN)}
        {kpi(f"${total:+,.0f}", "P&L Total", pnl_col)}
        {kpi(f"{mr_bars_pct:.0f}%", "Barres H<seuil", TEAL)}
    </div>""", unsafe_allow_html=True)

    c1, c2 = st.columns([2, 1])

    with c1:
        st.markdown('<div class="section-lbl">Equity Curve</div>', unsafe_allow_html=True)
        fig_eq = go.Figure()
        fig_eq.add_trace(go.Scatter(
            y=eq, mode="lines", name="Equity",
            line=dict(color=TEAL, width=2),
            fill="tozeroy", fillcolor="rgba(60,196,183,0.05)"
        ))
        fig_eq.add_hline(y=capital_ui + profit_target_ui,
                         line=dict(color=GREEN, dash="dash", width=1),
                         annotation_text=f"Target +${profit_target_ui:,.0f}", annotation_position="right")
        fig_eq.add_hline(y=capital_ui - max_dd_ui,
                         line=dict(color=RED, dash="dash", width=1),
                         annotation_text=f"Bust −${max_dd_ui:,.0f}", annotation_position="right")
        fig_eq.update_layout(**DARK, height=320, yaxis_tickformat="$,.0f",
                              title=f"Equity — ${capital_ui:,.0f} capital")
        st.plotly_chart(fig_eq, use_container_width=True)

    with c2:
        st.markdown('<div class="section-lbl">P&L Mensuel</div>', unsafe_allow_html=True)
        if len(monthly_df):
            fig_m = go.Figure(go.Bar(
                x=monthly_df["mois"],
                y=monthly_df["pnl"],
                marker_color=[GREEN if v > 0 else RED for v in monthly_df["pnl"]],
                text=[f"${v:+,.0f}" for v in monthly_df["pnl"]],
                textposition="outside", textfont=dict(size=9),
            ))
            fig_m.update_layout(**DARK, height=320, yaxis_tickformat="$,.0f",
                                 title="P&L / mois")
            st.plotly_chart(fig_m, use_container_width=True)

    # Diagnostique
    st.markdown('<div class="section-lbl">Diagnostique</div>', unsafe_allow_html=True)
    avg_win  = trades_df[trades_df["win"]]["pnl"].mean() if trades_df["win"].sum() > 0 else 0
    avg_loss = trades_df[~trades_df["win"]]["pnl"].mean() if (~trades_df["win"]).sum() > 0 else 0
    rratio   = abs(avg_win / avg_loss) if avg_loss else 0
    min_wr   = 1 / (1 + rratio) if rratio > 0 else 0.5

    diag = []
    if pf >= 1.5:   diag.append(("✅", "Profit Factor ≥ 1.5", GREEN))
    elif pf >= 1.2: diag.append(("⚠️", f"PF {pf:.2f} — acceptable mais vise 1.5+", YELLOW))
    else:           diag.append(("❌", f"PF {pf:.2f} — edge insuffisant", RED))
    if wr >= min_wr: diag.append(("✅", f"WR {wr*100:.1f}% ≥ seuil BEP {min_wr*100:.1f}%", GREEN))
    else:            diag.append(("❌", f"WR {wr*100:.1f}% < seuil BEP {min_wr*100:.1f}%", RED))
    if sharpe > 2:   diag.append(("✅", f"Sharpe {sharpe:.2f} — excellent", GREEN))
    elif sharpe > 1: diag.append(("⚠️", f"Sharpe {sharpe:.2f} — correct", YELLOW))
    else:            diag.append(("❌", f"Sharpe {sharpe:.2f} — trop faible", RED))
    if max_dd_pct < 3: diag.append(("✅", f"Max DD {max_dd_pct:.1f}% < 3% — Apex sécurisé", GREEN))
    elif max_dd_pct < 4.5: diag.append(("⚠️", f"Max DD {max_dd_pct:.1f}% — surveille", YELLOW))
    else:                  diag.append(("❌", f"Max DD {max_dd_pct:.1f}% — risque bust", RED))

    dc1, dc2 = st.columns(2)
    for i, (icon, msg, col) in enumerate(diag):
        target = dc1 if i % 2 == 0 else dc2
        target.markdown(f'<div class="info-box" style="border-color:{col}22">'
                        f'<span style="color:{col}">{icon} {msg}</span></div>',
                        unsafe_allow_html=True)

    # ── Export CSV ────────────────────────────────────────────────────
    st.markdown('<div class="section-lbl">Export</div>', unsafe_allow_html=True)
    ex1, ex2, ex3 = st.columns(3)

    with ex1:
        trades_csv = trades_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇ Trades CSV",
            data=trades_csv,
            file_name=f"hurst_mr_trades_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with ex2:
        monthly_csv = monthly_df.to_csv(index=False).encode("utf-8") if not monthly_df.empty else b""
        st.download_button(
            "⬇ Stats Mensuelles CSV",
            data=monthly_csv,
            file_name=f"hurst_mr_monthly_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with ex3:
        # Résumé paramètres + métriques — utile pour comparer des runs
        summary = {
            "date": pd.Timestamp.now().isoformat(),
            "hurst_threshold": hurst_threshold, "hurst_win": hurst_win,
            "lookback": lookback, "band_k": band_k, "sl_mult": sl_mult,
            "tp_overshoot": tp_overshoot, "slip_pts": slip_pts,
            "n_trades": n, "win_rate": round(wr, 4), "profit_factor": round(pf, 4),
            "sharpe": round(sharpe, 4), "max_dd_pct": round(max_dd_pct, 4),
            "total_pnl": round(total, 2),
        }
        import json as _json
        st.download_button(
            "⬇ Paramètres JSON",
            data=_json.dumps(summary, indent=2).encode("utf-8"),
            file_name=f"hurst_mr_params_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.json",
            mime="application/json",
            use_container_width=True,
        )

# ═══════════════════════════════════════════════════════════════════════
# TAB 2 — ANALYSE HURST
# ═══════════════════════════════════════════════════════════════════════
with t2:
    st.markdown('<div class="section-lbl">Distribution des H journaliers</div>', unsafe_allow_html=True)

    c1, c2 = st.columns([2, 1])
    with c1:
        fig_h = go.Figure()
        fig_h.add_trace(go.Histogram(
            x=h_vals, nbinsx=40,
            marker_color=[GREEN if v < hurst_threshold else RED for v in
                          np.linspace(h_vals.min(), h_vals.max(), 40)],
            name="H journalier",
        ))
        fig_h.add_vline(x=hurst_threshold, line=dict(color=YELLOW, dash="dash", width=2),
                        annotation_text=f"Seuil MR {hurst_threshold}", annotation_position="top right")
        fig_h.add_vline(x=0.5, line=dict(color="#444", dash="dot", width=1),
                        annotation_text="H=0.5 (Random Walk)")
        fig_h.update_layout(**DARK, height=320,
                            title=f"Distribution H — {mr_days}/{total_days} sessions MR ({mr_pct:.0f}%)",
                            xaxis_title="Hurst H", yaxis_title="Nb sessions")
        st.plotly_chart(fig_h, use_container_width=True)

    with c2:
        st.markdown('<div class="section-lbl">Stats H</div>', unsafe_allow_html=True)
        h_stats = {
            "H moyen":        f"{h_vals.mean():.3f}",
            "H médiane":      f"{np.median(h_vals):.3f}",
            "H min":          f"{h_vals.min():.3f}",
            "H max":          f"{h_vals.max():.3f}",
            "Sessions MR":    f"{mr_days} ({mr_pct:.0f}%)",
            "Sessions trend": f"{total_days-mr_days} ({100-mr_pct:.0f}%)",
        }
        rows = "".join([f'<div style="display:flex;justify-content:space-between;border-bottom:1px solid #111;padding:.3rem 0">'
                        f'<span style="color:#555">{k}</span><b style="color:{TEAL}">{v}</b></div>'
                        for k,v in h_stats.items()])
        st.markdown(f'<div class="info-box">{rows}</div>', unsafe_allow_html=True)

    # H par jour de semaine
    st.markdown('<div class="section-lbl">H moyen par jour de semaine</div>', unsafe_allow_html=True)
    dow_map  = {0:"Lun",1:"Mar",2:"Mer",3:"Jeu",4:"Ven"}
    day_keys = sorted(day_cache.keys())
    dow_h    = {d: [] for d in range(5)}
    for dk in day_keys:
        dt  = pd.Timestamp(dk)
        dow = dt.dayofweek
        if dow < 5:
            dow_h[dow].append(day_cache[dk]["hurst"])

    dow_means  = [np.mean(dow_h[d]) if dow_h[d] else 0.5 for d in range(5)]
    dow_colors = [GREEN if v < hurst_threshold else RED for v in dow_means]

    fig_dow = go.Figure(go.Bar(
        x=list(dow_map.values()), y=dow_means,
        marker_color=dow_colors,
        text=[f"{v:.3f}" for v in dow_means], textposition="outside",
    ))
    fig_dow.add_hline(y=hurst_threshold, line=dict(color=YELLOW, dash="dash"),
                      annotation_text=f"Seuil {hurst_threshold}")
    fig_dow.update_layout(**DARK, height=280, yaxis=dict(range=[0, 0.8]),
                          title="H moyen par jour — plus bas = plus MR")
    st.plotly_chart(fig_dow, use_container_width=True)

    # H par mois
    st.markdown('<div class="section-lbl">H moyen par mois</div>', unsafe_allow_html=True)
    month_h = {}
    for dk in day_keys:
        m = dk[:7]
        if m not in month_h: month_h[m] = []
        month_h[m].append(day_cache[dk]["hurst"])

    months   = sorted(month_h.keys())
    m_means  = [np.mean(month_h[m]) for m in months]
    m_colors = [GREEN if v < hurst_threshold else RED for v in m_means]

    fig_mh = go.Figure(go.Bar(
        x=months, y=m_means, marker_color=m_colors,
        text=[f"{v:.3f}" for v in m_means], textposition="outside",
    ))
    fig_mh.add_hline(y=hurst_threshold, line=dict(color=YELLOW, dash="dash"))
    fig_mh.update_layout(**DARK, height=260, yaxis=dict(range=[0, 0.8]),
                          title="H moyen par mois")
    st.plotly_chart(fig_mh, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════
# TAB 3 — SIGNAL & TIMING
# ═══════════════════════════════════════════════════════════════════════
with t3:
    c1, c2 = st.columns(2)

    with c1:
        st.markdown('<div class="section-lbl">Distribution Z-score à l\'entrée</div>', unsafe_allow_html=True)
        fig_z = go.Figure()
        z_long  = trades_df[trades_df["direction"] == "long"]["z"].abs()
        z_short = trades_df[trades_df["direction"] == "short"]["z"].abs()
        fig_z.add_trace(go.Histogram(x=z_long,  name="LONG",  marker_color=GREEN, opacity=0.7, nbinsx=20))
        fig_z.add_trace(go.Histogram(x=z_short, name="SHORT", marker_color=RED,   opacity=0.7, nbinsx=20))
        fig_z.add_vline(x=band_k, line=dict(color=YELLOW, dash="dash"), annotation_text=f"Seuil {band_k}σ")
        fig_z.update_layout(**DARK, height=280, barmode="overlay",
                            title="|Z| à l'entrée", xaxis_title="|Z-score|", yaxis_title="Nb trades")
        st.plotly_chart(fig_z, use_container_width=True)

    with c2:
        st.markdown('<div class="section-lbl">Win Rate par bucket Z-score</div>', unsafe_allow_html=True)
        z_abs  = trades_df["z"].abs()
        bins   = [band_k, band_k+0.5, band_k+1.0, band_k+1.5, band_k+2.0, 99]
        labels = [f"{bins[i]:.1f}–{bins[i+1]:.1f}σ" if bins[i+1] < 90 else f">{bins[i]:.1f}σ"
                  for i in range(len(bins)-1)]
        bkt_wr = []
        bkt_n  = []
        for i in range(len(bins)-1):
            mask = (z_abs >= bins[i]) & (z_abs < bins[i+1])
            sub  = trades_df[mask]
            bkt_wr.append(float(sub["win"].mean()) if len(sub) > 0 else 0)
            bkt_n.append(len(sub))

        fig_bk = go.Figure(go.Bar(
            x=labels, y=[v*100 for v in bkt_wr],
            marker_color=[GREEN if v >= 0.50 else YELLOW if v >= 0.45 else RED for v in bkt_wr],
            text=[f"{v*100:.0f}% (n={bkt_n[i]})" for i,v in enumerate(bkt_wr)],
            textposition="outside",
        ))
        fig_bk.add_hline(y=50, line=dict(color="#555", dash="dash"), annotation_text="50%")
        fig_bk.update_layout(**DARK, height=280, yaxis=dict(range=[0,100]),
                             title="WR par intensité signal")
        st.plotly_chart(fig_bk, use_container_width=True)

    # Win rate par heure
    st.markdown('<div class="section-lbl">Win Rate et volume de trades par heure</div>', unsafe_allow_html=True)
    hour_grp = trades_df.groupby("hour").agg(
        wr=("win","mean"), n=("win","count"), pnl=("pnl","sum")
    ).reset_index()

    fig_hr = make_subplots(specs=[[{"secondary_y": True}]])
    fig_hr.add_trace(go.Bar(x=hour_grp["hour"], y=hour_grp["n"], name="Nb trades",
                             marker_color="#1a1a1a"), secondary_y=True)
    fig_hr.add_trace(go.Scatter(x=hour_grp["hour"], y=hour_grp["wr"]*100,
                                mode="lines+markers", name="Win Rate",
                                line=dict(color=TEAL, width=2),
                                marker=dict(color=[GREEN if v >= 0.5 else RED for v in hour_grp["wr"]], size=8)),
                     secondary_y=False)
    fig_hr.add_hline(y=50, line=dict(color="#555", dash="dash"), secondary_y=False)
    fig_hr.update_layout(**DARK, height=300, title="Analyse par heure NY")
    fig_hr.update_yaxes(title_text="Win Rate %", range=[0,100], secondary_y=False)
    fig_hr.update_yaxes(title_text="Nb trades", secondary_y=True)
    st.plotly_chart(fig_hr, use_container_width=True)

    # Win rate par jour de semaine
    st.markdown('<div class="section-lbl">Win Rate par jour de semaine</div>', unsafe_allow_html=True)
    dow_grp = trades_df.groupby("dow").agg(wr=("win","mean"), n=("win","count")).reset_index()
    dow_labels = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi"]
    fig_dw = go.Figure(go.Bar(
        x=[dow_labels[int(d)] for d in dow_grp["dow"]],
        y=dow_grp["wr"]*100,
        marker_color=[GREEN if v >= 0.5 else RED for v in dow_grp["wr"]],
        text=[f"{v*100:.0f}% (n={int(n)})" for v,n in zip(dow_grp["wr"], dow_grp["n"])],
        textposition="outside",
    ))
    fig_dw.add_hline(y=50, line=dict(color="#555", dash="dash"))
    fig_dw.update_layout(**DARK, height=260, yaxis=dict(range=[0,100]),
                         title="WR par jour de semaine")
    st.plotly_chart(fig_dw, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════
# TAB 4 — MONTE CARLO
# ═══════════════════════════════════════════════════════════════════════
with t4:
    st.markdown('<div class="section-lbl">Simulation Monte Carlo — Challenge Apex 50K EOD</div>',
                unsafe_allow_html=True)
    st.caption(f"{mc_sims} simulations × {mc_days} jours | Capital ${capital_ui:,.0f} | DD max ${max_dd_ui:,.0f} | Target +${profit_target_ui:,.0f} | Risk {mc_risk}% DD/trade")

    with st.spinner("Monte Carlo…"):
        daily_pnls = trades_df.groupby("date")["pnl"].sum().values
        if len(daily_pnls) < 5:
            st.warning("Pas assez de données."); st.stop()

        passed_mc = 0; busted_mc = 0
        eq_paths  = []

        for _ in range(mc_sims):
            days_sample = np.random.choice(daily_pnls, size=mc_days, replace=True)
            eq   = capital_ui; peak = capital_ui; bust = False; done = False
            path = [eq]
            for pnl in days_sample:
                eq += pnl; path.append(eq)
                if eq > peak: peak = eq
                if (peak - eq) >= max_dd_ui: bust = True; break
                if (eq - capital_ui) >= profit_target_ui: done = True; break
            if bust:  busted_mc += 1
            elif done: passed_mc += 1
            if len(eq_paths) < 200: eq_paths.append(path)

        pass_rate = passed_mc / mc_sims * 100
        bust_rate = busted_mc / mc_sims * 100
        open_rate = 100 - pass_rate - bust_rate

    pr_col = GREEN if pass_rate >= 50 else YELLOW if pass_rate >= 30 else RED

    def kmc(v, l, c="#fff"):
        return f'<div class="stat-cell"><div class="stat-num" style="color:{c}">{v}</div><div class="stat-lbl">{l}</div></div>'
    st.markdown(f"""<div class="stat-row">
        {kmc(f"{pass_rate:.0f}%", "Pass Rate", pr_col)}
        {kmc(f"{bust_rate:.0f}%", "Bust Rate", RED)}
        {kmc(f"{open_rate:.0f}%", "En cours", "#888")}
        {kmc(f"{mc_sims:,}", "Simulations", CYAN)}
    </div>""", unsafe_allow_html=True)

    # Chemins equity
    fig_mc = go.Figure()
    for path in eq_paths[:150]:
        x_range = list(range(len(path)))
        final   = path[-1]
        color   = "rgba(0,255,136,0.04)" if final >= capital_ui + profit_target_ui else \
                  "rgba(255,51,102,0.04)" if final <= capital_ui - max_dd_ui else "rgba(255,214,0,0.03)"
        fig_mc.add_trace(go.Scatter(y=path, x=x_range, mode="lines",
                                    line=dict(width=0.5, color=color.replace("0.04","0.5")),
                                    showlegend=False))
    fig_mc.add_hline(y=capital_ui + profit_target_ui,
                     line=dict(color=GREEN, dash="dash", width=1.5),
                     annotation_text=f"Target +${profit_target_ui:,.0f}")
    fig_mc.add_hline(y=capital_ui - max_dd_ui,
                     line=dict(color=RED, dash="dash", width=1.5),
                     annotation_text=f"Bust −${max_dd_ui:,.0f}")
    fig_mc.update_layout(**DARK, height=360, yaxis_tickformat="$,.0f",
                         title=f"200 chemins simulés — Pass {pass_rate:.0f}%")
    st.plotly_chart(fig_mc, use_container_width=True)

    # Distribution P&L final
    final_pnls = []
    for _ in range(mc_sims):
        days_s = np.random.choice(daily_pnls, size=mc_days, replace=True)
        eq = capital_ui; pk = capital_ui
        for p in days_s:
            eq += p
            if eq > pk: pk = eq
            if pk - eq >= max_dd_ui: break
        final_pnls.append(eq - capital_ui)

    fig_fp = go.Figure(go.Histogram(
        x=final_pnls, nbinsx=50,
        marker_color=[GREEN if v > profit_target_ui else RED if v < -max_dd_ui else YELLOW
                      for v in np.linspace(min(final_pnls), max(final_pnls), 50)],
    ))
    fig_fp.add_vline(x=profit_target_ui, line=dict(color=GREEN, dash="dash"), annotation_text="Target")
    fig_fp.add_vline(x=-max_dd_ui,       line=dict(color=RED,   dash="dash"), annotation_text="Bust")
    fig_fp.add_vline(x=0, line=dict(color="#555", dash="dot"))
    fig_fp.update_layout(**DARK, height=260, xaxis_tickformat="$,.0f",
                         title="Distribution P&L fin de mois")
    st.plotly_chart(fig_fp, use_container_width=True)

    # ── Risk % Sweep ──────────────────────────────────────────────────────
    st.markdown('<div class="section-lbl">Sweep Risk % — Tradeoff Pass Rate vs Bust Rate</div>',
                unsafe_allow_html=True)
    st.caption("Chaque point = 1000 simulations avec ce risk %. Objectif : maximiser Pass Rate avec Bust Rate < 10%")

    if st.button("▶ Lancer le sweep Risk %", type="secondary"):
        risk_pcts = [3, 5, 7, 10, 12, 15, 18, 20, 25]
        sweep_res = []
        sp = st.progress(0)

        for idx_r, rp in enumerate(risk_pcts):
            # Rescale daily P&Ls proportionnellement au risk %
            scale = rp / max(mc_risk, 1)
            scaled_pnls = daily_pnls * scale

            p_cnt = 0; b_cnt = 0
            avg_days_to_pass = []

            for _ in range(mc_sims):
                days_s = np.random.choice(scaled_pnls, size=mc_days, replace=True)
                eq = capital_ui; pk = capital_ui; bust = False; done = False; d = 0
                for pnl in days_s:
                    d += 1
                    eq += pnl
                    if eq > pk: pk = eq
                    if (pk - eq) >= max_dd_ui: bust = True; break
                    if (eq - capital_ui) >= profit_target_ui: done = True; break
                if bust:  b_cnt += 1
                elif done:
                    p_cnt += 1
                    avg_days_to_pass.append(d)

            sweep_res.append(dict(
                risk_pct=rp,
                pass_rate=p_cnt / mc_sims * 100,
                bust_rate=b_cnt / mc_sims * 100,
                open_rate=(mc_sims - p_cnt - b_cnt) / mc_sims * 100,
                avg_days=float(np.mean(avg_days_to_pass)) if avg_days_to_pass else mc_days,
            ))
            sp.progress((idx_r + 1) / len(risk_pcts))

        sw_df = pd.DataFrame(sweep_res)

        fig_sw = make_subplots(specs=[[{"secondary_y": True}]])
        fig_sw.add_trace(go.Scatter(
            x=sw_df["risk_pct"], y=sw_df["pass_rate"],
            mode="lines+markers", name="Pass Rate",
            line=dict(color=GREEN, width=2.5),
            marker=dict(size=9, color=[GREEN if v >= 40 else YELLOW if v >= 25 else RED
                                       for v in sw_df["pass_rate"]]),
        ), secondary_y=False)
        fig_sw.add_trace(go.Scatter(
            x=sw_df["risk_pct"], y=sw_df["bust_rate"],
            mode="lines+markers", name="Bust Rate",
            line=dict(color=RED, width=2, dash="dot"),
            marker=dict(size=8, color=RED),
        ), secondary_y=False)
        fig_sw.add_trace(go.Bar(
            x=sw_df["risk_pct"], y=sw_df["avg_days"],
            name="Jours moy. jusqu'au pass",
            marker_color="rgba(0,229,255,0.15)",
        ), secondary_y=True)
        fig_sw.add_hline(y=10, line=dict(color=RED, dash="dash", width=1),
                         annotation_text="Bust max toléré 10%", secondary_y=False)
        fig_sw.add_hline(y=40, line=dict(color=GREEN, dash="dash", width=1),
                         annotation_text="Pass cible 40%", secondary_y=False)
        fig_sw.update_layout(
            **DARK, height=380,
            title="Pass Rate & Bust Rate selon le Risk % par trade",
            legend=dict(orientation="h", y=1.12),
        )
        fig_sw.update_yaxes(title_text="Taux (%)", range=[0, 100], secondary_y=False)
        fig_sw.update_yaxes(title_text="Jours jusqu'au pass", secondary_y=True)
        st.plotly_chart(fig_sw, use_container_width=True)

        # Table
        sw_df["optimal"] = (sw_df["bust_rate"] <= 10) & (sw_df["pass_rate"] == sw_df.loc[sw_df["bust_rate"] <= 10, "pass_rate"].max())
        st.dataframe(
            sw_df[["risk_pct","pass_rate","bust_rate","open_rate","avg_days"]].style
                .format({"pass_rate":"{:.1f}%","bust_rate":"{:.1f}%","open_rate":"{:.1f}%","avg_days":"{:.1f}j"})
                .background_gradient(subset=["pass_rate"], cmap="RdYlGn")
                .background_gradient(subset=["bust_rate"], cmap="RdYlGn_r"),
            use_container_width=True, hide_index=True,
        )

        best = sw_df[sw_df["bust_rate"] <= 10].sort_values("pass_rate", ascending=False)
        if len(best):
            br = best.iloc[0]
            st.success(f"✅ Risk optimal : **{br['risk_pct']:.0f}%** — Pass {br['pass_rate']:.1f}% | Bust {br['bust_rate']:.1f}% | Moy. {br['avg_days']:.1f} jours pour passer")


# ═══════════════════════════════════════════════════════════════════════
# TAB 5 — PREUVE D'EDGE
# ═══════════════════════════════════════════════════════════════════════
with t5:
    st.markdown('<div class="section-lbl">1 — Taux de reversion depuis les zones extrêmes</div>',
                unsafe_allow_html=True)
    st.caption("Mesure : dans les sessions MR (H < seuil), % de fois où une déviation Z > seuil revient au fair value dans les 30 barres suivantes")

    with st.spinner("Calcul taux de reversion…"):
        rev_results = []
        z_thresholds = [1.5, 2.0, 2.5, 3.0, 3.5]
        for zt in z_thresholds:
            rev = 0; tot = 0
            for dk, cached in day_cache.items():
                h = cached["hurst"]
                if h >= hurst_threshold: continue
                closes = cached["closes"]
                n = len(closes)
                for i in range(lookback, n - 30):
                    w = closes[i-lookback:i]
                    mid, std = w.mean(), w.std()
                    if std == 0: continue
                    z = abs((closes[i] - mid) / std)
                    if z < zt: continue
                    tot += 1
                    for j in range(i+1, min(n, i+31)):
                        c = closes[j]
                        if abs(c - mid) < std:
                            rev += 1; break
            rev_results.append(dict(z=zt, rev_pct=rev/tot*100 if tot > 0 else 0, n=tot))

        rev_df = pd.DataFrame(rev_results)

    fig_rev = go.Figure()
    fig_rev.add_trace(go.Bar(
        x=[f"{z}σ" for z in rev_df["z"]],
        y=rev_df["rev_pct"],
        marker_color=[GREEN if v >= 60 else YELLOW if v >= 50 else RED for v in rev_df["rev_pct"]],
        text=[f"{v:.0f}% (n={n})" for v,n in zip(rev_df["rev_pct"], rev_df["n"])],
        textposition="outside",
    ))
    fig_rev.add_hline(y=50, line=dict(color="#555", dash="dash"), annotation_text="Random = 50%")
    fig_rev.update_layout(**DARK, height=300, yaxis=dict(range=[0,100]),
                          title="Taux de reversion dans les 30 barres (sessions H < seuil)")
    st.plotly_chart(fig_rev, use_container_width=True)

    # 2 — Comparaison random entry
    st.markdown('<div class="section-lbl">2 — Comparaison entrée aléatoire</div>',
                unsafe_allow_html=True)
    st.caption("Même SL/TP/sizing mais entrées au hasard — mesure si l'edge vient du signal ou du hasard")

    with st.spinner("Random baseline…"):
        rng = np.random.default_rng(42)
        rand_trades = []
        for dk, cached in day_cache.items():
            closes = cached["closes"]
            n = len(closes)
            if n < lookback + 10: continue
            idx = rng.integers(lookback + skip_o, max(lookback + skip_o + 1, n - skip_c - 1))
            direction = "long" if rng.random() > 0.5 else "short"
            w = closes[idx-lookback:idx]
            mid, std = w.mean(), w.std()
            if std == 0: continue
            sl_pts = max(3.0, sl_mult * std)
            if direction == "long":
                tp_price = mid + tp_overshoot * std
            else:
                tp_price = mid - tp_overshoot * std
            result = 0.0
            for j in range(idx+1, min(n, idx+120)):
                c = closes[j]
                if direction == "long":
                    if c <= closes[idx] - sl_pts: result = -sl_pts; break
                    if c >= tp_price:             result = tp_price - closes[idx]; break
                else:
                    if c >= closes[idx] + sl_pts: result = -sl_pts; break
                    if c <= tp_price:             result = closes[idx] - tp_price; break
            rand_trades.append(dict(pnl=result * 2.0, win=result > 0))

        rand_df  = pd.DataFrame(rand_trades)
        rand_wr  = float(rand_df["win"].mean())
        rand_pos = rand_df[rand_df["pnl"] > 0]["pnl"].sum()
        rand_neg = abs(rand_df[rand_df["pnl"] < 0]["pnl"].sum())
        rand_pf  = rand_pos / max(rand_neg, 0.01)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"""<div class="info-box" style="border-color:{GREEN}33">
        <div style="color:{GREEN};font-size:1rem;font-weight:700">🎯 Hurst_MR Signal</div>
        <div>PF : <b style="color:{GREEN}">{pf:.2f}</b></div>
        <div>WR : <b style="color:{GREEN}">{wr*100:.1f}%</b></div>
        <div>Trades : {n}</div>
        <div>P&L total : <b style="color:{GREEN}">${total:+,.0f}</b></div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""<div class="info-box" style="border-color:{RED}33">
        <div style="color:{RED};font-size:1rem;font-weight:700">🎲 Entrée Aléatoire</div>
        <div>PF : <b style="color:{RED}">{rand_pf:.2f}</b></div>
        <div>WR : <b style="color:{RED}">{rand_wr*100:.1f}%</b></div>
        <div>Trades : {len(rand_df)}</div>
        <div>P&L total : <b style="color:{RED}">${rand_df["pnl"].sum():+,.0f}</b></div>
        </div>""", unsafe_allow_html=True)

    if pf > rand_pf * 1.2:
        st.success(f"✅ Edge confirmé — PF Hurst_MR {pf:.2f} vs aléatoire {rand_pf:.2f} (+{(pf/rand_pf-1)*100:.0f}%)")
    else:
        st.warning(f"⚠️ Edge faible — PF {pf:.2f} vs aléatoire {rand_pf:.2f}")

    # 3 — Impact Hurst threshold
    st.markdown('<div class="section-lbl">3 — Impact du seuil Hurst sur la qualité signal</div>',
                unsafe_allow_html=True)

    with st.spinner("Scan seuils Hurst…"):
        ht_results = []
        for ht_scan in [0.35, 0.40, 0.45, 0.50, 0.55]:
            mr = sum(1 for dk in day_cache if day_cache[dk]["hurst"] < ht_scan)
            sub = trades_df[trades_df["hurst"] < ht_scan]
            if len(sub) < 5: continue
            pos_s = sub[sub["pnl"]>0]["pnl"].sum()
            neg_s = abs(sub[sub["pnl"]<0]["pnl"].sum())
            pf_s  = pos_s / max(neg_s, 0.01)
            ht_results.append(dict(ht=ht_scan, pf=pf_s, wr=float(sub["win"].mean()),
                                   n=len(sub), mr_sessions=mr))

    ht_df = pd.DataFrame(ht_results)
    fig_ht = go.Figure()
    fig_ht.add_trace(go.Bar(x=[str(v) for v in ht_df["ht"]], y=ht_df["n"],
                             name="Nb trades", marker_color="#1a1a1a"))
    fig_ht.add_trace(go.Scatter(x=[str(v) for v in ht_df["ht"]], y=ht_df["pf"],
                                mode="lines+markers", name="PF",
                                line=dict(color=TEAL, width=2.5),
                                marker=dict(size=9, color=[GREEN if v>=1.5 else YELLOW for v in ht_df["pf"]]),
                                yaxis="y2"))
    fig_ht.add_hline(y=1.5, line=dict(color=GREEN, dash="dash"), yref="y2",
                     annotation_text="PF 1.5 cible")
    fig_ht.update_layout(
        **DARK, height=300,
        title="PF vs seuil Hurst — tradeoff qualité/quantité",
        yaxis=dict(title="Nb trades"),
        yaxis2=dict(title="PF", overlaying="y", side="right", range=[0.5, 3]),
        legend=dict(orientation="h", y=1.1),
    )
    st.plotly_chart(fig_ht, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════
# TAB 6 — GRID SEARCH  H × K × SL × TP
# ═══════════════════════════════════════════════════════════════════════
with t6:
    st.markdown('<div class="section-lbl">Grid Search — H × Band K × SL mult × TP overshoot</div>',
                unsafe_allow_html=True)

    # ── Critères de classement ────────────────────────────────────────
    dd_bust = max_dd_ui / capital_ui * 100   # % DD = bust (ex: 2500/50000 = 5%)
    dd_green = dd_bust * 0.60                # zone verte : < 60% du DD max

    st.markdown(f"""<div class="info-box" style="font-size:.75rem;line-height:1.8">
    <b style="color:{TEAL}">Critères de ranking 4PropTrader</b><br>
    📊 <b>Trades</b> : 480–720 / 5 ans (8–12/mois) &nbsp;|&nbsp;
    💰 <b>P&L</b> : ✅≥$60k · 🌟≥$100k · 🏆≥$150k &nbsp;|&nbsp;
    📈 <b>PF</b> : ≥1.9 &nbsp;|&nbsp;
    🎯 <b>Sharpe</b> : ≥1.9 &nbsp;|&nbsp;
    🎲 <b>WR</b> : ≥30% &nbsp;|&nbsp;
    🛡 <b>DD max</b> : 🟢&lt;{dd_green:.1f}% · 🟡{dd_green:.1f}–{dd_bust:.1f}% · 🔴≥{dd_bust:.1f}%
    </div>""", unsafe_allow_html=True)

    cg1, cg2, cg3, cg4 = st.columns(4)
    with cg1:
        ht_range = st.multiselect("Seuils H",
            [0.42, 0.45, 0.48, 0.50, 0.52, 0.55],
            default=[0.45, 0.50, 0.55])
    with cg2:
        bk_range = st.multiselect("Band k",
            [1.5, 2.0, 2.5, 3.0, 3.5],
            default=[1.5, 2.0, 2.5, 3.0])
    with cg3:
        sl_range = st.multiselect("SL mult",
            [0.75, 1.0, 1.25, 1.5, 2.0],
            default=[0.75, 1.0, 1.25, 1.5])
    with cg4:
        tp_os_range = st.multiselect("TP overshoot (σ)",
            [0.0, 0.25, 0.5, 0.75, 1.0, 1.5],
            default=[0.0, 0.25, 0.5, 0.75, 1.0])

    gs_opts1, gs_opts2 = st.columns(2)
    with gs_opts1:
        use_train_test = st.toggle("Train/Test split (70/30)", value=True,
            help="ON = grid sur 70% des données, validation sur 30% → évite l'overfit · OFF = full dataset")
    with gs_opts2:
        gs_atr_sl = st.toggle("SL adaptatif ATR(14)", value=use_atr_sl,
            help="ON = SL = sl_mult × max(std, ATR) · OFF = SL = sl_mult × std")

    atr_state  = "🟢 ON" if gs_atr_sl  else "🔴 OFF"
    tt_state   = "🟢 ON" if use_train_test else "🔴 OFF"
    total_combos_g = len(ht_range) * len(bk_range) * len(sl_range) * len(tp_os_range)
    st.caption(f"→ **{total_combos_g} combinaisons** · Train/Test {tt_state} · ATR SL {atr_state}")

    # Préparation train/test
    _all_keys     = sorted(day_cache.keys())
    _split        = int(len(_all_keys) * 0.70)
    _train_cache  = {k: day_cache[k] for k in _all_keys[:_split]}
    _test_cache   = {k: day_cache[k] for k in _all_keys[_split:]}
    _search_cache = _train_cache if use_train_test else day_cache

    def score_config(pf, wr, sharpe, dd, trades, pnl):
        """Score composite basé sur les critères 4PropTrader de l'utilisateur."""
        # ── Contraintes éliminatoires ──
        if trades < 480 or trades > 720: return 0.0
        if dd >= dd_bust:                return 0.0
        if pf < 1.5:                     return 0.0

        # ── Score P&L (35%) ──
        if   pnl >= 150_000: s_pnl = 1.00
        elif pnl >= 100_000: s_pnl = 0.85
        elif pnl >=  70_000: s_pnl = 0.70
        elif pnl >=  60_000: s_pnl = 0.55
        elif pnl >=  40_000: s_pnl = 0.30
        else:                s_pnl = 0.10

        # ── Score Trades (20%) — sweet spot 480-720 ──
        s_trades = 1.0 if 480 <= trades <= 720 else 0.0  # déjà filtré ci-dessus

        # ── Score PF (20%) ──
        if   pf >= 2.5: s_pf = 1.00
        elif pf >= 1.9: s_pf = 0.80
        elif pf >= 1.5: s_pf = 0.50
        else:           s_pf = 0.20

        # ── Score Sharpe (15%) ──
        if   sharpe >= 2.5: s_sh = 1.00
        elif sharpe >= 1.9: s_sh = 0.80
        elif sharpe >= 1.5: s_sh = 0.50
        else:               s_sh = 0.20

        # ── Score DD (10%) ──
        if   dd < dd_green: s_dd = 1.00   # zone verte
        elif dd < dd_bust:  s_dd = 0.50   # marginal
        else:               s_dd = 0.00   # bust (déjà éliminé)

        # ── Bonus WR ≥ 30% ──
        bonus_wr = 0.05 if wr >= 0.30 else 0.0

        return (0.35*s_pnl + 0.20*s_trades + 0.20*s_pf +
                0.15*s_sh  + 0.10*s_dd + bonus_wr)

    def rank_config(pf, wr, sharpe, dd, trades, pnl):
        """Tier de classement visuel."""
        if trades < 480 or trades > 720 or dd >= dd_bust or pf < 1.5:
            return "🔴 Éliminé"
        if pnl >= 100_000 and dd < dd_green and pf >= 1.9 and sharpe >= 1.9 and wr >= 0.30:
            return "🟢 Excellent"
        if pnl >= 60_000 and dd < dd_bust and pf >= 1.9:
            return "🟡 Acceptable"
        return "🟠 Marginal"

    if st.button("🔍 Lancer Grid Search", type="secondary"):
        if total_combos_g == 0:
            st.warning("Sélectionne au moins une valeur par paramètre.")
        else:
            if use_train_test:
                st.caption(f"Train : {len(_train_cache)} jours ({int(len(_train_cache)/len(_all_keys)*100)}%) · Test : {len(_test_cache)} jours ({int(len(_test_cache)/len(_all_keys)*100)}%)")

            grid_results = []
            prog = st.progress(0)
            idx_g = 0
            for ht_g in ht_range:
                for bk_g in bk_range:
                    for sl_g in sl_range:
                        for tp_g in tp_os_range:
                            # ── Backtest sur train (ou full) ──
                            t_df, _ = run_hurst_backtest(
                                _search_cache, ht_g, lookback, bk_g,
                                sl_g, tp_g, slip_pts, max_td, skip_o, skip_c,
                                capital=capital_ui, max_dd=max_dd_ui,
                                daily_lim=daily_lim_ui, profit_target=profit_target_ui,
                                risk_pct=mc_risk/100, atr_sl=gs_atr_sl,
                            )
                            idx_g += 1
                            prog.progress(idx_g / total_combos_g)
                            if len(t_df) < 10: continue
                            pos_g  = t_df[t_df["pnl"]>0]["pnl"].sum()
                            neg_g  = abs(t_df[t_df["pnl"]<0]["pnl"].sum())
                            pf_g   = pos_g / max(neg_g, 0.01)
                            wr_g   = float(t_df["win"].mean())
                            pnl_g  = t_df["pnl"].sum()
                            n_g    = len(t_df)
                            _d_g   = t_df.groupby("date")["pnl"].sum()
                            sh_g   = float(_d_g.mean()/_d_g.std()*np.sqrt(252)) if _d_g.std()>0 else 0
                            eq_g   = np.concatenate([[capital_ui], np.cumsum(t_df["pnl"].values)+capital_ui])
                            pk_g   = np.maximum.accumulate(eq_g)
                            dd_g   = float(((pk_g-eq_g)/np.maximum(pk_g, capital_ui)*100).max())

                            # ── Validation sur test (si train/test activé) ──
                            pf_test = wr_test = sh_test = dd_test = pnl_test = None
                            if use_train_test:
                                v_df, _ = run_hurst_backtest(
                                    _test_cache, ht_g, lookback, bk_g,
                                    sl_g, tp_g, slip_pts, max_td, skip_o, skip_c,
                                    capital=capital_ui, max_dd=max_dd_ui,
                                    daily_lim=daily_lim_ui, profit_target=profit_target_ui,
                                    risk_pct=mc_risk/100, atr_sl=gs_atr_sl,
                                )
                                if len(v_df) >= 5:
                                    pos_v = v_df[v_df["pnl"]>0]["pnl"].sum()
                                    neg_v = abs(v_df[v_df["pnl"]<0]["pnl"].sum())
                                    pf_test  = pos_v / max(neg_v, 0.01)
                                    wr_test  = float(v_df["win"].mean())
                                    pnl_test = v_df["pnl"].sum()
                                    eq_v = np.concatenate([[capital_ui], np.cumsum(v_df["pnl"].values)+capital_ui])
                                    pk_v = np.maximum.accumulate(eq_v)
                                    dd_test = float(((pk_v-eq_v)/np.maximum(pk_v, capital_ui)*100).max())
                                    _d_v = v_df.groupby("date")["pnl"].sum()
                                    sh_test = float(_d_v.mean()/_d_v.std()*np.sqrt(252)) if _d_v.std()>0 else 0
                            sc_g   = score_config(pf_g, wr_g, sh_g, dd_g, n_g, pnl_g)
                            rk_g   = rank_config(pf_g, wr_g, sh_g, dd_g, n_g, pnl_g)
                            row = dict(
                                Rank=rk_g, H=ht_g, K=bk_g, SL=sl_g, TP_os=tp_g,
                                PF=pf_g, WR=wr_g, Sharpe=sh_g, MaxDD=dd_g,
                                Trades=n_g, PnL=pnl_g, Score=sc_g,
                            )
                            if use_train_test and pf_test is not None:
                                row.update(dict(
                                    PF_test=pf_test, WR_test=wr_test,
                                    DD_test=dd_test, PnL_test=pnl_test,
                                    Sharpe_test=sh_test,
                                ))
                            grid_results.append(row)

            if grid_results:
                gr_df = pd.DataFrame(grid_results).sort_values("Score", ascending=False)

                # Comptage par tier
                n_exc  = (gr_df["Rank"] == "🟢 Excellent").sum()
                n_acc  = (gr_df["Rank"] == "🟡 Acceptable").sum()
                n_mar  = (gr_df["Rank"] == "🟠 Marginal").sum()
                n_eli  = (gr_df["Rank"] == "🔴 Éliminé").sum()

                def kgs(v, l, c):
                    return f'<div class="stat-cell"><div class="stat-num" style="color:{c}">{v}</div><div class="stat-lbl">{l}</div></div>'
                st.markdown(f"""<div class="stat-row">
                    {kgs(n_exc,  "🟢 Excellent", GREEN)}
                    {kgs(n_acc,  "🟡 Acceptable", YELLOW)}
                    {kgs(n_mar,  "🟠 Marginal", ORANGE)}
                    {kgs(n_eli,  "🔴 Éliminé", RED)}
                    {kgs(len(gr_df), "Total testés", CYAN)}
                </div>""", unsafe_allow_html=True)

                # Top 15 — toutes configs sauf éliminées
                show_df = gr_df[gr_df["Rank"] != "🔴 Éliminé"].head(15)
                if len(show_df) == 0:
                    show_df = gr_df.head(15)
                    st.warning("Aucune config viable — affichage du top 15 global.")
                else:
                    st.markdown(f'<div class="section-lbl">Top 15 — configs viables (trades 480–720 · DD < {dd_bust:.1f}% · PF ≥ 1.5)</div>',
                                unsafe_allow_html=True)

                def color_rank(val):
                    if "Excellent"  in str(val): return f"color: {GREEN}"
                    if "Acceptable" in str(val): return f"color: {YELLOW}"
                    if "Marginal"   in str(val): return f"color: {ORANGE}"
                    return f"color: {RED}"

                def color_dd(val):
                    try:
                        v = float(val)
                        if v < dd_green: return f"color: {GREEN}"
                        if v < dd_bust:  return f"color: {YELLOW}"
                        return f"color: {RED}"
                    except: return ""

                def color_pnl(val):
                    try:
                        v = float(str(val).replace("$","").replace(",","").replace("+",""))
                        if v >= 100_000: return f"color: {GREEN}"
                        if v >=  60_000: return f"color: {YELLOW}"
                        return f"color: {RED}"
                    except: return ""

                fmt = {"PF":"{:.2f}","WR":"{:.1%}","Sharpe":"{:.2f}",
                       "MaxDD":"{:.1f}%","Score":"{:.3f}","PnL":"${:+,.0f}"}
                dd_cols = ["MaxDD"]
                if use_train_test and "PF_test" in show_df.columns:
                    fmt.update({"PF_test":"{:.2f}","WR_test":"{:.1%}",
                                "DD_test":"{:.1f}%","PnL_test":"${:+,.0f}","Sharpe_test":"{:.2f}"})
                    dd_cols.append("DD_test")
                    st.caption("Colonnes _test = résultats sur les 30% out-of-sample — si PF_test ≈ PF → robuste")

                styled = (show_df.style
                    .format(fmt)
                    .applymap(color_rank, subset=["Rank"])
                    .applymap(color_dd,   subset=dd_cols)
                    .applymap(color_pnl,  subset=["PnL"])
                    .background_gradient(subset=["Score"], cmap="RdYlGn")
                )
                st.dataframe(styled, use_container_width=True, hide_index=True)

                # ── Meilleure config ──────────────────────────────────
                best = gr_df[gr_df["Score"] > 0].iloc[0] if (gr_df["Score"] > 0).any() else None
                if best is not None:
                    tier_color = GREEN if "Excellent" in best["Rank"] else YELLOW
                    st.markdown(f"""<div class="info-box" style="border-color:{tier_color}44">
                    <span style="color:{tier_color};font-size:1rem;font-weight:700">{best["Rank"]} — Config optimale</span><br>
                    H={best["H"]} · K={best["K"]} · SL={best["SL"]} · TP_os={best["TP_os"]}<br>
                    PF <b style="color:{tier_color}">{best["PF"]:.2f}</b> &nbsp;|&nbsp;
                    WR <b>{best["WR"]*100:.1f}%</b> &nbsp;|&nbsp;
                    Sharpe <b>{best["Sharpe"]:.2f}</b> &nbsp;|&nbsp;
                    DD <b>{best["MaxDD"]:.1f}%</b> &nbsp;|&nbsp;
                    Trades <b>{int(best["Trades"])}</b> &nbsp;|&nbsp;
                    P&L <b style="color:{GREEN}">${best["PnL"]:+,.0f}</b>
                    </div>""", unsafe_allow_html=True)

                # ── Heatmaps ──────────────────────────────────────────
                hm1, hm2 = st.columns(2)
                with hm1:
                    st.markdown('<div class="section-lbl">Score — Band K × TP overshoot</div>',
                                unsafe_allow_html=True)
                    piv1 = gr_df.pivot_table(index="K", columns="TP_os", values="Score", aggfunc="mean")
                    if not piv1.empty:
                        fig_hm1 = go.Figure(go.Heatmap(
                            z=piv1.values,
                            x=[str(c) for c in piv1.columns],
                            y=[str(i) for i in piv1.index],
                            colorscale=[[0,"#ff3366"],[0.5,"#ffd600"],[1,"#00ff88"]],
                            text=[[f"{v:.3f}" for v in row] for row in piv1.values],
                            texttemplate="%{text}", textfont=dict(size=10),
                            colorbar=dict(title="Score"),
                        ))
                        fig_hm1.update_layout(**DARK, height=300,
                            title="Score moyen — K × TP overshoot",
                            xaxis_title="TP overshoot (σ)", yaxis_title="Band K")
                        st.plotly_chart(fig_hm1, use_container_width=True)

                with hm2:
                    st.markdown('<div class="section-lbl">P&L moyen — Band K × TP overshoot</div>',
                                unsafe_allow_html=True)
                    piv2 = gr_df.pivot_table(index="K", columns="TP_os", values="PnL", aggfunc="mean")
                    if not piv2.empty:
                        fig_hm2 = go.Figure(go.Heatmap(
                            z=piv2.values,
                            x=[str(c) for c in piv2.columns],
                            y=[str(i) for i in piv2.index],
                            colorscale=[[0,"#ff3366"],[0.5,"#ffd600"],[1,"#00ff88"]],
                            text=[[f"${v:,.0f}" for v in row] for row in piv2.values],
                            texttemplate="%{text}", textfont=dict(size=9),
                            colorbar=dict(title="P&L $"),
                        ))
                        fig_hm2.add_hline(y=None)
                        fig_hm2.update_layout(**DARK, height=300,
                            title="P&L moyen — K × TP overshoot",
                            xaxis_title="TP overshoot (σ)", yaxis_title="Band K")
                        st.plotly_chart(fig_hm2, use_container_width=True)

                st.markdown('<div class="section-lbl">DD moyen — SL mult × Band K</div>',
                            unsafe_allow_html=True)
                piv3 = gr_df.pivot_table(index="SL", columns="K", values="MaxDD", aggfunc="mean")
                if not piv3.empty:
                    fig_hm3 = go.Figure(go.Heatmap(
                        z=piv3.values,
                        x=[str(c) for c in piv3.columns],
                        y=[str(i) for i in piv3.index],
                        colorscale=[[0,"#00ff88"],[0.5,"#ffd600"],[1,"#ff3366"]],
                        text=[[f"{v:.1f}%" for v in row] for row in piv3.values],
                        texttemplate="%{text}", textfont=dict(size=11),
                        colorbar=dict(title="Max DD %"),
                        zmin=0, zmax=dd_bust*1.5,
                    ))
                    fig_hm3.add_hline(y=None)
                    fig_hm3.update_layout(**DARK, height=280,
                        title=f"DD moyen — zone verte < {dd_green:.1f}% | danger > {dd_bust:.1f}%",
                        xaxis_title="Band K", yaxis_title="SL mult")
                    st.plotly_chart(fig_hm3, use_container_width=True)

            else:
                st.warning("Aucune combinaison viable — élargis les plages.")
    else:
        st.info("Configure les 4 dimensions et clique **🔍 Lancer Grid Search**.")

# ═══════════════════════════════════════════════════════════════════════
# TAB 7 — WALK-FORWARD
# ═══════════════════════════════════════════════════════════════════════
with t7:
    st.markdown("""
    > **Walk-Forward** : on optimise les paramètres sur une fenêtre **In-Sample (IS)**,
    > puis on teste sur la fenêtre suivante **Out-of-Sample (OOS)** — jamais vue pendant l'optimisation.
    > Si la stratégie est robuste, les métriques OOS restent cohérentes sur toutes les fenêtres.
    """)

    wf_c1, wf_c2, wf_c3, wf_c4 = st.columns(4)
    with wf_c1:
        wf_oos_m  = st.select_slider("Fenêtre OOS (mois)", [1, 2, 3, 6], value=3,
                                      help="Taille de chaque période de test OOS")
    with wf_c2:
        wf_is_min = st.select_slider("IS minimum (mois)", [3, 6, 9, 12], value=6,
                                      help="Taille minimale du premier IS avant le 1er OOS")
    with wf_c3:
        wf_step   = st.select_slider("Pas (mois)", [1, 2, 3, 6], value=3,
                                      help="De combien on avance IS+OOS à chaque fenêtre")
    with wf_c4:
        wf_opt    = st.toggle("Optimiser H + K sur IS", value=True,
                               help="ON : mini grid search sur IS pour trouver les meilleurs H threshold et K\n"
                                    "OFF : utilise les paramètres de la sidebar pour tous les OOS")

    wf_run = st.button("▶  Lancer Walk-Forward", type="primary", use_container_width=True,
                        key="wf_run_btn")

    if not wf_run and "wf_result" not in st.session_state:
        st.info("Configure les fenêtres ci-dessus et clique **▶ Lancer Walk-Forward**.")
    else:
        if wf_run:
            # ── 1. Construire la liste de mois disponibles ──────────────
            all_days   = sorted(day_cache.keys())   # "YYYY-MM-DD"
            all_months = sorted({d[:7] for d in all_days})  # "YYYY-MM"
            total_months = len(all_months)

            # Vérification
            needed = wf_is_min + wf_oos_m
            if total_months < needed:
                st.error(f"Pas assez de données : {total_months} mois disponibles, "
                         f"{needed} requis (IS_min={wf_is_min} + OOS={wf_oos_m}).")
                st.stop()

            # ── 2. Génération des fenêtres (IS croissant — anchored WF) ─
            windows = []
            oos_start_idx = wf_is_min   # premier OOS commence après IS_min mois
            while oos_start_idx + wf_oos_m <= total_months:
                is_months  = all_months[:oos_start_idx]
                oos_months = all_months[oos_start_idx: oos_start_idx + wf_oos_m]
                windows.append((is_months, oos_months))
                oos_start_idx += wf_step

            if not windows:
                st.error("Aucune fenêtre valide — ajuste IS_min ou le pas.")
                st.stop()

            # ── 3. Grid d'optimisation (si activé) ──────────────────────
            OPT_HT = [0.44, 0.46, 0.48, 0.50, 0.52, 0.54]
            OPT_K  = [2.75, 3.00, 3.25, 3.50]

            def _run_raw(cache_subset, ht, bk):
                """Backtest sans logique challenge — retourne trades_df pur."""
                t_df, _ = run_hurst_backtest(
                    cache_subset, ht, lookback, bk,
                    sl_mult, tp_overshoot, slip_pts, max_td,
                    skip_o, skip_c, timeout_bars=timeout_ui,
                    capital=capital_ui, max_dd=999_999,
                    daily_lim=daily_lim_ui,
                    profit_target=999_999,
                    atr_sl=use_atr_sl,
                )
                return t_df

            def _metrics(t_df):
                if t_df.empty or len(t_df) < 5:
                    return dict(n=0, wr=0., pf=0., sharpe=0., max_dd=0., pnl=0.)
                wr_  = t_df["win"].mean()
                pos_ = t_df[t_df["pnl"] > 0]["pnl"].sum()
                neg_ = abs(t_df[t_df["pnl"] < 0]["pnl"].sum())
                pf_  = pos_ / max(neg_, 0.01)
                eq_  = np.concatenate([[0], np.cumsum(t_df["pnl"].values)])
                pk_  = np.maximum.accumulate(eq_)
                dd_  = (pk_ - eq_) / np.maximum(pk_, capital_ui) * 100
                dly  = t_df.groupby("date")["pnl"].sum()
                sh_  = float(dly.mean() / dly.std() * np.sqrt(252)) if dly.std() > 0 else 0.
                return dict(n=len(t_df), wr=wr_, pf=pf_, sharpe=sh_,
                            max_dd=float(dd_.max()), pnl=float(t_df["pnl"].sum()))

            # ── 4. Boucle WF ─────────────────────────────────────────────
            wf_rows   = []   # stats par fenêtre
            oos_trades = []  # tous les trades OOS concaténés

            prog_bar = st.progress(0., "Walk-Forward en cours…")
            for idx, (is_mths, oos_mths) in enumerate(windows):
                prog_bar.progress((idx + 1) / len(windows),
                                  f"Fenêtre {idx+1}/{len(windows)}  "
                                  f"OOS={oos_mths[0]}→{oos_mths[-1]}")

                is_set  = {d for d in all_days if d[:7] in is_mths}
                oos_set = {d for d in all_days if d[:7] in oos_mths}
                is_cache  = {k: v for k, v in day_cache.items() if k in is_set}
                oos_cache = {k: v for k, v in day_cache.items() if k in oos_set}

                if not is_cache or not oos_cache:
                    continue

                # Optimisation IS
                if wf_opt:
                    best_sh, best_ht_, best_k_ = -999, hurst_threshold, band_k
                    for ht_ in OPT_HT:
                        for k_ in OPT_K:
                            t_ = _run_raw(is_cache, ht_, k_)
                            m_ = _metrics(t_)
                            if m_["n"] >= 20 and m_["sharpe"] > best_sh:
                                best_sh, best_ht_, best_k_ = m_["sharpe"], ht_, k_
                    used_ht, used_k = best_ht_, best_k_
                    is_m = _metrics(_run_raw(is_cache, used_ht, used_k))
                else:
                    used_ht, used_k = hurst_threshold, band_k
                    is_m = _metrics(_run_raw(is_cache, used_ht, used_k))

                # Test OOS
                oos_df = _run_raw(oos_cache, used_ht, used_k)
                oos_m  = _metrics(oos_df)

                # Collecte
                if not oos_df.empty:
                    oos_trades.append(oos_df)

                wf_rows.append({
                    "Fenêtre":   idx + 1,
                    "IS":        f"{is_mths[0]} → {is_mths[-1]}",
                    "OOS":       f"{oos_mths[0]} → {oos_mths[-1]}",
                    "H seuil":   f"{used_ht:.2f}",
                    "K bande":   f"{used_k:.2f}",
                    "IS PF":     round(is_m["pf"], 2),
                    "OOS PF":    round(oos_m["pf"], 2),
                    "OOS WR":    f"{oos_m['wr']*100:.1f}%",
                    "OOS Sharpe":round(oos_m["sharpe"], 2),
                    "OOS MaxDD": f"{oos_m['max_dd']:.1f}%",
                    "OOS Trades":oos_m["n"],
                    "OOS P&L":   f"${oos_m['pnl']:+,.0f}",
                    "_oos_pf":   oos_m["pf"],
                    "_oos_sh":   oos_m["sharpe"],
                    "_oos_pnl":  oos_m["pnl"],
                })

            prog_bar.empty()
            st.session_state["wf_result"]    = wf_rows
            st.session_state["wf_oos_trades"] = oos_trades

        # ── 5. Affichage ─────────────────────────────────────────────
        wf_rows    = st.session_state.get("wf_result", [])
        oos_trades = st.session_state.get("wf_oos_trades", [])

        if not wf_rows:
            st.warning("Pas de résultats — relance le walk-forward.")
        else:
            wf_df = pd.DataFrame(wf_rows)

            # ── KPIs OOS globaux ─────────────────────────────────────
            pfs_oos = wf_df["_oos_pf"].values
            shs_oos = wf_df["_oos_sh"].values
            n_wins_wf = int((pfs_oos > 1.0).sum())
            consistency = n_wins_wf / len(pfs_oos) * 100

            def kpi_wf(val, lbl, col="#fff"):
                return (f'<div class="stat-cell"><div class="stat-num" style="color:{col}">{val}</div>'
                        f'<div class="stat-lbl">{lbl}</div></div>')

            pf_mean = pfs_oos.mean()
            sh_mean = shs_oos.mean()
            cons_col = GREEN if consistency >= 75 else YELLOW if consistency >= 50 else RED
            pfm_col  = GREEN if pf_mean >= 1.5 else YELLOW if pf_mean >= 1.2 else RED
            shm_col  = GREEN if sh_mean >= 2.0 else YELLOW if sh_mean >= 1.0 else RED

            # Calmar OOS = Sharpe annualisé / MaxDD moyen
            _dd_mean = wf_df["OOS MaxDD"].mean() if "OOS MaxDD" in wf_df.columns else 0.0
            calmar_oos = sh_mean / max(_dd_mean / 100, 0.001)
            calm_col = GREEN if calmar_oos >= 2.0 else YELLOW if calmar_oos >= 1.0 else RED

            st.markdown(f"""<div class="stat-row">
                {kpi_wf(len(wf_df), "Fenêtres testées")}
                {kpi_wf(f"{pf_mean:.2f}", "PF moyen OOS", pfm_col)}
                {kpi_wf(f"{sh_mean:.2f}", "Sharpe moyen OOS", shm_col)}
                {kpi_wf(f"{calmar_oos:.2f}", "Calmar OOS", calm_col)}
                {kpi_wf(f"{consistency:.0f}%", "Fenêtres OOS > PF 1.0", cons_col)}
                {kpi_wf(f"{'Optimisé' if wf_opt else 'Fixe'}", "Paramètres")}
            </div>""", unsafe_allow_html=True)

            # ── Equity curve OOS concaténée ──────────────────────────
            if oos_trades:
                oos_all = pd.concat(oos_trades, ignore_index=True)
                oos_all = oos_all.sort_values("date")
                eq_oos  = np.concatenate([[capital_ui],
                                          np.cumsum(oos_all["pnl"].values) + capital_ui])
                pk_oos  = np.maximum.accumulate(eq_oos)
                dd_oos  = (pk_oos - eq_oos) / np.maximum(pk_oos, capital_ui) * 100

                c_eq, c_dd = st.columns([2, 1])
                with c_eq:
                    fig_wf = go.Figure()
                    fig_wf.add_trace(go.Scatter(
                        y=eq_oos, mode="lines", name="Equity OOS",
                        line=dict(color=TEAL, width=2),
                        fill="tozeroy", fillcolor="rgba(60,196,183,0.05)"
                    ))
                    fig_wf.add_hline(y=capital_ui + profit_target_ui,
                                     line=dict(color=GREEN, dash="dash", width=1),
                                     annotation_text=f"Target +${profit_target_ui:,.0f}")
                    fig_wf.add_hline(y=capital_ui - max_dd_ui,
                                     line=dict(color=RED, dash="dash", width=1),
                                     annotation_text=f"Bust −${max_dd_ui:,.0f}")

                    # Délimiteurs de fenêtres OOS
                    n_cum = 0
                    for row in wf_rows:
                        n_t = row["OOS Trades"]
                        if n_t > 0:
                            fig_wf.add_vline(x=n_cum, line=dict(color="#333", dash="dot", width=1))
                            fig_wf.add_annotation(
                                x=n_cum + n_t / 2, y=eq_oos.min(),
                                text=f"W{row['Fenêtre']}", showarrow=False,
                                font=dict(color="#444", size=9), yanchor="bottom"
                            )
                            n_cum += n_t

                    fig_wf.update_layout(**DARK, height=320,
                                         title=f"Equity OOS concaténée — {len(oos_all)} trades réels",
                                         yaxis=dict(tickprefix="$"),
                                         xaxis_title="Trades OOS (chronologique)")
                    st.plotly_chart(fig_wf, use_container_width=True)

                with c_dd:
                    # Stabilité PF + Sharpe par fenêtre
                    wf_plot = wf_df[wf_df["OOS Trades"] > 0].copy()
                    colors_pf = [GREEN if v >= 1.5 else YELLOW if v >= 1.0 else RED
                                 for v in wf_plot["_oos_pf"]]
                    fig_stab = go.Figure()
                    fig_stab.add_trace(go.Bar(
                        x=[f"W{r}" for r in wf_plot["Fenêtre"]],
                        y=wf_plot["_oos_pf"],
                        marker_color=colors_pf,
                        text=[f"{v:.2f}" for v in wf_plot["_oos_pf"]],
                        textposition="outside",
                        name="PF OOS", showlegend=False,
                    ))
                    fig_stab.add_hline(y=1.0, line=dict(color=RED, dash="dash", width=1),
                                       annotation_text="PF=1")
                    fig_stab.add_hline(y=1.5, line=dict(color=YELLOW, dash="dot", width=1),
                                       annotation_text="PF=1.5")
                    fig_stab.update_layout(**DARK, height=320,
                                           title="Profit Factor OOS par fenêtre",
                                           yaxis=dict(title="PF"),
                                           xaxis_title="Fenêtre OOS")
                    st.plotly_chart(fig_stab, use_container_width=True)

            # ── Tableau détaillé ──────────────────────────────────────
            st.markdown('<div class="section-lbl">Détail par fenêtre</div>',
                        unsafe_allow_html=True)
            disp_cols = ["Fenêtre","IS","OOS","H seuil","K bande",
                         "IS PF","OOS PF","OOS WR","OOS Sharpe","OOS MaxDD","OOS Trades","OOS P&L"]
            st.dataframe(
                wf_df[disp_cols].style.apply(
                    lambda col: [
                        (f"color:{GREEN}" if v >= 1.5 else
                         f"color:{YELLOW}" if v >= 1.0 else f"color:{RED}")
                        if col.name == "OOS PF" else ""
                        for v in col
                    ], axis=0
                ),
                use_container_width=True, hide_index=True,
            )

            # ── Verdict ───────────────────────────────────────────────
            st.markdown("---")
            if pf_mean >= 1.5 and consistency >= 75:
                st.success(
                    f"**Edge robuste.** PF moyen OOS = {pf_mean:.2f} · "
                    f"{consistency:.0f}% des fenêtres > PF 1.0. "
                    f"La stratégie n'est pas curve-fitted — elle est généralisable."
                )
            elif pf_mean >= 1.2 and consistency >= 50:
                st.warning(
                    f"**Edge modéré.** PF moyen = {pf_mean:.2f} · "
                    f"{consistency:.0f}% de fenêtres positives. "
                    f"Quelques fenêtres OOS < 1.0 → le régime change parfois. "
                    f"Envisage une re-calibration trimestrielle."
                )
            else:
                st.error(
                    f"**Edge fragile ou curve-fitting.** PF moyen = {pf_mean:.2f} · "
                    f"seulement {consistency:.0f}% de fenêtres OOS positives. "
                    f"Les paramètres ne se généralisent pas bien hors IS."
                )

            # ── Export WF ─────────────────────────────────────────────
            st.markdown('<div class="section-lbl">Export</div>', unsafe_allow_html=True)
            ec1, ec2 = st.columns(2)
            with ec1:
                _ts  = pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')
                _h_s = f"{hurst_threshold}" if not wf_opt else "optimisé"
                _k_s = f"{band_k}" if not wf_opt else "optimisé"
                _meta = "\n".join([
                    f"# RUN,{_ts}",
                    f"# OPTIMIZE,{'ON' if wf_opt else 'OFF'}",
                    f"# H,{_h_s}",
                    f"# K,{_k_s}",
                    f"# OOS_MOIS,{wf_oos_m}",
                    f"# IS_MIN_MOIS,{wf_is_min}",
                    f"# PAS_MOIS,{wf_step}",
                    f"# FENÊTRES,{len(wf_df)}",
                    f"# PF_MOY_OOS,{pf_mean:.3f}",
                    f"# SHARPE_MOY_OOS,{sh_mean:.3f}",
                    f"# CONSISTANCE,{consistency:.1f}%",
                ])
                _fname = (f"wf_H{str(hurst_threshold).replace('.','')}"
                          f"_K{str(band_k).replace('.','')}"
                          f"_OOS{wf_oos_m}m"
                          f"_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.csv")
                wf_csv = (_meta + "\n" + wf_df[disp_cols].to_csv(index=False)).encode("utf-8")
                st.download_button("⬇ Walk-Forward CSV", data=wf_csv,
                                   file_name=_fname,
                                   mime="text/csv", use_container_width=True)
            with ec2:
                if oos_trades:
                    oos_csv = oos_all.to_csv(index=False).encode("utf-8")
                    st.download_button("⬇ Trades OOS CSV", data=oos_csv,
                                       file_name=f"wf_oos_trades_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.csv",
                                       mime="text/csv", use_container_width=True)
