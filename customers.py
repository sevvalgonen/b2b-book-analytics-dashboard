"""Müşteri analitiği: RFM, K-Means segmentasyonu ve müşteri kaybı (churn) tahmini."""
from __future__ import annotations

import re

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, precision_recall_fscore_support
from sklearn.metrics import silhouette_score
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

# RFM skor çiftine (R, F) göre klasik segment haritası
SEGMENT_MAP = {
    r"[1-2][1-2]": "Uykuda",
    r"[1-2][3-4]": "Risk Altında",
    r"[1-2]5": "Kaybedilmemeli",
    r"3[1-2]": "Uyumak Üzere",
    r"33": "İlgi Bekleyen",
    r"[3-4][4-5]": "Sadık",
    r"41": "Umut Vaat Eden",
    r"51": "Yeni",
    r"[4-5][2-3]": "Potansiyel Sadık",
    r"5[4-5]": "Şampiyon",
}
SEGMENT_ACTIONS = {
    "Şampiyon": "Ödüllendir; yeni çıkan kitaplar için erken erişim ve özel kontenjan sun.",
    "Sadık": "Çapraz satış: sık aldıkları kategorilere komşu kategorileri öner.",
    "Potansiyel Sadık": "Sadakat programına dahil et, hacim bazlı kademeli iskonto öner.",
    "Yeni": "Karşılama kampanyası; ikinci siparişi teşvik eden sepet iskontosu.",
    "Umut Vaat Eden": "Katalog ve kampanya bildirimleriyle sipariş sıklığını artır.",
    "İlgi Bekleyen": "Sınırlı süreli teklif ile yeniden etkileşim sağla.",
    "Uyumak Üzere": "Satış temsilcisi araması; ihtiyaç ve stok durumunu sor.",
    "Risk Altında": "Öncelikli geri kazanım: kişisel teklif ve temsilci ziyareti.",
    "Kaybedilmemeli": "Yüksek değerli ama uzaklaşıyor — yönetici düzeyinde temas kur.",
    "Uykuda": "Düşük maliyetli toplu kampanya; yanıt yoksa önceliği düşür.",
}


def segment_of(rf_key: str) -> str:
    """'R' ve 'F' skorlarından oluşan iki haneli anahtarı segment adına çevirir."""
    for pattern, name in SEGMENT_MAP.items():
        if re.fullmatch(pattern, rf_key):
            return name
    return "Diğer"


def _score(s: pd.Series, ascending: bool = True) -> pd.Series:
    """1-5 arası beşli skor (bağları kırmak için sıralama kullanılır)."""
    ranks = s.rank(method="first", ascending=ascending)
    return pd.qcut(ranks, 5, labels=[1, 2, 3, 4, 5]).astype(int)


def rfm_table(df: pd.DataFrame, ref_date: pd.Timestamp | None = None) -> pd.DataFrame:
    ref = (ref_date or df["InvoiceDate"].max()) + pd.Timedelta(days=1)
    g = (df.groupby("CustomerID", observed=True)
           .agg(Son=("InvoiceDate", "max"), İlk=("InvoiceDate", "min"),
                Frequency=("InvoiceNo", "nunique"), Monetary=("Revenue", "sum"),
                Şehir=("City", "first"), Kategori=("Category", "nunique")))
    g["Recency"] = (ref - g["Son"]).dt.days
    g = g[g["Monetary"] > 0]
    if len(g) < 5:
        return g.assign(R=np.nan, F=np.nan, M=np.nan, Segment="—")
    g["R"] = _score(g["Recency"], ascending=False)
    g["F"] = _score(g["Frequency"])
    g["M"] = _score(g["Monetary"])
    g["RFM"] = g["R"].astype(str) + g["F"].astype(str) + g["M"].astype(str)
    key = g["R"].astype(str) + g["F"].astype(str)
    g["Segment"] = key.map(segment_of)
    return g.reset_index()


def segment_summary(rfm: pd.DataFrame) -> pd.DataFrame:
    s = (rfm.groupby("Segment")
            .agg(Müşteri=("CustomerID", "count"), Ciro=("Monetary", "sum"),
                 OrtRecency=("Recency", "mean"), OrtFrekans=("Frequency", "mean"),
                 OrtCiro=("Monetary", "mean"))
            .sort_values("Ciro", ascending=False))
    s["Ciro Payı %"] = s["Ciro"] / s["Ciro"].sum()
    s["Müşteri Payı %"] = s["Müşteri"] / s["Müşteri"].sum()
    s["Önerilen aksiyon"] = s.index.map(SEGMENT_ACTIONS).fillna("")
    return s.reset_index()


# ---------------------------------------------------------------------------
# K-Means
# ---------------------------------------------------------------------------
def _rfm_matrix(rfm: pd.DataFrame) -> np.ndarray:
    X = np.log1p(rfm[["Recency", "Frequency", "Monetary"]].to_numpy(dtype=float))
    return StandardScaler().fit_transform(X)


def silhouette_by_k(rfm: pd.DataFrame, ks=range(2, 9)) -> pd.DataFrame:
    X = _rfm_matrix(rfm)
    rows = []
    for k in ks:
        if k >= len(X):
            break
        km = KMeans(n_clusters=k, n_init=10, random_state=42).fit(X)
        rows.append({"k": k, "Siluet": silhouette_score(X, km.labels_),
                     "Inertia": km.inertia_})
    return pd.DataFrame(rows)


def kmeans_segments(rfm: pd.DataFrame, k: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """K-Means kümeleri + 2 boyutlu PCA izdüşümü ve küme profilleri."""
    X = _rfm_matrix(rfm)
    km = KMeans(n_clusters=k, n_init=10, random_state=42).fit(X)
    pcs = PCA(n_components=2, random_state=42).fit_transform(X)
    out = rfm.copy()
    out["PC1"], out["PC2"] = pcs[:, 0], pcs[:, 1]

    # Kümeleri ortalama ciroya göre sırala ve anlamlı isim ver
    prof = (out.assign(_c=km.labels_)
               .groupby("_c")[["Recency", "Frequency", "Monetary"]].mean()
               .sort_values("Monetary", ascending=False))
    names = ["Değerli", "Gelişen", "Ara", "Düşük Değer", "Pasif", "K6", "K7", "K8"]
    rename = {c: f"K{i + 1} · {names[i]}" for i, c in enumerate(prof.index)}
    out["Küme"] = pd.Series(km.labels_, index=out.index).map(rename)
    profile = (out.groupby("Küme")
                  .agg(Müşteri=("CustomerID", "count"), OrtRecency=("Recency", "mean"),
                       OrtFrekans=("Frequency", "mean"), OrtCiro=("Monetary", "mean"),
                       ToplamCiro=("Monetary", "sum"))
                  .sort_values("OrtCiro", ascending=False))
    profile["Ciro Payı %"] = profile["ToplamCiro"] / profile["ToplamCiro"].sum()
    return out, profile.reset_index()


# ---------------------------------------------------------------------------
# Müşteri kaybı (churn) tahmini
# ---------------------------------------------------------------------------
FEATURE_LABELS = {
    "recency": "Son alımdan bu yana gün",
    "frequency": "Sipariş sayısı",
    "monetary": "Toplam ciro",
    "tenure": "Müşteri yaşı (gün)",
    "aov": "Ortalama sipariş tutarı",
    "n_categories": "Farklı kategori sayısı",
    "avg_discount": "Ortalama iskonto",
    "mean_gap": "Ortalama sipariş aralığı",
    "recent_share": "Son 60 günün ciro payı",
    "active_months": "Aktif ay sayısı",
}


def customer_features(df: pd.DataFrame, ref: pd.Timestamp) -> pd.DataFrame:
    """Referans tarihine kadar olan işlemlerden müşteri düzeyinde öznitelikler."""
    d = df[df["InvoiceDate"] <= ref]
    inv = (d.groupby(["CustomerID", "InvoiceNo"], observed=True)
             .agg(date=("InvoiceDate", "first"), rev=("Revenue", "sum")).reset_index())
    inv = inv.sort_values(["CustomerID", "date"])
    inv["gap"] = inv.groupby("CustomerID", observed=True)["date"].diff().dt.days
    recent_cut = ref - pd.Timedelta(days=60)

    f = inv.groupby("CustomerID", observed=True).agg(
        last=("date", "max"), first=("date", "min"), frequency=("InvoiceNo", "nunique"),
        monetary=("rev", "sum"), mean_gap=("gap", "mean"))
    f["recency"] = (ref - f["last"]).dt.days
    f["tenure"] = (ref - f["first"]).dt.days
    f["aov"] = f["monetary"] / f["frequency"]
    recent = inv[inv["date"] > recent_cut].groupby("CustomerID", observed=True)["rev"].sum()
    f["recent_share"] = (recent.reindex(f.index).fillna(0) / f["monetary"]).clip(0, 1)
    line = d.groupby("CustomerID", observed=True).agg(
        n_categories=("Category", "nunique"), avg_discount=("DiscountRate", "mean"),
        active_months=("Month", "nunique"))
    f = f.join(line)
    f["mean_gap"] = f["mean_gap"].fillna(f["tenure"].clip(lower=1))
    return f.drop(columns=["last", "first"])


def churn_model(df: pd.DataFrame, horizon: int = 60, inactivity: int | None = None) -> dict:
    """Zaman bazlı churn modeli.

    Gözlem penceresi: kesim tarihinden önceki tüm işlemler.
    Etiket: müşteri kesim tarihinden sonraki `horizon` gün içinde hiç alım yapmadıysa 1.
    Eğitilen model, tüm veriyle hesaplanan güncel özniteliklere uygulanarak
    önümüzdeki `horizon` gün için kayıp olasılığı üretilir.
    """
    end = df["InvoiceDate"].max()
    cutoff = end - pd.Timedelta(days=horizon)
    if (cutoff - df["InvoiceDate"].min()).days < 90:
        return {"error": "Churn modeli için en az ~5 aylık veri gerekir; tarih aralığını genişletin."}

    X = customer_features(df, cutoff)
    after = df[df["InvoiceDate"] > cutoff]["CustomerID"].unique()
    y = (~X.index.isin(after)).astype(int)
    if y.sum() < 10 or (1 - y).sum() < 10:
        return {"error": "Seçili filtrelerde iki sınıf için yeterli müşteri yok."}

    feats = list(FEATURE_LABELS)
    models = {
        "Lojistik Regresyon": make_pipeline(
            StandardScaler(), LogisticRegression(max_iter=2000, class_weight="balanced")),
        "Random Forest": RandomForestClassifier(
            n_estimators=300, min_samples_leaf=5, class_weight="balanced",
            random_state=42, n_jobs=-1),
    }
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    Xtr, Xte, ytr, yte = train_test_split(X[feats], y, test_size=0.25,
                                          stratify=y, random_state=42)
    scores = []
    for name, m in models.items():
        cv_auc = cross_val_score(m, X[feats], y, cv=cv, scoring="roc_auc")
        m.fit(Xtr, ytr)
        p = m.predict_proba(Xte)[:, 1]
        pr, rc, f1, _ = precision_recall_fscore_support(
            yte, (p >= 0.5).astype(int), average="binary", zero_division=0)
        scores.append({"Model": name, "CV ROC-AUC": cv_auc.mean(), "± std": cv_auc.std(),
                       "Test ROC-AUC": roc_auc_score(yte, p),
                       "Kesinlik": pr, "Duyarlılık": rc, "F1": f1})
    scores = pd.DataFrame(scores).sort_values("Test ROC-AUC", ascending=False)
    best_name = scores.iloc[0]["Model"]
    best = models[best_name].fit(X[feats], y)  # tüm eğitim kümesiyle yeniden eğit

    if best_name == "Random Forest":
        imp = best.feature_importances_
    else:
        imp = np.abs(best[-1].coef_[0])
    importance = (pd.DataFrame({"Öznitelik": [FEATURE_LABELS[f] for f in feats],
                                "Önem": imp / imp.sum()})
                    .sort_values("Önem"))

    current = customer_features(df, end)
    current["Kayıp Olasılığı"] = best.predict_proba(current[feats])[:, 1]
    current = current.reset_index()
    return {"scores": scores, "best": best_name, "importance": importance,
            "scored": current, "cutoff": cutoff, "churn_rate": y.mean(),
            "n_train": len(y)}


def risk_band(p: float) -> str:
    if p >= 0.7:
        return "Yüksek"
    if p >= 0.4:
        return "Orta"
    return "Düşük"
