from __future__ import annotations

"""Presentación reutilizable de la herramienta Viajes.

La página principal coordina datos y acciones; este módulo se ocupa de cómo se
muestran métricas y jornadas. El objetivo es que los cambios visuales no mezclen
lógica de persistencia ni consultas SQLite.
"""

from collections import defaultdict
from datetime import date

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QKeyEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..constants import MONTHS_SHORT
from ..layouts import FlowLayout
from ..utils import money
from ..work_calendar import iter_week_days, weekday_name




class WorkMetricCard(QFrame):
    """Tarjeta compacta de resumen con ancho natural configurable.

    A diferencia de ``StatCard``, estas tarjetas no se estiran para rellenar una
    grilla completa. Esto evita que métricas pequeñas como Bulto ocupen cientos
    de píxeles sin contenido.
    """

    def __init__(self, caption: str, preferred_width: int = 170, parent=None):
        super().__init__(parent)
        self._preferred_width = preferred_width
        self.setObjectName("WorkMetricCard")
        self.setMinimumWidth(max(130, preferred_width - 30))
        # Todas las métricas terminan exactamente a la misma altura.
        self.setFixedHeight(112)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 11, 14, 11)
        layout.setSpacing(2)

        self.caption = QLabel(caption)
        self.caption.setObjectName("WorkMetricCaption")
        self.value = QLabel("—")
        self.value.setObjectName("WorkMetricValue")
        self.secondary = QLabel("")
        self.secondary.setObjectName("WorkMetricSecondary")
        self.secondary.setVisible(False)
        self.hint = QLabel("")
        self.hint.setObjectName("WorkMetricHint")
        self.hint.setVisible(False)
        for label in (self.caption, self.value, self.secondary, self.hint):
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setWordWrap(True)
        # El valor principal debe mantenerse en una sola línea (p. ej.
        # "220.0 km"). El wrap queda para captions/hints, donde sí aporta.
        self.value.setWordWrap(False)

        layout.addWidget(self.caption)
        layout.addWidget(self.value)
        layout.addWidget(self.secondary)
        layout.addWidget(self.hint)

    def sizeHint(self) -> QSize:  # noqa: N802 - API de Qt
        content_width = max(
            self.caption.sizeHint().width(),
            self.value.sizeHint().width(),
            self.secondary.sizeHint().width() if self.secondary.isVisible() else 0,
            self.hint.sizeHint().width() if self.hint.isVisible() else 0,
        ) + 28
        content_height = (
            self.caption.sizeHint().height()
            + self.value.sizeHint().height()
            + (self.secondary.sizeHint().height() if self.secondary.isVisible() else 0)
            + (self.hint.sizeHint().height() if self.hint.isVisible() else 0)
            + 28
        )
        return QSize(max(self._preferred_width, min(content_width, 390)), 112)

    def set_mileage(self, summary: dict) -> None:
        total = float(summary.get("real_km") or 0)
        days = int(summary.get("completed_days") or 0)
        self.set_value(
            f"{total:.1f} km" if days else "—",
            secondary=f"Promedio: {total / days:.1f} km/día" if days else "Promedio: —",
            hint=f"{days} día{'s' if days != 1 else ''} con registro" if days else "Sin días completos",
        )
        self.setToolTip("Promedio diario = KM reales / días con odómetro inicial y final. "
                        "Los días sin registro completo no se incluyen; los días completos con 0 km sí.")

    def set_value(self, value: str, secondary: str = "", hint: str = "") -> None:
        self.value.setText(value)
        self.secondary.setText(secondary)
        self.secondary.setVisible(bool(secondary))
        self.hint.setText(hint)
        self.hint.setVisible(bool(hint))
        self.updateGeometry()


class ClickableWorkMetricCard(WorkMetricCard):
    """Métrica compacta que activa un filtro al hacer clic o usar teclado."""

    clicked = Signal()

    def __init__(self, caption: str, preferred_width: int = 170, parent=None):
        super().__init__(caption, preferred_width, parent)
        self.setObjectName("WorkMetricCardClickable")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setProperty("active", False)

    def set_active(self, active: bool) -> None:
        if bool(self.property("active")) == bool(active):
            return
        self.setProperty("active", bool(active))
        self.style().unpolish(self)
        self.style().polish(self)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.clicked.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class DayGroupHeader(QFrame):
    """Encabezado completo de un día; toda la superficie abre/cierra la jornada."""

    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("WorkDayHeader")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        root = QVBoxLayout(self)
        root.setContentsMargins(13, 9, 13, 9)
        root.setSpacing(6)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(9)
        self.chevron = QLabel("›")
        self.chevron.setObjectName("WorkDayChevron")
        self.chevron.setFixedWidth(16)
        self.title = QLabel()
        self.title.setObjectName("WorkDayTitle")
        self.title.setMinimumWidth(125)
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # El chevron de la izquierda se compensa con un espejo a la derecha;
        # así el bloque del día queda centrado respecto de toda la tarjeta.
        mirror = QWidget()
        mirror.setFixedWidth(16)
        title_row.addWidget(self.chevron)
        title_row.addStretch(1)
        title_row.addWidget(self.title, 0, Qt.AlignmentFlag.AlignCenter)
        title_row.addStretch(1)
        title_row.addWidget(mirror)
        root.addLayout(title_row)

        self.chip_host = QWidget()
        self.chip_host.setMaximumWidth(560)
        self.chip_host.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        # Hay como máximo tres chips principales. QHBoxLayout evita el clipping
        # que producía FlowLayout al envolverlos sin aumentar la altura del host.
        self.chip_layout = QHBoxLayout(self.chip_host)
        self.chip_layout.setContentsMargins(0, 0, 0, 0)
        self.chip_layout.setSpacing(6)
        self.chip_layout.addStretch(1)
        self.chip_layout.addStretch(1)
        root.addWidget(self.chip_host, 0, Qt.AlignmentFlag.AlignHCenter)

        for widget in (self.chevron, self.title):
            widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self._chips: list[QLabel] = []

    def set_summary(
        self,
        day: date,
        trip_count: int,
        stop_count: int,
        *,
        total_count: int | None = None,
        real_km: float | None = None,
    ) -> None:
        weekday = weekday_name(day)
        month = MONTHS_SHORT[day.month - 1].lower()
        self.title.setText(f"{weekday}  ·  {day.day:02d} {month}")

        if total_count is not None and total_count != trip_count:
            trip_text = f"{trip_count} de {total_count} viajes"
        else:
            trip_text = f"{trip_count} viaje" if trip_count == 1 else f"{trip_count} viajes"
        stop_text = f"{stop_count} parada" if stop_count == 1 else f"{stop_count} paradas"

        values = [trip_text, stop_text]
        if real_km is not None:
            values.append(f"{real_km:.1f} km reales")

        self.set_chip_texts(values)

    def set_chip_texts(self, values: list[str]) -> None:
        """Reemplaza los chips del encabezado sin exponer detalles del layout."""
        while self._chips:
            chip = self._chips.pop()
            self.chip_layout.removeWidget(chip)
            chip.deleteLater()
        for text in values:
            chip = QLabel(str(text))
            chip.setObjectName("WorkDayChip")
            chip.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            # Siempre antes del stretch derecho para mantener el grupo centrado.
            self.chip_layout.insertWidget(max(1, self.chip_layout.count() - 1), chip)
            self._chips.append(chip)

    def set_expanded(self, expanded: bool) -> None:
        self.chevron.setText("⌄" if expanded else "›")
        self.setProperty("expanded", bool(expanded))
        self.style().unpolish(self)
        self.style().polish(self)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.clicked.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class TripCompactCard(QFrame):
    """Representación vertical de un viaje para pantallas angostas.

    Evita columnas horizontales y conserva la misma información mediante
    bloques de texto y chips. Así los campos personalizados no pueden romper la
    composición de monitores verticales.
    """

    clicked = Signal(int)
    doubleClicked = Signal(int)

    def __init__(self, trip: dict, field_definitions: list[dict], symbol: str, hidden_amounts: bool, parent=None):
        super().__init__(parent)
        self.trip = trip
        self.trip_id = int(trip["id"])
        self.setObjectName("WorkTripCompactCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setProperty("selected", False)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(7)

        top = QHBoxLayout()
        client = QLabel(str(trip.get("client") or "Sin cliente"))
        client.setObjectName("TransactionTitle")
        charged = QLabel("—" if trip.get("charged") is None else money(trip.get("charged") or 0, symbol, hidden_amounts))
        charged.setObjectName("TransactionAmount")
        top.addWidget(client, 1)
        top.addWidget(charged)
        root.addLayout(top)

        route_bits: list[str] = []
        if trip.get("origin"):
            route_bits.append(str(trip["origin"]))
        destinations = [str(x) for x in trip.get("destinations") or [] if str(x).strip()]
        if destinations:
            route_bits.append(" → ".join(destinations))
        route = QLabel("\n".join(route_bits) if route_bits else "Sin recorrido detallado")
        route.setObjectName("SmallMuted")
        route.setWordWrap(True)
        root.addWidget(route)

        chips_host = QWidget()
        chips = FlowLayout(chips_host, horizontal_spacing=6, vertical_spacing=5)
        stop_count = max(1, int(trip.get("stop_count") or len(destinations) or 1))
        chip_values = [f"{stop_count} parada" if stop_count == 1 else f"{stop_count} paradas"]
        custom_values = trip.get("custom_fields") or {}
        for definition in field_definitions:
            field_type = str(definition.get("field_type") or "")
            built_in = definition.get("built_in_key")
            field_id = int(definition["id"])
            value = trip.get(built_in) if built_in else custom_values.get(field_id)
            if field_type == "check":
                if value:
                    chip_values.append(str(definition.get("label") or "Sí"))
            elif value not in (None, "", 0, 0.0):
                if field_type == "money":
                    shown = money(float(value), symbol, hidden_amounts)
                else:
                    shown = str(value)
                chip_values.append(f"{definition.get('label')}: {shown}")
        if trip.get("calculated_price") is not None:
            scheme = trip.get("rate_scheme") or {}
            chip_values.append(f"{scheme.get('name') or 'Tarifa'}: {money(float(trip['calculated_price']), symbol, hidden_amounts)}")
        for value in chip_values:
            chip = QLabel(value)
            chip.setObjectName("WorkDayChip")
            chips.addWidget(chip)
        root.addWidget(chips_host)

        if trip.get("details"):
            details = QLabel(str(trip["details"]))
            details.setObjectName("SmallMuted")
            details.setWordWrap(True)
            root.addWidget(details)

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", bool(selected))
        self.style().unpolish(self)
        self.style().polish(self)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.trip_id)
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.doubleClicked.emit(self.trip_id)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


class DayGroupCard(QFrame):
    """Una jornada plegable con encabezado visual y tabla sólo al expandirse."""

    tripSelected = Signal(int)
    tripDoubleClicked = Signal(int)

    COLUMNS = (
        "Cliente",
        "Origen",
        "Paradas",
        "Destino(s)",
        "Bulto",
        "Lluvia",
        "Flex",
        "Propio",
        "Detalles",
        "Cobrado",
    )

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
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(False)
        self.table.setShowGrid(False)
        self.table.cellClicked.connect(self._selected)
        self.table.cellDoubleClicked.connect(self._double_clicked)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.Stretch)
        header.setStretchLastSection(False)
        centered = {2, 4, 5, 6, 7}
        for column in range(len(self.COLUMNS)):
            item = self.table.horizontalHeaderItem(column)
            if item is None:
                continue
            alignment = Qt.AlignmentFlag.AlignCenter if column in centered else Qt.AlignmentFlag.AlignLeft
            if column == 9:
                alignment = Qt.AlignmentFlag.AlignRight
            item.setTextAlignment(alignment | Qt.AlignmentFlag.AlignVCenter)

        self.compact_host = QWidget()
        self.compact_layout = QVBoxLayout(self.compact_host)
        self.compact_layout.setContentsMargins(0, 4, 0, 0)
        self.compact_layout.setSpacing(7)
        self.compact_host.setVisible(False)
        body_layout.addWidget(self.compact_host)
        self._compact_cards: list[TripCompactCard] = []

        self.empty = QLabel("Sin viajes")
        self.empty.setObjectName("WorkDayEmpty")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setMinimumHeight(48)

        body_layout.addWidget(self.table)
        body_layout.addWidget(self.empty)
        root.addWidget(self.body)
        self.body.setVisible(False)
        self._selected_row: int | None = None

    def set_expanded(self, expanded: bool) -> None:
        self._expanded = bool(expanded)
        self.body.setVisible(self._expanded)
        self.header.set_expanded(self._expanded)

    def toggle(self) -> None:
        self.set_expanded(not self._expanded)

    def is_expanded(self) -> bool:
        return self._expanded

    def set_rows(
        self,
        rows: list[dict],
        symbol: str,
        hidden_amounts: bool,
        *,
        empty_text: str = "Sin viajes",
        compact: bool = False,
        field_definitions: list[dict] | None = None,
    ) -> None:
        self._selected_row = None
        field_definitions = field_definitions or []
        self.table.setRowCount(len(rows))
        self.empty.setText(empty_text)
        self.empty.setVisible(not rows)
        self.table.setVisible(bool(rows) and not compact)
        self.compact_host.setVisible(bool(rows) and compact)

        while self.compact_layout.count():
            item = self.compact_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._compact_cards = []

        builtin_defs = {str(d.get("built_in_key")): d for d in field_definitions if d.get("built_in_key")}
        custom_defs = [d for d in field_definitions if not d.get("built_in_key")]
        labels = {
            "bulky": str((builtin_defs.get("bulky") or {}).get("label") or "Bulto"),
            "rain": str((builtin_defs.get("rain") or {}).get("label") or "Lluvia"),
            "flex": str((builtin_defs.get("flex") or {}).get("label") or "Flex"),
            "own_client": str((builtin_defs.get("own_client") or {}).get("label") or "Propio"),
        }
        headers = list(self.COLUMNS)
        headers[4] = labels["bulky"]
        headers[5] = labels["rain"]
        headers[6] = labels["flex"]
        headers[7] = labels["own_client"]
        headers[8] = "Datos / detalles"
        self.table.setHorizontalHeaderLabels(headers)

        for row_index, trip in enumerate(rows):
            destinations = trip.get("destinations") or []
            stop_count = TripsByDayView.stop_count(trip)
            charged = "—" if trip.get("charged") is None else money(trip.get("charged") or 0, symbol, hidden_amounts)
            custom_values = trip.get("custom_fields") or {}
            info_bits: list[str] = []
            for definition in custom_defs:
                value = custom_values.get(int(definition["id"]))
                if value in (None, "", False, 0, 0.0):
                    continue
                if definition.get("field_type") == "check":
                    info_bits.append(str(definition.get("label") or "Sí"))
                elif definition.get("field_type") == "money":
                    info_bits.append(f"{definition.get('label')}: {money(float(value), symbol, hidden_amounts)}")
                else:
                    info_bits.append(f"{definition.get('label')}: {value}")
            if trip.get("calculated_price") is not None:
                scheme = trip.get("rate_scheme") or {}
                info_bits.append(f"{scheme.get('name') or 'Tarifa'}: {money(float(trip['calculated_price']), symbol, hidden_amounts)}")
            if trip.get("details"):
                info_bits.append(str(trip["details"]))
            values = [
                trip.get("client") or "—",
                trip.get("origin") or "—",
                str(stop_count),
                "\n".join(destinations) or "—",
                "Sí" if trip.get("bulky") else "No",
                "Sí" if trip.get("rain") else "No",
                "Sí" if trip.get("flex") else "No",
                "Sí" if trip.get("own_client") else "No",
                " · ".join(info_bits) or "—",
                charged,
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, int(trip["id"]))
                if column in (2, 4, 5, 6, 7):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                elif column == 9:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row_index, column, item)

            card = TripCompactCard(trip, field_definitions, symbol, hidden_amounts)
            card.clicked.connect(self.tripSelected.emit)
            card.doubleClicked.connect(self.tripDoubleClicked.emit)
            self.compact_layout.addWidget(card)
            self._compact_cards.append(card)

        self.table.resizeRowsToContents()
        if rows and not compact:
            header_height = self.table.horizontalHeader().height()
            rows_height = sum(self.table.rowHeight(row) for row in range(self.table.rowCount()))
            desired = header_height + rows_height + 8
            self.table.setMinimumHeight(min(430, max(92, desired)))
            self.table.setMaximumHeight(min(430, max(92, desired)))
        elif compact:
            self.table.setMinimumHeight(0)
            self.table.setMaximumHeight(0)

    def clear_selection(self) -> None:
        self._apply_row_selection(None)
        for card in self._compact_cards:
            card.set_selected(False)

    def select_trip(self, trip_id: int) -> bool:
        found = False
        for row in range(self.table.rowCount()):
            if self._trip_id_for_row(row) == int(trip_id):
                self._apply_row_selection(row)
                found = True
                break
        for card in self._compact_cards:
            selected = card.trip_id == int(trip_id)
            card.set_selected(selected)
            found = found or selected
        return found

    def _apply_row_selection(self, row: int | None) -> None:
        rows_to_refresh = {self._selected_row, row}
        self._selected_row = row if row is not None and 0 <= row < self.table.rowCount() else None
        selected_color = QColor(132, 122, 255, 36)
        clear_color = QColor(0, 0, 0, 0)
        for row_index in rows_to_refresh:
            if row_index is None or not (0 <= row_index < self.table.rowCount()):
                continue
            is_selected = row_index == self._selected_row
            for column in range(self.table.columnCount()):
                item = self.table.item(row_index, column)
                if item is None:
                    continue
                item.setBackground(selected_color if is_selected else clear_color)

    def _trip_id_for_row(self, row: int) -> int | None:
        item = self.table.item(row, 0)
        if item is None:
            return None
        try:
            return int(item.data(Qt.ItemDataRole.UserRole))
        except (TypeError, ValueError):
            return None

    def _selected(self, row: int, _column: int) -> None:
        trip_id = self._trip_id_for_row(row)
        if trip_id is not None:
            self.tripSelected.emit(trip_id)

    def _double_clicked(self, row: int, _column: int) -> None:
        trip_id = self._trip_id_for_row(row)
        if trip_id is not None:
            self.tripDoubleClicked.emit(trip_id)


class TripsByDayView(QWidget):
    """Vista semanal formada por cinco tarjetas plegables, una por jornada."""

    tripDoubleClicked = Signal(int)
    selectionChanged = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cards: dict[str, DayGroupCard] = {}
        self._selected_trip_id: int | None = None
        self._has_populated = False
        self._compact = False
        self._field_definitions: list[dict] = []

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

    @staticmethod
    def stop_count(trip: dict) -> int:
        try:
            return max(1, int(trip.get("stop_count") or len(trip.get("destinations") or []) or 1))
        except (TypeError, ValueError):
            return max(1, len(trip.get("destinations") or []), 1)

    def set_compact(self, compact: bool) -> None:
        self._compact = bool(compact)

    def set_field_definitions(self, definitions: list[dict]) -> None:
        self._field_definitions = list(definitions or [])

    def populate(
        self,
        week_start: date,
        rows: list[dict],
        symbol: str,
        hidden_amounts: bool,
        *,
        all_rows: list[dict] | None = None,
        mileage_rows: list[dict] | None = None,
    ) -> None:
        expanded_days = {key for key, card in self._cards.items() if card.is_expanded()}
        self._selected_trip_id = None
        self.selectionChanged.emit(None)

        while self.host_layout.count() > 1:
            item = self.host_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._cards = {}

        visible_by_date: dict[str, list[dict]] = defaultdict(list)
        for trip in rows:
            visible_by_date[str(trip.get("trip_date") or "")].append(trip)
        all_by_date: dict[str, list[dict]] = defaultdict(list)
        for trip in all_rows if all_rows is not None else rows:
            all_by_date[str(trip.get("trip_date") or "")].append(trip)
        mileage_by_date = {str(row.get("work_date") or ""): row for row in (mileage_rows or [])}

        for day in iter_week_days(week_start):
            day_iso = day.isoformat()
            visible = visible_by_date.get(day_iso, [])
            all_for_day = all_by_date.get(day_iso, [])
            stop_count = sum(self.stop_count(trip) for trip in visible)
            mileage = mileage_by_date.get(day_iso) or {}
            real_km = mileage.get("real_km")

            card = DayGroupCard(day)
            card.header.clicked.connect(self.clear_selection)
            card.header.set_summary(
                day,
                len(visible),
                stop_count,
                total_count=len(all_for_day),
                real_km=float(real_km) if real_km is not None else None,
            )
            empty_text = "Sin viajes" if not all_for_day else "Sin coincidencias para el filtro actual"
            card.set_rows(
                visible,
                symbol,
                hidden_amounts,
                empty_text=empty_text,
                compact=self._compact,
                field_definitions=self._field_definitions,
            )
            card.tripSelected.connect(lambda trip_id, source=card: self._select_trip(source, trip_id))
            card.tripDoubleClicked.connect(self.tripDoubleClicked.emit)
            # Primera carga: todo plegado. Después respetamos exactamente lo que
            # el usuario haya abierto/cerrado durante esa semana.
            card.set_expanded(day_iso in expanded_days if self._has_populated else False)
            self._cards[day_iso] = card
            self.host_layout.insertWidget(self.host_layout.count() - 1, card)

        self._has_populated = True

    def _select_trip(self, source: DayGroupCard, trip_id: int) -> None:
        """Selecciona una fila; un segundo clic sobre la misma la deselecciona."""
        if self._selected_trip_id == trip_id:
            source.clear_selection()
            self._selected_trip_id = None
            self.selectionChanged.emit(None)
            return
        self._selected_trip_id = trip_id
        for card in self._cards.values():
            if card is source:
                card.select_trip(trip_id)
            else:
                card.clear_selection()
        self.selectionChanged.emit(trip_id)

    def clear_selection(self) -> None:
        if self._selected_trip_id is None:
            return
        for card in self._cards.values():
            card.clear_selection()
        self._selected_trip_id = None
        self.selectionChanged.emit(None)

    def selected_trip_id(self) -> int | None:
        return self._selected_trip_id

    def day_count(self) -> int:
        """Cantidad de jornadas visibles; útil para smoke tests sin acoplarse a internals."""
        return len(self._cards)
