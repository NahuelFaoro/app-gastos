from __future__ import annotations

from datetime import date
from typing import Any

from ..utils import add_months, month_bounds
from ..amounts import decimal_amount, installment_amount


class TransactionsMixin:
    """Repositorio de dominio extraído de ``Database`` para reducir acoplamiento."""

    @staticmethod
    def _normalize_tx_date(value: Any) -> str:
        raw = str(value or "").strip()[:10]
        try:
            return date.fromisoformat(raw).isoformat()
        except Exception as exc:
            raise ValueError("La fecha del movimiento no es válida.") from exc

    def _validate_tx(self, data: dict[str, Any]):
        if data.get("kind") not in {"expense", "income", "transfer"}:
            raise ValueError("Tipo de movimiento inválido.")
        if decimal_amount(data.get("amount") or 0) <= 0:
            raise ValueError("El importe debe ser mayor a cero.")
        if not data.get("account_id"):
            raise ValueError("Seleccioná una cuenta.")
        self._normalize_tx_date(data.get("tx_date"))
        if data["kind"] == "transfer":
            if not data.get("to_account_id"):
                raise ValueError("Seleccioná la cuenta de destino.")
            if int(data["account_id"]) == int(data["to_account_id"]):
                raise ValueError("Origen y destino deben ser cuentas distintas.")
        elif not data.get("category_id"):
            raise ValueError("Seleccioná una categoría.")

    def add_transaction(self, data: dict[str, Any], recurring_id: int | None = None, source: str = "manual", external_id: str | None = None):
        data = {**data, "amount": float(decimal_amount(data.get("amount") or 0))}
        self._validate_tx(data)
        installments = int(data.get("installments") or 1)
        account = self.account(int(data["account_id"]))
        use_installments = (
            source == "manual" and data.get("kind") == "expense" and installments > 1
            and account and account.get("type") == "Tarjeta"
        )
        with self.connect() as con:
            if source in ('work_trip', 'work_extra') and external_id:
                con.execute('BEGIN IMMEDIATE')
                existing=con.execute('SELECT id FROM transactions WHERE source=? AND external_id=?',(source,external_id)).fetchone()
                if existing:
                    raise ValueError('Este registro ya tiene un ingreso en Movimientos. Editá ese ingreso para modificarlo.')
            if use_installments:
                purchase_date = date.fromisoformat(self._normalize_tx_date(data["tx_date"]))
                total_amount = float(data["amount"])
                base_amount = float(decimal_amount(decimal_amount(total_amount) / installments))
                if base_amount <= 0 or installment_amount(total_amount, base_amount, installments, installments) <= 0:
                    raise ValueError("El importe de la cuota no es válido.")
                next_date = add_months(purchase_date, 1, purchase_date.day)
                plan_cur = con.execute(
                    """
                    INSERT INTO card_installment_plans(account_id,category_id,total_amount,installments,base_amount,purchase_date,
                                                       next_installment_date,next_number,description,note,tags,active)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,1)
                    """,
                    (int(data["account_id"]), data.get("category_id"), total_amount, installments, base_amount, purchase_date.isoformat(),
                     next_date.isoformat(), 2, data.get("description", "").strip(), data.get("note", "").strip(), data.get("tags", "").strip()),
                )
                plan_id = int(plan_cur.lastrowid)
                cur = con.execute(
                    """
                    INSERT INTO transactions(kind,amount,account_id,to_account_id,category_id,tx_date,description,note,tags,recurring_id,source,external_id,
                                             installment_plan_id,installment_number,installment_total)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    ("expense", base_amount, int(data["account_id"]), None, data.get("category_id"), purchase_date.isoformat(),
                     data.get("description", "").strip(), data.get("note", "").strip(), data.get("tags", "").strip(), recurring_id,
                     "installment", external_id, plan_id, 1, installments),
                )
                return int(cur.lastrowid)

            cur = con.execute(
                """
                INSERT INTO transactions(kind,amount,account_id,to_account_id,category_id,tx_date,description,note,tags,recurring_id,source,external_id)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    data["kind"], float(data["amount"]), int(data["account_id"]), data.get("to_account_id"),
                    data.get("category_id"), self._normalize_tx_date(data["tx_date"]), data.get("description", "").strip(),
                    data.get("note", "").strip(), data.get("tags", "").strip(), recurring_id, source or "manual", external_id,
                ),
            )
            return int(cur.lastrowid)

    def update_transaction(self, tx_id: int, data: dict[str, Any]):
        data = {**data, "amount": float(decimal_amount(data.get("amount") or 0))}
        self._validate_tx(data)
        with self.connect() as con:
            con.execute(
                """
                UPDATE transactions SET kind=?,amount=?,account_id=?,to_account_id=?,category_id=?,tx_date=?,
                    description=?,note=?,tags=?,updated_at=CURRENT_TIMESTAMP WHERE id=?
                """,
                (
                    data["kind"], float(data["amount"]), int(data["account_id"]), data.get("to_account_id"),
                    data.get("category_id"), self._normalize_tx_date(data["tx_date"]), data.get("description", "").strip(),
                    data.get("note", "").strip(), data.get("tags", "").strip(), tx_id,
                ),
            )

    def transaction(self, tx_id: int):
        with self.connect() as con:
            row = con.execute("SELECT * FROM transactions WHERE id=?", (tx_id,)).fetchone()
        return dict(row) if row else None

    def delete_transaction(self, tx_id: int):
        with self.connect() as con:
            con.execute("DELETE FROM transactions WHERE id=?", (tx_id,))

    def duplicate_transaction(self, tx_id: int, new_date: str | None = None):
        tx = self.transaction(tx_id)
        if not tx:
            return None
        data = {k: tx[k] for k in ("kind", "amount", "account_id", "to_account_id", "category_id", "tx_date", "description", "note", "tags")}
        data["tx_date"] = new_date or date.today().isoformat()
        return self.add_transaction(data)

    def transactions(
        self, year: int | None = None, month: int | None = None, kind: str | None = None,
        account_id: int | None = None, category_id: int | None = None, search: str = "", limit: int | None = None,
        order_by: str = "date", date_from: str | None = None, date_to: str | None = None,
    ):
        sql = """
        SELECT t.*, a.name AS account_name, ta.name AS to_account_name,
               c.name AS category_name, c.color AS category_color, c.secondary_color AS category_secondary_color, c.icon AS category_icon,
               p.name AS parent_category_name, p.color AS parent_category_color, p.secondary_color AS parent_category_secondary_color, p.icon AS parent_category_icon
        FROM transactions t
        JOIN accounts a ON a.id=t.account_id
        LEFT JOIN accounts ta ON ta.id=t.to_account_id
        LEFT JOIN categories c ON c.id=t.category_id
        LEFT JOIN categories p ON p.id=c.parent_id
        WHERE 1=1
        """
        params: list[Any] = []
        if year:
            sql += " AND strftime('%Y',date(t.tx_date))=?"
            params.append(f"{int(year):04d}")
        if month:
            sql += " AND strftime('%m',date(t.tx_date))=?"
            params.append(f"{int(month):02d}")
        if date_from:
            sql += " AND date(t.tx_date)>=date(?)"
            params.append(str(date_from)[:10])
        if date_to:
            sql += " AND date(t.tx_date)<=date(?)"
            params.append(str(date_to)[:10])
        if kind and kind != "all":
            sql += " AND t.kind=?"
            params.append(kind)
        if account_id:
            sql += " AND (t.account_id=? OR t.to_account_id=?)"
            params += [account_id, account_id]
        if category_id:
            category_ids = self.category_descendant_ids(int(category_id), include_self=True)
            if category_ids:
                placeholders = ",".join("?" for _ in category_ids)
                sql += f" AND c.id IN ({placeholders})"
                params.extend(category_ids)
            else:
                sql += " AND c.id=?"
                params.append(int(category_id))
        if search.strip():
            q = f"%{search.strip()}%"
            sql += """ AND (
                LOWER(t.description) LIKE LOWER(?) OR LOWER(t.note) LIKE LOWER(?) OR LOWER(t.tags) LIKE LOWER(?)
                OR LOWER(COALESCE(c.name,'')) LIKE LOWER(?) OR LOWER(COALESCE(p.name,'')) LIKE LOWER(?)
                OR LOWER(a.name) LIKE LOWER(?) OR LOWER(COALESCE(ta.name,'')) LIKE LOWER(?)
            )"""
            params += [q] * 7
        if order_by == "created":
            sql += " ORDER BY datetime(t.created_at) DESC, t.id DESC"
        elif order_by == "updated":
            sql += " ORDER BY datetime(t.updated_at) DESC, t.id DESC"
        elif order_by == "amount_desc":
            sql += " ORDER BY t.amount DESC, date(t.tx_date) DESC, t.id DESC"
        elif order_by == "amount_asc":
            sql += " ORDER BY t.amount ASC, date(t.tx_date) DESC, t.id DESC"
        elif order_by == "date_asc":
            sql += " ORDER BY date(t.tx_date) ASC, t.id ASC"
        else:
            sql += " ORDER BY date(t.tx_date) DESC, t.id DESC"
        if limit:
            sql += f" LIMIT {int(limit)}"
        with self.connect() as con:
            rows = con.execute(sql, params).fetchall()
        result = self._rows(rows)
        category_map = {int(row["id"]): row for row in self.categories()} if result else {}
        for r in result:
            if r["kind"] == "transfer":
                r["category_display"] = "Transferencia"
                r["category_effective_color"] = "#4CCFA9"
                r["category_effective_icon"] = "transfer"
                r["display"] = r["description"] or f"{r['account_name']} → {r['to_account_name']}"
            else:
                category = category_map.get(int(r["category_id"])) if r.get("category_id") else None
                r["category_display"] = (category.get("path") if category else None) or (
                    f"{r['parent_category_name']} / {r['category_name']}" if r["parent_category_name"] else (r["category_name"] or "Sin categoría")
                )
                r["category_effective_color"] = (category.get("color") if category else None) or r.get("category_color") or r.get("parent_category_color") or "#94A3B8"
                r["category_secondary_color"] = (category.get("secondary_color") if category else None) or r.get("category_secondary_color")
                r["category_effective_icon"] = (category.get("icon") if category else None) or r.get("category_icon") or r.get("parent_category_icon") or "other"
                r["display"] = r["description"] or r["category_display"]
        return result

    def daily_totals(self, year: int, month: int):
        """Totales de ingreso/gasto y cantidad de movimientos para cada día del mes."""
        start, end = month_bounds(year, month)
        with self.connect() as con:
            rows = con.execute(
                """
                SELECT date(tx_date) AS tx_day,
                       COALESCE(SUM(CASE WHEN kind='income' THEN amount ELSE 0 END),0) AS income,
                       COALESCE(SUM(CASE WHEN kind='expense' THEN amount ELSE 0 END),0) AS expense,
                       COUNT(*) AS tx_count
                FROM transactions
                WHERE date(tx_date)>=date(?) AND date(tx_date)<date(?)
                GROUP BY date(tx_date)
                ORDER BY date(tx_date)
                """,
                (start.isoformat(), end.isoformat()),
            ).fetchall()
        return {
            row["tx_day"]: {
                "income": float(row["income"] or 0),
                "expense": float(row["expense"] or 0),
                "net": float(row["income"] or 0) - float(row["expense"] or 0),
                "count": int(row["tx_count"] or 0),
            }
            for row in rows
        }

    def transactions_for_day(self, iso_date: str):
        """Movimientos de un día contable específico."""
        try:
            target = date.fromisoformat(str(iso_date)[:10]).isoformat()
        except Exception:
            return []
        y, m, _ = map(int, target.split("-"))
        return [row for row in self.transactions(year=y, month=m) if row.get("tx_date") == target]

    def recent_transactions(self, limit: int = 8):
        """Últimas operaciones registradas, independientemente de la fecha contable.

        Es importante cuando hoy cargás un gasto de hace varios días: aparece en
        Actividad reciente, pero se contabiliza en el período de tx_date.
        """
        return self.transactions(limit=limit, order_by="created")

    def filtered_totals(self, **filters):
        rows = self.transactions(**filters)
        income = sum(float(x["amount"]) for x in rows if x["kind"] == "income")
        expense = sum(float(x["amount"]) for x in rows if x["kind"] == "expense")
        return {"income": income, "expense": expense, "net": income - expense, "count": len(rows)}
