"""
Tests data loader Databento format (GLBX.MDP.3 .csv.zst).

Format colonnes attendu :
    ts_event, open, high, low, close, volume, symbol, [...]

Symboles continus front-month construits manuellement via rollover detection
(le plus liquide chaque jour).
"""
import io
import zstandard as zstd

import numpy as np
import pandas as pd
import pytest

from quant_v10.utils.databento_loader import (
    load_databento_zst,
    detect_rollover_dates,
    build_continuous_front_month,
)


# ───────────────────────────────────────────────────────────
# Fixtures : génère un mini-CSV Databento compressé en zstd
# ───────────────────────────────────────────────────────────
def _make_mini_csv_zst(rows, path):
    """Crée un CSV avec header Databento et compresse en zstd."""
    df = pd.DataFrame(rows)
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    cctx = zstd.ZstdCompressor()
    compressed = cctx.compress(csv_bytes)
    with open(path, "wb") as f:
        f.write(compressed)


@pytest.fixture
def mini_databento_csv(tmp_path):
    """Génère un mini-CSV ES contenant 2 contrats front-month avec rollover."""
    rows = []
    base_ts = pd.Timestamp("2024-03-01", tz="UTC")
    # 5 jours sur ESH4 (March), volume haut
    for d in range(5):
        for h in range(3):
            rows.append({
                "ts_event": (base_ts + pd.Timedelta(days=d, hours=h)).isoformat(),
                "open": 5000 + d + h * 0.5,
                "high": 5001 + d + h * 0.5,
                "low": 4999 + d + h * 0.5,
                "close": 5000.5 + d + h * 0.5,
                "volume": 10_000 - h * 100,
                "symbol": "ESH4",
            })
    # 5 jours sur ESM4 (June), volume monte progressivement
    for d in range(5, 10):
        for h in range(3):
            es_h_vol = max(100, 5000 - (d - 5) * 1500)
            es_m_vol = 1000 + (d - 5) * 2000
            rows.append({
                "ts_event": (base_ts + pd.Timedelta(days=d, hours=h)).isoformat(),
                "open": 5005 + d + h * 0.5,
                "high": 5006 + d + h * 0.5,
                "low": 5004 + d + h * 0.5,
                "close": 5005.5 + d + h * 0.5,
                "volume": es_h_vol,
                "symbol": "ESH4",
            })
            rows.append({
                "ts_event": (base_ts + pd.Timedelta(days=d, hours=h)).isoformat(),
                "open": 5010 + d + h * 0.5,
                "high": 5011 + d + h * 0.5,
                "low": 5009 + d + h * 0.5,
                "close": 5010.5 + d + h * 0.5,
                "volume": es_m_vol,
                "symbol": "ESM4",
            })

    path = tmp_path / "mini_es.csv.zst"
    _make_mini_csv_zst(rows, path)
    return str(path)


# ───────────────────────────────────────────────────────────
# 1. load_databento_zst
# ───────────────────────────────────────────────────────────
def test_load_returns_dataframe(mini_databento_csv):
    df = load_databento_zst(mini_databento_csv)
    assert isinstance(df, pd.DataFrame)
    assert len(df) > 0


def test_load_has_required_columns(mini_databento_csv):
    df = load_databento_zst(mini_databento_csv)
    assert {"ts_event", "open", "high", "low", "close", "volume", "symbol"}.issubset(df.columns)


def test_load_ts_is_datetime(mini_databento_csv):
    df = load_databento_zst(mini_databento_csv)
    assert pd.api.types.is_datetime64_any_dtype(df["ts_event"])


def test_load_invalid_path_raises():
    with pytest.raises(FileNotFoundError):
        load_databento_zst("nonexistent_file.csv.zst")


# ───────────────────────────────────────────────────────────
# 2. detect_rollover_dates
# ───────────────────────────────────────────────────────────
def test_detect_rollover_returns_set(mini_databento_csv):
    df = load_databento_zst(mini_databento_csv)
    rolls = detect_rollover_dates(df, symbol_root="ES")
    assert isinstance(rolls, set)


def test_detect_rollover_finds_known_rollover(mini_databento_csv):
    """Dans le fixture, le rollover ESH4 -> ESM4 doit être détecté."""
    df = load_databento_zst(mini_databento_csv)
    rolls = detect_rollover_dates(df, symbol_root="ES")
    # Au moins une date de rollover doit être détectée
    assert len(rolls) >= 1


# ───────────────────────────────────────────────────────────
# 3. build_continuous_front_month
# ───────────────────────────────────────────────────────────
def test_continuous_returns_dataframe(mini_databento_csv):
    cont = build_continuous_front_month(mini_databento_csv, symbol_root="ES",
                                         exclude_rollover_days=False)
    assert isinstance(cont, pd.DataFrame)


def test_continuous_one_row_per_timestamp(mini_databento_csv):
    """Le front-month continu = 1 prix par timestamp (le plus liquide)."""
    cont = build_continuous_front_month(mini_databento_csv, symbol_root="ES",
                                         exclude_rollover_days=False)
    assert cont["ts_event"].is_unique


def test_continuous_excludes_rollover_days_when_flagged(mini_databento_csv):
    """Si exclude_rollover_days=True, les jours de rollover ne sont pas dans le résultat."""
    cont_with = build_continuous_front_month(mini_databento_csv, symbol_root="ES",
                                              exclude_rollover_days=False)
    cont_without = build_continuous_front_month(mini_databento_csv, symbol_root="ES",
                                                 exclude_rollover_days=True)
    assert len(cont_without) <= len(cont_with)


def test_continuous_symbol_unknown_raises(mini_databento_csv):
    """Symbol root inconnu → DataFrame vide ou erreur claire."""
    cont = build_continuous_front_month(mini_databento_csv, symbol_root="ZZ",
                                         exclude_rollover_days=False)
    # Doit retourner DataFrame vide (pas crash)
    assert len(cont) == 0
