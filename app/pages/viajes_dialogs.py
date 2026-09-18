from __future__ import annotations

"""Formularios del módulo de trabajo.

El foco está en una carga cómoda y visualmente consistente con el resto de la
app: calendarios grandes, campos responsivos y diálogo centrado en pantalla.
"""

from datetime import date

from PySide6.QtCore import QDate, QTimer, Qt
from PySide6.QtGui import QDoubleValidator, QKeyEvent
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..widgets import MoneyEdit
from ..layouts import FlowLayout
from ..utils import money
from .common import page_header
from ..work_calendar import iter_week_days, weekday_name
from ..date_picker import DatePickerButton


def _qdate(value: date) -> QDate:
    """Convierte ``datetime.date`` a ``QDate`` sin depender de strings."""
    return QDate(value.year, value.month, value.day)


class BaseWorkDialog(QDialog):
    """Base común: centrado, scroll interno y guardado cómodo con Enter."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setModal(True)
        self.setSizeGripEnabled(True)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        QTimer.singleShot(0, self.recenter_to_parent)

    def recenter_to_parent(self) -> None:
        parent = self.parentWidget().window() if self.parentWidget() else None
        screen = parent.screen() if parent is not None else QApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        width = min(max(self.minimumWidth(), self.sizeHint().width() + 24), int(available.width() * 0.92))
        height = min(max(self.minimumHeight(), self.sizeHint().height() + 24), int(available.height() * 0.92))
        self.resize(width, height)
        if parent is not None:
            center = parent.frameGeometry().center()
        else:
            center = available.center()
        frame = self.frameGeometry()
        frame.moveCenter(center)
        self.move(frame.topLeft())

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            focused = self.focusWidget()
            if isinstance(focused, QPlainTextEdit) and not (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
                super().keyPressEvent(event)
                return
            self._save()
            event.accept()
            return
        super().keyPressEvent(event)

    def _wrap_scrollable_card(self, title: str, subtitle: str) -> tuple[QVBoxLayout, QFrame]:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(14)
        root.addWidget(page_header(title, subtitle))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        root.addWidget(scroll, 1)

        host = QWidget()
        scroll.setWidget(host)
        host_layout = QVBoxLayout(host)
        host_layout.setContentsMargins(0, 0, 0, 0)
        host_layout.setSpacing(10)

        card = QFrame()
        card.setObjectName("Card")
        host_layout.addWidget(card)
        host_layout.addStretch()

        return root, card


class DistanceEdit(QLineEdit):
    """Campo decimal opcional para lecturas de odómetro.

    ``autofilled`` permite distinguir un inicio sugerido por la app de un valor
    que el usuario escribió manualmente. Así podemos encadenar jornadas sin
    pisar correcciones hechas a mano.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        validator = QDoubleValidator(0.0, 9_999_999.9, 1, self)
        validator.setNotation(QDoubleValidator.Notation.StandardNotation)
        self.setValidator(validator)
        self.setPlaceholderText("—")
        self.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.autofilled = False
        self.textEdited.connect(self._mark_manual)

    def _mark_manual(self, _text: str) -> None:
        self.autofilled = False

    def value(self) -> float | None:
        raw = self.text().strip().replace(",", ".")
        if not raw:
            return None
        return float(raw)

    def set_value(self, value: float | None, *, inferred: bool = False) -> None:
        self.autofilled = bool(inferred and value is not None)
        if value is None:
            self.clear()
            return
        text = f"{float(value):.1f}".rstrip("0").rstrip(".")
        self.setText(text)


class MileageWeekDialog(BaseWorkDialog):
    """Carga semanal de odómetro: dos lecturas por día, sin estimaciones."""

    def __init__(self, db, week_start: date, parent=None):
        super().__init__(parent)
        self.db = db
        self.week_start = week_start
        self.setWindowTitle("Kilometraje real")
        self.setMinimumSize(560, 500)
        self.resize(900, 650)

        root, card = self._wrap_scrollable_card(
            "Kilometraje real",
            "Ingresá el odómetro al comenzar y terminar cada jornada. La diferencia es el kilometraje real.",
        )

        layout = QVBoxLayout(card)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(12)

        header = QHBoxLayout()
        for title, stretch in (("Día", 2), ("KM inicial", 2), ("KM final", 2), ("Real", 2)):
            label = QLabel(title)
            label.setObjectName("FieldLabel")
            if title != "Día":
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            header.addWidget(label, stretch)
        layout.addLayout(header)

        existing = {row["work_date"]: row for row in db.work_mileage_for_week(week_start)}
        self.rows: list[dict] = []
        carry_end = db.work_last_odometer_end_before(week_start)
        for day in iter_week_days(week_start):
            row_data = existing.get(day.isoformat(), {})
            row_frame = QFrame()
            row_frame.setObjectName("SoftCard")
            row_layout = QHBoxLayout(row_frame)
            row_layout.setContentsMargins(12, 10, 12, 10)
            row_layout.setSpacing(10)

            day_label = QLabel(f"{weekday_name(day)} · {day.strftime('%d/%m')}")
            start = DistanceEdit()
            end = DistanceEdit()
            real = QLabel("—")
            real.setObjectName("SectionTitle")
            real.setAlignment(Qt.AlignmentFlag.AlignCenter)

            stored_start = row_data.get("odometer_start")
            stored_end = row_data.get("odometer_end")
            if stored_start is not None:
                start.set_value(stored_start)
            elif carry_end is not None:
                start.set_value(carry_end, inferred=True)
            end.set_value(stored_end)
            start.textChanged.connect(lambda _=None, s=start, e=end, lab=real: self._update_real_label(s, e, lab))
            end.textChanged.connect(lambda _=None, s=start, e=end, lab=real: self._update_real_label(s, e, lab))
            end.textChanged.connect(self._propagate_starts)
            self._update_real_label(start, end, real)
            carry_end = float(stored_end) if stored_end is not None else None

            row_layout.addWidget(day_label, 2)
            row_layout.addWidget(start, 2)
            row_layout.addWidget(end, 2)
            row_layout.addWidget(real, 2)
            layout.addWidget(row_frame)
            self.rows.append({"date": day, "start": start, "end": end, "real": real})

        note = QLabel(
            "Al cargar el KM final de un día, la app lo usa automáticamente como KM inicial de la próxima jornada. "
            "Podés sobrescribir cualquier inicio si necesitás corregirlo."
        )
        note.setObjectName("SmallMuted")
        note.setWordWrap(True)
        layout.addWidget(note)

        actions = QHBoxLayout()
        actions.addStretch()
        cancel = QPushButton("Cancelar")
        cancel.setObjectName("SecondaryButton")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Guardar kilometraje")
        save.clicked.connect(self._save)
        actions.addWidget(cancel)
        actions.addWidget(save)
        root.addLayout(actions)

    def _propagate_starts(self, *_args) -> None:
        """Encadena el cierre de una jornada con el inicio de la siguiente.

        Sólo se actualizan campos vacíos o previamente autocompletados. Un valor
        escrito a mano se considera una corrección explícita y nunca se pisa.
        """
        carry = self.db.work_last_odometer_end_before(self.week_start)
        for row in self.rows:
            start: DistanceEdit = row["start"]
            end: DistanceEdit = row["end"]
            try:
                current_start = start.value()
            except ValueError:
                current_start = None
            if start.autofilled or current_start is None:
                if carry is None:
                    if start.autofilled:
                        start.set_value(None)
                else:
                    start.set_value(carry, inferred=True)
                self._update_real_label(start, end, row["real"])
            try:
                carry = end.value()
            except ValueError:
                carry = None

    @staticmethod
    def _update_real_label(start: DistanceEdit, end: DistanceEdit, label: QLabel) -> None:
        try:
            start_value = start.value()
            end_value = end.value()
        except ValueError:
            label.setText("—")
            return
        if start_value is None or end_value is None or end_value < start_value:
            label.setText("—")
            return
        label.setText(f"{end_value - start_value:.1f} km")

    def _save(self) -> None:
        try:
            for row in self.rows:
                self.db.set_work_day_mileage(row["date"], row["start"].value(), row["end"].value())
        except Exception as exc:
            QMessageBox.warning(self, "Kilometraje", str(exc))
            return
        self.accept()


class TripDialog(BaseWorkDialog):
    """Alta/edición de un viaje con campos y tarifas configurables."""

    BUILTIN_KEYS = {"bulky", "rain", "flex", "own_client"}

    def __init__(self, db, trip: dict | None = None, default_date: date | None = None, parent=None):
        super().__init__(parent)
        self.db = db
        self.trip = trip
        self.all_field_definitions = db.work_field_definitions(active_only=False)
        self.field_definitions = [
            row for row in self.all_field_definitions if bool(row.get("active", 1))
        ]
        self.field_widgets: dict[int, QWidget] = {}
        self._original_custom_values: dict[int, object] = dict((trip or {}).get("custom_fields") or {})
        self.setWindowTitle("Editar viaje" if trip else "Nuevo viaje")
        self.setMinimumSize(560, 560)
        self.resize(860, 780)

        root, card = self._wrap_scrollable_card(
            "Editar viaje" if trip else "Nuevo viaje",
            "La fecha ubica automáticamente el viaje en su semana. Los campos visibles se pueden personalizar desde Viajes.",
        )
        form = self._create_form(card)
        self._build_base_fields(form, default_date)
        self._build_custom_fields(form)
        self._build_rate_fields(form)
        self._build_details_fields(form)
        self._build_actions(root)

        if trip:
            self._load_trip(trip)
        else:
            self._sync_stop_count_display()
            self._sync_rate_ui()

    @staticmethod
    def _create_form(card: QWidget) -> QFormLayout:
        form = QFormLayout(card)
        form.setContentsMargins(22, 18, 22, 18)
        form.setSpacing(12)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        return form

    def _build_base_fields(self, form: QFormLayout, default_date: date | None) -> None:
        self.client = QLineEdit()
        self.client.setPlaceholderText("Ej. Cliente / comercio")
        self.origin = QLineEdit()
        self.origin.setPlaceholderText("Punto de retiro o inicio")
        self.destinations = QPlainTextEdit()
        self.destinations.setPlaceholderText("Un destino por línea")
        self.destinations.setMinimumHeight(130)
        self.destinations.textChanged.connect(self._sync_stop_count_display)
        self.trip_date = DatePickerButton(_qdate(default_date or date.today()))
        self.stop_count = QLineEdit("1")
        self.stop_count.setReadOnly(True)
        self.stop_count.setMinimumHeight(42)

        count_hint = QLabel("Cada línea en Destinos equivale a una parada del recorrido.")
        count_hint.setObjectName("SmallMuted")
        count_hint.setWordWrap(True)
        for label, widget in (
            ("Cliente", self.client),
            ("Origen", self.origin),
            ("Destino(s)", self.destinations),
            ("Fecha", self.trip_date),
            ("Paradas", self.stop_count),
        ):
            form.addRow(label, widget)
        form.addRow("", count_hint)

    def _create_custom_field_widget(self, definition: dict) -> tuple[QWidget, bool]:
        ui_type = str(definition.get("ui_type") or definition.get("field_type") or "text")
        label = str(definition.get("label") or "Campo")
        if ui_type == "check":
            return QCheckBox(label), True
        if ui_type == "number":
            widget = QDoubleSpinBox()
            widget.setRange(-999_999_999, 999_999_999)
            widget.setDecimals(2)
            widget.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
            return widget, False
        if ui_type == "money":
            widget = MoneyEdit(self.db.currency_symbol())
            widget.setProperty("compact", True)
            widget.setPlaceholderText("0")
            return widget, False
        if ui_type == "long_text":
            widget = QPlainTextEdit()
            widget.setPlaceholderText(label)
            widget.setMaximumHeight(100)
            return widget, False
        if ui_type == "choice":
            widget = QComboBox()
            widget.addItem("Seleccionar…", "")
            for option in definition.get("options") or []:
                widget.addItem(str(option), str(option))
            return widget, False

        widget = QLineEdit()
        if ui_type == "email":
            widget.setPlaceholderText("nombre@correo.com")
            widget.setInputMethodHints(Qt.InputMethodHint.ImhEmailCharactersOnly)
        elif ui_type == "phone":
            widget.setPlaceholderText("Teléfono / contacto")
            widget.setInputMethodHints(Qt.InputMethodHint.ImhDialableCharactersOnly)
        else:
            widget.setPlaceholderText(label)
        return widget, False

    def _build_custom_fields(self, form: QFormLayout) -> None:
        checks_host = QWidget()
        checks_layout = FlowLayout(checks_host, horizontal_spacing=8, vertical_spacing=7)
        non_check_rows: list[tuple[str, QWidget]] = []
        has_checks = False
        for definition in self.field_definitions:
            field_id = int(definition["id"])
            label = str(definition.get("label") or "Campo")
            widget, is_check = self._create_custom_field_widget(definition)
            self.field_widgets[field_id] = widget
            if is_check:
                checks_layout.addWidget(widget)
                has_checks = True
            else:
                non_check_rows.append((label, widget))
        if has_checks:
            form.addRow("Etiquetas", checks_host)
        for label, widget in non_check_rows:
            form.addRow(label, widget)

    def _build_rate_fields(self, form: QFormLayout) -> None:
        self.rate_scheme = QComboBox()
        self.rate_scheme.addItem("Sin tarifa automática", None)
        self.rate_schemes = self.db.work_rate_schemes(active_only=True)
        for scheme in self.rate_schemes:
            self.rate_scheme.addItem(str(scheme.get("name") or "Tarifa"), int(scheme["id"]))

        self.rate_quantity = QDoubleSpinBox()
        self.rate_quantity.setRange(0, 1_000_000)
        self.rate_quantity.setDecimals(2)
        self.rate_quantity.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.rate_quantity.setVisible(False)
        self.rate_option = QComboBox()
        self.rate_option.setVisible(False)
        self.rate_total = QLabel("—")
        self.rate_total.setObjectName("SectionTitle")
        self.rate_total.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        rate_box = QFrame()
        rate_box.setObjectName("SoftCard")
        rate_layout = QVBoxLayout(rate_box)
        rate_layout.setContentsMargins(12, 10, 12, 10)
        rate_layout.setSpacing(10)
        rate_layout.addWidget(self.rate_scheme)

        self.rate_factor_row = QWidget()
        factor_layout = QGridLayout(self.rate_factor_row)
        factor_layout.setContentsMargins(0, 0, 0, 0)
        factor_layout.setHorizontalSpacing(10)
        factor_layout.setVerticalSpacing(6)
        self.rate_factor_label = QLabel("Cantidad")
        self.rate_factor_label.setObjectName("SmallMuted")
        self.rate_price_caption = QLabel("Tarifa")
        self.rate_price_caption.setObjectName("SmallMuted")
        self.rate_price_value = QLabel("—")
        self.rate_price_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rate_total_caption = QLabel("Total calculado")
        self.rate_total_caption.setObjectName("SmallMuted")

        factor_layout.addWidget(self.rate_factor_label, 0, 0)
        factor_layout.addWidget(self.rate_price_caption, 0, 1)
        factor_layout.addWidget(self.rate_total_caption, 0, 2)
        factor_layout.addWidget(self.rate_quantity, 1, 0)
        factor_layout.addWidget(self.rate_option, 1, 0, 1, 2)
        factor_layout.addWidget(self.rate_price_value, 1, 1)
        factor_layout.addWidget(self.rate_total, 1, 2)
        factor_layout.setColumnStretch(0, 2)
        factor_layout.setColumnStretch(1, 1)
        factor_layout.setColumnStretch(2, 1)

        self.rate_apply = QPushButton("Usar como cobrado")
        self.rate_apply.setObjectName("SecondaryButton")
        self.rate_apply.setVisible(False)
        self.rate_apply.clicked.connect(self._copy_rate_to_charged)
        factor_layout.addWidget(self.rate_apply, 2, 0, 1, 3, Qt.AlignmentFlag.AlignLeft)
        rate_layout.addWidget(self.rate_factor_row)
        self.rate_factor_row.setVisible(False)
        form.addRow("Tarifa", rate_box)
        self.rate_scheme.currentIndexChanged.connect(self._sync_rate_ui)
        self.rate_quantity.valueChanged.connect(self._update_rate_total)
        self.rate_option.currentIndexChanged.connect(self._update_rate_total)

    def _build_details_fields(self, form: QFormLayout) -> None:
        self.details = QPlainTextEdit()
        self.details.setPlaceholderText("Demora, observaciones, incidencias…")
        self.details.setMinimumHeight(105)
        self.charged = MoneyEdit(self.db.currency_symbol())
        self.charged.setMinimumHeight(42)
        self.charged.setProperty("compact", True)
        self.charged.setPlaceholderText("Dejar vacío si no corresponde")
        form.addRow("Detalles", self.details)
        form.addRow("Cobrado", self.charged)
        hint = QLabel("La tarifa calculada es informativa; Cobrado sigue siendo un valor independiente.")
        hint.setObjectName("SmallMuted")
        hint.setWordWrap(True)
        form.addRow("", hint)

    def _build_actions(self, root: QVBoxLayout) -> None:
        self.register_income = QCheckBox('Registrar lo cobrado como ingreso al guardar')
        root.addWidget(self.register_income)
        actions = QHBoxLayout()
        actions.addStretch()
        cancel = QPushButton("Cancelar")
        cancel.setObjectName("SecondaryButton")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Guardar viaje")
        save.clicked.connect(self._save)
        actions.addWidget(cancel)
        actions.addWidget(save)
        root.addLayout(actions)

    def _definition_by_builtin(self, key: str) -> dict | None:
        return next((d for d in self.field_definitions if d.get("built_in_key") == key), None)

    def _widget_for_builtin(self, key: str) -> QWidget | None:
        definition = self._definition_by_builtin(key)
        return self.field_widgets.get(int(definition["id"])) if definition else None

    def _detected_stop_count(self) -> int:
        destinations = [line.strip() for line in self.destinations.toPlainText().splitlines() if line.strip()]
        return max(1, len(destinations) or 1)

    def _sync_stop_count_display(self) -> None:
        self.stop_count.setText(str(self._detected_stop_count()))

    def _current_scheme(self) -> dict | None:
        scheme_id = self.rate_scheme.currentData()
        if not scheme_id:
            return None
        return next((s for s in self.rate_schemes if int(s["id"]) == int(scheme_id)), None)

    def _sync_rate_ui(self) -> None:
        scheme = self._current_scheme()
        if not scheme:
            self.rate_factor_row.setVisible(False)
            self.rate_total.setText("—")
            self.rate_apply.setVisible(False)
            return
        self.rate_factor_row.setVisible(True)
        is_unit = scheme.get("mode") == "unit"
        self.rate_quantity.setVisible(is_unit)
        self.rate_option.setVisible(not is_unit)
        self.rate_price_caption.setVisible(is_unit)
        self.rate_price_value.setVisible(is_unit)
        if is_unit:
            unit_label = str(scheme.get("unit_label") or "unidad")
            self.rate_factor_label.setText(f"Cantidad ({unit_label})")
            self.rate_price_value.setText(
                f"{money(float(scheme.get('unit_rate') or 0), self.db.currency_symbol(), False)} / {unit_label}"
            )
        else:
            self.rate_factor_label.setText("Opción")
            current = self.rate_option.currentData()
            self.rate_option.blockSignals(True)
            self.rate_option.clear()
            self.rate_option.addItem("Seleccionar…", None)
            for option in scheme.get("options") or []:
                self.rate_option.addItem(str(option.get("label") or "Opción"), int(option["id"]))
            idx = self.rate_option.findData(current)
            if idx >= 0:
                self.rate_option.setCurrentIndex(idx)
            self.rate_option.blockSignals(False)
        self._update_rate_total()

    def _update_rate_total(self) -> None:
        scheme_id = self.rate_scheme.currentData()
        quantity = self.rate_quantity.value() if self.rate_quantity.isVisible() else None
        option_id = self.rate_option.currentData() if self.rate_option.isVisible() else None
        total = self.db.calculate_work_rate(scheme_id, quantity, option_id)
        self._calculated_rate_total = total
        self.rate_total.setText(money(total, self.db.currency_symbol(), False) if total is not None else "—")
        self.rate_apply.setVisible(total is not None)

    def _copy_rate_to_charged(self) -> None:
        total = getattr(self, "_calculated_rate_total", None)
        if total is not None:
            self.charged.setValue(float(total))

    def _load_trip(self, trip: dict) -> None:
        self.client.setText(trip.get("client") or "")
        self.origin.setText(trip.get("origin") or "")
        self.destinations.setPlainText("\n".join(trip.get("destinations") or []))
        try:
            self.trip_date.setDate(_qdate(date.fromisoformat(trip["trip_date"])))
        except Exception:
            pass
        custom_values = trip.get("custom_fields") or {}
        for definition in self.field_definitions:
            field_id = int(definition["id"])
            widget = self.field_widgets.get(field_id)
            if widget is None:
                continue
            built_in = definition.get("built_in_key")
            value = trip.get(built_in) if built_in else custom_values.get(field_id)
            ui_type = str(definition.get("ui_type") or definition.get("field_type") or "text")
            if ui_type == "check":
                widget.setChecked(bool(value))
            elif ui_type == "number":
                widget.setValue(float(value or 0))
            elif ui_type == "money":
                if value not in (None, ""):
                    widget.setValue(float(value))
            elif ui_type == "long_text":
                widget.setPlainText(str(value or ""))
            elif ui_type == "choice":
                idx = widget.findData(str(value or ""))
                if idx < 0 and value not in (None, ""):
                    widget.addItem(str(value), str(value))
                    idx = widget.findData(str(value))
                widget.setCurrentIndex(max(0, idx))
            else:
                widget.setText(str(value or ""))
        self._sync_stop_count_display()
        self.details.setPlainText(trip.get("details") or "")
        if trip.get("charged") is not None:
            self.charged.setValue(float(trip.get("charged") or 0))
        if trip.get("rate_scheme_id"):
            idx = self.rate_scheme.findData(int(trip["rate_scheme_id"]))
            if idx >= 0:
                self.rate_scheme.setCurrentIndex(idx)
                self._sync_rate_ui()
                if trip.get("rate_quantity") is not None:
                    self.rate_quantity.setValue(float(trip.get("rate_quantity") or 0))
                if trip.get("rate_option_id") is not None:
                    historical_option_id = int(trip["rate_option_id"])
                    opt_idx = self.rate_option.findData(historical_option_id)
                    if opt_idx < 0 and trip.get("rate_option"):
                        historical_label = str(trip["rate_option"].get("label") or "Opción histórica")
                        self.rate_option.addItem(f"{historical_label} (histórica)", historical_option_id)
                        opt_idx = self.rate_option.findData(historical_option_id)
                    if opt_idx >= 0:
                        self.rate_option.setCurrentIndex(opt_idx)
                self._update_rate_total()

    def _save(self) -> None:
        if not self.client.text().strip():
            QMessageBox.warning(self, "Dato faltante", "Ingresá el cliente.")
            self.client.setFocus()
            return
        for definition in self.field_definitions:
            if str(definition.get("ui_type") or "") != "email":
                continue
            widget = self.field_widgets.get(int(definition["id"]))
            value = widget.text().strip() if widget is not None else ""
            if value and ("@" not in value or value.startswith("@") or value.endswith("@")):
                QMessageBox.warning(self, "Email", f"Revisá el campo {definition.get('label') or 'Email'}.")
                widget.setFocus()
                return
        self.accept()

    def values(self) -> dict:
        destinations = [line.strip() for line in self.destinations.toPlainText().splitlines() if line.strip()]
        charged = self.charged.value() if self.charged.text().strip() else None
        # Valores ocultos/inactivos se preservan al editar. Ocultar un campo es
        # una decisión visual, no una orden para borrar el historial del viaje.
        original = self.trip or {}
        result = {
            "client": self.client.text().strip(),
            "origin": self.origin.text().strip(),
            "destinations": destinations,
            "trip_date": self.trip_date.date().toString("yyyy-MM-dd"),
            "stop_count": max(1, len(destinations) or 1),
            "bulky": bool(original.get("bulky", False)),
            "rain": bool(original.get("rain", False)),
            "flex": bool(original.get("flex", False)),
            "own_client": bool(original.get("own_client", False)),
            "details": self.details.toPlainText().strip(),
            "charged": charged,
            "custom_fields": dict(self._original_custom_values),
            "rate_scheme_id": self.rate_scheme.currentData(),
            "rate_quantity": self.rate_quantity.value() if self.rate_quantity.isVisible() else None,
            "rate_option_id": self.rate_option.currentData() if self.rate_option.isVisible() else None,
        }
        for definition in self.field_definitions:
            field_id = int(definition["id"])
            widget = self.field_widgets.get(field_id)
            if widget is None:
                continue
            ui_type = str(definition.get("ui_type") or definition.get("field_type") or "text")
            if ui_type == "check":
                value = widget.isChecked()
            elif ui_type == "number":
                value = widget.value()
            elif ui_type == "money":
                value = widget.value() if widget.text().strip() else None
            elif ui_type == "long_text":
                value = widget.toPlainText().strip()
            elif ui_type == "choice":
                value = widget.currentData() or ""
            else:
                value = widget.text().strip()
            built_in = definition.get("built_in_key")
            if built_in in self.BUILTIN_KEYS:
                result[built_in] = bool(value)
            else:
                result["custom_fields"][field_id] = value
        return result


class ExtraDialog(BaseWorkDialog):
    """Alta/edición de horas e ingresos hechos mediante una aplicación."""

    DEFAULT_APPS = ("PedidosYa", "Rappi", "Uber", "Cabify", "DiDi", "Otra")

    def __init__(self, db, extra: dict | None = None, default_date: date | None = None, parent=None):
        super().__init__(parent)
        self.db = db
        self.extra = extra
        self.setWindowTitle("Editar extra" if extra else "Nuevo extra")
        self.setMinimumSize(540, 480)
        self.resize(760, 620)

        root, card = self._wrap_scrollable_card(
            "Editar extra" if extra else "Nuevo extra",
            "Registrá tiempo e ingresos de PedidosYa, Rappi u otras aplicaciones.",
        )

        form = QFormLayout(card)
        form.setContentsMargins(22, 18, 22, 18)
        form.setSpacing(12)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)

        self.app_name = QComboBox()
        self.app_name.setEditable(True)
        saved_apps = self.db.work_extra_apps()
        for name in dict.fromkeys((*self.DEFAULT_APPS, *saved_apps)):
            self.app_name.addItem(name)
        self.app_name.setCurrentText("")
        if self.app_name.lineEdit():
            self.app_name.lineEdit().setPlaceholderText("Ej. PedidosYa")

        self.work_date = DatePickerButton(_qdate(default_date or date.today()))

        self.hours = QDoubleSpinBox()
        self.hours.setRange(0, 24)
        self.hours.setDecimals(2)
        self.hours.setSingleStep(0.5)
        self.hours.setSuffix(" h")
        self.hours.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)

        self.orders = QSpinBox()
        self.orders.setRange(0, 999)
        self.orders.setToolTip("Ingresá la cantidad. Usá 0 si no querés especificarla.")
        self.orders.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)

        self.amount = MoneyEdit(db.currency_symbol())
        self.amount.setMinimumHeight(42)
        self.amount.setProperty("compact", True)
        self.amount.setPlaceholderText("0")

        self.details = QPlainTextEdit()
        self.details.setMinimumHeight(120)
        self.details.setPlaceholderText("Turno, zona, propinas, observaciones…")

        info = QLabel("Podés dejar pedidos en 0 si sólo querés registrar horas e ingreso.")
        info.setObjectName("SmallMuted")
        info.setWordWrap(True)

        form.addRow("Aplicación", self.app_name)
        form.addRow("Fecha", self.work_date)
        form.addRow("Horas trabajadas", self.hours)
        form.addRow("Pedidos / viajes", self.orders)
        form.addRow("Ganado", self.amount)
        form.addRow("Detalles", self.details)
        form.addRow("", info)

        self.register_income = QCheckBox('Registrar lo ganado como ingreso al guardar')
        root.addWidget(self.register_income)

        actions = QHBoxLayout()
        actions.addStretch()
        cancel = QPushButton("Cancelar")
        cancel.setObjectName("SecondaryButton")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Guardar extra")
        save.clicked.connect(self._save)
        actions.addWidget(cancel)
        actions.addWidget(save)
        root.addLayout(actions)

        if extra:
            self._load_extra(extra)

    def _load_extra(self, extra: dict) -> None:
        self.app_name.setCurrentText(extra.get("app_name") or "")
        try:
            self.work_date.setDate(_qdate(date.fromisoformat(extra["work_date"])))
        except Exception:
            pass
        self.hours.setValue(float(extra.get("hours") or 0))
        self.orders.setValue(int(extra.get("orders") or 0))
        self.amount.setValue(float(extra.get("amount") or 0))
        self.details.setPlainText(extra.get("details") or "")

    def _save(self) -> None:
        if not self.app_name.currentText().strip():
            QMessageBox.warning(self, "Dato faltante", "Ingresá la aplicación.")
            self.app_name.setFocus()
            return
        self.accept()

    def values(self) -> dict:
        return {
            "app_name": self.app_name.currentText().strip(),
            "work_date": self.work_date.date().toString("yyyy-MM-dd"),
            "hours": self.hours.value(),
            "orders": self.orders.value(),
            "amount": self.amount.value(),
            "details": self.details.toPlainText().strip(),
        }
