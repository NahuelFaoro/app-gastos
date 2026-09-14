from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QBoxLayout, QFrame, QGridLayout, QLabel, QMessageBox, QPushButton,
    QScrollArea, QVBoxLayout, QWidget
)

from ..dialogs import AccountDialog, CardPaymentDialog, CardStatementDialog
from ..layouts import responsive_mode
from ..utils import money
from ..widgets import AccountCard, StatCard
from .common import clear_layout, page_header


class AccountsPage(QWidget):
    data_changed = Signal()

    def __init__(self, db):
        super().__init__()
        self.db = db
        self._cards = []
        self._last_columns = 0
        self._compact = False
        self._responsive_mode = None

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 28)
        root.setSpacing(16)

        self.top_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        top = self.top_layout
        top.addWidget(page_header(
            "Cuentas",
            "Separá el dinero disponible de ahorros o cuentas que no querés sumar al Dashboard",
        ))
        top.addStretch()
        add = QPushButton("+ Nueva cuenta")
        add.clicked.connect(self.add_account)
        top.addWidget(add)
        root.addLayout(top)

        summary = QFrame(); summary.setObjectName("MetricsStrip")
        self.summary_layout = QGridLayout(summary)
        self.summary_layout.setContentsMargins(22, 8, 22, 8)
        self.summary_layout.setHorizontalSpacing(24)
        self.summary_layout.setVerticalSpacing(10)
        self.available = StatCard("Saldo disponible")
        self.separated = StatCard("Cuentas separadas")
        self.net_worth = StatCard("Patrimonio total")
        self.count = StatCard("Cuentas activas")
        self._summary_cards = (self.available, self.separated, self.net_worth, self.count)
        for card in self._summary_cards:
            card.setMinimumWidth(0)
            card.setMaximumWidth(16777215)
        self._reflow_summary("wide")
        root.addWidget(summary)

        hint = QLabel("Doble clic para editar · clic derecho para acciones")
        hint.setObjectName("SmallMuted"); root.addWidget(hint)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setObjectName("AccountScroll")
        self.host = QWidget()
        self.grid = QGridLayout(self.host)
        self.grid.setContentsMargins(0, 0, 8, 8)
        self.grid.setHorizontalSpacing(12)
        self.grid.setVerticalSpacing(12)
        self.grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.host)
        root.addWidget(self.scroll, 1)

        self.refresh()

    def _reflow_summary(self, mode: str | None = None) -> None:
        """Recupera el espaciado amplio del resumen sin perder responsive."""
        mode = mode or responsive_mode(self.width(), self.height())
        columns = 4 if mode == "wide" else 2 if mode == "compact" else 1
        for card in self._summary_cards:
            self.summary_layout.removeWidget(card)
        for col in range(4):
            self.summary_layout.setColumnStretch(col, 0)
        for col in range(columns):
            self.summary_layout.setColumnStretch(col, 1)
        for index, card in enumerate(self._summary_cards):
            self.summary_layout.addWidget(card, index // columns, index % columns)

    def _fmt(self, value):
        return money(value, self.db.currency_symbol(), self.db.balances_hidden())

    def _column_count(self):
        """Cantidad de columnas según el ancho real disponible.

        Así una ventana maximizada aprovecha el espacio en vez de dejar una
        cuarta cuenta sola abajo; al achicar, baja gradualmente a 3/2/1.
        """
        try:
            width = max(1, self.scroll.viewport().width() - 8)
        except Exception:
            width = self.width()
        mode = responsive_mode(width, self.height())
        if mode == "narrow":
            return 1
        if width >= 1500 and mode == "wide":
            return 4
        if width >= 1050 and mode == "wide":
            return 3
        return 2 if width >= 560 else 1

    def _reflow_cards(self):
        if not self._cards:
            return
        columns = self._column_count()
        if columns == self._last_columns and self.grid.count() == len(self._cards):
            return

        # Quitamos los widgets del layout sin destruirlos y los volvemos a ubicar.
        for card in self._cards:
            self.grid.removeWidget(card)
        for col in range(6):
            self.grid.setColumnStretch(col, 0)
        for col in range(columns):
            self.grid.setColumnStretch(col, 1)

        for i, card in enumerate(self._cards):
            self.grid.addWidget(card, i // columns, i % columns)
        self._last_columns = columns

    def resizeEvent(self, event):
        super().resizeEvent(event)
        mode = responsive_mode(self.width(), self.height())
        compact = mode != "wide"
        if mode != self._responsive_mode:
            self._responsive_mode = mode
            self._compact = compact
            direction = QBoxLayout.Direction.TopToBottom if compact else QBoxLayout.Direction.LeftToRight
            self.top_layout.setDirection(direction)
            self._reflow_summary(mode)
            margins = 14 if compact else 28
            self.layout().setContentsMargins(margins, 18 if compact else 24, margins, 20 if compact else 28)
        QTimer.singleShot(0, self._reflow_cards)

    def refresh(self):
        clear_layout(self.grid)
        self._cards = []
        self._last_columns = 0
        rows = self.db.accounts_with_balances()

        for account in rows:
            if account.get("type") == "Tarjeta":
                overview = self.db.card_overview(int(account["id"]))
                account["card_debt_display"] = self._fmt(float(overview.get("debt") or 0))
                account["card_spent_display"] = self._fmt(float(overview.get("current_spent") or 0))
                if float(overview.get("credit_balance") or 0) > 0:
                    account["card_credit_display"] = self._fmt(float(overview["credit_balance"]))
                account["card_configured"] = bool(overview.get("configured"))
                if float(overview.get("credit_limit") or 0) > 0:
                    account["card_available_display"] = self._fmt(float(overview.get("available_credit") or 0))
            card = AccountCard(
                account,
                self._fmt(account["balance"]),
                self._fmt(account["opening_balance"]),
            )
            card.edit_requested.connect(self.edit_account)
            card.toggle_balance_requested.connect(self.toggle_balance_inclusion)
            card.delete_requested.connect(self.delete_account)
            card.statement_requested.connect(self.open_card_statement)
            card.payment_requested.connect(self.pay_card)
            self._cards.append(card)

        if not rows:
            empty = QFrame(); empty.setObjectName("SoftCard")
            box = QVBoxLayout(empty); box.setContentsMargins(22, 28, 22, 28)
            title = QLabel("Todavía no hay cuentas"); title.setObjectName("SectionTitle")
            subtitle = QLabel("Creá efectivo, bancos, billeteras o cuentas separadas de ahorro.")
            subtitle.setObjectName("Muted"); subtitle.setWordWrap(True)
            box.addWidget(title); box.addWidget(subtitle)
            self.grid.addWidget(empty, 0, 0)
        else:
            self._reflow_cards()

        included = [a for a in rows if bool(a.get("include_in_balance", 1))]
        excluded = [a for a in rows if not bool(a.get("include_in_balance", 1))]
        available = sum(float(a["balance"]) for a in included)
        separated = sum(float(a["balance"]) for a in excluded)

        self.available.set_value(
            self._fmt(available),
            f"{len(included)} cuenta{'s' if len(included) != 1 else ''} incluidas",
            "positive" if available >= 0 else "negative",
        )
        self.separated.set_value(
            self._fmt(separated),
            f"{len(excluded)} cuenta{'s' if len(excluded) != 1 else ''} fuera del balance",
        )
        self.net_worth.set_value(self._fmt(self.db.net_worth()), "Activos positivos − deuda real de tarjetas")
        self.count.set_value(str(len(rows)), "Disponibles para registrar movimientos")

    def add_account(self):
        dlg = AccountDialog(parent=self)
        if dlg.exec():
            try:
                self.db.add_account(*dlg.data())
            except Exception as exc:
                QMessageBox.warning(self, "Cuenta", str(exc)); return
            self.refresh(); self.data_changed.emit()

    def edit_account(self, account_id=None):
        if not account_id:
            return
        dlg = AccountDialog(self.db.account(int(account_id)), self)
        if dlg.exec():
            try:
                self.db.update_account(int(account_id), *dlg.data())
            except Exception as exc:
                QMessageBox.warning(self, "Cuenta", str(exc)); return
            self.refresh(); self.data_changed.emit()

    def toggle_balance_inclusion(self, account_id=None, included=True):
        if not account_id:
            return
        self.db.set_account_balance_inclusion(int(account_id), bool(included))
        self.refresh(); self.data_changed.emit()

    def open_card_statement(self, account_id=None):
        if not account_id:
            return
        account = self.db.account(int(account_id))
        if not account or account.get("type") != "Tarjeta":
            return
        CardStatementDialog(self.db, account, self).exec()

    def pay_card(self, account_id=None):
        if not account_id:
            return
        account = self.db.account(int(account_id))
        if not account or account.get("type") != "Tarjeta":
            return
        dlg = CardPaymentDialog(self.db, account, self)
        if dlg.exec():
            try:
                data = dlg.data()
                if data.get("payment_mode") == "external":
                    self.db.add_account_adjustment(
                        int(data["card_account_id"]),
                        float(data["amount"]),
                        data["tx_date"],
                        data.get("description") or f"Pago externo {account['name']}",
                        "card_payment_external",
                    )
                else:
                    data.pop("payment_mode", None)
                    self.db.add_transaction(data)
            except Exception as exc:
                QMessageBox.warning(self, "Pago de tarjeta", str(exc)); return
            self.refresh(); self.data_changed.emit()

    def delete_account(self, account_id=None):
        if not account_id:
            return
        if QMessageBox.question(self, "Eliminar cuenta", "¿Eliminar esta cuenta? Solo se permite si no está en uso.") != QMessageBox.StandardButton.Yes:
            return
        try:
            self.db.delete_account(int(account_id))
        except Exception as exc:
            QMessageBox.warning(self, "No se puede eliminar", str(exc)); return
        self.refresh(); self.data_changed.emit()
