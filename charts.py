"""Plotly tema ayarları ve tekrar kullanılan grafik bileşenleri."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio

from src import config as C

FONT = "Inter, system-ui, -apple-system, 'Segoe UI', sans-serif"

pio.templates["b2b"] = go.layout.Template(
    layout=dict(
        font=dict(family=FONT, size=13, color=C.INK["secondary"]),
        title=dict(font=dict(size=15, color=C.INK["primary"]), x=0, xanchor="left",
                   y=0.985, yref="container", yanchor="top"),
        colorway=C.SERIES,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=8, r=8, t=76, b=8),
        hoverlabel=dict(bgcolor="white", font=dict(family=FONT, size=12, color=C.INK["primary"]),
                        bordercolor=C.INK["grid"]),
        xaxis=dict(showgrid=False, linecolor=C.INK["axis"], ticks="",
                   tickfont=dict(color=C.INK["muted"]), title=dict(font=dict(color=C.INK["muted"]))),
        yaxis=dict(gridcolor=C.INK["grid"], zeroline=False, linecolor="rgba(0,0,0,0)",
                   tickfont=dict(color=C.INK["muted"]), title=dict(font=dict(color=C.INK["muted"]))),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0,
                    title=None, font=dict(size=12)),
        bargap=0.25,
        separators=",.",
    )
)
pio.templates.default = "plotly_white+b2b"

PLOT_CONFIG = {"displaylogo": False,
               "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"],
               "toImageButtonOptions": {"format": "png", "scale": 2}}


def finish(fig: go.Figure, title: str | None = None, height: int = 360,
           y_title: str | None = None, x_title: str | None = None,
           money_axis: bool = False) -> go.Figure:
    fig.update_layout(title=title, height=height)
    if y_title is not None:
        fig.update_yaxes(title=y_title)
    if x_title is not None:
        fig.update_xaxes(title=x_title)
    if money_axis:
        fig.update_yaxes(tickprefix=C.CURRENCY, tickformat="~s")
    return fig


def bar_marks(fig: go.Figure) -> go.Figure:
    """İnce, köşeleri yuvarlatılmış çubuklar."""
    fig.update_traces(marker_line_width=0, selector=dict(type="bar"))
    fig.update_layout(barcornerradius=4)
    return fig


def line_trend(df: pd.DataFrame, x: str, y: str, title: str, color: str | None = None,
               money_axis: bool = True, height: int = 340) -> go.Figure:
    fig = px.line(df, x=x, y=y, color=color, markers=False)
    fig.update_traces(line=dict(width=2))
    if color is None:
        fig.update_traces(name=y, showlegend=True)
    fig.update_layout(hovermode="x unified")
    fig.update_xaxes(tickformat="%d.%m.%y")  # dil bağımsız tarih etiketi
    return finish(fig, title, height, y_title="", x_title="", money_axis=money_axis)


def hbar(df: pd.DataFrame, x: str, y: str, title: str, money_axis: bool = True,
         height: int = 420, text: str | None = None, color: str = C.SERIES[0]) -> go.Figure:
    d = df.sort_values(x)
    fig = px.bar(d, x=x, y=y, orientation="h", text=text)
    fig.update_traces(marker_color=color, textposition="outside", cliponaxis=False,
                      textfont=dict(color=C.INK["secondary"], size=11))
    fig.update_yaxes(title="", automargin=True)
    xmax = float(d[x].max()) if len(d) else 1.0
    fig.update_xaxes(title="", showgrid=True, gridcolor=C.INK["grid"],
                     range=[0, xmax * (1.18 if text else 1.05)])
    if money_axis:
        fig.update_xaxes(tickprefix=C.CURRENCY, tickformat="~s")
    return bar_marks(finish(fig, title, height))


def heatmap(m: pd.DataFrame, title: str, fmt: str = "~s", height: int = 380,
            colors: list[str] | None = None, text_fmt: str | None = None) -> go.Figure:
    fig = px.imshow(m, aspect="auto", color_continuous_scale=colors or C.SEQUENTIAL,
                    text_auto=text_fmt or False)
    fig.update_layout(coloraxis_colorbar=dict(title="", tickformat=fmt, thickness=10))
    fig.update_xaxes(side="bottom", title="", tickangle=0)
    fig.update_yaxes(title="")
    return finish(fig, title, height)
