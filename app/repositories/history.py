from __future__ import annotations

import re
import unicodedata
from datetime import date
from typing import Any

from ..constants import CATEGORY_COLORS, CATEGORY_ICON_BY_NAME


class HistoryRepositoryMixin:
    """Importación histórica y reconciliación de categorías del Excel legado."""

    @staticmethod
    def _norm_name(value: str) -> str:
        text = unicodedata.normalize("NFKD", str(value or ""))
        text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
        return re.sub(r"[^a-z0-9]+", "", text)

    @classmethod
    def _icon_for_legacy_name(cls, name: str, fallback: str = "other") -> str:
        target = cls._norm_name(name)
        for label, icon in CATEGORY_ICON_BY_NAME.items():
            if cls._norm_name(label) == target:
                return icon
        # Pequeñas heurísticas para categorías que estaban en el Excel pero no en los seeds.
        hints = (
            (("curso", "educacion"), "graduation"), (("telefono", "celular"), "phone"),
            (("monotributo", "impuesto"), "receipt"), (("psicolog",), "medical"),
            (("obra social", "obrasocial"), "health"), (("makro", "supermerc"), "cart"),
            (("service", "reparacion"), "wrench"), (("seguro",), "shield"),
        )
        normalized_words = str(name or "").lower()
        for needles, icon in hints:
            if any(n in normalized_words for n in needles):
                return icon
        return fallback

    @classmethod
    def _stable_color_for_name(cls, name: str) -> str:
        norm = cls._norm_name(name)
        score = sum((i + 1) * ord(ch) for i, ch in enumerate(norm))
        return CATEGORY_COLORS[score % len(CATEGORY_COLORS)] if CATEGORY_COLORS else "#4CCFA9"

    def _ensure_category_path_con(self, con: sqlite3.Connection, kind: str, root_name: str, sub_name: str = "") -> int:
        root_name = str(root_name or "").strip() or ("Otros gastos" if kind == "expense" else "Otros ingresos")
        sub_name = str(sub_name or "").strip()
        target = self._norm_name(root_name)
        roots = con.execute("SELECT * FROM categories WHERE kind=? AND parent_id IS NULL ORDER BY id", (kind,)).fetchall()
        root = next((r for r in roots if self._norm_name(r["name"]) == target), None)
        if root is None and target == "otros":
            root = next((r for r in roots if self._norm_name(r["name"]).startswith("otros")), None)
        if root is None:
            order = con.execute("SELECT COALESCE(MAX(sort_order),-1)+1 FROM categories WHERE kind=? AND parent_id IS NULL", (kind,)).fetchone()[0]
            color = self._stable_color_for_name(root_name)
            icon = self._icon_for_legacy_name(root_name, "wallet" if "otro" in target else "other")
            cur = con.execute(
                "INSERT INTO categories(name,kind,parent_id,color,icon,sort_order) VALUES(?,?,NULL,?,?,?)",
                (root_name, kind, color, icon, int(order or 0)),
            )
            root_id = int(cur.lastrowid)
            root_color, root_icon = color, icon
        else:
            root_id = int(root["id"]); root_color = root["color"]; root_icon = root["icon"]

        if not sub_name:
            return root_id
        child_target = self._norm_name(sub_name)
        children = con.execute("SELECT * FROM categories WHERE kind=? AND parent_id=? ORDER BY id", (kind, root_id)).fetchall()
        child = next((r for r in children if self._norm_name(r["name"]) == child_target), None)
        if child is not None:
            return int(child["id"])
        order = con.execute(
            "SELECT COALESCE(MAX(sort_order),-1)+1 FROM categories WHERE kind=? AND parent_id=?", (kind, root_id)
        ).fetchone()[0]
        icon = self._icon_for_legacy_name(sub_name, root_icon or "other")
        cur = con.execute(
            "INSERT INTO categories(name,kind,parent_id,color,icon,sort_order) VALUES(?,?,?,?,?,?)",
            (sub_name, kind, root_id, root_color or self._stable_color_for_name(root_name), icon, int(order or 0)),
        )
        return int(cur.lastrowid)

    def _link_existing_history_categories(self, con: sqlite3.Connection) -> int:
        """Hace visibles como categorías reales los datos importados por versiones anteriores."""
        rows = con.execute(
            "SELECT id,kind,category_name,subcategory_name,category_id FROM historical_monthly ORDER BY id"
        ).fetchall()
        linked = 0
        for row in rows:
            cid = self._ensure_category_path_con(
                con, row["kind"], row["category_name"], row["subcategory_name"] or ""
            )
            if row["category_id"] != cid:
                con.execute("UPDATE historical_monthly SET category_id=? WHERE id=?", (cid, row["id"]))
                linked += 1
        return linked

    def sync_legacy_categories(self, payload: dict[str, Any]) -> dict[str, int]:
        """Importa la estructura de categorías del Excel, aunque no tenga importes en todas."""
        paths = payload.get("category_paths") or []
        created_before = len(self.categories())
        with self.connect() as con:
            for row in paths:
                self._ensure_category_path_con(
                    con, str(row.get("kind") or "expense"), str(row.get("category_name") or ""),
                    str(row.get("subcategory_name") or ""),
                )
            self._link_existing_history_categories(con)
        created_after = len(self.categories())
        return {"created": max(0, created_after - created_before), "total": created_after}

    def _match_root_category_id(self, kind: str, name: str) -> int | None:
        target = self._norm_name(name)
        if not target:
            return None
        roots = [c for c in self.categories(kind) if c.get("parent_id") is None]
        exact = next((c for c in roots if self._norm_name(c["name"]) == target), None)
        if exact:
            return int(exact["id"])
        # El Excel viejo usaba simplemente "Otros" mientras la app usa
        # "Otros gastos" / "Otros ingresos".
        if target == "otros":
            other = next((c for c in roots if self._norm_name(c["name"]).startswith("otros")), None)
            if other:
                return int(other["id"])
        return None

    def historical_import_exists(self, file_hash: str) -> bool:
        with self.connect() as con:
            return bool(con.execute("SELECT 1 FROM historical_imports WHERE file_hash=?", (file_hash,)).fetchone())

    def months_with_transactions(self) -> set[tuple[int, int]]:
        with self.connect() as con:
            rows = con.execute(
                "SELECT DISTINCT CAST(strftime('%Y',tx_date) AS INTEGER) y, CAST(strftime('%m',tx_date) AS INTEGER) m FROM transactions"
            ).fetchall()
        return {(int(r["y"]), int(r["m"])) for r in rows if r["y"] and r["m"]}

    def months_with_history(self) -> set[tuple[int, int]]:
        with self.connect() as con:
            rows = con.execute("SELECT DISTINCT year,month FROM historical_monthly").fetchall()
        return {(int(r["year"]), int(r["month"])) for r in rows}

    def import_monthly_history(
        self,
        payload: dict[str, Any],
        skip_transaction_months: bool = True,
        skip_existing_history_months: bool = True,
        closed_months_only: bool = True,
    ) -> dict[str, Any]:
        # Las categorías forman parte del import real y se crean aunque algunos meses se omitan.
        category_sync = self.sync_legacy_categories(payload)
        if self.historical_import_exists(payload["file_hash"]):
            raise ValueError("Este archivo ya fue importado anteriormente.")

        tx_months = self.months_with_transactions() if skip_transaction_months else set()
        history_months = self.months_with_history() if skip_existing_history_months else set()
        skipped_tx: set[tuple[int, int]] = set()
        skipped_history: set[tuple[int, int]] = set()
        skipped_open: set[tuple[int, int]] = set()
        current_ym = (date.today().year, date.today().month)
        selected = []
        for row in payload.get("records", []):
            ym = (int(row["year"]), int(row["month"]))
            if closed_months_only and ym >= current_ym:
                skipped_open.add(ym)
                continue
            if ym in tx_months:
                skipped_tx.add(ym)
                continue
            if ym in history_months:
                skipped_history.add(ym)
                continue
            selected.append(row)

        if not selected:
            reason = "Todos los meses del archivo ya tienen movimientos o historial en App Gastos."
            raise ValueError(reason)

        expense = sum(float(r["amount"]) for r in selected if r["kind"] == "expense")
        income = sum(float(r["amount"]) for r in selected if r["kind"] == "income")
        with self.connect() as con:
            cur = con.execute(
                """
                INSERT INTO historical_imports(source,file_name,file_hash,rows_count,total_expense,total_income)
                VALUES('legacy_excel',?,?,?,?,?)
                """,
                (payload.get("file_name", "Gestion de gastos.xlsx"), payload["file_hash"], len(selected), expense, income),
            )
            import_id = int(cur.lastrowid)
            for row in selected:
                category_id = self._ensure_category_path_con(
                    con, row["kind"], row["category_name"], row.get("subcategory_name") or ""
                )
                con.execute(
                    """
                    INSERT INTO historical_monthly(import_id,kind,year,month,category_name,subcategory_name,category_id,amount)
                    VALUES(?,?,?,?,?,?,?,?)
                    """,
                    (
                        import_id, row["kind"], int(row["year"]), int(row["month"]),
                        str(row["category_name"]), str(row.get("subcategory_name") or ""), category_id, float(row["amount"]),
                    ),
                )
        return {
            "import_id": import_id,
            "rows": len(selected),
            "expense_total": expense,
            "income_total": income,
            "months": sorted({(int(r["year"]), int(r["month"])) for r in selected}),
            "skipped_transaction_months": sorted(skipped_tx),
            "skipped_history_months": sorted(skipped_history),
            "skipped_open_months": sorted(skipped_open),
            "categories_created": category_sync.get("created", 0),
        }

    def historical_entries(
        self, year: int | None = None, month: int | None = None, kind: str | None = None,
        category_id: int | None = None, search: str = "", limit: int | None = None,
    ):
        """Registros mensuales del Excel expuestos como movimientos de precisión mensual."""
        sql = """
        SELECT h.*, i.file_name, i.imported_at,
               c.name AS current_category_name, c.color AS category_color, c.icon AS category_icon, c.parent_id,
               p.name AS parent_category_name, p.color AS parent_category_color, p.icon AS parent_category_icon
        FROM historical_monthly h
        JOIN historical_imports i ON i.id=h.import_id
        LEFT JOIN categories c ON c.id=h.category_id
        LEFT JOIN categories p ON p.id=c.parent_id
        WHERE 1=1
        """
        params: list[Any] = []
        if year:
            sql += " AND h.year=?"; params.append(int(year))
        if month:
            sql += " AND h.month=?"; params.append(int(month))
        if kind and kind != "all":
            sql += " AND h.kind=?"; params.append(kind)
        if category_id:
            category_ids = self.category_descendant_ids(int(category_id), include_self=True)
            if category_ids:
                placeholders = ",".join("?" for _ in category_ids)
                sql += f" AND c.id IN ({placeholders})"
                params.extend(category_ids)
            else:
                sql += " AND c.id=?"; params.append(int(category_id))
        if search.strip():
            q = f"%{search.strip()}%"
            sql += """ AND (
                LOWER(h.category_name) LIKE LOWER(?) OR LOWER(h.subcategory_name) LIKE LOWER(?)
                OR LOWER(COALESCE(c.name,'')) LIKE LOWER(?) OR LOWER(COALESCE(p.name,'')) LIKE LOWER(?)
                OR LOWER(i.file_name) LIKE LOWER(?)
            )"""
            params += [q] * 5
        sql += " ORDER BY h.year DESC,h.month DESC,h.kind,h.category_name COLLATE NOCASE,h.subcategory_name COLLATE NOCASE,h.id"
        if limit:
            sql += f" LIMIT {int(limit)}"
        with self.connect() as con:
            rows = self._rows(con.execute(sql, params).fetchall())
        category_map = {int(row["id"]): row for row in self.categories()} if rows else {}
        for r in rows:
            category = category_map.get(int(r["category_id"])) if r.get("category_id") else None
            if category:
                r["category_display"] = category.get("path") or category.get("name")
            elif r.get("parent_category_name"):
                r["category_display"] = f"{r['parent_category_name']} / {r.get('current_category_name') or r['subcategory_name']}"
            elif r.get("current_category_name"):
                r["category_display"] = r["current_category_name"]
            elif r.get("subcategory_name"):
                r["category_display"] = f"{r['category_name']} / {r['subcategory_name']}"
            else:
                r["category_display"] = r["category_name"]
            r["category_effective_color"] = (category.get("color") if category else None) or r.get("category_color") or r.get("parent_category_color") or self._stable_color_for_name(r["category_name"])
            r["category_secondary_color"] = (category.get("secondary_color") if category else None)
            r["category_effective_icon"] = (category.get("icon") if category else None) or r.get("category_icon") or r.get("parent_category_icon") or self._icon_for_legacy_name(r.get("subcategory_name") or r["category_name"])
            r["display"] = r["category_display"]
            r["source"] = "legacy_excel"
            r["precision"] = "month"
        return rows

    def historical_filtered_totals(self, **filters):
        rows = self.historical_entries(**filters)
        income = sum(float(x["amount"]) for x in rows if x["kind"] == "income")
        expense = sum(float(x["amount"]) for x in rows if x["kind"] == "expense")
        return {"income": income, "expense": expense, "net": income - expense, "count": len(rows)}

    def historical_entry(self, entry_id: int):
        rows = self.historical_entries()
        return next((r for r in rows if int(r["id"]) == int(entry_id)), None)

    def update_historical_entry(self, entry_id: int, amount: float, category_id: int):
        amount = float(amount or 0)
        if amount <= 0:
            raise ValueError("El importe debe ser mayor a cero.")
        with self.connect() as con:
            row = con.execute("SELECT * FROM historical_monthly WHERE id=?", (int(entry_id),)).fetchone()
            if not row:
                raise ValueError("No encontré el registro importado.")
            cat = con.execute("SELECT * FROM categories WHERE id=?", (int(category_id),)).fetchone()
            if not cat or cat["kind"] != row["kind"]:
                raise ValueError("La categoría elegida no corresponde al tipo de movimiento.")
            if cat["parent_id"] is not None:
                parent = con.execute("SELECT name FROM categories WHERE id=?", (cat["parent_id"],)).fetchone()
                root_name = parent["name"] if parent else row["category_name"]
                sub_name = cat["name"]
            else:
                root_name, sub_name = cat["name"], ""
            con.execute(
                "UPDATE historical_monthly SET amount=?,category_id=?,category_name=?,subcategory_name=? WHERE id=?",
                (amount, int(category_id), root_name, sub_name, int(entry_id)),
            )

    def delete_historical_entry(self, entry_id: int):
        with self.connect() as con:
            con.execute("DELETE FROM historical_monthly WHERE id=?", (int(entry_id),))

    def historical_imports(self):
        with self.connect() as con:
            return self._rows(con.execute("SELECT * FROM historical_imports ORDER BY datetime(imported_at) DESC,id DESC").fetchall())

    def historical_monthly_rows(self):
        with self.connect() as con:
            return self._rows(con.execute(
                """
                SELECT h.*,i.file_name,i.imported_at,c.name AS matched_category
                FROM historical_monthly h
                JOIN historical_imports i ON i.id=h.import_id
                LEFT JOIN categories c ON c.id=h.category_id
                ORDER BY h.year,h.month,h.kind,h.category_name,h.subcategory_name
                """
            ).fetchall())

    def delete_historical_import(self, import_id: int):
        with self.connect() as con:
            con.execute("DELETE FROM historical_imports WHERE id=?", (int(import_id),))
