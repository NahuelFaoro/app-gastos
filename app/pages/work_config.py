from __future__ import annotations

"""Configuración editable de la herramienta Viajes.

La configuración vive fuera de la pantalla operativa para mantener Viajes
simple. Los editores usan componentes responsivos y controles explícitos: no se
requieren formatos de texto del tipo ``Zona = precio``.
"""

from dataclasses import dataclass

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..layouts import FlowLayout
from ..ui_helpers import fit_dialog_to_screen, make_icon_button, make_reorder_actions
from ..widgets import MoneyEdit, SlideSwitch
from .common import page_header


FIELD_TYPES = (
    ("Sí / No", "check"),
    ("Texto corto", "text"),
    ("Texto largo", "long_text"),
    ("Número", "number"),
    ("Importe / precio", "money"),
    ("Email", "email"),
    ("Teléfono / contacto", "phone"),
    ("Lista de opciones", "choice"),
)



def _icon_button(icon_name: str, fallback: str, tooltip: str, danger: bool = False) -> QPushButton:
    return make_icon_button(icon_name, fallback, tooltip, danger=danger)



class ChoiceOptionsEditor(QFrame):
    """Lista editable de opciones de texto, una fila por valor."""

    def __init__(self, values: list[str] | None = None, parent=None):
        super().__init__(parent)
        self.setObjectName("WorkConfigInset")
        self.rows: list[tuple[QWidget, QLineEdit]] = []
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 9, 10, 9)
        root.setSpacing(6)
        self.rows_layout = QVBoxLayout()
        self.rows_layout.setSpacing(6)
        root.addLayout(self.rows_layout)
        add = QPushButton("＋ Agregar opción")
        add.setObjectName("SecondaryButton")
        add.clicked.connect(lambda: self.add_option(""))
        root.addWidget(add, 0, Qt.AlignmentFlag.AlignLeft)
        for value in values or []:
            self.add_option(str(value))
        if not self.rows:
            self.add_option("")

    def add_option(self, value: str) -> None:
        host = QWidget()
        row = QHBoxLayout(host)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(7)
        edit = QLineEdit(value)
        edit.setPlaceholderText("Nombre de la opción")
        remove = _icon_button("fa6s.trash", "×", "Eliminar opción", True)
        remove.clicked.connect(lambda: self._remove(host, edit))
        row.addWidget(edit, 1)
        row.addWidget(remove)
        self.rows_layout.addWidget(host)
        self.rows.append((host, edit))

    def _remove(self, host: QWidget, edit: QLineEdit) -> None:
        try:
            self.rows.remove((host, edit))
        except ValueError:
            return
        host.deleteLater()
        if not self.rows:
            self.add_option("")

    def values(self) -> list[str]:
        return [edit.text().strip() for _, edit in self.rows if edit.text().strip()]


class RateOptionsEditor(QFrame):
    """Opciones de una tarifa por zona/lista con nombre y precio separados."""

    def __init__(self, db, values: list[dict] | None = None, parent=None):
        super().__init__(parent)
        self.db = db
        self.setObjectName("WorkConfigInset")
        self.rows: list[tuple[QWidget, QLineEdit, MoneyEdit]] = []
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 9, 10, 9)
        root.setSpacing(7)
        heading = QHBoxLayout()
        a = QLabel("Opción")
        b = QLabel("Tarifa")
        a.setObjectName("SmallMuted")
        b.setObjectName("SmallMuted")
        heading.addWidget(a, 2)
        heading.addWidget(b, 1)
        heading.addSpacing(42)
        root.addLayout(heading)
        self.rows_layout = QVBoxLayout()
        self.rows_layout.setSpacing(6)
        root.addLayout(self.rows_layout)
        add = QPushButton("＋ Agregar opción")
        add.setObjectName("SecondaryButton")
        add.clicked.connect(lambda: self.add_option("", 0))
        root.addWidget(add, 0, Qt.AlignmentFlag.AlignLeft)
        for option in values or []:
            self.add_option(str(option.get("label") or ""), float(option.get("rate") or 0))
        if not self.rows:
            self.add_option("", 0)

    def add_option(self, label: str, rate: float) -> None:
        host = QWidget()
        row = QHBoxLayout(host)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(7)
        name = QLineEdit(label)
        name.setPlaceholderText("Ej. Zona 2")
        amount = MoneyEdit(self.db.currency_symbol())
        amount.setProperty("compact", True)
        amount.setMinimumWidth(125)
        if rate:
            amount.setValue(rate)
        remove = _icon_button("fa6s.trash", "×", "Eliminar opción", True)
        remove.clicked.connect(lambda: self._remove(host, name, amount))
        row.addWidget(name, 2)
        row.addWidget(amount, 1)
        row.addWidget(remove)
        self.rows_layout.addWidget(host)
        self.rows.append((host, name, amount))

    def _remove(self, host: QWidget, name: QLineEdit, amount: MoneyEdit) -> None:
        try:
            self.rows.remove((host, name, amount))
        except ValueError:
            return
        host.deleteLater()
        if not self.rows:
            self.add_option("", 0)

    def values(self) -> list[dict]:
        result: list[dict] = []
        for _, name, amount in self.rows:
            label = name.text().strip()
            if not label:
                continue
            result.append({"label": label, "rate": float(amount.value())})
        return result


@dataclass
class FieldEditorRow:
    frame: QFrame
    field_id: int | None
    built_in_key: str | None
    name: QLineEdit
    field_type: QComboBox
    active: SlideSwitch
    summary: SlideSwitch
    options: ChoiceOptionsEditor
    up: QPushButton
    down: QPushButton


class WorkFieldsTab(QWidget):
    """Editor funcional de campos configurables usados por los viajes."""

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.rows: list[FieldEditorRow] = []
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        help_text = QLabel(
            "Cada campo define qué control aparece al crear un viaje. Podés usar Sí/No, texto, número, importe, email, teléfono o una lista de opciones."
        )
        help_text.setObjectName("SmallMuted")
        help_text.setWordWrap(True)
        root.addWidget(help_text)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        root.addWidget(self.scroll, 1)
        host = QWidget()
        self.rows_layout = QVBoxLayout(host)
        self.rows_layout.setContentsMargins(0, 0, 6, 0)
        self.rows_layout.setSpacing(9)
        self.rows_layout.addStretch(1)
        self.scroll.setWidget(host)

        add = QPushButton("＋ Agregar campo")
        add.setObjectName("SecondaryButton")
        add.clicked.connect(lambda: self._add_row(None))
        root.addWidget(add, 0, Qt.AlignmentFlag.AlignLeft)
        for data in self.db.work_field_definitions():
            self._add_row(data)
        self._refresh_order_buttons()

    def _add_row(self, data: dict | None) -> None:
        frame = QFrame()
        frame.setObjectName("WorkConfigCard")
        root = QVBoxLayout(frame)
        root.setContentsMargins(13, 11, 13, 11)
        root.setSpacing(9)

        top_host = QWidget()
        top = FlowLayout(top_host, horizontal_spacing=9, vertical_spacing=8)
        name = QLineEdit()
        name.setPlaceholderText("Nombre del campo")
        name.setMinimumWidth(220)
        field_type = QComboBox()
        field_type.setMinimumWidth(170)
        for label, value in FIELD_TYPES:
            field_type.addItem(label, value)
        top.addWidget(name)
        top.addWidget(field_type)

        switches_host = QWidget()
        switches_host.setMinimumWidth(170)
        switches = QVBoxLayout(switches_host)
        switches.setContentsMargins(0, 0, 0, 0)
        switches.setSpacing(5)
        active = SlideSwitch()
        summary = SlideSwitch()
        active_row = QHBoxLayout()
        active_row.addWidget(QLabel("Activo"), 1)
        active_row.addWidget(active)
        summary_row = QHBoxLayout()
        summary_row.addWidget(QLabel("Mostrar en resumen"), 1)
        summary_row.addWidget(summary)
        switches.addLayout(active_row)
        switches.addLayout(summary_row)
        top.addWidget(switches_host)

        actions = make_reorder_actions("Eliminar campo")
        up, down, remove = actions.up, actions.down, actions.remove
        top.addWidget(actions.host)
        root.addWidget(top_host)

        options = ChoiceOptionsEditor((data or {}).get("options") or [])
        root.addWidget(options)

        field_id = int(data["id"]) if data else None
        built_in = str(data.get("built_in_key") or "") if data else ""
        if data:
            name.setText(str(data.get("label") or ""))
            ui_type = str(data.get("ui_type") or data.get("field_type") or "text")
            idx = field_type.findData(ui_type)
            field_type.setCurrentIndex(max(0, idx))
            active.setChecked(bool(data.get("active", 1)))
            summary.setChecked(bool(data.get("show_in_summary", 0)))
        else:
            field_type.setCurrentIndex(field_type.findData("text"))
            active.setChecked(True)
            summary.setChecked(False)
        field_type.setEnabled(not bool(built_in))
        remove.setEnabled(not bool(built_in))

        row = FieldEditorRow(frame, field_id, built_in or None, name, field_type, active, summary, options, up, down)
        self.rows.append(row)
        self.rows_layout.insertWidget(self.rows_layout.count() - 1, frame)

        def sync_type() -> None:
            ui_type = str(field_type.currentData() or "text")
            options.setVisible(ui_type == "choice")
            summary.setEnabled(ui_type == "check")
            if ui_type != "check":
                summary.setChecked(False)

        field_type.currentIndexChanged.connect(sync_type)
        sync_type()
        up.clicked.connect(lambda: self._move(row, -1))
        down.clicked.connect(lambda: self._move(row, 1))
        remove.clicked.connect(lambda: self._remove(row))
        self._refresh_order_buttons()

    def _rebuild_order(self) -> None:
        for row in self.rows:
            self.rows_layout.removeWidget(row.frame)
        for row in self.rows:
            self.rows_layout.insertWidget(self.rows_layout.count() - 1, row.frame)
        self._refresh_order_buttons()

    def _refresh_order_buttons(self) -> None:
        total = len(self.rows)
        for index, row in enumerate(self.rows):
            row.up.setEnabled(index > 0)
            row.down.setEnabled(index < total - 1)

    def _move(self, row: FieldEditorRow, delta: int) -> None:
        if row not in self.rows:
            return
        index = self.rows.index(row)
        target = max(0, min(len(self.rows) - 1, index + int(delta)))
        if target == index:
            return
        self.rows[index], self.rows[target] = self.rows[target], self.rows[index]
        self._rebuild_order()

    def _remove(self, row: FieldEditorRow) -> None:
        if row.built_in_key:
            return
        if row.field_id:
            try:
                self.db.delete_work_field_definition(row.field_id)
            except Exception as exc:
                QMessageBox.warning(self, "Campos", str(exc))
                return
        if row in self.rows:
            self.rows.remove(row)
        row.frame.deleteLater()
        self._refresh_order_buttons()

    def save(self) -> None:
        ids: list[int] = []
        for row in self.rows:
            field_id = self.db.save_work_field_definition(
                {
                    "label": row.name.text().strip(),
                    "ui_type": row.field_type.currentData(),
                    "options": row.options.values(),
                    "active": row.active.isChecked(),
                    "show_in_summary": row.summary.isChecked(),
                },
                row.field_id,
            )
            row.field_id = field_id
            ids.append(field_id)
        self.db.reorder_work_fields(ids)


@dataclass
class RateEditorRow:
    frame: QFrame
    scheme_id: int | None
    name: QLineEdit
    mode: QComboBox
    unit_label: QLineEdit
    unit_rate: MoneyEdit
    options: RateOptionsEditor
    active: SlideSwitch
    up: QPushButton
    down: QPushButton


class WorkRatesTab(QWidget):
    """Editor de tarifas por unidad o por opción con inputs estructurados."""

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.rows: list[RateEditorRow] = []
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)
        help_text = QLabel(
            "Por unidad: cantidad × tarifa. Por opción: elegís una opción con precio fijo. Los precios se configuran en campos separados."
        )
        help_text.setObjectName("SmallMuted")
        help_text.setWordWrap(True)
        root.addWidget(help_text)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        root.addWidget(scroll, 1)
        host = QWidget()
        self.rows_layout = QVBoxLayout(host)
        self.rows_layout.setContentsMargins(0, 0, 6, 0)
        self.rows_layout.setSpacing(9)
        self.rows_layout.addStretch(1)
        scroll.setWidget(host)
        add = QPushButton("＋ Agregar tarifa")
        add.setObjectName("SecondaryButton")
        add.clicked.connect(lambda: self._add_row(None))
        root.addWidget(add, 0, Qt.AlignmentFlag.AlignLeft)
        for data in self.db.work_rate_schemes():
            self._add_row(data)
        self._refresh_order_buttons()

    def _add_row(self, data: dict | None) -> None:
        frame = QFrame()
        frame.setObjectName("WorkConfigCard")
        root = QVBoxLayout(frame)
        root.setContentsMargins(13, 11, 13, 11)
        root.setSpacing(9)
        top_host = QWidget()
        top = FlowLayout(top_host, horizontal_spacing=9, vertical_spacing=8)
        name = QLineEdit()
        name.setPlaceholderText("Nombre de la tarifa")
        name.setMinimumWidth(220)
        mode = QComboBox()
        mode.setMinimumWidth(170)
        mode.addItem("Por unidad", "unit")
        mode.addItem("Por opción", "option")
        top.addWidget(name)
        top.addWidget(mode)
        active_host = QWidget()
        active_host.setMinimumWidth(130)
        active_box = QVBoxLayout(active_host)
        active_box.setContentsMargins(0, 0, 0, 0)
        active_row = QHBoxLayout()
        active = SlideSwitch()
        active_row.addWidget(QLabel("Activa"), 1)
        active_row.addWidget(active)
        active_box.addLayout(active_row)
        active_box.addStretch()
        top.addWidget(active_host)
        actions = make_reorder_actions("Eliminar tarifa")
        up, down, remove = actions.up, actions.down, actions.remove
        top.addWidget(actions.host)
        root.addWidget(top_host)

        unit_host = QFrame()
        unit_host.setObjectName("WorkConfigInset")
        unit_layout = FlowLayout(unit_host, margin=10, horizontal_spacing=8, vertical_spacing=7)
        unit_label = QLineEdit()
        unit_label.setPlaceholderText("Unidad, ej. km")
        unit_label.setMinimumWidth(180)
        unit_rate = MoneyEdit(self.db.currency_symbol())
        unit_rate.setProperty("compact", True)
        unit_rate.setPlaceholderText("Tarifa por unidad")
        unit_rate.setMinimumWidth(180)
        unit_layout.addWidget(unit_label)
        unit_layout.addWidget(unit_rate)
        root.addWidget(unit_host)

        options = RateOptionsEditor(self.db, (data or {}).get("options") or [])
        root.addWidget(options)

        row = RateEditorRow(frame, int(data["id"]) if data else None, name, mode, unit_label, unit_rate, options, active, up, down)
        self.rows.append(row)
        self.rows_layout.insertWidget(self.rows_layout.count() - 1, frame)
        if data:
            name.setText(str(data.get("name") or ""))
            idx = mode.findData(data.get("mode"))
            mode.setCurrentIndex(max(0, idx))
            unit_label.setText(str(data.get("unit_label") or ""))
            unit_rate.setValue(float(data.get("unit_rate") or 0))
            active.setChecked(bool(data.get("active", 1)))
        else:
            active.setChecked(True)
            unit_label.setText("unidad")

        def sync_mode() -> None:
            is_unit = mode.currentData() == "unit"
            unit_host.setVisible(is_unit)
            options.setVisible(not is_unit)

        mode.currentIndexChanged.connect(sync_mode)
        sync_mode()
        up.clicked.connect(lambda: self._move(row, -1))
        down.clicked.connect(lambda: self._move(row, 1))
        remove.clicked.connect(lambda: self._remove(row))
        self._refresh_order_buttons()

    def _refresh_order_buttons(self) -> None:
        total = len(self.rows)
        for index, row in enumerate(self.rows):
            row.up.setEnabled(index > 0)
            row.down.setEnabled(index < total - 1)

    def _move(self, row: RateEditorRow, delta: int) -> None:
        if row not in self.rows:
            return
        index = self.rows.index(row)
        target = max(0, min(len(self.rows) - 1, index + int(delta)))
        if target == index:
            return
        self.rows[index], self.rows[target] = self.rows[target], self.rows[index]
        for item in self.rows:
            self.rows_layout.removeWidget(item.frame)
        for item in self.rows:
            self.rows_layout.insertWidget(self.rows_layout.count() - 1, item.frame)
        self._refresh_order_buttons()

    def _remove(self, row: RateEditorRow) -> None:
        if row.scheme_id:
            try:
                self.db.delete_work_rate_scheme(row.scheme_id)
            except Exception as exc:
                QMessageBox.warning(self, "Tarifas", str(exc))
                return
        if row in self.rows:
            self.rows.remove(row)
        row.frame.deleteLater()
        self._refresh_order_buttons()

    def save(self) -> None:
        ids: list[int] = []
        for row in self.rows:
            mode = str(row.mode.currentData())
            options = row.options.values() if mode == "option" else []
            if mode == "option" and not options:
                raise ValueError(f"La tarifa '{row.name.text().strip() or 'sin nombre'}' necesita al menos una opción.")
            scheme_id = self.db.save_work_rate_scheme(
                {
                    "name": row.name.text().strip(),
                    "mode": mode,
                    "unit_label": row.unit_label.text().strip() or "unidad",
                    "unit_rate": row.unit_rate.value(),
                    "active": row.active.isChecked(),
                    "options": options,
                },
                row.scheme_id,
            )
            row.scheme_id = scheme_id
            ids.append(scheme_id)
        self.db.reorder_work_rate_schemes(ids)


class WorkCustomizationDialog(QDialog):
    """Punto único para personalizar campos y tarifas de Viajes."""

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Personalizar Viajes")
        self.setMinimumSize(560, 520)
        self.resize(940, 720)
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(14)
        root.addWidget(page_header("Personalizar Viajes", "Adaptá la herramienta a tu trabajo sin modificar código."))
        tabs = QTabWidget()
        self.fields = WorkFieldsTab(db)
        self.rates = WorkRatesTab(db)
        tabs.addTab(self.fields, "Campos")
        tabs.addTab(self.rates, "Tarifas")
        root.addWidget(tabs, 1)
        actions = QHBoxLayout()
        actions.addStretch()
        cancel = QPushButton("Cancelar")
        cancel.setObjectName("SecondaryButton")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Guardar cambios")
        save.clicked.connect(self._save)
        actions.addWidget(cancel)
        actions.addWidget(save)
        root.addLayout(actions)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        QTimer.singleShot(0, self._fit_to_screen)

    def _fit_to_screen(self) -> None:
        fit_dialog_to_screen(self, preferred_width=940, preferred_height=720)

    def _save(self) -> None:
        try:
            self.fields.save()
            self.rates.save()
        except Exception as exc:
            QMessageBox.warning(self, "Personalización", str(exc))
            return
        self.accept()
