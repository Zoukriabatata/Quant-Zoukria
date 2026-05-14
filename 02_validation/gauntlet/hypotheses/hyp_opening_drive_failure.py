"""Hypothèse de recherche #1 — Opening Drive Failure Fade (MNQ).

Première vraie hypothèse de recherche passée dans le gauntlet. Le 1er move de l'open
MNQ est un faux spike (mèche, pas corps) ; on le fade, entrée sur exhaustion conditionnée
(gap overnight significatif + rejet de bougie + régime haute vol + volume), exit = retour
au prix d'open. Feature set littérature-grounded.

Spec : docs/superpowers/specs/2026-05-15-opening-drive-failure-fade-design.md
"""
from __future__ import annotations

from src.features import compute_signal_features, compute_features_opening_drive
from src.signals import signal_opening_drive_failure
from src.backtest import exit_logic_return_to_open

from gauntlet.hypothesis import Hypothesis

# ── Constantes figées (cf. spec — "défauts sensés", non grillés) ────
_BAR_MIN = 1
_TIMEOUT_BARS = 15      # ~15 min : l'observation dit que le faux move se résout vite
_LOOKBACK = 20          # lookback de compute_signal_features (std / mid pour backtest_pa)
_SPIKE_MIN = 15.0       # déplacement minimum du spike (points)
_REJET_SEUIL = 0.66     # rejection_body minimum
_RELVOL_SEUIL = 1.0     # confirmation volume


def _prepare_features(df):
    """Chaîne compute_signal_features (std/mid pour backtest_pa) puis les features
    Opening Drive (gap_z, spike_magnitude, rejection_body, vol_regime, relvol_open)."""
    df = compute_signal_features(df, lookback=_LOOKBACK)
    df = compute_features_opening_drive(df)
    return df


def _build_variant(params):
    """params: {'window_end_min': int, 'gap_threshold': float}.
    Retourne (signal_fn, exit_logic, backtest_kwargs)."""
    window_end_min = params["window_end_min"]
    gap_threshold = params["gap_threshold"]

    def signal_fn(df):
        return signal_opening_drive_failure(
            df, window_end_min=window_end_min, gap_threshold=gap_threshold,
            spike_min=_SPIKE_MIN, rejet_seuil=_REJET_SEUIL, relvol_seuil=_RELVOL_SEUIL,
        )

    return signal_fn, exit_logic_return_to_open, {
        "bar_size_min": _BAR_MIN, "timeout_bars": _TIMEOUT_BARS,
    }


HYP_OPENING_DRIVE_FAILURE = Hypothesis(
    name="opening_drive_failure",
    description=("Opening Drive Failure Fade MNQ 1min — fade le faux spike d'open, "
                 "conditionné gap overnight + rejet + régime haute vol, exit retour open"),
    instrument="MNQ",
    timeframe="1min",
    build_variant=_build_variant,
    param_grid=[
        {"window_end_min": 600, "gap_threshold": 0.5},   # 9:30-10:00, gap 0.5σ
        {"window_end_min": 600, "gap_threshold": 1.0},   # 9:30-10:00, gap 1.0σ
        {"window_end_min": 630, "gap_threshold": 0.5},   # 9:30-10:30, gap 0.5σ
        {"window_end_min": 630, "gap_threshold": 1.0},   # 9:30-10:30, gap 1.0σ
    ],
    prepare_features=_prepare_features,
)
