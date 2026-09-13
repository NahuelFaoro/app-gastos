from __future__ import annotations

"""Resumen mensual de la gestión de viajes."""

from datetime import date

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..constants import MONTHS
from ..layouts import FlowLayout
from ..utils import money
from ..ui_helpers import fit_dialog_to_screen
from .viajes_widgets import WorkMetricCard


class MonthWeekCard(QFrame):
    """Tarjeta compacta para una semana del resumen mensual."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("WorkDayCard")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.header = QFrame()
        self.header.setObjectName("WorkDayHeader")
        header_layout = QVBoxLayout(self.header)
        header_layout.setContentsMargins(14, 11, 14, 11)
        header_layout.setSpacing(8)

        self.title = QLabel()
        self.title.setObjectName("WorkDayTitle")
        header_layout.addWidget(self.title)

        self.chips_host = QWidget()
        self.chips_layout = FlowLayout(self.chips_host, margin=0, horizontal_spacing=6, vertical_spacing=6)
        header_layout.addWidget(self.chips_host)

        root.addWidget(self.header)
        self._chips: list[QLabel] = []

    def _set_chips(self, values: list[str]) -> None:
        while self._chips:
            chip = self._chips.pop()
            self.chips_layout.removeWidget(chip)
            chip.deleteLater()
        for text in values:
            chip = QLabel(str(text))
            chip.setObjectName("WorkDayChip")
            self.chips_layout.addWidget(chip)
            self._chips.append(chip)

    def set_summary(
        self,
        title: str,
        row: dict,
        *,
        symbol: str,
        hidden_amounts: bool,
        field_definitions: list[dict],
        field_counts: dict[int, float],
    ) -> None:
        self.title.setText(title)
        values = [
            f"{int(row['trips'])} viaje" if int(row['trips']) == 1 else f"{int(row['trips'])} viajes",
            f"{int(row['stops'])} parada" if int(row['stops']) == 1 else f"{int(row['stops'])} paradas",
        ]
        for definition in field_definitions:
            if definition.get("field_type") != "check" or not definition.get("show_in_summary"):
                continue
            count = field_counts.get(int(definition["id"]), 0)
            shown = str(int(count)) if float(count).is_integer() else f"{count:g}"
            values.append(f"{shown} {str(definition.get('label') or 'campo').lower()}")
        values.extend([
            (
                f"{float(row['real_km']):.1f} km reales"
                if int(row.get('completed_days') or 0)
                else "sin km reales"
            ),
            money(float(row['charged'] or 0), symbol, hidden_amounts),
        ])
        self._set_chips(values)


class WorkMonthSummaryDialog(QDialog):
    """Muestra totales del mes y un resumen visual por semana."""

    def __init__(self, db, initial_date: date, parent=None):
        super().__init__(parent)
        self.db = db
        self.year = int(initial_date.year)
        self.month = int(initial_date.month)
        self.setWindowTitle("Resumen mensual")
        self.setMinimumSize(560, 520)
        self.resize(1080, 740)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(14)

        self.title = QLabel()
        self.title.setObjectName("PageTitle")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle = QLabel("Totales del mes y desglose de cada semana de trabajo.")
        subtitle.setObjectName("PageSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)
        root.addWidget(self.title)
        root.addWidget(subtitle)

        top = QHBoxLayout()
        top.addStretch()
        previous = QPushButton("‹")
        previous.setObjectName("SecondaryButton")
        previous.clicked.connect(lambda: self._shift_month(-1))
        current = QPushButton("Mes actual")
        current.setObjectName("SecondaryButton")
        current.clicked.connect(self._go_current_month)
        next_button = QPushButton("›")
        next_button.setObjectName("SecondaryButton")
        next_button.clicked.connect(lambda: self._shift_month(1))
        close = QPushButton("Cerrar")
        close.clicked.connect(self.accept)
        for button in (previous, current, next_button, close):
            top.addWidget(button)
        top.addStretch()
        root.addLayout(top)

        self.metrics_host = QFrame()
        self.metrics_host.setObjectName("SoftCard")
        self.metrics_layout = FlowLayout(self.metrics_host, margin=12, horizontal_spacing=9, vertical_spacing=9, center_rows=True)
        self.metrics = {
            "trips": WorkMetricCard("Viajes", 145),
            "stops": WorkMetricCard("Paradas", 145),
            "real_km": WorkMetricCard("KM reales", 170),
            "charged": WorkMetricCard("Cobrado", 190),
        }
        self.field_definitions = db.work_field_definitions(active_only=True)
        self.field_metrics: dict[int, WorkMetricCard] = {}
        # Viajes y Paradas primero, luego los checks configurables, y finalmente
        # km/cobrado. FlowLayout se encarga de envolver sin deformar tarjetas.
        self.metrics_layout.addWidget(self.metrics["trips"])
        self.metrics_layout.addWidget(self.metrics["stops"])
        for definition in self.field_definitions:
            if definition.get("field_type") == "check" and definition.get("show_in_summary"):
                card = WorkMetricCard(str(definition.get("label") or "Campo"), 145)
                self.field_metrics[int(definition["id"])] = card
                self.metrics_layout.addWidget(card)
        self.metrics_layout.addWidget(self.metrics["real_km"])
        self.metrics_layout.addWidget(self.metrics["charged"])
        root.addWidget(self.metrics_host)

        section = QLabel("Semanas del mes")
        section.setObjectName("SectionTitle")
        root.addWidget(section)

        self.weeks_scroll = QScrollArea()
        self.weeks_scroll.setWidgetResizable(True)
        self.weeks_scroll.setFrameShape(QFrame.Shape.NoFrame)
        root.addWidget(self.weeks_scroll, 1)

        self.weeks_host = QWidget()
        self.weeks_layout = QVBoxLayout(self.weeks_host)
        self.weeks_layout.setContentsMargins(0, 0, 4, 0)
        self.weeks_layout.setSpacing(8)
        self.weeks_layout.addStretch(1)
        self.weeks_scroll.setWidget(self.weeks_host)

        self._refresh()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        QTimer.singleShot(0, self._fit_to_screen)

    def _fit_to_screen(self) -> None:
        fit_dialog_to_screen(
            self, preferred_width=1080, preferred_height=740, width_ratio=0.94, height_ratio=0.90
        )

    @staticmethod
    def _week_label(row: dict) -> str:
        start = date.fromisoformat(row["period_start"])
        end = date.fromisoformat(row["period_end"])
        if start == end:
            return f"SEMANA · {start.strftime('%d/%m')}"
        return f"SEMANA · {start.strftime('%d/%m')} – {end.strftime('%d/%m')}"

    def _shift_month(self, delta: int) -> None:
        index = self.year * 12 + (self.month - 1) + int(delta)
        self.year, month_index = divmod(index, 12)
        self.month = month_index + 1
        self._refresh()

    def _go_current_month(self) -> None:
        today = date.today()
        self.year = today.year
        self.month = today.month
        self._refresh()

    def _rebuild_week_cards(self, weeks: list[dict], *, symbol: str, hidden: bool) -> None:
        while self.weeks_layout.count() > 1:
            item = self.weeks_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if not weeks:
            empty = QFrame()
            empty.setObjectName("SoftCard")
            empty_layout = QVBoxLayout(empty)
            empty_layout.setContentsMargins(16, 14, 16, 14)
            label = QLabel("Todavía no hay semanas con datos en este mes.")
            label.setObjectName("SmallMuted")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_layout.addWidget(label)
            self.weeks_layout.insertWidget(0, empty)
            return

        for row in weeks:
            card = MonthWeekCard()
            counts = self.db.work_field_counts_between(row["period_start"], row["period_end"])
            card.set_summary(
                self._week_label(row),
                row,
                symbol=symbol,
                hidden_amounts=hidden,
                field_definitions=self.field_definitions,
                field_counts=counts,
            )
            self.weeks_layout.insertWidget(self.weeks_layout.count() - 1, card)

    def _refresh(self) -> None:
        self.title.setText(f"{MONTHS[self.month - 1]} {self.year}")
        summary = self.db.work_month_summary(self.year, self.month)
        hidden = self.db.balances_hidden()
        symbol = self.db.currency_symbol()

        self.metrics["trips"].set_value(str(summary["trips"]))
        self.metrics["stops"].set_value(str(summary["stops"]))
        month_start = date(self.year, self.month, 1)
        from calendar import monthrange
        month_end = date(self.year, self.month, monthrange(self.year, self.month)[1])
        field_counts = self.db.work_field_counts_between(month_start, month_end)
        for field_id, card in self.field_metrics.items():
            count = field_counts.get(field_id, 0)
            card.set_value(str(int(count)) if float(count).is_integer() else f"{count:g}")
        self.metrics["real_km"].set_mileage(summary)
        self.metrics["charged"].set_value(money(summary["charged"], symbol, hidden))

        weeks = self.db.work_month_week_summaries(self.year, self.month)
        self._rebuild_week_cards(weeks, symbol=symbol, hidden=hidden)
