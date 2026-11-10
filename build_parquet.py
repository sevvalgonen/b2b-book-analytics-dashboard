"""Ham Excel dosyasını, hızlı yükleme için Parquet formatına dönüştürür.

Bu betik veriyi TEMİZLEMEZ; yalnızca biçim dönüşümü yapar. Tüm ön işleme
adımları uygulama içinde (src/data.py) şeffaf biçimde uygulanır ve
"Veri Kalitesi" sayfasında raporlanır.

Kullanım:
    python scripts/build_parquet.py
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "B2B_Transaction_Data_.xlsx"
DST = ROOT / "data" / "B2B_Transaction_Data.parquet"

TEXT_COLS = ["InvoiceNo", "CustomerID", "InvoiceDate", "StockCode",
             "Description", "Category", "City"]


def main() -> None:
    df = pd.read_excel(SRC, dtype={"StockCode": str})
    for col in TEXT_COLS:
        # Eksik değerleri koru, geri kalanları metne çevir (karışık tipli hücreler için)
        df[col] = df[col].where(df[col].isna(), df[col].astype(str))
    df.to_parquet(DST, index=False, compression="zstd")
    print(f"{len(df):,} satır yazıldı -> {DST} ({DST.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
