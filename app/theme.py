from __future__ import annotations

"""API pública de temas.

La paleta Qt, las primitivas de color y el catálogo QSS están separados para
evitar el antiguo archivo monolítico y los overrides accidentales.
"""

from PySide6.QtGui import QColor, QPalette

from .style_rules import build_stylesheet
from .theme_tokens import _resolve_theme


def build_palette(theme: str = "light") -> QPalette:
    dark, _accent_name, accent = _resolve_theme(theme)
    palette = QPalette()
    if dark:
        colors = {
            "window": "#0D1117", "base": "#151B23", "alt": "#19212B", "text": "#F4F7FA",
            "button": "#171E27", "muted": "#8A96A5", "midlight": "#28323E",
        }
    else:
        colors = {
            "window": "#F3F6F7", "base": "#FFFFFF", "alt": "#F7F9FA", "text": "#17222C",
            "button": "#FFFFFF", "muted": "#778391", "midlight": "#E5EAED",
        }
    palette.setColor(QPalette.ColorRole.Window, QColor(colors["window"]))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(colors["text"]))
    palette.setColor(QPalette.ColorRole.Base, QColor(colors["base"]))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(colors["alt"]))
    palette.setColor(QPalette.ColorRole.Text, QColor(colors["text"]))
    palette.setColor(QPalette.ColorRole.Button, QColor(colors["button"]))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(colors["text"]))
    palette.setColor(QPalette.ColorRole.Mid, QColor(colors["muted"]))
    palette.setColor(QPalette.ColorRole.Midlight, QColor(colors["midlight"]))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(accent))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#071410" if dark else "#FFFFFF"))
    return palette


__all__ = ["build_palette", "build_stylesheet"]
