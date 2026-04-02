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

st.set_page_config(page_title="Étude Hurst_MR", page_icon="📐", layout="wide")

# ═══════════════════════════════════════════════════════════════════════
# THEME
# ═══════════════════════════════════════════════════════════════════════
DARK = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(6,6,6,0)",
    plot_bgcolor="rgba(10,10,10,1)",
    font=dict(color="#888", size=11, family="JetBrains Mono"),
    margin=dict(t=45, b=35, l=50, r=20),
)
TEAL, GREEN, RED, YELLOW, CYAN, ORANGE, MAGENTA = (
    "#3CC4B7", "#00ff88", "#ff3366", "#ffd600", "#00e5ff", "#ff9100", "#ff00e5"
)

def _css(raw):
    import re
    css = re.sub(r'/\*.*?\*/', '', raw, flags=re.DOTALL)
    st.markdown(f"<style>{' '.join(css.split())}</style>", unsafe_allow_html=True)

_css("""
*,*::before,*::after{box-sizing:border-box}
[data-testid="stAppViewContainer"]{background:#060606;font-family:'Inter',sans-serif}
[data-testid="stSidebar"]{background:#080808;border-right:1px solid #141414}
[data-testid="stHeader"]{background:transparent}
[data-testid="stToolbar"]{display:none}
.block-container{padding-top:1.2rem;max-width:1300px}
.ph{padding:1.2rem 0 .5rem;border-bottom:1px solid #1a1a1a;margin-bottom:1.2rem}
.ph-tag{font-family:'JetBrains Mono',monospace;font-size:.6rem;letter-spacing:.2em;color:#3CC4B7;text-transform:uppercase}
.ph-title{font-size:1.7rem;font-weight:700;color:#fff;letter-spacing:-.02em;margin:.2rem 0 0}
.stat-row{display:flex;gap:0;border:1px solid #1a1a1a;border-radius:10px;overflow:hidden;margin:.5rem 0 1rem}
.stat-cell{flex:1;padding:1.1rem .9rem;text-align:center;border-right:1px solid #1a1a1a;background:#060606}
.stat-cell:last-child{border-right:none}
.stat-num{font-size:1.5rem;font-weight:700;font-family:'JetBrains Mono',monospace}
.stat-lbl{font-size:.55rem;color:#444;letter-spacing:.14em;text-transform:uppercase;margin-top:.2rem}
.info-box{background:#080808;border:1px solid #141414;border-radius:10px;padding:1rem 1.3rem;margin:.4rem 0;font-family:'JetBrains Mono',monospace;font-size:.82rem;line-height:2}
.section-lbl{font-family:'JetBrains Mono',monospace;font-size:.58rem;font-weight:700;letter-spacing:.2em;color:#3CC4B7;text-transform:uppercase;margin:1.5rem 0 .7rem}
""")

st.markdown("""
<div class="ph">
  <div class="ph-tag">ÉTUDE · MNQ M1 CSV · LEC 25 + LEC 51</div>
  <div class="ph-title">Hurst_MR — Analyse Complète</div>
</div>""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════
CSV_DEFAULT = r"C:\Users\ryadb\Downloads\GLBX-20260401-SHPXRNTFHK\glbx-mdp3-20250331-20260330.ohlcv-1m.csv"

with st.sidebar:
    st.header("Données")
    csv_path = st.text_input("CSV MNQ M1", value=CSV_DEFAULT)
    st.markdown("---")
    st.header("Hurst_MR")
    hurst_threshold = st.slider("Seuil Hurst H <", 0.35, 0.60, 0.45, 0.01,
        help="H < seuil → session anti-persistante → MR valide")
    lookback = st.select_slider("Lookback (barres)", [15, 20, 30, 45, 60, 90, 120], value=30)
    band_k   = st.slider("Bande k (σ)", 1.5, 4.0, 2.5, 0.25)
    hmm_filter = st.toggle("Filtre HMM (Lec 51)", value=True,
        help="Skip barres HMM state=2 (trending) dans les sessions MR")
    st.markdown("---")
    st.header("Exécution")
    sl_mult   = st.slider("SL = k × σ", 0.5, 3.0, 1.25, 0.25)
    tp_ratio  = st.slider("TP ratio (→ fair value)", 0.5, 1.0, 1.0, 0.1)
    slip_pts  = st.number_input("Slippage (pts)", 0.0, 5.0, 0.5, 0.25)
    max_td    = st.number_input("Max trades/jour", 1, 10, 3, 1)
    st.markdown("---")
    st.header("Session NY")
    sh, sm = st.columns(2)
    with sh: s_h = st.number_input("Début h", 9, 15, 9)
    with sm: s_m = st.number_input("Début m", 0, 59, 30)
    eh, em = st.columns(2)
    with eh: e_h = st.number_input("Fin h", 12, 21, 16)
    with em: e_m = st.number_input("Fin m", 0, 59, 0)
    skip_o = st.number_input("Skip open (barres)", 0, 30, 5)
    skip_c = st.number_input("Skip close (barres)", 0, 30, 3)
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
    lags = range(2, min(n // 2, 50))
    rs_vals = []
    for lag in lags:
        chunks = [ts[i:i+lag] for i in range(0, n - lag + 1, lag)]
        rs_c = []
        for c in chunks:
            std = c.std()
            if std > 0:
                devs = np.cumsum(c - c.mean())
                rs_c.append((devs.max() - devs.min()) / std)
        if rs_c:
            rs_vals.append(np.mean(rs_c))
    if len(rs_vals) < 3: return 0.5
    try:
        return float(np.clip(np.polyfit(
            np.log(list(lags)[:len(rs_vals)]),
            np.log(rs_vals), 1)[0], 0.0, 1.0))
    except Exception:
        return 0.5


def hmm_states_vec(closes, lookback=60):
    n = len(closes)
    states = np.ones(n, dtype=int)
    rets   = np.abs(np.diff(np.log(np.maximum(closes, 1e-9))))
    rets   = np.concatenate([[0], rets])
    for i in range(lookback, n):
        w   = rets[max(0, i-200):i]
        p33 = np.nanpercentile(w, 33)
        p67 = np.nanpercentile(w, 67)
        v   = rets[i]
        if v <= p33:   states[i] = 0
        elif v >= p67: states[i] = 2
    return states


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
    # Trim to last year
    end = df["bar"].max()
    df  = df[df["bar"] >= end - pd.DateOffset(years=1)].reset_index(drop=True)
    # Rollover
    day_sym = df.groupby("date").apply(
        lambda g: g.loc[g["volume"].idxmax(), "symbol"] if len(g) > 0 else None
    ).reset_index(); day_sym.columns = ["date","dominant"]
    day_sym["prev"] = day_sym["dominant"].shift(1)
    day_sym["roll"] = (day_sym["dominant"] != day_sym["prev"]) & day_sym["prev"].notna()
    day_sym["roll"] = day_sym["roll"] | day_sym["roll"].shift(-1).fillna(False)
    roll_dates = set(day_sym.loc[day_sym["roll"], "date"].astype(str))
    df["is_roll"] = df["date"].astype(str).isin(roll_dates)
    return df, None


def filter_session(df, sh, sm, eh, em):
    t = df["bar"].dt.hour * 60 + df["bar"].dt.minute
    return df[(t >= sh*60+sm) & (t < eh*60+em)].reset_index(drop=True)


@st.cache_data(show_spinner=False)
def build_study_cache(csv_path, sh, sm, eh, em):
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
        h_val  = hurst_rs(closes)
        hmm    = hmm_states_vec(closes)
        days[str(day)] = dict(
            bars=bars, closes=closes, highs=highs, lows=lows,
            rets=rets, hurst=h_val, hmm=hmm,
        )
    return days, None


# ═══════════════════════════════════════════════════════════════════════
# BACKTEST
# ═══════════════════════════════════════════════════════════════════════

def run_hurst_backtest(day_cache, ht, lb, bk, hf, sl_m, tp_r, slip,
                       max_td, skip_o, skip_c,
                       capital=50_000, max_dd=2_000, daily_lim=1_000,
                       profit_target=3_000, risk_pct=0.10):
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

        cached = day_cache[day_key]
        h_val  = cached["hurst"]
        if h_val >= ht: continue            # session persistante → skip

        closes = cached["closes"]
        hmm    = cached["hmm"]
        bars   = cached["bars"]
        n      = len(closes)

        last_exit  = -1; daily_pnl = 0.; day_td = 0

        for i in range(lb + skip_o, n - skip_c):
            if day_td >= max_td or daily_pnl <= -daily_lim: break
            if i <= last_exit: continue
            if hf and i < len(hmm) and hmm[i] == 2: continue

            w   = closes[i - lb: i]
            mid = w.mean(); std = w.std()
            if std == 0: continue
            price = closes[i]; z = (price - mid) / std
            if abs(z) < bk: continue

            direction = "short" if z > 0 else "long"
            sl_pts = max(3.0, sl_m * std)
            sl_pts = min(sl_pts, 20.0)
            tp_price = price + tp_r * (mid - price)

            dd_rem = max(0., max_dd - dd_used)
            risk   = max(50., min(risk_pct * dd_rem, daily_lim * 0.40))
            lpc    = sl_pts * 2.0
            if lpc <= 0: continue
            contracts = max(1, min(60, int(risk / lpc)))
            if contracts * lpc > max(0., daily_lim + daily_pnl):
                contracts = max(1, int(max(0., daily_lim + daily_pnl) / lpc))
            if contracts <= 0: continue

            # Simulate trade
            result_pts = 0.0; exit_bar = i
            for j in range(i+1, min(n, i+120)):
                c = closes[j]
                if direction == "long":
                    if c <= price - sl_pts: result_pts = -sl_pts - slip; exit_bar = j; break
                    if c >= tp_price:       result_pts = (tp_price - price) - slip; exit_bar = j; break
                else:
                    if c >= price + sl_pts: result_pts = -sl_pts - slip; exit_bar = j; break
                    if c <= tp_price:       result_pts = (price - tp_price) - slip; exit_bar = j; break
            if result_pts == 0 and exit_bar == i: exit_bar = min(n-1, i+60)

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
                direction=direction, hurst=h_val,
                hmm_state=int(hmm[i]) if i < len(hmm) else 1,
                hour=hour, dow=dow,
            ))
            m_trades.append(dict(win=win, pnl=pnl))

    return pd.DataFrame(trades), pd.DataFrame(monthly)


# ═══════════════════════════════════════════════════════════════════════
# RUN
# ═══════════════════════════════════════════════════════════════════════

if not run_btn:
    st.info("Configure les paramètres dans la sidebar puis clique **▶ Lancer l'étude**.")
    st.stop()

if not os.path.exists(csv_path):
    st.error(f"CSV introuvable : `{csv_path}`"); st.stop()

with st.spinner("Chargement et calcul Hurst par session…"):
    day_cache, err = build_study_cache(csv_path, s_h, s_m, e_h, e_m)

if err: st.error(err); st.stop()
if not day_cache: st.error("Aucune session valide."); st.stop()

with st.spinner("Backtest en cours…"):
    trades_df, monthly_df = run_hurst_backtest(
        day_cache, hurst_threshold, lookback, band_k, hmm_filter,
        sl_mult, tp_ratio, slip_pts, max_td, skip_o, skip_c,
        risk_pct=mc_risk/100,
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
eq    = np.concatenate([[50_000], np.cumsum(trades_df["pnl"].values) + 50_000])
peak  = np.maximum.accumulate(eq)
dd_   = (peak - eq) / 50_000 * 100
max_dd_pct = float(dd_.max())
sharpe= (trades_df["pnl"].mean() / trades_df["pnl"].std() * np.sqrt(252)
         if trades_df["pnl"].std() > 0 else 0)

# Hurst study data
h_vals    = np.array([day_cache[d]["hurst"] for d in sorted(day_cache)])
total_days= len(h_vals)
mr_days   = int((h_vals < hurst_threshold).sum())
mr_pct    = mr_days / total_days * 100

# ─── TABS ────────────────────────────────────────────────────────────
t1,t2,t3,t4,t5,t6 = st.tabs([
    "📊 Résultats","🔬 Analyse Hurst","⏱ Signal & Timing",
    "🎲 Monte Carlo","🧪 Preuve d'Edge","🔧 Grid Search"
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
        {kpi(f"{mr_pct:.0f}%", "Sessions MR", TEAL)}
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
        fig_eq.add_hline(y=53_000, line=dict(color=GREEN, dash="dash", width=1),
                         annotation_text="Target +$3K", annotation_position="right")
        fig_eq.add_hline(y=48_000, line=dict(color=RED, dash="dash", width=1),
                         annotation_text="Bust −$2K", annotation_position="right")
        fig_eq.update_layout(**DARK, height=320, yaxis_tickformat="$,.0f",
                              title="Equity — $50K capital")
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

    # HMM state analysis
    if "hmm_state" in trades_df.columns:
        st.markdown('<div class="section-lbl">Impact filtre HMM (Lec 51)</div>', unsafe_allow_html=True)
        hmm_grp = trades_df.groupby("hmm_state").agg(
            wr=("win","mean"), n=("win","count"), pnl=("pnl","sum")
        ).reset_index()
        state_names = {0:"CALM", 1:"NORMAL", 2:"TREND"}
        state_colors = {0:GREEN, 1:TEAL, 2:RED}

        hc1, hc2, hc3 = st.columns(3)
        for _, row in hmm_grp.iterrows():
            s = int(row["hmm_state"])
            nm = state_names.get(s, str(s))
            col = state_colors.get(s, "#888")
            target = [hc1, hc2, hc3][s] if s <= 2 else hc3
            target.markdown(f"""
            <div class="info-box" style="border-color:{col}33;text-align:center">
                <div style="font-size:1.1rem;color:{col};font-weight:700">HMM {s} — {nm}</div>
                <div>WR : <b style="color:{col}">{row["wr"]*100:.1f}%</b></div>
                <div>Trades : <b>{int(row["n"])}</b></div>
                <div>P&L : <b style="color:{GREEN if row["pnl"]>0 else RED}">${row["pnl"]:+,.0f}</b></div>
            </div>""", unsafe_allow_html=True)

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
    st.caption(f"{mc_sims} simulations × {mc_days} jours | Capital $50K | DD max $2K | Target +$3K | Risk {mc_risk}% DD/trade")

    with st.spinner("Monte Carlo…"):
        daily_pnls = trades_df.groupby("date")["pnl"].sum().values
        if len(daily_pnls) < 5:
            st.warning("Pas assez de données."); st.stop()

        passed_mc = 0; busted_mc = 0
        eq_paths  = []

        for _ in range(mc_sims):
            days_sample = np.random.choice(daily_pnls, size=mc_days, replace=True)
            eq   = 50_000; peak = 50_000; bust = False; done = False
            path = [eq]
            for pnl in days_sample:
                eq += pnl; path.append(eq)
                if eq > peak: peak = eq
                if (peak - eq) >= 2_000: bust = True; break
                if (eq - 50_000) >= 3_000: done = True; break
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
        color   = "rgba(0,255,136,0.04)" if final >= 53_000 else \
                  "rgba(255,51,102,0.04)" if final <= 48_000 else "rgba(255,214,0,0.03)"
        fig_mc.add_trace(go.Scatter(y=path, x=x_range, mode="lines",
                                    line=dict(width=0.5, color=color.replace("0.04","0.5")),
                                    showlegend=False))
    fig_mc.add_hline(y=53_000, line=dict(color=GREEN, dash="dash", width=1.5), annotation_text="Target +$3K")
    fig_mc.add_hline(y=48_000, line=dict(color=RED,   dash="dash", width=1.5), annotation_text="Bust −$2K")
    fig_mc.update_layout(**DARK, height=360, yaxis_tickformat="$,.0f",
                         title=f"200 chemins simulés — Pass {pass_rate:.0f}%")
    st.plotly_chart(fig_mc, use_container_width=True)

    # Distribution P&L final
    final_pnls = []
    for _ in range(mc_sims):
        days_s = np.random.choice(daily_pnls, size=mc_days, replace=True)
        eq = 50_000; pk = 50_000
        for p in days_s:
            eq += p
            if eq > pk: pk = eq
            if pk - eq >= 2_000: break
        final_pnls.append(eq - 50_000)

    fig_fp = go.Figure(go.Histogram(
        x=final_pnls, nbinsx=50,
        marker_color=[GREEN if v > 3_000 else RED if v < -2_000 else YELLOW
                      for v in np.linspace(min(final_pnls), max(final_pnls), 50)],
    ))
    fig_fp.add_vline(x=3_000,  line=dict(color=GREEN, dash="dash"), annotation_text="Target")
    fig_fp.add_vline(x=-2_000, line=dict(color=RED,   dash="dash"), annotation_text="Bust")
    fig_fp.add_vline(x=0, line=dict(color="#555", dash="dot"))
    fig_fp.update_layout(**DARK, height=260, xaxis_tickformat="$,.0f",
                         title="Distribution P&L fin de mois")
    st.plotly_chart(fig_fp, use_container_width=True)


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
            tp_price = closes[idx] + tp_ratio * (mid - closes[idx])
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
# TAB 6 — GRID SEARCH
# ═══════════════════════════════════════════════════════════════════════
with t6:
    st.markdown('<div class="section-lbl">Grid Search — Hurst threshold × Band K</div>',
                unsafe_allow_html=True)
    st.caption("Score composite = PF + Sharpe/3 − DD/10")

    col_g1, col_g2 = st.columns(2)
    with col_g1:
        ht_range = st.multiselect("Seuils H testés",
            [0.35, 0.38, 0.40, 0.42, 0.45, 0.48, 0.50, 0.52, 0.55],
            default=[0.40, 0.45, 0.50])
    with col_g2:
        bk_range = st.multiselect("Bandes k testées",
            [1.5, 2.0, 2.5, 3.0, 3.5],
            default=[2.0, 2.5, 3.0])

    if st.button("🔍 Lancer Grid Search", type="secondary"):
        grid_results = []
        total_combos = len(ht_range) * len(bk_range) * 2  # ×2 pour hmm True/False
        prog = st.progress(0)
        idx_g = 0
        for ht_g in ht_range:
            for bk_g in bk_range:
                for hf_g in [True, False]:
                    t_df, m_df = run_hurst_backtest(
                        day_cache, ht_g, lookback, bk_g, hf_g,
                        sl_mult, tp_ratio, slip_pts, max_td, skip_o, skip_c,
                        risk_pct=mc_risk/100,
                    )
                    idx_g += 1
                    prog.progress(idx_g / total_combos)
                    if len(t_df) < 10: continue
                    pos_g  = t_df[t_df["pnl"]>0]["pnl"].sum()
                    neg_g  = abs(t_df[t_df["pnl"]<0]["pnl"].sum())
                    pf_g   = pos_g / max(neg_g, 0.01)
                    wr_g   = float(t_df["win"].mean())
                    sh_g   = (t_df["pnl"].mean()/t_df["pnl"].std()*np.sqrt(252)
                              if t_df["pnl"].std()>0 else 0)
                    eq_g   = np.concatenate([[50_000], np.cumsum(t_df["pnl"].values)+50_000])
                    pk_g   = np.maximum.accumulate(eq_g)
                    dd_g   = float(((pk_g-eq_g)/50_000*100).max())
                    score  = pf_g + sh_g/3 - dd_g/10
                    grid_results.append(dict(
                        H=ht_g, K=bk_g, HMM=hf_g,
                        PF=pf_g, WR=wr_g, Sharpe=sh_g, MaxDD=dd_g,
                        Trades=len(t_df), Score=score,
                        PnL=t_df["pnl"].sum(),
                    ))

        if grid_results:
            gr_df = pd.DataFrame(grid_results).sort_values("Score", ascending=False)

            st.markdown("**Top 10 configurations**")
            st.dataframe(
                gr_df.head(10).style
                    .format({"PF":":.2f","WR":"{:.1%}","Sharpe":":.2f",
                             "MaxDD":":.1f%","Score":":.3f","PnL":"$,.0f"})
                    .background_gradient(subset=["Score"], cmap="RdYlGn"),
                use_container_width=True, hide_index=True,
            )

            # Heatmap PF — H × K (HMM=True)
            st.markdown('<div class="section-lbl">Heatmap PF (HMM filter = True)</div>',
                        unsafe_allow_html=True)
            gr_hmm = gr_df[gr_df["HMM"] == True]
            if not gr_hmm.empty:
                piv = gr_hmm.pivot_table(index="H", columns="K", values="PF", aggfunc="mean")
                fig_hm = go.Figure(go.Heatmap(
                    z=piv.values, x=[str(c) for c in piv.columns],
                    y=[str(i) for i in piv.index],
                    colorscale=[[0,"#ff3366"],[0.5,"#ffd600"],[1,"#00ff88"]],
                    text=[[f"{v:.2f}" for v in row] for row in piv.values],
                    texttemplate="%{text}", textfont=dict(size=11),
                    zmin=0.8, zmax=2.5, colorbar=dict(title="PF"),
                ))
                fig_hm.update_layout(**DARK, height=280,
                                     title="PF — Hurst threshold × Band K",
                                     xaxis_title="Band K", yaxis_title="Hurst threshold")
                st.plotly_chart(fig_hm, use_container_width=True)
        else:
            st.warning("Aucune combinaison viable.")
    else:
        st.info("Configure les paramètres de grid search et clique **🔍 Lancer Grid Search**.")
