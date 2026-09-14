from __future__ import annotations

"""Selector de herramientas de trabajo.

El hub sólo decide qué herramienta abrir. La implementación de Mercado Libre
Flex vive en :mod:`app.pages.flex` y Viajes en :mod:`app.pages.viajes`, evitando
que este archivo crezca con lógica ajena a la navegación.
"""

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
    QStackedWidget, QVBoxLayout, QWidget,
)

from ..layouts import responsive_mode
from ..widgets import IconBadge
from .common import page_header
from .flex import FlexToolPage


class ToolChooserTile(QFrame):
    """Acceso compacto a una herramienta; toda la tarjeta es clickeable."""

    clicked = Signal()

    def __init__(self, title: str, description: str, icon: str, parent=None):
        super().__init__(parent)
        self.setObjectName("ToolChooserTile")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumWidth(320)
        self.setMaximumWidth(500)
        self.setMinimumHeight(100)
        self.setMaximumHeight(118)
        # La tarjeta ocupa el ancho de su columna dentro de un bloque central
        # acotado. Así dos herramientas no terminan pegadas a extremos opuestos
        # en monitores anchos.
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(14)
        badge = IconBadge(icon, "#4CCFA9", 44)
        badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        layout.addWidget(badge, 0, Qt.AlignmentFlag.AlignVCenter)

        text_box = QVBoxLayout()
        text_box.setSpacing(3)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("ToolChooserTitle")
        self.detail_label = QLabel(description)
        self.detail_label.setObjectName("Muted")
        self.detail_label.setWordWrap(True)
        self.title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.detail_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        text_box.addWidget(self.title_label)
        text_box.addWidget(self.detail_label)
        layout.addLayout(text_box, 1)

        arrow = QLabel("›")
        arrow.setObjectName("ToolChooserArrow")
        arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        arrow.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        layout.addWidget(arrow)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.clicked.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class ToolsPage(QWidget):
    """Hub estable y responsive de herramientas de trabajo."""

    data_changed = Signal()

    def __init__(self, db):
        super().__init__()
        self.db = db
        self._home_mode: str | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 28)
        root.setSpacing(12)

        self.subnav = QFrame()
        self.subnav.setObjectName("ToolsSubnav")
        nav = QHBoxLayout(self.subnav)
        nav.setContentsMargins(10, 8, 10, 8)
        nav.setSpacing(8)
        back = QPushButton("‹  Herramientas")
        back.setObjectName("GhostButton")
        back.clicked.connect(self.show_home)
        self.flex_nav = QPushButton("Flex")
        self.flex_nav.setObjectName("SecondaryButton")
        self.flex_nav.clicked.connect(self.open_flex)
        self.viajes_nav = QPushButton("Viajes")
        self.viajes_nav.setObjectName("SecondaryButton")
        self.viajes_nav.clicked.connect(self.open_viajes)
        nav.addWidget(back)
        nav.addStretch()
        nav.addWidget(self.flex_nav)
        nav.addWidget(self.viajes_nav)
        self.subnav.setVisible(False)
        root.addWidget(self.subnav)

        self.stack = QStackedWidget()
        self.home = self._build_home()
        self.flex = FlexToolPage(db)

        # Import local para evitar que Viajes cargue si en el futuro se utiliza
        # Flex de forma independiente (por ejemplo, en una build reducida).
        from .viajes import ViajesPage
        self.viajes = ViajesPage(db)
        from ..ui_helpers import ensure_page_viewport
        ensure_page_viewport(self.viajes)
        ensure_page_viewport(self.home)

        self.stack.addWidget(self.home)
        self.stack.addWidget(self.flex)
        self.stack.addWidget(self.viajes)
        root.addWidget(self.stack, 1)

        self.flex.data_changed.connect(self.data_changed.emit)
        self.viajes.data_changed.connect(self.data_changed.emit)
        self.show_home()

    def _build_home(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(6, 4, 6, 6)
        layout.setSpacing(16)
        layout.addWidget(page_header(
            "Herramientas",
            "Accesos rápidos a utilidades de trabajo. Elegí una para continuar.",
        ))

        # Dos accesos conocidos no necesitan un FlowLayout. Una grilla explícita
        # es más predecible durante el primer render dentro del QStackedWidget y
        # evita geometrías provisionales/superpuestas.
        self.home_tiles_host = QWidget()
        self.home_tiles_host.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        self.home_grid = QGridLayout(self.home_tiles_host)
        self.home_grid.setContentsMargins(0, 0, 0, 0)
        self.home_grid.setHorizontalSpacing(12)
        self.home_grid.setVerticalSpacing(12)
        self.home_grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        self.flex_tile = ToolChooserTile(
            self.db.get_setting("flex_tool_name", "Pedidos por zonas"),
            "Contador configurable por zonas, tarifas y cierre semanal.",
            "package",
        )
        self.viajes_tile = ToolChooserTile(
            "Viajes",
            "Recorridos, paradas, kilometraje y trabajo extra.",
            "pin",
        )
        self.flex_tile.clicked.connect(self.open_flex)
        self.viajes_tile.clicked.connect(self.open_viajes)
        layout.addWidget(self.home_tiles_host, 0, Qt.AlignmentFlag.AlignHCenter)

        self.home_hint = QLabel("Las herramientas mantienen sus datos por separado, pero comparten backups, privacidad y configuración de App Gastos.")
        self.home_hint.setObjectName("SmallMuted")
        self.home_hint.setWordWrap(True)
        self.home_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.home_hint.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.home_hint, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch()
        return page

    def _arrange_home_tiles(self, force: bool = False) -> None:
        """Coloca los accesos con la geometría real del viewport.

        El primer render de una página de ``QStackedWidget`` puede ocurrir antes
        de que tenga su ancho definitivo. Reordenar una vez en el siguiente ciclo
        de eventos evita depender de esa geometría provisional.
        """
        viewport_width = max(1, self.stack.width() or self.width())
        viewport_height = max(1, self.stack.height() or self.height())
        mode = responsive_mode(viewport_width, viewport_height)
        if not force and mode == self._home_mode:
            return
        self._home_mode = mode

        for tile in (self.flex_tile, self.viajes_tile):
            self.home_grid.removeWidget(tile)

        # El selector vive en un bloque central de ancho limitado. Antes el grid
        # ocupaba todo el viewport y cada columna se estiraba hasta un extremo,
        # dejando un vacío enorme entre Flex y Viajes en pantallas 2K/4K.
        available = max(300, viewport_width - 24)
        target_width = min(1020 if mode == "wide" else 540, available)
        self.home_tiles_host.setFixedWidth(int(target_width))
        self.home_hint.setFixedWidth(int(target_width))

        if mode == "wide":
            self.home_grid.addWidget(self.flex_tile, 0, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
            self.home_grid.addWidget(self.viajes_tile, 0, 1, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
            self.home_grid.setColumnStretch(0, 1)
            self.home_grid.setColumnStretch(1, 1)
        else:
            self.home_grid.addWidget(self.flex_tile, 0, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
            self.home_grid.addWidget(self.viajes_tile, 1, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
            self.home_grid.setColumnStretch(0, 1)
            self.home_grid.setColumnStretch(1, 0)
        self.home_grid.invalidate()
        self.home_tiles_host.updateGeometry()

    def _sync_tool_names(self) -> None:
        name = self.db.get_setting("flex_tool_name", "Pedidos por zonas")
        self.flex_tile.title_label.setText(name)
        self.flex_nav.setText(name)

    def show_home(self) -> None:
        self._sync_tool_names()
        self.stack.setCurrentWidget(self.home)
        self.subnav.setVisible(False)
        # En este punto el stack puede seguir teniendo el tamaño de construcción.
        # La segunda pasada usa ya la geometría real de la ventana.
        self._arrange_home_tiles(force=True)
        QTimer.singleShot(0, lambda: self._arrange_home_tiles(force=True))

    def open_flex(self) -> None:
        self.stack.setCurrentWidget(self.flex)
        self.subnav.setVisible(True)
        self._sync_nav_buttons()
        self.flex.refresh()

    def open_viajes(self) -> None:
        self.stack.setCurrentWidget(self.viajes)
        self.subnav.setVisible(True)
        self._sync_nav_buttons()
        self.viajes.refresh()

    def _sync_nav_buttons(self) -> None:
        self.flex_nav.setEnabled(self.stack.currentWidget() is not self.flex)
        self.viajes_nav.setEnabled(self.stack.currentWidget() is not self.viajes)

    def on_show(self) -> None:
        # Entrar desde el sidebar siempre presenta el selector, tal como una
        # carpeta de herramientas. Los datos internos no se reinician.
        self.show_home()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        QTimer.singleShot(0, lambda: self._arrange_home_tiles(force=True))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._arrange_home_tiles()

    def refresh(self) -> None:
        current = self.stack.currentWidget()
        if current is self.flex:
            self.flex.refresh()
        elif current is self.viajes:
            self.viajes.refresh()
        elif current is self.home:
            self._sync_tool_names()
            self._arrange_home_tiles()
