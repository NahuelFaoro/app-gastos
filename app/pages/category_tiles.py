"""Paneles jerárquicos desplegables en una misma pantalla."""
from PySide6.QtCore import Qt, Signal, QPoint, QMimeData
from PySide6.QtGui import QDrag, QPainter, QPen, QPalette
from PySide6.QtWidgets import QApplication, QFrame, QGridLayout, QHBoxLayout, QLabel, QMenu, QPushButton, QSizePolicy, QVBoxLayout

from ..widgets import IconBadge

MIME_CATEGORY = "application/x-appgastos-category-id"


def dragged_category(event) -> int | None:
    if not event.mimeData().hasFormat(MIME_CATEGORY):
        return None
    try:
        return int(bytes(event.mimeData().data(MIME_CATEGORY)).decode("ascii"))
    except (ValueError, UnicodeError):
        return None


class CategoryDropButton(QPushButton):
    move_requested = Signal(int, int)

    def __init__(self, text: str, target_id: int = 0, parent=None):
        super().__init__(text, parent)
        self.target_id = target_id
        self.setAcceptDrops(True)
        self.setObjectName("SecondaryButton")

    def dragEnterEvent(self, event):
        source = dragged_category(event)
        if source is not None and source != self.target_id:
            self.setDown(True)
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.setDown(False)
        event.accept()

    def dropEvent(self, event):
        self.setDown(False)
        source = dragged_category(event)
        if source is not None and source != self.target_id:
            event.acceptProposedAction()
            self.move_requested.emit(source, self.target_id)


class CategoryTile(QFrame):
    opened = Signal(int)
    lift_requested = Signal(int)
    edit_requested = Signal(int)
    add_child_requested = Signal(int)
    duplicate_requested = Signal(int)
    delete_requested = Signal(int)
    move_requested = Signal(int, int)

    def __init__(self, category: dict, children: list[dict], parent=None):
        super().__init__(parent)
        self.cid = int(category["id"])
        self.has_children = bool(children)
        self.depth = 0
        self.lift_destination = category.get("lift_destination", "categorías principales")
        self.setObjectName("CategoryTreeRow")
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip(str(category.get("path") or category.get("name")) + " · arrastrá para mover")
        self._press = QPoint()
        self._dragged = False
        root = QHBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(7)
        self.disclosure = QPushButton("▸")
        self.disclosure.setObjectName("GhostButton")
        self.disclosure.setFixedSize(26, 30)
        self.disclosure.setEnabled(self.has_children)
        self.disclosure.clicked.connect(lambda: self.opened.emit(self.cid))
        root.addWidget(self.disclosure)
        badge = IconBadge(category.get("icon") or "other", category.get("color") or "#4CCFA9", 34,
                          secondary_color=category.get("secondary_color"))
        badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        root.addWidget(badge)
        text = QVBoxLayout()
        name = QLabel(str(category.get("name") or "Categoría"))
        name.setObjectName("CategoryItemName")
        name.setWordWrap(True)
        name.setMinimumWidth(0)
        name.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        name.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        text.addWidget(name)
        if children:
            meta = QLabel(f"{len(children)} subcategorías")
            meta.setObjectName("SmallMuted")
            meta.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            text.addWidget(meta)
        root.addLayout(text, 1)
        self.lift_button = None
        if category.get("parent_id") is not None:
            self.lift_button = QPushButton("↑")
            self.lift_button.setObjectName("GhostButton")
            self.lift_button.setFixedSize(30, 30)
            self.lift_button.setToolTip(f"Mover a {self.lift_destination}")
            self.lift_button.setAccessibleName(f"Mover {category.get('name')} a {self.lift_destination}")
            self.lift_button.clicked.connect(lambda: self.lift_requested.emit(self.cid))
            root.addWidget(self.lift_button)
        menu = QPushButton("⋯")
        menu.setObjectName("GhostButton")
        menu.setFixedSize(30, 30)
        menu.setAccessibleName(f"Acciones de {category.get('name')}")
        menu.clicked.connect(lambda: self._menu(menu.mapToGlobal(menu.rect().bottomLeft())))
        root.addWidget(menu)

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.depth:
            return
        painter = QPainter(self)
        color = self.palette().color(QPalette.ColorRole.Text)
        color.setAlpha(40)
        painter.setPen(QPen(color, 1))
        for level in range(min(self.depth, 4)):
            x = 21 + level * 22
            painter.drawLine(x, 0, x, self.height())
        x = 21 + (min(self.depth, 4) - 1) * 22
        painter.drawLine(x, self.height() // 2, x + 12, self.height() // 2)

    def set_expanded(self, expanded: bool) -> None:
        self.disclosure.setText("▾" if expanded else "▸" if self.has_children else "")
        self.disclosure.setToolTip("Contraer" if expanded else "Desplegar aquí")

    def _menu(self, position):
        menu = QMenu(self)
        actions = [("Desplegar / contraer", self.opened), ("Editar / mover", self.edit_requested),
                   ("Agregar subcategoría", self.add_child_requested),
                   ("Duplicar", self.duplicate_requested), ("Eliminar", self.delete_requested)]
        if self.lift_button is not None:
            actions.insert(1, (f"Mover a {self.lift_destination}", self.lift_requested))
        mapping = {menu.addAction(text): signal for text, signal in actions}
        action = menu.exec(position)
        if action in mapping:
            mapping[action].emit(self.cid)

    def contextMenuEvent(self, event):
        self._menu(event.globalPos())

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.opened.emit(self.cid)
        elif event.key() == Qt.Key.Key_F2:
            self.edit_requested.emit(self.cid)
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._press = event.position().toPoint()
            self._dragged = False
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and not self._dragged and self.rect().contains(event.position().toPoint()):
            self.opened.emit(self.cid)
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        if not event.buttons() & Qt.MouseButton.LeftButton or self._dragged:
            return
        if (event.position().toPoint() - self._press).manhattanLength() < QApplication.startDragDistance():
            return
        self._dragged = True
        mime = QMimeData()
        mime.setData(MIME_CATEGORY, str(self.cid).encode("ascii"))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.setPixmap(self.grab())
        drag.setHotSpot(self._press)
        drag.exec(Qt.DropAction.MoveAction)

    def _highlight(self, enabled: bool):
        self.setProperty("dropTarget", enabled)
        self.style().unpolish(self)
        self.style().polish(self)

    def dragEnterEvent(self, event):
        source = dragged_category(event)
        if source is not None and source != self.cid:
            self._highlight(True)
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self._highlight(False)
        event.accept()

    def dropEvent(self, event):
        self._highlight(False)
        source = dragged_category(event)
        if source is not None and source != self.cid:
            event.acceptProposedAction()
            self.move_requested.emit(source, self.cid)


class CategoryPanel(QFrame):
    """Un grupo principal: conserva filas y despliega sus hijos en el lugar."""
    def __init__(self, category: dict, by_parent: dict, expanded: set[int], connect_row,
                 visible_ids: set[int] | None = None, parent=None):
        super().__init__(parent)
        self.setObjectName("CategoryGroupCard")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self.expanded = expanded
        self.rows = {}
        self.parents = {}
        self.searching = visible_ids is not None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(0)
        pending = [(category, 0, None)]
        while pending:
            item, depth, parent_id = pending.pop()
            cid = int(item["id"])
            if cid in self.rows or (visible_ids is not None and cid not in visible_ids):
                continue
            children = by_parent.get(cid, [])
            row = CategoryTile(item, children)
            # Todos los niveles tienen la misma columna de iconos, más una
            # sangría por ascendiente. Nunca desaparece el espacio del indicador.
            row.depth = depth
            row.layout().setContentsMargins(8 + min(depth, 4) * 22, 8, 8, 8)
            row.opened.connect(self.toggle)
            connect_row(row)
            layout.addWidget(row)
            self.rows[cid] = row
            self.parents[cid] = parent_id
            pending.extend((child, depth + 1, cid) for child in reversed(children))
        self.apply_visibility()

    def toggle(self, cid: int) -> None:
        if self.searching:
            return
        if cid in self.expanded:
            self.expanded.remove(cid)
        else:
            self.expanded.add(cid)
        self.apply_visibility()

    def apply_visibility(self) -> None:
        visible = {}
        for cid, row in self.rows.items():
            parent_id = self.parents[cid]
            visible[cid] = parent_id is None or (visible.get(parent_id, False) and
                                                (self.searching or parent_id in self.expanded))
            row.setVisible(visible[cid])
            row.set_expanded(row.has_children and (self.searching or cid in self.expanded))
        self.updateGeometry()
