from __future__ import annotations

"""Gestión jerárquica de categorías.

Las categorías ya no están limitadas a dos niveles. Una categoría puede vivir
adentro de cualquier otra del mismo tipo y la interfaz mantiene la jerarquía
visible sin convertirla en una tabla rígida.
"""

from collections import defaultdict

from PySide6.QtCore import Qt, Signal, QTimer, QPoint, QMimeData
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import (
    QBoxLayout,
    QFrame,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..dialogs import CategoryDialog
from ..layouts import responsive_mode
from ..widgets import IconBadge
from .common import page_header


class CategoryNodeRow(QFrame):
    """Fila de una categoría en el árbol visual."""

    add_child_requested = Signal(int)
    edit_requested = Signal(int)
    delete_requested = Signal(int)
    duplicate_requested = Signal(int)
    move_requested = Signal(int, int)
    toggle_requested = Signal(int)

    def __init__(self, category: dict, child_count: int, depth: int = 0, expanded: bool = False, parent=None):
        super().__init__(parent)
        self.category = category
        self.cid = int(category["id"])
        self.depth = max(0, int(depth))
        self.setObjectName("CategoryTreeRow")
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip("Arrastrá sobre otra categoría para moverla · doble clic para editar · clic derecho para acciones")
        self.setAcceptDrops(True)
        self._drag_start = QPoint()

        root = QBoxLayout(QBoxLayout.Direction.LeftToRight, self)
        self.root_layout = root
        root.setContentsMargins(12 + min(5, self.depth) * 18, 9, 12, 9)
        root.setSpacing(8)

        self.disclosure = QPushButton("▾" if expanded else "›")
        self.disclosure.setObjectName("DisclosureButton")
        self.disclosure.setFixedSize(26, 34)
        self.disclosure.setCursor(Qt.CursorShape.PointingHandCursor)
        self.disclosure.setToolTip("Contraer" if expanded else "Desplegar")
        self.disclosure.setVisible(bool(child_count))
        self.disclosure.clicked.connect(lambda: self.toggle_requested.emit(self.cid))
        root.addWidget(self.disclosure, 0, Qt.AlignmentFlag.AlignVCenter)

        root.addWidget(
            IconBadge(
                category.get("icon") or "other",
                category.get("color") or "#4CCFA9",
                40,
                secondary_color=category.get("secondary_color"),
            )
        )

        text_box = QVBoxLayout()
        text_box.setSpacing(1)
        name = QLabel(str(category.get("name") or "Categoría"))
        name.setObjectName("CategoryItemName")
        name.setWordWrap(True)
        text_box.addWidget(name)
        meta_bits = []
        if child_count:
            meta_bits.append(f"{child_count} subcategoría{'s' if child_count != 1 else ''}")
        if category.get("path_parent"):
            meta_bits.append(str(category.get("path_parent")))
        meta = QLabel(" · ".join(meta_bits) if meta_bits else "Categoría final")
        meta.setObjectName("SmallMuted")
        meta.setWordWrap(True)
        text_box.addWidget(meta)
        root.addLayout(text_box, 1)

        add = QPushButton("＋ Subcategoría")
        add.setObjectName("CategoryAddChild")
        add.clicked.connect(lambda: self.add_child_requested.emit(self.cid))
        root.addWidget(add)

    def set_expanded(self, expanded: bool) -> None:
        """Actualiza sólo el indicador visual sin reconstruir la fila."""
        self.disclosure.setText("▾" if expanded else "›")
        self.disclosure.setToolTip("Contraer" if expanded else "Desplegar")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # En tarjetas angostas la acción baja a una segunda línea en vez de
        # comprimir nombre/ruta hasta volverlos ilegibles.
        compact = self.width() < 540
        self.root_layout.setDirection(
            QBoxLayout.Direction.TopToBottom if compact else QBoxLayout.Direction.LeftToRight
        )

    def mouseDoubleClickEvent(self, event):
        self.edit_requested.emit(self.cid)
        event.accept()

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        add = menu.addAction("Agregar subcategoría")
        edit = menu.addAction("Editar / mover")
        duplicate = menu.addAction("Duplicar")
        menu.addSeparator()
        delete = menu.addAction("Eliminar")
        chosen = menu.exec(event.globalPos())
        if chosen == add:
            self.add_child_requested.emit(self.cid)
        elif chosen == edit:
            self.edit_requested.emit(self.cid)
        elif chosen == duplicate:
            self.duplicate_requested.emit(self.cid)
        elif chosen == delete:
            self.delete_requested.emit(self.cid)


    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            super().mouseMoveEvent(event)
            return
        if (event.position().toPoint() - self._drag_start).manhattanLength() < 10:
            super().mouseMoveEvent(event)
            return
        mime = QMimeData()
        mime.setData("application/x-appgastos-category-id", str(self.cid).encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime)
        # El propio card acompaña el cursor como feedback visual, similar al
        # gesto de agrupar iconos en un launcher móvil.
        drag.setPixmap(self.grab())
        drag.setHotSpot(event.position().toPoint())
        drag.exec(Qt.DropAction.MoveAction)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-appgastos-category-id"):
            try:
                source_id = int(bytes(event.mimeData().data("application/x-appgastos-category-id")).decode("utf-8"))
            except Exception:
                event.ignore(); return
            if source_id != self.cid:
                self.setProperty("dropTarget", True)
                self.style().unpolish(self); self.style().polish(self)
                event.acceptProposedAction(); return
        event.ignore()

    def dragLeaveEvent(self, event):
        self.setProperty("dropTarget", False)
        self.style().unpolish(self); self.style().polish(self)
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        self.setProperty("dropTarget", False)
        self.style().unpolish(self); self.style().polish(self)
        try:
            source_id = int(bytes(event.mimeData().data("application/x-appgastos-category-id")).decode("utf-8"))
        except Exception:
            event.ignore(); return
        if source_id == self.cid:
            event.ignore(); return
        self.move_requested.emit(source_id, self.cid)
        event.acceptProposedAction()


class CategoryTreeGroup(QFrame):
    """Subárbol persistente de una categoría principal.

    Las filas se crean una sola vez por refresh estructural. Expandir/contraer
    sólo cambia visibilidad, evitando reconstruir la página completa y perder
    la posición del scroll.
    """

    add_child_requested = Signal(int)
    edit_requested = Signal(int)
    delete_requested = Signal(int)
    duplicate_requested = Signal(int)
    move_requested = Signal(int, int)

    def __init__(
        self,
        root_category: dict,
        by_parent: dict[int | None, list[dict]],
        visible_ids: set[int] | None = None,
        expanded_ids: set[int] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("CategoryGroupCard")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(8, 8, 8, 8)
        self._layout.setSpacing(7)
        self._expanded_ids = expanded_ids if expanded_ids is not None else set()
        self._search_mode = visible_ids is not None
        self._visible_ids = visible_ids
        self._rendered_ids: set[int] = set()
        self._rows: dict[int, CategoryNodeRow] = {}
        self._parents: dict[int, int | None] = {}
        self._children: dict[int, list[int]] = {}

        self._append_node(root_category, by_parent, visible_ids, 0, None)
        self._apply_visibility()

    def _append_node(
        self,
        category: dict,
        by_parent: dict[int | None, list[dict]],
        visible_ids: set[int] | None,
        depth: int,
        parent_id: int | None,
    ) -> None:
        cid = int(category["id"])
        if cid in self._rendered_ids:
            return
        if visible_ids is not None and cid not in visible_ids:
            return
        self._rendered_ids.add(cid)

        children = [
            child for child in by_parent.get(cid, [])
            if visible_ids is None or int(child["id"]) in visible_ids
        ]
        expanded = bool(children) and (self._search_mode or cid in self._expanded_ids)
        row = CategoryNodeRow(category, len(children), depth, expanded=expanded)
        row.add_child_requested.connect(self.add_child_requested)
        row.edit_requested.connect(self.edit_requested)
        row.delete_requested.connect(self.delete_requested)
        row.duplicate_requested.connect(self.duplicate_requested)
        row.move_requested.connect(self.move_requested)
        row.toggle_requested.connect(self._toggle_node)
        self._layout.addWidget(row)

        self._rows[cid] = row
        self._parents[cid] = parent_id
        self._children[cid] = [int(child["id"]) for child in children]
        for child in children:
            self._append_node(child, by_parent, visible_ids, depth + 1, cid)

    def _toggle_node(self, category_id: int) -> None:
        # Durante una búsqueda las ramas están abiertas de forma deliberada para
        # mostrar el contexto completo del resultado.
        if self._search_mode:
            return
        cid = int(category_id)
        if cid in self._expanded_ids:
            self._expanded_ids.remove(cid)
        else:
            self._expanded_ids.add(cid)
        self._apply_visibility()

    def _apply_visibility(self) -> None:
        logical_visibility: dict[int, bool] = {}
        for cid, row in self._rows.items():
            parent_id = self._parents.get(cid)
            if parent_id is None:
                visible = True
            else:
                parent_visible = logical_visibility.get(parent_id, False)
                parent_open = self._search_mode or parent_id in self._expanded_ids
                visible = parent_visible and parent_open
            logical_visibility[cid] = visible
            row.setVisible(visible)

            has_children = bool(self._children.get(cid))
            expanded = has_children and (self._search_mode or cid in self._expanded_ids)
            row.set_expanded(expanded)

        self._layout.invalidate()
        self.updateGeometry()


class CategoriesPage(QWidget):
    data_changed = Signal()

    def __init__(self, db):
        super().__init__()
        self.db = db
        self.current_kind = "expense"
        self._mode = None
        self._move_in_progress = False
        self._expanded_ids: set[int] = set()

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

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setObjectName("CategoryManageScroll")
        self.host = QWidget()
        self.groups_layout = QVBoxLayout(self.host)
        self.groups_layout.setContentsMargins(0, 0, 8, 0)
        self.groups_layout.setSpacing(11)
        self.scroll.setWidget(self.host)
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
        self.expense_btn.setChecked(kind == "expense")
        self.income_btn.setChecked(kind == "income")
        self.refresh(preserve_scroll=False)

    def _refresh_from_search(self) -> None:
        self.refresh(preserve_scroll=False)

    def _tree_data(self):
        rows = self.db.categories(self.current_kind)
        by_parent: dict[int | None, list[dict]] = defaultdict(list)
        for row in rows:
            pid = int(row["parent_id"]) if row.get("parent_id") is not None else None
            by_parent[pid].append(row)
        for values in by_parent.values():
            values.sort(key=lambda row: (int(row.get("sort_order") or 0), str(row.get("name") or "").casefold()))

        query = self.search.text().strip().casefold()
        visible_ids: set[int] | None = None
        if query:
            by_id = {int(row["id"]): row for row in rows}
            visible_ids = set()
            for row in rows:
                hay = f"{row.get('name','')} {row.get('path','')}".casefold()
                if query not in hay:
                    continue
                current = row
                while current:
                    cid = int(current["id"])
                    visible_ids.add(cid)
                    pid = current.get("parent_id")
                    current = by_id.get(int(pid)) if pid is not None else None
                # También mostramos descendientes del resultado para conservar contexto.
                visible_ids.update(self.db.category_descendant_ids(int(row["id"]), include_self=True))
        return rows, by_parent, visible_ids

    def _clear_groups_now(self) -> None:
        """Retira los grupos viejos del layout de forma inmediata.

        ``deleteLater()`` solo difiere la destrucción hasta el próximo ciclo de
        eventos. Durante un drop eso podía dejar a la vista, por unos instantes
        (o hasta otro repintado), la fila antigua y la nueva a la vez, dando la
        impresión de que la categoría se había duplicado. Desacoplar el widget
        del layout y de su padre elimina esa representación vieja al instante.
        """
        while self.groups_layout.count():
            item = self.groups_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()

    def refresh(self, preserve_scroll: bool = True):
        """Reconstruye sólo cuando cambió la estructura o el filtro.

        Expandir/contraer categorías no llama a este método: ``CategoryTreeGroup``
        mantiene sus filas y alterna visibilidad localmente. Cuando sí hace falta
        reconstruir (alta, edición, drag/drop), conservamos la posición de scroll
        para evitar saltos visuales.
        """
        scrollbar = self.scroll.verticalScrollBar()
        previous_scroll = scrollbar.value() if preserve_scroll else 0
        self.host.setUpdatesEnabled(False)
        try:
            self._clear_groups_now()
            rows, by_parent, visible_ids = self._tree_data()
            roots = by_parent.get(None, [])
            max_depth = max((int(row.get("depth") or 0) for row in rows), default=0)
            self.counter.setText(f"{len(rows)} categorías · {max_depth + 1 if rows else 0} niveles")

            shown = 0
            for root_category in roots:
                if visible_ids is not None and int(root_category["id"]) not in visible_ids:
                    continue
                group = CategoryTreeGroup(root_category, by_parent, visible_ids, self._expanded_ids)
                group.add_child_requested.connect(self.add_subcategory)
                group.edit_requested.connect(self.edit_category)
                group.delete_requested.connect(self.delete_category)
                group.duplicate_requested.connect(self.duplicate_category)
                group.move_requested.connect(self.move_category)
                self.groups_layout.addWidget(group)
                shown += 1
            if not shown:
                empty = QFrame()
                empty.setObjectName("SoftCard")
                box = QVBoxLayout(empty)
                box.setContentsMargins(22, 28, 22, 28)
                title = QLabel("No encontré categorías")
                title.setObjectName("SectionTitle")
                title.setAlignment(Qt.AlignmentFlag.AlignCenter)
                subtitle = QLabel("Probá otra búsqueda o creá una categoría nueva.")
                subtitle.setObjectName("Muted")
                subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
                box.addWidget(title)
                box.addWidget(subtitle)
                self.groups_layout.addWidget(empty)
            self.groups_layout.addStretch()
        finally:
            self.host.setUpdatesEnabled(True)

        # El rango del scrollbar se recalcula al terminar el ciclo de layout.
        # Restauramos después para no depender de un maximum() todavía viejo.
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
        target = self.db.category(int(target_id))
        if not source or not target:
            return
        if int(source_id) == int(target_id):
            return
        if str(source.get("kind")) != str(target.get("kind")):
            QMessageBox.warning(self, "Mover categoría", "Sólo podés mover categorías dentro del mismo tipo.")
            return

        self._move_in_progress = True
        try:
            self.db.move_category(int(source_id), int(target_id))
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
