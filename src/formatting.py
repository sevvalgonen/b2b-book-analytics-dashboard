"""Türkçe sayı ve para biçimlendirme yardımcıları."""
from __future__ import annotations

import math

from src.config import CURRENCY


def _tr(num_str: str) -> str:
    """1,234.5 → 1.234,5"""
    return num_str.replace(",", "_").replace(".", ",").replace("_", ".")


def number(x: float, decimals: int = 0) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "—"
    return _tr(f"{x:,.{decimals}f}")


def compact(x: float) -> str:
    """Büyük sayıları kısaltır: 2,9 Mn / 619 B."""
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "—"
    ax = abs(x)
    if ax >= 1e9:
        return _tr(f"{x / 1e9:.2f}") + " Mr"
    if ax >= 1e6:
        return _tr(f"{x / 1e6:.2f}") + " Mn"
    if ax >= 1e4:
        return _tr(f"{x / 1e3:.1f}") + " B"
    return number(x, 0 if ax >= 100 else 1)


def money(x: float, full: bool = False) -> str:
    return f"{CURRENCY}{number(x) if full else compact(x)}"


def pct(x: float, decimals: int = 1, signed: bool = False) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "—"
    sign = "-" if x < 0 else ("+" if signed and x > 0 else "")
    return f"{sign}%{_tr(f'{abs(x) * 100:.{decimals}f}')}"
