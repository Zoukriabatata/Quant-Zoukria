"""
config.py — Chemins et constantes centralisés pour toutes les pages.
Chaque chemin utilise os.environ en priorité → fallback sur valeur locale.
"""
import os
from pathlib import Path

# ── Racine du projet ──────────────────────────────────────────────────
ROOT = Path(__file__).parent

# ── Données live (dxfeed_bridge.js → Live Signal) ─────────────────────
DXFEED_FILE  = os.environ.get("DXFEED_FILE",  r"C:\tmp\mnq_live.json")
JOURNAL_DB   = os.environ.get("JOURNAL_DB",   r"C:\tmp\mnq_journal.db")

# ── Données historiques (backtests) ───────────────────────────────────
MNQ_CSV = os.environ.get(
    "MNQ_CSV",
    r"C:\Users\ryadb\Downloads\5 ANS DATA MNQ OHLCV M1\glbx-mdp3-20210405-20260404.ohlcv-1m.csv"
)

# ── Challenge 4PropTrader (partagé Accueil + Live + Session Prep) ─────
CHALLENGE_DD     = float(os.environ.get("CHALLENGE_DD",     "2500"))
CHALLENGE_TARGET = float(os.environ.get("CHALLENGE_TARGET", "3000"))

# ── Alertes ───────────────────────────────────────────────────────────
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "hurst-mnq-ryad")
