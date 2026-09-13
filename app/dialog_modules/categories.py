from __future__ import annotations

from collections import defaultdict

from PySide6.QtCore import QDate, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFormLayout, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from ..constants import CATEGORY_COLORS
from ..icons import draw_icon, normalize_icon
from ..widgets import CategoryTileButton, IconBadge, SlideSwitch
from .visual import ColorButton, IconButton

class CategoryPickerDialog(QDialog):
    """Selector visual de categorías, inspirado en apps móviles."""
    def __init__(self, db, kind, selected_id=None, include_parents=False, parent=None):
        super().__init__(parent)
        self.db = db
        self.kind = kind
        self.selected_id = selected_id
        self.include_parents = include_parents
        self.selected_category = None
        self.all_categories = db.category_choices(kind, include_parents=include_parents)
        self._expanded_picker_groups: set[str] = set()
        selected = next((c for c in self.all_categories if int(c.get("id") or 0) == int(selected_id or 0)), None)
        if selected:
            parent_path = str(selected.get("path_parent") or "").strip()
            self._expanded_picker_groups.add(parent_path.split(" / ", 1)[0] if parent_path else "Categorías")

        self.setWindowTitle("Elegir categoría")
        self.resize(940, 700)
        self.setMinimumSize(520, 480)
        root = QVBoxLayout(self); root.setContentsMargins(22, 20, 22, 20); root.setSpacing(13)

        top = QHBoxLayout()
        box = QVBoxLayout(); title = QLabel("Elegir categoría"); title.setObjectName("PageTitle")
        sub = QLabel("Elegí por ícono y color. Si hay muchas, buscá por nombre."); sub.setObjectName("PageSubtitle")
        box.addWidget(title); box.addWidget(sub); top.addLayout(box); top.addStretch()
        close = QPushButton("← Volver"); close.setObjectName("SecondaryButton"); close.clicked.connect(self.reject); top.addWidget(close)
        root.addLayout(top)

        self.search = QLineEdit(); self.search.setPlaceholderText("Buscar categoría…")
        self.search.setClearButtonEnabled(True); self.search.textChanged.connect(self.rebuild)
        root.addWidget(self.search)
        create = QPushButton("＋ Nueva categoría / subcategoría")
        create.setObjectName("SecondaryButton")
        create.setToolTip("Crear una categoría o subcategoría sin salir del movimiento")
        create.clicked.connect(self.create_category)
        root.addWidget(create, 0, Qt.AlignmentFlag.AlignHCenter)

        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True); self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setObjectName("CategoryPickerScroll")
        root.addWidget(self.scroll, 1)
        self._grid_columns = 6
        self.rebuild()
        self.search.setFocus()

    def _matches(self, c, query):
        if not query: return True
        hay = f"{c.get('name','')} {c.get('parent_name','')} {c.get('label','')}".lower()
        return all(part in hay for part in query.lower().split())

    def _group_key(self, category: dict) -> str:
        parent_path = str(category.get("path_parent") or "").strip()
        if parent_path:
            return parent_path.split(" / ", 1)[0]
        label = str(category.get("label") or category.get("name") or "Categorías")
        return label.split(" / ", 1)[0] if " / " in label else "Categorías"

    def _toggle_picker_group(self, group_name: str) -> None:
        if group_name in self._expanded_picker_groups:
            self._expanded_picker_groups.remove(group_name)
        else:
            self._expanded_picker_groups.add(group_name)
        self.rebuild()

    def rebuild(self):
        self._grid_columns = max(3, min(8, max(3, (max(360, self.width()) - 70) // 118)))
        host = QWidget(); layout = QVBoxLayout(host); layout.setContentsMargins(2, 2, 8, 8); layout.setSpacing(9)
        query = self.search.text().strip()
        cats = [c for c in self.all_categories if self._matches(c, query)]

        if not query:
            recent_ids = [c["id"] for c in self.db.recent_categories(self.kind, 8)]
            recents = [next((x for x in self.all_categories if x["id"] == cid), None) for cid in recent_ids]
            recents = [x for x in recents if x]
            if recents:
                t = QLabel("Recientes"); t.setObjectName("SectionTitle"); layout.addWidget(t)
                grid_host = QWidget(); grid = QGridLayout(grid_host); grid.setContentsMargins(0, 0, 0, 0); grid.setHorizontalSpacing(7); grid.setVerticalSpacing(6)
                for i, c in enumerate(recents): self._add_tile(grid, i, c, show_context=True)
                layout.addWidget(grid_host)

        groups = defaultdict(list)
        for c in cats:
            groups[self._group_key(c)].append(c)

        for group_name in sorted(groups, key=lambda value: value.casefold()):
            items = groups[group_name]
            expanded = bool(query) or group_name in self._expanded_picker_groups
            header = QPushButton(f"{'▾' if expanded else '›'}  {group_name}   ·   {len(items)}")
            header.setObjectName("CategoryPickerGroupButton")
            header.setCursor(Qt.CursorShape.PointingHandCursor)
            header.clicked.connect(lambda _checked=False, key=group_name: self._toggle_picker_group(key))
            layout.addWidget(header)
            if expanded:
                grid_host = QWidget(); grid = QGridLayout(grid_host); grid.setContentsMargins(12, 0, 0, 5); grid.setHorizontalSpacing(7); grid.setVerticalSpacing(6)
                for i, c in enumerate(items): self._add_tile(grid, i, c, show_context=True)
                layout.addWidget(grid_host)

        if not cats:
            empty = QLabel("No encontré categorías con esa búsqueda."); empty.setObjectName("Muted"); empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(empty); layout.addStretch()
        else:
            layout.addStretch()
        self.scroll.setWidget(host)

    def _add_tile(self, grid, index, category, show_context=False):
        tile = CategoryTileButton(category, show_context=show_context)
        tile.setChecked(category["id"] == self.selected_id)
        tile.clicked.connect(lambda checked=False, c=category: self.choose(c))
        grid.addWidget(tile, index // self._grid_columns, index % self._grid_columns)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        columns = max(3, min(8, max(3, (max(360, self.width()) - 70) // 118)))
        if columns != getattr(self, "_grid_columns", 6):
            self._grid_columns = columns
            QTimer.singleShot(0, self.rebuild)

    def create_category(self):
        dlg = CategoryDialog(self.db, preset_kind=self.kind, parent=self)
        if not dlg.exec():
            return
        try:
            category_id = self.db.add_category(*dlg.data())
        except Exception as exc:
            QMessageBox.warning(self, "Categoría", str(exc))
            return
        self.all_categories = self.db.category_choices(self.kind, include_parents=self.include_parents)
        created = next((row for row in self.db.category_choices(self.kind, include_parents=True) if int(row["id"]) == int(category_id)), None)
        if created:
            self.selected_id = int(category_id)
            self.selected_category = created
            self.accept()
        else:
            self.rebuild()

    def choose(self, category):
        self.selected_id = category["id"]
        self.selected_category = category
        self.accept()


class CategoryParentPickerDialog(QDialog):
    """Selector jerárquico visual para elegir el contenedor de una categoría.

    Evita el combo con rutas completas (``Moto / GLH / Seguro``), que se vuelve
    difícil de escanear cuando el árbol crece. Se navega un nivel por vez y la
    ruta actual queda siempre visible como breadcrumb.
    """

    def __init__(self, db, kind: str, selected_id: int | None = None, excluded_ids: set[int] | None = None, parent=None):
        super().__init__(parent)
        self.db = db
        self.kind = str(kind)
        self.selected_id = int(selected_id) if selected_id is not None else None
        self.excluded_ids = {int(value) for value in (excluded_ids or set())}
        self.current_parent_id: int | None = self.selected_id
        self._path_stack: list[int] = []
        self.setWindowTitle("Elegir ubicación")
        self.resize(620, 600)
        self.setMinimumSize(460, 440)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(12)
        title = QLabel("¿Dónde querés guardar esta categoría?")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Navegá por el árbol un nivel a la vez. No hace falta leer rutas largas.")
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(subtitle)

        nav = QHBoxLayout()
        self.back = QPushButton("←")
        self.back.setObjectName("SecondaryButton")
        self.back.setFixedWidth(44)
        self.back.clicked.connect(self._go_back)
        self.breadcrumb = QLabel("Nivel principal")
        self.breadcrumb.setObjectName("SectionTitle")
        self.breadcrumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nav.addWidget(self.back)
        nav.addWidget(self.breadcrumb, 1)
        root.addLayout(nav)

        self.use_current = QPushButton("Usar nivel principal")
        self.use_current.clicked.connect(self._accept_current)
        root.addWidget(self.use_current)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        root.addWidget(self.scroll, 1)
        self.host = QWidget()
        self.list_layout = QVBoxLayout(self.host)
        self.list_layout.setContentsMargins(0, 0, 6, 0)
        self.list_layout.setSpacing(8)
        self.scroll.setWidget(self.host)

        actions = QHBoxLayout()
        actions.addStretch()
        cancel = QPushButton("Cancelar")
        cancel.setObjectName("SecondaryButton")
        cancel.clicked.connect(self.reject)
        actions.addWidget(cancel)
        root.addLayout(actions)
        self._refresh()

    def _category_path(self, category_id: int | None) -> str:
        if category_id is None:
            return "Nivel principal"
        row = self.db.category(int(category_id))
        return str((row or {}).get("path") or (row or {}).get("name") or "Categoría")

    def _refresh(self) -> None:
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        self.breadcrumb.setText(self._category_path(self.current_parent_id))
        self.back.setEnabled(self.current_parent_id is not None)
        if self.current_parent_id is None:
            self.use_current.setText("Usar nivel principal")
        else:
            current = self.db.category(self.current_parent_id) or {}
            self.use_current.setText(f"Usar “{current.get('name') or 'esta categoría'}”")

        children = [
            row for row in self.db.category_children(self.current_parent_id, self.kind)
            if int(row["id"]) not in self.excluded_ids
        ]
        if not children:
            empty = QLabel("No hay subcategorías dentro de este nivel.")
            empty.setObjectName("SmallMuted")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.list_layout.addWidget(empty)
        for category in children:
            row = QFrame()
            row.setObjectName("SoftCard")
            layout = QHBoxLayout(row)
            layout.setContentsMargins(12, 9, 12, 9)
            layout.setSpacing(10)
            layout.addWidget(IconBadge(
                category.get("icon") or "other",
                category.get("color") or "#4CCFA9",
                38,
                secondary_color=category.get("secondary_color"),
            ))
            name = QLabel(str(category.get("name") or "Categoría"))
            name.setObjectName("SectionTitle")
            layout.addWidget(name, 1)
            open_button = QPushButton("Abrir  ›")
            open_button.setObjectName("SecondaryButton")
            cid = int(category["id"])
            open_button.clicked.connect(lambda _checked=False, value=cid: self._open(value))
            layout.addWidget(open_button)
            self.list_layout.addWidget(row)
        self.list_layout.addStretch(1)

    def _open(self, category_id: int) -> None:
        if self.current_parent_id is not None:
            self._path_stack.append(self.current_parent_id)
        self.current_parent_id = int(category_id)
        self._refresh()

    def _go_back(self) -> None:
        if self.current_parent_id is None:
            return
        row = self.db.category(self.current_parent_id)
        parent_id = row.get("parent_id") if row else None
        self.current_parent_id = int(parent_id) if parent_id is not None else None
        self._refresh()

    def _accept_current(self) -> None:
        self.selected_id = self.current_parent_id
        self.accept()


class CategoryParentButton(QPushButton):
    """Botón compacto que abre :class:`CategoryParentPickerDialog`."""

    selectionChanged = Signal(object)

    def __init__(self, db, kind: str, selected_id: int | None = None, excluded_ids: set[int] | None = None, parent=None):
        super().__init__(parent)
        self.db = db
        self.kind = str(kind)
        self.category_id = int(selected_id) if selected_id is not None else None
        self.excluded_ids = {int(value) for value in (excluded_ids or set())}
        self.setObjectName("SecondaryButton")
        self.setMinimumHeight(42)
        self.clicked.connect(self._pick)
        self._refresh_text()

    def set_kind(self, kind: str) -> None:
        self.kind = str(kind)
        current = self.db.category(self.category_id) if self.category_id is not None else None
        if current and str(current.get("kind")) != self.kind:
            self.category_id = None
        self._refresh_text()

    def set_category_id(self, category_id: int | None) -> None:
        self.category_id = int(category_id) if category_id is not None else None
        self._refresh_text()

    def _refresh_text(self) -> None:
        if self.category_id is None:
            self.setText("Nivel principal")
            self.setToolTip("Sin categoría contenedora")
            return
        row = self.db.category(self.category_id) or {}
        # El control principal muestra sólo el nombre actual para evitar volver
        # al problema de las rutas interminables. La ruta completa queda como
        # tooltip y dentro del selector jerárquico.
        self.setText(str(row.get("name") or "Categoría"))
        self.setToolTip(str(row.get("path") or row.get("name") or ""))

    def _pick(self) -> None:
        dialog = CategoryParentPickerDialog(
            self.db,
            self.kind,
            self.category_id,
            self.excluded_ids,
            self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.category_id = dialog.selected_id
        self._refresh_text()
        self.selectionChanged.emit(self.category_id)


class CategoryDialog(QDialog):
    def __init__(self, db, category=None, preset_kind=None, preset_parent_id=None, parent=None):
        super().__init__(parent)
        self.db=db; self.category=category; self.preset_parent_id=preset_parent_id
        self.setWindowTitle("Editar categoría" if category else "Nueva categoría")
        self.setMinimumWidth(450)

        root=QVBoxLayout(self); root.setContentsMargins(22,20,22,20); root.setSpacing(14)
        title=QLabel("Editar categoría" if category else ("Nueva subcategoría" if preset_parent_id else "Nueva categoría")); title.setObjectName("PageTitle")
        subtitle=QLabel("Nombre, color e ícono quedan visibles en toda la app."); subtitle.setObjectName("PageSubtitle")
        root.addWidget(title); root.addWidget(subtitle)

        form=QFormLayout(); form.setSpacing(11)
        self.name=QLineEdit(); self.name.setPlaceholderText("Ej: Combustible")
        self.kind=QComboBox(); self.kind.addItem("Gasto", "expense"); self.kind.addItem("Ingreso", "income")
        excluded = set(self.db.category_descendant_ids(int(category["id"]), include_self=True)) if category else set()
        initial_parent = category.get("parent_id") if category else preset_parent_id
        self.parent_selector = CategoryParentButton(
            self.db,
            category.get("kind") if category else (preset_kind or "expense"),
            int(initial_parent) if initial_parent is not None else None,
            excluded,
        )
        self.color=ColorButton(category["color"] if category else CATEGORY_COLORS[0])
        self.icon=IconButton(category.get("icon", "other") if category else "other")
        self.secondary_toggle = SlideSwitch()
        self.secondary_toggle.setChecked(bool(category and category.get("secondary_color")))
        self.secondary_color = ColorButton((category or {}).get("secondary_color") or CATEGORY_COLORS[1])
        secondary_row = QWidget(); secondary_layout = QHBoxLayout(secondary_row); secondary_layout.setContentsMargins(0,0,0,0); secondary_layout.setSpacing(10)
        secondary_layout.addWidget(QLabel("Dividir ícono en dos colores"), 1); secondary_layout.addWidget(self.secondary_toggle)
        form.addRow("Nombre", self.name); form.addRow("Tipo", self.kind); form.addRow("Dentro de", self.parent_selector); form.addRow("Ícono", self.icon); form.addRow("Color principal", self.color); form.addRow("Bicolor", secondary_row); form.addRow("Segundo color", self.secondary_color)
        self.secondary_color.setVisible(self.secondary_toggle.isChecked())
        self.secondary_toggle.toggled.connect(self.secondary_color.setVisible)
        root.addLayout(form)

        preview = QFrame(); preview.setObjectName("SoftCard")
        pl = QHBoxLayout(preview); pl.setContentsMargins(14,12,14,12); pl.setSpacing(11)
        self.preview_icon = QLabel(); self.preview_icon.setFixedSize(38,38)
        self.preview_name = QLabel("Vista previa"); self.preview_name.setObjectName("SectionTitle")
        self.preview_meta = QLabel("Así se verá en selectores y análisis"); self.preview_meta.setObjectName("SmallMuted")
        text_box = QVBoxLayout(); text_box.setSpacing(1); text_box.addWidget(self.preview_name); text_box.addWidget(self.preview_meta)
        pl.addWidget(self.preview_icon); pl.addLayout(text_box,1); root.addWidget(preview)

        hint=QLabel("Tip: las subcategorías heredan inicialmente el color e ícono del grupo, pero después podés personalizarlas.")
        hint.setObjectName("SmallMuted"); hint.setWordWrap(True); root.addWidget(hint)

        row=QHBoxLayout(); row.addStretch(); cancel=QPushButton("Cancelar"); cancel.setObjectName("SecondaryButton"); cancel.clicked.connect(self.reject); save=QPushButton("Guardar categoría"); save.clicked.connect(self._validate); row.addWidget(cancel); row.addWidget(save); root.addLayout(row)

        self.kind.currentIndexChanged.connect(self._kind_changed)
        self.parent_selector.selectionChanged.connect(lambda _value: self._parent_changed())
        self.name.textChanged.connect(self._refresh_preview)
        self.icon.clicked.connect(lambda: QDate.currentDate() and self._refresh_preview())
        self.color.clicked.connect(lambda: QDate.currentDate() and self._refresh_preview())
        self.secondary_color.clicked.connect(lambda: QDate.currentDate() and self._refresh_preview())
        self.secondary_toggle.toggled.connect(lambda _checked: self._refresh_preview())
        if category:
            self.name.setText(category["name"]); i=self.kind.findData(category["kind"]); self.kind.setCurrentIndex(max(i,0))
        elif preset_kind:
            i=self.kind.findData(preset_kind); self.kind.setCurrentIndex(i if i>=0 else 0)
        self._kind_changed()
        if preset_parent_id and not category:
            self.kind.setEnabled(False)
            self.parent_selector.setEnabled(False)
        self._refresh_preview()

    def _kind_changed(self):
        self.parent_selector.set_kind(str(self.kind.currentData()))
        self._parent_changed()

    def _parent_changed(self):
        if self.category:
            self._refresh_preview()
            return
        pid=self.parent_selector.category_id
        if not pid:
            return
        parent=self.db.category(int(pid))
        if parent:
            self.color.color=parent.get("color") or CATEGORY_COLORS[0]; self.color._refresh()
            self.icon.icon_value=parent.get("icon") or "other"; self.icon._refresh()
            if not self.secondary_toggle.isChecked():
                self.secondary_color.color = next((c for c in CATEGORY_COLORS if c.casefold() != self.color.color.casefold()), CATEGORY_COLORS[1])
                self.secondary_color._refresh()
            self._refresh_preview()

    def _refresh_preview(self):
        # Renderizamos un pequeño icono en un pixmap sin agregar dependencias.
        from PySide6.QtGui import QPixmap
        pix = QPixmap(38,38); pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(self.color.color if hasattr(self, "color") else "#4CCFA9")
        painter.setBrush(color); painter.setPen(Qt.PenStyle.NoPen); painter.drawEllipse(1,1,36,36)
        if hasattr(self, "secondary_toggle") and self.secondary_toggle.isChecked():
            from PySide6.QtGui import QPainterPath
            clip = QPainterPath(); clip.addEllipse(1, 1, 36, 36)
            painter.save(); painter.setClipPath(clip); painter.setBrush(QColor(self.secondary_color.color)); painter.drawRect(19, 1, 18, 36); painter.restore()
        draw_icon(painter, pix.rect().adjusted(9,9,-9,-9), getattr(self.icon,"icon_value","other"), QColor("white"), 1.8)
        painter.end(); self.preview_icon.setPixmap(pix)
        self.preview_name.setText(self.name.text().strip() or "Nombre de categoría")
        parent_name = self.parent_selector.text() if self.parent_selector.category_id is not None else "Categoría principal"
        self.preview_meta.setText(parent_name)

    def _validate(self):
        if not self.name.text().strip():
            QMessageBox.warning(self,"Categoría","Ingresá un nombre."); return
        self.accept()

    def data(self):
        return (
            self.name.text().strip(),
            self.kind.currentData(),
            self.parent_selector.category_id,
            self.color.color,
            normalize_icon(self.icon.icon_value, self.name.text().strip()),
            self.secondary_color.color if self.secondary_toggle.isChecked() else None,
        )
