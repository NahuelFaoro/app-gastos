from __future__ import annotations

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
    QFrame, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPlainTextEdit,
    QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from ..date_picker import WorkDateEdit
from ..utils import money
from ..widgets import CategoryChipButton, CategorySelectButton, MoneyEdit
from .categories import CategoryPickerDialog

class LegacyMonthlyEntryDialog(QDialog):
    """Editor de un importe mensual traído del Excel anterior.

    No inventa una fecha ni una cuenta: conserva la precisión mensual del dato original.
    """
    def __init__(self, db, entry, parent=None):
        super().__init__(parent)
        self.db = db
        self.entry = entry
        self.kind = entry["kind"]
        self.setWindowTitle("Editar movimiento importado")
        self.resize(520, 390)
        self.setMinimumWidth(480)

        root = QVBoxLayout(self); root.setContentsMargins(24,20,24,20); root.setSpacing(13)
        title = QLabel("Movimiento mensual importado"); title.setObjectName("PageTitle")
        subtitle = QLabel(
            "Este dato viene de tu Excel y representa el total de una categoría en un mes. "
            "Como el archivo no guardaba el día ni la cuenta, App Gastos no los inventa."
        ); subtitle.setObjectName("PageSubtitle"); subtitle.setWordWrap(True)
        root.addWidget(title); root.addWidget(subtitle)

        month_names = ["Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
        period = QLabel(f"{month_names[int(entry['month'])-1]} {entry['year']}  ·  {'Gasto' if self.kind == 'expense' else 'Ingreso'}")
        period.setObjectName("SectionTitle"); root.addWidget(period)

        amount_card = QFrame(); amount_card.setObjectName("AmountCard")
        al = QHBoxLayout(amount_card); al.setContentsMargins(18,10,18,10)
        currency = QLabel(db.currency_symbol()); currency.setObjectName("CurrencyPrefix")
        self.amount = MoneyEdit(db.currency_symbol()); self.amount.set_value(float(entry["amount"]))
        al.addWidget(currency); al.addWidget(self.amount,1); root.addWidget(amount_card)

        cap = QLabel("Categoría"); cap.setObjectName("FieldLabel"); root.addWidget(cap)
        self.category = CategorySelectButton("Elegir categoría")
        self.category.clicked.connect(self._pick_category); root.addWidget(self.category)
        chosen = next((c for c in db.category_choices(self.kind) if int(c["id"]) == int(entry.get("category_id") or 0)), None)
        self.category.set_category(chosen)

        note = QLabel("Doble clic desde Movimientos para volver a editar este registro cuando quieras.")
        note.setObjectName("SmallMuted"); note.setWordWrap(True); root.addWidget(note)
        root.addStretch()

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        save = QPushButton("Guardar cambios"); save.clicked.connect(self._accept)
        buttons.addButton(save, QDialogButtonBox.ButtonRole.AcceptRole); buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _pick_category(self):
        dlg = CategoryPickerDialog(self.db, self.kind, self.category.category_id, parent=self)
        if dlg.exec() and dlg.selected_category:
            self.category.set_category(dlg.selected_category)

    def _accept(self):
        if self.amount.value() <= 0:
            QMessageBox.warning(self,"Importe","Ingresá un importe mayor a cero."); return
        if not self.category.category_id:
            QMessageBox.warning(self,"Categoría","Elegí una categoría."); return
        self.accept()

    def data(self):
        return {"amount": self.amount.value(), "category_id": int(self.category.category_id)}


class TransactionDialog(QDialog):
    def __init__(self, db, tx=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.tx = tx
        self.kind = "expense"
        self.category_data = None
        self.setObjectName("TransactionDialog")
        self.setWindowTitle("Editar movimiento" if tx else "Nuevo movimiento")
        self.resize(620, 770)
        self.setMinimumWidth(520)

        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(26, 22, 26, 22)
        self.root.setSpacing(14)
        self._build_heading()
        self._build_kind_selector()
        self._build_amount_card()
        self._build_category_card()
        self._build_basic_details_card()
        self._build_installment_card()
        self._build_optional_details()
        self._build_actions()
        self._wire_form(tx)

    def _build_heading(self) -> None:
        eyebrow = QLabel("MOVIMIENTO")
        eyebrow.setObjectName("TinyCaption")
        title = QLabel("Editar movimiento" if self.tx else "Nuevo movimiento")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Cargalo rápido. Lo importante primero; el resto queda más abajo.")
        subtitle.setObjectName("PageSubtitle")
        self.root.addWidget(eyebrow)
        self.root.addWidget(title)
        self.root.addWidget(subtitle)

    def _build_kind_selector(self) -> None:
        self.mode_wrap = QFrame()
        self.mode_wrap.setObjectName("DialogSegmentWrap")
        layout = QHBoxLayout(self.mode_wrap)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)
        self.kind_group = QButtonGroup(self)
        self.kind_group.setExclusive(True)
        self.kind_buttons: dict[str, QPushButton] = {}
        for label, kind in (("Gasto", "expense"), ("Ingreso", "income"), ("Transferencia", "transfer")):
            button = QPushButton(label)
            button.setObjectName("SegmentButton")
            button.setCheckable(True)
            button.setMinimumHeight(40)
            self.kind_group.addButton(button)
            self.kind_buttons[kind] = button
            layout.addWidget(button)
            button.clicked.connect(lambda checked=False, k=kind: self.set_kind(k))
        self.root.addWidget(self.mode_wrap)

    def _build_amount_card(self) -> None:
        card = QFrame()
        card.setObjectName("AmountHeroCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(8)
        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        label = QLabel("Importe")
        label.setObjectName("FieldLabel")
        hint = QLabel("Separador de miles automático")
        hint.setObjectName("SmallMuted")
        head.addWidget(label)
        head.addStretch()
        head.addWidget(hint)
        layout.addLayout(head)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        currency = QLabel(self.db.currency_symbol())
        currency.setObjectName("CurrencyPrefix")
        self.amount = MoneyEdit(self.db.currency_symbol())
        self.amount.setAccessibleName("Importe")
        row.addWidget(currency, 0, Qt.AlignmentFlag.AlignBottom)
        row.addWidget(self.amount, 1)
        layout.addLayout(row)
        self.root.addWidget(card)

    def _build_category_card(self) -> None:
        self.category_card = QFrame()
        self.category_card.setObjectName("InputSectionCard")
        layout = QVBoxLayout(self.category_card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)
        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Categoría")
        title.setObjectName("SectionTitle")
        hint = QLabel("Elegí la categoría principal y su subcategoría")
        hint.setObjectName("SmallMuted")
        head.addWidget(title)
        head.addStretch()
        head.addWidget(hint)
        layout.addLayout(head)
        self.category = CategorySelectButton("Elegir categoría")
        self.category.clicked.connect(self.open_category_picker)
        layout.addWidget(self.category)
        self.recent_label = QLabel("Recientes")
        self.recent_label.setObjectName("SmallMuted")
        layout.addWidget(self.recent_label)
        self.recent_categories = QHBoxLayout()
        self.recent_categories.setSpacing(7)
        layout.addLayout(self.recent_categories)
        self.root.addWidget(self.category_card)

    def _build_basic_details_card(self) -> None:
        card = QFrame()
        card.setObjectName("InputSectionCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)
        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Detalles básicos")
        title.setObjectName("SectionTitle")
        hint = QLabel("Cuenta, descripción y fecha")
        hint.setObjectName("SmallMuted")
        head.addWidget(title)
        head.addStretch()
        head.addWidget(hint)
        layout.addLayout(head)

        form = QFormLayout()
        form.setSpacing(11)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setContentsMargins(0, 0, 0, 0)
        self.account = QComboBox()
        self.account.setMinimumHeight(40)
        self.to_account = QComboBox()
        self.to_account.setMinimumHeight(40)
        self.description = QLineEdit()
        self.description.setPlaceholderText("Ej: Nafta, supermercado, cliente…")
        self.date = WorkDateEdit(QDate.currentDate())
        self.date.setCalendarPopup(True)
        self.date.setDisplayFormat("dd/MM/yyyy")
        self.date.setMinimumHeight(40)
        self.date_box = QWidget()
        self.date_box.setObjectName("InlineActionGroup")
        date_row = QHBoxLayout(self.date_box)
        date_row.setContentsMargins(0, 0, 0, 0)
        date_row.setSpacing(8)
        date_row.addWidget(self.date, 1)
        today = QPushButton("Hoy")
        today.setObjectName("SecondaryButton")
        yesterday = QPushButton("Ayer")
        yesterday.setObjectName("SecondaryButton")
        today.clicked.connect(lambda: self.date.setDate(QDate.currentDate()))
        yesterday.clicked.connect(lambda: self.date.setDate(QDate.currentDate().addDays(-1)))
        date_row.addWidget(today)
        date_row.addWidget(yesterday)
        form.addRow("Cuenta", self.account)
        self.to_account_label = QLabel("Cuenta destino")
        form.addRow(self.to_account_label, self.to_account)
        form.addRow("Descripción", self.description)
        self.date_label = QLabel("Fecha")
        form.addRow(self.date_label, self.date_box)
        layout.addLayout(form)
        self.root.addWidget(card)

    def _build_installment_card(self) -> None:
        self.card_purchase_box = QFrame()
        self.card_purchase_box.setObjectName("InstallmentCard")
        layout = QVBoxLayout(self.card_purchase_box)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)
        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Compra con tarjeta")
        title.setObjectName("SectionTitle")
        hint = QLabel("Se usa solo cuando la cuenta elegida es una tarjeta")
        hint.setObjectName("SmallMuted")
        head.addWidget(title)
        head.addStretch()
        head.addWidget(hint)
        layout.addLayout(head)
        self.installments = QCheckBox("Pagar en cuotas")
        layout.addWidget(self.installments)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.installment_count = QSpinBox()
        self.installment_count.setRange(2, 36)
        self.installment_count.setValue(3)
        self.installment_count.setMinimumHeight(38)
        row.addWidget(QLabel("Cantidad"))
        row.addWidget(self.installment_count, 0)
        self.installment_preview = QLabel("")
        self.installment_preview.setObjectName("SmallMuted")
        row.addWidget(self.installment_preview, 1)
        layout.addLayout(row)
        self.installment_help = QLabel(
            "Ingresá arriba el total completo. App Gastos registra esta cuota y programa las siguientes mes a mes."
        )
        self.installment_help.setObjectName("SmallMuted")
        self.installment_help.setWordWrap(True)
        layout.addWidget(self.installment_help)
        self.root.addWidget(self.card_purchase_box)

    def _build_optional_details(self) -> None:
        self.more_btn = QPushButton("＋  Más detalles")
        self.more_btn.setObjectName("GhostButton")
        self.more_btn.setCheckable(True)
        self.more_btn.setChecked(False)
        self.more_btn.clicked.connect(self._toggle_details)
        self.root.addWidget(self.more_btn, 0, Qt.AlignmentFlag.AlignLeft)

        self.details = QFrame()
        self.details.setObjectName("InputSectionCard")
        form = QFormLayout(self.details)
        form.setContentsMargins(16, 14, 16, 14)
        form.setSpacing(11)
        self.tags = QLineEdit()
        self.tags.setPlaceholderText("trabajo, delivery, viaje…")
        self.note = QPlainTextEdit()
        self.note.setPlaceholderText("Nota opcional")
        self.note.setMaximumHeight(90)
        form.addRow("Etiquetas", self.tags)
        form.addRow("Nota", self.note)
        self.details.setVisible(False)
        self.root.addWidget(self.details)

    def _build_actions(self) -> None:
        self.root.addStretch()
        self.actions_widget = QFrame()
        self.actions_widget.setObjectName("DialogActionBar")
        actions = QHBoxLayout(self.actions_widget)
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(10)
        actions.addStretch()
        cancel = QPushButton("Cancelar")
        cancel.setObjectName("SecondaryButton")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Guardar movimiento")
        save.setObjectName("DialogPrimaryButton")
        save.setMinimumWidth(190)
        save.clicked.connect(self._accept)
        actions.addWidget(cancel)
        actions.addWidget(save)
        self.root.addWidget(self.actions_widget)

    def _wire_form(self, tx) -> None:
        self._load_accounts()
        self.account.currentIndexChanged.connect(self._update_card_purchase_ui)
        self.installments.toggled.connect(self._update_installment_preview)
        self.installment_count.valueChanged.connect(self._update_installment_preview)
        self.amount.valueChanged.connect(self._update_installment_preview)
        self.set_kind(tx["kind"] if tx else "expense")
        if tx:
            self._load_tx(tx)
        else:
            self._apply_last_used()
        self.amount.setFocus()
        self.shortcut_save = QShortcut(QKeySequence("Ctrl+Return"), self)
        self.shortcut_save.activated.connect(self._accept)
        self.shortcut_save2 = QShortcut(QKeySequence("Ctrl+Enter"), self)
        self.shortcut_save2.activated.connect(self._accept)

    def _load_accounts(self):
        self.account.clear(); self.to_account.clear()
        for a in self.db.accounts():
            label = f"●  {a['name']}"
            self.account.addItem(label, a["id"]); self.to_account.addItem(label, a["id"])

    def _category_by_id(self, category_id):
        if not category_id: return None
        return next((c for c in self.db.category_choices(self.kind) if c["id"] == int(category_id)), None)

    def set_kind(self, kind):
        previous_id = self.category.category_id if hasattr(self, "category") else None
        self.kind = kind; self.kind_buttons[kind].setChecked(True)
        is_transfer = kind == "transfer"
        self.category_card.setVisible(not is_transfer); self.to_account.setVisible(is_transfer); self.to_account_label.setVisible(is_transfer)
        if not is_transfer:
            chosen = self._category_by_id(previous_id)
            if not chosen:
                key = "last_expense_category_id" if kind == "expense" else "last_income_category_id"
                saved = self.db.get_setting(key, "")
                chosen = self._category_by_id(saved) if saved else None
            self.category.set_category(chosen)
            self._load_recent_category_chips()
        self._update_card_purchase_ui()

    def _selected_account(self):
        account_id = self.account.currentData() if hasattr(self, "account") else None
        return self.db.account(int(account_id)) if account_id else None

    def _update_card_purchase_ui(self):
        if not hasattr(self, "card_purchase_box"):
            return
        account = self._selected_account()
        is_card_expense = self.kind == "expense" and account and account.get("type") == "Tarjeta"
        # Al editar una cuota ya generada no ofrecemos recrear el plan.
        existing_installment = bool(self.tx and self.tx.get("installment_plan_id"))
        self.card_purchase_box.setVisible(bool(is_card_expense))
        self.installments.setEnabled(not existing_installment)
        if existing_installment:
            self.installments.setChecked(False)
            n = int(self.tx.get("installment_number") or 1)
            total = int(self.tx.get("installment_total") or 1)
            self.installment_preview.setText(f"Cuota {n}/{total} · editar acá modifica solo esta cuota")
        else:
            self._update_installment_preview()

    def _update_installment_preview(self):
        if not hasattr(self, "installment_preview"):
            return
        enabled = self.installments.isChecked() and self.installments.isEnabled()
        self.installment_count.setEnabled(enabled)
        if not enabled:
            if not (self.tx and self.tx.get("installment_plan_id")):
                self.installment_preview.setText("")
            return
        count = max(2, int(self.installment_count.value()))
        total = float(self.amount.value())
        per = total / count if total > 0 else 0
        symbol = self.db.currency_symbol()
        self.installment_preview.setText(f"≈ {money(per, symbol, self.db.balances_hidden())} por cuota")

    def _load_recent_category_chips(self):
        while self.recent_categories.count():
            item = self.recent_categories.takeAt(0); w = item.widget()
            if w: w.deleteLater()
        recent = self.db.recent_categories(self.kind, 4)
        has_recent = bool(recent)
        if hasattr(self, "recent_label"):
            self.recent_label.setVisible(has_recent)
        if not recent:
            return
        for c in recent:
            b = CategoryChipButton(c)
            b.clicked.connect(lambda checked=False, cat=c: self.category.set_category(cat)); self.recent_categories.addWidget(b)
        self.recent_categories.addStretch()

    def open_category_picker(self):
        dlg = CategoryPickerDialog(self.db, self.kind, self.category.category_id, parent=self)
        if dlg.exec() and dlg.selected_category:
            self.category.set_category(dlg.selected_category)

    def _apply_last_used(self):
        account = self.db.get_setting("last_account_id", "")
        if account:
            i = self.account.findData(int(account)); self.account.setCurrentIndex(i if i >= 0 else 0)
        key = "last_expense_category_id" if self.kind == "expense" else "last_income_category_id"
        cat = self.db.get_setting(key, "")
        if cat:
            self.category.set_category(self._category_by_id(cat))

    def _load_tx(self, tx):
        self.amount.setValue(float(tx["amount"])); self.description.setText(tx.get("description", "") or "")
        y, m, d = map(int, tx["tx_date"].split("-")); self.date.setDate(QDate(y, m, d))
        i = self.account.findData(tx["account_id"]); self.account.setCurrentIndex(i if i >= 0 else 0)
        if tx.get("to_account_id"):
            i = self.to_account.findData(tx["to_account_id"]); self.to_account.setCurrentIndex(i if i >= 0 else 0)
        if tx.get("category_id"): self.category.set_category(self._category_by_id(tx["category_id"]))
        self.tags.setText(tx.get("tags", "") or ""); self.note.setPlainText(tx.get("note", "") or "")
        self._update_card_purchase_ui()
        if self.tags.text() or self.note.toPlainText():
            self.more_btn.setChecked(True); self._toggle_details(True)

    def _toggle_details(self, checked):
        self.details.setVisible(checked); self.more_btn.setText("−  Menos detalles" if checked else "＋  Más detalles")
        self.adjustSize()

    def data(self):
        return {
            "kind": self.kind, "amount": float(self.amount.value()), "account_id": self.account.currentData(),
            "to_account_id": self.to_account.currentData() if self.kind == "transfer" else None,
            "category_id": self.category.category_id if self.kind != "transfer" else None,
            "tx_date": self.date.date().toString("yyyy-MM-dd"), "description": self.description.text().strip(),
            "tags": self.tags.text().strip(), "note": self.note.toPlainText().strip(),
            "installments": int(self.installment_count.value()) if (self.kind == "expense" and self.installments.isChecked() and self.installments.isEnabled()) else 1,
        }

    def _accept(self):
        try: self.db._validate_tx(self.data())
        except ValueError as e: QMessageBox.warning(self, "Revisá el movimiento", str(e)); return
        self.db.set_setting("last_account_id", self.account.currentData() or "")
        if self.kind != "transfer":
            self.db.set_setting("last_expense_category_id" if self.kind == "expense" else "last_income_category_id", self.category.category_id or "")
        self.accept()


class ExistingInstallmentDialog(QDialog):
    """Convierte un gasto ya existente en la cuota N de un plan activo.

    No inventa cuotas anteriores: únicamente etiqueta el movimiento elegido y
    programa las cuotas que todavía faltan.
    """
    def __init__(self, db, tx, parent=None):
        super().__init__(parent)
        self.db = db
        self.tx = tx
        self.setWindowTitle("Configurar cuotas")
        self.setMinimumWidth(500)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(14)

        title = QLabel("Plan de cuotas")
        title.setObjectName("PageTitle")
        root.addWidget(title)
        desc = tx.get("description") or "Gasto existente"
        sub = QLabel(f"{desc} · este movimiento representa una cuota ya pagada/cargada")
        sub.setObjectName("PageSubtitle"); sub.setWordWrap(True)
        root.addWidget(sub)

        info = QFrame(); info.setObjectName("SoftCard")
        il = QVBoxLayout(info); il.setContentsMargins(16, 14, 16, 14); il.setSpacing(4)
        amount = QLabel(money(float(tx.get("amount") or 0), db.currency_symbol(), db.balances_hidden()))
        amount.setObjectName("CardValue")
        il.addWidget(amount)
        amount_hint = QLabel("Importe de esta cuota")
        amount_hint.setObjectName("SmallMuted")
        il.addWidget(amount_hint)
        root.addWidget(info)

        form = QFormLayout(); form.setSpacing(11)
        self.card = QComboBox()
        cards = [a for a in db.accounts() if a.get("type") == "Tarjeta"]
        for a in cards:
            self.card.addItem(a["name"], a["id"])
        current_account = tx.get("account_id")
        idx = self.card.findData(current_account)
        if idx >= 0: self.card.setCurrentIndex(idx)

        self.total = QSpinBox(); self.total.setRange(2, 60); self.total.setValue(max(12, int(tx.get("installment_total") or 12)))
        self.current = QSpinBox(); self.current.setRange(1, self.total.value()); self.current.setValue(max(1, int(tx.get("installment_number") or 1)))
        self.total.valueChanged.connect(lambda v: self.current.setMaximum(v))
        self.current_date = WorkDateEdit(); self.current_date.setCalendarPopup(True); self.current_date.setDisplayFormat("dd/MM/yyyy")
        # En planes creados desde un resumen, la fecha impresa puede ser la
        # fecha original de compra y no la fecha del resumen/cuota actual. Al
        # corregirlos es más seguro arrancar en hoy y dejarla visible/editable.
        if str(tx.get("external_id") or "").strip():
            self.current_date.setDate(QDate.currentDate())
        else:
            try:
                y,m,d = map(int, str(tx.get("tx_date") or "").split("-")[:3])
                self.current_date.setDate(QDate(y,m,d))
            except Exception:
                self.current_date.setDate(QDate.currentDate())

        form.addRow("Tarjeta", self.card)
        form.addRow("Cuotas totales", self.total)
        form.addRow("Cuota actual", self.current)
        form.addRow("Fecha de esta cuota", self.current_date)
        root.addLayout(form)

        self.preview = QLabel()
        self.preview.setObjectName("Muted")
        self.preview.setWordWrap(True)
        root.addWidget(self.preview)
        self.current.valueChanged.connect(self._update_preview)
        self.total.valueChanged.connect(self._update_preview)
        self._update_preview()

        hint = QLabel(
            "Ejemplo: si elegís 6 de 12, este gasto queda marcado como Cuota 6/12 y App Gastos solo programará 7/12 a 12/12. "
            "Si estás corrigiendo un plan, las cuotas futuras que App Gastos generó automáticamente se reconstruyen desde acá."
        )
        hint.setObjectName("SmallMuted"); hint.setWordWrap(True)
        root.addWidget(hint)

        row = QHBoxLayout(); row.addStretch()
        cancel = QPushButton("Cancelar"); cancel.setObjectName("SecondaryButton"); cancel.clicked.connect(self.reject)
        save = QPushButton("Guardar plan"); save.clicked.connect(self._validate)
        row.addWidget(cancel); row.addWidget(save); root.addLayout(row)

    def _update_preview(self):
        current = int(self.current.value()); total = int(self.total.value())
        remaining = max(0, total - current)
        amount = float(self.tx.get("amount") or 0)
        rest = money(amount * remaining, self.db.currency_symbol(), self.db.balances_hidden())
        self.preview.setText(
            f"Cuota {current}/{total} · quedan {remaining} cuota{'s' if remaining != 1 else ''} · "
            f"restante estimado {rest}"
        )

    def _validate(self):
        if self.card.currentData() is None:
            QMessageBox.warning(self, "Cuotas", "Primero creá o seleccioná una cuenta de tipo Tarjeta.")
            return
        if self.current.value() > self.total.value():
            QMessageBox.warning(self, "Cuotas", "La cuota actual no puede superar el total.")
            return
        self.accept()

    def data(self):
        qd = self.current_date.date()
        return {
            "card_account_id": int(self.card.currentData()),
            "current_installment": int(self.current.value()),
            "total_installments": int(self.total.value()),
            "current_date": f"{qd.year():04d}-{qd.month():02d}-{qd.day():02d}",
        }
