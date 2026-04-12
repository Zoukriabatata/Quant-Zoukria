import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import yfinance as yf
import requests
from datetime import datetime

# ── Page config ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="BTC DCA · Quant Maths",
    page_icon="₿",
    layout="wide",
)
from styles import inject as _inj; _inj()

# ── CSS ────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;700&display=swap');

* { box-sizing: border-box; }
[data-testid="stAppViewContainer"] { background: #060606; font-family: 'Space Grotesk', sans-serif; }
[data-testid="stSidebar"]         { background: #0a0a0a; border-right: 1px solid #1a1a1a; }
[data-testid="stHeader"]          { background: transparent; }
[data-testid="stToolbar"]         { display: none; }
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: #0a0a0a; }
::-webkit-scrollbar-thumb { background: #F7931A; border-radius: 2px; }

.page-header {
    padding: 2rem 0 1rem;
    border-bottom: 1px solid #1a1a1a;
    margin-bottom: 2rem;
}
.page-tag {
    display: inline-block;
    padding: 0.3rem 1rem;
    border: 1px solid rgba(247,147,26,0.4);
    border-radius: 999px;
    font-size: 0.7rem;
    letter-spacing: 0.2em;
    color: #F7931A;
    margin-bottom: 1rem;
    font-family: 'JetBrains Mono', monospace;
}
.page-title {
    font-size: 2rem;
    font-weight: 700;
    color: #fff;
    margin: 0;
    letter-spacing: -0.02em;
}
.page-title span {
    background: linear-gradient(135deg, #F7931A 0%, #FFD700 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}
.page-sub { color: #444; font-size: 0.85rem; font-family: 'JetBrains Mono', monospace; margin-top: 0.4rem; }

/* Signal badge */
.signal-wrap { display: flex; justify-content: center; margin: 1.5rem 0; }
.signal-badge {
    padding: 1.2rem 3rem;
    border-radius: 12px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.6rem;
    font-weight: 700;
    letter-spacing: 0.15em;
    text-align: center;
}
.signal-strong-buy { background: rgba(0,255,100,0.08); border: 2px solid #00ff64; color: #00ff64; }
.signal-buy        { background: rgba(247,147,26,0.08); border: 2px solid #F7931A; color: #F7931A; }
.signal-neutral    { background: rgba(100,100,100,0.08); border: 2px solid #444; color: #888; }
.signal-wait       { background: rgba(255,50,50,0.08);  border: 2px solid #ff4444; color: #ff4444; }

/* Metric cards */
.metrics-row { display: flex; gap: 1px; background: #111; border: 1px solid #111; border-radius: 12px; overflow: hidden; margin: 1rem 0; }
.metric-card { flex: 1; background: #060606; padding: 1.2rem 1.5rem; text-align: center; }
.metric-card:hover { background: #0c0c0c; }
.metric-label { font-size: 0.62rem; color: #444; letter-spacing: 0.15em; text-transform: uppercase; font-family: 'JetBrains Mono', monospace; }
.metric-value { font-size: 1.6rem; font-weight: 700; font-family: 'JetBrains Mono', monospace; margin: 0.3rem 0 0; }
.metric-sub   { font-size: 0.7rem; color: #555; margin-top: 0.1rem; }
.col-orange { color: #F7931A; }
.col-green  { color: #00ff64; }
.col-red    { color: #ff4444; }
.col-teal   { color: #3CC4B7; }
.col-white  { color: #fff; }

/* DCA table */
.dca-table {
    background: #0a0a0a;
    border: 1px solid #1a1a1a;
    border-radius: 12px;
    padding: 1.5rem;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.82rem;
}
.dca-row { display: flex; justify-content: space-between; padding: 0.5rem 0; border-bottom: 1px solid #111; }
.dca-row:last-child { border-bottom: none; }
.dca-key  { color: #555; }
.dca-val  { color: #ccc; font-weight: 700; }
.dca-val-orange { color: #F7931A; font-weight: 700; }
.dca-val-green  { color: #00ff64; font-weight: 700; }
.dca-val-red    { color: #ff4444; font-weight: 700; }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════
#  DATA
# ══════════════════════════════════════════════════════════════════

@st.cache_data(ttl=300)
def fetch_btc(period="2y"):
    df = yf.download("BTC-USD", period=period, interval="1d", progress=False, auto_adjust=True)
    df = df[["Close"]].dropna()
    df.columns = ["close"]
    return df

@st.cache_data(ttl=3600)
def fetch_fear_greed(limit=90):
    try:
        url = f"https://api.alternative.me/fng/?limit={limit}&format=json"
        r = requests.get(url, timeout=8)
        data = r.json()["data"]
        fg = pd.DataFrame(data)
        fg["timestamp"] = pd.to_datetime(fg["timestamp"].astype(int), unit="s")
        fg["value"] = fg["value"].astype(int)
        fg = fg.sort_values("timestamp").reset_index(drop=True)
        return fg
    except Exception:
        return None

# ══════════════════════════════════════════════════════════════════
#  SIGNAL ENGINE
# ══════════════════════════════════════════════════════════════════

def compute_signals(df, vol_window=30, z_window=90):
    df = df.copy()
    df["ret"]      = df["close"].pct_change()
    df["rv30"]     = df["ret"].rolling(vol_window).std() * np.sqrt(252)   # annualized
    df["rv90_avg"] = df["rv30"].rolling(z_window).mean()
    df["vol_ratio"] = df["rv30"] / df["rv90_avg"]

    df["ma90"]    = df["close"].rolling(z_window).mean()
    df["std90"]   = df["close"].rolling(z_window).std()
    df["z_score"] = (df["close"] - df["ma90"]) / df["std90"]

    df["bb_upper"] = df["ma90"] + 2 * df["std90"]
    df["bb_lower"] = df["ma90"] - 2 * df["std90"]
    return df

def get_dca_signal(vol_ratio, z_score, fg_value):
    """
    Returns (signal_str, css_class, multiplier, reason)
    Signals inspired by Quant Guild volatility regime approach.
    """
    vol_high  = vol_ratio  > 1.25
    vol_mod   = vol_ratio  > 1.05
    oversold  = z_score    < -1.0
    dip       = z_score    < -0.4
    ext_fear  = fg_value   < 25
    fear      = fg_value   < 45
    greed     = fg_value   > 65
    ext_greed = fg_value   > 80

    if ext_greed and not oversold:
        return "WAIT", "signal-wait", 0.0, "Extreme Greed — skip cette semaine"
    if vol_high and oversold and (fear or ext_fear):
        return "STRONG BUY", "signal-strong-buy", 3.0, "Vol élevée + dip + Fear → triple dose"
    if (vol_high and oversold) or (ext_fear and dip):
        return "STRONG BUY", "signal-strong-buy", 2.0, "2 conditions réunies → double dose"
    if vol_mod or dip or fear:
        return "BUY", "signal-buy", 1.0, "1 condition → dose standard"
    return "NEUTRAL", "signal-neutral", 0.5, "Marché calme → demi-dose ou passer"

# ══════════════════════════════════════════════════════════════════
#  ALERTS
# ══════════════════════════════════════════════════════════════════

def send_discord(webhook_url, signal, price, vol_ratio, z_score, fg_val, fg_label, amount):
    colors = {"STRONG BUY": 0x00FF64, "BUY": 0xF7931A, "NEUTRAL": 0x888888, "WAIT": 0xFF4444}
    color  = colors.get(signal, 0xFFFFFF)
    embed  = {
        "embeds": [{
            "title": f"₿ BTC DCA — {signal}",
            "color": color,
            "fields": [
                {"name": "Prix BTC",      "value": f"${price:,.0f}",        "inline": True},
                {"name": "Signal",        "value": signal,                   "inline": True},
                {"name": "Montant DCA",   "value": f"${amount:.0f} USDT",   "inline": True},
                {"name": "Vol Ratio",     "value": f"{vol_ratio:.2f}x",     "inline": True},
                {"name": "Z-Score",       "value": f"{z_score:.2f}",        "inline": True},
                {"name": "Fear & Greed",  "value": f"{fg_val} ({fg_label})","inline": True},
            ],
            "footer": {"text": f"Quant Maths · BTC DCA Model · {datetime.now().strftime('%Y-%m-%d %H:%M')}"},
        }]
    }
    try:
        r = requests.post(webhook_url, json=embed, timeout=8)
        return r.status_code == 204
    except Exception as e:
        st.error(f"Discord: {e}")
        return False

def send_telegram(token, chat_id, signal, price, vol_ratio, z_score, fg_val, fg_label, amount):
    icons = {"STRONG BUY": "🟢🟢🟢", "BUY": "🟠", "NEUTRAL": "⚪", "WAIT": "🔴"}
    icon  = icons.get(signal, "")
    text  = (
        f"{icon} *BTC DCA — {signal}*\n\n"
        f"💰 Prix: `${price:,.0f}`\n"
        f"📊 Vol Ratio: `{vol_ratio:.2f}x`\n"
        f"📉 Z-Score: `{z_score:.2f}`\n"
        f"😨 Fear & Greed: `{fg_val} ({fg_label})`\n"
        f"💵 Montant: `${amount:.0f} USDT`\n\n"
        f"_Quant Maths · {datetime.now().strftime('%Y-%m-%d %H:%M')}_"
    )
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        r = requests.post(url, data={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}, timeout=8)
        return r.ok
    except Exception as e:
        st.error(f"Telegram: {e}")
        return False

# ══════════════════════════════════════════════════════════════════
#  CHARTS
# ══════════════════════════════════════════════════════════════════

CHART_BG    = "#060606"
GRID_COLOR  = "#111111"
BTC_COLOR   = "#F7931A"
MA_COLOR    = "#3CC4B7"
BB_COLOR    = "rgba(60,196,183,0.12)"

def chart_price(df):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df.index, y=df["bb_upper"], mode="lines",
        line=dict(color="rgba(60,196,183,0.3)", width=1, dash="dot"),
        name="BB Upper", showlegend=False,
    ))
    fig.add_trace(go.Scatter(
        x=df.index, y=df["bb_lower"], mode="lines",
        line=dict(color="rgba(60,196,183,0.3)", width=1, dash="dot"),
        fill="tonexty", fillcolor=BB_COLOR,
        name="Bollinger Bands",
    ))
    fig.add_trace(go.Scatter(
        x=df.index, y=df["ma90"], mode="lines",
        line=dict(color=MA_COLOR, width=1.5),
        name="MA 90j",
    ))
    fig.add_trace(go.Scatter(
        x=df.index, y=df["close"], mode="lines",
        line=dict(color=BTC_COLOR, width=2),
        name="BTC-USD",
    ))
    fig.update_layout(
        paper_bgcolor=CHART_BG, plot_bgcolor=CHART_BG,
        height=320,
        margin=dict(l=0, r=0, t=24, b=0),
        title=dict(text="BTC-USD · Prix + MA90 + Bollinger", font=dict(color="#555", size=11, family="JetBrains Mono"), x=0),
        xaxis=dict(showgrid=False, color="#333", tickfont=dict(color="#444", size=9)),
        yaxis=dict(showgrid=True, gridcolor=GRID_COLOR, color="#333", tickfont=dict(color="#444", size=9),
                   tickprefix="$", tickformat=",.0f"),
        legend=dict(font=dict(color="#555", size=9), bgcolor="rgba(0,0,0,0)"),
        hovermode="x unified",
    )
    return fig

def chart_volatility(df):
    df_plot = df.dropna(subset=["rv30", "rv90_avg"])
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_plot.index, y=df_plot["rv90_avg"],
        mode="lines", line=dict(color="#444", width=1.5, dash="dot"),
        name="Moy. 90j",
    ))
    fig.add_trace(go.Scatter(
        x=df_plot.index, y=df_plot["rv30"],
        mode="lines", line=dict(color=BTC_COLOR, width=2),
        name="Vol Réalisée 30j",
        fill="tozeroy", fillcolor="rgba(247,147,26,0.06)",
    ))
    fig.update_layout(
        paper_bgcolor=CHART_BG, plot_bgcolor=CHART_BG,
        height=200,
        margin=dict(l=0, r=0, t=24, b=0),
        title=dict(text="Volatilité Réalisée 30j (annualisée)", font=dict(color="#555", size=11, family="JetBrains Mono"), x=0),
        xaxis=dict(showgrid=False, color="#333", tickfont=dict(color="#444", size=9)),
        yaxis=dict(showgrid=True, gridcolor=GRID_COLOR, color="#333", tickfont=dict(color="#444", size=9),
                   tickformat=".0%"),
        legend=dict(font=dict(color="#555", size=9), bgcolor="rgba(0,0,0,0)"),
        hovermode="x unified",
    )
    return fig

def chart_fear_greed(fg_df):
    if fg_df is None or fg_df.empty:
        return None
    cmap = fg_df["value"].apply(
        lambda v: "#ff4444" if v < 25 else ("#F7931A" if v < 45 else ("#888" if v < 55 else ("#3CC4B7" if v < 75 else "#00ff64")))
    )
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=fg_df["timestamp"], y=fg_df["value"],
        marker_color=cmap.tolist(),
        name="F&G",
    ))
    fig.add_hline(y=25, line=dict(color="#ff4444", width=1, dash="dot"), annotation_text="Extreme Fear", annotation_font_color="#ff4444")
    fig.add_hline(y=75, line=dict(color="#00ff64", width=1, dash="dot"), annotation_text="Greed", annotation_font_color="#00ff64")
    fig.update_layout(
        paper_bgcolor=CHART_BG, plot_bgcolor=CHART_BG,
        height=200,
        margin=dict(l=0, r=0, t=24, b=0),
        title=dict(text="Fear & Greed Index (On-Chain Proxy)", font=dict(color="#555", size=11, family="JetBrains Mono"), x=0),
        xaxis=dict(showgrid=False, color="#333", tickfont=dict(color="#444", size=9)),
        yaxis=dict(showgrid=True, gridcolor=GRID_COLOR, color="#333", tickfont=dict(color="#444", size=9),
                   range=[0, 100]),
        showlegend=False,
        hovermode="x unified",
    )
    return fig

# ══════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════

def main():
    # ── Header ──────────────────────────────────────────────────────
    st.markdown("""
    <div class="page-header">
        <div class="page-tag">BTC SPOT · DCA QUANTITATIF · BINANCE</div>
        <h1 class="page-title">₿ <span>BTC DCA</span> Model</h1>
        <p class="page-sub">Volatilité Réalisée × Fear & Greed × Z-Score → Signal d'entrée DCA</p>
    </div>
    """, unsafe_allow_html=True)

    # ── Sidebar ─────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("### ₿ Configuration DCA")
        st.divider()

        budget_base = st.number_input("Budget DCA de base (USDT)", min_value=10, max_value=10000,
                                       value=100, step=10,
                                       help="Montant pour un signal BUY standard (x1)")
        freq        = st.selectbox("Fréquence de vérification", ["Manuel", "Hebdomadaire", "Bi-mensuel", "Mensuel"])

        st.markdown("---")
        st.markdown("**Seuils des signaux**")
        vol_thresh  = st.slider("Vol Ratio → BUY",          0.8, 2.0, 1.05, 0.05)
        vol_strong  = st.slider("Vol Ratio → STRONG BUY",   0.8, 2.5, 1.25, 0.05)
        z_thresh    = st.slider("Z-Score → BUY (dip)",     -3.0, 0.0, -0.4, 0.1)
        z_strong    = st.slider("Z-Score → STRONG BUY",    -3.0, 0.0, -1.0, 0.1)
        fg_fear     = st.slider("F&G → FEAR (BUY)",          0,  50,  45)
        fg_ext_fear = st.slider("F&G → EXTREME FEAR",        0,  40,  25)
        fg_greed    = st.slider("F&G → WAIT (Greed)",       50, 100,  80)

        st.markdown("---")
        st.markdown("**Alertes**")
        alert_type   = st.selectbox("Canal d'alerte", ["Désactivé", "Discord Webhook", "Telegram"])
        webhook_url  = ""
        tg_token     = ""
        tg_chat_id   = ""

        if alert_type == "Discord Webhook":
            webhook_url = st.text_input("Discord Webhook URL", type="password",
                                         placeholder="https://discord.com/api/webhooks/...")
            st.caption("Serveur Discord → Paramètres du canal → Intégrations → Webhooks")

        elif alert_type == "Telegram":
            tg_token   = st.text_input("Bot Token", type="password", placeholder="123456:ABC...")
            tg_chat_id = st.text_input("Chat ID",   placeholder="-100123456789")
            st.caption("@BotFather pour créer le bot · @userinfobot pour le chat_id")

        alert_signals = st.multiselect("Alerter pour", ["STRONG BUY", "BUY", "NEUTRAL", "WAIT"],
                                        default=["STRONG BUY", "BUY"])

        st.markdown("---")
        if st.button("Rafraîchir les données", use_container_width=True):
            st.cache_data.clear()

    # ── Data ────────────────────────────────────────────────────────
    with st.spinner("Chargement BTC-USD…"):
        df_raw = fetch_btc("2y")

    if df_raw is None or df_raw.empty:
        st.error("Impossible de charger BTC-USD via yfinance.")
        return

    df = compute_signals(df_raw)

    with st.spinner("Fear & Greed Index…"):
        fg_df = fetch_fear_greed(90)

    # ── Current values ───────────────────────────────────────────────
    last        = df.iloc[-1]
    price       = float(last["close"])
    vol_ratio   = float(last["vol_ratio"])  if not np.isnan(last["vol_ratio"])  else 1.0
    z_score     = float(last["z_score"])    if not np.isnan(last["z_score"])    else 0.0
    rv30        = float(last["rv30"])        if not np.isnan(last["rv30"])        else 0.0

    fg_value    = int(fg_df.iloc[-1]["value"])           if fg_df is not None else 50
    fg_label    = fg_df.iloc[-1]["value_classification"] if fg_df is not None else "Neutral"

    # Custom thresholds
    def _signal(vol_ratio, z_score, fg_value):
        _vol_high  = vol_ratio > vol_strong
        _vol_mod   = vol_ratio > vol_thresh
        _oversold  = z_score   < z_strong
        _dip       = z_score   < z_thresh
        _ext_fear  = fg_value  < fg_ext_fear
        _fear      = fg_value  < fg_fear
        _ext_greed = fg_value  > fg_greed

        if _ext_greed and not _oversold:
            return "WAIT",       "signal-wait",        0.0, "Extreme Greed — marché euphorique"
        if _vol_high and _oversold and (_fear or _ext_fear):
            return "STRONG BUY", "signal-strong-buy",  3.0, "Vol élevée + dip profond + Fear"
        if (_vol_high and _oversold) or (_ext_fear and _dip):
            return "STRONG BUY", "signal-strong-buy",  2.0, "Deux conditions simultanées"
        if _vol_mod or _dip or _fear:
            return "BUY",        "signal-buy",         1.0, "Signal modéré — dose standard"
        return   "NEUTRAL",      "signal-neutral",     0.5, "Pas de déclencheur actif"

    signal, css_class, multiplier, reason = _signal(vol_ratio, z_score, fg_value)
    amount = budget_base * multiplier

    # ── Signal badge ────────────────────────────────────────────────
    st.markdown(f"""
    <div class="signal-wrap">
        <div class="signal-badge {css_class}">
            {signal}<br>
            <span style="font-size:0.75rem;font-weight:400;opacity:0.7">{reason}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Alert button ────────────────────────────────────────────────
    col_alert, col_freq, _ = st.columns([2, 2, 6])
    with col_alert:
        if signal in alert_signals and alert_type != "Désactivé":
            if st.button(f"Envoyer alerte {signal}", type="primary", use_container_width=True):
                ok = False
                if alert_type == "Discord Webhook" and webhook_url:
                    ok = send_discord(webhook_url, signal, price, vol_ratio, z_score, fg_value, fg_label, amount)
                elif alert_type == "Telegram" and tg_token and tg_chat_id:
                    ok = send_telegram(tg_token, tg_chat_id, signal, price, vol_ratio, z_score, fg_value, fg_label, amount)
                if ok:
                    st.success("Alerte envoyée!")
                else:
                    st.error("Echec envoi — vérifie la config dans la sidebar")
    with col_freq:
        st.caption(f"Fréquence : **{freq}**")

    # ── Metric cards ─────────────────────────────────────────────────
    z_color  = "col-green" if z_score < z_strong else ("col-orange" if z_score < z_thresh else "col-white")
    vr_color = "col-green" if vol_ratio > vol_strong else ("col-orange" if vol_ratio > vol_thresh else "col-white")
    fg_color = "col-green" if fg_value < fg_ext_fear else ("col-orange" if fg_value < fg_fear else ("col-red" if fg_value > fg_greed else "col-white"))
    amt_color= "col-green" if multiplier >= 2 else ("col-orange" if multiplier >= 1 else "col-white")

    st.markdown(f"""
    <div class="metrics-row">
        <div class="metric-card">
            <div class="metric-label">BTC Price</div>
            <div class="metric-value col-orange">${price:,.0f}</div>
            <div class="metric-sub">USD · Binance</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Vol Ratio (30j/90j)</div>
            <div class="metric-value {vr_color}">{vol_ratio:.2f}x</div>
            <div class="metric-sub">RV 30j: {rv30:.1%}</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Z-Score Prix</div>
            <div class="metric-value {z_color}">{z_score:+.2f}σ</div>
            <div class="metric-sub">vs MA 90j</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Fear & Greed</div>
            <div class="metric-value {fg_color}">{fg_value}</div>
            <div class="metric-sub">{fg_label}</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Montant DCA</div>
            <div class="metric-value {amt_color}">${amount:.0f}</div>
            <div class="metric-sub">{multiplier:.1f}x base ({budget_base}$)</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Price chart ──────────────────────────────────────────────────
    st.plotly_chart(chart_price(df), use_container_width=True)

    # ── Vol + F&G charts ─────────────────────────────────────────────
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(chart_volatility(df), use_container_width=True)
    with c2:
        fg_fig = chart_fear_greed(fg_df)
        if fg_fig:
            st.plotly_chart(fg_fig, use_container_width=True)
        else:
            st.info("Fear & Greed non disponible")

    # ── DCA plan ─────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("**Plan DCA actuel**")
    amt_color_cls = "dca-val-green" if multiplier >= 2 else ("dca-val-orange" if multiplier >= 1 else "dca-val-red")

    next_note = {
        "STRONG BUY": "Acheter maintenant sur Binance",
        "BUY":        "Acheter selon fréquence planifiée",
        "NEUTRAL":    "Demi-dose ou attendre prochain check",
        "WAIT":       "Ne rien acheter — marché trop euphorique",
    }.get(signal, "")

    st.markdown(f"""
    <div class="dca-table">
        <div class="dca-row"><span class="dca-key">Signal actuel</span>   <span class="{amt_color_cls}">{signal}</span></div>
        <div class="dca-row"><span class="dca-key">Raison</span>          <span class="dca-val">{reason}</span></div>
        <div class="dca-row"><span class="dca-key">Multiplicateur</span>  <span class="dca-val">{multiplier:.1f}×</span></div>
        <div class="dca-row"><span class="dca-key">Montant à investir</span><span class="{amt_color_cls}">${amount:.0f} USDT</span></div>
        <div class="dca-row"><span class="dca-key">Fréquence</span>       <span class="dca-val">{freq}</span></div>
        <div class="dca-row"><span class="dca-key">Action recommandée</span><span class="dca-val">{next_note}</span></div>
        <div class="dca-row"><span class="dca-key">Dernière MAJ</span>    <span class="dca-val">{datetime.now().strftime('%Y-%m-%d %H:%M')}</span></div>
    </div>
    """, unsafe_allow_html=True)

    # ── Footer ────────────────────────────────────────────────────────
    st.markdown("""
    <div style="text-align:center;padding:2rem;color:#222;font-size:0.7rem;font-family:'JetBrains Mono',monospace;letter-spacing:0.1em">
        ← MODÈLE SECONDAIRE · BTC SPOT LONG TERME · HURST MR RESTE LE MODÈLE PRINCIPAL →
    </div>
    """, unsafe_allow_html=True)

main()
