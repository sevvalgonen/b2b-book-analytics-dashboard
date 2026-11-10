"""Veri › Veri Kalitesi ve Ön İşleme"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src import charts, config as C, state, ui
from src.formatting import number, pct

DICTIONARY = pd.DataFrame([
    ("InvoiceNo", "Fatura numarası; ilk 3 harf belge serisi", "DocType"),
    ("CustomerID", "Müşteri kodu; ilk harf müşteri grubu", "CustType"),
    ("InvoiceDate", "Fatura tarihi (2020)", "Month, Week, Weekday"),
    ("StockCode", "13 haneli ürün barkodu / ISBN", "—"),
    ("Description", "Ürün adı", "—"),
    ("Category", "Ürün kategorisi (306 adet)", "CategoryGroup (ilk 20 + Diğer)"),
    ("City", "Müşterinin bulunduğu il", "Resmi il adına standartlaştırıldı"),
    ("Quantity", "Satış adedi", "BulkOrder (aykırı işaret)"),
    ("NetPrice", "İskontolu birim satış fiyatı (₺)", "Revenue = Quantity × NetPrice"),
    ("UnitPrice", "Liste birim fiyatı (₺)", "DiscountRate = 1 − NetPrice/UnitPrice"),
], columns=["Sütun", "Açıklama", "Türetilen alan"])


def render() -> None:
    c = state.ctx()
    df, report, _, raw = state.load(c["dedup"])
    ui.page_header("Veri Kalitesi ve Ön İşleme",
                   "Ham verinin profili, uygulanan temizleme adımları ve türetilen öznitelikler.")

    ui.kpi_row([
        {"label": "Ham satır", "value": number(raw["rows"])},
        {"label": "Sütun", "value": number(raw["cols"])},
        {"label": "Eksik hücre", "value": number(raw["missing"].sum())},
        {"label": "Tam kopya satır", "value": number(raw["duplicates"])},
        {"label": "Analize giren satır", "value": number(len(df)),
         "delta": pct(len(df) / raw["rows"] - 1, signed=True), "delta_color": "off"},
    ])

    left, right = st.columns([2, 3])
    with left:
        miss = raw["missing"][raw["missing"] > 0].sort_values()
        fig = px.bar(x=miss.values, y=miss.index, orientation="h", text=[number(v) for v in miss.values],
                     color_discrete_sequence=[C.SERIES[1]])
        fig.update_traces(textposition="outside", cliponaxis=False)
        fig.update_xaxes(range=[0, float(miss.max()) * 1.2])
        ui.plot(charts.bar_marks(charts.finish(fig, "Ham veride eksik değerler", 260,
                                               x_title="", y_title="")))
        st.dataframe(pd.DataFrame({"Tip": raw["dtypes"]}), height=250)
    with right:
        steps = report.as_frame()
        fig = go.Figure(go.Funnel(y=["Ham veri"] + steps["Adım"].tolist(),
                                  x=[raw["rows"]] + steps["Sonra"].tolist(),
                                  textinfo="value", marker=dict(color=C.SERIES[0]),
                                  connector=dict(line=dict(color=C.INK["grid"]))))
        ui.plot(charts.finish(fig, "Temizleme hunisi (satır sayısı)", 300))
        st.dataframe(steps, hide_index=True, column_config={
            "Önce": st.column_config.NumberColumn(format="%,d"),
            "Sonra": st.column_config.NumberColumn(format="%,d"),
            "Etkilenen": st.column_config.NumberColumn(format="%,d"),
            "Uygulanan işlem": st.column_config.TextColumn(width="large")})

    ui.section("Düzeltme ve işaretleme adımları", "Satır silmeden uygulanan dönüşümler.")
    flags = pd.DataFrame(list(report.flags.items()), columns=["İşlem", "Etkilenen satır"])
    flags = pd.concat([flags, pd.DataFrame([
        ("İl adları resmi yazıma çevrildi (ör. IÇEL → Mersin, K.MARAS → Kahramanmaraş)", df["City"].nunique()),
        ("Türetilen öznitelik: ciro, brüt ciro, iskonto tutarı/oranı, ay, hafta, gün", len(df)),
        ("Bellek optimizasyonu: metin sütunları 'category' tipine çevrildi",
         int(df.memory_usage(deep=True).sum() / 1e6)),
    ], columns=flags.columns)])
    st.dataframe(flags, hide_index=True, column_config={
        "İşlem": st.column_config.TextColumn(width="large"),
        "Etkilenen satır": st.column_config.NumberColumn(format="%,d")})
    st.caption("Son satırdaki değer: temizlenmiş verinin bellekteki boyutu (MB).")

    a, b = st.columns(2)
    with a:
        q = df["Quantity"].clip(upper=df["Quantity"].quantile(0.999))
        fig = px.histogram(x=q, nbins=50, log_y=True, color_discrete_sequence=[C.SERIES[0]])
        ui.plot(charts.bar_marks(charts.finish(
            fig, "Miktar dağılımı (log ölçek, %99,9'da kırpılmış)", 300, x_title="Adet",
            y_title="Satır")))
        st.caption(f"Toplu sipariş olarak işaretlenen satır: **{number(df['BulkOrder'].sum())}**. "
                   "B2B toplu alımlar gerçek talep olduğundan silinmedi, yalnızca işaretlendi.")
    with b:
        s = df.sample(min(len(df), 50_000), random_state=1)
        fig = px.box(s, x="DocType", y="NetPrice", log_y=True, color_discrete_sequence=[C.SERIES[2]])
        ui.plot(charts.finish(fig, "Belge serisine göre net fiyat (log, örneklem)", 300,
                              x_title="", y_title="Net fiyat (₺)"))

    with st.expander("Ham veri örneği ve tanımlayıcı istatistikler"):
        st.dataframe(raw["sample"], hide_index=True)
        st.dataframe(raw["describe"])
    ui.section("Veri sözlüğü")
    st.dataframe(DICTIONARY, hide_index=True)
