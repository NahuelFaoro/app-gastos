from __future__ import annotations

import json
import re
import sqlite3
from typing import Any


class ImportQueueMixin:
    """Repositorio de dominio extraído de ``Database`` para reducir acoplamiento."""

    @staticmethod
    def _rule_text(value: str) -> str:
        import re
        text = (value or "").lower().strip()
        text = re.sub(r"[^a-záéíóúüñ0-9 ]+", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @classmethod
    def _learned_rule_pattern(cls, value: str) -> str:
        """Reduce descripciones variables a una firma más estable.

        Ej.: "EST SERV LPM 124" -> "est serv lpm". Así una regla aprendida
        sigue funcionando aunque cambie el número de sucursal/operación.
        """
        text = cls._rule_text(value)
        if not text:
            return ""
        tokens = []
        generic = {"mp", "pago", "compra", "debito", "credito", "tarjeta", "mercadopago"}
        for token in text.split():
            if token in generic and not tokens:
                continue
            if token.isdigit() and len(token) >= 2:
                continue
            if re.fullmatch(r"\d+[a-z]?", token):
                continue
            tokens.append(token)
        candidate = " ".join(tokens).strip()
        return candidate if len(candidate) >= 3 else text

    def import_rules(self, source: str | None = None):
        sql = """
            SELECT r.*, c.name category_name, p.name parent_category_name,
                   COALESCE(p.color,c.color,'#4CCFA9') color,
                   COALESCE(p.icon,c.icon,'other') icon
            FROM import_rules r
            JOIN categories c ON c.id=r.category_id
            LEFT JOIN categories p ON p.id=c.parent_id
            WHERE r.active=1
        """
        params=[]
        if source:
            sql += " AND r.source=?"; params.append(source)
        sql += " ORDER BY LENGTH(r.pattern) DESC, r.id DESC"
        with self.connect() as con:
            return self._rows(con.execute(sql, params).fetchall())

    def _builtin_import_category(self, description: str, kind: str):
        """Sugerencias conservadoras para comercios/productos conocidos.

        Las reglas que aprende el usuario siempre tienen prioridad. Estas heurísticas
        sólo cubren coincidencias bastante claras; ante textos ambiguos (p. ej. "jabón")
        preferimos dejarlo pendiente para no inventar una categoría.
        """
        if kind != "expense":
            return None
        hay = self._rule_text(description)
        if not hay:
            return None

        choices = self.category_choices(kind, include_parents=True)
        normalized = {}
        for c in choices:
            key = self._rule_text(c.get("label") or c.get("name") or "")
            normalized[key] = int(c["id"])
            normalized[self._rule_text(c.get("name") or "")] = int(c["id"])

        def target(*names):
            for name in names:
                key = self._rule_text(name)
                if key in normalized:
                    return normalized[key]
            return None

        # Orden: señales más específicas primero.
        rules = [
            (("ausol", "autopista", "telepase", "peaje"), ("Moto / Peaje", "Peaje")),
            (("ypf", "shell", "axion", "puma energy", "serviclub", "estacion de servicio", "est servicio", "combustible", "nafta"), ("Moto / Combustible", "Combustible")),
            (("uber", "didi", "cabify"), ("Moto / Didi/Uber", "Didi/Uber")),
            (("farmacity", "farmacia", "medicamento", "remedio"), ("Salud / Médicos / Farmacia", "Farmacia")),
            (("spotify",), ("Suscripciones / Spotify", "Spotify")),
            (("youtube",), ("Suscripciones / YouTube", "YouTube")),
            (("tinder",), ("Suscripciones / Tinder", "Tinder")),
            (("mcdonald", "burger king", "mostaza", "pedidosya", "rappi", "restaurant", "restaurante", "pizzeria", "pizza", "cafeteria", "panaderia"), ("Casa / Comida", "Comida")),
            (("coto", "carrefour", "changomas", "chango mas", "jumbo", "disco", "vea", "makro", "supermercado"), ("Casa / Compras", "Compras")),
            (("detergente", "lavandina", "suavizante", "desinfectante", "limpiador", "esponja", "magistral", "cif", "skip"), ("Casa / Limpieza/Higiene", "Limpieza/Higiene")),
            (("shampoo", "acondicionador", "desodorante", "dentifrico", "pasta dental", "cepillo dental", "dove", "rexona"), ("Gastos personales / Compras personales", "Compras personales")),
            (("edenor", "edesur"), ("Casa / Electricidad", "Electricidad")),
            (("aysa",), ("Casa / Agua", "Agua")),
            (("naturgy", "metrogas"), ("Casa / Gas", "Gas")),
            (("telecentro", "fibertel", "personal flow", "internet"), ("Casa / Wifi", "Wifi")),
        ]
        for needles, targets in rules:
            if any(n in hay for n in needles):
                found = target(*targets)
                if found:
                    return found
        return None

    def suggest_import_category(self, source: str, description: str, kind: str):
        hay = self._rule_text(description)
        if not hay:
            return None
        # Primero lo que la propia persona enseñó a App Gastos.
        for rule in self.import_rules(source):
            if rule["kind"] != kind:
                continue
            pattern = self._rule_text(rule["pattern"])
            if pattern and pattern in hay:
                return int(rule["category_id"])
        # Después, un set deliberadamente pequeño de heurísticas seguras.
        return self._builtin_import_category(description, kind)

    def add_import_rule(self, source: str, pattern: str, kind: str, category_id: int):
        pattern = self._learned_rule_pattern(pattern)
        if len(pattern) < 3:
            return
        with self.connect() as con:
            con.execute(
                """
                INSERT INTO import_rules(source,pattern,kind,category_id,active)
                VALUES(?,?,?,?,1)
                ON CONFLICT(source,pattern,kind) DO UPDATE SET category_id=excluded.category_id, active=1
                """,
                (source, pattern, kind, int(category_id)),
            )

    def stage_imported_movements(self, rows: list[dict[str, Any]], source: str, account_id: int):
        inserted = duplicate = 0
        with self.connect() as con:
            for row in rows:
                external_id = str(row.get("external_id") or "").strip()
                if not external_id:
                    continue
                kind = row.get("kind") if row.get("kind") in {"expense","income"} else "expense"
                description = str(row.get("description") or "").strip()
                category_id = self.suggest_import_category(source, description, kind)
                try:
                    con.execute(
                        """
                        INSERT INTO imported_movements(source,external_id,account_id,tx_date,kind,amount,description,raw_json,category_id)
                        VALUES(?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            source, external_id, int(account_id), self._normalize_tx_date(row.get("tx_date")), kind,
                            abs(float(row.get("amount") or 0)), description,
                            json.dumps(row.get("raw") or {}, ensure_ascii=False, default=str), category_id,
                        ),
                    )
                    inserted += 1
                except sqlite3.IntegrityError:
                    duplicate += 1
        return {"inserted": inserted, "duplicates": duplicate}

    def _enrich_import_row(self, row: dict[str, Any] | None, category_map: dict[int, dict] | None = None):
        if not row:
            return None
        r = dict(row)
        if r.get("category_id"):
            category = (category_map or {}).get(int(r["category_id"])) if category_map is not None else self.category(int(r["category_id"]))
        else:
            category = None
        r["category_display"] = (category.get("path") if category else None) or (
            f"{r['parent_category_name']} / {r['category_name']}" if r.get("parent_category_name")
            else (r.get("category_name") or "Sin categoría")
        )
        if category:
            r["category_color"] = category.get("color") or r.get("category_color")
            r["category_secondary_color"] = category.get("secondary_color")
            r["category_icon"] = category.get("icon") or r.get("category_icon")
        try:
            raw = json.loads(r.get("raw_json") or "{}")
        except Exception:
            raw = {}
        operation = str(raw.get("TRANSACTION_TYPE") or raw.get("OPERATION_TYPE") or "").upper()
        r["operation_type"] = operation
        r["raw"] = raw
        r["scan_installment_current"] = raw.get("installment_current")
        r["scan_installment_total"] = raw.get("installment_total")
        r["scan_parser"] = raw.get("parser")
        r["scan_ocr_score"] = raw.get("ocr_score")
        desc = str(r.get("description") or "").lower()
        r["transfer_hint"] = operation in {"WITHDRAWAL", "PAYOUT", "WITHDRAWAL_CANCEL"} or "transfer" in operation.lower() or "transferencia" in desc
        return r

    def imported_movements(self, status: str = "pending", source: str | None = None):
        sql = """
            SELECT i.*, a.name account_name,
                   c.name category_name, p.name parent_category_name,
                   COALESCE(p.color,c.color,'#94A3B8') category_color,
                   COALESCE(p.icon,c.icon,'other') category_icon
            FROM imported_movements i
            JOIN accounts a ON a.id=i.account_id
            LEFT JOIN categories c ON c.id=i.category_id
            LEFT JOIN categories p ON p.id=c.parent_id
            WHERE 1=1
        """
        params=[]
        if status and status != "all":
            sql += " AND i.status=?"; params.append(status)
        if source:
            sql += " AND i.source=?"; params.append(source)
        sql += " ORDER BY date(i.tx_date) DESC, i.id DESC"
        with self.connect() as con:
            rows=self._rows(con.execute(sql,params).fetchall())
        category_map = {int(row["id"]): row for row in self.categories()} if rows else {}
        return [self._enrich_import_row(r, category_map) for r in rows]

    def imported_movement(self, import_id: int):
        # Antes esta función cargaba y parseaba TODA la bandeja para encontrar
        # una sola fila. Con 100+ movimientos de Mercado Pago cada doble clic
        # podía sentirse lento. Ahora hace una consulta puntual por PK.
        with self.connect() as con:
            row = con.execute(
                """
                SELECT i.*, a.name account_name,
                       c.name category_name, p.name parent_category_name,
                       COALESCE(p.color,c.color,'#94A3B8') category_color,
                       COALESCE(p.icon,c.icon,'other') category_icon
                FROM imported_movements i
                JOIN accounts a ON a.id=i.account_id
                LEFT JOIN categories c ON c.id=i.category_id
                LEFT JOIN categories p ON p.id=c.parent_id
                WHERE i.id=?
                """,
                (int(import_id),),
            ).fetchone()
        return self._enrich_import_row(dict(row) if row else None)

    def pending_import_count(self) -> int:
        with self.connect() as con:
            return int(con.execute("SELECT COUNT(*) FROM imported_movements WHERE status='pending'").fetchone()[0])

    def update_import_category(self, import_id: int, category_id: int | None):
        with self.connect() as con:
            con.execute("UPDATE imported_movements SET category_id=? WHERE id=?", (category_id, int(import_id)))

    def ignore_import(self, import_id: int):
        with self.connect() as con:
            con.execute("UPDATE imported_movements SET status='ignored' WHERE id=?", (int(import_id),))

    def ignore_imports(self, import_ids: list[int]) -> int:
        ids = [int(x) for x in import_ids if x is not None]
        if not ids:
            return 0
        marks = ",".join("?" for _ in ids)
        with self.connect() as con:
            cur = con.execute(
                f"UPDATE imported_movements SET status='ignored' WHERE status='pending' AND id IN ({marks})",
                ids,
            )
            return int(cur.rowcount or 0)

    def delete_pending_scanned_imports(self) -> int:
        """Elimina sólo lecturas OCR todavía pendientes, nunca movimientos ya aceptados.

        Sirve para limpiar una lectura fallida y volver a analizar el mismo resumen con
        un parser mejor sin tocar Mercado Pago ni datos definitivos.
        """
        with self.connect() as con:
            cur = con.execute(
                "DELETE FROM imported_movements WHERE status='pending' AND source IN ('receipt_scan','statement_scan')"
            )
            return int(cur.rowcount or 0)

    def delete_pending_imports(self, group: str = "all") -> int:
        """Limpia la bandeja sin tocar movimientos ya aceptados."""
        group = (group or "all").lower()
        with self.connect() as con:
            if group == "mercado_pago":
                cur = con.execute("DELETE FROM imported_movements WHERE status='pending' AND source='mercado_pago'")
            elif group == "ocr":
                cur = con.execute("DELETE FROM imported_movements WHERE status='pending' AND source IN ('receipt_scan','statement_scan')")
            else:
                cur = con.execute("DELETE FROM imported_movements WHERE status='pending'")
            return int(cur.rowcount or 0)

    def pending_import_counts(self) -> dict[str, int]:
        with self.connect() as con:
            rows = con.execute(
                """
                SELECT source,COUNT(*) n FROM imported_movements
                WHERE status='pending' GROUP BY source
                """
            ).fetchall()
        out = {str(r["source"]): int(r["n"] or 0) for r in rows}
        out["all"] = sum(out.values())
        out["ocr"] = out.get("receipt_scan",0) + out.get("statement_scan",0)
        return out

    def accept_import(self, import_id: int, kind: str | None = None, category_id: int | None = None,
                      description: str | None = None, remember_rule: bool = False,
                      transfer_account_id: int | None = None):
        row = self.imported_movement(import_id)
        if not row or row["status"] != "pending":
            return None
        final_kind = kind if kind in {"expense","income","transfer"} else row["kind"]
        final_category = category_id or row.get("category_id")
        final_description = (description if description is not None else row.get("description") or "").strip()

        if final_kind == "transfer":
            if not transfer_account_id:
                raise ValueError("Elegí la otra cuenta de la transferencia.")
            imported_account = int(row["account_id"])
            other_account = int(transfer_account_id)
            if imported_account == other_account:
                raise ValueError("La otra cuenta debe ser distinta de Mercado Pago.")
            # Si el reporte muestra una salida, Mercado Pago es origen. Si
            # muestra una entrada, Mercado Pago es destino.
            if row["kind"] == "income":
                account_id, to_account_id = other_account, imported_account
            else:
                account_id, to_account_id = imported_account, other_account
            final_category = None
        else:
            if not final_category:
                raise ValueError("Elegí una categoría antes de guardar el movimiento.")
            account_id = int(row["account_id"])
            to_account_id = None

        data = {
            "kind": final_kind,
            "amount": float(row["amount"]),
            "account_id": account_id,
            "to_account_id": to_account_id,
            "category_id": int(final_category) if final_category else None,
            "tx_date": row["tx_date"],
            "description": final_description,
            "note": "",
            "tags": "importado",
        }
        try:
            tx_id = self.add_transaction(data, source=row["source"], external_id=row["external_id"])
        except sqlite3.IntegrityError:
            # Si el movimiento ya llegó a la tabla final, no lo duplicamos.
            with self.connect() as con:
                existing = con.execute(
                    "SELECT id FROM transactions WHERE source=? AND external_id=?",
                    (row["source"], row["external_id"]),
                ).fetchone()
            tx_id = int(existing[0]) if existing else None
        with self.connect() as con:
            con.execute(
                "UPDATE imported_movements SET status='imported',category_id=?,transaction_id=? WHERE id=?",
                (int(final_category) if final_category else None, tx_id, int(import_id)),
            )

        # Los resúmenes de tarjeta suelen traer algo como "C. 06/12". Desde
        # v0.18 esa información no queda sólo como texto del OCR: si el
        # movimiento fue aceptado en una cuenta Tarjeta, lo incorporamos al
        # apartado Cuotas empezando exactamente en la cuota detectada.
        if tx_id and final_kind == "expense" and row.get("source") == "statement_scan":
            try:
                raw = row.get("raw") or json.loads(row.get("raw_json") or "{}")
            except Exception:
                raw = {}
            try:
                current = int(raw.get("installment_current") or 0)
                total = int(raw.get("installment_total") or 0)
            except Exception:
                current = total = 0
            if total > 1 and 1 <= current <= total:
                try:
                    account = self.account(int(row["account_id"]))
                    tx = self.transaction(int(tx_id))
                    if account and account.get("type") == "Tarjeta" and tx and not tx.get("installment_plan_id"):
                        self.configure_existing_installment(int(tx_id), current, total, int(row["account_id"]))
                except Exception:
                    # La importación principal no debe fallar sólo porque un
                    # dato de cuotas leído por OCR sea inconsistente.
                    pass
        if remember_rule and final_kind != "transfer" and final_description and final_category:
            self.add_import_rule(row["source"], final_description, final_kind, int(final_category))
        return tx_id

    def accept_categorized_imports(self):
        count = 0
        for row in self.imported_movements("pending"):
            if row.get("category_id"):
                try:
                    self.accept_import(int(row["id"]), category_id=int(row["category_id"]))
                    count += 1
                except Exception:
                    pass
        return count
