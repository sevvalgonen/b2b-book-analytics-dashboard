"""B2B Kitap Dağıtımı — Akıllı Karar Destek Paneli.

ISL 533 Veri Madenciliği · Ödev I
Çalıştırma:  streamlit run streamlit_app.py
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src import state, ui
from src.data import Filters
from src.views import (basket, churn, customers, data_quality, explorer, forecast,
                       insights, inventory, overview, regional, sales)

st.set_page_config(page_title="B2B Kitap Dağıtımı · Karar Destek Paneli",
                   page_icon=":material/menu_book:", layout="wide",
                   initial_sidebar_state="expanded")
ui.inject_css()

PERIODS = {
    "Tüm yıl (2020)": ("2020-01-01", "2020-12-31"),
    "1. Çeyrek": ("2020-01-01", "2020-03-31"),
    "2. Çeyrek": ("2020-04-01", "2020-06-30"),
    "3. Çeyrek": ("2020-07-01", "2020-09-30"),
    "4. Çeyrek": ("2020-10-01", "2020-12-31"),
    "2. Yarıyıl": ("2020-07-01", "2020-12-31"),
}
FILTER_KEYS = ["f_period", "f_range", "f_doc", "f_cust", "f_city", "f_cat"]


def reset_filters() -> None:
    for k in FILTER_KEYS:
        st.session_state.pop(k, None)


def sidebar() -> tuple[bool, Filters]:
    with st.sidebar:
        st.markdown("### :material/menu_book: B2B Kitap Dağıtımı")
        st.caption("Satış · Pazarlama · Tedarik Zinciri karar destek sistemi")

        dedup = st.toggle("Mükerrer satırları temizle", value=True,
                          help="Tüm sütunları aynı olan satırları veri setinden çıkarır. "
                               "Etkisi 'Veri Kalitesi' sayfasında raporlanır.")
        df, *_ = state.load(dedup)
        dmin, dmax = df["InvoiceDate"].min().date(), df["InvoiceDate"].max().date()

        st.markdown("**Filtreler**")
        period = st.selectbox("Dönem", [*PERIODS, "Özel aralık"], key="f_period")
        if period == "Özel aralık":
            rng = st.date_input("Tarih aralığı", value=(dmin, dmax), min_value=dmin,
                                max_value=dmax, format="DD.MM.YYYY", key="f_range")
            start, end = (rng if isinstance(rng, tuple) and len(rng) == 2 else (dmin, dmax))
        else:
            start, end = PERIODS[period]

        doc = st.multiselect("Belge serisi", sorted(df["DocType"].cat.categories),
                             key="f_doc", placeholder="Tümü",
                             help="Fatura numarasının ilk 3 harfi (satış kanalı/belge serisi).")
        cust = st.multiselect("Müşteri grubu", sorted(df["CustType"].cat.categories),
                              key="f_cust", placeholder="Tümü",
                              help="Müşteri kodunun ilk harfine göre gruplama.")
        cities = (df.groupby("City", observed=True)["Revenue"].sum()
                    .sort_values(ascending=False).index.tolist())
        city = st.multiselect("Şehir", cities, key="f_city", placeholder="Tümü")
        cats = (df.groupby("Category", observed=True)["Revenue"].sum()
                  .sort_values(ascending=False).index.tolist())
        cat = st.multiselect("Kategori", cats, key="f_cat", placeholder="Tümü",
                             help="Ciroya göre sıralı.")
        st.button("Filtreleri sıfırla", on_click=reset_filters, icon=":material/restart_alt:",
                  width="stretch")

        f = Filters(pd.Timestamp(start), pd.Timestamp(end), tuple(doc), tuple(cust),
                    tuple(city), tuple(cat))
        n = len(state.filtered(dedup, f))
        st.caption(f"Filtrelenmiş kayıt: **{n:,}** / {len(df):,}".replace(",", "."))
        st.divider()
        st.caption("ISL 533 Veri Madenciliği · Ödev I  \nVeri: B2B kitap dağıtımcısı, 2020")
    return dedup, f


dedup, filters = sidebar()
st.session_state["ctx"] = {"dedup": dedup, "filters": filters}

pages = {
    "Yönetici Özeti": [
        st.Page(overview.render, title="Genel Bakış", icon=":material/dashboard:",
                url_path="genel-bakis", default=True),
        st.Page(insights.render, title="İçgörüler ve Öneriler", icon=":material/lightbulb:",
                url_path="icgoruler"),
    ],
    "Satış": [
        st.Page(sales.render, title="Satış Performansı", icon=":material/trending_up:",
                url_path="satis"),
        st.Page(regional.render, title="Bölgesel Analiz", icon=":material/map:",
                url_path="bolgesel"),
    ],
    "Pazarlama": [
        st.Page(customers.render, title="Müşteri Segmentasyonu", icon=":material/groups:",
                url_path="segmentasyon"),
        st.Page(churn.render, title="Müşteri Kaybı Tahmini", icon=":material/person_remove:",
                url_path="churn"),
        st.Page(basket.render, title="Sepet Analizi", icon=":material/shopping_basket:",
                url_path="sepet"),
    ],
    "Tedarik Zinciri": [
        st.Page(inventory.render, title="Envanter Analizi", icon=":material/inventory_2:",
                url_path="envanter"),
        st.Page(forecast.render, title="Talep Tahmini", icon=":material/query_stats:",
                url_path="tahmin"),
    ],
    "Veri": [
        st.Page(data_quality.render, title="Veri Kalitesi ve Ön İşleme",
                icon=":material/cleaning_services:", url_path="veri-kalitesi"),
        st.Page(explorer.render, title="Veri Gezgini", icon=":material/table_view:",
                url_path="veri-gezgini"),
    ],
}
st.navigation(pages, position="top").run()
