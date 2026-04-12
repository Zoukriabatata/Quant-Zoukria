"""
Journal de Trading — Hurst_MR MNQ
Visualisation complète des trades SQLite + ajout manuel + stats.
"""
import os
import sqlite3
import json
from datetime import datetime, date
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from config import JOURNAL_DB, CHALLENGE_DD, CHALLENGE_TARGET, HURST_THRESHOLD

st.set_page_config(page_title="Journal", page_icon="📒", layout="wide")
from styles import inject as _inj; _inj()

# ── Theme ─────────────────────────────────────────────────────────────
TEAL   = "#3CC4B7"
GREEN  = "#00ff88"
RED    = "#ff3366"
YELLOW = "#ffd600"
CYAN   = "#00e5ff"
DARK   = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(6,6,6,0)",
    plot_bgcolor="rgba(10,10,10,1)",
    font=dict(color="#888", size=11, family="JetBrains Mono"),
    margin=dict(t=40, b=30, l=50, r=20),
)
AXIS = dict(gridcolor="rgba(255,255,255,0.04)", linecolor="#1a1a1a",
            tickfont=dict(color="#444", size=11), zeroline=False)

st.markdown("""
<style>
.block-container{padding-top:1.2rem;max-width:1300px}
.ph{padding:1rem 0 0.8rem;border-bottom:1px solid #1a1a1a;margin-bottom:1.5rem}
.ph-tag{font-family:'JetBrains Mono',monospace;font-size:.6rem;letter-spacing:.2em;color:#3CC4B7;text-transform:uppercase}
.ph-title{font-size:1.8rem;font-weight:700;color:#fff;letter-spacing:-.02em;margin:.2rem 0 0}
.stat-row{display:flex;gap:0;border:1px solid #1a1a1a;border-radius:10px;overflow:hidden;margin:.5rem 0 1.2rem}
.stat-cell{flex:1;padding:1rem .8rem;text-align:center;border-right:1px solid #1a1a1a;background:#060606}
.stat-cell:last-child{border-right:none}
.stat-num{font-size:1.4rem;font-weight:700;font-family:'JetBrains Mono',monospace}
.stat-lbl{font-size:.55rem;color:#444;letter-spacing:.14em;text-transform:uppercase;margin-top:.2rem}
.trade-row{padding:.5rem .8rem;border:1px solid #1a1a1a;border-radius:6px;margin:3px 0;
           display:flex;gap:1rem;align-items:center;font-family:'JetBrains Mono',monospace;font-size:.78rem}
.trade-row.win{border-left:3px solid #00ff88}
.trade-row.loss{border-left:3px solid #ff3366}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="ph">
  <div class="ph-tag">JOURNAL · HURST_MR · MNQ</div>
  <div class="ph-title">Journal de Trading</div>
</div>""", unsafe_allow_html=True)

# ── Détection Cloud (pas de fichier local = DB vide éphémère) ─────────
_IS_CLOUD = not Path(JOURNAL_DB).exists() or os.environ.get("STREAMLIT_SHARING_MODE")
if _IS_CLOUD:
    st.markdown(f"""
    <div style="background:rgba(60,196,183,0.07);border:1px solid rgba(60,196,183,0.25);
         border-radius:8px;padding:.8rem 1.2rem;margin-bottom:1rem;
         font-family:'JetBrains Mono',monospace;font-size:.78rem;color:#3CC4B7;line-height:1.8">
        📡 <b>Mode Cloud</b> — base de données locale non disponible.<br>
        <span style="color:#555">Le journal fonctionne en session temporaire.
        Pour persister tes trades, lance l'app en local ou configure
        <code>JOURNAL_DB</code> dans les secrets Streamlit.</span>
    </div>
    """, unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════
# DB HELPERS
# ═══════════════════════════════════════════════════════════════════════

def _get_con():
    con = sqlite3.connect(JOURNAL_DB)
    con.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            date        TEXT,
            time_ny     TEXT,
            direction   TEXT,
            entry       REAL,
            sl_pts      REAL,
            tp          REAL,
            contracts   INTEGER DEFAULT 1,
            exit_price  REAL,
            pnl         REAL,
            hurst       REAL,
            z_score     REAL,
            notes       TEXT DEFAULT ''
        )""")
    con.commit()
    return con


@st.cache_data(ttl=10, show_spinner=False)
def load_trades() -> pd.DataFrame:
    try:
        con = _get_con()
        df = pd.read_sql("SELECT * FROM trades ORDER BY date DESC, time_ny DESC", con)
        con.close()
        if df.empty:
            return pd.DataFrame()
        df["date"] = pd.to_datetime(df["date"])
        df["win"]  = df["pnl"] > 0
        return df
    except Exception:
        return pd.DataFrame()


def insert_trade(d: dict):
    try:
        con = _get_con()
        con.execute("""
            INSERT INTO trades (date, time_ny, direction, entry, sl_pts, tp,
                                contracts, exit_price, pnl, hurst, z_score, notes)
            VALUES (:date,:time_ny,:direction,:entry,:sl_pts,:tp,
                    :contracts,:exit_price,:pnl,:hurst,:z_score,:notes)
        """, d)
        con.commit(); con.close()
        load_trades.clear()
        return True
    except Exception as e:
        st.error(f"DB error: {e}")
        return False


def delete_trade(trade_id: int):
    try:
        con = _get_con()
        con.execute("DELETE FROM trades WHERE id=?", (trade_id,))
        con.commit(); con.close()
        load_trades.clear()
    except Exception as e:
        st.error(f"DB error: {e}")


# ═══════════════════════════════════════════════════════════════════════
# LOAD DATA
# ═══════════════════════════════════════════════════════════════════════

df = load_trades()
no_data = df.empty

# ── KPIs globaux ─────────────────────────────────────────────────────

def _kpi(val, lbl, color="#fff"):
    return (f'<div class="stat-cell">'
            f'<div class="stat-num" style="color:{color}">{val}</div>'
            f'<div class="stat-lbl">{lbl}</div></div>')


if no_data:
    st.info("Aucun trade en base. Ajoute ton premier trade ci-dessous.")
    n = wr = pf = sharpe = max_dd_pct = total = 0
    eq = np.array([0.0])
else:
    n      = len(df)
    wins   = df["win"].sum()
    wr     = wins / n
    pos    = df[df["pnl"] > 0]["pnl"].sum()
    neg    = abs(df[df["pnl"] < 0]["pnl"].sum())
    pf     = pos / max(neg, 0.01)
    total  = df["pnl"].sum()
    eq_    = np.cumsum(df["pnl"].values[::-1])  # DESC→ASC : index 0=oldest
    eq     = np.concatenate([[0], eq_])
    peak   = np.maximum.accumulate(eq)
    dd_    = np.where(peak > 0, (peak - eq) / peak * 100, 0.0)
    max_dd_pct = float(dd_.max())
    daily  = df.groupby("date")["pnl"].sum()
    sharpe = float(daily.mean() / daily.std() * np.sqrt(252)) if daily.std() > 0 else 0.0
    dd_used = abs(df[df["pnl"] < 0]["pnl"].sum())
    dd_rem  = max(0., CHALLENGE_DD - dd_used)
    prog    = min(100., total / CHALLENGE_TARGET * 100)

if not no_data:
    pf_col  = GREEN if pf >= 1.5 else YELLOW if pf >= 1.2 else RED
    wr_col  = GREEN if wr >= 0.5 else YELLOW if wr >= 0.45 else RED
    dd_col  = GREEN if max_dd_pct < 3 else YELLOW if max_dd_pct < 5 else RED
    pnl_col = GREEN if total >= 0 else RED
    sh_col  = GREEN if sharpe >= 2 else YELLOW if sharpe >= 1 else RED

    st.markdown(f"""<div class="stat-row">
        {_kpi(n, "Trades")}
        {_kpi(f"{wr*100:.1f}%", "Win Rate", wr_col)}
        {_kpi(f"{pf:.2f}", "Profit Factor", pf_col)}
        {_kpi(f"{sharpe:.2f}", "Sharpe", sh_col)}
        {_kpi(f"{max_dd_pct:.1f}%", "Max DD", dd_col)}
        {_kpi(f"${total:+,.0f}", "P&L Total", pnl_col)}
        {_kpi(f"{prog:.0f}%" if not no_data else "—", "Challenge", GREEN if prog >= 50 else YELLOW)}
    </div>""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════
# TABS
# ═══════════════════════════════════════════════════════════════════════

tabs = st.tabs(["📈 Equity & P&L", "📋 Trades", "📊 Stats", "➕ Ajouter", "⬇ Export"])
t_equity, t_trades, t_stats, t_add, t_export = tabs

# ── TAB 1 : EQUITY & P&L ─────────────────────────────────────────────
with t_equity:
    if no_data:
        st.info("Pas encore de données.")
    else:
        c1, c2 = st.columns([2, 1])
        with c1:
            fig_eq = go.Figure()
            fig_eq.add_trace(go.Scatter(
                y=eq, mode="lines",
                line=dict(color=TEAL, width=2),
                fill="tozeroy", fillcolor="rgba(60,196,183,0.05)",
                name="Equity"
            ))
            fig_eq.add_hline(y=CHALLENGE_TARGET,
                             line=dict(color=GREEN, dash="dash", width=1),
                             annotation_text=f"Target +${CHALLENGE_TARGET:,.0f}")
            fig_eq.add_hline(y=-CHALLENGE_DD,
                             line=dict(color=RED, dash="dash", width=1),
                             annotation_text=f"Bust -${CHALLENGE_DD:,.0f}")
            fig_eq.update_layout(**DARK, height=320,
                                 title="Equity Curve",
                                 yaxis=dict(**AXIS, tickprefix="$"),
                                 xaxis=dict(**AXIS, title="Trades (chronologique)"))
            st.plotly_chart(fig_eq, use_container_width=True)

        with c2:
            daily_pnl = df.groupby("date")["pnl"].sum().reset_index()
            daily_pnl = daily_pnl.sort_values("date")
            colors_d  = [GREEN if v > 0 else RED for v in daily_pnl["pnl"]]
            fig_d = go.Figure(go.Bar(
                x=daily_pnl["date"].astype(str),
                y=daily_pnl["pnl"],
                marker_color=colors_d,
                text=[f"${v:+.0f}" for v in daily_pnl["pnl"]],
                textposition="outside",
            ))
            fig_d.update_layout(**DARK, height=320, title="P&L Journalier",
                                xaxis=dict(**AXIS), yaxis=dict(**AXIS, tickprefix="$"))
            st.plotly_chart(fig_d, use_container_width=True)

        # Drawdown chart
        fig_dd = go.Figure()
        fig_dd.add_trace(go.Scatter(
            y=-dd_, mode="lines", fill="tozeroy",
            fillcolor="rgba(255,51,102,0.08)",
            line=dict(color=RED, width=1.5), name="Drawdown"
        ))
        _dd_lim = -CHALLENGE_DD / max(eq.max(), 1) * 100
        fig_dd.add_hline(y=_dd_lim,
                         line=dict(color=YELLOW, dash="dot", width=1))
        fig_dd.update_layout(**DARK, height=200, title="Drawdown (%)",
                             xaxis=dict(**AXIS), yaxis=dict(**AXIS, ticksuffix="%"))
        st.plotly_chart(fig_dd, use_container_width=True)

# ── TAB 2 : TRADES ───────────────────────────────────────────────────
with t_trades:
    if no_data:
        st.info("Pas encore de données.")
    else:
        # Filtres
        fc1, fc2, fc3 = st.columns(3)
        with fc1:
            dir_filter = st.selectbox("Direction", ["Tout", "LONG", "SHORT"], key="j_dir")
        with fc2:
            res_filter = st.selectbox("Résultat", ["Tout", "Win", "Loss"], key="j_res")
        with fc3:
            n_show = st.select_slider("Afficher", [10, 25, 50, 100, 999], value=25, key="j_nshow")

        fdf = df.copy()
        if dir_filter != "Tout":
            fdf = fdf[fdf["direction"] == dir_filter]
        if res_filter == "Win":
            fdf = fdf[fdf["win"]]
        elif res_filter == "Loss":
            fdf = fdf[~fdf["win"]]

        fdf = fdf.head(n_show)

        # Affichage
        for _, row in fdf.iterrows():
            win_cls = "win" if row["win"] else "loss"
            pnl_col = GREEN if row["win"] else RED
            dir_badge = (f'<span style="background:rgba(0,255,136,.12);color:#00ff88;'
                         f'padding:1px 8px;border-radius:4px;font-size:.68rem">{row["direction"]}</span>'
                         if row["direction"] == "LONG" else
                         f'<span style="background:rgba(255,51,102,.12);color:#ff3366;'
                         f'padding:1px 8px;border-radius:4px;font-size:.68rem">{row["direction"]}</span>')
            h_str  = f"H={row['hurst']:.2f}" if pd.notna(row.get('hurst')) else ""
            z_str  = f"Z={row['z_score']:.1f}σ" if pd.notna(row.get('z_score')) else ""
            st.markdown(
                f'<div class="trade-row {win_cls}">'
                f'<span style="color:#555;min-width:30px">#{row["id"]}</span>'
                f'<span style="color:#777;min-width:85px">{str(row["date"])[:10]}</span>'
                f'<span style="min-width:55px">{row.get("time_ny","")}</span>'
                f'{dir_badge}'
                f'<span style="color:#888;min-width:70px">@{row["entry"]:.2f}</span>'
                f'<span style="color:{pnl_col};min-width:70px;font-weight:700">${row["pnl"]:+.2f}</span>'
                f'<span style="color:#555;font-size:.68rem">{h_str} {z_str}</span>'
                f'<span style="color:#444;font-size:.68rem;flex:1">{row.get("notes","")[:40]}</span>'
                f'</div>',
                unsafe_allow_html=True
            )

        st.markdown("---")
        with st.expander("Supprimer un trade"):
            del_id = st.number_input("ID du trade à supprimer", min_value=1, step=1)
            if st.button("Supprimer", type="secondary"):
                delete_trade(int(del_id))
                st.success(f"Trade #{del_id} supprimé.")
                st.rerun()

# ── TAB 3 : STATS ────────────────────────────────────────────────────
with t_stats:
    if no_data:
        st.info("Pas encore de données.")
    else:
        c1, c2 = st.columns(2)

        # Distribution P&L
        with c1:
            wins_arr   = df[df["win"]]["pnl"].values
            losses_arr = df[~df["win"]]["pnl"].values
            fig_dist = go.Figure()
            if len(wins_arr):
                fig_dist.add_trace(go.Histogram(
                    x=wins_arr, name="Wins", marker_color=GREEN,
                    opacity=0.7, nbinsx=20
                ))
            if len(losses_arr):
                fig_dist.add_trace(go.Histogram(
                    x=losses_arr, name="Losses", marker_color=RED,
                    opacity=0.7, nbinsx=20
                ))
            fig_dist.update_layout(**DARK, height=300,
                                   title="Distribution P&L (wins vs losses)",
                                   barmode="overlay",
                                   xaxis=dict(**AXIS, tickprefix="$"),
                                   yaxis=dict(**AXIS))
            st.plotly_chart(fig_dist, use_container_width=True)

        # Trades par heure
        with c2:
            if "time_ny" in df.columns and df["time_ny"].notna().any():
                _hour_s = pd.to_datetime(df["time_ny"], errors="coerce").dt.hour
                hourly = df.assign(hour=_hour_s).groupby("hour").agg(
                    n=("pnl", "count"),
                    wr=("win", "mean"),
                    pnl=("pnl", "sum")
                ).reset_index()
                colors_h = [GREEN if w >= 0.5 else YELLOW if w >= 0.4 else RED
                            for w in hourly["wr"]]
                fig_h = go.Figure(go.Bar(
                    x=hourly["hour"].astype(str) + "h",
                    y=hourly["n"],
                    marker_color=colors_h,
                    text=[f"{w:.0%}" for w in hourly["wr"]],
                    textposition="outside",
                ))
                fig_h.update_layout(**DARK, height=300,
                                    title="Trades par heure NY (couleur=win rate)",
                                    xaxis=dict(**AXIS), yaxis=dict(**AXIS))
                st.plotly_chart(fig_h, use_container_width=True)
            else:
                st.info("time_ny absent des données.")

        # Stats LONG vs SHORT
        c3, c4 = st.columns(2)
        with c3:
            by_dir = df.groupby("direction").agg(
                n=("pnl", "count"),
                wr=("win", "mean"),
                pnl=("pnl", "sum"),
                avg=("pnl", "mean")
            ).reset_index()
            fig_dir = go.Figure()
            for _, row in by_dir.iterrows():
                col_dir = GREEN if row["direction"] == "LONG" else CYAN
                fig_dir.add_trace(go.Bar(
                    x=[row["direction"]], y=[row["wr"] * 100],
                    marker_color=col_dir, name=row["direction"],
                    text=[f"{row['wr']:.0%}  ({row['n']} trades)"],
                    textposition="outside", showlegend=False,
                ))
            fig_dir.add_hline(y=50, line=dict(color=YELLOW, dash="dot", width=1))
            fig_dir.update_layout(**DARK, height=280,
                                  title="Win Rate — LONG vs SHORT",
                                  yaxis=dict(**AXIS, ticksuffix="%", range=[0, 100]),
                                  xaxis=dict(**AXIS))
            st.plotly_chart(fig_dir, use_container_width=True)

        with c4:
            # P&L mensuel
            monthly = (df.groupby(df["date"].dt.to_period("M").astype(str))["pnl"]
                       .sum().reset_index())
            monthly.columns = ["month", "pnl"]
            colors_m = [GREEN if v > 0 else RED for v in monthly["pnl"]]
            fig_m = go.Figure(go.Bar(
                x=monthly["month"], y=monthly["pnl"],
                marker_color=colors_m,
                text=[f"${v:+.0f}" for v in monthly["pnl"]],
                textposition="outside",
            ))
            fig_m.update_layout(**DARK, height=280, title="P&L Mensuel",
                                xaxis=dict(**AXIS), yaxis=dict(**AXIS, tickprefix="$"))
            st.plotly_chart(fig_m, use_container_width=True)

        # Hurst distribution (si disponible)
        if "hurst" in df.columns and df["hurst"].notna().any():
            h_vals = df["hurst"].dropna().values
            fig_hh = go.Figure()
            fig_hh.add_trace(go.Histogram(
                x=h_vals[df.loc[df["hurst"].notna(), "win"].values],
                name="Wins", marker_color=GREEN, opacity=0.7, nbinsx=15
            ))
            fig_hh.add_trace(go.Histogram(
                x=h_vals[~df.loc[df["hurst"].notna(), "win"].values],
                name="Losses", marker_color=RED, opacity=0.7, nbinsx=15
            ))
            fig_hh.add_vline(x=HURST_THRESHOLD, line=dict(color=TEAL, dash="dash"),
                             annotation_text=f"Seuil H={HURST_THRESHOLD}")
            fig_hh.update_layout(**DARK, height=280, barmode="overlay",
                                 title="Hurst au moment du signal (wins vs losses)",
                                 xaxis=dict(**AXIS, title="Hurst H"),
                                 yaxis=dict(**AXIS))
            st.plotly_chart(fig_hh, use_container_width=True)

# ── TAB 4 : AJOUTER ──────────────────────────────────────────────────
with t_add:
    st.markdown("**Ajouter un trade manuellement**")
    with st.form("add_trade", clear_on_submit=True):
        a1, a2, a3 = st.columns(3)
        with a1:
            trade_date = st.date_input("Date", value=date.today())
            direction  = st.selectbox("Direction", ["LONG", "SHORT"])
            entry      = st.number_input("Prix entrée", value=0.0, step=0.25)
        with a2:
            time_ny    = st.text_input("Heure NY (HH:MM)", value="")
            exit_price = st.number_input("Prix sortie", value=0.0, step=0.25)
            contracts  = st.number_input("Contrats", min_value=1, value=1)
        with a3:
            sl_pts     = st.number_input("SL (pts)", value=0.0, step=0.25)
            tp         = st.number_input("TP (prix)", value=0.0, step=0.25)
            hurst_val  = st.number_input("Hurst H", value=0.0, min_value=0.0, max_value=1.0, step=0.01)
            z_val      = st.number_input("Z-score", value=0.0, step=0.1)

        notes = st.text_area("Notes", placeholder="Contexte, setup, observations…", height=60)

        pnl_auto = (exit_price - entry) * contracts * 2.0 * (1 if direction == "LONG" else -1)
        st.caption(f"P&L calculé : **${pnl_auto:+.2f}** ({contracts} contrat(s) × 2$/pt)")

        submitted = st.form_submit_button("Enregistrer le trade", type="primary",
                                          use_container_width=True)
        if submitted:
            if entry == 0 or exit_price == 0:
                st.error("Entrée et sortie requis.")
            else:
                ok = insert_trade({
                    "date":       str(trade_date),
                    "time_ny":    time_ny,
                    "direction":  direction,
                    "entry":      entry,
                    "sl_pts":     sl_pts,
                    "tp":         tp,
                    "contracts":  contracts,
                    "exit_price": exit_price,
                    "pnl":        pnl_auto,
                    "hurst":      hurst_val if hurst_val > 0 else None,
                    "z_score":    z_val if z_val != 0 else None,
                    "notes":      notes,
                })
                if ok:
                    st.success(f"Trade enregistré — P&L ${pnl_auto:+.2f}")
                    st.rerun()

# ── TAB 5 : EXPORT ───────────────────────────────────────────────────
with t_export:
    if no_data:
        st.info("Pas encore de données à exporter.")
    else:
        st.markdown("**Exporter le journal**")

        ex1, ex2, ex3 = st.columns(3)

        with ex1:
            csv_all = df.drop(columns=["win"], errors="ignore").to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇ Tous les trades (CSV)",
                data=csv_all,
                file_name=f"journal_trades_{pd.Timestamp.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True,
            )

        with ex2:
            # Stats journalières
            daily_stats = df.groupby(df["date"].dt.date).agg(
                n_trades=("pnl", "count"),
                wins=("win", "sum"),
                pnl=("pnl", "sum"),
                avg_h=("hurst", "mean"),
                avg_z=("z_score", "mean"),
            ).reset_index()
            daily_stats["wr"] = daily_stats["wins"] / daily_stats["n_trades"]
            daily_csv = daily_stats.to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇ Stats journalières (CSV)",
                data=daily_csv,
                file_name=f"journal_daily_{pd.Timestamp.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True,
            )

        with ex3:
            summary_export = {
                "export_date": pd.Timestamp.now().isoformat(),
                "n_trades":    int(n),
                "win_rate":    round(float(wr), 4),
                "profit_factor": round(float(pf), 4),
                "sharpe":      round(float(sharpe), 4),
                "max_dd_pct":  round(float(max_dd_pct), 4),
                "total_pnl":   round(float(total), 2),
                "challenge_dd":     CHALLENGE_DD,
                "challenge_target": CHALLENGE_TARGET,
            }
            st.download_button(
                "⬇ Résumé JSON",
                data=json.dumps(summary_export, indent=2).encode("utf-8"),
                file_name=f"journal_summary_{pd.Timestamp.now().strftime('%Y%m%d')}.json",
                mime="application/json",
                use_container_width=True,
            )

        st.markdown("---")
        st.caption(f"Journal : `{JOURNAL_DB}` · {n} trades · dernière mise à jour : {df['date'].max().strftime('%Y-%m-%d') if not no_data else '—'}")
