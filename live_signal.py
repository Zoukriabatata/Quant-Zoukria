"""
Live Signal — Hurst_MR (Lec 25 + Lec 51)
Source données : yfinance NQ=F  (M1, ~15 min delay gratuit)
Instrument     : NQ front-month (proxy MNQ)

Logique :
  - Polling toutes les 60 secondes
  - Calcul Hurst sur session courante
  - Si H < 0.45 + HMM state != 2 + |z| > 2.5 → ALERTE

Usage : python live_signal.py
"""

import time
import numpy as np
import warnings
warnings.filterwarnings("ignore")

try:
    import yfinance as yf
except ImportError:
    raise SystemExit("pip install yfinance")

# ── Params (best backtest MNQ Score 0.580) ───────────────────────────────────
SYMBOL          = "NQ=F"       # NQ front-month (MNQ ×10)
HURST_THRESHOLD = 0.45
LOOKBACK        = 30
BAND_K          = 2.5
HMM_LOOKBACK    = 60
POLL_SECONDS    = 60           # polling toutes les 60 sec

# Session NY 09:30 → 16:00
SESSION_START_H, SESSION_START_M = 9,  30
SESSION_END_H,   SESSION_END_M   = 16,  0
SKIP_OPEN_BARS  = 5

# ── Hurst exponent R/S (Lec 25) ──────────────────────────────────────────────
def hurst_exponent(ts):
    ts = np.asarray(ts, dtype=float)
    n = len(ts)
    if n < 20:
        return 0.5
    lags = range(2, min(n // 2, 50))
    rs_vals = []
    for lag in lags:
        chunks = [ts[i:i+lag] for i in range(0, n - lag + 1, lag)]
        rs_chunk = []
        for chunk in chunks:
            std = chunk.std()
            if std > 0:
                devs = np.cumsum(chunk - chunk.mean())
                rs_chunk.append((devs.max() - devs.min()) / std)
        if rs_chunk:
            rs_vals.append(np.mean(rs_chunk))
    if len(rs_vals) < 3:
        return 0.5
    try:
        h = np.polyfit(np.log(list(lags)[:len(rs_vals)]), np.log(rs_vals), 1)[0]
        return float(np.clip(h, 0.0, 1.0))
    except Exception:
        return 0.5

# ── HMM proxy state (Lec 51) ─────────────────────────────────────────────────
def hmm_proxy_state(closes, lookback=60):
    """0=calm 1=normal 2=trending."""
    n = len(closes)
    if n < 3:
        return 1
    rets = np.abs(np.diff(np.log(np.maximum(closes, 1e-9))))
    if len(rets) < lookback:
        return 1
    recent = rets[-min(len(rets), 200):]
    p33 = np.nanpercentile(recent, 33)
    p67 = np.nanpercentile(recent, 67)
    cur = rets[-1]
    if cur <= p33:
        return 0
    elif cur >= p67:
        return 2
    return 1

# ── Signal evaluation ─────────────────────────────────────────────────────────
last_signal_key = None

def evaluate(closes, times):
    global last_signal_key

    n = len(closes)
    if n < LOOKBACK + SKIP_OPEN_BARS:
        return

    h = hurst_exponent(closes)
    if h >= HURST_THRESHOLD:
        return  # Session persistante

    hmm_state = hmm_proxy_state(closes, HMM_LOOKBACK)
    if hmm_state == 2:
        return  # Barre trending

    window = closes[-LOOKBACK:]
    mid = window.mean()
    std = window.std()
    if std == 0:
        return

    price = closes[-1]
    z = (price - mid) / std

    if abs(z) < BAND_K:
        return

    direction = "SHORT" if z > 0 else "LONG"
    bar_time  = times[-1]
    sig_key   = f"{bar_time}_{direction}"

    if sig_key == last_signal_key:
        return  # déjà alerté
    last_signal_key = sig_key

    sep = "▶" * 3
    print(f"\n{sep} SIGNAL Hurst_MR ◀◀◀")
    print(f"  Heure     : {bar_time}")
    print(f"  Direction : {direction}")
    print(f"  Prix NQ   : {price:,.2f}  (MNQ ≈ {price/10:,.1f})")
    print(f"  Z-score   : {z:+.2f}σ  (seuil {BAND_K}σ)")
    print(f"  Fair value: {mid:,.2f}  (cible TP)")
    print(f"  SL guide  : {std * 1.25:.0f} pts NQ  ({std/10 * 1.25:.1f} pts MNQ)")
    print(f"  Hurst H   : {h:.3f}  (< {HURST_THRESHOLD} → session MR)")
    print(f"  HMM state : {hmm_state}  (0=calm 1=normal 2=trend)")
    print()

    try:
        import winsound
        winsound.Beep(1200, 400)
        winsound.Beep(1000, 200)
    except Exception:
        print("\a")


# ── Fetch session data ────────────────────────────────────────────────────────
def fetch_session():
    try:
        df = yf.download(SYMBOL, period="1d", interval="1m",
                         progress=False, auto_adjust=True)
        if df is None or len(df) < 10:
            return None, None

        # Filtre session NY
        import pandas as pd
        df.index = pd.to_datetime(df.index)
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC")
        df.index = df.index.tz_convert("America/New_York")

        t = df.index.hour * 60 + df.index.minute
        df = df[(t >= SESSION_START_H * 60 + SESSION_START_M) &
                (t <  SESSION_END_H   * 60 + SESSION_END_M)]

        if len(df) < 10:
            return None, None

        closes = df["Close"].values.astype(float).flatten()
        times  = [str(x)[:16] for x in df.index]
        return closes, times

    except Exception as e:
        print(f"  [fetch error] {e}")
        return None, None


# ── Main loop ─────────────────────────────────────────────────────────────────
def main():
    from datetime import datetime
    print("=" * 55)
    print("  LIVE SIGNAL — Hurst_MR  |  NQ=F  |  yfinance M1")
    print(f"  Params : H<{HURST_THRESHOLD}  lookback={LOOKBACK}  band={BAND_K}σ")
    print("=" * 55)
    print(f"Polling toutes les {POLL_SECONDS}s  (Ctrl+C pour arrêter)\n")

    current_day = None

    while True:
        from datetime import timezone as tz
        import pytz
        ny = pytz.timezone("America/New_York")
        now_ny = datetime.now(tz.utc).astimezone(ny)
        today  = now_ny.date()

        # Reset session
        if today != current_day:
            current_day = today
            global last_signal_key
            last_signal_key = None
            print(f"{'─'*55}")
            print(f"  Nouvelle session : {today}  (heure NY)")
            print(f"{'─'*55}")

        # Heure de trading ? (NY time)
        h, m = now_ny.hour, now_ny.minute
        in_session = (
            (h * 60 + m) >= SESSION_START_H * 60 + SESSION_START_M and
            (h * 60 + m) <  SESSION_END_H   * 60 + SESSION_END_M
        )

        if in_session:
            closes, times = fetch_session()
            if closes is not None:
                evaluate(closes, times)
                print(f"  [{now_ny.strftime('%H:%M:%S')} NY] "
                      f"H={hurst_exponent(closes):.3f}  "
                      f"prix={closes[-1]:,.1f}  "
                      f"bars={len(closes)}", end="\r")
        else:
            print(f"  [{now_ny.strftime('%H:%M:%S')} NY] Hors session (9:30-16:00 NY)", end="\r")

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nArrêt.")
