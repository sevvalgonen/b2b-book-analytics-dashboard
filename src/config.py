"""Uygulama genelindeki sabitler: dosya yolları, renk paleti, etiketler."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
RAW_XLSX = DATA_DIR / "B2B_Transaction_Data_.xlsx"
RAW_PARQUET = DATA_DIR / "B2B_Transaction_Data.parquet"
GEOJSON = DATA_DIR / "tr-cities.json"

CURRENCY = "₺"

# --- Renk paleti (renk körlüğü testinden geçmiş kategorik sıra) ---------------
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100",
          "#e87ba4", "#008300", "#6250d6", "#e34948"]
SEQUENTIAL = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5",
              "#256abf", "#184f95", "#0d366b"]
DIVERGING = ["#184f95", "#6da7ec", "#f0efec", "#ec8c8c", "#b42f2f"]
STATUS = {"good": "#0ca30c", "warning": "#fab219",
          "serious": "#ec835a", "critical": "#d03b3b"}
INK = {"primary": "#0b0b0b", "secondary": "#52514e", "muted": "#898781",
       "grid": "#e1e0d9", "axis": "#c3c2b7", "surface": "#fcfcfb"}

# --- Etiketler -----------------------------------------------------------------
MONTHS_TR = ["Oca", "Şub", "Mar", "Nis", "May", "Haz",
             "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]
WEEKDAYS_TR = ["Pazartesi", "Salı", "Çarşamba", "Perşembe",
               "Cuma", "Cumartesi", "Pazar"]

# Veri setindeki ASCII-büyük harf il adlarının GeoJSON'daki resmi karşılıkları
CITY_ALIASES = {"IÇEL": "Mersin", "K.MARAS": "Kahramanmaraş", "AFYON": "Afyon"}

UNKNOWN = "Belirtilmemiş"
OTHER = "Diğer"
TOP_CATEGORY_N = 20  # grafiklerde ayrı gösterilecek kategori sayısı
