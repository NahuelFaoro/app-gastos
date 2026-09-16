from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPalette, QPen
from PySide6.QtWidgets import (
    QAbstractButton, QColorDialog, QDialog, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from ..constants import CATEGORY_COLORS, CATEGORY_ICONS
from ..icons import ICON_LABELS, draw_icon, normalize_icon
from ..widgets import IconChoiceButton
from ..layouts import FlowLayout

class ColorSwatchButton(QAbstractButton):
    def __init__(self, color, selected=False, parent=None):
        super().__init__(parent)
        self.color = QColor(color); self.setCheckable(True); self.setChecked(selected)
        self.setCursor(Qt.CursorShape.PointingHandCursor); self.setFixedSize(58, 42); self.setToolTip(color.upper())

    def paintEvent(self, event):
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            r = self.rect().adjusted(2, 2, -2, -2)
            outer = QColor("#4CCFA9") if self.isChecked() else self.palette().color(QPalette.ColorRole.Midlight)
            if self.underMouse() and not self.isChecked(): outer = self.palette().color(QPalette.ColorRole.Mid)
            p.setPen(QPen(outer, 2 if self.isChecked() else 1)); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(r, 11, 11)
            inner = r.adjusted(5, 5, -5, -5); p.setPen(Qt.PenStyle.NoPen); p.setBrush(self.color); p.drawRoundedRect(inner, 8, 8)
            if self.isChecked():
                p.setPen(QColor("#FFFFFF")); f=p.font(); f.setPointSize(10); f.setBold(True); p.setFont(f)
                p.drawText(inner, Qt.AlignmentFlag.AlignCenter, "✓")
        finally:
            p.end()


class ColorPickerDialog(QDialog):
    def __init__(self, current="#4CCFA9", parent=None):
        super().__init__(parent)
        self.selected = current
        self.setWindowTitle("Elegir color")
        self.setMinimumWidth(500)
        root = QVBoxLayout(self); root.setContentsMargins(24,22,24,22); root.setSpacing(15)
        title = QLabel("Color de la categoría"); title.setObjectName("PageTitle")
        sub = QLabel("Una paleta más corta mantiene la app consistente. Elegí el color que te ayude a reconocerla de un vistazo.")
        sub.setObjectName("PageSubtitle"); sub.setWordWrap(True)
        root.addWidget(title); root.addWidget(sub)

        grid = QGridLayout(); grid.setHorizontalSpacing(10); grid.setVerticalSpacing(10)
        palette = list(dict.fromkeys(CATEGORY_COLORS))
        for i, color in enumerate(palette):
            b = ColorSwatchButton(color, color.lower() == current.lower())
            b.clicked.connect(lambda checked=False, c=color: self._choose(c))
            grid.addWidget(b, i // 5, i % 5)
        root.addLayout(grid)

        custom = QPushButton("Color personalizado…"); custom.setObjectName("SecondaryButton"); custom.clicked.connect(self._custom)
        root.addWidget(custom, 0, Qt.AlignmentFlag.AlignLeft)
        row = QHBoxLayout(); row.addStretch()
        cancel = QPushButton("Cancelar"); cancel.setObjectName("SecondaryButton"); cancel.clicked.connect(self.reject)
        row.addWidget(cancel); root.addLayout(row)

    def _choose(self, color):
        self.selected = color; self.accept()

    def _custom(self):
        color = QColorDialog.getColor(QColor(self.selected), self, "Color personalizado")
        if color.isValid(): self.selected = color.name(); self.accept()


class ColorButton(QPushButton):
    def __init__(self, color="#4CCFA9", parent=None):
        super().__init__(parent)
        self.color = color
        self.clicked.connect(self.choose)
        self._refresh()

    def _refresh(self):
        self.setText(f"●   {self.color.upper()}   ·   Cambiar")
        self.setObjectName("SecondaryButton")
        self.setMinimumHeight(42)
        self.setStyleSheet(
            f"QPushButton{{text-align:left;padding-left:14px;color:{self.color};font-weight:800;}}"
        )

    def choose(self):
        dlg = ColorPickerDialog(self.color, self)
        if dlg.exec():
            self.color = dlg.selected
            self._refresh()


class IconPickerDialog(QDialog):
    def __init__(self, current="other", parent=None):
        super().__init__(parent)
        self.selected = normalize_icon(current)
        self.setWindowTitle("Elegir ícono")
        self.resize(780, 640)
        root = QVBoxLayout(self)
        title = QLabel("Elegí un ícono")
        title.setObjectName("SectionTitle")
        root.addWidget(title)
        subtitle = QLabel("Buscá por función. Los íconos usan el mismo estilo visual en toda la app.")
        subtitle.setObjectName("Muted")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        self.search = QLineEdit(); self.search.setPlaceholderText("Buscar: combustible, casa, seguro, comida…")
        self.search.setClearButtonEnabled(True); self.search.textChanged.connect(self._rebuild)
        root.addWidget(self.search)

        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True); self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        root.addWidget(self.scroll, 1)

        row = QHBoxLayout(); row.addStretch()
        cancel = QPushButton("Cancelar"); cancel.setObjectName("SecondaryButton"); cancel.clicked.connect(self.reject)
        row.addWidget(cancel); root.addLayout(row)
        self._rebuild()

    def _rebuild(self):
        query = self.search.text().strip().lower() if hasattr(self, "search") else ""
        host = QWidget(); grid = FlowLayout(host, horizontal_spacing=8, vertical_spacing=8); grid.setContentsMargins(2,2,8,8)
        icons = [i for i in CATEGORY_ICONS if not query or query in ICON_LABELS.get(i,i).lower() or query in i.lower()]
        for idx, icon in enumerate(icons):
            b = IconChoiceButton(icon, ICON_LABELS.get(icon, icon))
            b.setChecked(icon == self.selected)
            b.clicked.connect(lambda checked=False, x=icon: self._choose(x))
            grid.addWidget(b)
        if not icons:
            empty = QLabel("No encontré íconos con esa búsqueda."); empty.setObjectName("Muted")
            empty.setWordWrap(True); grid.addWidget(empty)
        self.scroll.setWidget(host)

    def _choose(self, icon):
        self.selected = normalize_icon(icon)
        self.accept()


class IconButton(QPushButton):
    def __init__(self, icon="other", parent=None):
        super().__init__(parent)
        self.icon_value = normalize_icon(icon)
        self.setMinimumWidth(150); self.setMinimumHeight(44)
        self.setObjectName("SecondaryButton")
        self.clicked.connect(self.choose)
        self._refresh()

    def _refresh(self):
        self.setText(f"      {ICON_LABELS.get(self.icon_value, 'Otro')}   ·   Cambiar")

    def paintEvent(self, event):
        super().paintEvent(event)
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        draw_icon(p, self.rect().adjusted(12,11,-self.width()+36,-11), self.icon_value, QColor("#4CCFA9"), 1.9)

    def choose(self):
        dlg = IconPickerDialog(self.icon_value, self)
        if dlg.exec():
            self.icon_value = dlg.selected
            self._refresh(); self.update()
