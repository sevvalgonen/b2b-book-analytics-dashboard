"""Veri yükleme, ön işleme ve filtreleme.

Ön işleme adımları sırayla uygulanır ve her adımın etkisi bir rapora
yazılır; böylece "Veri Kalitesi" sayfası tüm dönüşümleri şeffaf gösterir.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src import config as C

_TR_FOLD = str.maketrans("çğıİöşüÇĞÖŞÜâÂîÎ", "cgiIosuCGOSUaAiI")


# ---------------------------------------------------------------------------
# Yükleme
# ---------------------------------------------------------------------------
def load_raw() -> pd.DataFrame:
    """Ham veriyi okur. Parquet varsa onu (hızlı), yoksa Excel'i kullanır."""
    if C.RAW_PARQUET.exists():
        return pd.read_parquet(C.RAW_PARQUET)
    df = pd.read_excel(C.RAW_XLSX, dtype={"StockCode": str})
    for col in ["InvoiceNo", "CustomerID", "InvoiceDate", "StockCode",
                "Description", "Category", "City"]:
        df[col] = df[col].where(df[col].isna(), df[col].astype(str))
    return df


def _signed_area(ring: list) -> float:
    return sum(x0 * y1 - x1 * y0 for (x0, y0, *_), (x1, y1, *_) in zip(ring, ring[1:]))


def _rewind(geojson: dict) -> dict:
    """Plotly (d3-geo) dış halkaların saat yönünde olmasını bekler; RFC 7946 tersini
    önerir. Yanlış yönlü halkalar haritanın boş/ters dolu çizilmesine yol açar."""
    for feat in geojson["features"]:
        geom = feat["geometry"]
        polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
        for poly in polys:
            for i, ring in enumerate(poly):
                clockwise = _signed_area(ring) < 0
                if (i == 0) != clockwise:  # dış halka saat yönü, delikler ters yön
                    ring.reverse()
    return geojson


def load_geojson() -> dict:
    with open(C.GEOJSON, encoding="utf-8") as fh:
        return _rewind(json.load(fh))


def _fold(name: str) -> str:
    return name.translate(_TR_FOLD).upper().strip()


def city_name_map(geojson: dict) -> dict[str, str]:
    """Veri setindeki il yazımını GeoJSON'daki resmi ada eşler."""
    official = {_fold(f["properties"]["name"]): f["properties"]["name"]
                for f in geojson["features"]}
    mapping = {_fold(k): v for k, v in C.CITY_ALIASES.items()}
    return {**official, **mapping}


# ---------------------------------------------------------------------------
# Ön işleme
# ---------------------------------------------------------------------------
@dataclass
class QualityReport:
    raw_rows: int
    raw_missing: dict
    steps: list[dict] = field(default_factory=list)
    flags: dict = field(default_factory=dict)

    def log(self, step: str, before: int, after: int, action: str) -> None:
        self.steps.append({"Adım": step, "Önce": before, "Sonra": after,
                           "Etkilenen": before - after, "Uygulanan işlem": action})

    def as_frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.steps)


def preprocess(raw: pd.DataFrame, geojson: dict,
               drop_duplicates: bool = True) -> tuple[pd.DataFrame, QualityReport]:
    """Ham işlem verisini analize hazır hale getirir."""
    df = raw.copy()
    rep = QualityReport(raw_rows=len(df), raw_missing=df.isna().sum().to_dict())

    # 1) Tip dönüşümleri
    df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"], errors="coerce")
    n = len(df)
    df = df.dropna(subset=["InvoiceDate"])
    rep.log("Tarih dönüşümü", n, len(df), "Metin tarih → datetime; geçersiz tarihler silindi")

    # 2) Eksik miktar
    n = len(df)
    df = df.dropna(subset=["Quantity"])
    rep.log("Eksik miktar", n, len(df), "Quantity boş olan satırlar silindi")

    # 3) Sıfır / negatif miktar (düzeltme kayıtları)
    n = len(df)
    df = df[df["Quantity"] > 0]
    rep.log("Sıfır/negatif miktar", n, len(df),
            "Miktarı 0 olan düzeltme (iade/iptal) kayıtları silindi")

    # 4) Bedelsiz / sembolik fiyatlı satırlar
    n = len(df)
    df = df[(df["NetPrice"] > 0) & (df["UnitPrice"] >= 0.01)]
    rep.log("Bedelsiz satır", n, len(df),
            "Net fiyatı ≤ 0 veya liste fiyatı sembolik (0,0001) olan promosyon satırları silindi")

    # 5) Tam kopya satırlar
    n = len(df)
    if drop_duplicates:
        df = df.drop_duplicates()
        rep.log("Tam kopya satır", n, len(df),
                "Tüm sütunları aynı olan mükerrer satırlar silindi")
    else:
        rep.log("Tam kopya satır", n, n, "Kullanıcı tercihiyle korundu (kenar çubuğu)")

    # 6) Net fiyatı liste fiyatını aşan satırlar → liste fiyatı net fiyata eşitlenir
    over = df["NetPrice"] > df["UnitPrice"]
    df.loc[over, "UnitPrice"] = df.loc[over, "NetPrice"]
    rep.flags["Net > liste fiyatı (düzeltildi)"] = int(over.sum())

    # 7) Eksik kategori / şehir doldurma, il adlarını standartlaştırma
    rep.flags["Eksik kategori → 'Belirtilmemiş'"] = int(df["Category"].isna().sum())
    rep.flags["Eksik şehir → 'Belirtilmemiş'"] = int(df["City"].isna().sum())
    df["Category"] = df["Category"].fillna(C.UNKNOWN).str.strip()
    cmap = city_name_map(geojson)
    df["City"] = df["City"].map(lambda c: cmap.get(_fold(c), c.title())
                                if isinstance(c, str) else C.UNKNOWN)

    # 8) Özellik türetme
    df["Revenue"] = df["Quantity"] * df["NetPrice"]
    df["GrossRevenue"] = df["Quantity"] * df["UnitPrice"]
    df["DiscountAmt"] = df["GrossRevenue"] - df["Revenue"]
    df["DiscountRate"] = 1 - df["NetPrice"] / df["UnitPrice"]
    df["DocType"] = df["InvoiceNo"].str[:3]
    df["CustType"] = df["CustomerID"].str[0] + "-grubu"
    df["Month"] = df["InvoiceDate"].dt.month
    df["Week"] = df["InvoiceDate"].dt.to_period("W-SUN").dt.start_time
    df["Weekday"] = df["InvoiceDate"].dt.dayofweek

    # Küçük kategorileri grafikler için "Diğer" altında topla
    top = (df.groupby("Category")["Revenue"].sum()
             .nlargest(C.TOP_CATEGORY_N).index)
    df["CategoryGroup"] = np.where(df["Category"].isin(top), df["Category"], C.OTHER)

    # 9) Aykırı değer işaretleme (silinmez: B2B toplu siparişler gerçektir)
    # IQR sınırı bu veride çok dar (Q3=2) olduğundan %99'luk dilim de dikkate alınır
    q1, q3 = df["Quantity"].quantile([0.25, 0.75])
    upper = max(q3 + 3 * (q3 - q1), df["Quantity"].quantile(0.99))
    df["BulkOrder"] = df["Quantity"] > upper
    rep.flags[f"Toplu sipariş işareti (miktar > {upper:.0f})"] = int(df["BulkOrder"].sum())

    # Bellek optimizasyonu
    for col in ["CustomerID", "StockCode", "Description", "Category", "City",
                "DocType", "CustType", "CategoryGroup", "InvoiceNo"]:
        df[col] = df[col].astype("category")
    df["Quantity"] = df["Quantity"].astype("int32")
    df = df.reset_index(drop=True)
    return df, rep


# ---------------------------------------------------------------------------
# Filtreleme
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Filters:
    """Kenar çubuğu filtreleri. Hashlenebilir; önbellek anahtarı olarak kullanılır."""
    start: pd.Timestamp
    end: pd.Timestamp
    doc_types: tuple = ()
    cust_types: tuple = ()
    cities: tuple = ()
    categories: tuple = ()

    def describe(self) -> str:
        parts = [f"{self.start:%d.%m.%Y} – {self.end:%d.%m.%Y}"]
        for label, val in [("Belge", self.doc_types), ("Müşteri grubu", self.cust_types),
                           ("Şehir", self.cities), ("Kategori", self.categories)]:
            if val:
                parts.append(f"{label}: {len(val)} seçili")
        return " · ".join(parts)


def apply_filters(df: pd.DataFrame, f: Filters) -> pd.DataFrame:
    mask = df["InvoiceDate"].between(f.start, f.end)
    if f.doc_types:
        mask &= df["DocType"].isin(f.doc_types)
    if f.cust_types:
        mask &= df["CustType"].isin(f.cust_types)
    if f.cities:
        mask &= df["City"].isin(f.cities)
    if f.categories:
        mask &= df["Category"].isin(f.categories)
    out = df[mask]
    # Kullanılmayan kategori düzeylerini at (groupby/grafiklerde boş satır olmasın)
    cat_cols = out.select_dtypes("category").columns
    return out.assign(**{c: out[c].cat.remove_unused_categories() for c in cat_cols})
