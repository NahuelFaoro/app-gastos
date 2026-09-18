from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta

from PySide6.QtCore import QDate, QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup, QComboBox, QDialog, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget, QMessageBox,
)

from ..constants import MONTHS
from ..layouts import FlowLayout, responsive_mode
from ..ui_helpers import fit_dialog_to_screen
from ..utils import add_months, money
from ..widgets import IconBadge
from ..work_calendar import week_end, week_start
from .common import clear_layout, page_header, scroll_container
from ..date_picker import WorkDateEdit
from ..dialogs import TransactionDialog


WEEKDAYS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


class AnalysisDrillRow(QFrame):
    activated = Signal(int)

    def __init__(self, category_id=None, parent=None):
        super().__init__(parent)
        self.category_id = int(category_id) if category_id else 0
        if self.category_id:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setToolTip("Doble clic para ver estos movimientos")

    def mouseDoubleClickEvent(self, event):
        if self.category_id:
            self.activated.emit(self.category_id)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


class AnalysisCategoryRow(AnalysisDrillRow):
    """Tarjeta de ranking con un eje central estable para el porcentaje.

    La geometría vive en este componente y no en ``StatisticsPage.refresh``.
    Así nombre/importe pueden cambiar de ancho sin desplazar el porcentaje.
    """

    PERCENT_WIDTH = 96
    AMOUNT_WIDTH = 210

    def __init__(self, category: dict, share: float, amount_text: str, *, narrow: bool, parent=None):
        super().__init__(category.get("category_id"), parent)
        self.setObjectName("AnalysisCategoryCard")

        badge = IconBadge(
            category.get("icon", "other"),
            category.get("color") or "#4CCFA9",
            42,
            secondary_color=category.get("secondary_color"),
        )
        name = QLabel(category.get("category") or "Sin categoría")
        name.setObjectName("AnalysisCategoryName")
        name.setWordWrap(narrow)
        name.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        percent = QLabel(f"{share:.0f}%")
        percent.setObjectName("AnalysisCategoryPercent")
        percent.setFixedWidth(self.PERCENT_WIDTH)
        percent.setAlignment(Qt.AlignmentFlag.AlignCenter)

        amount = QLabel(amount_text)
        amount.setObjectName("AnalysisCategoryAmount")
        amount.setFixedWidth(self.AMOUNT_WIDTH)
        amount.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        open_button = QPushButton("›")
        open_button.setObjectName("GhostButton")
        open_button.setFixedWidth(34)
        open_button.setToolTip("Ver desglose")
        open_button.clicked.connect(lambda: self.activated.emit(self.category_id))

        self._row_mode = None
        self._badge, self._name = badge, name
        self._percent, self._amount, self._open = percent, amount, open_button
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(16, 10, 16, 10)
        self._grid.setHorizontalSpacing(12)
        self._left = QWidget()
        left = QHBoxLayout(self._left)
        left.setContentsMargins(0, 0, 0, 0)
        left.addWidget(badge)
        left.addWidget(name, 1)
        self._left.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._right = QWidget()
        right = QHBoxLayout(self._right)
        right.setContentsMargins(0, 0, 0, 0)
        right.addStretch()
        right.addWidget(amount)
        right.addWidget(open_button)
        self._right.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._arrange_row()

    def _arrange_row(self) -> None:
        # El ancho real de la tarjeta decide su layout, incluso al mostrarse
        # después de haber sido construida dentro de una página oculta.
        narrow = responsive_mode(self.width()) == "narrow"
        if narrow == self._row_mode:
            return
        self._row_mode = narrow
        grid = self._grid
        for widget in (self._left, self._percent, self._right):
            grid.removeWidget(widget)
        self._name.setWordWrap(True)
        for col in range(3):
            grid.setColumnStretch(col, 0)
        if narrow:
            grid.addWidget(self._left, 0, 0, 1, 3)
            grid.addWidget(self._percent, 1, 0, Qt.AlignmentFlag.AlignLeft)
            grid.addWidget(self._right, 1, 1, 1, 2)
            grid.setColumnStretch(1, 1)
            self._amount.setFixedWidth(min(self.AMOUNT_WIDTH, max(130, self.width() - 180)))
        else:
            self._amount.setFixedWidth(self.AMOUNT_WIDTH)
            grid.addWidget(self._left, 0, 0)
            grid.addWidget(self._percent, 0, 1, Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(self._right, 0, 2)
            grid.setColumnStretch(0, 1)
            grid.setColumnStretch(2, 1)
        self.setFixedHeight(max(112 if narrow else 76, self.fontMetrics().height() * (6 if narrow else 4)))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._arrange_row()


class CategoryBreakdownDialog(QDialog):
    data_changed = Signal()
    """Navegador jerárquico de Análisis sin abandonar la pantalla.

    Mientras una categoría tenga hijos se muestra el siguiente nivel. Al llegar
    a una categoría final se listan sus movimientos y se pueden ordenar por
    importe o fecha. El salto a Movimientos queda como acción opcional.
    """

    open_transactions_requested = Signal(object)

    SORT_OPTIONS = (
        ("Mayor gasto", "amount_desc"),
        ("Menor gasto", "amount_asc"),
        ("Más recientes", "date_desc"),
        ("Más antiguos", "date_asc"),
    )

    def __init__(self, db, kind, category_id, start, end, mode, fmt, parent=None):
        super().__init__(parent)
        self.db = db
        self.kind = kind
        self.start = start
        self.end = end
        self.mode = mode
        self.fmt = fmt
        self.current_category_id = int(category_id)
        self.history: list[int] = []
        self.setWindowTitle("Detalle de categoría")
        self.resize(760, 700)
        self.setMinimumSize(440, 500)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(12)

        top = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        self.title = QLabel()
        self.title.setObjectName("PageTitle")
        self.breadcrumb = QLabel()
        self.breadcrumb.setObjectName("PageSubtitle")
        self.breadcrumb.setWordWrap(True)
        title_box.addWidget(self.title)
        title_box.addWidget(self.breadcrumb)
        top.addLayout(title_box, 1)
        self.back = QPushButton("← Atrás")
        self.back.setObjectName("SecondaryButton")
        self.back.clicked.connect(self._go_back)
        close = QPushButton("Cerrar")
        close.setObjectName("SecondaryButton")
        close.clicked.connect(self.accept)
        top.addWidget(self.back)
        top.addWidget(close)
        root.addLayout(top)

        self.summary = QFrame()
        self.summary.setObjectName("SoftCard")
        summary_layout = QHBoxLayout(self.summary)
        summary_layout.setContentsMargins(14, 12, 14, 12)
        summary_layout.setSpacing(10)
        self.summary_icon_host = QWidget()
        self.summary_icon_layout = QHBoxLayout(self.summary_icon_host)
        self.summary_icon_layout.setContentsMargins(0, 0, 0, 0)
        summary_layout.addWidget(self.summary_icon_host)
        summary_text = QVBoxLayout()
        summary_text.setSpacing(1)
        self.summary_caption = QLabel("Total")
        self.summary_caption.setObjectName("SmallMuted")
        self.summary_value = QLabel()
        self.summary_value.setObjectName("CardValue")
        summary_text.addWidget(self.summary_caption)
        summary_text.addWidget(self.summary_value)
        summary_layout.addLayout(summary_text, 1)
        root.addWidget(self.summary)

        control_row = QHBoxLayout()
        self.content_hint = QLabel()
        self.content_hint.setObjectName("SmallMuted")
        self.content_hint.setWordWrap(True)
        control_row.addWidget(self.content_hint, 1)
        self.sort = QComboBox()
        for label, value in self.SORT_OPTIONS:
            self.sort.addItem(label, value)
        self.sort.currentIndexChanged.connect(self._rebuild_content)
        control_row.addWidget(self.sort)
        root.addLayout(control_row)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        root.addWidget(self.scroll, 1)

        bottom = QHBoxLayout()
        self.add_movement = QPushButton('+ Ingreso' if self.kind=='income' else '+ Gasto')
        self.add_movement.clicked.connect(self._add_movement)
        bottom.addWidget(self.add_movement)
        bottom.addStretch()
        self.open_movements = QPushButton("Ver en Movimientos")
        self.open_movements.setObjectName("SecondaryButton")
        self.open_movements.clicked.connect(self._emit_open)
        bottom.addWidget(self.open_movements)
        root.addLayout(bottom)
        self._refresh()

    def _add_movement(self):
        dialog=TransactionDialog(self.db,parent=self)
        dialog.set_kind(self.kind)
        dialog.category.set_category(self._category())
        selected_date=min(max(date.today(),self.start),self.end)
        dialog.date.setDate(QDate(selected_date.year,selected_date.month,selected_date.day))
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        try:self.db.add_transaction(dialog.data())
        except Exception as exc:
            QMessageBox.warning(self,'No se pudo guardar',str(exc));return
        self._refresh()
        self.data_changed.emit()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        QTimer.singleShot(0, self._fit_to_screen)

    def _fit_to_screen(self) -> None:
        fit_dialog_to_screen(self, preferred_width=760, preferred_height=700)

    def _category(self) -> dict:
        return self.db.category(self.current_category_id) or {
            "id": self.current_category_id,
            "name": "Categoría",
            "path": "Categoría",
            "color": "#4CCFA9",
            "icon": "other",
        }

    def _category_total(self, category_id: int) -> float:
        return float(self.db.category_subtree_total_period(
            self.kind, int(category_id), self.start, self.end, include_history=True
        ))

    def _refresh(self) -> None:
        category = self._category()
        self.title.setText(str(category.get("name") or "Categoría"))
        self.breadcrumb.setText(str(category.get("path") or category.get("name") or ""))
        self.back.setEnabled(bool(self.history))
        self.summary_value.setText(self.fmt(self._category_total(self.current_category_id)))
        clear_layout(self.summary_icon_layout)
        self.summary_icon_layout.addWidget(
            IconBadge(
                category.get("icon") or "other",
                category.get("color") or "#4CCFA9",
                42,
                secondary_color=category.get("secondary_color"),
            )
        )
        self._rebuild_content()

    def _rebuild_content(self) -> None:
        category = self._category()
        children = self.db.category_direct_children_totals_period(
            self.kind, self.current_category_id, self.start, self.end
        )
        # Sólo mostramos hijos que realmente tienen datos en el período. Si no
        # hay ninguno, este nivel se comporta como hoja y aparecen movimientos.
        children = [row for row in children if float(row.get("total") or 0) > 0]
        host = QWidget()
        layout = QVBoxLayout(host)
        layout.setContentsMargins(0, 0, 7, 0)
        layout.setSpacing(8)

        if children:
            self.sort.setVisible(False)
            self.content_hint.setText("Abrí una subcategoría para seguir bajando en el detalle.")
            total = sum(float(row.get("total") or 0) for row in children)
            for item in children:
                row = AnalysisDrillRow(item.get("category_id"))
                row.setObjectName("CategoryBreakdownRow")
                row.activated.connect(self._open_child)
                grid = QGridLayout(row)
                grid.setContentsMargins(12, 10, 12, 10)
                grid.setHorizontalSpacing(12)
                badge = IconBadge(
                    item.get("icon") or category.get("icon") or "other",
                    item.get("color") or category.get("color") or "#4CCFA9",
                    36,
                    secondary_color=item.get("secondary_color"),
                )
                name = QLabel(item.get("category") or "Subcategoría")
                name.setObjectName("TransactionTitle")
                percent = QLabel(f"{(float(item.get('total') or 0) / total * 100 if total else 0):.0f}%")
                percent.setObjectName("AnalysisCategoryPercent")
                percent.setAlignment(Qt.AlignmentFlag.AlignCenter)
                amount = QLabel(self.fmt(float(item.get("total") or 0)))
                amount.setObjectName("TransactionAmount")
                amount.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                arrow = QPushButton("›")
                arrow.setObjectName("GhostButton")
                arrow.setFixedWidth(32)
                arrow.clicked.connect(lambda _checked=False, cid=int(item["category_id"]): self._open_child(cid))
                grid.addWidget(badge, 0, 0)
                grid.addWidget(name, 0, 1)
                grid.addWidget(percent, 0, 2)
                grid.addWidget(amount, 0, 3)
                grid.addWidget(arrow, 0, 4)
                grid.setColumnStretch(1, 3)
                grid.setColumnStretch(2, 1)
                grid.setColumnStretch(3, 1)
                layout.addWidget(row)
        else:
            self.sort.setVisible(True)
            self.content_hint.setText("Movimientos de esta categoría. Podés ordenarlos por fecha o por importe.")
            order = str(self.sort.currentData() or "amount_desc")
            rows = self.db.category_transactions_period(
                self.kind, self.current_category_id, self.start, self.end, order
            )
            if not rows:
                empty = QLabel("No hay movimientos con fecha exacta para esta categoría en el período.")
                empty.setObjectName("Muted")
                empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
                empty.setWordWrap(True)
                layout.addWidget(empty)
            else:
                for tx in rows:
                    card = QFrame()
                    card.setObjectName("CategoryBreakdownRow")
                    grid = QGridLayout(card)
                    grid.setContentsMargins(12, 10, 12, 10)
                    grid.setHorizontalSpacing(12)
                    title = QLabel(tx.get("description") or tx.get("category_display") or "Movimiento")
                    title.setObjectName("TransactionTitle")
                    title.setWordWrap(True)
                    date_label = QLabel(f"{str(tx.get('tx_date') or '')[:10]} · {tx.get('account_name') or ''}")
                    date_label.setObjectName("SmallMuted")
                    amount = QLabel(self.fmt(float(tx.get("amount") or 0)))
                    amount.setObjectName("TransactionAmount")
                    amount.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    grid.addWidget(title, 0, 0)
                    grid.addWidget(amount, 0, 1, 2, 1)
                    grid.addWidget(date_label, 1, 0)
                    grid.setColumnStretch(0, 1)
                    layout.addWidget(card)
        layout.addStretch()
        self.scroll.setWidget(host)

    def _open_child(self, category_id: int) -> None:
        if int(category_id) == self.current_category_id:
            return
        self.history.append(self.current_category_id)
        self.current_category_id = int(category_id)
        self._refresh()

    def _go_back(self) -> None:
        if not self.history:
            return
        self.current_category_id = self.history.pop()
        self._refresh()

    def _emit_open(self) -> None:
        self.open_transactions_requested.emit({
            "kind": self.kind,
            "category_id": int(self.current_category_id),
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "mode": self.mode,
        })


class CategoryDistributionBar(QFrame):
    """Barra horizontal apilada inspirada en la vista móvil de Gestor de gastos."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("AnalysisDistributionBar")
        self.setFixedHeight(18)
        self.layout_bar = QHBoxLayout(self)
        self.layout_bar.setContentsMargins(0, 0, 0, 0)
        self.layout_bar.setSpacing(0)

    def set_data(self, rows: list[dict]) -> None:
        clear_layout(self.layout_bar)
        total = sum(max(0.0, float(row.get("total") or 0)) for row in rows)
        if total <= 0:
            empty = QFrame()
            empty.setStyleSheet("background: rgba(120,130,140,0.24); border-radius: 8px;")
            self.layout_bar.addWidget(empty, 1)
            return
        for row in rows:
            value = max(0.0, float(row.get("total") or 0))
            if value <= 0:
                continue
            segment = QFrame()
            color = row.get("color") or "#4CCFA9"
            segment.setStyleSheet(f"background:{color}; border:none;")
            # Qt usa enteros para stretch; 10.000 da suficiente precisión visual.
            self.layout_bar.addWidget(segment, max(1, int(value / total * 10_000)))


class StatisticsPage(QWidget):
    data_changed = Signal()
    """Análisis visual centrado en categorías y períodos.

    La pantalla sigue el patrón de Gestor de gastos: tipo (gastos/ingresos),
    granularidad temporal, período, barra apilada y ranking de categorías. El
    desglose fino permanece disponible sin llenar la pantalla principal de
    controles secundarios.
    """

    open_transactions_requested = Signal(object)

    def __init__(self, db):
        super().__init__()
        self.db = db
        self.focus_date = date.today()
        self.mode = "month"
        self.kind = "expense"
        # None fuerza una reconstrucción cuando la página recibe el viewport real.
        self._compact_layout: bool | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll, _, root = scroll_container()
        root.setSpacing(14)
        outer.addWidget(scroll)
        root.addWidget(page_header("Análisis", "Tus gastos e ingresos, ordenados para entenderlos de un vistazo"))

        root.addWidget(self._build_control_panel())
        root.addWidget(self._build_hero())
        self._build_category_section(root)
        self.refresh()

    def _build_control_panel(self) -> QFrame:
        control = QFrame()
        control.setObjectName("AnalysisControl")
        layout = QVBoxLayout(control)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(11)
        layout.addLayout(self._build_kind_selector())
        layout.addWidget(self._build_mode_selector())
        layout.addLayout(self._build_period_navigation())
        layout.addWidget(self._build_custom_period_row())
        return control

    def _build_kind_selector(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addStretch()
        self.kind_group = QButtonGroup(self)
        self.kind_group.setExclusive(True)
        for label, value in (("GASTOS", "expense"), ("INGRESOS", "income")):
            button = QPushButton(label)
            button.setObjectName("AnalysisKindButton")
            button.setCheckable(True)
            button.setChecked(value == self.kind)
            button.clicked.connect(lambda checked=False, v=value: self.set_kind(v))
            self.kind_group.addButton(button)
            row.addWidget(button)
        row.addStretch()
        return row

    def _build_mode_selector(self) -> QWidget:
        host = QWidget()
        flow = FlowLayout(host, horizontal_spacing=6, vertical_spacing=6, center_rows=True)
        self.mode_buttons: dict[str, QPushButton] = {}
        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        for label, value in (("Día", "day"), ("Semana", "week"), ("Mes", "month"), ("Año", "year"), ("Período", "custom")):
            button = QPushButton(label)
            button.setObjectName("AnalysisModeButton")
            button.setCheckable(True)
            button.setChecked(value == self.mode)
            button.clicked.connect(lambda checked=False, v=value: self.set_mode(v))
            self.mode_group.addButton(button)
            self.mode_buttons[value] = button
            flow.addWidget(button)
        return host

    def _build_period_navigation(self) -> QHBoxLayout:
        nav = QHBoxLayout()
        nav.setSpacing(8)
        nav.addStretch()
        self.prev = QPushButton("‹")
        self.prev.setObjectName("PeriodNavButton")
        self.prev.clicked.connect(lambda: self.shift_period(-1))
        self.period_label = QLabel()
        self.period_label.setObjectName("AnalysisPeriodLabel")
        self.period_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.period_label.setMinimumWidth(230)
        self.next = QPushButton("›")
        self.next.setObjectName("PeriodNavButton")
        self.next.clicked.connect(lambda: self.shift_period(1))
        today = QPushButton("Hoy")
        today.setObjectName("SecondaryButton")
        today.clicked.connect(self.go_today)
        nav.addWidget(self.prev)
        nav.addWidget(self.period_label)
        nav.addWidget(self.next)
        nav.addWidget(today)
        nav.addStretch()
        return nav

    def _build_custom_period_row(self) -> QWidget:
        self.custom_row = QWidget()
        flow = FlowLayout(self.custom_row, horizontal_spacing=8, vertical_spacing=6, center_rows=True)
        self.custom_from = WorkDateEdit()
        self.custom_to = WorkDateEdit()
        now = QDate.currentDate()
        self.custom_from.setDate(now.addMonths(-1))
        self.custom_to.setDate(now)
        apply = QPushButton("Aplicar período")
        apply.clicked.connect(self.refresh)
        flow.addWidget(QLabel("Desde"))
        flow.addWidget(self.custom_from)
        flow.addWidget(QLabel("Hasta"))
        flow.addWidget(self.custom_to)
        flow.addWidget(apply)
        self.custom_row.setVisible(False)
        return self.custom_row

    def _build_hero(self) -> QFrame:
        hero = QFrame()
        hero.setObjectName("AnalysisHero")
        layout = QVBoxLayout(hero)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(12)
        self.hero_period = QLabel()
        self.hero_period.setObjectName("SectionTitle")
        self.hero_period.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.distribution = CategoryDistributionBar()
        self.hero_value = QLabel("$ 0")
        self.hero_value.setObjectName("AnalysisHeroValue")
        self.hero_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hero_meta = QLabel()
        self.hero_meta.setObjectName("SmallMuted")
        self.hero_meta.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hero_meta.setWordWrap(True)
        layout.addWidget(self.hero_period)
        layout.addWidget(self.distribution)
        layout.addWidget(self.hero_value)
        layout.addWidget(self.hero_meta)
        return hero

    def _build_category_section(self, root: QVBoxLayout) -> None:
        header = QHBoxLayout()
        title = QLabel("Categorías")
        title.setObjectName("SectionTitle")
        self.category_hint = QLabel("De mayor a menor")
        self.category_hint.setObjectName("SmallMuted")
        header.addWidget(title)
        header.addSpacing(8)
        header.addWidget(self.category_hint)
        header.addStretch()
        root.addLayout(header)

        self.categories_host = QWidget()
        self.categories_host.setMaximumWidth(1500)
        self.categories_layout = QVBoxLayout(self.categories_host)
        self.categories_layout.setContentsMargins(0, 0, 0, 0)
        self.categories_layout.setSpacing(9)
        root.addWidget(self.categories_host, 0, Qt.AlignmentFlag.AlignHCenter)

        self.history_note = QLabel()
        self.history_note.setObjectName("AnalysisHistoryNote")
        self.history_note.setWordWrap(True)
        self.history_note.setVisible(False)
        root.addWidget(self.history_note)
        root.addStretch()

    def _fmt(self, value):
        return money(value, self.db.currency_symbol(), self.db.balances_hidden())

    def set_kind(self, kind: str) -> None:
        self.kind = kind
        self.refresh()

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self.custom_row.setVisible(mode == "custom")
        self.prev.setEnabled(mode != "custom")
        self.next.setEnabled(mode != "custom")
        self.refresh()

    def go_today(self) -> None:
        self.focus_date = date.today()
        if self.mode == "custom":
            today = QDate.currentDate()
            self.custom_from.setDate(today.addMonths(-1))
            self.custom_to.setDate(today)
        self.refresh()

    def shift_period(self, direction: int) -> None:
        if self.mode == "day":
            self.focus_date += timedelta(days=direction)
        elif self.mode == "week":
            self.focus_date += timedelta(days=7 * direction)
        elif self.mode == "month":
            self.focus_date = add_months(self.focus_date.replace(day=1), direction)
        elif self.mode == "year":
            try:
                self.focus_date = self.focus_date.replace(year=self.focus_date.year + direction)
            except ValueError:
                self.focus_date = self.focus_date.replace(year=self.focus_date.year + direction, day=28)
        self.refresh()

    def _bounds(self):
        f = self.focus_date
        if self.mode == "day":
            return f, f
        if self.mode == "week":
            start = week_start(f)
            return start, week_end(start)
        if self.mode == "month":
            return date(f.year, f.month, 1), date(f.year, f.month, monthrange(f.year, f.month)[1])
        if self.mode == "year":
            return date(f.year, 1, 1), date(f.year, 12, 31)
        start = self.custom_from.date().toPython()
        end = self.custom_to.date().toPython()
        return (start, end) if start <= end else (end, start)

    def _period_text(self, start: date, end: date) -> str:
        if self.mode == "day":
            return f"{start.day} de {MONTHS[start.month - 1].lower()} de {start.year}"
        if self.mode == "week":
            if start.month == end.month:
                return f"{start.day} – {end.day} de {MONTHS[start.month - 1].lower()} {end.year}"
            return f"{start.day} {MONTHS[start.month - 1][:3].lower()} – {end.day} {MONTHS[end.month - 1][:3].lower()} {end.year}"
        if self.mode == "month":
            return f"{MONTHS[start.month - 1]} {start.year}"
        if self.mode == "year":
            return str(start.year)
        return f"{start:%d/%m/%Y} – {end:%d/%m/%Y}"

    def _open_category_movements(self, category_id: int) -> None:
        start, end = self._bounds()
        dialog = CategoryBreakdownDialog(self.db, self.kind, int(category_id), start, end, self.mode, self._fmt, self)
        dialog.open_transactions_requested.connect(self.open_transactions_requested)
        dialog.data_changed.connect(self._movement_added)
        dialog.exec()

    def _movement_added(self):
        self.refresh()
        self.data_changed.emit()

    def _open_direct_movements(self, category_id: int) -> None:
        start, end = self._bounds()
        self.open_transactions_requested.emit({
            "kind": self.kind,
            "category_id": int(category_id),
            "start": start.isoformat(),
            "end": end.isoformat(),
            "mode": self.mode,
        })

    def refresh(self) -> None:
        start, end = self._bounds()
        period_text = self._period_text(start, end)
        self.period_label.setText(period_text)
        self.hero_period.setText(period_text)
        summary = self.db.period_summary(start, end, include_history=True)
        categories = self.db.category_totals_period(self.kind, start, end, include_history=True)
        total = summary["expense"] if self.kind == "expense" else summary["income"]
        hist_total = summary["history_expense"] if self.kind == "expense" else summary["history_income"]
        count = summary["expense_count"] if self.kind == "expense" else summary["income_count"]

        self.hero_value.setText(self._fmt(total))
        meta = f"{count} movimiento{'s' if count != 1 else ''}" if count else "Sin movimientos con fecha exacta"
        if hist_total:
            meta += f" · incluye {self._fmt(hist_total)} de historial mensual"
        self.hero_meta.setText(meta)
        self.distribution.set_data(categories[:10])

        clear_layout(self.categories_layout)
        if not categories:
            empty = QFrame()
            empty.setObjectName("SoftCard")
            box = QVBoxLayout(empty)
            box.setContentsMargins(16, 18, 16, 18)
            label = QLabel("Todavía no hay datos para este período.")
            label.setObjectName("Muted")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            box.addWidget(label)
            self.categories_layout.addWidget(empty)
        else:
            narrow = responsive_mode(self.width(), self.height()) == "narrow"
            for category in categories[:16]:
                value = float(category.get("total") or 0)
                share = value / total * 100 if total else 0
                row = AnalysisCategoryRow(category, share, self._fmt(value), narrow=narrow)
                row.activated.connect(self._open_category_movements)
                self.categories_layout.addWidget(row)

        if hist_total:
            self.history_note.setText("El total incluye historial mensual importado; no se inventan fechas para esos importes.")
            self.history_note.setVisible(True)
        else:
            self.history_note.setVisible(False)
        self._apply_responsive_layout()

    def _apply_responsive_layout(self) -> None:
        mode = responsive_mode(self.width(), self.height())
        compact = mode != "wide"
        previous = self._compact_layout
        self._compact_layout = compact
        self.period_label.setMinimumWidth(120 if mode == "narrow" else 150 if compact else 230)
        for button in self.mode_buttons.values():
            button.setMinimumWidth(0)

        # El contenedor no depende de su sizeHint (que antes lo reducía al
        # ancho del texto). En escritorio ocupa una franja claramente más
        # ancha, como la referencia, y sólo se contrae cuando falta espacio.
        available = max(320, self.width() - (36 if mode == "narrow" else 72))
        if mode == "wide":
            # Más cerca del ranking ancho original que gustaba visualmente,
            # dejando todavía aire a ambos lados en monitores grandes.
            target = min(1500, max(1180, available - 160))
        elif mode == "compact":
            target = min(980, available)
        else:
            target = available
        self.categories_host.setFixedWidth(int(target))

        if previous != compact and self.isVisible():
            QTimer.singleShot(0, self.refresh)

    def showEvent(self, event):
        super().showEvent(event)
        # Al mostrarse por primera vez ya conocemos el viewport real. La propia
        # aplicación responsive programa el refresh si el modo aún no estaba
        # inicializado o cambió respecto del anterior.
        self._apply_responsive_layout()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_responsive_layout()

