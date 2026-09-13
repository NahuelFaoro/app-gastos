from __future__ import annotations

"""Gestión jerárquica de categorías.

Las categorías ya no están limitadas a dos niveles. Una categoría puede vivir
adentro de cualquier otra del mismo tipo y la interfaz mantiene la jerarquía
visible sin convertirla en una tabla rígida.
"""

from collections import defaultdict

from PySide6.QtCore import Qt, Signal, QTimer, QEvent
from PySide6.QtWidgets import (
    QBoxLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..dialogs import CategoryDialog
from ..layouts import responsive_mode
from .category_tiles import CategoryPanel, CategoryDropButton
from .common import page_header


class CategoriesPage(QWidget):
    data_changed = Signal()

    def __init__(self, db):
        super().__init__()
        self.db = db
        self.current_kind = "expense"
        self._mode = None
        self._move_in_progress = False
        self._expanded_ids = set()
        self._known_roots = set()
        self._tiles = []
        self._columns = 0

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 28)
        root.setSpacing(15)

        self.top_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.top_layout.addWidget(page_header(
            "Categorías",
            "Organizá categorías en tantos niveles como necesites y movelas sin perder movimientos.",
        ))
        self.top_layout.addStretch()
        add = QPushButton("Nueva categoría")
        add.clicked.connect(lambda: self.add_category())
        self.top_layout.addWidget(add)
        root.addLayout(self.top_layout)

        toolbar = QFrame()
        toolbar.setObjectName("CategoryToolbar")
        self.toolbar_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight, toolbar)
        self.toolbar_layout.setContentsMargins(10, 9, 10, 9)
        self.toolbar_layout.setSpacing(8)
        self.expense_btn = QPushButton("Gastos")
        self.expense_btn.setObjectName("SegmentButton")
        self.expense_btn.setCheckable(True)
        self.expense_btn.setChecked(True)
        self.income_btn = QPushButton("Ingresos")
        self.income_btn.setObjectName("SegmentButton")
        self.income_btn.setCheckable(True)
        self.expense_btn.clicked.connect(lambda: self.set_kind("expense"))
        self.income_btn.clicked.connect(lambda: self.set_kind("income"))
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar por nombre o ruta…")
        self.search.setClearButtonEnabled(True)
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(140)
        self._search_timer.timeout.connect(self._refresh_from_search)
        self.search.textChanged.connect(lambda: self._search_timer.start())
        self.counter = QLabel()
        self.counter.setObjectName("SmallMuted")
        self.toolbar_layout.addWidget(self.expense_btn)
        self.toolbar_layout.addWidget(self.income_btn)
        self.toolbar_layout.addSpacing(5)
        self.toolbar_layout.addWidget(self.search, 1)
        self.toolbar_layout.addWidget(self.counter)
        root.addWidget(toolbar)

        navigation = QHBoxLayout()
        self.home_button = CategoryDropButton("Soltar aquí para hacer principal")
        self.home_button.move_requested.connect(self.move_category)
        self.path_label = QLabel("Desplegá varias categorías a la vez · ↑ saca una subcategoría un nivel")
        self.path_label.setObjectName("Muted")
        self.path_label.setWordWrap(True)
        navigation.addWidget(self.home_button)
        navigation.addWidget(self.path_label, 1)
        root.addLayout(navigation)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setObjectName("CategoryManageScroll")
        self.host = QWidget()
        self.groups_layout = QGridLayout(self.host)
        self.groups_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.groups_layout.setContentsMargins(0, 0, 8, 0)
        self.groups_layout.setSpacing(11)
        self.scroll.setWidget(self.host)
        self.scroll.viewport().installEventFilter(self)
        root.addWidget(self.scroll, 1)

        self.refresh()
        self._apply_responsive(force=True)

    def _apply_responsive(self, force: bool = False):
        mode = responsive_mode(self.width(), self.height())
        if not force and mode == self._mode:
            return
        self._mode = mode
        compact = mode != "wide"
        direction = QBoxLayout.Direction.TopToBottom if compact else QBoxLayout.Direction.LeftToRight
        self.top_layout.setDirection(direction)
        self.toolbar_layout.setDirection(direction)
        margins = 14 if mode == "narrow" else 20 if compact else 28
        self.layout().setContentsMargins(margins, 18 if compact else 24, margins, 20 if compact else 28)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_responsive()

    def set_kind(self, kind):
        self.current_kind = kind
        self._expanded_ids = set()
        self._known_roots = set()
        self.expense_btn.setChecked(kind == "expense")
        self.income_btn.setChecked(kind == "income")
        self.refresh(preserve_scroll=False)

    def _refresh_from_search(self) -> None:
        self.refresh(preserve_scroll=False)

    def lift_category(self, category_id: int) -> None:
        category = self.db.category(category_id)
        if not category or category.get("parent_id") is None:
            return
        parent = self.db.category(int(category["parent_id"]))
        self.move_category(category_id, int(parent.get("parent_id") or 0) if parent else 0)

    def _connect_row(self, row) -> None:
        row.edit_requested.connect(self.edit_category)
        row.add_child_requested.connect(self.add_subcategory)
        row.delete_requested.connect(self.delete_category)
        row.duplicate_requested.connect(self.duplicate_category)
        row.lift_requested.connect(self.lift_category, Qt.ConnectionType.QueuedConnection)
        row.move_requested.connect(self.move_category, Qt.ConnectionType.QueuedConnection)

    def eventFilter(self, watched, event):
        if watched is self.scroll.viewport() and event.type() == QEvent.Type.Resize:
            QTimer.singleShot(0, self._arrange_tiles)
        return super().eventFilter(watched, event)

    def _arrange_tiles(self) -> None:
        if not self._tiles:
            return
        available = max(1, self.scroll.viewport().width() - 8)
        # La celda sigue el tamaño tipográfico; el número de columnas depende
        # del viewport real, no del tamaño provisional de la página oculta.
        cell_width = max(350, self.fontMetrics().horizontalAdvance("Categorías personales") + 170)
        columns = max(1, available // (cell_width + 12))
        if columns == self._columns:
            return
        for tile in self._tiles:
            tile.setParent(None)
        while self.groups_layout.count():
            item = self.groups_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for column in range(max(self._columns, columns)):
            self.groups_layout.setColumnStretch(column, 1 if column < columns else 0)
        stacks = []
        for column in range(columns):
            host = QWidget()
            stack = QVBoxLayout(host)
            stack.setContentsMargins(0, 0, 0, 0)
            stack.setSpacing(11)
            stacks.append(stack)
            self.groups_layout.addWidget(host, 0, column)
        for index, tile in enumerate(self._tiles):
            stacks[index % columns].addWidget(tile)
            tile.show()
        for stack in stacks:
            stack.addStretch()
        self._columns = columns

    def _clear_groups_now(self) -> None:
        self._tiles = []
        for column in range(self._columns):
            self.groups_layout.setColumnStretch(column, 0)
        self._columns = 0
        while self.groups_layout.count():
            item = self.groups_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()

    def refresh(self, preserve_scroll: bool = True):
        scrollbar = self.scroll.verticalScrollBar()
        previous_scroll = scrollbar.value() if preserve_scroll else 0
        rows = self.db.categories(self.current_kind)
        by_id = {int(row["id"]): row for row in rows}
        by_parent = defaultdict(list)
        for row in rows:
            by_parent[row.get("parent_id")].append(row)
        roots = by_parent.get(None, [])
        root_ids = {int(row["id"]) for row in roots}
        self._expanded_ids.update(root_ids - self._known_roots)
        self._known_roots = root_ids
        query = self.search.text().strip().casefold()
        visible_ids = None
        if query:
            visible_ids = set()
            for row in rows:
                if query not in str(row.get("path") or row["name"]).casefold():
                    continue
                current = row
                while current:
                    cid = int(current["id"])
                    if cid in visible_ids:
                        break
                    visible_ids.add(cid)
                    current = by_id.get(current.get("parent_id"))
        self.counter.setText(f"{len(rows)} categorías")
        self.host.setUpdatesEnabled(False)
        try:
            self._clear_groups_now()
            for category in roots:
                if visible_ids is not None and int(category["id"]) not in visible_ids:
                    continue
                panel = CategoryPanel(category, by_parent, self._expanded_ids, self._connect_row, visible_ids)
                self._tiles.append(panel)
            if self._tiles:
                self._arrange_tiles()
            else:
                empty = QLabel("No hay resultados." if query else "Usá Nueva categoría para empezar.")
                empty.setObjectName("Muted")
                empty.setWordWrap(True)
                empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.groups_layout.addWidget(empty, 0, 0, 1, max(1, self._columns))
        finally:
            self.host.setUpdatesEnabled(True)
        QTimer.singleShot(0, lambda value=previous_scroll: scrollbar.setValue(min(value, scrollbar.maximum())))

    def add_category(self, parent_id=None):
        dlg = CategoryDialog(self.db, preset_kind=self.current_kind, preset_parent_id=parent_id, parent=self)
        if dlg.exec():
            try:
                self.db.add_category(*dlg.data())
            except Exception as exc:
                QMessageBox.warning(self, "Categoría", str(exc))
                return
            self.refresh()
            self.data_changed.emit()

    def add_subcategory(self, parent_id):
        self.add_category(int(parent_id))

    def edit_category(self, category_id=None):
        if not category_id:
            return
        category = self.db.category(int(category_id))
        if not category:
            return
        dlg = CategoryDialog(self.db, category=category, parent=self)
        if dlg.exec():
            try:
                self.db.update_category(int(category_id), *dlg.data())
            except Exception as exc:
                QMessageBox.warning(self, "Categoría", str(exc))
                return
            self.refresh()
            self.data_changed.emit()

    def duplicate_category(self, category_id=None):
        if not category_id:
            return
        category = self.db.category(int(category_id))
        if not category:
            return
        try:
            self.db.duplicate_category(int(category_id))
        except Exception as exc:
            QMessageBox.warning(self, "Duplicar categoría", str(exc))
            return
        self.refresh()
        self.data_changed.emit()

    def move_category(self, source_id: int, target_id: int):
        if self._move_in_progress:
            return
        source = self.db.category(int(source_id))
        target = self.db.category(int(target_id)) if target_id else None
        if not source or (target_id and not target):
            return
        if int(source_id) == int(target_id):
            return
        if target and str(source.get("kind")) != str(target.get("kind")):
            QMessageBox.warning(self, "Mover categoría", "Sólo podés mover categorías dentro del mismo tipo.")
            return

        self._move_in_progress = True
        try:
            self.db.move_category(int(source_id), int(target_id) if target_id else None)
        except Exception as exc:
            QMessageBox.warning(self, "Mover categoría", str(exc))
            return
        finally:
            self._move_in_progress = False

        self.refresh()
        self.data_changed.emit()

    def delete_category(self, category_id=None):
        if not category_id:
            return
        category = self.db.category(int(category_id))
        if not category:
            return
        message = f"¿Eliminar ‘{category['name']}’?"
        if self.db.category_children(int(category_id), self.current_kind):
            message += "\n\nTambién se eliminará su subárbol siempre que no tenga datos en uso."
        if QMessageBox.question(self, "Eliminar categoría", message) != QMessageBox.StandardButton.Yes:
            return
        try:
            self.db.delete_category(int(category_id))
        except Exception as exc:
            QMessageBox.warning(self, "No se puede eliminar", str(exc))
            return
        self.refresh()
        self.data_changed.emit()
