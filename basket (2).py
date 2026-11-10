"""Pazar sepeti analizi (FP-Growth + birliktelik kuralları) ve basit öneri motoru."""
from __future__ import annotations

import pandas as pd
from mlxtend.frequent_patterns import association_rules, fpgrowth


def basket_matrix(df: pd.DataFrame, level: str = "Category",
                  top_items: int = 150) -> pd.DataFrame:
    """Fatura × öğe ikili matrisi. Ürün düzeyinde en sık `top_items` ürün alınır."""
    col = "Description" if level == "Product" else level
    d = df[["InvoiceNo", col]].drop_duplicates()
    if level == "Product":
        top = d[col].value_counts().head(top_items).index
        d = d[d[col].isin(top)]
    d = d.assign(v=True)
    m = d.pivot_table(index="InvoiceNo", columns=col, values="v",
                      aggfunc="any", fill_value=False, observed=True)
    m = m[m.sum(axis=1) >= 2]  # tek kalemli sepetler kural üretmez
    m.columns = m.columns.astype(str)
    return m.astype(bool)


def mine_rules(basket: pd.DataFrame, min_support: float, min_confidence: float,
               min_lift: float = 1.0, max_len: int = 3) -> pd.DataFrame:
    if basket.empty:
        return pd.DataFrame()
    items = fpgrowth(basket, min_support=min_support, use_colnames=True, max_len=max_len)
    if items.empty or items["itemsets"].map(len).max() < 2:
        return pd.DataFrame()
    rules = association_rules(items, num_itemsets=len(basket),
                              metric="confidence", min_threshold=min_confidence)
    rules = rules[rules["lift"] >= min_lift].copy()
    rules["Öncül"] = rules["antecedents"].map(lambda s: " + ".join(sorted(s)))
    rules["Sonuç"] = rules["consequents"].map(lambda s: " + ".join(sorted(s)))
    out = rules.rename(columns={"support": "Destek", "confidence": "Güven",
                                "lift": "Kaldıraç (Lift)", "conviction": "İkna"})
    return out[["Öncül", "Sonuç", "Destek", "Güven", "Kaldıraç (Lift)", "İkna",
                "antecedents", "consequents"]].sort_values("Kaldıraç (Lift)", ascending=False)


def recommend(rules: pd.DataFrame, item: str, n: int = 10) -> pd.DataFrame:
    """Öncülünde `item` bulunan kurallardan öneri listesi."""
    if rules.empty:
        return rules
    r = rules[rules["antecedents"].map(lambda s: item in s)]
    return (r.sort_values(["Kaldıraç (Lift)", "Güven"], ascending=False)
             .drop_duplicates("Sonuç").head(n)[["Öncül", "Sonuç", "Güven", "Kaldıraç (Lift)", "Destek"]])
