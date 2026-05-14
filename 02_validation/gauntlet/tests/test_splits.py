"""Tests des splits Train/Valid/Holdout + embargo."""
import pandas as pd

from gauntlet.splits import split_train, split_valid, split_holdout


def _synthetic_df():
    """DataFrame horaire couvrant Train, Valid et Holdout (2021-05 -> 2026-05)."""
    idx = pd.date_range("2021-05-13", "2026-05-13", freq="1D", tz="UTC")
    return pd.DataFrame({"close": range(len(idx))}, index=idx)


def test_split_train_borne_les_dates():
    df = _synthetic_df()
    tr = split_train(df)
    assert tr.index.min() >= pd.Timestamp("2021-05-13", tz="UTC")
    assert tr.index.max() < pd.Timestamp("2024-05-13", tz="UTC")


def test_split_valid_borne_les_dates():
    df = _synthetic_df()
    va = split_valid(df)
    assert va.index.min() >= pd.Timestamp("2024-05-13", tz="UTC")
    assert va.index.max() < pd.Timestamp("2025-05-13", tz="UTC")


def test_split_holdout_borne_les_dates():
    df = _synthetic_df()
    ho = split_holdout(df)
    assert ho.index.min() >= pd.Timestamp("2025-05-13", tz="UTC")
    assert ho.index.max() < pd.Timestamp("2026-05-13", tz="UTC")


def test_splits_ne_se_chevauchent_pas():
    df = _synthetic_df()
    tr, va, ho = split_train(df), split_valid(df), split_holdout(df)
    assert tr.index.max() < va.index.min()
    assert va.index.max() < ho.index.min()


def test_embargo_jette_les_dernieres_barres():
    df = _synthetic_df()
    tr_full = split_train(df)
    tr_embargo = split_train(df, embargo_bars=5)
    assert len(tr_embargo) == len(tr_full) - 5
    assert tr_embargo.index.max() < tr_full.index.max()
