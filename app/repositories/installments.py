from __future__ import annotations

from calendar import monthrange
from datetime import date

from ..utils import add_months
from ..amounts import decimal_amount, installment_amount


class InstallmentsMixin:
    """Repositorio de dominio extraído de ``Database`` para reducir acoplamiento."""

    def installment_plans(self, account_id: int | None = None, active_only: bool = False):
        """Planes con estadísticas agregadas en una sola consulta.

        v0.18 hacía tres subconsultas correlacionadas por cada tarjeta. Con
        muchos planes eso se notaba al navegar. El agregado previo evita ese
        costo y además devuelve icono/color efectivos de la categoría.
        """
        where = ["1=1"]; params=[]
        if account_id is not None:
            where.append("p.account_id=?"); params.append(int(account_id))
        if active_only:
            where.append("p.active=1")
        with self.connect() as con:
            rows = con.execute(
                f"""
                SELECT p.*, a.name AS account_name,
                       c.name AS category_name, pc.name AS parent_category_name,
                       COALESCE(c.icon,pc.icon,'card') AS category_icon,
                       COALESCE(c.color,pc.color,a.color,'#4CCFA9') AS category_color,
                       COALESCE(s.registered_amount,0) AS registered_amount,
                       COALESCE(s.registered_count,0) AS registered_count,
                       COALESCE(s.current_number,0) AS current_number
                FROM card_installment_plans p
                JOIN accounts a ON a.id=p.account_id
                LEFT JOIN categories c ON c.id=p.category_id
                LEFT JOIN categories pc ON pc.id=c.parent_id
                LEFT JOIN (
                    SELECT installment_plan_id,
                           SUM(amount) registered_amount,
                           COUNT(*) registered_count,
                           MAX(COALESCE(installment_number,0)) current_number
                    FROM transactions
                    WHERE installment_plan_id IS NOT NULL
                    GROUP BY installment_plan_id
                ) s ON s.installment_plan_id=p.id
                WHERE {' AND '.join(where)}
                ORDER BY p.active DESC, date(p.next_installment_date), p.id DESC
                """, params
            ).fetchall()
        result = self._rows(rows)
        category_map = {int(row["id"]): row for row in self.categories()} if result else {}
        for row in result:
            category = category_map.get(int(row["category_id"])) if row.get("category_id") else None
            if category:
                row["category_name"] = category.get("path") or category.get("name")
                row["category_icon"] = category.get("icon") or row.get("category_icon") or "card"
                row["category_color"] = category.get("color") or row.get("category_color") or "#4CCFA9"
                row["category_secondary_color"] = category.get("secondary_color")
            else:
                row["category_secondary_color"] = None
        return result

    def installment_monthly_commitments(self, start_year: int | None = None, start_month: int | None = None, months: int = 12):
        """Devuelve el compromiso de cuotas agrupado por mes.

        Se reconstruye el calendario completo de cada plan a partir de su fecha
        de compra/inicio. Esto permite ver tanto cuotas ya registradas como las
        futuras, incluso cuando el plan fue incorporado a App Gastos a mitad de
        camino (por ejemplo 7/12).
        """
        today = date.today()
        start_year = int(start_year or today.year)
        start_month = int(start_month or today.month)
        months = max(1, min(int(months or 12), 36))
        start = date(start_year, start_month, 1)
        end = add_months(start, months - 1, 1)

        buckets = {}
        cursor = start
        for _ in range(months):
            key = (cursor.year, cursor.month)
            buckets[key] = {
                "year": cursor.year, "month": cursor.month, "total": 0.0,
                "count": 0, "items": [],
            }
            cursor = add_months(cursor, 1, 1)

        for plan in self.installment_plans(active_only=False):
            total = max(1, int(plan.get("installments") or 1))
            base = float(plan.get("base_amount") or 0)
            total_amount = float(plan.get("total_amount") or base * total)
            try:
                purchase = date.fromisoformat(str(plan.get("purchase_date") or "")[:10])
            except Exception:
                continue
            for n in range(1, total + 1):
                due = add_months(purchase, n - 1, purchase.day)
                if due < start or due > date(end.year, end.month, monthrange(end.year, end.month)[1]):
                    continue
                key = (due.year, due.month)
                if key not in buckets:
                    continue
                amount = installment_amount(total_amount, base, total, n)
                item = {
                    "plan_id": int(plan["id"]),
                    "description": plan.get("description") or plan.get("category_name") or "Compra en cuotas",
                    "account_name": plan.get("account_name") or "Tarjeta",
                    "category_name": plan.get("category_name"),
                    "parent_category_name": plan.get("parent_category_name"),
                    "category_icon": plan.get("category_icon") or "card",
                    "category_color": plan.get("category_color") or "#4CCFA9",
                    "category_secondary_color": plan.get("category_secondary_color"),
                    "installment_number": n,
                    "installment_total": total,
                    "amount": round(amount, 2),
                    "due_date": due.isoformat(),
                    "active": bool(plan.get("active")),
                }
                buckets[key]["items"].append(item)
                buckets[key]["total"] = float(decimal_amount(buckets[key]["total"]) + decimal_amount(amount))
                buckets[key]["count"] += 1

        result = []
        for data in buckets.values():
            data["total"] = round(float(data["total"]), 2)
            data["items"].sort(key=lambda x: (-float(x["amount"]), x["description"].lower()))
            result.append(data)
        return result

    def installment_transactions(self, plan_id: int):
        """Movimientos reales asociados a un plan, ordenados por número de cuota."""
        with self.connect() as con:
            rows = con.execute(
                """
                SELECT t.*, a.name AS account_name, c.name AS category_name, p.name AS parent_category_name
                FROM transactions t
                JOIN accounts a ON a.id=t.account_id
                LEFT JOIN categories c ON c.id=t.category_id
                LEFT JOIN categories p ON p.id=c.parent_id
                WHERE t.installment_plan_id=?
                ORDER BY COALESCE(t.installment_number,0), date(t.tx_date), t.id
                """,
                (int(plan_id),),
            ).fetchall()
        return self._rows(rows)

    def process_due_installments(self, through: date | None = None, max_generated: int = 500):
        through = through or date.today()
        generated = 0
        with self.connect() as con:
            rows = con.execute(
                "SELECT * FROM card_installment_plans WHERE active=1 AND date(next_installment_date)<=date(?) ORDER BY date(next_installment_date),id",
                (through.isoformat(),),
            ).fetchall()
            for row in rows:
                p = dict(row)
                next_date = date.fromisoformat(p["next_installment_date"])
                number = int(p["next_number"])
                total = int(p["installments"])
                while next_date <= through and number <= total and generated < max_generated:
                    amount = installment_amount(p["total_amount"], p["base_amount"], total, number)
                    con.execute(
                        """
                        INSERT INTO transactions(kind,amount,account_id,category_id,tx_date,description,note,tags,source,
                                                 installment_plan_id,installment_number,installment_total)
                        VALUES('expense',?,?,?,?,?,?,?,'installment',?,?,?)
                        """,
                        (amount, p["account_id"], p["category_id"], next_date.isoformat(), p["description"], p["note"], p["tags"], p["id"], number, total),
                    )
                    generated += 1
                    number += 1
                    next_date = add_months(next_date, 1, date.fromisoformat(p["purchase_date"]).day)
                active = 1 if number <= total else 0
                con.execute(
                    "UPDATE card_installment_plans SET next_number=?,next_installment_date=?,active=? WHERE id=?",
                    (number, next_date.isoformat(), active, p["id"]),
                )
        return generated

    def cancel_installment_plan(self, plan_id: int):
        with self.connect() as con:
            con.execute("UPDATE card_installment_plans SET active=0 WHERE id=?", (int(plan_id),))

    def installment_plan(self, plan_id: int):
        rows = self.installment_plans()
        return next((r for r in rows if int(r["id"]) == int(plan_id)), None)

    def latest_installment_transaction(self, plan_id: int):
        with self.connect() as con:
            row = con.execute(
                """
                SELECT * FROM transactions
                WHERE installment_plan_id=?
                ORDER BY COALESCE(installment_number,0) DESC, date(tx_date) DESC, id DESC
                LIMIT 1
                """,
                (int(plan_id),),
            ).fetchone()
        return dict(row) if row else None

    def installment_anchor_transaction(self, plan_id: int):
        """Devuelve el movimiento que originó el plan, no la última cuota auto-generada.

        Priorizamos un movimiento con external_id (por ejemplo uno leído de un
        resumen) y después el número de cuota más bajo. Esto permite corregir
        un plan 7/12 aunque v0.18 haya generado 8/12…12/12 automáticamente.
        """
        with self.connect() as con:
            row = con.execute(
                """
                SELECT * FROM transactions
                WHERE installment_plan_id=?
                ORDER BY CASE WHEN external_id IS NOT NULL AND external_id<>'' THEN 0 ELSE 1 END,
                         COALESCE(installment_number,9999), id
                LIMIT 1
                """,
                (int(plan_id),),
            ).fetchone()
        return dict(row) if row else None

    def configure_existing_installment(self, tx_id: int, current_installment: int, total_installments: int,
                                       card_account_id: int, current_date: date | str | None = None):
        """Marca/corrige un gasto como cuota N/T y reconstruye sólo lo automático.

        Si el plan ya tenía cuotas posteriores generadas por App Gastos, ahora
        se pueden retroceder/corregir: esas cuotas automáticas se eliminan y se
        recalcula el plan desde la cuota elegida. Nunca borramos una cuota
        posterior que tenga external_id, porque podría provenir de un documento
        o integración real y requiere intervención explícita.
        """
        tx = self.transaction(int(tx_id))
        if not tx:
            raise ValueError("No se encontró el movimiento.")
        if tx.get("kind") != "expense":
            raise ValueError("Solo los gastos pueden convertirse en compras en cuotas.")
        card = self.account(int(card_account_id))
        if not card or card.get("type") != "Tarjeta":
            raise ValueError("Seleccioná una cuenta de tipo Tarjeta.")
        total = int(total_installments)
        current = int(current_installment)
        if total < 2 or current < 1 or current > total:
            raise ValueError("La relación de cuotas no es válida.")
        amount = float(tx.get("amount") or 0)
        if amount <= 0:
            raise ValueError("El importe de la cuota debe ser mayor a cero.")
        effective_date = date.fromisoformat(
            self._normalize_tx_date(current_date if current_date is not None else tx.get("tx_date"))
        )
        purchase_date = add_months(effective_date, -(current - 1), effective_date.day)
        next_date = add_months(effective_date, 1, effective_date.day)
        active = 1 if current < total else 0
        plan_id = tx.get("installment_plan_id")

        with self.connect() as con:
            if plan_id:
                # Al corregir un plan podemos quitar cuotas que la propia app
                # generó después del ancla. Las importadas/manualmente
                # identificables no se tocan silenciosamente.
                later = con.execute(
                    """
                    SELECT id,installment_number,external_id
                    FROM transactions
                    WHERE installment_plan_id=? AND id<>?
                      AND COALESCE(installment_number,0)>?
                    ORDER BY installment_number,id
                    """,
                    (int(plan_id), int(tx_id), current),
                ).fetchall()
                protected = [r for r in later if str(r["external_id"] or "").strip()]
                if protected:
                    raise ValueError(
                        "Hay cuotas posteriores importadas o identificadas como reales. "
                        "Eliminá o desvinculá esas cuotas antes de retroceder el plan."
                    )
                if later:
                    con.executemany("DELETE FROM transactions WHERE id=?", [(int(r["id"]),) for r in later])
                con.execute(
                    """
                    UPDATE card_installment_plans
                    SET account_id=?, category_id=?, total_amount=?, installments=?, base_amount=?, purchase_date=?,
                        next_installment_date=?, next_number=?, description=?, note=?, tags=?, active=?
                    WHERE id=?
                    """,
                    (
                        int(card_account_id), tx.get("category_id"), float(decimal_amount(amount) * total), total, amount,
                        purchase_date.isoformat(), next_date.isoformat(), current + 1,
                        tx.get("description", ""), tx.get("note", ""), tx.get("tags", ""), active, int(plan_id),
                    ),
                )
                con.execute(
                    "UPDATE transactions SET installment_total=? WHERE installment_plan_id=?",
                    (total, int(plan_id)),
                )
            else:
                cur = con.execute(
                    """
                    INSERT INTO card_installment_plans(account_id,category_id,total_amount,installments,base_amount,purchase_date,
                                                       next_installment_date,next_number,description,note,tags,active)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        int(card_account_id), tx.get("category_id"), float(decimal_amount(amount) * total), total, amount,
                        purchase_date.isoformat(), next_date.isoformat(), current + 1,
                        tx.get("description", ""), tx.get("note", ""), tx.get("tags", ""), active,
                    ),
                )
                plan_id = int(cur.lastrowid)

            con.execute(
                """
                UPDATE transactions
                SET account_id=?, tx_date=?, source='installment', installment_plan_id=?, installment_number=?, installment_total=?,
                    updated_at=CURRENT_TIMESTAMP
                WHERE id=?
                """,
                (int(card_account_id), effective_date.isoformat(), int(plan_id), current, total, int(tx_id)),
            )
        return int(plan_id)

    def remove_installment_plan(self, plan_id: int, delete_movements: bool = False):
        """Elimina un plan incorrecto de forma explícita.

        delete_movements=False conserva el gasto ancla y cualquier movimiento
        importado real, pero elimina cuotas futuras auto-generadas y les quita
        la metadata de cuotas. delete_movements=True borra todos los gastos del
        plan y marca las importaciones vinculadas como ignoradas.
        """
        plan_id = int(plan_id)
        with self.connect() as con:
            txs = self._rows(con.execute(
                "SELECT id,external_id FROM transactions WHERE installment_plan_id=? ORDER BY id",
                (plan_id,),
            ).fetchall())
            ids = [int(r["id"]) for r in txs]
            if delete_movements:
                if ids:
                    marks = ",".join("?" for _ in ids)
                    con.execute(
                        f"UPDATE imported_movements SET status='ignored',transaction_id=NULL WHERE transaction_id IN ({marks})",
                        ids,
                    )
                    con.execute(f"DELETE FROM transactions WHERE id IN ({marks})", ids)
            else:
                anchor = con.execute(
                    """
                    SELECT id FROM transactions WHERE installment_plan_id=?
                    ORDER BY CASE WHEN external_id IS NOT NULL AND external_id<>'' THEN 0 ELSE 1 END,
                             COALESCE(installment_number,9999), id
                    LIMIT 1
                    """,
                    (plan_id,),
                ).fetchone()
                anchor_id = int(anchor["id"]) if anchor else (ids[0] if ids else None)
                # Cuotas auto-generadas posteriores no representan una compra
                # independiente cuando se elimina el plan.
                if anchor_id is not None:
                    con.execute(
                        "DELETE FROM transactions WHERE installment_plan_id=? AND id<>? AND (external_id IS NULL OR external_id='')",
                        (plan_id, anchor_id),
                    )
                remaining = self._rows(con.execute(
                    "SELECT id FROM transactions WHERE installment_plan_id=?", (plan_id,)
                ).fetchall())
                for row in remaining:
                    tid = int(row["id"])
                    source_row = con.execute(
                        "SELECT source FROM imported_movements WHERE transaction_id=? ORDER BY id DESC LIMIT 1", (tid,)
                    ).fetchone()
                    restored_source = source_row[0] if source_row and source_row[0] else "manual"
                    con.execute(
                        """
                        UPDATE transactions
                        SET installment_plan_id=NULL,installment_number=NULL,installment_total=NULL,
                            source=?,updated_at=CURRENT_TIMESTAMP
                        WHERE id=?
                        """,
                        (restored_source, tid),
                    )
            con.execute("DELETE FROM card_installment_plans WHERE id=?", (plan_id,))
        return len(ids)
