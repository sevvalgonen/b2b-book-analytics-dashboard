"""Pazarlama › Sepet Analizi (birliktelik kuralları + öneri)"""
from __future__ import annotations

import plotly.express as px
import streamlit as st

from src import basket, charts, config as C, state, ui
from src.formatting import number

LEVELS = {"Kategori": "Category", "Ürün (en sık 150)": "Product"}
DEFAULTS = {"Category": (0.02, 0.30, 1.2), "Product": (0.005, 0.20, 2.0)}


def render() -> None:
    c = state.ctx()
    df = state.filtered(c["dedup"], c["filters"])
    ui.page_header("Sepet Analizi",
                   "FP-Growth algoritmasıyla birlikte satın alınan kategori/ürünlerin keşfi; çapraz satış önerileri.",
                   c["filters"].describe())
    if not ui.guard(df, 500):
        return

    a, b, cc, d = st.columns([1.3, 1, 1, 1])
    level_label = a.segmented_control("Analiz düzeyi", list(LEVELS), default="Kategori",
                                      key="b_level") or "Kategori"
    level = LEVELS[level_label]
    s0, c0, l0 = DEFAULTS[level]
    sup = b.number_input("Min. destek", 0.001, 0.5, s0, 0.001, format="%.3f", key=f"b_s_{level}",
                         help="Kuralın geçtiği sepetlerin oranı")
    conf = cc.number_input("Min. güven", 0.05, 1.0, c0, 0.05, key=f"b_c_{level}",
                           help="P(Sonuç | Öncül)")
    lift = d.number_input("Min. lift", 1.0, 50.0, l0, 0.1, key=f"b_l_{level}",
                          help=">1: birlikte alınma olasılığı tesadüften yüksek")

    rules, n_baskets = state.rules(c["dedup"], c["filters"], level, sup, conf, lift)
    ui.kpi_row([
        {"label": "Analiz edilen sepet", "value": number(n_baskets),
         "help": "En az 2 farklı öğe içeren faturalar"},
        {"label": "Bulunan kural", "value": number(len(rules))},
        {"label": "En yüksek lift", "value": f"{rules['Kaldıraç (Lift)'].max():.1f}".replace(".", ",")
         if len(rules) else "—"},
        {"label": "Ort. güven", "value": f"%{rules['Güven'].mean() * 100:.0f}" if len(rules) else "—"},
    ])
    if rules.empty:
        st.info("Bu eşiklerle kural bulunamadı. Min. destek veya güveni düşürün.")
        return

    left, right = st.columns([3, 2])
    with left:
        top = rules.head(400)
        fig = px.scatter(top, x="Destek", y="Güven", size="Kaldıraç (Lift)", color="Kaldıraç (Lift)",
                         color_continuous_scale=C.SEQUENTIAL[2:], hover_data={"Öncül": True, "Sonuç": True},
                         size_max=18, log_x=True)
        fig.update_traces(marker=dict(line=dict(color="white", width=0.8)))
        fig.update_xaxes(tickformat=".1%")
        fig.update_yaxes(tickformat=".0%")
        fig.update_layout(coloraxis_colorbar=dict(title="Lift", thickness=10))
        ui.plot(charts.finish(fig, "Kurallar: destek × güven (boyut/renk = lift)", 430))
    with right:
        st.markdown("**Çapraz satış önerisi**")
        items = sorted({i for s in rules["antecedents"] for i in s})
        item = st.selectbox("Müşteri bunu aldığında…", items, key=f"b_item_{level}")
        rec = basket.recommend(rules, item, 8)
        st.dataframe(rec, hide_index=True, height=330, column_config={
            "Güven": st.column_config.ProgressColumn(format="percent", min_value=0, max_value=1),
            "Kaldıraç (Lift)": st.column_config.NumberColumn(format="%.2f"),
            "Destek": st.column_config.NumberColumn(format="percent")})

    ui.section("Kural tablosu", "Lift'e göre sıralı. Pazarlama: paket kampanya; Tedarik: birlikte stoklama ve raf yerleşimi.")
    show = rules.drop(columns=["antecedents", "consequents"])
    st.dataframe(show, hide_index=True, height=360, column_config={
        "Destek": st.column_config.NumberColumn(format="percent"),
        "Güven": st.column_config.NumberColumn(format="percent"),
        "Kaldıraç (Lift)": st.column_config.NumberColumn(format="%.2f"),
        "İkna": st.column_config.NumberColumn(format="%.2f")})
    ui.download(show, f"birliktelik_kurallari_{level.lower()}")
