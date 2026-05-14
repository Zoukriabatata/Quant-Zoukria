"""
HAR-RV — Heterogeneous Autoregressive Realized Volatility (Corsi 2009).

Modèle de forecast de volatilité multi-horizons capturant l'hétérogénéité
des agents de marché (intraday / hebdo / mensuel).

Mathématique :
    RV_{t+1} = c + beta_d * RV_t + beta_w * RV_t^{(w)} + beta_m * RV_t^{(m)}
              + epsilon_{t+1}

avec :
    RV_t       = sum_i r_{t,i}^2  (réalisation quotidienne)
    RV_t^{(w)} = moyenne RV sur 5 derniers jours
    RV_t^{(m)} = moyenne RV sur 22 derniers jours

Reference: Corsi, F. (2009). "A Simple Approximate Long-Memory Model of
Realized Volatility", Journal of Financial Econometrics 7(2), 174-196.

Usage dans le pipeline v10 :
    Forecast vol t+1 -> input du sizing (Grossman-Zhou) à la place de la
    std réalisée naïve.
"""
from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd


_MIN_OBS = 23  # 22 lags + 1 cible minimum


def compute_realized_volatility(intraday_returns: pd.Series) -> pd.Series:
    """
    Agrège les returns intraday en realized variance quotidienne.

    Parameters
    ----------
    intraday_returns : pd.Series
        Returns simples ou log-returns, indexés par datetime (intraday).

    Returns
    -------
    pd.Series
        RV quotidienne = somme des r^2 par jour calendaire.
    """
    if not isinstance(intraday_returns.index, pd.DatetimeIndex):
        raise ValueError("intraday_returns doit avoir un DatetimeIndex")

    squared = intraday_returns ** 2
    rv_daily = squared.groupby(squared.index.normalize()).sum()
    rv_daily.name = "rv"
    return rv_daily


def _build_har_features(rv: pd.Series) -> pd.DataFrame:
    """
    Construit la matrice de features HAR : RV_t (daily), RV_t^{(w)}, RV_t^{(m)}.

    Returns aligned DataFrame avec colonnes ['rv_d', 'rv_w', 'rv_m', 'target'].
    `target` = RV_{t+1}.
    """
    df = pd.DataFrame({"rv": rv})
    df["rv_d"] = df["rv"]                              # daily = RV_t
    df["rv_w"] = df["rv"].rolling(window=5).mean()     # weekly avg
    df["rv_m"] = df["rv"].rolling(window=22).mean()    # monthly avg
    df["target"] = df["rv"].shift(-1)                  # prédire RV_{t+1}
    return df


def fit_har_rv(rv: pd.Series) -> Dict[str, float]:
    """
    Estime les coefficients HAR-RV par OLS sur l'ensemble de la série fournie.

    Parameters
    ----------
    rv : pd.Series
        Series de realized variance quotidienne.

    Returns
    -------
    dict
        - 'c'      : constante
        - 'beta_d' : coefficient daily
        - 'beta_w' : coefficient weekly
        - 'beta_m' : coefficient monthly
        - 'r2'     : R^2 in-sample
    """
    if len(rv) < _MIN_OBS:
        raise ValueError(
            f"Au moins {_MIN_OBS} observations requises, reçu {len(rv)}"
        )

    df = _build_har_features(rv).dropna()
    if len(df) < 5:
        raise ValueError("Pas assez d'observations valides après alignement HAR")

    X = df[["rv_d", "rv_w", "rv_m"]].to_numpy()
    y = df["target"].to_numpy()

    # Design matrix avec intercept
    X_design = np.column_stack([np.ones(len(X)), X])

    # OLS : (X'X)^{-1} X'y — utilise lstsq pour stabilité numérique
    coeffs, *_ = np.linalg.lstsq(X_design, y, rcond=None)
    c, beta_d, beta_w, beta_m = coeffs

    # R²
    y_hat = X_design @ coeffs
    ss_res = np.sum((y - y_hat) ** 2)
    ss_tot = np.sum((y - y.mean()) ** 2)
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    r2 = max(0.0, min(1.0, r2))

    return {
        "c": float(c),
        "beta_d": float(beta_d),
        "beta_w": float(beta_w),
        "beta_m": float(beta_m),
        "r2": float(r2),
    }


def forecast_har_rv(rv: pd.Series, lookback: int = 252) -> pd.Series:
    """
    Forecast rolling de RV_{t+1} via HAR-RV ré-estimé sur fenêtre `lookback`.

    Pour chaque date t :
        1. fit HAR sur rv[t-lookback : t]
        2. forecast RV_{t+1} = c + b_d*rv_d + b_w*rv_w + b_m*rv_m  (features à t)

    Parameters
    ----------
    rv : pd.Series
        RV quotidienne.
    lookback : int, default 252
        Fenêtre de ré-estimation (1 an de jours ouvrés).

    Returns
    -------
    pd.Series
        Forecast indexé par t (la valeur prédit RV_{t+1}).
        NaN pendant la période de warm-up (lookback + 22 premiers points).
    """
    if lookback < _MIN_OBS:
        raise ValueError(f"lookback doit être >= {_MIN_OBS}, reçu {lookback}")

    feats = _build_har_features(rv)
    forecast = pd.Series(np.nan, index=rv.index, name="har_rv_forecast")

    warmup = lookback + 22
    n = len(rv)
    if n <= warmup:
        return forecast

    # Pré-extraction numpy pour rapidité (rolling OLS)
    rv_d_arr = feats["rv_d"].to_numpy()
    rv_w_arr = feats["rv_w"].to_numpy()
    rv_m_arr = feats["rv_m"].to_numpy()
    target_arr = feats["target"].to_numpy()

    for t in range(warmup, n):
        start = t - lookback
        end = t  # exclu

        Xd = rv_d_arr[start:end]
        Xw = rv_w_arr[start:end]
        Xm = rv_m_arr[start:end]
        y = target_arr[start:end]

        mask = ~(np.isnan(Xd) | np.isnan(Xw) | np.isnan(Xm) | np.isnan(y))
        if mask.sum() < _MIN_OBS:
            continue

        X_design = np.column_stack(
            [np.ones(mask.sum()), Xd[mask], Xw[mask], Xm[mask]]
        )
        y_clean = y[mask]

        try:
            coeffs, *_ = np.linalg.lstsq(X_design, y_clean, rcond=None)
        except np.linalg.LinAlgError:
            continue

        # Features courants à l'instant t
        feat_t = np.array([1.0, rv_d_arr[t], rv_w_arr[t], rv_m_arr[t]])
        if np.isnan(feat_t).any():
            continue

        fc = float(feat_t @ coeffs)
        forecast.iloc[t] = max(fc, 1e-12)  # clip strict positif

    return forecast
