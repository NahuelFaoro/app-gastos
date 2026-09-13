from __future__ import annotations

from datetime import date, datetime, timedelta

from PySide6.QtCore import QObject, QDate, Qt, QThread, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QBoxLayout, QFileDialog, QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QScrollArea,
    QVBoxLayout, QWidget, QMenu, QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView
)

from ..dialogs import CategoryPickerDialog, ImportReviewDialog
from ..importers import import_mercadopago_bytes, import_mercadopago_report
from ..secure_store import get_token
from ..scanner import scan_document
from ..utils import money
from ..widgets import IconBadge
from .common import clear_layout, page_header
from ..date_picker import WorkDateEdit
from ..layouts import responsive_mode


class ScanOptionsDialog(QDialog):
    def __init__(self, db, file_name: str, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Escanear comprobante")
        self.setMinimumWidth(480)
        root = QVBoxLayout(self); root.setContentsMargins(22, 20, 22, 20); root.setSpacing(13)
        title = QLabel("Interpretar comprobante"); title.setObjectName("PageTitle")
        sub = QLabel(file_name); sub.setObjectName("PageSubtitle"); sub.setWordWrap(True)
        root.addWidget(title); root.addWidget(sub)

        help_text = QLabel(
            "App Gastos extrae el texto localmente y manda cada consumo detectado a Por revisar. "
            "Las categorías son sugerencias: podés corregirlas y hacer que la app aprenda."
        )
        help_text.setObjectName("Muted"); help_text.setWordWrap(True); root.addWidget(help_text)

        form = QFormLayout(); form.setSpacing(11)
        self.account = QComboBox()
        for account in db.accounts():
            self.account.addItem(account["name"], account["id"])
        self.mode = QComboBox()
        self.mode.addItem("Detectar automáticamente", "auto")
        self.mode.addItem("Ticket / supermercado", "ticket")
        self.mode.addItem("Resumen / lista de consumos", "statement")
        self.fallback_date = WorkDateEdit(); self.fallback_date.setCalendarPopup(True); self.fallback_date.setDisplayFormat("dd/MM/yyyy"); self.fallback_date.setDate(QDate.currentDate())
        form.addRow("Cuenta", self.account)
        form.addRow("Tipo de documento", self.mode)
        form.addRow("Fecha si no se detecta", self.fallback_date)
        root.addLayout(form)

        note = QLabel(
            "En un ticket se intentan separar productos. En un resumen se buscan filas con fecha, descripción e importe. "
            "Si el texto es ambiguo, queda sin categoría para que lo revises."
        )
        note.setObjectName("SmallMuted"); note.setWordWrap(True); root.addWidget(note)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Analizar")
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); root.addWidget(buttons)

    def data(self):
        return {
            "account_id": self.account.currentData(),
            "mode": self.mode.currentData() or "auto",
            "fallback_date": date(self.fallback_date.date().year(), self.fallback_date.date().month(), self.fallback_date.date().day()),
        }


class ScanPreviewDialog(QDialog):
    """Vista previa obligatoria antes de mandar OCR a Por revisar.

    Un escáner financiero debe ser conservador: si una fila salió rara es mejor
    desmarcarla acá que contaminar saldos/categorías después.
    """
    def __init__(self, result, fmt, parent=None):
        super().__init__(parent)
        self.result = result
        self.movements = list(result.movements or [])
        self.fmt = fmt
        self.setWindowTitle("Revisar lectura del documento")
        self.resize(860, 560)
        self.setMinimumSize(560, 430)

        root = QVBoxLayout(self); root.setContentsMargins(22, 20, 22, 20); root.setSpacing(12)
        title = QLabel("Antes de importar, revisá lo detectado"); title.setObjectName("PageTitle")
        subtitle = QLabel(
            f"{len(self.movements)} movimientos detectados"
            + (f" · {int(getattr(result, 'rejected_count', 0) or 0)} filas dudosas omitidas" if getattr(result, 'rejected_count', 0) else "")
        )
        subtitle.setObjectName("PageSubtitle")
        root.addWidget(title); root.addWidget(subtitle)

        help_text = QLabel(
            "App Gastos ahora reconstruye las filas por posición en la hoja y sólo acepta importes con formato monetario. "
            "Desmarcá cualquier fila que no coincida con el resumen; nada se guarda hasta confirmar."
        )
        help_text.setObjectName("Muted"); help_text.setWordWrap(True); root.addWidget(help_text)

        self.table = QTableWidget(len(self.movements), 5)
        self.table.setHorizontalHeaderLabels(["Importar", "Fecha", "Descripción", "Cuota", "Importe"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.setColumnWidth(0, 76); self.table.setColumnWidth(1, 100); self.table.setColumnWidth(3, 82); self.table.setColumnWidth(4, 130)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

        for row, movement in enumerate(self.movements):
            check = QTableWidgetItem("")
            check.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsSelectable)
            check.setCheckState(Qt.CheckState.Checked)
            self.table.setItem(row, 0, check)
            self.table.setItem(row, 1, QTableWidgetItem(str(movement.get("tx_date") or "")))
            self.table.setItem(row, 2, QTableWidgetItem(str(movement.get("description") or "")))
            raw = movement.get("raw") or {}
            cur, total = raw.get("installment_current"), raw.get("installment_total")
            self.table.setItem(row, 3, QTableWidgetItem(f"{cur}/{total}" if cur and total else "—"))
            amount = float(movement.get("amount") or 0)
            shown = amount if movement.get("kind") == "income" else -amount
            amount_item = QTableWidgetItem(self.fmt(shown))
            amount_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 4, amount_item)
        root.addWidget(self.table, 1)

        warnings = list(getattr(result, "warnings", []) or [])
        if warnings:
            warning = QLabel(f"⚠ {len(warnings)} observación(es). Se omitieron filas que no pudieron interpretarse con seguridad.")
            warning.setObjectName("ImportTransferHint"); warning.setWordWrap(True); warning.setToolTip("\n".join(warnings[:20]))
            root.addWidget(warning)

        actions = QHBoxLayout()
        uncheck = QPushButton("Desmarcar todo"); uncheck.setObjectName("SecondaryButton")
        uncheck.clicked.connect(lambda: self._set_all(False))
        check_all = QPushButton("Marcar todo"); check_all.setObjectName("SecondaryButton")
        check_all.clicked.connect(lambda: self._set_all(True))
        actions.addWidget(uncheck); actions.addWidget(check_all); actions.addStretch()
        cancel = QPushButton("Cancelar"); cancel.setObjectName("SecondaryButton"); cancel.clicked.connect(self.reject)
        accept = QPushButton("Enviar seleccionados a Por revisar"); accept.clicked.connect(self._accept_selected)
        actions.addWidget(cancel); actions.addWidget(accept); root.addLayout(actions)

    def _set_all(self, checked):
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item: item.setCheckState(state)

    def selected_movements(self):
        selected = []
        for row, movement in enumerate(self.movements):
            item = self.table.item(row, 0)
            if item and item.checkState() == Qt.CheckState.Checked:
                selected.append(movement)
        return selected

    def _accept_selected(self):
        if not self.selected_movements():
            QMessageBox.information(self, "Escáner", "Marcá al menos un movimiento para continuar.")
            return
        self.accept()


class DocumentScanWorker(QObject):
    finished = Signal(object)

    def __init__(self, path, mode, fallback_date):
        super().__init__(); self.path = path; self.mode = mode; self.fallback_date = fallback_date

    @Slot()
    def run(self):
        try:
            result = scan_document(self.path, self.mode, self.fallback_date)
            self.finished.emit({"ok": True, "result": result})
        except Exception as exc:
            self.finished.emit({"ok": False, "error": str(exc)})


class MercadoPagoSyncWorker(QObject):
    finished = Signal(object)

    def __init__(self, start_day: date, end_day: date, existing_task_id=None):
        super().__init__()
        self.start_day = start_day
        self.end_day = end_day
        self.existing_task_id = existing_task_id

    @Slot()
    def run(self):
        from ..mercadopago import download_range_report
        result = download_range_report(
            self.start_day,
            self.end_day,
            existing_task_id=self.existing_task_id,
        )
        self.finished.emit(result)


class ImportedMovementCard(QFrame):
    review_requested = Signal(int)
    quick_category_requested = Signal(int)
    ignore_requested = Signal(int)

    def __init__(self, item, fmt, parent=None):
        super().__init__(parent)
        self.item = item
        self.import_id = int(item["id"])
        self.setObjectName("ImportMovementCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Doble clic para ver el movimiento completo")

        root = QHBoxLayout(self)
        root.setContentsMargins(12, 10, 14, 10)
        root.setSpacing(11)

        color = item.get("category_color") or ("#20A66A" if item["kind"] == "income" else "#E45567")
        icon = item.get("category_icon") or ("wallet" if item["kind"] == "income" else "receipt")
        root.addWidget(IconBadge(icon, color, 38, secondary_color=item.get("category_secondary_color")))

        info = QVBoxLayout(); info.setSpacing(2)
        title = QLabel(item.get("description") or "Movimiento importado")
        title.setObjectName("TransactionTitle")

        source_label = {
            "mercado_pago": "Mercado Pago",
            "receipt_scan": "Ticket",
            "statement_scan": "Resumen",
        }.get(item.get("source"), str(item.get("source") or "Importado").replace("_", " ").title())
        meta_text = f"{item['tx_date']}  ·  {item.get('account_name','')}  ·  {source_label}"
        cur, total = item.get("scan_installment_current"), item.get("scan_installment_total")
        if cur and total:
            meta_text += f"  ·  {cur}/{total} cuotas"
        meta = QLabel(meta_text); meta.setObjectName("SmallMuted")
        info.addWidget(title); info.addWidget(meta)
        root.addLayout(info, 1)

        category = QPushButton()
        category.setCursor(Qt.CursorShape.PointingHandCursor)
        if item.get("category_id"):
            category.setText(item.get("category_display") or "Categoría sugerida")
            category.setObjectName("ImportCategoryButtonReady")
        elif item.get("transfer_hint"):
            category.setText("Revisar transferencia")
            category.setObjectName("ImportCategoryButtonTransfer")
        else:
            category.setText("Elegir categoría")
            category.setObjectName("ImportCategoryButtonPending")
        category.clicked.connect(lambda checked=False: self.quick_category_requested.emit(self.import_id))
        root.addWidget(category)

        amount = float(item.get("amount") or 0)
        shown = amount if item["kind"] == "income" else -amount
        value = QLabel(fmt(shown))
        value.setObjectName("TransactionAmountPositive" if item["kind"] == "income" else "TransactionAmountNegative")
        value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        value.setMinimumWidth(112)
        root.addWidget(value)

    def mouseDoubleClickEvent(self, event):
        self.review_requested.emit(self.import_id); event.accept()

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        quick = menu.addAction("Elegir categoría")
        review = menu.addAction("Ver detalles")
        menu.addSeparator()
        ignore = menu.addAction("Ignorar")
        chosen = menu.exec(event.globalPos())
        if chosen == quick:
            self.quick_category_requested.emit(self.import_id)
        elif chosen == review:
            self.review_requested.emit(self.import_id)
        elif chosen == ignore:
            self.ignore_requested.emit(self.import_id)


class ImportInboxPage(QWidget):
    data_changed = Signal()

    def __init__(self, db):
        super().__init__(); self.db = db
        self._sync_thread = None
        self._sync_worker = None
        self._sync_silent = False
        self._sync_range = None
        self._pending_retry_count = 0
        self._pending_retry_scheduled = False
        self._scan_thread = None
        self._scan_worker = None
        self._scan_context = None
        self._show_low_detail_mp = False
        self._visible_limit = 55
        self._compact = False
        root = QVBoxLayout(self); root.setContentsMargins(30, 25, 30, 28); root.setSpacing(14)

        self.top_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        top = self.top_layout
        top.addWidget(page_header("Por revisar", "Una bandeja simple para lo que la app todavía no puede decidir sola"))
        top.addStretch()
        self.scan_btn = QPushButton("Escanear")
        self.scan_btn.setObjectName("SecondaryButton"); self.scan_btn.clicked.connect(self.scan_receipt)
        self.sync_btn = QPushButton("Sincronizar")
        self.sync_btn.clicked.connect(self.sync_api)
        self.more_btn = QPushButton("•••")
        self.more_btn.setObjectName("SecondaryButton")
        self.more_btn.setFixedWidth(46)
        more_menu = QMenu(self.more_btn)
        import_action = more_menu.addAction("Importar reporte de Mercado Pago…")
        import_action.triggered.connect(self.import_report)
        more_menu.addSeparator()
        clean_action = more_menu.addAction("Limpiar bandeja…")
        clean_action.triggered.connect(self.clean_pending)
        self.more_btn.setMenu(more_menu)
        top.addWidget(self.scan_btn); top.addWidget(self.sync_btn); top.addWidget(self.more_btn)
        root.addLayout(top)

        # Resumen visual: evita empezar la página con una barra técnica llena de combos.
        hero = QFrame(); hero.setObjectName("ImportInboxHero")
        self.hero_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight, hero); self.hero_layout.setContentsMargins(18, 14, 18, 14); self.hero_layout.setSpacing(4)
        hl = self.hero_layout
        self.pending_value = QLabel("0"); self.pending_value.setObjectName("ImportMetricValue")
        self.ready_value = QLabel("0"); self.ready_value.setObjectName("ImportMetricValueReady")
        self.uncategorized_value = QLabel("0"); self.uncategorized_value.setObjectName("ImportMetricValue")
        for title_text, value_widget in (("Pendientes", self.pending_value), ("Listos", self.ready_value), ("Por decidir", self.uncategorized_value)):
            block = QWidget(); bl = QVBoxLayout(block); bl.setContentsMargins(12, 0, 24, 0); bl.setSpacing(1)
            cap = QLabel(title_text); cap.setObjectName("TinyCaption")
            bl.addWidget(cap); bl.addWidget(value_widget)
            hl.addWidget(block)
        hl.addStretch()
        state = QVBoxLayout(); state.setSpacing(2)
        self.sync_state_label = QLabel(); self.sync_state_label.setObjectName("IntegrationStatus")
        self.last_sync_label = QLabel(); self.last_sync_label.setObjectName("SmallMuted")
        self.last_sync_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        state.addWidget(self.sync_state_label, 0, Qt.AlignmentFlag.AlignRight)
        state.addWidget(self.last_sync_label, 0, Qt.AlignmentFlag.AlignRight)
        hl.addLayout(state)
        root.addWidget(hero)

        self.controls_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight); self.controls_layout.setSpacing(8)
        controls = self.controls_layout
        self.status = QComboBox()
        self.status.addItem("Pendientes", "pending"); self.status.addItem("Agregados", "imported"); self.status.addItem("Ignorados", "ignored")
        self.source_filter = QComboBox()
        self.source_filter.addItem("Todos los orígenes", "all")
        self.source_filter.addItem("Mercado Pago", "mercado_pago")
        self.source_filter.addItem("Escaneos", "ocr")
        self.account = QComboBox(); self.account.setMinimumWidth(170)
        controls.addWidget(self.status)
        controls.addWidget(self.source_filter)
        controls.addStretch()
        account_label = QLabel("Cuenta MP"); account_label.setObjectName("TinyCaption")
        controls.addWidget(account_label); controls.addWidget(self.account)
        self.accept_all = QPushButton("Agregar listos")
        self.accept_all.setObjectName("ImportAcceptButton")
        self.accept_all.clicked.connect(self.accept_categorized)
        controls.addWidget(self.accept_all)
        root.addLayout(controls)

        self.list_hint = QLabel(""); self.list_hint.setObjectName("SmallMuted")
        root.addWidget(self.list_hint)

        self.scroll = QScrollArea(); self.scroll.setObjectName("MovementScroll"); self.scroll.setWidgetResizable(True); self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.host = QWidget(); self.list_layout = QVBoxLayout(self.host); self.list_layout.setContentsMargins(0, 0, 7, 0); self.list_layout.setSpacing(5)
        self.scroll.setWidget(self.host); root.addWidget(self.scroll, 1)

        self.status.currentIndexChanged.connect(self._filters_changed)
        self.source_filter.currentIndexChanged.connect(self._filters_changed)
        self.account.currentIndexChanged.connect(self._save_account)
        self._load_accounts(); self.refresh(); self._apply_responsive()

    def _apply_responsive(self):
        compact = responsive_mode(self.width(), self.height()) != "wide"
        if compact == self._compact:
            return
        self._compact = compact
        direction = QBoxLayout.Direction.TopToBottom if compact else QBoxLayout.Direction.LeftToRight
        self.top_layout.setDirection(direction)
        self.hero_layout.setDirection(direction)
        self.controls_layout.setDirection(direction)
        self.account.setMinimumWidth(0 if compact else 170)
        margins = 14 if compact else 30
        self.layout().setContentsMargins(margins, 18 if compact else 25, margins, 20 if compact else 28)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_responsive()

    def _filters_changed(self):
        self._visible_limit = 55
        self.refresh()

    def _fmt(self, value):
        return money(value, self.db.currency_symbol(), self.db.balances_hidden())

    def _load_accounts(self):
        current = self.db.get_setting("mercadopago_account_id", "")
        self.account.blockSignals(True); self.account.clear()
        chosen = 0
        for i, account in enumerate(self.db.accounts()):
            self.account.addItem(account["name"], account["id"])
            if current and str(account["id"]) == str(current): chosen = i
            elif not current and "mercado pago" in account["name"].lower(): chosen = i
        if self.account.count(): self.account.setCurrentIndex(chosen)
        self.account.blockSignals(False)
        self._save_account()

    def _save_account(self):
        if self.account.currentData():
            self.db.set_setting("mercadopago_account_id", self.account.currentData())

    @staticmethod
    def _is_low_detail_mp(item):
        if item.get("source") != "mercado_pago" or item.get("category_id"):
            return False
        text = " ".join(str(item.get("description") or "").lower().split())
        return (
            text in {"pago / movimiento mercado pago", "movimiento mercado pago"}
            or text.startswith("movimiento mercado pago ·")
        )

    def _add_low_detail_group(self, rows):
        if not rows:
            return
        card = QFrame(); card.setObjectName("ImportCollapsedGroup")
        box = QHBoxLayout(card); box.setContentsMargins(16, 13, 16, 13); box.setSpacing(12)
        box.addWidget(IconBadge("wallet", "#3E8EF7", 40))
        text = QVBoxLayout(); text.setSpacing(2)
        title = QLabel(f"{len(rows)} movimientos de Mercado Pago sin descripción útil")
        title.setObjectName("TransactionTitle")
        incoming = sum(float(r.get("amount") or 0) for r in rows if r.get("kind") == "income")
        outgoing = sum(float(r.get("amount") or 0) for r in rows if r.get("kind") == "expense")
        meta = QLabel(
            f"Entradas {self._fmt(incoming)} · salidas {self._fmt(outgoing)} · ocultos para que la bandeja no se vuelva interminable"
        )
        meta.setObjectName("SmallMuted"); meta.setWordWrap(True)
        text.addWidget(title); text.addWidget(meta); box.addLayout(text, 1)
        toggle = QPushButton("Ocultar" if self._show_low_detail_mp else "Mostrar")
        toggle.setObjectName("SecondaryButton")
        toggle.clicked.connect(self._toggle_low_detail)
        ignore = QPushButton("Ignorar lote")
        ignore.setObjectName("GhostDangerButton")
        ignore.clicked.connect(lambda checked=False, ids=[int(r["id"]) for r in rows]: self._ignore_low_detail(ids))
        box.addWidget(toggle); box.addWidget(ignore)
        self.list_layout.addWidget(card)

    def _toggle_low_detail(self):
        self._show_low_detail_mp = not self._show_low_detail_mp
        self.refresh()

    def _ignore_low_detail(self, ids):
        if not ids:
            return
        if QMessageBox.question(
            self, "Ignorar movimientos sin detalle",
            f"¿Mover {len(ids)} movimientos genéricos de Mercado Pago a Ignorados?\n\n"
            "No se borran movimientos ya aceptados y podés verlos después desde la pestaña Ignorados."
        ) != QMessageBox.StandardButton.Yes:
            return
        self.db.ignore_imports(ids)
        self.refresh(); self.data_changed.emit()

    def refresh(self):
        clear_layout(self.list_layout)
        status = self.status.currentData() or "pending"
        rows = self.db.imported_movements(status)

        source = self.source_filter.currentData() if hasattr(self, "source_filter") else "all"
        if source == "mercado_pago":
            rows = [r for r in rows if r.get("source") == "mercado_pago"]
        elif source == "ocr":
            rows = [r for r in rows if r.get("source") in {"receipt_scan", "statement_scan"}]

        pending_rows = self.db.imported_movements("pending")
        pending = len(pending_rows)
        ready = sum(1 for r in pending_rows if r.get("category_id"))
        undecided = max(0, pending - ready)
        self.pending_value.setText(str(pending))
        self.ready_value.setText(str(ready))
        self.uncategorized_value.setText(str(undecided))
        self.accept_all.setText(f"Agregar {ready} listos" if ready else "Agregar listos")
        self.accept_all.setEnabled(ready > 0)
        self.accept_all.setVisible(status == "pending")

        last = self.db.get_setting("mercadopago_last_api_sync", "")
        pending_task = self.db.get_setting("mercadopago_pending_task_id", "")
        if pending_task:
            self.sync_state_label.setText("Mercado Pago · preparando")
            self.sync_state_label.setProperty("state", "warn")
            self.sync_btn.setText("Revisar estado")
            self.last_sync_label.setText("Podés seguir usando la app mientras termina")
        else:
            self.sync_state_label.setText("Mercado Pago · listo")
            self.sync_state_label.setProperty("state", "ok")
            self.sync_btn.setText("Sincronizar")
            self.last_sync_label.setText(f"Última vez {last}" if last else "Todavía no sincronizado")
        self.sync_state_label.style().unpolish(self.sync_state_label); self.sync_state_label.style().polish(self.sync_state_label)

        label = {"pending": "pendientes", "imported": "agregados", "ignored": "ignorados"}.get(status, status)
        self.list_hint.setText(f"{len(rows)} {label}" + (" · sólo se muestran los primeros para mantener la app fluida" if len(rows) > self._visible_limit else ""))

        if not rows:
            card = QFrame(); card.setObjectName("ImportEmptyState")
            box = QVBoxLayout(card); box.setContentsMargins(24, 34, 24, 34); box.setSpacing(5)
            title = QLabel("Todo al día" if status == "pending" else "No hay movimientos acá")
            title.setObjectName("SectionTitle")
            subtitle = QLabel("La app deja en esta bandeja únicamente lo que necesita una decisión tuya.")
            subtitle.setObjectName("Muted"); subtitle.setWordWrap(True)
            box.addWidget(title, 0, Qt.AlignmentFlag.AlignHCenter); box.addWidget(subtitle, 0, Qt.AlignmentFlag.AlignHCenter)
            self.list_layout.addWidget(card)
        else:
            low_detail = [r for r in rows if status == "pending" and self._is_low_detail_mp(r)]
            actionable = [r for r in rows if r not in low_detail]
            if low_detail:
                self._add_low_detail_group(low_detail)
            visible_rows = actionable + (low_detail if self._show_low_detail_mp else [])
            shown = visible_rows[:self._visible_limit]
            for item in shown:
                card = ImportedMovementCard(item, self._fmt)
                card.quick_category_requested.connect(self.quick_categorize)
                card.review_requested.connect(self.review_item)
                card.ignore_requested.connect(self.ignore_item)
                self.list_layout.addWidget(card)
            if len(visible_rows) > len(shown):
                more = QPushButton(f"Mostrar {min(55, len(visible_rows)-len(shown))} más")
                more.setObjectName("ImportShowMore")
                more.clicked.connect(self._show_more)
                self.list_layout.addWidget(more, 0, Qt.AlignmentFlag.AlignHCenter)
        self.list_layout.addStretch()

    def _show_more(self):
        self._visible_limit += 55
        self.refresh()

    def clean_pending(self):
        counts = self.db.pending_import_counts()
        total = counts.get("all", 0)
        if not total:
            QMessageBox.information(self, "Por revisar", "No hay pendientes para limpiar.")
            return
        box = QMessageBox(self)
        box.setWindowTitle("Limpiar Por revisar")
        box.setIcon(QMessageBox.Icon.Question)
        box.setText(f"Hay {total} movimientos pendientes")
        box.setInformativeText("Elegí qué querés sacar de la bandeja. Esto nunca borra movimientos ya agregados a tus cuentas.")
        all_btn = box.addButton(f"Todo ({total})", QMessageBox.ButtonRole.DestructiveRole)
        mp_n = counts.get("mercado_pago", 0)
        ocr_n = counts.get("ocr", 0)
        mp_btn = box.addButton(f"Solo Mercado Pago ({mp_n})", QMessageBox.ButtonRole.ActionRole) if mp_n else None
        ocr_btn = box.addButton(f"Solo OCR ({ocr_n})", QMessageBox.ButtonRole.ActionRole) if ocr_n else None
        cancel = box.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        clicked = box.clickedButton()
        if clicked is None or clicked == cancel:
            return
        group = "all" if clicked == all_btn else "mercado_pago" if mp_btn is not None and clicked == mp_btn else "ocr"
        deleted = self.db.delete_pending_imports(group)
        self.refresh(); self.data_changed.emit()
        self.statusBar_message(f"Se limpiaron {deleted} pendientes")

    def statusBar_message(self, text):
        window = self.window()
        if hasattr(window, "statusBar"):
            window.statusBar().showMessage(text, 5000)

    def quick_categorize(self, import_id):
        item = self.db.imported_movement(int(import_id))
        if not item or item.get("status") != "pending":
            return
        dlg = CategoryPickerDialog(
            self.db, item.get("kind") or "expense", item.get("category_id"),
            include_parents=True, parent=self,
        )
        if dlg.exec() and dlg.selected_category:
            self.db.update_import_category(int(import_id), int(dlg.selected_category["id"]))
            self.refresh()

    def clean_pending_scans(self):
        count = len(self.db.imported_movements("pending", "statement_scan")) + len(self.db.imported_movements("pending", "receipt_scan"))
        if not count:
            return
        answer = QMessageBox.question(
            self, "Limpiar lecturas OCR",
            f"Se eliminarán {count} movimientos detectados por OCR que todavía están pendientes.\n\n"
            "No se toca Mercado Pago ni ningún movimiento que ya hayas aceptado. ¿Continuar?"
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        deleted = self.db.delete_pending_scanned_imports()
        self.refresh(); self.data_changed.emit()
        QMessageBox.information(self, "OCR", f"Se eliminaron {deleted} movimientos OCR pendientes. Ya podés volver a escanear el resumen.")

    def scan_receipt(self):
        if self._scan_thread is not None and self._scan_thread.isRunning():
            QMessageBox.information(self, "Escáner", "Ya hay un documento analizándose.")
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Escanear comprobante o resumen",
            "",
            "Comprobantes (*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff *.pdf);;Todos los archivos (*)",
        )
        if not path:
            return
        dlg = ScanOptionsDialog(self.db, path, self)
        if not dlg.exec():
            return
        options = dlg.data()
        if not options.get("account_id"):
            QMessageBox.warning(self, "Escáner", "Necesitás seleccionar una cuenta.")
            return
        self._scan_context = {**options, "path": path}
        self.scan_btn.setEnabled(False); self.scan_btn.setText("Analizando…")
        self._scan_thread = QThread(self)
        self._scan_worker = DocumentScanWorker(path, options["mode"], options["fallback_date"])
        self._scan_worker.moveToThread(self._scan_thread)
        self._scan_thread.started.connect(self._scan_worker.run)
        self._scan_worker.finished.connect(self._scan_finished)
        self._scan_worker.finished.connect(self._scan_thread.quit)
        self._scan_worker.finished.connect(self._scan_worker.deleteLater)
        self._scan_thread.finished.connect(self._scan_thread.deleteLater)
        self._scan_thread.finished.connect(self._scan_cleanup)
        self._scan_thread.start()

    @Slot(object)
    def _scan_finished(self, payload):
        self.scan_btn.setEnabled(True); self.scan_btn.setText("Escanear comprobante")
        context = self._scan_context or {}
        if not payload.get("ok"):
            QMessageBox.warning(
                self,
                "No pude analizar el documento",
                payload.get("error") or "El OCR no devolvió resultados.",
            )
            return
        result = payload["result"]
        movements = list(result.movements or [])
        if not movements:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Information)
            box.setWindowTitle("Documento leído")
            box.setText("Pude leer el documento, pero no detecté consumos con suficiente seguridad.")
            detail = "Podés revisar el texto reconocido en Detalles. En resúmenes, App Gastos ahora prefiere omitir una fila dudosa antes que inventar un importe."
            if getattr(result, "rejected_count", 0):
                detail += f" Se descartaron {result.rejected_count} filas dudosas."
            box.setInformativeText(detail)
            box.setDetailedText((result.text or "(sin texto)") + ("\n\nOBSERVACIONES\n" + "\n".join(result.warnings) if getattr(result, "warnings", None) else ""))
            box.exec()
            return

        preview = ScanPreviewDialog(result, self._fmt, self)
        if not preview.exec():
            return
        movements = preview.selected_movements()
        source = "receipt_scan" if result.mode == "ticket" else "statement_scan"
        try:
            stage = self.db.stage_imported_movements(movements, source, int(context["account_id"]))
        except Exception as exc:
            QMessageBox.critical(self, "Escáner", f"El documento se leyó pero no pude preparar los movimientos:\n\n{exc}")
            return
        self.status.setCurrentIndex(0); self.refresh(); self.data_changed.emit()
        kind_label = "productos/consumos" if result.mode == "ticket" else "movimientos"
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowTitle("Comprobante analizado")
        box.setText(f"Detecté {len(movements)} {kind_label}.")
        box.setInformativeText(
            f"Nuevos por revisar: {stage['inserted']} · ya conocidos: {stage['duplicates']}.\n"
            "Las categorías sugeridas no se guardan definitivamente hasta que las aceptes."
        )
        box.setDetailedText(result.text or "")
        box.exec()

    @Slot()
    def _scan_cleanup(self):
        self._scan_thread = None; self._scan_worker = None; self._scan_context = None

    def sync_api(self, silent=False):
        # clicked(bool) puede llegar como argumento; sólo True explícito se usa como modo silencioso.
        silent = bool(silent) if isinstance(silent, bool) else False
        if self._sync_thread is not None and self._sync_thread.isRunning():
            if not silent:
                QMessageBox.information(self, "Mercado Pago", "Ya hay una sincronización en curso.")
            return
        if not get_token():
            if not silent:
                QMessageBox.information(self, "Mercado Pago", "Primero guardá tu Access Token en Ajustes → Integraciones.")
            return
        if not self.account.currentData():
            if not silent:
                QMessageBox.warning(self, "Mercado Pago", "Seleccioná la cuenta local que representa Mercado Pago.")
            return

        try:
            days = max(1, min(90, int(self.db.get_setting("mercadopago_sync_days", "30") or 30)))
        except Exception:
            days = 30
        pending_task = self.db.get_setting("mercadopago_pending_task_id", "") or None
        if pending_task:
            try:
                start_day = date.fromisoformat(self.db.get_setting("mercadopago_pending_start", ""))
                end_day = date.fromisoformat(self.db.get_setting("mercadopago_pending_end", ""))
            except Exception:
                end_day = date.today(); start_day = end_day - timedelta(days=days - 1)
        else:
            end_day = date.today(); start_day = end_day - timedelta(days=days - 1)
        self._sync_range = (start_day, end_day)

        self._sync_silent = silent
        self.sync_btn.setEnabled(False)
        self.more_btn.setEnabled(False)
        self.sync_btn.setText("Revisando reporte…" if pending_task else "Sincronizando…")
        self.sync_state_label.setText("Procesando")
        self.sync_state_label.setProperty("state", "warn")
        self.sync_state_label.style().unpolish(self.sync_state_label); self.sync_state_label.style().polish(self.sync_state_label)
        self.last_sync_label.setText(
            "Consultando la tarea pendiente de Mercado Pago…" if pending_task
            else f"Consultando últimos {days} días…"
        )

        self._sync_thread = QThread(self)
        self._sync_worker = MercadoPagoSyncWorker(start_day, end_day, pending_task)
        self._sync_worker.moveToThread(self._sync_thread)
        self._sync_thread.started.connect(self._sync_worker.run)
        self._sync_worker.finished.connect(self._sync_finished)
        self._sync_worker.finished.connect(self._sync_thread.quit)
        self._sync_worker.finished.connect(self._sync_worker.deleteLater)
        self._sync_thread.finished.connect(self._sync_thread.deleteLater)
        self._sync_thread.finished.connect(self._sync_cleanup)
        self._sync_thread.start()

    def _schedule_pending_retry(self):
        if self._pending_retry_scheduled:
            return
        # Un reporte de Mercado Pago puede tardar varios minutos. Reintentamos
        # la MISMA tarea, nunca generamos otra. Tras ~10 minutos dejamos de
        # insistir automáticamente y el botón "Revisar estado" queda disponible.
        if self._pending_retry_count >= 30:
            return
        self._pending_retry_scheduled = True
        QTimer.singleShot(20000, self._retry_pending_task)

    @Slot()
    def _retry_pending_task(self):
        self._pending_retry_scheduled = False
        if not self.db.get_setting("mercadopago_pending_task_id", ""):
            return
        self._pending_retry_count += 1
        self.sync_api(True)

    @Slot()
    def _sync_cleanup(self):
        self._sync_thread = None
        self._sync_worker = None

    @Slot(object)
    def _sync_finished(self, result):
        self.sync_btn.setEnabled(True)
        self.more_btn.setEnabled(True)

        if getattr(result, "pending", False):
            task_id = getattr(result, "task_id", None)
            if task_id:
                self.db.set_setting("mercadopago_pending_task_id", str(task_id))
                if self._sync_range:
                    self.db.set_setting("mercadopago_pending_start", self._sync_range[0].isoformat())
                    self.db.set_setting("mercadopago_pending_end", self._sync_range[1].isoformat())
                if not self.db.get_setting("mercadopago_pending_created_iso", ""):
                    self.db.set_setting("mercadopago_pending_created_iso", datetime.now().isoformat(timespec="seconds"))
            self.sync_btn.setText("Revisar estado")
            self.sync_state_label.setText("Preparando reporte")
            self.sync_state_label.setProperty("state", "warn")
            self.sync_state_label.style().unpolish(self.sync_state_label); self.sync_state_label.style().polish(self.sync_state_label)
            self.last_sync_label.setText("Mercado Pago sigue procesando · App Gastos lo revisará solo")
            self._schedule_pending_retry()
            # Ya no mostramos un popup de error: procesar en segundo plano es
            # un estado normal de la API, no un fallo.
            return

        if not getattr(result, "ok", False):
            # Si la tarea guardada dejó de existir, olvidamos el ID para que el
            # próximo intento pueda descubrir o crear una tarea válida.
            message = getattr(result, "message", "No se pudo sincronizar.")
            low = message.lower()
            if (
                "404" in message
                or "not found" in low
                or "no encontrada" in low
                or "invalid taskid" in low
                or "invalid task-id" in low
                or "invalid_parameter" in low
            ):
                self.db.set_setting("mercadopago_pending_task_id", "")
                self.db.set_setting("mercadopago_pending_start", "")
                self.db.set_setting("mercadopago_pending_end", "")
                self.db.set_setting("mercadopago_pending_created_iso", "")
            self.refresh()
            if "invalid taskid" in low or "invalid task-id" in low:
                # Algunas cuentas argentinas no aceptan /task/{id}. No hacemos
                # que el usuario pelee con ese detalle técnico: olvidamos el
                # ID local y reintentamos por /list/creación una sola vez.
                self.db.set_setting("mercadopago_pending_task_id", "")
                self.db.set_setting("mercadopago_pending_start", "")
                self.db.set_setting("mercadopago_pending_end", "")
                self.db.set_setting("mercadopago_pending_created_iso", "")
                if self._pending_retry_count < 1:
                    self._pending_retry_count += 1
                    QTimer.singleShot(150, lambda: self.sync_api(True))
                    return
            if not self._sync_silent:
                QMessageBox.warning(self, "Mercado Pago", message)
            return

        try:
            self.db.set_setting("mercadopago_reports_configured", "1")
            self.db.set_setting("mercadopago_pending_task_id", "")
            self.db.set_setting("mercadopago_pending_start", "")
            self.db.set_setting("mercadopago_pending_end", "")
            self.db.set_setting("mercadopago_pending_created_iso", "")
            rows = import_mercadopago_bytes(result.content or b"", result.file_name or "report.csv")
            stage = self.db.stage_imported_movements(rows, "mercado_pago", int(self.account.currentData()))
            now = datetime.now()
            stamp = now.strftime("%d/%m/%Y %H:%M")
            self.db.set_setting("mercadopago_last_api_sync", stamp)
            self.db.set_setting("mercadopago_last_api_sync_iso", now.isoformat(timespec="seconds"))
            self._pending_retry_count = 0
        except Exception as exc:
            self.refresh()
            if not self._sync_silent:
                QMessageBox.critical(self, "Mercado Pago", f"El reporte se descargó, pero no pude procesarlo:\n\n{exc}")
            return
        self.status.setCurrentIndex(0)
        self.refresh()
        self.data_changed.emit()
        if not self._sync_silent:
            QMessageBox.information(
                self, "Mercado Pago sincronizado",
                f"Movimientos leídos: {len(rows)}\nNuevos por revisar: {stage['inserted']}\nYa conocidos: {stage['duplicates']}"
            )

    def import_report(self):
        if not self.account.currentData():
            QMessageBox.warning(self, "Cuenta", "Creá o seleccioná primero la cuenta que representa Mercado Pago.")
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Importar reporte de Mercado Pago", "",
            "Reportes (*.csv *.xlsx *.xlsm);;CSV (*.csv);;Excel (*.xlsx *.xlsm)"
        )
        if not path: return
        try:
            rows = import_mercadopago_report(path)
            result = self.db.stage_imported_movements(rows, "mercado_pago", int(self.account.currentData()))
            self.db.set_setting("mercadopago_last_import", path)
        except Exception as exc:
            QMessageBox.critical(self, "No se pudo importar", str(exc)); return
        self.status.setCurrentIndex(0); self.refresh(); self.data_changed.emit()
        QMessageBox.information(
            self, "Reporte importado",
            f"Encontré {len(rows)} movimientos compatibles.\n\n"
            f"Nuevos: {result['inserted']}\nYa existentes: {result['duplicates']}\n\n"
            "Los nuevos quedaron en 'Por revisar' para que puedas categorizarlos sin ensuciar tus estadísticas."
        )

    def review_item(self, import_id):
        item = self.db.imported_movement(int(import_id))
        if not item or item["status"] != "pending": return
        dlg = ImportReviewDialog(self.db, item, self)
        if dlg.exec():
            data = dlg.data()
            try:
                self.db.accept_import(int(import_id), **data)
            except Exception as exc:
                QMessageBox.warning(self, "No se pudo agregar", str(exc)); return
            self.refresh(); self.data_changed.emit()

    def ignore_item(self, import_id):
        if QMessageBox.question(self, "Ignorar movimiento", "¿Ignorar este movimiento importado?") != QMessageBox.StandardButton.Yes:
            return
        self.db.ignore_import(int(import_id)); self.refresh(); self.data_changed.emit()

    def accept_categorized(self):
        ready = sum(1 for r in self.db.imported_movements("pending") if r.get("category_id"))
        if not ready: return
        if QMessageBox.question(self, "Agregar movimientos", f"¿Agregar los {ready} movimientos que ya tienen categoría sugerida?") != QMessageBox.StandardButton.Yes:
            return
        count = self.db.accept_categorized_imports(); self.refresh(); self.data_changed.emit()
        QMessageBox.information(self, "Listo", f"Se agregaron {count} movimientos.")
