"""Yönetici Özeti › İçgörüler ve Öneriler"""
from __future__ import annotations

import streamlit as st

from src import insights, state, supply, ui
from src.customers import segment_summary


def render() -> None:
    c = state.ctx()
    dedup, f = c["dedup"], c["filters"]
    df = state.filtered(dedup, f)
    ui.page_header("İçgörüler ve Öneriler",
                   "Tüm analiz modüllerinin sonuçlarından otomatik üretilen, departmanlara göre "
                   "gruplanmış bulgular ve aksiyon önerileri.", f.describe())
    if not ui.guard(df, 1000):
        return

    with st.spinner("Analizler derleniyor…"):
        sales = insights.sales_insights(df)
        rfm = state.rfm(dedup, f)
        seg = segment_summary(rfm) if len(rfm) >= 20 else None
        churn = state.churn(dedup, f, 60)
        churn = None if "error" in churn else churn
        mkt = insights.marketing_insights(seg, churn) if seg is not None else []
        prod = state.abc_xyz(dedup, f)
        sc = insights.supply_insights(df, prod, supply.category_momentum(df),
                                      supply.weekday_workload(df))
        fc = state.forecast(dedup, f, "Revenue", 30, 28)
        mgmt = [i for i in sales if i.department == "Yönetim"] + insights.forecast_insight(fc)
        sales = [i for i in sales if i.department != "Yönetim"]

    t0, t1, t2, t3 = st.tabs([":material/workspace_premium: Yönetim", ":material/trending_up: Satış",
                              ":material/campaign: Pazarlama", ":material/local_shipping: Tedarik Zinciri"])
    with t0:
        ui.insight_cards(mgmt)
    with t1:
        ui.insight_cards(sales)
    with t2:
        ui.insight_cards(mkt)
    with t3:
        ui.insight_cards(sc)

    ui.section("Karar destek önerileri")
    st.markdown(
        """
| Departman | Öneri | Dayanak (panel sayfası) |
|---|---|---|
| **Satış** | Müşterilerin en büyük %20'si için kilit hesap yönetimi; İstanbul dışı illerde temsilci kapsamını genişletme | Satış Performansı › Müşteri, Bölgesel Analiz |
| **Satış** | Talebin düştüğü yaz aylarına (Tem) okul öncesi/okul hazırlık kampanyalarını öne çekme | Genel Bakış, Talep Tahmini |
| **Pazarlama** | *Risk Altında* ve *Kaybedilmemeli* segmentlerine kişisel geri kazanım teklifi; churn listesindeki yüksek cirolu müşterilere temsilci araması | Müşteri Segmentasyonu, Müşteri Kaybı Tahmini |
| **Pazarlama** | Yüksek lift'li kategori çiftleri için paket kampanya ve sipariş ekranında "birlikte alınanlar" önerisi | Sepet Analizi |
| **Tedarik Zinciri** | A sınıfı ürünlerde ROP tabanlı otomatik ikmal; CZ ürünlerinde siparişe göre tedarik | Envanter Analizi › ABC-XYZ, Stok Politikası |
| **Tedarik Zinciri** | Pazartesi pik yükü için depo vardiya planlaması; hareketsiz ürünlerde yayınevine iade | Envanter Analizi › Talep Sinyalleri |
"""
    )
