"""
alert_cron.py — SOL Signal Alert (GitHub Actions cron)
Tourne chaque jour à 22h00 UTC (après clôture daily Binance).
Envoie NTFY + Discord uniquement si le signal change (FLAT→LONG ou LONG→FLAT).
Aucun stockage persistant requis — détecte le changement via signal[-1] vs signal[-2].
"""
import os
import sys
import requests
import numpy as np
import pandas as pd

try:
    from statsmodels.tsa.seasonal import STL
    HAS_STL = True
except ImportError:
    HAS_STL = False

# ── Config ────────────────────────────────────────────────────────────────────
NTFY_TOPIC  = os.environ.get("SOL_NTFY_TOPIC",  "Sol-Alerte")
DISCORD_URL = os.environ.get("SOL_DISCORD_URL", "")
STL_PERIOD  = 5
EMA_FILTER  = 10
SYMBOL      = "SOLUSDT"


# ── Data ──────────────────────────────────────────────────────────────────────
def fetch_binance(symbol: str = SYMBOL, limit: int = 120) -> pd.Series:
    url = "https://api.binance.com/api/v3/klines"
    r = requests.get(url, params={"symbol": symbol, "interval": "1d",
                                  "limit": limit}, timeout=10)
    r.raise_for_status()
    raw = r.json()
    closes = [float(x[4]) for x in raw]
    dates  = pd.to_datetime([x[0] for x in raw], unit="ms").normalize()
    return pd.Series(closes, index=dates, name=symbol)


# ── Signal ────────────────────────────────────────────────────────────────────
def compute_signal(close: pd.Series) -> pd.Series:
    ema = close.ewm(span=EMA_FILTER, adjust=False).mean()
    if HAS_STL and len(close) >= STL_PERIOD * 2:
        try:
            res   = STL(np.log(close.values.astype(float)),
                        period=STL_PERIOD, robust=True).fit()
            trend = pd.Series(res.trend, index=close.index)
            sig   = np.sign(trend.diff()).clip(0, 1) * (close > ema).astype(float)
            return sig.shift(1).fillna(0)
        except Exception:
            pass
    # Fallback EMA
    ema_fast = close.ewm(span=STL_PERIOD, adjust=False).mean()
    ema_slow = close.ewm(span=STL_PERIOD * 3, adjust=False).mean()
    return ((ema_fast > ema_slow).astype(float) * (close > ema).astype(float)
            ).shift(1).fillna(0)


# ── Alertes ───────────────────────────────────────────────────────────────────
def send_ntfy(title: str, message: str) -> bool:
    if not NTFY_TOPIC:
        return False
    try:
        r = requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode("utf-8"),
            headers={"Title": title, "Priority": "high",
                     "Tags": "chart_with_upwards_trend,solana"},
            timeout=8,
        )
        return r.status_code == 200
    except Exception as e:
        print(f"NTFY error: {e}")
        return False


def send_discord(message: str) -> bool:
    if not DISCORD_URL:
        return False
    try:
        r = requests.post(
            DISCORD_URL,
            json={"content": message, "username": "QuantMaster SOL"},
            timeout=8,
        )
        return r.status_code in (200, 204)
    except Exception as e:
        print(f"Discord error: {e}")
        return False


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print(f"SOL Alert Cron — STL période={STL_PERIOD} · EMA={EMA_FILTER}")
    print(f"STL disponible : {HAS_STL}")

    close  = fetch_binance()
    signal = compute_signal(close)

    current  = float(signal.iloc[-1])
    previous = float(signal.iloc[-2])
    price    = float(close.iloc[-1])
    date_str = str(close.index[-1].date())

    print(f"Date       : {date_str}")
    print(f"Prix SOL   : ${price:.2f}")
    print(f"Signal[-2] : {'LONG' if previous == 1 else 'FLAT'}")
    print(f"Signal[-1] : {'LONG' if current  == 1 else 'FLAT'}")

    if current == previous:
        print("→ Aucun changement de signal. Pas d'alerte.")
        return

    # Changement détecté
    if current == 1:
        title   = "🟢 SOL — SIGNAL LONG"
        msg_ntfy = (f"Entrée LONG SOL/USD\n"
                    f"Prix : ${price:.2f}\n"
                    f"Modèle : STL période={STL_PERIOD} · EMA={EMA_FILTER}")
        msg_disc = (f"**🟢 QuantMaster SOL — SIGNAL LONG**\n"
                    f"Prix : **${price:.2f}**\n"
                    f"Modèle : STL p={STL_PERIOD} · EMA={EMA_FILTER}\n"
                    f"→ Entrée position recommandée")
    else:
        title    = "⬜ SOL — SIGNAL FLAT"
        msg_ntfy = (f"Sortie FLAT SOL/USD\n"
                    f"Prix : ${price:.2f}\n"
                    f"→ Fermer la position")
        msg_disc = (f"**⬜ QuantMaster SOL — SIGNAL FLAT**\n"
                    f"Prix : **${price:.2f}**\n"
                    f"→ Sortie de position recommandée")

    ok_ntfy = send_ntfy(title, msg_ntfy)
    ok_disc = send_discord(msg_disc)

    print(f"NTFY    : {'✓ envoyé' if ok_ntfy else '✗ échec'}")
    print(f"Discord : {'✓ envoyé' if ok_disc else '✗ échec'}")

    if not ok_ntfy and not ok_disc:
        sys.exit(1)


if __name__ == "__main__":
    main()
