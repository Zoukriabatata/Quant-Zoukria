"""Configuration globale — splits LdP, params signal Hurst_MR v9, Apex Eval rules."""
from __future__ import annotations
from pathlib import Path
import pandas as pd

# ════════════════════════════════════════════════════════════════════
# Splits Lopez de Prado (figés 2026-05-14)
# ════════════════════════════════════════════════════════════════════
TRAIN_START   = pd.Timestamp('2021-05-13', tz='UTC')
TRAIN_END     = pd.Timestamp('2024-05-13', tz='UTC')   # 3 ans
VALID_START   = TRAIN_END
VALID_END     = pd.Timestamp('2025-05-13', tz='UTC')   # 1 an
HOLDOUT_START = VALID_END
HOLDOUT_END   = pd.Timestamp('2026-05-13', tz='UTC')   # 1 an INTOUCHÉ jusqu'au verdict final

# ════════════════════════════════════════════════════════════════════
# Apex Trader Funding $50K Evaluation (règles officielles 2026)
# ════════════════════════════════════════════════════════════════════
APEX_CAPITAL          = 50_000
APEX_PROFIT_TARGET    = 3_000
APEX_TRAILING_DD      = 2_000
APEX_DAILY_LIMIT      = 1_000
APEX_MAX_MICROS       = 40             # MNQ, MES, MGC, etc.
APEX_MAX_MINIS        = 10             # NQ, ES, CL, GC, etc.
ENTRY_CUTOFF_NY_MIN   = 15 * 60 + 55   # entry interdite si close > 15:55 NY locale
EXIT_FORCE_NY_MIN     = 15 * 60 + 59   # force-flat MTM au close <= 15:59 NY locale

# ════════════════════════════════════════════════════════════════════
# Hurst_MR v9 — Config champion 2026-05-12 (cf. 03_spec/hurst_mr_v9_spec.md)
# ════════════════════════════════════════════════════════════════════
HURST_THRESHOLD = 0.58       # H < seuil → régime MR exploitable
HURST_WINDOW    = 50         # rolling Hurst sur log-returns
LOOKBACK        = 19         # rolling mean/std pour Z-score
BAND_K          = 2.75       # |z| > BAND_K → entrée signal
SL_MULT         = 0.65       # SL = SL_MULT × std (borné par floor/cap)
SL_FLOOR_PTS    = 5.0        # SL minimum en points MNQ (théorème Leung)
SL_CAP_PTS      = 20.0       # SL maximum en points MNQ
TP_OVERSHOOT    = 0.15       # TP = mid ± TP_OVERSHOOT × std
TIMEOUT_BARS    = 120        # liquidation MTM si ni TP ni SL touché
TRAIL_ENABLED   = True
TRAIL_H_THRESH  = 0.51       # trail actif quand H > seuil (régime trending)
STD_MIN         = 1.0        # filtre anti fake-stops (vol minimum en points)
MAX_TRADES_DAY  = 20
KELLY_RISK_PCT  = 0.12       # 12% du DD restant par trade
MAX_CONTRACTS_EVAL = 12      # plafond MNQ champion v9 (≠ plafond Apex 40 micros)

# ════════════════════════════════════════════════════════════════════
# Default paths
# ════════════════════════════════════════════════════════════════════
DEFAULT_MNQ_CSV = Path(r'C:\Users\ryadb\Downloads\MNQ 5ANS DATA\glbx-mdp3-20210513-20260512.ohlcv-1m.csv.zst')
