"""Yönetici Özeti › Genel Bakış"""
from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src import charts, config as C, insights, kpis, state, ui
from src.formatting import compact, money, number, pct


def _delta(cur: float, prev: float | None) -> str | None:
    if prev is None or not prev:
        return None
    return pct(cur / prev - 1, signed=True)


def kpi_block(df, prev_df) -> None:
    k = kpis.kpi_summary(df)
    p = kpis.kpi_summary(prev_df) if prev_df is not None and len(prev_df) else None
    g = (lambda key: p[key]) if p else (lambda key: None)
    ui.kpi_row([
        {"label": "Net Ciro", "value": money(k["revenue"]), "delta": _delta(k["revenue"], g("revenue")),
         "help": "Σ Miktar × Net fiyat. Değişim: aynı uzunluktaki bir önceki döneme göre."},
        {"label": "Sipariş (fatura)", "value": number(k["orders"]),
         "delta": _delta(k["orders"], g("orders"))},
        {"label": "Aktif Müşteri", "value": number(k["customers"]),
         "delta": _delta(k["customers"], g("customers"))},
        {"label": "Ort. Sipariş Tutarı", "value": money(k["aov"], full=True),
         "delta": _delta(k["aov"], g("aov"))},
        {"label": "Satılan Adet", "value": compact(k["units"]),
         "delta": _delta(k["units"], g("units"))},
        {"label": "Ort. İskonto", "value": pct(k["discount_rate"]),
         "delta": None if p is None else pct(k["discount_rate"] - p["discount_rate"], signed=True)
         .replace("%", "") + " puan",
         "delta_color": "inverse", "help": "1 − Net ciro / Liste fiyatı cirosu"},
    ])


def monthly_chart(df) -> go.Figure:
    m = kpis.monthly_trend(df)
    fig = go.Figure(go.Bar(
        x=m["Ay"], y=m["Ciro"], marker_color=C.SERIES[0],
        customdata=np.stack([m["Sipariş"], m["Aylık Değişim %"].fillna(0) * 100], axis=1),
        hovertemplate="<b>%{x}</b><br>Ciro: ₺%{y:,.0f}<br>Sipariş: %{customdata[0]:,}"
                      "<br>Aylık değişim: %{customdata[1]:+.1f}%<extra></extra>"))
    avg = m["Ciro"].mean()
    fig.add_hline(y=avg, line=dict(color=C.INK["secondary"], dash="dot", width=1))
    return charts.bar_marks(charts.finish(
        fig, f"Aylık net ciro <span style='font-size:12px;color:{C.INK['muted']}'>"
             f"· noktalı çizgi = aylık ortalama {money(avg)}</span>", 360, money_axis=True))


def turkey_map(df, geo, metric: str = "Ciro", height: int = 420) -> go.Figure:
    city = kpis.by_dimension(df, "City")
    city = city[city["City"] != C.UNKNOWN]
    city["log"] = np.log10(city[metric].clip(lower=1))
    fig = px.choropleth_map(city, geojson=geo, locations="City", featureidkey="properties.name",
                            color="log", color_continuous_scale=C.SEQUENTIAL,
                            hover_name="City", map_style="white-bg",
                            center={"lat": 39.0, "lon": 35.3}, zoom=4.0, opacity=0.95,
                            hover_data={"log": False, "Ciro": ":,.0f", "Sipariş": ":,",
                                        "Müşteri": ":,", "City": False})
    ticks = np.arange(np.floor(city["log"].min()), np.ceil(city["log"].max()) + 1)
    fig.update_layout(coloraxis_colorbar=dict(
        title="", tickvals=ticks, ticktext=[compact(10 ** t) for t in ticks], thickness=10,
        len=0.6), margin=dict(l=0, r=0, t=48, b=0))
    fig.update_traces(marker_line_color="white", marker_line_width=0.8)
    return charts.finish(fig, f"İllere göre {metric.lower()} (log ölçek)", height)


def render() -> None:
    c = state.ctx()
    df = state.filtered(c["dedup"], c["filters"])
    ui.page_header("Genel Bakış", "Şirketin satış performansının tek ekranda özeti.",
                   c["filters"].describe())
    if not ui.guard(df):
        return

    full, _, geo, _ = state.load(c["dedup"])
    f = c["filters"]
    span = f.end - f.start
    p_end = f.start - pd.Timedelta(days=1)
    prev_df = None
    if p_end - span >= full["InvoiceDate"].min():
        prev_df = state.filtered(c["dedup"], replace(f, start=p_end - span, end=p_end))
    kpi_block(df, prev_df)
    if prev_df is None:
        st.caption("Karşılaştırma: veri seti 2020 ile sınırlı olduğundan seçili dönemin "
                   "öncesinde aynı uzunlukta bir dönem yok; değişim oranları gösterilmiyor.")

    st.write("")
    left, right = st.columns([3, 2])
    with left:
        ui.plot(monthly_chart(df))
    with right:
        cat = kpis.by_dimension(df, "CategoryGroup")
        cat = cat[cat["CategoryGroup"] != C.OTHER].head(10)
        cat["Etiket"] = cat["Pay %"].map(lambda v: pct(v))
        ui.plot(charts.hbar(cat, "Ciro", "CategoryGroup", "En çok ciro getiren 10 kategori",
                            text="Etiket", height=360))

    left, right = st.columns([3, 2])
    with left:
        ui.plot(turkey_map(df, geo))
    with right:
        city = kpis.by_dimension(df, "City", 10)
        city["Etiket"] = city["Pay %"].map(lambda v: pct(v))
        ui.plot(charts.hbar(city, "Ciro", "City", "İlk 10 il", text="Etiket", height=420,
                            color=C.SERIES[2]))

    ui.section("Öne çıkan içgörüler",
               "Filtrelere göre otomatik üretilir. Tüm öneriler için 'İçgörüler ve Öneriler' sayfasına bakın.")
    ui.insight_cards(insights.sales_insights(df)[:4])
