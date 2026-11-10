"""Tedarik Zinciri › Envanter Analizi (ABC-XYZ, stok politikası, talep sinyalleri)"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from src import charts, config as C, state, supply, ui
from src.formatting import money, number, pct


def abc_tab(c) -> pd.DataFrame:
    a, b, _ = st.columns([1, 1, 2])
    x_cut = a.number_input("X sınırı (CV ≤)", 0.1, 2.0, 0.5, 0.1, key="i_x",
                           help="Haftalık talebin değişkenlik katsayısı")
    y_cut = b.number_input("Y sınırı (CV ≤)", x_cut, 5.0, max(1.0, x_cut), 0.1, key="i_y")
    prod = state.abc_xyz(c["dedup"], c["filters"], x_cut, y_cut)

    left, right = st.columns(2)
    with left:
        m = supply.abc_xyz_matrix(prod, "count")
        ui.plot(charts.heatmap(m, "Ürün sayısı (ABC × XYZ)", fmt="~s", height=330, text_fmt=",d"))
    with right:
        r = supply.abc_xyz_matrix(prod, "revenue")
        share = r / r.values.sum()
        ui.plot(charts.heatmap(share, "Ciro payı (ABC × XYZ)", fmt=".0%", height=330,
                               text_fmt=".1%"))
    st.caption("**A**: cironun ilk %80'i · **B**: sonraki %15 · **C**: son %5. "
               f"**X**: CV ≤ {x_cut} (istikrarlı) · **Y**: CV ≤ {y_cut} · **Z**: düzensiz talep.")

    summary = (prod.groupby("Sınıf").agg(Ürün=("StockCode", "count"), Ciro=("Ciro", "sum"),
                                         Adet=("Adet", "sum")).reset_index())
    summary["Ciro payı"] = summary["Ciro"] / summary["Ciro"].sum()
    summary["Önerilen politika"] = summary["Sınıf"].map(supply.ABC_XYZ_POLICY)
    st.dataframe(summary, hide_index=True, column_config={
        "Ciro": st.column_config.NumberColumn(format="₺%,.0f"),
        "Adet": st.column_config.NumberColumn(format="%,d"),
        "Ciro payı": st.column_config.ProgressColumn(format="percent", min_value=0, max_value=1),
        "Önerilen politika": st.column_config.TextColumn(width="large")})
    with st.expander("Ürün bazında sınıflandırma"):
        cls = st.multiselect("Sınıf", sorted(prod["Sınıf"].unique()), key="i_cls")
        view = prod[prod["Sınıf"].isin(cls)] if cls else prod
        cols = ["StockCode", "Ürün", "Kategori", "Sınıf", "Ciro", "Adet", "HaftalıkOrt", "CV"]
        st.dataframe(view[cols].head(3000), hide_index=True, column_config={
            "Ciro": st.column_config.NumberColumn(format="₺%,.0f"),
            "HaftalıkOrt": st.column_config.NumberColumn("Haftalık ort. adet", format="%.2f"),
            "CV": st.column_config.NumberColumn(format="%.2f")})
        ui.download(view[cols], "abc_xyz_siniflandirma")
    return prod


def policy_tab(c) -> None:
    st.markdown("Günlük talep dağılımına göre **emniyet stoğu (SS)**, **yeniden sipariş noktası (ROP)** "
                "ve **ekonomik sipariş miktarı (EOK)**. Parametreleri değiştirerek senaryo deneyin.")
    a, b, cc, d, e = st.columns(5)
    lt = a.number_input("Tedarik süresi (gün)", 1, 60, 7, key="i_lt")
    sl = b.select_slider("Hizmet düzeyi", [0.80, 0.85, 0.90, 0.95, 0.975, 0.99], 0.95, key="i_sl",
                         format_func=lambda v: f"%{v * 100:g}")
    oc = cc.number_input("Sipariş maliyeti (₺)", 0.0, 5000.0, 150.0, 10.0, key="i_oc")
    hr = d.number_input("Yıllık elde tutma oranı", 0.01, 1.0, 0.25, 0.01, key="i_hr",
                        help="Birim maliyetin yüzdesi olarak yıllık stok tutma maliyeti")
    classes = e.multiselect("ABC sınıfı", ["A", "B", "C"], ["A"], key="i_abc")
    if not classes:
        st.info("En az bir ABC sınıfı seçin.")
        return
    pol = state.inventory(c["dedup"], c["filters"], lt, sl, oc, hr, tuple(classes))
    ui.kpi_row([
        {"label": "Ürün", "value": number(len(pol))},
        {"label": "Toplam emniyet stoğu", "value": f"{number(pol['Emniyet Stoğu'].sum())} adet"},
        {"label": "Emniyet stoğu değeri", "value": money(pol["Emniyet Stoğu Değeri"].sum())},
        {"label": "Ort. yıllık sipariş sayısı", "value": number(pol["Yıllık Sipariş Sayısı"].median(), 1),
         "help": "Medyan (EOK'ya göre)"},
    ])
    q = st.text_input("Ürün ara", key="i_q", placeholder="Ürün adı veya stok kodu")
    view = pol
    if q:
        mask = (pol["Ürün"].astype(str).str.contains(q, case=False, na=False) |
                pol["StockCode"].astype(str).str.contains(q, na=False))
        view = pol[mask]
    st.dataframe(view.head(2000), hide_index=True, height=420, column_config={
        "Ciro": st.column_config.NumberColumn(format="₺%,.0f"),
        "Günlük Ort.": st.column_config.NumberColumn(format="%.2f"),
        "Günlük σ": st.column_config.NumberColumn(format="%.2f"),
        "Ort. Net Fiyat": st.column_config.NumberColumn(format="₺%.2f"),
        "Emniyet Stoğu Değeri": st.column_config.NumberColumn(format="₺%,.0f"),
        "Emniyet Stoğu": st.column_config.NumberColumn(format="%d"),
        "Yeniden Sipariş Noktası": st.column_config.NumberColumn("ROP", format="%d"),
        "EOK": st.column_config.NumberColumn(format="%d")})
    ui.download(pol, "stok_politikasi")
    st.caption("SS = z·σ·√LT · ROP = μ·LT + SS · EOK = √(2·D·S / H). Birim maliyet yerine ortalama "
               "net satış fiyatı kullanıldığı için EOK üst sınır niteliğindedir.")


def signals_tab(c, df, prod) -> None:
    left, right = st.columns(2)
    with left:
        mom = supply.category_momentum(df)
        mom = mom[mom["Kategori"] != C.OTHER]
        mom["Yön"] = mom["Değişim %"].map(lambda v: "Artış" if v >= 0 else "Azalış")
        mom["Etiket"] = mom["Değişim %"].map(lambda v: pct(v, 0, signed=True))
        fig = px.bar(mom, x="Değişim %", y="Kategori", orientation="h", color="Yön", text="Etiket",
                     color_discrete_map={"Artış": C.SERIES[0], "Azalış": C.SERIES[7]})
        fig.update_traces(textposition="outside", cliponaxis=False)
        fig.update_xaxes(tickformat=".0%", title="")
        fig.update_yaxes(title="")
        ui.plot(charts.bar_marks(charts.finish(fig, "Son 4 hafta vs önceki 4 hafta adet değişimi",
                                               560)))
    with right:
        w = supply.weekday_workload(df)
        w["Gün"] = w["Weekday"].map(lambda i: C.WEEKDAYS_TR[i])
        fig = px.bar(w, x="Gün", y="Günlük Ort. Satır", text=w["Pay %"].map(lambda v: pct(v, 0)),
                     color_discrete_sequence=[C.SERIES[2]])
        fig.update_traces(textposition="outside", cliponaxis=False)
        ui.plot(charts.bar_marks(charts.finish(fig, "Depo yükü: güne göre ort. sipariş satırı", 270,
                                               x_title="", y_title="Satır / gün")))
        heat = (df.groupby([df["InvoiceDate"].dt.month, "CategoryGroup"], observed=True)["Quantity"]
                  .sum().unstack(fill_value=0).T)
        heat = heat.loc[heat.sum(axis=1).sort_values(ascending=False).index[:12]]
        heat.columns = [C.MONTHS_TR[m - 1] for m in heat.columns]
        heat = heat.div(heat.max(axis=1), axis=0)
        ui.plot(charts.heatmap(heat, "Kategori talep mevsimselliği (satır max = 1)", fmt=".0%",
                               height=290))

    ui.section("Hareketsiz ürünler", "Geçmişte satılmış ancak uzun süredir satışı olmayan ürünler — iade/indirim adayları.")
    a, b, _ = st.columns([1, 1, 2])
    idle = a.slider("Hareketsiz gün ≥", 30, 180, 60, 10, key="i_idle")
    mu = b.number_input("Toplam satış ≥ (adet)", 1, 1000, 20, key="i_mu")
    end = df["InvoiceDate"].max()
    slow = supply.slow_movers(prod, end, idle, mu)
    st.caption(f"{number(len(slow))} ürün · geçmiş cirosu {money(slow['Ciro'].sum())}")
    st.dataframe(slow.head(1000), hide_index=True, height=300, column_config={
        "Ciro": st.column_config.NumberColumn(format="₺%,.0f"),
        "SonSatış": st.column_config.DateColumn("Son satış", format="DD.MM.YYYY")})
    ui.download(slow, "hareketsiz_urunler")


def render() -> None:
    c = state.ctx()
    df = state.filtered(c["dedup"], c["filters"])
    ui.page_header("Envanter Analizi",
                   "Ürün portföyü sınıflandırması, stok politikası ve talep sinyalleri.",
                   c["filters"].describe())
    if not ui.guard(df, 500):
        return
    t1, t2, t3 = st.tabs([":material/view_module: ABC-XYZ", ":material/inventory: Stok Politikası",
                          ":material/sensors: Talep Sinyalleri"])
    with t1:
        prod = abc_tab(c)
    with t2:
        policy_tab(c)
    with t3:
        signals_tab(c, df, prod)
