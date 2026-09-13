from __future__ import annotations

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFormLayout, QFrame, QHBoxLayout, QLineEdit,
    QMessageBox, QPushButton, QSpinBox, QVBoxLayout,
)

from ..date_picker import WorkDateEdit
from ..widgets import CategorySelectButton, MoneyEdit
from .categories import CategoryPickerDialog
from .transactions import TransactionDialog

class BudgetDialog(QDialog):
    def __init__(self, db, budget=None, parent=None):
        super().__init__(parent); self.db=db; self.category_data=None; self.setWindowTitle("Presupuesto"); self.setMinimumWidth(470)
        root=QVBoxLayout(self); form=QFormLayout()
        self.name=QLineEdit(); self.name.setPlaceholderText("Ej: Comida mensual")
        self.amount=MoneyEdit(db.currency_symbol()); self.category=CategorySelectButton("Todos los gastos"); self.category.clicked.connect(self._pick_category)
        self.account=QComboBox(); self.account.addItem("Todas las cuentas", None)
        for a in db.accounts(): self.account.addItem(a["name"], a["id"])
        self.start=WorkDateEdit(QDate.currentDate()); self.start.setCalendarPopup(True); self.start.setDisplayFormat("dd/MM/yyyy")
        form.addRow("Nombre", self.name); form.addRow("Límite mensual", self.amount); form.addRow("Categoría", self.category); form.addRow("Cuenta", self.account); form.addRow("Desde", self.start); root.addLayout(form)
        clear=QPushButton("Usar todos los gastos"); clear.setObjectName("GhostButton"); clear.clicked.connect(lambda: self.category.set_category(None)); root.addWidget(clear,0,Qt.AlignmentFlag.AlignLeft)
        row=QHBoxLayout(); row.addStretch(); cancel=QPushButton("Cancelar"); cancel.setObjectName("SecondaryButton"); cancel.clicked.connect(self.reject); save=QPushButton("Guardar"); save.clicked.connect(self._validate); row.addWidget(cancel); row.addWidget(save); root.addLayout(row)
        if budget:
            self.name.setText(budget["name"]); self.amount.setValue(float(budget["amount"]));
            if budget.get("category_id"):
                c=next((x for x in db.category_choices("expense",True) if x["id"]==budget["category_id"]),None); self.category.set_category(c)
            i=self.account.findData(budget.get("account_id")); self.account.setCurrentIndex(i if i>=0 else 0)
            y,m,d=map(int,budget["start_date"].split("-")); self.start.setDate(QDate(y,m,d))
    def _pick_category(self):
        dlg=CategoryPickerDialog(self.db,"expense",self.category.category_id,include_parents=True,parent=self)
        if dlg.exec() and dlg.selected_category:self.category.set_category(dlg.selected_category)
    def _validate(self):
        if not self.name.text().strip(): QMessageBox.warning(self,"Presupuesto","Poné un nombre al presupuesto."); return
        if self.amount.value()<=0: QMessageBox.warning(self,"Presupuesto","El límite debe ser mayor a cero."); return
        self.accept()
    def data(self): return {"name":self.name.text().strip(),"amount":float(self.amount.value()),"category_id":self.category.category_id,"account_id":self.account.currentData(),"start_date":self.start.date().toString("yyyy-MM-dd")}


class RecurringDialog(TransactionDialog):
    def __init__(self, db, item=None, parent=None):
        self.recurring_item=item; super().__init__(db, tx=None, parent=parent); self.setWindowTitle("Movimiento recurrente")
        card=QFrame(); card.setObjectName("SoftCard"); form=QFormLayout(card); form.setContentsMargins(14,12,14,12)
        self.frequency=QComboBox(); self.frequency.addItem("Cada día","daily"); self.frequency.addItem("Cada semana","weekly"); self.frequency.addItem("Cada mes","monthly"); self.frequency.addItem("Cada año","yearly"); self.frequency.setCurrentIndex(2)
        self.interval=QSpinBox(); self.interval.setRange(1,99); self.interval.setValue(1)
        self.next_date=WorkDateEdit(QDate.currentDate()); self.next_date.setCalendarPopup(True); self.next_date.setDisplayFormat("dd/MM/yyyy")
        form.addRow("Frecuencia",self.frequency); form.addRow("Cada",self.interval); form.addRow("Próxima fecha",self.next_date)
        self.root.insertWidget(self.root.indexOf(self.actions_widget), card)
        self.date_box.setVisible(False); self.date_label.setVisible(False)
        if item:
            self.set_kind(item["kind"]); self.amount.setValue(float(item["amount"])); self.description.setText(item.get("description","") or "")
            i=self.account.findData(item["account_id"]); self.account.setCurrentIndex(i if i>=0 else 0)
            if item.get("to_account_id"):
                i=self.to_account.findData(item["to_account_id"]); self.to_account.setCurrentIndex(i if i>=0 else 0)
            if item.get("category_id"): self.category.set_category(self._category_by_id(item["category_id"]))
            self.tags.setText(item.get("tags","") or ""); self.note.setPlainText(item.get("note","") or "")
            if self.tags.text() or self.note.toPlainText(): self.more_btn.setChecked(True); self._toggle_details(True)
            i=self.frequency.findData(item["frequency"]); self.frequency.setCurrentIndex(i if i>=0 else 2); self.interval.setValue(int(item["interval_value"]))
            y,m,d=map(int,item["next_date"].split("-")); self.next_date.setDate(QDate(y,m,d))
    def data(self):
        d=super().data(); d["next_date"]=self.next_date.date().toString("yyyy-MM-dd"); d["frequency"]=self.frequency.currentData(); d["interval_value"]=self.interval.value(); return d
