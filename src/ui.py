"""Arayüz bileşenleri: stil, sayfa başlığı, KPI kartları, içgörü kartları."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src import config as C
from src.charts import PLOT_CONFIG

CSS = f"""
<style>
.block-container {{padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1400px;}}
h1, h2, h3 {{letter-spacing: -0.01em;}}
.page-sub {{color: {C.INK['secondary']}; margin-top: -0.6rem; margin-bottom: 1.2rem;}}
.filter-pill {{display:inline-block; font-size: 0.78rem; color: {C.INK['secondary']};
  background: #f1f0ec; border-radius: 999px; padding: 2px 10px; margin-bottom: 0.8rem;}}
div[data-testid="stMetric"] {{background: #ffffff; border: 1px solid rgba(11,11,11,0.08);
  border-radius: 12px; padding: 14px 16px;}}
div[data-testid="stMetricLabel"] p {{font-size: 0.82rem; color: {C.INK['secondary']};}}
div[data-testid="stMetricValue"] {{font-size: 1.55rem;}}
.insight {{border: 1px solid rgba(11,11,11,0.08); border-left: 4px solid var(--c);
  border-radius: 10px; padding: 10px 14px; margin-bottom: 10px; background: #fff;}}
.insight .t {{font-weight: 600; color: {C.INK['primary']}; font-size: 0.92rem;}}
.insight .d {{font-size: 0.74rem; color: {C.INK['muted']}; text-transform: uppercase;
  letter-spacing: 0.04em;}}
.insight .b {{font-size: 0.88rem; color: {C.INK['secondary']}; margin-top: 2px;}}
.section-cap {{color: {C.INK['muted']}; font-size: 0.85rem; margin-top: -0.5rem;}}
</style>
"""

LEVEL_STYLE = {"good": (C.STATUS["good"], "✓"), "warning": (C.STATUS["warning"], "!"),
               "critical": (C.STATUS["critical"], "▲"), "info": (C.SERIES[0], "i")}


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def page_header(title: str, subtitle: str, filters_text: str | None = None) -> None:
    st.title(title)
    st.markdown(f"<div class='page-sub'>{subtitle}</div>", unsafe_allow_html=True)
    if filters_text:
        st.markdown(f"<span class='filter-pill'>Aktif filtre · {filters_text}</span>",
                    unsafe_allow_html=True)


def section(title: str, caption: str | None = None) -> None:
    st.subheader(title)
    if caption:
        st.markdown(f"<div class='section-cap'>{caption}</div>", unsafe_allow_html=True)


def kpi_row(items: list[dict]) -> None:
    """items: [{label, value, delta?, help?, delta_color?}]"""
    cols = st.columns(len(items))
    for col, it in zip(cols, items):
        col.metric(it["label"], it["value"], delta=it.get("delta"),
                   help=it.get("help"), delta_color=it.get("delta_color", "normal"))


def insight_cards(insights: list, columns: int = 2) -> None:
    if not insights:
        st.info("Seçili filtrelerde içgörü üretilecek kadar veri yok.")
        return
    cols = st.columns(columns)
    for i, ins in enumerate(insights):
        color, icon = LEVEL_STYLE.get(ins.level, LEVEL_STYLE["info"])
        cols[i % columns].markdown(
            f"<div class='insight' style='--c:{color}'>"
            f"<div class='d'>{icon} {ins.department}</div>"
            f"<div class='t'>{ins.title}</div><div class='b'>{ins.text}</div></div>",
            unsafe_allow_html=True)


def plot(fig) -> None:
    st.plotly_chart(fig, config=PLOT_CONFIG)


def download(df: pd.DataFrame, name: str, label: str = "CSV indir") -> None:
    st.download_button(label, df.to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"{name}.csv", mime="text/csv", icon=":material/download:")


def guard(df: pd.DataFrame, min_rows: int = 1) -> bool:
    """Filtre sonucu boşsa kullanıcıyı uyarır ve False döner."""
    if len(df) < min_rows:
        st.warning("Seçili filtrelerle eşleşen yeterli kayıt yok. Kenar çubuğundan filtreleri genişletin.")
        return False
    return True
