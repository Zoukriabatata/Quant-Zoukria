"""
Live Signal Dashboard — Hurst_MR (Lec 25 + Lec 51)
Source prioritaire : dxFeed 4PropTrader via dxfeed_bridge.js → C:/tmp/mnq_live.json
Fallback          : yfinance NQ=F M1 (~15 min delay)
"""

import os
import warnings
import threading
import urllib.request
import urllib.parse
import urllib.error
import json
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import sqlite3
from streamlit_autorefresh import st_autorefresh

warnings.filterwarnings("ignore")

try:
    import yfinance as yf
    import pytz
except ImportError:
    st.error("pip install yfinance pytz")
    st.stop()

# ═══════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════

st.set_page_config(page_title="Live Signal", page_icon="⚡", layout="wide")
from styles import inject as _inj, refresh_bar as _refresh_bar, toast as _toast; _inj()

# Auto-refresh toutes les 2s (non-bloquant, pas de time.sleep)
st_autorefresh(interval=2000, key="live_autorefresh")

# Toast persistant après rerun
if "_ls_toast" in st.session_state:
    _t = st.session_state.pop("_ls_toast")
    st.markdown(_toast(_t, variant="success"), unsafe_allow_html=True)

from config import (DXFEED_FILE, JOURNAL_DB, CHALLENGE_DD, CHALLENGE_TARGET,
                   NTFY_TOPIC as _NTFY_TOPIC,
                   HURST_THRESHOLD, HURST_WIN, LOOKBACK, BAND_K, SL_MULT,
                   DISCORD_STATUS_FILE, DAILY_LOSS_LIM as _DAILY_LOSS_LIM)

SYMBOL          = "NQ=F"
TP_OVERSHOOT    = 0.0       # fair value pure
MAX_TRADES_DAY  = 5         # stop après N signaux — identique backtest
DAILY_LOSS_LIM  = _DAILY_LOSS_LIM   # stop si perte journalière > limite — identique backtest
SKIP_OPEN_BARS  = 5
SKIP_CLOSE_BARS = 3         # ignore les 3 dernières barres — identique backtest
SIGNAL_MAX_AGE_MIN = 120   # signal expiré après 120 min — identique timeout backtest

SESSION_START   = (15, 30)   # 9:30 NY = 15:30 Paris
SESSION_END     = (22,  0)   # 16:00 NY = 22:00 Paris

TICK_VALUE      = 2.0       # $/pt MNQ (NQ full = 20.0)

try:
    DISCORD_WEBHOOK = st.secrets.get("DISCORD_WEBHOOK", None) or os.environ.get("DISCORD_WEBHOOK", "")
except FileNotFoundError:
    DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK", "")
NTFY_TOPIC      = _NTFY_TOPIC

PARIS = pytz.timezone("Europe/Paris")

TEAL   = "#06b6d4"
GREEN  = "#10b981"
RED    = "#ef4444"
YELLOW = "#f59e0b"
CYAN   = "#06b6d4"
ORANGE = "#f97316"
BLUE   = "#3b82f6"
DARK   = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="#050505",
    font=dict(color="#94a3b8", size=11,
              family="'JetBrains Mono','Space Grotesk',monospace"),
    margin=dict(t=48, b=40, l=52, r=24),
    legend=dict(bgcolor="rgba(0,0,0,0.9)",
                bordercolor="rgba(148,163,184,0.10)", borderwidth=1,
                font=dict(size=11, color="#94a3b8"), itemsizing="constant"),
    hoverlabel=dict(bgcolor="#0a0a0a", bordercolor="rgba(59,130,246,0.4)",
                    font=dict(size=12, family="JetBrains Mono", color="#f1f5f9")),
)

# ═══════════════════════════════════════════════════════
# JOURNAL SQLite
# ═══════════════════════════════════════════════════════

def _db():
    con = sqlite3.connect(JOURNAL_DB)
    con.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            date      TEXT,
            time_ny   TEXT,
            direction TEXT,
            entry     REAL,
            sl_pts    REAL,
            tp        REAL,
            contracts INTEGER,
            exit_price REAL,
            pnl       REAL,
            hurst     REAL,
            z_score   REAL,
            notes     TEXT
        )
    """)
    con.commit()
    return con

def journal_add(date, time_ny, direction, entry, sl_pts, tp,
                contracts, exit_price, hurst, z_score, notes):
    pnl = (exit_price - entry) * (1 if direction == "LONG" else -1) * TICK_VALUE * contracts
    con = _db()
    con.execute(
        "INSERT INTO trades (date,time_ny,direction,entry,sl_pts,tp,contracts,"
        "exit_price,pnl,hurst,z_score,notes) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (date, time_ny, direction, entry, sl_pts, tp,
         contracts, exit_price, pnl, hurst, z_score, notes)
    )
    con.commit(); con.close()

@st.cache_data(ttl=10, show_spinner=False)
def journal_load():
    con = _db()
    df = pd.read_sql("SELECT * FROM trades ORDER BY id DESC", con)
    con.close()
    return df

def journal_delete(trade_id):
    con = _db()
    con.execute("DELETE FROM trades WHERE id=?", (trade_id,))
    con.commit(); con.close()

# ═══════════════════════════════════════════════════════
# CSS
# ═══════════════════════════════════════════════════════

st.markdown("""
<style>
.block-container { padding-top:1rem; max-width:1500px; }

/* KPI cards — via design system tokens */
.kpi-card {
    background: var(--bg-surface);
    border: 1px solid var(--border-default);
    border-radius: var(--r-lg);
    padding: 1rem 1.2rem; text-align: center;
    transition: var(--t-normal);
    box-shadow: var(--shadow-card);
}
.kpi-card:hover {
    border-color: var(--border-active);
    box-shadow: var(--shadow-card), var(--shadow-glow);
    transform: translateY(-2px);
}
.kpi-value {
    font-size: 1.9rem; font-weight: 700;
    font-family: 'JetBrains Mono',monospace; line-height: 1.1;
    color: var(--text-primary);
}
.kpi-label {
    font-size: .68rem; color: var(--text-muted);
    text-transform: uppercase; letter-spacing: .12em; margin-top: .35rem;
}

/* Signal cards with animated glow border */
.sig-long {
    background: linear-gradient(135deg,rgba(16,185,129,0.06),rgba(16,185,129,0.02));
    border: 1.5px solid rgba(16,185,129,0.40);
    border-radius: var(--r-lg); padding: 1.4rem 1.6rem;
    animation: pulseGlow--green 3s ease-in-out infinite;
}
.sig-short {
    background: linear-gradient(135deg,rgba(239,68,68,0.06),rgba(239,68,68,0.02));
    border: 1.5px solid rgba(239,68,68,0.40);
    border-radius: var(--r-lg); padding: 1.4rem 1.6rem;
    animation: pulseGlow--red 3s ease-in-out infinite;
}
.sig-none {
    background: var(--bg-surface); border: 1px solid var(--border-default);
    border-radius: var(--r-lg); padding: 1.4rem 1.6rem;
    color: var(--text-muted); text-align: center;
}
.ctx-box {
    background: var(--bg-surface); border: 1px solid var(--border-default);
    border-radius: var(--r-lg); padding: 1.1rem 1.4rem;
    transition: var(--t-normal);
}
.ctx-box:hover { border-color: var(--border-active); }
.gauge-track {
    background: var(--bg-elevated); border-radius: var(--r-pill);
    height: 5px; overflow: hidden; margin: 4px 0 10px;
}
.gauge-fill { height: 100%; border-radius: var(--r-pill); transition: width .4s cubic-bezier(.16,1,.3,1); }
.sec-label {
    font-family: 'JetBrains Mono',monospace; font-size: .62rem; font-weight: 700;
    letter-spacing: .18em; color: var(--accent-cyan); text-transform: uppercase;
    margin: 1.4rem 0 .6rem; padding-bottom: .4rem; border-bottom: 1px solid var(--border-subtle);
}
/* Legacy live-dot — now using .qm-live-dot */
.live-dot {
    display: inline-block; width: 7px; height: 7px;
    background: var(--accent-green); border-radius: 50%; margin-right: 6px;
    animation: pulseDot 1.6s ease-in-out infinite;
}
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════
# MATH
# ═══════════════════════════════════════════════════════

def hurst_rs(ts):
    """R/S vectorisé sur log returns — identique backtest_hurst.py."""
    ts = np.asarray(ts, dtype=float)
    n  = len(ts)
    if n < 20: return 0.5
    lags = np.unique(np.round(
        np.exp(np.linspace(np.log(4), np.log(min(n // 2, 50)), 12))
    ).astype(int))
    lags = lags[lags >= 4]
    rs_vals = []
    for lag in lags:
        lag = int(lag)
        n_chunks = n // lag
        if n_chunks < 2: continue
        mat  = ts[:n_chunks * lag].reshape(n_chunks, lag)
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


def compute_bands(closes):
    """Rolling mean + std bands — vectorisé pandas (identique backtest)."""
    s     = pd.Series(closes)
    m     = s.rolling(LOOKBACK).mean().values
    std   = s.rolling(LOOKBACK).std(ddof=0).values
    return m, m + BAND_K * std, m - BAND_K * std


def precompute_hurst_arr(closes):
    """Précalcule rolling Hurst sur log-returns — identique build_study_cache backtest.
    Appelé une fois par refresh, pas dans la boucle de signaux.
    """
    log_rets = np.diff(np.log(np.maximum(closes, 1e-9)))
    log_rets = np.concatenate([[0.0], log_rets])   # aligné sur closes
    n        = len(closes)
    hurst_arr = np.full(n, np.nan)
    for i in range(HURST_WIN, n):
        hurst_arr[i] = hurst_rs(log_rets[i - HURST_WIN: i])
    h_now = hurst_arr[-1] if not np.isnan(hurst_arr[-1]) else 0.5
    return hurst_arr, h_now


def find_signals(closes, times_str, hurst_arr):
    """Signaux MR — utilise hurst_arr précalculé (zéro recalcul dans la boucle)."""
    n    = len(closes)
    sigs = []
    mids, upper, lower = compute_bands(closes)

    stop_bar = max(0, n - SKIP_CLOSE_BARS)
    for i in range(max(LOOKBACK + SKIP_OPEN_BARS, HURST_WIN), stop_bar):
        h_bar = hurst_arr[i]
        if np.isnan(h_bar) or h_bar >= HURST_THRESHOLD:
            continue
        mid = mids[i]
        if np.isnan(mid):
            continue
        std   = (closes[i - LOOKBACK: i]).std()
        if std == 0:
            continue
        price = closes[i]
        z     = (price - mid) / std
        if abs(z) < BAND_K:
            continue
        direction = "SHORT" if z > 0 else "LONG"
        tp_price  = mid + TP_OVERSHOOT * (mid - price)
        sl_pts    = max(0.25, SL_MULT * std / 10)
        sigs.append({
            "bar_idx":    i,
            "time":       times_str[i],
            "direction":  direction,
            "price":      price,
            "fair_value": mid,
            "tp_price":   tp_price,
            "sl_pts_mnq": sl_pts,
            "z_score":    z,
            "std":        std,
            "hurst":      h_bar,
        })
        if len(sigs) >= MAX_TRADES_DAY:
            break
    return sigs


# ═══════════════════════════════════════════════════════
# DATA
# ═══════════════════════════════════════════════════════

DXFEED_STALE_SECONDS = 120  # si le fichier n'a pas été mis à jour depuis 2min → stale

def _fetch_dxfeed() -> tuple:
    """Lit C:/tmp/mnq_live.json écrit par dxfeed_bridge.js (Node.js)."""
    import json, os, time as _t
    if not os.path.exists(DXFEED_FILE):
        return None, "dxfeed_bridge.js non lancé"
    # Contrôle fraîcheur — si fichier pas modifié depuis 2min, bridge probablement mort
    age = _t.time() - os.path.getmtime(DXFEED_FILE)
    if age > DXFEED_STALE_SECONDS:
        return None, f"Bridge inactif — données figées depuis {int(age)}s (> {DXFEED_STALE_SECONDS}s)"
    try:
        with open(DXFEED_FILE, encoding="utf-8") as f:
            raw = f.read().strip()
        if not raw:
            return None, "dxfeed_bridge.js non lancé (fichier vide)"
        data = json.loads(raw)
        bars = data.get("bars", [])
        if len(bars) < 1:
            return None, "Pas assez de barres dxFeed"

        df = pd.DataFrame(bars)
        df["bar"] = pd.to_datetime(df["time"], utc=True).dt.tz_convert(PARIS)
        df["close"] = df["close"].astype(float)
        df["open"]  = df["open"].astype(float)
        df["high"]  = df["high"].astype(float)
        df["low"]   = df["low"].astype(float)

        today_ny = df["bar"].dt.date.max()
        df = df[df["bar"].dt.date == today_ny].copy()
        if len(df) < 1:
            return None, "Pas assez de barres aujourd'hui"

        df["time_str"] = [str(x)[:16] for x in df["bar"]]
        df.reset_index(drop=True, inplace=True)
        return df, None
    except Exception as e:
        return None, f"dxFeed lecture: {e}"


def _fetch_yfinance_history() -> pd.DataFrame | None:
    """Récupère les barres M1 yfinance du jour (historique session).
    Résultat mis en cache dans session_state pour ne pas rappeler yfinance toutes les 2s.
    """
    import time as _time
    cache = st.session_state.get("_yf_hist_cache", None)
    now_ts = _time.time()
    # Rafraîchit le cache yfinance toutes les 5 minutes max
    if cache is not None and now_ts - cache["ts"] < 300:
        return cache["df"]
    try:
        raw = yf.download(SYMBOL, period="2d", interval="1m",
                          progress=False, auto_adjust=True)
        if raw is None or len(raw) < 5:
            return None
        raw.index = pd.to_datetime(raw.index)
        if raw.index.tz is None:
            raw.index = raw.index.tz_localize("UTC")
        raw.index = raw.index.tz_convert(PARIS)
        t = raw.index.hour * 60 + raw.index.minute
        raw = raw[(t >= SESSION_START[0]*60 + SESSION_START[1]) &
                  (t <  SESSION_END[0]  *60 + SESSION_END[1])].copy()
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)
        raw["close"] = raw["Close"].astype(float)
        raw["open"]  = raw["Open"].astype(float)
        raw["high"]  = raw["High"].astype(float)
        raw["low"]   = raw["Low"].astype(float)
        raw["bar"]   = raw.index
        raw["time_str"] = [str(x)[:16] for x in raw.index]
        df_out = raw[["bar", "open", "high", "low", "close", "time_str"]].copy()
        st.session_state["_yf_hist_cache"] = {"df": df_out, "ts": now_ts}
        return df_out
    except Exception:
        return None


def fetch_session_data():
    # 1. dxFeed temps réel (bridge Node.js)
    df_dx, dxfeed_err = _fetch_dxfeed()

    if df_dx is not None:
        # Complète avec historique yfinance uniquement si pas encore assez de barres
        # pour calculer Hurst — ne fausse aucun calcul (barres réelles passées, même échelle NQ)
        if len(df_dx) < HURST_WIN + LOOKBACK:
            df_hist = _fetch_yfinance_history()
            if df_hist is not None and len(df_hist) > 0:
                first_dx_time = df_dx["bar"].iloc[0]
                df_hist = df_hist[df_hist["bar"] < first_dx_time].copy()
                if len(df_hist) > 0:
                    df_merged = pd.concat([df_hist, df_dx], ignore_index=True)
                    df_merged = df_merged.sort_values("bar").reset_index(drop=True)
                    n_hist = len(df_hist)
                    return df_merged, None, f"dxFeed ⚡ + {n_hist} barres hist."
        return df_dx, None, "dxFeed 4PropTrader ⚡"

    # 2. Bridge non lancé — pas de fallback silencieux, on affiche l'erreur clairement
    _dxfeed_fail_reason = dxfeed_err or "raison inconnue"
    return None, f"Bridge dxFeed inactif : {_dxfeed_fail_reason}", "dxFeed ✗"


# ═══════════════════════════════════════════════════════
# PAGE
# ═══════════════════════════════════════════════════════

now_ny = datetime.now(PARIS)

# ── Sidebar ──────────────────────────────────────────
with st.sidebar:
    st.markdown(f"""
    <div style="padding:.4rem 0 .8rem">
        <div style="font-family:'JetBrains Mono',monospace;font-size:.58rem;
                    letter-spacing:.2em;color:var(--accent-cyan);text-transform:uppercase">
            Live Signal
        </div>
        <div style="font-size:1.25rem;font-weight:700;color:var(--text-primary);margin:.2rem 0;
                    background:var(--grad-primary);-webkit-background-clip:text;
                    -webkit-text-fill-color:transparent;background-clip:text">
            Hurst_MR
        </div>
        <div style="font-size:.72rem;color:var(--text-muted)">{now_ny.strftime('%A %d %b %Y')}</div>
        <div style="font-size:.82rem;color:var(--text-secondary);
                    font-family:'JetBrains Mono',monospace;margin-top:.3rem;
                    display:flex;align-items:center;gap:4px">
            <span class="qm-live-dot qm-live-dot--green" style="width:6px;height:6px"></span>
            {now_ny.strftime('%H:%M:%S')} Paris
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.divider()
    st.markdown(f"""
    <div style="font-family:'JetBrains Mono',monospace;font-size:.72rem;line-height:2.1;
                color:var(--text-muted)">
        <span style="color:var(--accent-cyan)">H seuil</span>&nbsp;&nbsp;&nbsp;{HURST_THRESHOLD}<br>
        <span style="color:var(--accent-cyan)">Band K</span>&nbsp;&nbsp;&nbsp;±{BAND_K}σ<br>
        <span style="color:var(--accent-cyan)">Lookback</span>&nbsp;{LOOKBACK} barres<br>
        <span style="color:var(--accent-cyan)">SL</span>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{SL_MULT}×std<br>
        <span style="color:var(--accent-cyan)">TP</span>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Fair Value pure<br>
        <span style="color:var(--accent-cyan)">Skip open</span> {SKIP_OPEN_BARS} barres<br>
        <span style="color:var(--accent-cyan)">Skip close</span> {SKIP_CLOSE_BARS} barres<br>
        <span style="color:var(--accent-red)">Max trades</span> {MAX_TRADES_DAY}/jour<br>
        <span style="color:var(--accent-red)">Daily limit</span> {DAILY_LOSS_LIM:.0f}$
    </div>
    """, unsafe_allow_html=True)
    st.divider()
    st.markdown("""
    <div style="font-family:'JetBrains Mono',monospace;font-size:.65rem;
                color:var(--text-muted);line-height:1.9">
        <span style="color:var(--accent-green)">PF=2.03</span> · Sharpe=2.50<br>
        MaxDD=5.5% · WR=29.4%<br>
        1095 trades · 5 ans WF ✓
    </div>
    """, unsafe_allow_html=True)

# ── Header ───────────────────────────────────────────
in_session = (
    (now_ny.hour * 60 + now_ny.minute) >= SESSION_START[0]*60 + SESSION_START[1] and
    (now_ny.hour * 60 + now_ny.minute) <  SESSION_END[0]  *60 + SESSION_END[1]
)
sess_col = "#00ff88" if in_session else "#ff3366"
sess_txt = "SESSION ACTIVE" if in_session else "HORS SESSION"
st.markdown(f"""
<div style="display:flex;align-items:center;justify-content:space-between;
            padding:.5rem 0 1rem;border-bottom:1px solid var(--border-subtle);
            margin-bottom:1rem" class="anim-fade-up">
    <div>
        <div style="font-family:'JetBrains Mono',monospace;font-size:.6rem;
                    letter-spacing:.2em;color:var(--accent-cyan);text-transform:uppercase">
            MNQ · 4PROPTRADER · HURST_MR
        </div>
        <div style="font-size:1.55rem;font-weight:700;color:var(--text-primary);
                    letter-spacing:-.02em;margin-top:.15rem">
            Live Signal
            <span style="background:var(--grad-primary);-webkit-background-clip:text;
                         -webkit-text-fill-color:transparent;background-clip:text">Hurst_MR</span>
        </div>
    </div>
    <div style="display:flex;align-items:center;gap:.6rem">
        <span class="qm-badge {'qm-badge--green' if in_session else 'qm-badge--red'}">
            <span class="qm-live-dot {'qm-live-dot--green' if in_session else 'qm-live-dot--red'}"
                  style="width:6px;height:6px;margin:0"></span>
            &nbsp;{sess_txt}
        </span>
    </div>
</div>
""", unsafe_allow_html=True)

# ── Fetch data ────────────────────────────────────────
with st.spinner("Chargement données..."):
    df, err, data_source = fetch_session_data()

# Badge source données
src_color = TEAL if "dxFeed" in data_source else YELLOW
st.markdown(
    f'<div style="font-size:.75rem;color:{src_color};margin-bottom:.3rem">📡 Source : {data_source}</div>'
    + _refresh_bar(duration_s=2.0),
    unsafe_allow_html=True,
)

if err or df is None:
    st.error(f"🔴 {err or 'Bridge dxFeed inactif'}")
    st.info("▶ Lance le bridge : `cd QUANT MATHS` → `node dxfeed_bridge.js` → attends '✓ Ticks reçus'")
    if not in_session:
        st.info("Session NY fermée (9:30-16:00 NY = 15:30-22:00 Paris).")
    st.stop()  # autorefresh gère le retry toutes les 2s

closes    = df["close"].values.flatten()
opens_arr = df["open"].values.flatten()
highs_arr = df["high"].values.flatten()
lows_arr  = df["low"].values.flatten()
times_str = df["time_str"].tolist()
# Volume (dxFeed ou yfinance)
if "volume" in df.columns:
    volumes = df["volume"].values.astype(float)
elif "Volume" in df.columns:
    volumes = df["Volume"].values.astype(float)
else:
    volumes = np.zeros(len(closes))
hurst_arr, h_val = precompute_hurst_arr(closes)   # O(n) — précalculé une fois
signals          = find_signals(closes, times_str, hurst_arr)
mids, upper_band, lower_band = compute_bands(closes)
price_now = float(closes[-1])
bars_count = len(closes)

# ── Limites journalières — lues depuis journal ────────
_today_str   = now_ny.strftime("%Y-%m-%d")
_j_today     = journal_load()
_j_today     = _j_today[_j_today["date"] == _today_str] if not _j_today.empty else _j_today
_trades_today = len(_j_today)
_pnl_today    = float(_j_today["pnl"].sum()) if not _j_today.empty else 0.0
_daily_blocked = (_trades_today >= MAX_TRADES_DAY) or (_pnl_today <= -DAILY_LOSS_LIM)

last_signal = signals[-1] if signals else None

# ── Âge du dernier signal ─────────────────────────────
_sig_age_min  = 0.0
_sig_expired  = False
if last_signal:
    try:
        _sig_dt      = PARIS.localize(datetime.strptime(last_signal["time"][:16], "%Y-%m-%d %H:%M"))
        _sig_age_min = (now_ny - _sig_dt).total_seconds() / 60
        _sig_expired = _sig_age_min > SIGNAL_MAX_AGE_MIN
    except Exception:
        pass

# ── Alerte Discord — envoi en thread pour ne pas bloquer ───
def _discord_write_status(ok: bool, err: str = ""):
    try:
        with open(DISCORD_STATUS_FILE, "w") as f:
            json.dump({"ok": ok, "err": err}, f)
    except Exception:
        pass

def _discord_read_status():
    try:
        with open(DISCORD_STATUS_FILE) as f:
            return json.load(f)
    except Exception:
        return {"ok": None, "err": ""}

def _build_discord_payload(sig):
    d        = sig["direction"]
    entry    = sig["price"] / 10
    tp       = sig["tp_price"] / 10
    fv       = sig.get("fair_value", sig["price"]) / 10
    sl_pts   = sig["sl_pts_mnq"]
    sl_price = entry - sl_pts if d == "LONG" else entry + sl_pts
    z        = sig["z_score"]
    h        = sig["hurst"]
    t        = sig["time"][11:16]
    pts_tp   = abs(tp - entry)
    rr       = pts_tp / sl_pts if sl_pts > 0 else 0

    # Couleur Discord : vert pour LONG, rouge pour SHORT
    color    = 0x00FF88 if d == "LONG" else 0xFF3366
    arrow    = "↑" if d == "LONG" else "↓"

    return {
        "embeds": [{
            "title":       f"{'🟢' if d == 'LONG' else '🔴'}  {d} MNQ  {arrow}",
            "description": f"**Hurst_MR** · Session NY · `{t} Paris`",
            "color":       color,
            "fields": [
                {"name": "📍 Entrée",  "value": f"`{entry:.2f}`",              "inline": True},
                {"name": "🎯 TP",     "value": f"`{tp:.2f}` (+{pts_tp:.2f} pts)", "inline": True},
                {"name": "🛑 SL",     "value": f"`{sl_price:.2f}` (−{sl_pts:.2f} pts)", "inline": True},
                {"name": "📊 Hurst H","value": f"`{h:.3f}`",                   "inline": True},
                {"name": "📈 Z-score","value": f"`{z:+.2f}σ`",                 "inline": True},
                {"name": "⚖️ R:R",   "value": f"`{rr:.1f}`",                  "inline": True},
            ],
            "footer":    {"text": "Hurst_MR · MNQ · 4PropTrader $50K"},
            "timestamp": sig["time"].replace(" ", "T") + "Z" if "T" not in sig["time"] else sig["time"] + "Z",
            "url":       "https://quant-zoukria.streamlit.app/3_Live_Signal",
        }]
    }

def _send_discord(sig):
    try:
        data = json.dumps(_build_discord_payload(sig)).encode("utf-8")
        req  = urllib.request.Request(
            DISCORD_WEBHOOK, data=data,
            headers={"Content-Type": "application/json",
                     "User-Agent": "QuantMaster/1.0"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
        _discord_write_status(True)
    except Exception as e:
        _discord_write_status(False, str(e)[:80])

def _send_discord_async(sig):
    threading.Thread(target=_send_discord, args=(sig,), daemon=True).start()

# ── Alerte ntfy ─────────────────────────────────────────────────────────────
def _send_ntfy(sig):
    try:
        d     = sig["direction"]
        entry = sig["price"] / 10
        tp    = sig.get("tp_price", sig["price"]) / 10
        sl    = sig.get("sl_pts_mnq", 0)
        z     = sig.get("z_score", 0)
        h     = sig.get("hurst", 0)
        t     = sig.get("time", "")[:16]
        pts_tp = abs(tp - entry)
        rr     = pts_tp / sl if sl > 0 else 0

        # Corps du message : compact et lisible sur mobile
        msg   = (
            f"Entrée  : {entry:,.2f}\n"
            f"TP      : {tp:,.2f}  (+{pts_tp:.2f} pts)\n"
            f"SL      : {sl:.2f} pts  ·  R:R {rr:.1f}\n"
            f"H={h:.3f}  ·  Z={z:+.2f}σ  ·  {t[:5]} Paris"
        )
        title_emoji = "📈" if d == "LONG" else "📉"
        tags        = "chart_with_upwards_trend,white_check_mark" if d == "LONG" \
                      else "chart_with_downwards_trend,red_circle"

        req = urllib.request.Request(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=msg.encode("utf-8"),
            method="POST",
            headers={
                "X-Title":    f"{title_emoji} SIGNAL {d} MNQ @ {entry:.2f}",
                "X-Tags":     tags,
                "X-Priority": "high",
                "X-Click":    "https://quant-zoukria.streamlit.app/3_Live_Signal",
                "X-Actions":  "view, Dashboard, https://quant-zoukria.streamlit.app/3_Live_Signal",
            }
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass

def _send_ntfy_async(sig):
    threading.Thread(target=_send_ntfy, args=(sig,), daemon=True).start()

# ── Alerte sonore — ne sonne qu'une fois par signal ───
def _play_signal_sound(direction: str):
    """Joue un son via Web Audio API dans le navigateur."""
    freq1 = 880 if direction == "LONG" else 440
    freq2 = 1100 if direction == "LONG" else 330
    import streamlit.components.v1 as _comp
    _comp.html(f"""
    <script>
    (function() {{
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        function beep(freq, start, dur) {{
            const osc  = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.connect(gain); gain.connect(ctx.destination);
            osc.type = 'sine';
            osc.frequency.setValueAtTime(freq, ctx.currentTime + start);
            gain.gain.setValueAtTime(0.35, ctx.currentTime + start);
            gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + start + dur);
            osc.start(ctx.currentTime + start);
            osc.stop(ctx.currentTime + start + dur + 0.05);
        }}
        beep({freq1}, 0.0, 0.25);
        beep({freq2}, 0.3, 0.20);
        beep({freq1}, 0.6, 0.35);
    }})();
    </script>
    """, height=0)

# Initialise session_state pour tracking signal
if "last_announced_sig" not in st.session_state:
    st.session_state.last_announced_sig = None

if last_signal and not _daily_blocked:
    sig_id = f"{last_signal['time']}_{last_signal['direction']}"
    if sig_id != st.session_state.last_announced_sig:
        st.session_state.last_announced_sig = sig_id
        _play_signal_sound(last_signal["direction"])
        _send_discord_async(last_signal)
        _send_ntfy_async(last_signal)

# ── Z-score actuel ────────────────────────────────────
if len(closes) >= LOOKBACK:
    w_now   = closes[-LOOKBACK:]
    z_now   = (closes[-1] - w_now.mean()) / (w_now.std() if w_now.std() > 0 else 1)
else:
    z_now = 0.0

z_pct    = min(100, abs(z_now) / BAND_K * 100)
z_col    = (RED if z_now > BAND_K else GREEN if z_now < -BAND_K else TEAL)
z_dir_lbl = "SHORT ZONE" if z_now > BAND_K else ("LONG ZONE" if z_now < -BAND_K else f"{abs(z_now):.2f}σ / {BAND_K}σ")

# ── Banner daily limit ───────────────────────────────
if _daily_blocked:
    if _pnl_today <= -DAILY_LOSS_LIM:
        st.markdown(f"""
        <div style="background:#1a0407;border:2px solid #ff3366;border-radius:10px;
                    padding:.8rem 1.2rem;margin-bottom:.8rem;
                    font-family:'JetBrains Mono',monospace;font-size:.85rem;color:#ff3366">
            🛑 <b>DAILY LIMIT ATTEINTE</b> — P&L jour : {_pnl_today:+.0f}$ / -{DAILY_LOSS_LIM:.0f}$<br>
            <span style="color:#555;font-size:.75rem">Stop trading pour aujourd'hui. Aucun nouveau signal ne sera activé.</span>
        </div>""", unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style="background:#0d1a04;border:2px solid #ffd600;border-radius:10px;
                    padding:.8rem 1.2rem;margin-bottom:.8rem;
                    font-family:'JetBrains Mono',monospace;font-size:.85rem;color:#ffd600">
            ⚠️ <b>MAX TRADES ATTEINT</b> — {_trades_today}/{MAX_TRADES_DAY} trades aujourd'hui<br>
            <span style="color:#555;font-size:.75rem">Limite journalière atteinte. Session terminée.</span>
        </div>""", unsafe_allow_html=True)

# ── Daily Limit Tracker ───────────────────────────────
_loss_used   = max(0.0, -_pnl_today)                          # perte nette du jour (≥0)
_loss_pct    = min(100.0, _loss_used / DAILY_LOSS_LIM * 100)  # % de la limite utilisé
_gain_today  = max(0.0, _pnl_today)                           # gain net du jour
_trades_left = max(0, MAX_TRADES_DAY - _trades_today)

# Couleur de la barre de perte
if _loss_pct >= 100:
    _bar_clr = "#ef4444"   # rouge — limite atteinte
elif _loss_pct >= 80:
    _bar_clr = "#f97316"   # orange — danger
elif _loss_pct >= 50:
    _bar_clr = "#f59e0b"   # amber — attention
else:
    _bar_clr = "#10b981"   # vert — safe

# Couleur P&L texte
_pnl_clr = "#ef4444" if _pnl_today < 0 else ("#10b981" if _pnl_today > 0 else "#94a3b8")

# Status global
if _daily_blocked:
    _status_cls, _status_txt = "qm-badge--red",   "STOP"
elif _loss_pct >= 80:
    _status_cls, _status_txt = "qm-badge--amber",  "ATTENTION"
elif _loss_pct >= 50:
    _status_cls, _status_txt = "qm-badge--amber",  "SURVEILLER"
else:
    _status_cls, _status_txt = "qm-badge--green",  "SAFE"

# Dots trades (● = utilisé, ○ = dispo)
_dots = "".join(
    f'<span style="color:#ef4444;font-size:.75rem">●</span>' if i < _trades_today
    else f'<span style="color:#334155;font-size:.75rem">○</span>'
    for i in range(MAX_TRADES_DAY)
)

st.markdown(f"""
<div style="background:var(--bg-surface);border:1px solid var(--border-default);
            border-radius:var(--r-lg);padding:.9rem 1.3rem;margin-bottom:.9rem;
            display:grid;grid-template-columns:1fr auto 1fr;gap:1.5rem;align-items:center">
    <div>
        <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:.4rem">
            <span style="font-family:'JetBrains Mono',monospace;font-size:.6rem;
                         font-weight:700;letter-spacing:.14em;color:var(--text-muted);
                         text-transform:uppercase">Limite journalière</span>
            <span style="font-family:'JetBrains Mono',monospace;font-size:.78rem;font-weight:700;
                         color:{_pnl_clr}">{_pnl_today:+.0f}$</span>
        </div>
        <div style="background:var(--bg-elevated);border-radius:var(--r-pill);height:6px;overflow:hidden">
            <div style="width:{_loss_pct:.1f}%;height:100%;background:{_bar_clr};
                        border-radius:var(--r-pill);
                        transition:width .5s cubic-bezier(.16,1,.3,1)"></div>
        </div>
        <div style="display:flex;justify-content:space-between;margin-top:.3rem">
            <span style="font-size:.7rem;color:{_bar_clr}">{_loss_pct:.0f}% utilisé</span>
            <span style="font-size:.7rem;color:var(--text-muted)">max −{DAILY_LOSS_LIM:.0f}$</span>
        </div>
    </div>
    <div style="text-align:center">
        <span class="qm-badge {_status_cls}" style="font-size:.75rem;padding:.3rem .8rem">{_status_txt}</span>
        <div style="font-size:.62rem;color:var(--text-muted);margin-top:.4rem;opacity:{1 if _gain_today > 0 else 0}">{f'+{_gain_today:.0f}$' if _gain_today > 0 else '—'} gain</div>
    </div>
    <div style="text-align:right">
        <div style="display:flex;justify-content:flex-end;align-items:baseline;gap:.5rem;margin-bottom:.4rem">
            <span style="font-family:'JetBrains Mono',monospace;font-size:.6rem;
                         font-weight:700;letter-spacing:.14em;color:var(--text-muted);
                         text-transform:uppercase">Trades</span>
            <span style="font-family:'JetBrains Mono',monospace;font-size:.78rem;font-weight:700;
                         color:{'#ef4444' if _trades_today >= MAX_TRADES_DAY else 'var(--text-primary)'}">
                {_trades_today}<span style="color:var(--text-muted);font-size:.7rem">/{MAX_TRADES_DAY}</span>
            </span>
        </div>
        <div style="letter-spacing:4px">{_dots}</div>
        <div style="font-size:.7rem;color:var(--text-muted);margin-top:.3rem">
            {_trades_left} restant{'s' if _trades_left != 1 else ''}
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# ── KPI Cards ─────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)

h_color = GREEN if h_val < HURST_THRESHOLD else RED
h_label = "MR ✓" if h_val < HURST_THRESHOLD else "Trending ✗"
with c1:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-value" style="color:{h_color}">{h_val:.3f}</div>
        <div class="kpi-label">Hurst H — {h_label}</div>
        <div class="gauge-track">
            <div class="gauge-fill" style="width:{max(0,100-int(h_val*100))}%;
                 background:{'#00ff88' if h_val < HURST_THRESHOLD else '#ff3366'}"></div>
        </div>
    </div>""", unsafe_allow_html=True)

with c2:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-value" style="color:{z_col}">{z_now:+.2f}σ</div>
        <div class="kpi-label">Z-score — {z_dir_lbl}</div>
        <div class="gauge-track">
            <div class="gauge-fill" style="width:{z_pct:.0f}%;background:{z_col}"></div>
        </div>
    </div>""", unsafe_allow_html=True)

mnq_price = price_now / 10
with c3:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-value" style="color:{YELLOW}">{mnq_price:,.1f}</div>
        <div class="kpi-label">MNQ · NQ {price_now:,.0f}</div>
    </div>""", unsafe_allow_html=True)

n_sigs  = len(signals)   # détections algo — pour le chart uniquement
n_taken = _trades_today  # trades réellement pris — pour le compteur KPI
sig_col = RED if _daily_blocked else (GREEN if n_taken > 0 else "#333")
sig_lbl = "🛑 STOP" if _daily_blocked else f"{n_taken}/{MAX_TRADES_DAY} trades pris"
with c4:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-value" style="color:{sig_col}">{n_taken}/{MAX_TRADES_DAY}</div>
        <div class="kpi-label">{sig_lbl}</div>
    </div>""", unsafe_allow_html=True)

bars_rdy = bars_count >= HURST_WIN + LOOKBACK
bars_col = GREEN if bars_rdy else YELLOW
with c5:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-value" style="color:{bars_col}">{bars_count}</div>
        <div class="kpi-label">Barres M1 {'✓' if bars_rdy else f'— min {HURST_WIN+LOOKBACK}'}</div>
    </div>""", unsafe_allow_html=True)

st.markdown("<div style='margin-top:.6rem'></div>", unsafe_allow_html=True)

# ── Niveaux Band K + Fair Value ───────────────────────
fv_now    = float(mids[-1])       / 10 if len(mids) and not np.isnan(mids[-1])       else None
upper_now = float(upper_band[-1]) / 10 if len(upper_band) and not np.isnan(upper_band[-1]) else None
lower_now = float(lower_band[-1]) / 10 if len(lower_band) and not np.isnan(lower_band[-1]) else None

bk1, bk2, bk3 = st.columns(3)
with bk1:
    val = f"{upper_now:,.2f}" if upper_now else "—"
    dist = f"  +{upper_now - mnq_price:+.1f} pts" if upper_now else ""
    st.markdown(f"""
    <div class="kpi-card" style="border-left:2px solid {RED}">
        <div class="kpi-value" style="color:{RED};font-size:1.1rem">{val}</div>
        <div class="kpi-label">Band K+ ({BAND_K}σ){dist}</div>
    </div>""", unsafe_allow_html=True)
with bk2:
    val = f"{fv_now:,.2f}" if fv_now else "—"
    dist = f"  {mnq_price - fv_now:+.1f} pts" if fv_now else ""
    st.markdown(f"""
    <div class="kpi-card" style="border-left:2px solid {TEAL}">
        <div class="kpi-value" style="color:{TEAL};font-size:1.1rem">{val}</div>
        <div class="kpi-label">Fair Value (mean 30){dist}</div>
    </div>""", unsafe_allow_html=True)
with bk3:
    val = f"{lower_now:,.2f}" if lower_now else "—"
    dist = f"  {lower_now - mnq_price:+.1f} pts" if lower_now else ""
    st.markdown(f"""
    <div class="kpi-card" style="border-left:2px solid {GREEN}">
        <div class="kpi-value" style="color:{GREEN};font-size:1.1rem">{val}</div>
        <div class="kpi-label">Band K− ({BAND_K}σ){dist}</div>
    </div>""", unsafe_allow_html=True)

st.markdown("<div style='margin-top:.4rem'></div>", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════
# MAIN LAYOUT : Chart (65%) | Panel (35%)
# ═══════════════════════════════════════════════════════
col_chart, col_panel = st.columns([0.63, 0.37], gap="small")
_chart_error = None  # capturé si le rendu plante — signal/Discord déjà partis avant

try:
    # Z-score rolling vectorisé — pandas rolling O(n)
    _s       = pd.Series(closes)
    _rm      = _s.rolling(LOOKBACK).mean()
    _rstd    = _s.rolling(LOOKBACK).std(ddof=0)
    z_rolling = np.where(_rstd > 0, (_s - _rm) / _rstd, np.nan)

    # ── Fenêtre d'affichage : 60 dernières barres seulement ─
    DISPLAY_BARS = 60
    d_start   = max(0, len(closes) - DISPLAY_BARS)
    d_closes  = closes[d_start:]
    d_opens   = opens_arr[d_start:]
    d_highs   = highs_arr[d_start:]
    d_lows    = lows_arr[d_start:]
    d_times   = times_str[d_start:]
    d_mids    = mids[d_start:]
    d_upper   = upper_band[d_start:]
    d_lower   = lower_band[d_start:]
    d_vols    = volumes[d_start:]
    d_z       = z_rolling[d_start:]

    x_idx     = list(range(len(d_closes)))
    tick_step = max(1, len(d_closes) // 8)
    tick_vals = x_idx[::tick_step]
    tick_text = [d_times[i][11:16] for i in tick_vals]

    # Couleurs volume (vert si hausse, rouge si baisse) — sur fenêtre display
    vol_colors = [
        "#00cc6a" if d_closes[i] >= d_opens[i] else "#cc2244"
        for i in range(len(d_closes))
    ]

    # ── Subplot 3 lignes : Candlestick / Volume / Z-score ──
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        row_heights=[0.60, 0.18, 0.22],
        vertical_spacing=0.02,
        subplot_titles=["", "", ""],
    )

    # ─── ROW 1 : Candlestick + bandes ─────────────────────

    # Fond zones signal (offset bar_idx par d_start)
    for sig in signals:
        di = sig["bar_idx"] - d_start
        if di < 0: continue
        clr = "rgba(0,255,136,0.05)" if sig["direction"] == "LONG" else "rgba(255,51,102,0.05)"
        fig.add_vrect(x0=di-0.5, x1=min(di+6, len(d_closes)-1),
                      fillcolor=clr, layer="below", line_width=0, row=1, col=1)

    # Bande +Kσ
    fig.add_trace(go.Scatter(
        x=x_idx, y=d_upper, name=f"+{BAND_K}σ",
        line=dict(color="rgba(255,51,102,0.45)", dash="dot", width=1),
        showlegend=True,
        hovertemplate=f"+{BAND_K}σ: %{{y:,.0f}}<extra></extra>",
    ), row=1, col=1)

    # Bande -Kσ + fill
    fig.add_trace(go.Scatter(
        x=x_idx, y=d_lower, name=f"−{BAND_K}σ",
        line=dict(color="rgba(0,255,136,0.45)", dash="dot", width=1),
        fill="tonexty", fillcolor="rgba(60,196,183,0.03)",
        showlegend=True,
        hovertemplate=f"−{BAND_K}σ: %{{y:,.0f}}<extra></extra>",
    ), row=1, col=1)

    # Fair Value
    fig.add_trace(go.Scatter(
        x=x_idx, y=d_mids, name="Fair Value",
        line=dict(color=TEAL, width=1.5, dash="dash"),
        hovertemplate="FV: %{y:,.0f}<extra></extra>",
    ), row=1, col=1)

    # Candlestick
    fig.add_trace(go.Candlestick(
        x=x_idx,
        open=d_opens, high=d_highs, low=d_lows, close=d_closes,
        name="MNQ M1",
        increasing=dict(line=dict(color="#00cc6a", width=1), fillcolor="#00cc6a"),
        decreasing=dict(line=dict(color="#cc2244", width=1), fillcolor="#cc2244"),
    ), row=1, col=1)

    # Signal markers (offset)
    for sig in signals:
        di = sig["bar_idx"] - d_start
        if di < 0: continue
        d   = sig["direction"]
        col = GREEN if d == "LONG" else RED
        sym = "triangle-up" if d == "LONG" else "triangle-down"
        ypos = sig["price"] * (0.9993 if d == "LONG" else 1.0007)
        fig.add_trace(go.Scatter(
            x=[di], y=[ypos],
            mode="markers+text",
            marker=dict(symbol=sym, size=16, color=col, line=dict(color="white", width=1)),
            text=[d], textposition="bottom center" if d == "LONG" else "top center",
            textfont=dict(color=col, size=9, family="JetBrains Mono"),
            showlegend=False, name=d,
        ), row=1, col=1)

    # TP / SL lignes horizontales (row 1 uniquement)
    n_disp = len(d_closes)
    if last_signal:
        tp_nq = last_signal["tp_price"]
        sl_nq = last_signal["price"] - last_signal["sl_pts_mnq"] * 10 * (
            1 if last_signal["direction"] == "LONG" else -1)
        for y_val, clr, lbl in [
            (tp_nq, TEAL, f"TP {tp_nq/10:.2f}"),
            (sl_nq, RED,  f"SL {sl_nq/10:.2f}"),
        ]:
            fig.add_shape(type="line", x0=0, x1=n_disp-1, y0=y_val, y1=y_val,
                          line=dict(color=clr, dash="dash", width=1), row=1, col=1)
            fig.add_annotation(x=n_disp-1, y=y_val, text=f" {lbl}",
                               showarrow=False, font=dict(color=clr, size=9, family="JetBrains Mono"),
                               xanchor="left", row=1, col=1)

    # Prix actuel
    fig.add_annotation(
        x=n_disp-1, y=price_now,
        text=f" ◄ {mnq_price:.1f}",
        showarrow=False, font=dict(color=YELLOW, size=11, family="JetBrains Mono"),
        xanchor="left", row=1, col=1,
    )

    # ─── ROW 2 : Volume ───────────────────────────────────
    fig.add_trace(go.Bar(
        x=x_idx, y=d_vols,
        marker_color=vol_colors,
        marker_line_width=0,
        name="Volume",
        showlegend=False,
        hovertemplate="Vol: %{y}<extra></extra>",
    ), row=2, col=1)

    # ─── ROW 3 : Z-score rolling ──────────────────────────
    # Zone signal colorée
    fig.add_hrect(y0=BAND_K, y1=BAND_K*1.5, fillcolor="rgba(255,51,102,0.06)",
                  line_width=0, row=3, col=1)
    fig.add_hrect(y0=-BAND_K*1.5, y1=-BAND_K, fillcolor="rgba(0,255,136,0.06)",
                  line_width=0, row=3, col=1)

    # Seuils ±Kσ
    fig.add_hline(y=BAND_K,  line=dict(color="rgba(255,51,102,0.6)", dash="dot", width=1),
                  annotation_text=f"+{BAND_K}σ",
                  annotation_font=dict(color=RED, size=9), row=3, col=1)
    fig.add_hline(y=-BAND_K, line=dict(color="rgba(0,255,136,0.6)", dash="dot", width=1),
                  annotation_text=f"−{BAND_K}σ",
                  annotation_font=dict(color=GREEN, size=9), row=3, col=1)
    fig.add_hline(y=0, line=dict(color="#1a1a1a", width=1), row=3, col=1)

    # Z-score line colorée selon zone
    z_clr_line = RED if z_now > BAND_K else (GREEN if z_now < -BAND_K else TEAL)
    fig.add_trace(go.Scatter(
        x=x_idx, y=d_z,
        name="Z-score",
        line=dict(color=z_clr_line, width=1.5),
        fill="tozeroy", fillcolor=f"rgba({','.join(str(int(z_clr_line.lstrip('#')[i:i+2],16)) for i in (0,2,4))},0.08)",
        hovertemplate="Z: %{y:.2f}σ<extra></extra>",
        showlegend=True,
    ), row=3, col=1)

    # ─── Layout global ────────────────────────────────────
    fig.update_layout(
        **DARK,
        title=dict(
            text=f"MNQ M1 · {now_ny.strftime('%d %b %Y')} · H={h_val:.3f} · Z={z_now:+.2f}σ",
            font=dict(color="#555", size=11, family="JetBrains Mono"),
        ),
        height=620,
        showlegend=True,
        hovermode="x unified",
        xaxis=dict(showticklabels=False, gridcolor="#0f0f0f", rangeslider=dict(visible=False)),
        xaxis2=dict(showticklabels=False, gridcolor="#0f0f0f"),
        xaxis3=dict(tickvals=tick_vals, ticktext=tick_text, gridcolor="#0f0f0f"),
        yaxis=dict(gridcolor="#0f0f0f", tickformat=",.0f", side="right"),
        yaxis2=dict(gridcolor="#0f0f0f", side="right", showticklabels=False, title="Vol"),
        yaxis3=dict(gridcolor="#0f0f0f", side="right", zeroline=False,
                    range=[-BAND_K*1.6, BAND_K*1.6]),
    )
    fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1,
                                  font=dict(size=10), bgcolor="rgba(0,0,0,0)"))
    with col_chart:
        st.plotly_chart(fig, use_container_width=True)
except Exception as _e:
    with col_chart:
        st.error(f"⚠️ Chart error: {_e}")

# ── Panel droit : Signal + Status ─────────────────────
try:
    with col_panel:
        # Signal card
        st.markdown('<div class="sec-label">Signal actif</div>', unsafe_allow_html=True)
        if last_signal:
            d         = last_signal["direction"]
            col       = GREEN if d == "LONG" else RED
            cls       = "sig-long" if d == "LONG" else "sig-short"
            icon      = "▲" if d == "LONG" else "▼"
            tp_mnq     = last_signal["tp_price"] / 10
            sl_mnq     = last_signal["sl_pts_mnq"]
            entry_mnq  = last_signal["price"] / 10
            fv_mnq     = last_signal["fair_value"] / 10
            sl_price   = entry_mnq - sl_mnq if d == "LONG" else entry_mnq + sl_mnq
            rr         = abs(tp_mnq - entry_mnq) / sl_mnq if sl_mnq > 0 else 0
            # Flash class for brand-new signals (< 30s)
            _flash_cls = " qm-signal-new" if _sig_age_min < 0.5 else ""
            # statut Discord (lu depuis fichier — persiste entre reruns)
            ds = _discord_read_status()
            if ds["ok"] is True:
                disc_lbl = '<span style="color:#3CC4B7">Discord ✓</span>'
            elif ds["ok"] is False:
                disc_lbl = f'<span style="color:#ff3366">Discord ✗ {ds["err"]}</span>'
            else:
                disc_lbl = '<span style="color:#333">Discord —</span>'
            st.markdown(f"""
            <div class="{cls}{_flash_cls}">
                <div style="font-size:1.8rem;font-weight:700;color:{col};
                            font-family:'JetBrains Mono',monospace">{icon} {d}</div>
                <div style="font-size:.6rem;color:{col};font-family:'JetBrains Mono',monospace;
                            letter-spacing:.15em;margin:-.1rem 0 .4rem">
                    {last_signal["time"][11:16]} · Z={last_signal["z_score"]:+.2f}σ
                    {"&nbsp;&nbsp;<span style='color:#ff9100;background:rgba(255,145,0,0.12);padding:1px 6px;border-radius:4px;font-size:.58rem'>⏱ EXPIRÉ " + f"{int(_sig_age_min)}min" + "</span>" if _sig_expired else ""}
                </div>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;
                            font-family:'JetBrains Mono',monospace">
                    <div style="background:rgba(0,0,0,.3);border-radius:7px;padding:.5rem .7rem">
                        <div style="font-size:.55rem;color:#444;margin-bottom:.15rem">ENTRÉE</div>
                        <div style="color:#fff;font-weight:700;font-size:.85rem">{entry_mnq:.2f}</div>
                    </div>
                    <div style="background:rgba(0,0,0,.3);border-radius:7px;padding:.5rem .7rem">
                        <div style="font-size:.55rem;color:#444;margin-bottom:.15rem">TP</div>
                        <div style="color:{TEAL};font-weight:700;font-size:.85rem">{tp_mnq:.2f}</div>
                    </div>
                    <div style="background:rgba(0,0,0,.3);border-radius:7px;padding:.5rem .7rem">
                        <div style="font-size:.55rem;color:{RED};margin-bottom:.15rem">SL PRIX</div>
                        <div style="color:{RED};font-weight:700;font-size:.85rem">{sl_price:.2f}</div>
                        <div style="font-size:.6rem;color:#444;margin-top:.1rem">-{sl_mnq:.2f} pts</div>
                    </div>
                    <div style="background:rgba(0,0,0,.3);border-radius:7px;padding:.5rem .7rem">
                        <div style="font-size:.55rem;color:#444;margin-bottom:.15rem">R:R · FV</div>
                        <div style="font-size:.85rem;font-weight:700;color:#fff">{rr:.1f}R</div>
                        <div style="font-size:.6rem;color:{TEAL};margin-top:.1rem">FV {fv_mnq:.2f}</div>
                    </div>
                </div>
                <div style="margin-top:.6rem;font-family:'JetBrains Mono',monospace;
                            font-size:.65rem;color:#333;display:flex;justify-content:space-between">
                    <span>H={last_signal["hurst"]:.3f} · {HURST_WIN} bars</span>
                    <span style="font-size:.6rem">{disc_lbl}</span>
                </div>
            </div>""", unsafe_allow_html=True)
        else:
            if h_val < HURST_THRESHOLD:
                _es_icon, _es_title = "◎", "Attente signal MR"
                _es_sub = f"H={h_val:.3f} < {HURST_THRESHOLD} — systeme actif, attente Z ≥ ±{BAND_K}σ"
            else:
                _es_icon, _es_title = "📈", "Regime trending — no trade"
                _es_sub = f"H={h_val:.3f} ≥ {HURST_THRESHOLD} — systeme inactif"
            from styles import empty_state as _es
            st.markdown(_es(_es_icon, _es_title, _es_sub), unsafe_allow_html=True)

        # Bouton test Discord
        if st.button("🔔 Test Discord", use_container_width=True):
            test_sig = last_signal if last_signal else {
                "direction": "LONG", "price": 250000, "tp_price": 251000,
                "sl_pts_mnq": 1.5, "z_score": -3.1, "hurst": 0.41,
                "time": "2026-01-01 00:00:00",
            }
            try:
                data = json.dumps(_build_discord_payload(test_sig)).encode("utf-8")
                req  = urllib.request.Request(
                    DISCORD_WEBHOOK, data=data,
                    headers={"Content-Type": "application/json",
                             "User-Agent": "QuantMaster/1.0"},
                    method="POST",
                )
                urllib.request.urlopen(req, timeout=5)
                _discord_write_status(True)
                st.success("Discord ✓ — message envoyé")
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", errors="ignore")
                _discord_write_status(False, f"{e.code} {body[:120]}")
                st.error(f"Discord ✗ HTTP {e.code} — {body[:300]}")
            except Exception as e:
                _discord_write_status(False, str(e)[:80])
                st.error(f"Discord ✗ — {e}")

        # Status box
        st.markdown('<div class="sec-label">Régime marché</div>', unsafe_allow_html=True)
        regime_color = GREEN if h_val < HURST_THRESHOLD else RED
        h_pct_gauge  = min(100, int(h_val * 200))
        z_abs_pct    = min(100, int(abs(z_now) / BAND_K * 100))
        z_signal_lbl = "SIGNAL ZONE" if abs(z_now) >= BAND_K else f"seuil ±{BAND_K}σ"
        st.markdown(f"""
        <div class="ctx-box">
            <div style="font-family:'JetBrains Mono',monospace;font-size:.62rem;color:#333;
                        text-transform:uppercase;letter-spacing:.1em;margin-bottom:.3rem">Hurst H</div>
            <div style="display:flex;justify-content:space-between;margin-bottom:3px">
                <span style="font-size:1rem;font-weight:700;color:{regime_color};
                             font-family:'JetBrains Mono',monospace">{h_val:.3f}</span>
                <span style="font-size:.65rem;color:{regime_color}">{'MR ✓' if h_val < HURST_THRESHOLD else 'Trend ✗'}</span>
            </div>
            <div class="gauge-track">
                <div class="gauge-fill" style="width:{h_pct_gauge}%;background:linear-gradient(90deg,#00ff88,#ffd600,#ff3366)"></div>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:.55rem;color:#1e1e1e;
                        font-family:'JetBrains Mono',monospace;margin-bottom:.8rem">
                <span>0</span><span>{HURST_THRESHOLD}</span><span>0.5</span><span>1.0</span>
            </div>
            <div style="font-family:'JetBrains Mono',monospace;font-size:.62rem;color:#333;
                        text-transform:uppercase;letter-spacing:.1em;margin-bottom:.3rem">Z-score</div>
            <div style="display:flex;justify-content:space-between;margin-bottom:3px">
                <span style="font-size:1rem;font-weight:700;color:{z_col};
                             font-family:'JetBrains Mono',monospace">{z_now:+.2f}σ</span>
                <span style="font-size:.65rem;color:{z_col}">{z_signal_lbl}</span>
            </div>
            <div class="gauge-track">
                <div class="gauge-fill" style="width:{z_abs_pct}%;background:{z_col}"></div>
            </div>
            <div style="margin-top:.8rem;padding-top:.7rem;border-top:1px solid #0f0f0f;
                        font-family:'JetBrains Mono',monospace;font-size:.65rem;color:#2a2a2a;line-height:1.9">
                <span style="color:#444">Source</span> {data_source[:28]}<br>
                <span style="color:#444">Barres</span> {bars_count} M1 {'✓' if bars_count >= HURST_WIN+LOOKBACK else f'— min {HURST_WIN+LOOKBACK}'}<br>
                <span style="color:#444">Màj &nbsp;&nbsp;</span>{now_ny.strftime('%H:%M:%S')} Paris
            </div>
        </div>""", unsafe_allow_html=True)
except Exception as _e:
    with col_panel:
        st.error(f"⚠️ Panel error: {_e}")

# ── Chart ACF — Signature MR ───────────────────────────
# ═══════════════════════════════════════════════════════
# TABS : Journal | Analyse | Signaux
# ═══════════════════════════════════════════════════════
tab_journal, tab_analyse, tab_signaux = st.tabs(["  📋  Journal  ", "  📈  Analyse  ", "  🔔  Signaux  "])

# ─────────────────────────────────────────────────────
# TAB JOURNAL
# ─────────────────────────────────────────────────────
with tab_journal:
    j_df = journal_load()
    total_pnl  = j_df["pnl"].sum() if not j_df.empty else 0.0
    dd_used    = abs(j_df[j_df["pnl"] < 0]["pnl"].sum()) if not j_df.empty else 0.0
    dd_rem     = CHALLENGE_DD - dd_used
    prog_pct   = min(100, total_pnl / CHALLENGE_TARGET * 100) if CHALLENGE_TARGET > 0 else 0
    n_trades   = len(j_df)
    n_wins     = int((j_df["pnl"] > 0).sum()) if not j_df.empty else 0
    wr         = n_wins / n_trades * 100 if n_trades > 0 else 0

    # Challenge KPIs
    ca, cb, cc, cd = st.columns(4)
    pnl_col = GREEN if total_pnl >= 0 else RED
    dd_col  = GREEN if dd_used < CHALLENGE_DD*0.5 else (YELLOW if dd_used < CHALLENGE_DD*0.8 else RED)
    prg_col = GREEN if prog_pct >= 100 else TEAL
    with ca:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-value" style="color:{pnl_col}">{total_pnl:+.0f}$</div>
            <div class="kpi-label">P&L Challenge</div></div>""", unsafe_allow_html=True)
    with cb:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-value" style="color:{dd_col}">{dd_rem:.0f}$</div>
            <div class="kpi-label">DD Restant / {CHALLENGE_DD:.0f}$</div></div>""", unsafe_allow_html=True)
    with cc:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-value" style="color:{TEAL}">{wr:.0f}%</div>
            <div class="kpi-label">Win Rate ({n_wins}/{n_trades})</div></div>""", unsafe_allow_html=True)
    with cd:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-value" style="color:{prg_col}">{prog_pct:.0f}%</div>
            <div class="kpi-label">Vers {CHALLENGE_TARGET:.0f}$</div></div>""", unsafe_allow_html=True)

    st.markdown("<div style='margin-top:.6rem'></div>", unsafe_allow_html=True)

    # Formulaire
    with st.expander("➕ Logger un trade", expanded=bool(last_signal)):
        pre_dir   = last_signal["direction"] if last_signal else "LONG"
        pre_entry = round(last_signal["price"] / 10, 2) if last_signal else 0.0
        pre_sl    = round(last_signal["sl_pts_mnq"], 2) if last_signal else 0.0
        pre_tp    = round(last_signal["tp_price"] / 10, 2) if last_signal else 0.0
        pre_h     = round(last_signal["hurst"], 3) if last_signal else 0.0
        pre_z     = round(last_signal["z_score"], 2) if last_signal else 0.0
        fa, fb = st.columns(2)
        with fa:
            j_dir  = st.selectbox("Direction", ["LONG", "SHORT"], index=0 if pre_dir == "LONG" else 1)
            j_entry = st.number_input("Entrée MNQ", value=pre_entry, step=0.25, format="%.2f")
            j_sl    = st.number_input("SL (pts)", value=pre_sl, step=0.25, format="%.2f")
            j_tp    = st.number_input("TP MNQ", value=pre_tp, step=0.25, format="%.2f")
        with fb:
            j_exit      = st.number_input("Sortie réelle MNQ", value=pre_entry, step=0.25, format="%.2f")
            j_contracts = st.number_input("Contrats", value=1, min_value=1, max_value=50)
            j_notes     = st.text_area("Notes", placeholder="ex: slippage, ATAS confirmait...")
        pnl_preview = (j_exit - j_entry) * (1 if j_dir == "LONG" else -1) * TICK_VALUE * j_contracts
        pc = GREEN if pnl_preview >= 0 else RED
        st.markdown(f"**P&L estimé : <span style='color:{pc}'>{pnl_preview:+.2f}$</span>**",
                    unsafe_allow_html=True)
        if st.button("💾 Enregistrer", type="primary"):
            journal_add(datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%H:%M"),
                        j_dir, j_entry, j_sl, j_tp, j_contracts, j_exit, pre_h, pre_z, j_notes)
            journal_load.clear()
            st.session_state["_ls_toast"] = f"Trade {j_dir} enregistre — P&L ${pnl_preview:+.2f}"
            st.rerun()

    # Tableau
    if not j_df.empty:
        st.markdown('<div class="sec-label" style="margin-top:.5rem">Historique</div>', unsafe_allow_html=True)
        to_delete = []
        for _, row in j_df.iterrows():
            pnl_col_r = GREEN if row["pnl"] > 0 else (RED if row["pnl"] < 0 else "#888")
            dir_col   = GREEN if row["direction"] == "LONG" else RED
            cols = st.columns([0.05, 0.12, 0.08, 0.08, 0.08, 0.08, 0.08, 0.08, 0.1, 0.25])
            if cols[0].checkbox("", key=f"del_{row['id']}"):
                to_delete.append(row["id"])
            cols[1].markdown(f"<span style='font-size:.75rem;color:#555'>{row['date']} {row['time_ny']}</span>", unsafe_allow_html=True)
            cols[2].markdown(f"<span style='color:{dir_col};font-weight:700;font-size:.8rem'>{row['direction']}</span>", unsafe_allow_html=True)
            cols[3].markdown(f"<span style='font-size:.8rem'>{row['entry']:.2f}</span>", unsafe_allow_html=True)
            cols[4].markdown(f"<span style='font-size:.8rem;color:{TEAL}'>{row['tp']:.2f}</span>", unsafe_allow_html=True)
            cols[5].markdown(f"<span style='font-size:.8rem;color:{RED}'>{row['sl_pts']:.2f}pts</span>", unsafe_allow_html=True)
            cols[6].markdown(f"<span style='font-size:.8rem'>{row['exit_price']:.2f}</span>", unsafe_allow_html=True)
            cols[7].markdown(f"<span style='font-size:.8rem;color:#888'>{int(row['contracts'])}x</span>", unsafe_allow_html=True)
            cols[8].markdown(f"<span style='font-weight:700;color:{pnl_col_r};font-size:.85rem'>{row['pnl']:+.0f}$</span>", unsafe_allow_html=True)
            cols[9].markdown(f"<span style='font-size:.7rem;color:#444'>{str(row['notes'])[:30]}</span>", unsafe_allow_html=True)
        if to_delete:
            if st.button(f"🗑 Supprimer {len(to_delete)} trade(s) sélectionné(s)", type="primary"):
                for tid in to_delete:
                    journal_delete(tid)
                journal_load.clear()
                st.rerun()

# ─────────────────────────────────────────────────────
# TAB ANALYSE
# ─────────────────────────────────────────────────────
with tab_analyse:
    col_h, col_acf = st.columns(2, gap="medium")

    # Hurst intraday
    with col_h:
        st.markdown('<div class="sec-label">Hurst intraday</div>', unsafe_allow_html=True)
        # Réutilise hurst_arr précalculé — zéro recalcul
        step = max(1, LOOKBACK)
        hurst_vals = [
            (i, hurst_arr[i])
            for i in range(HURST_WIN, len(closes), step)
            if not np.isnan(hurst_arr[i])
        ]
        if len(hurst_vals) > 2:
            hx = [v[0] for v in hurst_vals]
            hy = [v[1] for v in hurst_vals]
            hx_labels = [times_str[i][11:16] for i in hx if i < len(times_str)]
            fig_h = go.Figure()
            fig_h.add_hrect(y0=0, y1=HURST_THRESHOLD,
                            fillcolor="rgba(0,255,136,0.04)", line_width=0)
            fig_h.add_hline(y=HURST_THRESHOLD,
                            line=dict(color=RED, dash="dash", width=1.5),
                            annotation_text=f"Seuil {HURST_THRESHOLD}",
                            annotation_font=dict(color=RED, size=9))
            fig_h.add_hline(y=0.5, line=dict(color="#222", dash="dot", width=1))
            colors_h = [GREEN if v < HURST_THRESHOLD else ORANGE for v in hy]
            fig_h.add_trace(go.Scatter(
                x=hx[:len(hx_labels)], y=hy, mode="lines+markers",
                line=dict(color=TEAL, width=2),
                marker=dict(color=colors_h, size=6, line=dict(color="white", width=0.5)),
                fill="tozeroy", fillcolor="rgba(60,196,183,0.04)",
                hovertemplate="%{text}: H=%{y:.3f}<extra></extra>",
                text=hx_labels, showlegend=False,
            ))
            if hx:
                last_h_col = GREEN if hy[-1] < HURST_THRESHOLD else RED
                fig_h.add_trace(go.Scatter(
                    x=[hx[-1]], y=[hy[-1]], mode="markers+text",
                    marker=dict(size=10, color=last_h_col),
                    text=[f"H={hy[-1]:.3f}"], textposition="top right",
                    textfont=dict(size=10, color=last_h_col), showlegend=False,
                ))
            fig_h.update_layout(
                **DARK, height=280,
                title=dict(text=f"H rolling {HURST_WIN} returns · toutes les {step} barres",
                           font=dict(size=11, color="#555", family="JetBrains Mono")),
                yaxis=dict(range=[0, 1], gridcolor="#0f0f0f",
                           tickvals=[0, 0.25, HURST_THRESHOLD, 0.5, 0.75, 1.0]),
                xaxis=dict(tickvals=hx[:len(hx_labels)], ticktext=hx_labels, gridcolor="#0f0f0f"),
                showlegend=False,
            )
            st.plotly_chart(fig_h, use_container_width=True)
        else:
            st.caption(f"Hurst disponible après {HURST_WIN} barres.")

    # ACF
    with col_acf:
        st.markdown('<div class="sec-label">Autocorrélation — Signature MR</div>', unsafe_allow_html=True)
        log_rets_acf = np.diff(np.log(np.maximum(closes, 1e-9)))
        if len(log_rets_acf) >= 30:
            n_lags   = min(30, len(log_rets_acf) - 1)
            acf_vals = []
            x_mean = log_rets_acf - log_rets_acf.mean()
            c0 = np.dot(x_mean, x_mean)
            for lag in range(1, n_lags + 1):
                c_lag = np.dot(x_mean[:-lag], x_mean[lag:])
                acf_vals.append(c_lag / c0 if c0 > 0 else 0)
            lags      = list(range(1, n_lags + 1))
            sig_bound = 1.96 / np.sqrt(len(log_rets_acf))
            acf_colors = [
                GREEN if v < -sig_bound else (RED if v > sig_bound else "#333")
                for v in acf_vals
            ]
            fig_acf = go.Figure()
            fig_acf.add_hrect(y0=-sig_bound, y1=sig_bound,
                              fillcolor="rgba(255,255,255,0.02)", line_width=0)
            fig_acf.add_hline(y=sig_bound,  line=dict(color="#333", dash="dot", width=1),
                              annotation_text="95% conf.", annotation_font=dict(color="#333", size=9))
            fig_acf.add_hline(y=-sig_bound, line=dict(color="#333", dash="dot", width=1))
            fig_acf.add_hline(y=0, line=dict(color="#1a1a1a", width=1))
            fig_acf.add_trace(go.Bar(
                x=lags, y=acf_vals,
                marker_color=acf_colors,
                marker_line_width=0,
                name="ACF",
                hovertemplate="Lag %{x}: ACF=%{y:.3f}<extra></extra>",
            ))
            lag1_col = GREEN if acf_vals[0] < 0 else RED
            lag1_txt = "MR ✓" if acf_vals[0] < 0 else "Trend"
            fig_acf.add_annotation(
                x=1, y=acf_vals[0],
                text=f" Lag1={acf_vals[0]:.3f} ({lag1_txt})",
                showarrow=False, font=dict(color=lag1_col, size=10, family="JetBrains Mono"),
                xanchor="left",
            )
            fig_acf.update_layout(
                **DARK,
                height=280,
                title=dict(
                    text="ACF log returns · Lag1 < 0 = anti-persistance = MR confirmé",
                    font=dict(color="#555", size=11, family="JetBrains Mono"),
                ),
                xaxis=dict(title="Lag (barres M1)", gridcolor="#0f0f0f", dtick=5),
                yaxis=dict(gridcolor="#0f0f0f", zeroline=False, side="right"),
                showlegend=False,
                bargap=0.2,
            )
            st.plotly_chart(fig_acf, use_container_width=True)
        else:
            st.caption("ACF disponible après 30 barres.")

# ─────────────────────────────────────────────────────
# TAB SIGNAUX
# ─────────────────────────────────────────────────────
with tab_signaux:
    st.markdown('<div class="sec-label">Signaux session du jour</div>', unsafe_allow_html=True)
    if signals:
        rows = []
        for s in signals:
            rows.append({
                "Heure":      s["time"][11:16] + " Paris",
                "Direction":  s["direction"],
                "Entrée MNQ": f"{s['price']/10:,.2f}",
                "Fair Value": f"{s['fair_value']/10:,.2f}",
                "TP MNQ":     f"{s['tp_price']/10:,.2f}",
                "SL pts":     f"{s['sl_pts_mnq']:.2f}",
                "Z-score":    f"{s['z_score']:+.2f}σ",
                "Hurst H":    f"{s['hurst']:.3f}",
            })
        sig_df = pd.DataFrame(rows)
        def _color_dir(val):
            return f"color:{GREEN};font-weight:bold" if val == "LONG" else f"color:{RED};font-weight:bold"
        st.dataframe(
            sig_df.style.applymap(_color_dir, subset=["Direction"]),
            use_container_width=True, hide_index=True,
        )
        # Résumé signal actif
        if last_signal:
            d         = last_signal["direction"]
            col       = GREEN if d == "LONG" else RED
            cls       = "sig-long" if d == "LONG" else "sig-short"
            icon      = "▲" if d == "LONG" else "▼"
            tp_mnq    = last_signal["tp_price"] / 10
            sl_mnq    = last_signal["sl_pts_mnq"]
            entry_mnq = last_signal["price"] / 10
            rr        = abs(tp_mnq - entry_mnq) / sl_mnq if sl_mnq > 0 else 0
            st.markdown('<div class="sec-label" style="margin-top:1rem">Dernier signal actif</div>', unsafe_allow_html=True)
            _flash2 = " qm-signal-new" if _sig_age_min < 0.5 else ""
            st.markdown(f"""
            <div class="{cls}{_flash2}" style="max-width:480px">
                <div style="font-size:1.6rem;font-weight:700;color:{col};
                            font-family:'JetBrains Mono',monospace">{icon} {d}</div>
                <div style="font-size:.6rem;color:{col};font-family:'JetBrains Mono',monospace;
                            letter-spacing:.15em;margin:-.1rem 0 .7rem">
                    {last_signal["time"][11:16]} · Z={last_signal["z_score"]:+.2f}σ · H={last_signal["hurst"]:.3f}
                </div>
                <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:6px;
                            font-family:'JetBrains Mono',monospace">
                    <div style="background:rgba(0,0,0,.3);border-radius:7px;padding:.5rem .7rem">
                        <div style="font-size:.52rem;color:#444;margin-bottom:.15rem">ENTRÉE</div>
                        <div style="color:#fff;font-weight:700;font-size:.85rem">{entry_mnq:,.2f}</div>
                    </div>
                    <div style="background:rgba(0,0,0,.3);border-radius:7px;padding:.5rem .7rem">
                        <div style="font-size:.52rem;color:#444;margin-bottom:.15rem">FV</div>
                        <div style="color:{TEAL};font-weight:700;font-size:.85rem">{last_signal["fair_value"]/10:,.2f}</div>
                    </div>
                    <div style="background:rgba(0,0,0,.3);border-radius:7px;padding:.5rem .7rem">
                        <div style="font-size:.52rem;color:#444;margin-bottom:.15rem">TP MNQ</div>
                        <div style="color:{TEAL};font-weight:700;font-size:.85rem">{tp_mnq:,.2f}</div>
                    </div>
                    <div style="background:rgba(0,0,0,.3);border-radius:7px;padding:.5rem .7rem">
                        <div style="font-size:.52rem;color:#444;margin-bottom:.15rem">SL · R:R</div>
                        <div style="font-size:.85rem"><span style="color:{RED};font-weight:700">{sl_mnq:.1f}pts</span> <span style="color:#fff">{rr:.1f}R</span></div>
                    </div>
                </div>
            </div>""", unsafe_allow_html=True)
    else:
        _reg2 = f"H={h_val:.3f} — systeme actif, attente Z" if h_val < HURST_THRESHOLD else f"H={h_val:.3f} — regime trending, pas de trade"
        from styles import empty_state as _es2
        st.markdown(_es2("◎", "Aucun signal aujourd hui", _reg2), unsafe_allow_html=True)

# ── Footer ────────────────────────────────────────────
st.divider()
st.markdown(f"""
<div style="text-align:center;font-family:'JetBrains Mono',monospace;font-size:.6rem;
            color:#1a1a1a;letter-spacing:.1em;margin-top:1rem">
    HURST_MR · K={BAND_K}σ · H&lt;{HURST_THRESHOLD} · LB={LOOKBACK} ·
    MàJ {now_ny.strftime('%H:%M:%S')} ·
    <span class="live-dot" style="width:5px;height:5px"></span>LIVE 2s
</div>
""", unsafe_allow_html=True)
