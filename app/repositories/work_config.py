from __future__ import annotations

"""Persistencia de configuración editable para la herramienta Viajes.

Se mantiene fuera de ``db.py`` para que campos dinámicos y tarifas puedan
evolucionar sin agrandar el repositorio financiero principal. El mixin usa la
conexión/serialización que provee :class:`app.db.Database`.
"""

import json
import re
import sqlite3

from ..work_calendar import week_end
from datetime import date


class WorkConfigMixin:
    def _seed_work_field_definitions(self, con: sqlite3.Connection) -> None:
        """Crea la configuración editable de campos de Viajes.

        Los cuatro campos históricos siguen usando columnas nativas por
        compatibilidad y velocidad, pero su etiqueta/visibilidad/orden vive en
        la misma definición que los campos personalizados. Así la UI no queda
        acoplada a nombres elegidos durante el desarrollo.
        """
        defaults = [
            ("bulky", "Bulto", "check", "bulky", 1, 0),
            ("rain", "Lluvia", "check", "rain", 1, 1),
            ("flex", "Flex", "check", "flex", 1, 2),
            ("own_client", "Cliente propio", "check", "own_client", 1, 3),
        ]
        for key, label, field_type, built_in_key, show_in_summary, sort_order in defaults:
            con.execute(
                """
                INSERT OR IGNORE INTO work_field_definitions(
                    key,label,field_type,built_in_key,active,show_in_summary,sort_order
                ) VALUES(?,?,?,?,1,?,?)
                """,
                (key, label, field_type, built_in_key, show_in_summary, sort_order),
            )

    # ---------- configuración flexible de Viajes ----------
    def work_field_definitions(self, active_only: bool = False) -> list[dict]:
        sql = "SELECT * FROM work_field_definitions"
        if active_only:
            sql += " WHERE active=1"
        sql += " ORDER BY sort_order,id"
        with self.connect() as con:
            rows = self._rows(con.execute(sql).fetchall())
        for row in rows:
            row["ui_type"] = str(row.get("ui_type") or row.get("field_type") or "text")
            try:
                row["options"] = json.loads(row.get("options_json") or "[]")
            except Exception:
                row["options"] = []
            if not isinstance(row["options"], list):
                row["options"] = []
        return rows

    def save_work_field_definition(self, data: dict, field_id: int | None = None) -> int:
        """Crea o actualiza un campo configurable de Viajes."""
        label = str(data.get("label") or "").strip()
        if not label:
            raise ValueError("Ingresá un nombre para el campo.")
        ui_type = str(data.get("ui_type") or data.get("field_type") or "text").strip()
        allowed_ui = {"check", "text", "long_text", "email", "phone", "number", "money", "choice"}
        if ui_type not in allowed_ui:
            raise ValueError("Tipo de campo inválido.")
        field_type = ui_type if ui_type in {"check", "number", "money"} else "text"
        options = [str(value).strip() for value in (data.get("options") or []) if str(value).strip()]
        if ui_type == "choice" and not options:
            raise ValueError("Agregá al menos una opción al campo desplegable.")
        active = 1 if data.get("active", True) else 0
        show = 1 if data.get("show_in_summary", field_type == "check") else 0
        with self.connect() as con:
            if field_id:
                current = con.execute("SELECT * FROM work_field_definitions WHERE id=?", (int(field_id),)).fetchone()
                if not current:
                    raise ValueError("El campo ya no existe.")
                # Los campos nativos mantienen su tipo para no romper datos históricos.
                if current["built_in_key"]:
                    field_type = str(current["field_type"])
                    ui_type = str(current["field_type"])
                elif field_type != str(current["field_type"]):
                    used = int(con.execute(
                        "SELECT COUNT(*) FROM work_trip_field_values WHERE field_id=?",
                        (int(field_id),),
                    ).fetchone()[0] or 0)
                    if used:
                        raise ValueError(
                            "No se puede cambiar el tipo de un campo que ya tiene datos. "
                            "Creá un campo nuevo y ocultá el anterior para conservar el historial."
                        )
                con.execute(
                    """
                    UPDATE work_field_definitions
                    SET label=?,field_type=?,ui_type=?,options_json=?,active=?,show_in_summary=?,updated_at=CURRENT_TIMESTAMP
                    WHERE id=?
                    """,
                    (label, field_type, ui_type, json.dumps(options, ensure_ascii=False), active, show, int(field_id)),
                )
                return int(field_id)
            order = int(con.execute("SELECT COALESCE(MAX(sort_order),-1)+1 FROM work_field_definitions").fetchone()[0])
            base = re.sub(r"[^a-z0-9]+", "_", label.casefold()).strip("_") or "campo"
            key = base
            suffix = 2
            while con.execute("SELECT 1 FROM work_field_definitions WHERE key=?", (key,)).fetchone():
                key = f"{base}_{suffix}"
                suffix += 1
            cur = con.execute(
                """
                INSERT INTO work_field_definitions(key,label,field_type,ui_type,options_json,active,show_in_summary,sort_order)
                VALUES(?,?,?,?,?,?,?,?)
                """,
                (key, label, field_type, ui_type, json.dumps(options, ensure_ascii=False), active, show, order),
            )
            return int(cur.lastrowid)

    def delete_work_field_definition(self, field_id: int) -> None:
        """Elimina un campo sin destruir valores históricos ya cargados.

        Si el campo personalizado fue usado en algún viaje, se desactiva en
        lugar de borrarlo. Esto mantiene legible el historial y evita que una
        decisión de configuración borre datos silenciosamente.
        """
        with self.connect() as con:
            row = con.execute("SELECT built_in_key FROM work_field_definitions WHERE id=?", (int(field_id),)).fetchone()
            if not row:
                return
            if row["built_in_key"]:
                raise ValueError("Los campos base no se eliminan; podés ocultarlos o cambiarles el nombre.")
            used = int(con.execute(
                "SELECT COUNT(*) FROM work_trip_field_values WHERE field_id=?",
                (int(field_id),),
            ).fetchone()[0] or 0)
            if used:
                con.execute(
                    "UPDATE work_field_definitions SET active=0,show_in_summary=0,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (int(field_id),),
                )
            else:
                con.execute("DELETE FROM work_field_definitions WHERE id=?", (int(field_id),))

    def reorder_work_fields(self, ordered_ids: list[int]) -> None:
        with self.connect() as con:
            for order, field_id in enumerate(ordered_ids):
                con.execute("UPDATE work_field_definitions SET sort_order=? WHERE id=?", (order, int(field_id)))

    def work_trip_custom_values(self, trip_id: int) -> dict[int, object]:
        with self.connect() as con:
            rows = con.execute(
                """
                SELECT v.*, f.field_type FROM work_trip_field_values v
                JOIN work_field_definitions f ON f.id=v.field_id
                WHERE v.trip_id=?
                """,
                (int(trip_id),),
            ).fetchall()
        result: dict[int, object] = {}
        for row in rows:
            field_id = int(row["field_id"])
            if row["field_type"] == "check":
                result[field_id] = bool(row["value_bool"])
            elif row["field_type"] in {"number", "money"}:
                result[field_id] = row["value_number"]
            else:
                result[field_id] = row["value_text"] or ""
        return result

    def _store_work_trip_custom_values(self, con: sqlite3.Connection, trip_id: int, values: dict) -> None:
        con.execute("DELETE FROM work_trip_field_values WHERE trip_id=?", (int(trip_id),))
        definitions = {
            int(row["id"]): dict(row)
            for row in con.execute("SELECT * FROM work_field_definitions WHERE built_in_key IS NULL").fetchall()
        }
        for raw_id, value in (values or {}).items():
            try:
                field_id = int(raw_id)
            except (TypeError, ValueError):
                continue
            definition = definitions.get(field_id)
            if not definition:
                continue
            field_type = definition["field_type"]
            value_text = value_number = value_bool = None
            if field_type == "check":
                value_bool = 1 if bool(value) else 0
            elif field_type in {"number", "money"}:
                if value not in (None, ""):
                    value_number = float(value)
            else:
                value_text = str(value or "").strip()
            con.execute(
                """
                INSERT INTO work_trip_field_values(trip_id,field_id,value_text,value_number,value_bool)
                VALUES(?,?,?,?,?)
                """,
                (int(trip_id), field_id, value_text, value_number, value_bool),
            )

    def work_field_counts_between(self, start_date: str | date, end_date: str | date) -> dict[int, float]:
        """Conteos de campos checkbox para un rango calendario inclusive."""
        start = start_date.isoformat() if isinstance(start_date, date) else str(start_date)[:10]
        end = end_date.isoformat() if isinstance(end_date, date) else str(end_date)[:10]
        date.fromisoformat(start); date.fromisoformat(end)
        definitions = self.work_field_definitions(active_only=True)
        result: dict[int, float] = {}
        with self.connect() as con:
            for definition in definitions:
                if definition["field_type"] != "check" or not definition.get("show_in_summary"):
                    continue
                field_id = int(definition["id"])
                built_in = definition.get("built_in_key")
                if built_in in {"bulky", "rain", "own_client"}:
                    value = con.execute(
                        f"SELECT COUNT(*) FROM work_trips WHERE date(trip_date) BETWEEN date(?) AND date(?) AND {built_in}=1",
                        (start, end),
                    ).fetchone()[0]
                elif built_in == "flex":
                    value = con.execute(
                        "SELECT COALESCE(SUM(stop_count),0) FROM work_trips WHERE date(trip_date) BETWEEN date(?) AND date(?) AND flex=1",
                        (start, end),
                    ).fetchone()[0]
                elif not built_in:
                    value = con.execute(
                        """
                        SELECT COUNT(*) FROM work_trip_field_values v
                        JOIN work_trips t ON t.id=v.trip_id
                        WHERE date(t.trip_date) BETWEEN date(?) AND date(?) AND v.field_id=? AND v.value_bool=1
                        """,
                        (start, end, field_id),
                    ).fetchone()[0]
                else:
                    value = 0
                result[field_id] = float(value or 0)
        return result

    def work_week_field_counts(self, week: str | date) -> dict[int, float]:
        """Conteos semanales de campos checkbox visibles en el resumen."""
        week_start = date.fromisoformat(self._work_week_start(week))
        return self.work_field_counts_between(week_start, week_end(week_start))

    # ---------- tarifas configurables de Viajes ----------
    def work_rate_schemes(self, active_only: bool = False) -> list[dict]:
        sql = "SELECT * FROM work_rate_schemes"
        if active_only:
            sql += " WHERE active=1"
        sql += " ORDER BY sort_order,id"
        with self.connect() as con:
            schemes = self._rows(con.execute(sql).fetchall())
            for scheme in schemes:
                scheme["options"] = self._rows(con.execute(
                    "SELECT * FROM work_rate_options WHERE scheme_id=? AND active=1 ORDER BY sort_order,id",
                    (int(scheme["id"]),),
                ).fetchall())
        return schemes

    def save_work_rate_scheme(self, data: dict, scheme_id: int | None = None) -> int:
        name = str(data.get("name") or "").strip()
        if not name:
            raise ValueError("Ingresá un nombre para la tarifa.")
        mode = str(data.get("mode") or "unit")
        if mode not in {"unit", "option"}:
            raise ValueError("Tipo de tarifa inválido.")
        unit_label = str(data.get("unit_label") or "unidad").strip()
        unit_rate = max(0.0, float(data.get("unit_rate") or 0))
        active = 1 if data.get("active", True) else 0
        options = list(data.get("options") or [])
        with self.connect() as con:
            if scheme_id:
                con.execute(
                    """
                    UPDATE work_rate_schemes SET name=?,mode=?,unit_label=?,unit_rate=?,active=?,updated_at=CURRENT_TIMESTAMP
                    WHERE id=?
                    """,
                    (name, mode, unit_label, unit_rate, active, int(scheme_id)),
                )
                sid = int(scheme_id)
            else:
                order = int(con.execute("SELECT COALESCE(MAX(sort_order),-1)+1 FROM work_rate_schemes").fetchone()[0])
                cur = con.execute(
                    "INSERT INTO work_rate_schemes(name,mode,unit_label,unit_rate,active,sort_order) VALUES(?,?,?,?,?,?)",
                    (name, mode, unit_label, unit_rate, active, order),
                )
                sid = int(cur.lastrowid)
            existing_options = self._rows(con.execute(
                "SELECT * FROM work_rate_options WHERE scheme_id=? ORDER BY sort_order,id", (sid,)
            ).fetchall())
            existing_by_label = {str(row.get("label") or "").strip().casefold(): row for row in existing_options}
            used_option_ids: set[int] = set()
            if mode == "option":
                for order, option in enumerate(options):
                    label = str(option.get("label") or "").strip()
                    if not label:
                        continue
                    rate = max(0.0, float(option.get("rate") or 0))
                    previous = existing_by_label.get(label.casefold())
                    if previous:
                        option_id = int(previous["id"])
                        con.execute(
                            "UPDATE work_rate_options SET label=?,rate=?,sort_order=?,active=1 WHERE id=?",
                            (label, rate, order, option_id),
                        )
                    else:
                        cur = con.execute(
                            "INSERT INTO work_rate_options(scheme_id,label,rate,sort_order,active) VALUES(?,?,?,?,1)",
                            (sid, label, rate, order),
                        )
                        option_id = int(cur.lastrowid)
                    used_option_ids.add(option_id)
            # Las opciones eliminadas se desactivan, no se borran: viajes viejos
            # pueden seguir referenciándolas y conservar su contexto histórico.
            for previous in existing_options:
                option_id = int(previous["id"])
                if option_id not in used_option_ids:
                    con.execute("UPDATE work_rate_options SET active=0 WHERE id=?", (option_id,))
            return sid

    def delete_work_rate_scheme(self, scheme_id: int) -> None:
        with self.connect() as con:
            used = con.execute("SELECT COUNT(*) FROM work_trips WHERE rate_scheme_id=?", (int(scheme_id),)).fetchone()[0]
            if used:
                con.execute("UPDATE work_rate_schemes SET active=0 WHERE id=?", (int(scheme_id),))
            else:
                con.execute("DELETE FROM work_rate_schemes WHERE id=?", (int(scheme_id),))

    def reorder_work_rate_schemes(self, ordered_ids: list[int]) -> None:
        with self.connect() as con:
            for order, scheme_id in enumerate(ordered_ids):
                con.execute("UPDATE work_rate_schemes SET sort_order=? WHERE id=?", (order, int(scheme_id)))

    def calculate_work_rate(self, scheme_id: int | None, quantity: float | None = None, option_id: int | None = None) -> float | None:
        if not scheme_id:
            return None
        with self.connect() as con:
            scheme = con.execute("SELECT * FROM work_rate_schemes WHERE id=?", (int(scheme_id),)).fetchone()
            if not scheme:
                return None
            if scheme["mode"] == "unit":
                return round(max(0.0, float(quantity or 0)) * float(scheme["unit_rate"] or 0), 2)
            if option_id:
                option = con.execute(
                    "SELECT rate FROM work_rate_options WHERE id=? AND scheme_id=?",
                    (int(option_id), int(scheme_id)),
                ).fetchone()
                return round(float(option["rate"] or 0), 2) if option else None
        return None

