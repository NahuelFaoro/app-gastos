from __future__ import annotations

"""Helpers mínimos para normalizar el runtime de Qt entre plataformas.

Qt puede devolver una fuente de aplicación definida sólo por pixelSize, dejando
``pointSizeF()`` en ``-1``. Algunas librerías de iconos intentan reutilizar ese
valor como tamaño tipográfico y emiten warnings (o fallan según backend).
Normalizarla una sola vez evita que cada widget tenga que defenderse por su
cuenta.
"""

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication


def normalize_application_font(app: QApplication, fallback_points: float = 10.0) -> QFont:
    """Garantiza que la fuente global tenga un point size positivo.

    No altera una fuente válida del sistema. Sólo aplica el fallback cuando Qt
    informa un tamaño no positivo/indefinido.
    """
    font = QFont(app.font())
    if font.pointSizeF() <= 0:
        font.setPointSizeF(float(fallback_points))
        app.setFont(font)
    return font


__all__ = ["normalize_application_font"]
