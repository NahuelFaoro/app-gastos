from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import (
    QBoxLayout, QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

try:
    import qtawesome as qta
except Exception:
    qta = None

from ..constants import CATEGORY_COLORS
from ..dialogs import TransactionDialog
from ..layouts import FlowLayout, responsive_mode
from ..ui_helpers import fit_dialog_to_screen, make_reorder_actions
from ..utils import money
from ..widgets import IconBadge, MoneyEdit, SlideSwitch, StatCard
from ..work_calendar import full_week_label, week_end, week_start
from .common import clear_layout, page_header, scroll_container
from ..date_picker import WorkDateEdit
from .work_cards import FoldableWorkCard



monday_of = week_start
week_label = full_week_label





class FlexZoneCard(FoldableWorkCard):
    add_requested = Signal(int)
    remove_requested = Signal(int)

    def __init__(self, zone: dict, symbol: str, hidden: bool = False, parent=None):
        super().__init__(int(zone["id"]), str(zone.get("name") or "Zona"),
                         money(zone.get("total") or 0, symbol, hidden), parent)
        self.zone = zone
        self.zone_id = self.record_id
        self.symbol = symbol
        self.hidden = bool(hidden)
        self.edit_button.hide()
        root = self.detail_layout
        rate = QLabel(f"Tarifa actual · {money(zone.get('current_price') or 0, symbol, hidden)}")
        rate.setObjectName("SmallMuted")
        root.addWidget(rate)
        middle = QHBoxLayout()
        middle.setSpacing(16)
        countbox = QVBoxLayout(); countbox.setSpacing(0)
        count = QLabel(str(int(zone.get("quantity") or 0))); count.setObjectName("FlexZoneCount"); count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        item_plural = str(zone.get("item_plural") or "envíos")
        item_singular = str(zone.get("item_singular") or "envío")
        countcap = QLabel(f"{item_plural} esta semana"); countcap.setObjectName("SmallMuted"); countcap.setAlignment(Qt.AlignmentFlag.AlignCenter)
        countbox.addWidget(count); countbox.addWidget(countcap)
        middle.addLayout(countbox, 1)

        subtotalbox = QVBoxLayout(); subtotalbox.setSpacing(2)
        subtotal = QLabel(money(zone.get("total") or 0, symbol, self.hidden)); subtotal.setObjectName("FlexZoneSubtotal")
        subtotal.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subcap = QLabel("subtotal"); subcap.setObjectName("SmallMuted"); subcap.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtotalbox.addWidget(subtotal); subtotalbox.addWidget(subcap)
        middle.addLayout(subtotalbox, 1)
        for label in (count, countcap, subtotal, subcap, rate):
            label.setWordWrap(True)
            label.setMinimumWidth(0)
            label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        root.addLayout(middle)

        actions = QHBoxLayout(); actions.setSpacing(8)
        remove = QPushButton("−")
        remove.setObjectName("FlexMinusButton")
        remove.setFixedWidth(42)
        remove.setEnabled(int(zone.get("quantity") or 0) > 0)
        remove.setToolTip("Quitar un envío de esta zona")
        add = QPushButton(f"＋ 1 {item_singular}")
        add.setObjectName("FlexAddButton")
        add.setMinimumHeight(42)
        remove.clicked.connect(lambda: self.remove_requested.emit(self.zone_id))
        add.clicked.connect(lambda: self.add_requested.emit(self.zone_id))
        actions.addWidget(remove); actions.addWidget(add, 1)
        root.addLayout(actions)


class FlexRatesDialog(QDialog):
    """Editor compacto y claro de identidad, vigencia, zonas y tarifas."""

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.rows: list[dict] = []
        self.deleted_zone_ids: set[int] = set()
        self.setWindowTitle("Configurar zonas")
        self.resize(820, 720)
        self.setMinimumSize(640, 560)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 18)
        root.setSpacing(11)
        root.addWidget(page_header(
            "Configurar zonas",
            "Editá el nombre de la herramienta, sus unidades y las tarifas. Los cambios de precio conservan el historial anterior.",
        ))

        # Identidad: tres campos en una sola banda para evitar una tarjeta alta
        # que deje casi sin espacio al listado de zonas.
        identity = QFrame()
        identity.setObjectName("WorkConfigCard")
        identity_layout = QGridLayout(identity)
        identity_layout.setContentsMargins(15, 12, 15, 12)
        identity_layout.setHorizontalSpacing(10)
        identity_layout.setVerticalSpacing(6)
        identity_title = QLabel("Identidad de la herramienta")
        identity_title.setObjectName("SectionTitle")
        identity_hint = QLabel("Sólo cambia las etiquetas visibles; no altera los registros ya guardados.")
        identity_hint.setObjectName("SmallMuted")
        identity_hint.setWordWrap(True)
        identity_layout.addWidget(identity_title, 0, 0, 1, 3)
        identity_layout.addWidget(identity_hint, 1, 0, 1, 3)

        self.tool_name = QLineEdit(self.db.get_setting("flex_tool_name", "Pedidos por zonas"))
        self.tool_name.setPlaceholderText("Ej. Flex")
        self.item_singular = QLineEdit(self.db.get_setting("flex_item_singular", "envío"))
        self.item_singular.setPlaceholderText("Ej. envío")
        self.item_plural = QLineEdit(self.db.get_setting("flex_item_plural", "envíos"))
        self.item_plural.setPlaceholderText("Ej. envíos")
        for col, (label_text, widget) in enumerate((
            ("Nombre de la herramienta", self.tool_name),
            ("Unidad (singular)", self.item_singular),
            ("Unidad (plural)", self.item_plural),
        )):
            label = QLabel(label_text)
            label.setObjectName("FieldLabel")
            identity_layout.addWidget(label, 2, col)
            identity_layout.addWidget(widget, 3, col)
        identity_layout.setColumnStretch(0, 2)
        identity_layout.setColumnStretch(1, 1)
        identity_layout.setColumnStretch(2, 1)
        root.addWidget(identity)

        effective_card = QFrame()
        effective_card.setObjectName("SoftCard")
        ec = QHBoxLayout(effective_card)
        ec.setContentsMargins(14, 10, 14, 10)
        ec.setSpacing(10)
        effective_text = QVBoxLayout()
        effective_text.setSpacing(1)
        label = QLabel("Vigencia de las tarifas")
        label.setObjectName("FieldLabel")
        hint = QLabel("Los nuevos importes se aplican desde esta fecha; lo anterior mantiene su valor histórico.")
        hint.setObjectName("SmallMuted")
        hint.setWordWrap(True)
        effective_text.addWidget(label)
        effective_text.addWidget(hint)
        self.effective = WorkDateEdit(QDate.currentDate())
        self.effective.setCalendarPopup(True)
        self.effective.setDisplayFormat("dd/MM/yyyy")
        self.effective.setToolTip("La tarifa se aplicará desde esta fecha.")
        ec.addLayout(effective_text, 1)
        ec.addWidget(self.effective, 0, Qt.AlignmentFlag.AlignVCenter)
        root.addWidget(effective_card)

        section = QHBoxLayout()
        section_title = QLabel("Zonas y tarifas")
        section_title.setObjectName("SectionTitle")
        section_hint = QLabel("Podés reordenar, desactivar o eliminar zonas que todavía no tengan entregas registradas.")
        section_hint.setObjectName("SmallMuted")
        section_hint.setWordWrap(True)
        section.addWidget(section_title)
        section.addSpacing(8)
        section.addWidget(section_hint, 1)
        root.addLayout(section)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setObjectName("ZoneConfigScroll")
        self.scroll.setMinimumHeight(230)
        host = QWidget()
        self.rows_layout = QVBoxLayout(host)
        self.rows_layout.setContentsMargins(0, 0, 6, 0)
        self.rows_layout.setSpacing(9)
        self.rows_layout.addStretch(1)
        self.scroll.setWidget(host)
        root.addWidget(self.scroll, 1)

        for zone in self.db.flex_zones(include_inactive=True):
            self._add_row(zone)
        self.effective.dateChanged.connect(self._reload_prices_for_date)
        self._reload_prices_for_date()

        # Una sola barra inferior libera altura útil para las zonas.
        footer = QHBoxLayout()
        add_zone = QPushButton("＋ Agregar zona")
        add_zone.setObjectName("SecondaryButton")
        add_zone.clicked.connect(lambda: self._add_row(None))
        cancel = QPushButton("Cancelar")
        cancel.setObjectName("SecondaryButton")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Guardar tarifas")
        save.clicked.connect(self._save)
        footer.addWidget(add_zone)
        footer.addStretch()
        footer.addWidget(cancel)
        footer.addWidget(save)
        root.addLayout(footer)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        fit_dialog_to_screen(
            self, preferred_width=820, preferred_height=720, width_ratio=0.94, height_ratio=0.92
        )

    def _add_row(self, zone) -> None:
        frame = QFrame()
        frame.setObjectName("WorkConfigCard")
        row = QGridLayout(frame)
        row.setContentsMargins(13, 10, 13, 10)
        row.setHorizontalSpacing(10)
        row.setVerticalSpacing(5)

        name = QLineEdit()
        name.setPlaceholderText("Nombre de la zona")
        name.setMinimumWidth(185)
        amount = MoneyEdit(self.db.currency_symbol())
        amount.setMinimumHeight(42)
        amount.setMaximumHeight(44)
        amount.setMinimumWidth(145)
        rate_meta = QLabel("")
        rate_meta.setObjectName("SmallMuted")
        rate_meta.setWordWrap(True)

        active = SlideSwitch()
        active_host = QWidget()
        active_box = QHBoxLayout(active_host)
        active_box.setContentsMargins(0, 0, 0, 0)
        active_box.setSpacing(7)
        active_box.addWidget(QLabel("Activa"))
        active_box.addWidget(active)

        action_group = make_reorder_actions("Eliminar zona")
        up, down, remove = action_group.up, action_group.down, action_group.remove
        actions_host = action_group.host

        if zone:
            name.setText(str(zone.get("name") or ""))
            amount.setValue(float(zone.get("current_price") or 0))
            active.setChecked(bool(zone.get("active", 1)))
        else:
            active.setChecked(True)

        name_label = QLabel("Zona")
        name_label.setObjectName("FieldLabel")
        price_label = QLabel("Tarifa vigente")
        price_label.setObjectName("FieldLabel")
        state_label = QLabel("Estado")
        state_label.setObjectName("FieldLabel")
        row.addWidget(name_label, 0, 0)
        row.addWidget(price_label, 0, 1)
        row.addWidget(state_label, 0, 2)
        row.addWidget(name, 1, 0)
        row.addWidget(amount, 1, 1)
        row.addWidget(active_host, 1, 2, Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(actions_host, 0, 3, 3, 1, Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(rate_meta, 2, 1, 1, 2)
        row.setColumnStretch(0, 3)
        row.setColumnStretch(1, 2)
        row.setColumnStretch(2, 1)

        self.rows_layout.insertWidget(self.rows_layout.count() - 1, frame)
        row_data = {
            "id": int(zone["id"]) if zone else None,
            "frame": frame,
            "name": name,
            "amount": amount,
            "active": active,
            "rate_meta": rate_meta,
            "color": (zone.get("color") if zone else CATEGORY_COLORS[len(self.rows) % len(CATEGORY_COLORS)]) or "#4CCFA9",
            "up": up,
            "down": down,
        }
        self.rows.append(row_data)
        up.clicked.connect(lambda: self._move_row(row_data, -1))
        down.clicked.connect(lambda: self._move_row(row_data, 1))
        remove.clicked.connect(lambda: self._remove_row(row_data))
        self._refresh_order_buttons()

    def _refresh_order_buttons(self) -> None:
        total = len(self.rows)
        for index, row in enumerate(self.rows):
            row["up"].setEnabled(index > 0)
            row["down"].setEnabled(index < total - 1)

    def _remove_row(self, row_data: dict) -> None:
        zone_id = row_data.get("id")
        name = row_data["name"].text().strip() or "esta zona"
        if zone_id is not None:
            deliveries = self.db.flex_zone_delivery_count(int(zone_id))
            if deliveries:
                QMessageBox.information(
                    self,
                    "Zona con historial",
                    f"No puedo eliminar ‘{name}’ porque tiene {deliveries} entrega{'s' if deliveries != 1 else ''} registrada{'s' if deliveries != 1 else ''}.\n\n"
                    "Podés apagar ‘Activa’ para que deje de aparecer al cargar nuevos envíos sin perder el historial.",
                )
                return
            answer = QMessageBox.question(
                self,
                "Eliminar zona",
                f"¿Eliminar ‘{name}’? También se eliminará su historial de tarifas, ya que todavía no tiene entregas registradas.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            self.deleted_zone_ids.add(int(zone_id))
        if row_data in self.rows:
            self.rows.remove(row_data)
        frame = row_data["frame"]
        self.rows_layout.removeWidget(frame)
        frame.hide()
        frame.setParent(None)
        frame.deleteLater()
        self._refresh_order_buttons()

    def _move_row(self, row_data: dict, delta: int) -> None:
        try:
            index = self.rows.index(row_data)
        except ValueError:
            return
        new_index = max(0, min(len(self.rows) - 1, index + int(delta)))
        if new_index == index:
            return
        self.rows[index], self.rows[new_index] = self.rows[new_index], self.rows[index]
        for item in self.rows:
            self.rows_layout.removeWidget(item["frame"])
        for item in self.rows:
            self.rows_layout.insertWidget(self.rows_layout.count() - 1, item["frame"])
        self._refresh_order_buttons()

    def _reload_prices_for_date(self, *_args) -> None:
        selected = self.effective.date().toString("yyyy-MM-dd")
        symbol = self.db.currency_symbol()
        for row in self.rows:
            zone_id = row.get("id")
            meta = row.get("rate_meta")
            if not zone_id:
                if meta:
                    meta.setText("Nueva zona · primera tarifa")
                continue
            zone = self.db.flex_zone(int(zone_id), selected)
            price = float((zone or {}).get("current_price") or 0)
            row["amount"].setValue(price)
            history = self.db.flex_rate_history(int(zone_id))
            future = [h for h in history if str(h.get("effective_from") or "") > selected]
            if future:
                upcoming = sorted(future, key=lambda h: (str(h.get("effective_from") or ""), int(h.get("id") or 0)))[0]
                try:
                    y, m, d = map(int, str(upcoming["effective_from"]).split("-")[:3])
                    when = f"{d:02d}/{m:02d}/{y}"
                except Exception:
                    when = str(upcoming.get("effective_from") or "")
                if meta:
                    meta.setText(f"Vigente en esta fecha · próximo cambio {when}: {money(float(upcoming.get('price') or 0), symbol, self.db.balances_hidden())}")
            elif meta:
                meta.setText("Tarifa vigente en la fecha seleccionada")

    def _save(self) -> None:
        effective = self.effective.date().toString("yyyy-MM-dd")
        try:
            tool_name = self.tool_name.text().strip() or "Pedidos por zonas"
            singular = self.item_singular.text().strip() or "envío"
            plural = self.item_plural.text().strip() or f"{singular}s"

            seen: set[str] = set()
            for row in self.rows:
                name = row["name"].text().strip()
                if not name:
                    raise ValueError("Todas las zonas deben tener un nombre.")
                key = name.casefold()
                if key in seen:
                    raise ValueError(f"La zona '{name}' está repetida.")
                seen.add(key)
                if float(row["amount"].value()) < 0:
                    raise ValueError("Las tarifas no pueden ser negativas.")

            self.db.set_setting("flex_tool_name", tool_name)
            self.db.set_setting("flex_item_singular", singular)
            self.db.set_setting("flex_item_plural", plural)

            # Las eliminaciones se difieren hasta Guardar; Cancelar no toca la base.
            for zone_id in sorted(self.deleted_zone_ids):
                self.db.delete_flex_zone(zone_id)

            ordered_ids: list[int] = []
            for row in self.rows:
                name = row["name"].text().strip()
                price = float(row["amount"].value())
                if row["id"] is None:
                    row["id"] = self.db.add_flex_zone(name, price, effective, row["color"])
                else:
                    self.db.update_flex_zone(row["id"], name, bool(row["active"].isChecked()))
                    self.db.set_flex_zone_rate(row["id"], price, effective)
                ordered_ids.append(int(row["id"]))
            self.db.reorder_flex_zones(ordered_ids)
        except Exception as exc:
            QMessageBox.warning(self, "Configurar zonas", str(exc))
            return
        self.accept()


class FlexToolPage(QWidget):
    data_changed = Signal()

    def __init__(self, db):
        super().__init__()
        self.db = db
        self.current_week = monday_of(date.today())
        self.tool_name = self.db.get_setting("flex_tool_name", "Pedidos por zonas")
        self.item_singular = self.db.get_setting("flex_item_singular", "envío")
        self.item_plural = self.db.get_setting("flex_item_plural", "envíos")
        self.last_added_id = None
        self._compact = False
        self._zone_cards = []

        shell = QVBoxLayout(self); shell.setContentsMargins(0, 0, 0, 0)
        scroll, content, root = scroll_container(); shell.addWidget(scroll)

        self.top_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        top = self.top_layout
        top.addWidget(page_header("Zonas", "Contador semanal configurable por zonas y tarifas"))
        top.addStretch()
        rates = QPushButton("Configurar zonas"); rates.setObjectName("SecondaryButton"); rates.clicked.connect(self.open_rates)
        if qta is not None:
            try: rates.setIcon(qta.icon("fa6s.sliders"))
            except Exception: pass
        top.addWidget(rates)
        root.addLayout(top)

        tool_header = QFrame(); tool_header.setObjectName("FlexHero")
        self.tool_header_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight, tool_header); self.tool_header_layout.setContentsMargins(20, 17, 20, 17); self.tool_header_layout.setSpacing(14)
        # El icono ocupa la izquierda y un espaciador gemelo compensa a la
        # derecha. Así el bloque de texto queda centrado respecto de la tarjeta,
        # no respecto del espacio restante después del icono.
        self.tool_badge = IconBadge("package", "#4CCFA9", 50)
        self.tool_header_layout.addWidget(self.tool_badge, 0, Qt.AlignmentFlag.AlignCenter)
        text = QVBoxLayout(); text.setSpacing(2)
        self.tool_title = QLabel(self.tool_name); self.tool_title.setObjectName("FlexToolTitle"); self.tool_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tool_description = QLabel(); self.tool_description.setObjectName("PageSubtitle"); self.tool_description.setAlignment(Qt.AlignmentFlag.AlignCenter); self.tool_description.setWordWrap(True)
        text.addWidget(self.tool_title); text.addWidget(self.tool_description); self.tool_header_layout.addLayout(text, 1)
        self.tool_balance_spacer = QWidget(); self.tool_balance_spacer.setFixedSize(50, 50)
        self.tool_header_layout.addWidget(self.tool_balance_spacer, 0, Qt.AlignmentFlag.AlignCenter)
        root.addWidget(tool_header)

        self.week_nav = QFrame(); self.week_nav.setObjectName("FlexWeekBar")
        self.week_nav.setMaximumWidth(620)
        self.week_nav.setMinimumWidth(420)
        nl = QHBoxLayout(self.week_nav); nl.setContentsMargins(12, 9, 12, 9); nl.setSpacing(8)
        prev = QPushButton("‹"); prev.setObjectName("GhostButton"); prev.setFixedWidth(38); prev.clicked.connect(lambda: self.shift_week(-1))
        nxt = QPushButton("›"); nxt.setObjectName("GhostButton"); nxt.setFixedWidth(38); nxt.clicked.connect(lambda: self.shift_week(1))
        self.week_title = QLabel(); self.week_title.setObjectName("FlexWeekTitle"); self.week_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        today = QPushButton("Esta semana"); today.setObjectName("SecondaryButton"); today.clicked.connect(self.go_current_week)
        nl.addWidget(prev); nl.addWidget(self.week_title, 1); nl.addWidget(nxt); nl.addWidget(today)
        root.addWidget(self.week_nav, 0, Qt.AlignmentFlag.AlignHCenter)

        self.stats_host = QWidget()
        self.stats_layout = FlowLayout(self.stats_host, horizontal_spacing=10, vertical_spacing=10, center_rows=True)
        self.total_deliveries = StatCard(self.item_plural.capitalize())
        self.total_amount = StatCard("Total de la semana")
        self.average = StatCard(f"Promedio por {self.item_singular}")
        for card in (self.total_deliveries, self.total_amount, self.average):
            card.setMinimumWidth(175)
            card.setMaximumWidth(245)
            self.stats_layout.addWidget(card)
        root.addWidget(self.stats_host)

        self.zone_title_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        zone_title = self.zone_title_layout
        zt = QLabel(f"Registrar {self.item_singular}"); zt.setObjectName("SectionTitle")
        zh = QLabel(f"Un toque en + suma 1 {self.item_singular} con la tarifa vigente de esa zona."); zh.setObjectName("SmallMuted")
        zone_title.addWidget(zt); zone_title.addSpacing(8); zone_title.addWidget(zh); zone_title.addStretch()
        root.addLayout(zone_title)

        self.zone_host = QWidget(); self.zone_grid = QGridLayout(self.zone_host)
        self.zone_grid.setContentsMargins(0, 0, 0, 0); self.zone_grid.setSpacing(12)
        root.addWidget(self.zone_host)

        self.action_bar = QFrame(); self.action_bar.setObjectName("FlexActionBar")
        ab = QHBoxLayout(self.action_bar); ab.setContentsMargins(14, 10, 14, 10)
        self.last_action = QLabel("Listo para registrar envíos."); self.last_action.setObjectName("SmallMuted")
        self.undo = QPushButton("Deshacer último"); self.undo.setObjectName("GhostButton"); self.undo.clicked.connect(self.undo_last); self.undo.setVisible(False)
        ab.addWidget(self.last_action, 1); ab.addWidget(self.undo)
        root.addWidget(self.action_bar)

        settle = QFrame(); settle.setObjectName("FlexSettlementCard")
        self.settle_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight, settle); self.settle_layout.setContentsMargins(18, 15, 18, 15); self.settle_layout.setSpacing(12)
        sl = self.settle_layout
        info = QVBoxLayout(); info.setSpacing(2)
        si = QLabel("Cuando cierres la semana"); si.setObjectName("SectionTitle")
        self.settle_description = QLabel(); self.settle_description.setObjectName("SmallMuted"); self.settle_description.setWordWrap(True)
        info.addWidget(si); info.addWidget(self.settle_description); sl.addLayout(info, 1)
        self.register_income = QPushButton("Registrar como ingreso"); self.register_income.clicked.connect(self.register_as_income)
        sl.addWidget(self.register_income)
        root.addWidget(settle)

        hist_title = QLabel("Semanas anteriores"); hist_title.setObjectName("SectionTitle"); root.addWidget(hist_title)
        self.history_host = QWidget(); self.history_layout = QVBoxLayout(self.history_host)
        self.history_layout.setContentsMargins(0, 0, 0, 0); self.history_layout.setSpacing(8)
        root.addWidget(self.history_host)
        root.addStretch()

        self.refresh(); self._apply_responsive()

    def _apply_responsive(self):
        mode = responsive_mode(self.width(), self.height())
        compact = mode != "wide"
        changed = mode != getattr(self, "_layout_mode", None)
        self._layout_mode = mode
        self._compact = compact
        direction = QBoxLayout.Direction.TopToBottom if compact else QBoxLayout.Direction.LeftToRight
        self.top_layout.setDirection(direction)
        self.tool_header_layout.setDirection(direction)
        self.tool_balance_spacer.setVisible(not compact)
        self.zone_title_layout.setDirection(direction)
        self.settle_layout.setDirection(direction)
        if mode == "narrow":
            self.week_nav.setMinimumWidth(0)
            self.week_nav.setMaximumWidth(16777215)
        else:
            self.week_nav.setMinimumWidth(420)
            self.week_nav.setMaximumWidth(620)
        if changed:
            self.refresh()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_responsive()

    def _rate_date_for_week(self):
        today = date.today()
        if self.current_week <= today <= week_end(self.current_week):
            return today.isoformat()
        return self.current_week.isoformat()

    def shift_week(self, amount):
        self.current_week += timedelta(weeks=int(amount))
        self.last_added_id = None
        self.refresh()

    def go_current_week(self):
        self.current_week = monday_of(date.today())
        self.last_added_id = None
        self.refresh()

    def refresh(self):
        self.tool_name = self.db.get_setting("flex_tool_name", "Pedidos por zonas")
        self.item_singular = self.db.get_setting("flex_item_singular", "envío")
        self.item_plural = self.db.get_setting("flex_item_plural", "envíos")
        self.tool_title.setText(self.tool_name)
        self.tool_description.setText(f"Sumá cada {self.item_singular} por zona y llevá el total semanal sin hacer cuentas a mano.")
        self.settle_description.setText(
            f"Podés pasar el total de {self.tool_name} a Ingresos usando el formulario normal de la app."
        )
        self.total_deliveries.caption.setText(self.item_plural.capitalize())
        self.average.caption.setText(f"Promedio por {self.item_singular}")
        symbol = self.db.currency_symbol()
        week_iso = self.current_week.isoformat()
        summary = self.db.flex_week_summary(week_iso)
        self.week_title.setText(week_label(self.current_week))

        self.total_deliveries.set_value(str(summary["quantity"]), f"{self.item_plural} registrados")
        self.total_amount.set_value(money(summary["total"], symbol, self.db.balances_hidden()), "facturación calculada")
        self.average.set_value(money(summary["average"], symbol, self.db.balances_hidden()), f"por {self.item_singular}" if summary["quantity"] else f"sin {self.item_plural}")

        expanded_zones = {card.zone_id for card in self._zone_cards if card.is_expanded()}
        for old_card in self._zone_cards:
            old_card.hide()
        clear_layout(self.zone_grid)
        zones_for_rate = {int(z["id"]): z for z in self.db.flex_zones(self._rate_date_for_week(), True)}
        cards = []
        for item in summary["zones"]:
            item = dict(item)
            item["item_singular"] = self.item_singular
            item["item_plural"] = self.item_plural
            current = zones_for_rate.get(int(item["id"]))
            if current:
                item["current_price"] = current["current_price"]
            cards.append(item)
        self._zone_cards = []
        mode = responsive_mode(self.width(), self.height())
        cols = 1 if mode == "narrow" else 2 if mode == "compact" else 4
        if mode == "wide" and self.width() < 1250:
            cols = 3
        for i, zone in enumerate(cards):
            card = FlexZoneCard(zone, symbol, self.db.balances_hidden())
            card.set_expanded(card.zone_id in expanded_zones)
            card.add_requested.connect(self.add_delivery)
            card.remove_requested.connect(self.remove_delivery)
            self._zone_cards.append(card)
            self.zone_grid.addWidget(card, i // cols, i % cols,
                                     Qt.Alignment() if card.is_expanded() else Qt.AlignmentFlag.AlignTop)
            card.expansionChanged.connect(lambda c=card: self.zone_grid.setAlignment(c, Qt.Alignment() if c.is_expanded() else Qt.AlignmentFlag.AlignTop))
        for c in range(max(cols, self.zone_grid.columnCount())):
            self.zone_grid.setColumnStretch(c, 1 if c < cols else 0)
        if not cards:
            empty = QLabel("No hay zonas activas. Entrá en Configurar zonas para agregar una."); empty.setObjectName("Muted")
            self.zone_grid.addWidget(empty, 0, 0)

        link = self.db.flex_income_link(week_iso)
        already = bool(link and link.get("existing_transaction_id"))
        self.register_income.setEnabled(summary["total"] > 0 and not already)
        self.register_income.setText("Ingreso ya registrado" if already else "Registrar como ingreso")

        self._refresh_history()
        self.undo.setVisible(self.last_added_id is not None)

    def add_delivery(self, zone_id):
        try:
            self.last_added_id = self.db.add_flex_delivery(
                int(zone_id), self.current_week.isoformat(), 1, self._rate_date_for_week()
            )
            zone = self.db.flex_zone(int(zone_id), self._rate_date_for_week())
            self.last_action.setText(f"Sumaste 1 {self.item_singular} a {zone['name'] if zone else 'la zona'}.")
        except Exception as exc:
            QMessageBox.warning(self, self.tool_name, str(exc)); return
        self.refresh()

    def remove_delivery(self, zone_id):
        try:
            removed = self.db.remove_last_flex_delivery(int(zone_id), self.current_week.isoformat())
            if not removed:
                return
            zone = self.db.flex_zone(int(zone_id), self._rate_date_for_week())
            self.last_action.setText(f"Quitaste 1 {self.item_singular} de {zone['name'] if zone else 'la zona'}.")
            self.last_added_id = None
        except Exception as exc:
            QMessageBox.warning(self, self.tool_name, str(exc)); return
        self.refresh()

    def undo_last(self):
        if not self.last_added_id:
            return
        try:
            self.db.delete_flex_delivery(int(self.last_added_id))
        except Exception as exc:
            QMessageBox.warning(self, self.tool_name, str(exc)); return
        self.last_added_id = None
        self.last_action.setText(f"Último {self.item_singular} deshecho.")
        self.refresh()

    def open_rates(self):
        dlg = FlexRatesDialog(self.db, self)
        if dlg.exec():
            self.last_added_id = None
            self.refresh()

    def register_as_income(self):
        summary = self.db.flex_week_summary(self.current_week.isoformat())
        if summary["total"] <= 0:
            return
        link = self.db.flex_income_link(self.current_week.isoformat())
        if link and link.get("existing_transaction_id"):
            QMessageBox.information(self, self.tool_name, "Esta semana ya tiene un ingreso registrado.")
            return

        dlg = TransactionDialog(self.db, parent=self)
        dlg.set_kind("income")
        dlg.amount.setValue(summary["total"])
        dlg.description.setText(f"{self.tool_name} · {week_label(self.current_week)}")
        dlg.tags.setText("herramienta, zonas")
        dlg.note.setPlainText(f"{summary['quantity']} {self.item_plural} calculados desde Herramientas / {self.tool_name}.")
        end = week_end(self.current_week)
        tx_date = min(date.today(), end) if self.current_week <= date.today() else end
        dlg.date.setDate(QDate(tx_date.year, tx_date.month, tx_date.day))
        income_choices = self.db.category_choices("income")
        preferred_names = {self.tool_name.casefold(), "flex"}
        preferred_category = next(
            (c for c in income_choices if (c.get("name") or "").casefold() in preferred_names),
            None,
        )
        if preferred_category:
            dlg.category.set_category(preferred_category)
        if dlg.exec():
            try:
                tx_id = self.db.add_transaction(dlg.data(), source="flex_tool")
                self.db.set_flex_income_link(self.current_week.isoformat(), tx_id, summary["total"])
            except Exception as exc:
                QMessageBox.warning(self, self.tool_name, str(exc)); return
            self.last_action.setText("El total semanal quedó registrado como ingreso.")
            self.data_changed.emit()
            self.refresh()

    def _refresh_history(self):
        clear_layout(self.history_layout)
        rows = self.db.flex_week_history(10)
        if not rows:
            empty = QLabel(f"Cuando registres {self.item_plural}, acá vas a ver el historial semanal."); empty.setObjectName("Muted")
            self.history_layout.addWidget(empty)
            return
        for row in rows:
            try:
                start = date.fromisoformat(row["week_start"])
            except Exception:
                continue
            b = QPushButton(
                f"{week_label(start)}  ·  {int(row['quantity'])} {self.item_plural}  ·  {money(row['total'], self.db.currency_symbol(), self.db.balances_hidden())}"
            )
            b.setObjectName("FlexHistoryButton")
            b.clicked.connect(lambda checked=False, d=start: self._open_history_week(d))
            self.history_layout.addWidget(b)

    def _open_history_week(self, value: date):
        self.current_week = value
        self.last_added_id = None
        self.refresh()
