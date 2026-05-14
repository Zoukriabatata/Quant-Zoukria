"""Generators de signaux : MR Z-score, RSI extreme, ORB breakout.

Tous les signaux gèrent Apex-compliance (entry cutoff 15:55 NY) via entry_cutoff_ny_min.
Mettre entry_cutoff_ny_min=None pour désactiver (mode baseline non-Apex).
"""
from __future__ import annotations
from typing import Optional

import pandas as pd

from .config import ENTRY_CUTOFF_NY_MIN


def signal_mr_zscore(df: pd.DataFrame, entry_threshold: float = 2.0,
                     allowed_hours: Optional[set] = None,
                     entry_cutoff_ny_min: Optional[int] = ENTRY_CUTOFF_NY_MIN,
                     bar_size_min: int = 1) -> pd.DataFrame:
    """Signal MR Z-score : LONG si z < -threshold, SHORT si z > threshold.

    Args:
        df: DataFrame avec colonnes ['zscore', 'std', 'mid', 'hour_ny', 'min_ny'].
        entry_threshold: |z| > threshold pour entrer.
        allowed_hours: ensemble d'heures NY autorisées. None = toutes.
        entry_cutoff_ny_min: cutoff (en min NY locale) au-delà duquel l'entry est interdite.
        bar_size_min: taille bar en min (pour calculer le close time NY).

    Returns: copy de df + colonne 'signal' (+1 LONG, -1 SHORT, 0 none).
    """
    out = df.copy()
    out['signal'] = 0
    in_pocket = (out['hour_ny'].isin(allowed_hours)) if allowed_hours else True
    valid = out['zscore'].notna() & out['std'].notna() & (out['std'] > 0) & in_pocket
    if entry_cutoff_ny_min is not None:
        close_min_ny = out['hour_ny'] * 60 + out['min_ny'] + bar_size_min
        valid = valid & (close_min_ny <= entry_cutoff_ny_min)
    out.loc[valid & (out['zscore'] > entry_threshold), 'signal']  = -1
    out.loc[valid & (out['zscore'] < -entry_threshold), 'signal'] = +1
    return out


def signal_rsi_extreme(df: pd.DataFrame, low_threshold: float = 30, high_threshold: float = 70,
                       allowed_hours: Optional[set] = None,
                       entry_cutoff_ny_min: Optional[int] = ENTRY_CUTOFF_NY_MIN,
                       bar_size_min: int = 1) -> pd.DataFrame:
    """Signal RSI extreme reversal : LONG si RSI<low (oversold), SHORT si RSI>high (overbought).

    Args:
        df: DataFrame avec colonnes ['rsi', 'std', 'hour_ny', 'min_ny'].
    """
    out = df.copy()
    out['signal'] = 0
    in_pocket = (out['hour_ny'].isin(allowed_hours)) if allowed_hours else True
    valid = out['rsi'].notna() & out['std'].notna() & (out['std'] > 0) & in_pocket
    if entry_cutoff_ny_min is not None:
        close_min_ny = out['hour_ny'] * 60 + out['min_ny'] + bar_size_min
        valid = valid & (close_min_ny <= entry_cutoff_ny_min)
    out.loc[valid & (out['rsi'] < low_threshold), 'signal']  = +1
    out.loc[valid & (out['rsi'] > high_threshold), 'signal'] = -1
    return out


def signal_orb(df: pd.DataFrame,
               allowed_hours: Optional[set] = None,
               entry_cutoff_ny_min: Optional[int] = ENTRY_CUTOFF_NY_MIN,
               bar_size_min: int = 1) -> pd.DataFrame:
    """Signal ORB : LONG si close break or_high, SHORT si close break or_low (post-OR only).

    Args:
        df: DataFrame avec colonnes ['post_or', 'or_high', 'or_low', 'close', 'hour_ny', 'min_ny'].
            Utiliser compute_features_orb() d'abord pour obtenir ces colonnes.

    Raises:
        ValueError: si features ORB absentes.
    """
    out = df.copy()
    out['signal'] = 0
    if 'post_or' not in out.columns or 'or_high' not in out.columns:
        raise ValueError("ORB features required: appeler compute_features_orb() d'abord")
    in_pocket = (out['hour_ny'].isin(allowed_hours)) if allowed_hours else True
    valid = out['post_or'] & out['or_high'].notna() & out['or_low'].notna() & in_pocket
    if entry_cutoff_ny_min is not None:
        close_min_ny = out['hour_ny'] * 60 + out['min_ny'] + bar_size_min
        valid = valid & (close_min_ny <= entry_cutoff_ny_min)
    out.loc[valid & (out['close'] > out['or_high']), 'signal'] = +1
    out.loc[valid & (out['close'] < out['or_low']), 'signal']  = -1
    return out


def signal_opening_drive_failure(df: pd.DataFrame,
                                 window_end_min: int = 630,
                                 gap_threshold: float = 0.5,
                                 spike_min: float = 15.0,
                                 rejet_seuil: float = 0.66,
                                 relvol_seuil: float = 1.0) -> pd.DataFrame:
    """Signal Opening Drive Failure Fade : fade le faux spike d'open (cf. spec 2026-05-15).

    Down-spike -> LONG, up-spike -> SHORT, déclenché quand 5 conditions s'alignent :
    gap overnight significatif, spike notable, rejet de bougie (exhaustion), régime de
    volatilité élevé, confirmation volume. Comparaisons avec NaN -> False -> signal 0.

    Nécessite les colonnes (via compute_features_opening_drive) : gap_z,
    spike_magnitude, rejection_body, vol_regime, relvol_open, hour_ny, min_ny.

    Args:
        window_end_min: fin de la fenêtre en minutes NY locales (600 = 10:00, 630 = 10:30).
        gap_threshold: |gap_z| minimum (en σ) pour un setup valide.
        spike_min: déplacement minimum (points) du close vs open_ref.
        rejet_seuil: rejection_body minimum pour un rejet de down-spike (LONG).
        relvol_seuil: relvol_open minimum (confirmation volume).

    Returns: copy de df + colonne 'signal' (+1 LONG, -1 SHORT, 0 none).
    """
    out = df.copy()
    out['signal'] = 0
    ny_min = out['hour_ny'] * 60 + out['min_ny']
    in_window = (ny_min >= 9 * 60 + 30) & (ny_min < window_end_min)

    long_cond = (
        in_window
        & (out['gap_z'] <= -gap_threshold)
        & (out['spike_magnitude'] <= -spike_min)
        & (out['rejection_body'] >= rejet_seuil)
        & (out['vol_regime'])
        & (out['relvol_open'] >= relvol_seuil)
    )
    short_cond = (
        in_window
        & (out['gap_z'] >= gap_threshold)
        & (out['spike_magnitude'] >= spike_min)
        & (out['rejection_body'] <= 1.0 - rejet_seuil)
        & (out['vol_regime'])
        & (out['relvol_open'] >= relvol_seuil)
    )
    out.loc[long_cond, 'signal'] = 1
    out.loc[short_cond, 'signal'] = -1
    return out
