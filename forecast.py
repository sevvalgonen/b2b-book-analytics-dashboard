"""Tedarik Zinciri › Talep Tahmini"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src import charts, config as C, forecasting, state, ui
from src.formatting import compact, money, pct

TARGETS = {"Ciro (₺)": "Revenue", "Adet": "Quantity"}


def render() -> None:
    c = state.ctx()
    df = state.filtered(c["dedup"], c["filters"])
    ui.page_header("Talep Tahmini",
                   "Üç modelin geriye dönük testle karşılaştırılması ve en iyisiyle ileriye dönük tahmin. "
                   "Kategori/şehir bazında tahmin için kenar çubuğundan filtre seçin.",
                   c["filters"].describe())
    if not ui.guard(df, 500):
        return

    a, b, cc = st.columns([1, 2, 2])
    target_label = a.segmented_control("Hedef", list(TARGETS), default="Ciro (₺)", key="f_t") or "Ciro (₺)"
    target = TARGETS[target_label]
    horizon = b.slider("Tahmin ufku (gün)", 7, 90, 30, 1, key="f_h")
    test_days = cc.slider("Test penceresi (gün)", 14, 56, 28, 7, key="f_td",
                          help="Son N gün modelleri karşılaştırmak için ayrılır.")
    res = state.forecast(c["dedup"], c["filters"], target, horizon, test_days)
    if "error" in res:
        st.warning(res["error"])
        return

    fc, bt, scores = res["forecast"], res["backtest"], res["scores"]
    is_money = target == "Revenue"
    fmt = money if is_money else (lambda v: compact(v) + " adet")
    hist = forecasting.daily_series(df, target)
    last30 = hist.iloc[-horizon:].sum()
    ui.kpi_row([
        {"label": "En iyi model", "value": res["best"]},
        {"label": "Test hatası (WAPE)", "value": pct(scores.iloc[0]["WAPE %"]),
         "help": "Σ|gerçek − tahmin| / Σ gerçek", "delta_color": "inverse"},
        {"label": f"Önümüzdeki {horizon} gün", "value": fmt(fc["Tahmin"].sum()),
         "delta": pct(fc["Tahmin"].sum() / last30 - 1, signed=True) if last30 else None,
         "help": f"Son {horizon} gün gerçekleşen: {fmt(last30)}"},
        {"label": "Günlük ort. tahmin", "value": fmt(fc["Tahmin"].mean())},
    ])

    fig = go.Figure()
    h = hist.iloc[-150:]
    fig.add_scatter(x=h.index, y=h.values, name="Gerçekleşen", line=dict(color=C.INK["muted"], width=1.5))
    fig.add_scatter(x=bt.index, y=bt[res["best"]], name=f"Test tahmini ({res['best']})",
                    line=dict(color=C.SERIES[1], width=2, dash="dot"))
    fig.add_scatter(x=fc.index, y=fc["Üst"], line=dict(width=0), showlegend=False, hoverinfo="skip")
    fig.add_scatter(x=fc.index, y=fc["Alt"], line=dict(width=0), fill="tonexty",
                    fillcolor="rgba(42,120,214,0.15)", name="%95 tahmin aralığı", hoverinfo="skip")
    fig.add_scatter(x=fc.index, y=fc["Tahmin"], name="Tahmin", line=dict(color=C.SERIES[0], width=2.5))
    fig.add_vrect(x0=bt.index[0], x1=bt.index[-1], fillcolor=C.INK["grid"], opacity=0.35,
                  line_width=0, annotation_text="test", annotation_position="top left",
                  annotation_font=dict(size=11, color=C.INK["muted"]))
    fig.update_layout(hovermode="x unified")
    fig.update_xaxes(tickformat="%d.%m")
    ui.plot(charts.finish(fig, f"Günlük {target_label.lower()} · son 150 gün + {horizon} günlük tahmin",
                          430, money_axis=is_money))

    left, right = st.columns([2, 3])
    with left:
        st.markdown("**Model karşılaştırması (test penceresi)**")
        st.dataframe(scores, hide_index=True, column_config={
            "MAE": st.column_config.NumberColumn(format="%,.0f"),
            "RMSE": st.column_config.NumberColumn(format="%,.0f"),
            "WAPE %": st.column_config.NumberColumn(format="percent")})
        st.caption("**Mevsimsel naif**: 7 gün önceki değer (kıyas). **Holt-Winters**: sönümlü trend + "
                   "haftalık mevsimsellik. **Gradient Boosting**: takvim + gecikme (1/7/14 gün) + "
                   "hareketli ortalama öznitelikleri, özyinelemeli tahmin.")
    with right:
        fig = go.Figure()
        for i, col in enumerate(bt.columns):
            style = dict(color=C.INK["primary"], width=2) if col == "Gerçek" else \
                dict(color=C.SERIES[i - 1], width=1.8, dash="dot")
            fig.add_scatter(x=bt.index, y=bt[col], name=col, line=style)
        fig.update_layout(hovermode="x unified")
        fig.update_xaxes(tickformat="%d.%m")
        ui.plot(charts.finish(fig, "Test penceresinde modeller vs gerçek", 330, money_axis=is_money))

    weekly = fc.resample("W-SUN").sum()
    first = fc.index[0]
    weekly.index = [f"{max(d - pd.Timedelta(days=6), first):%d.%m} – {min(d, fc.index[-1]):%d.%m}"
                    for d in weekly.index]
    weekly = weekly.reset_index(names="Hafta")
    st.markdown("**Haftalık tahmin özeti** (planlama ve satın alma için)")
    col_fmt = "₺%,.0f" if is_money else "%,.0f"
    st.dataframe(weekly, hide_index=True, column_config={
        k: st.column_config.NumberColumn(format=col_fmt) for k in ["Tahmin", "Alt", "Üst"]})
    ui.download(fc.reset_index(names="Tarih"), "gunluk_tahmin")
    st.caption("Not: Veri yalnızca 2020'yi kapsadığından yıllık mevsimsellik öğrenilemez; pandemi "
               "dönemi (Nisan–Temmuz) trend tahminini etkileyebilir. Tahminler kısa vadeli planlama içindir.")
