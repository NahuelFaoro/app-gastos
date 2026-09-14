from __future__ import annotations

"""Vista semanal plegable para trabajos extra.

Comparte el lenguaje visual de Viajes (tarjetas por día, encabezados compactos,
selección reversible) sin mezclar reglas específicas de recorridos.
"""

from collections import defaultdict
from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..utils import money
from ..work_calendar import iter_week_days
from ..layouts import FlowLayout
from .viajes_widgets import DayGroupCard
from .work_cards import FoldableWorkCard


class ExtraCompactCard(FoldableWorkCard):
    """Registro de trabajo extra con detalle plegado inicialmente."""

    def __init__(self, extra: dict, symbol: str, hidden_amounts: bool, parent=None):
        super().__init__(int(extra["id"]), str(extra.get("app_name") or "Extra"),
                         money(extra.get("amount") or 0, symbol, hidden_amounts), parent)
        self.extra_id = self.record_id
        hours = float(extra.get("hours") or 0)
        orders = extra.get("orders")
        for caption, value in (("Horas trabajadas", f"{hours:g} h"),
                               ("Pedidos / viajes", str(orders) if orders is not None else "Sin especificar")):
            row = QHBoxLayout()
            label = QLabel(caption)
            label.setObjectName("SmallMuted")
            row.addWidget(label, 1)
            row.addWidget(QLabel(value))
            self.detail_layout.addLayout(row)
        if extra.get("details"):
            details = QLabel(str(extra["details"]))
            details.setTextFormat(Qt.TextFormat.PlainText)
            details.setWordWrap(True)
            details.setObjectName("SmallMuted")
            self.detail_layout.addWidget(details)


class ExtraDayCard(DayGroupCard):
    """Grilla adaptable compartida con las jornadas de Viajes."""

    extraSelected = Signal(int)
    extraDoubleClicked = Signal(int)

    def set_rows(self, rows: list[dict], symbol: str, hidden_amounts: bool, *, compact: bool = False) -> None:
        while self.compact_layout.count():
            widget = self.compact_layout.takeAt(0).widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()
        self._compact_cards = []
        for extra in rows:
            card = ExtraCompactCard(extra, symbol, hidden_amounts)
            card.clicked.connect(self.extraSelected.emit)
            card.doubleClicked.connect(self.extraDoubleClicked.emit)
            card.expansionChanged.connect(self._arrange_cards)
            self._compact_cards.append(card)
        if not rows:
            empty = QLabel("Sin extras")
            empty.setObjectName("WorkDayEmpty")
            self.compact_layout.addWidget(empty, 0, 0)
        self._arrange_cards()

    def select_extra(self, extra_id: int) -> None:
        for card in self._compact_cards:
            card.set_selected(card.extra_id == int(extra_id))


class ExtrasByDayView(QWidget):
    """Cinco tarjetas de día con el mismo comportamiento que Viajes."""

    extraDoubleClicked = Signal(int)
    selectionChanged = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cards: dict[str, ExtraDayCard] = {}
        self._selected_extra_id: int | None = None
        self._has_populated = False
        self._expanded_records: set[int] = set()
        self._compact = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setObjectName("WorkDaysScroll")
        root.addWidget(self.scroll)

        self.host = QWidget()
        self.host_layout = QVBoxLayout(self.host)
        self.host_layout.setContentsMargins(0, 0, 4, 0)
        self.host_layout.setSpacing(8)
        self.host_layout.addStretch(1)
        self.scroll.setWidget(self.host)

    def set_compact(self, compact: bool) -> None:
        self._compact = bool(compact)

    def populate(self, week_start: date, rows: list[dict], symbol: str, hidden_amounts: bool) -> None:
        expanded_days = {key for key, card in self._cards.items() if card.is_expanded()}
        for day_card in self._cards.values():
            for record in day_card._compact_cards:
                if record.is_expanded():
                    self._expanded_records.add(record.extra_id)
                else:
                    self._expanded_records.discard(record.extra_id)
        self._selected_extra_id = None
        self.selectionChanged.emit(None)

        while self.host_layout.count() > 1:
            item = self.host_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()
        self._cards = {}

        by_date: dict[str, list[dict]] = defaultdict(list)
        for extra in rows:
            by_date[str(extra.get("work_date") or "")].append(extra)

        for day in iter_week_days(week_start):
            day_iso = day.isoformat()
            day_rows = by_date.get(day_iso, [])
            hours = sum(float(row.get("hours") or 0) for row in day_rows)
            orders = sum(int(row.get("orders") or 0) for row in day_rows)
            amount = sum(float(row.get("amount") or 0) for row in day_rows)

            card = ExtraDayCard(day)
            card.header.clicked.connect(self.clear_selection)
            # Reutilizamos el header de Viajes y luego reemplazamos sus chips por
            # las métricas propias de Extras para mantener estética sin mezclar datos.
            card.header.set_summary(day, len(day_rows), orders)
            custom_values = [
                f"{len(day_rows)} registro" if len(day_rows) == 1 else f"{len(day_rows)} registros",
                f"{hours:.2f} h".replace(".00", ""),
            ]
            if orders:
                custom_values.append(f"{orders} pedidos/viajes")
            if amount:
                custom_values.append(money(amount, symbol, hidden_amounts))
            card.header.set_chip_texts(custom_values)

            card.set_rows(day_rows, symbol, hidden_amounts, compact=self._compact)
            for record in card._compact_cards:
                record.set_expanded(record.extra_id in self._expanded_records)
            card.extraSelected.connect(lambda extra_id, source=card: self._select_extra(source, extra_id))
            card.extraDoubleClicked.connect(self.extraDoubleClicked.emit)
            card.set_expanded(day_iso in expanded_days if self._has_populated else False)
            self._cards[day_iso] = card
            self.host_layout.insertWidget(self.host_layout.count() - 1, card)

        self._has_populated = True

    def _select_extra(self, source: ExtraDayCard, extra_id: int) -> None:
        if self._selected_extra_id == extra_id:
            source.clear_selection()
            self._selected_extra_id = None
            self.selectionChanged.emit(None)
            return
        self._selected_extra_id = extra_id
        for card in self._cards.values():
            card.clear_selection()
            if card is source:
                card.select_extra(extra_id)
        self.selectionChanged.emit(extra_id)

    def clear_selection(self) -> None:
        if self._selected_extra_id is None:
            return
        for card in self._cards.values():
            card.clear_selection()
        self._selected_extra_id = None
        self.selectionChanged.emit(None)

    def selected_extra_id(self) -> int | None:
        return self._selected_extra_id

    def day_count(self) -> int:
        """Cantidad de jornadas visibles; útil para pruebas de humo."""
        return len(self._cards)
