from __future__ import annotations


from ..icon_data import normalize_icon


class CategoryRepositoryMixin:
    """Jerarquía de categorías y operaciones que preservan el historial."""

    def categories(self, kind: str | None = None):
        """Devuelve categorías con contexto inmediato y ruta jerárquica completa."""
        where, params = "", []
        if kind:
            where = "WHERE c.kind=?"
            params.append(kind)
        with self.connect() as con:
            rows = self._rows(con.execute(
                f"""
                SELECT c.*, p.name AS parent_name, p.color AS parent_color,
                       p.secondary_color AS parent_secondary_color, p.icon AS parent_icon
                FROM categories c
                LEFT JOIN categories p ON p.id=c.parent_id
                {where}
                ORDER BY c.kind,c.sort_order,c.name COLLATE NOCASE
                """,
                params,
            ).fetchall())
        by_id = {int(row["id"]): row for row in rows}

        def path_for(row: dict) -> list[str]:
            names: list[str] = []
            seen: set[int] = set()
            current = row
            while current:
                cid = int(current["id"])
                if cid in seen:
                    break
                seen.add(cid)
                names.append(str(current.get("name") or ""))
                pid = current.get("parent_id")
                current = by_id.get(int(pid)) if pid is not None else None
            return list(reversed([name for name in names if name]))

        for row in rows:
            path = path_for(row)
            row["path"] = " / ".join(path)
            row["path_parent"] = " / ".join(path[:-1])
            row["depth"] = max(0, len(path) - 1)
        rows.sort(key=lambda row: (str(row.get("kind")), str(row.get("path") or "").casefold()))
        return rows

    def category(self, category_id: int):
        rows = self.categories()
        return next((row for row in rows if int(row["id"]) == int(category_id)), None)

    def category_children(self, category_id: int | None, kind: str | None = None) -> list[dict]:
        return [
            row for row in self.categories(kind)
            if (row.get("parent_id") is None if category_id is None else int(row.get("parent_id") or 0) == int(category_id))
        ]

    def category_descendant_ids(self, category_id: int, include_self: bool = True) -> list[int]:
        """IDs del subárbol de una categoría, útil para filtros y análisis."""
        with self.connect() as con:
            rows = con.execute(
                """
                WITH RECURSIVE descendants(id) AS (
                    SELECT id FROM categories WHERE id=?
                    UNION ALL
                    SELECT c.id FROM categories c JOIN descendants d ON c.parent_id=d.id
                )
                SELECT id FROM descendants
                """,
                (int(category_id),),
            ).fetchall()
        result = [int(row[0]) for row in rows]
        if not include_self:
            result = [value for value in result if value != int(category_id)]
        return result

    def category_choices(self, kind: str, include_parents: bool = False):
        rows = self.categories(kind)
        parent_ids = {int(r["parent_id"]) for r in rows if r.get("parent_id") is not None}
        result = []
        for row in rows:
            if not include_parents and int(row["id"]) in parent_ids:
                continue
            result.append({
                **row,
                "label": row.get("path") or row.get("name"),
                "effective_color": row.get("color") or row.get("parent_color") or "#4CCFA9",
                "effective_icon": row.get("icon") or row.get("parent_icon") or "other",
            })
        return result

    def add_category(
        self,
        name: str,
        kind: str,
        parent_id: int | None,
        color: str,
        icon: str = "other",
        secondary_color: str | None = None,
    ):
        name = (name or "").strip()
        if not name:
            raise ValueError("Ingresá un nombre para la categoría.")
        with self.connect() as con:
            if parent_id is not None:
                parent = con.execute("SELECT kind FROM categories WHERE id=?", (int(parent_id),)).fetchone()
                if not parent:
                    raise ValueError("La categoría contenedora ya no existe.")
                if str(parent["kind"]) != str(kind):
                    raise ValueError("Una categoría sólo puede moverse dentro del mismo tipo.")
            order = con.execute(
                "SELECT COALESCE(MAX(sort_order),-1)+1 FROM categories WHERE kind=? AND IFNULL(parent_id,0)=IFNULL(?,0)",
                (kind, parent_id),
            ).fetchone()[0]
            cur = con.execute(
                "INSERT INTO categories(name,kind,parent_id,color,secondary_color,icon,sort_order) VALUES(?,?,?,?,?,?,?)",
                (name, kind, parent_id, color, secondary_color or None, normalize_icon(icon, name), order),
            )
            return int(cur.lastrowid)

    def update_category(
        self,
        category_id: int,
        name: str,
        kind: str,
        parent_id: int | None,
        color: str,
        icon: str = "other",
        secondary_color: str | None = None,
    ):
        category_id = int(category_id)
        if parent_id is not None and int(parent_id) == category_id:
            raise ValueError("Una categoría no puede depender de sí misma.")
        descendants = set(self.category_descendant_ids(category_id, include_self=False))
        if parent_id is not None and int(parent_id) in descendants:
            raise ValueError("No podés mover una categoría dentro de una de sus propias subcategorías.")
        with self.connect() as con:
            if parent_id is not None:
                parent = con.execute("SELECT kind FROM categories WHERE id=?", (int(parent_id),)).fetchone()
                if not parent:
                    raise ValueError("La categoría contenedora ya no existe.")
                if str(parent["kind"]) != str(kind):
                    raise ValueError("Una categoría sólo puede moverse dentro del mismo tipo.")
            con.execute(
                "UPDATE categories SET name=?,kind=?,parent_id=?,color=?,secondary_color=?,icon=? WHERE id=?",
                ((name or "").strip(), kind, parent_id, color, secondary_color or None, normalize_icon(icon, name), category_id),
            )
            # Si cambia el tipo de un árbol completo, sus descendientes acompañan
            # para no crear jerarquías mezcladas entre gastos e ingresos.
            if descendants:
                placeholders = ",".join("?" for _ in descendants)
                con.execute(f"UPDATE categories SET kind=? WHERE id IN ({placeholders})", [kind, *sorted(descendants)])

    def move_category(self, category_id: int, new_parent_id: int | None) -> None:
        """Mueve un nodo existente sin copiarlo ni alterar sus movimientos.

        Si una build anterior dejó, dentro del destino, una copia *vacía* con
        el mismo nombre, se elimina esa copia antes de mover el nodo real. Esto
        permite reparar de forma segura el bug histórico de drag & drop sin
        borrar categorías que tengan datos o subcategorías.
        """
        category_id = int(category_id)
        parent_id = int(new_parent_id) if new_parent_id is not None else None
        if parent_id == category_id:
            raise ValueError("Una categoría no puede depender de sí misma.")

        descendants = set(self.category_descendant_ids(category_id, include_self=False))
        if parent_id is not None and parent_id in descendants:
            raise ValueError("No podés mover una categoría dentro de una de sus propias subcategorías.")

        with self.connect() as con:
            source = con.execute(
                "SELECT id,name,kind,parent_id FROM categories WHERE id=?",
                (category_id,),
            ).fetchone()
            if not source:
                raise ValueError("La categoría ya no existe.")

            if parent_id is not None:
                target = con.execute("SELECT id,kind FROM categories WHERE id=?", (parent_id,)).fetchone()
                if not target:
                    raise ValueError("La categoría contenedora ya no existe.")
                if str(target["kind"]) != str(source["kind"]):
                    raise ValueError("Sólo podés mover categorías dentro del mismo tipo.")

                # Detectamos hermanos homónimos dejados por versiones anteriores.
                candidates = con.execute(
                    "SELECT id,name FROM categories WHERE parent_id=? AND kind=? AND id<>?",
                    (parent_id, source["kind"], category_id),
                ).fetchall()
                normalized = str(source["name"] or "").strip().casefold()
                duplicates = [row for row in candidates if str(row["name"] or "").strip().casefold() == normalized]

                # Primero validamos todos; si alguno tiene contenido no tocamos nada.
                checks = (
                    ("transactions", "category_id"),
                    ("budgets", "category_id"),
                    ("recurring_transactions", "category_id"),
                    ("historical_monthly", "category_id"),
                )
                for duplicate in duplicates:
                    duplicate_id = int(duplicate["id"])
                    children = int(con.execute(
                        "SELECT COUNT(*) FROM categories WHERE parent_id=?", (duplicate_id,)
                    ).fetchone()[0] or 0)
                    if children:
                        raise ValueError(
                            f"Ya existe ‘{source['name']}’ en el destino y esa copia tiene subcategorías. "
                            "No se hizo ningún cambio para evitar perder estructura."
                        )
                    for table, column in checks:
                        used = int(con.execute(
                            f"SELECT COUNT(*) FROM {table} WHERE {column}=?", (duplicate_id,)
                        ).fetchone()[0] or 0)
                        if used:
                            raise ValueError(
                                f"Ya existe ‘{source['name']}’ en el destino y esa copia contiene datos. "
                                "No se hizo ningún cambio para evitar perder información."
                            )
                for duplicate in duplicates:
                    con.execute("DELETE FROM categories WHERE id=?", (int(duplicate["id"]),))

            current_parent = source["parent_id"]
            if (current_parent is None and parent_id is None) or (
                current_parent is not None and parent_id is not None and int(current_parent) == parent_id
            ):
                return
            con.execute("UPDATE categories SET parent_id=? WHERE id=?", (parent_id, category_id))

    def duplicate_category(self, category_id: int) -> int:
        """Duplicate only the visual/category node, never movements or children."""
        source = self.category(int(category_id))
        if not source:
            raise ValueError("La categoría ya no existe.")
        parent_id = source.get("parent_id")
        siblings = self.category_children(
            int(parent_id) if parent_id is not None else None,
            str(source.get("kind") or "expense"),
        )
        used = {str(row.get("name") or "").casefold() for row in siblings}
        base = str(source.get("name") or "Categoría").strip()
        candidate = f"{base} (copia)"
        suffix = 2
        while candidate.casefold() in used:
            candidate = f"{base} (copia {suffix})"
            suffix += 1
        return self.add_category(
            candidate,
            str(source.get("kind") or "expense"),
            int(parent_id) if parent_id is not None else None,
            str(source.get("color") or "#4CCFA9"),
            str(source.get("icon") or "other"),
            source.get("secondary_color"),
        )

    def delete_category(self, category_id: int):
        ids = self.category_descendant_ids(int(category_id), include_self=True)
        if not ids:
            return
        placeholders = ",".join("?" for _ in ids)
        with self.connect() as con:
            checks = (
                ("transactions", "category_id"),
                ("budgets", "category_id"),
                ("recurring_transactions", "category_id"),
                ("historical_monthly", "category_id"),
            )
            for table, column in checks:
                used = int(con.execute(f"SELECT COUNT(*) FROM {table} WHERE {column} IN ({placeholders})", ids).fetchone()[0] or 0)
                if used:
                    raise ValueError("La categoría o una de sus subcategorías está en uso por movimientos, historial o recurrentes.")
            con.execute("DELETE FROM categories WHERE id=?", (int(category_id),))

    def recent_categories(self, kind: str, limit: int = 6):
        """Categorías usadas más recientemente, sin duplicados."""
        with self.connect() as con:
            rows = con.execute(
                """
                SELECT c.*, p.name AS parent_name, p.color AS parent_color, p.icon AS parent_icon, MAX(t.id) AS last_tx
                FROM transactions t
                JOIN categories c ON c.id=t.category_id
                LEFT JOIN categories p ON p.id=c.parent_id
                WHERE t.kind=?
                GROUP BY c.id
                ORDER BY last_tx DESC
                LIMIT ?
                """,
                (kind, int(limit)),
            ).fetchall()
        out=[]
        by_id = {int(row["id"]): row for row in self.categories(kind)}
        for r in self._rows(rows):
            current = by_id.get(int(r["id"])) or r
            r.update({k: v for k, v in current.items() if k not in {"last_tx"}})
            r["label"] = current.get("path") or current.get("name") or r["name"]
            r["effective_color"] = current.get("color") or r.get("color") or r.get("parent_color") or "#4CCFA9"
            r["effective_icon"] = current.get("icon") or r.get("icon") or r.get("parent_icon") or "other"
            out.append(r)
        return out
