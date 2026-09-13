from __future__ import annotations

from datetime import date
from typing import Any

from ..utils import advance_recurrence, month_bounds


class PlanningMixin:
    """Repositorio de dominio extraído de ``Database`` para reducir acoplamiento."""

    def budgets(self, include_inactive: bool = False):
        where = "" if include_inactive else "WHERE b.active=1"
        with self.connect() as con:
            rows = con.execute(
                f"""
                SELECT b.*, a.name AS account_name, c.name AS category_name, p.name AS parent_category_name
                FROM budgets b
                LEFT JOIN accounts a ON a.id=b.account_id
                LEFT JOIN categories c ON c.id=b.category_id
                LEFT JOIN categories p ON p.id=c.parent_id
                {where}
                ORDER BY b.active DESC,b.name COLLATE NOCASE
                """
            ).fetchall()
        return self._rows(rows)

    def budget(self, budget_id: int):
        with self.connect() as con:
            row = con.execute("SELECT * FROM budgets WHERE id=?", (budget_id,)).fetchone()
        return dict(row) if row else None

    def add_budget(self, data: dict[str, Any]):
        with self.connect() as con:
            cur = con.execute(
                "INSERT INTO budgets(name,amount,category_id,account_id,start_date,active) VALUES(?,?,?,?,?,1)",
                (data["name"].strip(), float(data["amount"]), data.get("category_id"), data.get("account_id"), data["start_date"]),
            )
            return int(cur.lastrowid)

    def update_budget(self, budget_id: int, data: dict[str, Any]):
        with self.connect() as con:
            con.execute(
                "UPDATE budgets SET name=?,amount=?,category_id=?,account_id=?,start_date=? WHERE id=?",
                (data["name"].strip(), float(data["amount"]), data.get("category_id"), data.get("account_id"), data["start_date"], budget_id),
            )

    def delete_budget(self, budget_id: int):
        with self.connect() as con:
            con.execute("DELETE FROM budgets WHERE id=?", (budget_id,))

    def budget_spent(self, budget: dict[str, Any], year: int, month: int):
        start, end = month_bounds(year, month)
        sql = """
            SELECT COALESCE(SUM(t.amount),0)
            FROM transactions t
            LEFT JOIN categories c ON c.id=t.category_id
            WHERE t.kind='expense' AND date(t.tx_date)>=date(?) AND date(t.tx_date)<date(?)
        """
        params: list[Any] = [start.isoformat(), end.isoformat()]
        if budget.get("account_id"):
            sql += " AND t.account_id=?"
            params.append(budget["account_id"])
        if budget.get("category_id"):
            category_ids = self.category_descendant_ids(int(budget["category_id"]), include_self=True)
            if category_ids:
                placeholders = ",".join("?" for _ in category_ids)
                sql += f" AND c.id IN ({placeholders})"
                params.extend(category_ids)
            else:
                sql += " AND c.id=?"
                params.append(int(budget["category_id"]))
        with self.connect() as con:
            return float(con.execute(sql, params).fetchone()[0] or 0)

    def budget_status(self, year: int, month: int):
        _, end = month_bounds(year, month)
        rows = []
        for b in self.budgets():
            if date.fromisoformat(b["start_date"]) >= end:
                continue
            spent = self.budget_spent(b, year, month)
            amount = float(b["amount"])
            rows.append({**b, "spent": spent, "remaining": amount - spent, "progress": (spent / amount * 100) if amount else 0})
        return rows

    def recurring(self, include_inactive: bool = True):
        where = "" if include_inactive else "WHERE r.active=1"
        with self.connect() as con:
            rows = con.execute(
                f"""
                SELECT r.*, a.name account_name, ta.name to_account_name, c.name category_name, c.icon category_icon, c.color category_color,
                       p.name parent_category_name, p.icon parent_category_icon, p.color parent_category_color
                FROM recurring_transactions r
                JOIN accounts a ON a.id=r.account_id
                LEFT JOIN accounts ta ON ta.id=r.to_account_id
                LEFT JOIN categories c ON c.id=r.category_id
                LEFT JOIN categories p ON p.id=c.parent_id
                {where}
                ORDER BY r.active DESC,r.next_date,r.id
                """
            ).fetchall()
        result = self._rows(rows)
        category_map = {int(row["id"]): row for row in self.categories()} if result else {}
        for r in result:
            if r["kind"] == "transfer":
                r["category_display"] = f"{r['account_name']} → {r['to_account_name']}"
                r["category_effective_icon"] = "transfer"
                r["category_effective_color"] = "#4CCFA9"
                r["category_secondary_color"] = None
            else:
                category = category_map.get(int(r["category_id"])) if r.get("category_id") else None
                r["category_display"] = (category.get("path") if category else None) or (
                    f"{r['parent_category_name']} / {r['category_name']}" if r["parent_category_name"] else (r["category_name"] or "")
                )
                r["category_effective_icon"] = (category.get("icon") if category else None) or r.get("category_icon") or r.get("parent_category_icon") or "other"
                r["category_effective_color"] = (category.get("color") if category else None) or r.get("category_color") or r.get("parent_category_color") or "#4CCFA9"
                r["category_secondary_color"] = (category.get("secondary_color") if category else None)
        return result

    def recurring_item(self, recurring_id: int):
        with self.connect() as con:
            row = con.execute("SELECT * FROM recurring_transactions WHERE id=?", (recurring_id,)).fetchone()
        return dict(row) if row else None

    def add_recurring(self, data: dict[str, Any]):
        self._validate_tx(data)
        next_date = date.fromisoformat(data["next_date"])
        with self.connect() as con:
            cur = con.execute(
                """
                INSERT INTO recurring_transactions(kind,amount,account_id,to_account_id,category_id,description,note,tags,
                    frequency,interval_value,next_date,anchor_day,active)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,1)
                """,
                (
                    data["kind"], float(data["amount"]), data["account_id"], data.get("to_account_id"), data.get("category_id"),
                    data.get("description", "").strip(), data.get("note", "").strip(), data.get("tags", "").strip(),
                    data["frequency"], int(data.get("interval_value") or 1), data["next_date"], next_date.day,
                ),
            )
            return int(cur.lastrowid)

    def update_recurring(self, recurring_id: int, data: dict[str, Any]):
        self._validate_tx(data)
        next_date = date.fromisoformat(data["next_date"])
        with self.connect() as con:
            con.execute(
                """
                UPDATE recurring_transactions SET kind=?,amount=?,account_id=?,to_account_id=?,category_id=?,description=?,note=?,tags=?,
                    frequency=?,interval_value=?,next_date=?,anchor_day=? WHERE id=?
                """,
                (
                    data["kind"], float(data["amount"]), data["account_id"], data.get("to_account_id"), data.get("category_id"),
                    data.get("description", "").strip(), data.get("note", "").strip(), data.get("tags", "").strip(),
                    data["frequency"], int(data.get("interval_value") or 1), data["next_date"], next_date.day, recurring_id,
                ),
            )

    def toggle_recurring(self, recurring_id: int):
        with self.connect() as con:
            con.execute("UPDATE recurring_transactions SET active=CASE active WHEN 1 THEN 0 ELSE 1 END WHERE id=?", (recurring_id,))

    def delete_recurring(self, recurring_id: int):
        with self.connect() as con:
            con.execute("DELETE FROM recurring_transactions WHERE id=?", (recurring_id,))

    def process_due_recurring(self, through: date | None = None, max_generated: int = 500):
        through = through or date.today()
        generated = 0
        with self.connect() as con:
            rows = con.execute(
                "SELECT * FROM recurring_transactions WHERE active=1 AND next_date<=? ORDER BY next_date,id",
                (through.isoformat(),),
            ).fetchall()
            for row in rows:
                r = dict(row)
                next_date = date.fromisoformat(r["next_date"])
                while next_date <= through and generated < max_generated:
                    con.execute(
                        """
                        INSERT INTO transactions(kind,amount,account_id,to_account_id,category_id,tx_date,description,note,tags,recurring_id)
                        VALUES(?,?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            r["kind"], r["amount"], r["account_id"], r["to_account_id"], r["category_id"], next_date.isoformat(),
                            r["description"], r["note"], r["tags"], r["id"],
                        ),
                    )
                    generated += 1
                    next_date = advance_recurrence(next_date, r["frequency"], r["interval_value"], r["anchor_day"])
                con.execute("UPDATE recurring_transactions SET next_date=? WHERE id=?", (next_date.isoformat(), r["id"]))
        return generated
