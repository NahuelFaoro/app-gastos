from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QBoxLayout, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ..constants import MONTHS, MONTHS_SHORT
from ..dialogs import TransactionDialog
from ..layouts import responsive_mode
from ..utils import money, percent_change
from ..widgets import BudgetProgress, CashflowChart, DonutChart, IconBadge, TransactionRowWidget
from .common import clear_layout, page_header, scroll_container


class DashboardMetric(QFrame):
    def __init__(self, caption, parent=None):
        super().__init__(parent)
        self.setObjectName("OverviewMetric")
        box = QVBoxLayout(self); box.setContentsMargins(0, 2, 0, 2); box.setSpacing(5)
        self.caption = QLabel(caption); self.caption.setObjectName("OverviewMetricLabel")
        self.value = QLabel("$ 0"); self.value.setObjectName("OverviewMetricValue")
        self.hint = QLabel(""); self.hint.setObjectName("SmallMuted"); self.hint.setWordWrap(True)
        for label in (self.caption, self.value, self.hint):
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box.addWidget(self.caption); box.addWidget(self.value); box.addWidget(self.hint)

    def set_value(self, value, hint="", tone=None):
        self.value.setText(value); self.hint.setText(hint)
        self.hint.setObjectName("Positive" if tone == "positive" else "Negative" if tone == "negative" else "SmallMuted")
        self.hint.style().unpolish(self.hint); self.hint.style().polish(self.hint)


class DashboardPage(QWidget):
    data_changed = Signal()

    def __init__(self, db):
        super().__init__()
        self.db = db
        self._compact = False
        self._responsive_mode = None
        self._wallet_columns = 0
        self._wallet_accounts = []
        now = date.today(); self.current_year = now.year; self.current_month = now.month

        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0)
        scroll, _, root = scroll_container(); root.setSpacing(18); outer.addWidget(scroll)

        self.header_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight); self.header_layout.setSpacing(10)
        self.header_layout.addWidget(page_header("Dashboard", "Una vista clara de tu dinero, sin ruido"), 1)
        header_actions = QWidget(); ha = QHBoxLayout(header_actions); ha.setContentsMargins(0, 0, 0, 0); ha.setSpacing(8)
        prev_period = QPushButton("‹"); prev_period.setObjectName("PeriodNavButton"); prev_period.clicked.connect(self.previous_period)
        self.period_label = QLabel(); self.period_label.setObjectName("PeriodLabel"); self.period_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        next_period = QPushButton("›"); next_period.setObjectName("PeriodNavButton"); next_period.clicked.connect(self.next_period)
        today_period = QPushButton("Hoy"); today_period.setObjectName("SecondaryButton"); today_period.clicked.connect(self.go_today)
        add = QPushButton("Nuevo movimiento"); add.clicked.connect(self.add_transaction)
        ha.addWidget(prev_period); ha.addWidget(self.period_label, 1); ha.addWidget(next_period); ha.addWidget(today_period); ha.addWidget(add)
        self.header_layout.addWidget(header_actions)
        root.addLayout(self.header_layout)

        self.overview_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight); self.overview_layout.setSpacing(14)
        hero = QFrame(); hero.setObjectName("HeroCard"); hero.setMinimumHeight(174)
        h = QVBoxLayout(hero); h.setContentsMargins(24, 21, 24, 20); h.setSpacing(7)
        cap = QLabel("SALDO DISPONIBLE"); cap.setObjectName("HeroCaption")
        self.balance = QLabel(); self.balance.setObjectName("HeroValue")
        self.balance_hint = QLabel(); self.balance_hint.setObjectName("HeroHint"); self.balance_hint.setWordWrap(True)
        privacy = QLabel("Cuentas separadas no alteran este saldo"); privacy.setObjectName("HeroHint")
        for label in (cap, self.balance, self.balance_hint, privacy):
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        h.addWidget(cap); h.addWidget(self.balance); h.addWidget(self.balance_hint); h.addStretch(); h.addWidget(privacy)
        self.overview_layout.addWidget(hero, 5)

        month = QFrame(); month.setObjectName("OverviewCard"); month.setMinimumHeight(174)
        ml = QVBoxLayout(month); ml.setContentsMargins(22, 18, 22, 18); ml.setSpacing(13)
        # El título queda centrado respecto de toda la tarjeta, no respecto del
        # espacio que sobra antes de la fecha del mes.
        mh = QGridLayout()
        month_title = QLabel("Este mes"); month_title.setObjectName("SectionTitle")
        month_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.month_meta = QLabel(); self.month_meta.setObjectName("SmallMuted")
        self.month_meta.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        mh.addWidget(month_title, 0, 0, 1, 3, Qt.AlignmentFlag.AlignCenter)
        mh.addWidget(self.month_meta, 0, 2, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        mh.setColumnStretch(0, 1); mh.setColumnStretch(1, 1); mh.setColumnStretch(2, 1)
        ml.addLayout(mh)
        self.metrics_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight); self.metrics_layout.setSpacing(18)
        self.income = DashboardMetric("Ingresos"); self.expense = DashboardMetric("Gastos"); self.net = DashboardMetric("Resultado")
        self.metrics_layout.addWidget(self.income, 1); self.metrics_layout.addWidget(self.expense, 1); self.metrics_layout.addWidget(self.net, 1)
        ml.addLayout(self.metrics_layout)
        self.overview_layout.addWidget(month, 7)
        root.addLayout(self.overview_layout)

        accounts_header = QHBoxLayout(); at = QLabel("Cuentas"); at.setObjectName("SectionTitle")
        ah = QLabel("Disponible y separado, a simple vista"); ah.setObjectName("SmallMuted")
        accounts_header.addWidget(at); accounts_header.addSpacing(7); accounts_header.addWidget(ah); accounts_header.addStretch(); root.addLayout(accounts_header)
        self.wallets_grid = QGridLayout(); self.wallets_grid.setSpacing(9); root.addLayout(self.wallets_grid)

        self.charts_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight); self.charts_layout.setSpacing(14)
        cat_card = QFrame(); cat_card.setObjectName("DashboardSection")
        cat_l = QVBoxLayout(cat_card); cat_l.setContentsMargins(20, 18, 20, 18); cat_l.setSpacing(11)
        title = QLabel("Gastos por categoría"); title.setObjectName("SectionTitle")
        cat_hint = QLabel("Qué se llevó la mayor parte del mes"); cat_hint.setObjectName("SmallMuted")
        cat_l.addWidget(title); cat_l.addWidget(cat_hint)
        self.cat_body = QBoxLayout(QBoxLayout.Direction.LeftToRight); self.cat_body.setSpacing(12)
        self.category_donut = DonutChart(); self.category_donut.setMinimumSize(170, 170); self.category_donut.setMaximumWidth(235)
        self.cat_body.addWidget(self.category_donut, 4)
        self.category_layout = QVBoxLayout(); self.category_layout.setSpacing(4); self.cat_body.addLayout(self.category_layout, 6)
        cat_l.addLayout(self.cat_body, 1)
        self.charts_layout.addWidget(cat_card, 1)

        trend_card = QFrame(); trend_card.setObjectName("DashboardSection")
        tr = QVBoxLayout(trend_card); tr.setContentsMargins(20, 18, 20, 18); tr.setSpacing(8)
        tt = QLabel("Flujo de los últimos 6 meses"); tt.setObjectName("SectionTitle")
        th = QLabel("Ingresos y gastos para ver la tendencia, no sólo el mes actual"); th.setObjectName("SmallMuted")
        tr.addWidget(tt); tr.addWidget(th)
        self.trend = CashflowChart(); tr.addWidget(self.trend)
        self.charts_layout.addWidget(trend_card, 1)
        root.addLayout(self.charts_layout)

        self.bottom_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight); self.bottom_layout.setSpacing(14)
        recent = QFrame(); recent.setObjectName("DashboardSection")
        rl = QVBoxLayout(recent); rl.setContentsMargins(20, 18, 20, 18); rl.setSpacing(7)
        rh = QHBoxLayout(); rt = QLabel("Actividad reciente"); rt.setObjectName("SectionTitle")
        rsub = QLabel("Últimos movimientos cargados"); rsub.setObjectName("SmallMuted")
        rh.addWidget(rt); rh.addSpacing(7); rh.addWidget(rsub); rh.addStretch(); rl.addLayout(rh)
        self.recent_layout = QVBoxLayout(); self.recent_layout.setSpacing(2); rl.addLayout(self.recent_layout)
        self.bottom_layout.addWidget(recent, 2)

        installments = QFrame(); installments.setObjectName("DashboardSection")
        bl = QVBoxLayout(installments); bl.setContentsMargins(20, 18, 20, 18); bl.setSpacing(7)
        bt = QLabel("Cuotas activas"); bt.setObjectName("SectionTitle")
        self.installment_hint = QLabel("Compromisos que siguen corriendo"); self.installment_hint.setObjectName("SmallMuted")
        bl.addWidget(bt); bl.addWidget(self.installment_hint)
        self.installment_layout = QVBoxLayout(); self.installment_layout.setSpacing(3); bl.addLayout(self.installment_layout); bl.addStretch()
        self.bottom_layout.addWidget(installments, 1)
        root.addLayout(self.bottom_layout)
        root.addStretch()

        self.refresh(); self._apply_responsive()

    def _fmt(self, value):
        return money(value, self.db.currency_symbol(), self.db.balances_hidden())

    def _change_hint(self, current, previous, invert=False):
        p = percent_change(current, previous)
        if p is None: return "Sin comparación", None
        if previous == 0 and current > 0: return "Primer mes comparable", None
        good = p < 0 if invert else p > 0
        return f"{abs(p):.0f}% {'menos' if p < 0 else 'más'} vs. mes anterior", "positive" if good else "negative" if p != 0 else None

    def _render_wallets(self):
        clear_layout(self.wallets_grid)
        mode = responsive_mode(self.width(), self.height())
        cols = 1 if mode == "narrow" else 2 if mode == "compact" else 4
        if self.width() > 1350 and mode == "wide": cols = 5
        self._wallet_columns = cols
        accounts = self._wallet_accounts
        for i, account in enumerate(accounts[:5]):
            mini = QFrame(); mini.setObjectName("WalletMiniCard" if bool(account.get("include_in_balance", 1)) else "WalletMiniCardExcluded")
            ml = QVBoxLayout(mini); ml.setContentsMargins(14, 11, 14, 11); ml.setSpacing(3)
            top = QHBoxLayout(); name = QLabel(account["name"]); name.setObjectName("WalletMiniName")
            state = QLabel("Disponible" if bool(account.get("include_in_balance", 1)) else "Separada"); state.setObjectName("TinyCaption")
            top.addWidget(name); top.addStretch(); top.addWidget(state); ml.addLayout(top)
            value = QLabel(self._fmt(account["balance"])); value.setObjectName("WalletMiniBalance"); ml.addWidget(value)
            self.wallets_grid.addWidget(mini, i // cols, i % cols)
        if len(accounts) > 5:
            more = QLabel(f"+{len(accounts)-5} cuentas"); more.setObjectName("SmallMuted")
            self.wallets_grid.addWidget(more, (min(len(accounts), 5)) // cols, (min(len(accounts), 5)) % cols)
        for c in range(cols): self.wallets_grid.setColumnStretch(c, 1)

    def refresh(self):
        y = self.current_year; m = self.current_month
        self.period_label.setText(f"{MONTHS[m - 1]} {y}"); self.month_meta.setText(f"{MONTHS[m - 1]} {y}")
        summary = self.db.monthly_summary(y, m); previous = self.db.previous_month_summary(y, m)
        accounts = self.db.accounts_with_balances(); self._wallet_accounts = accounts
        included = [a for a in accounts if bool(a.get("include_in_balance", 1))]
        excluded = [a for a in accounts if not bool(a.get("include_in_balance", 1))]
        self.balance.setText(self._fmt(self.db.available_balance()))
        self.balance_hint.setText(f"{len(included)} cuentas disponibles · {len(excluded)} separadas" if excluded else f"{len(included)} cuentas incluidas en tu saldo diario")
        self._render_wallets()

        hint, tone = self._change_hint(summary["income"], previous["income"])
        if summary.get("history_income"): hint += " · historial"
        self.income.set_value(self._fmt(summary["income"]), hint, tone)
        hint, tone = self._change_hint(summary["expense"], previous["expense"], invert=True)
        if summary.get("history_expense"): hint += " · historial"
        self.expense.set_value(self._fmt(summary["expense"]), hint, tone)
        self.net.set_value(self._fmt(summary["net"]), "Ingresos − gastos", "positive" if summary["net"] >= 0 else "negative")

        categories = self.db.expense_by_category(y, m, 7)
        clear_layout(self.category_layout)
        total = sum(float(row.get("total") or 0) for row in categories)
        chart_data = [(c.get("category") or "Sin categoría", float(c.get("total") or 0), c.get("color") or "#4CCFA9") for c in categories]
        self.category_donut.set_data(chart_data, self.db.currency_symbol(), self.db.balances_hidden(), "Sin gastos")
        if not categories:
            empty = QLabel("No hay gastos en este mes todavía."); empty.setObjectName("Muted"); empty.setWordWrap(True); self.category_layout.addWidget(empty)
        else:
            for category in categories[:5]:
                value = float(category.get("total") or 0); share = value / total * 100 if total else 0
                row = QFrame(); row.setObjectName("DashboardCategoryRow")
                box = QHBoxLayout(row); box.setContentsMargins(7, 6, 7, 6); box.setSpacing(8)
                box.addWidget(IconBadge(
                    category.get("icon", "other"),
                    category.get("color") or "#4CCFA9",
                    30,
                    secondary_color=category.get("secondary_color"),
                ))
                texts = QVBoxLayout(); texts.setSpacing(0)
                name = QLabel(category.get("category") or "Sin categoría"); name.setObjectName("TransactionTitle")
                pct = QLabel(f"{share:.0f}% del gasto"); pct.setObjectName("TinyCaption")
                texts.addWidget(name); texts.addWidget(pct); box.addLayout(texts, 1)
                amount = QLabel(self._fmt(value)); amount.setObjectName("TransactionAmount"); box.addWidget(amount)
                self.category_layout.addWidget(row)
            self.category_layout.addStretch()

        trend = self.db.monthly_trend(y, m, 6)
        self.trend.set_data(trend, [MONTHS_SHORT[item["month"] - 1] for item in trend])

        clear_layout(self.recent_layout)
        txs = self.db.recent_transactions(limit=7)
        if not txs:
            empty = QLabel("Todavía no hay movimientos."); empty.setObjectName("Muted"); self.recent_layout.addWidget(empty)
        else:
            for tx in txs:
                amount = float(tx["amount"]); shown = amount if tx["kind"] == "income" else -amount if tx["kind"] == "expense" else amount
                row = TransactionRowWidget(tx, self._fmt(shown), compact=True); row.edit_requested.connect(self.edit_transaction)
                self.recent_layout.addWidget(row)

        clear_layout(self.installment_layout)
        commitments = self.db.installment_monthly_commitments(y, m, 1)
        month_commitment = float(commitments[0].get("total") or 0) if commitments else 0.0
        month_count = int(commitments[0].get("count") or 0) if commitments else 0
        self.installment_hint.setText(f"{self._fmt(month_commitment)} este mes · {month_count} {'cuota' if month_count == 1 else 'cuotas'}")
        plans = self.db.installment_plans(active_only=True)
        if not plans:
            empty = QLabel("No tenés planes de cuotas activos."); empty.setObjectName("Muted"); empty.setWordWrap(True); self.installment_layout.addWidget(empty)
        else:
            for plan in plans[:4]:
                total_n = max(1, int(plan.get("installments") or 1))
                current = int(plan.get("current_number") or max(0, int(plan.get("next_number") or 1) - 1)); current = min(total_n, max(0, current))
                pct = current / total_n * 100 if total_n else 0
                box = QFrame(); box.setObjectName("DashboardInstallmentRow")
                layout = QVBoxLayout(box); layout.setContentsMargins(8, 7, 8, 7); layout.setSpacing(5)
                top = QHBoxLayout(); name = QLabel(plan.get("description") or plan.get("category_name") or "Compra en cuotas"); name.setObjectName("TransactionTitle")
                amount = QLabel(self._fmt(float(plan.get("base_amount") or 0))); amount.setObjectName("TransactionAmountNegative")
                top.addWidget(name, 1); top.addWidget(amount); layout.addLayout(top)
                meta = QHBoxLayout(); info = QLabel(f"{current}/{total_n} · {plan.get('account_name','Tarjeta')}"); info.setObjectName("SmallMuted")
                percent = QLabel(f"{pct:.0f}%"); percent.setObjectName("InstallmentPercent")
                meta.addWidget(info); meta.addStretch(); meta.addWidget(percent); layout.addLayout(meta)
                layout.addWidget(BudgetProgress(pct)); self.installment_layout.addWidget(box)
        self._apply_responsive()

    def _apply_responsive(self):
        mode = responsive_mode(self.width(), self.height())
        compact = mode != "wide"
        if mode == self._responsive_mode:
            return
        self._responsive_mode = mode
        self._compact = compact
        direction = QBoxLayout.Direction.TopToBottom if compact else QBoxLayout.Direction.LeftToRight
        self.header_layout.setDirection(direction)
        self.overview_layout.setDirection(direction)
        self.charts_layout.setDirection(direction)
        self.bottom_layout.setDirection(direction)
        self.cat_body.setDirection(direction)
        self.metrics_layout.setDirection(QBoxLayout.Direction.TopToBottom if mode == "narrow" else QBoxLayout.Direction.LeftToRight)
        self.category_donut.setMaximumWidth(16777215 if compact else 235)
        self._render_wallets()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_responsive()

    def edit_transaction(self, txid=None):
        if not txid: return
        dlg = TransactionDialog(self.db, self.db.transaction(int(txid)), self)
        if dlg.exec(): self.db.update_transaction(int(txid), dlg.data()); self.refresh(); self.data_changed.emit()

    def add_transaction(self):
        dlg = TransactionDialog(self.db, parent=self)
        if dlg.exec():
            data = dlg.data(); self.db.add_transaction(data)
            try:
                y, m, _ = map(int, data["tx_date"].split("-")); self.current_year, self.current_month = y, m
            except Exception: pass
            self.refresh(); self.data_changed.emit()

    def previous_period(self):
        if self.current_month == 1: self.current_month = 12; self.current_year -= 1
        else: self.current_month -= 1
        self.refresh()

    def next_period(self):
        if self.current_month == 12: self.current_month = 1; self.current_year += 1
        else: self.current_month += 1
        self.refresh()

    def go_today(self):
        now = date.today(); self.current_year, self.current_month = now.year, now.month; self.refresh()
