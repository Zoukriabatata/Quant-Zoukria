"""
config.py — Chemins et constantes centralisés pour toutes les pages.
Chaque chemin utilise os.environ en priorité → fallback sur valeur locale.
"""
import os
import tempfile
from pathlib import Path

# ── Racine du projet ──────────────────────────────────────────────────
ROOT = Path(__file__).parent

# ── Données live (dxfeed_bridge.js → Live Signal) ─────────────────────
# C:\tmp est le path hardcodé dans dxfeed_bridge.js — on l'utilise comme fallback
_TMP = Path("C:/tmp")
DXFEED_FILE  = os.environ.get("DXFEED_FILE",  str(_TMP / "mnq_live.json"))
JOURNAL_DB   = os.environ.get("JOURNAL_DB",   str(Path(tempfile.gettempdir()) / "mnq_journal.db"))
SOL_JOURNAL_DB = os.environ.get("SOL_JOURNAL_DB", str(ROOT / "sol_journal.db"))

# ── Données historiques (backtests) ───────────────────────────────────
MNQ_CSV = os.environ.get(
    "MNQ_CSV",
    r"C:\Users\ryadb\Downloads\5 ANS DATA MNQ OHLCV M1\glbx-mdp3-20210405-20260404.ohlcv-1m.csv"
)

# ── Challenge Apex $50K EOD (partagé Accueil + Live + Session Prep) ──
CHALLENGE_DD     = float(os.environ.get("CHALLENGE_DD",     "2000"))
CHALLENGE_TARGET = float(os.environ.get("CHALLENGE_TARGET", "3000"))

# ── Apex Trader Funding $50K EOD — règles complètes ──────────────────
APEX_ACCOUNT_SIZE           = float(os.environ.get("APEX_ACCOUNT_SIZE",           "50000"))
APEX_TRAILING_DD            = float(os.environ.get("APEX_TRAILING_DD",            "2000"))
APEX_DAILY_LIMIT            = float(os.environ.get("APEX_DAILY_LIMIT",            "1000"))
APEX_PROFIT_TARGET          = float(os.environ.get("APEX_PROFIT_TARGET",          "3000"))
APEX_SAFETY_NET             = float(os.environ.get("APEX_SAFETY_NET",             "52100"))
APEX_SAFETY_NET_FLOOR       = float(os.environ.get("APEX_SAFETY_NET_FLOOR",       "50100"))
APEX_MAX_CONTRACTS_EVAL     = int(os.environ.get("APEX_MAX_CONTRACTS_EVAL",       "6"))
APEX_MAX_CONTRACTS_PA_START = int(os.environ.get("APEX_MAX_CONTRACTS_PA_START",   "2"))
APEX_MAX_CONTRACTS_PA_FULL  = int(os.environ.get("APEX_MAX_CONTRACTS_PA_FULL",    "4"))
APEX_CONSISTENCY_PCT        = float(os.environ.get("APEX_CONSISTENCY_PCT",        "0.50"))
APEX_PAYOUT_MIN_DAYS        = int(os.environ.get("APEX_PAYOUT_MIN_DAYS",          "8"))
APEX_PAYOUT_QUAL_DAYS       = int(os.environ.get("APEX_PAYOUT_QUAL_DAYS",         "5"))
APEX_PAYOUT_QUAL_MIN        = float(os.environ.get("APEX_PAYOUT_QUAL_MIN",        "50"))
APEX_PAYOUT_MIN_AMOUNT      = float(os.environ.get("APEX_PAYOUT_MIN_AMOUNT",      "500"))
APEX_EVAL_DAYS_MAX          = int(os.environ.get("APEX_EVAL_DAYS_MAX",            "30"))
APEX_PAYOUT_LADDER          = [1500, 1875, 2250, 2625, 2812.50, 3000]  # caps par payout
APEX_CLOSE_HOUR_PARIS       = 21   # règle personnelle : fermer tout avant 21h59 Paris
APEX_CLOSE_MINUTE_PARIS     = 59   # (= 15h59 NY, 1 min avant fin session 22h00 Paris)

# ── Paramètres Hurst_MR validés walk-forward ─────────────────────────
HURST_THRESHOLD = float(os.environ.get("HURST_THRESHOLD", "0.53"))
HURST_WIN       = int(os.environ.get("HURST_WIN",         "60"))
LOOKBACK        = int(os.environ.get("LOOKBACK",          "30"))
BAND_K          = float(os.environ.get("BAND_K",          "3.00"))
SL_MULT         = float(os.environ.get("SL_MULT",         "0.75"))

# ── Alertes ───────────────────────────────────────────────────────────
NTFY_TOPIC           = os.environ.get("NTFY_TOPIC", "hurst-mnq-ryad")
DISCORD_STATUS_FILE  = os.environ.get("DISCORD_STATUS_FILE", str(_TMP / "discord_status.json"))
NTFY_STATUS_FILE     = os.environ.get("NTFY_STATUS_FILE",    str(_TMP / "ntfy_status.json"))

# ── Limites journalières (Live Signal + Session Prep) ─────────────────
DAILY_LOSS_LIM = float(os.environ.get("DAILY_LOSS_LIM", "1000"))
