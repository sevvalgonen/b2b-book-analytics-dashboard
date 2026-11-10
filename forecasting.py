"""Günlük talep / ciro tahmini.

Üç model geriye dönük test (backtest) ile karşılaştırılır, en iyi model tüm
veriyle yeniden eğitilip ileriye dönük tahmin üretilir:
  1. Mevsimsel Naif (7 gün önceki değer) — kıyas modeli
  2. Holt-Winters (sönümlü trend + haftalık mevsimsellik)
  3. Gradient Boosting (takvim + gecikme öznitelikleri, özyinelemeli tahmin)
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from statsmodels.tsa.holtwinters import ExponentialSmoothing

LAGS = (1, 7, 14)


def daily_series(df: pd.DataFrame, target: str = "Revenue") -> pd.Series:
    s = df.groupby("InvoiceDate")[target].sum()
    idx = pd.date_range(s.index.min(), s.index.max(), freq="D")
    return s.reindex(idx, fill_value=0).astype(float)


def _metrics(y: np.ndarray, p: np.ndarray) -> dict:
    err = y - p
    denom = np.abs(y).sum()
    return {"MAE": np.abs(err).mean(),
            "RMSE": np.sqrt((err ** 2).mean()),
            "WAPE %": np.abs(err).sum() / denom if denom else np.nan}


# --- Modeller --------------------------------------------------------------
def _seasonal_naive(train: pd.Series, h: int) -> np.ndarray:
    last = train.iloc[-7:].to_numpy()
    return np.resize(last, h)


def _holt_winters(train: pd.Series, h: int) -> np.ndarray:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        m = ExponentialSmoothing(train, trend="add", damped_trend=True,
                                 seasonal="add", seasonal_periods=7,
                                 initialization_method="estimated").fit()
    return np.clip(m.forecast(h).to_numpy(), 0, None)


def _features(dates: pd.DatetimeIndex, history: list[float], i: int) -> list[float]:
    d = dates[i]
    hist = history[:i]
    feat = [d.dayofweek, d.day, d.month, int(d.dayofweek >= 5)]
    feat += [hist[-lag] if len(hist) >= lag else np.nan for lag in LAGS]
    feat += [np.mean(hist[-7:]) if hist else np.nan,
             np.mean(hist[-28:]) if hist else np.nan]
    return feat


def _gbm(train: pd.Series, h: int) -> np.ndarray:
    dates = train.index.append(pd.date_range(train.index[-1] + pd.Timedelta(days=1),
                                             periods=h, freq="D"))
    hist = list(train.to_numpy())
    X = np.array([_features(dates, hist, i) for i in range(28, len(train))])
    y = train.to_numpy()[28:]
    model = GradientBoostingRegressor(n_estimators=300, max_depth=3, learning_rate=0.05,
                                      subsample=0.8, random_state=42)
    model.fit(np.nan_to_num(X), y)
    preds = []
    for i in range(len(train), len(train) + h):  # özyinelemeli (recursive) tahmin
        x = np.nan_to_num(np.array(_features(dates, hist, i))).reshape(1, -1)
        p = max(0.0, float(model.predict(x)[0]))
        preds.append(p)
        hist.append(p)
    return np.array(preds)


MODELS = {"Mevsimsel Naif": _seasonal_naive,
          "Holt-Winters": _holt_winters,
          "Gradient Boosting": _gbm}


def backtest(series: pd.Series, test_days: int = 28) -> tuple[pd.DataFrame, pd.DataFrame]:
    train, test = series.iloc[:-test_days], series.iloc[-test_days:]
    rows, preds = [], pd.DataFrame({"Gerçek": test})
    for name, fn in MODELS.items():
        p = fn(train, test_days)
        preds[name] = p
        rows.append({"Model": name, **_metrics(test.to_numpy(), p)})
    return pd.DataFrame(rows).sort_values("WAPE %"), preds


def forecast(series: pd.Series, model: str, horizon: int,
             resid_std: float) -> pd.DataFrame:
    p = MODELS[model](series, horizon)
    idx = pd.date_range(series.index[-1] + pd.Timedelta(days=1), periods=horizon, freq="D")
    band = 1.96 * resid_std * np.sqrt(np.arange(1, horizon + 1) / 7).clip(1, None)
    return pd.DataFrame({"Tahmin": p, "Alt": np.clip(p - band, 0, None),
                         "Üst": p + band}, index=idx)


def run(series: pd.Series, horizon: int, test_days: int = 28) -> dict:
    if len(series) < test_days + 60:
        return {"error": "Tahmin için en az ~3 aylık günlük veri gerekir."}
    scores, preds = backtest(series, test_days)
    best = scores.iloc[0]["Model"]
    resid_std = float((preds["Gerçek"] - preds[best]).std())
    fc = forecast(series, best, horizon, resid_std)
    return {"scores": scores, "backtest": preds, "best": best, "forecast": fc}
