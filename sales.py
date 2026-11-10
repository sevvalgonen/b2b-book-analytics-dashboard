"""Satış › Satış Performansı"""
from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src import charts, config as C, kpis, state, ui
from src.formatting import money, pct

METRICS = {"Ciro": "Ciro", "Satılan adet": "Adet", "Sipariş sayısı": "Sipariş"}
FREQ = {"Günlük": "D", "Haftalık": "W", "Aylık": "M"}


def trend_tab(df) -> None:
    c1, c2, _ = st.columns([1, 1, 2])
    freq = c1.segmented_control("Zaman birimi", list(FREQ), default="Haftalık", key="s_freq")
    metric = c2.selectbox("Gösterge", list(METRICS), key="s_metric")
    ts = kpis.time_series(df, FREQ[freq or "Haftalık"])
    col = METRICS[metric]
    fig = charts.line_trend(ts, "Tarih", col, f"{freq or 'Haftalık'} {metric.lower()}",
                            money_axis=col == "Ciro")
    if (freq or "Haftalık") != "Aylık" and len(ts) > 8:
        win = 7 if freq == "Günlük" else 4
        ts["MA"] = ts[col].rolling(win, min_periods=1).mean()
        fig.add_scatter(x=ts["Tarih"], y=ts["MA"], name=f"{win} dönemlik hareketli ort.",
                        line=dict(color=C.SERIES[1], width=2, dash="dot"))
        fig.update_layout(showlegend=True)
    ui.plot(fig)

    left, right = st.columns(2)
    with left:
        m = kpis.weekday_month_matrix(df)
        ui.plot(charts.heatmap(m, "Ay × haftanın günü ciro yoğunluğu", height=400))
    with right:
        d = (df.groupby([df["InvoiceDate"].dt.month, "DocType"], observed=True)["Revenue"]
               .sum().reset_index())
        d.columns = ["Ay", "Belge serisi", "Ciro"]
        d["Ay"] = d["Ay"].map(lambda m: C.MONTHS_TR[m - 1])
        fig = px.bar(d, x="Ay", y="Ciro", color="Belge serisi",
                     color_discrete_sequence=C.SERIES,
                     category_orders={"Ay": C.MONTHS_TR})
        ui.plot(charts.bar_marks(charts.finish(fig, "Belge serisine göre aylık ciro", 400,
                                               money_axis=True, x_title="")))
    m = kpis.monthly_trend(df)
    show = m[["Ay", "Ciro", "Sipariş", "Müşteri", "Adet", "Sepet Ort.", "İskonto %",
              "Aylık Değişim %"]]
    st.dataframe(show, hide_index=True, column_config={
        "Ciro": st.column_config.NumberColumn(format="₺%,.0f"),
        "Sepet Ort.": st.column_config.NumberColumn(format="₺%,.0f"),
        "İskonto %": st.column_config.NumberColumn(format="percent"),
        "Aylık Değişim %": st.column_config.NumberColumn(format="percent"),
        "Adet": st.column_config.NumberColumn(format="%,d")})


def product_tab(df) -> None:
    left, right = st.columns([3, 2])
    with left:
        t = (df.groupby(["CategoryGroup", "Category"], observed=True)["Revenue"].sum()
               .reset_index())
        fig = px.treemap(t, path=[px.Constant("Tüm kategoriler"), "CategoryGroup", "Category"],
                         values="Revenue", color="Revenue",
                         color_continuous_scale=C.SEQUENTIAL)
        fig.update_traces(hovertemplate="<b>%{label}</b><br>Ciro: ₺%{value:,.0f}"
                                        "<br>Üst kırılım payı: %{percentParent:.1%}<extra></extra>",
                          marker_line_width=1, marker_line_color="white")
        fig.update_traces(root_color="rgba(0,0,0,0)")
        fig.update_layout(coloraxis_showscale=False)
        ui.plot(charts.finish(fig, "Kategori hiyerarşisinde ciro dağılımı (tıklayarak detaylandırın)",
                              470))
    with right:
        p = kpis.pareto(df, "StockCode")
        idx80 = int((p["Kümülatif %"] <= 0.8).sum())
        share80 = idx80 / len(p) if len(p) else 0
        fig = go.Figure(go.Scatter(x=p["Varlık %"], y=p["Kümülatif %"], mode="lines",
                                   line=dict(color=C.SERIES[0], width=2),
                                   hovertemplate="Ürünlerin %{x:.1%}'i → cironun %{y:.1%}'i<extra></extra>"))
        fig.add_hline(y=0.8, line=dict(dash="dot", color=C.INK["muted"], width=1))
        fig.add_vline(x=share80, line=dict(dash="dot", color=C.INK["muted"], width=1))
        fig.add_annotation(x=share80, y=0.8, text=f"Ürünlerin {pct(share80)}'i → cironun %80'i",
                           showarrow=False, xanchor="left", yanchor="top", xshift=6,
                           font=dict(size=11, color=C.INK["secondary"]))
        fig.update_xaxes(tickformat=".0%", title="Ürünler (ciroya göre sıralı)")
        fig.update_yaxes(tickformat=".0%", title="Kümülatif ciro")
        ui.plot(charts.finish(fig, "Ürün Pareto eğrisi", 470))

    ui.section("En çok satan ürünler")
    n = st.slider("Gösterilecek ürün", 10, 100, 25, 5, key="s_topn")
    top = kpis.top_products(df, n)
    st.dataframe(top, hide_index=True, column_config={
        "StockCode": "Stok kodu",
        "Ciro": st.column_config.ProgressColumn(format="₺%,.0f", min_value=0,
                                                max_value=float(top["Ciro"].max())),
        "Adet": st.column_config.NumberColumn(format="%,d")})
    ui.download(top, "en_cok_satan_urunler")


def customer_tab(df) -> None:
    left, right = st.columns(2)
    with left:
        c = (df.groupby("CustomerID", observed=True)
               .agg(Ciro=("Revenue", "sum"), Şehir=("City", "first"),
                    Sipariş=("InvoiceNo", "nunique"))
               .nlargest(15, "Ciro").reset_index())
        c["Etiket"] = c["Ciro"].map(money)
        ui.plot(charts.hbar(c, "Ciro", "CustomerID", "Ciroya göre ilk 15 müşteri", text="Etiket",
                            height=480))
    with right:
        g = kpis.by_dimension(df, "CustType")
        fig = px.bar(g, x="CustType", y="Ciro", text=g["Pay %"].map(pct),
                     color_discrete_sequence=[C.SERIES[2]])
        fig.update_traces(textposition="outside", cliponaxis=False)
        ui.plot(charts.bar_marks(charts.finish(fig, "Müşteri grubuna göre ciro", 240,
                                               money_axis=True, x_title="")))
        st.dataframe(g.rename(columns={"CustType": "Grup"}), hide_index=True, column_config={
            "Ciro": st.column_config.NumberColumn(format="₺%,.0f"),
            "Pay %": st.column_config.NumberColumn(format="percent"),
            "İskonto %": st.column_config.NumberColumn(format="percent")})
        share = kpis.share_of_top(df, "CustomerID", 0.2)
        st.info(f"Müşterilerin en büyük %20'si cironun **{pct(share)}**'ini oluşturuyor.",
                icon=":material/pie_chart:")


def pricing_tab(df) -> None:
    left, right = st.columns(2)
    with left:
        sample = df.sample(min(len(df), 60_000), random_state=1)
        fig = px.histogram(sample, x="DiscountRate", nbins=60,
                           color_discrete_sequence=[C.SERIES[0]])
        fig.update_xaxes(tickformat=".0%", title="İskonto oranı", range=[0, 0.7])
        fig.update_yaxes(title="Satır sayısı (örneklem)")
        ui.plot(charts.bar_marks(charts.finish(fig, "İskonto oranı dağılımı", 380)))
    with right:
        cat = kpis.by_dimension(df, "CategoryGroup")
        cat = cat[cat["CategoryGroup"] != C.OTHER]
        cat["Etiket"] = cat["İskonto %"].map(pct)
        fig = charts.hbar(cat, "İskonto %", "CategoryGroup", "Kategorilere göre ortalama iskonto",
                          money_axis=False, text="Etiket", height=520, color=C.SERIES[1])
        fig.update_xaxes(tickformat=".0%")
        ui.plot(fig)
    b = kpis.discount_bands(df)
    fig = px.bar(b, x="İskonto bandı", y="OrtAdet", text=b["OrtAdet"].round(2),
                 color_discrete_sequence=[C.SERIES[2]])
    fig.update_traces(textposition="outside", cliponaxis=False)
    ui.plot(charts.bar_marks(charts.finish(
        fig, "İskonto bandına göre satır başına ortalama adet (fiyat esnekliği göstergesi)", 340,
        y_title="Ort. adet")))
    st.caption("Yüksek iskonto bantlarında satır başı adetin artması, iskontonun hacim "
               "anlaşmalarıyla verildiğine işaret eder. Kâr marjı verisi olmadığından "
               "iskontonun kârlılığa etkisi bu veriyle ölçülemez.")


def render() -> None:
    c = state.ctx()
    df = state.filtered(c["dedup"], c["filters"])
    ui.page_header("Satış Performansı", "Zaman, ürün, müşteri ve fiyat kırılımlarında satış analizi.",
                   c["filters"].describe())
    if not ui.guard(df):
        return
    t1, t2, t3, t4 = st.tabs([":material/show_chart: Trend", ":material/category: Kategori ve Ürün",
                              ":material/person: Müşteri", ":material/sell: Fiyat ve İskonto"])
    with t1:
        trend_tab(df)
    with t2:
        product_tab(df)
    with t3:
        customer_tab(df)
    with t4:
        pricing_tab(df)
