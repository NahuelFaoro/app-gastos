from __future__ import annotations

from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QDialog, QFormLayout, QFrame,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout,
)

from ..widgets import CategorySelectButton
from .categories import CategoryPickerDialog

class ImportReviewDialog(QDialog):
    """Revisión rápida de un movimiento importado antes de incorporarlo.

    Además de gasto/ingreso permite convertir movimientos de Mercado Pago en
    transferencias entre cuentas propias. Así mover dinero a un banco o traer
    plata desde otra cuenta no altera ingresos/gastos del mes.
    """
    def __init__(self, db, item, parent=None):
        super().__init__(parent)
        self.db = db
        self.item = dict(item)
        self.original_kind = self.item.get("kind", "expense")
        self.kind = self.original_kind
        self.category_data = None
        self.setWindowTitle("Revisar movimiento importado")
        self.setMinimumWidth(540)

        root = QVBoxLayout(self); root.setContentsMargins(22, 20, 22, 20); root.setSpacing(14)
        title = QLabel("Revisar movimiento"); title.setObjectName("PageTitle")
        subtitle = QLabel(f"{self.item.get('source','').replace('_',' ').title()} · {self.item.get('tx_date','')} · {self.item.get('account_name','')}")
        subtitle.setObjectName("PageSubtitle")
        root.addWidget(title); root.addWidget(subtitle)

        amount_card = QFrame(); amount_card.setObjectName("AmountCard")
        al = QVBoxLayout(amount_card); al.setContentsMargins(18, 14, 18, 14); al.setSpacing(4)
        sign = "+" if self.original_kind == "income" else "−"
        amount = QLabel(f"{sign} {db.currency_symbol()} {float(self.item.get('amount') or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        amount.setObjectName("ImportAmount")
        al.addWidget(amount)
        root.addWidget(amount_card)

        scan_cur = self.item.get("scan_installment_current")
        scan_total = self.item.get("scan_installment_total")
        if scan_cur and scan_total:
            installment_detected = QLabel(
                f"El resumen parece indicar que este consumo corresponde a la cuota {scan_cur}/{scan_total}. "
                "La detección se conserva para que puedas vincularla a un plan de cuotas después de agregar el movimiento."
            )
            installment_detected.setObjectName("ImportTransferHint")
            installment_detected.setWordWrap(True)
            root.addWidget(installment_detected)

        hint = QLabel("Elegí cómo querés interpretar este movimiento. Usá Transferencia cuando solo moviste dinero entre cuentas tuyas.")
        hint.setObjectName("SmallMuted"); hint.setWordWrap(True); root.addWidget(hint)
        if self.item.get("transfer_hint"):
            op = self.item.get("operation_type") or "transferencia/retiro"
            detected = QLabel(f"Mercado Pago marcó esta operación como {op}. Si el dinero fue a otra cuenta tuya, registrala como Transferencia para que no cuente como gasto.")
            detected.setObjectName("ImportTransferHint"); detected.setWordWrap(True); root.addWidget(detected)

        segments = QHBoxLayout(); segments.setSpacing(7)
        self.kind_buttons = {}
        group = QButtonGroup(self); group.setExclusive(True)
        for key, label in (("expense", "Gasto"), ("income", "Ingreso"), ("transfer", "Transferencia")):
            b = QPushButton(label); b.setObjectName("SegmentButton"); b.setCheckable(True); b.setChecked(key == self.kind)
            b.clicked.connect(lambda checked=False, k=key: self._set_kind(k))
            group.addButton(b); segments.addWidget(b); self.kind_buttons[key] = b
        segments.addStretch(); root.addLayout(segments)

        form = QFormLayout(); form.setSpacing(11)
        self.description = QLineEdit(self.item.get("description") or "")
        self.category = CategorySelectButton("Elegir categoría")
        self.category.clicked.connect(self._pick_category)
        self.other_account = QComboBox()
        self.other_account.setMinimumWidth(240)
        origin_id = int(self.item.get("account_id") or 0)
        for account in self.db.accounts():
            if int(account["id"]) != origin_id:
                self.other_account.addItem(account["name"], account["id"])
        form.addRow("Descripción", self.description)
        form.addRow("Categoría", self.category)
        form.addRow("Otra cuenta", self.other_account)
        self.category_label = form.labelForField(self.category)
        self.other_account_label = form.labelForField(self.other_account)
        root.addLayout(form)

        if self.item.get("category_id"):
            self._load_category(int(self.item["category_id"]))

        self.remember = QCheckBox("Recordar esta categoría para descripciones similares")
        self.remember.setChecked(False)
        self.remember_hint = QLabel("Si la activás, los próximos movimientos importados con una descripción parecida se sugerirán automáticamente en esta categoría.")
        self.remember_hint.setObjectName("SmallMuted"); self.remember_hint.setWordWrap(True)
        root.addWidget(self.remember); root.addWidget(self.remember_hint)

        transfer_help = QLabel("En una salida de Mercado Pago, la otra cuenta será el destino. En una entrada, será la cuenta desde la que salió el dinero.")
        transfer_help.setObjectName("SmallMuted"); transfer_help.setWordWrap(True)
        self.transfer_help = transfer_help; root.addWidget(transfer_help)

        actions = QHBoxLayout(); actions.addStretch()
        cancel = QPushButton("Cancelar"); cancel.setObjectName("SecondaryButton"); cancel.clicked.connect(self.reject)
        save = QPushButton("Agregar a movimientos"); save.clicked.connect(self._validate)
        actions.addWidget(cancel); actions.addWidget(save); root.addLayout(actions)
        self._update_kind_ui()

    def _set_kind(self, kind):
        if kind == self.kind:
            return
        self.kind = kind
        self.kind_buttons[kind].setChecked(True)
        if kind != "transfer":
            # Una categoría de gasto no es válida como ingreso y viceversa.
            self.category.set_category(None)
            self.category_data = None
        self._update_kind_ui()

    def _update_kind_ui(self):
        transfer = self.kind == "transfer"
        self.category.setVisible(not transfer)
        if self.category_label: self.category_label.setVisible(not transfer)
        self.other_account.setVisible(transfer)
        if self.other_account_label: self.other_account_label.setVisible(transfer)
        self.remember.setVisible(not transfer)
        self.remember_hint.setVisible(not transfer)
        self.transfer_help.setVisible(transfer)

    def _load_category(self, category_id):
        if self.kind == "transfer":
            return
        choices = self.db.category_choices(self.kind, True)
        category = next((c for c in choices if int(c["id"]) == int(category_id)), None)
        if category:
            self.category.set_category(category)
            self.category_data = category

    def _pick_category(self):
        if self.kind == "transfer":
            return
        dlg = CategoryPickerDialog(self.db, self.kind, self.category.category_id, include_parents=True, parent=self)
        if dlg.exec() and dlg.selected_category:
            self.category_data = dlg.selected_category
            self.category.set_category(dlg.selected_category)

    def _validate(self):
        if self.kind == "transfer":
            if self.other_account.currentData() is None:
                QMessageBox.warning(self, "Transferencia", "Necesitás al menos otra cuenta para registrar una transferencia.")
                return
        elif not self.category.category_id:
            QMessageBox.warning(self, "Categoría", "Elegí una categoría para guardar el movimiento.")
            return
        self.accept()

    def data(self):
        return {
            "kind": self.kind,
            "category_id": self.category.category_id if self.kind != "transfer" else None,
            "description": self.description.text().strip(),
            "remember_rule": self.remember.isChecked() if self.kind != "transfer" else False,
            "transfer_account_id": self.other_account.currentData() if self.kind == "transfer" else None,
        }
