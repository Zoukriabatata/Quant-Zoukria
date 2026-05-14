"""PaAccount — simulateur de compte Apex $50K PA EOD (machine à états).

Deux mécaniques de risque DISTINCTES :
  - Seuil DD EOD : touché en intraday -> compte MORT (status 'dead_eod').
  - DLL          : touchée en intraday -> journée STOPPÉE, compte vivant.

PaAccount tient l'état ; il ne fait pas de backtest. Le backtest (backtest.py) le fait
avancer : record_trade() à chaque trade clos, check_intraday() à chaque barre,
start_session()/end_session() aux frontières de journée.
"""
from __future__ import annotations

from gauntlet.pa_rules import (
    ACCOUNT_SIZE, EOD_DD, EOD_THRESHOLD_INITIAL, EOD_THRESHOLD_LOCK, tier_for_balance,
)


class PaAccount:
    """État d'un compte PA EOD 50K, simulé dans le temps."""

    def __init__(self):
        self.balance: float = ACCOUNT_SIZE
        self.highest_eod_close: float = ACCOUNT_SIZE
        self.eod_threshold: float = EOD_THRESHOLD_INITIAL
        self.status: str = "alive"               # 'alive' | 'dead_eod'
        self.day_paused: bool = False            # DLL touchée dans la session courante
        self.session_start_balance: float = ACCOUNT_SIZE
        level, max_ctr, dll = tier_for_balance(self.balance)
        self.tier: int = level
        self.max_contracts_std: int = max_ctr
        self.dll: float = dll
        self.daily_history: list = []            # [(date, eod_close_balance, tier), ...]

    @property
    def threshold_locked(self) -> bool:
        """Le seuil EOD a-t-il atteint son plafond figé ($50,100) ?"""
        return self.eod_threshold >= EOD_THRESHOLD_LOCK

    def start_session(self, date) -> None:
        """Ouverture d'une journée de trading : reset l'état journalier."""
        if self.status == "alive":
            self.day_paused = False
        self.session_start_balance = self.balance

    def can_trade(self) -> bool:
        """True si on peut ouvrir un nouveau trade (compte vivant ET journée non stoppée)."""
        return self.status == "alive" and not self.day_paused

    def check_intraday(self, equity: float) -> str:
        """Vérifie les limites à partir de l'equity courante (balance + PnL non réalisé).

        Retourne 'dead' (seuil EOD touché -> compte mort), 'day_paused' (DLL touchée),
        ou 'ok'.
        """
        if self.status == "dead_eod":
            return "dead"
        # 1) Seuil DD EOD — touché = mort définitive
        if equity <= self.eod_threshold:
            self.status = "dead_eod"
            return "dead"
        # 2) Déjà en pause journée -> rien de plus à faire
        if self.day_paused:
            return "day_paused"
        # 3) Daily Loss Limit — perte du jour vs balance d'ouverture de session
        if (equity - self.session_start_balance) <= -self.dll:
            self.day_paused = True
            return "day_paused"
        return "ok"

    def record_trade(self, pnl: float) -> None:
        """Enregistre le P&L réalisé d'un trade clos."""
        self.balance += pnl

    def end_session(self, date) -> None:
        """Clôture d'une journée : met à jour le seuil EOD, le tier, l'historique.

        À appeler APRÈS le force-flat (toutes les positions sont closes -> balance = equity).
        """
        eod_close = self.balance
        if eod_close > self.highest_eod_close:
            self.highest_eod_close = eod_close
        # Le seuil trail la plus haute clôture, plafonné au lock. Monotone croissant car
        # highest_eod_close ne fait que monter -> le seuil "ne descend jamais".
        self.eod_threshold = min(self.highest_eod_close - EOD_DD, EOD_THRESHOLD_LOCK)
        # Tier pour la session suivante, calculé sur la balance de clôture.
        level, max_ctr, dll = tier_for_balance(eod_close)
        self.tier, self.max_contracts_std, self.dll = level, max_ctr, dll
        self.daily_history.append((date, eod_close, level))
