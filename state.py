"""Streamlit önbellek katmanı.

Analitik modüller (src/kpis.py, customers.py, ...) saf pandas fonksiyonlarıdır;
bu dosya onları Streamlit önbelleğine bağlar. Önbellek anahtarı, kenar çubuğu
filtrelerini temsil eden hashlenebilir `Filters` nesnesidir.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src import basket, customers, data, forecasting, supply
from src.data import Filters


@st.cache_resource(show_spinner="Veri yükleniyor ve ön işleniyor…")
def load(drop_duplicates: bool = True):
    raw = data.load_raw()
    geo = data.load_geojson()
    df, report = data.preprocess(raw, geo, drop_duplicates=drop_duplicates)
    raw_profile = {
        "rows": len(raw),
        "cols": raw.shape[1],
        "missing": raw.isna().sum(),
        "duplicates": int(raw.duplicated().sum()),
        "dtypes": raw.dtypes.astype(str),
        "sample": raw.head(8),
        "describe": raw[["Quantity", "NetPrice", "UnitPrice"]].describe().T,
    }
    return df, report, geo, raw_profile


@st.cache_resource(max_entries=6, show_spinner=False)
def filtered(dedup: bool, f: Filters) -> pd.DataFrame:
    df, *_ = load(dedup)
    return data.apply_filters(df, f)


def ctx() -> dict:
    """Aktif sayfanın ihtiyaç duyduğu bağlam (streamlit_app.py tarafından doldurulur)."""
    return st.session_state["ctx"]


# --- Önbellekli analitik çağrıları ------------------------------------------------
@st.cache_data(show_spinner="RFM hesaplanıyor…", max_entries=8)
def rfm(dedup: bool, f: Filters) -> pd.DataFrame:
    return customers.rfm_table(filtered(dedup, f))


@st.cache_data(show_spinner="Küme sayısı değerlendiriliyor…", max_entries=8)
def silhouette(dedup: bool, f: Filters) -> pd.DataFrame:
    return customers.silhouette_by_k(rfm(dedup, f))


@st.cache_data(show_spinner="K-Means çalıştırılıyor…", max_entries=16)
def kmeans(dedup: bool, f: Filters, k: int):
    return customers.kmeans_segments(rfm(dedup, f), k)


@st.cache_data(show_spinner="Churn modeli eğitiliyor…", max_entries=8)
def churn(dedup: bool, f: Filters, horizon: int) -> dict:
    return customers.churn_model(filtered(dedup, f), horizon)


@st.cache_data(show_spinner="ABC-XYZ sınıflandırması…", max_entries=16)
def abc_xyz(dedup: bool, f: Filters, x_cut: float = 0.5, y_cut: float = 1.0) -> pd.DataFrame:
    return supply.abc_xyz(filtered(dedup, f), x_cut=x_cut, y_cut=y_cut)


@st.cache_data(show_spinner="Stok politikası hesaplanıyor…", max_entries=16)
def inventory(dedup: bool, f: Filters, lead_time: int, service: float,
              order_cost: float, holding: float, classes: tuple) -> pd.DataFrame:
    df = filtered(dedup, f)
    return supply.inventory_policy(df, abc_xyz(dedup, f), lead_time, service,
                                   order_cost, holding, classes)


@st.cache_data(show_spinner="Tahmin modelleri karşılaştırılıyor…", max_entries=16)
def forecast(dedup: bool, f: Filters, target: str, horizon: int, test_days: int) -> dict:
    s = forecasting.daily_series(filtered(dedup, f), target)
    return forecasting.run(s, horizon, test_days)


@st.cache_data(show_spinner="Sık öğe kümeleri aranıyor (FP-Growth)…", max_entries=16)
def rules(dedup: bool, f: Filters, level: str, min_support: float,
          min_conf: float, min_lift: float) -> tuple[pd.DataFrame, int]:
    b = basket.basket_matrix(filtered(dedup, f), level)
    r = basket.mine_rules(b, min_support, min_conf, min_lift)
    return r, len(b)
