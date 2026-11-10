"""Veri › Veri Gezgini"""
from __future__ import annotations

import streamlit as st

from src import state, ui
from src.formatting import number

DEFAULT_COLS = ["InvoiceNo", "InvoiceDate", "CustomerID", "City", "Category", "Description",
                "Quantity", "UnitPrice", "NetPrice", "DiscountRate", "Revenue"]
GROUPS = {"Yok (satır düzeyi)": None, "Müşteri": "CustomerID", "Ürün": "Description",
          "Kategori": "Category", "Şehir": "City", "Fatura": "InvoiceNo"}


def render() -> None:
    c = state.ctx()
    df = state.filtered(c["dedup"], c["filters"])
    ui.page_header("Veri Gezgini", "Filtrelenmiş temiz veriyi inceleyin, gruplayın ve indirin.",
                   c["filters"].describe())
    if not ui.guard(df):
        return

    a, b = st.columns([1, 3])
    group = GROUPS[a.selectbox("Grupla", list(GROUPS), key="e_g")]
    q = b.text_input("Ürün / müşteri / fatura ara", key="e_q", placeholder="ör. Simyacı, A02212")
    d = df
    if q:
        mask = (df["Description"].astype(str).str.contains(q, case=False, na=False) |
                df["CustomerID"].astype(str).str.contains(q, case=False, na=False) |
                df["InvoiceNo"].astype(str).str.contains(q, case=False, na=False))
        d = df[mask]

    if group:
        out = (d.groupby(group, observed=True)
                 .agg(Ciro=("Revenue", "sum"), Adet=("Quantity", "sum"),
                      Sipariş=("InvoiceNo", "nunique"), Müşteri=("CustomerID", "nunique"),
                      İlk=("InvoiceDate", "min"), Son=("InvoiceDate", "max"))
                 .sort_values("Ciro", ascending=False).reset_index())
    else:
        cols = st.multiselect("Sütunlar", list(df.columns), DEFAULT_COLS, key="e_cols")
        out = d[cols or DEFAULT_COLS]

    st.caption(f"{number(len(out))} satır · tabloda en fazla 10.000 satır gösterilir.")
    st.dataframe(out.head(10_000), hide_index=True, height=560, column_config={
        "Revenue": st.column_config.NumberColumn("Ciro", format="₺%,.2f"),
        "Ciro": st.column_config.NumberColumn(format="₺%,.0f"),
        "DiscountRate": st.column_config.NumberColumn("İskonto", format="percent"),
        "InvoiceDate": st.column_config.DateColumn("Tarih", format="DD.MM.YYYY"),
        "İlk": st.column_config.DateColumn(format="DD.MM.YYYY"),
        "Son": st.column_config.DateColumn(format="DD.MM.YYYY")})
    ui.download(out, "veri_gezgini", "Tümünü CSV indir")
