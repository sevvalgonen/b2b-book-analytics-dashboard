# B2B Kitap Dağıtımı · Akıllı Karar Destek Paneli

**ISL 533 Veri Madenciliği – Ödev I** · Python Streamlit ile akıllı gösterge paneli

Bir B2B kitap dağıtımcısının 2020 yılına ait ~664 bin satırlık satış verisinden; **satış**, **pazarlama** ve
**tedarik zinciri** departmanları için KPI'lar, etkileşimli grafikler, makine öğrenmesi tabanlı tahminler ve
otomatik içgörüler üreten bir karar destek sistemi.

🔗 **Canlı panel:** _(Streamlit Cloud bağlantısı)_

---

## Panel yapısı

| Bölüm | Sayfa | İçerik |
|---|---|---|
| **Yönetici Özeti** | Genel Bakış | 6 KPI kartı, aylık ciro, kategori ve il dağılımı, Türkiye haritası, öne çıkan içgörüler |
| | İçgörüler ve Öneriler | Tüm modüllerden otomatik üretilen, departmanlara göre gruplanmış bulgular + karar önerileri |
| **Satış** | Satış Performansı | Günlük/haftalık/aylık trend + hareketli ortalama, ay×gün ısı haritası, kategori ağaç haritası, ürün Pareto (80/20), müşteri yoğunlaşması, iskonto analizi |
| | Bölgesel Analiz | İl haritası (ciro/sipariş/müşteri/adet), il tablosu, il detayında kategori endeksi |
| **Pazarlama** | Müşteri Segmentasyonu | RFM skorlaması (10 segment + aksiyon önerisi), K-Means (siluet analizi, 3B ve PCA görünüm), müşteri kartı |
| | Müşteri Kaybı Tahmini | Zaman bazlı churn modeli (Lojistik Regresyon vs Random Forest, 5-katlı CV), öznitelik önemi, aksiyon listesi |
| | Sepet Analizi | FP-Growth + birliktelik kuralları (kategori/ürün düzeyi), çapraz satış öneri motoru |
| **Tedarik Zinciri** | Envanter Analizi | ABC-XYZ matrisi ve politika önerileri, emniyet stoğu / ROP / EOK senaryo hesaplayıcı, talep momentumu, depo iş yükü, hareketsiz ürünler |
| | Talep Tahmini | Mevsimsel Naif vs Holt-Winters vs Gradient Boosting backtest karşılaştırması, %95 aralıklı ileri tahmin |
| **Veri** | Veri Kalitesi ve Ön İşleme | Ham veri profili, temizleme hunisi, düzeltme adımları, aykırı değer analizi, veri sözlüğü |
| | Veri Gezgini | Filtrelenmiş veride arama, gruplama ve CSV indirme |

Kenar çubuğundaki **dönem, belge serisi, müşteri grubu, şehir ve kategori** filtreleri tüm sayfalara uygulanır
(ör. yalnızca "Çocuk Öykü/Hikaye" seçilerek kategori bazında talep tahmini yapılabilir).

## Veri ön işleme

Tüm adımlar `src/data.py` içinde uygulanır ve panelde raporlanır:

1. Tarih dönüşümü (metin → datetime)
2. Eksik miktarlı satırların silinmesi (6)
3. Miktarı 0 olan düzeltme/iade kayıtlarının silinmesi (5)
4. Bedelsiz/sembolik fiyatlı (0,0001 ₺) promosyon satırlarının silinmesi (10)
5. Tam kopya satırların silinmesi (6.213) — kenar çubuğundan açılıp kapatılabilir
6. Eksik kategori/şehir → "Belirtilmemiş"; il adlarının resmi yazıma standardizasyonu (IÇEL → Mersin vb.)
7. Öznitelik türetme: ciro, brüt ciro, iskonto tutarı/oranı, belge serisi, müşteri grubu, ay/hafta/gün
8. Aykırı değer işaretleme (toplu sipariş; B2B'de gerçek talep olduğu için silinmez)
9. Bellek optimizasyonu (category veri tipi)

## Proje dizini

```
├── streamlit_app.py          # Giriş noktası: sayfa yapısı, kenar çubuğu filtreleri, navigasyon
├── requirements.txt
├── data/
│   ├── B2B_Transaction_Data_.xlsx     # Orijinal veri seti
│   ├── B2B_Transaction_Data.parquet   # Hızlı yükleme için aynı verinin Parquet kopyası
│   └── tr-cities.json                 # Türkiye il sınırları (GeoJSON)
├── scripts/build_parquet.py  # Excel → Parquet dönüştürücü (temizleme yapmaz)
├── src/
│   ├── config.py             # Sabitler, renk paleti
│   ├── data.py               # Yükleme, ön işleme, filtreleme
│   ├── kpis.py               # Satış KPI ve tanımlayıcı analizler
│   ├── customers.py          # RFM, K-Means, churn modeli
│   ├── supply.py             # ABC-XYZ, stok politikası, talep sinyalleri
│   ├── forecasting.py        # Zaman serisi tahmin modelleri
│   ├── basket.py             # FP-Growth, birliktelik kuralları, öneri
│   ├── insights.py           # Kural tabanlı içgörü üretimi
│   ├── state.py              # Streamlit önbellek katmanı
│   ├── charts.py, ui.py, formatting.py   # Görsel tema ve arayüz bileşenleri
│   └── views/                # Her panel sayfası ayrı modül
└── .streamlit/config.toml    # Tema
```

Analitik modüller (`src/*.py`) Streamlit'ten bağımsız saf pandas/scikit-learn fonksiyonlarıdır; önbellekleme
yalnızca `src/state.py` katmanında yapılır.

## Yerelde çalıştırma

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Kullanılan yöntemler

- **RFM**: Recency/Frequency/Monetary beşli skorlar, R-F matrisine göre 10 segment
- **K-Means**: log + standartlaştırılmış RFM, siluet skoru ile k seçimi, PCA ile 2B izdüşüm
- **Churn**: kesim tarihi öncesi 10 öznitelik, kesim sonrası ufukta alım olmaması = kayıp; LR ve RF karşılaştırması (ROC-AUC ≈ 0,92)
- **Sepet analizi**: FP-Growth (mlxtend), destek/güven/lift
- **ABC-XYZ**: kümülatif ciro payı + haftalık talep değişkenlik katsayısı
- **Stok politikası**: SS = z·σ·√LT, ROP = μ·LT + SS, EOK = √(2DS/H)
- **Tahmin**: Mevsimsel Naif, Holt-Winters (sönümlü trend, 7 günlük mevsimsellik), Gradient Boosting (takvim + gecikme öznitelikleri, özyinelemeli)
