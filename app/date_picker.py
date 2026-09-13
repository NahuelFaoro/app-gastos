from __future__ import annotations

"""Selector de fecha consistente con App Gastos.

Qt trae un popup de calendario compacto pensado para formularios genéricos. En
monitores con DPI alto o con el zoom de App Gastos ese popup puede quedar muy
chico o recortado. Este módulo usa un diálogo propio con navegación de mes/año
visible y geometría limitada al monitor actual.
"""

from PySide6.QtCore import QDate, QTimer, Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QCalendarWidget,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from .constants import MONTHS


class CalendarDialog(QDialog):
    """Calendario grande con controles explícitos de mes y año."""

    def __init__(self, initial: QDate, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Elegir fecha")
        self.setModal(True)
        self.setMinimumSize(480, 500)
        self.resize(600, 610)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(12)

        title = QLabel("Elegí una fecha")
        title.setObjectName("SectionTitle")
        subtitle = QLabel("Navegá por mes y año. La fecha sólo cambia cuando confirmás.")
        subtitle.setObjectName("SmallMuted")
        subtitle.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(subtitle)

        nav = QHBoxLayout()
        nav.setSpacing(8)
        previous = QPushButton("‹")
        previous.setObjectName("SecondaryButton")
        previous.setFixedWidth(44)
        previous.clicked.connect(lambda: self._shift_month(-1))
        next_button = QPushButton("›")
        next_button.setObjectName("SecondaryButton")
        next_button.setFixedWidth(44)
        next_button.clicked.connect(lambda: self._shift_month(1))

        self.month = QComboBox()
        for index, name in enumerate(MONTHS, start=1):
            self.month.addItem(name, index)
        self.month.setMinimumWidth(160)
        self.month.currentIndexChanged.connect(self._sync_calendar_page)

        self.year = QSpinBox()
        self.year.setRange(2000, 2100)
        self.year.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.year.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.year.setMinimumWidth(90)
        self.year.valueChanged.connect(self._sync_calendar_page)

        nav.addWidget(previous)
        nav.addWidget(self.month, 1)
        nav.addWidget(self.year)
        nav.addWidget(next_button)
        root.addLayout(nav)

        self.calendar = QCalendarWidget()
        self.calendar.setNavigationBarVisible(False)
        self.calendar.setGridVisible(False)
        self.calendar.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        self.calendar.setSelectedDate(initial)
        self.calendar.setCurrentPage(initial.year(), initial.month())
        self.calendar.activated.connect(lambda _date: self.accept())
        self.calendar.currentPageChanged.connect(self._calendar_page_changed)
        root.addWidget(self.calendar, 1)

        actions = QHBoxLayout()
        today = QPushButton("Hoy")
        today.setObjectName("SecondaryButton")
        today.clicked.connect(self._select_today)
        cancel = QPushButton("Cancelar")
        cancel.setObjectName("SecondaryButton")
        cancel.clicked.connect(self.reject)
        accept = QPushButton("Usar fecha")
        accept.clicked.connect(self.accept)
        actions.addWidget(today)
        actions.addStretch()
        actions.addWidget(cancel)
        actions.addWidget(accept)
        root.addLayout(actions)

        self._set_navigation(initial.year(), initial.month())
        QTimer.singleShot(0, self._fit_and_center)

    def _set_navigation(self, year: int, month: int) -> None:
        self.month.blockSignals(True)
        self.year.blockSignals(True)
        self.month.setCurrentIndex(max(0, min(11, month - 1)))
        self.year.setValue(year)
        self.month.blockSignals(False)
        self.year.blockSignals(False)

    def _sync_calendar_page(self, *_args) -> None:
        month = int(self.month.currentData() or 1)
        self.calendar.setCurrentPage(self.year.value(), month)

    def _calendar_page_changed(self, year: int, month: int) -> None:
        self._set_navigation(year, month)

    def _shift_month(self, delta: int) -> None:
        current = QDate(self.year.value(), int(self.month.currentData() or 1), 1)
        shifted = current.addMonths(int(delta))
        self._set_navigation(shifted.year(), shifted.month())
        self.calendar.setCurrentPage(shifted.year(), shifted.month())

    def _select_today(self) -> None:
        today = QDate.currentDate()
        self.calendar.setSelectedDate(today)
        self.calendar.setCurrentPage(today.year(), today.month())
        self._set_navigation(today.year(), today.month())

    def _fit_and_center(self) -> None:
        parent = self.parentWidget().window() if self.parentWidget() else None
        screen = parent.screen() if parent is not None else QGuiApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        # El límite evita que el zoom de interfaz haga crecer el diálogo más que
        # el monitor, que era la causa del calendario recortado.
        target_width = min(max(520, self.sizeHint().width()), int(available.width() * 0.82))
        target_height = min(max(540, self.sizeHint().height()), int(available.height() * 0.86))
        self.resize(target_width, target_height)
        center = parent.frameGeometry().center() if parent is not None else available.center()
        frame = self.frameGeometry()
        frame.moveCenter(center)
        # Clamp final: nunca dejamos una esquina afuera del área útil.
        x = min(max(frame.x(), available.left()), available.right() - frame.width() + 1)
        y = min(max(frame.y(), available.top()), available.bottom() - frame.height() + 1)
        self.move(x, y)

    def selected_date(self) -> QDate:
        return self.calendar.selectedDate()


class DatePickerButton(QPushButton):
    """Campo de fecha redondeado que no cambia valor hasta confirmar."""

    dateChanged = Signal(QDate)

    def __init__(self, initial: QDate | None = None, parent=None):
        super().__init__(parent)
        self._date = QDate(initial or QDate.currentDate())
        self._display_format = "dd/MM/yyyy"
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("SecondaryButton")
        self.setMinimumHeight(42)
        self.setStyleSheet("text-align:left; padding-left:12px;")
        self.clicked.connect(self._pick_date)
        self._refresh()

    def _refresh(self) -> None:
        self.setText(self._date.toString(self._display_format))

    def _pick_date(self) -> None:
        dialog = CalendarDialog(self._date, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.setDate(dialog.selected_date())

    def date(self) -> QDate:
        return QDate(self._date)

    def setDate(self, value: QDate) -> None:
        value = QDate(value)
        if value == self._date:
            return
        self._date = value
        self._refresh()
        self.dateChanged.emit(QDate(self._date))


class WorkDateEdit(DatePickerButton):
    """Compatibilidad liviana con ``QDateEdit`` usando el nuevo calendario.

    Varias pantallas de App Gastos sólo necesitan un campo de fecha con
    ``date()``, ``setDate()`` y la señal ``dateChanged``. Este wrapper permite
    reutilizar el selector nuevo sin reescribir toda la app en un solo paso.
    """

    def __init__(self, initial: QDate | None = None, parent=None):
        super().__init__(initial, parent)
        self._calendar_popup = True

    def setCalendarPopup(self, enabled: bool) -> None:  # noqa: N802 - compat Qt
        self._calendar_popup = bool(enabled)

    def calendarPopup(self) -> bool:  # noqa: N802 - compat Qt
        return self._calendar_popup

    def setDisplayFormat(self, fmt: str) -> None:  # noqa: N802 - compat Qt
        self._display_format = str(fmt or "dd/MM/yyyy")
        self._refresh()

    def displayFormat(self) -> str:  # noqa: N802 - compat Qt
        return self._display_format
