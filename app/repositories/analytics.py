from __future__ import annotations

from calendar import monthrange
from datetime import date
from typing import Any

from ..constants import CATEGORY_COLORS
from ..utils import month_bounds, previous_month


class AnalyticsMixin:
    """Repositorio de dominio extraído de ``Database`` para reducir acoplamiento."""

    @staticmethod
    def _full_months_inside(start: date, end: date) -> list[tuple[int, int]]:
        if end < start:
            start, end = end, start
        months: list[tuple[int, int]] = []
        y, m = start.year, start.month
        while (y, m) <= (end.year, end.month):
            first = date(y, m, 1)
            last = date(y, m, monthrange(y, m)[1])
            if first >= start and last <= end:
                months.append((y, m))
            if m == 12:
                y, m = y + 1, 1
            else:
                m += 1
        return months

    def period_summary(self, start_date: date | str, end_date: date | str, include_history: bool = True):
        start = date.fromisoformat(str(start_date)[:10]) if not isinstance(start_date, date) else start_date
        end = date.fromisoformat(str(end_date)[:10]) if not isinstance(end_date, date) else end_date
        if end < start:
            start, end = end, start
        with self.connect() as con:
            row = con.execute(
                """
                SELECT COALESCE(SUM(CASE WHEN kind='income' THEN amount ELSE 0 END),0) income,
                       COALESCE(SUM(CASE WHEN kind='expense' THEN amount ELSE 0 END),0) expense,
                       SUM(CASE WHEN kind='income' THEN 1 ELSE 0 END) income_count,
                       SUM(CASE WHEN kind='expense' THEN 1 ELSE 0 END) expense_count
                FROM transactions WHERE date(tx_date)>=date(?) AND date(tx_date)<=date(?)
                """,
                (start.isoformat(), end.isoformat()),
            ).fetchone()
        real_income = float(row["income"] or 0)
        real_expense = float(row["expense"] or 0)
        hist_income = hist_expense = 0.0
        full_months = self._full_months_inside(start, end) if include_history else []
        if full_months:
            clauses = " OR ".join("(year=? AND month=?)" for _ in full_months)
            params: list[Any] = []
            for y, m in full_months:
                params.extend([y, m])
            with self.connect() as con:
                h = con.execute(
                    f"""
                    SELECT COALESCE(SUM(CASE WHEN kind='income' THEN amount ELSE 0 END),0) income,
                           COALESCE(SUM(CASE WHEN kind='expense' THEN amount ELSE 0 END),0) expense
                    FROM historical_monthly WHERE {clauses}
                    """,
                    params,
                ).fetchone()
            hist_income = float(h["income"] or 0)
            hist_expense = float(h["expense"] or 0)
        income = real_income + hist_income
        expense = real_expense + hist_expense
        return {
            "income": income, "expense": expense, "net": income - expense,
            "real_income": real_income, "real_expense": real_expense,
            "history_income": hist_income, "history_expense": hist_expense,
            "income_count": int(row["income_count"] or 0), "expense_count": int(row["expense_count"] or 0),
            "history_months": full_months,
        }

    def category_totals_period(self, kind: str, start_date: date | str, end_date: date | str, include_history: bool = True):
        """Totales del primer nivel de la jerarquía para un período."""
        start = date.fromisoformat(str(start_date)[:10]) if not isinstance(start_date, date) else start_date
        end = date.fromisoformat(str(end_date)[:10]) if not isinstance(end_date, date) else end_date
        if end < start:
            start, end = end, start
        with self.connect() as con:
            live = self._rows(con.execute(
                """
                WITH RECURSIVE tree(id,root_id) AS (
                    SELECT id,id FROM categories WHERE parent_id IS NULL
                    UNION ALL
                    SELECT c.id,tree.root_id FROM categories c JOIN tree ON c.parent_id=tree.id
                )
                SELECT COALESCE(root.id,c.id,0) category_id,
                       COALESCE(root.name,c.name,'Sin categoría') category,
                       COALESCE(root.color,c.color,'#94A3B8') color,
                       CASE WHEN root.id IS NOT NULL THEN root.secondary_color ELSE c.secondary_color END secondary_color,
                       COALESCE(root.icon,c.icon,'other') icon,
                       SUM(t.amount) total,COUNT(*) tx_count
                FROM transactions t
                LEFT JOIN categories c ON c.id=t.category_id
                LEFT JOIN tree ON tree.id=c.id
                LEFT JOIN categories root ON root.id=tree.root_id
                WHERE t.kind=? AND date(t.tx_date)>=date(?) AND date(t.tx_date)<=date(?)
                GROUP BY COALESCE(root.id,c.id,0),COALESCE(root.name,c.name,'Sin categoría'),
                         COALESCE(root.color,c.color,'#94A3B8'),CASE WHEN root.id IS NOT NULL THEN root.secondary_color ELSE c.secondary_color END,COALESCE(root.icon,c.icon,'other')
                """,
                (kind, start.isoformat(), end.isoformat()),
            ).fetchall())
        merged: dict[str, dict[str, Any]] = {}
        for row in live:
            key = f"id:{row['category_id']}" if row.get("category_id") else "name:" + self._norm_name(row["category"])
            merged[key] = {
                "category_id": row.get("category_id"), "category": row["category"], "color": row["color"],
                "secondary_color": row.get("secondary_color"), "icon": row["icon"],
                "total": float(row["total"] or 0), "real_total": float(row["total"] or 0), "history_total": 0.0,
                "tx_count": int(row["tx_count"] or 0), "history_rows": 0,
            }

        full_months = self._full_months_inside(start, end) if include_history else []
        if full_months:
            clauses = " OR ".join("(h.year=? AND h.month=?)" for _ in full_months)
            params: list[Any] = [kind]
            for y, m in full_months:
                params.extend([y, m])
            with self.connect() as con:
                history = self._rows(con.execute(
                    f"""
                    WITH RECURSIVE tree(id,root_id) AS (
                        SELECT id,id FROM categories WHERE parent_id IS NULL
                        UNION ALL
                        SELECT c.id,tree.root_id FROM categories c JOIN tree ON c.parent_id=tree.id
                    )
                    SELECT COALESCE(root.id,c.id,h.category_id) category_id,
                           COALESCE(root.name,c.name,h.category_name) category_name,
                           SUM(h.amount) total,COUNT(*) row_count,
                           COALESCE(root.color,c.color) color,
                           CASE WHEN root.id IS NOT NULL THEN root.secondary_color ELSE c.secondary_color END secondary_color,
                           COALESCE(root.icon,c.icon) icon
                    FROM historical_monthly h
                    LEFT JOIN categories c ON c.id=h.category_id
                    LEFT JOIN tree ON tree.id=c.id
                    LEFT JOIN categories root ON root.id=tree.root_id
                    WHERE h.kind=? AND ({clauses})
                    GROUP BY COALESCE(root.id,c.id,h.category_id),COALESCE(root.name,c.name,h.category_name),
                             COALESCE(root.color,c.color),CASE WHEN root.id IS NOT NULL THEN root.secondary_color ELSE c.secondary_color END,COALESCE(root.icon,c.icon)
                    """,
                    params,
                ).fetchall())
            for row in history:
                cid = row.get("category_id")
                display = row.get("category_name") or "Historial"
                key = f"id:{cid}" if cid else "name:" + self._norm_name(display)
                if key not in merged:
                    idx = abs(hash(display)) % len(CATEGORY_COLORS)
                    merged[key] = {
                        "category_id": cid, "category": display,
                        "color": row.get("color") or CATEGORY_COLORS[idx], "secondary_color": row.get("secondary_color"),
                        "icon": row.get("icon") or "other", "total": 0.0, "real_total": 0.0,
                        "history_total": 0.0, "tx_count": 0, "history_rows": 0,
                    }
                amount = float(row["total"] or 0)
                merged[key]["total"] += amount
                merged[key]["history_total"] += amount
                merged[key]["history_rows"] += int(row["row_count"] or 0)
        return sorted(merged.values(), key=lambda item: float(item["total"]), reverse=True)

    def subcategory_totals_period(self, kind: str, start_date: date | str, end_date: date | str, include_history: bool = True):
        """Desglose de categorías hoja por hoja, incluyendo los totales mensuales del Excel."""
        start = date.fromisoformat(str(start_date)[:10]) if not isinstance(start_date, date) else start_date
        end = date.fromisoformat(str(end_date)[:10]) if not isinstance(end_date, date) else end_date
        if end < start:
            start, end = end, start
        with self.connect() as con:
            live = self._rows(con.execute(
                """
                SELECT c.id category_id,c.name category,p.name parent_category,
                       COALESCE(c.color,p.color,'#94A3B8') color,COALESCE(c.icon,p.icon,'other') icon,
                       SUM(t.amount) total,COUNT(*) tx_count
                FROM transactions t
                JOIN categories c ON c.id=t.category_id
                LEFT JOIN categories p ON p.id=c.parent_id
                WHERE t.kind=? AND date(t.tx_date)>=date(?) AND date(t.tx_date)<=date(?)
                GROUP BY c.id,c.name,p.name,COALESCE(c.color,p.color,'#94A3B8'),COALESCE(c.icon,p.icon,'other')
                """, (kind,start.isoformat(),end.isoformat())
            ).fetchall())
        merged: dict[str, dict[str, Any]] = {}
        for row in live:
            key = f"id:{row['category_id']}"
            merged[key] = {**row, "total": float(row["total"] or 0), "real_total": float(row["total"] or 0),
                           "history_total": 0.0, "history_rows": 0, "tx_count": int(row["tx_count"] or 0)}
        full_months = self._full_months_inside(start,end) if include_history else []
        if full_months:
            clauses = " OR ".join("(h.year=? AND h.month=?)" for _ in full_months)
            params: list[Any] = [kind]
            for y,m in full_months: params.extend([y,m])
            with self.connect() as con:
                hist = self._rows(con.execute(
                    f"""
                    SELECT h.category_id,h.category_name,h.subcategory_name,SUM(h.amount) total,COUNT(*) row_count,
                           c.name current_name,c.color,c.icon,p.name parent_name,p.color parent_color,p.icon parent_icon
                    FROM historical_monthly h
                    LEFT JOIN categories c ON c.id=h.category_id
                    LEFT JOIN categories p ON p.id=c.parent_id
                    WHERE h.kind=? AND ({clauses})
                    GROUP BY h.category_id,h.category_name,h.subcategory_name,c.name,c.color,c.icon,p.name,p.color,p.icon
                    """, params
                ).fetchall())
            for row in hist:
                cid = row.get("category_id")
                leaf = row.get("current_name") or row.get("subcategory_name") or row.get("category_name") or "Historial"
                parent = row.get("parent_name") or (row.get("category_name") if row.get("subcategory_name") else "")
                key = f"id:{cid}" if cid else "name:" + self._norm_name(f"{parent}/{leaf}")
                if key not in merged:
                    merged[key] = {
                        "category_id": cid,"category": leaf,"parent_category": parent,
                        "color": row.get("color") or row.get("parent_color") or self._stable_color_for_name(parent or leaf),
                        "icon": row.get("icon") or row.get("parent_icon") or self._icon_for_legacy_name(leaf),
                        "total": 0.0,"real_total": 0.0,"history_total": 0.0,"history_rows": 0,"tx_count": 0,
                    }
                amount = float(row["total"] or 0)
                merged[key]["total"] += amount; merged[key]["history_total"] += amount
                merged[key]["history_rows"] += int(row["row_count"] or 0)
        return sorted(merged.values(), key=lambda item: float(item["total"]), reverse=True)

    def category_direct_children_totals_period(
        self,
        kind: str,
        parent_id: int | None,
        start_date: date | str,
        end_date: date | str,
    ) -> list[dict]:
        """Totales por hijo directo, agregando todo su subárbol en una consulta."""
        start = date.fromisoformat(str(start_date)[:10]) if not isinstance(start_date, date) else start_date
        end = date.fromisoformat(str(end_date)[:10]) if not isinstance(end_date, date) else end_date
        if end < start:
            start, end = end, start
        children = self.category_children(parent_id, kind)
        if not children:
            return []
        child_map = {int(row["id"]): row for row in children}
        with self.connect() as con:
            if parent_id is None:
                seed_where = "parent_id IS NULL AND kind=?"
                seed_params: list[Any] = [kind]
            else:
                seed_where = "parent_id=? AND kind=?"
                seed_params = [int(parent_id), kind]
            live = self._rows(con.execute(
                f"""
                WITH RECURSIVE branch(id,branch_id) AS (
                    SELECT id,id FROM categories WHERE {seed_where}
                    UNION ALL
                    SELECT c.id,branch.branch_id FROM categories c JOIN branch ON c.parent_id=branch.id
                )
                SELECT branch.branch_id category_id,COALESCE(SUM(t.amount),0) total,COUNT(t.id) tx_count
                FROM branch
                LEFT JOIN transactions t ON t.category_id=branch.id
                    AND t.kind=? AND date(t.tx_date) BETWEEN date(?) AND date(?)
                GROUP BY branch.branch_id
                """,
                [*seed_params, kind, start.isoformat(), end.isoformat()],
            ).fetchall())
        totals = {int(row["category_id"]): {"total": float(row["total"] or 0), "tx_count": int(row["tx_count"] or 0)} for row in live}

        # El historial mensual sólo se suma para meses enteros, igual que el
        # resto de Análisis. No inventamos fechas para esos importes.
        full_months = self._full_months_inside(start, end)
        if full_months:
            clauses = " OR ".join("(h.year=? AND h.month=?)" for _ in full_months)
            params: list[Any] = [*seed_params, kind]
            for year, month in full_months:
                params.extend([year, month])
            with self.connect() as con:
                hist = self._rows(con.execute(
                    f"""
                    WITH RECURSIVE branch(id,branch_id) AS (
                        SELECT id,id FROM categories WHERE {seed_where}
                        UNION ALL
                        SELECT c.id,branch.branch_id FROM categories c JOIN branch ON c.parent_id=branch.id
                    )
                    SELECT branch.branch_id category_id,COALESCE(SUM(h.amount),0) total
                    FROM branch
                    LEFT JOIN historical_monthly h ON h.category_id=branch.id
                        AND h.kind=? AND ({clauses})
                    GROUP BY branch.branch_id
                    """,
                    params,
                ).fetchall())
            for row in hist:
                cid = int(row["category_id"])
                totals.setdefault(cid, {"total": 0.0, "tx_count": 0})["total"] += float(row["total"] or 0)

        result: list[dict] = []
        for cid, child in child_map.items():
            value = totals.get(cid, {"total": 0.0, "tx_count": 0})
            result.append({
                "category_id": cid,
                "category": child["name"],
                "path": child.get("path") or child["name"],
                "color": child.get("color") or "#94A3B8",
                "secondary_color": child.get("secondary_color"),
                "icon": child.get("icon") or "other",
                "total": float(value["total"]),
                "tx_count": int(value["tx_count"]),
                "has_children": bool(self.category_children(cid, kind)),
            })
        return sorted(result, key=lambda item: float(item["total"]), reverse=True)

    def category_subtree_total_period(
        self,
        kind: str,
        category_id: int,
        start_date: date | str,
        end_date: date | str,
        include_history: bool = True,
    ) -> float:
        """Importe total de una categoría y todos sus descendientes."""
        start = date.fromisoformat(str(start_date)[:10]) if not isinstance(start_date, date) else start_date
        end = date.fromisoformat(str(end_date)[:10]) if not isinstance(end_date, date) else end_date
        if end < start:
            start, end = end, start
        ids = self.category_descendant_ids(int(category_id), include_self=True)
        if not ids:
            return 0.0
        placeholders = ",".join("?" for _ in ids)
        with self.connect() as con:
            total = float(con.execute(
                f"SELECT COALESCE(SUM(amount),0) FROM transactions WHERE kind=? AND date(tx_date) BETWEEN date(?) AND date(?) AND category_id IN ({placeholders})",
                [kind, start.isoformat(), end.isoformat(), *ids],
            ).fetchone()[0] or 0)
            if include_history:
                full_months = self._full_months_inside(start, end)
                if full_months:
                    clauses = " OR ".join("(year=? AND month=?)" for _ in full_months)
                    params: list[Any] = [kind, *ids]
                    for year, month in full_months:
                        params.extend([year, month])
                    total += float(con.execute(
                        f"SELECT COALESCE(SUM(amount),0) FROM historical_monthly WHERE kind=? AND category_id IN ({placeholders}) AND ({clauses})",
                        params,
                    ).fetchone()[0] or 0)
        return total

    def category_transactions_period(
        self,
        kind: str,
        category_id: int,
        start_date: date | str,
        end_date: date | str,
        order: str = "amount_desc",
    ) -> list[dict]:
        """Movimientos de un subárbol con orden explícito para Análisis."""
        start = date.fromisoformat(str(start_date)[:10]) if not isinstance(start_date, date) else start_date
        end = date.fromisoformat(str(end_date)[:10]) if not isinstance(end_date, date) else end_date
        order_map = {
            "amount_desc": "amount_desc",
            "amount_asc": "amount_asc",
            "date_desc": "date",
            "date_asc": "date_asc",
        }
        return self.transactions(
            kind=kind,
            category_id=int(category_id),
            date_from=start.isoformat(),
            date_to=end.isoformat(),
            order_by=order_map.get(order, "amount_desc"),
        )

    def monthly_summary(self, year: int, month: int):
        start, end_exclusive = month_bounds(year, month)
        end = date.fromordinal(end_exclusive.toordinal() - 1)
        summary = self.period_summary(start, end, include_history=True)
        return {
            "income": summary["income"], "expense": summary["expense"], "net": summary["net"],
            "expense_count": summary["expense_count"],
            "history_income": summary["history_income"], "history_expense": summary["history_expense"],
        }

    def previous_month_summary(self, year: int, month: int):
        py, pm = previous_month(year, month)
        return self.monthly_summary(py, pm)

    def expense_by_category(self, year: int, month: int, limit: int | None = None):
        start, end_exclusive = month_bounds(year, month)
        end = date.fromordinal(end_exclusive.toordinal() - 1)
        rows = self.category_totals_period("expense", start, end, include_history=True)
        return rows[: int(limit)] if limit else rows

    def monthly_trend(self, year: int, month: int, count: int = 6):
        points = []
        y, m = year, month
        for _ in range(count):
            points.append((y, m))
            if m == 1:
                y, m = y - 1, 12
            else:
                m -= 1
        points.reverse()
        out = []
        for y, m in points:
            s = self.monthly_summary(y, m)
            out.append({"year": y, "month": m, **s})
        return out

    def yearly_totals(self, year: int):
        out = []
        for month in range(1, 13):
            out.append({"month": month, **self.monthly_summary(year, month)})
        return out

    def analytics_overview(self, year: int):
        months = self.yearly_totals(year)
        expenses = [m["expense"] for m in months]
        incomes = [m["income"] for m in months]
        active_expenses = [x for x in expenses if x > 0]
        total_income, total_expense = sum(incomes), sum(expenses)
        peak = max(months, key=lambda x: x["expense"]) if months else None
        with self.connect() as con:
            biggest = con.execute(
                "SELECT MAX(amount) FROM transactions WHERE kind='expense' AND strftime('%Y',tx_date)=?",
                (str(year),),
            ).fetchone()[0]
        return {
            "total_income": total_income,
            "total_expense": total_expense,
            "net": total_income - total_expense,
            "avg_monthly_expense": sum(active_expenses) / len(active_expenses) if active_expenses else 0,
            "savings_rate": ((total_income - total_expense) / total_income * 100) if total_income else 0,
            "peak_month": peak["month"] if peak and peak["expense"] else None,
            "peak_expense": peak["expense"] if peak else 0,
            "biggest_expense": float(biggest or 0),
        }
