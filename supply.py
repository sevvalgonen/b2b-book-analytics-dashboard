"""Tedarik zinciri analitiği: ABC-XYZ sınıflandırması, stok politikası, talep sinyalleri."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import norm


def weekly_demand(df: pd.DataFrame) -> pd.DataFrame:
    """Ürün × hafta adet matrisi (satış olmayan haftalar 0)."""
    weeks = pd.date_range(df["Week"].min(), df["Week"].max(), freq="7D")
    w = (df.groupby(["StockCode", "Week"], observed=True)["Quantity"].sum()
           .unstack(fill_value=0)
           .reindex(columns=weeks, fill_value=0))
    return w


def abc_xyz(df: pd.DataFrame, a_cut: float = 0.80, b_cut: float = 0.95,
            x_cut: float = 0.5, y_cut: float = 1.0) -> pd.DataFrame:
    """ABC: ciro payına göre; XYZ: haftalık talebin değişkenlik katsayısına (CV) göre."""
    prod = (df.groupby("StockCode", observed=True)
              .agg(Ürün=("Description", "first"), Kategori=("Category", "first"),
                   Ciro=("Revenue", "sum"), Adet=("Quantity", "sum"),
                   SonSatış=("InvoiceDate", "max"), Müşteri=("CustomerID", "nunique"))
              .sort_values("Ciro", ascending=False))
    cum = prod["Ciro"].cumsum() / prod["Ciro"].sum()
    prod["ABC"] = np.select([cum <= a_cut, cum <= b_cut], ["A", "B"], "C")

    w = weekly_demand(df).reindex(prod.index)
    mean = w.mean(axis=1)
    cv = (w.std(axis=1) / mean.replace(0, np.nan)).fillna(np.inf)
    prod["HaftalıkOrt"] = mean
    prod["CV"] = cv
    prod["XYZ"] = np.select([cv <= x_cut, cv <= y_cut], ["X", "Y"], "Z")
    prod["Sınıf"] = prod["ABC"] + prod["XYZ"]
    return prod.reset_index()


ABC_XYZ_POLICY = {
    "AX": "Sürekli ikmal, düşük emniyet stoğu, otomatik sipariş",
    "AY": "Sık gözden geçirme, orta emniyet stoğu",
    "AZ": "Talebe göre sipariş, yakın izleme; yüksek risk",
    "BX": "Periyodik ikmal, standart emniyet stoğu",
    "BY": "Periyodik gözden geçirme, orta emniyet stoğu",
    "BZ": "Sipariş üzerine tedarik değerlendir",
    "CX": "Toplu ve seyrek sipariş, düşük stok",
    "CY": "Minimum stok, toplu sipariş",
    "CZ": "Stoksuz çalış / siparişe göre tedarik; portföyden çıkarmayı değerlendir",
}


def abc_xyz_matrix(prod: pd.DataFrame, value: str = "count") -> pd.DataFrame:
    if value == "count":
        m = pd.crosstab(prod["ABC"], prod["XYZ"])
    else:
        m = prod.pivot_table(index="ABC", columns="XYZ", values="Ciro",
                             aggfunc="sum", fill_value=0)
    return m.reindex(index=["A", "B", "C"], columns=["X", "Y", "Z"], fill_value=0)


def inventory_policy(df: pd.DataFrame, prod: pd.DataFrame, lead_time: int,
                     service_level: float, order_cost: float, holding_rate: float,
                     classes: tuple = ("A", "B")) -> pd.DataFrame:
    """Emniyet stoğu, yeniden sipariş noktası ve EOK (ekonomik sipariş miktarı).

    Talep günlük düzeyde (satışsız günler 0) modellenir:
      SS  = z · σ_gün · √LT
      ROP = μ_gün · LT + SS
      EOK = √(2 · D_yıllık · S / H),   H = birim maliyet · yıllık elde tutma oranı
    Birim maliyet yaklaşık olarak ortalama net fiyat alınır.
    """
    sel = prod[prod["ABC"].isin(classes)]
    codes = sel["StockCode"]
    d = df[df["StockCode"].isin(codes)]
    days = pd.date_range(df["InvoiceDate"].min(), df["InvoiceDate"].max(), freq="D")
    daily = (d.groupby(["StockCode", "InvoiceDate"], observed=True)["Quantity"].sum()
               .unstack(fill_value=0).reindex(columns=days, fill_value=0))
    mu, sigma = daily.mean(axis=1), daily.std(axis=1)
    price = d.groupby("StockCode", observed=True)["NetPrice"].mean()

    z = norm.ppf(service_level)
    out = sel.set_index("StockCode")[["Ürün", "Kategori", "Sınıf", "Ciro", "Adet"]].copy()
    out["Günlük Ort."] = mu
    out["Günlük σ"] = sigma
    out["Emniyet Stoğu"] = np.ceil(z * sigma * np.sqrt(lead_time))
    out["Yeniden Sipariş Noktası"] = np.ceil(mu * lead_time) + out["Emniyet Stoğu"]
    annual = mu * 365
    h = (price * holding_rate).replace(0, np.nan)
    out["EOK"] = np.ceil(np.sqrt(2 * annual * order_cost / h)).fillna(0)
    out["Yıllık Sipariş Sayısı"] = (annual / out["EOK"].replace(0, np.nan)).round(1)
    out["Ort. Net Fiyat"] = price
    out["Emniyet Stoğu Değeri"] = out["Emniyet Stoğu"] * price
    return out.reset_index().sort_values("Ciro", ascending=False)


def category_momentum(df: pd.DataFrame, window_days: int = 28) -> pd.DataFrame:
    """Son pencere ile bir önceki pencere arasındaki talep değişimi (kategori bazında)."""
    end = df["InvoiceDate"].max()
    cur = df[df["InvoiceDate"] > end - pd.Timedelta(days=window_days)]
    prev = df[(df["InvoiceDate"] <= end - pd.Timedelta(days=window_days)) &
              (df["InvoiceDate"] > end - pd.Timedelta(days=2 * window_days))]
    a = cur.groupby("CategoryGroup", observed=True)["Quantity"].sum()
    b = prev.groupby("CategoryGroup", observed=True)["Quantity"].sum()
    out = pd.DataFrame({"Son dönem": a, "Önceki dönem": b}).fillna(0)
    out["Değişim %"] = (out["Son dönem"] - out["Önceki dönem"]) / out["Önceki dönem"].replace(0, np.nan)
    return out.dropna().sort_values("Değişim %").reset_index(names="Kategori")


def slow_movers(prod: pd.DataFrame, end: pd.Timestamp, idle_days: int = 60,
                min_units: int = 10) -> pd.DataFrame:
    """Geçmişte satılmış ama son `idle_days` gündür hareketsiz ürünler."""
    p = prod.copy()
    p["Hareketsiz Gün"] = (end - p["SonSatış"]).dt.days
    p = p[(p["Hareketsiz Gün"] >= idle_days) & (p["Adet"] >= min_units)]
    return p.sort_values("Ciro", ascending=False)[
        ["StockCode", "Ürün", "Kategori", "Adet", "Ciro", "SonSatış", "Hareketsiz Gün"]]


def weekday_workload(df: pd.DataFrame) -> pd.DataFrame:
    """Depo toplama yükü: haftanın günlerine göre sipariş satırı ve adet."""
    g = df.groupby("Weekday").agg(Satır=("Revenue", "size"), Adet=("Quantity", "sum"),
                                  Sipariş=("InvoiceNo", "nunique"))
    n_days = df.groupby("Weekday")["InvoiceDate"].nunique()
    g["Günlük Ort. Satır"] = g["Satır"] / n_days
    g["Pay %"] = g["Satır"] / g["Satır"].sum()
    return g.reset_index()
