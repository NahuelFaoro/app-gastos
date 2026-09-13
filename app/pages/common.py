from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QScrollArea, QVBoxLayout, QWidget


_EYEBROWS = {
    "Dashboard": "PANORAMA",
    "Movimientos": "REGISTRO",
    "Calendario": "ACTIVIDAD",
    "Por revisar": "AUTOMATIZACIÓN",
    "Cuentas": "PATRIMONIO",
    "Cuotas": "PLANIFICACIÓN",
    "Análisis": "TENDENCIAS",
    "Categorías": "ORGANIZACIÓN",
    "Recurrentes": "AUTOMATIZACIÓN",
    "Herramientas": "UTILIDADES",
    "Viajes": "TRABAJO",
    "Móvil": "SINCRONIZACIÓN",
    "Ajustes": "PREFERENCIAS",
}


def page_header(title: str, subtitle: str = ""):
    box = QWidget(); box.setObjectName("PageHeaderBox")
    layout = QVBoxLayout(box); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(3)
    eye = QLabel(_EYEBROWS.get(title, "APP GASTOS")); eye.setObjectName("PageEyebrow")
    t = QLabel(title); t.setObjectName("PageTitle")
    layout.addWidget(eye); layout.addWidget(t)
    if subtitle:
        s = QLabel(subtitle); s.setObjectName("PageSubtitle"); s.setWordWrap(True); layout.addWidget(s)
    return box


def scroll_container():
    scroll = QScrollArea(); scroll.setObjectName("PageScroll"); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.Shape.NoFrame)
    content = QWidget(); layout = QVBoxLayout(content); layout.setContentsMargins(34, 28, 34, 34); layout.setSpacing(18); scroll.setWidget(content)
    return scroll, content, layout


def clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0); w = item.widget()
        if w: w.deleteLater()
        elif item.layout(): clear_layout(item.layout())
