from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QBoxLayout, QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QMenu, QMessageBox,
    QPushButton, QScrollArea, QVBoxLayout, QWidget
)

from ..constants import MONTHS
from ..dialogs import ExistingInstallmentDialog, LegacyMonthlyEntryDialog, TransactionDialog
from ..utils import money
from ..widgets import IconBadge, TransactionRowWidget
from ..layouts import responsive_mode
from .common import clear_layout, page_header


WEEKDAYS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


class DayGroup(QFrame):
    def __init__(self, iso_date, transactions, fmt, parent=None):
        super().__init__(parent)
        self.setObjectName("DayGroup")
        root = QVBoxLayout(self); root.setContentsMargins(0, 0, 0, 5); root.setSpacing(0)

        d = date.fromisoformat(iso_date)
        today = date.today()
        if d == today:
            label = "Hoy"
        elif d == today - timedelta(days=1):
            label = "Ayer"
        else:
            label = f"{WEEKDAYS[d.weekday()].capitalize()} {d.day} de {MONTHS[d.month-1].lower()}"

        income = sum(float(x["amount"]) for x in transactions if x["kind"] == "income")
        expense = sum(float(x["amount"]) for x in transactions if x["kind"] == "expense")

        head = QWidget(); hl = QHBoxLayout(head); hl.setContentsMargins(14, 10, 14, 8)
        title = QLabel(label); title.setObjectName("DayTitle")
        date_label = QLabel(d.strftime("%d/%m/%Y")); date_label.setObjectName("SmallMuted")
        left = QVBoxLayout(); left.setSpacing(0); left.addWidget(title); left.addWidget(date_label)
        hl.addLayout(left); hl.addStretch()
        if income:
            inc = QLabel(f"+ {fmt(income)}"); inc.setObjectName("Positive"); hl.addWidget(inc)
        if expense:
            exp = QLabel(f"− {fmt(expense)}"); exp.setObjectName("Negative"); hl.addWidget(exp)
        root.addWidget(head)

        divider = QFrame(); divider.setObjectName("CategoryDivider"); divider.setFixedHeight(1); root.addWidget(divider)


class LegacyMonthlyRowWidget(QFrame):
    edit_requested = Signal(int)
    delete_requested = Signal(int)

    def __init__(self, row, formatted_amount, parent=None):
        super().__init__(parent)
        self.row = row; self.entry_id = int(row["id"])
        self.setObjectName("TransactionRow")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Dato mensual importado del Excel · doble clic para editar")
        root = QHBoxLayout(self); root.setContentsMargins(12,10,12,10); root.setSpacing(11)
        root.addWidget(IconBadge(
            row.get("category_effective_icon", "other"),
            row.get("category_effective_color", "#4CCFA9"),
            40,
            secondary_color=row.get("category_secondary_color"),
        ))
        info = QVBoxLayout(); info.setSpacing(2)
        title = QLabel(row.get("category_display") or "Movimiento importado"); title.setObjectName("TransactionTitle")
        info.addWidget(title)
        meta = QLabel(f"Total mensual importado · {MONTHS[int(row['month'])-1]} {row['year']} · sin fecha exacta ni cuenta")
        meta.setObjectName("SmallMuted"); info.addWidget(meta); root.addLayout(info,1)
        amount = QLabel(formatted_amount)
        amount.setObjectName("TransactionAmountPositive" if row["kind"]=="income" else "TransactionAmountNegative")
        amount.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter); root.addWidget(amount)

    def mouseDoubleClickEvent(self,event):
        self.edit_requested.emit(self.entry_id); event.accept()

    def contextMenuEvent(self,event):
        menu=QMenu(self); edit=menu.addAction("Editar registro mensual"); menu.addSeparator(); delete=menu.addAction("Eliminar del historial")
        chosen=menu.exec(event.globalPos())
        if chosen==edit: self.edit_requested.emit(self.entry_id)
        elif chosen==delete: self.delete_requested.emit(self.entry_id)


class LegacyMonthGroup(QFrame):
    def __init__(self, year, month, rows, fmt, parent=None):
        super().__init__(parent); self.setObjectName("DayGroup")
        root=QVBoxLayout(self); root.setContentsMargins(0,0,0,5); root.setSpacing(0)
        income=sum(float(x["amount"]) for x in rows if x["kind"]=="income")
        expense=sum(float(x["amount"]) for x in rows if x["kind"]=="expense")
        head=QWidget(); hl=QHBoxLayout(head); hl.setContentsMargins(14,10,14,8)
        left=QVBoxLayout(); left.setSpacing(0)
        title=QLabel(f"Importado del Excel · {MONTHS[int(month)-1]} {year}"); title.setObjectName("DayTitle")
        sub=QLabel("Cada fila es un total mensual real de tu Excel; el archivo no tenía día ni cuenta."); sub.setObjectName("SmallMuted")
        left.addWidget(title); left.addWidget(sub); hl.addLayout(left); hl.addStretch()
        if income:
            inc=QLabel(f"+ {fmt(income)}"); inc.setObjectName("Positive"); hl.addWidget(inc)
        if expense:
            exp=QLabel(f"− {fmt(expense)}"); exp.setObjectName("Negative"); hl.addWidget(exp)
        root.addWidget(head)
        divider=QFrame(); divider.setObjectName("CategoryDivider"); divider.setFixedHeight(1); root.addWidget(divider)


class TransactionsPage(QWidget):
    data_changed = Signal()
    back_requested = Signal()

    def __init__(self, db):
        super().__init__()
        self.db = db
        now = date.today()
        self.range_start = None
        self.range_end = None
        self._compact = False

        root = QVBoxLayout(self); root.setContentsMargins(28, 24, 28, 28); root.setSpacing(14)
        self.top_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight); self.top_layout.setSpacing(8)
        self.top_layout.addWidget(page_header("Movimientos", "Doble clic para editar · clic derecho para duplicar o eliminar"), 1)
        add = QPushButton("+ Nuevo movimiento"); add.clicked.connect(self.add_transaction); self.top_layout.addWidget(add); root.addLayout(self.top_layout)

        self.back_bar = QFrame(); self.back_bar.setObjectName("AnalysisBackBar")
        back_l = QHBoxLayout(self.back_bar); back_l.setContentsMargins(10,8,10,8); back_l.setSpacing(9)
        back_btn = QPushButton("← Volver a Análisis"); back_btn.setObjectName("SecondaryButton"); back_btn.clicked.connect(self._go_back)
        self.back_context = QLabel("Filtro abierto desde Análisis"); self.back_context.setObjectName("SmallMuted")
        back_l.addWidget(back_btn); back_l.addWidget(self.back_context); back_l.addStretch()
        self.back_bar.setVisible(False); root.addWidget(self.back_bar)

        filters_card = QFrame(); filters_card.setObjectName("FilterBar")
        self.filters_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight, filters_card); self.filters_layout.setContentsMargins(10, 9, 10, 9); self.filters_layout.setSpacing(8); filters = self.filters_layout
        self.search = QLineEdit(); self.search.setPlaceholderText("Buscar movimiento…"); self.search.setClearButtonEnabled(True); filters.addWidget(self.search, 2)
        self.kind = QComboBox(); self.kind.addItem("Todos", "all"); self.kind.addItem("Gastos", "expense"); self.kind.addItem("Ingresos", "income"); self.kind.addItem("Transferencias", "transfer"); filters.addWidget(self.kind)
        self.account = QComboBox(); filters.addWidget(self.account)
        self.category = QComboBox(); filters.addWidget(self.category)
        self.month = QComboBox(); self.month.addItem("Todos los meses", 0)
        for i, name in enumerate(MONTHS, 1): self.month.addItem(name, i)
        self.month.setCurrentIndex(now.month); filters.addWidget(self.month)
        self.year = QComboBox(); self.year.addItem("Todos los años", 0)
        for y in range(now.year + 1, now.year - 6, -1): self.year.addItem(str(y), y)
        yi = self.year.findData(now.year); self.year.setCurrentIndex(yi if yi >= 0 else 0); filters.addWidget(self.year)
        self.range_chip = QPushButton("")
        self.range_chip.setObjectName("CategoryChip")
        self.range_chip.setVisible(False)
        self.range_chip.setToolTip("Quitar filtro de período")
        self.range_chip.clicked.connect(self.clear_date_range)
        filters.addWidget(self.range_chip)
        root.addWidget(filters_card)

        summary_card = QFrame(); summary_card.setObjectName("MovementSummary")
        sum_l = QHBoxLayout(summary_card); sum_l.setContentsMargins(14, 9, 14, 9)
        self.summary = QLabel(); self.summary.setObjectName("Muted"); sum_l.addWidget(self.summary); sum_l.addStretch()
        root.addWidget(summary_card)

        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True); self.scroll.setFrameShape(QFrame.Shape.NoFrame); self.scroll.setObjectName("MovementScroll")
        self.host = QWidget(); self.list_layout = QVBoxLayout(self.host); self.list_layout.setContentsMargins(0, 0, 8, 0); self.list_layout.setSpacing(10)
        self.scroll.setWidget(self.host); root.addWidget(self.scroll, 1)

        self._search_timer = QTimer(self); self._search_timer.setSingleShot(True); self._search_timer.setInterval(140)
        self._search_timer.timeout.connect(self.refresh)
        self.search.textChanged.connect(lambda: self._search_timer.start())
        for widget in (self.kind, self.account, self.category):
            widget.currentIndexChanged.connect(self.refresh)
        self.month.currentIndexChanged.connect(self._manual_period_changed)
        self.year.currentIndexChanged.connect(self._manual_period_changed)

        self._load_filters(); self.refresh(); self._apply_responsive()

    def _apply_responsive(self):
        compact = responsive_mode(self.width(), self.height()) != "wide"
        if compact == self._compact:
            return
        self._compact = compact
        self.top_layout.setDirection(QBoxLayout.Direction.TopToBottom if compact else QBoxLayout.Direction.LeftToRight)
        self.filters_layout.setDirection(QBoxLayout.Direction.TopToBottom if compact else QBoxLayout.Direction.LeftToRight)
        margins = 14 if compact else 28
        self.layout().setContentsMargins(margins, 18 if compact else 24, margins, 20 if compact else 28)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_responsive()

    def _manual_period_changed(self):
        if self.range_start or self.range_end:
            self.range_start = None
            self.range_end = None
            self.range_chip.setVisible(False)
        self.refresh()

    def _fmt(self, value):
        return money(value, self.db.currency_symbol(), self.db.balances_hidden())

    def _load_filters(self):
        aid = self.account.currentData() if self.account.count() else None
        cid = self.category.currentData() if self.category.count() else None
        self.account.blockSignals(True); self.account.clear(); self.account.addItem("Todas las cuentas", None)
        for account in self.db.accounts(): self.account.addItem(account["name"], account["id"])
        i=self.account.findData(aid); self.account.setCurrentIndex(i if i>=0 else 0); self.account.blockSignals(False)
        self.category.blockSignals(True); self.category.clear(); self.category.addItem("Todas las categorías", None)
        for category in self.db.category_choices("expense", True): self.category.addItem(category["label"], category["id"])
        for category in self.db.category_choices("income", True): self.category.addItem(category["label"], category["id"])
        i=self.category.findData(cid); self.category.setCurrentIndex(i if i>=0 else 0); self.category.blockSignals(False)

    def _filters(self):
        return {
            "year": self.year.currentData() or None,
            "month": self.month.currentData() or None,
            "kind": self.kind.currentData(),
            "account_id": self.account.currentData(),
            "category_id": self.category.currentData(),
            "search": self.search.text(),
            "date_from": self.range_start,
            "date_to": self.range_end,
        }

    def refresh(self):
        filters = self._filters()
        rows = self.db.transactions(**filters)
        history_filters = {
            "year": filters.get("year"), "month": filters.get("month"), "kind": filters.get("kind"),
            "category_id": filters.get("category_id"), "search": filters.get("search", ""),
        }
        # El Excel no tenía cuentas ni fechas exactas. Cuando venimos desde un
        # rango de Día/Semana/Período, mostramos solo movimientos con fecha real.
        history_rows = [] if (filters.get("account_id") or self.range_start or self.range_end) else self.db.historical_entries(**history_filters)
        clear_layout(self.list_layout)

        if not rows and not history_rows:
            empty = QFrame(); empty.setObjectName("SoftCard"); box=QVBoxLayout(empty); box.setContentsMargins(22,28,22,28)
            title=QLabel("No hay movimientos con estos filtros"); title.setObjectName("SectionTitle")
            subtitle=QLabel("Probá cambiar el período o cargá un movimiento nuevo."); subtitle.setObjectName("Muted")
            box.addWidget(title); box.addWidget(subtitle); self.list_layout.addWidget(empty)
        else:
            # Primero mostramos el historial mensual del Excel. Así, al entrar por ejemplo
            # a Agosto, las categorías que ya tenías cargadas no parecen desaparecer.
            if history_rows:
                hgroups = defaultdict(list)
                for row in history_rows: hgroups[(int(row["year"]), int(row["month"]))].append(row)
                for (hy,hm) in sorted(hgroups.keys(), reverse=True):
                    month_rows=hgroups[(hy,hm)]
                    group=LegacyMonthGroup(hy,hm,month_rows,self._fmt)
                    gl=group.layout()
                    for row in month_rows:
                        amount=float(row["amount"]); shown=amount if row["kind"]=="income" else -amount
                        w=LegacyMonthlyRowWidget(row,self._fmt(shown))
                        w.edit_requested.connect(self.edit_historical_entry); w.delete_requested.connect(self.delete_historical_entry)
                        gl.addWidget(w)
                    self.list_layout.addWidget(group)

            if rows:
                groups = defaultdict(list)
                for tx in rows: groups[tx["tx_date"]].append(tx)
                for iso_date, day_rows in groups.items():
                    group = DayGroup(iso_date, day_rows, self._fmt)
                    group_layout = group.layout()
                    for tx in day_rows:
                        amount=float(tx["amount"]); shown=amount if tx["kind"]=="income" else -amount if tx["kind"]=="expense" else amount
                        row=TransactionRowWidget(tx,self._fmt(shown)); row.setObjectName("TransactionRowFlat")
                        row.edit_requested.connect(self.edit_transaction); row.installments_requested.connect(self.configure_installments); row.duplicate_requested.connect(self.duplicate_transaction); row.delete_requested.connect(self.delete_transaction)
                        group_layout.addWidget(row)
                    self.list_layout.addWidget(group)
        self.list_layout.addStretch()

        real_totals=self.db.filtered_totals(**filters)
        hist_totals={"income":0.0,"expense":0.0,"net":0.0,"count":0}
        if history_rows:
            hist_totals = {
                "income": sum(float(x["amount"]) for x in history_rows if x["kind"]=="income"),
                "expense": sum(float(x["amount"]) for x in history_rows if x["kind"]=="expense"),
                "count": len(history_rows),
            }
            hist_totals["net"] = hist_totals["income"] - hist_totals["expense"]
        income=real_totals["income"]+hist_totals["income"]; expense=real_totals["expense"]+hist_totals["expense"]
        net=income-expense
        pieces=[]
        if real_totals["count"]: pieces.append(f"{real_totals['count']} movimientos")
        if hist_totals["count"]: pieces.append(f"{hist_totals['count']} registros mensuales del Excel")
        prefix=" + ".join(pieces) if pieces else "0 movimientos"
        text=f"{prefix}   ·   Ingresos {self._fmt(income)}   ·   Gastos {self._fmt(expense)}   ·   Neto {self._fmt(net)}"
        if history_rows:
            text += "   ·   El historial importado no tiene cuenta ni día exactos"
        self.summary.setText(text)

    def clear_date_range(self):
        self.range_start = None
        self.range_end = None
        self.range_chip.setVisible(False)
        self.refresh()

    def apply_analysis_filter(self, payload):
        """Abre Movimientos con el mismo contexto elegido en Análisis."""
        payload = payload or {}
        self.back_bar.setVisible(True)
        self.search.clear()
        self.account.setCurrentIndex(0)

        kind = payload.get("kind") or "all"
        idx = self.kind.findData(kind)
        if idx >= 0:
            self.kind.setCurrentIndex(idx)

        category_id = payload.get("category_id")
        idx = self.category.findData(category_id)
        if idx >= 0:
            self.category.setCurrentIndex(idx)

        mode = payload.get("mode")
        start = payload.get("start")
        end = payload.get("end")
        self.range_start = self.range_end = None

        try:
            start_d = date.fromisoformat(str(start)[:10])
            end_d = date.fromisoformat(str(end)[:10])
        except Exception:
            start_d = end_d = None

        if mode == "month" and start_d:
            yi = self.year.findData(start_d.year)
            if yi >= 0: self.year.setCurrentIndex(yi)
            mi = self.month.findData(start_d.month)
            if mi >= 0: self.month.setCurrentIndex(mi)
        elif mode == "year" and start_d:
            yi = self.year.findData(start_d.year)
            if yi >= 0: self.year.setCurrentIndex(yi)
            self.month.setCurrentIndex(0)
        elif start_d and end_d:
            self.year.setCurrentIndex(0)
            self.month.setCurrentIndex(0)
            self.range_start = start_d.isoformat()
            self.range_end = end_d.isoformat()
            self.range_chip.setText(f"{start_d:%d/%m/%Y} – {end_d:%d/%m/%Y}  ×")
            self.range_chip.setVisible(True)
        else:
            self.year.setCurrentIndex(0)
            self.month.setCurrentIndex(0)

        self.refresh()

    def _go_back(self):
        self.back_bar.setVisible(False)
        self.back_requested.emit()

    def edit_historical_entry(self, entry_id=None):
        if not entry_id: return
        entry=self.db.historical_entry(int(entry_id))
        if not entry: return
        dlg=LegacyMonthlyEntryDialog(self.db,entry,self)
        if dlg.exec():
            data=dlg.data(); self.db.update_historical_entry(int(entry_id),data["amount"],data["category_id"])
            self._load_filters(); self.refresh(); self.data_changed.emit()

    def delete_historical_entry(self, entry_id=None):
        if not entry_id: return
        if QMessageBox.question(
            self,"Eliminar registro importado",
            "¿Eliminar este total mensual importado del Excel? Esta acción modifica tus estadísticas históricas."
        )==QMessageBox.StandardButton.Yes:
            self.db.delete_historical_entry(int(entry_id)); self.refresh(); self.data_changed.emit()

    def _show_period_for(self, iso_date):
        try:
            y,m,_=map(int,iso_date.split("-"))
            yi=self.year.findData(y)
            if yi>=0: self.year.setCurrentIndex(yi)
            mi=self.month.findData(m)
            if mi>=0: self.month.setCurrentIndex(mi)
        except Exception:
            pass

    def add_transaction(self):
        dlg=TransactionDialog(self.db,parent=self)
        if dlg.exec():
            data=dlg.data(); self.db.add_transaction(data)
            self._load_filters(); self._show_period_for(data["tx_date"]); self.refresh(); self.data_changed.emit()

    def edit_transaction(self,txid=None):
        if not txid:return
        dlg=TransactionDialog(self.db,self.db.transaction(int(txid)),self)
        if dlg.exec():
            data=dlg.data(); self.db.update_transaction(int(txid),data); self._show_period_for(data["tx_date"]); self.refresh(); self.data_changed.emit()

    def configure_installments(self, txid=None):
        if not txid:
            return
        tx = self.db.transaction(int(txid))
        if not tx or tx.get("kind") != "expense":
            return
        if tx.get("installment_plan_id"):
            anchor = self.db.installment_anchor_transaction(int(tx["installment_plan_id"]))
            if anchor:
                tx = anchor
                txid = int(anchor["id"])
        if not any(a.get("type") == "Tarjeta" for a in self.db.accounts()):
            QMessageBox.information(self, "Cuotas", "Primero necesitás crear una cuenta de tipo Tarjeta en Cuentas.")
            return
        dlg = ExistingInstallmentDialog(self.db, tx, self)
        if dlg.exec():
            try:
                data = dlg.data()
                self.db.configure_existing_installment(
                    int(txid), data["current_installment"], data["total_installments"],
                    data["card_account_id"], data.get("current_date")
                )
                # Si el gasto configurado es histórico y ya venció la siguiente cuota,
                # la generamos inmediatamente para no esperar a reiniciar la app.
                self.db.process_due_installments()
            except Exception as exc:
                QMessageBox.warning(self, "Cuotas", str(exc))
                return
            self._load_filters(); self.refresh(); self.data_changed.emit()

    def duplicate_transaction(self,txid=None):
        if not txid:return
        new_id=self.db.duplicate_transaction(int(txid)); self._show_period_for(date.today().isoformat()); self.refresh(); self.data_changed.emit()

    def delete_transaction(self,txid=None):
        if not txid:return
        if QMessageBox.question(self,"Eliminar movimiento","¿Eliminar este movimiento definitivamente?")==QMessageBox.StandardButton.Yes:
            self.db.delete_transaction(int(txid)); self.refresh(); self.data_changed.emit()
