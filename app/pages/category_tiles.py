"""Iconos de carpetas y destinos de arrastre para categorías."""
from PySide6.QtCore import Qt, Signal, QPoint, QMimeData
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import QApplication, QFrame, QGridLayout, QHBoxLayout, QLabel, QMenu, QPushButton, QVBoxLayout

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
    edit_requested = Signal(int)
    add_child_requested = Signal(int)
    duplicate_requested = Signal(int)
    delete_requested = Signal(int)
    move_requested = Signal(int, int)

    def __init__(self, category: dict, children: list[dict], parent=None):
        super().__init__(parent)
        self.cid = int(category["id"])
        self.setObjectName("CategoryFolderTile")
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Clic para abrir · arrastrá sobre otra categoría para mover · ⋯ para editar")
        self._press = QPoint()
        self._dragged = False
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 14)
        root.setSpacing(6)
        top = QHBoxLayout()
        identity = IconBadge(category.get("icon") or "other", category.get("color") or "#4CCFA9", 24,
                             secondary_color=category.get("secondary_color"))
        identity.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        top.addWidget(identity)
        top.addStretch()
        menu = QPushButton("⋯")
        menu.setObjectName("GhostButton")
        menu.setFixedSize(34, 30)
        menu.setAccessibleName(f"Acciones de {category.get('name')}")
        menu.clicked.connect(lambda: self._menu(menu.mapToGlobal(menu.rect().bottomLeft())))
        top.addWidget(menu)
        root.addLayout(top)
        icon_host = QFrame()
        icon_host.setObjectName("CategoryFolderIcon")
        icon_host.setFixedSize(76, 76)
        icons = QGridLayout(icon_host)
        icons.setContentsMargins(6, 6, 6, 6)
        icons.setSpacing(4)
        previews = children[:4] if children else [category]
        for index, item in enumerate(previews):
            badge = IconBadge(item.get("icon") or "other", item.get("color") or "#4CCFA9",
                              27 if children else 56, secondary_color=item.get("secondary_color"))
            icons.addWidget(badge, index // 2, index % 2, Qt.AlignmentFlag.AlignCenter)
        icon_host.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        root.addWidget(icon_host, 0, Qt.AlignmentFlag.AlignHCenter)
        name = QLabel(str(category.get("name") or "Categoría"))
        name.setObjectName("CategoryItemName")
        name.setWordWrap(True)
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        root.addWidget(name)
        meta = QLabel(f"{len(children)} subcategorías" if children else "Sin subcategorías")
        meta.setObjectName("SmallMuted")
        meta.setAlignment(Qt.AlignmentFlag.AlignCenter)
        meta.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        root.addWidget(meta)
        path = str(category.get("path_parent") or "")
        if path:
            context = QLabel(path)
            context.setObjectName("SmallMuted")
            context.setWordWrap(True)
            context.setAlignment(Qt.AlignmentFlag.AlignCenter)
            context.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            root.addWidget(context)
        root.addStretch()
        self.setFixedHeight(max(210, 130 + self.fontMetrics().height() * (7 if path else 5)))

    def _menu(self, position):
        menu = QMenu(self)
        actions = [("Abrir", self.opened), ("Editar / mover", self.edit_requested),
                   ("Agregar subcategoría", self.add_child_requested),
                   ("Duplicar", self.duplicate_requested), ("Eliminar", self.delete_requested)]
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
