from __future__ import annotations

"""Primitivas cromáticas compartidas por paleta y stylesheet."""

import re

from PySide6.QtGui import QColor

from .constants import ACCENT


THEME_ACCENTS = {
    "mint": "#4CCFA9",
    "ocean": "#45B6D9",
    "violet": "#7A78E8",
    "sunset": "#E79A55",
}


def _resolve_theme(theme: str | None):
    raw = (theme or "dark_mint").strip().lower()
    aliases = {"dark": "dark_mint", "light": "light_mint"}
    raw = aliases.get(raw, raw)
    mode, _, accent_name = raw.partition("_")
    if mode not in {"light", "dark"}:
        mode = "dark" if "dark" in raw else "light"
    if accent_name not in THEME_ACCENTS:
        accent_name = "mint"
    dark = mode == "dark"
    return dark, accent_name, THEME_ACCENTS.get(accent_name, ACCENT)


def _blend(color_a: str, color_b: str, t: float) -> str:
    a = QColor(color_a)
    b = QColor(color_b)
    t = max(0.0, min(1.0, float(t)))
    r = round(a.red() * (1 - t) + b.red() * t)
    g = round(a.green() * (1 - t) + b.green() * t)
    bl = round(a.blue() * (1 - t) + b.blue() * t)
    return QColor(r, g, bl).name()


def _rgba(color: str, alpha: float) -> str:
    c = QColor(color)
    a = max(0, min(255, int(round(alpha * 255))))
    return f"rgba({c.red()}, {c.green()}, {c.blue()}, {a})"


def _scale_qss_pixels(qss: str, scale: float = 1.0) -> str:
    """Escala valores ``px`` del stylesheet para el zoom en caliente."""
    try:
        scale = float(scale)
    except (TypeError, ValueError):
        scale = 1.0
    scale = max(0.8, min(2.0, scale))
    if abs(scale - 1.0) < 0.001:
        return qss

    def repl(match: re.Match[str]) -> str:
        value = float(match.group(1))
        scaled = max(1, round(value * scale))
        return f"{scaled}px"

    return re.sub(r"(-?\d+(?:\.\d+)?)px", repl, qss)
