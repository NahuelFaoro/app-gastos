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
from .category_tiles import CategoryTile, CategoryDropButton
from .common import page_header


class CategoriesPage(QWidget):
    data_changed = Signal()

    def __init__(self, db):
        super().__init__()
        self.db = db
        self.current_kind = "expense"
        self._mode = None
        self._move_in_progress = False
        self.current_parent = None
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
        add.clicked.connect(lambda: self.add_category(self.current_parent))
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
        self.home_button = CategoryDropButton("Todas")
        self.home_button.clicked.connect(lambda: self.open_folder(None))
        self.home_button.move_requested.connect(self.move_category)
        self.back_button = CategoryDropButton("↑ Subir")
        self.back_button.clicked.connect(self.go_up)
        self.back_button.move_requested.connect(self.move_category)
        self.path_label = QLabel()
        self.path_label.setObjectName("Muted")
        self.path_label.setWordWrap(True)
        navigation.addWidget(self.home_button)
        navigation.addWidget(self.back_button)
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
        self.current_parent = None
        self.expense_btn.setChecked(kind == "expense")
        self.income_btn.setChecked(kind == "income")
        self.refresh(preserve_scroll=False)

    def _refresh_from_search(self) -> None:
        self.refresh(preserve_scroll=False)

    def open_folder(self, category_id: int | None) -> None:
        self.current_parent = category_id
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        self._search_timer.stop()
        self.refresh(preserve_scroll=False)

    def go_up(self) -> None:
        category = self.db.category(self.current_parent) if self.current_parent else None
        self.open_folder(category.get("parent_id") if category else None)

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
        cell_width = max(170, self.fontMetrics().horizontalAdvance("Categorías personales") + 32)
        columns = max(1, available // (cell_width + 12))
        for column in range(max(self._columns, columns)):
            self.groups_layout.setColumnStretch(column, 1 if column < columns else 0)
        for tile in self._tiles:
            self.groups_layout.removeWidget(tile)
        for index, tile in enumerate(self._tiles):
            self.groups_layout.addWidget(tile, index // columns, index % columns)
        self._columns = columns

    def _clear_groups_now(self) -> None:
        self._tiles = []
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
        if self.current_parent not in by_id:
            self.current_parent = None
        current = by_id.get(self.current_parent)
        self.path_label.setText(str(current.get("path") or current["name"]) if current else "Categorías principales")
        self.back_button.setEnabled(current is not None)
        self.back_button.target_id = int(current.get("parent_id") or 0) if current else 0
        self.home_button.setToolTip("Volver al inicio · soltá aquí una categoría para llevarla al nivel principal")
        self.back_button.setToolTip("Subir un nivel · soltá aquí una categoría para moverla al nivel superior")
        query = self.search.text().strip().casefold()
        visible = ([row for row in rows if query in str(row.get("path") or row["name"]).casefold()]
                   if query else by_parent.get(self.current_parent, []))
        visible = sorted(visible, key=lambda row: (int(row.get("sort_order") or 0), row["name"].casefold()))
        self.counter.setText(f"{len(visible)} visibles · {len(rows)} categorías")
        self.host.setUpdatesEnabled(False)
        try:
            self._clear_groups_now()
            for category in visible:
                tile = CategoryTile(category, by_parent.get(int(category["id"]), []))
                tile.opened.connect(self.open_folder)
                tile.edit_requested.connect(self.edit_category)
                tile.add_child_requested.connect(self.add_subcategory)
                tile.delete_requested.connect(self.delete_category)
                tile.duplicate_requested.connect(self.duplicate_category)
                # El drop termina antes de reconstruir y destruir su widget origen.
                tile.move_requested.connect(self.move_category, Qt.ConnectionType.QueuedConnection)
                self._tiles.append(tile)
            if self._tiles:
                self._arrange_tiles()
            else:
                empty = QLabel("No hay resultados." if query else "Esta carpeta está vacía. Usá Nueva categoría para agregar una subcategoría.")
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
