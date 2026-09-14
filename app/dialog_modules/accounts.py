from __future__ import annotations

from collections import defaultdict

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFormLayout, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QScrollArea, QSpinBox, QVBoxLayout, QWidget,
)

from ..constants import CATEGORY_COLORS
from ..date_picker import WorkDateEdit
from ..utils import money
from ..widgets import IconBadge, MoneyEdit, StatCard, TransactionRowWidget
from .visual import ColorButton

class AccountDialog(QDialog):
    def __init__(self, account=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Editar cuenta" if account else "Nueva cuenta")
        self.setMinimumWidth(470)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(14)

        title = QLabel("Editar cuenta" if account else "Nueva cuenta")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Configurá efectivo, bancos, billeteras, ahorros o una tarjeta de crédito.")
        subtitle.setObjectName("PageSubtitle")
        root.addWidget(title); root.addWidget(subtitle)

        form = QFormLayout(); form.setSpacing(11)
        self.name = QLineEdit(); self.name.setPlaceholderText("Ej: Billetera, Ahorros, Visa…")
        self.type = QComboBox(); self.type.addItems(["Efectivo", "Banco", "Billetera", "Tarjeta", "Ahorro", "Inversión", "Otra"])
        self.opening = MoneyEdit("$", allow_negative=True)
        self.color = ColorButton(account["color"] if account else CATEGORY_COLORS[0])
        form.addRow("Nombre", self.name)
        form.addRow("Tipo", self.type)
        form.addRow("Saldo inicial", self.opening)
        form.addRow("Color", self.color)
        root.addLayout(form)

        self.card_box = QFrame(); self.card_box.setObjectName("SoftCard")
        cb = QVBoxLayout(self.card_box); cb.setContentsMargins(14, 12, 14, 12); cb.setSpacing(9)
        card_title = QLabel("Tarjeta de crédito"); card_title.setObjectName("SectionTitle"); cb.addWidget(card_title)
        card_hint = QLabel("Con cierre y vencimiento App Gastos puede separar consumos en curso del último resumen.")
        card_hint.setObjectName("SmallMuted"); card_hint.setWordWrap(True); cb.addWidget(card_hint)
        card_form = QFormLayout(); card_form.setSpacing(9)
        self.credit_limit = MoneyEdit("$")
        self.credit_limit.setMinimumHeight(42)
        self.closing_day = QSpinBox(); self.closing_day.setRange(1, 31); self.closing_day.setValue(28)
        self.due_day = QSpinBox(); self.due_day.setRange(1, 31); self.due_day.setValue(10)
        card_form.addRow("Límite", self.credit_limit)
        card_form.addRow("Día de cierre", self.closing_day)
        card_form.addRow("Día de vencimiento", self.due_day)
        cb.addLayout(card_form)
        root.addWidget(self.card_box)

        balance_card = QFrame(); balance_card.setObjectName("SoftCard")
        bl = QVBoxLayout(balance_card); bl.setContentsMargins(14, 12, 14, 12); bl.setSpacing(4)
        self.include = QCheckBox("Incluir esta cuenta en el saldo disponible")
        self.include.setChecked(bool(account.get("include_in_balance", 1)) if account else True)
        detail = QLabel(
            "Si la desactivás, la cuenta sigue guardando su saldo y sus movimientos, "
            "pero no se suma al número principal del Dashboard. En tarjetas suele ser útil dejarla separada."
        )
        detail.setObjectName("SmallMuted"); detail.setWordWrap(True)
        bl.addWidget(self.include); bl.addWidget(detail)
        root.addWidget(balance_card)

        row = QHBoxLayout(); row.addStretch()
        cancel = QPushButton("Cancelar"); cancel.setObjectName("SecondaryButton"); cancel.clicked.connect(self.reject)
        save = QPushButton("Guardar cuenta"); save.clicked.connect(self._validate)
        row.addWidget(cancel); row.addWidget(save); root.addLayout(row)

        self.type.currentTextChanged.connect(self._update_card_fields)
        if account:
            self.name.setText(account["name"])
            self.opening.setValue(float(account["opening_balance"]))
            i = self.type.findText(account["type"])
            self.type.setCurrentIndex(i if i >= 0 else 0)
            self.credit_limit.setValue(float(account.get("credit_limit") or 0))
            self.closing_day.setValue(int(account.get("closing_day") or 28))
            self.due_day.setValue(int(account.get("due_day") or 10))
        self._update_card_fields()

    def _update_card_fields(self):
        self.card_box.setVisible(self.type.currentText() == "Tarjeta")

    def _validate(self):
        if not self.name.text().strip():
            QMessageBox.warning(self, "Cuenta", "Ingresá un nombre.")
            return
        if self.type.currentText() == "Tarjeta" and self.credit_limit.value() < 0:
            QMessageBox.warning(self, "Tarjeta", "El límite no puede ser negativo.")
            return
        self.accept()

    def data(self):
        is_card = self.type.currentText() == "Tarjeta"
        return (
            self.name.text().strip(),
            self.type.currentText(),
            float(self.opening.value()),
            self.color.color,
            bool(self.include.isChecked()),
            float(self.credit_limit.value()) if is_card else 0.0,
            int(self.closing_day.value()) if is_card else None,
            int(self.due_day.value()) if is_card else None,
        )


class CardPaymentDialog(QDialog):
    def __init__(self, db, card_account, parent=None):
        super().__init__(parent)
        self.db = db; self.card = card_account
        self.setWindowTitle("Pagar tarjeta")
        self.setMinimumWidth(430)
        root = QVBoxLayout(self); root.setContentsMargins(22,20,22,20); root.setSpacing(13)
        title = QLabel(f"Pagar {card_account['name']}"); title.setObjectName("PageTitle"); root.addWidget(title)
        overview = db.card_overview(int(card_account["id"]))
        debt = float(overview.get("debt") or 0)
        hint = QLabel(
            "Podés pagar desde una cuenta registrada o simplemente marcar la tarjeta como ya pagada. "
            "La segunda opción no toca Efectivo/Mercado Pago ni se contabiliza como ingreso."
        )
        hint.setObjectName("PageSubtitle"); hint.setWordWrap(True); root.addWidget(hint)
        form = QFormLayout(); form.setSpacing(10)
        self.mode = QComboBox()
        self.mode.addItem("Desde una cuenta de App Gastos", "account")
        self.mode.addItem("Ya fue pagada · no modificar otras cuentas", "external")
        self.source = QComboBox()
        for a in db.accounts():
            if int(a["id"]) != int(card_account["id"]): self.source.addItem(a["name"], a["id"])
        self.amount = MoneyEdit(db.currency_symbol()); self.amount.setValue(debt)
        self.date = WorkDateEdit(QDate.currentDate()); self.date.setCalendarPopup(True); self.date.setDisplayFormat("dd/MM/yyyy")
        form.addRow("Cómo registrarlo", self.mode); form.addRow("Pagar desde", self.source); form.addRow("Importe", self.amount); form.addRow("Fecha", self.date); root.addLayout(form)

        # Atajos útiles: normalmente se paga el último resumen, no toda la deuda
        # (que puede incluir consumos del ciclo actual).
        quick = QHBoxLayout(); quick.setSpacing(7)
        last_statement = float(overview.get("last_statement") or 0)
        if last_statement > 0:
            last_btn = QPushButton(f"Último cierre · {money(last_statement, db.currency_symbol(), db.balances_hidden())}")
            last_btn.setObjectName("SecondaryButton")
            last_btn.clicked.connect(lambda: self.amount.setValue(last_statement))
            quick.addWidget(last_btn)
        if debt > 0:
            debt_btn = QPushButton(f"Deuda total · {money(debt, db.currency_symbol(), db.balances_hidden())}")
            debt_btn.setObjectName("SecondaryButton")
            debt_btn.clicked.connect(lambda: self.amount.setValue(debt))
            quick.addWidget(debt_btn)
        if quick.count():
            root.addLayout(quick)

        self.external_note = QLabel(
            "Ajuste de saldo: reduce la deuda de la tarjeta sin crear un ingreso y sin descontar ninguna de tus cuentas."
        )
        self.external_note.setObjectName("SmallMuted"); self.external_note.setWordWrap(True); self.external_note.setVisible(False)
        root.addWidget(self.external_note)
        self.mode.currentIndexChanged.connect(self._mode_changed)
        row=QHBoxLayout(); row.addStretch(); cancel=QPushButton("Cancelar"); cancel.setObjectName("SecondaryButton"); cancel.clicked.connect(self.reject)
        save=QPushButton("Registrar pago"); save.clicked.connect(self._validate); row.addWidget(cancel); row.addWidget(save); root.addLayout(row)
    def _validate(self):
        if self.mode.currentData() == "account" and self.source.currentData() is None:
            QMessageBox.warning(self,"Pago","Necesitás otra cuenta desde donde pagar."); return
        if self.amount.value() <= 0: QMessageBox.warning(self,"Pago","Ingresá un importe mayor a cero."); return
        from datetime import date
        payment_date = date.fromisoformat(self.date.date().toString("yyyy-MM-dd"))
        debt = max(0.0, -self.db.account_balance(int(self.card['id']), payment_date))
        if float(self.amount.value()) > debt + 0.005:
            excess = money(float(self.amount.value()) - debt, self.db.currency_symbol(), self.db.balances_hidden())
            if QMessageBox.question(self, "Pago mayor que la deuda", f"El importe supera la deuda registrada para esa fecha en {excess}. Ese excedente compensará compras futuras. Si solo querés dejar la tarjeta en cero, cancelá y usá el importe de la deuda. ¿Registrar igualmente?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
                return
        self.accept()
    def _mode_changed(self):
        external = self.mode.currentData() == "external"
        self.source.setEnabled(not external)
        self.external_note.setVisible(external)
    def data(self):
        if self.mode.currentData() == "external":
            return {
                "payment_mode": "external",
                "amount": float(self.amount.value()),
                "card_account_id": int(self.card["id"]),
                "tx_date": self.date.date().toString("yyyy-MM-dd"),
                "description": f"Pago externo {self.card['name']}",
            }
        return {"payment_mode":"account","kind":"transfer","amount":float(self.amount.value()),"account_id":int(self.source.currentData()),"to_account_id":int(self.card["id"]),
                "category_id":None,"tx_date":self.date.date().toString("yyyy-MM-dd"),"description":f"Pago {self.card['name']}","note":"","tags":"tarjeta"}


class StatementCategoryGroup(QFrame):
    """Grupo desplegable del resumen de tarjeta.

    Primero muestra la subcategoría y su total; sólo al desplegar se ven los
    consumos individuales. Es mucho más legible para resúmenes largos.
    """
    def __init__(self, db, name, rows, formatted_total, color="#4CCFA9", icon="other", parent=None):
        super().__init__(parent)
        self.db = db; self.tx_rows = list(rows); self.expanded = False
        self.setObjectName("StatementCategoryGroup")
        root = QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)

        header = QFrame(); header.setObjectName("StatementCategoryHeader")
        hl = QHBoxLayout(header); hl.setContentsMargins(10,9,12,9); hl.setSpacing(8)
        self.arrow = QPushButton("›"); self.arrow.setObjectName("DisclosureButton"); self.arrow.setFixedSize(28,28)
        self.arrow.clicked.connect(self.toggle)
        hl.addWidget(self.arrow)
        hl.addWidget(IconBadge(icon or "other", color or "#4CCFA9", 34))
        self.name_btn = QPushButton(name); self.name_btn.setObjectName("StatementCategoryName")
        self.name_btn.setCursor(Qt.CursorShape.PointingHandCursor); self.name_btn.clicked.connect(self.toggle)
        hl.addWidget(self.name_btn,1)
        count = QLabel(f"{len(self.tx_rows)} mov."); count.setObjectName("SmallMuted"); hl.addWidget(count)
        amount = QLabel(formatted_total); amount.setObjectName("TransactionAmountNegative"); hl.addWidget(amount)
        root.addWidget(header)

        self.body = QWidget(); bl = QVBoxLayout(self.body); bl.setContentsMargins(38,4,4,8); bl.setSpacing(6)
        for tx in self.tx_rows:
            text = money(-float(tx["amount"]), db.currency_symbol(), db.balances_hidden())
            bl.addWidget(TransactionRowWidget(tx, text, compact=True))
        self.body.setVisible(False); root.addWidget(self.body)

    def toggle(self):
        self.expanded = not self.expanded
        self.body.setVisible(self.expanded)
        self.arrow.setText("⌄" if self.expanded else "›")


class CardStatementDialog(QDialog):
    def __init__(self, db, card_account, parent=None):
        super().__init__(parent)
        self.db=db; self.card=card_account; self.setWindowTitle(f"Resumen · {card_account['name']}")
        self.resize(760,650); self.setMinimumSize(560,480)
        root=QVBoxLayout(self); root.setContentsMargins(22,20,22,20); root.setSpacing(13)
        top=QHBoxLayout(); titlebox=QVBoxLayout(); title=QLabel(card_account["name"]); title.setObjectName("PageTitle")
        sub=QLabel("Resumen de tarjeta · compras, cierre, vencimiento y cuotas"); sub.setObjectName("PageSubtitle")
        titlebox.addWidget(title); titlebox.addWidget(sub); top.addLayout(titlebox); top.addStretch(); close=QPushButton("← Volver"); close.setObjectName("SecondaryButton"); close.clicked.connect(self.accept); top.addWidget(close); root.addLayout(top)
        self.overview=db.card_overview(int(card_account["id"]))
        cards=QHBoxLayout(); cards.setSpacing(10)
        symbol=db.currency_symbol(); hidden=db.balances_hidden(); fmt=lambda v: money(v,symbol,hidden)
        debt=StatCard("Deuda actual"); debt.set_value(fmt(self.overview.get("debt",0)), "Pagos ya descontados")
        current=StatCard("Consumos en curso"); current.set_value(fmt(self.overview.get("current_spent",0)), f"Cierra {self._date(self.overview.get('next_close'))}")
        last=StatCard("Último cierre"); last.set_value(fmt(self.overview.get("last_statement",0)), (f"Vence {self._date(self.overview.get('last_due'))}" if self.overview.get("last_due") else "Mes anterior"))
        cards.addWidget(debt,1); cards.addWidget(current,1); cards.addWidget(last,1); root.addLayout(cards)
        if not self.overview.get("configured"):
            warning=QLabel("Esta tarjeta viene de una versión anterior y todavía no tiene cierre/vencimiento configurados. Hasta que los edites, los períodos se muestran por mes calendario.")
            warning.setObjectName("SmallMuted"); warning.setWordWrap(True); root.addWidget(warning)
        if float(self.overview.get("credit_limit") or 0)>0:
            limit=QLabel(f"Límite {fmt(self.overview['credit_limit'])}  ·  disponible estimado {fmt(self.overview['available_credit'])}")
            limit.setObjectName("Muted"); root.addWidget(limit)
        seg=QHBoxLayout(); self.current_btn=QPushButton("En curso"); self.current_btn.setObjectName("SegmentButton"); self.current_btn.setCheckable(True)
        self.last_btn=QPushButton("Último cierre"); self.last_btn.setObjectName("SegmentButton"); self.last_btn.setCheckable(True)
        self.current_btn.clicked.connect(lambda: self._load("current")); self.last_btn.clicked.connect(lambda: self._load("last")); seg.addWidget(self.current_btn); seg.addWidget(self.last_btn); seg.addStretch(); root.addLayout(seg)
        self.scroll=QScrollArea(); self.scroll.setWidgetResizable(True); self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.host=QWidget(); self.rows=QVBoxLayout(self.host); self.rows.setContentsMargins(0,0,8,0); self.rows.setSpacing(8); self.scroll.setWidget(self.host); root.addWidget(self.scroll,1)
        self._load("current")
    @staticmethod
    def _date(iso):
        if not iso: return "—"
        try:
            y,m,d=map(int,str(iso)[:10].split("-")); return f"{d:02d}/{m:02d}/{y}"
        except Exception: return str(iso)
    def _clear(self):
        while self.rows.count():
            item=self.rows.takeAt(0); w=item.widget()
            if w: w.deleteLater()
    def _load(self, mode):
        self.current_btn.setChecked(mode=="current"); self.last_btn.setChecked(mode=="last")
        self._clear()
        if mode=="current": start=self.overview.get("current_start"); end=QDate.currentDate().toString("yyyy-MM-dd")
        else: start=self.overview.get("last_statement_start"); end=self.overview.get("last_close")
        rows=self.db.card_statement_transactions(int(self.card["id"]),start,end)
        if not rows:
            empty=QFrame(); empty.setObjectName("SoftCard"); el=QVBoxLayout(empty); msg=QLabel("No hay consumos en este período."); msg.setObjectName("Muted"); el.addWidget(msg); self.rows.addWidget(empty)
        else:
            groups = defaultdict(list)
            for tx in rows:
                leaf = tx.get("category_name") or tx.get("parent_category_name") or "Sin categoría"
                parent = tx.get("parent_category_name") or ""
                groups[(parent, leaf)].append(tx)
            ordered = sorted(groups.items(), key=lambda item: sum(float(x.get("amount") or 0) for x in item[1]), reverse=True)
            for (_, name), txs in ordered:
                total = sum(float(x.get("amount") or 0) for x in txs)
                sample = txs[0]
                group = StatementCategoryGroup(
                    self.db,
                    name,
                    txs,
                    money(-total, self.db.currency_symbol(), self.db.balances_hidden()),
                    sample.get("category_effective_color") or "#4CCFA9",
                    sample.get("category_effective_icon") or "other",
                )
                self.rows.addWidget(group)
        self.rows.addStretch()
