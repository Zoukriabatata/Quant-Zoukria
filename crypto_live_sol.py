import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import yfinance as yf
from datetime import datetime, timedelta
import requests
import json
import sqlite3
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

from config import SOL_JOURNAL_DB

try:
    from statsmodels.tsa.seasonal import STL
    HAS_STL = True
except ImportError:
    HAS_STL = False

from styles import inject as _inj; _inj()

# ─── PALETTE ────────────────────────────────────────────────────────────────
C = dict(bg="#050505", paper="rgba(0,0,0,0)", white="#f1f5f9", text="#94a3b8",
         green="#e5e7eb", red="#6b7280", blue="#d1d5db", grey="#4b5563")
DARK = dict(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="#050505",
            font=dict(color="#94a3b8", size=11, family="'JetBrains Mono',monospace"),
            margin=dict(t=48, b=40, l=52, r=24),
            hoverlabel=dict(bgcolor="#0a0a0a", font=dict(size=12, family="JetBrains Mono")))

# ─── CONSTANTES ─────────────────────────────────────────────────────────────
TICKER = "SOL-USD"
STL_PERIOD = 5
EMA_FILTER = 10
SIGNAL_FILE = Path(__file__).parent / ".sol_last_signal.json"

# Alertes — lues depuis secrets.toml, jamais à retaper
_NTFY_DEFAULT    = st.secrets.get("SOL_NTFY_TOPIC",  "")
_DISCORD_DEFAULT = st.secrets.get("SOL_DISCORD_URL", "")

# ─── CSS ADDITIONNEL ────────────────────────────────────────────────────────
st.markdown("""
<style>
.live-badge-long {
    display:inline-block;padding:.4rem 1.2rem;
    background:rgba(229,231,235,.08);border:2px solid #e5e7eb;
    border-radius:999px;color:#e5e7eb;font-size:1rem;font-weight:700;
    font-family:'JetBrains Mono',monospace;letter-spacing:.1em;
}
.live-badge-flat {
    display:inline-block;padding:.4rem 1.2rem;
    background:rgba(75,85,99,.08);border:2px solid #4b5563;
    border-radius:999px;color:#6b7280;font-size:1rem;font-weight:700;
    font-family:'JetBrains Mono',monospace;letter-spacing:.1em;
}
.live-price {
    font-size:2.2rem;font-weight:700;color:#f1f5f9;
    font-family:'JetBrains Mono',monospace;
}
.info-box {
    background:#060606;border:1px solid #1a1a1a;border-radius:10px;
    padding:.8rem 1rem;font-family:'JetBrains Mono',monospace;
}
.info-label {
    font-size:.6rem;color:#444;text-transform:uppercase;letter-spacing:.15em;
}
.info-val {
    font-size:1.1rem;font-weight:700;margin-top:.2rem;
}
</style>
""", unsafe_allow_html=True)


# ─── FONCTIONS ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def load_live_data(symbol: str = "SOLUSDT", days: int = 730) -> pd.DataFrame:
    """Télécharge les données daily via Binance public API (sans clé)."""
    try:
        url = "https://api.binance.com/api/v3/klines"
        params = {"symbol": symbol, "interval": "1d", "limit": min(days, 1000)}
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        raw = resp.json()
        df = pd.DataFrame(raw, columns=[
            "open_time","Open","High","Low","Close","Volume",
            "close_time","qav","num_trades","tbbav","tbqav","ignore"
        ])
        df["Close"] = df["Close"].astype(float)
        df["Open"]  = df["Open"].astype(float)
        df["High"]  = df["High"].astype(float)
        df["Low"]   = df["Low"].astype(float)
        df["Volume"]= df["Volume"].astype(float)
        df.index = pd.to_datetime(df["open_time"], unit="ms").dt.normalize()
        df = df[["Open","High","Low","Close","Volume"]].dropna()
        return df
    except Exception as e:
        # Fallback yfinance
        try:
            df = yf.download(TICKER, period="2y", interval="1d",
                             progress=False, auto_adjust=True)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df.index = pd.to_datetime(df.index)
            return df.dropna(subset=["Close"])
        except Exception:
            return pd.DataFrame()


def compute_stl_signal(close: pd.Series, period: int, ema_filter: int):
    """
    Calcule le signal STL decomposition.
    Retourne : signal, trend, stl_res (ou None), ema
    """
    ema = close.ewm(span=ema_filter, adjust=False).mean()

    if HAS_STL and len(close) >= period * 2:
        try:
            log_close = np.log(close.values.astype(float))
            res = STL(log_close, period=period, robust=True).fit()
            trend = pd.Series(res.trend, index=close.index)
            trend_dir = np.sign(trend.diff()).clip(0, 1)
            signal = trend_dir * (close > ema).astype(float)
            signal = signal.shift(1).fillna(0)
            return signal, trend, res, ema
        except Exception:
            pass

    # Fallback EMA si STL indisponible
    ema_fast = close.ewm(span=period, adjust=False).mean()
    ema_slow = close.ewm(span=period * 3, adjust=False).mean()
    trend = ema_slow
    trend_dir = (ema_fast > ema_slow).astype(float)
    signal = (trend_dir * (close > ema).astype(float)).shift(1).fillna(0)
    return signal, trend, None, ema


def send_ntfy(topic: str, title: str, message: str, priority: str = "default") -> bool:
    """Envoie une notification via ntfy.sh."""
    if not topic:
        return False
    try:
        resp = requests.post(
            f"https://ntfy.sh/{topic}",
            data=message.encode("utf-8"),
            headers={
                "Title": title,
                "Priority": priority,
                "Tags": "chart_with_upwards_trend,solana",
            },
            timeout=8
        )
        return resp.status_code == 200
    except Exception:
        return False


def send_discord(webhook_url: str, message: str) -> bool:
    """Envoie un message via Discord webhook."""
    if not webhook_url:
        return False
    try:
        resp = requests.post(
            webhook_url,
            json={"content": message, "username": "QuantMaster SOL"},
            timeout=8
        )
        return resp.status_code in (200, 204)
    except Exception:
        return False


def load_last_signal() -> dict | None:
    """Lit le dernier signal sauvegardé depuis le fichier JSON."""
    if SIGNAL_FILE.exists():
        try:
            with open(SIGNAL_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None


def save_last_signal(signal_val: float, price: float, date: str) -> None:
    """Sauvegarde le signal courant dans le fichier JSON."""
    try:
        with open(SIGNAL_FILE, "w", encoding="utf-8") as f:
            json.dump({"signal": signal_val, "price": price, "date": date}, f)
    except Exception:
        pass


# ─── JOURNAL SOL ────────────────────────────────────────────────────────────

def _sol_db():
    con = sqlite3.connect(SOL_JOURNAL_DB)
    con.execute("""
        CREATE TABLE IF NOT EXISTS sol_trades (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            date_entry    TEXT,
            date_exit     TEXT,
            entry_price   REAL,
            exit_price    REAL,
            capital       REAL DEFAULT 500,
            leverage      REAL DEFAULT 1.0,
            pnl_pct       REAL,
            pnl_usd       REAL,
            duration_days INTEGER,
            status        TEXT DEFAULT 'OPEN',
            notes         TEXT DEFAULT ''
        )""")
    con.commit()
    return con


def journal_open_trade(entry_price: float, capital: float, leverage: float, date_entry: str):
    con = _sol_db()
    con.execute(
        "INSERT INTO sol_trades (date_entry, entry_price, capital, leverage, status) "
        "VALUES (?, ?, ?, ?, 'OPEN')",
        (date_entry, entry_price, capital, leverage)
    )
    con.commit()
    con.close()


def journal_close_trade(exit_price: float, date_exit: str):
    con = _sol_db()
    row = con.execute(
        "SELECT id, entry_price, capital, leverage, date_entry "
        "FROM sol_trades WHERE status='OPEN' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if row:
        trade_id, entry_price, capital, leverage, date_entry = row
        pnl_pct = (exit_price / entry_price - 1) * leverage * 100
        pnl_usd = pnl_pct / 100 * capital
        try:
            d0 = datetime.strptime(date_entry[:10], "%Y-%m-%d")
            d1 = datetime.strptime(date_exit[:10], "%Y-%m-%d")
            duration = (d1 - d0).days
        except Exception:
            duration = None
        con.execute(
            "UPDATE sol_trades SET date_exit=?, exit_price=?, pnl_pct=?, pnl_usd=?, "
            "duration_days=?, status='CLOSED' WHERE id=?",
            (date_exit, exit_price, pnl_pct, pnl_usd, duration, trade_id)
        )
        con.commit()
    con.close()


def journal_load() -> pd.DataFrame:
    try:
        con = _sol_db()
        df = pd.read_sql("SELECT * FROM sol_trades ORDER BY id DESC", con)
        con.close()
        return df
    except Exception:
        return pd.DataFrame()


def journal_delete(trade_id: int):
    con = _sol_db()
    con.execute("DELETE FROM sol_trades WHERE id=?", (trade_id,))
    con.commit()
    con.close()


def find_entry_date(signal: pd.Series) -> pd.Timestamp | None:
    """Trouve la date de début de la séquence LONG actuelle (remonte en arrière)."""
    sig_vals = signal.values
    idx = signal.index
    n = len(sig_vals)
    if n == 0 or sig_vals[-1] == 0:
        return None
    # Remonte jusqu'au premier 0 avant la séquence de 1
    i = n - 1
    while i > 0 and sig_vals[i] > 0:
        i -= 1
    # i+1 est le début de la séquence LONG courante
    entry_i = i + 1 if sig_vals[i] == 0 else 0
    return idx[entry_i] if entry_i < n else idx[-1]


# ─── CHARGEMENT DONNÉES ─────────────────────────────────────────────────────
df = load_live_data()

if df.empty:
    st.error("Impossible de charger les données SOL-USD. Vérifiez la connexion.")
    st.stop()

close = df["Close"].squeeze()
signal, trend, stl_res, ema = compute_stl_signal(close, STL_PERIOD, EMA_FILTER)

current_signal = float(signal.iloc[-1])
current_price = float(close.iloc[-1])
prev_price = float(close.iloc[-2]) if len(close) > 1 else current_price
prev_day_change = (current_price / prev_price - 1) * 100
is_long = current_signal > 0

# Entrée + PnL non-réalisé
entry_date = find_entry_date(signal) if is_long else None
entry_price = float(close.loc[entry_date]) if entry_date is not None else None
days_in_trade = (close.index[-1] - entry_date).days if entry_date is not None else None
unrealized_pnl = ((current_price / entry_price) - 1) * 100 if entry_price else None

# ─── GESTION ALERTES AUTO ───────────────────────────────────────────────────
last = load_last_signal()
alert_triggered = False
if last and last["signal"] != current_signal:
    alert_triggered = True
    # Les alertes seront envoyées dans le tab Alertes si configurées
    save_last_signal(current_signal, current_price, str(datetime.now().date()))
elif not last:
    save_last_signal(current_signal, current_price, str(datetime.now().date()))

# ─── HEADER ─────────────────────────────────────────────────────────────────
st.markdown("""
<div style='font-size:.7rem;color:#444;letter-spacing:.25em;
    font-family:JetBrains Mono,monospace;text-transform:uppercase;margin-bottom:.5rem;'>
    QUANTMASTER · SOL/USD LIVE
</div>
""", unsafe_allow_html=True)

col_badge, col_price, col_chg = st.columns([2, 2, 2])
with col_badge:
    if is_long:
        st.markdown('<span class="live-badge-long">▲ LONG</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="live-badge-flat">— FLAT</span>', unsafe_allow_html=True)
with col_price:
    st.markdown(f'<div class="live-price">${current_price:,.2f}</div>', unsafe_allow_html=True)
with col_chg:
    chg_color = "#e5e7eb" if prev_day_change >= 0 else "#6b7280"
    sign = "+" if prev_day_change >= 0 else ""
    st.markdown(
        f'<div style="font-size:1.4rem;font-weight:700;color:{chg_color};'
        f'font-family:JetBrains Mono,monospace;padding-top:.4rem;">'
        f'{sign}{prev_day_change:.2f}%</div>',
        unsafe_allow_html=True
    )

st.markdown(
    '<div style="color:#444;font-size:.72rem;font-family:JetBrains Mono,monospace;'
    'margin:.5rem 0 1rem 0;letter-spacing:.05em;">'
    f'Stratégie : STL Decomposition · période={STL_PERIOD} · EMA={EMA_FILTER} · daily'
    + (" &nbsp;|&nbsp; <b style='color:#6b7280'>STL indisponible → fallback EMA</b>" if not HAS_STL else "")
    + '</div>',
    unsafe_allow_html=True
)

# ─── MÉTRIQUES ──────────────────────────────────────────────────────────────
m1, m2, m3, m4, m5, m6 = st.columns(6)
metrics = [
    ("Prix", f"${current_price:,.2f}", "#f1f5f9"),
    ("24h", f"{'+' if prev_day_change >= 0 else ''}{prev_day_change:.2f}%",
     "#e5e7eb" if prev_day_change >= 0 else "#6b7280"),
    ("Signal", "LONG" if is_long else "FLAT",
     "#e5e7eb" if is_long else "#6b7280"),
    ("Jours trade", str(days_in_trade) if days_in_trade is not None else "--", "#94a3b8"),
    ("PnL latent", f"{'+' if unrealized_pnl and unrealized_pnl >= 0 else ''}{unrealized_pnl:.2f}%"
     if unrealized_pnl is not None else "--",
     "#e5e7eb" if unrealized_pnl and unrealized_pnl >= 0 else "#6b7280"),
    ("Mise à jour", close.index[-1].strftime("%d/%m/%Y"), "#4b5563"),
]
for col, (label, val, color) in zip([m1, m2, m3, m4, m5, m6], metrics):
    with col:
        st.markdown(
            f'<div class="info-box">'
            f'<div class="info-label">{label}</div>'
            f'<div class="info-val" style="color:{color};">{val}</div>'
            f'</div>',
            unsafe_allow_html=True
        )

st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)

# ─── TABS ───────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📡 Signal Live", "🔬 Décomposition STL", "🔔 Alertes", "🗺️ Optimisation 3D", "📒 Journal SOL", "🔄 Walk-Forward"])


# ════════════════════════════════════════════════════════════════════════════
# TAB 1 — SIGNAL LIVE
# ════════════════════════════════════════════════════════════════════════════
with tab1:
    # Trend normalisé
    trend_vals = trend.values.astype(float)
    trend_norm = (trend_vals - trend_vals.mean()) / (trend_vals.std() + 1e-9)
    trend_norm_series = pd.Series(trend_norm, index=close.index)

    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        row_heights=[0.55, 0.25, 0.20],
        vertical_spacing=0.04,
        subplot_titles=["Prix SOL/USD + Trend STL", "Trend STL (normalisé)", "Signal (0/1)"]
    )

    # ── Row 1 : Prix + zones LONG ──
    # Zone LONG (fill under price)
    long_mask = signal > 0
    close_long = close.where(long_mask)
    fig.add_trace(go.Scatter(
        x=close.index, y=close_long.values,
        mode="lines", line=dict(width=0),
        fill="tozeroy",
        fillcolor="rgba(255,255,255,0.04)",
        showlegend=False, hoverinfo="skip"
    ), row=1, col=1)

    # Prix
    fig.add_trace(go.Scatter(
        x=close.index, y=close.values,
        mode="lines", name="Prix",
        line=dict(color="#94a3b8", width=1.4),
        hovertemplate="<b>%{x|%d/%m/%y}</b><br>Prix : $%{y:,.2f}<extra></extra>"
    ), row=1, col=1)

    # Trend STL
    if HAS_STL and stl_res is not None:
        # Trend en espace prix (exp du trend log)
        trend_price = np.exp(stl_res.trend)
        fig.add_trace(go.Scatter(
            x=close.index, y=trend_price,
            mode="lines", name="Trend STL",
            line=dict(color="#f1f5f9", width=2.0),
            hovertemplate="Trend : $%{y:,.2f}<extra></extra>"
        ), row=1, col=1)
    else:
        fig.add_trace(go.Scatter(
            x=trend.index, y=trend.values,
            mode="lines", name="Trend (EMA)",
            line=dict(color="#f1f5f9", width=2.0),
            hovertemplate="Trend : $%{y:,.2f}<extra></extra>"
        ), row=1, col=1)

    # EMA10
    fig.add_trace(go.Scatter(
        x=ema.index, y=ema.values,
        mode="lines", name=f"EMA{EMA_FILTER}",
        line=dict(color="#4b5563", width=1.2, dash="dash"),
        hovertemplate=f"EMA{EMA_FILTER} : $%{{y:,.2f}}<extra></extra>"
    ), row=1, col=1)

    # ── Row 2 : Trend normalisé ──
    fig.add_trace(go.Scatter(
        x=close.index, y=trend_norm_series.values,
        mode="lines", name="Trend norm.",
        line=dict(color="#d1d5db", width=1.2),
        fill="tozeroy",
        fillcolor="rgba(209,213,219,0.05)",
        hovertemplate="Trend norm. : %{y:.3f}<extra></extra>"
    ), row=2, col=1)
    fig.add_hline(y=0, line_color="#333333", line_width=1, row=2, col=1)

    # ── Row 3 : Signal bar ──
    bar_colors = ["rgba(229,231,235,0.6)" if v > 0 else "rgba(75,85,99,0.4)"
                  for v in signal.values]
    fig.add_trace(go.Bar(
        x=signal.index, y=signal.values,
        name="Signal",
        marker_color=bar_colors,
        hovertemplate="<b>%{x|%d/%m/%y}</b><br>Signal : %{y}<extra></extra>"
    ), row=3, col=1)

    fig.update_layout(
        height=620,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.01,
                    xanchor="left", x=0, font=dict(size=10)),
        **DARK
    )
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(showgrid=True, gridcolor="#111111", zeroline=False)

    st.plotly_chart(fig, use_container_width=True)

    # ── Signal actuel visuel ──
    st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
    if is_long:
        entry_str = entry_date.strftime("%d %b %Y") if entry_date else "N/A"
        st.markdown(
            f'<div style="text-align:center;padding:1.2rem;">'
            f'<div style="font-size:1.6rem;font-weight:700;color:#e5e7eb;'
            f'font-family:JetBrains Mono,monospace;letter-spacing:.08em;">SIGNAL ACTUEL : 🟢 LONG</div>'
            f'<div style="font-size:.9rem;color:#6b7280;margin-top:.4rem;'
            f'font-family:JetBrains Mono,monospace;">Depuis le {entry_str}</div>'
            f'</div>',
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            '<div style="text-align:center;padding:1.2rem;">'
            '<div style="font-size:1.6rem;font-weight:700;color:#6b7280;'
            'font-family:JetBrains Mono,monospace;letter-spacing:.08em;">SIGNAL ACTUEL : ⬜ FLAT</div>'
            '<div style="font-size:.9rem;color:#4b5563;margin-top:.4rem;'
            'font-family:JetBrains Mono,monospace;">Aucune position ouverte</div>'
            '</div>',
            unsafe_allow_html=True
        )

    if alert_triggered:
        st.info("Signal changé depuis la dernière session — vérifiez vos alertes dans le tab 🔔")

    # ── Graphique 3D Signal Live ──
    st.markdown(
        '<div style="color:#444;font-size:.72rem;font-family:JetBrains Mono,monospace;'
        'letter-spacing:.1em;text-transform:uppercase;margin:1.4rem 0 .6rem 0;">'
        'Vue 3D — Ruban Prix / Trend STL coloré par signal</div>',
        unsafe_allow_html=True
    )

    # ── Données 365 jours ──
    n_3d    = min(365, len(close))
    idx_3d  = np.arange(n_3d)
    c3d     = close.iloc[-n_3d:].values.astype(float)
    s3d     = signal.iloc[-n_3d:].values.astype(float)
    e3d     = ema.iloc[-n_3d:].values.astype(float)
    dates3d = close.index[-n_3d:]

    if HAS_STL and stl_res is not None:
        t3d_price = np.exp(stl_res.trend[-n_3d:])
    else:
        t3d_price = trend.iloc[-n_3d:].values.astype(float)

    # ── Surface ruban entre Prix et Trend ──
    # Z = axe "profondeur" : 0 = prix, 1 = trend
    # Y = valeur (USD)
    # X = temps
    Z_surf = np.vstack([c3d, t3d_price])        # shape (2, N)
    X_surf = np.vstack([idx_3d, idx_3d])
    Y_surf = np.array([[0] * n_3d, [1] * n_3d], dtype=float)

    # Couleur surface = signal (0→gris, 1→blanc)
    surf_color = np.vstack([s3d, s3d])

    fig3dl = go.Figure()

    # Surface ruban colorée par signal
    fig3dl.add_trace(go.Surface(
        x=X_surf,
        y=Y_surf,
        z=Z_surf,
        surfacecolor=surf_color,
        colorscale=[
            [0.0, "rgba(30,30,40,0.55)"],    # FLAT → gris sombre
            [1.0, "rgba(220,225,235,0.75)"],  # LONG → blanc
        ],
        showscale=False,
        opacity=0.72,
        hovertemplate=(
            "<b>%{customdata}</b><br>"
            "Prix : $%{z:,.2f}<extra></extra>"
        ),
        customdata=np.vstack([
            [d.strftime("%d/%m/%y") for d in dates3d],
            [d.strftime("%d/%m/%y") for d in dates3d],
        ]),
    ))

    # Ligne prix (arête avant du ruban)
    fig3dl.add_trace(go.Scatter3d(
        x=idx_3d, y=np.zeros(n_3d), z=c3d,
        mode="lines",
        name="Prix SOL/USD",
        line=dict(color="#94a3b8", width=4),
        hovertemplate="<b>%{customdata}</b><br>Prix : $%{z:,.2f}<extra></extra>",
        customdata=[d.strftime("%d/%m/%y") for d in dates3d]
    ))

    # Ligne trend STL (arête arrière du ruban)
    fig3dl.add_trace(go.Scatter3d(
        x=idx_3d, y=np.ones(n_3d), z=t3d_price,
        mode="lines",
        name="Trend STL",
        line=dict(color="#f1f5f9", width=5),
        hovertemplate="Trend : $%{z:,.2f}<extra></extra>"
    ))

    # Ligne EMA filtre
    fig3dl.add_trace(go.Scatter3d(
        x=idx_3d, y=np.zeros(n_3d), z=e3d,
        mode="lines",
        name=f"EMA{EMA_FILTER}",
        line=dict(color="#4b5563", width=2, dash="dash"),
        hovertemplate=f"EMA{EMA_FILTER} : $%{{z:,.2f}}<extra></extra>"
    ))

    # Point NOW
    now_color = "#e5e7eb" if is_long else "#4b5563"
    fig3dl.add_trace(go.Scatter3d(
        x=[idx_3d[-1]], y=[0.0], z=[c3d[-1]],
        mode="markers+text",
        marker=dict(size=11, color=now_color, symbol="diamond",
                    line=dict(color="#ffffff", width=1.5)),
        text=[f"${c3d[-1]:,.0f}"],
        textfont=dict(color="#f1f5f9", size=11, family="JetBrains Mono"),
        textposition="top center",
        name="Maintenant",
        hovertemplate=f"Maintenant · {'LONG' if is_long else 'FLAT'}<br>${c3d[-1]:,.2f}<extra></extra>"
    ))

    # Ticks dates sur X
    tick_idx = np.linspace(0, n_3d - 1, 7).astype(int)
    tick_lbl = [dates3d[i].strftime("%b %y") for i in tick_idx]

    fig3dl.update_layout(
        height=600,
        scene=dict(
            xaxis=dict(
                title="", backgroundcolor="#050505", gridcolor="#111111",
                color="#94a3b8", tickmode="array",
                tickvals=tick_idx.tolist(), ticktext=tick_lbl,
            ),
            yaxis=dict(
                title="", backgroundcolor="#050505", gridcolor="#0a0a0a",
                color="#050505", tickvals=[0, 1],
                ticktext=["Prix", "Trend"],
                tickfont=dict(color="#4b5563", size=9),
            ),
            zaxis=dict(
                title="USD", backgroundcolor="#050505",
                gridcolor="#111111", color="#94a3b8",
            ),
            bgcolor="#050505",
            camera=dict(eye=dict(x=1.8, y=-1.4, z=0.7)),
            aspectmode="manual",
            aspectratio=dict(x=2.5, y=0.4, z=1.0),
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#94a3b8", size=11, family="JetBrains Mono,monospace"),
        margin=dict(t=16, b=16, l=0, r=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    xanchor="left", x=0, font=dict(size=10, color="#94a3b8"),
                    bgcolor="rgba(0,0,0,0)"),
    )

    st.plotly_chart(fig3dl, use_container_width=True)
    st.markdown(
        '<div style="color:#333;font-size:.68rem;font-family:JetBrains Mono,monospace;">'
        'Surface claire = LONG · Surface sombre = FLAT · '
        'Ligne blanche = Trend STL · Ligne grise = Prix · ◆ = maintenant — 365 jours'
        '</div>',
        unsafe_allow_html=True
    )


# ════════════════════════════════════════════════════════════════════════════
# TAB 2 — DÉCOMPOSITION STL
# ════════════════════════════════════════════════════════════════════════════
with tab2:
    if HAS_STL and stl_res is not None:
        fig2 = make_subplots(
            rows=4, cols=1,
            shared_xaxes=True,
            row_heights=[0.30, 0.25, 0.25, 0.20],
            vertical_spacing=0.04,
            subplot_titles=[
                "Prix original (USD)",
                "Trend component",
                "Seasonal component",
                "Residual component"
            ]
        )

        # Row 1 : Prix original
        fig2.add_trace(go.Scatter(
            x=close.index, y=close.values,
            mode="lines", name="Prix",
            line=dict(color="#94a3b8", width=1.3),
            hovertemplate="<b>%{x|%d/%m/%y}</b><br>$%{y:,.2f}<extra></extra>"
        ), row=1, col=1)

        # Row 2 : Trend (log space)
        fig2.add_trace(go.Scatter(
            x=close.index, y=stl_res.trend,
            mode="lines", name="Trend",
            line=dict(color="#f1f5f9", width=1.8),
            hovertemplate="Trend : %{y:.4f}<extra></extra>"
        ), row=2, col=1)

        # Row 3 : Seasonal
        fig2.add_trace(go.Scatter(
            x=close.index, y=stl_res.seasonal,
            mode="lines", name="Seasonal",
            line=dict(color="#d1d5db", width=1.2),
            fill="tozeroy",
            fillcolor="rgba(209,213,219,0.06)",
            hovertemplate="Seasonal : %{y:.4f}<extra></extra>"
        ), row=3, col=1)
        fig2.add_hline(y=0, line_color="#2a2a2a", line_width=1, row=3, col=1)

        # Row 4 : Residual
        resid = stl_res.resid
        resid_colors = ["rgba(229,231,235,0.5)" if v >= 0 else "rgba(107,114,128,0.5)"
                        for v in resid]
        fig2.add_trace(go.Bar(
            x=close.index, y=resid,
            name="Residual",
            marker_color=resid_colors,
            hovertemplate="Résidu : %{y:.4f}<extra></extra>"
        ), row=4, col=1)
        fig2.add_hline(y=0, line_color="#333333", line_width=1, row=4, col=1)

        fig2.update_layout(
            height=700,
            title=dict(
                text=f"STL Decomposition SOL/USD — période={STL_PERIOD}j (saisonnalité hebdomadaire)",
                font=dict(size=13, color="#94a3b8", family="JetBrains Mono"),
                x=0.0
            ),
            showlegend=False,
            **DARK
        )
        fig2.update_xaxes(showgrid=False)
        fig2.update_yaxes(showgrid=True, gridcolor="#111111", zeroline=False)

        st.plotly_chart(fig2, use_container_width=True)

        st.markdown("""
**Comment lire cette décomposition :**
- **Trend** : direction de fond — c'est ce que le modèle trade
- **Seasonal** : cycle hebdomadaire répétitif du SOL (weekend/semaine)
- **Residual** : bruit pur — ce que le modèle ignore
""")

        # Stats rapides
        st.divider()
        st.markdown(
            '<div style="color:#444;font-size:.72rem;font-family:JetBrains Mono,monospace;'
            'letter-spacing:.1em;text-transform:uppercase;margin-bottom:.6rem;">Variance expliquée</div>',
            unsafe_allow_html=True
        )
        log_close = np.log(close.values.astype(float))
        total_var = np.var(log_close)
        trend_var = np.var(stl_res.trend) / total_var * 100 if total_var > 0 else 0
        seasonal_var = np.var(stl_res.seasonal) / total_var * 100 if total_var > 0 else 0
        resid_var = np.var(stl_res.resid) / total_var * 100 if total_var > 0 else 0

        sv1, sv2, sv3 = st.columns(3)
        for col, label, val, color in [
            (sv1, "Trend", trend_var, "#f1f5f9"),
            (sv2, "Seasonal", seasonal_var, "#d1d5db"),
            (sv3, "Residual", resid_var, "#6b7280"),
        ]:
            with col:
                st.markdown(
                    f'<div class="info-box">'
                    f'<div class="info-label">{label}</div>'
                    f'<div class="info-val" style="color:{color};">{val:.1f}%</div>'
                    f'</div>',
                    unsafe_allow_html=True
                )
    else:
        st.warning("STL non disponible. Installe `statsmodels` : `pip install statsmodels`")
        st.markdown("""
Le fallback EMA est actif :
- **Trend** : EMA lente (période × 3)
- **Signal** : EMA rapide > EMA lente + prix > EMA filtre
""")
        # Afficher quand même le graphe EMA fallback
        fig_fb = go.Figure()
        fig_fb.add_trace(go.Scatter(
            x=close.index, y=close.values,
            mode="lines", name="Prix",
            line=dict(color="#94a3b8", width=1.3)
        ))
        fig_fb.add_trace(go.Scatter(
            x=trend.index, y=trend.values,
            mode="lines", name=f"EMA Trend ({STL_PERIOD * 3})",
            line=dict(color="#f1f5f9", width=2.0)
        ))
        fig_fb.add_trace(go.Scatter(
            x=ema.index, y=ema.values,
            mode="lines", name=f"EMA Filtre ({EMA_FILTER})",
            line=dict(color="#4b5563", width=1.2, dash="dash")
        ))
        fig_fb.update_layout(height=400, **DARK)
        st.plotly_chart(fig_fb, use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════
# TAB 3 — ALERTES
# ════════════════════════════════════════════════════════════════════════════
with tab3:
    col_ntfy, col_discord = st.columns(2)

    with col_ntfy:
        st.markdown("### 📱 NTFY")
        ntfy_topic = st.text_input(
            "Topic NTFY",
            value=_NTFY_DEFAULT,
            placeholder="mon-topic-sol",
            key="ntfy_topic"
        )
        st.caption("Installe l'app NTFY sur ton téléphone → abonne-toi à ton topic")
        if st.button("🧪 Test NTFY"):
            ok = send_ntfy(
                ntfy_topic,
                "Test QuantMaster",
                f"SOL signal actuel : {'LONG' if is_long else 'FLAT'} @ ${current_price:.2f}"
            )
            if ok:
                st.success("✓ Envoyé")
            else:
                st.error("✗ Échec — vérifie le topic et la connexion")

    with col_discord:
        st.markdown("### 💬 Discord")
        discord_url = st.text_input(
            "Webhook URL",
            value=_DISCORD_DEFAULT,
            placeholder="https://discord.com/api/webhooks/...",
            key="discord_url",
            type="password"
        )
        st.caption("Discord → paramètres serveur → Intégrations → Webhooks")
        if st.button("🧪 Test Discord"):
            ok = send_discord(
                discord_url,
                f"**QuantMaster SOL** | Signal : {'🟢 LONG' if is_long else '⬜ FLAT'} @ ${current_price:.2f}"
            )
            if ok:
                st.success("✓ Envoyé")
            else:
                st.error("✗ Échec — vérifie l'URL webhook")

    st.divider()
    st.markdown("### ⚡ Auto-alerte sur changement de signal")

    last_sig = load_last_signal()
    if last_sig:
        sig_label = "LONG" if last_sig["signal"] > 0 else "FLAT"
        sig_color = "#e5e7eb" if last_sig["signal"] > 0 else "#6b7280"
        st.markdown(
            f'<div class="info-box" style="margin-bottom:.8rem;">'
            f'<div class="info-label">Dernier signal sauvegardé</div>'
            f'<div style="display:flex;gap:2rem;margin-top:.3rem;">'
            f'<span><span style="color:#444;font-size:.7rem;">SIGNAL&nbsp;</span>'
            f'<span style="color:{sig_color};font-weight:700;">{sig_label}</span></span>'
            f'<span><span style="color:#444;font-size:.7rem;">PRIX&nbsp;</span>'
            f'<span style="color:#94a3b8;font-weight:700;">${last_sig["price"]:,.2f}</span></span>'
            f'<span><span style="color:#444;font-size:.7rem;">DATE&nbsp;</span>'
            f'<span style="color:#4b5563;font-weight:700;">{last_sig["date"]}</span></span>'
            f'</div></div>',
            unsafe_allow_html=True
        )
    else:
        st.info("Aucun signal sauvegardé pour l'instant.")

    col_btn, col_chk = st.columns([1, 2])
    with col_btn:
        if st.button("🔄 Forcer vérification"):
            st.cache_data.clear()
            save_last_signal(current_signal, current_price, str(datetime.now().date()))
            st.success(f"Signal mis à jour : {'LONG' if is_long else 'FLAT'} @ ${current_price:.2f}")

    with col_chk:
        auto_alert = st.checkbox("Activer les alertes automatiques", key="auto_alert")

    if auto_alert:
        if alert_triggered:
            st.markdown(
                '<div style="background:rgba(229,231,235,.04);border:1px solid #e5e7eb;'
                'border-radius:8px;padding:.8rem 1rem;font-family:JetBrains Mono,monospace;'
                'font-size:.85rem;color:#e5e7eb;margin-top:.6rem;">'
                '⚡ Changement de signal détecté dans cette session — configurez NTFY ou Discord ci-dessus '
                'pour recevoir les prochaines alertes automatiquement.'
                '</div>',
                unsafe_allow_html=True
            )
            if ntfy_topic:
                msg = f"{'🟢 LONG' if is_long else '⬜ FLAT'} SOL/USD @ ${current_price:.2f}"
                title = "QuantMaster — Changement signal SOL"
                send_ntfy(ntfy_topic, title, msg, priority="high")
            if discord_url:
                msg = (f"**QuantMaster SOL** | Changement signal !\n"
                       f"{'🟢 LONG' if is_long else '⬜ FLAT'} @ ${current_price:.2f}")
                send_discord(discord_url, msg)
        else:
            st.success("✓ Surveillance active — aucun changement de signal depuis la dernière vérification")

    st.markdown(
        '<div style="color:#333;font-size:.68rem;font-family:JetBrains Mono,monospace;'
        'margin-top:1rem;">Note : les alertes automatiques nécessitent que l\'app soit ouverte dans le navigateur. '
        'Pour des alertes 24/7, déploie sur un serveur ou utilise un cron job.</div>',
        unsafe_allow_html=True
    )

# ════════════════════════════════════════════════════════════════════════════
# TAB 4 — OPTIMISATION 3D
# ════════════════════════════════════════════════════════════════════════════
with tab4:
    st.markdown(
        '<div style="color:#444;font-size:.72rem;font-family:JetBrains Mono,monospace;'
        'letter-spacing:.1em;text-transform:uppercase;margin-bottom:.8rem;">'
        'Surface Sharpe — STL Période × EMA Filtre</div>',
        unsafe_allow_html=True
    )

    col_ng, col_run = st.columns([3, 1])
    with col_ng:
        n_grid = st.slider("Résolution grille N×N", 5, 12, 8, key="sol_opt_n")
    with col_run:
        st.markdown("<div style='height:1.8rem'></div>", unsafe_allow_html=True)
        run_opt = st.button("⚡ Lancer optimisation", key="sol_opt_run")

    if run_opt:
        st.session_state.pop("_sol_opt_results", None)
        st.session_state["_sol_opt_run"] = True

    if not st.session_state.get("_sol_opt_run", False):
        st.info("Lance l'optimisation pour afficher la surface 3D.")
    else:
        if "_sol_opt_results" not in st.session_state:
            periods = np.linspace(3, 20, n_grid).astype(int)
            emas    = np.linspace(3, 30, n_grid).astype(int)
            periods = sorted(set(periods))
            emas    = sorted(set(emas))

            sharpe_grid = np.full((len(periods), len(emas)), np.nan)

            bar = st.progress(0, text="Optimisation en cours…")
            total = len(periods) * len(emas)
            done  = 0

            for i, p in enumerate(periods):
                for j, e in enumerate(emas):
                    try:
                        sig, _, _, _ = compute_stl_signal(close, int(p), int(e))
                        rets = close.pct_change().fillna(0)
                        strat_rets = sig.shift(1).fillna(0) * rets
                        strat_rets = strat_rets - 0.001 * sig.diff().abs().fillna(0)
                        if strat_rets.std() > 1e-9:
                            sh = (strat_rets.mean() / strat_rets.std()) * np.sqrt(365)
                        else:
                            sh = 0.0
                        sharpe_grid[i, j] = float(np.clip(sh, -3, 6))
                    except Exception:
                        sharpe_grid[i, j] = 0.0
                    done += 1
                    bar.progress(done / total, text=f"Optimisation… {done}/{total}")

            bar.empty()
            st.session_state["_sol_opt_results"] = {
                "periods": periods, "emas": emas, "grid": sharpe_grid
            }

        res = st.session_state["_sol_opt_results"]
        periods  = res["periods"]
        emas     = res["emas"]
        Z        = res["grid"]

        # ── Surface 3D ──
        fig3d = go.Figure(data=[go.Surface(
            x=emas,
            y=periods,
            z=Z,
            colorscale=[
                [0.0,  "#050505"],
                [0.25, "#1a1a2e"],
                [0.5,  "#4b5563"],
                [0.75, "#9ca3af"],
                [1.0,  "#f1f5f9"],
            ],
            colorbar=dict(
                title=dict(text="Sharpe", font=dict(color="#94a3b8", size=11)),
                tickfont=dict(color="#94a3b8", size=10),
                thickness=14, len=0.7
            ),
            hovertemplate=(
                "<b>STL période : %{y}</b><br>"
                "EMA filtre : %{x}<br>"
                "Sharpe : %{z:.2f}<extra></extra>"
            ),
            opacity=0.92,
        )])

        # Marque le point optimal validé (période=5, EMA=10)
        opt_idx_p = min(range(len(periods)), key=lambda i: abs(periods[i] - STL_PERIOD))
        opt_idx_e = min(range(len(emas)),    key=lambda i: abs(emas[i]    - EMA_FILTER))
        opt_z     = Z[opt_idx_p, opt_idx_e]

        fig3d.add_trace(go.Scatter3d(
            x=[EMA_FILTER], y=[STL_PERIOD], z=[opt_z + 0.15],
            mode="markers+text",
            marker=dict(size=8, color="#f1f5f9", symbol="diamond"),
            text=["★ Optimal"],
            textfont=dict(color="#f1f5f9", size=11, family="JetBrains Mono"),
            textposition="top center",
            name="Paramètres actifs",
            hovertemplate=f"Optimal validé<br>période={STL_PERIOD} · EMA={EMA_FILTER}<br>Sharpe={opt_z:.2f}<extra></extra>"
        ))

        # Pic absolu
        flat_idx = np.nanargmax(Z)
        pi, ei   = np.unravel_index(flat_idx, Z.shape)
        best_p, best_e, best_sh = periods[pi], emas[ei], Z[pi, ei]

        fig3d.add_trace(go.Scatter3d(
            x=[best_e], y=[best_p], z=[best_sh + 0.15],
            mode="markers+text",
            marker=dict(size=8, color="#e5e7eb", symbol="circle"),
            text=["▲ Pic"],
            textfont=dict(color="#e5e7eb", size=11, family="JetBrains Mono"),
            textposition="top center",
            name="Pic Sharpe",
            hovertemplate=f"Pic Sharpe<br>période={best_p} · EMA={best_e}<br>Sharpe={best_sh:.2f}<extra></extra>"
        ))

        fig3d.update_layout(
            height=620,
            scene=dict(
                xaxis=dict(title="EMA Filtre", backgroundcolor="#050505",
                           gridcolor="#1a1a1a", color="#94a3b8"),
                yaxis=dict(title="STL Période", backgroundcolor="#050505",
                           gridcolor="#1a1a1a", color="#94a3b8"),
                zaxis=dict(title="Sharpe annualisé", backgroundcolor="#050505",
                           gridcolor="#1a1a1a", color="#94a3b8"),
                bgcolor="#050505",
                camera=dict(eye=dict(x=1.5, y=-1.8, z=0.9)),
            ),
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#94a3b8", size=11, family="JetBrains Mono,monospace"),
            margin=dict(t=24, b=16, l=0, r=0),
            legend=dict(font=dict(size=10, color="#94a3b8"), bgcolor="rgba(0,0,0,0)"),
        )

        st.plotly_chart(fig3d, use_container_width=True)

        # ── Résumé ──
        c1, c2, c3 = st.columns(3)
        for col, label, val, color in [
            (c1, "Paramètres actifs", f"période={STL_PERIOD} · EMA={EMA_FILTER}", "#f1f5f9"),
            (c2, "Sharpe actifs",     f"{opt_z:.2f}",   "#d1d5db"),
            (c3, "Pic absolu grille", f"période={best_p} · EMA={best_e} → {best_sh:.2f}", "#9ca3af"),
        ]:
            with col:
                st.markdown(
                    f'<div class="info-box">'
                    f'<div class="info-label">{label}</div>'
                    f'<div class="info-val" style="color:{color};font-size:.95rem;">{val}</div>'
                    f'</div>',
                    unsafe_allow_html=True
                )

        if abs(best_p - STL_PERIOD) > 2 or abs(best_e - EMA_FILTER) > 5:
            st.info(
                f"Le pic de la grille ({best_p}/{best_e}) diffère de tes paramètres validés ({STL_PERIOD}/{EMA_FILTER}). "
                "Les paramètres actifs viennent du backtest walk-forward — ils restent prioritaires."
            )
        else:
            st.success("Tes paramètres actifs sont proches du pic de la surface ✓")


# ════════════════════════════════════════════════════════════════════════════
# TAB 5 — JOURNAL SOL
# ════════════════════════════════════════════════════════════════════════════
with tab5:
    st.markdown(
        '<div style="color:#444;font-size:.72rem;font-family:JetBrains Mono,monospace;'
        'letter-spacing:.1em;text-transform:uppercase;margin-bottom:1rem;">'
        'Journal automatique — SOL × STL Decomposition</div>',
        unsafe_allow_html=True
    )

    # ── Config position ──
    jc1, jc2, jc3 = st.columns(3)
    with jc1:
        j_capital  = st.number_input("Capital ($)", min_value=10.0, value=500.0,
                                     step=50.0, key="j_capital")
    with jc2:
        j_leverage = st.number_input("Levier ×", min_value=1.0, max_value=5.0,
                                     value=2.0, step=0.5, key="j_leverage")
    with jc3:
        j_notes = st.text_input("Notes", placeholder="optionnel", key="j_notes")

    col_open, col_close, col_refresh = st.columns(3)
    with col_open:
        if st.button("✚ Enregistrer entrée LONG", key="j_open"):
            journal_open_trade(
                entry_price=current_price,
                capital=j_capital,
                leverage=j_leverage,
                date_entry=str(datetime.now().date())
            )
            st.success(f"Entrée enregistrée @ ${current_price:.2f}")
            st.cache_data.clear()

    with col_close:
        if st.button("✖ Enregistrer sortie FLAT", key="j_close"):
            journal_close_trade(
                exit_price=current_price,
                date_exit=str(datetime.now().date())
            )
            st.success(f"Sortie enregistrée @ ${current_price:.2f}")
            st.cache_data.clear()

    with col_refresh:
        if st.button("↺ Rafraîchir", key="j_reload"):
            st.cache_data.clear()

    # ── Auto-enregistrement sur changement de signal ──
    if alert_triggered and last:
        prev_sig = last["signal"]
        prev_price = last["price"]
        if prev_sig == 0 and current_signal == 1:
            # FLAT → LONG : entrée automatique
            journal_open_trade(
                entry_price=current_price,
                capital=j_capital,
                leverage=j_leverage,
                date_entry=str(datetime.now().date())
            )
            st.info(f"Auto-journal : entrée LONG enregistrée @ ${current_price:.2f}")
        elif prev_sig == 1 and current_signal == 0:
            # LONG → FLAT : sortie automatique
            journal_close_trade(
                exit_price=current_price,
                date_exit=str(datetime.now().date())
            )
            st.info(f"Auto-journal : sortie FLAT enregistrée @ ${current_price:.2f}")

    st.markdown("<div style='height:.6rem'></div>", unsafe_allow_html=True)

    # ── Chargement trades ──
    df_j = journal_load()

    if df_j.empty:
        st.markdown(
            '<div style="text-align:center;padding:2rem;color:#333;'
            'font-family:JetBrains Mono,monospace;font-size:.85rem;">'
            'Aucun trade enregistré — clique sur "Enregistrer entrée LONG" pour commencer.'
            '</div>',
            unsafe_allow_html=True
        )
    else:
        # ── Stats globales ──
        closed = df_j[df_j["status"] == "CLOSED"]
        open_t = df_j[df_j["status"] == "OPEN"]

        s1, s2, s3, s4, s5 = st.columns(5)
        total_pnl = closed["pnl_usd"].sum() if not closed.empty else 0.0
        wins      = (closed["pnl_usd"] > 0).sum() if not closed.empty else 0
        total_cl  = len(closed)
        wr        = wins / total_cl * 100 if total_cl > 0 else 0.0
        avg_dur   = closed["duration_days"].mean() if not closed.empty else 0.0

        for col, label, val, color in [
            (s1, "Trades fermés",  str(total_cl),           "#94a3b8"),
            (s2, "Win Rate",       f"{wr:.1f}%",            "#e5e7eb" if wr >= 50 else "#6b7280"),
            (s3, "PnL total $",    f"{'+'if total_pnl>=0 else ''}{total_pnl:.2f}",
                                                             "#e5e7eb" if total_pnl >= 0 else "#6b7280"),
            (s4, "Durée moy.",     f"{avg_dur:.0f}j",       "#94a3b8"),
            (s5, "Open",           str(len(open_t)),         "#d1d5db"),
        ]:
            with col:
                st.markdown(
                    f'<div class="info-box">'
                    f'<div class="info-label">{label}</div>'
                    f'<div class="info-val" style="color:{color};">{val}</div>'
                    f'</div>', unsafe_allow_html=True
                )

        st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)

        # ── Trade ouvert actuel ──
        if not open_t.empty:
            ot = open_t.iloc[0]
            ep = ot["entry_price"]
            lv = ot["leverage"]
            cap = ot["capital"]
            unreal_pct = (current_price / ep - 1) * lv * 100 if ep else 0
            unreal_usd = unreal_pct / 100 * cap
            unreal_color = "#e5e7eb" if unreal_pct >= 0 else "#6b7280"
            st.markdown(
                f'<div style="background:rgba(229,231,235,0.03);border:1px solid rgba(255,255,255,0.08);'
                f'border-radius:10px;padding:1rem 1.2rem;font-family:JetBrains Mono,monospace;'
                f'margin-bottom:1rem;">'
                f'<div style="color:#444;font-size:.6rem;letter-spacing:.15em;'
                f'text-transform:uppercase;margin-bottom:.5rem;">Trade ouvert</div>'
                f'<div style="display:flex;gap:2.5rem;flex-wrap:wrap;">'
                f'<span><span style="color:#444;font-size:.7rem;">ENTRÉE </span>'
                f'<span style="color:#f1f5f9;font-weight:700;">${ep:,.2f}</span></span>'
                f'<span><span style="color:#444;font-size:.7rem;">ACTUEL </span>'
                f'<span style="color:#f1f5f9;font-weight:700;">${current_price:,.2f}</span></span>'
                f'<span><span style="color:#444;font-size:.7rem;">LEVIER </span>'
                f'<span style="color:#94a3b8;font-weight:700;">×{lv:.1f}</span></span>'
                f'<span><span style="color:#444;font-size:.7rem;">PnL LATENT </span>'
                f'<span style="color:{unreal_color};font-weight:700;">'
                f'{"+"if unreal_pct>=0 else ""}{unreal_pct:.2f}% '
                f'({"+"if unreal_usd>=0 else ""}${unreal_usd:.2f})</span></span>'
                f'<span><span style="color:#444;font-size:.7rem;">DEPUIS </span>'
                f'<span style="color:#4b5563;font-weight:700;">{ot["date_entry"]}</span></span>'
                f'</div></div>',
                unsafe_allow_html=True
            )

        # ── Equity curve ──
        if not closed.empty:
            eq = closed.sort_values("date_entry")["pnl_usd"].cumsum().values
            fig_eq = go.Figure()
            fig_eq.add_trace(go.Scatter(
                y=eq, mode="lines+markers",
                line=dict(color="#d1d5db", width=2),
                marker=dict(size=5, color=["#e5e7eb" if v >= 0 else "#4b5563" for v in eq]),
                fill="tozeroy",
                fillcolor="rgba(209,213,219,0.05)",
                hovertemplate="Trade %{x}<br>PnL cumulé : $%{y:.2f}<extra></extra>"
            ))
            fig_eq.update_layout(
                height=220,
                title=dict(text="Equity curve SOL", font=dict(size=11, color="#94a3b8"), x=0),
                xaxis=dict(showgrid=False, color="#333"),
                yaxis=dict(showgrid=True, gridcolor="#111", color="#94a3b8"),
                **{k: v for k, v in DARK.items() if k != "margin"},
                margin=dict(t=36, b=24, l=48, r=12),
            )
            st.plotly_chart(fig_eq, use_container_width=True)

        # ── Historique ──
        st.markdown(
            '<div style="color:#444;font-size:.65rem;font-family:JetBrains Mono,monospace;'
            'letter-spacing:.12em;text-transform:uppercase;margin:.6rem 0 .4rem;">Historique</div>',
            unsafe_allow_html=True
        )

        for _, row in df_j.iterrows():
            status_color = "#4b5563" if row["status"] == "OPEN" else (
                "#e5e7eb" if (row["pnl_usd"] or 0) >= 0 else "#6b7280"
            )
            pnl_str = (
                f'{"+"if row["pnl_usd"]>=0 else ""}{row["pnl_usd"]:.2f}$'
                if row["status"] == "CLOSED" and row["pnl_usd"] is not None
                else "OUVERT"
            )
            pnl_pct_str = (
                f' ({("+"if row["pnl_pct"]>=0 else "")}{row["pnl_pct"]:.2f}%)'
                if row["status"] == "CLOSED" and row["pnl_pct"] is not None
                else ""
            )
            dur_str = f'{int(row["duration_days"])}j' if row["duration_days"] is not None else "--"
            exit_str = f'→ ${row["exit_price"]:,.2f}' if row["exit_price"] else ""

            col_row, col_del = st.columns([10, 1])
            with col_row:
                st.markdown(
                    f'<div style="background:#060606;border:1px solid #111;border-radius:8px;'
                    f'padding:.5rem 1rem;margin-bottom:.3rem;font-family:JetBrains Mono,monospace;'
                    f'font-size:.78rem;display:flex;gap:2rem;align-items:center;flex-wrap:wrap;">'
                    f'<span style="color:#333;">#{int(row["id"])}</span>'
                    f'<span style="color:#4b5563;">{row["date_entry"]}</span>'
                    f'<span style="color:#94a3b8;">${row["entry_price"]:,.2f} {exit_str}</span>'
                    f'<span style="color:#555;">×{row["leverage"]:.1f}</span>'
                    f'<span style="color:{status_color};font-weight:700;">{pnl_str}{pnl_pct_str}</span>'
                    f'<span style="color:#333;">{dur_str}</span>'
                    f'</div>',
                    unsafe_allow_html=True
                )
            with col_del:
                if st.button("✕", key=f"del_{row['id']}"):
                    journal_delete(int(row["id"]))
                    st.rerun()


# ════════════════════════════════════════════════════════════════════════════
# TAB 6 — WALK-FORWARD VALIDATION
# ════════════════════════════════════════════════════════════════════════════
with tab6:
    st.markdown(
        '<div style="color:#444;font-size:.72rem;font-family:JetBrains Mono,monospace;'
        'letter-spacing:.1em;text-transform:uppercase;margin-bottom:.8rem;">'
        'Walk-Forward — SOL × STL · période=5 · EMA=10 · validation hors-échantillon</div>',
        unsafe_allow_html=True
    )

    wf_col1, wf_col2, wf_col3 = st.columns(3)
    with wf_col1:
        wf_train = st.slider("Fenêtre train (jours)", 90, 365, 252, key="wf_train")
    with wf_col2:
        wf_test  = st.slider("Fenêtre test (jours)",  30, 180,  90, key="wf_test")
    with wf_col3:
        wf_comm  = st.slider("Commission (%)", 0.0, 0.5, 0.1, 0.05, key="wf_comm")

    wf_run = st.button("⚡ Lancer Walk-Forward", key="wf_run_btn")
    if wf_run:
        st.session_state.pop("_wf_results", None)
        st.session_state["_wf_run"] = True

    if not st.session_state.get("_wf_run", False):
        st.info("Configure les fenêtres et lance le Walk-Forward.")
    else:
        if "_wf_results" not in st.session_state:
            n = len(close)
            comm = wf_comm / 100
            windows = []
            start = wf_train

            prog = st.progress(0, text="Walk-Forward en cours…")
            total_w = max(1, (n - wf_train) // wf_test)
            done_w  = 0

            while start + wf_test <= n:
                # Signal calculé sur train + test (STL a besoin d'historique)
                w_close = close.iloc[:start + wf_test]
                w_sig, _, _, _ = compute_stl_signal(w_close, STL_PERIOD, EMA_FILTER)

                # Évaluation sur fenêtre test uniquement
                t_close = w_close.iloc[start:]
                t_sig   = w_sig.iloc[start:]
                rets    = t_close.pct_change().fillna(0)
                s_rets  = t_sig.shift(1).fillna(0) * rets
                s_rets  = s_rets - comm * t_sig.diff().abs().fillna(0)

                sharpe = (s_rets.mean() / s_rets.std() * np.sqrt(365)
                          if s_rets.std() > 1e-9 else 0.0)
                total_ret  = float((1 + s_rets).prod() - 1) * 100
                n_trades   = int((t_sig.diff().abs() > 0.5).sum() // 2)
                trade_rets = [float(s_rets.iloc[i]) for i in range(len(s_rets)) if abs(float(t_sig.diff().iloc[i])) > 0.5]
                win_r      = sum(1 for r in trade_rets if r > 0) / max(len(trade_rets), 1) * 100

                dd_series = (1 + s_rets).cumprod()
                roll_max  = dd_series.cummax()
                max_dd    = float(((dd_series - roll_max) / roll_max).min()) * 100

                windows.append({
                    "Période":    f"{t_close.index[0].strftime('%b %y')} → {t_close.index[-1].strftime('%b %y')}",
                    "date_start": t_close.index[0],
                    "Sharpe":     round(float(sharpe), 2),
                    "Return %":   round(total_ret, 1),
                    "Max DD %":   round(max_dd, 1),
                    "Trades":     n_trades,
                    "WR %":       round(win_r, 1),
                    "Pass":       sharpe > 0.5 and total_ret > 0,
                })

                start  += wf_test
                done_w += 1
                prog.progress(min(done_w / total_w, 1.0))

            prog.empty()
            st.session_state["_wf_results"] = windows

        windows = st.session_state["_wf_results"]
        df_wf   = pd.DataFrame(windows)

        # ── Résumé global ──
        n_pass   = df_wf["Pass"].sum()
        n_total  = len(df_wf)
        avg_sh   = df_wf["Sharpe"].mean()
        avg_ret  = df_wf["Return %"].mean()
        avg_dd   = df_wf["Max DD %"].mean()
        consistency = n_pass / n_total * 100 if n_total > 0 else 0

        wm1, wm2, wm3, wm4, wm5 = st.columns(5)
        for col, label, val, color in [
            (wm1, "Fenêtres",      str(n_total),              "#94a3b8"),
            (wm2, "Consistance",   f"{consistency:.0f}%",     "#e5e7eb" if consistency >= 60 else "#6b7280"),
            (wm3, "Sharpe moyen",  f"{avg_sh:.2f}",           "#e5e7eb" if avg_sh > 0.5 else "#6b7280"),
            (wm4, "Return moyen",  f"{avg_ret:+.1f}%",        "#e5e7eb" if avg_ret > 0 else "#6b7280"),
            (wm5, "DD moyen",      f"{avg_dd:.1f}%",          "#9ca3af"),
        ]:
            with col:
                st.markdown(
                    f'<div class="info-box">'
                    f'<div class="info-label">{label}</div>'
                    f'<div class="info-val" style="color:{color};">{val}</div>'
                    f'</div>', unsafe_allow_html=True
                )

        verdict_color = "#e5e7eb" if consistency >= 60 else "#6b7280"
        verdict_txt   = "MODÈLE ROBUSTE ✓" if consistency >= 60 else "MODÈLE FRAGILE ⚠"
        st.markdown(
            f'<div style="text-align:center;padding:.8rem;margin:.8rem 0;'
            f'border:1px solid rgba(255,255,255,0.08);border-radius:10px;">'
            f'<span style="font-family:JetBrains Mono,monospace;font-size:1rem;'
            f'font-weight:700;color:{verdict_color};letter-spacing:.1em;">{verdict_txt}</span>'
            f'<span style="color:#333;font-size:.75rem;font-family:JetBrains Mono,monospace;'
            f' margin-left:1rem;">{n_pass}/{n_total} fenêtres positives</span>'
            f'</div>', unsafe_allow_html=True
        )

        # ── Graphique Sharpe par fenêtre ──
        colors_bar = ["rgba(229,231,235,0.7)" if r else "rgba(75,85,99,0.5)"
                      for r in df_wf["Pass"]]
        fig_wf = make_subplots(rows=2, cols=1, shared_xaxes=True,
                               row_heights=[0.6, 0.4], vertical_spacing=0.06,
                               subplot_titles=["Sharpe par fenêtre test", "Return % par fenêtre"])

        fig_wf.add_trace(go.Bar(
            x=df_wf["Période"], y=df_wf["Sharpe"],
            marker_color=colors_bar,
            hovertemplate="<b>%{x}</b><br>Sharpe : %{y:.2f}<extra></extra>",
            name="Sharpe"
        ), row=1, col=1)
        fig_wf.add_hline(y=0.5, line_color="#4b5563", line_dash="dash",
                         line_width=1, row=1, col=1)
        fig_wf.add_hline(y=0,   line_color="#333",    line_width=1, row=1, col=1)

        ret_colors = ["rgba(229,231,235,0.6)" if v > 0 else "rgba(75,85,99,0.5)"
                      for v in df_wf["Return %"]]
        fig_wf.add_trace(go.Bar(
            x=df_wf["Période"], y=df_wf["Return %"],
            marker_color=ret_colors,
            hovertemplate="<b>%{x}</b><br>Return : %{y:+.1f}%<extra></extra>",
            name="Return %"
        ), row=2, col=1)
        fig_wf.add_hline(y=0, line_color="#333", line_width=1, row=2, col=1)

        fig_wf.update_layout(
            height=480, showlegend=False,
            **{k: v for k, v in DARK.items() if k != "margin"},
            margin=dict(t=40, b=24, l=52, r=16),
        )
        fig_wf.update_xaxes(showgrid=False, tickangle=-35, tickfont=dict(size=9))
        fig_wf.update_yaxes(showgrid=True, gridcolor="#111111")
        st.plotly_chart(fig_wf, use_container_width=True)

        # ── Tableau détail ──
        st.markdown(
            '<div style="color:#444;font-size:.65rem;font-family:JetBrains Mono,monospace;'
            'letter-spacing:.12em;text-transform:uppercase;margin:.4rem 0;">Détail par fenêtre</div>',
            unsafe_allow_html=True
        )
        for _, r in df_wf.iterrows():
            ok_color = "#e5e7eb" if r["Pass"] else "#4b5563"
            ok_icon  = "✓" if r["Pass"] else "✗"
            st.markdown(
                f'<div style="background:#060606;border:1px solid #111;border-radius:7px;'
                f'padding:.45rem 1rem;margin-bottom:.25rem;font-family:JetBrains Mono,monospace;'
                f'font-size:.76rem;display:flex;gap:2rem;flex-wrap:wrap;">'
                f'<span style="color:{ok_color};font-weight:700;min-width:1rem;">{ok_icon}</span>'
                f'<span style="color:#94a3b8;min-width:12rem;">{r["Période"]}</span>'
                f'<span><span style="color:#333;">Sharpe </span>'
                f'<span style="color:{"#e5e7eb" if r["Sharpe"]>0.5 else "#6b7280"};font-weight:700;">'
                f'{r["Sharpe"]:.2f}</span></span>'
                f'<span><span style="color:#333;">Ret </span>'
                f'<span style="color:{"#e5e7eb" if r["Return %"]>0 else "#6b7280"};font-weight:700;">'
                f'{r["Return %"]:+.1f}%</span></span>'
                f'<span><span style="color:#333;">DD </span>'
                f'<span style="color:#6b7280;">{r["Max DD %"]:.1f}%</span></span>'
                f'<span><span style="color:#333;">WR </span>'
                f'<span style="color:#94a3b8;">{r["WR %"]:.0f}%</span></span>'
                f'<span><span style="color:#333;">Trades </span>'
                f'<span style="color:#4b5563;">{r["Trades"]}</span></span>'
                f'</div>', unsafe_allow_html=True
            )

        if consistency < 60:
            st.warning(
                f"Consistance {consistency:.0f}% < 60% — les paramètres période=5/EMA=10 "
                "ne tiennent pas uniformément hors-échantillon. "
                "Considère d'agrandir la fenêtre train ou de réoptimiser."
            )


# ─── AUTO-REFRESH ────────────────────────────────────────────────────────────
try:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=3_600_000, key="sol_live_refresh")
except ImportError:
    st.markdown(
        '<div style="color:#333;font-size:.65rem;font-family:JetBrains Mono,monospace;'
        'text-align:right;margin-top:1rem;">'
        'Auto-refresh désactivé — installe streamlit-autorefresh pour l\'activer'
        '</div>',
        unsafe_allow_html=True
    )