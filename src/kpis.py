"""Satış KPI'ları ve tanımlayıcı satış analizleri."""
from __future__ import annotations

import pandas as pd

from src import config as C


def kpi_summary(df: pd.DataFrame) -> dict:
    """Temel performans göstergeleri."""
    if df.empty:
        return {k: 0.0 for k in ["revenue", "gross", "discount_rate", "orders",
                                 "customers", "skus", "units", "aov", "lines_per_order",
                                 "revenue_per_customer"]}
    revenue = df["Revenue"].sum()
    gross = df["GrossRevenue"].sum()
    orders = df["InvoiceNo"].nunique()
    customers = df["CustomerID"].nunique()
    return {
        "revenue": revenue,
        "gross": gross,
        "discount_rate": 1 - revenue / gross if gross else 0,
        "orders": orders,
        "customers": customers,
        "skus": df["StockCode"].nunique(),
        "units": int(df["Quantity"].sum()),
        "aov": revenue / orders if orders else 0,
        "lines_per_order": len(df) / orders if orders else 0,
        "revenue_per_customer": revenue / customers if customers else 0,
    }


def previous_period(full: pd.DataFrame, start: pd.Timestamp,
                    end: pd.Timestamp) -> pd.DataFrame | None:
    """Seçili dönemle aynı uzunluktaki bir önceki dönem (veri varsa)."""
    span = end - start
    p_end = start - pd.Timedelta(days=1)
    p_start = p_end - span
    if p_start < full["InvoiceDate"].min():
        return None
    return full[full["InvoiceDate"].between(p_start, p_end)]


def monthly_trend(df: pd.DataFrame) -> pd.DataFrame:
    m = (df.groupby(df["InvoiceDate"].dt.to_period("M"), observed=True)
           .agg(Ciro=("Revenue", "sum"), Sipariş=("InvoiceNo", "nunique"),
                Müşteri=("CustomerID", "nunique"), Adet=("Quantity", "sum"),
                Brüt=("GrossRevenue", "sum")))
    m["İskonto %"] = 1 - m["Ciro"] / m["Brüt"]
    m["Sepet Ort."] = m["Ciro"] / m["Sipariş"]
    m["Aylık Değişim %"] = m["Ciro"].pct_change()
    m.index = m.index.to_timestamp()
    one_year = m.index.year.nunique() == 1
    m["Ay"] = [C.MONTHS_TR[d.month - 1] if one_year else f"{C.MONTHS_TR[d.month - 1]} {d.year}"
               for d in m.index]
    return m.reset_index(names="Tarih")


def time_series(df: pd.DataFrame, freq: str = "W") -> pd.DataFrame:
    rule = {"D": "D", "W": "W-SUN", "M": "MS"}[freq]
    s = (df.set_index("InvoiceDate")
           .resample(rule)
           .agg({"Revenue": "sum", "Quantity": "sum", "InvoiceNo": "nunique"}))
    s.columns = ["Ciro", "Adet", "Sipariş"]
    return s.reset_index(names="Tarih")


def by_dimension(df: pd.DataFrame, col: str, n: int | None = None) -> pd.DataFrame:
    g = (df.groupby(col, observed=True)
           .agg(Ciro=("Revenue", "sum"), Adet=("Quantity", "sum"),
                Sipariş=("InvoiceNo", "nunique"), Müşteri=("CustomerID", "nunique"),
                Brüt=("GrossRevenue", "sum"))
           .sort_values("Ciro", ascending=False))
    g["Pay %"] = g["Ciro"] / g["Ciro"].sum()
    g["İskonto %"] = 1 - g["Ciro"] / g["Brüt"]
    g = g.drop(columns="Brüt")
    if n:
        g = g.head(n)
    return g.reset_index()


def top_products(df: pd.DataFrame, n: int = 20) -> pd.DataFrame:
    g = (df.groupby("StockCode", observed=True)
           .agg(Ürün=("Description", "first"), Kategori=("Category", "first"),
                Ciro=("Revenue", "sum"), Adet=("Quantity", "sum"),
                Müşteri=("CustomerID", "nunique"))
           .sort_values("Ciro", ascending=False).head(n))
    return g.reset_index()


def pareto(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """Kümülatif ciro payı (Pareto / 80-20 analizi)."""
    s = df.groupby(col, observed=True)["Revenue"].sum().sort_values(ascending=False)
    out = pd.DataFrame({"Ciro": s})
    out["Kümülatif %"] = s.cumsum() / s.sum()
    out["Varlık %"] = (pd.RangeIndex(1, len(s) + 1) / len(s)).to_numpy()
    return out.reset_index()


def share_of_top(df: pd.DataFrame, col: str, top_frac: float = 0.2) -> float:
    s = df.groupby(col, observed=True)["Revenue"].sum().sort_values(ascending=False)
    k = max(1, int(len(s) * top_frac))
    return s.head(k).sum() / s.sum() if s.sum() else 0


def weekday_month_matrix(df: pd.DataFrame) -> pd.DataFrame:
    m = (df.groupby([df["InvoiceDate"].dt.month, "Weekday"])["Revenue"].sum()
           .unstack(fill_value=0))
    m.index = [C.MONTHS_TR[i - 1] for i in m.index]
    m.columns = [C.WEEKDAYS_TR[i] for i in m.columns]
    return m


def discount_bands(df: pd.DataFrame) -> pd.DataFrame:
    bins = [-0.001, 0.2, 0.3, 0.35, 0.4, 0.45, 1.0]
    labels = ["<%20", "%20-30", "%30-35", "%35-40", "%40-45", ">%45"]
    band = pd.cut(df["DiscountRate"], bins=bins, labels=labels)
    g = df.groupby(band, observed=True).agg(
        Ciro=("Revenue", "sum"), Satır=("Revenue", "size"),
        OrtAdet=("Quantity", "mean"))
    return g.reset_index(names="İskonto bandı")
