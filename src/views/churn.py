"""Pazarlama › Müşteri Kaybı (Churn) Tahmini"""
from __future__ import annotations

import plotly.express as px
import streamlit as st

from src import charts, config as C, state, ui
from src.customers import risk_band
from src.formatting import money, number, pct


def render() -> None:
    c = state.ctx()
    df = state.filtered(c["dedup"], c["filters"])
    ui.page_header("Müşteri Kaybı Tahmini",
                   "Makine öğrenmesi ile önümüzdeki dönemde alım yapmayacak müşterilerin tespiti.",
                   c["filters"].describe())
    if not ui.guard(df, 1000):
        return

    with st.expander("Yöntem", icon=":material/info:"):
        st.markdown(
            "- **Kesim tarihi** = son işlem tarihi − ufuk. Kesimden önceki işlemlerden müşteri "
            "öznitelikleri (recency, frekans, ciro, sipariş aralığı, kategori çeşitliliği, son 60 gün payı…) hesaplanır.\n"
            "- **Etiket**: müşteri kesimden sonraki *ufuk* gün içinde hiç alım yapmadıysa **kayıp (1)**.\n"
            "- Lojistik Regresyon ve Random Forest 5 katlı çapraz doğrulama + %25 test kümesiyle karşılaştırılır; "
            "en yüksek test ROC-AUC'li model seçilir.\n"
            "- Seçilen model, tüm veriyle hesaplanan **güncel** özniteliklere uygulanarak "
            "önümüzdeki *ufuk* gün için kayıp olasılığı üretir.")

    horizon = st.segmented_control("Tahmin ufku (gün)", [30, 60, 90], default=60, key="ch_h") or 60
    res = state.churn(c["dedup"], c["filters"], horizon)
    if "error" in res:
        st.warning(res["error"])
        return

    scored = res["scored"].copy()
    scored["Risk"] = scored["Kayıp Olasılığı"].map(risk_band)
    best = res["scores"].iloc[0]
    high = scored[scored["Risk"] == "Yüksek"]
    ui.kpi_row([
        {"label": "Seçilen model", "value": res["best"]},
        {"label": "Test ROC-AUC", "value": f"{best['Test ROC-AUC']:.3f}".replace(".", ","),
         "help": "0,5 = rastgele, 1 = mükemmel ayrım"},
        {"label": "Eğitim kümesi kayıp oranı", "value": pct(res["churn_rate"]),
         "help": f"{number(res['n_train'])} müşteri, kesim: {res['cutoff']:%d.%m.%Y}"},
        {"label": "Yüksek riskli müşteri", "value": number(len(high)),
         "help": "Kayıp olasılığı ≥ %70"},
        {"label": "Risk altındaki yıllık ciro", "value": money(high["monetary"].sum())},
    ])

    a, b = st.columns(2)
    with a:
        st.markdown("**Model karşılaştırması**")
        st.dataframe(res["scores"], hide_index=True, column_config={
            k: st.column_config.NumberColumn(format="%.3f")
            for k in ["CV ROC-AUC", "± std", "Test ROC-AUC", "Kesinlik", "Duyarlılık", "F1"]})
        imp = res["importance"]
        fig = px.bar(imp, x="Önem", y="Öznitelik", orientation="h",
                     color_discrete_sequence=[C.SERIES[0]])
        fig.update_xaxes(tickformat=".0%")
        ui.plot(charts.bar_marks(charts.finish(fig, f"Öznitelik önemi · {res['best']}", 360,
                                               x_title="", y_title="")))
    with b:
        fig = px.histogram(scored, x="Kayıp Olasılığı", nbins=25, color="Risk",
                           category_orders={"Risk": ["Düşük", "Orta", "Yüksek"]},
                           color_discrete_map={"Düşük": C.STATUS["good"], "Orta": C.STATUS["warning"],
                                               "Yüksek": C.STATUS["critical"]})
        fig.update_xaxes(tickformat=".0%")
        ui.plot(charts.bar_marks(charts.finish(fig, "Kayıp olasılığı dağılımı", 300,
                                               y_title="Müşteri")))
        fig = px.scatter(scored, x="recency", y="monetary", color="Kayıp Olasılığı",
                         color_continuous_scale=["#cde2fb", "#f0efec", "#ec835a", "#d03b3b"],
                         log_y=True, hover_name="CustomerID", range_color=[0, 1])
        fig.update_traces(marker=dict(size=7, line=dict(color="white", width=0.8)))
        fig.update_yaxes(tickprefix=C.CURRENCY, tickformat="~s", dtick=1)
        fig.update_layout(coloraxis_colorbar=dict(tickformat=".0%", thickness=10, title=""))
        ui.plot(charts.finish(fig, "Recency × ciro, renk = kayıp olasılığı", 360,
                              x_title="Son alımdan bu yana gün", y_title="Toplam ciro"))

    ui.section("Aksiyon listesi", "Kayıp olasılığı eşiğin üzerindeki müşteriler, cirolarına göre sıralı.")
    th = st.slider("Olasılık eşiği", 0.3, 0.95, 0.7, 0.05, key="ch_th")
    lst = (scored[scored["Kayıp Olasılığı"] >= th]
           .sort_values("monetary", ascending=False)
           [["CustomerID", "Kayıp Olasılığı", "Risk", "recency", "frequency", "monetary",
             "mean_gap", "recent_share"]])
    st.dataframe(lst, hide_index=True, height=320, column_config={
        "Kayıp Olasılığı": st.column_config.ProgressColumn(format="percent", min_value=0, max_value=1),
        "recency": st.column_config.NumberColumn("Son alım (gün)"),
        "frequency": st.column_config.NumberColumn("Sipariş"),
        "monetary": st.column_config.NumberColumn("Ciro", format="₺%,.0f"),
        "mean_gap": st.column_config.NumberColumn("Ort. sipariş aralığı (gün)", format="%.0f"),
        "recent_share": st.column_config.NumberColumn("Son 60 gün payı", format="percent")})
    ui.download(lst, "churn_aksiyon_listesi", "Aksiyon listesini indir")
