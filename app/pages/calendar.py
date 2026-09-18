from __future__ import annotations

import calendar as pycalendar
from datetime import date

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import (
    QBoxLayout, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QVBoxLayout, QWidget, QLayout
)

from ..constants import MONTHS
from ..dialogs import TransactionDialog
from ..utils import money
from ..widgets import TransactionRowWidget
from ..layouts import responsive_mode, AdaptiveSplitter
from .common import clear_layout, page_header


WEEKDAYS_SHORT = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
WEEKDAYS_FULL = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


class CalendarDayCell(QFrame):
    clicked = Signal(str)
    add_requested = Signal(str)

    def __init__(self, iso_date: str | None, day_number: int | None, totals: dict | None, fmt, selected=False, today=False, parent=None):
        super().__init__(parent)
        self.iso_date = iso_date
        self.setObjectName("CalendarDay" if iso_date else "CalendarDayEmpty")
        self.setProperty("selected", bool(selected))
        self.setProperty("today", bool(today))
        self.setCursor(Qt.CursorShape.PointingHandCursor if iso_date else Qt.CursorShape.ArrowCursor)
        self.setMinimumHeight(94)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(11, 9, 11, 9)
        layout.setSpacing(3)

        if not iso_date:
            return

        top = QHBoxLayout()
        day = QLabel(str(day_number))
        day.setObjectName("CalendarDayNumber")
        top.addWidget(day)
        top.addStretch()
        if today:
            badge = QLabel("HOY")
            badge.setObjectName("CalendarTodayBadge")
            top.addWidget(badge)
        layout.addLayout(top)

        totals = totals or {}
        income = float(totals.get("income") or 0)
        expense = float(totals.get("expense") or 0)
        count = int(totals.get("count") or 0)

        layout.addStretch()
        if expense:
            exp = QLabel(f"− {fmt(expense)}")
            exp.setObjectName("CalendarExpense")
            layout.addWidget(exp)
        if income:
            inc = QLabel(f"+ {fmt(income)}")
            inc.setObjectName("CalendarIncome")
            layout.addWidget(inc)
        if count:
            meta = QLabel(f"{count} movimiento{'s' if count != 1 else ''}")
            meta.setObjectName("CalendarMeta")
            layout.addWidget(meta)

    def mousePressEvent(self, event):
        if self.iso_date and event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.iso_date)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if self.iso_date and event.button() == Qt.MouseButton.LeftButton:
            self.add_requested.emit(self.iso_date)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


class CalendarPage(QWidget):
    data_changed = Signal()

    def __init__(self, db):
        super().__init__()
        self.db = db
        today = date.today()
        self.year = today.year
        self.month = today.month
        self.selected_date = today.isoformat()
        self._compact = False

        root = QVBoxLayout(self)
        root.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        root.setContentsMargins(28, 24, 28, 28)
        root.setSpacing(14)

        self.top_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.top_layout.addWidget(page_header("Calendario", "Mirá rápidamente qué días gastaste, cobraste o moviste plata"), 1)
        navigation=QWidget()
        top=QHBoxLayout(navigation)
        top.setContentsMargins(0,0,0,0)
        self.top_layout.addWidget(navigation)
        prev_btn = QPushButton("‹")
        prev_btn.setObjectName("CalendarNavButton")
        prev_btn.clicked.connect(self.previous_month)
        self.period_label = QLabel()
        self.period_label.setObjectName("CalendarPeriod")
        self.period_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        next_btn = QPushButton("›")
        next_btn.setObjectName("CalendarNavButton")
        next_btn.clicked.connect(self.next_month)
        today_btn = QPushButton("Hoy")
        today_btn.setObjectName("SecondaryButton")
        today_btn.clicked.connect(self.go_today)
        top.addWidget(prev_btn)
        top.addWidget(self.period_label)
        top.addWidget(next_btn)
        top.addSpacing(6)
        top.addWidget(today_btn)
        root.addLayout(self.top_layout)

        summary = QFrame()
        summary.setObjectName("MovementSummary")
        sl = QHBoxLayout(summary)
        sl.setContentsMargins(14, 9, 14, 9)
        self.summary_label = QLabel()
        self.summary_label.setObjectName("Muted")
        self.summary_label.setWordWrap(True)
        sl.addWidget(self.summary_label, 1)
        hint = QLabel("Clic: ver día · doble clic: agregar movimiento")
        hint.setObjectName("SmallMuted")
        hint.setWordWrap(True)
        sl.addWidget(hint)
        root.addWidget(summary)

        self.body_layout = AdaptiveSplitter((3,1))
        body = self.body_layout

        calendar_card = QFrame()
        calendar_card.setObjectName("Card")
        calendar_layout = QVBoxLayout(calendar_card)
        calendar_layout.setContentsMargins(16, 15, 16, 16)
        calendar_layout.setSpacing(10)

        self.grid_host = QWidget()
        self.grid = QGridLayout(self.grid_host)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(8)
        self.grid.setVerticalSpacing(8)
        for col in range(7):
            self.grid.setColumnStretch(col, 1)
        calendar_layout.addWidget(self.grid_host)
        self.calendar_scroll=QScrollArea()
        self.calendar_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.calendar_scroll.setWidgetResizable(True)
        self.calendar_scroll.setMinimumHeight(180)
        self.calendar_scroll.setWidget(calendar_card)
        body.addWidget(self.calendar_scroll)

        self.detail_card = QFrame()
        detail = self.detail_card
        detail.setObjectName("Card")
        detail.setMinimumWidth(300)
        dl = QVBoxLayout(detail)
        dl.setContentsMargins(18, 18, 18, 18)
        dl.setSpacing(10)

        self.detail_title = QLabel()
        self.detail_title.setObjectName("SectionTitle")
        self.detail_subtitle = QLabel()
        self.detail_subtitle.setObjectName("SmallMuted")
        self.detail_subtitle.setWordWrap(True)
        dl.addWidget(self.detail_title)
        dl.addWidget(self.detail_subtitle)

        add_btn = QPushButton("+ Movimiento este día")
        add_btn.clicked.connect(lambda: self.add_transaction(self.selected_date))
        dl.addWidget(add_btn)

        self.detail_scroll = QScrollArea()
        self.detail_scroll.setWidgetResizable(True)
        self.detail_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.detail_scroll.setObjectName("MovementScroll")
        self.detail_host = QWidget()
        self.detail_layout = QVBoxLayout(self.detail_host)
        self.detail_layout.setContentsMargins(0, 0, 4, 0)
        self.detail_layout.setSpacing(7)
        self.detail_scroll.setWidget(self.detail_host)
        dl.addWidget(self.detail_scroll, 1)
        body.addWidget(detail)

        root.addWidget(body, 1)
        self.refresh(); self._apply_responsive()

    def _apply_responsive(self):
        compact = responsive_mode(self.width(), self.height()) != "wide"
        if compact == self._compact:
            return
        self._compact = compact
        direction = QBoxLayout.Direction.TopToBottom if compact else QBoxLayout.Direction.LeftToRight
        self.top_layout.setDirection(direction)
        self.body_layout.set_compact(compact)
        self.detail_card.setMinimumWidth(0 if compact else 300)
        margins = 14 if compact else 28
        self.layout().setContentsMargins(margins, 18 if compact else 24, margins, 20 if compact else 28)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_responsive()

    def _fmt(self, value):
        return money(value, self.db.currency_symbol(), self.db.balances_hidden())

    def _month_summary_text(self, totals):
        income = sum(float(item.get("income") or 0) for item in totals.values())
        expense = sum(float(item.get("expense") or 0) for item in totals.values())
        active = sum(1 for item in totals.values() if int(item.get("count") or 0) > 0)
        return (
            f"{active} días con actividad   ·   "
            f"Ingresos {self._fmt(income)}   ·   Gastos {self._fmt(expense)}   ·   Neto {self._fmt(income - expense)}"
        )

    def refresh(self):
        self.period_label.setText(f"{MONTHS[self.month - 1]} {self.year}")
        totals = self.db.daily_totals(self.year, self.month)
        self.summary_label.setText(self._month_summary_text(totals))

        clear_layout(self.grid)
        for col, name in enumerate(WEEKDAYS_SHORT):
            label = QLabel(name)
            label.setObjectName("CalendarWeekday")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid.addWidget(label, 0, col)

        month_rows = pycalendar.Calendar(firstweekday=0).monthdayscalendar(self.year, self.month)
        while len(month_rows) < 6:
            month_rows.append([0] * 7)
        today = date.today()
        for row_index, week in enumerate(month_rows, start=1):
            for col, day_number in enumerate(week):
                if day_number == 0:
                    cell = CalendarDayCell(None, None, None, self._fmt)
                else:
                    d = date(self.year, self.month, day_number)
                    iso = d.isoformat()
                    cell = CalendarDayCell(
                        iso,
                        day_number,
                        totals.get(iso),
                        self._fmt,
                        selected=(iso == self.selected_date),
                        today=(d == today),
                    )
                    cell.clicked.connect(self.select_day)
                    cell.add_requested.connect(self.add_transaction)
                self.grid.addWidget(cell, row_index, col)
        self.grid_host.setMinimumHeight(len(month_rows)*102+30)

        # Si la fecha seleccionada quedó fuera del mes visible, elegimos un día útil.
        try:
            selected = date.fromisoformat(self.selected_date)
        except Exception:
            selected = date(self.year, self.month, 1)
        if selected.year != self.year or selected.month != self.month:
            if today.year == self.year and today.month == self.month:
                self.selected_date = today.isoformat()
            else:
                self.selected_date = date(self.year, self.month, 1).isoformat()
            # Repintamos una sola vez con la selección corregida.
            return self.refresh()
        self.refresh_day_detail()

    def refresh_day_detail(self):
        clear_layout(self.detail_layout)
        d = date.fromisoformat(self.selected_date)
        title = "Hoy" if d == date.today() else f"{WEEKDAYS_FULL[d.weekday()].capitalize()} {d.day}"
        self.detail_title.setText(title)
        rows = self.db.transactions_for_day(self.selected_date)
        income = sum(float(x["amount"]) for x in rows if x["kind"] == "income")
        expense = sum(float(x["amount"]) for x in rows if x["kind"] == "expense")
        self.detail_subtitle.setText(
            f"{d.strftime('%d/%m/%Y')}  ·  {len(rows)} movimientos  ·  Neto {self._fmt(income - expense)}"
        )
        if not rows:
            empty = QFrame()
            empty.setObjectName("SoftCard")
            box = QVBoxLayout(empty)
            box.setContentsMargins(15, 16, 15, 16)
            msg = QLabel("No hay movimientos este día.")
            msg.setObjectName("Muted")
            box.addWidget(msg)
            self.detail_layout.addWidget(empty)
        else:
            for tx in rows:
                amount = float(tx["amount"])
                shown = amount if tx["kind"] == "income" else -amount if tx["kind"] == "expense" else amount
                row = TransactionRowWidget(tx, self._fmt(shown), compact=True)
                row.edit_requested.connect(self.edit_transaction)
                row.duplicate_requested.connect(self.duplicate_transaction)
                row.delete_requested.connect(self.delete_transaction)
                self.detail_layout.addWidget(row)
        self.detail_layout.addStretch()

    def select_day(self, iso_date):
        self.selected_date = iso_date
        self.refresh()

    def add_transaction(self, iso_date=None):
        iso_date = iso_date or self.selected_date
        dlg = TransactionDialog(self.db, parent=self)
        try:
            y, m, d = map(int, str(iso_date).split("-"))
            dlg.date.setDate(QDate(y, m, d))
        except Exception:
            pass
        if dlg.exec():
            data = dlg.data()
            self.db.add_transaction(data)
            self.selected_date = data["tx_date"]
            y, m, _ = map(int, self.selected_date.split("-"))
            self.year, self.month = y, m
            self.refresh()
            self.data_changed.emit()

    def edit_transaction(self, txid=None):
        if not txid:
            return
        tx = self.db.transaction(int(txid))
        if not tx:
            return
        dlg = TransactionDialog(self.db, tx, self)
        if dlg.exec():
            data = dlg.data()
            self.db.update_transaction(int(txid), data)
            self.selected_date = data["tx_date"]
            y, m, _ = map(int, self.selected_date.split("-"))
            self.year, self.month = y, m
            self.refresh()
            self.data_changed.emit()

    def duplicate_transaction(self, txid=None):
        if not txid:
            return
        self.db.duplicate_transaction(int(txid), new_date=self.selected_date)
        self.refresh()
        self.data_changed.emit()

    def delete_transaction(self, txid=None):
        if not txid:
            return
        from PySide6.QtWidgets import QMessageBox
        if QMessageBox.question(self, "Eliminar movimiento", "¿Eliminar este movimiento definitivamente?") == QMessageBox.StandardButton.Yes:
            self.db.delete_transaction(int(txid))
            self.refresh()
            self.data_changed.emit()

    def previous_month(self):
        if self.month == 1:
            self.month = 12
            self.year -= 1
        else:
            self.month -= 1
        self.selected_date = date(self.year, self.month, 1).isoformat()
        self.refresh()

    def next_month(self):
        if self.month == 12:
            self.month = 1
            self.year += 1
        else:
            self.month += 1
        self.selected_date = date(self.year, self.month, 1).isoformat()
        self.refresh()

    def go_today(self):
        today = date.today()
        self.year, self.month = today.year, today.month
        self.selected_date = today.isoformat()
        self.refresh()
