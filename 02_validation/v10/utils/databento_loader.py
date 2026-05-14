"""
Loader pour fichiers Databento format GLBX.MDP.3 .csv.zst.

Construit des séries continues front-month pour ES, NQ, MNQ, MES en :
    1. Décompressant le fichier zstd
    2. Filtrant le symbole racine (ESxx, NQxx, ...)
    3. Détectant les rollovers (jour où le contrat dominant change)
    4. Sélectionnant pour chaque timestamp le contrat le plus liquide

Format colonnes attendu Databento :
    ts_event,open,high,low,close,volume,symbol,[...]
"""
from __future__ import annotations

import os
from typing import Set

import pandas as pd
import zstandard as zstd


def load_databento_zst(path: str) -> pd.DataFrame:
    """
    Charge un CSV Databento compressé en zstd.

    Returns
    -------
    pd.DataFrame
        Colonnes : ts_event (datetime), open, high, low, close, volume, symbol.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Fichier introuvable : {path}")

    # Databento utilise du multi-frame zstd → utiliser stream_reader
    dctx = zstd.ZstdDecompressor()
    with open(path, "rb") as f:
        with dctx.stream_reader(f) as reader:
            df = pd.read_csv(reader)
    # Conversion ts_event
    df["ts_event"] = pd.to_datetime(df["ts_event"], utc=True, errors="coerce")
    df = df.dropna(subset=["ts_event"])
    # Types numériques
    for col in ("open", "high", "low", "close"):
        if col in df.columns:
            df[col] = df[col].astype(float)
    if "volume" in df.columns:
        df["volume"] = df["volume"].fillna(0).astype("int64")
    return df


def detect_rollover_dates(df: pd.DataFrame, symbol_root: str) -> Set[str]:
    """
    Détecte les dates de rollover pour un symbole racine donné.

    Pour chaque jour, on identifie le contrat le plus liquide (volume max).
    Un rollover survient quand le contrat dominant change d'un jour à l'autre.
    Les jours de rollover ET les jours adjacents sont marqués (transition).

    Parameters
    ----------
    df : pd.DataFrame
        Output de load_databento_zst.
    symbol_root : str
        Racine du symbole (ex: "ES", "NQ", "MNQ", "MES").

    Returns
    -------
    set of str
        Dates au format YYYY-MM-DD où un rollover survient ou est imminent.
    """
    # Filtrer symboles du root (ESxx) en excluant spreads (contiennent "-")
    mask = df["symbol"].str.startswith(symbol_root) & ~df["symbol"].str.contains("-", na=False)
    sub = df[mask].copy()
    if sub.empty:
        return set()

    sub["date"] = sub["ts_event"].dt.date.astype(str)
    # Volume total par (date, symbol)
    daily_vol = sub.groupby(["date", "symbol"])["volume"].sum().reset_index()
    # Dominant par jour
    idx_max = daily_vol.groupby("date")["volume"].idxmax()
    dom = daily_vol.loc[idx_max, ["date", "symbol"]].rename(columns={"symbol": "dominant"})
    dom = dom.sort_values("date").reset_index(drop=True)
    dom["prev"] = dom["dominant"].shift(1)
    dom["roll"] = (dom["dominant"] != dom["prev"]) & dom["prev"].notna()
    # Inclure aussi le jour adjacent (transition lissée)
    dom["roll"] = (dom["roll"] | dom["roll"].shift(-1).fillna(False)).astype(bool)
    return set(dom.loc[dom["roll"], "date"])


def build_continuous_front_month(
    path: str,
    symbol_root: str,
    exclude_rollover_days: bool = True,
) -> pd.DataFrame:
    """
    Construit une série continue front-month en sélectionnant pour chaque
    timestamp le contrat le plus liquide du root donné.

    Parameters
    ----------
    path : str
        Chemin du fichier .csv.zst Databento.
    symbol_root : str
        Racine symbole (ES, NQ, MNQ, MES).
    exclude_rollover_days : bool, default True
        Si True, exclut les jours de rollover (et adjacents) pour éviter
        les artefacts de transition de contrat.

    Returns
    -------
    pd.DataFrame
        Index temporel UTC, colonnes : ts_event, open, high, low, close, volume,
        symbol (contrat dominant à ce moment).
    """
    df = load_databento_zst(path)
    mask = df["symbol"].str.startswith(symbol_root) & ~df["symbol"].str.contains("-", na=False)
    sub = df[mask].copy()
    if sub.empty:
        return pd.DataFrame(columns=df.columns)

    # Pour chaque ts_event, garde le contrat avec le volume max
    sub_sorted = sub.sort_values(["ts_event", "volume"], ascending=[True, False])
    cont = sub_sorted.groupby("ts_event", as_index=False).first()

    if exclude_rollover_days:
        roll_dates = detect_rollover_dates(df, symbol_root)
        cont["date"] = cont["ts_event"].dt.date.astype(str)
        cont = cont[~cont["date"].isin(roll_dates)].drop(columns="date")

    cont = cont.sort_values("ts_event").reset_index(drop=True)
    return cont
