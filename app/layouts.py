from __future__ import annotations

"""Layouts reutilizables de App Gastos.

Este módulo reúne geometría de UI genérica que no pertenece a una página
concreta. Mantener estos helpers fuera de las vistas evita duplicar lógica de
responsividad y facilita cambiar el diseño global más adelante.
"""

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import QLayout, QLayoutItem, QSizePolicy, QWidget


class FlowLayout(QLayout):
    """Layout horizontal que envuelve widgets a una nueva fila al quedarse sin ancho.

    Qt no incluye un flow layout listo para usar. Esta implementación sigue el
    patrón recomendado por Qt y permite que tarjetas compactas conserven su
    ancho natural en lugar de estirarse para rellenar toda la pantalla.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        margin: int = 0,
        horizontal_spacing: int = 10,
        vertical_spacing: int = 10,
        center_rows: bool = False,
    ) -> None:
        super().__init__(parent)
        self._items: list[QLayoutItem] = []
        self._h_spacing = horizontal_spacing
        self._v_spacing = vertical_spacing
        self._center_rows = bool(center_rows)
        self.setContentsMargins(margin, margin, margin, margin)

    def addItem(self, item: QLayoutItem) -> None:  # noqa: N802 - API de Qt
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> QLayoutItem | None:  # noqa: N802 - API de Qt
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int) -> QLayoutItem | None:  # noqa: N802 - API de Qt
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self) -> Qt.Orientations:  # noqa: N802 - API de Qt
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:  # noqa: N802 - API de Qt
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802 - API de Qt
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect: QRect) -> None:  # noqa: N802 - API de Qt
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QSize:  # noqa: N802 - API de Qt
        return self.minimumSize()

    def minimumSize(self) -> QSize:  # noqa: N802 - API de Qt
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def addWidget(
        self,
        widget: QWidget,
        stretch: int = 0,
        alignment: Qt.Alignment = Qt.Alignment(),
    ) -> None:  # noqa: N802 - mirrors Qt API
        """Agrega un widget con una firma compatible con layouts estándar de Qt.

        ``FlowLayout`` no distribuye stretch como ``QHBoxLayout`` porque cada
        fila conserva el ancho natural de sus widgets. Aun así aceptamos los
        parámetros habituales para que los componentes reutilizables puedan
        cambiar de layout sin romperse por diferencias de firma.
        """
        horizontal_policy = (
            QSizePolicy.Policy.Expanding if int(stretch or 0) > 0
            else QSizePolicy.Policy.Preferred
        )
        widget.setSizePolicy(horizontal_policy, QSizePolicy.Policy.Fixed)
        super().addWidget(widget)
        if alignment:
            item = self.itemAt(self.count() - 1)
            if item is not None:
                item.setAlignment(alignment)

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        margins = self.contentsMargins()
        effective = rect.adjusted(
            margins.left(),
            margins.top(),
            -margins.right(),
            -margins.bottom(),
        )

        visible: list[tuple[QLayoutItem, QSize]] = []
        for item in self._items:
            widget = item.widget()
            # ``isVisible()`` también devuelve False cuando un ancestro está
            # oculto (por ejemplo una página aún no seleccionada de un
            # QStackedWidget). Filtrar por eso dejaba widgets sin geometría en
            # el primer render y podían aparecer superpuestos hasta el próximo
            # relayout. Sólo excluimos widgets ocultados explícitamente.
            if widget is not None and widget.isHidden():
                continue
            visible.append((item, item.sizeHint()))

        # Primero armamos las líneas; esto permite centrar cada fila sin alterar
        # el comportamiento clásico de wrap cuando ``center_rows`` es falso.
        lines: list[list[tuple[QLayoutItem, QSize]]] = []
        current: list[tuple[QLayoutItem, QSize]] = []
        current_width = 0
        for pair in visible:
            _, hint = pair
            candidate = hint.width() if not current else current_width + self._h_spacing + hint.width()
            if current and candidate > max(1, effective.width()):
                lines.append(current)
                current = [pair]
                current_width = hint.width()
            else:
                current.append(pair)
                current_width = candidate
        if current:
            lines.append(current)

        y = effective.y()
        for line in lines:
            line_width = sum(hint.width() for _, hint in line) + self._h_spacing * max(0, len(line) - 1)
            line_height = max((hint.height() for _, hint in line), default=0)
            x = effective.x()
            if self._center_rows:
                x += max(0, (effective.width() - line_width) // 2)
            for item, hint in line:
                if not test_only:
                    item.setGeometry(QRect(QPoint(x, y), hint))
                x += hint.width() + self._h_spacing
            y += line_height + self._v_spacing

        if lines:
            y -= self._v_spacing
        return y - rect.y() + margins.bottom()


# Breakpoints compartidos por todo el proyecto. No dependen únicamente del
# ancho: una ventana alta/vertical necesita comportamiento compacto incluso si
# su ancho supera por poco un umbral fijo.
NARROW_WIDTH = 720
COMPACT_WIDTH = 1040
SIDEBAR_COMPACT_WIDTH = 1180


def responsive_mode(width: int, height: int = 0) -> str:
    """Devuelve ``wide``, ``compact`` o ``narrow`` según el viewport.

    La relación de aspecto evita que un monitor vertical de 768×1360 sea tratado
    como una pantalla de escritorio horizontal sólo por superar un breakpoint.
    """
    width = max(1, int(width or 0))
    height = max(1, int(height or 0))
    portrait = height > width * 1.18
    if width < NARROW_WIDTH or (portrait and width < 900):
        return "narrow"
    if width < COMPACT_WIDTH or portrait:
        return "compact"
    return "wide"


def is_compact(width: int, height: int = 0) -> bool:
    return responsive_mode(width, height) != "wide"
