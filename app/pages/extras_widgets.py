from __future__ import annotations

"""Vista semanal plegable para trabajos extra.

Comparte el lenguaje visual de Viajes (tarjetas por día, encabezados compactos,
selección reversible) sin mezclar reglas específicas de recorridos.
"""

from collections import defaultdict
from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..utils import money
from ..work_calendar import iter_week_days
from ..layouts import FlowLayout
from .viajes_widgets import DayGroupHeader


class ExtraCompactCard(QFrame):
    """Fila vertical de Extras para monitores angostos."""

    clicked = Signal(int)
    doubleClicked = Signal(int)

    def __init__(self, extra: dict, symbol: str, hidden_amounts: bool, parent=None):
        super().__init__(parent)
        self.extra_id = int(extra["id"])
        self.setObjectName("WorkTripCompactCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setProperty("selected", False)
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(6)

        top = QHBoxLayout()
        name = QLabel(str(extra.get("app_name") or "Extra"))
        name.setObjectName("TransactionTitle")
        amount = QLabel(money(extra.get("amount") or 0, symbol, hidden_amounts))
        amount.setObjectName("TransactionAmount")
        top.addWidget(name, 1)
        top.addWidget(amount)
        root.addLayout(top)

        chips_host = QWidget()
        chips = FlowLayout(chips_host, horizontal_spacing=6, vertical_spacing=5)
        hours = float(extra.get("hours") or 0)
        orders = int(extra.get("orders") or 0)
        for value in [
            (f"{hours:g} h" if hours else ""),
            (f"{orders} pedidos/viajes" if orders else ""),
        ]:
            if value:
                chip = QLabel(value)
                chip.setObjectName("WorkDayChip")
                chips.addWidget(chip)
        root.addWidget(chips_host)
        if extra.get("details"):
            details = QLabel(str(extra["details"]))
            details.setObjectName("SmallMuted")
            details.setWordWrap(True)
            root.addWidget(details)

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", bool(selected))
        self.style().unpolish(self)
        self.style().polish(self)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.extra_id)
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.doubleClicked.emit(self.extra_id)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


class ExtraDayCard(QFrame):
    """Jornada plegable de Extras."""

    extraSelected = Signal(int)
    extraDoubleClicked = Signal(int)

    COLUMNS = ("Aplicación", "Horas", "Pedidos / viajes", "Ganado", "Detalles")

    def __init__(self, day: date, parent=None):
        super().__init__(parent)
        self.day = day
        self.setObjectName("WorkDayCard")
        self._expanded = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.header = DayGroupHeader()
        self.header.clicked.connect(self.toggle)
        root.addWidget(self.header)

        self.body = QWidget()
        body_layout = QVBoxLayout(self.body)
        body_layout.setContentsMargins(10, 0, 10, 10)
        body_layout.setSpacing(0)

        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setObjectName("WorkDayTable")
        self.table.setHorizontalHeaderLabels(list(self.COLUMNS))
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(False)
        self.table.setShowGrid(False)
        self.table.cellClicked.connect(self._selected)
        self.table.cellDoubleClicked.connect(self._double_clicked)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setStretchLastSection(False)
        for column in range(len(self.COLUMNS)):
            item = self.table.horizontalHeaderItem(column)
            if item is None:
                continue
            if column in (1, 2):
                alignment = Qt.AlignmentFlag.AlignCenter
            elif column == 3:
                alignment = Qt.AlignmentFlag.AlignRight
            else:
                alignment = Qt.AlignmentFlag.AlignLeft
            item.setTextAlignment(alignment | Qt.AlignmentFlag.AlignVCenter)

        self.compact_host = QWidget()
        self.compact_layout = QVBoxLayout(self.compact_host)
        self.compact_layout.setContentsMargins(0, 4, 0, 0)
        self.compact_layout.setSpacing(7)
        self.compact_host.setVisible(False)
        body_layout.addWidget(self.compact_host)
        self._compact_cards: list[ExtraCompactCard] = []

        self.empty = QLabel("Sin extras")
        self.empty.setObjectName("WorkDayEmpty")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setMinimumHeight(48)

        body_layout.addWidget(self.table)
        body_layout.addWidget(self.empty)
        root.addWidget(self.body)
        self.body.setVisible(False)

    def set_expanded(self, expanded: bool) -> None:
        self._expanded = bool(expanded)
        self.body.setVisible(self._expanded)
        self.header.set_expanded(self._expanded)

    def toggle(self) -> None:
        self.set_expanded(not self._expanded)

    def is_expanded(self) -> bool:
        return self._expanded

    def set_rows(self, rows: list[dict], symbol: str, hidden_amounts: bool, *, compact: bool = False) -> None:
        self.table.setRowCount(len(rows))
        self.empty.setVisible(not rows)
        self.table.setVisible(bool(rows) and not compact)
        self.compact_host.setVisible(bool(rows) and compact)
        while self.compact_layout.count():
            item = self.compact_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._compact_cards = []

        for row_index, extra in enumerate(rows):
            hours = float(extra.get("hours") or 0)
            orders = int(extra.get("orders") or 0)
            values = [
                extra.get("app_name") or "—",
                (f"{hours:.2f}".rstrip("0").rstrip(".") + " h") if hours else "—",
                str(orders) if orders else "—",
                money(extra.get("amount") or 0, symbol, hidden_amounts),
                extra.get("details") or "—",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, int(extra["id"]))
                if column in (1, 2):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                elif column == 3:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row_index, column, item)
            card = ExtraCompactCard(extra, symbol, hidden_amounts)
            card.clicked.connect(self.extraSelected.emit)
            card.doubleClicked.connect(self.extraDoubleClicked.emit)
            self.compact_layout.addWidget(card)
            self._compact_cards.append(card)

        self.table.resizeRowsToContents()
        if rows and not compact:
            desired = self.table.horizontalHeader().height() + sum(
                self.table.rowHeight(row) for row in range(self.table.rowCount())
            ) + 8
            height = min(360, max(92, desired))
            self.table.setMinimumHeight(height)
            self.table.setMaximumHeight(height)
        elif compact:
            self.table.setMinimumHeight(0)
            self.table.setMaximumHeight(0)

    def clear_selection(self) -> None:
        self.table.clearSelection()
        self.table.setCurrentCell(-1, -1)
        for card in self._compact_cards:
            card.set_selected(False)

    def select_extra(self, extra_id: int) -> None:
        for card in self._compact_cards:
            card.set_selected(card.extra_id == int(extra_id))

    def _extra_id_for_row(self, row: int) -> int | None:
        item = self.table.item(row, 0)
        if item is None:
            return None
        try:
            return int(item.data(Qt.ItemDataRole.UserRole))
        except (TypeError, ValueError):
            return None

    def _selected(self, row: int, _column: int) -> None:
        extra_id = self._extra_id_for_row(row)
        if extra_id is not None:
            self.extraSelected.emit(extra_id)

    def _double_clicked(self, row: int, _column: int) -> None:
        extra_id = self._extra_id_for_row(row)
        if extra_id is not None:
            self.extraDoubleClicked.emit(extra_id)


class ExtrasByDayView(QWidget):
    """Cinco tarjetas de día con el mismo comportamiento que Viajes."""

    extraDoubleClicked = Signal(int)
    selectionChanged = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cards: dict[str, ExtraDayCard] = {}
        self._selected_extra_id: int | None = None
        self._has_populated = False
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
        self._selected_extra_id = None
        self.selectionChanged.emit(None)

        while self.host_layout.count() > 1:
            item = self.host_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
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
