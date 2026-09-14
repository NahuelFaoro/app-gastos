from PySide6.QtCore import Qt, Signal, QEvent
from PySide6.QtWidgets import QFrame, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy


class FoldableWorkCard(QFrame):
    """Encabezado y detalle plegable compartidos por las herramientas."""

    expansionChanged = Signal()
    clicked = Signal(int)
    doubleClicked = Signal(int)

    def __init__(self, record_id: int, title: str, amount: str, parent=None):
        super().__init__(parent)
        self.record_id = int(record_id)
        self.setObjectName("WorkTripCompactCard")
        self.setProperty("selected", False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 14, 18, 14)
        root.setSpacing(10)
        root.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.header = QFrame()
        self.header.setCursor(Qt.CursorShape.PointingHandCursor)
        self.header.installEventFilter(self)
        top = QHBoxLayout(self.header)
        top.setContentsMargins(0, 0, 0, 0)
        self.chevron = QLabel("›")
        self.chevron.setObjectName("WorkDayChevron")
        top.addWidget(self.chevron)
        client = QLabel(title)
        client.setObjectName("TransactionTitle")
        client.setWordWrap(True)
        client.setMinimumWidth(0)
        top.addWidget(client, 1)
        charged = QLabel(amount)
        charged.setObjectName("SmallMuted" if amount == "Sin importe" else "TransactionAmount")
        top.addWidget(charged)
        self.edit_button = QPushButton("Editar")
        self.edit_button.setObjectName("GhostButton")
        self.edit_button.setToolTip("Editar registro")
        self.edit_button.clicked.connect(lambda: self.doubleClicked.emit(self.record_id))
        top.addWidget(self.edit_button)
        root.addWidget(self.header)
        self.details_body = QWidget()
        self.detail_layout = QVBoxLayout(self.details_body)
        detail_layout = self.detail_layout
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(10)
        root.addWidget(self.details_body)

        for label in self.header.findChildren(QLabel):
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.set_expanded(False)

    def set_expanded(self, expanded: bool) -> None:
        self._expanded = bool(expanded)
        self.details_body.setVisible(self._expanded)
        self.chevron.setText("⌄" if self._expanded else "›")
        self.header.setToolTip("Ocultar detalle" if self._expanded else "Ver detalle")
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Minimum if self._expanded else QSizePolicy.Policy.Fixed)
        self.updateGeometry()
        self.expansionChanged.emit()

    def is_expanded(self) -> bool:
        return self._expanded

    def eventFilter(self, watched, event):
        if watched is self.header and event.type() == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
            self.set_expanded(not self._expanded)
            self.clicked.emit(self.record_id)
            return True
        return super().eventFilter(watched, event)

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", bool(selected))
        self.style().unpolish(self)
        self.style().polish(self)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.record_id)
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.doubleClicked.emit(self.record_id)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.set_expanded(not self._expanded)
            event.accept()
        elif event.key() == Qt.Key.Key_Space:
            self.set_expanded(not self._expanded)
            self.clicked.emit(self.record_id)
            event.accept()
        else:
            super().keyPressEvent(event)


