"""Specs contracts par instrument (Databento path, point value, tick size, commission, plafond Apex)."""
from __future__ import annotations
from pathlib import Path

# Contract specs cohérents avec backtests Apex-compliant phase recherche
INSTRUMENTS = {
    'MNQ': {
        'path': Path(r'C:\Users\ryadb\Downloads\MNQ 5ANS DATA\glbx-mdp3-20210513-20260512.ohlcv-1m.csv.zst'),
        'root': 'MNQ',
        'point_value': 2.00,    # $ par point
        'tick_size': 0.25,      # 1 tick = 0.25 pt = $0.50
        'commission_rt': 1.10,  # round-trip Apex/CME retail
        'max_contracts_eval': 40,
        'sl_floor_pts': 5.0,
        'sl_cap_pts': 10.0,
    },
    'NQ': {
        'path': Path(r'NQ 5ANS DATA\glbx-mdp3-20210513-20260512.ohlcv-1m.csv.zst'),
        'root': 'NQ',
        'point_value': 20.00,
        'tick_size': 0.25,      # 1 tick = $5
        'commission_rt': 4.50,
        'max_contracts_eval': 10,
        'sl_floor_pts': 5.0,
        'sl_cap_pts': 10.0,
    },
    'ES': {
        'path': Path(r'ES 5ANS DATA\glbx-mdp3-20210513-20260512.ohlcv-1m.csv.zst'),
        'root': 'ES',
        'point_value': 50.00,   # $ par point
        'tick_size': 0.25,      # 1 tick = $12.50
        'commission_rt': 4.50,
        'max_contracts_eval': 10,
        'sl_floor_pts': 1.0,    # ES bouge ~3× moins en pts qu'NQ
        'sl_cap_pts': 2.0,
    },
}

SLIPPAGE_TICKS = 1
