"""
Live Signal — Hurst_MR
Source données : DXFeed Production (4proptrader)
Instrument     : MNQ M1 temps réel

Logique validée backtest 5 ans (PF=2.03, Sharpe=2.50, MaxDD=5.5%, $158k/5ans) :
  - Polling toutes les 60 secondes
  - Hurst rolling sur les 60 derniers log returns
  - Si H < 0.52 + |z| > 3.25 → ALERTE sonore + affichage niveaux

Usage :
  1. pip install dxfeed python-dotenv pytz
  2. Remplis .env avec tes credentials (après reset mot de passe)
  3. python live_signal.py
"""

import time
import os
import urllib.request
import numpy as np
import warnings
warnings.filterwarnings("ignore")

# ── Credentials depuis .env (jamais hardcodés) ───────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
except ImportError:
    raise SystemExit("pip install python-dotenv")

DXFEED_LOGIN    = os.environ.get("DXFEED_LOGIN", "")
DXFEED_PASSWORD = os.environ.get("DXFEED_PASSWORD", "")
DXFEED_SERVER   = os.environ.get("DXFEED_SERVER", "dxfeed.4proptrader.com")

if not DXFEED_LOGIN or "CHANGE_MOI" in DXFEED_PASSWORD:
    raise SystemExit("⚠️  Remplis .env avec tes vrais credentials DXFeed d'abord.")

# ── Params validés backtest 5 ans ────────────────────────────────────────────
# Config : PF 2.03 · Sharpe 2.50 · DD 5.5% · 1095 trades · $158k / 5 ans
MNQ_SYMBOL      = "/MNQ:XCME"   # format DXFeed CME futures MNQ
HURST_THRESHOLD = 0.52          # seuil H rolling sur log-returns
HURST_WIN       = 60            # fenêtre rolling Hurst (barres)
LOOKBACK        = 30            # fenêtre Z-score (barres)
BAND_K          = 3.25          # seuil Z-score entrée
SL_MULT         = 0.75          # SL = 0.75 × std
TP_OVERSHOOT    = 0.0           # TP = fair value (mid exact, pas d'overshoot)
MAX_TRADES_DAY  = 5             # max trades par session
DAILY_LOSS_LIM  = 600.0         # stop journalier en $ (perte max)
POLL_SECONDS    = 15
NTFY_TOPIC      = "hurst-mnq-ryad"
SESSION_START_H, SESSION_START_M = 9,  30
SESSION_END_H,   SESSION_END_M   = 16,  0
SKIP_OPEN_BARS  = 5
SKIP_CLOSE_BARS = 3             # skip fin de session — identique backtest

# ── Notification ntfy ───────────────────────────────────────────────────────
def send_ntfy(msg: str):
    try:
        urllib.request.urlopen(urllib.request.Request(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=msg.encode("utf-8"),
            method="POST"
        ), timeout=5)
    except Exception:
        pass

# ── Hurst R/S vectorisé (identique backtest_hurst.py) ───────────────────────
def hurst_rs(ts):
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

# ── Signal evaluation ────────────────────────────────────────────────────────
last_signal_key = None

def evaluate(closes, times):
    global last_signal_key
    n = len(closes)
    if n < HURST_WIN + LOOKBACK + SKIP_OPEN_BARS:
        return
    # Skip fin de session — identique backtest skip_c=3
    from datetime import datetime as _dt
    try:
        last_bar = _dt.strptime(times[-1][:16], "%Y-%m-%d %H:%M")
        mins_to_close = (SESSION_END_H * 60 + SESSION_END_M) - (last_bar.hour * 60 + last_bar.minute)
        if mins_to_close <= SKIP_CLOSE_BARS:
            return
    except Exception:
        pass

    log_rets = np.diff(np.log(np.maximum(closes, 1e-9)))
    if len(log_rets) < HURST_WIN:
        return

    h = hurst_rs(log_rets[-HURST_WIN:])
    if h >= HURST_THRESHOLD:
        return

    window = closes[-LOOKBACK:]
    mid = window.mean()
    std = window.std()
    if std == 0:
        return

    price = closes[-1]
    z = (price - mid) / std
    if abs(z) < BAND_K:
        return

    direction  = "SHORT" if z > 0 else "LONG"
    bar_time   = times[-1]
    sig_key    = f"{bar_time}_{direction}"
    if sig_key == last_signal_key:
        return
    last_signal_key = sig_key

    sl_pts_mnq   = max(0.25, SL_MULT * std / 10)
    tp_price_mnq = (mid / 10) + TP_OVERSHOOT * (mid - price) / 10  # fair value pure

    print(f"\n{'▶'*3} SIGNAL Hurst_MR {'◀'*3}")
    print(f"  Heure      : {bar_time}")
    print(f"  Direction  : {direction}")
    print(f"  Prix MNQ   : {price/10:,.2f}")
    print(f"  Z-score    : {z:+.2f}σ  (seuil {BAND_K}σ)")
    print(f"  TP MNQ     : {tp_price_mnq:,.2f}  (fair value pure)")
    print(f"  SL MNQ     : {sl_pts_mnq:.2f} pts  ({SL_MULT}×std)")
    print(f"  Hurst H    : {h:.3f}  (rolling {HURST_WIN} returns)")
    print()

    try:
        import winsound
        winsound.Beep(1200, 400); winsound.Beep(1000, 200)
    except Exception:
        print("\a")

    send_ntfy(
        f"HURST_MR {direction} MNQ\n"
        f"Prix : {price/10:,.2f}\n"
        f"TP   : {tp_price_mnq:,.2f}\n"
        f"SL   : {sl_pts_mnq:.2f} pts\n"
        f"Z    : {z:+.2f}s  H={h:.3f}\n"
        f"Heure: {bar_time}"
    )

# ── Fetch données DXFeed ─────────────────────────────────────────────────────
def fetch_session_dxfeed():
    """Récupère les candles M1 MNQ de la session via DXFeed."""
    try:
        import dxfeed as dx
        import pandas as pd
        import pytz
        from datetime import datetime, timezone

        ny = pytz.timezone("America/New_York")
        now_ny = datetime.now(timezone.utc).astimezone(ny)
        today  = now_ny.date()

        # Connexion DXFeed
        con = dx.Connection(f"{DXFEED_SERVER}:443")
        con.set_property("username", DXFEED_LOGIN)
        con.set_property("password", DXFEED_PASSWORD)

        # Abonnement candles 1 minute
        candle_sub = con.create_subscription("Candle", dx.EventType.CANDLE)
        symbol = dx.CandleSymbol.valueOf(
            MNQ_SYMBOL,
            dx.CandlePeriod.valueOf(1, dx.CandleType.MINUTE),
            dx.CandlePrice.LAST
        )
        candle_sub.add_symbols([str(symbol)])
        time.sleep(3)  # attend les données

        df = candle_sub.get_dataframe()
        con.disconnect()

        if df is None or len(df) < 10:
            return None, None

        # Convertit timestamps
        df.index = pd.to_datetime(df.index, utc=True).tz_convert("America/New_York")
        df = df[df.index.date == today]

        # Filtre session NY
        t = df.index.hour * 60 + df.index.minute
        df = df[(t >= SESSION_START_H*60+SESSION_START_M) &
                (t <  SESSION_END_H*60+SESSION_END_M)]
        df = df.sort_index()

        if len(df) < 10:
            return None, None

        closes = df["Close"].values.astype(float)
        times  = [str(x)[:16] for x in df.index]
        return closes, times

    except Exception as e:
        print(f"  [DXFeed error] {e}")
        return None, None

# ── Main loop ────────────────────────────────────────────────────────────────
def main():
    import pytz
    from datetime import datetime, timezone

    print("=" * 60)
    print("  LIVE SIGNAL — Hurst_MR  |  MNQ  |  DXFeed Production")
    print(f"  H<{HURST_THRESHOLD} rolling {HURST_WIN}  |  K={BAND_K}σ  |  SL={SL_MULT}  |  TP=FairValue")
    print(f"  Backtest 5 ans : PF=1.97  Sharpe=3.81  MaxDD=2.6%")
    print(f"  Serveur : {DXFEED_SERVER}")
    print("=" * 60)
    print(f"Polling toutes les {POLL_SECONDS}s  (Ctrl+C pour arrêter)\n")

    ny = pytz.timezone("America/New_York")
    current_day = None
    global last_signal_key

    while True:
        now_ny = datetime.now(timezone.utc).astimezone(ny)
        today  = now_ny.date()

        if today != current_day:
            current_day = today
            last_signal_key = None
            print(f"\n{'─'*60}")
            print(f"  Nouvelle session : {today}")
            print(f"{'─'*60}")

        h_cur, m_cur = now_ny.hour, now_ny.minute
        in_session = (
            h_cur*60+m_cur >= SESSION_START_H*60+SESSION_START_M and
            h_cur*60+m_cur <  SESSION_END_H*60+SESSION_END_M
        )

        if in_session:
            closes, times = fetch_session_dxfeed()
            if closes is not None and len(closes) >= HURST_WIN:
                evaluate(closes, times)
                log_rets_live = np.diff(np.log(np.maximum(closes, 1e-9)))
                h_live = hurst_rs(log_rets_live[-HURST_WIN:]) if len(log_rets_live) >= HURST_WIN else float("nan")
                w = closes[-LOOKBACK:] if len(closes) >= LOOKBACK else closes
                z_live = (closes[-1]-w.mean())/w.std() if w.std()>0 else 0
                print(f"  [{now_ny.strftime('%H:%M:%S')} NY] "
                      f"H={h_live:.3f}({'MR' if h_live < HURST_THRESHOLD else '--'})  "
                      f"Z={z_live:+.2f}  MNQ={closes[-1]/10:,.2f}  bars={len(closes)}", end="\r")
            else:
                print(f"  [{now_ny.strftime('%H:%M:%S')} NY] En attente données DXFeed...", end="\r")
        else:
            print(f"  [{now_ny.strftime('%H:%M:%S')} NY] Hors session NY (9:30-16:00)", end="\r")

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nArrêt.")
