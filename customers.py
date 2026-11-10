"""Pazarlama › Müşteri Segmentasyonu (RFM + K-Means + müşteri kartı)"""
from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src import charts, config as C, kpis, state, ui
from src.customers import segment_summary
from src.formatting import money, number, pct

SEGMENT_ORDER = ["Şampiyon", "Sadık", "Potansiyel Sadık", "Yeni", "Umut Vaat Eden",
                 "İlgi Bekleyen", "Uyumak Üzere", "Risk Altında", "Kaybedilmemeli", "Uykuda"]


def rfm_tab(rfm, seg) -> None:
    ui.kpi_row([
        {"label": "Müşteri", "value": number(len(rfm))},
        {"label": "Ort. Recency", "value": f"{rfm['Recency'].mean():.0f} gün",
         "help": "Son alımdan bu yana geçen gün"},
        {"label": "Ort. Frekans", "value": f"{number(rfm['Frequency'].mean(), 1)} sipariş"},
        {"label": "Ort. Monetary", "value": money(rfm["Monetary"].mean())},
    ])
    left, right = st.columns([3, 2])
    with left:
        fig = px.treemap(seg, path=["Segment"], values="Müşteri", color="Ciro",
                         color_continuous_scale=C.SEQUENTIAL,
                         custom_data=["Ciro", "Ciro Payı %", "Müşteri Payı %"])
        fig.update_traces(
            texttemplate="<b>%{label}</b><br>%{value} müşteri<br>ciro %{customdata[1]:.0%}",
            hovertemplate="<b>%{label}</b><br>Müşteri: %{value} (%{customdata[2]:.1%})"
                          "<br>Ciro: ₺%{customdata[0]:,.0f}<extra></extra>",
            marker_line_width=2, marker_line_color="white")
        fig.update_traces(root_color="rgba(0,0,0,0)")
        fig.update_layout(coloraxis_showscale=False)
        ui.plot(charts.finish(fig, "RFM segmentleri (alan = müşteri sayısı, renk = ciro)", 430))
    with right:
        m = rfm.pivot_table(index="F", columns="R", values="CustomerID", aggfunc="count",
                            fill_value=0).sort_index(ascending=False)
        m.index = [f"F{i}" for i in m.index]
        m.columns = [f"R{i}" for i in m.columns]
        ui.plot(charts.heatmap(m, "R × F skor matrisi (müşteri sayısı)", fmt="d", height=430,
                               text_fmt="d"))
    ui.section("Segment profilleri ve önerilen aksiyonlar")
    st.dataframe(seg, hide_index=True, column_config={
        "Ciro": st.column_config.NumberColumn(format="₺%,.0f"),
        "OrtCiro": st.column_config.NumberColumn("Ort. ciro", format="₺%,.0f"),
        "OrtRecency": st.column_config.NumberColumn("Ort. recency (gün)", format="%.0f"),
        "OrtFrekans": st.column_config.NumberColumn("Ort. frekans", format="%.1f"),
        "Ciro Payı %": st.column_config.ProgressColumn(format="percent", min_value=0, max_value=1),
        "Müşteri Payı %": st.column_config.NumberColumn(format="percent"),
        "Önerilen aksiyon": st.column_config.TextColumn(width="large")})

    sel = st.multiselect("Segment listesi", SEGMENT_ORDER, default=["Risk Altında", "Kaybedilmemeli"],
                         key="c_seg", help="Kampanya listesi oluşturmak için segment seçin.")
    lst = rfm[rfm["Segment"].isin(sel)].sort_values("Monetary", ascending=False)
    cols = ["CustomerID", "Segment", "RFM", "Recency", "Frequency", "Monetary", "Şehir", "Son"]
    st.dataframe(lst[cols], hide_index=True, height=280, column_config={
        "Monetary": st.column_config.NumberColumn("Ciro", format="₺%,.0f"),
        "Son": st.column_config.DateColumn("Son alım", format="DD.MM.YYYY")})
    ui.download(lst[cols], "rfm_kampanya_listesi", "Kampanya listesini indir")


def kmeans_tab(c, rfm) -> None:
    sil = state.silhouette(c["dedup"], c["filters"])
    left, right = st.columns([1, 2])
    with left:
        fig = go.Figure(go.Scatter(x=sil["k"], y=sil["Siluet"], mode="lines+markers",
                                   line=dict(color=C.SERIES[0], width=2), marker=dict(size=8)))
        fig.update_xaxes(dtick=1, title="Küme sayısı (k)")
        ui.plot(charts.finish(fig, "Siluet skoru", 260, y_title="Siluet"))
        best = int(sil.loc[sil["Siluet"].idxmax(), "k"])
        k = st.slider("Küme sayısı", 2, 8, 4, key="c_k",
                      help=f"En yüksek siluet k={best}. İş açısından yorumlanabilirlik için "
                           "4 küme varsayılan alınmıştır.")
        st.caption(f"Öznitelikler: log(1+R), log(1+F), log(1+M), standartlaştırılmış. "
                   f"En yüksek siluet k = **{best}**.")
    out, prof = state.kmeans(c["dedup"], c["filters"], k)
    with right:
        tab_a, tab_b = st.tabs(["3B RFM uzayı", "PCA izdüşümü"])
        colors = {name: C.SERIES[i] for i, name in enumerate(sorted(out["Küme"].unique()))}
        with tab_a:
            fig = px.scatter_3d(out, x="Recency", y="Frequency", z="Monetary", color="Küme",
                                log_y=True, log_z=True, hover_name="CustomerID",
                                color_discrete_map=colors, opacity=0.75)
            fig.update_traces(marker=dict(size=3.5))
            ui.plot(charts.finish(fig, None, 460))
        with tab_b:
            fig = px.scatter(out, x="PC1", y="PC2", color="Küme", hover_name="CustomerID",
                             hover_data={"Recency": True, "Frequency": True,
                                         "Monetary": ":,.0f", "PC1": False, "PC2": False},
                             color_discrete_map=colors, opacity=0.8)
            fig.update_traces(marker=dict(size=8, line=dict(color="white", width=1)))
            ui.plot(charts.finish(fig, None, 460))
    st.dataframe(prof, hide_index=True, column_config={
        "OrtRecency": st.column_config.NumberColumn("Ort. recency (gün)", format="%.0f"),
        "OrtFrekans": st.column_config.NumberColumn("Ort. frekans", format="%.1f"),
        "OrtCiro": st.column_config.NumberColumn("Ort. ciro", format="₺%,.0f"),
        "ToplamCiro": st.column_config.NumberColumn("Toplam ciro", format="₺%,.0f"),
        "Ciro Payı %": st.column_config.ProgressColumn(format="percent", min_value=0, max_value=1)})
    cross = (out.groupby(["Küme", "Segment"]).size().unstack(fill_value=0))
    with st.expander("K-Means kümeleri ile RFM segmentlerinin çapraz tablosu"):
        st.dataframe(cross)


def card_tab(c, df, rfm) -> None:
    ids = rfm.sort_values("Monetary", ascending=False)["CustomerID"].tolist()
    cid = st.selectbox("Müşteri (ciroya göre sıralı)", ids, key="c_card")
    r = rfm[rfm["CustomerID"] == cid].iloc[0]
    d = df[df["CustomerID"] == cid]
    rank = ids.index(cid) + 1
    ui.kpi_row([
        {"label": "Segment", "value": r["Segment"], "help": f"RFM skoru {r['RFM']}"},
        {"label": "Toplam ciro", "value": money(r["Monetary"]), "help": f"Ciro sıralaması: {rank}"},
        {"label": "Sipariş", "value": number(r["Frequency"])},
        {"label": "Son alım", "value": f"{r['Recency']} gün önce"},
        {"label": "Şehir", "value": str(r["Şehir"])},
    ])
    a, b = st.columns(2)
    with a:
        m = kpis.monthly_trend(d)
        fig = px.bar(m, x="Ay", y="Ciro", color_discrete_sequence=[C.SERIES[0]])
        ui.plot(charts.bar_marks(charts.finish(fig, "Aylık alımlar", 320, money_axis=True,
                                               x_title="")))
    with b:
        cat = kpis.by_dimension(d, "Category", 8)
        cat["Etiket"] = cat["Pay %"].map(pct)
        ui.plot(charts.hbar(cat, "Ciro", "Category", "Tercih ettiği kategoriler", text="Etiket",
                            height=320, color=C.SERIES[2]))
    top = kpis.top_products(d, 15)
    st.dataframe(top, hide_index=True, column_config={
        "Ciro": st.column_config.NumberColumn(format="₺%,.0f")})


def render() -> None:
    c = state.ctx()
    df = state.filtered(c["dedup"], c["filters"])
    ui.page_header("Müşteri Segmentasyonu",
                   "RFM skorlaması ve K-Means kümeleme ile müşteri değer grupları.",
                   c["filters"].describe())
    if not ui.guard(df, 100):
        return
    rfm = state.rfm(c["dedup"], c["filters"])
    if len(rfm) < 20:
        st.warning("Segmentasyon için en az 20 müşteri gerekir; filtreleri genişletin.")
        return
    seg = segment_summary(rfm)
    t1, t2, t3 = st.tabs([":material/grid_view: RFM Analizi", ":material/hub: K-Means Kümeleme",
                          ":material/badge: Müşteri Kartı"])
    with t1:
        rfm_tab(rfm, seg)
    with t2:
        kmeans_tab(c, rfm)
    with t3:
        card_tab(c, df, rfm)
