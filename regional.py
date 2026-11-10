"""Satış › Bölgesel Analiz"""
from __future__ import annotations

import plotly.express as px
import streamlit as st

from src import charts, config as C, kpis, state, ui
from src.formatting import money, number, pct
from src.views.overview import turkey_map

MAP_METRICS = {"Ciro": "Ciro", "Sipariş": "Sipariş", "Müşteri": "Müşteri", "Adet": "Adet"}


def render() -> None:
    c = state.ctx()
    df = state.filtered(c["dedup"], c["filters"])
    _, _, geo, _ = state.load(c["dedup"])
    ui.page_header("Bölgesel Analiz", "İl bazında pazar büyüklüğü, penetrasyon ve kategori tercihleri.",
                   c["filters"].describe())
    if not ui.guard(df):
        return

    city = kpis.by_dimension(df, "City")
    known = city[city["City"] != C.UNKNOWN]
    ist_rev = known.loc[known["City"] == "İstanbul", "Ciro"].sum()
    ist = ist_rev / city["Ciro"].sum()
    ui.kpi_row([
        {"label": "Satış yapılan il", "value": number(len(known)), "help": "81 il içinden"},
        {"label": "İstanbul payı", "value": pct(ist)},
        {"label": "İstanbul dışı ciro", "value": money(known["Ciro"].sum() - ist_rev)},
        {"label": "İl başına ort. müşteri", "value": number(known["Müşteri"].mean(), 1)},
    ])

    metric = st.segmented_control("Harita göstergesi", list(MAP_METRICS), default="Ciro",
                                  key="r_metric") or "Ciro"
    left, right = st.columns([3, 2])
    with left:
        ui.plot(turkey_map(df, geo, MAP_METRICS[metric], height=470))
    with right:
        known = known.assign(**{"Müşteri başı ciro": known["Ciro"] / known["Müşteri"]})
        fig = px.scatter(known, x="Müşteri", y="Ciro", size="Sipariş", hover_name="City",
                         log_x=True, log_y=True, color_discrete_sequence=[C.SERIES[0]],
                         size_max=40)
        fig.update_traces(marker=dict(line=dict(color="white", width=1.5), opacity=0.8))
        fig.update_yaxes(tickprefix=C.CURRENCY, tickformat="~s", dtick=1)
        fig.update_xaxes(dtick=1)
        ui.plot(charts.finish(fig, "Müşteri sayısı ve ciro (log-log, kabarcık = sipariş)", 470,
                              x_title="Müşteri sayısı", y_title="Ciro"))

    ui.section("İl tablosu", "Sütun başlıklarına tıklayarak sıralayın.")
    st.dataframe(known.rename(columns={"City": "İl"}), hide_index=True, height=320, column_config={
        "Ciro": st.column_config.NumberColumn(format="₺%,.0f"),
        "Müşteri başı ciro": st.column_config.NumberColumn(format="₺%,.0f"),
        "Pay %": st.column_config.NumberColumn(format="percent"),
        "İskonto %": st.column_config.NumberColumn(format="percent"),
        "Adet": st.column_config.NumberColumn(format="%,d")})
    ui.download(known, "il_bazinda_satis")

    ui.section("İl detayı")
    sel = st.selectbox("İl seçin", known["City"].tolist(), key="r_city")
    d = df[df["City"] == sel]
    a, b = st.columns(2)
    with a:
        m = kpis.monthly_trend(d)
        fig = px.bar(m, x="Ay", y="Ciro", color_discrete_sequence=[C.SERIES[0]])
        ui.plot(charts.bar_marks(charts.finish(fig, f"{sel} · aylık ciro", 340, money_axis=True,
                                               x_title="")))
    with b:
        cat = kpis.by_dimension(d, "Category", 10)
        nat = df.groupby("Category", observed=True)["Revenue"].sum() / df["Revenue"].sum()
        cat["Ulusal pay"] = cat["Category"].map(nat).astype(float)
        cat["Endeks"] = (cat["Pay %"] / cat["Ulusal pay"] * 100).round(0)
        cat["Etiket"] = cat["Endeks"].map(lambda v: f"endeks {v:.0f}")
        ui.plot(charts.hbar(cat, "Ciro", "Category", f"{sel} · ilk 10 kategori", text="Etiket",
                            height=340, color=C.SERIES[2]))
    st.caption("Endeks = ildeki kategori payı / genel kategori payı × 100. 100'ün üzeri, "
               "kategorinin bu ilde ortalamadan daha güçlü olduğunu gösterir (bölgesel kampanya fırsatı).")
