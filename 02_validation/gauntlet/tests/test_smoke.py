"""Sentinelle : le package gauntlet et la config 01_research sont importables."""


def test_gauntlet_package_importable():
    import gauntlet  # noqa: F401


def test_research_config_importable():
    from src.config import TRAIN_START, HOLDOUT_END  # noqa: F401
