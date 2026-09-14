from __future__ import annotations

"""Gestión semanal de viajes y trabajo extra.

La pantalla trabaja con dos conceptos independientes:

* ``Viajes``: recorridos con cliente, destinos y etiquetas Bulto/Lluvia/Flex.
* ``Extras``: horas e ingresos obtenidos mediante apps como PedidosYa o Rappi.

Los registros se agrupan por semana completa (lunes a domingo) y permanecen en
la misma base SQLite que el resto de App Gastos, por lo que entran en backups y
restauraciones de forma automática.
"""

from datetime import date, timedelta

from PySide6.QtCore import QDate, Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QBoxLayout,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

try:
    import qtawesome as qta
except Exception:
    qta = None

from ..layouts import FlowLayout, responsive_mode
from ..utils import money
from ..work_calendar import compact_week_label, week_start
from .common import page_header
from .viajes_dialogs import ExtraDialog, MileageWeekDialog, TripDialog
from ..date_picker import DatePickerButton
from .viajes_widgets import (
    ClickableWorkMetricCard,
    TripsByDayView,
    WorkMetricCard,
)
from .extras_widgets import ExtrasByDayView
from .work_monthly import WorkMonthSummaryDialog
from .work_config import WorkCustomizationDialog


FILTER_LABELS = {
    "bulky": "Bulto",
    "rain": "Lluvia",
    "flex": "Flex",
    "own_client": "Cliente propio",
}



# Alias locales conservados para mantener el código de la página legible.
monday_of = week_start
workweek_label = compact_week_label



class ViajesPage(QWidget):
    """Herramienta de gestión semanal de viajes y extras."""

    data_changed = Signal()

    def __init__(self, db):
        super().__init__()
        self.db = db
        self.current_week = monday_of(date.today())
        self.trip_filter: str | None = None
        self._compact = False
        self._responsive_mode = None

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 28)
        root.setSpacing(16)

        self._build_header(root)
        self._build_primary_actions(root)
        self._build_week_navigation(root)
        self._build_summary_metrics(root)
        self._build_toolbar(root)
        self._build_content_tabs(root)

        self.refresh()
        self._apply_responsive(force=True)

    def _build_header(self, root: QVBoxLayout) -> None:
        self.header_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.header_layout.addWidget(
            page_header(
                "Viajes",
                "Historial semanal de recorridos y trabajo extra, organizado por día.",
            ),
            1,
        )
        root.addLayout(self.header_layout)

    def _build_primary_actions(self, root: QVBoxLayout) -> None:
        # Acciones principales centradas. El layout no envuelve, así la
        # jerarquía se mantiene estable y el responsive decide cuándo apilar.
        self.actions_host = QWidget()
        self.actions_host.setMaximumWidth(560)
        self.actions_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight, self.actions_host)
        self.actions_layout.setContentsMargins(0, 0, 0, 0)
        self.actions_layout.setSpacing(10)

        self.mileage_button = QPushButton("Kilometraje")
        self.mileage_button.setObjectName("SecondaryButton")
        self.mileage_button.setFixedSize(172, 44)
        self.mileage_button.setToolTip("Cargar odómetro inicial y final de cada día")
        self.mileage_button.clicked.connect(self.open_mileage)

        self.add_button = QPushButton("Nuevo viaje")
        self.add_button.setFixedSize(172, 44)
        if qta is not None:
            try:
                self.add_button.setIcon(qta.icon("mdi6.plus", color="#082018"))
            except Exception:
                pass
        self.add_button.clicked.connect(self._new_for_current_tab)

        self.customize_button = QPushButton("Personalizar")
        self.customize_button.setObjectName("SecondaryButton")
        self.customize_button.setFixedSize(172, 44)
        self.customize_button.setToolTip("Elegir campos, nombres y tarifas de Viajes")
        self.customize_button.clicked.connect(self.open_customization)

        for button in (self.mileage_button, self.add_button, self.customize_button):
            self.actions_layout.addWidget(button)
        root.addWidget(self.actions_host, 0, Qt.AlignmentFlag.AlignHCenter)

    def _build_week_navigation(self, root: QVBoxLayout) -> None:
        self.week_bar = QFrame()
        self.week_bar.setObjectName("SoftCard")
        self.week_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight, self.week_bar)
        self.week_layout.setContentsMargins(13, 10, 13, 10)
        self.week_layout.setSpacing(8)

        prev_button = QPushButton("‹")
        prev_button.setObjectName("GhostButton")
        prev_button.setFixedWidth(38)
        prev_button.clicked.connect(lambda: self.shift_week(-1))
        next_button = QPushButton("›")
        next_button.setObjectName("GhostButton")
        next_button.setFixedWidth(38)
        next_button.clicked.connect(lambda: self.shift_week(1))

        self.week_title = QLabel()
        self.week_title.setObjectName("WorkWeekTitle")
        current_button = QPushButton("Esta semana")
        current_button.setObjectName("SecondaryButton")
        current_button.clicked.connect(self.go_current_week)
        self.month_button = QPushButton("Este mes")
        self.month_button.setObjectName("SecondaryButton")
        self.month_button.setToolTip("Ver totales mensuales y el resumen de cada semana")
        self.month_button.clicked.connect(self.open_month_summary)

        self.saved_weeks = QComboBox()
        self.saved_weeks.setMinimumWidth(190)
        self.saved_weeks.currentIndexChanged.connect(self.jump_saved_week)
        self.jump_date = DatePickerButton()
        self.jump_date.dateChanged.connect(self.jump_to_date)

        self.week_layout.addWidget(prev_button)
        self.week_layout.addWidget(self.week_title)
        self.week_layout.addWidget(next_button)
        self.week_layout.addWidget(current_button)
        self.week_layout.addWidget(self.month_button)
        self.week_layout.addStretch()
        self.saved_label = QLabel("Semanas guardadas")
        self.saved_label.setObjectName("SmallMuted")
        self.date_label = QLabel("Ir a")
        self.date_label.setObjectName("SmallMuted")
        self.week_layout.addWidget(self.saved_label)
        self.week_layout.addWidget(self.saved_weeks)
        self.week_layout.addWidget(self.date_label)
        self.week_layout.addWidget(self.jump_date)
        self.week_bar.setMaximumWidth(1100)
        root.addWidget(self.week_bar, 0, Qt.AlignmentFlag.AlignHCenter)

    def _build_summary_metrics(self, root: QVBoxLayout) -> None:
        # Una grilla estable evita que personalizar campos cambie dimensiones
        # arbitrariamente o desplace tarjetas no relacionadas.
        self.stats_host = QWidget()
        self.stats_host.setMaximumWidth(1180)
        self.stats_host.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.stats_layout = QGridLayout(self.stats_host)
        self.stats_layout.setContentsMargins(0, 0, 0, 0)
        self.stats_layout.setHorizontalSpacing(10)
        self.stats_layout.setVerticalSpacing(10)
        self.stat_trips = ClickableWorkMetricCard("Viajes", preferred_width=160)
        self.stat_km = WorkMetricCard("KM reales", preferred_width=160)
        self.stat_charged = WorkMetricCard("Cobrado", preferred_width=160)
        self.dynamic_metric_cards: dict[str, ClickableWorkMetricCard] = {}
        self.stat_trips.clicked.connect(lambda: self.set_trip_filter(None))
        self._rebuild_dynamic_metrics()
        root.addWidget(self.stats_host, 0, Qt.AlignmentFlag.AlignHCenter)

    def _build_toolbar(self, root: QVBoxLayout) -> None:
        self.toolbar_host = QWidget()
        self.toolbar_host.setMaximumWidth(1020)
        self.toolbar_outer = QVBoxLayout(self.toolbar_host)
        self.toolbar_outer.setContentsMargins(0, 0, 0, 0)
        self.toolbar_outer.setSpacing(7)
        self.toolbar_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.toolbar_layout.setContentsMargins(0, 0, 0, 0)
        self.toolbar_layout.setSpacing(8)

        self.search = QLineEdit()
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumWidth(650)
        self.search.setPlaceholderText("Buscar cliente, origen, destino o detalle en esta semana…")
        self.search.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.search.textChanged.connect(self.refresh_trips)
        self.toolbar_layout.addWidget(self.search, 1)

        self.edit_button = QPushButton("Editar")
        self.edit_button.setObjectName("SecondaryButton")
        self.edit_button.setEnabled(False)
        self.edit_button.clicked.connect(self.edit_selected)
        self.delete_button = QPushButton("Eliminar")
        self.delete_button.setObjectName("GhostDangerButton")
        self.delete_button.setEnabled(False)
        self.delete_button.clicked.connect(self.delete_selected)
        self.toolbar_layout.addWidget(self.edit_button)
        self.toolbar_layout.addWidget(self.delete_button)
        self.toolbar_outer.addLayout(self.toolbar_layout)

        # El filtro vive en su propia fila para no superponerse con búsqueda.
        self.filter_chip = QPushButton()
        self.filter_chip.setObjectName("WorkFilterChip")
        self.filter_chip.setVisible(False)
        self.filter_chip.clicked.connect(lambda: self.set_trip_filter(None))
        self.toolbar_outer.addWidget(self.filter_chip, 0, Qt.AlignmentFlag.AlignHCenter)
        root.addWidget(self.toolbar_host, 0, Qt.AlignmentFlag.AlignHCenter)

    def _build_content_tabs(self, root: QVBoxLayout) -> None:
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_trips_tab(), "Viajes")
        self.tabs.addTab(self._build_extras_tab(), "Extras")
        self.tabs.currentChanged.connect(self._tab_changed)
        root.addWidget(self.tabs, 1)

    # ------------------------------------------------------------------ UI
    def _build_trips_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        hint = QLabel("Abrí un día y tocá el encabezado de un viaje para ver su detalle. Las casillas guardan los cambios al marcarlas.")
        hint.setObjectName("SmallMuted")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.trips_tree = TripsByDayView()
        self.trips_tree.tripDoubleClicked.connect(self._trip_double_clicked)
        self.trips_tree.selectionChanged.connect(self._trip_selection_changed)
        self.trips_tree.fieldChanged.connect(self._update_trip_check)
        layout.addWidget(self.trips_tree, 1)
        return page

    def _build_extras_tab(self) -> QWidget:
        """Extras usa el mismo patrón visual de jornadas plegables que Viajes."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(10)

        self.extra_stats_host = QWidget()
        self.extra_stats_layout = FlowLayout(self.extra_stats_host, horizontal_spacing=9, vertical_spacing=9, center_rows=True)
        self.extra_hours = WorkMetricCard("Horas", 150)
        self.extra_orders = WorkMetricCard("Pedidos / viajes", 180)
        self.extra_amount = WorkMetricCard("Ganado", 190)
        self.extra_entries = WorkMetricCard("Registros", 150)
        for card in (self.extra_hours, self.extra_orders, self.extra_amount, self.extra_entries):
            self.extra_stats_layout.addWidget(card)
        layout.addWidget(self.extra_stats_host)

        description = QLabel(
            "Cada día funciona igual que en Viajes: abrilo para ver las jornadas de PedidosYa, Rappi u otras apps. "
            "Un segundo clic sobre la misma fila deselecciona."
        )
        description.setObjectName("SmallMuted")
        description.setWordWrap(True)
        layout.addWidget(description)

        self.extras_view = ExtrasByDayView()
        self.extras_view.extraDoubleClicked.connect(self._extra_double_clicked)
        self.extras_view.selectionChanged.connect(self._extra_selection_changed)
        layout.addWidget(self.extras_view, 1)
        return page

    def _apply_responsive(self, force: bool = False) -> None:
        mode = responsive_mode(self.width(), self.height())
        compact = mode != "wide"
        if not force and mode == self._responsive_mode:
            return
        self._responsive_mode = mode
        self._compact = compact
        direction = QBoxLayout.Direction.TopToBottom if compact else QBoxLayout.Direction.LeftToRight
        self.toolbar_layout.setDirection(direction)
        # Navegación principal compacta y estable. En vertical ocultamos los
        # accesos secundarios en vez de estirar/apilar la barra completa.
        self.week_layout.setDirection(QBoxLayout.Direction.LeftToRight)
        show_secondary = mode == "wide"
        self.saved_label.setVisible(show_secondary)
        self.date_label.setVisible(show_secondary)
        self.saved_weeks.setVisible(show_secondary)
        self.jump_date.setVisible(show_secondary)
        self.week_bar.setMaximumWidth(1100 if mode == "wide" else 760 if mode == "compact" else 640)
        self.week_bar.setMinimumWidth(0)

        # Las tres acciones principales usan QBoxLayout, no FlowLayout: nunca
        # quedan ocultas por un wrap cuya altura no sea propagada al host.
        if mode == "narrow":
            self.actions_layout.setDirection(QBoxLayout.Direction.TopToBottom)
            self.actions_host.setMaximumWidth(240)
            for button in (self.mileage_button, self.add_button, self.customize_button):
                button.setFixedSize(220, 44)
        else:
            self.actions_layout.setDirection(QBoxLayout.Direction.LeftToRight)
            self.actions_host.setMaximumWidth(560)
            for button in (self.mileage_button, self.add_button, self.customize_button):
                button.setFixedSize(172, 44)

        self.toolbar_host.setMaximumWidth(1020 if mode == "wide" else 760 if mode == "compact" else 520)
        self.search.setMinimumWidth(650 if mode == "wide" else 0)
        self._layout_metric_cards(mode)
        self.trips_tree.set_compact(compact)
        if hasattr(self.extras_view, "set_compact"):
            self.extras_view.set_compact(compact)
        margins = 12 if mode == "narrow" else 18 if compact else 28
        self.layout().setContentsMargins(margins, 16 if compact else 24, margins, 18 if compact else 28)
        self.refresh_trips()
        self.refresh_extras()

    def _metric_cards(self) -> list[WorkMetricCard]:
        return [
            self.stat_trips,
            *self.dynamic_metric_cards.values(),
            self.stat_km,
            self.stat_charged,
        ]

    def _layout_metric_cards(self, mode: str | None = None) -> None:
        """Distribuye todas las métricas con geometría estable y uniforme."""
        mode = mode or self._responsive_mode or responsive_mode(self.width(), self.height())
        while self.stats_layout.count():
            item = self.stats_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(self.stats_host)

        cards = self._metric_cards()
        columns = len(cards) if mode == "wide" else min(4, len(cards)) if mode == "compact" else min(2, len(cards))
        columns = max(1, columns)
        for col in range(12):
            self.stats_layout.setColumnStretch(col, 0)
        for index, card in enumerate(cards):
            card.setMinimumWidth(145)
            card.setMaximumWidth(16777215)
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            row, col = divmod(index, columns)
            self.stats_layout.addWidget(card, row, col)
        for col in range(columns):
            self.stats_layout.setColumnStretch(col, 1)
        self.stats_host.setMaximumWidth(1180 if mode == "wide" else 820 if mode == "compact" else 520)

    def _rebuild_dynamic_metrics(self) -> None:
        """Reconstruye métricas configurables sin alterar la geometría del resumen."""
        for card in self.dynamic_metric_cards.values():
            self.stats_layout.removeWidget(card)
            card.setParent(None)
            card.deleteLater()
        self.dynamic_metric_cards = {}
        definitions = self.db.work_field_definitions(active_only=True)
        for definition in definitions:
            if definition.get("field_type") != "check" or not definition.get("show_in_summary"):
                continue
            built_in = str(definition.get("built_in_key") or "")
            filter_key = built_in if built_in else f"custom:{int(definition['id'])}"
            card = ClickableWorkMetricCard(str(definition.get("label") or "Campo"), preferred_width=160)
            card.clicked.connect(lambda key=filter_key: self.toggle_trip_filter(key))
            self.dynamic_metric_cards[filter_key] = card
        self._layout_metric_cards()

    def open_customization(self) -> None:
        dialog = WorkCustomizationDialog(self.db, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.set_trip_filter(None)
            self._rebuild_dynamic_metrics()
            self.refresh()

    def _filter_label(self, key: str) -> str:
        definitions = self.db.work_field_definitions()
        builtin = next((d for d in definitions if d.get("built_in_key") == key), None)
        if builtin:
            return str(builtin.get("label") or key)
        if key.startswith("custom:"):
            try:
                field_id = int(key.split(":", 1)[1])
            except (TypeError, ValueError):
                return "Campo"
            definition = next((d for d in self.db.work_field_definitions() if int(d["id"]) == field_id), None)
            if definition:
                return str(definition.get("label") or "Campo")
        return key

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_responsive()

    # ----------------------------------------------------------- Navegación
    def _date_for_new(self) -> date:
        today = date.today()
        return today if self.current_week == monday_of(today) else self.current_week

    def shift_week(self, amount: int) -> None:
        self.current_week += timedelta(weeks=int(amount))
        self._sync_date()
        self.refresh()

    def go_current_week(self) -> None:
        self.current_week = monday_of(date.today())
        self._sync_date()
        self.refresh()

    def jump_to_date(self, qdate) -> None:
        self.current_week = monday_of(date(qdate.year(), qdate.month(), qdate.day()))
        self.refresh()

    def jump_saved_week(self, index: int) -> None:
        if index <= 0:
            return
        value = self.saved_weeks.itemData(index)
        if not value:
            return
        try:
            self.current_week = date.fromisoformat(str(value))
        except (TypeError, ValueError):
            return
        self._sync_date()
        self.refresh()

    def _sync_date(self) -> None:
        self.jump_date.blockSignals(True)
        self.jump_date.setDate(QDate.fromString(self.current_week.isoformat(), "yyyy-MM-dd"))
        self.jump_date.blockSignals(False)

    def _refresh_saved_weeks(self) -> None:
        current = self.current_week.isoformat()
        weeks = self.db.work_available_weeks()
        self.saved_weeks.blockSignals(True)
        self.saved_weeks.clear()
        self.saved_weeks.addItem("Seleccionar…", None)
        selected = 0
        for index, week in enumerate(weeks, start=1):
            self.saved_weeks.addItem(workweek_label(week, include_year=True), week)
            if week == current:
                selected = index
        self.saved_weeks.setCurrentIndex(selected)
        self.saved_weeks.blockSignals(False)

    # --------------------------------------------------------------- Filtros
    def toggle_trip_filter(self, flag: str) -> None:
        self.set_trip_filter(None if self.trip_filter == flag else flag)

    def set_trip_filter(self, flag: str | None) -> None:
        if flag is not None and flag not in FILTER_LABELS and not str(flag).startswith("custom:"):
            return
        self.trip_filter = flag
        self._sync_filter_ui()
        if self.tabs.currentIndex() != 0:
            self.tabs.setCurrentIndex(0)
        self.refresh_trips()

    def _sync_filter_ui(self) -> None:
        self.stat_trips.set_active(self.trip_filter is None)
        for flag, card in self.dynamic_metric_cards.items():
            card.set_active(self.trip_filter == flag)
        if self.trip_filter:
            self.filter_chip.setText(f"Filtro: {self._filter_label(self.trip_filter)}  ×")
            self.filter_chip.setVisible(True)
        else:
            self.filter_chip.setVisible(False)

    # -------------------------------------------------------------- Refresh
    def refresh(self) -> None:
        self._sync_date()
        self.week_title.setText(workweek_label(self.current_week))
        self._refresh_saved_weeks()
        self._sync_filter_ui()

        summary = self.db.work_week_summary(self.current_week)
        paradas = int(summary.get("stops") or 0)
        parada_label = "parada" if paradas == 1 else "paradas"
        self.stat_trips.set_value(
            str(summary["trips"]),
            secondary=f"{paradas} {parada_label}",
            hint="Clic para limpiar filtros",
        )
        field_counts = self.db.work_week_field_counts(self.current_week)
        definitions = {int(d["id"]): d for d in self.db.work_field_definitions(active_only=True)}
        for filter_key, card in self.dynamic_metric_cards.items():
            if filter_key.startswith("custom:"):
                field_id = int(filter_key.split(":", 1)[1])
            else:
                field_id = next(
                    (fid for fid, definition in definitions.items() if definition.get("built_in_key") == filter_key),
                    None,
                )
            value = field_counts.get(int(field_id), 0) if field_id else 0
            shown = str(int(value)) if float(value).is_integer() else f"{value:g}"
            hint = "paradas · clic para inspeccionar" if filter_key == "flex" else "viajes · clic para inspeccionar"
            card.set_value(shown, hint=hint)
        mileage = self.db.work_week_mileage_summary(self.current_week)
        self.stat_km.set_mileage(mileage)
        self.stat_charged.set_value(
            money(summary["charged"], self.db.currency_symbol(), self.db.balances_hidden()),
            hint="total semanal",
        )
        self.refresh_trips()
        self.refresh_extras()

    def on_show(self) -> None:
        self.refresh()

    def refresh_trips(self) -> None:
        search = self.search.text().strip()
        visible_rows = self.db.work_trips_for_week(self.current_week, search, self.trip_filter)
        all_rows = self.db.work_trips_for_week(self.current_week)
        self.trips_tree.set_field_definitions(self.db.work_field_definitions(active_only=True))
        self.trips_tree.populate(
            self.current_week,
            visible_rows,
            self.db.currency_symbol(),
            self.db.balances_hidden(),
            all_rows=all_rows,
            mileage_rows=self.db.work_mileage_for_week(self.current_week),
        )

    def refresh_extras(self) -> None:
        rows = self.db.work_extras_for_week(self.current_week)
        summary = self.db.work_extra_week_summary(self.current_week)
        hidden = self.db.balances_hidden()
        symbol = self.db.currency_symbol()

        hours = float(summary.get("hours") or 0)
        self.extra_hours.set_value(f"{hours:.2f} h".replace(".00", ""), hint="trabajadas")
        self.extra_orders.set_value(str(summary["orders"]), hint="pedidos / viajes")
        self.extra_amount.set_value(money(summary["amount"], symbol, hidden), hint="total semanal")
        self.extra_entries.set_value(str(summary["entries"]), hint="jornadas registradas")
        self.extras_view.populate(self.current_week, rows, symbol, hidden)

    # ---------------------------------------------------------- Resumen mensual
    def open_month_summary(self) -> None:
        """Abre el mes correspondiente a la semana que el usuario está viendo."""
        reference = self.current_week + timedelta(days=2)
        WorkMonthSummaryDialog(self.db, reference, parent=self).exec()

    # --------------------------------------------------------- Kilometraje
    def open_mileage(self) -> None:
        """Edita las lecturas de odómetro de lunes a domingo de la semana."""
        dialog = MileageWeekDialog(self.db, self.current_week, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.refresh()
        self.data_changed.emit()

    # -------------------------------------------------------------- Viajes
    def _selected_trip_id(self) -> int | None:
        return self.trips_tree.selected_trip_id()

    def _trip_selection_changed(self, trip_id) -> None:
        if self.tabs.currentIndex() == 0:
            selected = trip_id is not None
            self.edit_button.setEnabled(selected)
            self.delete_button.setEnabled(selected)

    def _update_trip_check(self, trip_id: int, definition: dict, checked: bool) -> None:
        trip = self.db.work_trip(trip_id)
        if not trip:
            self.refresh_trips()
            return
        scroll = self.trips_tree.scroll.verticalScrollBar().value()
        key = definition.get("built_in_key")
        if key:
            trip[key] = checked
        else:
            trip["custom_fields"] = dict(trip.get("custom_fields") or {})
            trip["custom_fields"][int(definition["id"])] = checked
        try:
            self.db.update_work_trip(trip_id, trip)
        except Exception as exc:
            QMessageBox.warning(self, "No se pudo guardar", str(exc))
            self.refresh_trips()
        else:
            self.refresh()
            self.data_changed.emit()
        QTimer.singleShot(0, lambda: self.trips_tree.scroll.verticalScrollBar().setValue(scroll))

    def _trip_double_clicked(self, trip_id: int) -> None:
        trip = self.db.work_trip(trip_id)
        if not trip:
            return
        self._edit_trip_record(trip_id, trip)

    def new_trip(self) -> None:
        dialog = TripDialog(self.db, default_date=self._date_for_new(), parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        try:
            self.db.add_work_trip(values)
        except Exception as exc:
            QMessageBox.warning(self, "Viajes", str(exc))
            return
        self.current_week = monday_of(date.fromisoformat(values["trip_date"]))
        self._sync_date()
        self.refresh()
        self.data_changed.emit()

    def edit_trip(self) -> None:
        trip_id = self._selected_trip_id()
        if trip_id is None:
            return
        trip = self.db.work_trip(trip_id)
        if not trip:
            return
        self._edit_trip_record(trip_id, trip)

    def _edit_trip_record(self, trip_id: int, trip: dict) -> None:
        """Edita un viaje ya resuelto evitando duplicar el flujo de guardado."""
        dialog = TripDialog(self.db, trip=trip, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        try:
            self.db.update_work_trip(trip_id, values)
        except Exception as exc:
            QMessageBox.warning(self, "Viajes", str(exc))
            return
        self.current_week = monday_of(date.fromisoformat(values["trip_date"]))
        self._sync_date()
        self.refresh()
        self.data_changed.emit()

    def delete_trip(self) -> None:
        trip_id = self._selected_trip_id()
        if trip_id is None:
            return
        answer = QMessageBox.question(
            self,
            "Eliminar viaje",
            "¿Querés eliminar este viaje?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.db.delete_work_trip(trip_id)
        self.refresh()
        self.data_changed.emit()

    # --------------------------------------------------------------- Extras
    def _selected_extra_id(self) -> int | None:
        return self.extras_view.selected_extra_id()

    def _extra_double_clicked(self, extra_id: int) -> None:
        extra = self.db.work_extra(extra_id)
        if not extra:
            return
        self._edit_extra_record(extra_id, extra)

    def _extra_selection_changed(self, extra_id) -> None:
        if self.tabs.currentIndex() == 1:
            selected = extra_id is not None
            self.edit_button.setEnabled(selected)
            self.delete_button.setEnabled(selected)

    def new_extra(self) -> None:
        dialog = ExtraDialog(self.db, default_date=self._date_for_new(), parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        try:
            self.db.add_work_extra(values)
        except Exception as exc:
            QMessageBox.warning(self, "Extras", str(exc))
            return
        self.current_week = monday_of(date.fromisoformat(values["work_date"]))
        self._sync_date()
        self.refresh()
        self.data_changed.emit()

    def edit_extra(self) -> None:
        extra_id = self._selected_extra_id()
        if extra_id is None:
            return
        extra = self.db.work_extra(extra_id)
        if not extra:
            return
        self._edit_extra_record(extra_id, extra)

    def _edit_extra_record(self, extra_id: int, extra: dict) -> None:
        dialog = ExtraDialog(self.db, extra=extra, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        try:
            self.db.update_work_extra(extra_id, values)
        except Exception as exc:
            QMessageBox.warning(self, "Extras", str(exc))
            return
        self.current_week = monday_of(date.fromisoformat(values["work_date"]))
        self._sync_date()
        self.refresh()
        self.data_changed.emit()

    def delete_extra(self) -> None:
        extra_id = self._selected_extra_id()
        if extra_id is None:
            return
        answer = QMessageBox.question(
            self,
            "Eliminar extra",
            "¿Querés eliminar este registro extra?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.db.delete_work_extra(extra_id)
        self.refresh()
        self.data_changed.emit()

    # --------------------------------------------------------- Acciones tabs
    def _new_for_current_tab(self) -> None:
        self.new_trip() if self.tabs.currentIndex() == 0 else self.new_extra()

    def edit_selected(self) -> None:
        self.edit_trip() if self.tabs.currentIndex() == 0 else self.edit_extra()

    def delete_selected(self) -> None:
        self.delete_trip() if self.tabs.currentIndex() == 0 else self.delete_extra()

    def _tab_changed(self, index: int) -> None:
        trips_visible = index == 0
        self.search.setVisible(trips_visible)
        self.filter_chip.setVisible(trips_visible and self.trip_filter is not None)
        self.mileage_button.setVisible(trips_visible)
        self.customize_button.setVisible(trips_visible)
        self.add_button.setText("Nuevo viaje" if trips_visible else "Nuevo extra")
        selected = self._selected_trip_id() if trips_visible else self._selected_extra_id()
        self.edit_button.setEnabled(selected is not None)
        self.delete_button.setEnabled(selected is not None)
        if qta is not None:
            try:
                self.add_button.setIcon(qta.icon("mdi6.plus", color="#082018"))
            except Exception:
                pass
