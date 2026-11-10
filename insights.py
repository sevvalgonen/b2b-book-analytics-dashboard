"""Kural tabanlı otomatik içgörü üretimi.

Filtrelenmiş veriden hesaplanan metriklerle her departman için okunabilir,
eyleme dönük cümleler üretir. Eşikler bilinçli olarak basit tutulmuştur.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src import config as C
from src import kpis
from src.formatting import money, number, pct


@dataclass
class Insight:
    department: str   # Satış / Pazarlama / Tedarik Zinciri / Yönetim
    level: str        # good / warning / critical / info
    title: str
    text: str


def sales_insights(df: pd.DataFrame) -> list[Insight]:
    out: list[Insight] = []
    m = kpis.monthly_trend(df)
    if len(m) >= 2:
        best, worst = m.loc[m["Ciro"].idxmax()], m.loc[m["Ciro"].idxmin()]
        out.append(Insight("Satış", "info", "Zirve ve dip ay",
                           f"En yüksek ciro {best['Ay']} ({money(best['Ciro'])}), en düşük "
                           f"{worst['Ay']} ({money(worst['Ciro'])}). Fark "
                           f"{number(best['Ciro'] / max(worst['Ciro'], 1), 1)} kat."))
        last = m.iloc[-1]
        if pd.notna(last["Aylık Değişim %"]):
            lvl = "good" if last["Aylık Değişim %"] >= 0 else "warning"
            out.append(Insight("Satış", lvl, "Son ay momentumu",
                               f"{last['Ay']} cirosu bir önceki aya göre "
                               f"{pct(last['Aylık Değişim %'], signed=True)} değişti."))
    if df["InvoiceDate"].dt.month.isin([4, 5, 6, 7]).any() and len(m) >= 8:
        spring = m[m["Tarih"].dt.month.isin([4, 5, 6, 7])]["Ciro"].mean()
        rest = m[~m["Tarih"].dt.month.isin([4, 5, 6, 7])]["Ciro"].mean()
        if rest and spring < rest * 0.85:
            out.append(Insight("Yönetim", "warning", "Nisan–Temmuz daralması",
                               f"Nisan–Temmuz aylık ortalama cirosu diğer aylardan "
                               f"{pct(1 - spring / rest)} düşük. Pandemi kapanma dönemiyle "
                               "örtüşüyor; 2021 bütçesinde baz etkisi dikkate alınmalı."))
    top20 = kpis.share_of_top(df, "CustomerID", 0.2)
    out.append(Insight("Satış", "warning" if top20 > 0.8 else "info", "Müşteri yoğunlaşması",
                       f"Müşterilerin en büyük %20'si cironun {pct(top20)}'ini oluşturuyor."
                       + (" Yüksek bağımlılık riski: kilit hesaplar için temsilci ataması önerilir."
                          if top20 > 0.8 else "")))
    city = kpis.by_dimension(df, "City", 3)
    if not city.empty:
        c0 = city.iloc[0]
        out.append(Insight("Satış", "info", "Bölgesel dağılım",
                           f"{c0['City']} cironun {pct(c0['Pay %'])}'ini üretiyor. "
                           "İlk 3 il toplamı " + pct(city['Pay %'].sum()) + "."))
    return out


def marketing_insights(segments: pd.DataFrame, churn: dict | None) -> list[Insight]:
    out: list[Insight] = []
    if not segments.empty:
        champ = segments[segments["Segment"] == "Şampiyon"]
        if not champ.empty:
            r = champ.iloc[0]
            out.append(Insight("Pazarlama", "good", "Şampiyon müşteriler",
                               f"{int(r['Müşteri'])} müşteri (%{r['Müşteri Payı %'] * 100:.0f}) "
                               f"cironun {pct(r['Ciro Payı %'])}'ini getiriyor."))
        risk = segments[segments["Segment"].isin(["Risk Altında", "Kaybedilmemeli"])]
        if not risk.empty:
            out.append(Insight("Pazarlama", "critical", "Uzaklaşan değerli müşteriler",
                               f"'Risk Altında' ve 'Kaybedilmemeli' segmentlerinde "
                               f"{int(risk['Müşteri'].sum())} müşteri ve "
                               f"{money(risk['Ciro'].sum())} geçmiş ciro var. "
                               "Geri kazanım kampanyası önceliklendirilmeli."))
    if churn and "scored" in churn:
        s = churn["scored"]
        high = s[s["Kayıp Olasılığı"] >= 0.7]
        out.append(Insight("Pazarlama", "critical" if len(high) else "good",
                           "Kayıp riski yüksek müşteriler",
                           f"{churn['best']} modeline göre {len(high)} müşterinin önümüzdeki "
                           f"dönemde alım yapmama olasılığı ≥ %70; bu müşterilerin yıllık "
                           f"cirosu {money(high['monetary'].sum())}."))
    return out


def supply_insights(df: pd.DataFrame, prod: pd.DataFrame, momentum: pd.DataFrame,
                    workload: pd.DataFrame) -> list[Insight]:
    out: list[Insight] = []
    if not prod.empty:
        a = prod[prod["ABC"] == "A"]
        out.append(Insight("Tedarik Zinciri", "info", "Ürün yoğunlaşması (ABC)",
                           f"{len(prod):,} ürünün yalnızca {len(a):,}'i "
                           f"(%{len(a) / len(prod) * 100:.1f}) cironun %80'ini oluşturuyor. "
                           "Stok ve raf önceliği bu A ürünlerine verilmeli.".replace(",", ".")))
        z_share = (prod["XYZ"] == "Z").mean()
        if z_share > 0.5:
            out.append(Insight("Tedarik Zinciri", "warning", "Kesintili talep",
                               f"Ürünlerin {pct(z_share)}'i Z sınıfında (haftalık talep CV > 1). "
                               "Kitap talebi düzensiz: nokta tahmin yerine emniyet stoğu ve "
                               "kategori düzeyinde planlama daha güvenilir."))
    if not workload.empty:
        mon = workload.loc[workload["Weekday"] == 0, "Pay %"]
        if len(mon) and mon.iloc[0] > 0.22:
            out.append(Insight("Tedarik Zinciri", "warning", "Pazartesi yükü",
                               f"Sipariş satırlarının {pct(mon.iloc[0])}'i Pazartesi geliyor "
                               "(diğer iş günlerinin ~1,5 katı). Pazartesi depo vardiyası "
                               "güçlendirilmeli veya hafta sonu siparişleri Cuma'ya yönlendirilmeli."))
    if not momentum.empty:
        up = momentum[momentum["Kategori"] != C.OTHER].tail(2)
        down = momentum[momentum["Kategori"] != C.OTHER].head(2)
        out.append(Insight("Tedarik Zinciri", "info", "Talebi değişen kategoriler",
                           "Son 4 haftada artan: " +
                           ", ".join(f"{k} ({pct(v, signed=True)})"
                                     for k, v in zip(up["Kategori"], up["Değişim %"]))
                           + ". Azalan: " +
                           ", ".join(f"{k} ({pct(v, signed=True)})"
                                     for k, v in zip(down["Kategori"], down["Değişim %"]))
                           + "."))
    return out


def forecast_insight(fc: dict | None) -> list[Insight]:
    if not fc or "forecast" not in fc:
        return []
    f = fc["forecast"]
    total = f["Tahmin"].sum()
    wape = fc["scores"].iloc[0]["WAPE %"]
    return [Insight("Yönetim", "info", "Ciro tahmini",
                    f"{fc['best']} modeli önümüzdeki {len(f)} gün için yaklaşık "
                    f"{money(total)} ciro öngörüyor (geriye dönük test hatası WAPE "
                    f"{pct(wape)}).")]
