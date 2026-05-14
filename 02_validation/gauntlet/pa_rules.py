"""Constantes du compte Apex $50K PA EOD. Source : help-center Apex, vérifié 2026-05-14.

Remplace les constantes Apex Eval périmées de 01_research/src/config.py (qui restent
pour la Couche 1 recherche). Le gauntlet utilise UNIQUEMENT pa_rules.
"""
from __future__ import annotations

# ── Compte ──────────────────────────────────────────────────────────
ACCOUNT_SIZE = 50_000.0
EOD_DD = 2_000.0                                # drawdown EOD max
EOD_THRESHOLD_INITIAL = ACCOUNT_SIZE - EOD_DD   # 48_000.0 — seuil au jour 1
EOD_THRESHOLD_LOCK = ACCOUNT_SIZE + 100.0       # 50_100.0 — seuil figé une fois atteint

# ── Tiers de scaling ────────────────────────────────────────────────
# (seuil_balance_EOD, contrats_std_max, daily_loss_limit). Le tier d'une balance =
# le plus haut tier dont le seuil est <= balance. Plancher L1 (jamais en dessous).
TIERS = [
    (50_000.0, 2, 1_000.0),   # L1 : balance >= 50_000
    (51_500.0, 3, 1_000.0),   # L2 : balance >= 51_500
    (53_000.0, 4, 2_000.0),   # L3 : balance >= 53_000
    (56_000.0, 4, 3_000.0),   # L4 : balance >= 56_000
]

# ── Contrats ────────────────────────────────────────────────────────
MICROS_PER_STANDARD = 10        # 10 contrats micro (MNQ) = 1 contrat standard (NQ)

# ── Force-flat (règle perso BB) ─────────────────────────────────────
FORCE_FLAT_NY = (15, 55)        # (heure, minute) America/New_York

# ── Inactivité ──────────────────────────────────────────────────────
INACTIVITY_MIN_GREEN_DAYS = 2       # jours à >= seuil de profit, par fenêtre glissante
INACTIVITY_GREEN_THRESHOLD = 50.0   # $ net pour qu'un jour "compte"
INACTIVITY_WINDOW_DAYS = 30         # fenêtre glissante (jours calendaires)


def tier_for_balance(balance: float) -> tuple[int, int, float]:
    """Retourne (level, contrats_std_max, daily_loss_limit) pour une balance EOD.

    Plancher L1 : une balance sous 50_000 reste au Level 1.
    """
    level, max_ctr, dll = 1, TIERS[0][1], TIERS[0][2]
    for i, (threshold, ctr, d) in enumerate(TIERS, start=1):
        if balance >= threshold:
            level, max_ctr, dll = i, ctr, d
        else:
            break
    return level, max_ctr, dll
