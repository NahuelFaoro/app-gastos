from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QBoxLayout, QButtonGroup, QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QMenu, QMessageBox,
    QProgressBar, QPushButton, QScrollArea, QVBoxLayout, QWidget
)

from ..constants import MONTHS, MONTHS_SHORT
from ..dialogs import ExistingInstallmentDialog
from ..utils import add_months, human_date, money
from ..widgets import IconBadge, StatCard
from ..layouts import responsive_mode
from .common import clear_layout, page_header


class InstallmentTimelineRow(QFrame):
    def __init__(self, number, total, expected_date, amount, state, tx=None, current=False, parent=None):
        super().__init__(parent)
        self.setObjectName("InstallmentTimelineCurrent" if current else "InstallmentTimelineRow")
        root = QHBoxLayout(self); root.setContentsMargins(12, 9, 12, 9); root.setSpacing(10)

        badge = QLabel(str(number)); badge.setAlignment(Qt.AlignmentFlag.AlignCenter); badge.setFixedSize(30, 30)
        badge.setObjectName("InstallmentNumberCurrent" if current else "InstallmentNumber")
        root.addWidget(badge)

        info = QVBoxLayout(); info.setSpacing(2)
        title = QLabel(f"Cuota {number}/{total}"); title.setObjectName("TransactionTitle")
        actual_date = (tx or {}).get("tx_date") if tx else None
        date_text = human_date(actual_date or expected_date.isoformat())
        meta = QLabel(f"{date_text} · {state}"); meta.setObjectName("SmallMuted")
        info.addWidget(title); info.addWidget(meta); root.addLayout(info, 1)

        amount_lbl = QLabel(amount); amount_lbl.setObjectName("TransactionAmountNegative")
        amount_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        root.addWidget(amount_lbl)


class InstallmentDetailDialog(QDialog):
    edit_requested = Signal(int)

    def __init__(self, db, plan, fmt, parent=None):
        super().__init__(parent)
        self.db = db
        self.plan = dict(plan)
        self.plan_id = int(plan["id"])
        self.fmt = fmt
        self.setWindowTitle("Detalle de cuotas")
        self.resize(720, 760)
        self.setMinimumSize(560, 560)

        total = max(1, int(plan.get("installments") or 1))
        current = int(plan.get("current_number") or max(0, int(plan.get("next_number") or 1) - 1))
        current = min(total, max(0, current))
        remaining = max(0, total - current)
        base = float(plan.get("base_amount") or 0)
        total_amount = float(plan.get("total_amount") or base * total)
        paid_estimate = min(total_amount, base * current)
        remaining_amount = max(0.0, total_amount - paid_estimate)
        pct = round((current / total) * 100) if total else 0

        root = QVBoxLayout(self); root.setContentsMargins(24, 22, 24, 20); root.setSpacing(14)

        heading = QHBoxLayout(); heading.setSpacing(12)
        heading.addWidget(IconBadge(plan.get("category_icon") or "card", plan.get("category_color") or "#4CCFA9", 48, secondary_color=plan.get("category_secondary_color")))
        hinfo = QVBoxLayout(); hinfo.setSpacing(2)
        title = QLabel(plan.get("description") or plan.get("category_name") or "Compra en cuotas"); title.setObjectName("PageTitle")
        cat = plan.get("category_name") or "Sin categoría"
        if plan.get("parent_category_name"):
            cat = f"{plan['parent_category_name']} / {cat}"
        sub = QLabel(f"{plan.get('account_name','Tarjeta')} · {cat}"); sub.setObjectName("PageSubtitle")
        hinfo.addWidget(title); hinfo.addWidget(sub); heading.addLayout(hinfo, 1)
        price = QLabel(self.fmt(base)); price.setObjectName("CardValue"); heading.addWidget(price)
        root.addLayout(heading)

        progress_card = QFrame(); progress_card.setObjectName("SoftCard")
        pc = QVBoxLayout(progress_card); pc.setContentsMargins(16, 14, 16, 14); pc.setSpacing(9)
        prow = QHBoxLayout()
        ptitle = QLabel(f"Cuota {current} de {total}"); ptitle.setObjectName("SectionTitle")
        ppct = QLabel(f"{pct}%"); ppct.setObjectName("Muted")
        prow.addWidget(ptitle); prow.addStretch(); prow.addWidget(ppct); pc.addLayout(prow)
        bar = QProgressBar(); bar.setRange(0, 100); bar.setValue(pct); bar.setTextVisible(False); bar.setFixedHeight(9); pc.addWidget(bar)
        note = QLabel(
            "El progreso muestra el plan completo aunque las cuotas anteriores a la incorporación a App Gastos no tengan un movimiento individual guardado."
        )
        note.setObjectName("SmallMuted"); note.setWordWrap(True); pc.addWidget(note)
        root.addWidget(progress_card)

        stats = QGridLayout(); stats.setHorizontalSpacing(10); stats.setVerticalSpacing(10)
        data = [
            ("Total de la compra", self.fmt(total_amount)),
            ("Acumulado estimado", self.fmt(paid_estimate)),
            ("Restante", self.fmt(remaining_amount)),
            ("Cuotas restantes", str(remaining)),
        ]
        for i, (label, value) in enumerate(data):
            card = QFrame(); card.setObjectName("MiniStatCard")
            cl = QVBoxLayout(card); cl.setContentsMargins(12, 10, 12, 10); cl.setSpacing(2)
            cap = QLabel(label); cap.setObjectName("SmallMuted")
            val = QLabel(value); val.setObjectName("SectionTitle")
            cl.addWidget(cap); cl.addWidget(val); stats.addWidget(card, i // 2, i % 2)
        root.addLayout(stats)

        purchase_date = date.fromisoformat(str(plan.get("purchase_date") or date.today().isoformat())[:10])
        final_date = add_months(purchase_date, total - 1, purchase_date.day)
        dates = QLabel(
            f"Inicio estimado: {human_date(purchase_date.isoformat())}   ·   "
            f"Finaliza: {human_date(final_date.isoformat())}"
        )
        dates.setObjectName("Muted"); root.addWidget(dates)

        timeline_title = QHBoxLayout()
        tt = QLabel("Recorrido del plan"); tt.setObjectName("SectionTitle")
        real_count = int(plan.get("registered_count") or 0)
        rc = QLabel(f"{real_count} movimientos guardados en App Gastos"); rc.setObjectName("SmallMuted")
        timeline_title.addWidget(tt); timeline_title.addStretch(); timeline_title.addWidget(rc); root.addLayout(timeline_title)

        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.Shape.NoFrame)
        host = QWidget(); rows = QVBoxLayout(host); rows.setContentsMargins(0, 0, 7, 0); rows.setSpacing(7)
        txs = {int(t.get("installment_number") or 0): t for t in db.installment_transactions(self.plan_id)}
        for n in range(1, total + 1):
            expected = add_months(purchase_date, n - 1, purchase_date.day)
            tx = txs.get(n)
            if tx:
                state = "Registrada en App Gastos"
            elif n < current:
                state = "Anterior · sin detalle individual"
            elif n == current:
                state = "Cuota actual · sin movimiento individual"
            else:
                state = "Programada"
            amount_value = base if n < total else max(0.0, total_amount - base * (total - 1))
            rows.addWidget(InstallmentTimelineRow(n, total, expected, self.fmt(amount_value), state, tx, n == current))
        rows.addStretch(); scroll.setWidget(host); root.addWidget(scroll, 1)

        actions = QHBoxLayout(); actions.addStretch()
        close = QPushButton("← Volver"); close.setObjectName("SecondaryButton"); close.clicked.connect(self.accept)
        edit = QPushButton("Modificar plan"); edit.clicked.connect(lambda: self.edit_requested.emit(self.plan_id))
        actions.addWidget(close); actions.addWidget(edit); root.addLayout(actions)


class InstallmentPlanCard(QFrame):
    detail_requested = Signal(int)
    edit_requested = Signal(int)
    cancel_requested = Signal(int)
    delete_requested = Signal(int)

    def __init__(self, plan, fmt, parent=None):
        super().__init__(parent)
        self.plan = plan
        self.plan_id = int(plan["id"])
        self.setObjectName("SoftCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Doble clic para ver el detalle · clic derecho para más acciones")

        total = max(1, int(plan.get("installments") or 1))
        current = int(plan.get("current_number") or max(0, int(plan.get("next_number") or 1) - 1))
        current = min(total, max(0, current))
        remaining = max(0, total - current)
        remaining_amount = max(0.0, float(plan.get("total_amount") or 0) - float(plan.get("base_amount") or 0) * current)
        pct = round((current / total) * 100) if total else 0

        root = QVBoxLayout(self); root.setContentsMargins(16, 14, 16, 14); root.setSpacing(9)
        top = QHBoxLayout(); top.setSpacing(11)
        top.addWidget(IconBadge(plan.get("category_icon") or "card", plan.get("category_color") or "#4CCFA9", 42, secondary_color=plan.get("category_secondary_color")))
        info = QVBoxLayout(); info.setSpacing(2)
        title = QLabel(plan.get("description") or plan.get("category_name") or "Compra en cuotas"); title.setObjectName("SectionTitle")
        cat = plan.get("category_name") or "Sin categoría"
        if plan.get("parent_category_name"): cat = f"{plan['parent_category_name']} / {cat}"
        meta = QLabel(f"{plan.get('account_name','Tarjeta')}  ·  {cat}"); meta.setObjectName("SmallMuted")
        info.addWidget(title); info.addWidget(meta); top.addLayout(info, 1)
        amount = QLabel(fmt(float(plan.get("base_amount") or 0))); amount.setObjectName("CardValue"); top.addWidget(amount)
        root.addLayout(top)

        status = QHBoxLayout()
        progress_text = QLabel(f"Cuota {current} de {total}"); progress_text.setObjectName("Muted")
        percent_text = QLabel(f"{pct}%"); percent_text.setObjectName("InstallmentPercent")
        remaining_text = QLabel(f"Restan {remaining} · {fmt(remaining_amount)} comprometidos"); remaining_text.setObjectName("SmallMuted")
        status.addWidget(progress_text); status.addWidget(percent_text); status.addStretch(); status.addWidget(remaining_text); root.addLayout(status)

        bar = QProgressBar(); bar.setRange(0,100); bar.setValue(pct); bar.setTextVisible(False); bar.setFixedHeight(8)
        root.addWidget(bar)
        next_text = "Plan finalizado" if remaining == 0 else f"Próxima cuota: {human_date(plan.get('next_installment_date') or '')}"
        next_lbl = QLabel(next_text); next_lbl.setObjectName("SmallMuted"); root.addWidget(next_lbl)

    def mouseDoubleClickEvent(self, event):
        self.detail_requested.emit(self.plan_id); event.accept()

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        detail = menu.addAction("Ver detalle")
        edit = menu.addAction("Corregir plan")
        cancel = None
        if bool(self.plan.get("active")):
            cancel = menu.addAction("Cancelar cuotas restantes")
        menu.addSeparator()
        delete = menu.addAction("Eliminar / desvincular plan…")
        chosen = menu.exec(event.globalPos())
        if chosen == detail: self.detail_requested.emit(self.plan_id)
        elif chosen == edit: self.edit_requested.emit(self.plan_id)
        elif cancel is not None and chosen == cancel: self.cancel_requested.emit(self.plan_id)
        elif chosen == delete: self.delete_requested.emit(self.plan_id)



class MonthlyCommitmentCard(QFrame):
    detail_requested = Signal(int, int)

    def __init__(self, data, fmt, current=False, parent=None):
        super().__init__(parent)
        self.data = data
        self.year = int(data["year"]); self.month = int(data["month"])
        self.setObjectName("MonthlyCommitmentCurrent" if current else "MonthlyCommitmentCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Doble clic para ver qué cuotas componen este mes")
        box = QVBoxLayout(self); box.setContentsMargins(14, 12, 14, 12); box.setSpacing(5)
        month = QLabel(f"{MONTHS_SHORT[self.month - 1]} {str(self.year)[-2:]}")
        month.setObjectName("TinyCaption")
        total = QLabel(fmt(float(data.get("total") or 0)))
        total.setObjectName("SectionTitle")
        count = int(data.get("count") or 0)
        hint = QLabel(f"{count} {'cuota' if count == 1 else 'cuotas'}")
        hint.setObjectName("SmallMuted")
        box.addWidget(month); box.addWidget(total); box.addWidget(hint)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.detail_requested.emit(self.year, self.month)
            event.accept(); return
        super().mouseDoubleClickEvent(event)


class MonthlyCommitmentDialog(QDialog):
    def __init__(self, data, fmt, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cuotas del mes")
        self.resize(620, 560)
        self.setMinimumSize(540, 460)
        year = int(data["year"]); month = int(data["month"])
        root = QVBoxLayout(self); root.setContentsMargins(24, 22, 24, 20); root.setSpacing(14)
        top = QHBoxLayout()
        title_box = QVBoxLayout(); title_box.setSpacing(2)
        title = QLabel(f"{MONTHS[month - 1]} {year}"); title.setObjectName("PageTitle")
        subtitle = QLabel(f"{int(data.get('count') or 0)} cuotas comprometidas"); subtitle.setObjectName("PageSubtitle")
        title_box.addWidget(title); title_box.addWidget(subtitle); top.addLayout(title_box, 1)
        value = QLabel(fmt(float(data.get("total") or 0))); value.setObjectName("HeroValue"); top.addWidget(value)
        root.addLayout(top)

        line = QFrame(); line.setObjectName("Hairline"); root.addWidget(line)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.Shape.NoFrame)
        host = QWidget(); rows = QVBoxLayout(host); rows.setContentsMargins(0, 0, 7, 0); rows.setSpacing(3)
        items = data.get("items") or []
        if not items:
            empty = QLabel("No hay cuotas en este mes."); empty.setObjectName("Muted"); rows.addWidget(empty)
        else:
            for item in items:
                row = QFrame(); row.setObjectName("FlatListRow")
                box = QHBoxLayout(row); box.setContentsMargins(10, 10, 10, 10); box.setSpacing(10)
                box.addWidget(IconBadge(item.get("category_icon") or "card", item.get("category_color") or "#4CCFA9", 34, secondary_color=item.get("category_secondary_color")))
                text = QVBoxLayout(); text.setSpacing(1)
                name = QLabel(item.get("description") or "Compra en cuotas"); name.setObjectName("TransactionTitle")
                cat = item.get("category_name") or "Sin categoría"
                if item.get("parent_category_name"):
                    cat = f"{item['parent_category_name']} / {cat}"
                meta = QLabel(f"{item.get('account_name','Tarjeta')} · {cat} · {item.get('installment_number')}/{item.get('installment_total')}")
                meta.setObjectName("SmallMuted")
                text.addWidget(name); text.addWidget(meta); box.addLayout(text, 1)
                amount = QLabel(fmt(float(item.get("amount") or 0))); amount.setObjectName("TransactionAmountNegative")
                box.addWidget(amount); rows.addWidget(row)
        rows.addStretch(); scroll.setWidget(host); root.addWidget(scroll, 1)
        actions = QHBoxLayout(); actions.addStretch()
        close = QPushButton("Cerrar"); close.setObjectName("SecondaryButton"); close.clicked.connect(self.accept)
        actions.addWidget(close); root.addLayout(actions)


class InstallmentsPage(QWidget):
    data_changed = Signal()

    def __init__(self, db):
        super().__init__(); self.db = db; self._compact = False; self._commitments = []
        root = QVBoxLayout(self); root.setContentsMargins(28,24,28,28); root.setSpacing(15)
        root.addWidget(page_header("Cuotas", "Todas tus compras financiadas y lo que todavía queda comprometido"))

        summary = QFrame(); summary.setObjectName("MetricsStrip")
        self.summary_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight, summary); self.summary_layout.setContentsMargins(8,6,8,6); self.summary_layout.setSpacing(6)
        cards = self.summary_layout
        self.active = StatCard("Planes activos")
        self.remaining = StatCard("Restante comprometido")
        self.next_month = StatCard("Este mes en cuotas")
        self.cards_count = StatCard("Próximo mes")
        metrics=(self.active,self.remaining,self.next_month,self.cards_count)
        for i,c in enumerate(metrics):
            cards.addWidget(c,1)
        root.addWidget(summary)

        monthly = QFrame(); monthly.setObjectName("DashboardSection")
        monthly_box = QVBoxLayout(monthly); monthly_box.setContentsMargins(18, 16, 18, 16); monthly_box.setSpacing(10)
        monthly_head = QHBoxLayout(); monthly_head.setSpacing(8)
        mt = QLabel("Compromiso por mes"); mt.setObjectName("SectionTitle")
        mh = QLabel("Cuánto vas a pagar en cuotas, mes a mes"); mh.setObjectName("SmallMuted")
        self.monthly_current = QLabel(""); self.monthly_current.setObjectName("InstallmentMonthlyHighlight")
        monthly_head.addWidget(mt); monthly_head.addSpacing(6); monthly_head.addWidget(mh); monthly_head.addStretch(); monthly_head.addWidget(self.monthly_current)
        monthly_box.addLayout(monthly_head)
        self.monthly_layout = QGridLayout(); self.monthly_layout.setSpacing(8); monthly_box.addLayout(self.monthly_layout)
        note = QLabel("Doble clic en un mes para ver qué compras componen ese total."); note.setObjectName("TinyCaption")
        monthly_box.addWidget(note)
        root.addWidget(monthly)

        filter_row = QHBoxLayout(); filter_row.setSpacing(8)
        hint = QLabel("Doble clic para ver el recorrido completo · clic derecho para corregir, cancelar o limpiar un plan")
        hint.setObjectName("SmallMuted"); filter_row.addWidget(hint); filter_row.addStretch()
        self.active_only_btn = QPushButton("Activas"); self.active_only_btn.setObjectName("SegmentButton"); self.active_only_btn.setCheckable(True); self.active_only_btn.setChecked(True)
        self.all_btn = QPushButton("Todas"); self.all_btn.setObjectName("SegmentButton"); self.all_btn.setCheckable(True)
        self.filter_group = QButtonGroup(self); self.filter_group.setExclusive(True); self.filter_group.addButton(self.active_only_btn); self.filter_group.addButton(self.all_btn)
        self.active_only_btn.clicked.connect(lambda: self._set_filter(True)); self.all_btn.clicked.connect(lambda: self._set_filter(False))
        filter_row.addWidget(self.active_only_btn); filter_row.addWidget(self.all_btn); root.addLayout(filter_row)
        self.active_only = True

        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True); self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.host = QWidget(); self.rows = QVBoxLayout(self.host); self.rows.setContentsMargins(0,0,8,8); self.rows.setSpacing(10)
        self.scroll.setWidget(self.host); root.addWidget(self.scroll,1)
        self.refresh()

    def _fmt(self, value):
        return money(value, self.db.currency_symbol(), self.db.balances_hidden())

    def _set_filter(self, active_only: bool):
        self.active_only = bool(active_only)
        self.active_only_btn.setChecked(self.active_only)
        self.all_btn.setChecked(not self.active_only)
        self.refresh()

    def refresh(self):
        clear_layout(self.rows)
        all_plans = self.db.installment_plans(active_only=False)
        active_plans = [p for p in all_plans if bool(p.get("active"))]
        plans = active_plans if self.active_only else all_plans
        if not plans:
            empty = QFrame(); empty.setObjectName("SoftCard"); box=QVBoxLayout(empty); box.setContentsMargins(22,28,22,28)
            title=QLabel("No hay planes activos" if self.active_only and all_plans else "Todavía no hay compras en cuotas"); title.setObjectName("SectionTitle")
            sub=QLabel("Cambiá a ‘Todas’ para ver planes finalizados." if self.active_only and all_plans else "Podés crear una compra nueva en cuotas o hacer clic derecho sobre un gasto existente y elegir “Configurar cuotas”."); sub.setObjectName("Muted"); sub.setWordWrap(True)
            box.addWidget(title); box.addWidget(sub); self.rows.addWidget(empty)
        else:
            for plan in plans:
                card=InstallmentPlanCard(plan,self._fmt)
                card.detail_requested.connect(self.show_detail)
                card.edit_requested.connect(self.edit_plan); card.cancel_requested.connect(self.cancel_plan); card.delete_requested.connect(self.delete_plan)
                self.rows.addWidget(card)
        self.rows.addStretch()

        remaining = sum(
            max(0.0, float(p.get("total_amount") or 0) - float(p.get("base_amount") or 0) * int(p.get("current_number") or max(0, int(p.get("next_number") or 1) - 1)))
            for p in active_plans
        )
        card_count = len({int(p["account_id"]) for p in active_plans})
        today = date.today()
        commitments = self.db.installment_monthly_commitments(today.year, today.month, 6)
        this_month = commitments[0] if commitments else {"total": 0.0, "count": 0}
        next_month = commitments[1] if len(commitments) > 1 else {"total": 0.0, "count": 0}
        self.active.set_value(str(len(active_plans)), "Compras todavía en curso")
        self.remaining.set_value(self._fmt(remaining), "Cuotas que todavía faltan")
        self.next_month.set_value(self._fmt(float(this_month.get("total") or 0)), f"{int(this_month.get('count') or 0)} cuotas este mes")
        self.cards_count.set_value(self._fmt(float(next_month.get("total") or 0)), f"{int(next_month.get('count') or 0)} cuotas el próximo mes")

        self._commitments = list(commitments)
        self._render_monthly_commitments()
        self.monthly_current.setText(f"Este mes · {self._fmt(float(this_month.get('total') or 0))}")
        self._apply_responsive()

    def _render_monthly_commitments(self):
        clear_layout(self.monthly_layout)
        cols = 2 if self._compact else 6
        if not self._compact and self.width() < 1320:
            cols = 3
        for i, data in enumerate(self._commitments):
            card = MonthlyCommitmentCard(data, self._fmt, current=(i == 0))
            card.detail_requested.connect(self.show_month_detail)
            card.setMinimumWidth(0)
            self.monthly_layout.addWidget(card, i // cols, i % cols)
        for c in range(cols):
            self.monthly_layout.setColumnStretch(c, 1)

    def _apply_responsive(self):
        compact = responsive_mode(self.width(), self.height()) != "wide"
        changed = compact != self._compact
        self._compact = compact
        self.summary_layout.setDirection(QBoxLayout.Direction.TopToBottom if compact else QBoxLayout.Direction.LeftToRight)
        margins = 14 if compact else 28
        self.layout().setContentsMargins(margins, 18 if compact else 24, margins, 20 if compact else 28)
        if changed and self._commitments:
            self._render_monthly_commitments()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_responsive()

    def show_month_detail(self, year, month):
        rows = self.db.installment_monthly_commitments(int(year), int(month), 1)
        if not rows:
            return
        MonthlyCommitmentDialog(rows[0], self._fmt, self).exec()

    def show_detail(self, plan_id=None):
        if not plan_id: return
        plan = self.db.installment_plan(int(plan_id))
        if not plan:
            QMessageBox.warning(self, "Cuotas", "No encontré ese plan de cuotas."); return
        dlg = InstallmentDetailDialog(self.db, plan, self._fmt, self)
        dlg.edit_requested.connect(lambda pid: (dlg.accept(), self.edit_plan(pid)))
        dlg.exec()

    def edit_plan(self, plan_id=None):
        if not plan_id: return
        # Corregimos desde el movimiento ancla. Usar la última cuota generada
        # impedía retroceder un plan (por ejemplo de 12/12 a 7/12).
        tx = self.db.installment_anchor_transaction(int(plan_id))
        if not tx:
            QMessageBox.warning(self,"Cuotas","No encontré un movimiento asociado a este plan."); return
        dlg = ExistingInstallmentDialog(self.db, tx, self)
        if dlg.exec():
            try:
                d=dlg.data()
                self.db.configure_existing_installment(
                    int(tx["id"]), d["current_installment"], d["total_installments"],
                    d["card_account_id"], d.get("current_date")
                )
                self.db.process_due_installments()
            except Exception as exc:
                QMessageBox.warning(self,"Cuotas",str(exc)); return
            self.refresh(); self.data_changed.emit()

    def delete_plan(self, plan_id=None):
        if not plan_id: return
        plan = self.db.installment_plan(int(plan_id))
        if not plan: return
        box = QMessageBox(self)
        box.setWindowTitle("Eliminar plan de cuotas")
        box.setIcon(QMessageBox.Icon.Question)
        box.setText(plan.get("description") or plan.get("category_name") or "Plan de cuotas")
        box.setInformativeText(
            "Si el plan se creó por error, podés quitar únicamente la estructura de cuotas y conservar el gasto original, "
            "o borrar también todos los movimientos asociados a este plan."
        )
        keep = box.addButton("Quitar plan · conservar gasto", QMessageBox.ButtonRole.AcceptRole)
        delete_all = box.addButton("Eliminar plan y movimientos", QMessageBox.ButtonRole.DestructiveRole)
        cancel = box.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        clicked = box.clickedButton()
        if clicked == cancel or clicked is None:
            return
        try:
            self.db.remove_installment_plan(int(plan_id), delete_movements=(clicked == delete_all))
        except Exception as exc:
            QMessageBox.warning(self, "Cuotas", str(exc)); return
        self.refresh(); self.data_changed.emit()

    def cancel_plan(self, plan_id=None):
        if not plan_id: return
        if QMessageBox.question(self,"Cancelar cuotas","¿Dejar de generar las cuotas restantes de este plan? Los movimientos ya registrados no se borran.") != QMessageBox.StandardButton.Yes:
            return
        self.db.cancel_installment_plan(int(plan_id)); self.refresh(); self.data_changed.emit()
