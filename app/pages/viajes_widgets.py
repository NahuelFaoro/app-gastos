from __future__ import annotations

"""Presentación reutilizable de la herramienta Viajes.

La página principal coordina datos y acciones; este módulo se ocupa de cómo se
muestran métricas y jornadas. El objetivo es que los cambios visuales no mezclen
lógica de persistencia ni consultas SQLite.
"""

from collections import defaultdict
from datetime import date

from PySide6.QtCore import QSize, Qt, Signal, QEvent
from PySide6.QtGui import QKeyEvent, QPainter, QPen, QPalette
from PySide6.QtWidgets import (
    QCheckBox,
    QStyle,
    QStyleOptionButton,
    QGridLayout,
    QPushButton,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .work_cards import FoldableWorkCard
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
            hint=f"Prom. {total / days:.1f} km/día" if days else "Promedio: —",
        )
        self.hint.setWordWrap(False)
        self.setToolTip(f"{days} días con registro completo. Promedio diario = KM reales / días con odómetro inicial y final. "
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


class TripCheckBox(QCheckBox):
    """Casilla con tilde visible además del color de selección."""

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if not self.isChecked():
            return
        option = QStyleOptionButton()
        self.initStyleOption(option)
        rect = self.style().subElementRect(QStyle.SubElement.SE_CheckBoxIndicator, option, self)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(self.palette().color(QPalette.ColorRole.HighlightedText), 2,
                            Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.drawLine(rect.left() + 4, rect.center().y(), rect.left() + 7, rect.bottom() - 4)
        painter.drawLine(rect.left() + 7, rect.bottom() - 4, rect.right() - 3, rect.top() + 4)
        painter.end()


class TripCompactCard(FoldableWorkCard):
    """Detalle de recorrido con casillas editables."""

    fieldChanged = Signal(int, object, bool)

    def __init__(self, trip: dict, field_definitions: list[dict], symbol: str, hidden_amounts: bool, parent=None):
        amount = "Sin importe" if trip.get("charged") is None else money(trip.get("charged") or 0, symbol, hidden_amounts)
        super().__init__(int(trip["id"]), str(trip.get("client") or "Sin cliente"), amount, parent)
        self.trip_id = self.record_id
        detail_layout = self.detail_layout
        destinations = [str(x) for x in trip.get("destinations") or [] if str(x).strip()]
        count = TripsByDayView.stop_count(trip)
        for caption, value in (
            ("Desde", str(trip.get("origin") or "Sin origen")),
            (f"{count} parada" if count == 1 else f"{count} paradas", "  →  ".join(destinations) or "Sin destinos detallados"),
        ):
            row = QHBoxLayout()
            label = QLabel(caption)
            label.setObjectName("SmallMuted")
            label.setFixedWidth(76)
            value_label = QLabel(value)
            value_label.setTextFormat(Qt.TextFormat.PlainText)
            value_label.setWordWrap(True)
            value_label.setMinimumWidth(0)
            row.addWidget(label, 0, Qt.AlignmentFlag.AlignTop)
            row.addWidget(value_label, 1)
            detail_layout.addLayout(row)

        host = QWidget()
        flow = FlowLayout(host, horizontal_spacing=18, vertical_spacing=8)
        self.checks = {}
        custom_values = trip.get("custom_fields") or {}
        for definition in field_definitions:
            field_id = int(definition["id"])
            key = definition.get("built_in_key")
            value = trip.get(key) if key else custom_values.get(field_id)
            if definition.get("field_type") == "check":
                check = TripCheckBox(str(definition.get("label") or "Opción"))
                check.setObjectName("WorkTripCheck")
                check.setChecked(bool(value))
                check.setCursor(Qt.CursorShape.PointingHandCursor)
                check.setToolTip("Marcar o desmarcar guarda el cambio")
                check.toggled.connect(lambda checked, d=dict(definition): self.fieldChanged.emit(self.trip_id, d, checked))
                self.checks[field_id] = check
                flow.addWidget(check)
            elif value not in (None, ""):
                shown = money(float(value), symbol, hidden_amounts) if definition.get("field_type") == "money" else str(value)
                label = QLabel(f"{definition.get('label')}: {shown}")
                label.setObjectName("WorkDayChip")
                flow.addWidget(label)
        if flow.count():
            detail_layout.addWidget(host)
        else:
            host.deleteLater()
        if trip.get("calculated_price") is not None:
            scheme = trip.get("rate_scheme") or {}
            label = QLabel(f"{scheme.get('name') or 'Tarifa'} · {money(float(trip['calculated_price']), symbol, hidden_amounts)}")
            label.setObjectName("SmallMuted")
            label.setWordWrap(True)
            detail_layout.addWidget(label)
        if trip.get("details"):
            details = QLabel(str(trip["details"]))
            details.setObjectName("SmallMuted")
            details.setWordWrap(True)
            details.setTextFormat(Qt.TextFormat.PlainText)
            detail_layout.addWidget(details)


class DayGroupCard(QFrame):
    """Jornada plegable sin tabla ni desplazamiento interno."""

    tripSelected = Signal(int)
    tripDoubleClicked = Signal(int)
    fieldChanged = Signal(int, object, bool)

    def __init__(self, day: date, parent=None):
        super().__init__(parent)
        self.day = day
        self.setObjectName("WorkDayCard")
        self._expanded = False
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.header = DayGroupHeader()
        self.header.clicked.connect(self.toggle)
        root.addWidget(self.header)
        self.body = QWidget()
        self.compact_layout = QGridLayout(self.body)
        self._columns = 0
        self.compact_layout.setContentsMargins(10, 10, 10, 10)
        self.compact_layout.setSpacing(8)
        self._compact_cards: list[TripCompactCard] = []
        root.addWidget(self.body)
        self.body.hide()

    def set_expanded(self, expanded: bool) -> None:
        self._expanded = bool(expanded)
        self.body.setVisible(self._expanded)
        self.header.set_expanded(self._expanded)

    def toggle(self) -> None:
        self.set_expanded(not self._expanded)

    def is_expanded(self) -> bool:
        return self._expanded

    def set_rows(self, rows: list[dict], symbol: str, hidden_amounts: bool, *,
                 empty_text: str = "Sin viajes", compact: bool = False,
                 field_definitions: list[dict] | None = None) -> None:
        while self.compact_layout.count():
            widget = self.compact_layout.takeAt(0).widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()
        self._compact_cards = []
        for trip in rows:
            card = TripCompactCard(trip, field_definitions or [], symbol, hidden_amounts)
            card.expansionChanged.connect(self._arrange_cards)
            card.clicked.connect(self.tripSelected.emit)
            card.doubleClicked.connect(self.tripDoubleClicked.emit)
            card.fieldChanged.connect(self.fieldChanged.emit)
            self._compact_cards.append(card)
        if not rows:
            empty = QLabel(empty_text)
            empty.setObjectName("WorkDayEmpty")
            empty.setMinimumHeight(40)
            self.compact_layout.addWidget(empty, 0, 0)
        self._arrange_cards()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._arrange_cards()

    def _arrange_cards(self) -> None:
        if not self._compact_cards:
            return
        columns = max(1, min(3, self.width() // 540))
        for card in self._compact_cards:
            self.compact_layout.removeWidget(card)
        for column in range(max(self._columns, columns)):
            self.compact_layout.setColumnStretch(column, 1 if column < columns else 0)
        for index, card in enumerate(self._compact_cards):
            self.compact_layout.addWidget(card, index // columns, index % columns,
                                              Qt.Alignment() if card.is_expanded() else Qt.AlignmentFlag.AlignTop)
        self._columns = columns

    def clear_selection(self) -> None:
        for card in self._compact_cards:
            card.set_selected(False)

    def select_trip(self, trip_id: int) -> bool:
        found = False
        for card in self._compact_cards:
            selected = card.trip_id == int(trip_id)
            card.set_selected(selected)
            found = found or selected
        return found


class TripsByDayView(QWidget):
    """Vista semanal formada por cinco tarjetas plegables, una por jornada."""

    tripDoubleClicked = Signal(int)
    selectionChanged = Signal(object)
    fieldChanged = Signal(int, object, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cards: dict[str, DayGroupCard] = {}
        self._selected_trip_id: int | None = None
        self._has_populated = False
        self._expanded_trips: set[int] = set()
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
        for day_card in self._cards.values():
            for trip_card in day_card._compact_cards:
                if trip_card.is_expanded():
                    self._expanded_trips.add(trip_card.trip_id)
                else:
                    self._expanded_trips.discard(trip_card.trip_id)
        self._selected_trip_id = None
        self.selectionChanged.emit(None)

        while self.host_layout.count() > 1:
            item = self.host_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
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
            for trip_card in card._compact_cards:
                trip_card.set_expanded(trip_card.trip_id in self._expanded_trips)
            card.tripSelected.connect(lambda trip_id, source=card: self._select_trip(source, trip_id))
            card.tripDoubleClicked.connect(self.tripDoubleClicked.emit)
            card.fieldChanged.connect(self.fieldChanged.emit)
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
