from __future__ import annotations

"""Helpers de interfaz sin conocimiento de páginas concretas.

Las acciones compactas y el ajuste de diálogos se usaban con implementaciones
ligeramente distintas en varias pantallas. Tener una sola fábrica evita que una
corrección visual se aplique en un módulo y quede desfasada en otro.
"""

from dataclasses import dataclass

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QApplication, QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from .constants import NEGATIVE

try:
    import qtawesome as qta
except Exception:  # dependencia visual opcional
    qta = None

DANGER_ICON_COLOR = NEGATIVE
DANGER_ICON_DISABLED_COLOR = "#D66B7A"
COMPACT_ACTION_SIZE = QSize(40, 34)


def make_icon_button(
    icon_name: str,
    fallback: str,
    tooltip: str,
    *,
    danger: bool = False,
    object_name: str | None = None,
) -> QPushButton:
    """Crea una acción compacta rectangular consistente en toda la app."""
    button = QPushButton()
    button.setFixedSize(COMPACT_ACTION_SIZE)
    button.setToolTip(tooltip)
    button.setObjectName(object_name or ("DangerIconButton" if danger else "CompactIconButton"))
    if qta is not None:
        try:
            kwargs = {}
            if danger:
                kwargs = {
                    "color": DANGER_ICON_COLOR,
                    "color_disabled": DANGER_ICON_DISABLED_COLOR,
                }
            button.setIcon(qta.icon(icon_name, **kwargs))
            button.setIconSize(QSize(15, 15))
            return button
        except Exception:
            pass
    button.setText(fallback)
    return button



@dataclass(frozen=True)
class ReorderActionGroup:
    host: QWidget
    up: QPushButton
    down: QPushButton
    remove: QPushButton


def make_reorder_actions(remove_tooltip: str) -> ReorderActionGroup:
    """Botonera consistente: orden vertical + acción destructiva lateral."""
    host = QWidget()
    outer = QHBoxLayout(host)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(7)

    order_host = QWidget()
    order = QVBoxLayout(order_host)
    order.setContentsMargins(0, 0, 0, 0)
    order.setSpacing(4)
    up = make_icon_button("fa6s.chevron-up", "▲", "Subir")
    down = make_icon_button("fa6s.chevron-down", "▼", "Bajar")
    remove = make_icon_button("fa6s.trash", "×", remove_tooltip, danger=True)
    order.addWidget(up)
    order.addWidget(down)
    outer.addWidget(order_host)
    outer.addWidget(remove, 0, Qt.AlignmentFlag.AlignVCenter)
    return ReorderActionGroup(host, up, down, remove)

def fit_dialog_to_screen(
    widget: QWidget,
    *,
    preferred_width: int,
    preferred_height: int,
    width_ratio: float = 0.92,
    height_ratio: float = 0.90,
) -> None:
    """Ajusta y centra una ventana sin exceder el área útil del monitor."""
    parent = widget.parentWidget().window() if widget.parentWidget() else None
    screen = parent.screen() if parent is not None else QApplication.primaryScreen()
    if screen is None:
        return
    area = screen.availableGeometry()
    if widget.minimumSizeHint().width() > area.width() * width_ratio or widget.minimumSizeHint().height() > area.height() * height_ratio:
        ensure_page_viewport(widget)
        widget.setMinimumSize(0, 0)
    minimum = widget.minimumSize()
    width = max(minimum.width(), min(int(preferred_width), int(area.width() * width_ratio)))
    height = max(minimum.height(), min(int(preferred_height), int(area.height() * height_ratio)))
    widget.resize(width, height)
    frame = widget.frameGeometry()
    frame.moveCenter(parent.frameGeometry().center() if parent is not None else area.center())
    x = min(max(area.left(), frame.x()), max(area.left(), area.right() - frame.width() + 1))
    y = min(max(area.top(), frame.y()), max(area.top(), area.bottom() - frame.height() + 1))
    widget.move(x, y)


def repolish(widget: QWidget) -> None:
    """Reaplica QSS después de cambiar propiedades dinámicas."""
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)


def ensure_page_viewport(page: QWidget) -> None:
    """Permite llegar a todos los controles cuando falta altura o ancho.

    Conserva el widget público de la página y sus señales. Las páginas que ya
    desplazan todo su contenido mantienen su contenedor original.
    """
    from PySide6.QtWidgets import QScrollArea, QFrame, QLayout
    old = page.layout()
    if old is None or getattr(page, "_page_viewport", None) is not None:
        return
    if old.count() == 1 and isinstance(old.itemAt(0).widget(), QScrollArea):
        return
    content = QWidget()
    content.setLayout(old)
    old.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
    shell = QVBoxLayout(page)
    shell.setContentsMargins(0, 0, 0, 0)
    scroll = QScrollArea()
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setWidgetResizable(True)
    scroll.setObjectName("PageScroll")
    scroll.setWidget(content)
    shell.addWidget(scroll)
    page._page_viewport = scroll
    page._content_layout = old
