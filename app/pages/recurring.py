from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QBoxLayout, QFrame, QHBoxLayout, QLabel, QMenu, QMessageBox, QPushButton,
    QScrollArea, QVBoxLayout, QWidget
)

from ..dialogs import RecurringDialog
from ..utils import human_date, money
from ..widgets import IconBadge
from ..layouts import responsive_mode
from .common import clear_layout, page_header


FREQ = {"daily": "Diaria", "weekly": "Semanal", "monthly": "Mensual", "yearly": "Anual"}


class RecurringCard(QFrame):
    edit_requested = Signal(int)
    toggle_requested = Signal(int)
    delete_requested = Signal(int)

    def __init__(self, item, fmt, parent=None):
        super().__init__(parent)
        self.item = item
        self.rid = int(item["id"])
        self.setObjectName("RecurringCard" if item["active"] else "RecurringCardPaused")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Doble clic para editar · clic derecho para pausar o eliminar")

        root = QHBoxLayout(self)
        root.setContentsMargins(15, 13, 15, 13)
        root.setSpacing(12)
        root.addWidget(IconBadge(
            item.get("category_effective_icon", "other"),
            item.get("category_effective_color", "#4CCFA9"),
            44,
            secondary_color=item.get("category_secondary_color"),
        ))

        info = QVBoxLayout(); info.setSpacing(3)
        title = QLabel(item.get("description") or item.get("category_display") or "Movimiento recurrente")
        title.setObjectName("RecurringTitle")
        info.addWidget(title)

        freq = FREQ.get(item["frequency"], item["frequency"])
        interval = int(item.get("interval_value") or 1)
        freq_text = freq if interval == 1 else f"{freq} · cada {interval}"
        meta = QLabel(f"{item.get('category_display') or ''}  ·  {item['account_name']}  ·  {freq_text}")
        meta.setObjectName("SmallMuted")
        info.addWidget(meta)
        root.addLayout(info, 1)

        next_box = QVBoxLayout(); next_box.setSpacing(1)
        next_cap = QLabel("PRÓXIMO"); next_cap.setObjectName("TinyCaption")
        next_date = QLabel(human_date(item["next_date"])); next_date.setObjectName("RecurringDate")
        next_box.addWidget(next_cap, 0, Qt.AlignmentFlag.AlignRight)
        next_box.addWidget(next_date, 0, Qt.AlignmentFlag.AlignRight)
        root.addLayout(next_box)

        amount = float(item["amount"])
        shown = amount if item["kind"] == "income" else -amount if item["kind"] == "expense" else amount
        amount_label = QLabel(fmt(shown))
        amount_label.setObjectName(
            "TransactionAmountPositive" if item["kind"] == "income"
            else "TransactionAmountNegative" if item["kind"] == "expense"
            else "TransactionAmount"
        )
        amount_label.setMinimumWidth(115)
        amount_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        root.addWidget(amount_label)

        status = QLabel("Activo" if item["active"] else "Pausado")
        status.setObjectName("RecurringActiveChip" if item["active"] else "RecurringPausedChip")
        root.addWidget(status)

    def mouseDoubleClickEvent(self, event):
        self.edit_requested.emit(self.rid)
        event.accept()

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        edit = menu.addAction("Editar recurrente")
        toggle = menu.addAction("Pausar" if self.item["active"] else "Activar")
        menu.addSeparator()
        delete = menu.addAction("Eliminar recurrente")
        chosen = menu.exec(event.globalPos())
        if chosen == edit:
            self.edit_requested.emit(self.rid)
        elif chosen == toggle:
            self.toggle_requested.emit(self.rid)
        elif chosen == delete:
            self.delete_requested.emit(self.rid)


class RecurringPage(QWidget):
    data_changed = Signal()

    def __init__(self, db):
        super().__init__()
        self.db = db
        self._compact = False
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 28)
        root.setSpacing(14)

        self.top_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        top = self.top_layout
        top.addWidget(page_header(
            "Recurrentes",
            "Suscripciones, servicios e ingresos repetidos · doble clic para editar",
        ))
        top.addStretch()
        process = QPushButton("Generar pendientes")
        process.setObjectName("SecondaryButton")
        process.clicked.connect(self.process_due)
        add = QPushButton("+ Nuevo recurrente")
        add.clicked.connect(self.add_item)
        top.addWidget(process); top.addWidget(add)
        root.addLayout(top)

        self.info = QLabel("Al abrir la app se generan automáticamente los recurrentes cuya fecha ya llegó.")
        self.info.setObjectName("SmallMuted")
        root.addWidget(self.info)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.host = QWidget()
        self.list_layout = QVBoxLayout(self.host)
        self.list_layout.setContentsMargins(0, 0, 8, 0)
        self.list_layout.setSpacing(9)
        self.scroll.setWidget(self.host)
        root.addWidget(self.scroll, 1)

        self.refresh(); self._apply_responsive()

    def _apply_responsive(self):
        compact = responsive_mode(self.width(), self.height()) != "wide"
        if compact == self._compact:
            return
        self._compact = compact
        self.top_layout.setDirection(QBoxLayout.Direction.TopToBottom if compact else QBoxLayout.Direction.LeftToRight)
        margins = 14 if compact else 28
        self.layout().setContentsMargins(margins, 18 if compact else 24, margins, 20 if compact else 28)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_responsive()

    def _fmt(self, value):
        return money(value, self.db.currency_symbol(), self.db.balances_hidden())

    def refresh(self):
        clear_layout(self.list_layout)
        rows = self.db.recurring(True)
        if not rows:
            empty = QFrame(); empty.setObjectName("SoftCard")
            box = QVBoxLayout(empty); box.setContentsMargins(22, 28, 22, 28)
            title = QLabel("No hay movimientos recurrentes"); title.setObjectName("SectionTitle")
            subtitle = QLabel("Podés automatizar alquiler, servicios, suscripciones, sueldo y otros movimientos repetidos.")
            subtitle.setObjectName("Muted"); subtitle.setWordWrap(True)
            box.addWidget(title); box.addWidget(subtitle)
            self.list_layout.addWidget(empty)
        else:
            for item in rows:
                card = RecurringCard(item, self._fmt)
                card.edit_requested.connect(self.edit_item)
                card.toggle_requested.connect(self.toggle_item)
                card.delete_requested.connect(self.delete_item)
                self.list_layout.addWidget(card)
        self.list_layout.addStretch()

    def add_item(self):
        dlg = RecurringDialog(self.db, parent=self)
        if dlg.exec():
            self.db.add_recurring(dlg.data())
            self.refresh(); self.data_changed.emit()

    def edit_item(self, rid=None):
        if not rid:
            return
        dlg = RecurringDialog(self.db, self.db.recurring_item(int(rid)), self)
        if dlg.exec():
            self.db.update_recurring(int(rid), dlg.data())
            self.refresh(); self.data_changed.emit()

    def toggle_item(self, rid=None):
        if not rid:
            return
        self.db.toggle_recurring(int(rid))
        self.refresh(); self.data_changed.emit()

    def delete_item(self, rid=None):
        if not rid:
            return
        if QMessageBox.question(
            self,
            "Eliminar recurrente",
            "¿Eliminar esta regla recurrente? Los movimientos ya generados no se borran.",
        ) == QMessageBox.StandardButton.Yes:
            self.db.delete_recurring(int(rid))
            self.refresh(); self.data_changed.emit()

    def process_due(self):
        n = self.db.process_due_recurring()
        self.info.setText(f"Se generaron {n} movimientos pendientes." if n else "No había recurrentes pendientes.")
        self.refresh(); self.data_changed.emit()
