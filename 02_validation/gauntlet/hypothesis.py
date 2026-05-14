"""L'interface Hypothesis : l'objet enfichable que le gauntlet juge."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class Hypothesis:
    """Une hypothèse de stratégie, prête à passer dans le gauntlet.

    Champs :
        name           : identifiant court (sert au nom du dossier d'output).
        description    : l'énoncé de l'hypothèse en une phrase.
        instrument     : clé dans INSTRUMENTS (ex. 'MNQ').
        timeframe      : règle de resampling pandas (ex. '5min').
        build_variant  : callable(params: dict) -> (signal_fn, exit_logic, backtest_kwargs).
                         Produit le couple signal/exit pour UN jeu de params.
        param_grid     : list[dict] — la petite grille délibérée de params à tester.
                         n_trials = len(param_grid), utilisé pour le Deflated Sharpe.
        prepare_features : callable(df) -> df OPTIONNEL. Calcule les features dont la
                         signal_fn a besoin (mid/std/zscore, Hurst rolling…). Appliqué
                         UNE fois sur le df de session complet avant le découpage en
                         splits — les features sont backward-looking, donc les calculer
                         puis slicer ne fuit rien. None -> df de session utilisé tel quel.
    """
    name: str
    description: str
    instrument: str
    timeframe: str
    build_variant: Callable
    param_grid: list
    prepare_features: Optional[Callable] = None

    def __post_init__(self):
        if not self.param_grid:
            raise ValueError(f"Hypothesis '{self.name}': param_grid est vide")
        if not callable(self.build_variant):
            raise TypeError(f"Hypothesis '{self.name}': build_variant doit être callable")
        if self.prepare_features is not None and not callable(self.prepare_features):
            raise TypeError(
                f"Hypothesis '{self.name}': prepare_features doit être callable ou None"
            )

    @property
    def n_trials(self) -> int:
        """Nombre de variants testés — alimente la pénalité du Deflated Sharpe."""
        return len(self.param_grid)
