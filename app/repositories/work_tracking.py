from __future__ import annotations

from calendar import monthrange
from datetime import date
from typing import Any

from ..work_calendar import week_end


class WorkTrackingMixin:
    """Persistencia del dominio Viajes, Extras y kilometraje."""

    def work_trip(self, trip_id: int):
        """Devuelve un viaje con sus destinos ordenados."""
        with self.connect() as con:
            row = con.execute("SELECT * FROM work_trips WHERE id=?", (int(trip_id),)).fetchone()
            if not row:
                return None
            item = dict(row)
            item["destinations"] = [
                r["destination"]
                for r in con.execute(
                    "SELECT destination FROM work_trip_destinations WHERE trip_id=? ORDER BY position,id",
                    (int(trip_id),),
                ).fetchall()
            ]
            item["custom_fields"] = self.work_trip_custom_values(int(trip_id))
            if item.get("rate_scheme_id"):
                scheme = con.execute("SELECT * FROM work_rate_schemes WHERE id=?", (int(item["rate_scheme_id"]),)).fetchone()
                item["rate_scheme"] = dict(scheme) if scheme else None
                if item.get("rate_option_id"):
                    option = con.execute("SELECT * FROM work_rate_options WHERE id=?", (int(item["rate_option_id"]),)).fetchone()
                    item["rate_option"] = dict(option) if option else None
            return item

    def work_trips_for_week(self, week: str | date, search: str = "", flag: str | None = None):
        """Lista viajes de una semana con filtros de campos configurables."""
        week_start = self._work_week_start(week)
        flag = (flag or "").strip()
        builtin_where = {
            "bulky": "bulky=1",
            "rain": "rain=1",
            "flex": "flex=1",
            "own_client": "own_client=1",
            "multi_stop": "stop_count > 1",
        }.get(flag)
        where = "week_start=?" + (f" AND {builtin_where}" if builtin_where else "")
        params: list[Any] = [week_start]
        custom_field_id: int | None = None
        if flag.startswith("custom:"):
            try:
                custom_field_id = int(flag.split(":", 1)[1])
            except (TypeError, ValueError):
                custom_field_id = None

        with self.connect() as con:
            rows = self._rows(con.execute(
                f"SELECT * FROM work_trips WHERE {where} ORDER BY date(trip_date),id",
                params,
            ).fetchall())
            if custom_field_id:
                allowed = {
                    int(r[0]) for r in con.execute(
                        """
                        SELECT trip_id FROM work_trip_field_values
                        WHERE field_id=? AND value_bool=1
                        """,
                        (custom_field_id,),
                    ).fetchall()
                }
                rows = [item for item in rows if int(item["id"]) in allowed]
            for item in rows:
                trip_id = int(item["id"])
                item["destinations"] = [
                    r["destination"]
                    for r in con.execute(
                        "SELECT destination FROM work_trip_destinations WHERE trip_id=? ORDER BY position,id",
                        (trip_id,),
                    ).fetchall()
                ]
                item["custom_fields"] = self.work_trip_custom_values(trip_id)
                if item.get("rate_scheme_id"):
                    scheme = con.execute("SELECT * FROM work_rate_schemes WHERE id=?", (int(item["rate_scheme_id"]),)).fetchone()
                    item["rate_scheme"] = dict(scheme) if scheme else None
                    if item.get("rate_option_id"):
                        option = con.execute("SELECT * FROM work_rate_options WHERE id=?", (int(item["rate_option_id"]),)).fetchone()
                        item["rate_option"] = dict(option) if option else None

        query = (search or "").strip().casefold()
        if not query:
            return rows
        definitions = {int(d["id"]): d for d in self.work_field_definitions()}
        result = []
        for item in rows:
            custom_bits = []
            for field_id, value in (item.get("custom_fields") or {}).items():
                definition = definitions.get(int(field_id), {})
                custom_bits.extend([str(definition.get("label") or ""), str(value or "")])
            haystack = "\n".join([
                str(item.get("client") or ""),
                str(item.get("origin") or ""),
                *[str(x) for x in item.get("destinations", [])],
                str(item.get("details") or ""),
                str(item.get("trip_date") or ""),
                *custom_bits,
            ]).casefold()
            if query in haystack:
                result.append(item)
        return result

    @staticmethod
    def _validated_work_trip(data: dict) -> tuple[str, str, list[str], int]:
        """Valida los campos estructurales compartidos por alta y edición."""
        trip_date = str(data.get("trip_date") or "").strip()
        client = str(data.get("client") or "").strip()
        if not client:
            raise ValueError("Ingresá el cliente.")
        date.fromisoformat(trip_date)
        destinations = [str(x).strip() for x in data.get("destinations", []) if str(x).strip()]
        raw_stop_count = data.get("stop_count")
        try:
            stop_count = int(raw_stop_count or len(destinations) or 1)
        except (TypeError, ValueError) as exc:
            raise ValueError("La cantidad de paradas debe ser un número entero.") from exc
        stop_count = max(1, stop_count, len(destinations))
        return trip_date, client, destinations, stop_count

    def add_work_trip(self, data: dict) -> int:
        trip_date, client, destinations, stop_count = self._validated_work_trip(data)
        with self.connect() as con:
            cur = con.execute(
                """
                INSERT INTO work_trips(
                    client,origin,trip_date,week_start,trip_count,stop_count,bulky,rain,flex,own_client,
                    details,charged,rate_scheme_id,rate_quantity,rate_option_id,calculated_price,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
                """,
                (
                    client, str(data.get("origin") or "").strip(), trip_date,
                    self._work_week_start(trip_date), 1, stop_count, 1 if data.get("bulky") else 0,
                    1 if data.get("rain") else 0, 1 if data.get("flex") else 0,
                    1 if data.get("own_client") else 0,
                    str(data.get("details") or "").strip(), data.get("charged"),
                    data.get("rate_scheme_id"), data.get("rate_quantity"), data.get("rate_option_id"),
                    self.calculate_work_rate(data.get("rate_scheme_id"), data.get("rate_quantity"), data.get("rate_option_id")),
                ),
            )
            trip_id = int(cur.lastrowid)
            con.executemany(
                "INSERT INTO work_trip_destinations(trip_id,position,destination) VALUES(?,?,?)",
                [(trip_id, pos, destination) for pos, destination in enumerate(destinations)],
            )
            self._store_work_trip_custom_values(con, trip_id, data.get("custom_fields") or {})
            return trip_id

    def update_work_trip(self, trip_id: int, data: dict):
        """Actualiza un viaje sin borrar campos ocultos de la configuración.

        La UI puede ocultar campos configurables. Esos campos no aparecen en el
        formulario, por lo que una edición parcial no debe convertirlos en False
        ni borrar sus valores históricos. Los valores enviados explícitamente sí
        reemplazan a los anteriores, incluyendo cadenas vacías o checks en False.
        """
        trip_id = int(trip_id)
        current = self.work_trip(trip_id)
        if not current:
            raise ValueError("El viaje ya no existe.")
        trip_date, client, destinations, stop_count = self._validated_work_trip(data)

        builtin_values = {
            key: bool(data[key]) if key in data else bool(current.get(key))
            for key in ("bulky", "rain", "flex", "own_client")
        }
        custom_values = dict(current.get("custom_fields") or {})
        if "custom_fields" in data:
            custom_values.update(data.get("custom_fields") or {})

        rate_scheme_id = data.get("rate_scheme_id") if "rate_scheme_id" in data else current.get("rate_scheme_id")
        rate_quantity = data.get("rate_quantity") if "rate_quantity" in data else current.get("rate_quantity")
        rate_option_id = data.get("rate_option_id") if "rate_option_id" in data else current.get("rate_option_id")

        # ``calculated_price`` es un snapshot histórico. Editar el cliente o los
        # detalles de un viaje no debe aplicar retroactivamente una tarifa que
        # haya cambiado después. Sólo recalculamos si cambió el esquema/factor.
        same_rate_input = (
            rate_scheme_id == current.get("rate_scheme_id")
            and rate_option_id == current.get("rate_option_id")
            and (
                rate_quantity == current.get("rate_quantity")
                or (rate_quantity is not None and current.get("rate_quantity") is not None
                    and abs(float(rate_quantity) - float(current.get("rate_quantity"))) < 1e-9)
            )
        )
        if same_rate_input:
            calculated_price = current.get("calculated_price")
        else:
            calculated_price = self.calculate_work_rate(rate_scheme_id, rate_quantity, rate_option_id)

        with self.connect() as con:
            con.execute(
                """
                UPDATE work_trips SET
                    client=?,origin=?,trip_date=?,week_start=?,trip_count=1,stop_count=?,bulky=?,rain=?,flex=?,own_client=?,
                    details=?,charged=?,rate_scheme_id=?,rate_quantity=?,rate_option_id=?,calculated_price=?,updated_at=CURRENT_TIMESTAMP
                WHERE id=?
                """,
                (
                    client, str(data.get("origin") or "").strip(), trip_date,
                    self._work_week_start(trip_date), stop_count, 1 if builtin_values["bulky"] else 0,
                    1 if builtin_values["rain"] else 0, 1 if builtin_values["flex"] else 0,
                    1 if builtin_values["own_client"] else 0,
                    str(data.get("details") or "").strip(), data.get("charged"),
                    rate_scheme_id, rate_quantity, rate_option_id, calculated_price,
                    trip_id,
                ),
            )
            con.execute("DELETE FROM work_trip_destinations WHERE trip_id=?", (trip_id,))
            con.executemany(
                "INSERT INTO work_trip_destinations(trip_id,position,destination) VALUES(?,?,?)",
                [(trip_id, pos, destination) for pos, destination in enumerate(destinations)],
            )
            self._store_work_trip_custom_values(con, trip_id, custom_values)

    def delete_work_trip(self, trip_id: int):
        with self.connect() as con:
            con.execute("DELETE FROM work_trips WHERE id=?", (int(trip_id),))

    def work_week_summary(self, week: str | date):
        """Resume una semana de trabajo con unidades explícitas por métrica.

        Viajes, Bulto, Lluvia y Cliente propio cuentan recorridos. ``flex`` es
        distinto por decisión de producto: cuenta *paradas Flex*, por lo que un
        único viaje Flex con cinco destinos aporta 5 al total Flex.
        """
        week_start = self._work_week_start(week)
        with self.connect() as con:
            row = con.execute(
                """
                SELECT
                    COUNT(*) entries,
                    COUNT(*) trips,
                    COALESCE(SUM(stop_count),0) stops,
                    COALESCE(SUM(CASE WHEN bulky=1 THEN 1 ELSE 0 END),0) bulky,
                    COALESCE(SUM(CASE WHEN rain=1 THEN 1 ELSE 0 END),0) rain,
                    COALESCE(SUM(CASE WHEN flex=1 THEN stop_count ELSE 0 END),0) flex,
                    COALESCE(SUM(CASE WHEN own_client=1 THEN 1 ELSE 0 END),0) own_client,
                    COALESCE(SUM(CASE WHEN stop_count > 1 THEN 1 ELSE 0 END),0) multi_stop,
                    COALESCE(SUM(charged),0) charged
                FROM work_trips WHERE week_start=?
                """,
                (week_start,),
            ).fetchone()
        return {
            "entries": int(row["entries"] or 0),
            "trips": int(row["trips"] or 0),
            "stops": int(row["stops"] or 0),
            "bulky": int(row["bulky"] or 0),
            "rain": int(row["rain"] or 0),
            "flex": int(row["flex"] or 0),
            "own_client": int(row["own_client"] or 0),
            "multi_stop": int(row["multi_stop"] or 0),
            "charged": float(row["charged"] or 0),
        }

    def _work_summary_between(self, start_date: date, end_date: date) -> dict:
        """Resume Viajes y kilometraje dentro de un rango inclusivo.

        Se usa para el resumen mensual. Trabajar por fecha real (en lugar de
        sumar semanas completas) evita atribuir al mes actual días pertenecientes
        al mes anterior/siguiente cuando una semana cruza el cambio de mes.
        """
        start = start_date.isoformat()
        end = end_date.isoformat()
        with self.connect() as con:
            trips = con.execute(
                """
                SELECT
                    COUNT(*) trips,
                    COALESCE(SUM(stop_count),0) stops,
                    COALESCE(SUM(CASE WHEN bulky=1 THEN 1 ELSE 0 END),0) bulky,
                    COALESCE(SUM(CASE WHEN rain=1 THEN 1 ELSE 0 END),0) rain,
                    COALESCE(SUM(CASE WHEN flex=1 THEN stop_count ELSE 0 END),0) flex,
                    COALESCE(SUM(CASE WHEN own_client=1 THEN 1 ELSE 0 END),0) own_client,
                    COALESCE(SUM(charged),0) charged
                FROM work_trips
                WHERE trip_date BETWEEN ? AND ?
                """,
                (start, end),
            ).fetchone()
            mileage = con.execute(
                """
                SELECT
                    COALESCE(SUM(
                        CASE WHEN odometer_start IS NOT NULL AND odometer_end IS NOT NULL
                             THEN odometer_end - odometer_start ELSE 0 END
                    ),0) real_km,
                    COALESCE(SUM(
                        CASE WHEN odometer_start IS NOT NULL AND odometer_end IS NOT NULL
                             THEN 1 ELSE 0 END
                    ),0) completed_days
                FROM work_day_mileage
                WHERE work_date BETWEEN ? AND ?
                """,
                (start, end),
            ).fetchone()
        return {
            "trips": int(trips["trips"] or 0),
            "stops": int(trips["stops"] or 0),
            "bulky": int(trips["bulky"] or 0),
            "rain": int(trips["rain"] or 0),
            "flex": int(trips["flex"] or 0),
            "own_client": int(trips["own_client"] or 0),
            "charged": float(trips["charged"] or 0),
            "real_km": float(mileage["real_km"] or 0),
            "completed_days": int(mileage["completed_days"] or 0),
        }

    def work_month_summary(self, year: int, month: int) -> dict:
        """Totales de Viajes para un mes calendario."""
        year = int(year)
        month = int(month)
        last_day = monthrange(year, month)[1]
        return self._work_summary_between(date(year, month, 1), date(year, month, last_day))

    def work_month_week_summaries(self, year: int, month: int) -> list[dict]:
        """Desglosa un mes por semanas laborales sin duplicar días limítrofes."""
        year = int(year)
        month = int(month)
        first = date(year, month, 1)
        last = date(year, month, monthrange(year, month)[1])
        with self.connect() as con:
            rows = con.execute(
                """
                SELECT week_start FROM work_trips
                WHERE trip_date BETWEEN ? AND ?
                UNION
                SELECT week_start FROM work_day_mileage
                WHERE work_date BETWEEN ? AND ?
                ORDER BY week_start
                """,
                (first.isoformat(), last.isoformat(), first.isoformat(), last.isoformat()),
            ).fetchall()
        result: list[dict] = []
        for row in rows:
            week_start = date.fromisoformat(str(row["week_start"]))
            segment_start = max(first, week_start)
            segment_end = min(last, week_end(week_start))
            summary = self._work_summary_between(segment_start, segment_end)
            summary.update({
                "week_start": week_start.isoformat(),
                "period_start": segment_start.isoformat(),
                "period_end": segment_end.isoformat(),
            })
            result.append(summary)
        return result

    def work_day_mileage(self, work_date: str | date):
        day = work_date.isoformat() if isinstance(work_date, date) else str(work_date)
        date.fromisoformat(day)
        with self.connect() as con:
            row = con.execute("SELECT * FROM work_day_mileage WHERE work_date=?", (day,)).fetchone()
            return dict(row) if row else None

    def work_last_odometer_end_before(self, work_date: str | date) -> float | None:
        """Última lectura final disponible antes de ``work_date``.

        Se usa para precargar el KM inicial de una jornada con el cierre de la
        jornada anterior. Buscar hacia atrás (en lugar de asumir "ayer") hace
        que también funcione de viernes a lunes o cuando hubo días sin trabajo.
        """
        day = work_date.isoformat() if isinstance(work_date, date) else str(work_date)
        date.fromisoformat(day)
        with self.connect() as con:
            row = con.execute(
                """
                SELECT odometer_end
                FROM work_day_mileage
                WHERE work_date < ? AND odometer_end IS NOT NULL
                ORDER BY work_date DESC
                LIMIT 1
                """,
                (day,),
            ).fetchone()
        return float(row["odometer_end"]) if row and row["odometer_end"] is not None else None

    def work_mileage_for_week(self, week: str | date) -> list[dict]:
        week_start = self._work_week_start(week)
        with self.connect() as con:
            rows = self._rows(con.execute(
                "SELECT * FROM work_day_mileage WHERE week_start=? ORDER BY work_date",
                (week_start,),
            ).fetchall())
        for row in rows:
            start = row.get("odometer_start")
            end = row.get("odometer_end")
            row["real_km"] = (
                max(0.0, float(end) - float(start))
                if start is not None and end is not None
                else None
            )
        return rows

    def work_week_mileage_summary(self, week: str | date) -> dict:
        """Resume únicamente el kilometraje real de una semana laboral."""
        week_start = self._work_week_start(week)
        with self.connect() as con:
            real = con.execute(
                """
                SELECT
                    COALESCE(SUM(
                        CASE WHEN odometer_start IS NOT NULL AND odometer_end IS NOT NULL
                             THEN odometer_end - odometer_start ELSE 0 END
                    ),0) real_km,
                    COALESCE(SUM(
                        CASE WHEN odometer_start IS NOT NULL AND odometer_end IS NOT NULL
                             THEN 1 ELSE 0 END
                    ),0) completed_days
                FROM work_day_mileage WHERE week_start=?
                """,
                (week_start,),
            ).fetchone()
        return {
            "real_km": float(real["real_km"] or 0),
            "completed_days": int(real["completed_days"] or 0),
        }

    def work_available_weeks(self):
        with self.connect() as con:
            rows = con.execute(
                """
                SELECT week_start FROM work_trips
                UNION
                SELECT week_start FROM work_extras
                UNION
                SELECT week_start FROM work_services
                UNION
                SELECT week_start FROM work_day_mileage
                ORDER BY week_start DESC
                """
            ).fetchall()
            return [str(r["week_start"]) for r in rows]

    def work_extra(self, extra_id: int):
        with self.connect() as con:
            row = con.execute("SELECT * FROM work_extras WHERE id=?", (int(extra_id),)).fetchone()
            return dict(row) if row else None

    def work_extras_for_week(self, week: str | date):
        week_start = self._work_week_start(week)
        with self.connect() as con:
            return self._rows(con.execute(
                "SELECT * FROM work_extras WHERE week_start=? ORDER BY date(work_date),id",
                (week_start,),
            ).fetchall())

    def work_extra_apps(self) -> list[str]:
        """Nombres de apps ya usadas, útiles para autocompletar el formulario."""
        with self.connect() as con:
            rows = con.execute(
                "SELECT DISTINCT trim(app_name) app_name FROM work_extras WHERE trim(app_name)<>'' ORDER BY lower(app_name)"
            ).fetchall()
        return [str(r["app_name"]) for r in rows]

    @staticmethod
    def _validated_work_extra(data: dict) -> tuple[str, str, float, int, float]:
        work_date = str(data.get("work_date") or "").strip()
        app_name = str(data.get("app_name") or "").strip()
        if not app_name:
            raise ValueError("Ingresá la aplicación.")
        date.fromisoformat(work_date)
        hours = max(0.0, float(data.get("hours") or 0))
        orders = max(0, int(data.get("orders") or 0))
        amount = max(0.0, float(data.get("amount") or 0))
        return work_date, app_name, hours, orders, amount

    def add_work_extra(self, data: dict) -> int:
        work_date, app_name, hours, orders, amount = self._validated_work_extra(data)
        with self.connect() as con:
            cur = con.execute(
                """
                INSERT INTO work_extras(app_name,work_date,week_start,hours,orders,amount,details,updated_at)
                VALUES(?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
                """,
                (
                    app_name, work_date, self._work_week_start(work_date), hours, orders, amount,
                    str(data.get("details") or "").strip(),
                ),
            )
            return int(cur.lastrowid)

    def update_work_extra(self, extra_id: int, data: dict):
        work_date, app_name, hours, orders, amount = self._validated_work_extra(data)
        with self.connect() as con:
            con.execute(
                """
                UPDATE work_extras SET app_name=?,work_date=?,week_start=?,hours=?,orders=?,amount=?,details=?,
                    updated_at=CURRENT_TIMESTAMP WHERE id=?
                """,
                (
                    app_name, work_date, self._work_week_start(work_date), hours, orders, amount,
                    str(data.get("details") or "").strip(), int(extra_id),
                ),
            )

    def delete_work_extra(self, extra_id: int):
        with self.connect() as con:
            con.execute("DELETE FROM work_extras WHERE id=?", (int(extra_id),))

    def work_extra_week_summary(self, week: str | date) -> dict[str, float | int]:
        week_start = self._work_week_start(week)
        with self.connect() as con:
            row = con.execute(
                """
                SELECT COUNT(*) entries,COALESCE(SUM(hours),0) hours,COALESCE(SUM(orders),0) orders,
                       COALESCE(SUM(amount),0) amount
                FROM work_extras WHERE week_start=?
                """,
                (week_start,),
            ).fetchone()
        return {
            "entries": int(row["entries"] or 0),
            "hours": float(row["hours"] or 0),
            "orders": int(row["orders"] or 0),
            "amount": float(row["amount"] or 0),
        }

    def set_work_day_mileage(
        self,
        work_date: str | date,
        odometer_start: float | None,
        odometer_end: float | None,
        notes: str = "",
    ) -> None:
        day = work_date.isoformat() if isinstance(work_date, date) else str(work_date)
        date.fromisoformat(day)
        start = None if odometer_start is None else float(odometer_start)
        end = None if odometer_end is None else float(odometer_end)
        if start is not None and start < 0:
            raise ValueError("El kilometraje inicial no puede ser negativo.")
        if end is not None and end < 0:
            raise ValueError("El kilometraje final no puede ser negativo.")
        if start is not None and end is not None and end < start:
            raise ValueError("El kilometraje final no puede ser menor al inicial.")
        week_start = self._work_week_start(day)
        with self.connect() as con:
            con.execute(
                """
                INSERT INTO work_day_mileage(
                    work_date,week_start,odometer_start,odometer_end,notes,updated_at
                ) VALUES(?,?,?,?,?,CURRENT_TIMESTAMP)
                ON CONFLICT(work_date) DO UPDATE SET
                    week_start=excluded.week_start,
                    odometer_start=excluded.odometer_start,
                    odometer_end=excluded.odometer_end,
                    notes=excluded.notes,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (day, week_start, start, end, (notes or "").strip()),
            )
