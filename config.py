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

# ── Données historiques (backtests) ───────────────────────────────────
MNQ_CSV = os.environ.get(
    "MNQ_CSV",
    r"C:\Users\ryadb\Downloads\5 ANS DATA MNQ OHLCV M1\glbx-mdp3-20210405-20260404.ohlcv-1m.csv"
)

# ── Challenge 4PropTrader (partagé Accueil + Live + Session Prep) ─────
CHALLENGE_DD     = float(os.environ.get("CHALLENGE_DD",     "2500"))
CHALLENGE_TARGET = float(os.environ.get("CHALLENGE_TARGET", "3000"))

# ── Paramètres Hurst_MR validés walk-forward ─────────────────────────
HURST_THRESHOLD = float(os.environ.get("HURST_THRESHOLD", "0.52"))
HURST_WIN       = int(os.environ.get("HURST_WIN",         "60"))
LOOKBACK        = int(os.environ.get("LOOKBACK",          "30"))
BAND_K          = float(os.environ.get("BAND_K",          "3.25"))
SL_MULT         = float(os.environ.get("SL_MULT",         "0.75"))

# ── Alertes ───────────────────────────────────────────────────────────
NTFY_TOPIC           = os.environ.get("NTFY_TOPIC", "hurst-mnq-ryad")
DISCORD_STATUS_FILE  = os.environ.get("DISCORD_STATUS_FILE", str(_TMP / "discord_status.json"))

# ── Limites journalières (Live Signal + Session Prep) ─────────────────
DAILY_LOSS_LIM = float(os.environ.get("DAILY_LOSS_LIM", "600"))
