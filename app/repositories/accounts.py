from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta
from typing import Any


class AccountsMixin:
    """Repositorio de dominio extraído de ``Database`` para reducir acoplamiento."""

    def accounts(self, include_archived: bool = False):
        where = "" if include_archived else "WHERE archived=0"
        with self.connect() as con:
            return self._rows(con.execute(f"SELECT * FROM accounts {where} ORDER BY archived, name COLLATE NOCASE").fetchall())

    def account(self, account_id: int):
        with self.connect() as con:
            row = con.execute("SELECT * FROM accounts WHERE id=?", (account_id,)).fetchone()
        return dict(row) if row else None

    def add_account(
        self, name: str, type_: str, opening_balance: float, color: str, include_in_balance: bool = True,
        credit_limit: float = 0, closing_day: int | None = None, due_day: int | None = None,
    ):
        if type_ == "Tarjeta":
            closing_day = int(closing_day or 1)
            due_day = int(due_day or 1)
            if not 1 <= closing_day <= 31 or not 1 <= due_day <= 31:
                raise ValueError("Cierre y vencimiento deben estar entre los días 1 y 31.")
        else:
            credit_limit, closing_day, due_day = 0, None, None
        with self.connect() as con:
            cur = con.execute(
                "INSERT INTO accounts(name,type,opening_balance,color,include_in_balance,credit_limit,closing_day,due_day) VALUES(?,?,?,?,?,?,?,?)",
                (name.strip(), type_, float(opening_balance), color, 1 if include_in_balance else 0, float(credit_limit or 0), closing_day, due_day),
            )
            return int(cur.lastrowid)

    def update_account(
        self, account_id: int, name: str, type_: str, opening_balance: float, color: str, include_in_balance: bool = True,
        credit_limit: float = 0, closing_day: int | None = None, due_day: int | None = None,
    ):
        if type_ == "Tarjeta":
            closing_day = int(closing_day or 1)
            due_day = int(due_day or 1)
            if not 1 <= closing_day <= 31 or not 1 <= due_day <= 31:
                raise ValueError("Cierre y vencimiento deben estar entre los días 1 y 31.")
        else:
            credit_limit, closing_day, due_day = 0, None, None
        with self.connect() as con:
            con.execute(
                "UPDATE accounts SET name=?,type=?,opening_balance=?,color=?,include_in_balance=?,credit_limit=?,closing_day=?,due_day=? WHERE id=?",
                (name.strip(), type_, float(opening_balance), color, 1 if include_in_balance else 0, float(credit_limit or 0), closing_day, due_day, account_id),
            )

    def set_account_balance_inclusion(self, account_id: int, included: bool):
        with self.connect() as con:
            con.execute(
                "UPDATE accounts SET include_in_balance=? WHERE id=?",
                (1 if included else 0, account_id),
            )

    def delete_account(self, account_id: int):
        with self.connect() as con:
            if con.execute("SELECT COUNT(*) FROM accounts WHERE archived=0").fetchone()[0] <= 1:
                raise ValueError("Necesitás conservar al menos una cuenta.")
            used = con.execute(
                "SELECT COUNT(*) FROM transactions WHERE account_id=? OR to_account_id=?", (account_id, account_id)
            ).fetchone()[0]
            recurring = con.execute(
                "SELECT COUNT(*) FROM recurring_transactions WHERE account_id=? OR to_account_id=?", (account_id, account_id)
            ).fetchone()[0]
            budgets = con.execute("SELECT COUNT(*) FROM budgets WHERE account_id=?", (account_id,)).fetchone()[0]
            adjustments = con.execute("SELECT COUNT(*) FROM account_adjustments WHERE account_id=?", (account_id,)).fetchone()[0]
            if used or recurring or budgets or adjustments:
                raise ValueError("La cuenta está en uso por movimientos, ajustes, presupuestos o recurrentes. Podés editarla, pero no eliminarla.")
            con.execute("DELETE FROM accounts WHERE id=?", (account_id,))

    def account_balance(self, account_id: int, reference: date | None = None) -> float:
        as_of = (reference or date.today()).isoformat()
        with self.connect() as con:
            row = con.execute(
                """
                SELECT a.opening_balance
                    + COALESCE(SUM(CASE WHEN t.kind='income' AND t.account_id=a.id THEN t.amount ELSE 0 END),0)
                    - COALESCE(SUM(CASE WHEN t.kind='expense' AND t.account_id=a.id THEN t.amount ELSE 0 END),0)
                    - COALESCE(SUM(CASE WHEN t.kind='transfer' AND t.account_id=a.id THEN t.amount ELSE 0 END),0)
                    + COALESCE(SUM(CASE WHEN t.kind='transfer' AND t.to_account_id=a.id THEN t.amount ELSE 0 END),0)
                    + COALESCE((
                        SELECT SUM(adj.amount)
                        FROM account_adjustments adj
                        WHERE adj.account_id=a.id
                          AND date(adj.adjustment_date) <= date(?)
                    ),0) AS balance
                FROM accounts a
                LEFT JOIN transactions t ON (t.account_id=a.id OR t.to_account_id=a.id)
                    AND date(t.tx_date) <= date(?)
                WHERE a.id=?
                GROUP BY a.id
                """,
                (as_of, as_of, account_id),
            ).fetchone()
        return float(row[0] or 0) if row else 0.0

    def add_account_adjustment(self, account_id: int, amount: float, adjustment_date: str,
                               description: str = "", adjustment_type: str = "manual") -> int:
        """Ajusta el saldo de una cuenta sin crear ingreso/gasto.

        Se usa, por ejemplo, cuando una tarjeta ya fue pagada con dinero que no
        queremos modelar como una de las cuentas de App Gastos. Un importe
        positivo reduce la deuda de una tarjeta porque aumenta su saldo.
        """
        if not self.account(int(account_id)):
            raise ValueError("La cuenta indicada no existe.")
        value = float(amount or 0)
        if value == 0:
            raise ValueError("El ajuste no puede ser cero.")
        adj_date = self._normalize_tx_date(adjustment_date)
        with self.connect() as con:
            cur = con.execute(
                """
                INSERT INTO account_adjustments(account_id,amount,adjustment_date,adjustment_type,description)
                VALUES(?,?,?,?,?)
                """,
                (int(account_id), value, adj_date, str(adjustment_type or "manual"), str(description or "").strip()),
            )
            return int(cur.lastrowid)

    def account_adjustments(self, account_id: int | None = None):
        sql = """
            SELECT adj.*, a.name AS account_name
            FROM account_adjustments adj
            JOIN accounts a ON a.id=adj.account_id
            WHERE 1=1
        """
        params: list[Any] = []
        if account_id is not None:
            sql += " AND adj.account_id=?"
            params.append(int(account_id))
        sql += " ORDER BY date(adj.adjustment_date) DESC, adj.id DESC"
        with self.connect() as con:
            return self._rows(con.execute(sql, params).fetchall())

    def accounts_with_balances(self):
        """Devuelve cuentas con su saldo económico actual.

        Las tarjetas de crédito representan pasivos, no activos. Históricamente
        algunas instalaciones guardaron un saldo inicial positivo en tarjetas
        (por ejemplo, un resumen importado o un valor de referencia). Ese valor
        positivo no debe aumentar el patrimonio: una tarjeta pagada aporta 0 y
        una tarjeta con deuda aporta un saldo negativo.
        """
        items = self.accounts()
        for item in items:
            raw_balance = self.account_balance(item["id"])
            if str(item.get("type") or "").casefold() == "tarjeta":
                item["balance"] = min(0.0, float(raw_balance))
                item["raw_balance"] = float(raw_balance)
            else:
                item["balance"] = float(raw_balance)
            item["include_in_balance"] = bool(item.get("include_in_balance", 1))
        return items

    def available_balance(self) -> float:
        """Saldo que el usuario decidió considerar disponible en el Dashboard."""
        return sum(
            float(x["balance"])
            for x in self.accounts_with_balances()
            if bool(x.get("include_in_balance", 1))
        )

    def excluded_balance(self) -> float:
        """Saldo de cuentas separadas (por ejemplo ahorros o inversiones)."""
        return sum(
            float(x["balance"])
            for x in self.accounts_with_balances()
            if not bool(x.get("include_in_balance", 1))
        )

    def net_worth(self) -> float:
        """Patrimonio conservador: activos positivos menos deuda de tarjetas.

        Un saldo operativo negativo en Efectivo/Billetera suele indicar que el
        usuario todavía no registró el origen de esos fondos y no representa un
        pasivo patrimonial real. Las tarjetas sí son deuda financiera y por eso
        sus saldos negativos reducen el patrimonio.
        """
        total = 0.0
        for account in self.accounts_with_balances():
            balance = float(account.get("balance") or 0)
            if str(account.get("type") or "").casefold() == "tarjeta":
                total += min(0.0, balance)
            else:
                total += max(0.0, balance)
        return total

    def total_balance(self):
        # Compatibilidad con las pantallas anteriores: desde v0.6 "total" significa
        # el saldo operativo/disponible, no el patrimonio completo.
        return self.available_balance()

    @staticmethod
    def _safe_month_day(year: int, month: int, day: int) -> date:
        return date(year, month, min(max(1, int(day or 1)), monthrange(year, month)[1]))

    @staticmethod
    def _shift_year_month(year: int, month: int, delta: int) -> tuple[int, int]:
        total = year * 12 + (month - 1) + delta
        y, m0 = divmod(total, 12)
        return y, m0 + 1

    def _card_due_for_close(self, close_date: date, due_day: int) -> date:
        # Si el vencimiento numéricamente cae después del cierre, suele ser en
        # el mismo mes. Si cae antes (ej. cierre 28 / vence 10), corresponde al siguiente.
        delta = 0 if int(due_day or 1) > close_date.day else 1
        y, m = self._shift_year_month(close_date.year, close_date.month, delta)
        return self._safe_month_day(y, m, int(due_day or 1))

    def card_overview(self, account_id: int, reference: date | None = None) -> dict[str, Any]:
        account = self.account(int(account_id))
        if not account or account.get("type") != "Tarjeta":
            return {}
        today = reference or date.today()
        closing_raw = account.get("closing_day")
        due_raw = account.get("due_day")
        configured = bool(closing_raw and due_raw)
        if configured:
            closing_day = int(closing_raw)
            due_day = int(due_raw)
            close_this = self._safe_month_day(today.year, today.month, closing_day)
            if today <= close_this:
                next_close = close_this
                py, pm = self._shift_year_month(today.year, today.month, -1)
                last_close = self._safe_month_day(py, pm, closing_day)
            else:
                last_close = close_this
                ny, nm = self._shift_year_month(today.year, today.month, 1)
                next_close = self._safe_month_day(ny, nm, closing_day)
            ppy, ppm = self._shift_year_month(last_close.year, last_close.month, -1)
            previous_close = self._safe_month_day(ppy, ppm, closing_day)
            current_start = last_close + timedelta(days=1)
            previous_start = previous_close + timedelta(days=1)
            last_due = self._card_due_for_close(last_close, due_day)
        else:
            # Tarjetas creadas en versiones viejas no tenían cierre/vencimiento.
            # Hasta que el usuario los configure usamos meses calendario, sin inventar días.
            current_start = date(today.year, today.month, 1)
            ny, nm = self._shift_year_month(today.year, today.month, 1)
            next_close = date(ny, nm, 1) - timedelta(days=1)
            py, pm = self._shift_year_month(today.year, today.month, -1)
            previous_start = date(py, pm, 1)
            last_close = current_start - timedelta(days=1)
            last_due = None
        balance = self.account_balance(int(account_id), today)
        debt = max(0.0, -float(balance))
        credit_limit = float(account.get("credit_limit") or 0)
        available_credit = max(0.0, credit_limit - debt) if credit_limit > 0 else 0.0
        with self.connect() as con:
            current_spent = float(con.execute(
                "SELECT COALESCE(SUM(amount),0) FROM transactions WHERE kind='expense' AND account_id=? AND date(tx_date) BETWEEN date(?) AND date(?)",
                (int(account_id), current_start.isoformat(), today.isoformat()),
            ).fetchone()[0] or 0)
            last_statement = float(con.execute(
                "SELECT COALESCE(SUM(amount),0) FROM transactions WHERE kind='expense' AND account_id=? AND date(tx_date) BETWEEN date(?) AND date(?)",
                (int(account_id), previous_start.isoformat(), last_close.isoformat()),
            ).fetchone()[0] or 0)
        return {
            "account": account,
            "configured": configured,
            "balance": balance,
            "debt": debt,
            "credit_balance": max(0.0, float(balance)),
            "credit_limit": credit_limit,
            "available_credit": available_credit,
            "current_start": current_start.isoformat(),
            "next_close": next_close.isoformat(),
            "last_statement_start": previous_start.isoformat(),
            "last_close": last_close.isoformat(),
            "last_due": last_due.isoformat() if last_due else None,
            "current_spent": current_spent,
            "last_statement": last_statement,
        }

    def card_statement_transactions(self, account_id: int, start_date: str, end_date: str):
        with self.connect() as con:
            rows = con.execute(
                """
                SELECT t.*, a.name AS account_name,
                       c.name AS category_name, p.name AS parent_category_name,
                       COALESCE(c.color,p.color,'#4CCFA9') AS category_effective_color,
                       COALESCE(c.icon,p.icon,'other') AS category_effective_icon
                FROM transactions t
                JOIN accounts a ON a.id=t.account_id
                LEFT JOIN categories c ON c.id=t.category_id
                LEFT JOIN categories p ON p.id=c.parent_id
                WHERE t.account_id=? AND t.kind='expense'
                  AND date(t.tx_date) BETWEEN date(?) AND date(?)
                ORDER BY date(t.tx_date) DESC, t.id DESC
                """,
                (int(account_id), str(start_date)[:10], str(end_date)[:10]),
            ).fetchall()
        out = self._rows(rows)
        for r in out:
            cat = r.get("category_name") or "Sin categoría"
            r["category_display"] = f"{r['parent_category_name']} / {cat}" if r.get("parent_category_name") else cat
            r["display"] = r.get("description") or r["category_display"]
        return out
